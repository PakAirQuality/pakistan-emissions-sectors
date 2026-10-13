"""The petroleum industry's monthly customer-class sales, as a seasonal shape for four modules.

WHY THIS IS IN CORE. Four modules anchor on the same publication: transport on its Road rows,
railways on its Railways row, power on its Total Power liquids, industry on Total Industry.
`industry/monthly.py` worked out how to read it first and this is that solution generalised -
four copies of a differencing rule with an off-by-one at the fiscal-year boundary is four things
to drift apart, which this project has now watched happen twice with declared tables.

WHAT THE EDITIONS ACTUALLY PUBLISH. Not months. Within a fiscal year the editions print
PAKISTAN-wide CUMULATIVE year-to-date totals, so a month is recovered by differencing
consecutive columns - an arithmetic identity on two published numbers, not a model, which is
why the twelve months close to the annual control exactly rather than approximately. The first
month of a fiscal year is not a difference at all: its cumulative column IS the month, so it is
T1 and the eleven after it are T2. The regime is not uniform across years either - the FY2024-25
editions are direct monthly - so `report_kind` on the panel decides, never the calendar.

A NEGATIVE DIFFERENCE RAISES. A cumulative series that goes backwards means two editions
disagree, and the month cannot be recovered; clipping it to zero would put the disagreement
into the profile silently.

WHAT IT IS AND IS NOT. These are SALES BY CUSTOMER CLASS in a calendar month - an
administrative record of when fuel was delivered, not an observation of when it was burned. A
dispatch schedule, a dealer's stocking decision or a public holiday moves a month's sales
without moving anyone's combustion. It is the closest monthly evidence that exists for these
streams, and T2 says exactly that.

THE PROFILE IS A SHAPE, NEVER A MAGNITUDE. Every consumer normalises to twelve shares summing
to one and applies them to its own annual control, so a month's sales figure could be wrong by
any amount without moving the inventory. Only the distribution in time comes from here.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.paths import DATA
from pkinv.activity.store import read_rows

PANEL = asset_path(DATA, "activity", "transport", "ocac_sectoral_provincial.csv")
NATIONAL = "PAKISTAN"

# sector_row values as the ingested panel carries them.
ROAD = "Road"
RAILWAYS = "Railways"
TOTAL_POWER = "Total Power"
TOTAL_INDUSTRY = "Total Industry"
DOMESTIC = "DOMESTIC"
AGRICULTURE = "AGRICULTURE"

PETROL = ("MS", "HOBC")
DIESEL = ("HSD",)
FURNACE_OIL = ("FO",)
JET = ("JP-1",)
KEROSENE = ("KERO",)


def _panel(sector_row, area=NATIONAL):
    return [r for r in read_rows(PANEL, comments=False) if r["sector_row"] == sector_row and r["area"] == area]


def _panel_months(fy_start):
    """OCAC's own YYYY-MM labels for a July-June fiscal year, in order."""
    return (["%d-%02d" % (fy_start, m) for m in range(7, 13)]
            + ["%d-%02d" % (fy_start + 1, m) for m in range(1, 7)])


def tonnes(sector_row, products, fy_start, area=NATIONAL):
    """({YYYYMM: tonnes}, {YYYYMM: T-class}) for one customer class and product set.

    Products are summed before differencing, not after, because the cumulative columns are
    per product and the sum of differences equals the difference of sums only when every
    product is present in every edition - which is exactly what a missing column would break.
    """
    months = _panel_months(fy_start)
    direct, cumulative = {}, {}
    for r in _panel(sector_row, area):
        if r["month"] not in months or r["product"] not in products:
            continue
        bucket = direct if r["report_kind"] == "monthly" else cumulative
        bucket[r["month"]] = bucket.get(r["month"], 0.0) + float(r["tonnes"] or 0.0)

    out, method, running = {}, {}, 0.0
    for i, m in enumerate(months):
        if m in cumulative:
            value, cls = cumulative[m] - running, "T2"
            running = cumulative[m]
        elif m in direct:
            value, cls = direct[m], "T1"
            running += value
        else:
            raise KeyError("the OCAC panel has no %s edition covering %s for %s"
                           % (sector_row, m, "+".join(products)))
        if i == 0:
            cls = "T1"          # the first month's cumulative column is the month itself
        if value < 0:
            raise ValueError(
                "OCAC cumulative %s/%s goes backwards at %s (%.0f t): the editions disagree "
                "and the month cannot be recovered by differencing"
                % (sector_row, "+".join(products), m, value))
        key = m.replace("-", "")
        out[key], method[key] = value, cls
    return out, method


