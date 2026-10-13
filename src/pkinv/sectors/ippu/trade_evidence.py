"""Is a fiscal year's clinker trade OBSERVED, or merely unobtained? The gate that decides.

WHY A GATE AND NOT A LOOKUP. IPCC Equation 2.1 solves the clinker balance as
production = clinker in cement - imports + exports, so a cement estimate without a trade
term is not a cement estimate with one small piece missing; it is a different quantity. At
the reference year the correction is worth 3,766 kt of clinker, about 2.0 Mt CO2 on a 17.4
Mt category - twelve percent of the number. Omitting it does not add noise, it adds bias in
one direction, because Pakistan exports far more clinker than it imports.

THE ONE FAILURE THIS MODULE EXISTS TO PREVENT. UN Comtrade returns no record for a month in
which nothing was traded AND for a month it has not processed, and the response cannot tell
them apart. Reading silence as zero would manufacture a complete nine-year panel out of an
incomplete one - and would do it in the direction that flatters the inventory, since a
missing export month read as zero lowers inferred domestic production. So silence is never
a number here. It is either PROVED zero against the source's own annual total, or it is
absent.

THE FOUR STATES, and what each one licenses:

  observed        every month of the fiscal year is an affirmative record. The year may be
                  estimated.
  observed_zero   a month with no record whose calendar year's monthly records already sum
                  to that year's annual total - the source itself says nothing more moved.
                  Counts as covered; the year may be estimated.
  bounded         a justified interval estimate carrying its own uncertainty and evidence
                  status. NONE ARE POPULATED. The state exists so that a future bounded
                  estimate has an honest place to live rather than arriving as a silent
                  central value.
  absent          not obtained. The year is NE. It is not zero, it is not interpolated from
                  its neighbours, and it does not enter the annual product, the common-scope
                  trend or any national total.

Usage:  python3 -m pkinv.sectors.ippu.trade_evidence
"""
from __future__ import annotations

from pkinv.activity.store import input_exists as _input_exists
import collections
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows
from pkinv.assets import asset_path

OBSERVED = "observed"
OBSERVED_ZERO = "observed_zero"
BOUNDED = "bounded"
ABSENT = "absent"
STATES = (OBSERVED, OBSERVED_ZERO, BOUNDED, ABSENT)

FLOWS = ("import", "export")
IPPU = asset_path(DATA, "activity", "ippu")
MONTHLY = asset_path(IPPU, "clinker_trade_monthly.csv")
CONTROLS = asset_path(IPPU, "clinker_trade_annual_controls.csv")

# How closely the monthly records must reach the annual control before the year's silent
# months may be read as zero. Comtrade's monthly and annual aggregates are compiled from the
# same declarations but rounded independently, so an exact match is not available; a tenth of
# a percent is far tighter than any month this would be used to fill.
RECONCILIATION_TOLERANCE = 0.001


class TradeNotObserved(Exception):
    """Raised where a caller asks for a number the evidence does not support.

    Deliberately not a return of 0.0: every arithmetic path in this repository would happily
    consume a zero, and the whole point is that this quantity is unknown rather than small.
    """


def _read(path):
    if not _input_exists(path):
        return []
    return read_rows(path, comments=False)


def _months_of(fiscal_end_year):
    """July of the opening year through June of the closing one."""
    start = int(fiscal_end_year) - 1
    return (["%04d-%02d" % (start, m) for m in range(7, 13)] +
            ["%04d-%02d" % (int(fiscal_end_year), m) for m in range(1, 7)])


def monthly_records(path=None):
    """{(month, flow): tonnes} - affirmative records only, never a filled zero."""
    out = {}
    for row in _read(path or MONTHLY):
        out[(row["month"], row["flow"])] = float(row["quantity_t"])
    return out


def annual_controls(path=None):
    """{(calendar_year, flow): tonnes} from the source's own annual frequency."""
    out = {}
    for row in _read(path or CONTROLS):
        out[(str(row["calendar_year"]), row["flow"])] = float(row["quantity_t"])
    return out


