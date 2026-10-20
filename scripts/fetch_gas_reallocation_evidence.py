#!/usr/bin/env python3
"""Acquire the public documents the gas-reallocation application reads beyond the inventory.

WHAT IS MISSING WITHOUT THEM. The application moves network gas from two urea plants to gas
power stations and keeps both services. Three of its factor families have no holding in
this repository (scripts/holdings.py, 2026-10-20):
- the upstream (well-to-tank) intensity of the fuels a pathway displaces or imports:
  LNG, fuel oil and coal. The UK DESNZ conversion-factor set publishes all three under one
  method;
- coal-gasification ammonia, the route of the coal-based imported-urea pathway. IPCC 2006
  Table 3.1 prints gas and partial-oxidation routes only; the 2019 Refinement adds coal;
- energy-industry air-pollutant factors. The EMEP/EEA 2023 1.A.2 chapter is held; 1.A.1 is not.

Every attempt gets a log row, hits and misses alike. Bytes are kept through
pkinv.core.retention before anything reads them.

Usage:  PYTHONPATH=src python3 scripts/fetch_gas_reallocation_evidence.py [--dry-run]
Writes: data/raw/desnz/, data/raw/ipcc/, data/raw/emep/ (through the restricted-layer mount)
        data/raw/ACQUISITION_LOG_gas_reallocation_20261020.csv
"""
import csv
import datetime as dt
import hashlib
import os
import sys

from pkinv.assets import asset_path
from pkinv.core import retention

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = asset_path(ROOT, "data", "raw", "ACQUISITION_LOG_gas_reallocation_20261020.csv")
FIELDS = ["retrieved_utc", "url", "local_path", "status", "sha256", "bytes", "note"]
DRY = "--dry-run" in sys.argv

EEA = ("https://www.eea.europa.eu/en/analysis/publications/emep-eea-guidebook-2023/"
       "part-b-sectoral-guidance-chapters/1-energy/1-a-combustion/")
GOV_UK = "https://assets.publishing.service.gov.uk/media/"

# (source directory, file name, url, expected magic, why)
TARGETS = (
    ("desnz", "ghg-conversion-factors-2024-full_set_v1_1.xlsx",
     GOV_UK + "6722567487df31a87d8c497e/"
              "ghg-conversion-factors-2024-full_set__for_advanced_users__v1_1.xlsx",
     b"PK", "UK DESNZ 2024 GHG conversion factors, full set: the WTT-fuels sheet holds the "
            "well-to-tank intensity of LNG, natural gas, fuel oil and coal on one method"),
    ("desnz", "2024-greenhouse-gas-conversion-factors-methodology.pdf",
     GOV_UK + "66a9fe4ca3c2a28abb50da4a/2024-greenhouse-gas-conversion-factors-methodology.pdf",
     b"%PDF", "the methodology paper behind the WTT factors: what their boundary contains"),
    ("ipcc", "19R_V3_Ch03_Chemical_Industry.pdf",
     "https://www.ipcc-nggip.iges.or.jp/public/2019rf/pdf/3_Volume3/"
     "19R_V3_Ch03_Chemical_Industry.pdf",
     b"%PDF", "2019 Refinement Vol. 3 Ch. 3: ammonia Table 3.1 with the coal-gasification route"),
    ("emep", "emep_eea_2023_1a1_energy_industries.pdf",
     EEA + "1-a-1-energy-industries-2023/@@download/file",
     b"%PDF", "EMEP/EEA 2023 1.A.1 Energy industries: Tier 1/2 factors for gas turbines, "
              "oil-fired and coal-fired generation"),
    ("epa_ap42", "ap42_c08s02_urea.pdf",
     "https://www.epa.gov/sites/default/files/2020-09/documents/8.2_urea.pdf",
     b"%PDF", "AP-42 Section 8.2 Urea: solids-formation (prilling, granulation) PM and NH3, "
              "which the inventory types NE because the chapter was not held"),
)


def _log(row):
    fresh = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        if fresh:
            writer.writeheader()
        writer.writerow(row)


def main():
    failures = 0
    for source, name, url, magic, why in TARGETS:
        stamp = dt.datetime.now(dt.timezone.utc).isoformat()
        if DRY:
            print("would fetch %s -> data/raw/%s/%s" % (url, source, name))
            continue
        try:
            body = retention.get(url)
        except OSError as error:
            failures += 1
            _log({"retrieved_utc": stamp, "url": url, "local_path": "", "status": "failed",
                  "sha256": "", "bytes": "", "note": "%s; %s" % (why, error)})
            print("FAILED  %s: %s" % (name, error))
            continue
        if not body.startswith(magic):
            failures += 1
            _log({"retrieved_utc": stamp, "url": url, "local_path": "", "status": "not-a-document",
                  "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                  "note": "%s; the response does not start with %r" % (why, magic)})
            print("REFUSED %s: not the expected file type" % name)
            continue
        path = retention.keep(body, source, name, url, note=why)
        _log({"retrieved_utc": stamp, "url": url,
              "local_path": os.path.relpath(path, os.path.dirname(os.path.dirname(LOG))),
              "status": "acquired", "sha256": hashlib.sha256(body).hexdigest(),
              "bytes": len(body), "note": why})
        print("kept    %s (%d bytes)" % (path, len(body)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
