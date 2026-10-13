#!/usr/bin/env python3
"""Check the hand-entered protein supply series against the held FAOSTAT Food Balance bulk.

data/activity/wastewater/protein.csv is four numbers typed from the FAOSTAT web query
(Pakistan, Grand Total, protein supply quantity in g/capita/day). The register called its
source an "interactive API extract; no fixed document existed". The fixed document is the
Food Balance Sheets bulk, and it is held: data/raw/faostat/
faostat_FoodBalanceSheets_E_All_Data_(Normalized).zip. A bulk that is not held is downloaded
and kept (pkinv.core.retention), never replaced.

This script reads every year the table holds out of the bulk and compares. It writes
nothing: the table is a transcription and stays one; this is its cross-check.

Usage:  python3 scripts/check_faostat_protein.py
"""
import csv
import io
import os
import sys
import zipfile

from pkinv.assets import asset_path
from pkinv.core import retention

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://bulks-faostat.fao.org/production/FoodBalanceSheets_E_All_Data_(Normalized).zip"
TABLE = asset_path(ROOT, "data", "activity", "wastewater", "protein.csv")


def bulk():
    held = "faostat_" + URL.rsplit("/", 1)[1]
    path = os.path.join(retention.RAW, "faostat", held)
    if not os.path.exists(path):
        path = retention.fetch_and_keep(URL, "faostat", held, timeout=600)
    return path


def published():
    """{year: g/capita/day} for Pakistan, Grand Total, from the held bulk."""
    archive = zipfile.ZipFile(bulk())
    name = [n for n in archive.namelist() if n.endswith("(Normalized).csv")][0]
    out = {}
    with archive.open(name) as raw:
        reader = csv.reader(io.TextIOWrapper(raw, encoding="latin-1"))
        at = {k: i for i, k in enumerate(next(reader))}
        for row in reader:
            if (row[at["Area"]] == "Pakistan" and row[at["Item"]] == "Grand Total"
                    and row[at["Element"]].startswith("Protein supply quantity (g/capita/day)")
                    and row[at["Value"]]):
                out[int(row[at["Year"]])] = float(row[at["Value"]])
    return out


def main():
    source = published()
    with open(TABLE, encoding="utf-8", newline="") as handle:
        table = {int(r["year"]): float(r["protein_g_per_capita_day"])
                 for r in csv.DictReader(handle)}
    wrong = ["%d: table %.2f, bulk %s" % (y, v, "%.2f" % source[y] if y in source else "absent")
             for y, v in sorted(table.items()) if round(source.get(y, -1.0), 2) != round(v, 2)]
    for line in wrong:
        print("  ! %s" % line)
    print("FAOSTAT protein supply: %d of %d table years agree with the held bulk"
          % (len(table) - len(wrong), len(table)))
    return 1 if wrong else 0


if __name__ == "__main__":
    sys.exit(main())
