"""Legacy analytical sensitivity to component and parameter dependence over time.

This product keeps the historical component/parameter graph for comparison. It
is not the current conserved native nitrogen, crop-burning, waste or fugitive
replay, and its scenario endpoints do not bound the true trend uncertainty.
The current paired native levels/trends are the separately named GHG conditional
and trend products. No probability attaches to the choice among legacy cases.
"""

from pkinv.assets import asset_path
import csv
import hashlib
import os

from pkinv.core import montecarlo as mc
from pkinv.paths import OUTPUTS
from pkinv.report import annual_product as ap
from pkinv.report import national_series as ns
from pkinv.activity.store import read_rows
from pkinv.core.io import seq_sum

LEVELS_OUT = asset_path(OUTPUTS, "pakemis_longitudinal_uncertainty.csv")
TREND_OUT = asset_path(OUTPUTS, "pakemis_trend_uncertainty.csv")

N_ITER = 20000
SEED = mc.SEED
SCENARIOS = ("time_correlated", "parameter_typed", "time_independent")
REFERENCE_YEAR = 2024

# ---------------------------------------------------------------------------
# THE TYPED SCENARIO, and why the bracket needed a third member.
#
# The first run of this module published two scenarios and the honest reading of the result
# was uncomfortable: under time_correlated every year-on-year change was resolved to about
# two megatonnes, and under time_independent not one consecutive change was resolved at all.
# An answer that swings that far on an unmeasured assumption is not an answer.
#
# Worse, the wide end is not merely conservative - it is PHYSICALLY IMPOSSIBLE. An IPCC
# default carbon content does not take one value in FY2017-18 and an unrelated value in
# FY2018-19; resampling it per year models a world that does not exist. Publishing it as one
# end of a bracket would invite a reader to split the difference between a plausible bound
# and a nonsensical one.
#
# core.parameters.decompose already splits each component's variance into named shared
# parameters plus a private residual, and it resolves all seventy-five groups in every one of
# the nine years (checked, not assumed). So each group can be TYPED by what it names:
#
#   persists    a physical constant, emission factor, conversion or model parameter. One
#               draw for all nine years, because it is one quantity.
#   resamples   a measured quantity of activity in a particular year. A fresh draw wherever
#               the measurement actually changed.
#
# `resamples` does NOT mean "a fresh draw every year". The qualifier below fingerprints the
# group's members by their PIN YEAR in that year, so a group held constant across years - residential's
# five sub-four-percent streams, waste's 2023 JMP split - shares its draw automatically,
# because it is the same number and not a modelling choice.
#
# An unclassified group RAISES. A default would silently type the next parameter someone adds.
GROUP_TYPE = {
    # -- persists: not a property of a year --------------------------------------------
    "1a3c_ncv": ("persists", "net calorific value of diesel: a physical property of the fuel"),
    "1a3c_hsd_density": ("persists", "high-speed diesel density: a physical property"),
    "waste:swds_k": ("persists", "IPCC first-order-decay rate constant"),
    "waste:swds_docf": ("persists", "IPCC degradable-organic-carbon fraction dissimilated"),
    "waste:ww_bo": ("persists", "IPCC maximum methane-producing capacity"),
    "waste:ww_bod_g_per_cap_day": ("persists", "IPCC per-capita BOD load parameter"),
    "waste:ww_ef_effluent": ("persists", "IPCC effluent N2O emission factor"),
    "waste:burned_fraction": ("persists", "modelled share of waste openly burned, held at "
                                          "reference vintage in every year of the series"),
    "waste_composition": ("persists", "waste composition shares, held at reference vintage"),
    "waste_partition": ("persists", "disposal-route partition, the 2023 JMP split held in "
                                    "every year - national_series declares it held"),
    "post_meter_appliances": ("persists", "modelled post-meter appliance leak rates"),
    "post_meter_nonresidential": ("persists", "modelled post-meter non-residential leak rates"),
    "all domestic stages": ("persists", "aviation stage-length representation: a fleet "
                                        "modelling parameter, not a year's measurement"),
    # rc41 Wave 4 scoped the non-agriculture sectors' groups to their streams; the groups
    # that are not a `factor:`/`ef:` family are typed here by what they name.
    "clinker_factor": ("persists", "the clinker CO2 emission factor (IPCC V3 Ch2)"),
    # rc52: the three activated IPPU categories - factors persist, activities resample
    "ammonia_factor": ("persists", "the calibrated ammonia CO2 factor: one quantity every year multiplies"),
    "steel_factor": ("persists", "the IPCC Tier 1 EAF factor"),
    "lubricant_odu": ("persists", "the IPCC oxidised-during-use fraction"),
    "clinker_fraction_census_implied": ("persists", "rc50: the census-implied clinker-in-cement "
                                                    "ratio - one FY2023-24 measurement applied to "
                                                    "every back-year, not a property of a year"),
    "power:Bagasse heat rate": ("persists", "the declared bagasse cogeneration heat rate "
                                            "(kJ/kWh): a conversion held in every year, "
                                            "listed on the activity side because it is the "
                                            "term the activity uncertainty rides"),
    "waste:dry_matter": ("persists", "IPCC dry-matter fraction of openly burned waste"),
    "waste:oxidation_factor": ("persists", "IPCC open-burning oxidation factor"),
    "waste:swds_f": ("persists", "IPCC fraction of CH4 in generated landfill gas"),
    "waste:swds_mcf": ("persists", "IPCC methane correction factor by disposal-site class"),
    "waste:ww_f_npr": ("persists", "IPCC non-consumed protein factor"),
    "waste:ww_mcf_latrine": ("persists", "IPCC latrine methane correction factor"),
    "waste:ww_mcf_septic": ("persists", "IPCC septic-system methane correction factor"),
    "waste:ww_mcf_sewer": ("persists", "IPCC sewer methane correction factor; the "
                                       "flowing/stagnant reading is a structural scenario"),
    # -- resamples: a quantity measured in a particular year ---------------------------
    "1a1a_toe_activity": ("resamples", "annual power-sector fuel throughput"),
    "1a3b_cng_chain": ("resamples", "annual CNG fuel account"),
    "delivered_gas_ogra_3_31": ("resamples", "a year's OGRA Table 3.31 delivered-gas "
                                             "reading, shared across the four metered "
                                             "modules (rc19)"),
    "1a3b_diesel_control": ("resamples", "annual road diesel control total"),
    "1a3b_petrol_control": ("resamples", "annual road petrol control total"),
    "1a3c_fuel_account": ("resamples", "annual railways fuel account"),
    "1a4b_charcoal": ("resamples", "annual household charcoal quantity"),
    "1a4b_coal": ("resamples", "annual household coal quantity"),
    "1a4b_dung_chain": ("resamples", "annual dung-cake fuel quantity; the chain also carries "
                                     "parameters, and it is typed by the term that moves"),
    "1a4b_firewood": ("resamples", "annual household firewood quantity"),
    "1a4b_gas": ("resamples", "annual metered household gas"),
    "1a4b_generators": ("resamples", "annual household generator fuel"),
    "1a4b_kerosene": ("resamples", "annual household kerosene quantity"),
    "1a4b_lpg": ("resamples", "annual household LPG quantity"),
    "1a4b_residue": ("resamples", "annual crop-residue fuel quantity"),
    "all jet fuel": ("resamples", "annual domestic jet-fuel sales"),
    "cement_activity": ("resamples", "annual cement and clinker production"),
    "ammonia_activity": ("resamples", "NFDC fertilizer production per year"),
    "steel_activity": ("resamples", "QIM billets and ingots per year"),
    "lubricant_activity": ("resamples", "OCAC lubricant sales per year"),
    "fertiliser:nitrogen_N_offtake": ("resamples", "annual national nitrogen offtake"),
    "gas-production-volume": ("resamples", "annual gas production volume"),
    "gas_distribution_pipeline": ("resamples", "distribution network length in the year"),
    "gas_transmission_pipeline": ("resamples", "transmission network length in the year"),
    "industry:OCAC Total Industry liquid fuels": ("resamples", "the year's OCAC Total "
                                                               "Industry liquid-product sales"),
    "lng_import_terminals": ("resamples", "the LNG import terminals OGRA counts in the year"),
    "waste:protein supply (FAOSTAT)": ("resamples", "the year's FAOSTAT per-capita protein "
                                                    "supply"),
    "oil-production-volume": ("resamples", "annual oil production volume"),
    "oil_refining": ("resamples", "annual refinery throughput"),
    "trade_export": ("resamples", "the year's observed clinker exports"),
    "trade_import": ("resamples", "the year's observed clinker imports"),
    "waste_generation": ("resamples", "population-driven annual waste generation"),
}
# Namespaced families, applied when a group has no entry of its own. Kept as prefixes rather
# than expanded because the members are generated: `factor:` carries twenty-six emission
# factors today and gains one whenever a sector declares a new one, and a list of them here
# would be a second register of something data/ already owns.
GROUP_TYPE_PREFIXES = (
    ("factor:", "persists", "an emission factor or conversion constant"),
    ("ef:", "persists", "an emission factor"),
    ("crop:", "resamples", "the year's crop area or production"),
    ("livestock:", "resamples", "the year's livestock head count"),
    ("activity:", "resamples", "the year's source-specific physical activity"),
    ("power:coal_factor_rank_share", "persists", "rank factor composition sensitivity"),
)


