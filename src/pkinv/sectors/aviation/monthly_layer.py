"""Domestic aviation, resolved into the twelve months of FY2023-24.

WHY THIS IS A SEPARATE FILE FROM monthly.py. `aviation/monthly.py` is a fuel RECONCILIATION
STUDY - it extracts OCAC's monthly jet-fuel series, compares it against the OECD's, and reports
where the two disagree. It never spreads this sector's components, so aviation had no monthly
layer at all despite holding the best monthly evidence in the inventory. This file is the
layer; the study stays what it is.

The source series describes jet fuel sold to resident airline customers, whose flights
include international services. It is not an observed monthly series of domestic airport
movements or flight-stage fuel. The source cells retain their direct/differenced status,
while their use to allocate domestic-flight emissions is explicitly a T3 timing proxy.

The profile is remarkably flat - a nine percent spread between the busiest and quietest months
- which is a real property of a scheduled domestic network rather than an artefact of the
method, and it is worth saying so: a flat curve derived from an observed series and a flat
curve asserted for want of one look identical in a chart and mean opposite things. The class
column is the only thing that distinguishes them.

THE SUFFIX SAYS FY2023-24 AND SO DO THE ROWS. It read fy2024_25 for one release, for the
same reason power's did: aviation keys its year by the fiscal year's START, and the suffix
rename treated every sector as END-keyed, so the two fiscal-start sectors were the only two
labelled a year forward. The months inside are 202307 to 202406 and never moved.

Usage:  python3 -m pkinv.sectors.aviation.monthly_layer
Writes: outputs/aviation_monthly_fy2023_24.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.paths import OUTPUTS
from pkinv.sectors.aviation import engine
from pkinv.sectors.aviation.data import AviationData

FY_START = 2023
SERIES = asset_path(OUTPUTS, "aviation_ocac_monthly.csv")
OUT = asset_path(OUTPUTS, "aviation_monthly_fy2023_24.csv")
BASIS = ("OCAC resident-airline jet-fuel sales proxy for domestic flight activity; "
         "customer and flight-geography boundaries differ")


def domestic_series(fy_start=FY_START):
    """({YYYYMM: tonnes}, {YYYYMM: T-class}) for domestic commercial jet fuel."""
    values, kinds = {}, {}
    for r in _activity_rows(SERIES, comments=False):
        if r["fiscal_year"] != str(fy_start):
            continue
        if not r["customer_category"].startswith("Domestic Avi"):
            continue
        key = r["period_end"].replace("-", "")
        values[key] = values.get(key, 0.0) + float(r["monthly_t"] or 0.0)
        # A direct edition is an observation; a differenced cumulative column is a
        # reconstruction. Where the two categories disagree in a month the weaker wins.
        cls = "T1" if r["report_kind"] == "monthly" else "T2"
        kinds[key] = "T2" if kinds.get(key) == "T2" else cls
    missing = set(core_monthly.months_for(fy_start)) - set(values)
    if missing:
        raise KeyError("the OCAC monthly jet series is missing %s" % sorted(missing))
    return values, kinds


def rows(data=None, fy_start=FY_START):
    data = data if data is not None else AviationData()
    components = engine.build_components(data)
    try:
        values, kinds = domestic_series(fy_start)
    except KeyError:
        # The OCAC jet series opens partway through this inventory's window. Saying so here
        # is what stops the exception travelling up to a caller that would read it as "this
        # sector has no monthly layer at all".
        return components, core_monthly.apply_profile(
            components, core_monthly.days_weighted_profile(fy_start), fy_start,
            temporal_method="T4",
            basis="flat: the OCAC monthly jet series does not reach this fiscal year, and "
                  "one year's uplift shape is not carried to another")
    shares = core_monthly.normalise(values)
    return components, core_monthly.apply_profile(
        components, shares, fy_start,
        temporal_method="T3", basis=BASIS)


def main():
    components, month_rows = rows()
    core_monthly.write_layer(OUT, month_rows, components)
    totals = core_monthly.month_totals(month_rows)
    spread = (max(totals.values()) - min(totals.values())) / (sum(totals.values()) / 12.0)
    print("aviation monthly layer -> %s" % OUT)
    print("  %d rows; closes exactly" % len(month_rows))
    print("  observed spread between busiest and quietest month: %.0f%% of the mean"
          % (100 * spread))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
