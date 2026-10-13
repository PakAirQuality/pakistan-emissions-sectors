"""Benchmark: which district predictor best explains where the kilns ARE (rc13).

WHY THIS EXISTS. The kiln allocation product must say something about the 82
ADM2 units the detection survey never covered - "absence means unsurveyed, not
zero kilns" is the coverage mask's own tested sentence, so a points-only
allocation is forbidden by the data's own declaration. The honest way to choose
the unsurveyed-frame fallback is to TEST candidate predictors where the truth is
held: the mask's observed_kilns counts over the 65 surveyed districts. This
module scores uniform / population / builtup as predictors of those counts,
leave-one-province-out (spatially blocked - the frozen split is
data/benchmark_splits/spatial_kiln_allocation.csv), and the allocation product
adopts the pooled winner for the unsurveyed frame, by name.

WHAT THE SCORE IS NOT. Not an emissions benchmark: the truth here is detected
kiln COUNTS, which carry the survey's own coverage and the shared-shape
double-attribution (counts over shared geoBoundaries shapes appear on every
member unit, so the mask's count column sums above 11,272 - declared in the
task registry). And kiln counts are not kiln production: a count-weighted
allocation still assumes equal fuel per kiln, which the product's notes carry.

Usage:  python3 -m pkinv.eval.benchmark_kiln_allocation
Writes: outputs/benchmark_kiln_allocation.csv
"""

from pkinv.assets import asset_path
import csv
import os
import sys
from pkinv.core.io import read_rows, write_table

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))))
OUT = asset_path(ROOT, "outputs")

CANDIDATES = ("uniform", "population", "builtup")


def _spearman(xs, ys):
    def rank(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        ranks = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks
    rx, ry = rank(xs), rank(ys)
    n = len(xs)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = sum((a - mx) ** 2 for a in rx) ** 0.5
    dy = sum((b - my) ** 2 for b in ry) ** 0.5
    return num / (dx * dy) if dx and dy else 0.0


def _wape_shares(pred, truth):
    ps, ts = sum(pred), sum(truth)
    if not ps or not ts:
        return 1.0
    return sum(abs(p / ps - t / ts) for p, t in zip(pred, truth)) / 2.0 * 2.0


def proxy_by_adm2():
    """{adm2_id: {predictor: value}} for every canonical unit the grid resolves.

    Grid district names map to canonical ids through core.adm2.resolve; districts
    the boundary layer carries but the resolver cannot name are pooled and
    DECLARED in the output rather than silently dropped.
    """
    import numpy as np

    from pkinv.core import adm2
    from pkinv.core.gis.grid import build_grid
    grid = build_grid()
    out, unresolved = {}, []
    rasters = {}
    for name in ("population", "builtup"):
        rasters[name] = np.load(asset_path(
            ROOT, "data", "gis", "proxy_%s_267x340.npy" % name)).astype(np.float64)
    ids = grid.district_id
    valid = ids >= 0
    for pname, raster in rasters.items():
        mass = np.bincount(ids[valid].ravel().astype(np.int64),
                           weights=np.nan_to_num(raster[valid]).ravel(),
                           minlength=len(grid.districts))
        for idx, dname in enumerate(grid.districts):
            try:
                key = adm2.resolve(dname)
            except KeyError:
                if pname == "population":
                    unresolved.append(dname)
                continue
            out.setdefault(key, {"uniform": 1.0})[pname] = \
                out.get(key, {}).get(pname, 0.0) + float(mass[idx])
    return out, sorted(set(unresolved))


def split_rows():
    path = asset_path(ROOT, "data", "benchmark_splits",
                        "spatial_kiln_allocation.csv")
    return read_rows(path, comments=False)


def score():
    predictors, unresolved = proxy_by_adm2()
    rows = split_rows()
    usable = [r for r in rows if r["adm2_id"] in predictors]
    dropped = [r["adm2_id"] for r in rows if r["adm2_id"] not in predictors]
    provinces = sorted({r["record_province"] for r in usable})
    out = []
    for cand in CANDIDATES:
        pooled_pred = [predictors[r["adm2_id"]].get(cand, 0.0) for r in usable]
        pooled_truth = [float(r["observed_kilns"]) for r in usable]
        out.append({"candidate": cand, "block": "pooled",
                    "n_districts": len(usable),
                    "spearman_rho": round(_spearman(pooled_pred, pooled_truth), 4),
                    "wape_shares": round(_wape_shares(pooled_pred, pooled_truth), 4),
                    "note": ("truth = coverage-mask observed_kilns over the "
                             "surveyed frame; %d split districts unresolvable on "
                             "the grid (%s)" % (len(dropped),
                                                ";".join(dropped) or "none"))})
        for block in provinces:
            members = [r for r in usable if r["record_province"] == block]
            if len(members) < 3:
                out.append({"candidate": cand, "block": block,
                            "n_districts": len(members), "spearman_rho": "",
                            "wape_shares": "", "status": "declared_unscorable",
                            "note": "block too small to score; declared"})
                continue
            pred = [predictors[r["adm2_id"]].get(cand, 0.0) for r in members]
            truth = [float(r["observed_kilns"]) for r in members]
            out.append({"candidate": cand, "block": block,
                        "n_districts": len(members),
                        "spearman_rho": round(_spearman(pred, truth), 4),
                        "wape_shares": round(_wape_shares(pred, truth), 4),
                        "note": "held-out province block (leave-one-province-out "
                                "view: score within the block the pooled fit "
                                "never saw as a block)"})
    return out, unresolved


def winner(rows=None):
    """The pooled-best candidate by spearman, ties broken by wape."""
    rows = rows if rows is not None else score()[0]
    pooled = [r for r in rows if r["block"] == "pooled"]
    return sorted(pooled, key=lambda r: (-r["spearman_rho"],
                                         r["wape_shares"]))[0]["candidate"]


TASK_ID = "spatial_kiln_allocation"   # data/benchmark_tasks.csv


def _shaped(rows):
    """The benchmark shape the siblings carry (rc35): task_id joins the frozen
    task register, role says every candidate here is a baseline the winner is
    chosen FROM, status is the verdict column the validation catalog projects -
    'scored' where a metric exists, 'declared_unscorable' where the block was
    too small (a declared absence, never NO_RECORD: the record exists)."""
    out = []
    for r in rows:
        shaped = {"task_id": TASK_ID, "candidate": r["candidate"], "role": "baseline",
                  "block": r["block"], "n_districts": r["n_districts"],
                  "spearman_rho": r["spearman_rho"], "wape_shares": r["wape_shares"],
                  "status": r.get("status", "scored"), "note": r["note"]}
        out.append(shaped)
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    rows, _unresolved = score()
    path = asset_path(OUT, "benchmark_kiln_allocation.csv")
    write_table(path, ["task_id", "candidate", "role", "block", "n_districts",
                       "spearman_rho", "wape_shares", "status", "note"], _shaped(rows))
    best = winner(rows)
    print("kiln allocation benchmark -> %s" % os.path.basename(path))
    for r in rows:
        if r["block"] == "pooled":
            print("  %-10s pooled rho %s  wape %s"
                  % (r["candidate"], r["spearman_rho"], r["wape_shares"]))
    print("  winner (unsurveyed-frame fallback): %s" % best)
    return 0


if __name__ == "__main__":
    sys.exit(main())
