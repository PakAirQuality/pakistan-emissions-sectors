"""Coordinates for the grid fleet, gated by the geography the inventory already declared.

WHAT THIS IS FOR. All 157 grid power stations are `exact_coordinate_unresolved`. They are the
largest point-source fleet in the inventory and their emissions are spread over a built-up-area
raster, because `data/activity/power/plant_locations.csv` locates them to a TOWN and nothing
here held a coordinate. The cube says so in its own words - "where geometry is claimed but
coordinates are not held (power grid towns, LNG terminals), the surface is the declared proxy -
no faked points, ever" - and `data/stream_grid_proxy.csv` says built-up is the surface "until
coordinates land". Two coordinate sources are tracked in this repository and neither had been
read: WRI's Global Power Plant Database (62 Pakistani plants) and ClimateTRACE's power assets
(71).

WHY THE NAME MATCH IS ALLOWED TO BE GENEROUS HERE, HAVING BEEN REFUSED ELSEWHERE. A containment
join was measured and rejected for the fuel labels last pass, because it bound HUBCO Narowal to
`hub` and nothing downstream could have noticed. The difference here is that a wrong match
CANNOT get through: every candidate coordinate is checked against the district or province the
station already declares, and a point in the wrong place fails geography rather than being
believed. So candidates are proposed liberally by shared name tokens - the two sources write
"Hubco power station" and "AES Lalpir Ltd. Mahmood Kot Muzaffargarh" for stations this
inventory calls "Hub Power" and "Lal Pir" - and the map, not the string, decides.

THE LADDER, STRONGEST FIRST.

  1. DISTRICT CONTAINS THE POINT. The station's declared town resolves to a canonical ADM2
     unit for 100 of the 157, and the candidate must fall inside that unit's polygon. This is
     the strong rung and it costs nothing: the existing town-level assignment becomes the
     validator of the new point rather than being discarded by it.
  2. PROVINCE CONTAINS THE POINT AND THE TWO SOURCES AGREE. Where the town is a locality
     rather than a district - Guddu, Bhikki, Balloki, Chashma - the province still constrains,
     and two independently compiled databases landing within a few kilometres of each other is
     evidence a single one is not.
  2b. PROVINCE CONTAINS THE POINT AND THE SOURCE'S OWN NAME CONFIRMS THE TOWN (Wave 5).
     The locality problem, answered without a gazetteer this repository does not hold: when
     ClimateTRACE writes "Bhikki power station" and NEPRA's own location column says Bhikki,
     two independently compiled records agree on the PLACE by name, and the province polygon
     still constrains the point. The match is on the town's tokens appearing in the
     candidate's name - never the reverse, and never on the corporate name alone.
  3. Neither. The station stays `exact_coordinate_unresolved`, keeps the built-up proxy, and is
     NAMED in the report. No faked points, ever.

Usage:  python3 scripts/ingest_grid_plant_coordinates.py [--dry-run]
Writes: data/activity/power/plant_coordinates.csv
"""
import argparse
import csv
import json
import math
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "src"))

from pkinv.assets import asset_path
from pkinv.core.io import write_or_check
from pkinv.core import adm2  # noqa: E402
from pkinv.core.io import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIONS = asset_path(ROOT, "data", "activity", "power", "plant_locations.csv")
WRI = asset_path(ROOT, "sources", "Power Plants", "wri_gppd_PAK.csv")
TRACE = asset_path(ROOT, "sources", "Power Plants", "climatetrace_power_assets_PAK.csv")
ADM1 = asset_path(ROOT, "data", "gis", "PAK_ADM1.geojson")
ADM2 = asset_path(ROOT, "data", "gis", "PAK_ADM2.geojson")
OUT = asset_path(ROOT, "data", "activity", "power", "plant_coordinates.csv")

FIELDS = ("plant", "latitude", "longitude", "adm2_id", "district_evidence", "corroboration",
          "sources", "agreement_km", "matched_names", "source_file", "note")

# Words that identify a company or a plant rather than a place, and so carry no matching
# power. "power station" is ClimateTRACE's suffix on every row; the rest are corporate.
STOP = {"power", "station", "ltd", "limited", "pvt", "private", "company", "energy", "plant",
        "the", "and", "of", "epc", "pakistan", "co", "generation", "electric", "block",
        "unit", "units", "project", "international", "holdings", "corporation"}
