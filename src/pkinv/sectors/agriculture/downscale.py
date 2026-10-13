"""Phase 3 - downscale national Tier 1 emissions to provinces.

Each national component is allocated to provinces using a category-appropriate proxy
(province shares in data/province_shares.csv). Because every proxy's shares sum to 1,
the provincial totals reconcile exactly to the national control totals - the roadmap's
core safeguard against false precision.

Usage:  python3 -m pkinv.sectors.agriculture.downscale
Writes: outputs/provincial_by_category.csv, outputs/provincial_totals_2024.csv
"""

from pkinv.assets import asset_path
import csv
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData, _read, DATA_DIR  # noqa: E402
from pkinv.sectors.agriculture.run_inventory import build_components, OUT_DIR, CATEGORIES  # noqa: E402,F401

# Re-exported, not redefined: this name is imported from here by six modules.
from pkinv.core.geography import PROVINCES  # noqa: E402,F401

# Map each component to the proxy that best represents where its activity occurs.
# Keyed by (category, subitem); falls back to PROXY_FALLBACK by category.
PROXY_MAP = {
    ("Enteric fermentation", "dairy_cattle"): "livestock_cattle",
    ("Enteric fermentation", "other_cattle"): "livestock_cattle",
    ("Enteric fermentation", "buffalo"): "livestock_buffalo",
    ("Enteric fermentation", "sheep"): "livestock_sheep",
    ("Enteric fermentation", "goats"): "livestock_goats",
    ("Enteric fermentation", "camels"): "livestock_total",
    ("Manure management", "dairy_cattle (CH4)"): "livestock_cattle",
    ("Manure management", "other_cattle (CH4)"): "livestock_cattle",
    ("Manure management", "buffalo (CH4)"): "livestock_buffalo",
    ("Manure management", "sheep (CH4)"): "livestock_sheep",
    ("Manure management", "goats (CH4)"): "livestock_goats",
    ("Manure management", "camels (CH4)"): "livestock_total",
    ("Manure management", "poultry (CH4)"): "livestock_total",
    ("Manure management", "Direct N2O"): "livestock_total",
    ("Manure management", "Indirect N2O (volatilisation)"): "livestock_total",
    ("Rice cultivation", "Continuously flooded"): "rice_area",
    # Upland synthetic N follows fertiliser offtake; the rice-specific stream follows paddy area,
    # which is where that nitrogen is actually applied.
    ("Managed soils", "Direct N2O - synthetic fertiliser (upland)"): "fertilizer_N",
    ("Managed soils", "Direct N2O - synthetic fertiliser (rice EF1FR)"): "rice_area",
    # Applied manure follows neither animal density alone (it is carted to fields) nor cropland alone
    # (transport cost keeps it near the herd), but their intersection -- see proxies.manure_applied.
    ("Managed soils", "Direct N2O - organic manure"): "manure_applied",
    ("Managed soils", "Direct N2O - crop residues"): "crop_total",
    ("Managed soils", "Direct N2O - pasture deposition (cattle-type)"): "livestock_total",
    ("Managed soils", "Direct N2O - pasture deposition (sheep/goat/other)"): "livestock_smallrum",
    # Indirect N2O is allocated per source stream, not lumped: most of this nitrogen is
    # livestock-derived, so a single fertiliser proxy misplaced the bulk of it.
    ("Managed soils", "Indirect N2O - volatilisation (synthetic fertiliser)"): "fertilizer_N",
    ("Managed soils", "Indirect N2O - volatilisation (organic manure)"): "manure_applied",
    ("Managed soils", "Indirect N2O - volatilisation (pasture, cattle-type)"): "livestock_total",
    ("Managed soils", "Indirect N2O - volatilisation (pasture, sheep/goat/other)"): "livestock_smallrum",
    ("Managed soils", "Indirect N2O - leaching/runoff (synthetic fertiliser)"): "fertilizer_N",
    ("Managed soils", "Indirect N2O - leaching/runoff (organic manure)"): "manure_applied",
    ("Managed soils", "Indirect N2O - leaching/runoff (crop residues)"): "crop_total",
    ("Managed soils", "Indirect N2O - leaching/runoff (pasture, cattle-type)"): "livestock_total",
    ("Managed soils", "Indirect N2O - leaching/runoff (pasture, sheep/goat/other)"): "livestock_smallrum",
    ("Field burning of residues", "Residue burning CH4"): "crop_total",
    ("Field burning of residues", "Residue burning N2O"): "crop_total",
    ("Urea application", "Urea application CO2"): "fertilizer_N",
    ("Urea application", "Liming CO2"): "crop_total",
}
PROXY_FALLBACK = {
    "Enteric fermentation": "livestock_total", "Manure management": "livestock_total",
    "Rice cultivation": "rice_area", "Managed soils": "fertilizer_N",
    "Field burning of residues": "crop_total", "Urea application": "fertilizer_N",
}


def load_shares(period=None):   # rc44 A1: accepted, not yet used here
    shares = {}
    for r in _read(asset_path(DATA_DIR, "province_shares.csv")):
        shares[r["proxy"]] = {p: float(r[p]) for p in PROVINCES}
    return shares


def proxy_for(c):
    return PROXY_MAP.get((c["category"], c["subitem"]),
                         PROXY_FALLBACK[c["category"]])


