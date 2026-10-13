"""The month registry: 108 months, with their real lengths and their disturbances named.

WHY A TABLE AND NOT A FUNCTION, for the same reason data/periods.csv exists. core/monthly.py
computes a fiscal year's twelve YYYYMM keys, and that was enough while a month was something
one product generated for one year. It stops being enough when a row has to REFERENCE a
month: a profile registry keyed on (profile, component, fiscal year, month) needs a month to
be a value with an id and a length, not a string every caller re-derives.

DAYS ARE NOT DECORATION. A continuous emission is proportional to elapsed time, so an
equal-twelfths profile silently claims February emits as much as July - a 10.7 percent error
between the shortest and longest month, on every stream with no seasonal evidence, which is
most of this inventory by mass. The `days` column here is what the days-weighted default
profile divides by, and two of these nine fiscal years contain a leap February.

SPECIAL PERIODS ARE FLAGS, NOT ADJUSTMENTS. Nothing in this pass changes a number because a
month is flagged. What the flag does is refuse: a profile borrowed from an ordinary year may
not cover a month that was not ordinary, because the borrowing assumption - that this month
resembles the same month elsewhere - is exactly what a disturbance breaks. The flagged spans
are the ones an inventory of Pakistan cannot pretend away:

  covid_restrictions   2020-03 .. 2020-06   national lockdown from 24 March 2020; transport
                       fuel, industrial output and electricity demand all move together and
                       none of them recovers within the fiscal year
  covid_recovery       2020-07 .. 2021-06   FY2020-21, a year that is neither the disruption
                       nor the pre-disruption normal
  floods_2022          2022-08 .. 2022-09   the 2022 monsoon floods; a third of the country
                       under water, with agriculture, transport and gas distribution affected
                       on different timescales

Each is a span of calendar months, declared once here rather than rediscovered per sector.

Usage:  python3 -m pkinv.report.months
Writes: data/months.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

import calendar
import csv
import datetime
import os

from pkinv.core import monthly as core_monthly
from pkinv.core import period
from pkinv.paths import DATA
from pkinv.report import periods
from pkinv.core.io import write_table

OUT = asset_path(DATA, "months.csv")

FIELDS = ("month_id", "period_start", "period_end", "days_in_month", "fiscal_year",
          "fiscal_month_number", "calendar_year", "calendar_month",
          "special_period_flag", "special_period_note")

# (first month, last month, flag, note). Inclusive spans, YYYYMM.
SPECIAL_PERIODS = (
    ("202003", "202006", "covid_restrictions",
     "national lockdown from 24 March 2020; transport fuel, industrial output and "
     "electricity demand move together and none recovers within the fiscal year"),
    ("202007", "202106", "covid_recovery",
     "FY2020-21: neither the disruption nor the pre-disruption normal"),
    ("202208", "202209", "floods_2022",
     "the 2022 monsoon floods; agriculture, transport and gas distribution affected on "
     "different timescales"),
)


def _flag(month_id):
    for first, last, flag, note in SPECIAL_PERIODS:
        if first <= month_id <= last:
            return flag, note
    return "", ""


def rows():
    """One row per month of the reporting window, in fiscal order."""
    out = []
    for start_year in range(periods.FIRST_START_YEAR, periods.LAST_START_YEAR + 1):
        fiscal_start, fiscal_end = period.fiscal(start_year)
        label = period.label(fiscal_start, fiscal_end)
        for number, month_id in enumerate(core_monthly.months_for(start_year), 1):
            year, month = int(month_id[:4]), int(month_id[4:])
            days = calendar.monthrange(year, month)[1]
            flag, note = _flag(month_id)
            out.append({
                "month_id": month_id,
                "period_start": datetime.date(year, month, 1).isoformat(),
                "period_end": datetime.date(year, month, days).isoformat(),
                "days_in_month": days,
                "fiscal_year": label,
                "fiscal_month_number": number,
                "calendar_year": year,
                "calendar_month": month,
                "special_period_flag": flag,
                "special_period_note": note,
            })
    return out


def days_in_year(fiscal_start_year, table=None):
    """{month_id: days} for one fiscal year, from the registry rather than from a constant."""
    label = period.label(*period.fiscal(fiscal_start_year))
    table = table if table is not None else rows()
    return {r["month_id"]: int(r["days_in_month"])
            for r in table if r["fiscal_year"] == label}


def main():
    written = rows()
    write_table(OUT, FIELDS, written)
    flagged = [r for r in written if r["special_period_flag"]]
    leap = [r for r in written if r["calendar_month"] == 2 and r["days_in_month"] == 29]
    print("month registry -> %s" % OUT)
    print("  %d months, %s to %s, across %d fiscal years"
          % (len(written), written[0]["month_id"], written[-1]["month_id"],
             len({r["fiscal_year"] for r in written})))
    print("  %d months carry a special-period flag: %s"
          % (len(flagged), ", ".join(sorted({r["special_period_flag"] for r in flagged}))))
    print("  %d leap Februaries (%s) - an equal-twelfths profile loses them"
          % (len(leap), ", ".join(r["month_id"] for r in leap)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
