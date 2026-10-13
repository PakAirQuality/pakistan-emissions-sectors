"""Freeze the benchmark splits: the holdout definitions, hashed into the registry.

WHY. Gate 6 requires ML and allocation claims to be scored on FROZEN holdouts - and
until rc10 the eval family's comparisons were hand-run against whatever was on disk,
with no split manifest and no hash, so nothing could prove a later run used the same
holdout. This script derives each split deterministically from the held records,
writes the manifests under data/benchmark_splits/, and stamps their sha256 into
data/benchmark_tasks.csv. A perturbed manifest fails the suite's hash check; a
re-derived one is byte-identical.

Splits frozen here:
  spatial_rice_mnfsr        the matched-district list for rice vs MNFSR 2022-23
  spatial_wheat_mnfsr       ditto for managed soils vs wheat area
  spatial_rice_punjabcrs    rice vs the Punjab Crop Reporting Service panel
                            (2022-25, three years - the second, independent record,
                            unused before rc10)
  temporal_origins          the rolling-origin schedule over the 48-month OCAC panel,
                            with each origin's train/test measurement regime declared
                            (direct monthly editions vs cumulative-differenced - the
                            regime changes at 2022-07 and 2024-07 are part of the
                            split definition, not a surprise for the scorer)

Usage:  python3 scripts/build_benchmark_splits.py [--check]
Writes: data/benchmark_splits/*.csv ; updates data/benchmark_tasks.csv hashes
"""
import csv
import hashlib
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "src", "pkinv", "eval", "validation"))

from pkinv.assets import asset_path

SPLITS = asset_path(ROOT, "data", "benchmark_splits")
TASKS = asset_path(ROOT, "data", "benchmark_tasks.csv")

# fy_start -> measurement regime, from the panel's report_kind survey. The stream
# list itself lives in pkinv.eval.benchmark_temporal.STREAMS - the split freezes
# the ORIGINS, the scorer owns the streams.
REGIME = {2021: "direct_monthly", 2022: "cumulative_differenced",
          2023: "cumulative_differenced", 2024: "direct_monthly"}


def _norm():
    from district_rice_records import _norm as fn
    return fn


def _matched(model_category, record_file, record_col):
    # match on the NORMALIZED NAME ONLY, exactly like the validated module -
    # province spellings differ between the record ("KPK") and the model
    # ("Khyber Pakhtunkhwa"), and a tuple match silently drops 23 KP districts
    norm = _norm()
    model = set()
    with open(asset_path(ROOT, "outputs", "district_totals_2024.csv"), newline="",
              encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["category"] == model_category and float(r["co2e_Mt_AR5"]) > 0:
                model.add(norm(r["district"]))
    record = {}
    with open(asset_path(ROOT, "data", "district_records", record_file), newline="",
              encoding="utf-8") as f:
        for r in csv.DictReader(f):
            try:
                a = float(r[record_col])
            except (ValueError, KeyError):
                continue
            if a > 0:
                record[norm(r["district"])] = r["province"]
    matched = sorted(model & set(record))
    return [{"district": d, "record_province": record[d]} for d in matched]


def build():
    manifests = {}
    manifests["spatial_rice_mnfsr.csv"] = _matched(
        "Rice cultivation", "district_rice_area_MNFSR_2022-23.csv", "rice_area_ha")
    manifests["spatial_wheat_mnfsr.csv"] = _matched(
        "Managed soils", "district_wheat_area_MNFSR_2022-23.csv", "wheat_area_ha")
    manifests["spatial_rice_punjabcrs.csv"] = _matched(
        "Rice cultivation", "district_rice_area_PunjabCRS_2022-25.csv",
        "rice_area_ha")

    origins = []
    for test_fy in (2022, 2023, 2024):
        origins.append({
            "origin_id": "fy%d" % test_fy,
            "train_fy_start": test_fy - 1, "test_fy_start": test_fy,
            "train_regime": REGIME[test_fy - 1], "test_regime": REGIME[test_fy],
            "regime_change": "yes" if REGIME[test_fy - 1] != REGIME[test_fy]
                             else "no",
            "note": "predict the test fiscal year's 12-month shape from data "
                    "available at its start; a regime change between train and "
                    "test years is part of what the error measures"})
    manifests["temporal_origins.csv"] = origins

    # rc13: the kiln-allocation split - the SURVEYED half of the coverage mask,
    # blocked by province. The truth column is the mask's own observed_kilns
    # count (shared-shape counts appear on every member unit, so the column sums
    # above the 11,272 asset rows - a property of the mask, declared in the task
    # registry, not a defect of the split).
    kiln = []
    with open(asset_path(ROOT, "data", "gis", "kilns",
                           "pak_brick_kiln_coverage.csv"), newline="",
              encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["coverage"] == "observed_kilns":
                kiln.append({"adm2_id": r["adm2_id"],
                             "record_province": r["province"],
                             "observed_kilns": r["observed_kilns"]})
    manifests["spatial_kiln_allocation.csv"] = sorted(
        kiln, key=lambda r: r["adm2_id"])

    # rc13: the road-transport allocation split - frozen NOW so the day a
    # district traffic or fuel record is acquired, the holdout already exists
    # and cannot be chosen after seeing the model. All canonical frame units,
    # blocked by province; the truth column is deliberately absent
    # (status=pending_record in the task registry).
    road = []
    with open(asset_path(ROOT, "data", "gis", "kilns",
                           "pak_brick_kiln_coverage.csv"), newline="",
              encoding="utf-8") as f:
        for r in csv.DictReader(f):
            road.append({"adm2_id": r["adm2_id"],
                         "record_province": r["province"]})
    manifests["spatial_road_transport.csv"] = sorted(
        road, key=lambda r: r["adm2_id"])

    return manifests


def _render(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(check=False):
    manifests = build()
    texts = {name: _render(rows) for name, rows in manifests.items()}
    hashes = {name: hashlib.sha256(text.encode()).hexdigest()
              for name, text in texts.items()}

    if check:
        for name, text in texts.items():
            path = asset_path(SPLITS, name)
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
                print("%s is stale; run python3 scripts/build_benchmark_splits.py"
                      % name)
                return 1
        print("benchmark splits are current.")
        return 0

    os.makedirs(SPLITS, exist_ok=True)
    for name, text in texts.items():
        open(asset_path(SPLITS, name), "w", encoding="utf-8").write(text)

    # stamp hashes into the task registry
    with open(TASKS, newline="", encoding="utf-8") as f:
        tasks = list(csv.DictReader(line for line in f
                                    if not line.startswith("#")))
    header = open(TASKS, encoding="utf-8").read().split("\n")
    comments = [line for line in header if line.startswith("#")]
    for t in tasks:
        split = t["holdout_definition"].split("/")[-1]
        if split in hashes:
            t["holdout_sha256"] = hashes[split]
    out = io.StringIO()
    for c in comments:
        out.write(c + "\n")
    writer = csv.DictWriter(out, fieldnames=list(tasks[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(tasks)
    open(TASKS, "w", encoding="utf-8").write(out.getvalue())
    for name, rows in manifests.items():
        print("  %-28s %4d rows  %s" % (name, len(rows), hashes[name][:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
