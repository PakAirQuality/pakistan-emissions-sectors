"""The residential sector's uncertainty: parametric where a percentage is honest,
structural where a choice is discrete, and the 20:1 headline replaced by a distribution.

THE SHAPE OF THIS SECTOR'S UNCERTAINTY. Gas CO2 at +/-10.8 percent is a metered quantity
on a 4 percent factor - power-station quality - while the biomass CH4 and N2O rows that
supply a third of the sector carry +/-150-plus factor intervals on activity data ranging
from design-weighted surveys (firewood and, since rc67, dung: 35 percent each) to
supply-side controls. One number cannot describe both halves; this module publishes
the decomposition.

PARAMETRIC. The grouped Approach 1 treats each stream's activity term as perfectly
shared across its gas rows (the same metered account, survey total or ledger drives CO2,
CH4 and N2O alike - linear within stream, quadrature between terms); the independent
treatment is published alongside, and the conservative grouped figure is the headline.
Computed HERE, analytically: the shipped components already carry the dung correlation
group the national pooled Monte Carlo consumes, and restamping them would reorder the
seed-42 gauss stream every published national percentile depends on.

STRUCTURAL - named cases, conditional intervals, no probabilities. The two firewood
cases are the anchors this sector has actually used (the HIES survey now; FAOSTAT, flaw
and all, before August 2026). The dung cases (rc67) are readings of one quantity,
the cake households burn, around the survey series the reference now carries:
configuration L (all the dung agriculture diverts), the series with the 2018-19 round's
rate held, the 2024-25 round as measured, and two readings of configuration L's own
mass chain kept for traceability (legacy VS pairing, dry-ash-free NCV). The PM-definition and stove-mix rows are air-scope and
declaration-and-sensitivity rows: the PM-definition row is a scope declaration, and
the stove-mix and residue-family rows are declared deterministic sensitivities on the
MTF stove typology and the factor-family choice.

THE PM RATIO IS SAMPLED, NOT ASSERTED. The paper's twenty-to-one claim against road
transport becomes a distribution: every residential PM2.5 row and the road exhaust row
drawn lognormally on their published uncertainties, ratio percentiles reported. Matched
basis - primary exhaust PM2.5 from each sector's own fuel-anchored layer; road
non-exhaust wear PM is exploratory in that sector and excluded here as there.

SCENARIO_SEED = 1404 keeps this module's draws off the national seed-42 stream entirely.

Usage:  python3 -m pkinv.sectors.residential.uncertainty
Writes: outputs/residential_uncertainty_2024.csv,
        outputs/residential_uncertainty_inputs_2024.csv,
        outputs/residential_uncertainty_scenarios_2024.csv,
        outputs/residential_pm_ratio_2024.csv
"""

from pkinv.assets import asset_path
import csv
import math
import os
import random

from pkinv.core import montecarlo as mc_core
from pkinv.core.uncertainty import combine_sum
from pkinv.paths import OUTPUTS
from pkinv.sectors.residential import air_pollutants, combustion, engine, hies
from pkinv.sectors.residential.data import ResidentialData
from pkinv.core.io import write_table

SCENARIO_SEED = 1404          # private stream; the national MC's seed 42 is untouched
INTERPRETATION = "conditional parametric interval; no structural probability"

# stream label (first token of subitem) -> activity_uncert parameter suffix
_AD_KEY = {s.split()[0]: k for s, _i, k in combustion.FOSSIL_FUELS}
_AD_KEY.update({s.split()[0]: k for s, _i, k, _g in combustion.BIOMASS_FUELS})


def _stream_word(c):
    return c["subitem"].rsplit(" ", 1)[0].split()[0]