def group_type(group):
    """('persists'|'resamples', reason). Raises on anything undeclared - a default here would
    silently type the next parameter someone adds, and typing is the whole model."""
    if group in GROUP_TYPE:
        return GROUP_TYPE[group]
    for prefix, kind, reason in GROUP_TYPE_PREFIXES:
        if group.startswith(prefix):
            return kind, reason
    raise KeyError(
        "dependency group %r is not typed in longitudinal_uncertainty.GROUP_TYPE. Decide "
        "whether it names a quantity that PERSISTS across fiscal years (a factor, a constant, "
        "a held parameter) or one that is RESAMPLED by each year's measurement, and say why."
        % group)

# The published series rounds to five decimals, so a component sum landing within half of the
# last published digit is that cell's own rounding rather than a disagreement. Float summation
# slack sits far below it. Anything larger means the ensemble is describing a different
# inventory from the one the release publishes, and the build stops.
# rc42: a FULL last published digit, not half of one. The published cell is rounded to
# five decimals from a sum that can sit on an exact half-way tie (agriculture FY2022-23,
# 208.5645650...), and half a digit of tolerance turned a one-ULP difference in that sum
# into a build stop on the reviewer's interpreter. The components path and the series path
# both accumulate sequentially now (core.io.seq_sum), so the two agree on this tree; the
# tolerance says what "the same published number" means, which is one unit in the last digit.
CLOSURE_TOL_MT = 1.0e-5 + 1e-9