def reconciled_years(records=None, controls=None):
    """Calendar years whose monthly records already sum to their annual control.

    In such a year a month with no record is an OBSERVED ZERO: the source's own annual total
    leaves nothing for it to contain. In any other year a silent month is unobtained, and
    saying which of the two it is is the only thing standing between this inventory and a
    fabricated panel.
    """
    records = monthly_records() if records is None else records
    controls = annual_controls() if controls is None else controls
    summed = collections.defaultdict(float)
    for (month, flow), tonnes in records.items():
        summed[(month[:4], flow)] += tonnes
    out = set()
    for key, control in controls.items():
        got = summed.get(key, 0.0)
        if control == 0.0:
            # The source states the year's total is zero, so every month of it is zero.
            if got == 0.0:
                out.add(key)
            continue
        if abs(got - control) / control <= RECONCILIATION_TOLERANCE:
            out.add(key)
    return out


def month_state(month, flow, records=None, reconciled=None):
    records = monthly_records() if records is None else records
    reconciled = reconciled_years(records) if reconciled is None else reconciled
    if (month, flow) in records:
        return OBSERVED
    if (month[:4], flow) in reconciled:
        return OBSERVED_ZERO
    return ABSENT


def resolve(fiscal_end_year, records=None, controls=None):
    """The verdict for one fiscal year: status, the two flow totals, and why.

    A year is covered only when BOTH flows are covered in ALL twelve months. Eleven months
    of exports and a twelfth that is merely unobtained is not an eleven-twelfths year to be
    scaled up; it is a year this inventory cannot estimate.
    """
    records = monthly_records() if records is None else records
    controls = annual_controls() if controls is None else controls
    reconciled = reconciled_years(records, controls)

    months = _months_of(fiscal_end_year)
    detail, totals, missing = {}, {}, []
    for flow in FLOWS:
        states = {m: month_state(m, flow, records, reconciled) for m in months}
        detail[flow] = states
        gaps = sorted(m for m, s in states.items() if s == ABSENT)
        missing.extend("%s %s" % (flow, m) for m in gaps)
        if not gaps:
            totals[flow] = sum(records.get((m, flow), 0.0) for m in months) / 1000.0

    if missing:
        return {
            "fiscal_end_year": int(fiscal_end_year), "status": ABSENT,
            "import_kt": None, "export_kt": None,
            "observed_months": sum(1 for f in FLOWS for s in detail[f].values()
                                   if s == OBSERVED),
            "proved_zero_months": sum(1 for f in FLOWS for s in detail[f].values()
                                      if s == OBSERVED_ZERO),
            "missing_months": len(missing),
            "reason": "no record and no annual control for: %s"
                      % ("; ".join(missing[:6]) + (" (+%d more)" % (len(missing) - 6)
                                                   if len(missing) > 6 else "")),
        }

    proved = sum(1 for f in FLOWS for s in detail[f].values() if s == OBSERVED_ZERO)
    return {
        "fiscal_end_year": int(fiscal_end_year),
        "status": OBSERVED_ZERO if proved else OBSERVED,
        "import_kt": totals["import"], "export_kt": totals["export"],
        "observed_months": sum(1 for f in FLOWS for s in detail[f].values()
                               if s == OBSERVED),
        "proved_zero_months": proved, "missing_months": 0,
        "reason": ("all twenty-four month-flows reported" if not proved else
                   "%d month-flows reported, %d proved zero against the source's annual "
                   "total" % (24 - proved, proved)),
    }


def require(fiscal_end_year, records=None, controls=None):
    """The verdict, or raise. The entry point for anything that needs a NUMBER."""
    verdict = resolve(fiscal_end_year, records, controls)
    if verdict["status"] == ABSENT:
        raise TradeNotObserved(
            "clinker trade for FY%d-%02d is not observed, so no valid cement configuration "
            "exists for that year: %s. It is NE, not zero."
            % (verdict["fiscal_end_year"] - 1, verdict["fiscal_end_year"] % 100,
               verdict["reason"]))
    return verdict


def table(years=range(2016, 2025)):
    return [resolve(y) for y in years]


def main():
    rows = table()
    print("clinker trade evidence, per fiscal year")
    for row in rows:
        label = "FY%d-%02d" % (row["fiscal_end_year"] - 1, row["fiscal_end_year"] % 100)
        if row["status"] == ABSENT:
            print("  %-10s %-14s %s" % (label, row["status"], row["reason"]))
        else:
            print("  %-10s %-14s import %8.3f kt   export %9.3f kt   (%s)"
                  % (label, row["status"], row["import_kt"], row["export_kt"],
                     row["reason"]))
    covered = [r for r in rows if r["status"] != ABSENT]
    print("\n%d of %d fiscal years have an observed trade term; the rest are NE, not zero."
          % (len(covered), len(rows)))


if __name__ == "__main__":
    main()
