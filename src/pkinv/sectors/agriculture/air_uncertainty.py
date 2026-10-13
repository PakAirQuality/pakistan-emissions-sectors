"""Monte-Carlo uncertainty for the air-pollutant layer, per pollutant.

Same construction as the GHG Monte-Carlo (src/pkinv/inventory/montecarlo.py): each component is drawn from a
mean-preserving lognormal parameterised by its documented combined uncertainty (a 95% relative
half-width), and the draws are aggregated. It is therefore an alternative distributional representation
of the same Approach-1 uncertainty assumptions, not independent evidence -- exactly as for the GHGs.
Components are sampled independently; correlations among shared drivers are not modelled.

Usage:  python3 -m pkinv.sectors.agriculture.air_uncertainty
Writes: outputs/air_uncertainty_montecarlo.csv, outputs/air_uncertainty_distribution.png
"""

from pkinv.assets import asset_path
import csv
import os
import random
import sys


from pkinv.sectors.agriculture import air_pollutants as ap  # noqa: E402
from pkinv.sectors.agriculture.montecarlo import _percentile, _sigma_log, N_ITER, SEED  # noqa: E402
from pkinv.core.uncertainty import combine_sum                 # noqa: E402

from pkinv.paths import ROOT

OUT = asset_path(ROOT, "outputs")
CSV_PATH = asset_path(OUT, "air_uncertainty_montecarlo.csv")
PNG_PATH = asset_path(OUT, "air_uncertainty_distribution.png")
POLLUTANTS = ["NH3", "NOx", "CO", "PM2.5", "NMVOC", "BC", "SO2"]


def _grouped(rows):
    """[(pollutant, group_kt, mass_weighted_uncert_pct)] at POOL grain, first-appearance
    order. THE DRAW IS PER POOL, NOT PER ROW, and this is a correctness property: the
    air spatial Wave A disaggregation split 14 rows into 76 (fertiliser per product,
    livestock per stage, soil NOx per N pool, burning per crop) as a pure REGROUPING of
    the same knowledge - and a per-row independent draw silently narrowed the NH3 95%
    interval by a factor of two (sqrt-N cancellation across sub-rows that share one
    factor family). Uncertainty must be invariant under a regrouping that adds no
    information, so the atoms of one pool draw as one component with the pool's
    mass-weighted uncertainty - the same _group() pooling the key-category ranking
    uses, for the same reason."""
    from pkinv.sectors.agriculture.air_key_categories import _group

    def correlation_group(subitem):
        g = _group(subitem)
        # the three N pools ride ONE shared NOx emission fraction - the pools differ
        # in their activity surface, not in factor knowledge, so for uncertainty they
        # are one component even though the ranking fairly treats them as three sources
        if g.startswith("Soil NOx"):
            g = "Soil NOx"
        return g

    order, acc = [], {}
    for r in rows:
        if r["emissions_kt"] <= 0:
            continue
        key = (r["pollutant"], correlation_group(r["subitem"]))
        if key not in acc:
            order.append(key)
            acc[key] = [0.0, 0.0]
        acc[key][0] += r["emissions_kt"]
        acc[key][1] += r["emissions_kt"] * float(r["uncert_pct"] or 0.0)
    return [(poll, acc[(poll, g)][0], acc[(poll, g)][1] / acc[(poll, g)][0])
            for poll, g in order]


def run_mc(n_iter=N_ITER, seed=SEED, rows=None):
    """{pollutant: {mean,p025,p50,p975,rel_pct,approach1_pct}} plus per-pollutant sample lists."""
    rows = rows if rows is not None else ap.compute()
    rng = random.Random(seed)
    pools = _grouped(rows)
    params = [(poll, value, _sigma_log(uncert)) for poll, value, uncert in pools]

    samples = {p: [] for p in POLLUTANTS}
    for _ in range(n_iter):
        acc = {p: 0.0 for p in POLLUTANTS}
        for poll, value, sig in params:
            # mean-preserving lognormal: E[draw] == value
            acc[poll] += value * pow(2.718281828459045, rng.gauss(0.0, sig) - sig * sig / 2.0)
        for poll in POLLUTANTS:
            samples[poll].append(acc[poll])

    # Approach-1 analytical cross-check over the same POOL components (the per-row
    # version re-narrows exactly the way the per-row draw did)
    a1 = {}
    for poll in POLLUTANTS:
        comps = [(value, uncert) for p, value, uncert in pools if p == poll]
        if comps:
            _, a1[poll] = combine_sum(comps)

    stats = {}
    for poll in POLLUTANTS:
        s = sorted(samples[poll])
        if not s or s[-1] <= 0:
            continue
        p025, p50, p975 = _percentile(s, 0.025), _percentile(s, 0.50), _percentile(s, 0.975)
        mean = sum(s) / len(s)
        rel = ((p975 - p025) / 2.0 / p50 * 100.0) if p50 else 0.0
        stats[poll] = {"mean": mean, "p025": p025, "p50": p50, "p975": p975,
                       "rel_pct": rel, "approach1_pct": a1.get(poll, 0.0)}
    return stats, samples


def _write_csv(stats):
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pollutant", "mean_kt", "P2.5_kt", "P50_kt", "P97.5_kt",
                    "rel_uncert_pct_MC_95", "approach1_pct_95"])
        for poll in POLLUTANTS:
            s = stats.get(poll)
            if s:
                w.writerow([poll, round(s["mean"], 2), round(s["p025"], 2), round(s["p50"], 2),
                            round(s["p975"], 2), round(s["rel_pct"], 1),
                            round(s["approach1_pct"], 1)])


def _write_chart(stats, samples):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        print("  (skipped air uncertainty chart: %s)" % e)
        return
    polls = [p for p in POLLUTANTS if p in stats]
    ncol = 4
    nrow = -(-len(polls) // ncol)
    fig, axes = plt.subplots(nrow, ncol, figsize=(3.4 * ncol, 2.7 * nrow))
    axflat = axes.ravel()
    for ax in axflat[len(polls):]:
        ax.axis("off")
    for ax, poll in zip(axflat, polls):
        s = stats[poll]
        ax.hist(samples[poll], bins=50, color="#4a7", alpha=0.85, edgecolor="white", linewidth=0.2)
        for q, col in ((s["p025"], "#c33"), (s["p50"], "#222"), (s["p975"], "#c33")):
            ax.axvline(q, color=col, ls="--", lw=1.1)
        ax.set_title("%s: %.0f kt $\\pm$%.0f%%" % (poll, s["mean"], s["rel_pct"]), fontsize=9)
        ax.tick_params(labelsize=7)
    fig.suptitle("Air-pollutant uncertainty: category-level lognormal Monte-Carlo (N=%d)" % N_ITER)
    fig.tight_layout()
    fig.savefig(PNG_PATH, dpi=130)
    plt.close(fig)


def main():
    os.makedirs(OUT, exist_ok=True)
    stats, samples = run_mc()
    _write_csv(stats)
    _write_chart(stats, samples)
    print("Air-pollutant Monte-Carlo (N=%d, seed=%d; 95%% CI):" % (N_ITER, SEED))
    for poll in POLLUTANTS:
        s = stats.get(poll)
        if s:
            print("  %-6s mean %8.1f  P2.5-P97.5 [%8.1f, %8.1f]  +/-%4.1f%% (A1 %4.1f%%)"
                  % (poll, s["mean"], s["p025"], s["p975"], s["rel_pct"], s["approach1_pct"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
