"""Which ADM2 polygon contains a point, by ray casting against the canonical frame.

WHY THIS MODULE EXISTS. The district a facility sits in was being answered two ways. The
province boundary audit computed it from the geometry - ray casting the point against
PAK_ADM2.geojson, the same 152-unit frame every spatial product uses. The facility registry
instead read a district STRING supplied by the third-party source beside the coordinates.
When the two disagreed the registry shipped the string.

On 2026-10-05 that shipped a defect a reader could see from the file alone. Global Energy
Monitor gives district "Thatta" for ThalNova, Thar Energy and Engro Powergen Thar, all three
at about 24.81 N, 70.39 E in the Thar coalfield - roughly 250 km from Thatta. The audit had
already computed Tharparkar for all of them, and Thar Coal Block-I 11 km away carried
"Tharparkar" in the same column of the same file. The registry split them: Engro resolved to
Tharparkar because NEPRA's location table happens to list it, and the two GEM-only plants
resolved to Thatta. Three stations about a kilometre apart, two districts.

A coordinate and a district name are not two independent facts about a facility; the name is
a claim ABOUT the coordinate, and this repository already holds the frame that adjudicates it.
So the geometry decides, the source's claim is recorded beside it, and there is one
implementation rather than one per consumer.

Ray casting is kept rather than replaced by a GIS dependency: the frame is a single committed
GeoJSON, the points number in the dozens, and the audit's own results were produced by this
code - swapping the algorithm would change published placements for a reason unrelated to the
defect being fixed.
"""
from __future__ import annotations

import io
import json

from pkinv.assets import asset_path
from pkinv.paths import DATA

GEOJSON = asset_path(DATA, "gis", "PAK_ADM2.geojson")

_POLYGONS = None


def polygons():
    """[(shapeName, polygon rings, bounding box)], loaded once per process."""
    global _POLYGONS
    if _POLYGONS is None:
        with io.open(GEOJSON, encoding="utf-8") as handle:
            gj = json.load(handle)
        out = []
        for ft in gj["features"]:
            g = ft["geometry"]
            polys = [g["coordinates"]] if g["type"] == "Polygon" else g["coordinates"]
            for poly in polys:
                xs = [p[0] for p in poly[0]]
                ys = [p[1] for p in poly[0]]
                out.append((ft["properties"]["shapeName"], poly,
                            (min(xs), min(ys), max(xs), max(ys))))
        _POLYGONS = out
    return _POLYGONS


def in_ring(x, y, ring):
    inside = False
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        if ((y1 > y) != (y2 > y)) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def containing(x, y, polys=None):
    """The shapeName of the ADM2 polygon containing (lon, lat), or "" if none does.

    An empty answer is a real result, not a failure: China Power Hub falls in no polygon at
    all, which is what identified the boundary error rather than a station error. A caller
    must decide what to do with it and must not treat it as "unresolved by accident".
    """
    for name, poly, (x0, y0, x1, y1) in (polys if polys is not None else polygons()):
        if x0 <= x <= x1 and y0 <= y <= y1 and in_ring(x, y, poly[0]):
            if not any(in_ring(x, y, hole) for hole in poly[1:]):
                return name
    return ""
