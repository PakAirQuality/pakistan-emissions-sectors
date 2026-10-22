#!/usr/bin/env python3
"""FAOSTAT's manure-nitrogen activities for Pakistan, unrounded, as a public evidence table.

WHY. The managed-soils comparison (pkinv.sectors.agriculture.faostat_nitrogen_flows) reads FAOSTAT's
emissions for manure applied to soils (item 5062) and left on pasture (5063), but not the nitrogen
those emissions are computed from. The contribution-evidence review of 21 October 2026 asked for the
manure-handling evidence behind them. FAOSTAT's Livestock Manure domain (EMN) prints it: nitrogen
excreted, treated in manure management, lost from it, applied to soils and left on pasture, by
species, with the head counts it starts from. The bulk is held (scripts/fetch_cooking_manure_evidence.py,
2026-10-21) and FAOSTAT data are CC BY 4.0, so the Pakistan rows for the inventory's fiscal years are
published here exactly as received: every item, element, unit and flag, values unrounded.

What the table says and does not. FAOSTAT's pools do not close on excretion: excreted N less treated
N less pasture N is about 14-15% of excretion in every year here. FAOSTAT's EMN methodological note
(kept 2026-10-22) says why: the N in manure burned for fuel is counted half as pasture (the urine) and
half in neither pool, with the IPCC 2006 Indian-subcontinent defaults (burned for fuel 51-55% of cattle
and buffalo N; data/sectors/agriculture/evidence holds the transcribed rows). The remainder is a Tier 1
default, not an observation of dung burned in Pakistan.

Reads:  data/raw/faostat/faostat_Environment_LivestockManure_E_All_Data_(Normalized).zip
        (held in the restricted layer; data/raw/faostat/RETRIEVALS.csv)
Writes: data/sectors/agriculture/evidence/faostat_manure_nitrogen.csv
Usage:  PYTHONPATH=src python3 scripts/ingest_faostat_manure_nitrogen.py [--check]
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

RAW = asset_path(DATA, "raw", "faostat", "faostat_Environment_LivestockManure_E_All_Data_(Normalized).zip")
MEMBER = "Environment_LivestockManure_E_All_Data_(Normalized).csv"
OUT = asset_path(DATA, "sectors", "agriculture", "evidence", "faostat_manure_nitrogen.csv")
AREA = "Pakistan"
# calendar years covering the inventory's fiscal years FY2015-16..FY2024-25 that FAOSTAT has printed
FIRST_YEAR = 2015
FIELDS = ("area", "area_code_m49", "item_code", "item", "element_code", "element", "year", "unit",
          "value", "flag", "note")
BULK = "https://bulks-faostat.fao.org/production/Environment_LivestockManure_E_All_Data_(Normalized).zip"


def rows():
    if not os.path.exists(RAW):
        raise SystemExit("%s is not mounted: this ingest reads the restricted layer "
                         "(scripts/overlay.py link)" % RAW)
    out = []
    with zipfile.ZipFile(RAW) as archive, archive.open(MEMBER) as handle:
        # the bulk is ASCII in every Pakistan row; latin-1 never fails on the other areas' names
        for r in csv.DictReader(io.TextIOWrapper(handle, encoding="latin-1", newline="")):
            if r["Area"] != AREA or int(r["Year"]) < FIRST_YEAR:
                continue
            out.append({"area": r["Area"], "area_code_m49": r["Area Code (M49)"].lstrip("'"),
                        "item_code": r["Item Code"], "item": r["Item"], "element_code": r["Element Code"],
                        "element": r["Element"], "year": r["Year"], "unit": r["Unit"], "value": r["Value"],
                        "flag": r["Flag"], "note": r["Note"]})
    out.sort(key=lambda r: (int(r["item_code"]), r["element_code"], int(r["year"])))
    if not out:
        raise SystemExit("the held bulk carries no %s rows from %d" % (AREA, FIRST_YEAR))
    return out


def banner():
    with open(RAW, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    return ("FAOSTAT LIVESTOCK MANURE (EMN) FOR PAKISTAN, AS FAOSTAT PRINTS IT (CC BY 4.0).",
            "Every item (species and aggregates), element (head, and kg N excreted, treated, lost, applied to "
            "soils, left on pasture, volatilised, leached), year from %d, unit and flag; values unrounded." % FIRST_YEAR,
            "Source: FAOSTAT bulk %s, held as data/raw/faostat/faostat_Environment_LivestockManure_E_All_Data_"
            "(Normalized).zip (sha256 %s)." % (BULK, digest),
            "Written by scripts/ingest_faostat_manure_nitrogen.py. The nitrogen elements are FAOSTAT's own Tier 1 estimates "
            "(flag E) on official or imputed head counts (A, I), not observations; excreted less treated less pasture N "
            "is the N FAOSTAT assigns to neither pool.")


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
