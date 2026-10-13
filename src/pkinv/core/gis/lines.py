"""Length-proportional rasterisation of line geometries onto the inventory grid.

WHY NOT rasterio.features.rasterize. Burning lines with all_touched=True gives a cell the
line barely clips the same weight as a cell it crosses corner to corner, and with
all_touched=False drops cells entirely; neither conserves length, and a mass-conserving
allocation needs the raster weight of a route to BE its length. So lines are densified and
binned: each segment between consecutive vertices contributes its length (times the
record's weight) to the cell its midpoint falls in. The burned TOTAL equals the line's
length exactly at any step; what the step controls is which side of a cell edge a
boundary segment lands on, and at RES/8 (~700 m) that jitter is up to ~6 percent of a
single cell traverse - it cancels at every aggregation actually used (corridor, district,
province), and a test pins both properties: exact total conservation, and bounded per-cell
movement under step halving.

Everything downstream renormalises within masks, so absolute units of the weights do not
matter; only their proportions do.
"""
import math

import numpy as np

from pkinv.core.gis.grid import RES


def _densify(coords, step_deg):
    """Vertices of a polyline with no gap longer than step_deg (in degrees)."""
    out = [coords[0]]
    for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]):
        d = math.hypot(x1 - x0, y1 - y0)
        n = max(1, int(math.ceil(d / step_deg)))
        for i in range(1, n + 1):
            out.append((x0 + (x1 - x0) * i / n, y0 + (y1 - y0) * i / n))
    return out


def _km(x0, y0, x1, y1):
    """Segment length in km on a sphere - adequate at these scales."""
    lat = math.radians((y0 + y1) / 2.0)
    dx = (x1 - x0) * 111.320 * math.cos(lat)
    dy = (y1 - y0) * 110.574
    return math.hypot(dx, dy)


def burn_lines(grid, records, step_deg=RES / 8.0):
    """Accumulate weighted line length onto the grid.

    records: iterable of (coords, weight) where coords is a sequence of (lon, lat)
    vertices (a LineString's coords, or each part of a MultiLineString) and weight is any
    per-km intensity. Returns float64 (height, width): each cell holds
    sum(segment_km x weight) for sub-segments whose midpoint falls inside it.
    """
    arr = np.zeros((grid.height, grid.width), dtype="float64")
    inv = ~grid.transform
    for coords, weight in records:
        pts = _densify(list(coords), step_deg)
        for (x0, y0), (x1, y1) in zip(pts[:-1], pts[1:]):
            mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
            c, r = inv * (mx, my)
            r, c = int(r), int(c)
            if 0 <= r < grid.height and 0 <= c < grid.width:
                arr[r, c] += _km(x0, y0, x1, y1) * weight
    return arr


def burn_points(grid, records):
    """(lon, lat, weight) records accumulated onto the grid - yards, stations, plants."""
    arr = np.zeros((grid.height, grid.width), dtype="float64")
    inv = ~grid.transform
    for lon, lat, weight in records:
        c, r = inv * (lon, lat)
        r, c = int(r), int(c)
        if 0 <= r < grid.height and 0 <= c < grid.width:
            arr[r, c] += weight
    return arr
