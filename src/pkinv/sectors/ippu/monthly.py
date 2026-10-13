"""Cement calcination, resolved into the twelve months of the reference year's OWN output.

WHAT CHANGED, AND WHY IT MATTERED MORE THAN EXPECTED. This module used to borrow a CALENDAR
2022 shape into FY2023-24, declared T3, because the only QIM edition held was a twelve-month
calendar window transcribed by hand from two fiscal files. All nine fiscal editions are now
parsed (scripts/ingest_pbs_qim.py), so the reference year takes its shape from its own months
and the borrowing is gone.

The borrowed shape was not a small error. Calendar 2022 peaks at 2.27 times its trough;
FY2023-24 actually peaks at 1.48 times its own. Importing the earlier year overstated cement's
seasonality by roughly half and moved single months by up to 3.1 percentage points of the
year - July and August were understated by 2.5 and 2.9 points, June overstated by 3.1. The
borrowed shape was a defensible choice while it was the only one; it was also wrong.

THE CLASS FOLLOWS THE EVIDENCE, IN BOTH DIRECTIONS. An own-year administrative record is T2 -
"reconstructed from a monthly administrative record" - and never T1, because output and
calcination are different processes however closely they track. Where the panel cannot serve a
year the borrowed shape remains, still declared T3, and `profile_or_borrowed` returns which of
the two happened rather than leaving the caller to assume.

WHY A SHAPE AT ALL. Cement output is genuinely seasonal in Pakistan: construction slows in the
monsoon and in the coldest weeks. A flat profile would assert that this does not happen, which
is a worse error than either shape.

Usage:  python3 -m pkinv.sectors.ippu.monthly
Writes: outputs/ippu_monthly_2024.csv
"""
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.core import pbs_qim
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.ippu import engine
from pkinv.sectors.ippu.data import IppuData
from pkinv.assets import asset_path

FY_START = 2023
QIM = asset_path(DATA, "activity", "ippu", "cement_monthly_2022.csv")
OUT = asset_path(OUTPUTS, "ippu_monthly_2024.csv")
OWN_YEAR_BASIS = ("PBS QIM monthly cement output, the reference year's OWN fiscal months; the "
                  "annual clinker magnitude is unchanged and only the twelve shares come "
                  "from it")
BORROWED_BASIS = ("PBS QIM monthly cement output, CALENDAR 2022 - a borrowed shape used only "
                  "where the fiscal panel cannot serve the year; the magnitude is unchanged "
                  "and only the twelve shares come from the earlier year")


def borrowed_shape(fy_start=FY_START):
    """{YYYYMM of the reference year: share}, mapped month-of-year from the 2022 series."""
    by_month_of_year = {}
    for r in _activity_rows(QIM, comments=False):
        by_month_of_year[int(r["month"].split("-")[1])] = float(r["cement_kt"])
    missing = set(range(1, 13)) - set(by_month_of_year)
    if missing:
        raise KeyError("the QIM series is missing month(s) %s" % sorted(missing))
    weights = {}
    for key in core_monthly.months_for(fy_start):
        weights[key] = by_month_of_year[int(key[4:])]
    return core_monthly.normalise(weights)


def shape(fy_start=FY_START):
    """(shares, temporal_method, basis, own_year) - this year's own months where they exist."""
    shares, method, own = pbs_qim.profile_or_borrowed(
        pbs_qim.CEMENT, fy_start, borrowed_shape(fy_start), fallback_method="T3")
    return shares, method, (OWN_YEAR_BASIS if own else BORROWED_BASIS), own


FLAT_BASIS = ("flat (days-weighted): no monthly production or sales record reaches this stream (NFDC prints "
              "annual production; OCAC's non-energy table is annual) - a declared assumption, T4")
BILLETS_BASIS = ("PBS QIM monthly billets and ingots, the year's OWN fiscal months; the annual "
                 "tonnage is unchanged and only the twelve shares come from it")


def profile_for_component(fy_start=FY_START):
    """(profile_for, method_for, basis_for): each activated category rides its own record.
    Cement keeps its QIM cement months; steel its QIM billet months (T2 where the year is
    covered); ammonia and lubricants are flat, declared T4."""
    cement_shares, cement_method, cement_basis, _own = shape(fy_start)
    # a continuous emission with no monthly record is DAYS-WEIGHTED flat (July emits 31/366 of
    # the year, not one twelfth) - the convention the all-years layer applies to every T4 stream
    flat = core_monthly.days_weighted_profile(fy_start)
    billet_shares, billet_method, _b = pbs_qim.profile_or_borrowed(
        pbs_qim.BILLETS, fy_start, flat, fallback_method="T4")

    def profile_for(c):
        if c["category"] == engine.steel.CATEGORY:
            return billet_shares
        if c["category"] in (engine.ammonia.CATEGORY, engine.lubricants.CATEGORY):
            return flat
        return cement_shares

    def method_for(c, _month):
        if c["category"] == engine.steel.CATEGORY:
            return billet_method
        if c["category"] in (engine.ammonia.CATEGORY, engine.lubricants.CATEGORY):
            return "T4"
        return cement_method

    def basis_for(c):
        if c["category"] == engine.steel.CATEGORY:
            return BILLETS_BASIS if billet_method == "T2" else FLAT_BASIS
        if c["category"] in (engine.ammonia.CATEGORY, engine.lubricants.CATEGORY):
            return FLAT_BASIS
        return cement_basis
    return profile_for, method_for, basis_for


def rows(data=None, fy_start=FY_START):
    data = data if data is not None else IppuData()
    components = engine.build_components(data)
    profile_for, method_for, basis_for = profile_for_component(fy_start)
    return components, core_monthly.apply_profile(
        components, None, fy_start, temporal_method=method_for, profile_for=profile_for,
        basis=basis_for)


def main():
    components, month_rows = rows()
    core_monthly.write_layer(OUT, month_rows, components)
    totals = core_monthly.month_totals(month_rows)
    hi, lo = max(totals, key=totals.get), min(totals, key=totals.get)
    _shares, method, _basis, own = shape()
    print("ippu monthly layer -> %s" % OUT)
    print("  %d rows; closes exactly" % len(month_rows))
    print("  shape: %s (%s)"
          % ("the reference year's own QIM months" if own
             else "BORROWED from calendar 2022 - the fiscal panel does not serve this year",
             method))
    print("  peaks %s and troughs %s, a factor of %.2f" % (hi, lo, totals[hi] / totals[lo]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