def allocate_rows(data, components):
    """Allocate national components to provinces. Returns list of allocation rows."""
    shares = load_shares()
    for proxy, sh in shares.items():
        s = sum(sh.values())
        if abs(s - 1.0) > 1e-6:
            raise ValueError("province shares for '%s' sum to %.6f, not 1.0" % (proxy, s))
    rows = []  # province, category, subitem, proxy, co2e_Mt_AR5
    for c in components:
        proxy = proxy_for(c)
        for prov in PROVINCES:
            rows.append({
                "province": prov, "category": c["category"], "subitem": c["subitem"],
                "proxy": proxy,
                "co2e_Mt_AR5": c["co2e_Mt_AR5"] * shares[proxy][prov],
            })
    return rows


def provincial_rows(data=None):
    """Province x subitem allocation rows, each carrying the proxy that produced it.

    Phase 4 grids from these rather than from provincial_matrix, so a category whose subitems ride
    different proxies (managed soils: fertiliser, manure, pasture, cropland) is gridded per stream
    instead of on one category-wide raster.
    """
    if data is None:
        data = InventoryData()
    return allocate_rows(data, build_components(data))


def provincial_matrix(data=None):
    """Province x category control totals {province: {category: co2e_Mt_AR5}}.

    Single source of truth reused by Phase 4 gridding so it grids the same numbers
    the provincial report publishes.
    """
    matrix = {p: {c: 0.0 for c in CATEGORIES} for p in PROVINCES}
    for r in provincial_rows(data):
        matrix[r["province"]][r["category"]] += r["co2e_Mt_AR5"]
    return matrix


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    data = InventoryData()
    components = build_components(data)
    rows = allocate_rows(data, components)

    _write_by_category(rows)
    matrix = _write_totals(rows, components)
    _check_reconciliation(rows, components)
    _write_report(matrix)
    _print_summary(matrix)


def _write_by_category(rows):
    path = asset_path(OUT_DIR, "provincial_by_category.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["province", "category", "subitem", "proxy", "co2e_Mt_AR5"])
        for r in rows:
            w.writerow([r["province"], r["category"], r["subitem"], r["proxy"],
                        round(r["co2e_Mt_AR5"], 4)])


def _write_totals(rows, components):
    cats = CATEGORIES
    # matrix[province][category] = co2e
    matrix = {p: {c: 0.0 for c in cats} for p in PROVINCES}
    for r in rows:
        matrix[r["province"]][r["category"]] += r["co2e_Mt_AR5"]

    path = asset_path(OUT_DIR, "provincial_totals_2024.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["province"] + cats + ["TOTAL"])
        for p in PROVINCES:
            vals = [matrix[p][c] for c in cats]
            # rc41 (M-3): three decimals, like national_totals_2024.csv - at two, the
            # national rice cell read 16.55 and a manuscript rounding it once more printed
            # 16.6 against an engine value of 16.548.
            w.writerow([p] + [round(v, 3) for v in vals] + [round(sum(vals), 3)])
        # national control-total row
        natl = [sum(matrix[p][c] for p in PROVINCES) for c in cats]
        w.writerow(["NATIONAL (control)"] + [round(v, 3) for v in natl]
                   + [round(sum(natl), 3)])
    return matrix


def _check_reconciliation(rows, components):
    national = sum(c["co2e_Mt_AR5"] for c in components)
    allocated = sum(r["co2e_Mt_AR5"] for r in rows)
    assert abs(national - allocated) < 1e-6, \
        "reconciliation failed: national %.6f vs allocated %.6f" % (national, allocated)


def _write_report(matrix):
    cats = CATEGORIES
    national = sum(sum(matrix[p].values()) for p in PROVINCES)
    lines = ["# Pakistan Agricultural GHG - Provincial Downscaling (2024, provisional)\n",
             "National Tier 1 emissions allocated to provinces by category-appropriate "
             "proxies (`data/province_shares.csv`). Provincial totals reconcile exactly to "
             "the national control totals.\n",
             "## Provincial totals (Mt CO2e, AR5)\n",
             "| Province | " + " | ".join(cats) + " | TOTAL | Share |",
             "|---|" + "---:|" * (len(cats) + 2)]
    for p in PROVINCES:
        vals = [matrix[p][c] for c in cats]
        tot = sum(vals)
        lines.append("| %s | %s | %.1f | %.0f%% |"
                     % (p, " | ".join("%.1f" % v for v in vals), tot, 100 * tot / national))
    lines.append("| **NATIONAL** | %s | **%.1f** | 100%% |"
                 % (" | ".join("%.1f" % sum(matrix[p][c] for p in PROVINCES) for c in cats),
                    national))
    lines += ["", "## Allocation proxies\n",
              "- Enteric & manure CH4 -> province livestock shares by species "
              "(**PBS 7th Agricultural Census 2024**).",
              "- Rice CH4 -> rice harvested-area shares (MNFSR district-wise 2022-23).",
              "- Soils synthetic-N N2O -> fertiliser offtake shares (NFDC 2024-25).",
              "- Soils manure/pasture N2O -> livestock shares; residue N2O -> "
              "residue-mass-weighted crop shares.",
              "",
              "Livestock province shares are now on the **2024 census** (was 2006; e.g. KP's livestock "
              "share rose 0.153->0.195). District downscaling uses real 2024 census district counts "
              "(EF-weighted) where available, GLW-2020 proxy for unmatched districts.",
              ""]
    with open(asset_path(OUT_DIR, "provincial_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def _print_summary(matrix):
    print("Pakistan agricultural emissions by province (2024, provisional, Mt CO2e AR5):")
    for p in PROVINCES:
        print("  %-20s %7.1f" % (p, sum(matrix[p].values())))


if __name__ == "__main__":
    main()