# Two independently compiled databases pointing at the same station should land within this
# of each other. A power station is a site, not a point, so this is generous by design.
AGREEMENT_KM = 10.0

# WHAT KIND OF STATION IS THIS, AND WHAT KIND IS THE CANDIDATE. The ladder used to match on
# name tokens and geography alone, with no gate on TECHNOLOGY, and that let four rows ship a
# point belonging to a different plant: the run-of-canal hydel `Nandipur` took the adjacent gas
# CCPP's coordinate, and three wind farms (`Gul Ahmed Electric`, `Liberty Wind Power-I` and
# `-II`) took the coordinates of the thermal plants their corporate group also owns - the
# Liberty rows landing 370 km away in Ghotki. A candidate may now corroborate a station only
# where the two declare a compatible technology.
STATION_CLASS = (
    ("wt", "wind"), ("solar", "solar"),
    ("run of river", "hydro"), ("run of canal", "hydro"), ("reservoir", "hydro"),
    ("canal fall", "hydro"), ("high head", "hydro"), ("hydro", "hydro"),
    ("bagasse", "biomass"), ("biomass", "biomass"),
)
# ClimateTRACE's asset_type vocabulary is fossil and biomass ONLY - it carries no wind, solar
# or hydro asset anywhere in Pakistan - so it can never corroborate one of those stations.
CANDIDATE_CLASS = {
    "coal": "thermal", "gas": "thermal", "oil": "thermal", "other_fossil": "thermal",
    "nuclear": "thermal", "biomass": "biomass", "hydro": "hydro", "wind": "wind",
    "solar": "solar",
}
# WRI's CARMA-geolocated rows are demonstrably unreliable here: of the three this ladder
# matched, `Shadiwal` sits about 120 km from the Gujrat canal station it names (inside Lahore)
# and `Dargai` lands in Upper Dir for a station at Malakand. A CARMA candidate may still
# supply a coordinate, but it cannot carry a DISTRICT on its own.
WEAK_GEOLOCATION = {"carma"}
# NEPRA's location column spells a handful of districts differently from the canonical
# ADM2 register; tried before giving up on rung 1. Spelling equivalences only - a town
# this table cannot spell-correct stays a locality and falls to the weaker rungs.
TOWN_ALIASES = {"lasbella": "Lasbela", "sheikhupura": "Sheikhupura"}
PROVINCE_ALIASES = {
    "kp": "Khyber Pakhtunkhwa", "khyber pakhtunkhwa": "Khyber Pakhtunkhwa",
    "kpk": "Khyber Pakhtunkhwa", "punjab": "Punjab", "sindh": "Sindh",
    "balochistan": "Balochistan", "azad kashmir": "Azad Kashmir", "ajk": "Azad Kashmir",
    "azad jammu & kashmir": "Azad Kashmir", "azad jammu and kashmir": "Azad Kashmir",
    "gilgit-baltistan": "Gilgit-Baltistan", "gilgit baltistan": "Gilgit-Baltistan",
    "islamabad": "Islamabad Capital Territory", "ict": "Islamabad Capital Territory",
}


def _rows(path):
    return read_rows(path)


def station_class(station_type):
    """The technology class NEPRA's station_type declares; everything unlisted is thermal."""
    lowered = (station_type or "").lower()
    for token, klass in STATION_CLASS:
        if token in lowered:
            return klass
    return "thermal"


def candidate_classes(declared):
    """The technology classes a candidate declares. WRI prints one fuel; ClimateTRACE prints a
    comma list. An unrecognised token yields nothing, which refuses rather than admits."""
    out = set()
    for part in re.split(r"[,;/]", (declared or "").lower()):
        klass = CANDIDATE_CLASS.get(part.strip())
        if klass:
            out.add(klass)
    return out


def tokens(name):
    cleaned = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    return {t for t in cleaned.split() if len(t) > 2 and t not in STOP}


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def _shapes(path, key="shapeName"):
    """Polygons keyed as the caller needs them.

    The ADM2 frame is keyed by shapeID, not by name: `adm2.adm2_to_shape()` returns the
    geoBoundaries ID, and looking those up by shapeName silently matched nothing at all -
    every district check failed and the whole fleet fell through to the weaker rung.
    """
    from shapely.geometry import shape
    with open(path, encoding="utf-8") as handle:
        data = json.load(handle)
    return {feature["properties"][key]: shape(feature["geometry"])
            for feature in data["features"]}


