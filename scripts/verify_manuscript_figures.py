#!/usr/bin/env python3
"""Every value a main figure plots, re-read from the released product it came from.

The active plot tables are built by scripts/build_integrated_figures.py.
This script does NOT go through the builder: it opens the products
themselves, selects the rows the captions name, and compares them with what the plot tables
hold. A value that survives two independent readings was not altered by a reshape.

    python3 scripts/verify_manuscript_figures.py            # current five figures
    python3 scripts/verify_manuscript_figures.py --legacy   # retained eight-figure diagnostics

Tolerance is half a unit in the last decimal a plot table prints; shares recomputed from masses
are compared at 1e-6 percentage points; grid sums are compared in parts per million, because the
cube stores float32.
"""
import csv
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
OUT = os.path.join(ROOT, "outputs")
FIG = os.path.join(ROOT, "paper_national", "figures")
DATA = os.path.join(FIG, "rewrite_inputs", "data")
REPORT = os.path.join(FIG, "redesign", "figure_value_checks.csv")
YEAR = "FY2023-24"

checks = []


def check(figure, quantity, source, product_value, plotted_value, tolerance):
    ok = abs(float(product_value) - float(plotted_value)) <= tolerance
    checks.append({"figure": figure, "quantity": quantity, "product": source,
                   "product_value": repr(float(product_value)), "plotted_value": repr(float(plotted_value)),
                   "tolerance": repr(tolerance), "agrees": "yes" if ok else "NO"})


def product(name, **kw):
    return pd.read_csv(os.path.join(OUT, name), comment="#", **kw)


def table(name):
    return pd.read_csv(os.path.join(DATA, name))


