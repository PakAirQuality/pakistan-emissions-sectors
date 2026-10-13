"""Project the district population panel one year past its census anchor, for FY2023-24.

WHY. The waste sector's activity is population x a per-capita generation rate, and its panel
is a gapless district series built by geometric interpolation between the 6th (2017) and 7th
(2023) Population and Housing Censuses. That made the sector's reference period CY2023 - the
last anchor - while eight other sectors report the July-June fiscal year. A six-month offset
on a slowly-moving stock is a small error, but an undeclared one, and it kept the national
total from being a single-period figure.

WHAT THIS DOES, AND WHAT IT DOES NOT. FY2023-24 is centred on 1 January 2024, so the sector
needs a population one year past the census. This applies THE SAME per-district geometric
growth the panel already uses between its two anchors, one step further. It is not a new
assumption; it is the existing one extrapolated rather than interpolated, and that distinction
is the whole reason the appended rows are labelled a projection rather than an interpolation.

An extrapolated year is weaker evidence than an interpolated one, and the waste sector's rows
drop from evidence class E2 to E3 to say so: the quantity is now derived from a published
census plus a growth assumption rather than read from a census.

Deliberately reads the COMMITTED panel rather than the source workbook, so the projection is
reproducible from this repository alone - ingest_waste_population.py needs Domestic.xlsx,
which is not in it.

Usage:  python3 scripts/project_waste_population.py
Writes: data/activity/waste/population_district.csv (appends the projected year in place)
"""

from pkinv.assets import asset_path
import csv
import os
import sys

from pkinv.paths import DATA

PANEL = asset_path(DATA, "activity", "waste", "population_district.csv")

ANCHOR_EARLY = 2017          # 6th Population and Housing Census
ANCHOR_LATE = 2023           # 7th Population and Housing Census, the panel's last year
TARGET = 2024                # the FY2023-24 midpoint, 1 January 2024
COLUMNS = ("pop_total", "pop_rural", "pop_urban")
SOURCE = ("PBS 6th (2017) + 7th (2023) Population and Housing Census, PROJECTED one year "
          "past the 7th Census anchor at the panel's own 2017-2023 district growth rate, "
          "for the FY2023-24 midpoint (1 January 2024). An extrapolation, not an "
          "interpolation - see scripts/project_waste_population.py")


def project(rows):
    """Rows for TARGET, one per district, from the panel's own intercensal growth."""
    by_district = {}
    for r in rows:
        by_district.setdefault(r["district"], {})[int(r["year"])] = r

    out = []
    for district, years in sorted(by_district.items()):
        early, late = years.get(ANCHOR_EARLY), years.get(ANCHOR_LATE)
        if early is None or late is None:
            raise SystemExit("%s lacks a %d or %d row; the panel is not anchored on both "
                             "censuses and cannot be projected" % (district, ANCHOR_EARLY,
                                                                   ANCHOR_LATE))
        row = {"province": late["province"], "district": district, "year": TARGET,
               "source": SOURCE}
        # The district's own total growth, which is always defined because no district has
        # zero people. Used as the fallback rate for a component that was zero in 2017:
        # several districts are recorded as wholly rural at the 6th Census, and a geometric
        # rate out of zero does not exist. Growing such a component at the district total's
        # rate holds the urban share where the 7th Census put it, which is the conservative
        # choice - the alternative, freezing it, would make the district's urban share fall
        # every projected year for an arithmetic reason rather than a demographic one.
        span = ANCHOR_LATE - ANCHOR_EARLY
        step = TARGET - ANCHOR_LATE
        total_cagr = (float(late["pop_total"]) / float(early["pop_total"])) ** (1.0 / span)
        for col in COLUMNS:
            a, b = float(early[col]), float(late[col])
            cagr = (b / a) ** (1.0 / span) if a > 0 else total_cagr
            row[col] = round(b * cagr ** step, 1)
        # Rural plus urban must still be the total, which componentwise growth does not
        # guarantee. Scale the two parts onto the projected total rather than letting the
        # panel stop adding up.
        parts = row["pop_rural"] + row["pop_urban"]
        if parts > 0:
            scale = row["pop_total"] / parts
            row["pop_rural"] = round(row["pop_rural"] * scale, 1)
            row["pop_urban"] = round(row["pop_total"] - row["pop_rural"], 1)
        out.append(row)
    return out


def main():
    with open(PANEL, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = list(reader.fieldnames)
        rows = list(reader)

    existing = {int(r["year"]) for r in rows}
    if TARGET in existing:
        rows = [r for r in rows if int(r["year"]) != TARGET]     # regenerate, do not double
    projected = project(rows)

    with open(PANEL, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows + projected:
            w.writerow(r)

    total_late = sum(float(r["pop_total"]) for r in rows if int(r["year"]) == ANCHOR_LATE)
    total_target = sum(float(r["pop_total"]) for r in projected)
    print("Projected %d districts from %d to %d" % (len(projected), ANCHOR_LATE, TARGET))
    print("  national population %.1f M -> %.1f M  (+%.2f%%, the panel's own intercensal rate)"
          % (total_late / 1e6, total_target / 1e6,
             100 * (total_target / total_late - 1)))
    print("  labelled a projection, not an interpolation: %s" % PANEL)


if __name__ == "__main__":
    sys.exit(main())
