"""Which located power stations the 0.05 degree province raster puts in the wrong province.

WHY THIS EXISTS. Every located grid station reaches a province the same way: its coordinate
is dropped into the 0.05 degree grid and the cell's `province_id` decides. A cell is about
5.5 km across, so a station within roughly half a cell of a provincial boundary can be
assigned to the wrong side of it, and nothing in the build notices - the assignment is
silent, self-consistent and wrong.

Six of the seventy-seven located stations already disagree with their own curated record,
and a seventh disagrees with the source the ingest reads. In every one of the seven the
curated or source province is the defensible one and the raster is the error:

  China Power Hub   the coal station at Hub. GEM's `Subnational unit (province, state)`
                    says Balochistan and its district field says Lasbela, which
                    adm2_canonical.csv maps to Balochistan. The raster says Sindh, and
                    because scripts/ingest_coal_plant_coordinates.py takes the province
                    FROM the raster, the table's own province column says Sindh too - so
                    this one cannot be caught by comparing the table against the raster.
                    It is caught by comparing the table against GEM.
  Hub Power         the oil station 1.11 km away, same raster cell. Its table says
                    Balochistan, so the repository already holds two stations on one site
                    in two different provinces.
  TPS Guddu x2      Kashmore District, Sindh, on the Rajanpur (Punjab) line.
  Tapal Energy      Keamari, Karachi, Sindh.
  Attock Gen.       Morgah, Rawalpindi District, Punjab, near the ICT boundary.
  Mangla            Mirpur, AJK ("Other"), on the Punjab line. Hydro, so no mass moves.

WHAT THIS DOES NOT DO. It does not correct them. The correction is not a label change:
pkinv.core.gis.grid rasterises districts INSIDE the province raster
(`_rasterize_districts(..., province_id=province_id)`), so a station's province and its
district are one decision. pkinv.report.grid_cube reads neither table's province column -
it recomputes the cell - and pkinv.report.spatial_by_year asserts
`ADM1 == ADM2 + outside + unallocated` for all nine periods. Relabelling a station's
province while its mass stays binned in the old district's cell would break that identity
in exactly the place the whole spatial pass exists to protect. Moving the mass properly
means deciding how a point in a boundary cell is attributed at all, which is a declared
provincial re-base with a geometry decision in it, not a patch.

AND A FINER GRID WOULD NOT FIX IT, which is the finding that decides the remedy. Every one
of the seven sits within 3.4 km of a provincial boundary vertex and five within 1.6 km, and
for four of them the SIMPLIFIED ADM2 POLYGONS disagree with the curated record too: ray
casting puts Hub Power in Karachi (1.00 km from Lasbela), both Guddu units in Dera Ghazi Khan
(1.52 km from Kashmore) and Tapal Energy in Lasbela (1.31 km from its own nearest vertex),
while China Power Hub falls in no polygon at all. The error is therefore in the BOUNDARY
GEOMETRY at these sites, not only in the 5.5 km rasterisation of it - so refining the grid
would move the misassignments around rather than remove them. What would settle each case is
an authoritative district for the station, which for six of the seven the sources already
state and this audit records.

So this measures the defect, names every instance, and gives the guard a denominator.
tests/test_power_province_boundary.py holds the count at the known seven: a new station
whose curated province disagrees with the raster fails the suite rather than joining a
silent list.

Usage:  python3 scripts/build_power_province_boundary_audit.py [--check]
Writes: outputs/pakemis_power_province_boundary_audit.csv
"""
import argparse
import collections
import csv
import io
import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pkinv.assets import asset_path                                    # noqa: E402
from pkinv.core.io import read_rows, write_table                       # noqa: E402
from pkinv.core.geography import PROVINCES                             # noqa: E402
from pkinv.core import adm2 as _adm2                                   # noqa: E402
from pkinv.core.gis.grid import build_grid                             # noqa: E402
from pkinv.paths import DATA, OUTPUTS, ROOT                            # noqa: E402

OUT = asset_path(OUTPUTS, "pakemis_power_province_boundary_audit.csv")
ADM2_GEOJSON = asset_path(DATA, "gis", "PAK_ADM2.geojson")

TABLES = ("plant_coordinates.csv", "coal_plant_coordinates.csv", "gas_plant_coordinates.csv")

