"""The waste sector's uncertainty: the partition's coupling made explicit, the sewer
as a mixture, and the survey evidence priced as a named scenario.

WHY THE GROUPED APPROACH 1 EXISTS. The pooled national treatment combines the six
component uncertainties as if independent, but two of the sector's three categories are
built from ONE generation figure and ONE collection coverage. Those couplings pull in
opposite directions. The generation rates are shared POSITIVELY - if Pakistanis generate
more waste than the Pak-EPA rates say, disposal and burning are both underestimated at
once - which widens the sector band. The uncollected fractions are shared NEGATIVELY - a
tonne not collected is a tonne unavailable to the decay model and available to burn - so
the partition term partially cancels between 4A and 4C2, which narrows it. The grouped
figure carries both couplings analytically (shared terms linear with their signed
elasticities, residuals in quadrature); the independent figure is what the pooled
national Monte Carlo sees. Publishing both, with the decomposition, is the finding.

The grouping is computed HERE, analytically, rather than by stamping corr_group onto the
shipped components: the national pooled MC already carries waste in its seed-42 stream,
and changing the shipped rows would reorder every published national percentile
(core/montecarlo.py's own warning). SCENARIO_SEED keeps this module's draws on their
own stream - published in the paper and the output's seed column since rc12, because
"private" had come to mean unpublished and that made the intervals irreproducible.

THE SEWER AS A MIXTURE. The paper's central tension - IPCC 0.5 for stagnant open sewers
against 0.1 for river discharge - is physically a statement about weights, not about
which single row of Table 6.3 Pakistan occupies. Because Eq 6.1 is linear in the MCF,
any mixture w_stagnant*0.5 + w_flowing*0.1 + w_treated*MCF_treated is exactly a scalar
through the existing sewer_mcf override, so the mixture costs nothing to represent. The
weights are unmeasured: the configurations below are named structural scenarios with
conditional intervals, never a probability distribution over weights.

Usage:  python3 -m pkinv.sectors.waste.uncertainty
Writes: outputs/waste_uncertainty_2023.csv,
        outputs/waste_uncertainty_inputs_2023.csv,
        outputs/waste_uncertainty_scenarios_2023.csv
"""

from pkinv.assets import asset_path
import csv
import math
import os
import random

from pkinv.core import montecarlo as mc_core
from pkinv.core.uncertainty import combine_sum, product
from pkinv.paths import OUTPUTS
from pkinv.sectors.waste import engine, ledger, open_burning, swds, wastewater
from pkinv.sectors.waste.data import WasteData

SCENARIO_SEED = 4321          # PUBLISHED (paper S1 + the seed column); its own
                              # stream, so the national MC's seed 42 is untouched -
                              # separate, never secret
INTERPRETATION = "conditional parametric interval; no structural probability"

PARTITIONED = (swds.CATEGORY, open_burning.CATEGORY)

# Parameters drawn from their published BOUNDS instead of a symmetric percentage.
# The rc11 wastewater repair: ww_ef_effluent's stated range spans a factor of 500
# and an earlier edition priced it +/-100% - a 6.6-fold 95% span against the
# 500-fold evidence, which the seventh review rejected. A bounded parameter keeps
# the IPCC default as MODE AND MEDIAN and lets the published endpoints bound the
# draw; the mean sits above the deterministic value, which is what a long right
# tail means and is said rather than hidden.
BOUNDED_DRAW = ("ww_ef_effluent",
                # rc67, the 2019 Refinement's nitrogen account: each drawn over the range
                # its own table prints (Tables 6.8A, 6.10A, 6.10C), mode at the default.
                "ww_ef_plant_aerobic", "ww_nrem_secondary", "ww_nrem_septic",
                "ww_nrem_latrine", "ww_n_hh")


def bounded_log_split_triangular(u, low, mode, high):
    """Inverse CDF: two half-triangles in LOG space meeting at the mode.

    Exactly half the probability lies each side of the mode, so the mode is also
    the median; the density falls linearly (in log space) to zero at the published
    endpoints. The same shape as the fugitives sector's split triangular
    (fugitives/uncertainty._split_triangular_from_u), taken in log space because
    the bounds span orders of magnitude - a linear-space triangle over a 500-fold
    range would put most of its mass above the default.
    """
    llo, lmo, lhi = math.log(low), math.log(mode), math.log(high)
    if u < 0.5:
        return math.exp(llo + (lmo - llo) * math.sqrt(2.0 * u))
    return math.exp(lhi - (lhi - lmo) * math.sqrt(2.0 * (1.0 - u)))


def log_split_triangular_sigma(low, mode, high):
    """The log-space standard deviation of the split triangular, closed form.

    Each half is a right triangle peaked at the mode: variance (b-a)^2/18, mean
    a + 2(b-a)/3 toward the peak. Used to DECLARE an equivalent symmetric width
    (exp(1.96 sigma) - 1) for the quadrature and national streams that cannot carry
    an asymmetric shape - the honest degradation, stated on the row that uses it.
    """
    llo, lmo, lhi = math.log(low), math.log(mode), math.log(high)
    means = (llo + 2.0 * (lmo - llo) / 3.0, lhi - 2.0 * (lhi - lmo) / 3.0)
    variances = ((lmo - llo) ** 2 / 18.0, (lhi - lmo) ** 2 / 18.0)
    mixture_mean = 0.5 * (means[0] + means[1])
    second = 0.5 * ((variances[0] + means[0] ** 2) + (variances[1] + means[1] ** 2))
    return math.sqrt(second - mixture_mean ** 2)


def equivalent_bounded_uncert_pct(data, param):
    """The declared width whose lognormal carries the bounded draw's log-variance.

    The declared uncert_pct is CONSUMED through core.montecarlo.sigma_log, which
    moment-matches a lognormal to pct/1.96 as a coefficient of variation. So the
    honest symmetric declaration is the value that round-trips to the bounded
    shape's own log-sigma - about 401% for the effluent factor - not the 95%
    multiplicative span (about 1135%), which is quoted in prose as the span. Using
    the span here would make the national stream sample MORE log-variance than the
    bounded truth carries.
    """
    low, high = data.param_bounds[param]
    sigma = log_split_triangular_sigma(low, data.p(param), high)
    return 1.959964 * math.sqrt(math.exp(sigma * sigma) - 1.0) * 100.0