def _identity(component):
    return "%s|%s|%s" % (component["category"], component["subitem"], component["gas"])


def components_by_year():
    """{fiscal_end_year: {sector: [component]}} for every non-absent sector-year.

    Reuses annual_product.components_for, which is the existing per-year dispatch and already
    documented as "one dispatch, two consumers" - it becomes three rather than acquiring a
    rival. Agriculture is the exception it declares: that function returns None for backcast
    years because the annual product wants a category-gas grain there, while an ensemble needs
    the components themselves, and those exist now that the fiscal path builds them.
    """
    from pkinv.core import registry

    context = ap.build_context()
    out = {}
    for row in ns_rows():
        if row["co2e_Mt_AR5"] == ns.ABSENT:
            continue
        name, fy_end = row["sector"], int(row["fiscal_end_year"])
        if name == "agriculture":
            comps = registry.get("agriculture").components_for_fiscal_year(fy_end)
        else:
            comps = ap.components_for(name, fy_end, context)
        if comps is None:
            raise SystemExit("%s FY%d has no components, so it cannot carry an interval; "
                             "the ensemble will not silently omit half a year" % (name, fy_end))
        out.setdefault(fy_end, {})[name] = comps
    return out


def ns_rows():
    path = asset_path(OUTPUTS, "pakemis_national_series.csv")
    return [r for r in read_rows(path, comments=False) if r["row_kind"] == "sector"]


