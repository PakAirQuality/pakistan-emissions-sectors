#!/usr/bin/env python3
"""Sanitation pathway shares by year, from the held WHO/UNICEF JMP household workbook.

WHY THIS EXISTS. data/sectors/waste/activity/wastewater/sanitation_shares.csv held ONE year
(2023), typed by hand from the workbook's Estimates sheet, and wastewater.py held that year for
every year of the national series ("an explicit HOLD, not a default ... when the WHO/UNICEF
annual series is transcribed, this becomes a year lookup"). The workbook has carried the annual
series all along: one row per year and setting from 2000 to 2030. The 2019 Refinement's
nitrous-oxide method allocates nitrogen to treatment pathways, so the pathway shares are now
activity data for two gases and a held year is no longer good enough.

WHAT IT READS. Sheet `Estimates`, the five columns that partition the population by sanitation
facility: sewer connection, septic tanks, latrines and other, unimproved sanitation, open
defecation. Urban, Rural and Total, calendar years 2015 to 2023, which serve fiscal years
FY2015-16 to FY2023-24 on the fiscal-start convention the 2023 row has always used.

WHAT IT REFUSES. A header that is not where it is expected; a non-numeric cell in a wanted row;
five shares that do not sum to 100 within the rounding of one-decimal cells (0.3); and any
difference from the three 2023 rows the table already held, which were typed independently.

Usage:  python3 scripts/ingest_jmp_sanitation.py            write the table
        python3 scripts/ingest_jmp_sanitation.py --check    compare, write nothing
Writes: data/sectors/waste/activity/wastewater/sanitation_shares.csv
"""
import csv
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path                 # noqa: E402
from pkinv.core import retention                    # noqa: E402
from pkinv.paths import DATA                        # noqa: E402

WORKBOOK = os.path.join(ROOT, "data", "raw", "who_unicef_jmp",
                        "JMP_2025_PAK_Pakistan_household.xlsx")
OUT = asset_path(DATA, "activity", "wastewater", "sanitation_shares.csv")
SHEET = "Estimates"
YEARS = range(2015, 2024)
SETTINGS = ("Urban", "Rural", "Total")
# output column -> the header the workbook prints over it
COLUMNS = (("open_defecation_pct", "Open defecation"),
           ("latrines_and_other_pct", "Latrines and other"),
           ("septic_tanks_pct", "Septic tanks"),
           ("sewer_connection_pct", "Sewer connection"),
           ("unimproved_pct", "Unimproved sanitation"))
FIELDS = ["year", "setting"] + [c for c, _h in COLUMNS] + ["source"]
SUM_TOLERANCE = 0.3
# The three rows the table held before this script existed, typed by hand in August 2026.
HELD_2023 = {"Urban": (0.6, 8.4, 18.0, 62.6, 10.3), "Rural": (14.4, 29.9, 34.8, 8.8, 12.2),
             "Total": (9.1, 21.7, 28.4, 29.3, 11.5)}
SOURCE = ("WHO/UNICEF Joint Monitoring Programme, Pakistan household country file "
          "(washdata.org/data/country/PAK/household/download), Estimates sheet")


def read():
    import openpyxl
    book = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    rows = list(book[SHEET].iter_rows(values_only=True))
    header = next((i for i, r in enumerate(rows[:12])
                   if r and r[0] == "Country" and r[1] == "Year"), None)
    if header is None:
        raise SystemExit("%s: no Country/Year header in the first rows of %s"
                         % (os.path.basename(WORKBOOK), SHEET))
    names = [str(c).replace("\n", " ").strip() if c is not None else ""
             for c in rows[header]]
    index = {}
    for column, printed in COLUMNS:
        hits = [i for i, n in enumerate(names) if n == printed]
        if len(hits) != 1:
            raise SystemExit("header %r appears %d times in %s" % (printed, len(hits), SHEET))
        index[column] = hits[0]
    out = []
    for r in rows[header + 1:]:
        if not r or r[0] != "Pakistan" or r[2] not in SETTINGS:
            continue
        year = int(r[1])
        if year not in YEARS:
            continue
        values = []
        for column, printed in COLUMNS:
            cell = r[index[column]]
            if not isinstance(cell, (int, float)):
                raise SystemExit("%d %s: %s is %r, not a number" % (year, r[2], printed, cell))
            values.append(float(cell))
        if abs(sum(values) - 100.0) > SUM_TOLERANCE:
            raise SystemExit("%d %s: the five shares sum to %.1f" % (year, r[2], sum(values)))
        out.append((year, r[2], values))
    wanted = {(y, s) for y in YEARS for s in SETTINGS}
    got = {(y, s) for y, s, _v in out}
    if got != wanted:
        raise SystemExit("missing rows: %s" % sorted(wanted - got))
    for setting, held in HELD_2023.items():
        read_back = next(v for y, s, v in out if y == 2023 and s == setting)
        if tuple(read_back) != held:
            raise SystemExit("2023 %s: the workbook reads %s, the table held %s"
                             % (setting, read_back, held))
    order = {s: i for i, s in enumerate(SETTINGS)}
    return sorted(out, key=lambda t: (t[0], order[t[1]]))


def render(rows):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(FIELDS)
    for year, setting, values in rows:
        note = SOURCE
        if setting == "Total":
            note += (". Carried for cross-checking the urban/rural weighting; the sector "
                     "uses the urban and rural rows.")
        writer.writerow([year, setting] + ["%g" % v for v in values] + [note])
    return buffer.getvalue()


def main():
    text = render(read())
    if "--check" in sys.argv[1:]:
        return retention.report_check("JMP sanitation shares", OUT, text)
    with open(OUT, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)
    print("JMP sanitation shares -> %s (%d rows, %d-%d)"
          % (os.path.relpath(OUT, ROOT), text.count("\n") - 1, min(YEARS), max(YEARS)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
