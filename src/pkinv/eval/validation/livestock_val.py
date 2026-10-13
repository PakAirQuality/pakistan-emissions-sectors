"""Livestock desk-validation: province-ordering plausibility (no pixel validation, by design).

The management-intensity model has near-chance pixel skill; its usable output is a province-level
ordering of confined/intensive management. We validate only that ordering against an independent
reference: the PBS Livestock Census province shares (data/province_shares.csv) - buffalo and cattle
are concentrated in the Punjab/Sindh canal belt where intensive/stall-fed dairy dominates, versus
pastoral Balochistan. Metric: Spearman rank correlation of the model's confined fraction with the
census dairy/herd concentration. Pure local, no GEE.

Outputs: data/validation/livestock_validation.csv, outputs/eval/validation/livestock_validation.json.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import json
import os
import sys

from pkinv.paths import ROOT, DATA


CARD = asset_path(ROOT, "models", "livestock_mgmt_card.json")
SHARES = asset_path(DATA, "province_shares.csv")
WORKSHEET = asset_path(ROOT, "data", "validation", "livestock_validation.csv")
METRICS = asset_path(ROOT, "outputs", "eval", "validation", "livestock_validation.json")
PROVS = ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan"]   # named provinces (exclude "Other")
COL = {"Punjab": 0, "Sindh": 1, "Khyber Pakhtunkhwa": 2, "Balochistan": 3}


def _census_shares():
    """{'cattle': {prov: share}, 'buffalo': {...}} from province_shares.csv (PBS Livestock Census)."""
    out = {}
    for r in _activity_rows(SHARES, comments=False):
        key = r.get("category") or r.get("proxy") or list(r.values())[0]
        if key in ("livestock_cattle", "livestock_buffalo"):
            vals = [float(v) for v in list(r.values())[1:5]]
            out[key.replace("livestock_", "")] = {p: vals[COL[p]] for p in PROVS}
    return out


def _spearman(a, b):
    def rank(x):
        order = sorted(range(len(x)), key=lambda i: x[i])
        rk = [0] * len(x)
        for pos, i in enumerate(order):
            rk[i] = pos
        return rk
    ra, rb = rank(a), rank(b)
    n = len(a)
    return 1 - 6 * sum((ra[i] - rb[i]) ** 2 for i in range(n)) / (n * (n * n - 1)) if n > 1 else None


def run():
    os.makedirs(os.path.dirname(WORKSHEET), exist_ok=True)
    os.makedirs(os.path.dirname(METRICS), exist_ok=True)
    if not os.path.exists(CARD):
        print("  livestock validation skipped (train the management model first)")
        return None
    model = json.load(open(CARD)).get("province_confined_fraction", {})
    census = _census_shares()
    mv = [model.get(p, 0.0) for p in PROVS]
    buf = [census.get("buffalo", {}).get(p, 0.0) for p in PROVS]
    cat = [census.get("cattle", {}).get(p, 0.0) for p in PROVS]
    rho_buf = _spearman(mv, buf)
    rho_cat = _spearman(mv, cat)

    with open(WORKSHEET, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["province", "model_confined_fraction", "census_buffalo_share",
                    "census_cattle_share", "manual_note"])
        for p in PROVS:
            w.writerow([p, _r(model.get(p)), _r(census.get("buffalo", {}).get(p)),
                        _r(census.get("cattle", {}).get(p)), ""])

    metrics = {
        "module": "livestock",
        "reference": "PBS Livestock Census province shares (independent of the model)",
        "validation_scope": "PROVINCE ORDERING ONLY - no pixel validation claimed",
        "spearman_vs_cattle": round(rho_cat, 3) if rho_cat is not None else None,
        "spearman_vs_buffalo_circular": round(rho_buf, 3) if rho_buf is not None else None,
        "model_order": sorted(PROVS, key=lambda p: -model.get(p, 0.0)),
        "census_cattle_order": sorted(PROVS, key=lambda p: -census.get("cattle", {}).get(p, 0.0)),
        "note": ("Plausibility check on the province ordering only (no pixel validation). The model now "
                 "uses buffalo-share as a feature, so the buffalo-census comparison is CIRCULAR and shown "
                 "for reference only; the independent check is vs CATTLE census province shares."),
    }
    with open(METRICS, "w") as f:
        json.dump(metrics, f, indent=2)
    print("Livestock desk-validation (province ordering vs PBS census):")
    print("  Spearman rho vs CATTLE (independent) %s | vs buffalo (circular ref) %s | model order: %s"
          % (metrics["spearman_vs_cattle"], metrics["spearman_vs_buffalo_circular"], metrics["model_order"]))
    return metrics


def _r(v, nd=3):
    try:
        return round(float(v), nd)
    except (TypeError, ValueError):
        return ""


if __name__ == "__main__":
    import sys as _sys
    if "--check" in _sys.argv[1:]:
        # re-derive into a temporary directory and compare; nothing in the tree is written
        from pkinv.core.checkmode import compare_only
        _sys.exit(compare_only(globals(), ("WORKSHEET", "METRICS"), run))
    run()