def assert_closure(by_year):
    """Every sector-year's components must sum to the total the release publishes.

    THE GATE THAT COMES BEFORE ANY DRAW. An ensemble is a statement about dispersion around a
    number, and it is worthless - worse, it is misleading - if the number it disperses around
    is not the published one. This repository has shipped a diagnostic that priced a join it
    could not see and a coverage denominator that carried its own answer; a band around the
    wrong central estimate would be the same defect wearing a confidence interval.
    """
    published = {(r["sector"], int(r["fiscal_end_year"])): r["co2e_Mt_AR5"]
                 for r in ns_rows() if r["co2e_Mt_AR5"] != ns.ABSENT}
    checked = 0
    for fy_end, sectors in sorted(by_year.items()):
        for name, comps in sorted(sectors.items()):
            got = seq_sum(c["co2e_Mt_AR5"] for c in comps)
            want = float(published[(name, fy_end)])
            if abs(got - want) > CLOSURE_TOL_MT:
                raise SystemExit(
                    "the ensemble does not describe the published inventory: %s FY%d "
                    "components sum to %.9f against a published %.9f"
                    % (name, fy_end, got, want))
            checked += 1
    return checked


def pinned_share(by_year):
    """{fiscal_end_year: (pinned_Mt, total_Mt)} - mass whose value is bit-identical elsewhere.

    Measured, not declared. A component pinned here shares a draw in BOTH scenarios because it
    is literally the same number in more than one year, so no choice is being made about it.
    """
    seen = {}
    for fy_end, sectors in by_year.items():
        for name, comps in sectors.items():
            for c in comps:
                key = (name, _identity(c), c["co2e_Mt_AR5"])
                seen[key] = seen.get(key, 0) + 1
    out = {}
    for fy_end, sectors in by_year.items():
        pinned = total = 0.0
        for name, comps in sectors.items():
            for c in comps:
                value = c["co2e_Mt_AR5"]
                total += value
                if seen[(name, _identity(c), value)] > 1:
                    pinned += value
        out[fy_end] = (pinned, total)
    return out


def pin_years(by_year):
    """{(sector, identity, value): first fiscal end-year carrying exactly that value}.

    THE VALUE-FREE QUALIFIER (rc41, the nineteenth review's T-2). Every stream key that
    used to write `repr(co2e)` into a seed - the time_independent `_mc_key`, the resampling
    groups' member fingerprints, the row-private residual qualifier - now writes the PIN
    YEAR instead: the earliest year in the panel whose component is bit-for-bit the same
    number. Two years holding a component at one value still share a draw (same pin year);
    a year whose value moved gets its own. What changed is what a platform can do to the
    seed: a float's repr differs between platforms whenever a libm-sensitive computation
    lands one ulp apart, and that re-seeded the stream; equality between two values that
    the same code computed from the same inputs does not, because any such shift moves
    both. The float is used as a dictionary key here and appears in no string."""
    first = {}
    for fy_end in sorted(by_year):
        for sector, comps in by_year[fy_end].items():
            for c in comps:
                first.setdefault((sector, _identity(c), c["co2e_Mt_AR5"]), fy_end)
    return first


def _keyed(comps, sector, fy_end, scenario, pins=None):
    """Copies carrying the scenario's stream key. NEVER mutates a sector's own rows.

    uncertainty_all makes the same promise for the same reason: a module that expresses a
    correlation scenario by editing the components would leave the next consumer reading a
    scenario it did not ask for.
    """
    out = []
    for c in comps:
        pin = (pins or {}).get((sector, _identity(c), c["co2e_Mt_AR5"]), fy_end)
        # THE FIRST FIELD MUST BE THE ENGINE CATEGORY. core.parameters.original_category reads
        # `_mc_key.split("|", 1)[0]` to recover the category through uncertainty_all's
        # by-sector relabelling, so every category-scoped dependency group in the parameter
        # decomposition is matched against it. A key that led with the sector name instead
        # made the whole factor graph fail to bind - loudly, which is the only reason this
        # cost an hour rather than a release. The contract lived in one docstring; it is
        # asserted below and in tests/test_longitudinal_uncertainty.py now.
        identity = "%s|%s" % (_identity(c), sector)
        if scenario in ("time_correlated", "parameter_typed"):
            # STABLE, and under parameter_typed it must be: `_mc_key` anchors each dependency
            # group's representative member, so writing the year or the value into it would
            # re-seed every shared parameter as well as the residual. The typed scenario
            # varies the two separately, through group_qualifier and residual_qualifier.
            key = identity
        elif scenario == "time_independent":
            # The PIN YEAR, not the year and not the value. Two years that hold a component
            # at the same number get the same key and therefore the same draw, because they
            # are the same number - and the key carries no float string (see pin_years).
            key = "%s|pin|%d" % (identity, pin)
        else:
            raise ValueError("unknown time-correlation scenario %r" % scenario)
        if key.split("|", 1)[0] != c["category"]:
            raise AssertionError("_mc_key must lead with the engine category: %r" % key)
        out.append(dict(c, _mc_key=key, _sector=c.get("_sector", sector), _pin_year=pin))
    return out


