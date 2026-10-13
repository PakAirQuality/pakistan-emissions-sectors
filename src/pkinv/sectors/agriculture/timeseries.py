"""Phase 6 - drive the Tier 2 engine over 1990-2024 with FAOSTAT historical activity data.

Method (Tier 2 EFs/parameters) is held constant; only activity data varies. The engine reads
activity purely from InventoryData's .livestock/.crops/.fertilizer dicts, so we mutate those
per year and call the existing build_components - no engine refactor.

Usage:  python3 -m pkinv.sectors.agriculture.timeseries   (run fetch_history.py first)
Writes: outputs/timeseries_1990_2024.csv, crt_AFOLU_table.csv, timeseries_validation.csv,
        trend_chart.png, timeseries_report.md
"""

from pkinv.assets import asset_path
import csv
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture.run_inventory import build_components, CATEGORIES  # noqa: E402

from pkinv.paths import ROOT
from pkinv.activity.store import read_rows

HIST = asset_path(ROOT, "data", "activity", "historical")
OUT = asset_path(ROOT, "outputs")
SPECIES = ["cattle", "buffalo", "sheep", "goats", "camels", "poultry"]
RUMINANTS = ["cattle", "buffalo", "sheep", "goats", "camels"]
START, ANCHOR = 1990, 2024


def _read(name):
    return read_rows(asset_path(HIST, name), comments=False)


def _load_history():
    live = {int(r["year"]): {s: float(r[s]) for s in SPECIES} for r in _read("livestock_stocks.csv")}
    crops = {}
    for r in _read("crops.csv"):
        crops.setdefault(int(r["year"]), {})[r["crop"]] = {
            "area_ha": float(r["area_ha"]) if r["area_ha"] else None,
            "production_t": float(r["production_t"]) if r["production_t"] else None}
    # fertilizer_n.csv ends at 2023 while its sibling files reach 2024 - a
    # DECLARED limit, not a defect: the FAOSTAT-basis path only ever computes
    # 1990-2023 (the 2024 anchor short-circuits to the census reconstruction
    # below and never reads this dict), so a 2024 fertiliser row would be dead.
    nitro = {int(r["year"]): float(r["n_tonnes"]) for r in _read("fertilizer_n.csv")}
    return live, crops, nitro


def _apply_year(data, live, crops, nitro, year=None):
    # rc39 A3: the backcast declares itself. A historical year carries a FAOSTAT total-N
    # figure and no product split, so its urea mass MUST be reconstructed; the reference year
    # has NFDC's printed product offtake and must not be. liming_urea reads this stamp rather
    # than inferring the basis from the numbers, because the two are only 0.2% apart and a
    # guess between them would be invisible when wrong.
    data.faostat_basis_year = year
    data.livestock = {s: {"head": live[s], "uncert_pct": 15} for s in SPECIES}
    data.crops = {c: {"area_ha": d["area_ha"], "production_t": d["production_t"],
                      "uncert_pct": 15} for c, d in crops.items()}
    data.fertilizer["nitrogen_N_offtake"]["value_t"] = nitro


def data_for_year(year):
    """Public: an InventoryData populated with FAOSTAT historical activity for `year`.

    2024 is the census-based anchor (standard InventoryData); 2020-2023 are rebuilt from
    data/activity/historical (same Tier-2 method, only activity varies). Used by the multi-year
    backcast to obtain per-year control totals via provincial_matrix(data_for_year(y))."""
    if year == ANCHOR:
        return InventoryData()
    live, crops, nitro = _load_history()
    if year not in live or year not in crops or year not in nitro:
        have = sorted(set(live) & set(crops) & set(nitro))
        raise ValueError("no historical activity for %d (have %d-%d)" % (year, have[0], have[-1]))
    data = InventoryData()
    _apply_year(data, live[year], crops[year], nitro[year], year=year)
    return data


def _aggregate(components):
    cat = {c: 0.0 for c in CATEGORIES}
    gas = {c: {"CO2": 0.0, "CH4": 0.0, "N2O": 0.0} for c in CATEGORIES}
    for comp in components:
        cat[comp["category"]] += comp["co2e_Mt_AR5"]
        gas[comp["category"]][comp["gas"]] += comp["emissions_Gg"]   # Gg = kt
    return cat, gas


