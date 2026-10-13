#!/usr/bin/env python3
"""The reference-year crop split, measured against the proxy it replaced (rc47 Wave 1).

For four releases the FY2023-24 within-province crop split came from the MapSPAM/cropland
proxy family (outputs/district_totals_2024.csv) while the eight other years read the PBS
district panel - and a docstring claimed the two were "asserted equal" when no such
assertion existed and the shares differed by up to 0.26 in a district. rc47 Wave 1 put
the reference year on the panel like every other year; this product is the measured
record of what that changed: per crop category and canonical shape, the within-province
share under the proxy product and under the PBS panel, side by side.

The proxy product is NOT retired - it remains the within-district raster source and the
livestock panel - and this table is why a reader can see exactly where the statistical
record and the satellite proxy disagree about where a province's crop activity sits.

Usage:  python3 scripts/build_agri_panel_divergence.py [--check]
Writes: outputs/agri_reference_panel_divergence.csv
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core import adm2  # noqa: E402
from pkinv.core.io import read_rows, write_or_check  # noqa: E402
from pkinv.paths import DATA, OUTPUTS  # noqa: E402

PANEL = asset_path(DATA, "activity", "agriculture", "crop_district_panel.csv")
PRODUCT = asset_path(OUTPUTS, "district_totals_2024.csv")
OUT = asset_path(OUTPUTS, "agri_reference_panel_divergence.csv")
REFERENCE = "2023-24"
CATEGORIES = {"Rice cultivation": ("rice",),
              "Managed soils": ("maize", "rice", "sugarcane", "wheat", "cotton"),
              "Urea application": ("maize", "rice", "sugarcane", "wheat", "cotton"),
              "Field burning of residues": ("maize", "rice", "sugarcane", "wheat", "cotton")}
FIELDS = ("category", "province", "shape_id", "shape_name", "product_share",
          "panel_share", "abs_delta", "note")


def _to_shape(mass_by_name):
    """{(province, shape_id): mass} from {canonical-or-display name: mass}."""
    canonical = adm2.load_canonical()
    out = defaultdict(float)
    names = {}
    for name, value in mass_by_name.items():
        unit = canonical[adm2.resolve(name)]
        if not unit["shape_id"]:
            # Larkana / Cholistan / the Other residual: no polygon, no share to compare
            continue
        key = (unit["province_id"], unit["shape_id"])
        out[key] += value
        names[key] = unit.get("shape_name") or unit["canonical_name"]
    return out, names


def _shares(by_shape):
    prov_tot = defaultdict(float)
    for (prov, _sid), v in by_shape.items():
        prov_tot[prov] += v
    return {k: (v / prov_tot[k[0]] if prov_tot[k[0]] > 0 else 0.0)
            for k, v in by_shape.items()}


def build():
    product = defaultdict(lambda: defaultdict(float))
    for r in read_rows(PRODUCT):
        product[r["category"]][r["district"]] += float(r["co2e_Mt_AR5"])
    panel = defaultdict(lambda: defaultdict(float))
    canonical_name = {u["adm2_id"]: u["canonical_name"]
                      for u in adm2.load_canonical().values()}
    for r in read_rows(PANEL):
        if r["period_id"] != REFERENCE or r["qa_flag"] == "excluded_corrupt":
            continue
        if not r["adm2_id"]:
            continue
        panel[r["crop"]][canonical_name[r["adm2_id"]]] += float(r["area_kha"])
    rows = []
    for category, crops in CATEGORIES.items():
        merged = defaultdict(float)
        for crop in crops:
            for name, area in panel[crop].items():
                merged[name] += area
        prod_shape, names_a = _to_shape(product[category])
        panel_shape, names_b = _to_shape(dict(merged))
        names = {**names_a, **names_b}
        p_share, q_share = _shares(prod_shape), _shares(panel_shape)
        for key in sorted(set(p_share) | set(q_share)):
            a, b = p_share.get(key, 0.0), q_share.get(key, 0.0)
            if a == 0.0 and b == 0.0:
                continue
            rows.append({
                "category": category, "province": key[0], "shape_id": key[1],
                "shape_name": names[key],
                "product_share": "%.6f" % a, "panel_share": "%.6f" % b,
                "abs_delta": "%.6f" % abs(a - b),
                "note": ("proxy only: the panel places no %s here" % category
                         if b == 0.0 else
                         "panel only: the proxy places no %s here" % category
                         if a == 0.0 else "")})
    rows.sort(key=lambda r: (r["category"], -float(r["abs_delta"])))
    banner = [
        "THE REFERENCE-YEAR CROP SPLIT, PROXY VS PANEL (rc47 Wave 1). Within-province",
        "shares of the FY2023-24 crop categories under the MapSPAM/cropland proxy product",
        "(district_totals_2024.csv, retained as raster source and livestock panel) and the",
        "PBS district crop panel the allocation now reads for every year. Shares are per",
        "canonical SHAPE within province; units without a polygon are excluded from both",
        "sides. Sorted by disagreement, per category. Field burning's rows measure the",
        "FRP-vs-crop-area disagreement that made the allocation decline BOTH panels for",
        "that category: it rides the period's own FIRMS raster alone (grid_cube).",
    ]
    check = "--check" in sys.argv
    write_or_check(OUT, list(FIELDS), rows, check=check, banner=banner,
                   lineterminator="\n")
    worst = rows[0] if rows else None
    print("divergence table: %d rows; worst %s %s |delta| %s"
          % (len(rows), worst["category"], worst["shape_name"], worst["abs_delta"]))


if __name__ == "__main__":
    build()