def _group_fingerprints(comps):
    """{group: digest of its member values} - what makes `resamples` mean "where it moved".

    A resampling group is qualified by the VALUES its members take in this year, not by the
    year, so a group held at reference vintage in every year keeps one stream without anyone
    having to declare that it is held. The declaration and the arithmetic cannot disagree
    because there is no declaration.
    """
    from pkinv.core import parameters as param_core
    members = {}
    for component, shared, _residual, _derived in param_core.decompose(comps):
        # (member, pin year): the group re-draws where a member's value MOVED, which is
        # what a member value fingerprint expressed - without the float in the digest.
        stamp = "%s|%s|%d" % (_identity(component), component.get("_sector", ""),
                               component.get("_pin_year", 0))
        for group in shared:
            members.setdefault(group, []).append(stamp)
    return {group: hashlib.blake2b("|".join(sorted(values)).encode("utf-8"),
                                   digest_size=8).hexdigest()
            for group, values in members.items()}


def variance_shares(comps):
    """{'persists'|'resamples'|'residual': share of first-order variance}.

    WHY THIS SHIPS BESIDE THE ANSWER. Without this number a reader cannot tell whether the
    width of the typed scenario is a fact about Pakistan or a bug in the typing. The
    first edition of this column found four fifths of the national variance row-private
    residual, and said that naming parameters was the work that would narrow a trend
    band; naming agriculture's factors did exactly that, and the column now reads about
    three quarters persistent, one fifth year-resampling and a few percent residual
    (the shipped CSV carries the live figures).

    THE ARITHMETIC (rc42, the twentieth review's T-2). Members of one dependency group
    draw ONE factor, so their first-order contributions add before they are squared:
    the group's variance term is (sum over members of value x sigma)^2, not the sum of
    the squares. rc41 summed the squares, which dropped every within-group covariance
    and printed 86.63 / 10.67 / 2.70 for FY2023-24 where the covariance-aware shares are
    about 76.95 / 20.85 / 2.20 - the resampling share nearly doubled, because the
    activity groups are the wide ones with many members. The residual stays per row: it
    is by definition what no group shares. The finding the column supports does not
    change - persistent error is what a difference cancels, and it is still the largest
    part - but the reason sentence in the paper follows the corrected number.
    """
    from pkinv.core import parameters as param_core
    return _variance_shares_from(param_core.decompose(comps))


def _variance_shares_from(decomposed):
    """The arithmetic of variance_shares over decompose()'s [(component, {group: sigma},
    sigma_residual, derived)] - separated so a synthetic two-member group can prove the
    covariance term is counted."""
    group_sums = {}
    kinds = {}
    out = {"persists": 0.0, "resamples": 0.0, "residual": 0.0}
    for component, shared, resid, _derived in decomposed:
        value = component["co2e_Mt_AR5"]
        for group, sigma in shared.items():
            if group not in kinds:
                kinds[group], _reason = group_type(group)
            group_sums[group] = group_sums.get(group, 0.0) + value * sigma
        out["residual"] += (value * resid) ** 2
    for group, first_order in group_sums.items():
        out[kinds[group]] += first_order ** 2
    total = sum(out.values())
    return {k: 100.0 * v / total for k, v in out.items()} if total else out


def _run_year(by_year, fy_end, scenario, n_iter, seed, pins=None):
    comps = []
    for sector, rows in sorted(by_year[fy_end].items()):
        comps += _keyed(rows, sector, fy_end, scenario, pins)
    categories = sorted({c["category"] for c in comps})
    if scenario == "parameter_typed":
        positive = [c for c in comps if c["co2e_Mt_AR5"] > 0]
        fingerprint = _group_fingerprints(positive)
        def qualifier(group, _f=fingerprint):
            kind, _reason = group_type(group)
            return None if kind == "persists" else _f.get(group)

        def residual(component):
            # The row-private residual is what the named parameters do NOT explain, so it is
            # a mixture and no typing of it is provable. It is treated as activity-like -
            # resampling wherever the row's value moved - which is the CONSERVATIVE choice:
            # it widens the difference interval rather than narrowing it, and a typed
            # scenario that flattered itself on an unprovable term would be worth less than
            # no typed scenario at all.
            return "resid|%s|%s|%d" % (_identity(component), component.get("_sector", ""),
                                       component.get("_pin_year", 0))

        _stats, totals, _samples = mc.run(comps, categories, n_iter=n_iter, seed=seed,
                                          stream="parameter", return_samples=True,
                                          group_qualifier=qualifier,
                                          residual_qualifier=residual)
        return totals
    _stats, totals, _samples = mc.run(comps, categories, n_iter=n_iter, seed=seed,
                                      stream="per_component", return_samples=True)
    return totals