def main():
    os.makedirs(OUT, exist_ok=True)
    live, crops, nitro = _load_history()
    years = [y for y in range(START, ANCHOR) if y in live and y in nitro and y in crops]

    data = InventoryData()
    series = {}    # year -> {"cat":..., "gas":..., "ad":...}
    for y in years:
        _apply_year(data, live[y], crops[y], nitro[y], year=y)
        cat, gas = _aggregate(build_components(data))
        series[y] = {"cat": cat, "gas": gas, "ad": _activity(live[y], crops[y], nitro[y])}

    # 2024 anchor = standard census-based Tier 2 run
    anchor = InventoryData()
    cat, gas = _aggregate(build_components(anchor))
    series[ANCHOR] = {"cat": cat, "gas": gas,
                      "ad": _activity({s: anchor.livestock[s]["head"] for s in SPECIES},
                                      {c: anchor.crops.get(c, {}) for c in anchor.crops},
                                      anchor.fertilizer["nitrogen_N_offtake"]["value_t"])}

    allyears = sorted(series)
    _write_series(series, allyears)
    _write_crt(series, [START, max(years), ANCHOR])
    faostat = _write_validation(series, years)
    _write_chart(series, allyears, faostat)
    _write_report(series, allyears, faostat)

    lo, hi = series[START]["cat"], series[ANCHOR]["cat"]
    tlo, thi = sum(lo.values()), sum(hi.values())
    cagr = ((thi / tlo) ** (1.0 / (ANCHOR - START)) - 1) * 100
    print("Pakistan agricultural emissions time series %d-%d (Tier 2):" % (START, ANCHOR))
    print("  %d total %.0f Mt CO2e -> %d total %.0f Mt CO2e  (CAGR %.1f%%/yr)"
          % (START, tlo, ANCHOR, thi, cagr))


def _activity(live, crops, nitro):
    rum = sum(live[s] for s in RUMINANTS)
    rice_area = (crops.get("rice") or {}).get("area_ha") or 0.0
    return {"ruminant_head": rum, "livestock_head": rum + live.get("poultry", 0.0),
            "rice_area_ha": rice_area, "n_tonnes": nitro}


def _write_series(series, years):
    with open(asset_path(OUT, "timeseries_1990_2024.csv"), "w", newline="") as f:
        w = csv.writer(f)
        # year_basis (the tenth review): 1990-2023 run on FAOSTAT CALENDAR-year
        # activity while the anchor is the FY2023-24 census reconstruction - a
        # TIME-basis break as well as a source break, and a column is the only
        # place it cannot be skimmed past. The seam's price lives in
        # outputs/pakemis_series_splice_agriculture.csv.
        w.writerow(["year", "year_basis", "category", "CO2_kt", "CH4_kt", "N2O_kt",
                    "co2e_Mt_AR5"])
        for y in years:
            basis = "fiscal_census_anchor" if y == ANCHOR else "calendar_faostat"
            for c in CATEGORIES:
                g = series[y]["gas"][c]
                w.writerow([y, basis, c, round(g["CO2"], 1), round(g["CH4"], 2),
                            round(g["N2O"], 3), round(series[y]["cat"][c], 2)])
            w.writerow([y, basis, "TOTAL", "", "", "",
                        round(sum(series[y]["cat"].values()), 2)])


