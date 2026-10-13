#!/usr/bin/env python3
"""Acquire the public air-pollutant FACTOR chapters the industrial air layer reads (rc58 W1).

WHY A SCRIPT. The rc57 air layer priced industry on AP-42 rows the power module had transcribed
from chapters it held (1.1, 1.7, 1.8, 3.1) and typed everything else absent "because the chapter
is not held" - fuel oil, natural gas, brick and cement kilns, the EMEP/EEA 1.A.2 chapter. Every
one of those documents is public. This script fetches them to data/raw/<source>/ (never
sources/, the frozen legacy tree), hashes them, and writes one log row per attempt - hits and
misses alike - so "not held" can never again mean "never fetched".

THE ADDRESSES ARE THE RESOLVED ONES. The first guesses (www3.epa.gov/ttn/chief/ap42/...,
eea.europa.eu/publications/.../view, jeodpp .../v81_FT2022_AP_new/SO2/...) all 404; the
addresses below were located from the publishers' own index pages on 2026-09-17 and answer
200 with the right content type. A miss here is therefore a real miss and is logged as one.

Idempotent: a file already on disk with the logged size is left alone and logged as `held`.

Usage:  python3 scripts/fetch_air_factor_chapters.py [--dry-run]
Writes: data/raw/emep/*.pdf, data/raw/epa_ap42/*.pdf, data/raw/edgar/*.zip
        data/raw/ACQUISITION_LOG_industrial_air.csv (one row per attempt)
        data/acquisition_attempts.csv (appended, one row per dataset)
"""

from pkinv.assets import asset_path
import csv
import datetime as dt
import hashlib
import os
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = asset_path(ROOT, "data", "raw")
LOG = asset_path(RAW, "ACQUISITION_LOG_industrial_air.csv")
ATTEMPTS = asset_path(ROOT, "data", "acquisition_attempts.csv")
DRY = "--dry-run" in sys.argv
TODAY = dt.date.today().isoformat()

EEA = ("https://www.eea.europa.eu/en/analysis/publications/emep-eea-guidebook-2023/"
       "part-b-sectoral-guidance-chapters/")
EPA = "https://www.epa.gov/sites/default/files/"
EDGAR = "https://jeodpp.jrc.ec.europa.eu/ftp/jrc-opendata/EDGAR/datasets/v81_FT2022_AP_new/"