def _interval(samples):
    ordered = sorted(samples)
    p025 = mc.percentile(ordered, 0.025)
    p50 = mc.percentile(ordered, 0.50)
    p975 = mc.percentile(ordered, 0.975)
    return p025, p50, p975


def levels(by_year, n_iter=N_ITER, seed=SEED):
    """[row] per (fiscal year, scenario), plus the draws so differences reuse them."""
    pinned = pinned_share(by_year)
    pins = pin_years(by_year)
    shares = {}
    for fy_end in sorted(by_year):
        comps = []
        for sector, rows_ in sorted(by_year[fy_end].items()):
            comps += _keyed(rows_, sector, fy_end, "parameter_typed", pins)
        shares[fy_end] = variance_shares([c for c in comps if c["co2e_Mt_AR5"] > 0])
    rows, draws = [], {}
    for scenario in SCENARIOS:
        for fy_end in sorted(by_year):
            totals = _run_year(by_year, fy_end, scenario, n_iter, seed, pins)
            draws[(scenario, fy_end)] = totals
            p025, p50, p975 = _interval(totals)
            deterministic = sum(c["co2e_Mt_AR5"]
                                for rows_ in by_year[fy_end].values() for c in rows_)
            quantile_se = mc.batch_quantile_se(totals) or {}
            pinned_mt, total_mt = pinned[fy_end]
            rows.append({
                "fiscal_end_year": fy_end,
                "period_label": "FY%d-%02d" % (fy_end - 1, fy_end % 100),
                "scenario": scenario,
                "covered_total_Mt": round(deterministic, 5),
                "P2.5_Mt": round(p025, 4),
                "P50_Mt": round(p50, 4),
                "P97.5_Mt": round(p975, 4),
                "rel_down_pct_95": round(100.0 * (p50 - p025) / p50, 3),
                "rel_up_pct_95": round(100.0 * (p975 - p50) / p50, 3),
                "half_width_se_pp": round(mc.batch_standard_error(totals) or 0.0, 4),
                "p50_se_Mt": round(quantile_se.get("p50_se", 0.0), 4),
                "pinned_mass_share_pct": round(100.0 * pinned_mt / total_mt, 2),
                "variance_share_persists_pct": round(shares[fy_end]["persists"], 2),
                "variance_share_resamples_pct": round(shares[fy_end]["resamples"], 2),
                "variance_share_residual_pct": round(shares[fy_end]["residual"], 2),
                "n_iter": n_iter,
            })
    return rows, draws


def _restricted_draws(by_year, fy_end, sectors, scenario, n_iter, seed, cache, pins=None):
    """Draws for one year over a SUBSET of its sectors, memoised per (year, subset, scenario).

    The components carry their own stream keys, so dropping a sector leaves every remaining
    component drawing the same numbers it drew in the full run. That is asserted rather than
    assumed: where a pair's two years already share every sector the restriction is a no-op and
    must reproduce the unrestricted draws exactly, which `tests/test_longitudinal_uncertainty`
    checks.
    """
    key = (fy_end, tuple(sorted(sectors)), scenario)
    if key not in cache:
        subset = {fy_end: {s: rows for s, rows in by_year[fy_end].items() if s in sectors}}
        cache[key] = _run_year(subset, fy_end, scenario, n_iter, seed, pins)
    return cache[key]


