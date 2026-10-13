"""The railway sector's uncertainty: parametric where a percentage is honest, structural
where a choice is discrete, and the settled question retired rather than resampled.

THE SHAPE OF THIS SECTOR'S UNCERTAINTY IS UNUSUAL AND WORTH STATING PLAINLY. Diesel CO2 at
+/-5.4 percent is among the best-constrained streams in the national inventory - a metered
fuel account against a factor whose 95 percent interval spans 3 percent - while diesel N2O
carries +/-150 and is a tenth of the sector. The sector is simultaneously the most
accurately measured and, in its second gas, the least confidently factored; one number
cannot say both, so this module publishes the decomposition.

PARAMETRIC. One metered account drives every stream, so the activity components of the row
uncertainties are correlated: the grouped Approach 1 treats each fuel's activity term as
perfectly shared across its gas rows (linear within fuel, quadrature between terms), the
independent treatment is published alongside, and the conservative grouped figure is the
headline. The grouping is computed HERE, analytically, rather than by stamping corr_group
onto the shipped components: the national pooled Monte Carlo already carries railways in
its cross-sector fossil-correlated scenario, and changing the shipped rows would reorder
the seed-42 gauss stream that every published national percentile depends on -
core/montecarlo.py's own warning.

STRUCTURAL - named cases, conditional intervals, no probabilities. The road-factor case is
doubly motivated: it is the counterfactual the sector always published, and it is what
Pakistan's current CRT actually did (official_reporting reads 3.9 kg/TJ off the filing's
own IEF cells). The boundary case removes the measured non-traction share from 1A3c. The
timing case bounds the Tier 1 consumed-equals-burnt assumption with the prior-year mean.
The SO2 ladder is scope-noted in kt of SO2 - never a CO2e row. And the detail-table case
that once belonged here is RETIRED: the 2024-25 edition restated the disputed cell and the
question no longer exists; the inputs register records the retirement so its absence reads
as resolution, not omission.

SCENARIO_SEED keeps this module's draws off the national stream entirely.

Usage:  python3 -m pkinv.sectors.railways.uncertainty
Writes: outputs/railways_uncertainty_2024.csv,
        outputs/railways_uncertainty_inputs_2024.csv,
        outputs/railways_uncertainty_scenarios_2024.csv
"""

from pkinv.assets import asset_path
import csv
import math
import os

from pkinv.core import montecarlo as mc_core
from pkinv.core.uncertainty import combine_sum
from pkinv.paths import OUTPUTS
from pkinv.sectors.railways import air_pollutants, engine, reconcile, traction
from pkinv.sectors.railways.data import RailwaysData

SCENARIO_SEED = 1435          # private stream; the national MC's seed 42 is untouched
INTERPRETATION = "conditional parametric interval; no structural probability"

def _fuel_key(subitem):
    # both booking categories share the two physical fuel accounts: "Diesel CO2" and
    # "Non-traction diesel CO2" are the same metered diesel purchase
    return "diesel" if "diesel" in subitem.lower() else "rfo"


def _rows(data, comps=None):
    comps = comps or engine.build_components(data)
    return [(c, _fuel_key(c["subitem"])) for c in comps]


def approach1(data):
    """Grouped and independent Approach-1 percentages for the sector total.

    Grouped: each fuel's activity term is one perfectly-correlated component across its
    gas rows (the same metered account), factor terms stay independent. Independent: the
    published per-row uncertainties combined as if unrelated - what the national rollup's
    generic treatment sees.
    """
    rows = _rows(data)
    total = sum(c["co2e_Mt_AR5"] for c, _f in rows)
    var = 0.0
    for fuel_key in ("diesel", "rfo"):
        act_u = data.p("activity_uncert_" + fuel_key)
        fuel_rows = [c for c, f in rows if f == fuel_key]
        fuel_total = sum(c["co2e_Mt_AR5"] for c in fuel_rows)
        var += (act_u * fuel_total) ** 2                     # shared, linear within fuel
        for c in fuel_rows:                                   # factor residuals, quadrature
            factor_u = math.sqrt(max(c["uncert_pct"] ** 2 - act_u ** 2, 0.0))
            var += (factor_u * c["co2e_Mt_AR5"]) ** 2
    grouped = math.sqrt(var) / total
    _t, indep = combine_sum([(c["co2e_Mt_AR5"], c["uncert_pct"], None)
                             for c, _f in rows])
    return {"category": traction.CATEGORY, "co2e_Mt_AR5": total,
            "approach1_pct_grouped": grouped, "approach1_pct_independent": indep}