def candidates():
    """{station name: [(source, name, lat, lon, geolocation)]} - proposed by shared tokens AND
    a compatible technology, not decided. The technology gate is what stops a wind farm being
    corroborated by the thermal plant its owner also runs."""
    pools = []
    for source, path, lat_key, lon_key, tech_key, geo_key in (
            ("wri_gppd", WRI, "latitude", "longitude", "primary_fuel", "geolocation_source"),
            ("climatetrace", TRACE, "lat", "lon", "asset_type", None)):
        for row in _rows(path):
            if not row.get(lat_key) or not row.get(lon_key):
                continue
            pools.append((source, row["name"], float(row[lat_key]), float(row[lon_key]),
                          tokens(row["name"]), candidate_classes(row.get(tech_key)),
                          (row.get(geo_key) or "").strip().lower() if geo_key else ""))
    out, gated = {}, []
    for station in _rows(STATIONS):
        mine = tokens(station["plant"])
        if not mine:
            continue
        wanted = station_class(station.get("station_type", ""))
        found = []
        for source, name, lat, lon, theirs, classes, geo in pools:
            shared = mine & theirs
            if not (shared and (mine <= theirs or theirs <= mine or len(shared) >= 2)):
                continue
            if wanted not in classes:
                gated.append((station["plant"], wanted, name, "/".join(sorted(classes)) or "?"))
                continue
            found.append((source, name, lat, lon, geo))
        if found:
            out[station["plant"]] = found
    candidates.gated = gated
    return out


candidates.gated = []


def _adm2_of(town):
    for attempt in (town, TOWN_ALIASES.get(town.strip().lower(), town)):
        try:
            return adm2.resolve(attempt)
        except KeyError:
            continue
    return None


