#!/usr/bin/env python3
"""Acquire the public documents the cooking-manure application's data gate asks for.

WHAT IS MISSING WITHOUT THEM. The contribution-evidence review of 21 October 2026 set a data gate for a
second application: the same cooking service supplied by replacement fuels, with the diverted dung
followed through storage and the field. Three evidence families had no holding
(scripts/holdings.py stove / efficiency / cookstove, 2026-10-21):
- cookstove thermal efficiencies: the World Bank 2024 Pakistan Energy Survey, held, states that it
  "did not collect data to analyze the efficiency attribute";
- FAOSTAT's manure-nitrogen activities behind its managed-soils items;
- the peer-reviewed version of the CCAC/SEI household assessment, and the "MDPI Sustainability 2021"
  dung-cake study that the agriculture manure-management shares table names as the source of
  its burned-fuel shares.

Every attempt gets a log row, hits, misses and blocked addresses alike. Bytes are kept through
pkinv.core.retention before anything reads them.

Usage:  PYTHONPATH=src python3 scripts/fetch_cooking_manure_evidence.py [--dry-run] [--only FILE_NAME ...]
Writes: data/raw/literature/, data/raw/faostat/ (through the restricted-layer mount)
        data/raw/ACQUISITION_LOG_cooking_manure_20261021.csv
"""
import csv
import datetime as dt
import hashlib
import os
import sys

from pkinv.assets import asset_path
from pkinv.core import retention

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = asset_path(ROOT, "data", "raw", "ACQUISITION_LOG_cooking_manure_20261021.csv")
FIELDS = ["retrieved_utc", "url", "local_path", "status", "sha256", "bytes", "note"]
DRY = "--dry-run" in sys.argv
# --only NAME [NAME ...]: fetch just those targets, and log only those not-found titles that contain a
# name given (a later addition is run alone so the earlier hits are not fetched and logged twice)
ONLY = sys.argv[sys.argv.index("--only") + 1:] if "--only" in sys.argv else None

# (source directory, file name, url, expected magic, why)
TARGETS = (
    ("literature", "jetter_2012_est_cookstove_emissions_efficiency.pdf",
     "https://cleancooking.org/wp-content/uploads/2021/07/195-1.pdf", b"%PDF",
     "Jetter et al. 2012, Environ. Sci. Technol. (EPA laboratory, WBT Version 4): thermal efficiency of "
     "twenty-two cookstoves on six fuels (no dung) against the three-stone fire; accepted manuscript as "
     "posted by the Clean Cooking Alliance"),
    ("literature", "shen_2017_energy_fuels_pmc6145494.html",
     "https://pmc.ncbi.nlm.nih.gov/articles/PMC6145494/", b"<",
     "Shen et al. 2017, Energy & Fuels 31(3) 3081-3090 (EPA; PMC author manuscript): thermal efficiency "
     "of LPG, kerosene and two wood stoves under WBT 4.2.3"),
    ("faostat", "faostat_Environment_LivestockManure_E_All_Data_(Normalized).zip",
     "https://bulks-faostat.fao.org/production/Environment_LivestockManure_E_All_Data_(Normalized).zip",
     b"PK", "FAOSTAT Livestock Manure (EMN): manure N excreted, treated, applied to soils and left on pasture "
            "- the nitrogen activities behind the managed-soils items 5062/5063"),
    ("literature", "slater_2024_acsestair_4c00003.pdf",
     "https://pubs.acs.org/doi/pdf/10.1021/acsestair.4c00003", b"%PDF",
     "Slater et al. 2024, ACS ES&T Air 1(8) 815-836: the peer-reviewed version of the held CCAC/SEI 2022 "
     "assessment (open access per OpenAlex)"),
    ("literature", "mir_2026_sustainability_18_3954.pdf",
     "https://www.mdpi.com/2071-1050/18/8/3954/pdf", b"%PDF",
     "Mir et al. 2026, Sustainability 18(8) 3954 (CC BY 4.0): Pakistan transport multi-pollutant scenarios, "
     "cited by docs/pakistan_inventory_comparison.md [S10]"),
    ("literature", "sei_2024_publication_page_pakistan_clean_air_policy.html",
     "https://www.sei.org/publications/air-pollutant-emissions-pakistan-clean-air-policy/", b"<",
     "SEI's publication page for Slater et al. 2024, searched for the LEAP model export behind the CCAC/SEI "
     "household tables: it links only the DOI, no data file (added 2026-10-21)"),
)
# Searched for and not found at any address: logged so 'not held' never means 'never looked for'.
NOT_FOUND = (
    ("MDPI Sustainability 2021 'Pakistan dung-cake fuel studies'",
     "named only as a working pointer in the agriculture MMS shares (burned_fuel cattle 0.28, buffalo 0.30), with no "
     "author, title or volume; web searches on 2026-10-21 found no MDPI Sustainability 2021 paper matching "
     "it. The shares stay unsourced (data_gaps: mms-distribution)"),
    ("CCAC/SEI LEAP model export for Pakistan (household fuels and technologies)",
     "no public export found: the SEI publication page links only the article DOI, the article PDF returned "
     "403, and web searches on 2026-10-21 found CCAC project pages describing the LEAP-IBC assessment but no "
     "data file. The held 2022 report's printed tables are what is returned "
     "(the CCAC/SEI household extract under the residential evidence tables)"),
)


def _log(row):
    fresh = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        if fresh:
            writer.writeheader()
        writer.writerow(row)


def main():
    misses = 0
    for source, name, url, magic, why in TARGETS:
        if ONLY is not None and name not in ONLY:
            continue
        stamp = dt.datetime.now(dt.timezone.utc).isoformat()
        if DRY:
            print("would fetch %s -> data/raw/%s/%s" % (url, source, name))
            continue
        try:
            body = retention.get(url)
        except OSError as error:
            misses += 1
            _log({"retrieved_utc": stamp, "url": url, "local_path": "", "status": "failed",
                  "sha256": "", "bytes": "", "note": "%s; %s" % (why, error)})
            print("FAILED  %s: %s" % (name, error))
            continue
        if not body.lstrip().startswith(magic):
            misses += 1
            _log({"retrieved_utc": stamp, "url": url, "local_path": "", "status": "not-a-document",
                  "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
                  "note": "%s; the response does not start with %r" % (why, magic)})
            print("REFUSED %s: not the expected file type" % name)
            continue
        path = retention.keep(body, source, name, url, note=why)
        _log({"retrieved_utc": stamp, "url": url,
              "local_path": os.path.relpath(path, os.path.dirname(os.path.dirname(LOG))),
              "status": "acquired", "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body),
              "note": why})
        print("kept    %s (%d bytes)" % (path, len(body)))
    if not DRY:
        for title, why in NOT_FOUND:
            if ONLY is not None and not any(n in title for n in ONLY):
                continue
            _log({"retrieved_utc": dt.datetime.now(dt.timezone.utc).isoformat(), "url": "", "local_path": "",
                  "status": "not-found", "sha256": "", "bytes": "", "note": "%s: %s" % (title, why)})
    return 0 if not misses else 1


if __name__ == "__main__":
    sys.exit(main())
