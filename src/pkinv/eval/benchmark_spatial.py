"""Benchmark task: district allocation scored against held records, on frozen splits.

WHY. The rho-0.944 rice claim was computed by a hand-run validation module against
whatever record was on disk. This module is the registered form: the district lists
are FROZEN in data/benchmark_splits/ (sha256 in data/benchmark_tasks.csv), the
baselines are deterministic (uniform and population - anyone could produce them
without the model), and the model's own allocation is scored beside them so the
claim is comparative, not absolute. The cropland proxy is also scored but labelled
REFERENCE: it is the model's own allocator, so its agreement with the model is
partly self-agreement and it must never be read as an independent baseline.

Records: MNFSR district rice and wheat area 2022-23, and the Punjab Crop Reporting
Service rice panel 2022-25 - the second, independent record, scored per year.
District categories with no held record are carried as NO_RECORD rows so absence is
declared, not implied.

Usage:  python3 -m pkinv.eval.benchmark_spatial [--check]
Writes: outputs/benchmark_spatial_allocation.csv
"""
import csv
import io
import os
import sys

from pkinv.paths import ROOT

sys.path.insert(0, os.path.join(ROOT, "src", "pkinv", "eval", "validation"))

from pkinv.assets import asset_path
from district_rice_records import _norm, _spearman  # noqa: E402
from pkinv.core.io import read_rows

SPLITS = asset_path(ROOT, "data", "benchmark_splits")
MODEL = asset_path(ROOT, "outputs", "district_totals_2024.csv")
RECORDS = asset_path(ROOT, "data", "district_records")
OUT = asset_path(ROOT, "outputs", "benchmark_spatial_allocation.csv")

# (task_id, model category, record file, record area column, per-year?)
TASKS = (
    ("spatial_rice_mnfsr", "Rice cultivation",
     "district_rice_area_MNFSR_2022-23.csv", "rice_area_ha", False),
    ("spatial_wheat_mnfsr", "Managed soils",
     "district_wheat_area_MNFSR_2022-23.csv", "wheat_area_ha", False),
    ("spatial_rice_punjabcrs", "Rice cultivation",
     "district_rice_area_PunjabCRS_2022-25.csv", "rice_area_ha", True),
)
# district-allocated categories with no independent held record (declared, not
# implied absent); enteric/manure records are the named acquisition in
# DATA_ACQUISITION.md
NO_RECORD = ("Enteric fermentation", "Manure management", "Manure on pasture")

ROLE_NOTE = {
    "uniform": "baseline: equal mass per matched district",
    "population": "baseline: WorldPop mass per district (proxy raster bincount)",
    "model": "the engine's own district allocation (district_totals_2024.csv)",
    "cropland": "reference (the model's own allocator; agreement is partly "
                "self-agreement) - never a baseline",
}


def _split(task_id):
    return [r["district"] for r in read_rows(asset_path(SPLITS, "%s.csv" % task_id), comments=False)]


