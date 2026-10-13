#!/usr/bin/env python3
"""Keep NASA FIRMS's keyless country-year files for Pakistan and check the held fire layer.

WHY THIS EXISTS. data/gis/manual/firms_fire.csv is 1.66 million VIIRS detections fetched in
August 2026 through the FIRMS area API, nine burning seasons of five-day windows. The fetcher
kept five columns of each detection and let every response go, so the fire layer had no held
document behind it. Asking the area API again needs a personal MAP_KEY.

FIRMS also publishes, without a key, one file per country and calendar year of the same
product (VIIRS S-NPP, standard processing). Those are fixed, citable files. This script keeps
the Pakistan file for every year the fire layer touches and compares the two.

WHAT THE COMPARISON CAN AND CANNOT SAY. The fire layer covers a box (60.5-77.5 E, 23.5-37.5 N)
that includes parts of India, Afghanistan and Iran; the country files cover Pakistan only. So
the check runs one way: every country-file detection dated inside a fetched window should be
in the fire layer. It reports the share that is. It cannot vouch for the layer's detections
outside Pakistan, and it says so in its output.

Usage:  python3 scripts/fetch_firms_country_archive.py [--check]
Writes: data/raw/firms/country_archive/viirs-snpp_<year>_Pakistan.csv
"""
import csv
import json
import os
import sys

from pkinv.assets import asset_path
from pkinv.core import retention

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
URL = "https://firms.modaps.eosdis.nasa.gov/data/country/viirs-snpp/%d/viirs-snpp_%d_Pakistan.csv"
LAYER = asset_path(ROOT, "data", "gis", "manual", "firms_fire.csv")
SIDECAR = asset_path(ROOT, "data", "gis", "manual", "FIRMS_SOURCES.json")


def windows():
    with open(SIDECAR, encoding="utf-8") as handle:
        return sorted((w[1], w[2]) for w in json.load(handle)["windows_fetched"])


def key(row):
    return ("%.5f" % float(row["latitude"]), "%.5f" % float(row["longitude"]), row["acq_date"])


def main(argv=None):
    spans = windows()
    years = range(int(spans[0][0][:4]), int(spans[-1][1][:4]) + 1)
    held = {}
    for year in years:
        name = "country_archive/viirs-snpp_%d_Pakistan.csv" % year
        path = os.path.join(retention.RAW, "firms", name)
        if not os.path.exists(path):
            path = retention.fetch_and_keep(URL % (year, year), "firms", name, timeout=300)
        held[year] = path
        print("  %d  %s (%d bytes)" % (year, os.path.relpath(path, ROOT), os.path.getsize(path)))
    with open(LAYER, encoding="utf-8", newline="") as handle:
        layer = {key(r) for r in csv.DictReader(handle)}
    inside = found = 0
    by_year = {}
    for year, path in held.items():
        with open(path, encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                day = row["acq_date"]
                if not any(a <= day <= b for a, b in spans):
                    continue
                inside += 1
                hit = key(row) in layer
                found += hit
                tally = by_year.setdefault(year, [0, 0])
                tally[0] += 1
                tally[1] += hit
    for year in sorted(by_year):
        n, hit = by_year[year]
        print("  %d: %d of %d in-window Pakistan detections are in the fire layer (%.2f%%)"
              % (year, hit, n, 100.0 * hit / n))
    share = 100.0 * found / inside if inside else 0.0
    print("country archive vs fire layer: %d of %d in-window Pakistan detections found "
          "(%.2f%%). The layer's %d detections include the box outside Pakistan, which "
          "these files cannot check." % (found, inside, share, len(layer)))
    return 0 if share >= 99.0 else 1


if __name__ == "__main__":
    sys.exit(main())