def bounded_span_pct(data, param):
    """The 95% multiplicative span of the bounded draw, exp(1.96 sigma) - 1, in
    percent - the number for prose, never for sigma_log consumption."""
    low, high = data.param_bounds[param]
    sigma = log_split_triangular_sigma(low, data.p(param), high)
    return (math.exp(1.959964 * sigma) - 1.0) * 100.0


def sewer_mcf_mixture(data, w_stagnant, w_flowing, w_treated=0.0):
    """The effective sewer MCF of a hydraulic-regime mixture. Exact, because Eq 6.1 is
    linear in the MCF: the mixture never needs a model change, only this scalar."""
    if abs(w_stagnant + w_flowing + w_treated - 1.0) > 1e-9:
        raise ValueError("mixture weights must sum to 1")
    return (w_stagnant * data.p("ww_mcf_sewer")
            + w_flowing * data.p("ww_mcf_sewer_river")
            + w_treated * data.p("ww_mcf_treated"))


def approach1(data):
    """Sector-total Approach 1: grouped (partition couplings shared) and independent.

    Shared terms across 4A and 4C2, per component category totals E:
      generation  u_gen = quadrature(population 5, gen_rate 40) - positive everywhere,
                  so it adds linearly across both categories;
      partition   u_unc = 30 on the uncollected fractions - elasticity +1 on burning
                  (B ~ u) and -u/(1-u) on disposal (D ~ 1-u), so the two contributions
                  carry opposite signs and partially cancel.
    Every component keeps its residual sqrt(u^2 - shared^2) in quadrature; 4D1 shares
    neither term and stays fully independent.
    """
    comps = engine.build_components(data)
    total = sum(c["co2e_Mt_AR5"] for c in comps)

    u_gen = product(5, data.pu("gen_rate_urban"))
    u_unc = data.pu("uncollected_urban")
    generated = swds.waste_generated(data)
    u_eff = (generated - swds.waste_disposed(data)) / generated
    elasticity = {open_burning.CATEGORY: 1.0, swds.CATEGORY: -u_eff / (1.0 - u_eff)}

    gen_abs, part_abs, resid_sq = 0.0, 0.0, 0.0
    for c in comps:
        e = c["co2e_Mt_AR5"]
        if c["category"] in PARTITIONED:
            gen_abs += u_gen / 100.0 * e
            part_abs += u_unc / 100.0 * e * elasticity[c["category"]]
            resid = math.sqrt(max(c["uncert_pct"] ** 2 - u_gen ** 2 - u_unc ** 2, 0.0))
            resid_sq += (resid / 100.0 * e) ** 2
        else:
            resid_sq += (c["uncert_pct"] / 100.0 * e) ** 2

    grouped = math.sqrt(gen_abs ** 2 + part_abs ** 2 + resid_sq) / total * 100.0
    _t, indep = combine_sum([(c["co2e_Mt_AR5"], c["uncert_pct"]) for c in comps])

    per_category = []
    for cat in (open_burning.CATEGORY, swds.CATEGORY, wastewater.CATEGORY):
        members = [(c["co2e_Mt_AR5"], c["uncert_pct"]) for c in comps
                   if c["category"] == cat]
        cat_total, cat_u = combine_sum(members)
        per_category.append({"category": cat, "co2e_Mt_AR5": cat_total,
                             "approach1_pct_independent": cat_u,
                             "approach1_pct_grouped": "",
                             "note": ""})
    per_category.append({
        "category": "SECTOR", "co2e_Mt_AR5": total,
        "approach1_pct_independent": indep, "approach1_pct_grouped": grouped,
        "note": "grouped shares the generation term (+%.1f%% linear across 4A+4C2, "
                "%.2f Mt absolute) and the signed partition term (30%% at elasticity "
                "+1 on 4C2, %.2f on 4A; net %.2f Mt absolute against %.2f if treated "
                "as independent). Generation coupling widens, partition anticorrelation "
                "narrows; the net is what the grouped figure reports."
                % (u_gen, gen_abs, elasticity[swds.CATEGORY], part_abs,
                   math.sqrt(sum((u_unc / 100.0 * c["co2e_Mt_AR5"]) ** 2
                                 for c in comps if c["category"] in PARTITIONED)))})
    return per_category


def _with_params(**overrides):
    """A fresh WasteData with named parameters overridden - never the shared instance."""
    d = WasteData()
    for k, v in overrides.items():
        if k not in d.params:
            raise KeyError(k)
        d.params[k] = v
    return d


def _no_spinup_components(data):
    ratio = swds.ch4_emitted(data, spinup=False) / swds.ch4_emitted(data, spinup=True)
    out = []
    for c in engine.build_components(data):
        c2 = dict(c)
        if c["category"] == swds.CATEGORY:
            for k in ("co2e_Mt_AR5", "co2e_Mt_AR6", "emissions_Gg"):
                c2[k] = c2[k] * ratio
        out.append(c2)
    return out


def _unresolved_fate_components(data, mcf_alt):
    """The unresolved dumped mass priced as if it decayed at an unmanaged-site MCF.

    The fate ledger's honest remainder - uncollected waste that is neither burned nor
    landfilled - carries no GHG pathway in the reference build, because no site
    conditions are observed for it. These scenarios BOUND what that choice can hide.
    Eq 6.1 is linear in deposited mass and in the MCF, so pricing the dumped stream at
    an alternative MCF is an exact scaling of the SWDS stream by
    (unresolved / disposed) x (MCF_alt / reference MCF) - conditional on the declared
    assumption that the dumped stream shares the collected stream's deposit-history
    shape and composition, which is an assumption, not evidence."""
    generated = swds.waste_generated(data)
    disposed = swds.waste_disposed(data)
    unresolved = (generated - disposed) - open_burning.waste_burnt(data)
    scale = 1.0 + (unresolved / disposed) * (mcf_alt / data.p("swds_mcf"))
    out = []
    for c in engine.build_components(data):
        c2 = dict(c)
        if c["category"] == swds.CATEGORY:
            for k in ("co2e_Mt_AR5", "co2e_Mt_AR6", "emissions_Gg"):
                c2[k] = c2[k] * scale
        out.append(c2)
    return out