def differences(by_year, draws, n_iter=N_ITER, seed=SEED):
    """[row] per (year pair, scenario) - the interval this release has never published.

    Differenced DRAW BY DRAW, not by combining two published intervals. That is the entire
    point: iteration i of FY2021-22 and iteration i of FY2022-23 share the same z for every
    component whose stream key they share, so the subtraction cancels the shared error the way
    the real quantity does. Combining the two intervals in quadrature would throw that away
    and reproduce the wrong answer a reader gets today.

    EVERY PAIR IS RESTRICTED TO THE SECTORS BOTH YEARS HAVE, and this function used to report
    that restriction without performing it. `comparable_sectors` counted the intersection while
    the point estimate summed every sector in each year, so a pair spanning FY2015-16 - where
    transport and industry are absent - subtracted eight sectors from ten and published the
    result under a column saying eight.

    It was not a small error. The headline nine-year change read 131.27 Mt where the
    comparable-scope change is 80.28 Mt: 50.99 Mt, thirty-nine per cent of the published
    figure, was two sectors ENTERING THE RECORD rather than emissions moving. The draws behind
    the interval were contaminated the same way, so the band was wrong too and not merely the
    point.

    A LABEL IS NOT A RESTRICTION. The column now describes what was actually summed.
    """
    years = sorted(by_year)
    pairs = [(years[i], years[i + 1]) for i in range(len(years) - 1)]
    # The full window, and the window over the years every sector reports. The second is the
    # primary trend: the first cannot separate emissions moving from the record filling in,
    # however carefully its scope is restricted, because the sectors it drops are a fifth of
    # the inventory.
    pairs.append((years[0], years[-1]))
    common_start = min(y for y in years if set(by_year[y]) == set(by_year[years[-1]]))
    if common_start != years[0]:
        pairs.append((common_start, years[-1]))
    rows, cache = [], {}
    pins = pin_years(by_year)
    for scenario in SCENARIOS:
        for early, late in pairs:
            shared = set(by_year[early]) & set(by_year[late])
            restricted = (shared != set(by_year[early])) or (shared != set(by_year[late]))
            if restricted:
                a = _restricted_draws(by_year, early, shared, scenario, n_iter, seed, cache,
                                      pins)
                b = _restricted_draws(by_year, late, shared, scenario, n_iter, seed, cache,
                                      pins)
            else:
                a, b = draws[(scenario, early)], draws[(scenario, late)]
            delta = [y - x for x, y in zip(a, b)]
            p025, p50, p975 = _interval(delta)
            # Significance is stated PER SCENARIO and never merged into one verdict: the two
            # scenarios are a bracket on a quantity nobody has measured, and collapsing them
            # into a single yes or no would hide which end of the bracket carried it.
            significant = "yes" if (p025 > 0.0 or p975 < 0.0) else "no"
            # THE SAME SECTOR SET ON BOTH SIDES, which is what `comparable_sectors` says.
            point = (sum(c["co2e_Mt_AR5"] for sector in shared
                         for c in by_year[late][sector])
                     - sum(c["co2e_Mt_AR5"] for sector in shared
                           for c in by_year[early][sector]))
            if late - early == 1:
                kind = "consecutive"
            elif early == years[0]:
                # "window_coverage_transition" until rc20: the pair straddled the
                # eight-to-ten-sector step. The FY2015-16 recovery made the first
                # year full-scope, so this window is now simply the full panel.
                kind = "window_full_panel"
            else:
                kind = "window_common_scope"
            rows.append({
                "from_period": "FY%d-%02d" % (early - 1, early % 100),
                "to_period": "FY%d-%02d" % (late - 1, late % 100),
                "pair_kind": kind,
                "scenario": scenario,
                "difference_Mt": round(point, 5),
                "P2.5_Mt": round(p025, 4),
                "P50_Mt": round(p50, 4),
                "P97.5_Mt": round(p975, 4),
                "half_width_Mt": round((p975 - p025) / 2.0, 4),
                "significant_at_95": significant,
                "comparable_sectors": len(shared),
                "sectors_dropped": ";".join(sorted(
                    (set(by_year[early]) | set(by_year[late])) - shared)) or "none",
                "scope_note": ("restricted to the sectors both years report"
                               if restricted else "both years report the same sectors"),
                "n_iter": n_iter,
            })
    return rows


def _write(path, rows, header_lines):
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        header_lines = ["LEGACY ANALYTICAL SENSITIVITY: not the current native material-flow uncertainty; "
                        "scenario endpoints are not uncertainty bounds."] + list(header_lines)
        for line in header_lines:
            handle.write("# %s\n" % line)
        rows = [dict(row, model_basis="legacy_parameter_graph_sensitivity_not_native_material_flow")
                for row in rows]
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


