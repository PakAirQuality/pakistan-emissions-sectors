"""Monte-Carlo uncertainty for the agriculture inventory (IPCC Approach 2).

Each deterministic component (from build_components) is drawn lognormally from its documented
combined uncert_pct (the AD x EF Approach-1 value); IPCC recommends lognormal for emissions
(non-negative, right-skewed). Components are aggregated to category and national totals over many
seeded iterations to give mean + P5/P50/P95 bands, cross-checked against Approach 1.

A KNOWN ARCHITECTURAL LIMIT, SHARED WITH THE PRE-rc11 WASTE SECTOR. Drawing component
TOTALS cannot promise that the nitrogen ledger (n_ledger.py) closes in any single
realization, and expresses no covariance between the categories its stages couple - the
same defect the seventh review named and the waste sector repaired in rc11 with a
parameter-rerun Monte Carlo (waste/uncertainty.parameter_rerun_mc: draw the inputs,
rebuild the sector, assert the ledger per draw). Agriculture is the scheduled next
application - its N excretion, MMS shares and soil pathways are exactly the shared
parameters a rerun would couple correctly - and the wider goal, one common parameter
graph across every sector and the national engine, is recorded on the road to v1.0 in
docs/ROADMAP_STATE.md. Until then this module's bands carry the component-independence
caveat its own Approach-1 grouping notes already state.

Zero new core dependencies: stdlib `random` for sampling; matplotlib (optional) for the chart.

Usage:  python3 -m pkinv.sectors.agriculture.montecarlo
"""

from pkinv.assets import asset_path
import csv
import math
import os
import random
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture.run_inventory import build_components, CATEGORIES, OUT_DIR  # noqa: E402
from pkinv.core import montecarlo as mc_core  # noqa: E402

N_ITER = mc_core.N_ITER
SEED = mc_core.SEED
Z95 = mc_core.Z95

# Re-exported: the air-pollutant Monte Carlo imports these two by name from here.
_sigma_log = mc_core.sigma_log
_percentile = mc_core.percentile


def run_mc(n_iter=N_ITER, seed=SEED, data=None):
    """Return {category|'TOTAL': {mean,p025,p50,p975,rel_pct,approach1_pct}} and the samples.

    Agriculture's driver over core.montecarlo. HAS_SINKS is False, so the historic filter
    that drops non-positive components is preserved exactly -- it is sum-neutral but not
    RNG-stream-neutral, since dropping a row removes a gauss() call.
    """
    data = data or InventoryData()
    return mc_core.run(build_components(data), CATEGORIES,
                       n_iter=n_iter, seed=seed, has_sinks=False)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    stats, total_samples = run_mc()
    _write_csv(stats)
    _write_chart(total_samples, stats["TOTAL"])

    t = stats["TOTAL"]
    print("Monte-Carlo uncertainty (agriculture, N=%d, seed=%d; 95%% CI):" % (N_ITER, SEED))
    for c in CATEGORIES:
        s = stats[c]
        print("  %-26s mean %6.1f P50 %6.1f  P2.5-P97.5 [%5.1f, %5.1f]  +/-%4.1f%% (A1 %4.1f%%)"
              % (c, s["mean"], s["p50"], s["p025"], s["p975"], s["rel_pct"], s["approach1_pct"]))
    print("  %-26s mean %6.1f P50 %6.1f  P2.5-P97.5 [%5.1f, %5.1f]  +/-%4.1f%% (A1 %4.1f%%)"
          % ("TOTAL", t["mean"], t["p50"], t["p025"], t["p975"], t["rel_pct"], t["approach1_pct"]))


def _write_csv(stats):
    path = asset_path(OUT_DIR, "uncertainty_montecarlo.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "mean_Mt", "P2.5_Mt", "P50_Mt", "P97.5_Mt",
                    "rel_uncert_pct_MC_95", "approach1_pct_95"])
        for key in CATEGORIES + ["TOTAL"]:
            s = stats[key]
            w.writerow([key, round(s["mean"], 2), round(s["p025"], 2), round(s["p50"], 2),
                        round(s["p975"], 2), round(s["rel_pct"], 1), round(s["approach1_pct"], 1)])


def _write_chart(total_samples, t):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(total_samples, bins=60, color="#4a7", alpha=0.8, edgecolor="white", linewidth=0.3)
    for q, lab, col in ((t["p025"], "P2.5", "#c33"), (t["p50"], "P50", "#222"),
                        (t["p975"], "P97.5", "#c33")):
        ax.axvline(q, color=col, linestyle="--", linewidth=1.4)
        ax.text(q, ax.get_ylim()[1] * 0.95, " %s=%.0f" % (lab, q), color=col, fontsize=9)
    ax.set_xlabel("Pakistan agricultural emissions (Mt CO2e, AR5)")
    ax.set_ylabel("Monte-Carlo frequency")
    ax.set_title("Category-level lognormal Monte-Carlo aggregation (N=%d)\nmean %.0f Mt, 95%% CI [%.0f, %.0f], +/-%.0f%%"
                 % (len(total_samples), t["mean"], t["p025"], t["p975"], t["rel_pct"]))
    fig.tight_layout()
    fig.savefig(asset_path(OUT_DIR, "uncertainty_distribution.png"), dpi=130)
    plt.close(fig)


if __name__ == "__main__":
    main()