def structural_scenarios(data=None, n_iter=10000, seed=SCENARIO_SEED):
    data = data or WasteData()
    t = data.p("ww_treated_share")
    cases = [
        ("reference", lambda: engine.build_components(data),
         "the estimate: sewer MCF 0.5, What a Waste partition, spun-up FOD"),
        ("sewer_all_stagnant",
         lambda: engine.build_components(_with_params(
             ww_mcf_sewer=sewer_mcf_mixture(data, 1.0, 0.0, 0.0))),
         "the central case restated as a pure mixture endpoint (w_stagnant=1): "
         "identical to reference by construction, which proves the mixture is exact"),
        ("sewer_all_flowing",
         lambda: engine.build_components(_with_params(
             ww_mcf_sewer=sewer_mcf_mixture(data, 0.0, 1.0, 0.0))),
         "every sewered load at the river-discharge 0.1 - the published sensitivity, "
         "now with a conditional interval; EDGAR's comparator reading"),
        ("sewer_equal_mix",
         lambda: engine.build_components(_with_params(
             ww_mcf_sewer=sewer_mcf_mixture(data, (1 - t) / 2, (1 - t) / 2, t))),
         "the genuinely new number: half the sewered load stagnant, half flowing, with "
         "the treated sliver (%.0f%%) at the not-well-managed plant MCF - effective "
         "MCF %.3f. Seasonally plausible for drains that stagnate dry and flush in "
         "monsoon; the weights are unmeasured, which is why this is a scenario"
         % (100 * t, sewer_mcf_mixture(data, (1 - t) / 2, (1 - t) / 2, t))),
        ("bod_india",
         lambda: engine.build_components(_with_params(
             ww_bod_g_per_cap_day=data.p("ww_bod_india"))),
         "BOD at India's 34 g/cap/day (IPCC Table 6.4) instead of the regional 40"),
        ("no_spinup", lambda: _no_spinup_components(data),
         "FOD started empty at the panel's first year - what ignoring the pre-2000 "
         "deposit history would report"),
        ("hies_route_shares",
         lambda: engine.build_components(_with_params(
             uncollected_urban=data.hies_share("urban", "uncollected"),
             uncollected_rural=data.hies_share("rural", "uncollected"))),
         "the partition on HIES 2024-25 design-weighted household routes (uncollected "
         "0.42 urban / 0.93 rural, data/activity/waste/hies_disposal_routes.csv) "
         "instead of What a Waste's 0.30 / 0.70. Household shares are not mass shares "
         "- the declared caveat - and the sector total FALLS: the extra uncollected "
         "tonnage burns immediately instead of decaying at the disposal MCF"),
        ("unresolved_inert",
         lambda: engine.build_components(data),
         "STRUCTURAL FAMILY unresolved_fate, REFERENCE MEMBER (rc13 formalization): "
         "the fate ledger's 6.27 Mt unresolved remainder produces nothing this "
         "inventory estimates. An EVIDENCE-ABSENCE choice, not a physical claim "
         "- no site census says where the dumped mass sits - and identical to "
         "reference by construction: the family's lower endpoint, stated as a "
         "row so the bound has both ends. The three family members may not be "
         "quoted separately"),
        ("unresolved_shallow_dumps",
         lambda: _unresolved_fate_components(data, 0.4),
         "STRUCTURAL FAMILY unresolved_fate, member: the remainder decaying as "
         "unmanaged SHALLOW disposal (IPCC Table 3.1 MCF 0.4), on the declared "
         "assumption that it shares the collected stream's deposit history and "
         "composition; waterway decay is bounded between this and inert"),
        ("unresolved_deep_dumps",
         lambda: _unresolved_fate_components(data, 0.8),
         "STRUCTURAL FAMILY unresolved_fate, upper member: the remainder as "
         "unmanaged DEEP disposal (MCF 0.8). No probability attaches to any "
         "point in the family - a site census, not a better default, is what "
         "would close it"),
        ("effluent_ef_low",
         lambda: engine.build_components(_with_params(
             ww_ef_effluent=data.param_bounds["ww_ef_effluent"][0])),
         "the effluent N2O factor at its published floor (%g). With effluent_ef_high "
         "this states the discrete structural endpoints of the %.0f-fold range the "
         "bounded draw prices continuously; the endpoints are NOT equally probable "
         "and no probability attaches to either"
         % (data.param_bounds["ww_ef_effluent"][0],
            data.param_bounds["ww_ef_effluent"][1]
            / data.param_bounds["ww_ef_effluent"][0])),
        ("effluent_ef_high",
         lambda: engine.build_components(_with_params(
             ww_ef_effluent=data.param_bounds["ww_ef_effluent"][1])),
         "the effluent N2O factor at its published ceiling (%g, the 2019 "
         "Refinement's; the 2006 Guidelines printed %g and through rc66 this row "
         "priced that). What would close the range is a Pakistani effluent-pathway "
         "measurement, not a narrower default"
         % (data.param_bounds["ww_ef_effluent"][1],
            data.p("ww_ef_effluent_2006_high"))),
        # rc67: the nitrous-oxide method and the three things it needs that are
        # declared, not measured. One scenario each; no probabilities.
        ("n2o_method_ipcc2006",
         lambda: engine.build_components(_with_params(ww_n2o_method_2019=0)),
         "the 2006 Guidelines' equation, the reference through rc66: one nitrogen "
         "total on protein supply, the industrial factor on the whole population, "
         "nothing removed, all of it effluent. Its interval here is conditional on "
         "the 2019 range of the effluent factor; the 2006 method drawn over its own "
         "range (to 0.25) is in outputs/pakemis_wastewater_method_comparison.csv"),
        ("decentralised_effluent_to_soil",
         lambda: engine.build_components(_with_params(ww_decentralised_to_water=0)),
         "the nitrogen leaving septic tanks, latrines, unimproved facilities and open "
         "defecation goes to soil and not to water, as the Refinement's Figure 6.1 "
         "draws it, so only sewered nitrogen is effluent. The reference follows Eq "
         "6.8, which sums every pathway. Soil emissions would belong to Volume 4 and "
         "are NOT added back here: this is a lower reading of the category, not a "
         "transfer"),
        ("effluent_nutrient_impacted",
         lambda: engine.build_components(_with_params(
             ww_ef_effluent=data.p("ww_ef_effluent_nutrient"))),
         "every discharge to nutrient-impacted or hypoxic water: the Refinement's "
         "Tier 3 effluent factor (%g) in place of the Tier 1 %g. No classification "
         "of Pakistan's receiving waters is compiled, so this is the declared upper "
         "reading and the Tier 1 factor is the reference"
         % (data.p("ww_ef_effluent_nutrient"), data.p("ww_ef_effluent"))),
        ("septic_with_dispersal_field",
         lambda: engine.build_components(_with_params(
             ww_nrem_septic=data.p("ww_nrem_septic_field"),
             ww_ef_septic=data.p("ww_ef_septic_field"))),
         "septic tanks WITH a land dispersal field: %g of the nitrogen removed "
         "instead of %g, and a soil-dispersal factor of %g at the system. The field's "
         "own emission outweighs the nitrogen it keeps out of the effluent, so this "
         "reading is above the reference, which takes the stand-alone tank"
         % (data.p("ww_nrem_septic_field"), data.p("ww_nrem_septic"),
            data.p("ww_ef_septic_field"))),
        ("treated_share_high",
         lambda: engine.build_components(_with_params(
             ww_treated_share=data.param_bounds["ww_treated_share"][1])),
         "twice the declared treated share of sewered flow (%g): more nitrogen "
         "removed, more emitted at plants. The share is declared, not measured"
         % data.param_bounds["ww_treated_share"][1]),
        ("sewer_flowing_river_low",
         lambda: engine.build_components(_with_params(
             ww_mcf_sewer=sewer_mcf_mixture(
                 _with_params(ww_mcf_sewer_river=data.param_bounds[
                     "ww_mcf_sewer_river"][0]), 0.0, 1.0, 0.0))),
         "the river-discharge reading at ITS OWN published floor (MCF 0): sewered "
         "CH4 vanishes entirely. Conditional on the flowing reading - this prices "
         "the 0-0.2 range the reference build never touches, which its zero "
         "reference-uncertainty used to leave silent"),
        ("sewer_flowing_river_high",
         lambda: engine.build_components(_with_params(
             ww_mcf_sewer=sewer_mcf_mixture(
                 _with_params(ww_mcf_sewer_river=data.param_bounds[
                     "ww_mcf_sewer_river"][1]), 0.0, 1.0, 0.0))),
         "the river-discharge reading at its published ceiling (MCF 0.2): the "
         "flowing case doubles from its default. The two rows bracket what the "
         "EDGAR-agreeing reading can mean on its own terms"),
    ]
    categories = [open_burning.CATEGORY, swds.CATEGORY, wastewater.CATEGORY]
    # Endpoint statements whose conditional interval would be meaningless: the
    # effluent-EF endpoints override the very parameter whose bounded shape sets
    # the component's declared width, so a lognormal around the endpoint would
    # manufacture a fictitious spread around a deliberately extreme point. They
    # publish the deterministic statement alone.
    deterministic_only = {"effluent_ef_low", "effluent_ef_high",
                          "effluent_nutrient_impacted"}
    out = []
    for i, (name, build, note) in enumerate(cases):
        comps = build()
        det = sum(c["co2e_Mt_AR5"] for c in comps)
        if name in deterministic_only:
            out.append({"structural_scenario": name, "scope": "GHG Mt CO2e AR5",
                        "deterministic": det, "mean": "", "P2.5": "",
                        "P50": "", "P97.5": "", "seed": "", "note": note,
                        "interpretation": "deterministic endpoint statement; "
                                          "no conditional interval"})
            continue
        stats, _samples = mc_core.run(comps, categories, n_iter=n_iter, seed=seed + i)
        s = stats["TOTAL"]
        # The seed column is the row's OWN seed (base + case index), published since
        # rc12: the paper used to call this stream "private", which made the
        # scenario intervals irreproducible from the release (the eighth review).
        out.append({"structural_scenario": name, "scope": "GHG Mt CO2e AR5",
                    "deterministic": det, "mean": s["mean"], "P2.5": s["p025"],
                    "P50": s["p50"], "P97.5": s["p975"], "seed": seed + i,
                    "note": note, "interpretation": INTERPRETATION})
    return out


