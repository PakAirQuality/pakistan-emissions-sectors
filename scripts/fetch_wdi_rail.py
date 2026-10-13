"""Fetch the World Bank WDI railway activity series for Pakistan (UIC-sourced, CC BY 4.0).

Corroboration, not activity: the WDI passenger-km series (IS.RRS.PASG.KM, millions) ends
in 2018 at 24,903 - consistent in magnitude with the Year Book's own trajectory toward
29,865 million in FY2023-24 - and the freight series (IS.RRS.GOOD.MT.K6) likewise. The
Year Book remains the activity source; this file exists so the efficiency comparison has
an institutionally independent series next to it.

Usage:  python3 scripts/fetch_wdi_rail.py [--check]
Writes: data/raw/worldbank_wdi/PAK_<indicator>.json   (each response, kept before parsing)
        data/activity/railways/wdi_rail.csv
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
OUT = asset_path(ROOT, "data", "activity", "railways", "wdi_rail.csv")
INDICATORS = {"IS.RRS.PASG.KM": "passenger_km_million",
              "IS.RRS.GOOD.MT.K6": "tonne_km_million"}


def fetch(indicator):
    url = ("https://api.worldbank.org/v2/country/PAK/indicator/%s"
           "?format=json&per_page=80" % indicator)
    # the API times out routinely; get() retries
    kept = retention.fetch_and_keep(url, "worldbank_wdi", "PAK_%s.json" % indicator,
                                    attempts=4, timeout=60)
    with open(kept, encoding="utf-8") as handle:
        data = json.load(handle)
    return {int(row["date"]): row["value"] for row in data[1]
            if row["value"] is not None}


def table():
    series = {name: fetch(code) for code, name in INDICATORS.items()}
    years = sorted(set().union(*[s.keys() for s in series.values()]))
    text = io.StringIO()
    w = csv.writer(text)
    w.writerow(["year"] + list(series.keys()) + ["source"])
    for y in years:
        w.writerow([y] + [series[n].get(y, "") for n in series]
                   + ["World Bank WDI (UIC Railisa), CC BY 4.0"])
    return text.getvalue(), years


def main(argv=None):
    text, years = table()
    if "--check" in (sys.argv[1:] if argv is None else argv):
        return retention.report_check("World Bank WDI rail", OUT, text)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        f.write(text)
    print("wrote %s: %d years, latest %d" % (OUT, len(years), years[-1]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
