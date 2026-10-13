"""Coordinates for the IPPU register, gated by the district each facility already declares.

WHAT THIS IS FOR. Eight of the thirty-four IPPU facilities carry a coordinate, all of them
cement works located from OpenStreetMap, and the register is the second largest item in the
spatial gap at 17.39 Mt. The cement coordinates for most of the rest have been in this
repository unread: `data/activity/industry/gem_cement_pak.csv` is the Global Energy Monitor
cement tracker's Pakistani rows, thirty-two plants, thirty-one of them carrying a coordinate
GEM itself grades `exact`.

THE GATE IS STRONGER HERE THAN IT WAS FOR THE POWER FLEET. `data/activity/ippu/facilities.csv`
declares a DISTRICT for every one of the thirty-four, and every one resolves to a canonical
ADM2 unit - so each candidate is checked against a district polygon and none has to fall back
to a province, which is where eleven of the power stations had to be settled. Names are
proposed liberally, by shared tokens between the register's operator and facility names and
GEM's plant and owner names, for the reason that made it safe there too: a wrong match cannot
survive the map. A coordinate that lands in the wrong district is refused and named.

TWO SOURCES ON ONE SITE IS CORROBORATION, NOT A CONFLICT. Where GEM places a plant this
register already located from OpenStreetMap, the existing row is kept and the distance between
the two readings is recorded. Two independently compiled datasets agreeing to within a few
hundred metres is worth publishing; the disagreement, where there is one, is worth publishing
more.

GEM'S OWN ACCURACY GRADE IS CARRIED THROUGH. One of the thirty-two rows says `approximate`
rather than `exact`, and it is written as approximate rather than being quietly promoted by
passing the same district test as its neighbours.

Usage:  python3 scripts/ingest_ippu_coordinates.py [--dry-run]
Writes: data/activity/ippu/facility_geocoding_overrides.csv
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
from pkinv.core import adm2  # noqa: E402
from pkinv.core.io import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACILITIES = asset_path(ROOT, "data", "activity", "ippu", "facilities.csv")
GEM = asset_path(ROOT, "data", "activity", "industry", "gem_cement_pak.csv")
ADM2 = asset_path(ROOT, "data", "gis", "PAK_ADM2.geojson")
OUT = asset_path(ROOT, "data", "activity", "ippu", "facility_geocoding_overrides.csv")

FIELDS = ("facility_id", "latitude", "longitude", "coordinate_source",
          "coordinate_source_reference", "coordinate_quality", "boundary_scope",
          "geocode_status", "note")

# Corporate and process words that identify a company or a product rather than a place.
STOP = {"cement", "limited", "ltd", "pvt", "private", "company", "works", "plant", "factory",
        "the", "and", "industries", "industry", "pakistan", "group", "holdings", "mills",
        "corporation", "fertilizer", "fertiliser", "chemicals", "white"}
TOKEN_SPLIT = re.compile(r"[^a-z0-9]+")


def _rows(path):
    return read_rows(path)


def tokens(*names):
    out = set()
    for name in names:
        for token in TOKEN_SPLIT.split((name or "").lower()):
            if len(token) > 2 and token not in STOP:
                out.add(token)
    return out


def haversine_km(a, b):
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0088 * math.asin(math.sqrt(h))


def districts():
    """{shapeID: polygon} - the ADM2 frame is keyed by ID, never by name."""
    from shapely.geometry import shape
    with open(ADM2, encoding="utf-8") as handle:
        data = json.load(handle)
    return {f["properties"]["shapeID"]: shape(f["geometry"]) for f in data["features"]}


def gem_plants():
    """[(name, lat, lon, accuracy)] for the tracker rows that carry a coordinate."""
    out = []
    for row in _rows(GEM):
        raw = (row.get("Coordinates") or "").strip()
        if "," not in raw:
            continue
        lat, lon = (part.strip() for part in raw.split(",", 1))
        try:
            out.append((row["Plant name (English)"], float(lat), float(lon),
                        (row.get("Coordinate accuracy") or "").strip() or "unstated",
                        row.get("Owner (English)", "")))
        except ValueError:
            continue
    return out


def build():
    from shapely.geometry import Point

    facilities = _rows(FACILITIES)
    existing = {r["facility_id"]: r for r in _rows(OUT)} if os.path.exists(OUT) else {}
    shapes = districts()
    to_shape = adm2.adm2_to_shape()
    plants = gem_plants()

    accepted, refused, agreements = [], [], []
    for facility in facilities:
        unit = adm2.resolve(facility["district"])
        polygon = shapes.get(to_shape.get(unit))
        if polygon is None:
            refused.append((facility["facility_id"],
                            "the district %r resolves to %s and that unit has no polygon"
                            % (facility["district"], unit)))
            continue
        mine = tokens(facility["facility_name"], facility["operator"])
        inside = []
        for name, lat, lon, accuracy, owner in plants:
            shared = mine & tokens(name, owner)
            if not shared:
                continue
            if polygon.contains(Point(lon, lat)):
                inside.append((name, lat, lon, accuracy))

        held = existing.get(facility["facility_id"])
        if held and held.get("latitude"):
            # The NEAREST candidate only. Hub and Chakwal each hold two companies' plants in
            # one district, so a token like "hub" matches both and reporting every match makes
            # a 0.7 km agreement look like a 13 km disagreement sitting beside it. The count
            # of candidates is carried instead, because ambiguity is the thing worth knowing.
            scored = sorted((haversine_km((float(held["latitude"]),
                                           float(held["longitude"])), (lat, lon)), name)
                            for name, lat, lon, _a in inside)
            if scored:
                agreements.append((facility["facility_id"], scored[0][1], scored[0][0],
                                   len(scored)))
            continue                      # a located facility is never relocated by this pass
        if not inside:
            refused.append((facility["facility_id"],
                            "no tracker plant whose name shares a token with it falls inside "
                            "%s" % unit))
            continue
        if len({(round(lat, 3), round(lon, 3)) for _n, lat, lon, _a in inside}) > 1:
            spread = max(haversine_km((a[1], a[2]), (b[1], b[2]))
                         for a in inside for b in inside)
            if spread > 2.0:
                refused.append((facility["facility_id"],
                                "%d tracker plants fall inside %s and they are %.1f km apart"
                                % (len(inside), unit, spread)))
                continue
        name, lat, lon, accuracy = inside[0]
        accepted.append({
            "facility_id": facility["facility_id"],
            "latitude": "%.7f" % lat, "longitude": "%.7f" % lon,
            "coordinate_source": "Global Energy Monitor Global Cement and Concrete Tracker "
                                 "(coordinate accuracy: %s)" % accuracy,
            "coordinate_source_reference": "data/activity/industry/gem_cement_pak.csv; xlsx "
                                           "sha256 pinned in sources/GEM/GEM_SOURCES.json",
            "coordinate_quality": "exact" if accuracy == "exact" else accuracy,
            "boundary_scope": "plant site",
            "geocode_status": "exact_coordinate_resolved",
            "note": "matched to GEM %r and accepted because the point falls inside %s, the "
                    "district this register already declared for it" % (name, unit),
        })
    return accepted, refused, agreements, existing


AGREEMENT = asset_path(ROOT, "outputs", "ippu_facility_coordinate_agreement.csv")
OUT_WRITE = OUT        # where main() writes the table it read from OUT; --check redirects it


def write_agreements(agreements):
    """Publish the two-source agreement as a validation product rather than as a print.

    IT WAS ONLY EVER PRINTED, and the validation registry consequently recorded IPPU as
    having no geographic check at all - a declared absence over evidence that was being
    computed on every run and thrown away. Two independently compiled registers placing the
    same works within a few hundred metres is the strongest geographic evidence this
    inventory holds for any facility set, and it belongs in a file a reader can open.

    Built in memory and row-counted before the real file is opened: a one-off script here
    once raised mid-writerows after writeheader and truncated airports.csv to 36 of 38 lines.
    """
    import io
    # HALF OF THESE ARE NOT CORROBORATION AND THE FILE HAS TO SAY WHICH. Eleven of the
    # nineteen held coordinates came FROM the GEM tracker, so their distance to the GEM
    # plant is exactly zero - a register compared with itself. Only the eight located from
    # OpenStreetMap before the tracker was read are two independent compilations agreeing,
    # and they separate by 24 to 744 metres. Publishing all nineteen as agreements would
    # claim more than twice the independent evidence that exists.
    held = {r["facility_id"]: r for r in _rows(OUT)} if os.path.exists(OUT) else {}
    fields = ("facility_id", "gem_plant_name", "separation_km", "candidates_in_district",
              "held_coordinate_source", "independent", "sources", "note")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    independent = 0
    for facility_id, name, km, candidates in sorted(agreements, key=lambda a: a[2]):
        source = (held.get(facility_id, {}).get("coordinate_source") or "unrecorded")
        same_register = source.startswith("Global Energy Monitor")
        independent += not same_register
        writer.writerow({
            "facility_id": facility_id, "gem_plant_name": name,
            "separation_km": "%.3f" % km, "candidates_in_district": candidates,
            "held_coordinate_source": source.split("(")[0].strip(),
            "independent": "no" if same_register else "yes",
            "sources": "Global Energy Monitor cement tracker; "
                       "data/activity/ippu/facility_geocoding_overrides.csv",
            "note": ("the held coordinate came from GEM, so this distance is a register "
                     "compared with itself and is not evidence of anything"
                     if same_register else
                     "two independently compiled registers place this works at the same "
                     "site; the OSM reading is kept and the separation recorded"),
        })
    text = buffer.getvalue()
    assert text.count("\n") == len(agreements) + 1, "row count is not what was built"
    with open(AGREEMENT, "w", newline="", encoding="utf-8") as handle:
        handle.write(text)
    print("wrote %s (%d rows, %d of them independent)"
          % (os.path.relpath(AGREEMENT, ROOT), len(agreements), independent))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Locate IPPU facilities from GEM.")
    parser.add_argument("--dry-run", action="store_true", help="report and write nothing")
    args = parser.parse_args(argv)

    accepted, refused, agreements, existing = build()
    total = len(_rows(FACILITIES))
    print("IPPU facility coordinates, gated by the declared district")
    print("  %d already held, %d newly located, %d still unlocated of %d"
          % (len(existing), len(accepted), total - len(existing) - len(accepted), total))
    if agreements:
        print("\n  where two sources place the same site (existing OSM row kept):")
        for facility_id, name, km, candidates in sorted(agreements, key=lambda a: -a[2]):
            print("    %-26s %-34s %.2f km apart%s"
                  % (facility_id[:26], name[:34], km,
                     "  (%d candidates in the district)" % candidates
                     if candidates > 1 else ""))
    print("\n  refused, and named rather than placed:")
    for facility_id, why in refused:
        print("    %-26s %s" % (facility_id[:26], why))
    if args.dry_run:
        print("\n--dry-run: nothing written.")
        return 0
    write_agreements(agreements)
    rows = sorted(list(existing.values()) + accepted, key=lambda r: r["facility_id"])
    with open(OUT_WRITE, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print("\nwrote %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(rows)))
    return 0


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        if "--check" in sys.argv[1:]:
            # re-derive into a temporary directory and compare; nothing in the tree is
            # written. This producer extends the table it rewrites, so it READS the table
            # at OUT, through the store, and only its write is redirected (OUT_WRITE).
            from pkinv.core.checkmode import compare_only
            sys.exit(compare_only(globals(), ("AGREEMENT", "OUT_WRITE"), lambda: main([])))
        sys.exit(main())