RERUN_SEED = SCENARIO_SEED + 100     # its own stream; scenarios and national MC untouched


def parameter_rerun_mc(data=None, n_iter=10000, seed=RERUN_SEED,
                       return_samples=False, n2o_method=None, freeze=(),
                       return_native=False):
    """Approach 2 by PARAMETER RERUN: draw the inputs, rebuild the sector, every draw.

    The seventh review's architectural point: a Monte Carlo that draws component
    TOTALS as independent lognormals cannot promise the fate identity D + U = G in
    any single realization, and expresses no covariance between categories built
    from one generation figure and one collection coverage. This entry point fixes
    both by construction - each iteration draws the sector's parametric inputs
    (mean-preserving lognormal per parameter, each on its own seeded stream;
    BOUNDED_DRAW parameters on their published-range split triangular), rebuilds
    every component through the same engine the deterministic run uses, and asserts
    the fate ledger's closure identities before the draw is accepted. Covariance is
    not modelled; it EMERGES: generation rates drive disposal and burning together,
    the uncollected fraction moves mass between them with opposite signs, and the
    FOD's nonlinearity in k is exact rather than linearised.

    The analytic approach1() remains published beside this as the cross-check; the
    old component-lognormal treatment survives only in the pooled national stream,
    whose documented limits (unsigned sharing) the parameter_scope repair narrows.

    n2o_method (rc67) runs the wastewater nitrous-oxide ALTERNATIVE on the same draws:
    "ipcc2006" switches the equation and draws the effluent factor over the 2006
    Guidelines' own range (to 0.25) instead of the Refinement's (to 0.075), so the
    alternative's interval is the one that method published. Every stream is
    identity-seeded, so draw d of the alternative used the same random numbers as draw d
    of the reference and the two can be differenced draw by draw.

    freeze (rc67) names parameters held at their default in every draw. Each parameter
    draws from its own identity-seeded stream, so freezing one leaves every other
    parameter's draw d exactly as it was: the frozen run differs from the reference run
    by that parameter and by nothing else, draw by draw.

    Returns rows per category + SECTOR with asymmetric percentiles.
    """
    base = data or WasteData()
    categories = [open_burning.CATEGORY, swds.CATEGORY, wastewater.CATEGORY]
    unknown = [p for p in freeze if p not in base.params]
    if unknown:
        raise KeyError("cannot freeze parameters the sector does not have: %s" % unknown)
    bounds = dict(base.param_bounds)
    switch = None
    if n2o_method == "ipcc2006":
        switch = 0.0
        bounds["ww_ef_effluent"] = (bounds["ww_ef_effluent"][0],
                                    base.p("ww_ef_effluent_2006_high"))
    elif n2o_method not in (None, "ipcc2019"):
        raise ValueError("unknown wastewater N2O method %r" % (n2o_method,))

    drawn = [p for p in base.params
             if _REGISTER[p][2] == "parametric" or p in BOUNDED_DRAW]
    drawn = [p for p in drawn
             if p in BOUNDED_DRAW or (base.param_uncert.get(p) or 0) > 0]
    drawn = [p for p in drawn if p not in freeze]
    ef_items = [("waste_burning", "CH4"), ("waste_burning", "N2O")]

    rngs = {p: random.Random(mc_core.stream_seed(seed, "param|" + p))
            for p in drawn}
    ef_rngs = {item: random.Random(
        mc_core.stream_seed(seed, "ef|%s|%s" % item)) for item in ef_items}

    saved_params = dict(base.params)
    saved_ef = {item: base.ef[item]["value"] for item in ef_items}
    sums = {c: [] for c in categories}
    totals = []
    native = {}
    try:
        for _ in range(n_iter):
            for p in drawn:
                if p in BOUNDED_DRAW:
                    lo, hi = bounds[p]
                    base.params[p] = bounded_log_split_triangular(
                        rngs[p].random(), lo, saved_params[p], hi)
                else:
                    sig = mc_core.sigma_log(base.param_uncert[p])
                    base.params[p] = saved_params[p] * math.exp(
                        rngs[p].gauss(0, 1) * sig - sig * sig / 2.0)
            for item in ef_items:
                sig = mc_core.sigma_log(base.efu(*item))
                base.ef[item]["value"] = saved_ef[item] * math.exp(
                    ef_rngs[item].gauss(0, 1) * sig - sig * sig / 2.0)
            if switch is not None:
                base.params["ww_n2o_method_2019"] = switch
            ledger.rows(base)        # raises if D+U!=G or B+R!=U in THIS draw
            comps = engine.build_components(base)
            if return_native:
                for parameter in drawn:
                    native.setdefault("parameter:" + parameter, []).append(base.params[parameter])
                for c in comps:
                    key = "%s|%s|%s" % (c["category"], c["subitem"], c["gas"])
                    native.setdefault(key, []).append(c["emissions_Gg"])
                wet = open_burning.waste_burnt(base)
                native.setdefault("burned_wet_t", []).append(wet)
                native.setdefault("burned_dry_t", []).append(wet * base.p("dry_matter"))
            draw_total = 0.0
            for cat in categories:
                v = sum(c["co2e_Mt_AR5"] for c in comps if c["category"] == cat)
                sums[cat].append(v)
                draw_total += v
            totals.append(draw_total)
    finally:
        base.params.update(saved_params)
        for item in ef_items:
            base.ef[item]["value"] = saved_ef[item]

    if switch is not None:
        # the deterministic value beside the alternative's draws is the alternative's
        base.params["ww_n2o_method_2019"] = switch
    try:
        out = _summarize_draws(base, sums, totals, n_iter, seed)
    finally:
        base.params.update(saved_params)
    if return_native:
        return out, sums, totals, native
    if return_samples:
        return out, sums, totals
    return out


