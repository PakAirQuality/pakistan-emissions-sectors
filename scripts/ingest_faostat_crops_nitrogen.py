#!/usr/bin/env python3
"""FAOSTAT's crop nitrogen activities and emissions for Pakistan, unrounded, as a public evidence table.

WHY. The managed-soils comparison (pkinv.sectors.agriculture.faostat_nitrogen_flows) compares the engine's
pools with FAOSTAT's emissions for synthetic fertilizer and crop residues, but not the nitrogen those
emissions are computed from. FAOSTAT's Emissions from Crops domain (GCE) prints it: synthetic-fertilizer N
applied (and the parts that volatilise and leach), crop-residue N content by crop, harvested area, and the
N2O and CH4 computed from them. The bulk was kept on 2026-10-22 (scripts/fetch_contribution_followup_
evidence.py) and FAOSTAT data are CC BY 4.0, so the Pakistan rows for the inventory's years are published
here exactly as received. FAOSTAT's projection years (2030, 2050) are left out.

Reads:  data/raw/faostat/faostat_Emissions_crops_E_All_Data_(Normalized).zip
        (held in the restricted layer; data/raw/faostat/RETRIEVALS.csv)
Writes: data/sectors/agriculture/evidence/faostat_crops_nitrogen.csv
Usage:  PYTHONPATH=src python3 scripts/ingest_faostat_crops_nitrogen.py [--check]
"""
import argparse
import csv
import hashlib
import io
import os
import sys
import zipfile

from pkinv.assets import asset_path
from pkinv.core.io import write_or_check
from pkinv.paths import DATA

RAW = asset_path(DATA, "raw", "faostat", "faostat_Emissions_crops_E_All_Data_(Normalized).zip")
MEMBER = "Emissions_crops_E_All_Data_(Normalized).csv"
OUT = asset_path(DATA, "sectors", "agriculture", "evidence", "faostat_crops_nitrogen.csv")
AREA = "Pakistan"
# calendar years covering the inventory's fiscal years FY2015-16..FY2024-25; FAOSTAT's 2030 and 2050
# projections are not observations of any year and are left out
FIRST_YEAR = 2015
LAST_YEAR = 2025
FIELDS = ("area", "area_code_m49", "item_code", "item", "element_code", "element", "year", "unit",
          "value", "flag", "note")
BULK = "https://bulks-faostat.fao.org/production/Emissions_crops_E_All_Data_(Normalized).zip"


def rows():
    if not os.path.exists(RAW):
        raise SystemExit("%s is not mounted: this ingest reads the restricted layer "
                         "(scripts/overlay.py link)" % RAW)
    out = []
    with zipfile.ZipFile(RAW) as archive, archive.open(MEMBER) as handle:
        # the bulk is ASCII in every Pakistan row; latin-1 never fails on the other areas' names
        for r in csv.DictReader(io.TextIOWrapper(handle, encoding="latin-1", newline="")):
            if r["Area"] != AREA or not FIRST_YEAR <= int(r["Year"]) <= LAST_YEAR:
                continue
            out.append({"area": r["Area"], "area_code_m49": r["Area Code (M49)"].lstrip("'"),
                        "item_code": r["Item Code"], "item": r["Item"], "element_code": r["Element Code"],
                        "element": r["Element"], "year": r["Year"], "unit": r["Unit"], "value": r["Value"],
                        "flag": r["Flag"], "note": r["Note"]})
    out.sort(key=lambda r: (int(r["item_code"]), r["element_code"], int(r["year"])))
    if not out:
        raise SystemExit("the held bulk carries no %s rows for %d-%d" % (AREA, FIRST_YEAR, LAST_YEAR))
    return out


def banner():
    with open(RAW, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    return ("FAOSTAT EMISSIONS FROM CROPS (GCE) FOR PAKISTAN, AS FAOSTAT PRINTS IT (CC BY 4.0).",
            "Every item and element (synthetic-fertilizer N applied, volatilised and leached; crop-residue N; "
            "harvested area; N2O and CH4), years %d-%d; values unrounded; projections left out." % (FIRST_YEAR, LAST_YEAR),
            "Source: FAOSTAT bulk %s, held as data/raw/faostat/faostat_Emissions_crops_E_All_Data_(Normalized).zip "
            "(sha256 %s). Its size differs from the bulk catalogue's printed size (the FAOSTAT versions table "
            "beside this one)." % (BULK, digest),
            "Written by scripts/ingest_faostat_crops_nitrogen.py. FAOSTAT's own Tier 1 estimates, not observations.")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="re-derive and report a difference; write nothing")
    args = ap.parse_args(argv)
    result = rows()
    code = write_or_check(OUT, FIELDS, result, check=args.check, banner=banner(), lineterminator="\n")
    if not args.check:
        print("wrote %s (%d rows)" % (os.path.relpath(OUT, os.path.dirname(DATA)), len(result)))
    return code


if __name__ == "__main__":
    sys.exit(main())
