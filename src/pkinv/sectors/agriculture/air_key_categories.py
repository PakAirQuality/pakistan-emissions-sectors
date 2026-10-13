"""Key-source analysis for the air-pollutant layer, per pollutant (IPCC Approach 1).

Same two assessments the GHG key-category analysis uses (src/pkinv/inventory/key_categories.py), applied to
each pollutant separately and at SUB-ITEM granularity: with only three source categories -- and five of
the seven pollutants arising from a single crop-residue-burning stream -- a category-level analysis
would be degenerate at 100%.

  level : share of that pollutant's 2024 national total, cumulated to the 95% threshold
  trend : IPCC Eq 4.2, T_x = L_x,0 * |g_x - g_tot|, over 1990 -> 2024

UNCERTAINTY-AWARE SINCE rc10. A ranking of point estimates hides how sure it is: two
sources at 32% and 31% with 40-50% uncertainties could swap on any redraw. Each source
now carries a Monte Carlo interval on its level share and a RANK-STABILITY column - the
percentage of draws in which it keeps the rank the point estimate gives it - using the
per-component stream discipline from core.montecarlo (each source draws from its own
seeded RNG, so adding a source moves nobody else's interval). DEGENERACY IS DECLARED,
NOT LAUNDERED: five pollutants arise from a single estimated stream, so their 100%
stability is a statement about COVERAGE (nothing else is estimated), not certainty,
and the note column says so on exactly those rows.

Usage:  python3 -m pkinv.sectors.agriculture.air_key_categories
Writes: outputs/air_key_categories.csv, outputs/air_key_categories.md
"""

from pkinv.assets import asset_path
import collections
import csv
import math
import os
import random
import sys


from pkinv.sectors.agriculture import air_pollutants as ap  # noqa: E402
from pkinv.sectors.agriculture import timeseries as ts  # noqa: E402
from pkinv.sectors.agriculture.ef_library import InventoryData            # noqa: E402
from pkinv.sectors.agriculture.key_categories import _cumulative_flag     # noqa: E402  (unit-agnostic, reused as-is)
from pkinv.core import montecarlo as mc  # noqa: E402

from pkinv.paths import ROOT

OUT = asset_path(ROOT, "outputs")
CSV_PATH = asset_path(OUT, "air_key_categories.csv")
MD_PATH = asset_path(OUT, "air_key_categories.md")
BASE_YEAR, YEAR = ts.START, ts.ANCHOR


def _group(subitem):
    """The pool-level source name: the Wave A disaggregation gave the atoms product,
    species-stage and crop suffixes, but a KEY CATEGORY is a pool - five crops of the
    same burning practice are one source for ranking, and treating them as five would
    dilute every rank into false stability."""
    g = subitem.rsplit(" (", 1)[0]
    if g in ("NH3 - housing", "NH3 - yard", "NH3 - storage"):
        g = "NH3 - housing and storage"
    return g


def _by_pollutant_subitem(rows):
    out = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in rows:
        out[r["pollutant"]][_group(r["subitem"])] += abs(r["emissions_kt"])
    return {p: dict(d) for p, d in out.items()}


N_MC = 10000


def mc_rank_stability(rows, n_iter=N_MC, seed=mc.SEED):
    """{(pollutant, subitem): (share_p2_5, share_p97_5, rank_stability_pct)}.

    Mean-preserving lognormal per source, per-component streams: each
    (pollutant, subitem) draws from its own RNG seeded off its identity, so the
    intervals are stable under additions elsewhere - the same discipline the
    national GHG Monte Carlo uses and for the same reason.
    """
    grouped = collections.defaultdict(lambda: [0.0, 0.0])
    for r in rows:
        if r["emissions_kt"]:
            g = grouped[(r["pollutant"], _group(r["subitem"]))]
            g[0] += abs(r["emissions_kt"])
            # the group's uncertainty: mass-weighted mean of its atoms' (the atoms of
            # one pool share their factor family, so the weighting is the honest
            # single number for the rank draw)
            g[1] += abs(r["emissions_kt"]) * float(r["uncert_pct"] or 0.0)
    by_poll = collections.defaultdict(list)
    for (poll, name), (value, wu) in grouped.items():
        by_poll[poll].append((name, value, wu / value if value else 0.0))
    out = {}
    for poll, sources in by_poll.items():
        point_rank = sorted(sources, key=lambda s: -s[1])
        rank_of = {name: i for i, (name, _v, _u) in enumerate(point_rank)}
        draws = {}
        for name, value, uncert in sources:
            rng = random.Random(mc.stream_seed(seed, "air|%s|%s" % (poll, name)))
            sigma = mc.sigma_log(uncert)
            draws[name] = [value * math.exp(sigma * rng.gauss(0, 1)
                                            - 0.5 * sigma * sigma)
                           for _ in range(n_iter)]
        held = {name: 0 for name, _v, _u in sources}
        shares = {name: [] for name, _v, _u in sources}
        for i in range(n_iter):
            sample = [(name, draws[name][i]) for name, _v, _u in sources]
            total = sum(v for _n, v in sample)
            order = sorted(sample, key=lambda s: -s[1])
            for rank, (name, value) in enumerate(order):
                if rank == rank_of[name]:
                    held[name] += 1
                shares[name].append(value / total)
        for name, _v, _u in sources:
            vals = sorted(shares[name])
            out[(poll, name)] = (mc.percentile(vals, 0.025),
                                 mc.percentile(vals, 0.975),
                                 100.0 * held[name] / n_iter)
    return out


