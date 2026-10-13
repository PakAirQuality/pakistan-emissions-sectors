"""PBS monthly minerals production, as a seasonal shape for the sectors it can serve.

WHY THIS EXISTS NOW AND NOT TWO PASSES AGO. The panel behind it was parsed with both of the
document's own controls and then deliberately left unwired, with a test enforcing the refusal,
because each canonical mineral resolves in only five or six of the eight held editions and a
profile covering six years of nine - the other three silently days-weighted - looked like the
borrowed-shape trap in a new costume. An external review overruled that: "too conservative for
an evidence-graded panel. Do not require nine perfect years before using six observed years.
TE2 for source-years with valid monthly data; TE4 for missing years; no borrowed shape across
missing years." That is the degrade-in-the-open contract every other panel here already
follows - `covers()` answers per year, an uncovered year falls to days-weighting IN THE OPEN,
and the class follows the evidence year by year. The refusal predated the per-year machinery
and had become the inconsistency.

WHY THIS IS IN CORE. Two consumers read it: fugitives shapes its upstream gas and oil streams
on the production months, and the limestone series is a cross-check against cement's QIM shape.

WHAT A MONTH IS EVIDENCE OF. Physical PRODUCTION in the month it left the field or quarry -
gas in MMCF, crude in barrels, limestone in tonnes, per province. The national series is the
provinces summed. It is a direct administrative record of the activity that drives upstream
emissions in the same month, which is T2; it is not T1, because the EMISSION is not observed.
And it is production-side only: gas DELIVERIES, send-out and consumption are different
quantities with different seasons, and this module must never shape a demand-side stream.

THE PROFILE IS A SHAPE, NEVER A MAGNITUDE. Every consumer normalises twelve shares to one over
its own annual control, so a published quantity could be wrong by any amount without moving the
inventory.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import input_exists as _input_exists
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.paths import DATA
from pkinv.activity.store import read_rows

PANEL = asset_path(DATA, "activity", "monthly", "pbs_minerals_month_province.csv")

NATURAL_GAS = "natural_gas"
CRUDE_OIL = "crude_oil"
LIMESTONE = "limestone"
COAL = "coal"


def _panel():
    if not _input_exists(PANEL):
        return []
    return read_rows(PANEL)


def series(mineral, fy_start, rows=None):
    """{YYYYMM: national quantity} for one mineral-year, or {} where the panel lacks it.

    An EMPTY DICT for "this year is not covered" and an exception only for a year present but
    partial - the distinction a caller with a fallback needs, because an exception thrown past
    it discards the fallback too. Twelve months are required: a partial year normalised into
    twelve shares is a different quantity wearing the same name.
    """
    rows = rows if rows is not None else _panel()
    matched = [r for r in rows if r["canonical_mineral"] == mineral
               and int(r["fiscal_year_start"]) == fy_start]
    if not matched:
        return {}
    out = {}
    for row in matched:
        out[row["month"]] = out.get(row["month"], 0.0) + float(row["quantity"])
    missing = set(core_monthly.months_for(fy_start)) - set(out)
    if missing:
        raise KeyError("%s FY%d-%02d is present but missing month(s) %s"
                       % (mineral, fy_start, (fy_start + 1) % 100, sorted(missing)))
    return out


def covers(mineral, fy_start, rows=None):
    try:
        return bool(series(mineral, fy_start, rows))
    except KeyError:
        return False


def profile(mineral, fy_start, rows=None):
    """({YYYYMM: share summing to 1}, {month: "T2"})."""
    values = series(mineral, fy_start, rows)
    return core_monthly.normalise(values), {month: "T2" for month in values}


def profile_or_flat(mineral, fy_start, rows=None):
    """(shares, method_map, covered) - the panel where it reaches, the calendar where not.

    NO YEAR WEARS ANOTHER YEAR'S SHAPE. The uncovered years take days-weighting and say T4;
    carrying a neighbouring year's production curve across would be precisely the borrowing
    the review's ruling forbade alongside the wiring it required.
    """
    if covers(mineral, fy_start, rows):
        return profile(mineral, fy_start, rows) + (True,)
    flat = core_monthly.days_weighted_profile(fy_start)
    return flat, {month: "T4" for month in flat}, False
