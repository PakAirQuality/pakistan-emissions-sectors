"""Derive the harvest-session table the burning windows read, from the FAO crop calendar.

WHY A TABLE STANDS BETWEEN THE ENGINE AND THE DOCUMENT. The agriculture monthly layer's
burning windows used to parse FAO's Pakistan crop-calendar JSON directly, every run. That
JSON is a publisher document held under data/raw with no stated redistribution terms, so a
validation package cannot carry it - and without it the monthly layer could not run at all.
The rule the reviewer stated is the right one: when a raw source is omitted, its CONSUMED
DERIVATIVE, its immutable hash, its acquisition record and the processing code must still be
present. This script is the processing code; the table it writes is the consumed derivative;
the JSON's hash is in the raw-data manifest and the package's source manifest.

The table is a transcription in the same sense as every other data/activity file: one row
per FAO harvest session for the five crops the burning ledger prices, month and day of the
early and late harvest exactly as the JSON states them. burn_windows.harvest_sessions() reads
this table; burn_windows.sessions_from_calendar() is the parser this script uses, and
tests/test_burn_windows.py asserts the two agree whenever the JSON is present.

Writes: data/activity/agriculture/fao_harvest_sessions.csv
"""

from pkinv.assets import asset_path
import os
import sys

from pkinv.core.io import write_table
from pkinv.paths import ROOT
from pkinv.sectors.agriculture import burn_windows

OUT = asset_path(ROOT, "data", "activity", "agriculture", "fao_harvest_sessions.csv")
FIELDS = ("crop", "crop_fao", "session", "early_month", "early_day", "late_month", "late_day")


def main():
    if not os.path.exists(burn_windows.CALENDAR):
        print("the FAO calendar JSON is not held here (%s); the committed table stands"
              % os.path.relpath(burn_windows.CALENDAR, ROOT))
        return 0
    rows = []
    for crop, crop_fao, session, early, late in burn_windows.sessions_from_calendar():
        rows.append({"crop": crop, "crop_fao": crop_fao, "session": session,
                     "early_month": early[0], "early_day": early[1],
                     "late_month": late[0], "late_day": late[1]})
    write_table(OUT, FIELDS, rows, banner=[
        "FAO/GIEWS crop calendar, Pakistan: the harvest sessions of the five crops the burning",
        "ledger prices, transcribed by scripts/derive_fao_harvest_sessions.py from",
        "data/raw/fao_crop_calendar/Pakistan_crop_calendar.json (hash in the raw-data manifest).",
        "Read by pkinv.sectors.agriculture.burn_windows; the JSON itself is not redistributed."])
    print("FAO harvest sessions -> %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(rows)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