BANNER = """\
# WHICH LOCATED POWER STATIONS THE 0.05 DEGREE PROVINCE RASTER MISPLACES
#
# One row per located grid station (row_kind=station), plus one row per fiscal year
# (row_kind=period_exposure) giving the plant-ledger generation the misplaced stations
# carry. `verdict` is the finding; nothing here is corrected - see the module docstring in
# scripts/build_power_province_boundary_audit.py for why a relabel would break the
# ADM1 == ADM2 + outside + unallocated identity, and why the correction is a declared
# provincial re-base rather than a patch.
#
# stated_province    the curated record: the table's own province column, or the province
#                    of its adm2_id in adm2_canonical.csv
# source_province    what the upstream source says in its own province field (GEM
#                    'Subnational unit (province, state)' for coal, 'State/Province' for
#                    gas and oil). Blank where the table has no GEM join.
# raster_province    what the 0.05 degree cell says - and what grid_cube actually uses
# km_to_nearest_adm2_vertex  how close the station is to a district line. All seven
#                    misplaced stations are within 3.4 km and five within 1.6 km
# adm2_containing    the ADM2 polygon that contains the point, by ray casting against
#                    PAK_ADM2.geojson; blank means NO polygon contains it (the point is in
#                    a sliver between simplified boundaries, which is itself the signal)
"""


def _adm2_province():
    # registered legacy path is data/adm2_canonical.csv, not data/gis/ - the shim keeps
    # each asset's published identity, which is not always where the file now sits
    rows = read_rows(asset_path(DATA, "adm2_canonical.csv"))
    return {r["adm2_id"]: r["province_id"] for r in rows}


# The ray caster moved to pkinv.core.gis.adm2_point on 2026-10-05, unchanged, because a
# second consumer needed it: the facility registry was answering the same question from a
# third-party district STRING and shipping a different answer from this audit's for the same
# station. These three names are kept as thin aliases so the rest of this script reads as it
# did, and so there is exactly one implementation of "which polygon contains this point".
from pkinv.core.gis.adm2_point import (                                 # noqa: E402
    containing as _containing_point, in_ring as _in_ring, polygons as _polygons)


def _containing(polys, x, y):
    return _containing_point(x, y, polys)


def _nearest_km(polys, x, y):
    """Great-circle distance to the nearest ADM2 boundary VERTEX, and whose it is.

    A vertex distance, not a distance to the edge, so it is an upper bound on how far the
    point is from the boundary - which is the conservative direction for a column whose
    job is to say "this station is near a line". Longitude degrees are shortened by
    cos(latitude) before the hypotenuse; at 25N that is a factor of 0.9.
    """
    kx = 111.32 * math.cos(math.radians(y))
    ky = 110.57
    best = (float("inf"), "")
    for name, poly, _bb in polys:
        for px, py in poly[0]:
            d = math.hypot((px - x) * kx, (py - y) * ky)
            if d < best[0]:
                best = (d, name)
    return best[0], best[1]