def integrated_checks():
    """Independently select final-product records for every integrated panel."""
    from pkinv.core import configurations as cfg
    import netCDF4
    folder = os.path.join(FIG, "integrated_inputs")
    def source(name):
        frame = product(name)
        if "configuration_id" in frame:
            frame = frame[frame.configuration_id.map(cfg.canonical) == cfg.REFERENCE]
        return frame
    ghg = source("pakemis_atomic_annual.csv")
    air = source("pakemis_air_annual_fy2015_16_fy2024_25.csv")
    ghg_mass = ghg.groupby(["period_id", "gas", "sector_id"]).emission_native_mass.sum()
    air_mass = air.groupby(["period_id", "pollutant", "sector_id"]).emissions_Gg.sum()
    def native(period, species, sector=None):
        own = ghg_mass if species in ("CO2", "CH4", "N2O") else air_mass
        matched = own.loc[period, species]
        return matched.get(sector) if sector is not None else matched.sum()
    for row in pd.read_csv(os.path.join(folder, "f09_integrated_composition.csv")).itertuples():
        quantity = native(row.period, row.species, row.module)
        if row.coverage_status == "no_admitted_estimate":
            assert quantity is None and pd.isna(row.native_Gg) and pd.isna(row.share_pct)
            continue
        total = native(row.period, row.species)
        check("9", row.species + "/" + row.module + " mass", "final native annual atoms", quantity, row.native_Gg, max(1e-8, abs(quantity) * 1e-12))
        check("9", row.species + "/" + row.module + " share", "native source and national sums", 100 * quantity / total, row.share_pct, 1e-9)
    levels = source("pakemis_air_conditional_uncertainty.csv")
    gas_levels = source("pakemis_ghg_conditional_uncertainty.csv")
    ar5 = ghg.groupby("period_id").co2e_Mt_AR5.sum()
    for row in pd.read_csv(os.path.join(folder, "f10_integrated_trends.csv")).itertuples():
        deterministic = ar5.loc[row.period] if row.species == "AR5" else native(row.period, row.species)
        pool = gas_levels if row.species == "AR5" else levels
        selected = pool[(pool.period_id == row.period) & (pool.sector_id == "national_covered") &
                        (pool.dependence_case == "persistent_parameters")]
        selected = selected[selected.species_or_metric == "CO2e_AR5"] if row.species == "AR5" else selected[selected.pollutant == row.species]
        assert len(selected) == 1
        own = selected.iloc[0]
        check("10", row.period + "/" + row.species + " central", "final annual atoms", deterministic, row.deterministic, 1e-7)
        for suffix in ("P2_5", "P97_5"):
            key = suffix + ("_quantity" if row.species == "AR5" else "_Gg")
            check("10", row.period + "/" + row.species + " " + suffix, "released conditional ensemble", own[key], getattr(row, suffix), 1e-7)
    cells = pd.read_csv(os.path.join(folder, "f11_integrated_maps.csv"))
    scales = pd.read_csv(os.path.join(folder, "f11_integrated_map_scales.csv"))
    paths = ("pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc", "pakemis_air_grid_0p05_annual_s_tan_fy2015_16_fy2024_25.nc")
    for row in scales.itertuples():
        gas = row.species in ("CO2", "CH4", "N2O")
        variable = {"CO2": "co2", "CH4": "ch4", "N2O": "n2o", "PM2.5": "pm25", "NOx": "nox", "NH3": "nh3"}[row.species] + "_emissions"
        with netCDF4.Dataset(os.path.join(OUT, paths[0 if gas else 1])) as ds:
            t = list(ds.variables["period_id"][:]).index(row.period)
            array = np.ma.asarray(ds.variables[variable][t], dtype="float64") * 1000
            if gas:
                array = array.sum(axis=0)  # disjoint partitions, not alternative complete maps
            mask = np.asarray(ds.variables["pakistan_fraction"][:]) <= 0
            expected = np.ma.masked_where(mask | (array <= 0), array)
            own = cells[cells.species == row.species]
            check("11", row.species + " cell count", "final cube positive placed cells", expected.count(), len(own), 0)
            check("11", row.species + " placed tonnes", "final cube native Gg to tonnes", expected.sum(), own.tonnes_per_cell.sum(), max(1e-7, expected.sum() * 1e-12))
            check("11", row.species + " published scale mass", "final cube placed sum", expected.sum(), row.placed_tonnes, max(1e-7, expected.sum() * 1e-12))
    cases = source("pakemis_air_structural_sensitivities.csv")
    for row in pd.read_csv(os.path.join(folder, "f12_air_sensitivity.csv")).itertuples():
        if row.kind in ("structural_case_no_probability", "attribution_diagnostic_no_probability"):
            selected = cases[(cases.period_id == YEAR) & (cases.pollutant == row.species) & (cases.scenario_id == row.case)]
            assert len(selected) == 1
            own = selected.iloc[0]
            check("12", row.species + "/" + row.case, "released structural case", own.case_covered_Gg / own.reference_covered_Gg, row.ratio, 1e-10)
        else:
            own = levels[(levels.period_id == YEAR) & (levels.pollutant == row.species) &
                         (levels.sector_id == "national_covered") & (levels.dependence_case == "persistent_parameters")].iloc[0]
            check("12", row.species + " lower", "released conditional interval", own.P2_5_Gg / own.deterministic_Gg, row.low_ratio, 1e-10)
            check("12", row.species + " upper", "released conditional interval", own.P97_5_Gg / own.deterministic_Gg, row.high_ratio, 1e-10)
    edgar = source("pakemis_industry_air_edgar_comparison.csv")
    htap = source("pakemis_air_htap_species_comparison.csv")
    for row in pd.read_csv(os.path.join(folder, "f13_air_evaluation.csv")).itertuples():
        if row.comparator == "HTAPv3.2":
            own = htap[(htap.period_id == row.period) & (htap.comparison_group == row.sector)
                       & (htap.pollutant == row.species) & (htap.comparison_status == "process_comparison")]
            assert len(own) == 1, (row.period, row.sector, row.species)
            own = own.iloc[0]
            other, estimate = own.htap_Gg, own.pakemis_Gg
        else:
            own = edgar[(edgar.period_id == row.period) & (edgar.species == row.species)].iloc[0]
            other, estimate = own.edgar_1a2_fossil_plus_2a1_kt, own.engine_industry_kt
            if "biomass" in row.comparator:
                other += own.edgar_1a2_fossil_bio_kt - own.edgar_1a2_fossil_kt
        check("13", row.period + "/" + row.species + "/" + row.sector + "/" + row.comparator, "released matched-boundary comparison", estimate / other, row.ratio_pakemis_over_comparator, 1e-10)


