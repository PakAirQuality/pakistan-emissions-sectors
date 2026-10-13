"""One attribution ladder for the FIRMS field-burning detections - temporal and spatial alike.

rc42 (the twentieth review's S-3). The temporal profile of residue burning attributed a
detection only if it fell in a crop's FAO burning window, inside Pakistan, on cropland and
away from a registered kiln (52,428 of the year's 169,657), and weighted it by FRP; the
spatial raster kept every in-Pakistan detection (65,910), weighted each by FRP + 1, and so
put 17.35 % of its weight - 0.116 of the 0.670 Mt stream - on detections the temporal
method had rejected: kiln plumes and non-cropland fires. Two pipelines, one event table,
two answers. The ladder lives here now and both call it; the counts they publish are the
same counts.

The ladder, strongest first: inside the crop burning window (a callable the caller
supplies, so the fetch scope and the attribution scope stay one set of dates); inside
Pakistan and on cropland, read from the grid's own district raster and the WorldCover
cropland proxy the spatial allocation uses; not within KILN_EXCLUSION_DEG of a registered
kiln. What fails a rung is counted, never forced.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA

KILN_EXCLUSION_DEG = 0.01
FACILITY_REGISTRY = asset_path(DATA, "facility_registry.csv")
FIRMS_FIRE = asset_path(DATA, "gis", "manual", "firms_fire.csv")
CROPLAND = asset_path(DATA, "gis", "proxy_cropland_267x340.npy")
COUNTS = ("detections_in_year", "out_of_window", "outside_pakistan", "near_kiln",
          "off_cropland", "attributed")

_kiln_bins_cache = None
_cropland_cache = None


def kiln_bins():
    global _kiln_bins_cache
    if _kiln_bins_cache is None:
        bins = {}
        for r in _activity_rows(FACILITY_REGISTRY, comments=True):
            if "kiln" not in r["facility_id"].lower() or not r["latitude"]:
                continue
            lat, lon = float(r["latitude"]), float(r["longitude"])
            key = (round(lat / KILN_EXCLUSION_DEG), round(lon / KILN_EXCLUSION_DEG))
            bins.setdefault(key, []).append((lat, lon))
        _kiln_bins_cache = bins
    return _kiln_bins_cache


def near_kiln(lat, lon):
    bins = kiln_bins()
    base = (round(lat / KILN_EXCLUSION_DEG), round(lon / KILN_EXCLUSION_DEG))
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            for klat, klon in bins.get((base[0] + dy, base[1] + dx), ()):
                if abs(klat - lat) < KILN_EXCLUSION_DEG and abs(klon - lon) < KILN_EXCLUSION_DEG:
                    return True
    return False


def _cropland():
    global _cropland_cache
    if _cropland_cache is None:
        import numpy as np
        from pkinv.core.gis.grid import RES, build_grid
        grid = build_grid()
        raster = np.load(CROPLAND)
        _cropland_cache = (grid, raster, RES)
    return _cropland_cache


def cell_state(lat, lon):
    """"outside_pakistan" | "cropland" | "non_cropland" for the cell under a point, and the
    (row, col) of that cell on the inventory grid (None outside)."""
    grid, raster, res = _cropland()
    minx, _miny, _maxx, maxy = grid.bounds
    row = int((maxy - lat) / res)
    col = int((lon - minx) / res)
    if not (0 <= row < raster.shape[0] and 0 <= col < raster.shape[1]):
        return "outside_pakistan", None
    if grid.district_id[row, col] < 0:
        return "outside_pakistan", None
    return ("cropland" if raster[row, col] > 0 else "non_cropland"), (row, col)


def attribute(fy_start, in_window):
    """([(row, col, frp, acq_month_key)], counts) for the fiscal year starting 1 July fy_start.

    `in_window(date)` says whether a detection date falls inside a crop's burning window;
    the caller derives it from burn_windows so the fetch scope and the attribution scope
    are the same dates. Weight is bare FRP (fire radiative power) - the same weight on the
    temporal and the spatial side; a zero-FRP detection carries no weight on either.
    """
    import datetime
    hits = []
    counts = {k: 0 for k in COUNTS}
    for r in _activity_rows(FIRMS_FIRE, comments=False):
        year, month = int(r["acq_date"][:4]), int(r["acq_date"][5:7])
        fy = year if month >= 7 else year - 1
        if fy != fy_start:
            continue
        counts["detections_in_year"] += 1
        when = datetime.date(year, month, int(r["acq_date"][8:10]))
        if not in_window(when):
            counts["out_of_window"] += 1
            continue
        lat, lon = float(r["latitude"]), float(r["longitude"])
        state, cell = cell_state(lat, lon)
        if state == "outside_pakistan":
            counts["outside_pakistan"] += 1
            continue
        if near_kiln(lat, lon):
            counts["near_kiln"] += 1
            continue
        if state == "non_cropland":
            counts["off_cropland"] += 1
            continue
        counts["attributed"] += 1
        hits.append((cell[0], cell[1], float(r["frp"] or 0.0), "%d%02d" % (year, month)))
    return hits, counts