def _gem_provinces():
    """{(lat, lon) rounded: province} from both GEM extracts, by their own province field."""
    out = {}
    for name, col in (("gem_coal_pak.csv", "Subnational unit (province, state)"),
                      ("gem_gas_oil_pak.csv", "State/Province")):
        path = asset_path(DATA, "activity", "power", name)
        if not os.path.exists(path):
            continue
        for r in read_rows(path):
            try:
                la, lo = float(r["Latitude"]), float(r["Longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            prov = (r.get(col) or "").strip()
            if prov:
                out.setdefault((round(la, 4), round(lo, 4)), set()).add(prov)
    return out


def _raster_lookup():
    grid = build_grid()

    def look(lon, lat):
        col, row = (~grid.transform) * (lon, lat)
        row, col = int(row), int(col)
        if 0 <= row < grid.height and 0 <= col < grid.width:
            pid = int(grid.province_id[row, col])
            if 0 <= pid < len(PROVINCES):
                return PROVINCES[pid], "%d,%d" % (row, col)
        return "", ""
    return look


# WHICH KIND OF CONFLICT, which is what decides the remedy (T-VAL-2, 2026-10-05).
#
# `verdict` says a station is misplaced. It does not say WHERE the fault is, and the seven
# are not one problem: two have a frame that disagrees with itself, one sits in a hole in the
# frame, and four have two records agreeing against the frame. Those need three different
# fixes and no station-level relabelling helps any of them.
#
# DELIBERATELY NOT A VOTE. An earlier draft of this counted curated, source, raster and
# polygon as four witnesses and took a majority, which decided four stations on a weighting
# that cannot be defended: the 0.05 degree raster reads PAK_ADM1.geojson and the containing
# test ray-casts PAK_ADM2.geojson, so the two are different files AND different resolutions,
# and a disagreement between them can be either. Classifying the conflict states what the
# held evidence shows; voting would have invented an authority none of these sources has.
#
# The classes, in the order they are tested, because an earlier class makes the later ones
# unanswerable:
#   frame-gap                     no ADM2 polygon contains the point at all
#   frame-inconsistent            the ADM1 raster and the ADM2 polygon name different provinces
#   records-disagree              curated and source disagree; needs an external authority
#   records-agree-frame-dissents  both records agree and the frame does not
ADJUDICATION_CLASSES = ("frame-gap", "frame-inconsistent", "records-disagree",
                        "records-agree-frame-dissents", "agree")


def _adjudicate(stated, source, raster, polygon_province, contains, km):
    if not contains:
        return ("frame-gap",
                "no ADM2 polygon contains the point (%.2f km from the nearest vertex)" % km)
    if raster and polygon_province and raster != polygon_province:
        return ("frame-inconsistent",
                "the 0.05 degree ADM1 raster says %s and the ADM2 polygon says %s, so the "
                "frame disagrees with itself and no station relabelling settles it"
                % (raster, polygon_province))
    if stated and source and stated != source:
        return ("records-disagree",
                "curated says %s and the source record says %s; the frame cannot arbitrate "
                "two records" % (stated, source))
    record = stated or source
    frame = polygon_province or raster
    if record and frame and record != frame:
        return ("records-agree-frame-dissents",
                "curated and source both say %s and the frame says %s, %.2f km from a "
                "boundary" % (record, frame, km))
    return ("agree", "")


def station_rows():
    adm2prov = _adm2_province()
    polys = _polygons()
    gem = _gem_provinces()
    look = _raster_lookup()
    placement = _placement_by_plant()
    curated = _curated_provinces()
    rows = []
    for table in TABLES:
        path = asset_path(DATA, "activity", "power", table)
        if not os.path.exists(path):
            continue
        for r in read_rows(path):
            lat, lon = float(r["latitude"]), float(r["longitude"])
            # THE CURATED RECORD FIRST, and the coordinate table's own column second.
            # coal_plant_coordinates.csv used to carry a column called Province that was
            # RASTER-DERIVED, and reading it here reported a raster value as the station's
            # stated province - which is the very confusion this audit exists to expose, so
            # the audit was blind to it in its own strongest case. The column is now named
            # raster_province and the stated province comes from plant_locations.csv, the
            # same record grid_cube's dispatch reads.
            stated = curated.get(_plant_key(r["plant"]), "")
            basis = "curated record (plant_locations.csv)"
            if not stated:
                stated = (r.get("province") or "").strip()
                basis = "table province column"
            if not stated and r.get("adm2_id"):
                stated = adm2prov.get(r["adm2_id"], "")
                basis = "province of adm2_id in adm2_canonical.csv"
            if not stated:
                basis = "none stated"
            source = ";".join(sorted(gem.get((round(lat, 4), round(lon, 4)), ())))
            rp, cell = look(lon, lat)
            contains = _containing(polys, lon, lat)
            km, near = _nearest_km(polys, lon, lat)

            disagrees = []
            if stated and rp and stated != rp:
                disagrees.append("curated vs raster")
            if source and rp and source != rp:
                disagrees.append("source vs raster")
            if source and stated and source != stated:
                disagrees.append("source vs curated")
            if disagrees:
                verdict = "MISPLACED BY RASTER (%s)" % "; ".join(disagrees)
            elif not contains:
                verdict = "on a boundary sliver, all three agree"
            else:
                verdict = "agree"

            poly_prov = ""
            if contains:
                try:
                    poly_prov = adm2prov.get(_adm2.resolve(contains), "")
                except Exception:
                    poly_prov = ""
            adj_class, adj_detail = _adjudicate(stated, source, rp, poly_prov, contains,
                                                km if km < 1e6 else 0.0)

            placed = placement.get(_plant_key(r["plant"]), {})
            rows.append({
                "row_kind": "station", "table": table, "plant": r["plant"],
                "latitude": "%.6f" % lat, "longitude": "%.6f" % lon,
                "stated_province": stated, "stated_basis": basis,
                "source_province": source, "raster_province": rp, "raster_cell": cell,
                "adm2_containing": contains,
                "km_to_nearest_adm2_vertex": "%.2f" % km if km < 1e6 else "",
                "nearest_adm2": near, "period_id": "", "metric": "", "value": "",
                "verdict": verdict,
                "polygon_province": poly_prov,
                "adjudication": adj_class,
                "adjudication_detail": adj_detail,
                "booked_province": placed.get("booked_province", ""),
                "curated_district": placed.get("curated_district", ""),
                "curated_district_province": placed.get("curated_district_province", ""),
                "adm2_placement": placed.get("adm2_placement", ""),
            })
    return rows


def exposure_rows(stations):
    """How much plant-ledger generation the misplaced stations carry, per fiscal year."""
    misplaced = {s["plant"] for s in stations if s["verdict"].startswith("MISPLACED")}
    led = read_rows(asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv"))

    def num(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return 0.0

    out = []
    for y in sorted({r["fiscal_year"] for r in led}):
        rows = [r for r in led if r["fiscal_year"] == y]
        tot = sum(num(r["net_generation_GWh"]) for r in rows)
        aff = sum(num(r["net_generation_GWh"]) for r in rows if r["plant"] in misplaced)
        by = collections.Counter()
        for r in rows:
            if r["plant"] in misplaced:
                by[r["plant"]] += num(r["net_generation_GWh"])
        period = "FY%s-%s" % (y, str(int(y) + 1)[-2:])
        out.append({
            "row_kind": "period_exposure", "table": "plant_fuel_ledger.csv",
            "plant": "", "latitude": "", "longitude": "",
            "stated_province": "", "stated_basis": "", "source_province": "",
            "raster_province": "", "raster_cell": "", "adm2_containing": "",
            "km_to_nearest_adm2_vertex": "", "nearest_adm2": "",
            "period_id": period,
            "metric": "misplaced share of plant-ledger net generation (percent)",
            "value": "%.2f" % (100.0 * aff / tot) if tot else "",
            "verdict": "%.0f of %.0f GWh; %s" % (
                aff, tot, ", ".join("%s %.0f" % (k, v) for k, v in by.most_common())),
        })
    return out


def _plant_key(name):
    from pkinv.sectors.power.plant_names import plant_key
    return plant_key(name)


def _curated_provinces():
    """{name key: inventory province} from plant_locations.csv, via grid_cube's reader."""
    from pkinv.report import grid_cube
    return grid_cube._curated_station_provinces()


def _placement_by_plant():
    """What the LIVE dispatch does with each station, keyed by name key.

    The audit used to end at the finding - its own banner said "nothing here is corrected".
    Since 2026-10-07 something is: a point whose ADM2 polygon leaves the province it was
    pooled under is placed in the district its curated record names, when that district's
    own polygon majority keeps the province. So the audit must now report the placement
    beside the defect, or a reader would still take the finding for the outcome.

    It is read from grid_cube rather than recomputed, because recomputing it is how this
    repository came to ship two different answers to "which polygon contains this station"
    (the ray caster was centralised in pkinv.core.gis.adm2_point for exactly that reason).
    """
    from pkinv.report import grid_cube
    return {_plant_key(row["plant"]): row
            for row in grid_cube.grid_plant_province_sources()}


FIELDS = ("row_kind", "table", "plant", "latitude", "longitude", "stated_province",
          "stated_basis", "source_province", "raster_province", "raster_cell",
          "adm2_containing", "km_to_nearest_adm2_vertex", "nearest_adm2", "period_id",
          "metric", "value", "verdict", "polygon_province", "adjudication",
          "booked_province", "curated_district",
          "curated_district_province", "adm2_placement",
          "adjudication_detail")


def build():
    stations = station_rows()
    return stations + exposure_rows(stations)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped file matches a fresh build; write nothing")
    args = ap.parse_args()
    rows = build()
    if args.check:
        if not os.path.exists(OUT):
            raise SystemExit("%s does not exist" % OUT)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        fresh = BANNER + buf.getvalue()
        if io.open(OUT, encoding="utf-8").read() != fresh:
            raise SystemExit("%s differs from a fresh build" % OUT)
        print("%s: current" % OUT)
        return
    write_table(OUT, FIELDS, rows, banner=BANNER.splitlines())
    misplaced = [r for r in rows if r["verdict"].startswith("MISPLACED")]
    print("Power province boundary audit -> %s (%d stations, %d MISPLACED)"
          % (OUT, sum(1 for r in rows if r["row_kind"] == "station"), len(misplaced)))
    for r in misplaced:
        print("   %-40s curated=%-14s source=%-14s raster=%s"
              % (r["plant"][:40], r["stated_province"] or "-",
                 r["source_province"] or "-", r["raster_province"]))


if __name__ == "__main__":
    main()
