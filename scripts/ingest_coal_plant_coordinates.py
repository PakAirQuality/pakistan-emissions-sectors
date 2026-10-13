#!/usr/bin/env python3
"""Coordinates for the FY2023-24 coal grid fleet, from GEM corroborated by Climate TRACE (rc42).

WHY. rc41's cube placed 34.71 Mt of the 38.46 Mt coal grid stream - 90 percent - on the
Sindh and Balochistan built-up rasters, because the only coordinate table the dispatch reads
(data/activity/power/plant_coordinates.csv) located one of the eight FY2023-24 coal stations.
The other seven are in two tables this repository already held: the Global Energy Monitor
coal tracker extract (data/activity/power/gem_coal_pak.csv, location accuracy `exact`) and
the Climate TRACE power assets (climatetrace_power_assets_pak.csv). Neither reached the
dispatch: the grid-coordinate ingest gates candidates on the NEPRA town list, and three
Thar stations have no town in it. The twentieth review named this as the largest spatial
misrepresentation in the release; no new collection was needed.

THE JOIN IS EXPLICIT, NOT TOKENISED. The eight ledger names map to eight GEM plant names in
ALIASES below, written out by hand from the two tables - a token join was measured and
refused in rc41 ("China Power Hub" binds to "Hub Power"). Two gates before a row is written:
the ADM1 polygon of the province the point lands in must be a province of Pakistan (the
grid's own province raster decides), and Climate TRACE's coordinate for the same station
must agree with GEM's within AGREEMENT_KM. The dispatch (grid_cube.grid_plant_points) reads
plant_coordinates.csv first and this table for the ledger keys still unlocated, so the
existing corroborated points are never overridden.

Deterministic; --check re-derives and diffs (write_or_check discipline). Both inputs ship
with the package, so this re-derives everywhere.

Usage:  python3 scripts/ingest_coal_plant_coordinates.py [--check]
Writes: data/activity/power/coal_plant_coordinates.csv
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows, write_or_check  # noqa: E402
from pkinv.paths import DATA, ROOT  # noqa: E402

GEM = asset_path(DATA, "activity", "power", "gem_coal_pak.csv")
TRACE = asset_path(DATA, "activity", "power", "climatetrace_power_assets_pak.csv")
LEDGER = asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv")
OUT = asset_path(DATA, "activity", "power", "coal_plant_coordinates.csv")
FIELDS = ("plant", "latitude", "longitude", "gem_plant", "gem_location_id", "gem_accuracy",
          "gem_district", "climatetrace_name", "agreement_km", "raster_province",
          "sources", "note")
AGREEMENT_KM = 5.0
# the plant-fuel ledger's FY2023-24 coal station names -> GEM's plant names, by hand
ALIASES = {
    "China Power Hub": "Hubco power station",
    "Engro Powergen Thar": "Thar Block II power station",
    "Huaneng Shandong Ruyi (Sahiwal Imported Coal)": "Sahiwal power station",
    "Lucky Electric": "Port Qasim Lucky power station",
    "Port Qasim Electric Power": "Port Qasim EPC power station",
    "ThalNova": "ThalNova power station",
    "Thar Coal Block-I": "Thar Block I power station",
    "Thar Energy": "Thar Energy Limited power station",
}


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def build():
    from pkinv.core.geography import PROVINCES
    from pkinv.core.gis.grid import build_grid
    grid = build_grid()
    ledger = sorted({r["plant"] for r in read_rows(LEDGER, comments=False)
                     if r["fiscal_year"] == "2023" and r["fuel"] == "Coal"})
    unmapped = [p for p in ledger if p not in ALIASES]
    if unmapped:
        raise SystemExit("FY2023-24 coal stations with no GEM alias: %s" % unmapped)
    gem = {}
    district_key = None
    for r in read_rows(GEM, comments=False):
        if district_key is None:
            district_key = next(k for k in r if k.startswith("Major area"))
        if r["Status"] != "operating" or r["Location accuracy"] != "exact":
            continue
        gem.setdefault(r["Plant name"], r)          # units share the plant's location
    trace = {r["name"]: r for r in read_rows(TRACE) if "coal" in r.get("asset_type", "")}
    rows = []
    for plant in ledger:
        gem_name = ALIASES[plant]
        g = gem.get(gem_name)
        if g is None:
            raise SystemExit("%s -> %r: not an operating, exactly located GEM plant" % (plant, gem_name))
        lat, lon = float(g["Latitude"]), float(g["Longitude"])
        t = trace.get(gem_name)
        if t is None:
            raise SystemExit("%s -> %r: no Climate TRACE coal asset of that name to corroborate" % (plant, gem_name))
        km = haversine_km((lat, lon), (float(t["lat"]), float(t["lon"])))
        if km > AGREEMENT_KM:
            raise SystemExit("%s: GEM and Climate TRACE disagree by %.1f km" % (plant, km))
        col, row_i = (~grid.transform) * (lon, lat)
        row_i, col = int(row_i), int(col)
        pid = int(grid.province_id[row_i, col]) if (0 <= row_i < grid.height and 0 <= col < grid.width) else -1
        if not (0 <= pid < len(PROVINCES)):
            raise SystemExit("%s: the point (%.5f, %.5f) is outside every province" % (plant, lat, lon))
        rows.append({"plant": plant, "latitude": "%.6f" % lat, "longitude": "%.6f" % lon,
                     "gem_plant": gem_name, "gem_location_id": g["GEM location ID"],
                     "gem_accuracy": g["Location accuracy"], "gem_district": g[district_key].strip(),
                     "climatetrace_name": t["name"],
                     "agreement_km": "%.2f" % km, "raster_province": PROVINCES[pid],
                     "sources": "data/activity/power/gem_coal_pak.csv; data/activity/power/climatetrace_power_assets_pak.csv",
                     "note": "GEM exact location, Climate TRACE within %.2f km, inside %s" % (km, PROVINCES[pid])})
    return rows


def main(check=False):
    rows = build()
    banner = [
        "COAL GRID STATION COORDINATES (rc42): the FY2023-24 plant-fuel ledger's coal stations,",
        "located by the Global Energy Monitor coal tracker (accuracy exact) and corroborated by",
        "Climate TRACE within %.0f km; the ledger name -> GEM name map is explicit in" % AGREEMENT_KM,
        "scripts/ingest_coal_plant_coordinates.py (no token join). Read by pkinv.report.grid_cube",
        "for ledger keys data/activity/power/plant_coordinates.csv does not locate.",
    ]
    return write_or_check(OUT, list(FIELDS), rows, check=check, banner=banner, lineterminator="\n")


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