if "--legacy" not in sys.argv:
    integrated_checks()
    report = os.path.join(FIG, "integrated_inputs", "figure_value_checks.csv")
    os.makedirs(os.path.dirname(report), exist_ok=True)
    with open(report, "w", newline="") as handle:
        writer = csv.DictWriter(handle, list(checks[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(checks)
    failed = [r for r in checks if r["agrees"] != "yes"]
    print("Integrated figures: %d values checked against their products; %d disagree" % (len(checks), len(failed)))
    for row in failed:
        print(row)
    raise SystemExit(bool(failed))

# --- Figure 2 ------------------------------------------------------------------------------------
sectors = product("national_all_sectors.csv")
national = float(sectors.loc[sectors.row_kind == "national_total", "co2e_Mt_AR5"].iloc[0])
modules = table("module_totals.csv")
by_sector = sectors[sectors.row_kind == "sector"].set_index("sector")["co2e_Mt_AR5"]
assert len(by_sector) == len(modules) == 10
for value, plotted in zip(sorted(by_sector, reverse=True), sorted(modules.emissions_Mt_CO2e, reverse=True)):
    check("2a", "module total, rank order", "national_all_sectors.csv row_kind=sector", value, plotted, 0.005)
check("2a", "sum of the ten modules = reference total", "national_all_sectors.csv row_kind=national_total",
      national, float(by_sector.sum()), 5e-5)
series = product("pakemis_national_series.csv")
covered = series[series.row_kind == "covered_total"].sort_values("period_label")
annual = table("annual_national_series.csv")
assert list(covered.period_label) == list(annual.period)
value_column = [c for c in covered.columns if c.startswith("co2e_Mt") or c == "total_Mt"][0]
for (_, r), plotted in zip(covered.iterrows(), annual.emissions_Mt_CO2e):
    check("2b", "annual estimate %s" % r.period_label, "pakemis_national_series.csv row_kind=covered_total",
          r[value_column], plotted, 0.0005)
check("2b", "reference year of the series = reference total", "national_all_sectors.csv",
      national, float(covered.set_index("period_label").loc[YEAR, value_column]), 5e-5)
trend = product("pakemis_trend_uncertainty.csv")
trend = trend[trend.pair_kind == "window_full_panel"].set_index("scenario")
change = table("period_change_intervals.csv").set_index("scenario")
for scenario in ("time_correlated", "parameter_typed", "time_independent"):
    for col, pcol in (("difference_Mt", "difference_Mt_CO2e"), ("P2.5_Mt", "p025_Mt_CO2e"), ("P97.5_Mt", "p975_Mt_CO2e")):
        check("2c", "%s %s" % (scenario, col), "pakemis_trend_uncertainty.csv pair_kind=window_full_panel",
              trend.loc[scenario, col], change.loc[scenario, pcol], 0.005)
check("2c", "deterministic difference = last estimate less first", "pakemis_national_series.csv",
      float(covered[value_column].iloc[-1]) - float(covered[value_column].iloc[0]),
      float(trend.loc["parameter_typed", "difference_Mt"]), 5e-5)

# --- Figure 3 ------------------------------------------------------------------------------------
profile = product("temporal_profile.csv")
nat = profile[profile.scope == "NATIONAL"]
mass_column = [c for c in nat.columns if "Mt" in c][0]
by_class = nat.groupby("temporal_method")[mass_column].sum()
evidence = table("reference_temporal_evidence.csv").set_index("evidence_class")
for code in ("T1", "T2", "T3", "T4"):
    check("3a", "share of emissions in TE%s" % code[1], "temporal_profile.csv scope=NATIONAL",
          100.0 * by_class[code] / by_class.sum(), evidence.loc["TE" + code[1], "share_percent"], 0.005)
check("3a", "temporal classes cover the reference total", "temporal_profile.csv", national, float(by_class.sum()), 5e-4)
mc = product("national_uncertainty_montecarlo.csv")
row = mc[(mc.scenario == "within_sector") & (mc.aggregation_level == "national") & (mc.name == "TOTAL")].iloc[0]
unc = table("national_uncertainty.csv")
check("3b", "deterministic reference", "national_all_sectors.csv", national, unc.point_Mt_CO2e.iloc[0], 0.005)
for col, pcol in (("P2.5_Mt", "p025_Mt_CO2e"), ("P50_Mt", "point_Mt_CO2e"), ("P97.5_Mt", "p975_Mt_CO2e")):
    check("3b", "ensemble %s, within-module sharing" % col, "national_uncertainty_montecarlo.csv scenario=within_sector",
          row[col], unc[pcol].iloc[1], 0.005)

# --- Figures 4, 5, 6 -----------------------------------------------------------------------------
import xarray as xr                                                      # noqa: E402

cube = xr.open_dataset(os.path.join(OUT, "pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc"), decode_times=False)
iy = [str(x) for x in cube.period_id.values].index(YEAR)
ledger = product("pakemis_stream_support_ledger.csv")
unalloc = product("pakemis_spatial_unallocated.csv")
with open(os.path.join(FIG, "fig_ghg_grid_provenance.json"), encoding="utf-8") as handle:
    prov = json.load(handle)
ev = pd.read_csv(os.path.join(FIG, "fig_ghg_grid_evidence.csv"))
ref_ledger = ledger[ledger.period_id == YEAR]
LABEL = {"annual_observed_activity": "That year's observed activity", "static_structural": "Timeless structural surface",
         "reference_shape_backcast": "Reference year's pattern, rescaled", "substituted_surface": "Declared stand-in surface",
         "unallocated": "Retained at province level"}
for gas in ("CO2", "CH4", "N2O"):
    v = cube["%s_emissions" % gas.lower()].isel(time=iy).values.astype("float64")
    inside = np.isfinite(v).all(axis=0)
    placed = float(np.nansum(np.where(inside, np.nansum(v, axis=0), np.nan)))
    nat_gas = float(ref_ledger.loc[ref_ledger.gas == gas, "emissions_Gg"].sum())
    kept = float(unalloc.loc[unalloc.gas == gas, "emissions_Gg"].sum())
    check("4", "%s placed mass (Gg)" % gas, "annual cube, three views summed over valid cells",
          placed, prov["maps"][gas]["placed_Gg"], 1e-6 * placed)
    check("4", "%s placed + unallocated = national (Gg)" % gas, "cube + pakemis_spatial_unallocated.csv vs stream ledger",
          nat_gas, placed + kept, 1e-6 * nat_gas)
    check("4", "%s valid cells" % gas, "annual cube", int(inside.sum()), prov["maps"][gas]["valid_cells"], 0)
    for period, group in ledger[ledger.gas == gas].groupby("period_id"):
        total = float(group.emissions_Gg.sum())
        drawn = ev[(ev.gas == gas) & (ev.period_id == period)].iloc[0]
        for code, label in LABEL.items():
            share = 100.0 * float(group.loc[group.spatial_time_basis == code, "emissions_Gg"].sum()) / total
            check("5", "%s %s share: %s" % (gas, period, label), "pakemis_stream_support_ledger.csv",
                  share, drawn[label], 1e-6)

# figure 6(a): mass at register locations is the stream's mass times its located share
drawn_surface = pd.read_csv(os.path.join(FIG, "fig_ghg_grid_proxy.csv"))
for gas in ("CO2", "CH4", "N2O"):
    rows_ = ref_ledger[ref_ledger.gas == gas]
    points = rows_[rows_.surface.astype(str).str.contains("points")]
    at_points = float((points.emissions_Gg * points.located_share.fillna(1.0)).sum())
    row = drawn_surface[(drawn_surface.gas == gas) & (drawn_surface.period_id == YEAR)].iloc[0]
    check("6a", "%s share at facility and site locations" % gas, "pakemis_stream_support_ledger.csv emissions_Gg x located_share",
          100.0 * at_points / float(rows_.emissions_Gg.sum()), row["Facility and site locations"], 1e-6)
    kept = float(rows_.loc[rows_.spatial_time_basis == "unallocated", "emissions_Gg"].sum())
    check("6a", "%s share retained at province level" % gas, "pakemis_stream_support_ledger.csv spatial_time_basis=unallocated",
          100.0 * kept / float(rows_.emissions_Gg.sum()), row["Retained at province level"], 1e-6)

# --- Figure 7 ------------------------------------------------------------------------------------
btr = product("pakemis_btr_comparison.csv")
drawn = table("btr_subject_comparison.csv").set_index("subject")
like = btr[btr.tier.isin(["exact", "aggregate"]) & btr.btr_Mt_co2e.notna() & btr.pakemis_Mt_co2e.notna()
          & (btr.btr_Mt_co2e > 0)]
for subject, r in drawn.iterrows():
    if r["tier"] == "total-of-plotted":
        # computed by the plot-table builder; recomputed here from the product's own masses
        check("7", "ratio: total of the %d like-for-like categories" % len(like), "pakemis_btr_comparison.csv tiers exact, aggregate",
              like.pakemis_Mt_co2e.sum() / like.btr_Mt_co2e.sum(), r["ratio_pakemis_over_btr"], 0.005)
        check("7", "ratio at uniform CH4 28: total of the like-for-like categories", "pakemis_btr_comparison.csv",
              like.pakemis_Mt_co2e_ch4_uniform_28.sum() / like.btr_Mt_co2e.sum(), r["ratio_ch4_uniform_28"], 0.005)
        continue
    src = btr[btr.subject == subject].iloc[0]
    check("7", "ratio: %s" % subject, "pakemis_btr_comparison.csv", src["ratio_pakemis_over_btr"],
          r["ratio_pakemis_over_btr"], 0.005)
    check("7", "ratio = PakEmis / BTR: %s" % subject, "pakemis_btr_comparison.csv",
          float(src["pakemis_Mt_co2e"]) / float(src["btr_Mt_co2e"]), src["ratio_pakemis_over_btr"], 0.006)
    if str(r.get("ratio_ch4_uniform_28", "")) not in ("", "nan"):
        check("7", "ratio at uniform CH4 28: %s" % subject, "pakemis_btr_comparison.csv",
              src["ratio_ch4_uniform_28"], r["ratio_ch4_uniform_28"], 0.005)
plotted = set(drawn.index) - {"TOTAL of the like-for-like categories"}
eligible = set(btr[(btr.tier.isin(["exact", "aggregate", "total"])) & btr.btr_Mt_co2e.notna()
                   & btr.pakemis_Mt_co2e.notna() & (btr.btr_Mt_co2e > 0)].subject)
check("7", "every like-for-like subject is plotted, and nothing else", "pakemis_btr_comparison.csv tiers exact, aggregate, total",
      len(eligible), len(plotted & eligible) if plotted == eligible else -1, 0)

# --- Figure 8 ------------------------------------------------------------------------------------
flows = product("pakemis_faostat_nitrogen_flows.csv").set_index("flow")
sens = pd.read_csv(os.path.join(OUT, "eval", "sensitivity.csv"))
both = sens[sens.scenario.str.startswith("Both 2006 direct factors")].iloc[0]
soil = table("managed_soils_factor_scenarios.csv").set_index("case")
check("8", "reference", "pakemis_faostat_nitrogen_flows.csv 'managed soils, as reported' pakemis",
      flows.loc["managed soils, as reported", "pakemis"], soil.loc["PakEmis reference", "emissions_Mt_CO2e"], 0.005)
check("8", "2006 direct soil factor", "pakemis_faostat_nitrogen_flows.csv \"managed soils, at FAOSTAT's EF1 vintage\" pakemis",
      flows.loc["managed soils, at FAOSTAT's EF1 vintage", "pakemis"], soil.loc["2006 EF1", "emissions_Mt_CO2e"], 0.005)
pasture = sens[sens.scenario.str.startswith("Pasture EF3PRP = 2006 aggregate")].iloc[0]
check("8", "2006 pasture factors", "eval/sensitivity.csv scenario 'Pasture EF3PRP = 2006 aggregate' soils",
      pasture["soils"], soil.loc["2006 pasture", "emissions_Mt_CO2e"], 0.005)
check("8", "the two substitutions are additive on disjoint pathways", "eval/sensitivity.csv",
      float(both["soils"]) - float(flows.loc["managed soils, as reported", "pakemis"]),
      (float(flows.loc["managed soils, at FAOSTAT's EF1 vintage", "pakemis"]) - float(flows.loc["managed soils, as reported", "pakemis"]))
      + (float(pasture["soils"]) - float(flows.loc["managed soils, as reported", "pakemis"])), 0.02)
check("8", "2006 direct soil and pasture factors", "eval/sensitivity.csv scenario 'Both 2006 direct factors ...' soils",
      both["soils"], soil.loc["2006 EF1 and pasture", "emissions_Mt_CO2e"], 0.005)
check("8", "FAOSTAT", "pakemis_faostat_nitrogen_flows.csv 'managed soils, as reported' faostat",
      flows.loc["managed soils, as reported", "faostat"], soil.loc["FAOSTAT", "emissions_Mt_CO2e"], 0.005)

integrated_checks()
os.makedirs(os.path.dirname(REPORT), exist_ok=True)
with open(REPORT, "w", newline="", encoding="utf-8") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(checks[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(checks)
failed = [c for c in checks if c["agrees"] != "yes"]
by_figure = {}
for c in checks:
    by_figure.setdefault(c["figure"].rstrip("abc"), [0, 0])
    by_figure[c["figure"].rstrip("abc")][0 if c["agrees"] == "yes" else 1] += 1
for figure in sorted(by_figure):
    print("figure %s: %d values agree, %d do not" % (figure, by_figure[figure][0], by_figure[figure][1]))
print("%d values checked against their products; %d disagree -> %s" % (len(checks), len(failed), os.path.relpath(REPORT, ROOT)))
for c in failed:
    print("[FAIL] %(figure)s %(quantity)s: product %(product_value)s, plotted %(plotted_value)s" % c)
raise SystemExit(1 if failed else 0)
