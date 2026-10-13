"""Reference periods: what twelve months a sector's number actually describes.

WHY THIS EXISTS. Every sector declared an integer YEAR and none of them declared what it
meant. Power and aviation used the year the fiscal year OPENS in, so 2023 meant July 2023 to
June 2024. Railways, residential, industry, IPPU and fugitives used the year it CLOSES in, so
2024 meant the same twelve months. Waste used a calendar year. Nothing enforced any of it,
nothing converted between them, and the national manuscript ended up contradicting its own
results table about which year the power sector reported - a defect that survived a full
release because an integer cannot be wrong about its own meaning.

An integer year is not a period. This module makes the period explicit, so a released row
answers "which twelve months?" without a reader consulting the code, and so the two
conventions can coexist honestly instead of colliding silently. Sectors keep their own YEAR
key - renumbering ten sectors would break every output filename and every anchored figure for
no gain - and declare the convention beside it:

    YEAR_CONVENTION = "fiscal-end"      # 2024 means July 2023 - June 2024
    PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

A contract test then re-derives the dates from the year and the convention, so a sector
cannot declare a period its own year does not support.

Pakistan's fiscal year runs July to June. That is the July of FISCAL_START_MONTH below, and
it is a property of the country's statistics rather than of this software, which is why it is
a module constant and not a parameter.
"""
import datetime

FISCAL_START_MONTH = 7

CONVENTIONS = {
    "fiscal-start": "YEAR is the calendar year the July-June fiscal year opens in",
    "fiscal-end": "YEAR is the calendar year the July-June fiscal year closes in",
    "calendar": "YEAR is a January-December calendar year",
}

# NOT EVERY ACTIVITY DATUM IS A FLOW OVER A PERIOD. Fuel sold, waste generated and crops
# harvested accumulate across twelve months. A livestock herd does not: the PBS 7th
# Agricultural Census counted animals once, and enteric fermentation - the single largest
# category in this inventory - rides that count. Giving it a twelve-month span asserts a
# basis the source does not have, and the difference matters downstream, because a flow can
# be spread over months by a seasonal profile and a stock cannot.
#
# The distinction is already visible in the data and was invisible in the contract:
# data/activity/livestock_2024.csv carries head_value beside head_following_year - the
# enumeration and the Economic Survey's fiscal-year projection - and selects the census.
#
# No precise enumeration date is published in the material held here, so a row declares the
# KIND of its activity period and its year; it does not invent a day.
PERIOD_KINDS = {
    "span": "a flow accumulated over the reporting period",
    "enumeration": "a stock counted at one time, not accumulated over the period",
}


def fiscal(start_year):
    """The July-June fiscal year opening in `start_year`, as (start, end) dates."""
    return (datetime.date(start_year, FISCAL_START_MONTH, 1),
            datetime.date(start_year + 1, FISCAL_START_MONTH, 1) - datetime.timedelta(days=1))


def calendar(year):
    return datetime.date(year, 1, 1), datetime.date(year, 12, 31)


def from_year(year, convention):
    """(start, end) for a sector's declared year under its declared convention."""
    if convention == "fiscal-start":
        return fiscal(year)
    if convention == "fiscal-end":
        return fiscal(year - 1)
    if convention == "calendar":
        return calendar(year)
    raise ValueError("unknown year convention %r (expected one of %s)"
                     % (convention, sorted(CONVENTIONS)))


def file_suffix(year, convention):
    """The file-safe period name: (2023, "fiscal-start") and (2024, "fiscal-end")
    both return "fy2023_24"; calendar years return "cy2024". Derived from the same
    from_year() the contract test checks, so a filename can never disagree with the
    declared period - which is the point of renaming away the bare-year suffixes
    the tenth review flagged (aviation_totals_2023.csv and power_totals_2023.csv
    described the same twelve months as the _2024 files beside them)."""
    start, end = from_year(year, convention)
    if convention == "calendar":
        return "cy%d" % start.year
    return "fy%d_%02d" % (start.year, end.year % 100)


def label(start, end):
    """'FY2023-24' or 'CY2023' - the form a reader recognises."""
    if start.month == FISCAL_START_MONTH and start.day == 1:
        return "FY%d-%02d" % (start.year, (start.year + 1) % 100)
    if (start.month, start.day) == (1, 1) and (end.month, end.day) == (12, 31):
        return "CY%d" % start.year
    return "%s..%s" % (start.isoformat(), end.isoformat())


def span_months(start, end):
    """Whole months covered, rounded to the nearest month. A reference period is twelve."""
    months = (end.year - start.year) * 12 + (end.month - start.month)
    return months + 1 if end.day >= 28 or end.day >= start.day else months


def midpoint(start, end):
    """The instant a period is centred on, as a fractional year.

    Used where a stock quantity has to be evaluated for a period rather than an instant -
    the waste sector's district population is the case this was written for, since a
    July-June fiscal year is centred on 1 January, not on either calendar year.
    """
    middle = start + (end - start) / 2
    year_start = datetime.date(middle.year, 1, 1)
    year_end = datetime.date(middle.year + 1, 1, 1)
    return middle.year + (middle - year_start).days / (year_end - year_start).days


def overlap_months(a, b):
    """Whole months two periods share. Zero when they do not meet.

    The honest way to report a comparison against a differently-dated official filing: not
    "the years differ" but how much of the two periods is actually the same time.
    """
    start, end = max(a[0], b[0]), min(a[1], b[1])
    return 0 if start > end else span_months(start, end)