def _scaled(comps, scale, fuel="diesel"):
    # scales the physical fuel ACCOUNT across both booking categories: a timing or
    # quantity scenario on diesel moves the traction and non-traction rows together,
    # because they are one metered purchase
    out = []
    for c in comps:
        c2 = dict(c)
        if _fuel_key(c["subitem"]) == fuel:
            for k in ("co2e_Mt_AR5", "co2e_Mt_AR6", "emissions_Gg"):
                c2[k] = c2[k] * scale
        out.append(c2)
    return out


def _road_n2o(data):
    """N2O on Table 3.2.2's 3.9 kg/TJ instead of rail's 28.6 - the CRT's own treatment."""
    comps = []
    ratio = 3.9 / data.efv("railway_traction_n2o", "Gas/Diesel Oil")
    for c in engine.build_components(data):
        c2 = dict(c)
        if c["gas"] == "N2O":
            for k in ("co2e_Mt_AR5", "co2e_Mt_AR6", "emissions_Gg"):
                c2[k] = c2[k] * ratio
        comps.append(c2)
    return comps


def structural_scenarios(data, n_iter=10000, seed=SCENARIO_SEED):
    share = reconcile.non_traction_share(data)
    fo = reconcile.detail_for(data.year, "Residual Fuel Oil")
    fo_loco_frac = (fo["locomotive"] or 0.0) / ((fo["locomotive"] or 0.0)
                                                + fo["other_than_locomotive"])
    prior_mean = (data.quantity("Gas/Diesel Oil", data.year - 1)
                  + data.quantity("Gas/Diesel Oil")) / 2.0
    timing_scale = prior_mean / data.quantity("Gas/Diesel Oil")
    cases = [
        ("reference", lambda: engine.build_components(data), "the estimate"),
        ("road_n2o_factor", lambda: _road_n2o(data),
         "N2O at Table 3.2.2's 3.9 kg/TJ - the substitution the paper documents, and the "
         "treatment visible in the current CRT's own IEF cells"),
        ("stock_timing_prior_year_mean",
         lambda: _scaled(engine.build_components(data), timing_scale),
         "Tier 1 assumes fuel consumed in the year equals fuel burnt in it; this bounds "
         "the assumption with the mean of the reference and prior fiscal years - a lumpy "
         "account's plausible smoothing, not a better estimate"),
    ]
    out = []
    for i, (name, build, note) in enumerate(cases):
        comps = build()
        det = sum(c["co2e_Mt_AR5"] for c in comps)
        stats, _s = mc_core.run(comps, list(engine.CATEGORIES),
                                n_iter=n_iter, seed=seed + i)
        s = stats["TOTAL"]
        out.append({"structural_scenario": name, "scope": "GHG Mt CO2e AR5",
                    "deterministic": det, "mean": s["mean"], "P2.5": s["p025"],
                    "P50": s["p50"], "P97.5": s["p975"],
                    "receiving_category": "", "moved_Mt": "",
                    "national_delta_Mt": "", "note": note,
                    "interpretation": INTERPRETATION})
    # Tier 2 invariance: the row exists to state that the service split CANNOT move the
    # total, because it is a decomposition rescaled to the control by construction.
    ref = out[0]["deterministic"]
    out.append({"structural_scenario": "tier2_service_split", "scope": "GHG Mt CO2e AR5",
                "deterministic": ref, "mean": "", "P2.5": "", "P50": "", "P97.5": "",
                "receiving_category": "", "moved_Mt": "", "national_delta_Mt": "",
                "note": "INVARIANT BY CONSTRUCTION: tier2.split rescales exactly to the "
                        "fuel control, so the split moves pollutant composition and "
                        "geography, never the total",
                "interpretation": INTERPRETATION})
    # The booking axis, FLIPPED IN rc11: the recode IS the reference now - the engine
    # itself books 1.A.3.c at locomotive traction and the measured non-traction share
    # at its own category - so the scenario row states the PRE-rc11 summary booking
    # (everything inside 1.A.3.c, non-traction declared IE). Deterministic equals the
    # reference by construction either way: the same fuel, the same factors, only the
    # reporting code differs, and the moved quantity is the claimant ledger's
    # RESOLVED-RECODED total.
    moved = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data)
                if c["category"] == engine.traction.NON_TRACTION_CATEGORY)
    out.append({"structural_scenario": "ie_summary",
                "scope": "GHG reporting allocation",
                "deterministic": ref, "mean": "", "P2.5": "", "P50": "", "P97.5": "",
                "receiving_category": "1.A.3.c (all fuel, non-traction declared IE)",
                "moved_Mt": round(moved, 5), "national_delta_Mt": 0.0,
                "note": "THE PRE-rc11 BOOKING, restated as the alternative: all "
                        "railway fuel inside 1.A.3.c with the measured non-traction "
                        "shares (diesel %.2f%%, furnace oil %.0f%% - most of that "
                        "stream runs power houses, not trains) declared IE. The rc11 "
                        "reference books those %.5f Mt at the non-traction category "
                        "and 1.A.3.c at %.5f Mt locomotive traction; either booking "
                        "conserves the sector and national totals exactly, so "
                        "national_delta_Mt is zero by construction"
                        % (100 * share, 100 * (1 - fo_loco_frac), moved, ref - moved),
                "interpretation": INTERPRETATION})
    # The provincial-split alternative: national total identical by construction, so the
    # scenario is stated on the share that moves most - Sindh's - under each basis.
    from pkinv.sectors.railways import downscale
    shares = downscale.load_shares()
    out.append({"structural_scenario": "provincial_wagons_proxy",
                "scope": "provincial: Sindh share",
                "deterministic": shares[downscale.WAGONS_PROXY]["Sindh"],
                "mean": "", "P2.5": "", "P50": "", "P97.5": "",
                "note": "the retained freight-wagons-loaded alternative puts Sindh at "
                        "%.1f%% where the route model puts it at %.1f%%; the national "
                        "total is unchanged under either"
                        % (100 * shares[downscale.WAGONS_PROXY]["Sindh"],
                           100 * shares[downscale.PROXY]["Sindh"]),
                "interpretation": INTERPRETATION})
    # The SO2 ladder: scope-noted kt of SO2, stoichiometric, unsampled.
    for case, ppm, kt in air_pollutants.sulfur_cases(data):
        out.append({"structural_scenario": "sulfur_%s" % case, "scope": "air: SO2 kt",
                    "deterministic": kt, "mean": "", "P2.5": "", "P50": "", "P97.5": "",
                    "note": "diesel at %g ppm sulfur; stoichiometric, so the case IS the "
                            "answer - kt of SO2, never CO2e" % ppm,
                    "interpretation": INTERPRETATION})
    return out