def _summarize_draws(base, sums, totals, n_iter, seed):
    """The same summary for freshly drawn and persisted round-trip float samples."""
    categories = list(sums)
    det_comps = engine.build_components(base)
    out = []
    for cat in categories + ["SECTOR"]:
        samples = sorted(totals if cat == "SECTOR" else sums[cat])
        det = (sum(c["co2e_Mt_AR5"] for c in det_comps) if cat == "SECTOR"
               else sum(c["co2e_Mt_AR5"] for c in det_comps
                        if c["category"] == cat))
        out.append({
            "scope": cat, "deterministic": det,
            "mean": sum(samples) / len(samples),
            "P2.5": mc_core.percentile(samples, 0.025),
            "P50": mc_core.percentile(samples, 0.50),
            "P97.5": mc_core.percentile(samples, 0.975),
            "n_iter": n_iter, "seed": seed,
            "ledger_closed_in_every_draw": "yes",
            "note": ("parameter rerun: inputs drawn, sector rebuilt, fate ledger "
                     "asserted per draw; covariance emerges from shared "
                     "parameters; the wastewater N2O tail is the bounded "
                     "effluent-factor range, asymmetric by construction")})
    return out


def summary_from_draw_file(data=None, n_iter=10000, seed=RERUN_SEED):
    """Summarize the deterministic prefix of the national pool; never draw again."""
    from pkinv.core import mc_draws
    base = data or WasteData()
    columns, meta = mc_draws.read("waste_parameter_rerun")
    if (meta["seed"] != seed or meta["n_iter"] < n_iter
            or meta["distribution_id"] != "parameter_rerun_ledger_true"
            or meta["rng"] != mc_draws.RNG_IDENTITY):
        raise ValueError("waste draw file does not match the requested seed, count or engine")
    categories = [open_burning.CATEGORY, swds.CATEGORY, wastewater.CATEGORY]
    if set(columns) != set(categories + ["MODULE_TOTAL"]):
        raise ValueError("waste draw file has unexpected categories")
    rows = _summarize_draws(base, {cat: columns[cat][:n_iter] for cat in categories},
                           columns["MODULE_TOTAL"][:n_iter], n_iter, seed)
    for row in rows:
        column = "MODULE_TOTAL" if row["scope"] == "SECTOR" else row["scope"]
        if row["deterministic"] != meta["deterministic"][column]:
            raise ValueError("waste draw file is stale for %s; rebuild the draws first" % column)
    return rows


