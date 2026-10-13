#!/usr/bin/env python3
"""Consumed derivatives of the aviation reconciliation study's documents (rc41).

Reads:  sources/Aviation/ocac_monthly/*.pdf (48 reports, pdftotext), sources/Aviation/ocac_annual/*.pdf (9),
        sources/Aviation/OECD_air_transport_PAK_2019_2025.csv,
        sources/Aviation/climatetrace_aviation_PAK_2015_2024.json,
        sources/Aviation/climatetrace_airports_PAK_2021_2024.json,
        sources/Aviation/ERA5_route_weather_FY2023_24.nc (xarray),
        sources/Aviation/ADSBLOL_pilot_FY2023_24.json
Writes: data/activity/aviation/ocac_monthly_extract.csv
        data/activity/aviation/ocac_annual_extract.csv
        data/activity/aviation/oecd_monthly_extract.csv
        data/activity/aviation/climatetrace_national_monthly_extract.csv
        data/activity/aviation/climatetrace_airport_monthly_extract.csv
        data/activity/aviation/era5_route_weather_extract.csv
        data/activity/aviation/adsblol_pilot_fy2023_24.json

pkinv.sectors.aviation.run_reconciliation_study read every one of those documents live;
the validation package registers them without shipping them, so the study now reads
these tables - exactly the rows and columns the readers returned from the documents -
and this script proves each against its document wherever it is held. Deterministic;
--check re-derives and diffs; exit 3 when a document is not held. The extractors stay
in the sector modules (monthly.extract_*, annual.extract_source_rows,
climatetrace.extract_*, era5.extract_route_weather); this script only drives them.

Usage:  python3 scripts/ingest_aviation_study_inputs.py [--check]
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pkinv.assets import asset_path

from pkinv.paths import ROOT  # noqa: E402
from pkinv.core import documents  # noqa: E402
from pkinv.core.io import write_or_check  # noqa: E402
from pkinv.sectors.aviation import annual, climatetrace, era5, monthly  # noqa: E402

ADSBLOL_SOURCE = asset_path(ROOT, "sources", "Aviation", "ADSBLOL_pilot_FY2023_24.json")
ADSBLOL_TABLE = asset_path(ROOT, "data", "activity", "aviation", "adsblol_pilot_fy2023_24.json")

# (table, fieldnames, extractor, documents the extractor opens, what the table is, reader)
TABLES = (
    (monthly.OCAC_EXTRACT, monthly.OCAC_EXTRACT_FIELDS, monthly.extract_ocac_monthly,
     (monthly.SOURCE_DIR,),
     "the five JP-1 customer cells of each tracked OCAC monthly sectoral-sales report (pdftotext)",
     "pkinv.sectors.aviation.monthly.ocac_monthly"),
    (annual.EXTRACT_CSV, annual.EXTRACT_FIELDS, annual.extract_source_rows,
     (annual.SOURCE_DIR,),
     "the customer x fuel cells of each tracked OCAC annual sectoral-sales report (pdftotext)",
     "pkinv.sectors.aviation.annual.source_rows"),
    (monthly.OECD_EXTRACT, monthly.OECD_EXTRACT_FIELDS, monthly.extract_oecd_monthly,
     (monthly.OECD_SOURCE,),
     "the OECD air-transport CO2 monthly series for Pakistan, summed to the six scopes the study reads",
     "pkinv.sectors.aviation.monthly.oecd_monthly"),
    (climatetrace.NATIONAL_EXTRACT, climatetrace.NATIONAL_FIELDS, climatetrace.extract_national_monthly,
     (climatetrace.NATIONAL,),
     "the Climate TRACE v7 national aviation monthly series for Pakistan (CC BY 4.0 per the package)",
     "pkinv.sectors.aviation.climatetrace.national_monthly"),
    (climatetrace.AIRPORTS_EXTRACT, climatetrace.AIRPORTS_FIELDS, climatetrace.extract_airport_monthly,
     (climatetrace.AIRPORTS,),
     "the Climate TRACE v7 airport-source monthly rows for Pakistan with the nearest-airport match "
     "against data/activity/aviation/airports.csv",
     "pkinv.sectors.aviation.climatetrace.airport_monthly"),
    (era5.EXTRACT_CSV, era5.EXTRACT_FIELDS, era5.extract_route_weather,
     (era5.SOURCE,),
     "per-route 250 hPa tailwind and temperature statistics from the ERA5 route-weather sample",
     "pkinv.sectors.aviation.era5.route_weather"),
)


def _held(path):
    return os.path.isdir(path) or os.path.isfile(path)


def main(check=False):
    needed = [doc for _t, _f, _x, docs, _w, _r in TABLES for doc in docs] + [ADSBLOL_SOURCE]
    missing = [documents.relative(doc) for doc in needed if not _held(doc)]
    if missing:
        print("document not held: %s" % ", ".join(missing))
        return 3
    codes = []
    for table, fields, extract, docs, what, reader in TABLES:
        rows = extract()
        digests = ["%s sha256 %s" % (documents.relative(doc), documents.digest(doc, quiet=True))
                   if os.path.isfile(doc) else
                   "%s/ (%d files; per-file sha256 in the source_sha256 column)"
                   % (documents.relative(doc), len(os.listdir(doc)))
                   for doc in docs]
        banner = [
            "CONSUMED DERIVATIVE (rc41): %s" % what,
            "document: %s (data/raw_manifest.csv; data/consumed_derivatives.csv)" % "; ".join(digests),
            "written by scripts/ingest_aviation_study_inputs.py; --check re-derives it wherever the documents are held",
            "read by %s" % reader,
        ]
        codes.append(write_or_check(table, fields, rows, check=check, banner=banner,
                                    lineterminator="\n"))
    # The ADS-B pilot package is this project's own pilot output (a JSON document): a byte copy.
    with open(ADSBLOL_SOURCE, "rb") as handle:
        source_bytes = handle.read()
    if check:
        held = open(ADSBLOL_TABLE, "rb").read() if os.path.exists(ADSBLOL_TABLE) else b""
        if held != source_bytes:
            print("%s does not match %s" % (documents.relative(ADSBLOL_TABLE),
                                            documents.relative(ADSBLOL_SOURCE)))
            codes.append(1)
    else:
        shutil.copyfile(ADSBLOL_SOURCE, ADSBLOL_TABLE)
    return max(codes)


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        raise SystemExit(main(check="--check" in sys.argv))
