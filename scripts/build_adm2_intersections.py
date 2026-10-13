"""The fractional cell x ADM2 intersection table (rc32, the eighteenth review).

WHAT THIS REPLACES, WITHOUT DELETING IT. The grid's cell->district assignment is
a rasterized int16 label with all_touched=True: every boundary cell is claimed
by each polygon that touches it and the tie is broken by rasterization order -
alphabetical-last-wins, an arbitrary rule at ~5.5 km cells over 152 districts.
This table computes the EXACT area fraction of every grid cell inside every
ADM2 polygon (equal-area projection), so a boundary cell can be split among its
claimants instead of donated whole to one of them. The label array survives for
the S-class derivation and for any reader of the old path until the two are
proven equal in aggregate; the marginals consume the fractions.

Cells outside every polygon (sea, across borders) appear with shape_id
``OUTSIDE`` and their fraction - the ~2 percent the ADM2 conservation test
tolerates becomes an explicit, sum-checked row instead of a bincount key of -1.

Slow once (exact polygon-cell intersection over 90,780 cells x 152 polygons via
a spatial index), cached as a committed artifact like the proxy caches.

Usage:  python3 scripts/build_adm2_intersections.py
Writes: data/gis/adm2_intersections_267x340.csv (+ .txt provenance sidecar)
"""

from pkinv.assets import asset_path
import csv
import os

import geopandas as gpd
import numpy as np
from shapely.geometry import box

from pkinv.core.gis.grid import ADM2_PATH, build_grid
from pkinv.paths import ROOT

OUT = asset_path(ROOT, "data", "gis", "adm2_intersections_267x340.csv")


def main():
    grid = build_grid()
    gdf = gpd.read_file(ADM2_PATH).to_crs("EPSG:4326")
    name_field = "shapeName" if "shapeName" in gdf.columns else "ADM2_NAME"
    id_field = "shapeID" if "shapeID" in gdf.columns else name_field
    # equal-area for honest fractions; Pakistan sits well inside the band
    ea = "ESRI:54034"    # World Cylindrical Equal Area
    gdf_ea = gdf.to_crs(ea)
    sindex = gdf_ea.sindex
    t = grid.transform
    rows = []
    for r in range(grid.height):
        for c in range(grid.width):
            x0, y0 = t * (c, r + 1)
            x1, y1 = t * (c + 1, r)
            cell = gpd.GeoSeries([box(x0, y0, x1, y1)], crs="EPSG:4326").to_crs(ea)[0]
            cell_area = cell.area
            hits = list(sindex.intersection(cell.bounds))
            claimed = 0.0
            for i in hits:
                geom = gdf_ea.geometry.iloc[i]
                inter = cell.intersection(geom)
                if inter.is_empty:
                    continue
                frac = inter.area / cell_area
                if frac < 1e-9:
                    continue
                rows.append({"row": r, "col": c,
                             "shape_id": str(gdf[id_field].iloc[i]),
                             "shape_name": str(gdf[name_field].iloc[i]),
                             "area_fraction": "%.9f" % frac})
                claimed += frac
            outside = 1.0 - claimed
            if outside > 1e-6:
                rows.append({"row": r, "col": c, "shape_id": "OUTSIDE",
                             "shape_name": "", "area_fraction": "%.9f" % outside})
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        f.write("# Exact cell x ADM2 area fractions on the 0.05-degree grid "
                "(equal-area ESRI:54034); OUTSIDE rows make the off-polygon "
                "remainder explicit. Built once by scripts/build_adm2_intersections.py "
                "and committed like the proxy caches.\n")
        w = csv.DictWriter(f, fieldnames=["row", "col", "shape_id", "shape_name",
                                          "area_fraction"])
        w.writeheader()
        w.writerows(rows)
    with open(OUT + ".txt", "w", encoding="utf-8") as f:
        f.write("adm2_intersections_267x340.csv: exact fractional cell-in-polygon "
                "areas for the %dx%d 0.05-degree grid against %s (%d polygons), "
                "computed in ESRI:54034; every cell's fractions (including OUTSIDE) "
                "sum to 1 within 1e-6, asserted by tests/test_adm2_fractions.py.\n"
                % (grid.height, grid.width, os.path.basename(ADM2_PATH), len(gdf)))
    print("intersections -> %s (%d rows)" % (OUT, len(rows)))


if __name__ == "__main__":
    main()
