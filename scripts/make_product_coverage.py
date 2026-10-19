"""The product-coverage matrix: what each module holds, and what actually ships.

The third review asked a question no artifact answered: for each sector, does the
release hold native geometry, what does the cube allocate that sector on, does the
sector publish its own spatial products, and on what basis is it resolved monthly?
The answers existed - scattered across the source-stream ledger, the geometry and
proxy registries, and the outputs directory - which is exactly the state that let
five sector papers describe their spatial coverage inaccurately at once.

Writes:  outputs/pakemis_product_coverage.csv
Usage:   python3 scripts/make_product_coverage.py
"""

from pkinv.assets import asset_path
import csv
import glob
import os
from pkinv.core.io import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = asset_path(ROOT, "outputs")

MODULES = ("agriculture", "power", "transport", "residential", "industry", "ippu",
           "waste", "fugitives", "railways", "aviation")

LABEL = {"agriculture": "Agriculture", "power": "Electricity generation",
         "transport": "Road transport", "residential": "Residential fuel",
         "industry": "Industrial combustion", "ippu": "Cement (IPPU)",
         "waste": "Waste", "fugitives": "Fugitive oil and gas",
         "railways": "Railways", "aviation": "Domestic aviation"}


def _streams():
    return read_rows(asset_path(OUT, 'pakemis_source_streams.csv'), comments=False)


def _own_products(module):
    """Which spatial products the sector itself publishes, from the outputs on disk."""
    found = []
    if glob.glob(asset_path(OUT, "%s*provincial*.csv" % module)):
        found.append("provincial")
    if glob.glob(asset_path(OUT, "%s*district*.csv" % module)) or (
            module == "agriculture"
            and os.path.exists(asset_path(OUT, "district_totals_2024.csv"))):
        found.append("district")
    if module == "agriculture" or glob.glob(
            asset_path(OUT, "%s_gis_*" % module)) or glob.glob(
            asset_path(OUT, "%s_grid_*" % module)):
        found.append("grid")
    return "+".join(found) if found else "none"


def rows():
    streams = _streams()
    out = []
    for module in MODULES:
        mine = [s for s in streams if s["module"] == module]
        total = sum(float(s["emissions_ar5"]) for s in mine)
        geo = sorted({s["geometry_id"].split(":")[0] for s in mine})
        s4 = sum(float(s["emissions_ar5"]) for s in mine
                 if s["geometry_id"] == "S4:no-native-geometry")
        spatial = {}
        for s in mine:
            spatial[s["spatial_class"]] = (spatial.get(s["spatial_class"], 0.0)
                                           + float(s["emissions_ar5"]))
        dominant_sp = max(spatial, key=spatial.get)
        proxies = sorted({s["spatial_profile_id"] for s in mine
                          if s["spatial_profile_id"]})
        temporal = {}
        for s in mine:
            temporal[s["temporal_class"]] = (temporal.get(s["temporal_class"], 0.0)
                                             + float(s["emissions_ar5"]))
        # PUBLISHED AS TE, matching the temporal_evidence_class column every product ships.
        # The source ledger carries the layer's own T-code, and the two are one scale under
        # two names; printing the layer's name in a manuscript beside a CSV that prints the
        # other is the vocabulary split the reviewer found.
        dominant_t = max(temporal, key=temporal.get)
        if dominant_t.startswith("T") and not dominant_t.startswith("TE"):
            dominant_t = "TE" + dominant_t[1:]
        out.append({
            "module": module,
            "native_geometry_kinds": ";".join(geo),
            "s4_no_geometry_share_pct": round(100.0 * s4 / total, 2) if total else 0.0,
            "dominant_spatial_class": dominant_sp,
            "cube_allocation_bases": ";".join(proxies),
            "own_spatial_products": _own_products(module),
            "dominant_temporal_class": dominant_t,
        })
    return out


def main():
    table_rows = rows()
    path = asset_path(OUT, "pakemis_product_coverage.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(table_rows[0]))
        w.writeheader()
        w.writerows(table_rows)
    print("wrote %s" % path)


if __name__ == "__main__":
    main()