def approach1(data):
    """Grouped and independent Approach-1 percentages for the sector total.

    Grouped: each stream's activity term is one perfectly-correlated component across
    its gas rows, factor terms stay independent. Independent: the published per-row
    uncertainties combined as if unrelated - the national rollup's generic view.
    """
    comps = engine.build_components(data)
    total = sum(c["co2e_Mt_AR5"] for c in comps)
    var = 0.0
    for word, ad_key in _AD_KEY.items():
        act_u = data.p("activity_uncert_" + ad_key)
        rows = [c for c in comps if _stream_word(c) == word]
        stream_total = sum(c["co2e_Mt_AR5"] for c in rows)
        var += (act_u * stream_total) ** 2                  # shared, linear within stream
        for c in rows:                                       # factor residuals, quadrature
            factor_u = math.sqrt(max(c["uncert_pct"] ** 2 - act_u ** 2, 0.0))
            var += (factor_u * c["co2e_Mt_AR5"]) ** 2
    grouped = math.sqrt(var) / total
    _t, indep = combine_sum([(c["co2e_Mt_AR5"], c["uncert_pct"], None) for c in comps])
    return {"category": combustion.CATEGORY, "co2e_Mt_AR5": total,
            "approach1_pct_grouped": grouped, "approach1_pct_independent": indep}


def variance_decomposition(data):
    """Per-stream, per-term (activity vs factor) shares of the grouped Approach-1
    variance - which lever actually carries the sector's band."""
    comps = engine.build_components(data)
    total = sum(c["co2e_Mt_AR5"] for c in comps)
    terms = []
    for word, ad_key in _AD_KEY.items():
        act_u = data.p("activity_uncert_" + ad_key)
        rows = [c for c in comps if _stream_word(c) == word]
        stream_total = sum(c["co2e_Mt_AR5"] for c in rows)
        terms.append((word, "activity", (act_u * stream_total) ** 2))
        fvar = 0.0
        for c in rows:
            factor_u = math.sqrt(max(c["uncert_pct"] ** 2 - act_u ** 2, 0.0))
            fvar += (factor_u * c["co2e_Mt_AR5"]) ** 2
        terms.append((word, "factors", fvar))
    var_total = sum(v for _w, _t, v in terms)
    out = []
    for word, term, v in sorted(terms, key=lambda t: -t[2]):
        out.append({"stream": word, "term": term,
                    "variance_share_pct": round(100.0 * v / var_total, 2),
                    # u is already in percent, so sqrt(v)/total is percent of total
                    "sd_contribution_pct_of_total":
                        round(math.sqrt(v) / total, 2)})
    return out


def _scaled(comps, scale, words):
    out = []
    for c in comps:
        c2 = dict(c)
        if _stream_word(c) in words:
            for k in ("co2e_Mt_AR5", "co2e_Mt_AR6", "emissions_Gg"):
                c2[k] = c2[k] * scale
        out.append(c2)
    return out