ALTERNATIVE_DRAWS = 10000    # the released ensemble's N: enough to difference against it


def write_alternative_draw_file(data=None, n_iter=ALTERNATIVE_DRAWS, seed=RERUN_SEED):
    """The 2006 nitrous-oxide method on the SAME draws, for the method comparison (rc67).

    Not injected anywhere and in no total: the national pool takes the reference draw
    file. This file exists so pakemis_wastewater_method_comparison.csv can difference the
    two methods draw by draw against the released ensemble, instead of setting two
    unrelated intervals side by side."""
    from pkinv.core import mc_draws
    base = data or WasteData()
    out, sums, totals = parameter_rerun_mc(base, n_iter=n_iter, seed=seed,
                                           return_samples=True, n2o_method="ipcc2006")
    det = {r["scope"]: r["deterministic"] for r in out}
    columns = {cat: sums[cat] for cat in
               [open_burning.CATEGORY, swds.CATEGORY, wastewater.CATEGORY]}
    columns["MODULE_TOTAL"] = totals
    path, meta = mc_draws.write("waste_parameter_rerun_ipcc2006", columns, {
        "seed": seed, "n_iter": n_iter,
        "engine": "pkinv.sectors.waste.uncertainty.parameter_rerun_mc(n2o_method='ipcc2006')",
        "distribution_id": "parameter_rerun_ledger_true_n2o_ipcc2006",
        "deterministic": {c: (det["SECTOR"] if c == "MODULE_TOTAL" else det[c])
                          for c in columns},
        "note": "the ALTERNATIVE wastewater N2O method (IPCC 2006 equation, effluent "
                "factor drawn to 0.25) on the reference draw file's own streams; not "
                "injected into the national pool",
    })
    print("waste alternative draw file -> %s (%d draws, seed %d, sha256 %s...)"
          % (os.path.basename(path), n_iter, seed, meta["sha256"][:12]))
    return path


def write_draw_file(data=None, n_iter=100000, seed=RERUN_SEED):
    """Persist the rerun engine's draws for the national pool (rc12).

    100,000 draws - the national run's own N - on the same per-parameter
    identity-seeded streams as the published 10,000-draw table, so the file's
    first 10,000 draws ARE that table's draws bit-for-bit (a test asserts the
    prefix). The national engine injects these vectors in place of its lognormal
    surrogate, which is what stops the wastewater tail being compressed on the
    way to the national row.
    """
    from pkinv.core import mc_draws
    base = data or WasteData()
    out, sums, totals = parameter_rerun_mc(base, n_iter=n_iter, seed=seed,
                                           return_samples=True)
    det = {r["scope"]: r["deterministic"] for r in out}
    columns = {cat: sums[cat] for cat in
               [open_burning.CATEGORY, swds.CATEGORY, wastewater.CATEGORY]}
    columns["MODULE_TOTAL"] = totals
    path, meta = mc_draws.write("waste_parameter_rerun", columns, {
        "seed": seed, "n_iter": n_iter,
        "engine": "pkinv.sectors.waste.uncertainty.parameter_rerun_mc",
        "distribution_id": "parameter_rerun_ledger_true",
        "deterministic": {c: (det["SECTOR"] if c == "MODULE_TOTAL" else det[c])
                          for c in columns},
        "note": "fate ledger identities (D+U=G, B+R=U) asserted in every draw; "
                "first 10000 draws bit-identical to waste_parameter_mc_2024.csv",
    })
    print("waste draw file -> %s (%d draws, seed %d, sha256 %s...)"
          % (os.path.basename(path), n_iter, seed, meta["sha256"][:12]))
    return path


