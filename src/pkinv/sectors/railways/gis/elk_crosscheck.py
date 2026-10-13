"""ELK 2019 against this inventory - DIAGNOSTIC ONLY, hypotheses stated before the run.

ELK (DLR's global transport inventory, ESSD 2026) is the only open global product with
separate passenger-rail and freight-rail layers on a 0.1-degree grid. Its paper warns that
railway activity is known for relatively few countries, so the FIRST question is whether
Pakistan's layer is modelled from observed activity or is a fleet-model default - and the
comparison is a benchmark, never a calibration target.

HYPOTHESES, STATED BEFORE COMPUTING:
  H1  ELK carries a non-zero Pakistan rail layer at all.
  H2  Its national rail CO2 magnitude sits within a factor of a few of this inventory's
      calendar-2019 value (~0.45 Mt) - NOT at the BUR/CRT's 4+ Mt, which would suggest it
      ingested the official submission.
  H3  Its passenger/freight split is broadly passenger-heavy, like the operator's traffic.
  H4  Its spatial mass concentrates along the ML-1 spine, like the route model's.

WHAT THIS CANNOT SAY. Agreement does not validate either side (both may share defaults);
disagreement does not refute the metered inventory. The one asymmetric fact available: this
inventory's national total is an operator fuel meter, ELK's is a fleet model.

Cells are country-masked by looking each ELK cell centre up in the inventory's own ADM
raster - a lat/lon box would swallow Indian border rail and treble the total.

Licence note, recorded because it disagrees with itself: the ESSD paper states CC BY 4.0;
the DLR download directory footer links CC BY-NC 4.0. The extraction table here is a
derived comparison, not a redistribution of the gridded data.

Usage:  python3 -m pkinv.sectors.railways.gis.elk_crosscheck   (needs [gis] + netCDF4)
Writes: outputs/railways_elk_crosscheck_2024.csv
"""

from pkinv.assets import asset_path
import csv
import math
import os

from pkinv.paths import OUTPUTS, ROOT
from pkinv.sectors.railways import engine
from pkinv.sectors.railways.data import RailwaysData

ELK_DIR = asset_path(ROOT, "sources", "ELK")
# rc41: the crosscheck reads the consumed derivative (scripts/ingest_elk_rail.py proves it
# against the netCDFs wherever they are held); the package registers the 26 MB documents
# without shipping them, and the rebuild there must produce the same table.
ELK_TABLE = asset_path(ROOT, "data", "activity", "railways", "elk_rail_pak_2019.csv")
SECONDS = 365.0 * 86400.0
SPECIES = {"CO2-rep": "CO2_rep_emiss", "NOx": "NOx_emiss"}


def _cell_area_m2(lat, dlat=0.1, dlon=0.1):
    R = 6371000.0
    return (math.radians(dlon) * R * math.cos(math.radians(lat))
            * math.radians(dlat) * R)


def pakistan_total_kt(path, varname, grid):
    """kt/yr summed over ELK cells whose centres fall inside Pakistan's ADM raster."""
    import netCDF4
    import numpy as np
    ds = netCDF4.Dataset(path)
    la, lo = ds.variables["lat"][:], ds.variables["lon"][:]
    var = None
    for name in (varname, *[v for v in ds.variables
                            if v.endswith("_emiss")]):
        if name in ds.variables:
            var = name
            break
    arr = np.squeeze(np.array(ds.variables[var][:]))
    ii = np.where((la >= 23.0) & (la <= 37.5))[0]
    jj = np.where((lo >= 60.0) & (lo <= 78.0))[0]
    inv = ~grid.transform
    total = 0.0
    cells = 0
    for i in ii:
        area = _cell_area_m2(float(la[i]))
        for j in jj:
            v = arr[i, j]
            if not v or np.isnan(v):
                continue
            c, r = inv * (float(lo[j]), float(la[i]))
            r, c = int(r), int(c)
            if 0 <= r < grid.height and 0 <= c < grid.width \
                    and grid.province_id[r, c] >= 0:
                total += float(v) * area * SECONDS
                cells += 1
    return total / 1e6, cells      # kg -> kt


def main():
    from pkinv.core.gis.grid import build_grid
    data = RailwaysData()
    grid = build_grid()

    from pkinv.core import documents
    results = {}
    for r in documents.read_extract(ELK_TABLE, {"elk_pak_kt_2019": float, "cells": int}):
        results[(r["species"], r["subsector"])] = (r["elk_pak_kt_2019"], r["cells"])

    # This inventory's calendar-2019 comparables: mean of FY2018-19 and FY2019-20.
    own_co2 = sum(
        sum(c["emissions_Gg"] for c in engine.build_components(data, y)
            if c["gas"] == "CO2") for y in (2019, 2020)) / 2.0 / 1e3  # Mt -> as Mt
    own_co2_kt = own_co2 * 1e3

    out = asset_path(OUTPUTS, "railways_elk_crosscheck_%d.csv" % data.year)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["species", "subsector", "elk_pak_kt_2019", "cells", "own_kt_cy2019",
                    "ratio_elk_over_own", "note"])
        for (species, sub), (kt, cells) in sorted(results.items()):
            w.writerow([species, sub, round(kt, 3), cells, "", "", ""])
        co2_total = sum(kt for (s, _), (kt, _c) in results.items()
                        if s == "CO2-rep")
        nox_total = sum(kt for (s, _), (kt, _c) in results.items() if s == "NOx")
        w.writerow(["CO2-rep", "rail-total", round(co2_total, 3), "",
                    round(own_co2_kt, 3), round(co2_total / own_co2_kt, 3),
                    "own value: mean of FY2018-19 and FY2019-20, CO2 only; "
                    "ELK is a fleet model, this inventory a fuel meter"])
        if nox_total:
            w.writerow(["NOx", "rail-total", round(nox_total, 3), "", "", "",
                        "compare outputs/railways_air_pollutants (5.9 kt on FY2024 "
                        "fuel; scale by ~1.2 for FY2019 fuel)"])

    print("ELK 2019 Pakistan rail (country-masked):")
    for (species, sub), (kt, cells) in sorted(results.items()):
        print("  %-8s %-15s %10.3f kt  (%d cells)" % (species, sub, kt, cells))
    print("  CO2 rail total %.1f kt vs own CY2019 %.1f kt (x%.2f)"
          % (co2_total, own_co2_kt, co2_total / own_co2_kt))


if __name__ == "__main__":
    main()