def structural_scenarios(data, n_iter=10000, seed=SCENARIO_SEED):
    tj = combustion.fuel_TJ(data)
    tj_faostat = combustion.fuel_TJ(data, firewood_basis="faostat")
    firewood_scale = tj_faostat["Firewood"] / tj["Firewood"]

    # The dung scenarios. The REFERENCE is the survey series (rc67); each scenario scales
    # the reference dung rows to another reading of the SAME quantity, household cake.
    from pkinv.sectors.residential import timeseries
    vs = combustion.dung_vs_kg(data)
    survey = combustion.dung_air_dry_kg(data)
    ledger = combustion.dung_air_dry_kg(data, basis="ledger")
    ledger_scale = ledger / survey
    legacy_scale = vs / survey
    daf_scale = (vs * data.p("dung_ncv_daf")) / (
        survey * data.efv("residential_ncv", "Other Primary Solid Biomass"))
    rate_2019 = (hies.national_quantity("dung_cake", "hies2019")[0]
                 / timeseries.households(2019))
    round_2019_scale = rate_2019 * timeseries.households(data.year) / survey
    round_2025_scale = hies.national_quantity("dung_cake", "hies2025")[0] / survey

    # The residue-fuel bracket (rc67). The survey records residue fuel in rupees, so the
    # ledger keeps the quantity; the two survey-internal prices that bound it are priced
    # here as the dung readings are. Both ends are consistent with the residue ledger
    # without a second agriculture run: the difference is exchanged with the ledger's
    # "other" destination (fodder, bedding, sale), which carries no emission and is five
    # times the fuel destination.
    residue = combustion.residue_air_dry_kg(data)
    residue_low, residue_high = hies.residue_implied_range_kg()
    residue_low_scale, residue_high_scale = residue_low / residue, residue_high / residue

    cases = [
        ("reference", lambda: engine.build_components(data), "the estimate"),
        ("firewood_faostat",
         lambda: _scaled(engine.build_components(data), firewood_scale, ("Firewood",)),
         "the superseded anchor: FAOSTAT's flagged, unmoving series on its oven-dry-"
         "with-as-received-NCV pairing, %.0f%% of the HIES quantity - kept because a "
         "reader must be able to see what the re-anchoring did" % (100 * firewood_scale)),
        ("firewood_none",
         lambda: engine.build_components(data, woodfuel_override="none"),
         "the exclusion bound: the sector with no firewood stream at all"),
        ("dung_all_diverted_household",
         lambda: _scaled(engine.build_components(data), ledger_scale, ("Dung",)),
         "CONFIGURATION L: every tonne of dung agriculture diverts burned by households, "
         "%.1f times the survey quantity. The reference of every release through rc66, "
         "retained as a destination assumption for the diverted dung and not as a "
         "reading of household use: no household survey supports it. The interval "
         "is the reference dung rows scaled, so it carries the survey's activity width "
         "(35 per cent); configuration L's own chain is wider (50 per cent on the "
         "diverted nitrogen), and its own run is residential_configurations_*.csv"
         % ledger_scale),
        ("dung_survey_rate_2018_19",
         lambda: _scaled(engine.build_components(data), round_2019_scale, ("Dung",)),
         "the survey series with the 2018-19 round's per-household rate held to the "
         "reference year instead of interpolated toward the 2024-25 round: %.0f%% of "
         "the reference. The two rounds disagree by a factor of 1.5 per household, "
         "and the later round's total is concentrated in a few large reports"
         % (100 * round_2019_scale)),
        ("dung_survey_round_2024_25_as_measured",
         lambda: _scaled(engine.build_components(data), round_2025_scale, ("Dung",)),
         "the 2024-25 round's national quantity taken as the reference year's own, "
         "without interpolation: %.0f%% of the reference. The reference year lies "
         "between the rounds, and firewood, the other survey-primary fuel, takes this "
         "round as measured in the reference year" % (100 * round_2025_scale)),
        ("dung_basis_legacy_vs",
         lambda: _scaled(engine.build_components(data), legacy_scale, ("Dung",)),
         "A READING OF CONFIGURATION L's mass chain, kept for traceability: the diverted "
         "dung as ash-free volatile solids on the as-received NCV - the three-bases "
         "conflation the August 2026 audit retired, %.0f%% of configuration L's stream"
         % (100 * legacy_scale / ledger_scale)),
        ("dung_basis_daf",
         lambda: _scaled(engine.build_components(data), daf_scale, ("Dung",)),
         "A READING OF CONFIGURATION L's mass chain: VS mass on an independent "
         "dry-ash-free NCV of %.1f TJ/Gg - lands within %.0f%% of configuration L's "
         "corrected pairing, which is the point"
         % (data.p("dung_ncv_daf"), 100 * abs(1 - daf_scale / ledger_scale))),
        # appended, not inserted: each case draws on seed + its position, so a case added
        # in the middle would move the published intervals of every case after it
        ("residue_fuel_survey_bracket_low",
         lambda: _scaled(engine.build_components(data), residue_low_scale, ("Crop",)),
         "household residue fuel at the LOW end of the survey's price bracket: the "
         "survey's residue expenditure at firewood's unit value, %.1f Mt air-dry "
         "against the ledger's %.1f (%.0f%% of the reference stream). The survey "
         "records rupees, not kilograms, so neither end is an observed quantity; "
         "the residue not burned stays in the ledger's other destination and "
         "nothing in agriculture moves"
         % (residue_low / 1e9, residue / 1e9, 100 * residue_low_scale)),
        ("residue_fuel_survey_bracket_high",
         lambda: _scaled(engine.build_components(data), residue_high_scale, ("Crop",)),
         "household residue fuel at the HIGH end of the survey's price bracket: the "
         "same expenditure at dung cake's unit value, the cheapest biomass the survey "
         "prices, %.1f Mt air-dry (%.0f%% of the reference stream). The extra mass "
         "is drawn from the ledger's other destination, which holds several times "
         "that; the reference stream is itself an upper-bound household allocation "
         "of ALL residue fuel use, so this end stacks one bound on another"
         % (residue_high / 1e9, 100 * residue_high_scale)),
    ]
    out = []
    for i, (name, build, note) in enumerate(cases):
        comps = build()
        det = sum(c["co2e_Mt_AR5"] for c in comps)
        stats, _s = mc_core.run(comps, [combustion.CATEGORY], n_iter=n_iter,
                                seed=seed + i)
        s = stats[combustion.CATEGORY]
        out.append({"structural_scenario": name, "scope": "GHG Mt CO2e AR5",
                    "deterministic": det, "mean": s["mean"], "P2.5": s["p025"],
                    "P50": s["p50"], "P97.5": s["p975"], "note": note,
                    "interpretation": INTERPRETATION})

    pm_total = sum(r["emissions_kt"] for r in air_pollutants.compute(data)
                   if r["pollutant"] == "PM2.5")
    out.append({"structural_scenario": "pm_condensables", "scope": "air: PM2.5 kt",
                "deterministic": pm_total, "mean": "", "P2.5": "", "P50": "",
                "P97.5": "", "note":
                    "SCOPE DECLARATION, not a sample: the biomass rows carry Andreae "
                    "field measurements (plume PM, condensables partly included by "
                    "capture); the fossil rows carry EMEP factors whose own review "
                    "note says filterable-vs-total is unresolved. No published split "
                    "supports sampling the definition; the CCAC bridge names it as a "
                    "wedge instead", "interpretation": INTERPRETATION})
    # Technology-mix sensitivity on the MTF stove typology (data/activity/
    # residential/stove_mix_mtf.csv): the implicit reference class of the Andreae
    # field-type factors is the traditional/open stove that dominates rural biomass
    # cooking. The MTF's 6.2% stacking plus the small clean-stove share among
    # biomass-USING households bounds how much biomass mass could already burn in
    # an improved class; the EMEP small-combustion advanced-vs-conventional span
    # (~factor 5 on filterable PM) prices that class. Declared arithmetic:
    # PM_low = PM_biomass x (1 - improved_share x (1 - 1/5)) with improved_share
    # = 0.10 as the declared upper bound for biomass-burning households (clean-fuel
    # stoves burn gas/LPG, not biomass, so the 44.3% clean share does NOT transfer;
    # stacking 6.2% plus improved-biomass adoption bounds it near ten percent).
    pm_biomass = sum(r["emissions_kt"] for r in air_pollutants.compute(data)
                     if r["pollutant"] == "PM2.5"
                     and r["subitem"].split()[0] in ("Dung", "Firewood", "Crop",
                                                     "Charcoal"))
    improved_share = 0.10
    stove_low = pm_total - pm_biomass * improved_share * (1.0 - 1.0 / 5.0)
    out.append({"structural_scenario": "stove_mix_mtf", "scope": "air: PM2.5 kt",
                "deterministic": stove_low, "mean": "", "P2.5": "", "P50": "",
                "P97.5": "",
                "note": "technology-mix sensitivity on the MTF 2021-22 stove "
                        "typology: if up to 10%% of biomass-burning households "
                        "already use an improved class (bounded by the survey's "
                        "6.2%% stacking and low improved-biomass adoption), biomass "
                        "PM falls by the EMEP advanced-vs-conventional span for "
                        "that share - the reference assumes the traditional/open "
                        "class throughout, consistent with 71.8%% of rural "
                        "households. The remaining unlock is the fuel-by-device "
                        "crosswalk the MTF report does not publish",
                "interpretation": INTERPRETATION})
    # Residue factor-family sensitivity: the residue rows mirror FIELD-burning
    # factors (nearest available); the Andreae domestic-biofuel family is the
    # declared alternative for stove combustion.
    residue_pm = sum(r["emissions_kt"] for r in air_pollutants.compute(data)
                     if r["subitem"].startswith("Crop residues")
                     and r["pollutant"] == "PM2.5")
    wood_f = data.efv("residential_biofuel", "Gef_PM25_Wood")
    residue_f = data.efv("residential_biofuel", "Gef_PM25_Residue")
    out.append({"structural_scenario": "residue_factor_family",
                "scope": "air: PM2.5 kt",
                "deterministic": pm_total - residue_pm * (1.0 - wood_f / residue_f),
                "mean": "", "P2.5": "", "P50": "", "P97.5": "",
                "note": "residue PM under the Andreae domestic-biofuel family "
                        "(%.1f g/kg) instead of the field-burning mirror (%.1f) - "
                        "the factors are field measurements applied to stove "
                        "combustion as the nearest available class, and this row "
                        "prices the declared alternative" % (wood_f, residue_f),
                "interpretation": INTERPRETATION})
    return out