# parameter -> (applies_to, correlation_group, class, note). Everything in
# waste_params.csv that feeds a component, sensitivity or scenario must appear here:
# tests/test_waste_uncertainty.py asserts the coverage bidirectionally.
_REGISTER = {
    "gen_rate_urban": ("4A + 4C2 activity", "waste_generation", "parametric",
                       "shared POSITIVELY across the partition: more waste means more "
                       "disposal and more burning at once"),
    "gen_rate_rural": ("4A + 4C2 activity", "waste_generation", "parametric", ""),
    "uncollected_urban": ("the partition point", "waste_partition", "parametric",
                          "shared with OPPOSITE signs: B ~ u, D ~ 1-u. Also the axis "
                          "of the hies_route_shares scenario"),
    "uncollected_rural": ("the partition point", "waste_partition", "parametric", ""),
    "burned_fraction": ("4C2 + the whole air-pollutant layer", "", "parametric",
                        "least evidenced parameter in the sector; scales open burning "
                        "and every pollutant linearly"),
    "oxidation_factor": ("4C2 CO2", "", "parametric", ""),
    "oxidation_factor_2006": ("retired alternative", "", "structural",
                              "superseded 1996-vintage value kept for the documented "
                              "double-discount argument in the factors section"),
    "dry_matter": ("4C2 N2O + air factors' dry-mass basis", "", "parametric", ""),
    "fossil_c_per_wet_t": ("4C2 fossil CO2", "waste_composition", "parametric",
                           "one Pak-EPA composition; shares the derivation with "
                           "total carbon and the FOD's DOC"),
    "total_c_per_wet_t": ("4C2 biogenic memo + 4A DOC", "waste_composition",
                          "parametric", ""),
    "swds_k": ("4A decay", "", "parametric", ""),
    "swds_docf": ("4A", "", "parametric", ""),
    "swds_mcf": ("4A", "", "structural",
                 "IPCC 'uncategorised' 0.6; the site-type census that would classify "
                 "it does not exist - see waste-site-classification"),
    "swds_f": ("4A", "", "parametric", ""),
    "swds_oxidation": ("4A", "", "structural",
                       "zero by IPCC default for unmanaged sites; a documented cover "
                       "at any large site would change it"),
    "swds_recovery_t": ("4A", "", "structural",
                        "zero: no operating landfill-gas recovery is documented"),
    "swds_delay_months": ("4A monthly shape only", "", "structural",
                          "the six-month reaction delay is applied in the MONTHLY "
                          "state engine as a shape refinement and normalised away "
                          "at annual grain, so no figure this register prices can "
                          "move with it; the annual-methodology revision that "
                          "WOULD move one is the driver registry's priced "
                          "candidate, not a draw"),
    "swds_backprojection": ("4A deposit history", "", "structural",
                            "the VALUE is the uncertainty percentage; scenario "
                            "no_spinup bounds the whole assumption"),
    "ww_bod_g_per_cap_day": ("4D1 CH4 load", "", "parametric",
                             "regional default; scenario bod_india prices the "
                             "neighbouring table row"),
    "ww_bod_india": ("scenario bod_india only", "", "structural", ""),
    "ww_bo": ("4D1 CH4", "", "parametric", ""),
    "ww_mcf_sewer": ("4D1 sewered load", "", "parametric",
                     "THE JUDGEMENT THAT DECIDES THE SECTOR, in two separable "
                     "parts: the +/-60 width around the stagnant reading IS "
                     "sampled (it enters the CH4 component's declared width), "
                     "while the stagnant-vs-river READING is the structural axis "
                     "(scenarios sewer_*). An earlier register labelled the whole "
                     "row 'not sampled' while the width was being sampled through "
                     "the component - the rc11 repair says both halves plainly"),
    "ww_mcf_sewer_river": ("scenario sewer_all_flowing", "", "structural",
                           "its own published 0-0.2 range is priced by scenarios "
                           "sewer_flowing_river_low/high, conditional on the "
                           "flowing reading; absent from the reference build"),
    "ww_mcf_treated": ("the mixture's treated term", "", "structural",
                       "enters only through sewer_mcf_mixture; invisible at the "
                       "current treated share; its 0.2-0.4 range is carried in "
                       "the bounds columns"),
    "ww_treated_share": ("the mixture's treated weight", "", "structural",
                         "declared weight, not a measurement; the 0.005-0.02 "
                         "bounds are a declared judgement span"),
    "ww_mcf_septic": ("4D1 septic load", "", "parametric", ""),
    "ww_mcf_latrine": ("4D1 latrine + unimproved load", "", "parametric", ""),
    "ww_mcf_open": ("4D1 open defecation", "", "structural",
                    "explicit zero - a decision, not an oversight"),
    "ww_n_sludge_kg": ("4D1 effluent nitrogen", "", "structural",
     "N_SLUDGE in IPCC 2006 Vol 5 Ch 6 Eq 6.8, explicit default zero: no measurement of sludge "
     "removal is held; a measurement would replace the default, not a draw"),
    "ww_industrial_factor": ("4D1 sewered load", "", "parametric", ""),
    "ww_f_npr": ("4D1 N2O", "", "parametric", ""),
    "ww_f_non_con": ("4D1 N2O", "", "parametric", ""),
    "ww_f_ind_com": ("4D1 N2O, sewered nitrogen", "", "parametric",
                     "on the sewered population under the 2019 method, on everyone "
                     "under the 2006 alternative"),
    "ww_ef_effluent": ("4D1 N2O", "", "parametric",
                       "the softest factor in the sector. Drawn from the bounded "
                       "split-triangular over its published range since rc11 (mode "
                       "and median at the 0.005 default). The range is the 2019 "
                       "Refinement's 0.0005-0.075 since rc67 (0.0005-0.25 before); "
                       "the symmetric width declared for the surfaces that need one "
                       "is the log-variance-matched equivalent, computed not typed; "
                       "the endpoint scenarios effluent_ef_low/high state the "
                       "discrete bounds"),
    "ww_n2o_method_2019": ("4D1 N2O method", "", "structural",
                           "a switch, never drawn; scenario n2o_method_ipcc2006"),
    "ww_f_pc": ("4D1 N2O, protein consumed", "", "parametric", ""),
    "ww_n_hh": ("4D1 N2O, household products", "", "parametric",
                "bounded draw over the country values Table 6.10A prints"),
    "ww_f_ind_com_decentralised": ("4D1 N2O, non-sewered nitrogen", "", "structural",
                                   "fixed at 1 by the method"),
    "ww_nrem_secondary": ("4D1 N2O, treated sewered nitrogen", "", "parametric", ""),
    "ww_nrem_septic": ("4D1 N2O, septic nitrogen", "", "parametric",
                       "scenario septic_with_dispersal_field prices the other row"),
    "ww_nrem_septic_field": ("scenario septic_with_dispersal_field only", "",
                             "structural", ""),
    "ww_nrem_latrine": ("4D1 N2O, latrine + unimproved nitrogen", "", "parametric", ""),
    "ww_ef_plant_aerobic": ("4D1 N2O at treatment plants", "", "parametric", ""),
    "ww_ef_septic": ("4D1 N2O at septic systems", "", "structural",
                     "the table's explicit zero"),
    "ww_ef_septic_field": ("scenario septic_with_dispersal_field only", "",
                           "structural", ""),
    "ww_ef_effluent_nutrient": ("scenario effluent_nutrient_impacted only", "",
                                "structural", ""),
    "ww_decentralised_to_water": ("4D1 N2O, effluent of decentralised systems", "",
                                  "structural",
                                  "declared 1 (Eq 6.8); scenario "
                                  "decentralised_effluent_to_soil prices 0"),
    "ww_ef_effluent_2006_high": ("the 2006 alternative's draw only", "", "structural",
                                 ""),
}