PREFIX_N_ITER = 200
PREFIX_OUT = asset_path(OUTPUTS, "pakemis_longitudinal_prefix.csv")


def prefix_rows(draws, n=PREFIX_N_ITER):
    """The first n national-total draws of every (scenario, fiscal year) stream.

    The longitudinal engine ships summary statistics of 20,000 draws and no samples, so
    until rc41 nothing a second platform produced could be compared with what this one
    shipped - the reviewer's T-2 asked for exactly that comparison. Draw d is draw d (the
    streams are seeded per component and drawn sequentially; a 200-draw run reproduces the
    first 200 of a 20,000-draw run bit for bit on the same platform, asserted in
    tests/test_longitudinal_uncertainty.py), so these rows are a prefix of the published
    pool and a rerun on another platform must match them to libm precision."""
    out = []
    for (scenario, fy_end), totals in sorted(draws.items()):
        for i, value in enumerate(totals[:n]):
            out.append({"scenario": scenario, "fiscal_end_year": fy_end, "draw_index": i,
                        "covered_total_Mt": repr(float(value))})
    return out


def main():
    by_year = components_by_year()
    checked = assert_closure(by_year)
    level_rows, draws = levels(by_year)
    trend_rows = differences(by_year, draws)
    _write(PREFIX_OUT, prefix_rows(draws), [
        "First %d draws per legacy scenario/year, for reproducibility only." % PREFIX_N_ITER,
        "Parameter/row identities and pin years determine the shared random streams.",
    ])
    _write(LEVELS_OUT, level_rows, [
        "Conditional percentiles under the named legacy component/parameter dependence cases.",
        "Conserved native source engines are not replayed here. Use the separate GHG "
        "conditional and paired-trend products for the current native uncertainty.",
        "Cases have no assigned probabilities and their endpoints do not bound true uncertainty.",
        "pinned_mass_share_pct records repeated deterministic component values. "
        "variance_share_* describes the analytical graph, not native source-driver importance.",
    ])
    _write(TREND_OUT, trend_rows, [
        "Legacy case differences are paired by draw identity and restricted to comparable sectors.",
        "significant_at_95 is conditional on the selected analytical sensitivity case; "
        "it does not establish a universally resolved trend or bound the current native interval.",
    ])

    print("longitudinal uncertainty -> %s" % os.path.relpath(LEVELS_OUT))
    print("  %d sector-years closed to the published series before any draw" % checked)
    by_key = {(r["scenario"], r["fiscal_end_year"]): r for r in level_rows}
    print("  %-11s %10s  %-16s %-16s %7s"
          % ("year", "total Mt", "typed 95%", "correlated 95%", "pinned"))
    for fy_end in sorted(by_year):
        t_ = by_key[("parameter_typed", fy_end)]
        c = by_key[("time_correlated", fy_end)]
        print("  %-11s %10.2f  -%5.1f%% +%5.1f%%   -%5.1f%% +%5.1f%%   %5.1f%%"
              % (c["period_label"], c["covered_total_Mt"],
                 t_["rel_down_pct_95"], t_["rel_up_pct_95"],
                 c["rel_down_pct_95"], c["rel_up_pct_95"], c["pinned_mass_share_pct"]))

    print("\ntrend intervals -> %s" % os.path.relpath(TREND_OUT))
    print("  %-22s %9s  %-26s %-26s"
          % ("change", "Mt", "PARAMETER-TYPED", "independent sensitivity case"))
    trend = {(r["scenario"], r["from_period"], r["to_period"]): r for r in trend_rows}
    for row in trend_rows:
        if row["scenario"] != "parameter_typed":
            continue
        other = trend[("time_independent", row["from_period"], row["to_period"])]
        print("  %-22s %+9.2f  [%+8.2f,%+8.2f] %-3s  [%+8.2f,%+8.2f] %-3s"
              % ("%s->%s" % (row["from_period"], row["to_period"]), row["difference_Mt"],
                 row["P2.5_Mt"], row["P97.5_Mt"], row["significant_at_95"],
                 other["P2.5_Mt"], other["P97.5_Mt"], other["significant_at_95"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