def inputs_register(data):
    def row(variable, central, unit, u, dist, source, applies_to, group, klass, note=""):
        return {"variable": variable, "central_value": central, "unit": unit,
                "uncert_pct_95": u, "distribution": dist, "source": source,
                "applies_to": applies_to, "correlation_group": group,
                "uncertainty_class": klass, "note": note}

    d = data
    rows = [
        row("Diesel consumption FY2023-24", d.quantity("Gas/Diesel Oil"),
            "thousand litres", d.p("activity_uncert_diesel"), "lognormal",
            "Year Book 2023-24 Principal Statistics + narrative (stated twice); detail "
            "table reconciles since the 2024-25 restatement", "all diesel streams",
            "1a3c_fuel_account", "parametric",
            "the sector's control total; one metered account drives every stream"),
        row("Furnace-oil consumption FY2023-24", d.quantity("Residual Fuel Oil"),
            "tonnes", d.p("activity_uncert_rfo"), "lognormal",
            "Year Book 2023-24 narrative (79.907 M.T); basis settled as tonnes",
            "all furnace-oil streams", "1a3c_fuel_account", "parametric"),
        row("HSD density", d.p("hsd_density_kg_per_l"), "kg/litre",
            d.pu("hsd_density_kg_per_l"), "lognormal", d.ps("hsd_density_kg_per_l"),
            "all diesel streams + the road-transport deduction", "1a3c_hsd_density",
            "parametric", "the PSO MSDS 0.83-0.86 spread is the whole term"),
        row("Diesel NCV", d.efv("railway_ncv", "Gas/Diesel Oil"), "TJ/Gg",
            d.efu("railway_ncv", "Gas/Diesel Oil"), "lognormal",
            d.efs("railway_ncv", "Gas/Diesel Oil"), "all diesel streams", "1a3c_ncv",
            "parametric"),
        row("Diesel CO2 factor", d.efv("railway_traction_co2", "Gas/Diesel Oil"),
            "kg/TJ", d.efu("railway_traction_co2", "Gas/Diesel Oil"), "lognormal",
            d.efs("railway_traction_co2", "Gas/Diesel Oil"), "Diesel CO2", "",
            "parametric"),
        row("Diesel CH4 factor (rail)", d.efv("railway_traction_ch4", "Gas/Diesel Oil"),
            "kg/TJ", d.efu("railway_traction_ch4", "Gas/Diesel Oil"), "lognormal",
            d.efs("railway_traction_ch4", "Gas/Diesel Oil"), "CH4 streams", "",
            "parametric"),
        row("Diesel N2O factor (rail)", d.efv("railway_traction_n2o", "Gas/Diesel Oil"),
            "kg/TJ", d.efu("railway_traction_n2o", "Gas/Diesel Oil"), "lognormal",
            d.efs("railway_traction_n2o", "Gas/Diesel Oil"), "N2O streams", "",
            "parametric", "14.3-85.8 kg/TJ: effectively the whole sector interval; only "
            "measurement on Pakistani locomotives would narrow it, and the sector is too "
            "small for that to be the priority"),
        row("EMEP Tier 1 air factors", "Table 3-1", "kg/t fuel", "row-specific",
            "lognormal", "EMEP/EEA 2023 ch 1.A.3.c Table 3-1",
            "air layer", "1a3c_fuel_account", "parametric",
            "chapter CIs on each factor row; the PM rows' printed CIs do not bracket "
            "their centrals - defect recorded on the rows, +/-100 adopted"),
        row("BC fraction of PM2.5", d.efv("railway_air_frac", "BC_of_PM2.5"), "fraction",
            d.efu("railway_air_frac", "BC_of_PM2.5"), "lognormal",
            "EMEP/EEA 2023 ch 1.A.3.c Table 3-1 note", "BC", "", "parametric"),
        row("Diesel sulfur content", d.p("diesel_sulfur_ppm_reference"), "ppm", "",
            "not sampled", d.ps("diesel_sulfur_ppm_reference"), "SO2", "", "structural",
            "a 10-10,000 ppm supply-mix span is a choice of case, not a distribution; "
            "scenarios sulfur_*"),
        row("IPCC factor table (rail 3.4.1 vs road 3.2.2)", "3.4.1", "choice", "",
            "not sampled", "IPCC 2006 Vol 2 Ch 3", "CH4/N2O streams", "", "structural",
            "scenario road_n2o_factor; the current CRT's IEF cells show the road value"),
        row("1A3c boundary (non-traction fuel)", reconcile.non_traction_share(data),
            "fraction", "", "not sampled", "Year Book detail table via reconcile.py",
            "all streams", "", "structural", "scenario locomotive_only_1a3c"),
        row("Consumed-equals-burnt timing", 1.0, "ratio", "", "not sampled",
            "Tier 1 assumption, stated in Study Area", "all streams", "", "structural",
            "scenario stock_timing_prior_year_mean"),
        row("Summary-vs-detail diesel total", "RETIRED", "choice", "", "not sampled",
            "Year Book 2024-25 restatement of the 2023-24 misprint", "-", "",
            "structural",
            "the one-time 4.52 percent structural case no longer exists: the source "
            "settled it at one part in 132,588; recorded here so absence reads as "
            "resolution, not omission"),
        row("Shunting fuel share", d.p("shunting_fuel_share"), "fraction",
            d.pu("shunting_fuel_share"), "lognormal", d.ps("shunting_fuel_share"),
            "Tier 2 diagnostic + yard allocation only", "", "parametric",
            "declared assumption; cannot move the sector total by construction"),
    ]
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = RailwaysData()

    a1 = approach1(data)
    with open(asset_path(OUTPUTS, "railways_uncertainty_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(a1.keys()))
        w.writeheader()
        w.writerow({k: (round(v, 5) if isinstance(v, float) else v)
                    for k, v in a1.items()})

    with open(asset_path(OUTPUTS, "railways_uncertainty_inputs_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        rows = inputs_register(data)
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    scen = structural_scenarios(data)
    with open(asset_path(OUTPUTS, "railways_uncertainty_scenarios_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(scen[0].keys()))
        w.writeheader()
        for r in scen:
            w.writerow({k: (round(v, 5) if isinstance(v, float) else v)
                        for k, v in r.items()})

    print("Railways Approach 1: %.1f%% grouped, %.1f%% independent on %.5f Mt"
          % (a1["approach1_pct_grouped"], a1["approach1_pct_independent"],
             a1["co2e_Mt_AR5"]))
    for r in scen:
        if r["scope"].startswith("GHG"):
            print("  %-28s %.5f Mt  [%s, %s]"
                  % (r["structural_scenario"], r["deterministic"],
                     ("%.3f" % r["P2.5"]) if r["P2.5"] != "" else "-",
                     ("%.3f" % r["P97.5"]) if r["P97.5"] != "" else "-"))
        else:
            print("  %-28s %.4f %s" % (r["structural_scenario"], r["deterministic"],
                                       r["scope"]))


if __name__ == "__main__":
    main()
