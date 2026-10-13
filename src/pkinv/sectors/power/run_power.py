"""Run the power inventory (IPCC 1A1a) and write its outputs.

Usage:  python3 -m pkinv.sectors.power.run_power
"""
import os

from pkinv.core.downscale import allocate_rows, check_reconciliation
from pkinv.core.geography import PROVINCES
from pkinv.core.runner import Runner
from pkinv.paths import OUTPUTS
from pkinv.core import period
from pkinv.sectors.power import (bagasse, benchmarks_plants, captive, combustion,
                                 decomposition, downscale, engine, heat_rate, implied_cv,
                                 ke_leg, official_reporting, plant_ledger, point_sources,
                                 tropomi_crosscheck, uncertainty)
from pkinv.sectors.power.data import PowerData

def _sfx(year):
    """The output filename's period suffix - "fy2023_24", not a bare year.
    rc15 (the tenth review): this sector keys its code on the fiscal-START year,
    so a bare _2023 filename described the same twelve months as the _2024 files
    beside it. The name now carries the period the row does."""
    return period.file_suffix(year, engine.YEAR_CONVENTION)


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = PowerData()
    year = data.year
    run = Runner("power", declared=(
        "power_by_stream_%s.csv" % _sfx(year),
        "power_totals_%s.csv" % _sfx(year),
        "power_fuel_%s.csv" % _sfx(year),
        "power_provincial_%s.csv" % _sfx(year),
        "power_timeseries_%s.csv" % _sfx(year),
        "power_heat_rate_%s.csv" % _sfx(year),
        "power_heat_rate_stability_%s.csv" % _sfx(year),
        "power_energy_closure_%s.csv" % _sfx(year),
        "power_gas_technology_%s.csv" % _sfx(year),
        "power_point_sources_%s.csv" % _sfx(year),
        "power_uncertainty_%s.csv" % _sfx(year),
        "power_uncertainty_inputs_%s.csv" % _sfx(year),
        "power_uncertainty_scenarios_%s.csv" % _sfx(year),
        "power_lmdi_%s.csv" % _sfx(year),
        "power_climatetrace_plants_%s.csv" % _sfx(year),
        "power_tropomi_crosscheck.csv",
        "power_ke_leg_%s.csv" % _sfx(year),
        "power_bagasse_%s.csv" % _sfx(year),
        "power_implied_coal_cv_%s.csv" % _sfx(year),
        "power_hr_circularity_%s.csv" % _sfx(year),
        "power_crt_comparison.csv",
        "power_boundary_audit_%s.csv" % _sfx(year),
        "power_coal_blend_%s.csv" % _sfx(year)))
    comps = engine.build_components(data)
    total = sum(c["co2e_Mt_AR5"] for c in comps)
    tj = combustion.fuel_TJ(data)

    run.write("power_by_stream_%s.csv" % _sfx(year),
           ["category", "subitem", "gas", "fossil", "emissions_Gg", "co2e_Mt_AR5",
            "co2e_Mt_AR6", "uncert_pct"],
           [[c["category"], c["subitem"], c["gas"], c.get("fossil", False),
             round(c["emissions_Gg"], 4), round(c["co2e_Mt_AR5"], 5),
             round(c["co2e_Mt_AR6"], 5), round(c["uncert_pct"], 1)] for c in comps])

    # Per CATEGORY, not per sector: the module now carries two IPCC codes, and a total row
    # labelled with the grid category while holding the captive figure too would be read as
    # 1A1a by anyone downstream.
    def cat_total(components, name):
        return sum(c["co2e_Mt_AR5"] for c in components if c["category"] == name)

    grid = cat_total(comps, combustion.CATEGORY)
    cap = cat_total(comps, captive.CATEGORY)
    bit = cat_total(engine.build_components(data, coal_override="bituminous"), combustion.CATEGORY)
    lig = cat_total(engine.build_components(data, coal_override="lignite"), combustion.CATEGORY)
    cap_lo = cat_total(engine.build_components(data, hhv_btu=900.0), captive.CATEGORY)
    # The coal-conversion sensitivity: same emission factors, the activity restated as
    # ledger mass x per-plant implied NCV (Tables 20/23/28). The largest labelled case in
    # the table, and deliberately a sensitivity rather than the estimate - the CRT's 2%
    # agreement with Table 3's solid-fuel energy is unresolved counter-evidence.
    coal_co2e = sum(c["co2e_Mt_AR5"] for c in comps
                    if c["category"] == combustion.CATEGORY
                    and c["subitem"].startswith("Coal"))
    cv_scale = implied_cv.restated_coal_TJ(data, year) / tj["Coal"]
    grid_cv = grid + coal_co2e * (cv_scale - 1.0)
    # The account the re-base replaced, priced the same way: Table 3's printed coal energy
    # over the booked coal energy, applied to the coal component only.
    t3_TJ = data.table3_coal_toe(year) * data.p("toe_to_tj")
    grid_t3 = grid + coal_co2e * (t3_TJ / tj["Coal"] - 1.0)
    run.write("power_totals_%s.csv" % _sfx(year), ["category", "co2e_Mt_AR5", "note"],
           [[combustion.CATEGORY, round(grid, 5),
             "1A1a, from the generating stations' own metered coal at IPCC Vol.2 Ch.1 "
             "Table 1.2 rank default calorific values (data/activity/power/"
             "coal_energy_booking.csv); gas, furnace oil and diesel from NEPRA SIR Table 3"],
            [captive.CATEGORY, round(cap, 5),
             "1A2, from OGRA metered captive gas FY%d (%.0f MMCFD). A FLOOR ON 1A2, not an "
             "estimate of it: captive gas only, and the rest of industrial combustion is not "
             "estimated." % (data.captive_year(), data.captive_total_mmcfd())],
            ["TOTAL", round(total, 5), "both categories, one reference year: FY2023-24 "
             "under two labelling conventions (grid year-starting, captive year-ending)"],
            ["Sensitivity: all coal bituminous", round(bit, 5),
             "lower bound on the coal blend (1A1a only)"],
            ["Sensitivity: all coal lignite", round(lig, 5),
             "upper bound on the coal blend (1A1a only)"],
            ["Sensitivity: Table 3 published coal energy (legacy control)",
             round(grid_t3, 5),
             "1A1a as every release before the coal re-base booked it: NEPRA SIR Table 3's "
             "published coal energy (%.0f TJ against the booked %.0f, factor %.2f). "
             "RETAINED AND NOT PREFERRED - divided into NEPRA's own printed generation it "
             "implies net fleet efficiencies inside 28-47 per cent in two of nine panel "
             "years where the booked account manages nine. Kept so a reader holding a total "
             "published before the re-base can find the account it came from."
             % (t3_TJ, tj["Coal"], t3_TJ / tj["Coal"])],
            ["Sensitivity: coal at ledger mass x implied CV", round(grid_cv, 5),
             "1A1a with coal energy restated as plant mass x per-plant implied NCV from "
             "SIR Tables 20/23/28 (%.0f against Table 3's %.0f TJ, factor %.2f). The "
             "three-channel evidence says Table 3 converts lignite at a bituminous-like "
             "CV. This route is CIRCULAR - its calorific values are derived as generation "
             "x a printed heat rate / mass - which is why the re-base went to the "
             "rank-default account and not to this one, and why it stays a labelled case."
             % (implied_cv.restated_coal_TJ(data, year), tj["Coal"], cv_scale)],
            ["Sensitivity: captive gas at 900 Btu/scf", round(cap_lo, 5),
             "the dominant assumption in 1A2: pipeline gas heating value is not pinned by any "
             "Pakistani source, and 900 against the reported 1,000 moves the category by "
             "%.2f Mt" % (cap - cap_lo)],
            ["Sensitivity: grid + K-Electric ledger fuel", round(grid + ke_leg.fy2023_case(data), 5),
             "1A1a if Table 3 excludes the K-Electric system, as the boundary audit's "
             "evidence leans: the K-E ledger rows add %.2f Mt CO2 in FY2023-24 (CO2 only; "
             "CH4 and N2O would add under half a percent). Weaker evidence classes - MMCFT "
             "at an assumed heating value, oil at default NCVs, only the two Nooriabad "
             "units metered exactly - and the open boundary question, not the arithmetic, "
             "are what keep this a labelled case. The K-E term is a trend, not a flat "
             "adder: 7.1 down to 4.0 Mt across FY2019-23 as furnace oil retired."
             % ke_leg.fy2023_case(data)]]
           + [[m["item"], "", "%.1f Gg CO2 - %s" % (m["emissions_Gg"], m["note"])]
              for m in engine.memo_items(data)])

    run.write("power_fuel_%s.csv" % _sfx(year), ["fuel", "TJ", "share_pct"],
           [[f, round(v, 0), round(v / sum(tj.values()) * 100, 2)] for f, v in sorted(tj.items())])

    rows = allocate_rows(comps, downscale.load_shares(), downscale.proxy_for, PROVINCES)
    check_reconciliation(rows, comps)
    prov = {p: 0.0 for p in PROVINCES}
    for r in rows:
        prov[r["province"]] += r["co2e_Mt_AR5"]
    run.write("power_provincial_%s.csv" % _sfx(year), ["province", "co2e_Mt_AR5"],
           [[p, round(prov[p], 5)] for p in PROVINCES])

    # GRID ONLY. Captive has its own panel starting FY2016, so a grid series reaching back
    # to FY2013-14 must not build it - and until the series round it could not anyway,
    # because captive ignored the year. This builds the grid stream directly rather than
    # building the whole engine and discarding the captive rows, the same repair the LMDI
    # decomposition needed for the same reason.
    from pkinv.core.components import enrich_co2e
    from pkinv.sectors.power import bagasse
    series = []
    for y in sorted({r["fiscal_year"] for r in data.fuel}):
        c, _memo = combustion.compute(data, y, None)
        b, _bmemo = bagasse.compute(data, y)
        c = enrich_co2e(c + b)      # bagasse reports under the same grid category
        series.append([y, round(cat_total(c, combustion.CATEGORY), 4)])
    run.write("power_timeseries_%s.csv" % _sfx(year), ["fiscal_year", "mt_co2e_AR5"], series)

    print("Power (1A1a) FY%d-%02d: %.2f Mt CO2e (AR5)" % (year, (year + 1) % 100, total))
    for c in comps:
        if c["gas"] == "CO2":
            print("  %-18s %9.1f Gg CO2  %6.2f Mt" % (c["subitem"], c["emissions_Gg"],
                                                      c["co2e_Mt_AR5"]))
    # The implied-heat-rate check. Diagnostic only: it validates the ACTIVITY tables against
    # each other and never feeds the estimate, in the same way the railway sector publishes
    # what it would report on the wrong factor table.
    hr_rows = []
    for y in heat_rate.overlap_years(data):
        for r in heat_rate.implied(data, y):
            hr_rows.append([y, r["fuel"], r["generation_fuels"], round(r["toe"], 0),
                            r["gwh_net"], r["heat_rate_kJ_per_kWh"], r["efficiency"],
                            r["verdict"], r["note"]])
    run.write("power_heat_rate_%s.csv" % _sfx(year),
           ["fiscal_year", "fuel", "generation_fuels", "toe", "gwh_net",
            "heat_rate_kJ_per_kWh", "efficiency", "verdict", "note"], hr_rows)

    stab = heat_rate.stability(data)
    run.write("power_heat_rate_stability_%s.csv" % _sfx(year),
           ["fuel", "material_years", "efficiency_lo", "efficiency_hi", "spread", "verdict",
            "note"],
           [[f, s["years"], s["lo"], s["hi"], s["spread"], s["verdict"], s["note"]]
            for f, s in sorted(stab.items())])

    print("  coal sensitivity: %.2f (all bituminous) to %.2f Mt (all lignite)" % (bit, lig))
    print("  provincial reconciliation exact; %s"
          % ", ".join("%s %.1f" % (p, prov[p]) for p in PROVINCES))
    # The plant-side energy closure. Diagnostic only: it tests the ACTIVITY basis and never
    # feeds the estimate, like the heat-rate check below.
    L = plant_ledger.legs(data)
    eff = plant_ledger.implied_efficiency(data)
    gc = plant_ledger.gas_closure(data)
    run.write("power_energy_closure_%s.csv" % _sfx(year),
           ["item", "value", "unit", "evidence", "note"],
           [["MMBTU-metered plant energy", round(L["exact_TJ"], 0), "TJ", "exact",
             "MMBTU to TJ is a definition; no calorific assumption enters"],
            ["MMCFT-metered plant energy", round(L["assumed_TJ"], 0), "TJ", "assumed",
             "a volume needs a heating value; 900-1,000 Btu/scf is unpinned here"],
            ["Mass-metered plant energy", round(L["default_TJ"], 0), "TJ", "IPCC default",
             "coal and RFO at Vol 2 Ch 1 Table 1.2 net calorific values, not Pakistani fuel"],
            ["Implied net efficiency, MMBTU plants", round(100 * eff, 1), "percent", "exact",
             "THE ASSUMPTION-FREE TEST OF THE TOE CONVENTION. A modern combined cycle runs "
             "about 50 percent net; read as gross the same fuel would imply %.1f percent, at "
             "the ceiling of any fleet average. Consistent with net." % (100 * eff / 0.9)],
            ["Plant gas energy over national TOE gas", round(gc["ratio"], 3), "ratio",
             "mixed", "plant sum exceeds the national row; the residual is reported, not "
                      "absorbed"],
            ["Heating value that would reconcile them",
             round(gc["implied_hhv_btu_per_scf"], 0), "Btu/scf", "derived",
             "below the plausible 900-1,000 range, so the two sources do not fully "
             "reconcile - a statement about NEPRA's tables, not an adjustment to make"]])

    # The gas fleet by combustor type, classified from ledger heat rates. This one is NOT
    # purely diagnostic: the air layer's grid gas NOx factor blends the boiler and turbine
    # chapters by the turbine share. The greenhouse-gas path still never reads it.
    ts = plant_ledger.gas_technology_split(data)
    run.write("power_gas_technology_%s.csv" % _sfx(year),
           ["bucket", "energy_TJ", "share", "plants", "note"],
           [["turbine", round(ts["turbine_TJ"], 0), round(ts["turbine_TJ"] / ts["total_TJ"], 4),
             "; ".join(ts["turbine_plants"]),
             "combined cycle by heat rate (at or below 9,000 kJ/kWh net, reachable by no "
             "boiler or simple-cycle turbine) or turbine hardware named in the plant name"],
            ["boiler", round(ts["boiler_TJ"], 0), round(ts["boiler_TJ"] / ts["total_TJ"], 4),
             "; ".join(ts["boiler_plants"]),
             "heat rate at or above 10,500 kJ/kWh, ordinary for steam and above any "
             "combined-cycle design point"],
            ["unresolved", round(ts["unresolved_TJ"], 0), round(ts["unresolved_share"], 4),
             "; ".join(ts["unresolved_plants"]),
             "the 9,000-10,500 band, where the ledger cannot separate a degraded combined "
             "cycle from a steam plant; kept on the boiler NOx factor and reported here "
             "rather than assigned"]])
    print("  gas fleet by combustor: %.1f%% turbine, %.1f%% boiler, %.1f%% unresolved "
          "(kept on the boiler factor)"
          % (100 * ts["turbine_share"], 100 * ts["boiler_TJ"] / ts["total_TJ"],
             100 * ts["unresolved_share"]))

    # The point-source register behind the provincial split: every ledger plant-fuel row
    # with its energy, its evidence class, and where it sits. Also the join surface any
    # future satellite comparison (TROPOMI) would use.
    ps = point_sources.rows(data)
    run.write("power_point_sources_%s.csv" % _sfx(year),
           ["fiscal_year", "system", "plant", "fuel", "energy_TJ", "energy_evidence",
            "town", "province", "located_by"],
           [[r["fiscal_year"], r["system"], r["plant"], r["fuel"], r["energy_TJ"],
             r["energy_evidence"], r["town"], r["province"], r["located_by"]]
            for r in ps])
    unmatched = [r for r in ps if r["located_by"] == "UNMATCHED"]
    print("  point sources: %d plant-fuel rows located (%d unmatched)"
          % (len(ps) - len(unmatched), len(unmatched)))

    # The uncertainty statement, rebuilt around evidence classes: per-fuel parametric
    # widths (grouped through the shared TOE conversion), and the one-sided questions as
    # named structural cases with conditional intervals - never folded into a percentage.
    a1 = uncertainty.approach1_rows(data)
    run.write("power_uncertainty_%s.csv" % _sfx(year),
           ["category", "co2e_Mt_AR5", "approach1_pct_grouped",
            "approach1_pct_independent"],
           [[r["category"], round(r["co2e_Mt_AR5"], 5),
             round(r["approach1_pct_grouped"], 2),
             round(r["approach1_pct_independent"], 2)] for r in a1])
    run.write("power_uncertainty_inputs_%s.csv" % _sfx(year),
           ["variable", "central_value", "unit", "uncert_pct_95", "distribution",
            "source", "applies_to", "correlation_group", "uncertainty_class", "note"],
           [[r["variable"], r["central_value"], r["unit"], r["uncert_pct_95"],
             r["distribution"], r["source"], r["applies_to"], r["correlation_group"],
             r["uncertainty_class"], r["note"]]
            for r in uncertainty.full_factor_table(data)])
    run.write("power_uncertainty_scenarios_%s.csv" % _sfx(year),
           ["structural_scenario", "scope", "deterministic_Mt", "mean_Mt", "P2.5_Mt",
            "P50_Mt", "P97.5_Mt", "family_id", "status", "note", "interpretation"],
           [[r["structural_scenario"], r["scope"], round(r["deterministic_Mt"], 5),
             round(r["mean_Mt"], 3), round(r["P2.5_Mt"], 3), round(r["P50_Mt"], 3),
             round(r["P97.5_Mt"], 3), r["family_id"], r["status"],
             r["note"], r["interpretation"]]
            for r in uncertainty.structural_scenarios(data)])
    g = next(r for r in a1 if r["category"] == combustion.CATEGORY)
    print("  uncertainty rebuilt: grid +/-%.1f%% grouped (%.1f%% independent); the "
          "one-sided questions are %d named structural cases, unsampled"
          % (g["approach1_pct_grouped"], g["approach1_pct_independent"],
             sum(1 for r in uncertainty.structural_scenarios(data, n_iter=10)
                 if r["structural_scenario"] != "reference")))

    # The series, decomposed: LMDI-I attributes each year's movement to activity, mix
    # and factor exactly (the terms must close to machine precision).
    lm_rows = []
    for r in decomposition.series_rows(data):
        pf = r["per_fuel"]
        lm_rows.append([r["y0"], r["y1"], round(r["E0_Mt"], 3), round(r["E1_Mt"], 3),
                        round(r["delta_Mt"], 3), round(r["activity_Mt"], 3),
                        round(r["mix_Mt"], 3), round(r["factor_Mt"], 3),
                        round(pf.get("Coal", {}).get("mix", 0.0), 3),
                        round(pf.get("Furnace Oil", {}).get("mix", 0.0), 3),
                        round(pf.get("Gas", {}).get("mix", 0.0), 3),
                        "factor term is zero by construction: the engine applies the "
                        "FY2023-24 blend to every year, a stated limitation of the series"
                        if r["y1"] - r["y0"] > 1 else ""])
    run.write("power_lmdi_%s.csv" % _sfx(year),
           ["y0", "y1", "E0_Mt", "E1_Mt", "delta_Mt", "activity_Mt", "mix_Mt",
            "factor_Mt", "coal_mix_Mt", "fo_mix_Mt", "gas_mix_Mt", "note"], lm_rows)
    yrs = sorted({r["fiscal_year"] for r in data.fuel})
    end = decomposition.decompose(data, yrs[0], yrs[-1])
    print("  LMDI FY%d->FY%d: +%.1f Mt = %.1f activity + %.1f mix (coal mix +%.1f, "
          "oil %.1f, gas %.1f)"
          % (yrs[0], yrs[-1], end["delta_Mt"], end["activity_Mt"], end["mix_Mt"],
             end["per_fuel"]["Coal"]["mix"], end["per_fuel"]["Furnace Oil"]["mix"],
             end["per_fuel"]["Gas"]["mix"]))

    # Climate TRACE, per plant: the 56 Mt coal anomaly resolved into its structure.
    tr = benchmarks_plants.comparison(data)
    run.write("power_climatetrace_plants_%s.csv" % _sfx(year),
           ["trace_name", "asset_type", "activity_MWh", "trace_co2e_t",
            "trace_g_per_kwh", "ledger_plant", "engine_co2_Mt_fy2023",
            "trace_over_engine", "flags"],
           [[r["trace_name"], r["asset_type"], r["activity_MWh"], r["trace_co2e_t"],
             round(r["trace_g_per_kwh"], 0) if r["trace_g_per_kwh"] != "" else "",
             r["ledger_plant"], r["engine_co2_Mt_fy2023"], r["trace_over_engine"],
             r["flags"]] for r in tr],
           banner=[
               "CLIMATE TRACE PLANT COMPARISON. The comparator applies ONE intensity per",
               "fuel class, not per plant: trace_g_per_kwh has a single distinct value",
               "across every coal asset (2431 g CO2e/kWh), and the pure oil and biomass",
               "classes are single-valued too - only the mixed gas/other-fossil class",
               "varies, and there with the mix rather than with the plant. So",
               "trace_over_engine tests this inventory's GENERATION and fuel typing, and",
               "cannot test a plant's emission intensity: a plant-level ratio read as a",
               "magnitude benchmark would be reading a constant. The validation catalog",
               "registers this comparison for GEOGRAPHY only, and that is the grain it",
               "can carry.",
           ])
    coal_assets = [r for r in tr if r["asset_type"] == "coal" and r["trace_g_per_kwh"]]
    print("  Climate TRACE per plant: every coal-labelled asset carries %.0f g/kWh - one "
          "modelled intensity, not plant data; %d imputation twins flagged; gas plants "
          "agree at 0.97-1.03"
          % (coal_assets[0]["trace_g_per_kwh"],
             sum(1 for r in tr if "imputation" in r["flags"])))

    # Sentinel-5P against the fleet: the one comparator outside every reporting chain.
    # Reads only the committed extraction; the SSD is never needed here or in CI.
    tv = tropomi_crosscheck.verdicts()
    tt = tropomi_crosscheck.table("no2")
    ts2 = {(r["source"], r["fiscal_year"]): r for r in tropomi_crosscheck.table("so2")}
    sp = tropomi_crosscheck.spearman()
    run.write("power_tropomi_crosscheck.csv",
           ["source", "fiscal_year", "no2_enh_mol_m2", "so2_enh_mol_m2", "n_days",
            "n_months", "ledger_net_GWh", "note"],
           [[r["source"], r["fiscal_year"], "%.4g" % r["no2_enh"],
             "%.4g" % ts2[(r["source"], r["fiscal_year"])]["so2_enh"]
             if (r["source"], r["fiscal_year"]) in ts2 else "",
             r["n_days"], r["n_months"],
             round(r["ledger_net_GWh"], 1) if r["ledger_net_GWh"] else "",
             "" if r["ledger_net_GWh"] else "beyond ledger coverage - observation only"]
            for r in tt]
           + [["VERDICT: " + k, "", "%.4g" % v if isinstance(v, float) else str(v),
               "", "", "", "", ""] for k, v in tv.items()]
           + [["SPEARMAN pooled", "", "%.3f" % sp["pooled_rho"],
               "p=%.3g" % sp["pooled_p"], sp["pooled_n"], "", "", ""],
              ["SPEARMAN within-source", "", "%.3f" % sp["within_rho"],
               "p=%.3g" % sp["within_p"], "", "", "", ""]])
    print("  TROPOMI: Thar ramp x%.1f NO2 / x%.1f SO2; Hub decline x%.2f; Sahiwal "
          "FY2021 satellite sides with generation (%.2f vs mass %.2f); within-source "
          "rank rho %.2f (p %.1g)"
          % (tv["h2_thar_no2_ratio"], tv["h2_thar_so2_ratio"],
             tv["h1_hub_ratio_fy2023_over_fy2020"],
             tv["h3_sahiwal_enh_ratio_fy2021_over_fy2020"],
             tv["h3_suspect_mass_ratio"], sp["within_rho"], sp["within_p"]))

    # The K-Electric leg, decision-ready: the exact series behind the boundary question.
    ke = ke_leg.series(data)
    run.write("power_ke_leg_%s.csv" % _sfx(year),
           ["fiscal_year", "gas_TJ", "rlng_TJ", "rfo_TJ", "hsd_TJ", "total_TJ",
            "co2_Mt", "net_GWh", "implied_net_efficiency_pct", "note"],
           [[r["fiscal_year"], round(r["gas_TJ"], 0), round(r["rlng_TJ"], 0),
             round(r["rfo_TJ"], 0), round(r["hsd_TJ"], 0), round(r["total_TJ"], 0),
             round(r["co2_Mt"], 3), round(r["net_GWh"], 1),
             round(100 * r["implied_net_efficiency"], 1),
             "MMCFT at the sector heating value, oil at IPCC default NCVs; only the two "
             "Nooriabad MMBTU rows are exact. CO2 only." if r["fiscal_year"] == 2019
             else ""] for r in ke])
    print("  K-Electric leg: %.1f -> %.1f Mt CO2 FY2019->FY2023 (RFO retired 977->209 kt);"
          " grid+KE sensitivity %.2f Mt"
          % (ke[0]["co2_Mt"], ke[-1]["co2_Mt"], grid + ke_leg.fy2023_case(data)))

    # The bagasse stream, at a glance: the sector's one generation-derived activity and
    # its one memo item, so the numbers a reader will quote live in one small file.
    bag_memo = engine.memo_items(data)
    bag_comps = [c for c in comps if c["subitem"].startswith("Bagasse")]
    run.write("power_bagasse_%s.csv" % _sfx(year), ["item", "value", "note"],
           [["Generation (GWh)", round(bagasse.generation_GWh(data), 2),
             "NEPRA SoIR 2024 Table 8 (E3), eight plants, reconciled against the printed "
             "total"],
            ["Fuel energy (TJ)", round(bagasse.fuel_TJ(data), 0),
             "generation x assumed 15,000 kJ/kWh - the sector's one generation-derived "
             "activity, labelled structurally weaker"],
            ["CH4+N2O (Mt CO2e, AR5)",
             round(sum(c["co2e_Mt_AR5"] for c in bag_comps), 5),
             "counted in 1A1a; the CH4 is non-fossil and takes AR5 28"],
            ["Biogenic CO2 memo (Gg)", round(bag_memo[0]["emissions_Gg"], 1),
             "outside every total, IPCC biomass convention"]])
    print("  bagasse: %.1f GWh -> %.3f Mt CH4+N2O in 1A1a; %.0f Gg biogenic CO2 as memo"
          % (bagasse.generation_GWh(data),
             sum(c["co2e_Mt_AR5"] for c in bag_comps), bag_memo[0]["emissions_Gg"]))

    # The implied coal calorific values - the third channel on the coal-conversion
    # question. Diagnostic (the sensitivity row above is its only touch on the totals).
    cv_rows = [[r["fiscal_year"], r["plant"], r["fuel_origin"], r["mass_kt"],
                r["net_generation_GWh"], r["hr_btu_kwh"], r["hr_basis_used"],
                r["implied_cv_TJ_per_Gg"], r["evidence_class"], r["note"]]
               for r in implied_cv.implied_coal_cv(data)]
    for y in sorted({r[0] for r in cv_rows}):
        f = implied_cv.fleet_cv(data, y)
        for label, key in (("FLEET (mass-weighted)", "fleet_cv"),
                           ("Thar lignite only", "thar_cv"),
                           ("imported only", "imported_cv"),
                           ("Table 3 implied NCV", "table3_implied_ncv")):
            cv_rows.append([y, label, "", round(f["fleet_mass_kt"], 1) if key == "fleet_cv" else "",
                            "", "", "",
                            round(f[key], 2) if f[key] else "",
                            "summary",
                            "Table 3 implies %s TJ/Gg (x%s) over ALL ledger mass; the "
                            "fleet CV covers %.0f%% of it"
                            % ("%.2f" % f["table3_implied_ncv"] if f["table3_implied_ncv"] else "-",
                               "%.2f" % f["table3_over_fleet"] if f["table3_over_fleet"] else "-",
                               100 * f["covered_share"])
                            if key == "fleet_cv" else ""])
    run.write("power_implied_coal_cv_%s.csv" % _sfx(year),
           ["fiscal_year", "plant", "fuel_origin", "mass_kt", "net_generation_GWh",
            "hr_btu_kwh", "hr_basis_used", "implied_cv_TJ_per_Gg", "evidence_class",
            "note"], cv_rows)
    run.write("power_hr_circularity_%s.csv" % _sfx(year),
           ["fiscal_year", "plant", "fuel", "ledger_btu_kwh", "t_hr_gross", "t_hr_net",
            "ratio_gross", "ratio_net", "verdict"],
           [[c["fiscal_year"], c["plant"], c["fuel"], c["ledger_btu_kwh"],
             c["t_hr_gross"], c["t_hr_net"], c["ratio_gross"], c["ratio_net"],
             c["verdict"]] for c in implied_cv.circularity(data)])
    fcv = implied_cv.fleet_cv(data, year)
    print("  IMPLIED COAL CV (Tables 20/23/28, LHV): Thar %.1f TJ/Gg - IPCC lignite; "
          "fleet %.1f vs Table 3's %.1f (x%.2f). Coal restated at these CVs: %.2f Mt "
          "(sensitivity row)."
          % (fcv["thar_cv"], fcv["fleet_cv"], fcv["table3_implied_ncv"],
             fcv["table3_over_fleet"], grid_cv))

    # Pakistan's official CRT filing for 1.A.1.a, cell-audited. Diagnostic only.
    crt = official_reporting.comparison(data)
    run.write("power_crt_comparison.csv", ["item", "value", "note"],
           [["CRT 1.A.1.a activity (TJ, CY2022)", round(crt["crt_total_TJ"], 0),
             "liquid + solid; gaseous fuels are NE in the official filing"],
            ["CRT 1.A.1.a CO2 (kt)", round(crt["crt_co2_kt"], 0),
             "arithmetic reproduced from activity x implied EF before any comparison"],
            ["Reporting basis", crt["basis"],
             "the CRT states NCV - official confirmation of the net calorific basis the "
             "plant-meter evidence (48.7 percent implied efficiency) supports physically"],
            ["Solid fuel, engine over CRT", round(crt["solid_ratio_engine_over_crt"], 3),
             "regulator's FY2022-23 coal energy against the CRT's CY2022 solid fuels: the "
             "two institutions agree on coal energy to 2 percent, which cuts against the "
             "reading of the coal-NCV diagnostic in which Table 3 grossly overstates it"],
            ["Liquid fuel, engine over CRT", round(crt["liquid_ratio_engine_over_crt"], 3),
             "the CRT's liquid activity is several times the regulator's fuel oil plus "
             "diesel; some reallocation is likely at work and the filing does not say"],
            ["Engine gas energy unmatched in CRT (TJ)",
             round(crt["engine_gas_TJ_unmatched_in_crt"], 0),
             "gaseous fuels are NOT ESTIMATED in the official public-electricity category, "
             "in a country whose regulator reports gas and RLNG as 43 percent of thermal "
             "fuel energy"],
            ["CRT implied lignite share of solid-fuel factor",
             round(crt["crt_implied_lignite_share"], 3),
             "97.57 t/TJ sits at a 46 percent lignite share on IPCC endpoints - between "
             "this paper's superseded 35 percent and its ledger-derived 79, dating from "
             "2022 when the Thar fleet was mid-ramp"]])
    print("  CRT 1.A.1.a (CY2022): 62,841 kt CO2 on NCV; solid agrees with the regulator "
          "to 2%%; GASEOUS FUELS ARE NE in the official filing")

    # The K-Electric boundary, tested rather than assumed. Diagnostic only.
    run.write("power_boundary_audit_%s.csv" % _sfx(year),
           ["fiscal_year", "gas_without_KE", "gas_with_KE", "KE_gas_TJ",
            "rfo_without_KE", "rfo_with_KE", "KE_rfo_TJ", "note"],
           [[a["fiscal_year"], round(a["gas_without_KE_over_national"], 3),
             round(a["gas_with_KE_over_national"], 3), round(a["KE_gas_TJ"], 0),
             round(a["rfo_without_KE_over_national"], 3),
             round(a["rfo_with_KE_over_national"], 3), round(a["KE_rfo_TJ"], 0),
             "plant energy over the national fuel row; gas leans CPPA-only, and FY2023 RFO is "
             "the panel's sharpest discriminator (0.890 without-KE vs 1.256 with). If "
             "Table 3 is CPPA-only, K-Electric's fuel - 7.1 down to 4.0 Mt CO2 across "
             "FY2019-23, see power_ke_leg - is outside the activity basis. The author's "
             "call, not a diagnostic's; the grid+KE case is a labelled sensitivity."]
            for a in plant_ledger.ke_boundary_audit(data)])
    audit = plant_ledger.ke_boundary_audit(data)
    over = sum(1 for a in audit if a["gas_with_KE_over_national"] > 1.0)
    print("  K-Electric boundary: gas with-KE exceeds the national row in %d of %d years; "
          "evidence leans CPPA-side-only coverage" % (over, len(audit)))

    # Whether NEPRA's coal energy and NEPRA's coal mass can describe one fleet, over
    # the whole ledger span. Reads the implied-CV diagnostic written above and is read
    # by the hypotheses register below, so it sits exactly here.
    from pkinv.sectors.power import coal_energy_adjudication
    coal_energy_adjudication.main([])

    # The Table 3 question, enumerated: reads the implied-CV, scenario, CRT,
    # boundary, circularity and adjudication diagnostics written above, so it must run
    # after every one of them and fails closed if a cited row disappears.
    from pkinv.sectors.power import table3_hypotheses
    table3_hypotheses.main()

    # The coal blend, from the plants - with Lucky Electric carried as bounds, and the
    # control-total NCV question published rather than acted on.
    cb = plant_ledger.coal_blend(data)
    ncv = plant_ledger.coal_ncv_diagnostic(data)
    run.write("power_coal_blend_%s.csv" % _sfx(year),
           ["item", "value", "unit", "note"],
           [["Thar-named plants, share of coal generation",
             round(100 * cb["gen_weighted_lo"], 1), "percent",
             "eight plants, FY%d-%d, from the plant fuel ledger" % (year, (year + 1) % 100)],
            ["Lucky Electric, share of coal generation",
             round(100 * cb["residual_share_of_generation"], 1), "percent",
             "THE RESIDUAL: its name states no coal origin, so it is carried as bounds "
             "rather than assigned"],
            ["Lignite share, Lucky as imported", round(cb["gen_weighted_lo"], 3), "fraction",
             "lower bound of coal_lignite_share"],
            ["Lignite share, Lucky as Thar", round(cb["gen_weighted_hi"], 3), "fraction",
             "upper bound; 0.79 is the midpoint"],
            ["Corroboration: mass x IPCC rank NCVs",
             "%.3f-%.3f" % (cb["ncv_route_lo"], cb["ncv_route_hi"]), "fraction",
             "independent route resting on default calorific values; overlaps the "
             "generation route, which is what makes the range defensible"],
            ["Implied fleet NCV from Table 3", round(ncv["implied_NCV_TJ_per_Gg"], 1),
             "TJ/Gg", "national coal TOE over ledger coal mass"],
            ["Default-blend NCV for the same fleet",
             round(ncv["default_blend_NCV_TJ_per_Gg"], 1), "TJ/Gg",
             "a fleet 92 percent lignite by mass at IPCC rank defaults. THE RATIO IS %.2f: "
             "either the TOE conversion treats all coal alike, or Thar coal far exceeds the "
             "lignite default, or the sources differ in scope. A control-total question, "
             "reported not resolved - it is also the shape of the coal heat-rate "
             "instability." % ncv["ratio"]]])

    print("  coal blend from the plant ledger: lignite %.3f-%.3f (Lucky unresolved at "
          "%.1f%% of coal generation); parameter set to 0.79"
          % (cb["gen_weighted_lo"], cb["gen_weighted_hi"],
             100 * cb["residual_share_of_generation"]))
    print("  COAL NCV DIAGNOSTIC: Table 3 implies %.1f TJ/Gg over a fleet that defaults "
          "to %.1f - ratio %.2f, reported not resolved"
          % (ncv["implied_NCV_TJ_per_Gg"], ncv["default_blend_NCV_TJ_per_Gg"], ncv["ratio"]))
    print("  plant-side energy closure (diagnostic):")
    print("    MMBTU plants imply %.1f%% net efficiency - no calorific assumption; gross "
          "would be %.1f%%" % (100 * eff, 100 * eff / 0.9))
    print("    plant gas energy is %.3f x the national TOE gas row; equality needs %.0f "
          "Btu/scf" % (gc["ratio"], gc["implied_hhv_btu_per_scf"]))
    print("  implied heat rate vs SIR Table 17 (diagnostic, does not enter the estimate):")
    for f, sv in sorted(stab.items()):
        if sv["spread"] is None:
            print("    %-12s %s" % (f, sv["note"]))
        else:
            print("    %-12s %4.1f-%4.1f%% over %d yr, spread x%.2f  %s"
                  % (f, 100 * sv["lo"], 100 * sv["hi"], sv["years"], sv["spread"],
                     sv["verdict"]))

    from pkinv.sectors.power import monthly
    monthly.main()

    run.finalize(qa_table="power_qa_%s.csv" % _sfx(year))


if __name__ == "__main__":
    main()