def _write_crt(series, crt_years):
    # UNFCCC AFOLU CRT CODES, DELIBERATELY, AND THIS IS NOW THE ONLY PLACE THEY SURVIVE.
    # On 2026-10-06 the inventory adopted IPCC 2006 as its canonical classification and every
    # other shipped code column moved with it; a sweep for the retired sector-3 leaves (3.E,
    # 3.F, 3.G, 3.H, 3.I, 3.J, LU) across all 42 products with a code column returns this file
    # and nothing else. That is correct, not a miss: the table exists to be read against
    # Pakistan's own reporting, whose codes these are, and rewriting it to IPCC 2006 would
    # destroy the one thing it is for. The mapping between the two schemes is
    # data/shared/lookups/category_crosswalk.csv. Do not "fix" these codes.
    rows = []
    for y in crt_years:
        if y not in series:
            continue
        s = series[y]
        gas, ad = s["gas"], s["ad"]
        ent_ch4, man = gas["Enteric fermentation"]["CH4"], gas["Manure management"]
        rice_ch4 = gas["Rice cultivation"]["CH4"]
        soil_n2o = gas["Managed soils"]["N2O"]
        lu = gas.get("Urea application", {"CO2": 0.0})
        rows.append([y, "3.A", "Enteric Fermentation", round(ad["ruminant_head"]), "head",
                     0.0, round(ent_ch4, 1), 0.0, round(s["cat"]["Enteric fermentation"] * 1000),
                     round(ent_ch4 * 1e6 / ad["ruminant_head"], 1), "kg CH4/head/yr"])
        rows.append([y, "3.B", "Manure Management", round(ad["livestock_head"]),
                     "head incl. poultry",
                     0.0, round(man["CH4"], 1), round(man["N2O"], 2),
                     round(s["cat"]["Manure management"] * 1000), "", "CH4+N2O"])
        rows.append([y, "3.C", "Rice Cultivation", round(ad["rice_area_ha"]), "ha",
                     0.0, round(rice_ch4, 1), 0.0, round(s["cat"]["Rice cultivation"] * 1000),
                     round(rice_ch4 * 1e6 / ad["rice_area_ha"], 1) if ad["rice_area_ha"] else "",
                     "kg CH4/ha/yr"])
        rows.append([y, "3.D", "Agricultural Soils", round(ad["n_tonnes"]), "t N synthetic",
                     0.0, 0.0, round(soil_n2o, 2), round(s["cat"]["Managed soils"] * 1000),
                     round(soil_n2o / (ad["n_tonnes"] / 1000.0), 2) if ad["n_tonnes"] else "",
                     "kg N2O/t N (implied)"])
        burn = gas.get("Field burning of residues", {"CH4": 0.0, "N2O": 0.0})
        rows.append([y, "3.F", "Field Burning of Residues", "", "residue dry matter",
                     0.0, round(burn["CH4"], 2), round(burn["N2O"], 3),
                     round(s["cat"].get("Field burning of residues", 0.0) * 1000), "", "CH4+N2O"])
        # rc42 (the twentieth review's P-1): 3.G is NE in completeness.csv (no liming
        # activity is recorded for Pakistan's alkaline soils), and a notation key is not a
        # zero - this row used to print 0 in every numeric cell beside an NE elsewhere.
        rows.append([y, "3.G", "Liming", "NE", "t CaCO3/dolomite",
                     "NE", "NE", "NE", "NE", "", "NE: not estimated (alkaline soils; see completeness.csv)"])
        rows.append([y, "3.H", "Urea Application", "", "t urea (from N)",
                     round(lu["CO2"], 1), 0.0, 0.0,
                     round(s["cat"].get("Urea application", 0.0) * 1000), "", "CO2"])
        rows.append([y, "3", "Agriculture TOTAL", "", "", "", "", "",
                     round(sum(s["cat"].values()) * 1000), "", ""])
    with open(asset_path(OUT, "crt_AFOLU_table.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "code", "category", "activity_data", "AD_unit",
                    "CO2_kt", "CH4_kt", "N2O_kt", "CO2e_kt_AR5", "implied_EF", "EF_unit"])
        w.writerows(rows)