def _sigma(u_pct):
    """Lognormal sigma from a 95% relative half-width - the ONE inventory-wide
    convention (core.montecarlo.sigma_log, the exact CV inversion). An earlier
    edition used the multiplicative-CI reading ln(1+u/100)/1.96 here, ~12 percent
    narrower at u=30: the sixth review's harmonisation ask, and the reason the
    published PM-ratio interval widened slightly at unchanged point estimates."""
    return mc_core.sigma_log(u_pct)


def pm_ratio_distribution(data, n_iter=10000, seed=SCENARIO_SEED + 100,
                          dung_basis=None):
    """Sampled R = residential primary PM2.5 / road-transport primary exhaust PM2.5,
    PARAMETRIC UNDER ONE CONFIGURATION - the interval is conditional on the dung
    activity configuration passed in, and the structural span across configurations
    is published alongside (main), never blended into one interval.

    Matched basis: each sector's own fuel-anchored exhaust layer; road wear PM is
    exploratory there and excluded here. Every PM2.5 row is drawn mean-preserving
    lognormally on its published row uncertainty, rows independent (the shared-activity
    refinement moves the ratio's spread by little next to the 50-percent-class factor
    terms, and the simplicity is auditable).
    """
    from pkinv.sectors.transport import air_pollutants as road_air
    from pkinv.sectors.transport.data import TransportData
    dung_basis = combustion.reference_basis(dung_basis)

    res_rows = [(r["emissions_kt"], _sigma(r["uncert_pct"]))
                for r in air_pollutants.compute(data, dung_basis=dung_basis)
                if r["pollutant"] == "PM2.5"]
    # the whole exhaust fleet: the air layer is per (class, fuel, process) since the
    # EMEP Tier 1 refactor, and the ratio's denominator is the exhaust fleet sum -
    # wear stays outside, per this docstring's own exclusion. Tier 1 publishes a
    # DIFFERENT min-max width per class and fuel, so the denominator is drawn per row
    # exactly as the numerator is (the single-lognormal shortcut described the one
    # shared workbook class and died with it).
    road_rows = [(r["emissions_kt"], _sigma(r["uncert_pct"]))
                 for r in road_air.compute(TransportData())
                 if r["pollutant"] == "PM2.5" and r["process"] == "exhaust"]
    road_val = sum(v for v, _s in road_rows)

    rng = random.Random(seed)
    ratios = []
    for _ in range(n_iter):
        num = sum(v * math.exp(rng.gauss(0.0, s) - s * s / 2.0) for v, s in res_rows)
        den = sum(v * math.exp(rng.gauss(0.0, s) - s * s / 2.0) for v, s in road_rows)
        ratios.append(num / den)
    ratios.sort()
    p = lambda q: ratios[int(q * n_iter)]
    det = sum(v for v, _s in res_rows) / road_val
    return {"configuration": {"ledger": "L", "survey": "S"}[dung_basis],
            "deterministic_ratio": det, "P2.5": p(0.025), "P50": p(0.50),
            "P97.5": p(0.975), "n_iter": n_iter,
            "note": "PARAMETRIC 95%% interval under configuration %s: residential "
                    "primary PM2.5 over road primary exhaust PM2.5, both from "
                    "fuel-anchored layers; road non-exhaust wear PM excluded on both "
                    "sides by the ratio's definition"
                    % {"ledger": "L", "survey": "S"}[dung_basis]}


