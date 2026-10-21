#!/usr/bin/env python3
"""FAOSTAT's managed-soils pools for Pakistan, unrounded, as a public evidence table.

WHY. The managed-soils comparison (pkinv.sectors.agriculture.faostat_nitrogen_flows) compares the
engine's four nitrogen pools with FAOSTAT's four Emissions Totals items. The contribution-evidence
pass of 21 October 2026 had to fall back on a four-row snapshot rounded to 4 dp and transcribed
from this repository's own earlier output, because the FAOSTAT extract it was read from sits in the
restricted layer. That extract is held, and FAOSTAT data are CC BY 4.0, so its Pakistan rows for the
four items can be published as they were received: every element (direct and indirect N2O, total
N2O, CO2e AR5), every year, value, unit, flag and source exactly as FAOSTAT prints them.

Reads:  data/raw/faostat/faostat_emissions_totals_pakistan.csv (Pakistan rows of FAOSTAT's
        Emissions Totals bulk, held in the restricted layer; data/raw/faostat/RETRIEVALS.csv)
Writes: data/sectors/agriculture/evidence/faostat_soils_pools.csv
Usage:  PYTHONPATH=src python3 scripts/ingest_faostat_soils_pools.py [--check]
"""
import argparse
import csv
import hashlib
import os
import sys

from pkinv.assets import asset_path
from pkinv.core.io import write_or_check
from pkinv.paths import DATA

RAW = asset_path(DATA, "raw", "faostat", "faostat_emissions_totals_pakistan.csv")
OUT = asset_path(DATA, "sectors", "agriculture", "evidence", "faostat_soils_pools.csv")
ITEMS = ("5061", "5062", "5063", "5064")
FIELDS = ("area", "area_code_m49", "item_code", "item", "element_code", "element", "year", "unit",
          "value", "flag", "source")
BULK = ("https://bulks-faostat.fao.org/production/Emissions_Totals_E_All_Data_(Normalized).zip "
        "(retrieved 2026-06-30, sha256 d2c47e116553711f7c2fd6b62437db511038fd9bd9ec77815fa69ff7a18a89a9)")


def rows():
    if not os.path.exists(RAW):
        raise SystemExit("%s is not mounted: this ingest reads the restricted layer "
                         "(scripts/overlay.py link)" % RAW)
    with open(RAW, encoding="utf-8-sig", newline="") as handle:
        src = list(csv.DictReader(handle))
    out = []
    for r in src:
        if r["Item Code"] not in ITEMS:
            continue
        out.append({"area": r["Area"], "area_code_m49": r["Area Code (M49)"].lstrip("'"),
                    "item_code": r["Item Code"], "item": r["Item"], "element_code": r["Element Code"],
                    "element": r["Element"], "year": r["Year"], "unit": r["Unit"], "value": r["Value"],
                    "flag": r["Flag"], "source": r["Source"]})
    out.sort(key=lambda r: (r["item_code"], r["element_code"], int(r["year"])))
    if {r["item_code"] for r in out} != set(ITEMS):
        raise SystemExit("the held extract does not carry all four managed-soils items")
    return out


def banner():
    with open(RAW, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    return ("FAOSTAT MANAGED-SOILS POOLS FOR PAKISTAN, AS FAOSTAT PRINTS THEM (CC BY 4.0).",
            "Items 5061 synthetic fertilizers, 5062 manure applied to soils, 5063 manure left on pasture, "
            "5064 crop residues; every element, year, unit and flag of the held extract, values unrounded.",
            "Source: FAOSTAT Emissions Totals bulk %s; Pakistan rows held as "
            "data/raw/faostat/faostat_emissions_totals_pakistan.csv (sha256 %s)." % (BULK, digest),
            "Written by scripts/ingest_faostat_soils_pools.py. A comparator, not independent validation: "
            "FAOSTAT applies Tier 1 defaults to its own activity data.")


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
