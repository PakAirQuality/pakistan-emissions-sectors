#!/usr/bin/env python3
"""Lahore District's air pollutants by sector and year, with the unplaced remainder beside them
(rc58 W3).

WHAT LAHORE MEANS HERE. The census district (adm2 punjab_lahore, geoBoundaries shape
60131773B12131197496886), the grain every spatial product in this release is built on - not
the municipal area and not an airshed. A territorial total: facilities in neighbouring
districts that affect Lahore's air are outside it, and secondary particulate formed from SO2,
NOx and NH3 is not primary mass and is not added. Both are stated on the file rather than left
to the reader.

WHAT THE ROWS ARE. For every (period, configuration, sector, species) the district's Gg from
pakemis_air_adm2_by_year.csv - the same allocation the grid and the provincial tables are
marginals of - beside the allocation_basis the sector's anchor streams carry that period
(the weight registry's basis, operator and grade, joined from the support ledger), so a reader
sees that industrial gas rode a provincial diffuse pattern while brick coal rode the surveyed
kiln points. Then, per (period, configuration, species), ONE national row for the mass no
geometry placed below the province (the unallocated table's below_adm1 term) - the remainder
a district figure must be read against, never spread over districts.

Reads:  outputs/pakemis_air_adm2_by_year.csv, outputs/pakemis_air_unallocated_by_year.csv,
        outputs/pakemis_air_spatial_support_by_year.csv, data/adm2_canonical.csv
Writes: outputs/pakemis_air_lahore_by_year.csv
"""
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows  # noqa: E402
from pkinv.paths import DATA, OUTPUTS  # noqa: E402

ADM2 = asset_path(OUTPUTS, "pakemis_air_adm2_by_year.csv")
UNALLOC = asset_path(OUTPUTS, "pakemis_air_unallocated_by_year.csv")
SUPPORT = asset_path(OUTPUTS, "pakemis_air_spatial_support_by_year.csv")
CANONICAL = asset_path(DATA, "adm2_canonical.csv")
OUT = asset_path(OUTPUTS, "pakemis_air_lahore_by_year.csv")
ADM2_ID = "punjab_lahore"
FIELDS = ("period_id", "configuration_id", "row_kind", "sector_id", "pollutant", "emissions_Gg",
          "geography", "allocation_basis", "note")
HEADER = """\
# LAHORE DISTRICT'S AIR POLLUTANTS BY SECTOR AND YEAR (adm2 punjab_lahore, the census district -
# not the municipal area, not an airshed; a TERRITORIAL total: neighbouring districts' sources are
# outside it and secondary particulate is not primary mass). district rows are the release's own
# ADM2 allocation (pakemis_air_adm2_by_year.csv), allocation_basis the anchor streams' weight-registry
# basis:operator:grade joined from the support ledger; unplaced rows are the NATIONAL mass no geometry
# placed below the province that period (the unallocated table's below_adm1 term), shown beside the
# district so its figure is read against what could not be placed anywhere. Gg == kt.
# scripts/build_air_lahore_view.py
"""


GENERIC_NOTE = ("the release's ADM2 allocation for the sector's anchor streams; the district's "
                "share of a national or provincial pattern, not a measurement")
# The admitted power fleet does not reach the district that way and has not since rc61. Its frames
# declare their own provincial marginal and place each station on its own coordinate, so for this
# district the SO2 row IS a named station rather than a share of a national series. Stamping the
# generic sentence on it was not a rounding of the truth - a reviewer read it, concluded the
# release had never published a plant-derived Lahore power number, and said so.
PLANT_DERIVED_NOTE = (
    "NOT a share of a national pattern: Lahore holds one emitting grid station, Kohinoor Energy, "
    "placed on its own point-in-polygon coordinate, and this row equals that station's own line in "
    "data/activity/power/power_so2_admission.csv to six decimals. Five of the nine periods "
    "(FY2019-20 onward) are METERED NEPRA fuel quantities with no heat rate, calorific value or "
    "efficiency between the document and the mass; the four earlier ones carry the station's own "
    "published heat rate backwards, a route that runs about 8 percent high where both can be "
    "compared (outputs/pakemis_air_lahore_power_register.csv)")


def _note(sector_id, pollutant):
    if sector_id == "power" and pollutant.upper() == "SO2":
        return PLANT_DERIVED_NOTE
    return GENERIC_NOTE


def main():
    shape = next(r["shape_id"] for r in read_rows(CANONICAL) if r["adm2_id"] == ADM2_ID)
    basis = defaultdict(set)
    for r in read_rows(SUPPORT):
        basis[(r["period_id"], r["configuration_id"], r["sector_id"])].add(
            "%s:%s:%s" % (r["spatial_time_basis"], r["temporal_operator"], r["evidence_grade"]))
    rows = []
    for r in read_rows(ADM2):
        if r["shape_id"] != shape:
            continue
        key = (r["period_id"], r["configuration_id"], r["sector_id"])
        rows.append({"period_id": r["period_id"], "configuration_id": r["configuration_id"],
                     "row_kind": "district", "sector_id": r["sector_id"], "pollutant": r["pollutant"],
                     "emissions_Gg": r["emissions_Gg"], "geography": "Lahore District (%s)" % ADM2_ID,
                     "allocation_basis": ";".join(sorted(basis.get(key, {"not in support ledger"}))),
                     "note": _note(r["sector_id"], r["pollutant"])})
    unplaced = defaultdict(float)
    for r in read_rows(UNALLOC):
        if r["level"] == "below_adm1":
            unplaced[(r["period_id"], r["configuration_id"], r["pollutant"], r["sector_id"])] += float(r["emissions_Gg"])
    for (pid, cfg, pol, sector), v in sorted(unplaced.items()):
        rows.append({"period_id": pid, "configuration_id": cfg, "row_kind": "unplaced_national",
                     "sector_id": sector, "pollutant": pol, "emissions_Gg": "%.12g" % v,
                     "geography": "Pakistan, not placed below ADM1",
                     "allocation_basis": "none (no native geometry below the province)",
                     "note": "the remainder a district figure is read against; never spread over districts"})
    rows.sort(key=lambda r: (r["period_id"], r["configuration_id"], r["row_kind"], r["sector_id"], r["pollutant"]))
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    n_d = sum(1 for r in rows if r["row_kind"] == "district")
    print("Lahore air view -> %s (%d district rows, %d unplaced rows)" % (os.path.relpath(OUT), n_d, len(rows) - n_d))
    tot = defaultdict(float)
    for r in rows:
        if r["row_kind"] == "district" and r["period_id"] == "FY2023-24" and r["configuration_id"] == "S_TAN":
            tot[(r["pollutant"], r["sector_id"])] += float(r["emissions_Gg"])
    for pol in ("PM2.5", "SO2", "NOx"):
        by = sorted(((s, v) for (p, s), v in tot.items() if p == pol), key=lambda kv: -kv[1])
        print("  FY2023-24 %-6s " % pol + ", ".join("%s %.2f" % kv for kv in by))
    return 0


if __name__ == "__main__":
    sys.exit(main())