def compute():
    """({pollutant: {"level": [...], "trend": [...]}}, mc_map) with rows (name, share, cum, key)."""
    ref_rows = ap.compute(InventoryData())
    ref = _by_pollutant_subitem(ref_rows)
    base = _by_pollutant_subitem(ap.compute(ts.data_for_year(BASE_YEAR)))
    mc_map = mc_rank_stability(ref_rows)
    n_sources = collections.Counter(p for p, _n in mc_map)

    result = {}
    for poll, level_scores in ref.items():
        if sum(level_scores.values()) <= 0:          # nothing emitted: no key sources
            result[poll] = {"level": [], "trend": []}
            continue
        level_rows = _cumulative_flag(level_scores)

        b = base.get(poll, {})
        trend_rows = []
        base_total = sum(b.values())
        if base_total > 0:
            tot_b = base_total
            tot_r = sum(level_scores.get(k, 0.0) for k in b)
            g_tot = (tot_r - tot_b) / abs(tot_b)
            trend_score = {}
            for sub, e0 in b.items():
                et = level_scores.get(sub, 0.0)
                g_x = (et - e0) / abs(e0) if e0 else 0.0
                l_x0 = abs(e0) / base_total
                trend_score[sub] = l_x0 * abs(g_x - g_tot)
            if sum(trend_score.values()) > 0:
                trend_rows = _cumulative_flag(trend_score)
        result[poll] = {"level": level_rows, "trend": trend_rows}
    return result, mc_map, n_sources


def _write(result, mc_map, n_sources):
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["pollutant", "source", "level_pct", "cum_level_pct", "key_by_level",
                    "trend_pct", "cum_trend_pct", "key_by_trend", "key",
                    "level_pct_p2_5", "level_pct_p97_5", "rank_stability_pct", "note"])
        for poll in sorted(result):
            trend = {n: (s, c, k) for n, s, c, k in result[poll]["trend"]}
            for name, share, cum, key in result[poll]["level"]:
                ts_, tc, tk = trend.get(name, (None, None, None))
                lo, hi, stable = mc_map.get((poll, name), (None, None, None))
                degenerate = n_sources.get(poll, 0) == 1
                w.writerow([poll, name, round(100 * share, 2), round(100 * cum, 2),
                            "YES" if key else "no",
                            round(100 * ts_, 2) if ts_ is not None else "n/a",
                            round(100 * tc, 2) if tc is not None else "n/a",
                            ("YES" if tk else "no") if tk is not None else "n/a",
                            "YES" if (key or tk) else "no",
                            round(100 * lo, 2) if lo is not None else "n/a",
                            round(100 * hi, 2) if hi is not None else "n/a",
                            round(stable, 1) if stable is not None else "n/a",
                            ("single estimated stream: the 100 percent share and "
                             "stability measure COVERAGE, not certainty - nothing "
                             "else is estimated for this pollutant"
                             if degenerate else "")])

    lines = ["# Air-pollutant key-source analysis (IPCC Approach 1, 95% threshold)\n",
             "Level = share of the pollutant's %d national total; trend = IPCC Eq 4.2 over %d-%d. "
             "Analysed at sub-item granularity, because five of the seven pollutants arise from a "
             "single crop-residue-burning stream and would otherwise be trivially 100%%.\n"
             % (YEAR, BASE_YEAR, YEAR)]
    for poll in sorted(result):
        rows = result[poll]["level"]
        if not rows:
            continue
        keys = [n for n, _, _, k in rows if k]
        lines.append("## %s\n" % poll)
        lines.append("| Source | Level %% | Cum %% | Key |")
        lines.append("|---|---:|---:|:--:|")
        for name, share, cum, key in rows:
            lines.append("| %s | %.1f | %.1f | %s |"
                         % (name, 100 * share, 100 * cum, "YES" if key else ""))
        lines.append("")
        lines.append("Key sources by level: %s\n" % ", ".join(keys))
    with open(MD_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    os.makedirs(OUT, exist_ok=True)
    result, mc_map, n_sources = compute()
    _write(result, mc_map, n_sources)
    print("Air-pollutant key-source analysis -> air_key_categories.{csv,md}")
    for poll in sorted(result):
        rows = result[poll]["level"]
        if rows:
            keys = [n for n, _, _, k in rows if k]
            print("  %-6s %d source(s); key by level: %s" % (poll, len(rows), "; ".join(keys)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