def inputs_register(data):
    rows = []
    for param in data.params:
        applies, group, klass, note = _REGISTER[param]
        u = data.param_uncert.get(param)
        if param in BOUNDED_DRAW:
            lo, hi = data.param_bounds[param]
            dist = ("bounded log split-triangular [%g, %g], mode %g" %
                    (lo, hi, data.p(param)))
            u = round(equivalent_bounded_uncert_pct(data, param), 1)
        elif klass == "parametric":
            dist = "lognormal"
        else:
            dist = "not sampled"
        rows.append({"variable": param, "central_value": data.p(param),
                     "unit": "", "uncert_pct_95": "" if u is None else u,
                     "distribution": dist,
                     "source": data.ps(param), "applies_to": applies,
                     "correlation_group": group, "uncertainty_class": klass,
                     "note": note})
    rows.append({"variable": "waste_ch4 / waste_n2o burning factors",
                 "central_value": "%.1f / %.2f" % (data.efv("waste_burning", "CH4"),
                                                   data.efv("waste_burning", "N2O")),
                 "unit": "g/kg wet; g/kg dry", "uncert_pct_95": "%.0f / %.0f"
                 % (data.efu("waste_burning", "CH4"), data.efu("waste_burning", "N2O")),
                 "distribution": "lognormal", "source": data.efs("waste_burning", "CH4"),
                 "applies_to": "4C2 CH4 / N2O", "correlation_group": "",
                 "uncertainty_class": "parametric",
                 "note": "note the deliberate wet/dry basis split"})
    # rc41 (the nineteenth review's P-1): the N2O row's activity is the FAOSTAT protein
    # supply, an observed series (data/activity/wastewater/protein.csv) the engine reads by
    # clamped year; registered here so the row's activity has a named parameter, not sampled
    # because FAO publishes no interval for it.
    protein_year = max(y for y in data.protein if y <= data.year) if any(y <= data.year for y in data.protein) else max(data.protein)
    rows.append({"variable": "protein supply (FAOSTAT)",
                 "central_value": data.protein[protein_year],
                 "unit": "g protein per capita per day", "uncert_pct_95": "",
                 "distribution": "not sampled",
                 "source": "FAOSTAT Food Balances, Pakistan, year %d (clamped lookup)" % protein_year,
                 "applies_to": "4D1 N2O load", "correlation_group": "",
                 "uncertainty_class": "structural",
                 "note": "observed national series; FAO publishes no interval - the N2O "
                         "row's width rests on its effluent factor"})
    rows.append({"variable": "HIES vs What a Waste partition", "central_value":
                 "0.30/0.70 central; 0.42/0.93 surveyed", "unit": "fraction",
                 "uncert_pct_95": "", "distribution": "not sampled",
                 "source": "HIES 2024-25 Sec 5 Mod 3 (PBS microdata)",
                 "applies_to": "the partition point", "correlation_group": "",
                 "uncertainty_class": "structural",
                 "note": "scenario hies_route_shares; household route shares are not "
                         "mass shares, the declared reason the survey is priced "
                         "rather than adopted"})
    rows.append({"variable": "sewer hydraulic-regime weights", "central_value":
                 "w_stagnant=1 central", "unit": "weights", "uncert_pct_95": "",
                 "distribution": "not sampled",
                 "source": "unmeasured - see wastewater-sewer-mcf",
                 "applies_to": "4D1 sewered load", "correlation_group": "",
                 "uncertainty_class": "structural",
                 "note": "scenarios sewer_all_stagnant / sewer_all_flowing / "
                         "sewer_equal_mix; dissolved-methane sampling on urban drains "
                         "would measure the weights"})
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = WasteData()

    a1 = approach1(data)
    with open(asset_path(OUTPUTS, "waste_uncertainty_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(a1[0].keys()))
        w.writeheader()
        for r in a1:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v)
                        for k, v in r.items()})

    with open(asset_path(OUTPUTS, "waste_uncertainty_inputs_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        rows = inputs_register(data)
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    scen = structural_scenarios(data)
    with open(asset_path(OUTPUTS, "waste_uncertainty_scenarios_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(scen[0].keys()))
        w.writeheader()
        for r in scen:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v)
                        for k, v in r.items()})

    rerun = summary_from_draw_file(data)
    with open(asset_path(OUTPUTS, "waste_parameter_mc_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rerun[0].keys()))
        w.writeheader()
        for r in rerun:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v)
                        for k, v in r.items()})

    sector = a1[-1]
    print("Waste Approach 1: %.2f%% grouped vs %.2f%% independent on %.4f Mt"
          % (sector["approach1_pct_grouped"], sector["approach1_pct_independent"],
             sector["co2e_Mt_AR5"]))
    for r in scen:
        band = ("[%7.3f, %7.3f]" % (r["P2.5"], r["P97.5"])
                if r["P2.5"] != "" else "(deterministic endpoint)")
        print("  %-24s %8.4f Mt  %s"
              % (r["structural_scenario"], r["deterministic"], band))
    print("Parameter-rerun MC (ledger asserted per draw):")
    for r in rerun:
        print("  %-24s det %8.4f  mean %8.4f  [%7.3f, %7.3f]"
              % (r["scope"], r["deterministic"], r["mean"], r["P2.5"], r["P97.5"]))


if __name__ == "__main__":
    import sys
    if "draws" in sys.argv[1:]:
        # The national draw-file stage (rc12): ~4-5 minutes at 100k, deterministic,
        # run separately so the ordinary sector stage stays fast.
        raise SystemExit(0 if write_draw_file() else 1)
    if "alternative-draws" in sys.argv[1:]:
        # rc67: the 2006 nitrous-oxide method on the same streams, 10,000 draws, for
        # the method comparison. Seconds, not minutes.
        raise SystemExit(0 if write_alternative_draw_file() else 1)
    main()