def editions(sector_row, products, fy_start, area=NATIONAL):
    """{YYYYMM: {source_file, source_sha256, report_kind}} - the edition each month came from.

    A separate accessor rather than a change to tonnes(): every existing caller wants
    the numbers, and the monthly-controls register is the one consumer that needs the
    revision stamps tonnes() has always dropped. Where a month appears in more than one
    panel row (several products from the same edition PDF), the stamps are asserted
    identical - two products of one month citing different editions would mean the
    ingest mixed vintages, which must fail here rather than ship quietly.
    """
    months = _panel_months(fy_start)
    by_kind = {}
    for r in _panel(sector_row, area):
        if r["month"] not in months or r["product"] not in products:
            continue
        stamp = {"source_file": r["source_file"],
                 "source_sha256": r["source_sha256"],
                 "report_kind": r["report_kind"]}
        key = (r["month"].replace("-", ""), r["report_kind"])
        if key in by_kind and by_kind[key] != stamp:
            # Two documents of the SAME kind for one month is the ingest mixing vintages,
            # and must still fail here rather than ship quietly.
            raise ValueError("mixed editions for %s %s: %s vs %s"
                             % (sector_row, r["month"], by_kind[key], stamp))
        by_kind[key] = stamp
    # A month may legitimately carry BOTH kinds since the direct editions' national pages
    # joined the panel as its area-page closure controls (verified identical to the tonne in
    # outputs/ocac_direct_edition_crosscheck.csv). The stamp reported is the edition
    # `tonnes()` actually consumes - cumulative where present, since the differencing prefers
    # it - because this register documents where a published number CAME FROM, not every
    # document that agrees with it.
    out = {}
    for (month, kind), stamp in sorted(by_kind.items()):
        if month not in out or kind == "cumulative":
            out[month] = stamp
    return out


def profile(sector_row, products, fy_start, area=NATIONAL):
    """({YYYYMM: share summing to 1}, {YYYYMM: T-class}) - the shape, ready for apply_profile."""
    values, method = tonnes(sector_row, products, fy_start, area)
    missing = set(core_monthly.months_for(fy_start)) - set(values)
    if missing:
        raise KeyError("profile is missing months %s" % sorted(missing))
    return core_monthly.normalise(values), method


def covers(sector_row, products, fy_start, area=NATIONAL):
    """Whether the panel can shape this fiscal year at all.

    The panel starts partway through this inventory's window, so most sectors ask for a year
    it cannot serve and take a flat profile instead - which `profile` signals by raising. That
    is the right signal for a caller with nothing else to fall back on. It is the wrong one
    for a caller that has ANOTHER monthly source for the same year: an exception thrown past a
    second source discards it too. This answers the question directly so that the choice
    between two real sources is not made by an exception.
    """
    try:
        profile(sector_row, products, fy_start, area)
    except (KeyError, ValueError):
        return False
    return True


def profile_or_flat(sector_row, products, fy_start, area=NATIONAL):
    """(shares, temporal_method, covered) - the panel where it reaches, the calendar where not.

    Every sector that reads this panel wants the same thing for the years before it opens, and
    each of them used to get it by letting `profile` raise and having the caller above swallow
    it. That works only while the panel is the sector's ONLY monthly source. It stopped being
    true for power, where a raised KeyError discarded PBS's plant-month generation on the way
    out, and it was never true for agriculture, where the rice calendar needs no panel at all
    and was thrown away with it for eight of nine years. Degrading here, in the open, is what
    stops the next second source being lost the same way.
    """
    if covers(sector_row, products, fy_start, area):
        shares, method = profile(sector_row, products, fy_start, area)
        return shares, method_of(method), True
    return core_monthly.days_weighted_profile(fy_start), (lambda _c, _m: "T4"), False


def method_of(method_map):
    """A callable(component, month) -> T-class, for apply_profile.

    The class is a property of the MONTH, not of the component: one fiscal year is T1 in July
    and T2 for the eleven editions after it, and flattening that to the weaker class everywhere
    would discard the only directly published month.
    """
    return lambda _component, month: method_map[month]
