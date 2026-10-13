"""District validation against INDEPENDENT official crop records, beyond rice.

Extends district_rice_records.py to a second crop-driven category. The model's per-district ranking
(outputs/district_totals_2024.csv) is compared, by rank, to official MNFSR district-wise crop AREA
(data/district_records/, parsed from the 2022-23 Crops Area & Production booklet):

  * Rice cultivation  vs  district RICE area   (MNFSR Table No.2)   -- the existing check (rho~0.94)
  * Managed soils      vs  district WHEAT area  (MNFSR Table No.1)   -- new: soil-N2O geography is
        driven by cropland/fertiliser intensity, for which wheat area (the dominant crop, ~9 Mha,
        grown across every cropping district) is a strong INDEPENDENT proxy -- independent of the
        WorldCover cropland and NFDC fertiliser layers the model's district split actually uses.

Honesty guard: livestock categories (enteric, manure) are NOT validated here -- their district split
already uses the PBS 2024 census head-counts, so the only district livestock "record" is the same data
the model consumes; comparing them would be circular. That gap is reported explicitly, not papered over.

Uses only real government figures -- nothing is labelled by anyone.

Usage:  python3 -m pkinv.eval.validation.district_records_multi
Writes: outputs/eval/validation/district_records_multi.{csv,json}
"""

from pkinv.assets import asset_path
import csv
import json
import os
import sys

from pkinv.eval.validation.district_rice_records import _norm, _spearman, _topn_overlap  # noqa: E402

from pkinv.paths import ROOT

MODEL = asset_path(ROOT, "outputs", "district_totals_2024.csv")
DREC = asset_path(ROOT, "data", "district_records")
OUT = asset_path(ROOT, "outputs", "eval", "validation")

# (model category, record CSV, record area column, human label)
CHECKS = [
    ("Rice cultivation", "district_rice_area_MNFSR_2022-23.csv", "rice_area_ha", "district rice area (MNFSR Table 2)"),
    ("Managed soils", "district_wheat_area_MNFSR_2022-23.csv", "wheat_area_ha", "district wheat area (MNFSR Table 1)"),
]
# categories with no independent district record (proxy IS the only district statistic) -> stated gap
NO_RECORD = {
    "Enteric fermentation": "district split uses PBS 2024 census head-counts; the census is the only "
                            "district livestock statistic, so an independent records check would be circular",
    "Manure management": "same PBS 2024 census basis as enteric -- no independent district record",
    "Field burning of residues": "district split is satellite FIRMS active fire; no official district "
                                 "crop-residue-burning record is published",
    "Urea application": "district split is fertiliser/cropland proxy; no district-wise urea/lime "
                           "offtake record is published",
}


def _model_category(cat):
    m = {}
    for r in csv.DictReader(open(MODEL, newline="", encoding="utf-8")):
        if r["category"] == cat:
            v = float(r["co2e_Mt_AR5"])
            if v > 0:
                m[_norm(r["district"])] = {"v": v, "province": r["province"]}
    return m


def _records(path, col):
    rec = {}
    for r in csv.DictReader(open(path, newline="", encoding="utf-8")):
        try:
            a = float(r[col])
        except (ValueError, KeyError):
            continue
        if a > 0:
            rec[_norm(r["district"])] = {"a": a, "province": r["province"]}
    return rec


def _one_check(cat, rec_file, col, label):
    path = asset_path(DREC, rec_file)
    if not os.path.exists(path):
        return {"category": cat, "record": label, "status": "record file absent (%s)" % rec_file}
    model, rec = _model_category(cat), _records(path, col)
    common = sorted(set(model) & set(rec))
    res = {"category": cat, "record": label, "record_source": rec_file,
           "n_model_districts": len(model), "n_record_districts": len(rec), "n_matched": len(common),
           "note": "model per-district %s (Mt CO2e) vs official %s; rank comparison" % (cat, label)}
    if len(common) >= 5:
        rho, p = _spearman([model[k]["v"] for k in common], [rec[k]["a"] for k in common])
        res["spearman_rho"], res["p_value"] = rho, p
        for n in (10, 15, 20):
            if len(common) >= n:
                ov, _ = _topn_overlap({k: model[k] for k in common}, {k: rec[k] for k in common}, n)
                res["top%d_overlap" % n] = ov
        res["per_province"] = {}
        for prov in ("Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan"):
            ck = [k for k in common if rec[k]["province"] == prov]
            if len(ck) >= 5:
                pr, pp = _spearman([model[k]["v"] for k in ck], [rec[k]["a"] for k in ck])
                res["per_province"][prov] = {"n": len(ck), "spearman_rho": pr, "p": pp}
    return res, model, rec, common


def compute():
    checks, tables = [], {}
    for cat, rec_file, col, label in CHECKS:
        out = _one_check(cat, rec_file, col, label)
        if isinstance(out, tuple):
            res, model, rec, common = out
            checks.append(res)
            tables[cat] = (model, rec, common)
        else:
            checks.append(out)
    gaps = [{"category": c, "reason": r} for c, r in NO_RECORD.items()]
    return {"checks": checks, "no_independent_record": gaps,
            "summary": "Independent government crop-area records validate the district geography of the "
                       "two crop-driven categories; livestock/fire/liming have no independent district "
                       "record and are reported as gaps."}, tables


def main():
    if not os.path.exists(MODEL):
        print("Need %s" % MODEL)
        return 1
    result, tables = compute()
    os.makedirs(OUT, exist_ok=True)
    with open(asset_path(OUT, "district_records_multi.json"), "w") as f:
        json.dump(result, f, indent=2)
    # a stacked side-by-side ranked CSV across the checks
    with open(asset_path(OUT, "district_records_multi.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["category", "district", "province", "model_Mt", "record_area_ha",
                    "model_rank", "record_rank"])
        for cat, (model, rec, common) in tables.items():
            mrank = {k: i + 1 for i, k in enumerate(sorted(common, key=lambda k: -model[k]["v"]))}
            rrank = {k: i + 1 for i, k in enumerate(sorted(common, key=lambda k: -rec[k]["a"]))}
            for k in sorted(common, key=lambda k: -model[k]["v"]):
                w.writerow([cat, k, rec[k]["province"], round(model[k]["v"], 3),
                            round(rec[k]["a"], 0), mrank[k], rrank[k]])
    print("District validation vs independent records -> outputs/eval/validation/district_records_multi.{json,csv}")
    for c in result["checks"]:
        if "spearman_rho" in c:
            print("  %-24s vs %-32s n=%-3d rho=%s (p=%s) top15=%s"
                  % (c["category"], c["record"], c["n_matched"], c["spearman_rho"],
                     c["p_value"], c.get("top15_overlap")))
            for prov, d in c.get("per_province", {}).items():
                print("      %-22s rho %s (n=%d)" % (prov, d["spearman_rho"], d["n"]))
        else:
            print("  %-24s %s" % (c["category"], c.get("status", "not scored")))
    print("  no independent district record (stated gaps): " + ", ".join(NO_RECORD))
    return 0


if __name__ == "__main__":
    sys.exit(main())