def build():
    stations = _rows(STATIONS)
    proposed = candidates()
    districts = _shapes(ADM2, key="shapeID")
    provinces = _shapes(ADM1)
    to_shape = adm2.adm2_to_shape()
    from shapely.geometry import Point

    accepted, refused = [], []
    for station in stations:
        found = proposed.get(station["plant"], [])
        if not found:
            refused.append((station["plant"], "no source names a station whose tokens match"))
            continue
        unit = _adm2_of(station["town"])
        shape_name = to_shape.get(unit) if unit else None
        district = districts.get(shape_name) if shape_name else None
        province = provinces.get(
            PROVINCE_ALIASES.get(station["province"].strip().lower(), station["province"]))

        inside_district = [c for c in found if district and district.contains(Point(c[3], c[2]))]
        inside_province = [c for c in found if province and province.contains(Point(c[3], c[2]))]

        town_tokens = tokens(station["town"] or "")
        name_confirms = [c for c in inside_province
                         if town_tokens and town_tokens <= tokens(c[1])]

        pick, corroboration, note = None, "", ""
        if inside_district:
            pick, corroboration = inside_district, "district_contains_the_point"
            note = "the town %r resolves to %s and the point falls inside it" % (
                station["town"], unit)
        elif len(inside_province) >= 2:
            worst = max(haversine_km((a[2], a[3]), (b[2], b[3]))
                        for a in inside_province for b in inside_province)
            if worst <= AGREEMENT_KM:
                pick, corroboration = inside_province, "province_contains_and_sources_agree"
                note = ("the town %r is a locality rather than a district, so the province "
                        "constrains and two databases agree to %.1f km"
                        % (station["town"], worst))
            elif name_confirms:
                pick, corroboration = (name_confirms,
                                       "province_contains_and_name_confirms_town")
                note = ("the sources disagree with each other, but %d of them NAME the "
                        "declared town %r in their own station name and sit inside the "
                        "province - the place is corroborated by name, the corporate "
                        "string decides nothing" % (len(name_confirms), station["town"]))
            else:
                refused.append((station["plant"],
                                "inside the province but the sources disagree by %.0f km, "
                                "which is two different places" % worst))
                continue
        elif name_confirms:
            pick, corroboration = (name_confirms,
                                   "province_contains_and_name_confirms_town")
            note = ("the town %r is a locality rather than a district; the single "
                    "candidate names that town itself and sits inside the province - "
                    "two independently compiled records agreeing on the PLACE"
                    % station["town"])
        else:
            refused.append((station["plant"],
                            "no candidate falls inside the declared %s"
                            % ("district" if district else "province")))
            continue

        spread = max((haversine_km((a[2], a[3]), (b[2], b[3]))
                      for a in pick for b in pick), default=0.0)
        if spread > AGREEMENT_KM:
            refused.append((station["plant"],
                            "candidates inside the declared area are %.0f km apart" % spread))
            continue
        latitude = sum(c[2] for c in pick) / len(pick)
        longitude = sum(c[3] for c in pick) / len(pick)

        # THE DISTRICT THE POINT IS ACTUALLY IN. Until rc60 this file wrote `unit` - the district
        # the TOWN resolves to - on rungs 2 and 2b without ever testing that the point it ships
        # beside it falls inside that district. Three rows contradicted themselves as a result.
        # The point now decides, and `district_evidence` records how:
        #   point_in_polygon          the accepted point falls inside exactly one canonical unit
        #   point_in_shared_shape     it falls inside a shape several carved-from units share, so
        #                             the polygon cannot separate them and the town's name is used
        #   town_only                 no polygon contains the point (a coastal or border sliver)
        #   weak_geolocation          the only candidate is CARMA-geolocated; a coordinate, not a
        #                             district
        point = Point(longitude, latitude)
        containing = sorted(unit_id for unit_id, shape_id in to_shape.items()
                            if shape_id and shape_id in districts
                            and districts[shape_id].contains(point))
        only_weak = all((c[4] in WEAK_GEOLOCATION) for c in pick)
        if only_weak:
            resolved, evidence = (unit or "unresolved"), "weak_geolocation"
        elif len(containing) == 1:
            resolved, evidence = containing[0], "point_in_polygon"
        elif len(containing) > 1:
            resolved = unit if unit in containing else "unresolved"
            evidence = "point_in_shared_shape"
        else:
            resolved, evidence = (unit or "unresolved"), "town_only"
        accepted.append({
            "plant": station["plant"],
            "latitude": round(latitude, 5), "longitude": round(longitude, 5),
            "adm2_id": resolved or "unresolved",
            "district_evidence": evidence,
            "corroboration": corroboration,
            "sources": "+".join(sorted({c[0] for c in pick})),
            "agreement_km": round(spread, 2),
            "matched_names": " | ".join(sorted({c[1] for c in pick})),
            "source_file": "sources/Power Plants/wri_gppd_PAK.csv; "
                           "sources/Power Plants/climatetrace_power_assets_PAK.csv",
            "note": note,
        })
    return accepted, refused


def main(argv=None, check=False):
    parser = argparse.ArgumentParser(description="Corroborate grid plant coordinates.")
    parser.add_argument("--dry-run", action="store_true", help="report and write nothing")
    parser.add_argument("--check", action="store_true",
                        help="re-derive and report whether the committed file "
                             "still follows from the held document; writes nothing")
    args = parser.parse_args(argv)
    check = check or args.check

    accepted, refused = build()
    total = len(_rows(STATIONS))
    print("grid plant coordinates, gated by the geography already declared")
    print("  %d of %d stations corroborated; %d stay coordinate_unresolved"
          % (len(accepted), total, len(refused)))
    by = {}
    for row in accepted:
        by[row["corroboration"]] = by.get(row["corroboration"], 0) + 1
    for rung, count in sorted(by.items()):
        print("    %-38s %d" % (rung, count))
    print("\n  refused, and named rather than placed:")
    for plant, why in refused[:12]:
        print("    %-30s %s" % (plant[:30], why))
    if len(refused) > 12:
        print("    ... and %d more, all in the written report" % (len(refused) - 12))
    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0
    if write_or_check(OUT, FIELDS,
                      sorted(accepted, key=lambda r: r["plant"]), check):
        return 1
    if check:
        print("the plant coordinates reproduces from the held document.")
        return 0
    print("\nwrote %s" % os.path.relpath(OUT, ROOT))
    return 0


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        sys.exit(main())
