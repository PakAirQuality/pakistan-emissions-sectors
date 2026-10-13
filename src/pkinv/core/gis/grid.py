"""National grid for Pakistan + province rasterization (Phase 4).

Defines a regular 0.05-degree lon/lat grid over Pakistan and tags each cell to one of
the five inventory provinces (Punjab, Sindh, Khyber Pakhtunkhwa, Balochistan, Other),
matching the Phase-3 control totals. Other = Gilgit-Baltistan + Azad Kashmir + ICT.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import os

import numpy as np
import geopandas as gpd
import rasterio
from rasterio import features
import math

from rasterio.transform import from_origin

from pkinv.paths import ROOT

DATA_GIS = asset_path(ROOT, "data", "gis")
ADM1_PATH = asset_path(DATA_GIS, "PAK_ADM1.geojson")
ADM2_PATH = asset_path(DATA_GIS, "PAK_ADM2.geojson")   # FAO GAUL L2 districts (optional)
RES = 0.05  # degrees (~5 km)

# THE LATTICE IS FROZEN (rc45). Until now the extent was whatever data/gis/PAK_ADM1.geojson's
# total_bounds implied, snapped outward to a multiple of RES and recomputed on every call. That
# is a published coordinate system derived from an input file: replace the boundary with a
# differently-generalised one and every cell silently renumbers, every cached raster's
# 267x340 filename stops matching, and a nine-year product's cell ids stop meaning what the
# previous release said they meant.
#
# A changed boundary must produce a new MASK version, not a new lattice. So the lattice is
# declared here and build_grid asserts against it; the boundary file may be revised, and the
# day it moves the extent this fails loudly instead of shifting the grid under a published
# product.
GRID_SPEC_ID = "pk_0p05_epsg4326_v1"
GRID_SPEC = {
    "grid_spec_id": GRID_SPEC_ID,
    "crs": "EPSG:4326",
    "west": 60.85, "east": 77.85, "south": 23.70, "north": 37.05,
    "resolution_deg": RES,
    "width": 340, "height": 267, "cells": 90780,
    # row 0 is the NORTHERNMOST row; cell_id = row * width + column
    "row_zero": "north", "cell_id": "row * width + column",
}


def pakistan_fraction(grid):
    """The share of each cell that is inside a Pakistani district, from exact intersections.

    WHY THIS IS NOT grid.province_id >= 0. The label rasters are rasterised with
    all_touched=True, so a cell the boundary merely clips is wholly "inside": summing their
    areas gives 900,261 km2 against a country of about 881,913. The exact partition in
    data/gis/adm2_intersections_267x340.csv gives 877,057 km2, which is 0.55 percent out and
    that residual is geoBoundaries' own generalisation rather than the grid's.

    The allocator does NOT use this and should not: cube._fraction_matrix deliberately
    renormalises the OUTSIDE share away, because a coastal cell's field value is land activity
    and splitting it to the sea would dilute a known facility into the water. This is a
    PUBLISHED variable so a consumer can turn Gg per cell into a flux per square kilometre of
    land, which is the one thing they cannot reconstruct from the mask.
    """
    import csv as _csv
    import numpy as np
    out = np.zeros((grid.height, grid.width), dtype=np.float64)
    path = asset_path(DATA_GIS, "adm2_intersections_%dx%d.csv" % (grid.height, grid.width))
    for row in _activity_rows(path, comments=True):
        if row["shape_id"] == "OUTSIDE":
            continue
        out[int(row["row"]), int(row["col"])] += float(row["area_fraction"])
    return np.clip(out, 0.0, 1.0)


def cell_area_km2(grid):
    """The geodesic area of every cell, km^2, as an array shaped like the grid.

    A 0.05-degree cell is not a fixed area: on the sphere it is R^2 . dlon . (sin(lat_top) -
    sin(lat_bottom)), which over Pakistan runs from 28.298 km2 at the southern edge (23.75 N)
    to 24.678 km2 at the northern (37.05 N) - a 14.7 percent gradient south to north. Anything
    that treats a cell as a unit of area is therefore treating a Karachi cell and a Gilgit cell
    as equal when they are not.

    R is the WGS84 authalic radius, the sphere with the ellipsoid's surface area, which is the
    right sphere for an area and is what ESRI:54034 - the projection build_adm2_intersections
    already computes exact cell-district overlaps in - is built on.
    """
    import numpy as np
    radius_km = 6371.0072
    dlon = math.radians(RES)
    top = grid.bounds[3]
    lat_top = np.array([top - i * RES for i in range(grid.height)])
    row_area = (radius_km * radius_km * dlon
                * (np.sin(np.radians(lat_top)) - np.sin(np.radians(lat_top - RES))))
    return np.repeat(row_area[:, None], grid.width, axis=1)

# Re-exported rather than redefined. Both `grid.PROVINCES` and `downscale.PROVINCES` are
# load-bearing names across ~35 import sites, so the single definition lives in
# core.geography and both spellings keep resolving to it.
from pkinv.core.geography import (  # noqa: E402,F401
    PROVINCES, PROV_ID, ADM1_TO_PROVINCE, GAUL_ADM1_TO_PROVINCE)


class Grid:
    def __init__(self, transform, width, height, bounds, province_id,
                 district_id=None, districts=None, district_province=None,
                 adm1_id=None, adm1_names=None):
        self.transform = transform
        self.width = width
        self.height = height
        self.bounds = bounds            # (minx, miny, maxx, maxy)
        self.province_id = province_id  # (H, W) int8, -1 outside country
        self.district_id = district_id  # (H, W) int16, -1 outside; None if no ADM2 file
        self.districts = districts or []                # index -> district name
        self.district_province = district_province or []  # index -> inventory province
        # The ADM1 unit each cell belongs to, kept beside the province id: "Other" is a
        # reporting group of three territories and a share row may be entitled to only
        # some of them (core.geography.other_membership).
        self.adm1_id = adm1_id                  # (H, W) int8, -1 outside; None if not built
        self.adm1_names = adm1_names or []      # index -> ADM1 name as the boundary file spells it
        self.crs = "EPSG:4326"

    def province_mask(self, province):
        return self.province_id == PROV_ID[province]

    def members_mask(self, province, members):
        """The province's cells restricted to the named ADM1 units.

        `members` is what core.geography.members_of() returns for the share row. An empty
        tuple, an unbuilt adm1 raster or a name the boundary file does not spell means the
        whole province - never a silently empty mask, which would drop mass.
        """
        mask = self.province_mask(province)
        if not members or self.adm1_id is None:
            return mask
        idx = [i for i, n in enumerate(self.adm1_names) if n in members]
        if not idx:
            return mask
        import numpy as _np
        keep = _np.isin(self.adm1_id, _np.array(idx, dtype=self.adm1_id.dtype))
        restricted = mask & keep
        return restricted if restricted.any() else mask

    def district_mask(self, did):
        return self.district_id == did

    def districts_in(self, province):
        return [i for i, p in enumerate(self.district_province) if p == province]


def _name_field(gdf):
    for k in gdf.columns:
        if k.lower() in ("shapename", "name") or "NAME" in k.upper():
            return k
    raise KeyError("no name field in ADM1 geojson")


def build_grid(res=RES, adm1_path=ADM1_PATH):
    gdf = gpd.read_file(adm1_path).to_crs("EPSG:4326")
    name_f = _name_field(gdf)
    gdf["prov"] = gdf[name_f].map(ADM1_TO_PROVINCE).fillna("Other")

    minx, miny, maxx, maxy = gdf.total_bounds
    # snap bounds outward to a multiple of res for clean alignment
    minx = np.floor(minx / res) * res
    miny = np.floor(miny / res) * res
    maxx = np.ceil(maxx / res) * res
    maxy = np.ceil(maxy / res) * res
    width = int(round((maxx - minx) / res))
    height = int(round((maxy - miny) / res))
    # THE ASSERTION, not a derivation. The four bounds and the two counts are the published
    # coordinate system; a boundary revision that moves any of them is a new grid and must be
    # declared as one rather than discovered by a consumer whose cell ids stopped matching.
    if res == RES:
        observed = {"west": round(minx, 10), "east": round(maxx, 10),
                    "south": round(miny, 10), "north": round(maxy, 10),
                    "width": width, "height": height}
        expected = {k: GRID_SPEC[k] for k in observed}
        if observed != expected:
            raise ValueError(
                "%s is frozen and this boundary file does not fit it: %s against %s. A "
                "revised boundary makes a new MASK version, not a new lattice - if the extent "
                "genuinely must move, declare a new grid_spec_id and re-cut every cached "
                "raster and the intersection table with it."
                % (GRID_SPEC_ID, observed, expected))
    transform = from_origin(minx, maxy, res, res)

    shapes = [(geom, PROV_ID[p]) for geom, p in zip(gdf.geometry, gdf["prov"])]
    province_id = features.rasterize(
        shapes, out_shape=(height, width), transform=transform,
        fill=-1, all_touched=True, dtype="int32").astype(np.int8)

    # the same rasterisation keyed on the ADM1 unit itself, so a share row that names only
    # part of the residual unit can be honoured (Grid.members_mask)
    adm1_names = [str(n) for n in gdf[name_f]]
    adm1_id = features.rasterize(
        [(geom, i) for i, geom in enumerate(gdf.geometry)],
        out_shape=(height, width), transform=transform,
        fill=-1, all_touched=True, dtype="int32").astype(np.int8)

    district_id, districts, district_province = _rasterize_districts(
        transform, height, width, province_id=province_id)
    return Grid(transform, width, height, (minx, miny, maxx, maxy), province_id,
                district_id, districts, district_province, adm1_id, adm1_names)


_DISTRICT_TREE = {}


def district_index_at(points, adm2_path=ADM2_PATH):
    """Exact district index for each (lon, lat), or -1 outside every district.

    THE CELL IS NOT THE ANSWER FOR A POINT (rc45). A facility's mass is burned into its
    containing cell, and the ADM2 leg then splits that cell by its district area fractions -
    so a plant near a boundary is apportioned by the geometry of its CELL rather than by the
    district it is actually in. Measured over the facility register: 2,063 of 12,529 located
    facilities sit in a split cell, and for those a mean 29 percent of the mass is attributed
    to a district the facility is not in; 203 keep under a tenth of their own mass and several
    keep none of it at all.

    The raster is right - a point does belong in its cell, and the grid product is a raster.
    It is the district PROJECTION that has to come from the point.

    The index is the position in the ADM2 file sorted by name, which is exactly how
    _rasterize_districts numbers grid.districts; the two orderings are the same fact and this
    function reads the same file the same way rather than mirroring the rule.
    """
    import geopandas as gpd
    from shapely.geometry import Point
    from shapely import STRtree
    key = os.path.abspath(adm2_path)
    if key not in _DISTRICT_TREE:
        gdf = gpd.read_file(adm2_path).to_crs("EPSG:4326")
        name_field = "ADM2_NAME" if "ADM2_NAME" in gdf.columns else _name_field(gdf)
        gdf = gdf.sort_values(name_field).reset_index(drop=True)
        geoms = list(gdf.geometry)
        _DISTRICT_TREE[key] = (STRtree(geoms), geoms)
    tree, geoms = _DISTRICT_TREE[key]
    out = []
    for lon, lat in points:
        point = Point(lon, lat)
        found = -1
        for candidate in tree.query(point):
            index = int(candidate)
            if geoms[index].covers(point):
                found = index
                break
        out.append(found)
    return out


def _rasterize_districts(transform, height, width, adm2_path=ADM2_PATH,
                         province_id=None):
    """Rasterize ADM2 boundaries and attach them to inventory provinces.

    FAO/GAUL files carry ``ADM2_NAME`` and ``ADM1_NAME``.  Public-domain
    geoBoundaries files carry ``shapeName`` only, so their province is inferred
    from the majority of each district's cells in the already-rasterized ADM1
    control.  Supporting both schemas keeps the spatial engine independent of a
    particular boundary distributor.
    """
    if not os.path.exists(adm2_path):
        return None, [], []
    gdf = gpd.read_file(adm2_path).to_crs("EPSG:4326")
    name_field = "ADM2_NAME" if "ADM2_NAME" in gdf.columns else _name_field(gdf)
    gdf = gdf.sort_values(name_field).reset_index(drop=True)
    districts = list(gdf[name_field])
    shapes = [(geom, i) for i, geom in enumerate(gdf.geometry)]
    district_id = features.rasterize(
        shapes, out_shape=(height, width), transform=transform,
        fill=-1, all_touched=True, dtype="int32").astype(np.int16)
    if "ADM1_NAME" in gdf.columns:
        district_province = [GAUL_ADM1_TO_PROVINCE.get(a, "Other")
                             for a in gdf["ADM1_NAME"]]
    elif province_id is not None:
        province_for_id = {value: name for name, value in PROV_ID.items()}
        district_province = []
        for index in range(len(districts)):
            values = province_id[district_id == index]
            values = values[values >= 0]
            if values.size:
                counts = np.bincount(values.astype(int), minlength=len(PROV_ID))
                district_province.append(province_for_id[int(np.argmax(counts))])
            else:
                district_province.append("Other")
    else:
        district_province = ["Other"] * len(districts)
    return district_id, districts, district_province


def cell_lonlat(grid):
    """Return (lon, lat) 2D arrays of cell centres."""
    minx, miny, maxx, maxy = grid.bounds
    lons = minx + (np.arange(grid.width) + 0.5) * RES
    lats = maxy - (np.arange(grid.height) + 0.5) * RES
    return np.meshgrid(lons, lats)


if __name__ == "__main__":
    g = build_grid()
    print("grid %dx%d  bounds %s" % (g.width, g.height, tuple(round(b, 2) for b in g.bounds)))
    for p in PROVINCES:
        print("  %-20s %6d cells" % (p, int(g.province_mask(p).sum())))