def _write_validation(series, years):
    rows = _read("faostat_emissions.csv")
    # STRICT ON THE SCHEMA. This used to be `float(r.get(c) or 0.0)`, which turns an absent
    # COLUMN into a plausible zero: rename a category and the FAOSTAT comparison quietly
    # starts validating the engine against nothing for that row, reporting a ratio instead of
    # an error. rc39 A4 renamed a category and this is what would have happened. A missing
    # column is a schema mismatch and has to say so; a missing VALUE is still legitimately 0.
    missing = [c for c in CATEGORIES if rows and c not in rows[0]]
    if missing:
        raise KeyError("faostat_emissions.csv has no column for %s - the engine's category "
                       "vocabulary and the cached FAOSTAT extract have diverged" % missing)
    faostat = {int(r["year"]): {c: float(r[c] or 0.0) for c in CATEGORIES} for r in rows}
    with open(asset_path(OUT, "timeseries_validation.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["year", "category", "engine_Mt", "faostat_Mt", "ratio", "band"])
        for y in years:
            if y not in faostat:
                continue
            for c in CATEGORIES:
                e, fa = series[y]["cat"][c], faostat[y][c]
                if not fa:  # urea/liming have no FAOSTAT GT item
                    w.writerow([y, c, round(e, 2), "n/a", "n/a", "no-faostat"])
                    continue
                ratio = e / fa
                band = "ok" if 0.5 <= ratio <= 1.5 else "review"
                w.writerow([y, c, round(e, 2), round(fa, 2), round(ratio, 2), band])
    return faostat


def _write_chart(series, years, faostat):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    ys = years
    # FAOSTAT has no urea/liming line, so the benchmark comparison is matched to the five
    # agriculture categories FAOSTAT reports (drop "Urea application" from both sides).
    fao_cats = [c for c in CATEGORIES if c != "Urea application"]
    stacks = [[series[y]["cat"][c] for y in ys] for c in CATEGORIES]
    _display = {"Urea application": "Urea application"}   # display-only relabel
    labels = [_display.get(c, c) for c in CATEGORIES]
    fig, ax = plt.subplots(figsize=(9, 5.5))
    ax.stackplot(ys, *stacks, labels=labels, alpha=0.85)
    # matched-scope engine subtotal (5 categories) and FAOSTAT line (5 categories)
    eng5 = [sum(series[y]["cat"][c] for c in fao_cats) for y in ys]
    ax.plot(ys, eng5, color="#0a3", lw=1.6, label="Engine, 5 agriculture categories (matched scope)")
    fa_years = [y for y in ys if y in faostat]
    fa5 = [sum(faostat[y].get(c, 0.0) for c in fao_cats) for y in fa_years]
    ax.plot(fa_years, fa5, "k--", lw=1.6, label="FAOSTAT, 5 agriculture categories")
    ax.axvline(ANCHOR, color="#555", ls=":", lw=1.2)
    ax.text(ANCHOR, ax.get_ylim()[1] * 0.02, " PBS-census anchor", rotation=90,
            va="bottom", ha="right", fontsize=7, color="#555")
    ax.set_xlabel("Year")
    ax.set_ylabel("Mt CO2e (AR5)")
    ax.set_title("Pakistan agricultural GHG emissions 1990-2024 (hybrid Tier 1/2, provisional)")
    ax.legend(loc="upper left", fontsize=8)
    ax.set_xlim(min(ys), max(ys))
    fig.tight_layout()
    fig.savefig(asset_path(OUT, "trend_chart.png"), dpi=130)


def _write_report(series, years, faostat):
    lo, hi = series[years[0]]["cat"], series[years[-1]]["cat"]
    tlo, thi = sum(lo.values()), sum(hi.values())
    n = years[-1] - years[0]
    cagr = ((thi / tlo) ** (1.0 / n) - 1) * 100
    lines = ["# Pakistan Agricultural GHG - Time Series 1990-2024 (Tier 2, provisional)\n",
             "Tier 2 method (constant Phase-5 EFs) driven over FAOSTAT historical activity "
             "data (livestock stocks, crop area/production, N fertiliser). The %d point is the "
             "census-based Tier 2 anchor; earlier years are FAOSTAT-activity-driven.\n" % ANCHOR,
             "## Trajectory\n",
             "- **%d:** %.0f Mt CO2e -> **%d:** %.0f Mt CO2e  (CAGR **%.1f%%/yr**, x%.1f over %d yr)\n"
             % (years[0], tlo, years[-1], thi, cagr, thi / tlo, n),
             "| Category | %d (Mt) | %d (Mt) | growth |" % (years[0], years[-1]),
             "|---|---:|---:|---:|"]
    for c in CATEGORIES:
        lines.append("| %s | %.1f | %.1f | x%.1f |" % (c, lo[c], hi[c], hi[c] / lo[c] if lo[c] else 0))
    lines += ["| **TOTAL** | **%.1f** | **%.1f** | **x%.1f** |" % (tlo, thi, thi / tlo), ""]
    lines += ["## Validation vs FAOSTAT (latest common year)\n",
              "| Category | Engine (Mt) | FAOSTAT (Mt) | ratio |", "|---|---:|---:|---:|"]
    vy = max(y for y in years if y in faostat)
    for c in CATEGORIES:
        e, fa = series[vy]["cat"][c], faostat[vy][c]
        lines.append("| %s | %.1f | %.1f | %.2f |" % (c, e, fa, e / fa if fa else 0))
    lines += ["",
              "## Caveats",
              "- Activity data is FAOSTAT (consistent series); the %d census-based snapshot "
              "(217 Mt) differs slightly from the FAOSTAT-driven point." % ANCHOR,
              "- Method held constant (Tier 2 EFs, dairy share 0.295) - this is an "
              "activity-driven trajectory, not a re-derivation of EFs per year.",
              "- Managed soils tracks below FAOSTAT (2019 disaggregated dry vs 2006 aggregate, "
              "see tier2_changelog.md); enteric/manure/rice track closely.", ""]
    with open(asset_path(OUT, "timeseries_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
