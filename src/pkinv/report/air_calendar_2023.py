"""Calendar 2023 for the industrial air layer, composed from two fiscal years (rc58 W3).

TIME IN THIS INVENTORY IS NINE FISCAL INTERVALS, and nothing relabels a fiscal year as a
calendar one (annual_grid.py says why). A calendar 2023 industrial figure is nevertheless
what a Lahore campaign or an EDGAR/CAMS column is dated to, so it is COMPOSED here, in the
open: January-June 2023 from FY2022-23's months, July-December 2023 from FY2023-24's, each
class-year's air mass split across its months by the monthly cube's own share vector for the
greenhouse-gas component the class rides (outputs/pakemis_monthly_fy2015_16_fy2023_24.csv:
the same T2 differenced OCAC editions, T3 QIM production shapes and days-weighted flat
profiles that time the CO2). The month_method column names, per row, which of those it was
- an air row cannot be better timed than the fuel it burns.

WHAT THIS IS NOT. Not a tenth period of the panel, not benchmarked this round (EDGAR v8.1
ends in 2022; the comparison script says so), and not a Lahore figure - it is national, by
class and species, the input a later spatial composition would multiply.

Usage:  python3 -m pkinv.report.air_calendar_2023
Reads:  outputs/pakemis_air_source_classes_fy2015_16_fy2023_24.csv (industry rows),
        outputs/pakemis_monthly_fy2015_16_fy2023_24.csv, data/air_source_classes.csv
Writes: outputs/pakemis_air_industry_cy2023.csv
"""

from pkinv.assets import asset_path
import csv
import os
from collections import defaultdict

from pkinv.activity.store import read_rows
from pkinv.paths import DATA, OUTPUTS

DETAIL = asset_path(OUTPUTS, "pakemis_air_source_classes_fy2015_16_fy2023_24.csv")
MONTHLY = asset_path(OUTPUTS, "pakemis_monthly_fy2015_16_fy2023_24.csv")
REGISTER = asset_path(DATA, "air_source_classes.csv")
OUT = asset_path(OUTPUTS, "pakemis_air_industry_cy2023.csv")
CALENDAR_YEAR = 2023
HALVES = (("FY2022-23", range(1, 7)), ("FY2023-24", range(7, 13)))     # Jan-Jun, Jul-Dec
FIELDS = ("calendar_year", "month", "source_class_id", "pollutant", "emissions_kt",
          "fiscal_period", "component_id", "month_share", "month_method", "temporal_evidence_class")


def _component_shares():
    """{(period_id, component_id): {month(YYYYMM): (share, profile_id, TE class)}} for the
    industry and captive CO2 components - the monthly cube's own timing."""
    out = defaultdict(dict)
    for r in read_rows(MONTHLY):
        if r["gas"] != "CO2" or r["configuration_id"] != "REF_2023_24":
            continue
        if r["sector_id"] != "industry" and not r["category"].startswith("Captive"):
            continue
        out[(r["period_id"], r["component_id"])][r["month"]] = (
            float(r["share"]), r["profile_id"], r["temporal_evidence_class"])
    return out


def _component_of(cls):
    """The CO2 component whose months a class rides: the anchor stream's component id."""
    module = cls["ghg_anchor_module"]
    sub = cls["ghg_anchor_subitem"]
    slug = sub.lower().replace(" ", "-")
    category = ("captive-gas-self-generation-(1a2)" if module == "power"
                else "industrial-fuel-combustion-(1a2)")
    return "%s|%s|%s|co2" % (module, category, slug)


def build():
    shares = _component_shares()
    register = {r["source_class_id"]: r for r in read_rows(REGISTER)}
    # industry classes only: the ippu and fugitives classes (rc59) have no CO2 component of
    # their own in the monthly cube to ride and are not composed here
    detail = [r for r in read_rows(DETAIL) if r["status"] == "estimate" and r["sector_id"] == "industry"]
    rows = []
    for pid, months in HALVES:
        fy_rows = [r for r in detail if r["period_id"] == pid]
        for r in fy_rows:
            comp = _component_of(register[r["source_class_id"]])
            vec = shares.get((pid, comp))
            if vec is None:
                raise KeyError("no monthly shares for %s in %s (class %s)" % (comp, pid, r["source_class_id"]))
            annual = float(r["emissions_kt"])
            for m in months:
                key = "%d%02d" % (CALENDAR_YEAR, m)
                share, profile, te = vec[key]
                rows.append({"calendar_year": CALENDAR_YEAR, "month": key,
                             "source_class_id": r["source_class_id"], "pollutant": r["pollutant"],
                             "emissions_kt": annual * share, "fiscal_period": pid,
                             "component_id": comp, "month_share": share,
                             "month_method": profile, "temporal_evidence_class": te})
    rows.sort(key=lambda r: (r["month"], r["source_class_id"], r["pollutant"]))
    return rows


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write("# CALENDAR 2023 FOR THE INDUSTRIAL AIR LAYER, COMPOSED: Jan-Jun from FY2022-23, Jul-Dec from\n"
                "# FY2023-24, each class-year's mass split by the monthly cube's own share vector for the CO2\n"
                "# component it rides (month_method = that profile; TE class carried). National, by class and\n"
                "# species; not a panel period and not benchmarked (EDGAR v8.1 ends 2022). pkinv.report.air_calendar_2023\n")
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow(dict(r, emissions_kt="%.6f" % r["emissions_kt"], month_share="%.6f" % r["month_share"]))
    totals = defaultdict(float)
    for r in rows:
        totals[r["pollutant"]] += r["emissions_kt"]
    print("industry air, calendar 2023 -> %s (%d rows)" % (os.path.relpath(OUT), len(rows)))
    for p, v in sorted(totals.items()):
        print("  CY2023 %-6s %9.3f kt" % (p, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