def inputs_register(data):
    def row(variable, central, unit, u, dist, source, applies_to, group, klass, note=""):
        return {"variable": variable, "central_value": central, "unit": unit,
                "uncert_pct_95": u, "distribution": dist, "source": source,
                "applies_to": applies_to, "correlation_group": group,
                "uncertainty_class": klass, "note": note}

    d = data
    rows = [
        row("Domestic gas volume FY2023-24", d.quantity("Natural Gas"), "MMCFD",
            d.p("activity_uncert_gas"), "lognormal",
            "OGRA Table 3.31 residential row", "all gas rows",
            "delivered_gas_ogra_3_31", "parametric",
            "metered at the consumer; the best-measured stream in the sector. "
            "SHARED GROUP (rc19): one OGRA Table 3.31 publication behind the "
            "residential, CNG, industrial and captive delivered volumes, so "
            "their activity errors share one draw direction; the gross-to-net "
            "conversion below stays module-local in 1a4b_gas"),
        row("Gas gross-to-net conversion", d.p("gas_mmcf_to_TJ"), "TJ/MMCF",
            d.pu("gas_mmcf_to_TJ"), "lognormal", d.ps("gas_mmcf_to_TJ"),
            "all gas rows", "1a4b_gas", "parametric",
            "the sector's largest single CO2 lever; billed gross, factored net"),
        row("LPG national supply", d.quantity("Liquefied Petroleum Gases"), "t/yr",
            "", "lognormal", "OGRA Table 5.1", "all LPG rows", "1a4b_lpg", "parametric",
            "firm total; the split below carries the uncertainty"),
        row("LPG domestic share", d.p("lpg_domestic_share"), "fraction",
            d.pu("lpg_domestic_share"), "lognormal", d.ps("lpg_domestic_share"),
            "all LPG rows", "1a4b_lpg", "parametric",
            "chart-read from Figure 5.2; HIES puts the household quantity 25% above "
            "this share's implication, in the direction the parameter note predicted"),
        row("Household kerosene", d.quantity("Other Kerosene"), "kt/yr",
            d.p("activity_uncert_kerosene"), "lognormal",
            "OCAC sectoral sales, DOMESTIC row (the August 2026 correction from the "
            "rounded 60 kt)", "all kerosene rows", "1a4b_kerosene", "parametric"),
        row("HIES firewood quantity", hies.firewood_air_dry_kg(), "kg/yr air-dry",
            d.p("activity_uncert_woodfuel"), "lognormal",
            "HIES 2024-25 design-weighted total; clustered design SE 7.1%",
            "all firewood rows", "1a4b_firewood", "parametric",
            "the 35% prices recall, out-of-dwelling and enterprise use on top of the "
            "7.1% design SE; 2018-19 within 6%, FAOSTAT moisture-matched within 7%"),
        row("Firewood air-dry moisture", d.p("firewood_moisture_ar"), "fraction",
            d.pu("firewood_moisture_ar"), "lognormal", d.ps("firewood_moisture_ar"),
            "firewood air rows (oven-dry mass)", "1a4b_firewood", "parametric"),
        row("Household dung cake (survey series)",
            combustion.dung_air_dry_kg(d) / 1e9, "Mt/yr air-dry",
            d.p("activity_uncert_dung_survey"), "lognormal",
            "HIES 2018-19 and 2024-25, per-household quantity interpolated",
            "all dung rows", "1a4b_dung_chain", "parametric",
            "the reference since rc67. Design SE 6.6% (2024-25) and 4.1% (2018-19); "
            "the 35% prices the two rounds' disagreement (a factor of 1.5 per "
            "household) on top of it. Configuration L's chain (diverted nitrogen, "
            "50%) applies only where all diverted dung is burned in households"),
        row("Dung cake ash (dry basis)", d.p("dung_ash_frac_dry"), "fraction",
            d.pu("dung_ash_frac_dry"), "lognormal", d.ps("dung_ash_frac_dry"),
            "dung mass chain", "1a4b_dung_chain", "parametric"),
        row("Dung cake moisture (as-received)", d.p("dung_cake_moisture_ar"),
            "fraction", d.pu("dung_cake_moisture_ar"), "lognormal",
            d.ps("dung_cake_moisture_ar"), "dung mass chain", "1a4b_dung_chain",
            "parametric"),
        row("Residue fuel mass (ledger)", combustion.residue_dry_kg(d) / 1e9,
            "Mt/yr dry", d.p("activity_uncert_residue"), "lognormal",
            "agriculture residue ledger frac_fuel destinations",
            "all residue rows", "1a4b_residue", "parametric",
            "frac_fuel is Tier 2 judgement; the HIES price bracket (%.1f-%.1f Mt "
            "air-dry) contains the ledger's %.1f and a test holds it there"
            % (hies.residue_implied_range_kg()[0] / 1e9,
               hies.residue_implied_range_kg()[1] / 1e9,
               combustion.residue_air_dry_kg(d) / 1e9)),
        row("Charcoal quantity", hies.sole_source_kg("charcoal") / 1e6, "kt/yr",
            d.p("activity_uncert_charcoal"), "lognormal",
            "HIES 2024-25, 47 observations", "charcoal rows", "1a4b_charcoal",
            "parametric"),
        row("Coal quantity", hies.sole_source_kg("coal") / 1e6, "kt/yr",
            d.p("activity_uncert_coal"), "lognormal",
            "HIES 2024-25, 42 observations", "coal rows", "1a4b_coal", "parametric"),
        row("Generator petrol", combustion.generator_petrol_kt(d), "kt/yr",
            d.p("activity_uncert_generators"), "lognormal",
            "HIES generator expenditure / administered petrol price",
            "generator rows + the road carve-out", "1a4b_generators", "parametric",
            "the deduction propagates to road transport by construction"),
        row("IPCC Table 2.5 factors", "per-row", "kg/TJ", "row-specific", "lognormal",
            "IPCC 2006 Vol 2 Ch 2 Table 2.5 (residential column), chapter CIs",
            "all GHG rows", "", "parametric",
            "biomass CH4/N2O at +/-150 dominate the sector band"),
        row("Andreae biofuel air factors", "per-row", "g/kg dry", "row-specific",
            "lognormal", "Andreae 2019 Table 1 (biofuel, dung, charcoal-burning "
            "columns) + agriculture-mirror residue rows", "biomass air rows", "",
            "parametric"),
        row("EMEP small-combustion air factors", "per-row", "g/GJ", "row-specific",
            "lognormal", "EMEP/EEA 2023 ch 1.A.4 Tables 3-3/3-4/3-5",
            "fossil air rows", "", "parametric",
            "two defective printed CIs (coal NH3, solid BC fraction) carried at "
            "+/-100 with bounds quoted - the railways convention"),
        row("Firewood anchor (HIES vs FAOSTAT)", "HIES 2024-25", "choice", "",
            "not sampled", "hies.py module docstring", "all firewood rows", "",
            "structural", "scenarios firewood_faostat, firewood_none"),
        row("Dung mass basis (configuration L)", "air-dry/TS chain", "choice", "",
            "not sampled", "combustion.py three-mass chain", "all dung rows", "",
            "structural", "scenarios dung_basis_legacy_vs, dung_basis_daf"),
        row("Dung activity source", "household survey", "choice", "", "not sampled",
            "what households report burning; the diverted supply is a different "
            "quantity and its remainder is unresolved",
            "all dung rows", "", "structural",
            "scenario dung_all_diverted_household (configuration L)"),
        row("Dung survey series construction", "two rounds interpolated", "choice", "",
            "not sampled", "timeseries.dung_survey_air_dry_kg", "all dung rows", "",
            "structural", "scenarios dung_survey_rate_2018_19, "
            "dung_survey_round_2024_25_as_measured"),
        row("BCEF_R (wood volume to mass)", d.p("woodfuel_bcef_r"),
            "t oven-dry/m3", d.pu("woodfuel_bcef_r"), "lognormal",
            d.ps("woodfuel_bcef_r"), "firewood_faostat scenario only", "",
            "parametric", "demoted with its series: enters nothing reported"),
        row("PM definition (filterable vs condensable)", "compilation-dependent",
            "choice", "", "not sampled", "EMEP review note; Andreae capture basis",
            "air layer", "", "structural", "scenario pm_condensables (scope row)"),
        row("Stove technology mix", "single implicit class per fuel", "choice", "",
            "not sampled", "World Bank 2024 Pakistan Energy Survey (MTF 2021-22) "
            "stove typology, HELD in data/activity/residential/stove_mix_mtf.csv",
            "air layer", "", "structural",
            "scenario stove_mix_mtf prices the improved-class share; the remaining "
            "unlock is the fuel-by-device crosswalk the report does not publish"),
        row("Biogas digesters", "NE", "absence", "", "not sampled",
            "residential-biogas gap row", "-", "", "structural",
            "not a scenario: no count exists to scale; believed small"),
    ]
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = ResidentialData()

    a1 = approach1(data)
    with open(asset_path(OUTPUTS, "residential_uncertainty_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(a1.keys()))
        w.writeheader()
        w.writerow({k: (round(v, 5) if isinstance(v, float) else v)
                    for k, v in a1.items()})

    decomp = variance_decomposition(data)
    write_table(asset_path(OUTPUTS,
                           "residential_variance_decomposition_%d.csv" % data.year), list(decomp[0].keys()), decomp)

    with open(asset_path(OUTPUTS,
                           "residential_uncertainty_inputs_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        rows = inputs_register(data)
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    scen = structural_scenarios(data)
    with open(asset_path(OUTPUTS,
                           "residential_uncertainty_scenarios_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(scen[0].keys()))
        w.writeheader()
        for r in scen:
            w.writerow({k: (round(v, 5) if isinstance(v, float) else v)
                        for k, v in r.items()})

    ratio_s = pm_ratio_distribution(data, dung_basis="survey")     # the reference
    ratio_l = pm_ratio_distribution(data, dung_basis="ledger")
    span = {"configuration": "structural", "deterministic_ratio": "",
            "P2.5": ratio_s["P2.5"], "P50": "", "P97.5": ratio_l["P97.5"],
            "n_iter": "",
            "note": "Structural span across the two configurations: the "
                    "survey configuration's parametric lower bound to the ledger "
                    "configuration's upper - the honest total range, since no "
                    "probability attaches to the configuration choice"}
    with open(asset_path(OUTPUTS, "residential_pm_ratio_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(ratio_l.keys()))
        w.writeheader()
        for row in (ratio_s, ratio_l, span):
            w.writerow({k: (round(v, 3) if isinstance(v, float) else v)
                        for k, v in row.items()})
    ratio = ratio_s

    print("Residential Approach 1: %.1f%% grouped, %.1f%% independent on %.5f Mt"
          % (a1["approach1_pct_grouped"], a1["approach1_pct_independent"],
             a1["co2e_Mt_AR5"]))
    for r in scen:
        if r["scope"].startswith("GHG"):
            print("  %-24s %.5f Mt  [%.3f, %.3f]"
                  % (r["structural_scenario"], r["deterministic"], r["P2.5"],
                     r["P97.5"]))
    print("  PM ratio vs road exhaust: %.1f deterministic, [%.1f, %.1f, %.1f] "
          "P2.5/P50/P97.5" % (ratio["deterministic_ratio"], ratio["P2.5"],
                              ratio["P50"], ratio["P97.5"]))


if __name__ == "__main__":
    main()
