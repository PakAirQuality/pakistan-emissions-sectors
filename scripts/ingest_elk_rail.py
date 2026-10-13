#!/usr/bin/env python3
"""Consumed derivative of the ELK 2019 rail layers over Pakistan (rc41).

Reads:  sources/ELK/ELK_{CO2-rep,NOx}_land_rail-{passenger,freight}_2019_*_annual.nc
        (registered in data/raw_manifest.csv, not shipped: 26 MB each)
Writes: data/activity/railways/elk_rail_pak_2019.csv

The railways ELK crosscheck (pkinv.sectors.railways.gis.elk_crosscheck) summed the ELK
cells inside Pakistan's ADM raster straight from the netCDFs; the validation package
registers the documents without shipping them, so the crosscheck's rebuild in the package
wrote a one-row file and the artifact inventory that records its size could not
reproduce. The crosscheck now reads THIS table - the country-masked kt/yr and cell count
per (species, subsector), at full float precision - and this script proves the table
against the documents wherever they are held. Deterministic; --check re-derives and diffs
(write_or_check discipline); exit 3 when the documents are not held.

Usage:  python3 scripts/ingest_elk_rail.py [--check]
"""
import glob
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pkinv.assets import asset_path

from pkinv.core import documents  # noqa: E402
from pkinv.core.io import write_or_check  # noqa: E402
from pkinv.sectors.railways.gis import elk_crosscheck as elk  # noqa: E402

FIELDS = ("species", "subsector", "elk_pak_kt_2019", "cells", "document")


def main(check=False):
    from pkinv.core.gis.grid import build_grid
    found = sorted(glob.glob(asset_path(elk.ELK_DIR, "ELK_*_land_rail-*_2019_*_annual.nc")))
    if not found:
        print("documents not held: %s" % documents.relative(elk.ELK_DIR))
        return 3
    grid = build_grid()
    rows = []
    for species, varname in elk.SPECIES.items():
        for sub in ("rail-passenger", "rail-freight"):
            paths = glob.glob(asset_path(
                elk.ELK_DIR, "ELK_%s_land_%s_2019_*_annual.nc" % (species, sub)))
            if not paths:
                continue
            kt, cells = elk.pakistan_total_kt(paths[0], varname, grid)
            rows.append({"species": species, "subsector": sub,
                         "elk_pak_kt_2019": repr(float(kt)), "cells": cells,
                         "document": documents.relative(paths[0])})
    banner = [
        "CONSUMED DERIVATIVE (rc41): ELK 2019 rail emissions summed over the cells whose",
        "centres fall inside Pakistan's ADM raster, per species and subsector, at full float",
        "precision - what pkinv.sectors.railways.gis.elk_crosscheck used to compute from the",
        "netCDFs directly (sources/ELK/, registered in data/raw_manifest.csv, not shipped).",
        "sha256 of the documents: " + "; ".join(
            "%s %s" % (os.path.basename(p), documents.digest(p, quiet=True)[:16]) for p in found),
        "written by scripts/ingest_elk_rail.py; --check re-derives it wherever the documents are held",
    ]
    return write_or_check(elk.ELK_TABLE, list(FIELDS), rows, check=check, banner=banner,
                          lineterminator="\n")


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        raise SystemExit(main(check="--check" in sys.argv))
