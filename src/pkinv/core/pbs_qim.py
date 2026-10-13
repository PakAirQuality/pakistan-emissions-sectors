"""PBS Table 2 monthly physical output, as a seasonal shape for the sectors that make things.

WHY THIS IS IN CORE. Two sectors read the same publication for the same reason: `ippu` shapes
clinker calcination on cement output, and `industry` shapes steel and glass combustion on
billet and sheet output. One reader, because four copies of a fiscal-year mapping is four
things to drift apart, which this project has watched happen twice with declared tables.

WHAT THE EDITIONS PUBLISH, and how it differs from the OCAC panel beside it. These are DIRECT
monthly quantities, not cumulative year-to-date columns, so nothing is differenced and there
is no first-month special case. Each fiscal edition covers its own July-June year, so a
reference year takes its shape from ITS OWN months rather than borrowing one.

THE PROFILE IS A SHAPE, NEVER A MAGNITUDE. Every consumer normalises twelve shares to one and
applies them to its own annual control, so a published quantity could be wrong by any amount
without moving the inventory. Only the distribution in time comes from here.

WHAT IT IS AND IS NOT. Physical output of a PRODUCT in the month it was made. For cement that
tracks the kiln closely, because clinker is not stockpiled for long - but production and
calcination are different processes, and a month of output is not a month of calcination. That
is why what this feeds is T2, "reconstructed from a monthly administrative record", and never
T1. Refinery output is production evidence and is never a road-transport profile.

INDEX ROWS ARE REFUSED, NOT SILENTLY AVERAGED. Table 2 mixes quantity rows with group INDEX
rows on the 2015-16=100 base, whose annual column is the mean of the twelve rather than their
sum. The ingest marks which is which; asking this module for an index row raises rather than
returning a shape, because an index and a tonnage are not the same kind of number and the
difference is invisible once it has been normalised to twelve shares.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.paths import DATA
from pkinv.activity.store import read_rows

PANEL = asset_path(DATA, "activity", "monthly", "pbs_qim_month_item.csv")

# The QIM serial numbers this inventory reads, by the name the ingest gives them.
CEMENT = "cement"
BILLETS = "billets_ingots"
GLASS = "glass_plates_sheets"
# The 1-3 group row is effectively sugar alone (bakery and confectionery print
# zero in every held month); its months are the crushing season and time the
# mills' bagasse combustion (rc30, the eighteenth review's open-data fix).
SUGAR = "sugar"


def _panel():
    return read_rows(PANEL)


def series(canonical_item, fy_start, rows=None):
    """{YYYYMM: quantity} for one item in one fiscal year, or {} if the panel lacks it.

    An EMPTY DICT rather than an exception for the ordinary "this year is not covered" case,
    and an exception only for the two things that mean something is wrong: an index row asked
    for as a quantity, and a year present but incomplete. A caller with a second source needs
    to distinguish "not here" from "here and broken", and an exception thrown past it discards
    the second source too - the bug that lost power its PBS generation for six years.
    """
    rows = rows if rows is not None else _panel()
    matched = [r for r in rows
               if r["canonical_item"] == canonical_item
               and int(r["fiscal_year_start"]) == fy_start]
    if not matched:
        return {}
    kinds = {r["row_kind"] for r in matched}
    if kinds != {"quantity"}:
        raise ValueError(
            "%s FY%d-%02d carries row kind(s) %s: an index row's annual column is the MEAN of "
            "its twelve months, not their sum, and it must not be read as a tonnage"
            % (canonical_item, fy_start, (fy_start + 1) % 100, sorted(kinds)))
    out = {r["month"]: float(r["quantity"]) for r in matched}
    expected = core_monthly.months_for(fy_start)
    missing = set(expected) - set(out)
    if missing:
        raise KeyError("%s FY%d-%02d is present but missing month(s) %s - a partial year "
                       "cannot be normalised into twelve shares"
                       % (canonical_item, fy_start, (fy_start + 1) % 100, sorted(missing)))
    return out


def covers(canonical_item, fy_start, rows=None):
    """Whether the panel can shape this item-year at all.

    Answered directly rather than by catching an exception, so that a caller choosing between
    this and another real source does not have to make that choice inside an except block.
    """
    try:
        return bool(series(canonical_item, fy_start, rows))
    except (KeyError, ValueError):
        return False


def profile(canonical_item, fy_start, rows=None):
    """{YYYYMM: share summing to 1} - the shape, ready for apply_profile."""
    return core_monthly.normalise(series(canonical_item, fy_start, rows))


def profile_or_borrowed(canonical_item, fy_start, fallback, fallback_method="T3",
                        rows=None):
    """(shares, temporal_method, own_year) - this year's own months where they exist.

    The degradation is in the open and the return says which happened, because the difference
    between a year's own observed months and a shape imported from another year is exactly
    what a T-class is for. A caller that could not tell them apart would publish T2 for a
    borrowed shape, which is the claim this project most wants not to make.
    """
    if covers(canonical_item, fy_start, rows):
        return profile(canonical_item, fy_start, rows), "T2", True
    return fallback, fallback_method, False
