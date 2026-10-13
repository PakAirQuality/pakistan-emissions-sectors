"""Fetch monthly 2-metre temperature for the five provincial anchor cities and derive
degree-days - the shape behind the residential monthly profiles.

NASA POWER (power.larc.nasa.gov) rather than ERA5: same reanalysis family
(MERRA-2-based), an open JSON API with no CDS account, and monthly points are all the
profile layer needs. One point per province (the largest city, where the households
are), every month of the nine-year series. HDD base 18 C and CDD base 24 C on monthly
means - a monthly-mean degree-day understates threshold crossings within a month, which
is fine for a SHAPE (the annual totals never depend on it; monthly.py normalises).

NINE YEARS, NOT ONE, AND THAT IS THE POINT. This fetched FY2023-24 alone, so every other
fiscal year of the residential layer would have had to wear the reference year's weather -
a borrowed profile presented as a process-based one. Winters differ: the shape that
matters here is exactly the thing that varies between years, so borrowing it is the least
defensible place to borrow. The window runs July 2014 so that a fiscal year before the
series can still be assembled if one is ever needed.

Usage:  python3 scripts/fetch_hdd.py [--check]
Writes: data/raw/nasa_power/T2M_monthly_<city>_2014_2024.json  (each response, kept first)
        data/activity/residential/monthly_degree_days.csv  (5 provinces x 114 months)
--check keeps the responses, re-derives the table and compares; it writes no table.
"""

from pkinv.assets import asset_path
import csv
import io
import json
import os
import sys

from pkinv.core import retention

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = asset_path(ROOT, "data", "activity", "residential",
                   "monthly_degree_days.csv")

CITIES = {
    "Punjab": ("Lahore", 31.55, 74.35),
    "Sindh": ("Karachi", 24.86, 67.01),
    "Khyber Pakhtunkhwa": ("Peshawar", 34.01, 71.58),
    "Balochistan": ("Quetta", 30.18, 66.99),
    "Other": ("Islamabad", 33.68, 73.05),
}
# July 2014 through June 2024: the nine fiscal years of the series, plus the months of
# FY2014-15 that a tenth would need. Calendar years are what the API takes.
FIRST_YEAR, LAST_YEAR = 2014, 2024
MONTHS = ["%d%02d" % (y, m) for y in range(FIRST_YEAR, LAST_YEAR + 1)
          for m in range(1, 13)][6:-6]
HDD_BASE, CDD_BASE = 18.0, 24.0
URL = ("https://power.larc.nasa.gov/api/temporal/monthly/point?parameters=T2M"
       "&community=RE&longitude=%s&latitude=%s&start=" + str(FIRST_YEAR) +
       "&end=" + str(LAST_YEAR) + "&format=JSON")
DAYS = {"01": 31, "02": 28, "03": 31, "04": 30, "05": 31, "06": 30,
        "07": 31, "08": 31, "09": 30, "10": 31, "11": 30, "12": 31}


def _days(ym):
    """February is 29 days in a leap year, and two of these ten Februaries are.

    A degree-day is a temperature difference times a DURATION, so a 28-day February in a
    leap year understates the month by 3.6 percent. It never moved anything while one
    fiscal year was fetched and no leap February was in it; over nine years it would.
    """
    year, month = int(ym[:4]), ym[4:]
    if month == "02" and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        return 29
    return DAYS[month]


def table():
    rows = []
    for prov, (city, lat, lon) in CITIES.items():
        kept = retention.fetch_and_keep(
            URL % (lon, lat), "nasa_power",
            "T2M_monthly_%s_%d_%d.json" % (city, FIRST_YEAR, LAST_YEAR), timeout=60)
        with open(kept, encoding="utf-8") as handle:
            t2m = json.load(handle)["properties"]["parameter"]["T2M"]
        for ym in MONTHS:
            if ym not in t2m:
                raise SystemExit("NASA POWER returned no T2M for %s at %s; nothing written"
                                 % (ym, city))
            t = t2m[ym]
            days = _days(ym)
            rows.append({
                "province": prov, "city": city, "month": ym,
                "t2m_C": t,
                "hdd18": round(max(HDD_BASE - t, 0.0) * days, 1),
                "cdd24": round(max(t - CDD_BASE, 0.0) * days, 1),
                "source": "NASA POWER monthly T2M (MERRA-2 family), point %s,%s"
                          % (lat, lon),
            })
    text = io.StringIO()
    w = csv.DictWriter(text, fieldnames=list(rows[0].keys()))
    w.writeheader()
    w.writerows(rows)
    return text.getvalue(), len(rows)


def main(argv=None):
    text, count = table()
    if "--check" in (sys.argv[1:] if argv is None else argv):
        return retention.report_check("NASA POWER degree days", OUT, text)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        f.write(text)
    print("wrote %s (%d rows)" % (OUT, count))
    return 0


if __name__ == "__main__":
    sys.exit(main())
