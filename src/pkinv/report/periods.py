"""The period registry: the nine reporting years, written down rather than recomputed.

WHY A TABLE AND NOT A FUNCTION. core/period.py already knows everything here - the three
year conventions, the two period kinds, the July-June boundary - and every module calls it
to turn its own integer YEAR into dates. That worked while a period was something each
sector computed for itself. It stops working the moment a row has to REFERENCE a period:
an atomic table keyed on (period, component, gas, configuration, geography) needs a period
to be a value with an id, not a function call, or the key is a string that different
callers spell differently.

So this materialises what period.py computes. It invents nothing: `period_id`, the dates
and the label all come from `period.fiscal()` and `period.label()`, and a test asserts the
table equals what the functions return, so the file cannot drift from the code that
defines it.

THE CONVENTION COLUMN IS THE POINT. Three sectors number a fiscal year by the calendar
year it opens in and seven by the year it closes in, and that ambiguity has already put a
contradiction into a shipped paper about which year the power sector reported. A period_id
is unambiguous by construction - FY2023-24 is one object with two dates - and the
convention column records which integer each sector would have used for it, so a reader
converting between the two never has to guess.

Usage:  python3 -m pkinv.report.periods
Writes: data/periods.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

import csv
import os

from pkinv.core import period
from pkinv.core.reporting_window import FIRST_FY_START, CORE_LAST_FY_START, REFERENCE_FY_START
from pkinv.paths import DATA
from pkinv.core.io import write_table

OUT = asset_path(DATA, "periods.csv")

# The reporting window the annual product covers: FY2015-16 through FY2023-24, named by the
# calendar year each fiscal year OPENS in.
FIRST_START_YEAR, LAST_START_YEAR = FIRST_FY_START, CORE_LAST_FY_START

FIELDS = ("period_id", "period_start", "period_end", "time_basis", "days",
          "fiscal_start_year", "fiscal_end_year", "is_reference", "note")


def rows():
    out = []
    for start_year in range(FIRST_START_YEAR, LAST_START_YEAR + 1):
        start, end = period.fiscal(start_year)
        out.append({
            "period_id": period.label(start, end),
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "time_basis": "fiscal-july-june",
            # Real days, not a nominal 365: a continuous emission is days-weighted, and a
            # leap year is four hours of national emissions that a nominal year loses.
            "days": (end - start).days + 1,
            "fiscal_start_year": start_year,
            "fiscal_end_year": start_year + 1,
            "is_reference": start_year == REFERENCE_FY_START,
            "note": ("the reference period every sector reports"
                     if start_year == REFERENCE_FY_START else
                     "series period; sector coverage is declared per cell in the "
                     "coverage matrix"),
        })
    return out


def main():
    written = rows()
    write_table(OUT, FIELDS, written)
    print("period registry -> %s" % OUT)
    print("  %d periods, %s to %s, reference %s"
          % (len(written), written[0]["period_id"], written[-1]["period_id"],
             next(r["period_id"] for r in written if r["is_reference"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
