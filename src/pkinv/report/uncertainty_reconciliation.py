"""Sector-level vs national Monte Carlo: one table saying which distribution is which.

WHY. The sixth review put two published fugitives medians side by side - 25.434 Mt in
the sector's own output, 23.785 Mt in the national Monte Carlo - and observed that the
documents make them look like the same calculation. They are not: the sector module
draws bounded split-triangular multipliers (the mode IS the deterministic estimate, and
asymmetric IPCC ranges push the median above it), while the national engine draws
mean-preserving lognormals (the mean is the deterministic estimate, so the median sits
below it by exp(-sigma^2/2)). Neither is wrong; nothing said which a reader was looking
at. This table does, for every module: the deterministic centre, each treatment's
median and family, the gap, and why the gap exists.

Most rows are boring by construction - one family, and the gap is the lognormal
mean-median offset. The interesting rows CHANGED MEANING at rc12: fugitives and waste
now inject their sector engines' persisted draw files into the national pool
(report/uncertainty_all.INJECTED_MODULES), so their national rows carry the SAME
distribution family as the sector product and the median gap collapses to draw-count
noise - the sector tables publish 10,000 draws, the national rows their first
100,000-draw superset (the 10k are a bit-identical prefix). The 1.6 Mt fugitives gap
this table was built to explain no longer exists; the table now proves THAT.

Usage:  python3 -m pkinv.report.uncertainty_reconciliation
Writes: outputs/national_uncertainty_reconciliation.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

FIELDS = ("module", "deterministic_Mt", "national_p50_Mt", "national_distribution",
          "sector_p50_Mt", "sector_distribution", "sector_scope", "median_gap_Mt",
          "why")

NATIONAL_FAMILY = "mean_preserving_lognormal"

# Modules with a sector-level sampled product on the module total. (file, selector
# column, selector value, median column, family column or literal, scope note.)
SECTOR_MC = {
    "fugitives": ("fugitives_uncertainty_2024.csv", "segment", "TOTAL", "p50",
                  "@distribution", "module total"),
    "waste": ("waste_parameter_mc_2024.csv", "scope",
              "SECTOR", "P50", "parameter_rerun_ledger_true", "module total"),
    "railways": ("railways_uncertainty_scenarios_2024.csv", "structural_scenario",
                 "reference", "P50", NATIONAL_FAMILY, "module total"),
    "transport": ("transport_uncertainty_scenarios_2024.csv", "structural_scenario",
                  "reference", "P50", NATIONAL_FAMILY, "module total"),
    "power": ("power_uncertainty_scenarios_fy2023_24.csv", "structural_scenario",
              "reference", "P50_Mt", NATIONAL_FAMILY,
              "grid (1A1a) only - narrower than the national module row, which "
              "includes captive gas"),
}


def _rows(name):
    return read_rows(asset_path(OUTPUTS, name), comments=False)


def build():
    deterministic = {r["sector"]: float(r["co2e_Mt_AR5"])
                     for r in _rows("national_all_sectors.csv")
                     if r["row_kind"] == "sector"}
    national = {r["name"]: r for r in _rows("national_uncertainty_montecarlo.csv")
                if r["scenario"] == "within_sector"
                and r["aggregation_level"] == "module"}

    out = []
    for module in sorted(deterministic):
        nat = national.get(module)
        row = {"module": module,
               "deterministic_Mt": round(deterministic[module], 5),
               "national_p50_Mt": float(nat["P50_Mt"]) if nat else "",
               "national_distribution": nat["distribution_id"] if nat else "",
               "sector_p50_Mt": "", "sector_distribution": "", "sector_scope": "",
               "median_gap_Mt": "", "why": ""}
        spec = SECTOR_MC.get(module)
        if spec:
            fname, key_col, key, p50_col, family, scope = spec
            src = next(r for r in _rows(fname) if r[key_col] == key)
            sector_p50 = float(src[p50_col])
            row["sector_p50_Mt"] = round(sector_p50, 3)
            row["sector_distribution"] = (src[family[1:]] if family.startswith("@")
                                          else family)
            row["sector_scope"] = scope
            if nat and "grid" not in scope:
                row["median_gap_Mt"] = round(sector_p50 - float(nat["P50_Mt"]), 3)
            if nat and row["sector_distribution"] == nat["distribution_id"] \
                    and row["sector_distribution"] != NATIONAL_FAMILY:
                row["why"] = ("SAME DRAWS BY CONSTRUCTION (rc12): the national row "
                              "consumes the sector engine's persisted draw file "
                              "(outputs/mc_draws/), whose first 10,000 draws are "
                              "bit-identical to the sector table's; the residual "
                              "median gap is the draw-count difference (sector "
                              "10k vs national 100k), bounded by the convergence "
                              "table")
            elif row["sector_distribution"] != NATIONAL_FAMILY:
                row["why"] = ("DIFFERENT FAMILIES, neither wrong: the sector module "
                              "draws a family whose MODE is the deterministic "
                              "estimate, the national engine draws mean-preserving "
                              "lognormals whose MEAN is. Until rc12 fugitives and "
                              "waste sat in this branch; injection retired them "
                              "from it, and any module HERE now is a new finding")
            elif "grid" in scope:
                row["why"] = ("same family; the medians differ by SCOPE (the sector "
                              "product samples grid generation only), so no gap is "
                              "printed")
            else:
                row["why"] = ("same family; the residual gap is sampling noise plus "
                              "the mean-median offset at the module's sigma")
        else:
            row["why"] = ("no sector-level sampled product on the module total; the "
                          "national row is the only Monte Carlo treatment")
        out.append(row)
    return out


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = asset_path(OUTPUTS, "national_uncertainty_reconciliation.csv")
    write_table(path, list(FIELDS), rows)
    different = [r for r in rows
                 if r["sector_distribution"]
                 and r["sector_distribution"] != NATIONAL_FAMILY]
    print("uncertainty reconciliation -> %s (%d modules, %d with a different "
          "sector-level family)" % (os.path.basename(path), len(rows), len(different)))
    for r in different:
        print("  %-10s sector %s %s vs national %s %s"
              % (r["module"], r["sector_p50_Mt"], r["sector_distribution"],
                 r["national_p50_Mt"], r["national_distribution"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