def _model_values(category):
    values = {}
    with open(MODEL, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["category"] == category:
                values[_norm(r["district"])] = (
                    values.get(_norm(r["district"]), 0.0)
                    + float(r["co2e_Mt_AR5"]))
    return values


def _record_values(record_file, col, year=None):
    values = {}
    with open(asset_path(RECORDS, record_file), newline="",
              encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if year is not None and r.get("year") != year:
                continue
            try:
                a = float(r[col])
            except (ValueError, KeyError):
                continue
            if a > 0:
                values[_norm(r["district"])] = values.get(_norm(r["district"]),
                                                          0.0) + a
    return values


def _record_years(record_file):
    return sorted({r["year"] for r in read_rows(asset_path(RECORDS, record_file), comments=False) if r.get("year")})


def _proxy_by_district(proxy_name):
    """Sum a proxy raster per canonical district via the grid's district_id."""
    import numpy as np

    from pkinv.core.gis.grid import build_grid
    grid = build_grid()
    raster = np.load(asset_path(ROOT, "data", "gis",
                                  "proxy_%s_267x340.npy" % proxy_name)
                     ).astype(np.float64)
    ids = grid.district_id
    valid = ids >= 0
    mass = np.bincount(ids[valid].ravel().astype(np.int64),
                       weights=raster[valid].ravel(),
                       minlength=len(grid.districts))
    return {_norm(name): float(mass[idx])
            for idx, name in enumerate(grid.districts)}


def _score(candidate, record, districts):
    xs = [candidate.get(d, 0.0) for d in districts]
    ys = [record[d] for d in districts]
    if len(set(xs)) == 1:
        # a constant candidate (uniform) carries no ranking: Spearman and top-N
        # are undefined for it, only the share error is meaningful
        x_sum = sum(xs)
        wape = sum(abs(x / x_sum - y / sum(ys)) for x, y in zip(xs, ys))
        return {"spearman_rho": "", "p_value": "", "top10_overlap": "",
                "top15_overlap": "", "wape_shares": round(wape, 4)}
    rho, p = _spearman(xs, ys)
    x_sum, y_sum = sum(xs), sum(ys)
    wape = sum(abs(x / x_sum - y / y_sum) for x, y in zip(xs, ys)) \
        if x_sum > 0 else ""
    row = {"spearman_rho": rho, "p_value": p,
           "wape_shares": round(wape, 4) if wape != "" else ""}
    for n in (10, 15):
        if len(districts) >= n:
            top_c = {d for d, _ in sorted(zip(districts, xs),
                                          key=lambda kv: -kv[1])[:n]}
            top_r = {d for d, _ in sorted(zip(districts, ys),
                                          key=lambda kv: -kv[1])[:n]}
            row["top%d_overlap" % n] = round(len(top_c & top_r) / n, 3)
        else:
            row["top%d_overlap" % n] = ""
    return row


def compute():
    population = _proxy_by_district("population")
    cropland = _proxy_by_district("cropland")
    rows = []
    for task_id, category, record_file, col, per_year in TASKS:
        split = _split(task_id)
        model = _model_values(category)
        candidates = (("uniform", "baseline", {d: 1.0 for d in split}),
                      ("population", "baseline", population),
                      ("model", "model", model),
                      ("cropland", "reference", cropland))
        years = _record_years(record_file) if per_year else [None]
        for year in years:
            record = _record_values(record_file, col, year)
            districts = [d for d in split if record.get(d, 0.0) > 0]
            for name, role, values in candidates:
                row = {"task_id": task_id, "category": category,
                       "record": record_file,
                       "record_year": year or "2022-23",
                       "candidate": name, "role": role,
                       "n_districts": len(districts),
                       "status": "scored", "note": ROLE_NOTE[name]}
                row.update(_score(values, record, districts))
                rows.append(row)
    for category in NO_RECORD:
        rows.append({"task_id": "", "category": category, "record": "",
                     "record_year": "", "candidate": "", "role": "",
                     "n_districts": "", "spearman_rho": "", "p_value": "",
                     "wape_shares": "", "top10_overlap": "", "top15_overlap": "",
                     "status": "NO_RECORD",
                     "note": "district-allocated category with no independent "
                             "held record; declared absent, not implied - "
                             "livestock district records are a named "
                             "acquisition"})
    order = ["task_id", "category", "record", "record_year", "candidate",
             "role", "n_districts", "spearman_rho", "p_value", "top10_overlap",
             "top15_overlap", "wape_shares", "status", "note"]
    return [{k: r.get(k, "") for k in order} for r in rows], order


def main(check=False):
    rows, order = compute()
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=order, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    text = out.getvalue()
    if check:
        if not os.path.exists(OUT) or open(OUT, encoding="utf-8").read() != text:
            print("benchmark_spatial_allocation stale; rerun "
                  "python3 -m pkinv.eval.benchmark_spatial")
            return 1
        print("benchmark spatial allocation is current.")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    scored = [r for r in rows if r["status"] == "scored"]
    for r in scored:
        if r["candidate"] in ("model",):
            print("  %-24s %-8s rho %-6s top10 %-5s wape %s"
                  % (r["task_id"], r["record_year"], r["spearman_rho"],
                     r["top10_overlap"], r["wape_shares"]))
    print("wrote %d rows (%d scored, %d NO_RECORD) -> %s"
          % (len(rows), len(scored), len(rows) - len(scored),
             os.path.relpath(OUT, ROOT)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
