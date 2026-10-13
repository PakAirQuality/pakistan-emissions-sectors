"""The OSM building-footprint fraction: an independent DIAGNOSTIC beside WorldCover.

WHY. The sixth review asked for a built-environment ensemble; the held snapshot's
785,749 building footprints are the one member buildable offline. This raster is a
DIAGNOSTIC, never a stream proxy: OSM building coverage in Pakistan is wildly
non-uniform - metro areas are mapped nearly building-by-building, rural settlements
barely at all - so the surface measures mapping effort as much as built area, and the
comparison table this script also writes is precisely the place that non-uniformity
becomes visible instead of latent.

METHOD. Each footprint's area (EPSG:32642) is assigned to the 0.05-degree cell of its
representative point - buildings are tiny against a ~5.5 km cell, so the
single-cell assignment loses nothing material - and the per-cell sum is divided by
the cell's area to give a fraction. The ADM2 comparison expresses each shape's share
of the national WorldCover built-up mass beside its share of the national OSM
building area; where OSM's share is far below WorldCover's, the mapping is sparse,
not the buildings absent.

Usage:  python3 scripts/build_building_fraction.py [--check]
Writes: data/gis/osm_building_fraction_267x340.npy (+ .txt sidecar)
        outputs/pakemis_builtup_comparison_adm2.csv
"""
import csv
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

ZIP_PATH = asset_path(ROOT, "sources", "OSM", "pakistan-20260809",
                        "pakistan-latest-free.shp.zip")
NPY = asset_path(ROOT, "data", "gis", "osm_building_fraction_267x340.npy")
COMPARISON = asset_path(ROOT, "outputs", "pakemis_builtup_comparison_adm2.csv")
RES = 0.05


def build():
    import geopandas as gpd
    import numpy as np

    from pkinv.core.gis.grid import build_grid

    grid = build_grid()
    minx, miny, maxx, maxy = grid.bounds

    gdf = gpd.read_file("zip://%s!gis_osm_buildings_a_free_1.shp" % ZIP_PATH,
                        columns=["osm_id"])
    areas = gdf.geometry.to_crs("EPSG:32642").area.values
    reps = gdf.geometry.representative_point()
    lon = reps.x.values
    lat = reps.y.values
    col = np.floor((lon - minx) / RES).astype(np.int64)
    row = np.floor((maxy - lat) / RES).astype(np.int64)
    inside = (col >= 0) & (col < grid.width) & (row >= 0) & (row < grid.height)
    building_m2 = np.zeros((grid.height, grid.width), dtype=np.float64)
    np.add.at(building_m2, (row[inside], col[inside]), areas[inside])

    # cell area varies with latitude; a 0.05 deg cell at lat phi is ~ (111.32 km x
    # cos phi) x 111.32 km x RES^2 in km2 -> m2
    lats = maxy - (np.arange(grid.height) + 0.5) * RES
    cell_m2 = (111_320.0 * RES) * (111_320.0 * RES) * np.cos(np.radians(lats))
    fraction = building_m2 / cell_m2[:, None]

    # ADM2 comparison against the WorldCover proxy
    from pkinv.core.gis import cube as cube_core
    builtup = np.load(asset_path(ROOT, "data", "gis",
                                   "proxy_builtup_267x340.npy")).astype(np.float64)
    ids = grid.district_id
    valid = ids >= 0
    wc = np.bincount(ids[valid].ravel().astype(np.int64),
                     weights=builtup[valid].ravel(), minlength=len(grid.districts))
    osm = np.bincount(ids[valid].ravel().astype(np.int64),
                      weights=building_m2[valid].ravel(),
                      minlength=len(grid.districts))
    wc_share = wc / wc.sum()
    osm_share = osm / osm.sum()

    from pkinv.core import adm2 as adm2_core
    canonical = adm2_core.load_canonical()
    name_to_units = {}
    for adm2_id, r in canonical.items():
        name_to_units.setdefault(r["shape_name"], []).append(adm2_id)
    rows = []
    for idx, name in enumerate(grid.districts):
        units = sorted(name_to_units.get(name, []))
        rows.append({
            "adm2_ids": ";".join(units) if units else name,
            "province": grid.district_province[idx],
            "worldcover_builtup_share": round(float(wc_share[idx]), 6),
            "osm_building_share": round(float(osm_share[idx]), 6),
            "share_ratio_osm_over_wc": (round(float(osm_share[idx] / wc_share[idx]), 3)
                                        if wc_share[idx] > 0 else ""),
            "note": "ratio far below 1 marks sparse OSM mapping, not absent "
                    "buildings; the comparison is the diagnostic"})
    rows.sort(key=lambda r: r["adm2_ids"])
    return fraction.astype(np.float32), rows, int(inside.sum()), len(gdf)


def _render(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(check=False):
    import numpy as np
    fraction, rows, inside_count, total_count = build()
    sidecar = ("OSM building-footprint fraction per 0.05 deg cell (%d footprints, "
               "Geofabrik snapshot 2026-08-06). DIAGNOSTIC ONLY - measures mapping "
               "effort as much as built area; never a stream proxy. See "
               "PROXY_SOURCES.md and pakemis_builtup_comparison_adm2.csv\n"
               % total_count)
    csv_text = _render(rows)
    if check:
        held = np.load(NPY)
        if not np.allclose(held, fraction, rtol=0, atol=1e-7):
            print("osm_building_fraction stale; rerun")
            return 1
        if open(COMPARISON, encoding="utf-8").read() != csv_text:
            print("builtup comparison stale; rerun")
            return 1
        # The coverage contract (rc64): name every product compared above, so the held
        # registry can be held to it. See tests/test_held_product_freshness.py.
        for covered in ("data/gis/osm_building_fraction_267x340.npy",
                        "outputs/pakemis_builtup_comparison_adm2.csv"):
            print("checked: %s" % covered)
        print("building fraction products are current.")
        return 0
    np.save(NPY, fraction)
    open(NPY + ".txt", "w", encoding="utf-8").write(sidecar)
    open(COMPARISON, "w", encoding="utf-8").write(csv_text)
    print("wrote building fraction (%d of %d footprints on-grid) + ADM2 comparison "
          "(%d rows)" % (inside_count, total_count, len(rows)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