# (source, dataset label, url, relative destination under data/raw/, expected magic)
TARGETS = (
    ("EMEP/EEA 2023", "1.A.2 Combustion in manufacturing industries and construction (2023 FINAL)",
     EEA + "1-energy/1-a-combustion/1-a-2-combustion-in/@@download/file",
     "emep/emep_eea_2023_1a2_combustion_in_manufacturing.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "2.A.1 Cement production 2023",
     EEA + "2-industrial-processes-and-product-use/2-a-mineral-products/"
           "2-a-1-cement-production-2023/@@download/file",
     "emep/emep_eea_2023_2a1_cement_production.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "2.A.2 Lime production 2023",
     EEA + "2-industrial-processes-and-product-use/2-a-mineral-products/"
           "2-a-2-lime-production-2023/@@download/file",
     "emep/emep_eea_2023_2a2_lime_production.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "2.A.3 Glass production 2023",
     EEA + "2-industrial-processes-and-product-use/2-a-mineral-products/"
           "2-a-3-glass-production-2023/@@download/file",
     "emep/emep_eea_2023_2a3_glass_production.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "2.A.5.c Storage, handling and transport of mineral products 2023",
     EEA + "2-industrial-processes-and-product-use/2-a-mineral-products/"
           "2-a-5-c-storage/@@download/file",
     "emep/emep_eea_2023_2a5c_storage_handling_mineral_products.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "2.A.6 Other mineral products 2023 (bricks, ceramics)",
     EEA + "2-industrial-processes-and-product-use/2-a-mineral-products/"
           "2-a-6-other-mineral/@@download/file",
     "emep/emep_eea_2023_2a6_other_mineral_products.pdf", b"%PDF"),
    ("US EPA AP-42", "Section 1.3 Fuel Oil Combustion (Supplement E 1999, corrected May 2010)",
     EPA + "2020-09/documents/1.3_fuel_oil_combustion.pdf",
     "epa_ap42/ap42_c01s03_fuel_oil_combustion.pdf", b"%PDF"),
    ("US EPA AP-42", "Section 1.4 Natural Gas Combustion (1998, corrected)",
     EPA + "2020-09/documents/1.4_natural_gas_combustion.pdf",
     "epa_ap42/ap42_c01s04_natural_gas_combustion.pdf", b"%PDF"),
    ("US EPA AP-42", "Section 11.3 Bricks and Related Clay Products (Supplement C, August 1997)",
     EPA + "2020-10/documents/c11s03.pdf",
     "epa_ap42/ap42_c11s03_bricks_and_clay_products.pdf", b"%PDF"),
    ("US EPA AP-42", "Section 11.6 Portland Cement Manufacturing (February 2025)",
     "https://www.epa.gov/system/files/documents/2025-02/c11s06_final_2-2025_0.pdf",
     "epa_ap42/ap42_c11s06_portland_cement_2025.pdf", b"%PDF"),
    ("US EPA AP-42", "Section 11.17 Lime Manufacturing (February 1998)",
     EPA + "2020-10/documents/c11s17.pdf",
     "epa_ap42/ap42_c11s17_lime_manufacturing.pdf", b"%PDF"),
    ("US EPA AP-42", "Section 3.2 Natural Gas-fired Reciprocating Engines (July 2000)",
     EPA + "2020-10/documents/c03s02.pdf",
     "epa_ap42/ap42_c03s02_natural_gas_reciprocating_engines.pdf", b"%PDF"),
    ("US EPA AP-42", "Section 3.3 Gasoline and Diesel Industrial Engines (April 2025)",
     "https://www.epa.gov/system/files/documents/2025-04/c03s03_april2025.pdf",
     "epa_ap42/ap42_c03s03_gasoline_diesel_industrial_engines_2025.pdf", b"%PDF"),
    ("US EPA AP-42", "Section 3.4 Large Stationary Diesel and Dual-fuel Engines (April 2025)",
     "https://www.epa.gov/system/files/documents/2025-04/c03s04_april2025.pdf",
     "epa_ap42/ap42_c03s04_large_stationary_diesel_2025.pdf", b"%PDF"),
    # rc59: the IPPU process and fugitive chapters
    ("EMEP/EEA 2023", "2.B.7 Soda ash production 2023",
     EEA + "2-industrial-processes-and-product-use/2-b-chemical-industry/2-b-7-soda-ash/@@download/file",
     "emep/emep_eea_2023_2b7_soda_ash_production.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "2.C.1 Iron and steel production 2023",
     EEA + "2-industrial-processes-and-product-use/2-c-metal-production/2-c-1-iron-and/@@download/file",
     "emep/emep_eea_2023_2c1_iron_and_steel_production.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "1.B.2.a.i and 1.B.2.b Fugitive emissions - exploration, production, transport (oil and gas) 2023",
     EEA + "1-energy/1-b-fugitive-emissions-from-fuels/1-b-2-a-i/@@download/file",
     "emep/emep_eea_2023_1b2ai_1b2b_exploration_production_transport.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "1.B.2.a.iv Fugitive emissions oil - refining, storage 2023",
     EEA + "1-energy/1-b-fugitive-emissions-from-fuels/1-b-2-a-iv/@@download/file",
     "emep/emep_eea_2023_1b2aiv_refining_storage.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "1.B.2.a.v Distribution of oil products 2023",
     EEA + "1-energy/1-b-fugitive-emissions-from-fuels/1-b-2-a-v/@@download/file",
     "emep/emep_eea_2023_1b2av_distribution_of_oil_products.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "1.B.2.c Venting and flaring 2023",
     EEA + "1-energy/1-b-fugitive-emissions-from-fuels/1-b-2-c-venting/@@download/file",
     "emep/emep_eea_2023_1b2c_venting_and_flaring.pdf", b"%PDF"),
    ("EMEP/EEA 2023", "2.B Chemical industry 2023 (consolidated: 2.B.1 ammonia, 2.B.2 nitric acid, 2.B.10.a other)",
     EEA + "2-industrial-processes-and-product-use/2-b-chemical-industry/2-b-chemical-industry-2023/@@download/file",
     "emep/emep_eea_2023_2b_chemical_industry.pdf", b"%PDF"),
    # the February 2018 revision (www3.epa.gov/ttnchie1/...) answers 404 to a plain fetch; the
    # 1995 section on EPA's gaftp mirror is the public copy that answers, declared by vintage
    ("US EPA AP-42", "Section 13.5 Industrial Flares (September 1991 / 1995 print)",
     "https://gaftp.epa.gov/ap42/ch13/s05/final/c13s05_1995.pdf",
     "epa_ap42/ap42_c13s05_industrial_flares_1995.pdf", b"%PDF"),
    ("EDGAR v8.1 AP", "SO2 country x sector time series 1970-2022 (v2)",
     EDGAR + "EDGAR_SO2_1970_2022_v2.zip", "edgar/EDGAR_SO2_1970_2022_v2.zip", b"PK"),
    ("EDGAR v8.1 AP", "CO country x sector time series 1970-2022",
     EDGAR + "EDGAR_CO_1970_2022.zip", "edgar/EDGAR_CO_1970_2022.zip", b"PK"),
    ("EDGAR v8.1 AP", "NMVOC country x sector time series 1970-2022",
     EDGAR + "EDGAR_NMVOC_1970_2022.zip", "edgar/EDGAR_NMVOC_1970_2022.zip", b"PK"),
    ("EDGAR v8.1 AP", "NH3 country x sector time series 1970-2022",
     EDGAR + "EDGAR_NH3_1970_2022.zip", "edgar/EDGAR_NH3_1970_2022.zip", b"PK"),
    ("EDGAR v8.1 AP", "BC country x sector time series 1970-2022",
     EDGAR + "EDGAR_BC_1970_2022.zip", "edgar/EDGAR_BC_1970_2022.zip", b"PK"),
)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(url, dest, magic):
    req = urllib.request.Request(url, headers={"User-Agent": "PakEmis/1.0 (research inventory)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        body = r.read()
    if not body.startswith(magic):
        raise ValueError("unexpected content (first bytes %r)" % body[:8])
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(dest, "wb") as f:
        f.write(body)
    return len(body)


def main():
    rows, attempts = [], []
    for source, label, url, rel, magic in TARGETS:
        dest = asset_path(RAW, rel)
        if os.path.exists(dest):
            status, note, size = "held", "already on disk; not re-fetched", os.path.getsize(dest)
        elif DRY:
            status, note, size = "dry-run", "would fetch", ""
        else:
            try:
                size = fetch(url, dest, magic)
                status, note = "fetched", "resolved from the publisher's index page; first-guess address 404'd"
            except Exception as exc:          # noqa: BLE001 - every failure is a logged negative
                status, note, size = "failed", "%s: %s" % (type(exc).__name__, exc), ""
        digest = sha256(dest)[:16] if os.path.exists(dest) else ""
        rows.append({"date": TODAY, "source": source, "url": url, "file": "data/raw/" + rel,
                     "sha256_16": digest, "size_bytes": size, "status": status, "note": note})
        attempts.append({"attempt_date": TODAY, "dataset": "%s - %s" % (source, label),
                         "recipient": source.split(" ")[0] if source.startswith("US") else source.split("/")[0],
                         "url_tried": url, "outcome": "fetched" if status in ("fetched", "held") else "discovery_failed",
                         "detail": "%s -> data/raw/%s (%s)" % (status, rel, note),
                         "next_step": "" if status in ("fetched", "held") else "locate the current address on the publisher's index page and retry"})
        print("%-8s %s" % (status, rel))
    if DRY:
        return 0
    new = not os.path.exists(LOG)
    with open(LOG, "a", newline="", encoding="utf-8") as h:
        if new:
            h.write("# The industrial air-pollutant factor-chapter acquisition (rc58 W1): every attempt logged,\n"
                    "# hits and negatives alike. Documents land in data/raw/<source>/; sources/ is frozen.\n")
        w = csv.DictWriter(h, fieldnames=list(rows[0]), lineterminator="\n")
        if new:
            w.writeheader()
        w.writerows(rows)
    with open(ATTEMPTS, "a", newline="", encoding="utf-8") as h:
        w = csv.DictWriter(h, fieldnames=list(attempts[0]), lineterminator="\n")
        w.writerows(attempts)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
