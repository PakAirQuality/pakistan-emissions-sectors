"""Validated monthly field production; incomplete or suspect years fall to T4.

The profiles shape upstream production emissions only. Twelve months covering a
subset of producing provinces cannot establish observed national timing.
"""
from pkinv.assets import asset_path
from pkinv.activity.store import input_exists as _input_exists, read_rows
from pkinv.core import monthly as core_monthly
from pkinv.paths import DATA

PANEL = asset_path(DATA, "activity/monthly/pbs_minerals_month_province.csv")
NATURAL_GAS, CRUDE_OIL, LIMESTONE, COAL = "natural_gas", "crude_oil", "limestone", "coal"

def _panel():
    return read_rows(PANEL) if _input_exists(PANEL) else []

def series(mineral, fy_start, rows=None):
    rows = _panel() if rows is None else rows
    matched = [r for r in rows if r["canonical_mineral"] == mineral and int(r["fiscal_year_start"]) == fy_start]
    if not matched or any(r.get("timing_usable") != "yes" or r.get("national_coverage") != "complete" for r in matched):
        return {}
    keys = [(r["province"], r["month"]) for r in matched]
    if len(keys) != len(set(keys)):
        raise KeyError("duplicate reporting-area/month records for %s FY%d" % (mineral, fy_start))
    out = {}
    for month in core_monthly.months_for(fy_start):
        members = [r for r in matched if r["month"] == month]
        if not members:
            raise KeyError("missing national month %s for %s" % (month, mineral))
        expected = {tuple(r["source_expected_provinces"].split(";")) for r in members}
        if len(expected) != 1 or {r["province"] for r in members} != set(next(iter(expected))):
            raise KeyError("incomplete reporting areas for %s/%s" % (mineral, month))
        controls = {float(r["source_national_month_quantity"]) for r in members}
        if len(controls) != 1:
            raise KeyError("conflicting national monthly controls for %s/%s" % (mineral, month))
        value = sum(float(r["quantity"]) for r in members)
        if abs(value - controls.pop()) > 2.0:
            raise KeyError("exported provinces fail national monthly control for %s/%s" % (mineral, month))
        out[month] = value
    if set(r["month"] for r in matched) != set(out):
        raise KeyError("month outside fiscal period for %s FY%d" % (mineral, fy_start))
    return out

def withdrawn(mineral, fy_start, rows=None):
    """True when the panel HOLDS the mineral-year but its timing is withdrawn for quality
    (timing_usable != yes): the source exists and was read, and its monthly shape was refused.
    Distinct from a year the panel does not hold at all."""
    rows = _panel() if rows is None else rows
    matched = [r for r in rows if r["canonical_mineral"] == mineral
               and int(r["fiscal_year_start"]) == fy_start]
    return bool(matched) and any(r.get("timing_usable") != "yes" for r in matched)


def covers(mineral, fy_start, rows=None):
    try:
        return bool(series(mineral, fy_start, rows))
    except (KeyError, ValueError):
        return False

def profile(mineral, fy_start, rows=None):
    values = series(mineral, fy_start, rows)
    if not values:
        raise KeyError("no validated national monthly support for %s FY%d" % (mineral, fy_start))
    return core_monthly.normalise(values), {month: "T2" for month in values}

def profile_or_flat(mineral, fy_start, rows=None):
    if covers(mineral, fy_start, rows):
        return profile(mineral, fy_start, rows) + (True,)
    flat = core_monthly.days_weighted_profile(fy_start)
    return flat, {month: "T4" for month in flat}, False
