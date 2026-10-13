"""District rice validation against INDEPENDENT official crop records (no labelling needed).

Compares the model's per-district rice ranking (outputs/district_totals_2024.csv, Rice cultivation) to
the official district-wise rice AREA published by MNFSR / provincial Crop Reporting Services
(data/district_records/). Reports Spearman rank correlation + top-N overlap, overall and per province.
This is a genuine records-based check of the district downscaling (the desk step only had HLS flooding,
rho~0.19). Uses only real government figures -- nothing here is labelled by anyone.

Usage:  python3 -m pkinv.eval.validation.district_rice_records
Writes: outputs/eval/validation/district_rice_vs_records.{csv,json}
"""

from pkinv.assets import asset_path
import csv
import json
import os
import sys

from pkinv.paths import ROOT

MODEL = asset_path(ROOT, "outputs", "district_totals_2024.csv")
RECORDS = asset_path(ROOT, "data", "district_records", "district_rice_area_MNFSR_2022-23.csv")
OUT = asset_path(ROOT, "outputs", "eval", "validation")


def _norm(name):
    n = str(name).lower().replace(" district", "").replace("district", "").strip()
    return n.replace("shaikhupura", "sheikhupura").replace("qambar", "kambar").replace("-", " ").strip()


def _model_rice():
    m = {}
    for r in csv.DictReader(open(MODEL)):
        if r["category"] == "Rice cultivation":
            v = float(r["co2e_Mt_AR5"])
            if v > 0:
                m[_norm(r["district"])] = {"v": v, "province": r["province"]}
    return m


def _records_rice():
    rec = {}
    for r in csv.DictReader(open(RECORDS)):
        try:
            a = float(r["rice_area_ha"])
        except (ValueError, KeyError):
            continue
        if a > 0:
            rec[_norm(r["district"])] = {"a": a, "province": r["province"]}
    return rec


def _spearman(xs, ys):
    from scipy.stats import spearmanr
    rho, p = spearmanr(xs, ys)
    return (round(float(rho), 3), round(float(p), 5)) if rho == rho else (None, None)


def _topn_overlap(model, rec, n):
    tm = {k for k, _ in sorted(model.items(), key=lambda kv: -kv[1]["v"])[:n]}
    tr = {k for k, _ in sorted(rec.items(), key=lambda kv: -kv[1]["a"])[:n]}
    inter = tm & tr
    return round(len(inter) / n, 3), sorted(inter)


def compute():
    model, rec = _model_rice(), _records_rice()
    common = sorted(set(model) & set(rec))
    result = {"n_model_districts": len(model), "n_record_districts": len(rec),
              "n_matched": len(common), "records_source": os.path.basename(RECORDS),
              "note": "model per-district rice (Mt CO2e) vs official rice AREA (ha); rank comparison"}
    if len(common) >= 5:
        xs = [model[k]["v"] for k in common]
        ys = [rec[k]["a"] for k in common]
        rho, p = _spearman(xs, ys)
        result["spearman_rho"] = rho
        result["p_value"] = p
        for n in (10, 15, 20):
            if len(common) >= n:
                ov, inter = _topn_overlap({k: model[k] for k in common}, {k: rec[k] for k in common}, n)
                result["top%d_overlap" % n] = ov
        # per province
        result["per_province"] = {}
        for prov in ("Punjab", "Sindh"):
            ck = [k for k in common if rec[k]["province"] == prov]
            if len(ck) >= 5:
                pr, pp = _spearman([model[k]["v"] for k in ck], [rec[k]["a"] for k in ck])
                result["per_province"][prov] = {"n": len(ck), "spearman_rho": pr, "p": pp}
    return result, model, rec, common


def main():
    if not (os.path.exists(MODEL) and os.path.exists(RECORDS)):
        print("Need %s and %s" % (MODEL, RECORDS))
        return 1
    result, model, rec, common = compute()
    os.makedirs(OUT, exist_ok=True)
    with open(asset_path(OUT, "district_rice_vs_records.json"), "w") as f:
        json.dump(result, f, indent=2)
    # a side-by-side ranked CSV for inspection
    rows = sorted(common, key=lambda k: -model[k]["v"])
    with open(asset_path(OUT, "district_rice_vs_records.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["district", "province", "model_rice_Mt", "record_rice_ha",
                    "model_rank", "record_rank"])
        mrank = {k: i + 1 for i, k in enumerate(sorted(common, key=lambda k: -model[k]["v"]))}
        rrank = {k: i + 1 for i, k in enumerate(sorted(common, key=lambda k: -rec[k]["a"]))}
        for k in rows:
            w.writerow([k, rec[k]["province"], round(model[k]["v"], 3), round(rec[k]["a"], 0),
                        mrank[k], rrank[k]])
    print("District rice vs official records -> outputs/eval/validation/district_rice_vs_records.{json,csv}")
    print("  matched %d districts | Spearman rho %s (p=%s) | top-15 overlap %s"
          % (result["n_matched"], result.get("spearman_rho"), result.get("p_value"),
             result.get("top15_overlap")))
    for prov, d in result.get("per_province", {}).items():
        print("  %s: rho %s (n=%d)" % (prov, d["spearman_rho"], d["n"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
