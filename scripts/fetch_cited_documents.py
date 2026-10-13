#!/usr/bin/env python3
"""Fetch and KEEP the single documents and web pages the inventory cites.

WHY THIS EXISTS. data/catalog/not_retained_register.csv listed sources that were "read live and
not snapshotted": two news articles on the fuel-standard dates, a product page, four airline
and route pages, the UNFCCC CDM project pages, two WITS pages, a central-bank supplement whose
address was said never to have been recorded (it was), one Zenodo file and several listed-
company reports. Each is one address. None needed a parser; they needed someone to save the
bytes. This script is that route, and DOCUMENTS below is the list.

WHAT IT DOES for each document, in order:
  1. asks the publisher's own address and keeps the response under data/raw/<source>/;
  2. if the publisher refuses, serves a challenge page or an empty body, asks the Internet
     Archive for the capture nearest the date the page was read, and keeps THAT, recorded as
     an archive copy with the capture's timestamp;
  3. if neither answers, writes nothing and logs the document as one the maintainer must save
     from a browser.

A CHALLENGE PAGE IS NOT A DOCUMENT. The CDM site answers an unattended client with a 212-byte
Incapsula page and HTTP 200. Kept as a document, that would be a held file that says nothing,
under the name of the source. blocked() refuses it, and nothing here tries to get past it.

AN ARCHIVE COPY IS LABELLED. It is evidence of what the page said on the capture date, which
for a page read in August 2026 may be closer to what was read than what the publisher serves
today. RETRIEVALS.csv carries `via=internet-archive` and the archive address.

A SAVED PAGE IS NOT THE CITED FACT. Several of these sites build the page in the reader's
browser: the bytes they serve an unattended client hold the menu and none of the content.
The first sweep saved PIA's fleet page (219 kB) and it names no aircraft. So each document
that a table cites for a stated fact carries, in EXPECT, the words or figures that fact
needs, and --verify reads the held file and says whether they are there. A page held without
them is reported as `empty-of-it`: it is kept, because it is what the publisher served, and it is
NOT counted as holding the citation. tests/test_document_retention.py runs --verify.

Every attempt is a row of data/raw/ACQUISITION_LOG_retention_2026_10.csv: hits, archive
copies and failures alike.

Usage:  python3 scripts/fetch_cited_documents.py [--only KEY[,KEY...]] [--list] [--verify]
"""
import argparse
import csv
import datetime
import json
import os
import sys
import urllib.parse

from pkinv.core import retention

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = os.path.join(ROOT, "data", "raw", "ACQUISITION_LOG_retention_2026_10.csv")
LOG_FIELDS = ["date", "source", "url", "file", "sha256_16", "size_bytes", "status", "note"]
LOG_HEADER = (
    "# The retention sweep (2026-10-12): every cited document that the project had read and\n"
    "# not kept, fetched and held. One row per attempt, hits and failures alike. status:\n"
    "# held (publisher's address), held-archive (Internet Archive capture), held-local (copied\n"
    "# from another directory on the maintainer's machine or restored from git history),\n"
    "# blocked (the publisher refuses an unattended client), not-found, error.\n")

# key: (data/raw source directory, file name, address, date the page was read (YYYYMMDD,
#       steers the archive lookup), what cites it)
DOCUMENTS = {
    # --- road-fuel sulphur: the dates of the fuel-standard mandates -------------------------
    "dawn-1434195": ("web_snapshots/dawn", "dawn_news_1434195.html",
                     "https://www.dawn.com/news/1434195", "20260808",
                     "transport/fuel_sulfur_by_year.csv: diesel imports to Euro-II 500 ppm"),
    "dawn-1567870": ("web_snapshots/dawn", "dawn_news_1567870.html",
                     "https://www.dawn.com/news/1567870", "20260808",
                     "transport/fuel_sulfur_by_year.csv: Euro-V imports mandatory"),
    "pso-euro5": ("web_snapshots/pso", "pso_premier_euro_5.html",
                  "https://psopk.com/en/fuels/retail-fuels/premier-euro-5", "20260808",
                  "transport/fuel_sulfur_by_year.csv: Premier Euro 5 product sheet"),
    # --- aviation: fleet and route pages behind aircraft_family_shares_2023_24.csv -----------
    "pia-fleet": ("web_snapshots/pia", "piac_about_us_fleet.html",
                  "https://www.piac.com.pk/corporate/about-us/fleet", "20260808",
                  "aviation/aircraft_family_shares_2023_24.csv: PIA fleet"),
    "airblue-flightinfo": ("web_snapshots/airblue", "airblue_flightinfo.html",
                           "https://www.airblue.com/flightinfo/", "20260808",
                           "aviation/aircraft_family_shares_2023_24.csv: Airblue routes"),
    "serene-destinations": ("web_snapshots/sereneair", "sereneair_destinations.html",
                            "https://www.sereneair.com/destinations", "20260808",
                            "aviation/aircraft_family_shares_2023_24.csv: Serene Air routes"),
    "aeroroutes-231102": ("web_snapshots/aeroroutes", "aeroroutes_231102-erpkx.html",
                          "https://www.aeroroutes.com/eng/231102-erpkx", "20260808",
                          "aviation/aircraft_family_shares_2023_24.csv: route filing"),
    # The address the table cites (231102-erpkx) answers 404 and no archive holds it. This is
    # the same publisher's filing for the same service two months on: Serene Air ER901/902,
    # Islamabad to Beijing Daxing, equipment 332. Held as a witness to the A330-200
    # international occurrence; the table's citation is not rewritten from it.
    "aeroroutes-240119": ("web_snapshots/aeroroutes", "aeroroutes_240119-er1q24cn.html",
                          "https://www.aeroroutes.com/eng/240119-er1q24cn", "20260808",
                          "aviation/aircraft_family_shares_2023_24.csv: witness for the SEP "
                          "A332 international row, whose cited address 231102-erpkx is gone"),
    "app-pia-flights": ("web_snapshots/app",
                        "app_pia_increases_flights.html",
                        "https://www.app.com.pk/national/pia-increases-flights-to-"
                        "international-domestic-routes/", "20260808",
                        "aviation/aircraft_family_shares_2023_24.csv: PIA frequencies"),
    "dawn-1718018": ("web_snapshots/dawn", "dawn_news_1718018.html",
                     "https://www.dawn.com/news/1718018", "20260808",
                     "aviation/aircraft_family_shares_2023_24.csv"),
    "dawn-1744716": ("web_snapshots/dawn", "dawn_news_1744716.html",
                     "https://www.dawn.com/news/1744716", "20260808",
                     "aviation/aircraft_family_shares_2023_24.csv"),
    # --- nitric acid: the UNFCCC CDM project and review pages --------------------------------
    # Project 0557 is Pakarab (Multan), reference TUEV-SUED1155134039.49; project 5461 is
    # Fatima (Sadiqabad), reference RWTUV1322686352.38. The Pakarab issuance list is on the
    # first crediting period's page (?cp=1); the plain /view shows the renewal request.
    "cdm-pakarab-cp1": ("unfccc_cdm", "cdm_project_TUEV-SUED1155134039.49_view_cp1.html",
                        "https://cdm.unfccc.int/Projects/DB/TUEV-SUED1155134039.49/view?cp=1",
                        "20260808", "ippu/nitric_acid_monitoring.csv: Pakarab project 0557, "
                        "first crediting period (the issuance list)"),
    "cdm-pakarab-cp2": ("unfccc_cdm", "cdm_project_TUEV-SUED1155134039.49_view_cp2.html",
                        "https://cdm.unfccc.int/Projects/DB/TUEV-SUED1155134039.49/view?cp=2",
                        "20260808", "ippu/nitric_acid_monitoring.csv: Pakarab project 0557, "
                        "second crediting period"),
    "cdm-fatima": ("unfccc_cdm", "cdm_project_RWTUV1322686352.38_view.html",
                   "https://cdm.unfccc.int/Projects/DB/RWTUV1322686352.38/view",
                   "20260808", "ippu/nitric_acid_monitoring.csv: Fatima project 5461"),
    "cdm-review-uwga": ("unfccc_cdm", "cdm_review_UWGA8K2YM2Z0BQ48PVAFDVBVAGLZ8P.html",
                        "https://cdm.unfccc.int/Projects/DB/TUEV-SUED1155134039.49/iProcess/"
                        "DNV-CUK1218364087.49/ReviewInitialComments/"
                        "UWGA8K2YM2Z0BQ48PVAFDVBVAGLZ8P", "20260808",
                        "ippu/nitric_acid_monitoring_detail.csv: review comments"),
    "cdm-review-qrcj": ("unfccc_cdm", "cdm_review_QRCJ4TFXFE2NXMFL2PML2A4DIL6F01.html",
                        "https://cdm.unfccc.int/Projects/DB/TUEV-SUED1155134039.49/iProcess/"
                        "DNV-CUK1218364087.49/ReviewInitialComments/"
                        "QRCJ4TFXFE2NXMFL2PML2A4DIL6F01", "20260808",
                        "ippu/nitric_acid_monitoring_detail.csv: review comments"),
    # The Pakarab project page without its paging parameter (the renewal request view);
    # the monitoring-period request the two review records belong to; and the three review
    # forms of that request the archive captured in 2008. The two ReviewInitialComments
    # addresses themselves were never captured by anyone and the site refuses unattended
    # clients, so those two stay for a browser.
    "cdm-pakarab-view": ("unfccc_cdm", "cdm_project_TUEV-SUED1155134039.49_view.html",
                         "https://cdm.unfccc.int/Projects/DB/TUEV-SUED1155134039.49/view",
                         "20260808", "ippu/nitric_acid_monitoring.csv: Pakarab project 0557, "
                         "renewal request view"),
    "cdm-pakarab-request": ("unfccc_cdm",
                           "cdm_request_DNV-CUK1218364087.49_view.html",
                           "https://cdm.unfccc.int/Projects/DB/TUEV-SUED1155134039.49/iProcess/"
                           "DNV-CUK1218364087.49/view", "20240811",
                           "ippu/nitric_acid_monitoring_detail.csv: the issuance request the "
                           "review comments were filed against"),
    "cdm-review-6wing": ("unfccc_cdm", "cdm_review_6WINGBMJ7VZ88ZAJJZSILABRUNR7S2_display.html",
                         "http://cdm.unfccc.int:80/Projects/DB/TUEV-SUED1155134039.49/iProcess/"
                         "DNV-CUK1218364087.49/Review/6WINGBMJ7VZ88ZAJJZSILABRUNR7S2/display",
                         "20081229", "ippu/nitric_acid_monitoring_detail.csv: request for review"),
    "cdm-review-uskov": ("unfccc_cdm", "cdm_review_USKOVPTSH6YH05GRDI87EF7ACD42NW_display.html",
                         "http://cdm.unfccc.int:80/Projects/DB/TUEV-SUED1155134039.49/iProcess/"
                         "DNV-CUK1218364087.49/Review/USKOVPTSH6YH05GRDI87EF7ACD42NW/display",
                         "20081229", "ippu/nitric_acid_monitoring_detail.csv: request for review"),
    "cdm-review-xnqe3": ("unfccc_cdm", "cdm_review_XNQE3NN43K4LQ7ATG13NX3LPGOZYT0_display.html",
                         "http://cdm.unfccc.int:80/Projects/DB/TUEV-SUED1155134039.49/iProcess/"
                         "DNV-CUK1218364087.49/Review/XNQE3NN43K4LQ7ATG13NX3LPGOZYT0/display",
                         "20081229", "ippu/nitric_acid_monitoring_detail.csv: request for review"),
    # --- clinker trade: the two WITS pages behind clinker_trade_annual.csv -------------------
    "wits-pak-exports-2022": ("wits", "wits_PAK_2022_exports_252310.html",
                              "https://wits.worldbank.org/trade/comtrade/en/country/PAK/year/"
                              "2022/tradeflow/Exports/partner/ALL/product/252310", "20260815",
                              "ippu/clinker_trade_annual.csv: exports 2022"),
    "wits-all-imports-2022": ("wits", "wits_ALL_2022_imports_WLD_252310.html",
                              "https://wits.worldbank.org/trade/comtrade/en/country/ALL/year/"
                              "2022/tradeflow/Imports/partner/WLD/product/252310", "20260815",
                              "ippu/clinker_trade_annual.csv: imports 2022"),
    # --- single published files ---------------------------------------------------------------
    # The address in references.bib (…/reports/annual/aarFY24/Statistical-Supplement/
    # Complete.pdf) now redirects to an http address that times out; the https form of the
    # redirect target serves the file. "A site is down" was, again, a wrong address.
    "sbp-supplement-fy24": ("sbp", "sbp_annual_report_fy24_statistical_supplement.pdf",
                            "https://www.sbp.org.pk/assets/document/publications/reports/"
                            "annual/aarFY24/Statistical-Supplement/Complete.pdf", "20260808",
                            "ippu/national_activity.csv: cement fiscal series"),
    # The record's ?download=1 address answers an unattended client with 403; the record's
    # own API serves the same file, whose md5 the record publishes.
    "zenodo-kilns": ("brick_kilns", "zenodo_14718244_Brick_Kilns_IGP_PK-Main.csv",
                     "https://zenodo.org/api/records/14718244/files/"
                     "Brick_Kilns_IGP_PK-Main.csv/content", "20260808",
                     "data/ml/brick_kilns_pk.csv: Hamdani et al. 2025 published file"),
    "psx-250354": ("company_reports/fertilizer", "psx_document_250354.pdf",
                   "https://dps.psx.com.pk/download/document/250354.pdf", "20260808",
                   "ippu/chemical_plant_activity.csv: Fatima annual 2024 as cited"),
    "psx-228733": ("company_reports/fertilizer", "psx_document_228733.pdf",
                   "https://dps.psx.com.pk/download/document/228733.pdf", "20260808",
                   "ippu/chemical_plant_activity.csv: Agritech annual 2024 as cited"),
    "psx-250529": ("company_reports/fertilizer", "psx_files_attachment_250529.pdf",
                   "https://www.psx.com.pk/psx/files-attachment/?file=250529.pdf", "20260808",
                   "ippu/chemical_plant_activity.csv"),
    # --- documents a register row called archived that were not in the archive -------------
    # The WHO/UNICEF JMP household country file: the row pointed at sources/OGRA.
    "jmp-pakistan": ("who_unicef_jmp", "JMP_2025_PAK_Pakistan_household.xlsx",
                     "https://washdata.org/data/country/PAK/household/download", "20260808",
                     "wastewater/sanitation_shares.csv: JMP household country file"),
    # Pakistan Railways publishes no 2014-15 Year Book today; its earliest is 2015-16, whose
    # Principal Statistics carry the two years the fuel table cites the 2014-15 edition for.
    "railways-yearbook-2015-16": ("pakistan_railways", "ybook201516.pdf",
                                  "https://www.pakrail.gov.pk/images/yearbook/ybook201516.pdf",
                                  "20260808",
                                  "railways/fuel_consumption.csv: FY2014 and FY2015 rows"),
    "railways-yearbook-2014-15": ("pakistan_railways", "yearbook2014_15.pdf",
                                  "https://www.pakrail.gov.pk/images/yearbook/yearbook2014_15.pdf",
                                  "20200101",
                                  "railways/fuel_consumption.csv: the edition the table names"),
    # --- producers cited by their home page ----------------------------------------------------
    "ffc-home": ("web_snapshots/ffc", "ffc_com_pk_home.html", "https://ffc.com.pk/",
                 "20260808", "ippu/chemical_plant_activity.csv: source_id ffc_public"),
    "ffbl-home": ("web_snapshots/ffbl", "ffbl_com_home.html", "https://www.ffbl.com/",
                  "20260808", "ippu/chemical_plant_activity.csv: source_id ffbl_public"),
    "fatima-home": ("web_snapshots/fatima", "fatima_group_com_home.html",
                    "https://www.fatima-group.com/", "20260808",
                    "ippu/chemical_plant_activity.csv: source_id fatima_annual_2022"),
    # --- found by the archived-row audit: cited by a file the register called archived -------
    "cherat-annual-2024": ("company_reports/cement", "Cherat_Annual_Report_2024.pdf",
        "https://gfg.com.pk/cccl/wp-content/uploads/2024/09/CCL-A.R.-2024-Final.pdf", "20260808",
        "ippu/cement_producer_census_2023_24.csv, company_boundary_audit.csv, "
        "company_clinker_2023_24.csv: the sixteenth producer's report"),
    "census2023-t1-national": ("pbs/population_census_2023", "table_1_national.xlsx",
        "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_national.xlsx", "20260808",
        "waste/population_district.csv: 7th Population and Housing Census 2023, Table 1"),
    "census2023-t1-punjab_districts": ("pbs/population_census_2023", "table_1_punjab_districts.xlsx",
        "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_punjab_districts.xlsx", "20260808",
        "waste/population_district.csv: 7th Population and Housing Census 2023, Table 1"),
    "census2023-t1-sindh_districts": ("pbs/population_census_2023", "table_1_sindh_districts.xlsx",
        "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_sindh_districts.xlsx", "20260808",
        "waste/population_district.csv: 7th Population and Housing Census 2023, Table 1"),
    "census2023-t1-kp_districts": ("pbs/population_census_2023", "table_1_kp_districts.xlsx",
        "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_kp_districts.xlsx", "20260808",
        "waste/population_district.csv: 7th Population and Housing Census 2023, Table 1"),
    "census2023-t1-balochistan_districts": ("pbs/population_census_2023", "table_1_balochistan_districts.xlsx",
        "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_balochistan_districts.xlsx", "20260808",
        "waste/population_district.csv: 7th Population and Housing Census 2023, Table 1"),
    "census2023-t1-islamabad": ("pbs/population_census_2023", "table_1_islamabad.xlsx",
        "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_islamabad.xlsx", "20260808",
        "waste/population_district.csv: 7th Population and Housing Census 2023, Table 1"),
    "census2023-t1-punjab_province": ("pbs/population_census_2023", "table_1_punjab_province.xlsx",
        "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_punjab_province.xlsx", "20260808",
        "waste/population_district.csv: 7th Population and Housing Census 2023, Table 1"),
    "census2023-t1-sindh_province": ("pbs/population_census_2023", "table_1_sindh_province.xlsx",
        "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_sindh_province.xlsx", "20260808",
        "waste/population_district.csv: 7th Population and Housing Census 2023, Table 1"),
    "census2023-t1-kp_province": ("pbs/population_census_2023", "table_1_kp_province.xlsx",
        "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_kp_province.xlsx", "20260808",
        "waste/population_district.csv: 7th Population and Housing Census 2023, Table 1"),
    "census2023-t1-balochistan_province": ("pbs/population_census_2023", "table_1_balochistan_province.xlsx",
        "https://www.pbs.gov.pk/wp-content/uploads/2020/07/table_1_balochistan_province.xlsx", "20260808",
        "waste/population_district.csv: 7th Population and Housing Census 2023, Table 1"),
    "brecorder-40220197": ("web_snapshots/brecorder", "brecorder_news_40220197.html",
        "https://www.brecorder.com/news/40220197", "20260808",
        "aviation/route_evidence_2023_24.csv"),
    "aeroroutes-230725": ("web_snapshots/aeroroutes", "aeroroutes_230725-9pjul23uet.html",
        "https://www.aeroroutes.com/eng/230725-9pjul23uet", "20260808",
        "aviation/route_evidence_2023_24.csv"),
    "app-fly-jinnah-muscat": ("web_snapshots/app", "app_fly_jinnah_islamabad_muscat.html",
        "https://www.app.com.pk/domestic/fly-jinnah-launches-another-non-stop-flights-from-islamabad-muscat/", "20260808",
        "aviation/route_evidence_2023_24.csv"),
    "airblue-schedule": ("web_snapshots/airblue", "airblue_schedule_popup.html",
        "https://www.airblue.com/Sched/schedule_popup.asp", "20260808",
        "aviation/route_evidence_2023_24.csv"),
    "flightsfrom-khi-pa": ("web_snapshots/flightsfrom", "flightsfrom_KHI_PA.html",
        "https://www.flightsfrom.com/KHI/PA", "20260808",
        "aviation/route_evidence_2023_24.csv"),
    "airsial-destinations": ("web_snapshots/airsial", "airsial_destinations.html",
        "https://www.airsial.com/destinations", "20260808",
        "aviation/route_evidence_2023_24.csv"),
    "wikipedia-sereneair": ("web_snapshots/wikipedia", "wikipedia_SereneAir.html",
        "https://en.wikipedia.org/wiki/SereneAir", "20260808",
        "aviation/route_evidence_2023_24.csv"),
    "reddit-dubai-199jved": ("web_snapshots/reddit", "reddit_dubai_199jved.html",
        "https://www.reddit.com/r/dubai/comments/199jved", "20260808",
        "aviation/route_evidence_2023_24.csv"),
    "reddit-islamabad-15e8vvq": ("web_snapshots/reddit", "reddit_islamabad_15e8vvq.html",
        "https://www.reddit.com/r/islamabad/comments/15e8vvq/", "20260808",
        "aviation/route_evidence_2023_24.csv"),
    "reddit-pakistan-174gchc": ("web_snapshots/reddit", "reddit_pakistan_174gchc.html",
        "https://www.reddit.com/r/pakistan/comments/174gchc", "20260808",
        "aviation/route_evidence_2023_24.csv"),
}

# What the citing table needs each page to say. Patterns are searched in the page's text with
# tags removed and thousands separators dropped. A key with no entry is a file whose content
# is checked elsewhere (a PDF read by pdftotext, a workbook, a digest the publisher prints).
EXPECT = {
    "dawn-1434195": [r"Euro.?II", r"500\s?ppm"],
    "dawn-1567870": [r"Euro.?V"],
    "pso-euro5": [r"500\s?ppm", r"10\s?ppm"],
    "pia-fleet": [r"A320|Airbus", r"777|Boeing"],
    "airblue-flightinfo": [r"A32[01]|Airbus"],
    "serene-destinations": [r"A330|737"],
    "aeroroutes-231102": [r"332|A330"],
    "aeroroutes-240119": [r"ER901", r"332"],
    "app-pia-flights": [r"A320", r"ATR"],
    "dawn-1718018": [r"A320"],
    "dawn-1744716": [r"A320"],
    "cdm-fatima": [r"171471", r"991104", r"399699"],
    "cdm-pakarab-cp1": [r"76499", r"175219"],
    "cdm-review-uwga": [r"[Rr]eview"],
    "cdm-review-qrcj": [r"[Rr]eview"],
    "wits-pak-exports-2022": [r"1341580000"],
    "wits-all-imports-2022": [r"Pakistan.{0,80}3999000"],
    "ffc-home": [r"Goth Machhi", r"Mirpur Mathelo"],
    "ffbl-home": [r"Fauji|FFBL"],
    "fatima-home": [r"Fatima"],
    "aeroroutes-230725": [r"Quetta"],
    "airblue-schedule": [r"Karachi", r"Islamabad"],
    "brecorder-40220197": [r"Airblue|airblue", r"Lahore"],
    "flightsfrom-khi-pa": [r"Quetta"],
    "airsial-destinations": [r"Islamabad"],
    "wikipedia-sereneair": [r"A330", r"Jeddah"],
    "app-fly-jinnah-muscat": [r"Muscat"],
    "reddit-dubai-199jved": [r"Serene"],
    "reddit-islamabad-15e8vvq": [r"Serene"],
    "reddit-pakistan-174gchc": [r"[Aa]irblue"],
}

CHALLENGES = (b"_Incapsula_Resource", b"Incapsula incident", b"Just a moment...",
              b"cf-browser-verification", b"Access Denied", b"Request unsuccessful",
              b"Attention Required! | Cloudflare", b"captcha-delivery")


def blocked(body):
    """True when the response is a refusal dressed as a page: a bot challenge, an access
    notice, or a body too small to be the document."""
    if len(body) < 600:
        return True
    head = body[:6000]
    return any(mark in head for mark in CHALLENGES) and len(body) < 20000


def log(row):
    fresh = not os.path.exists(LOG)
    with open(LOG, "a", encoding="utf-8", newline="") as handle:
        if fresh:
            handle.write(LOG_HEADER)
        writer = csv.DictWriter(handle, fieldnames=LOG_FIELDS, lineterminator="\n")
        if fresh:
            writer.writeheader()
        writer.writerow(row)


def _row(source, url, status, note, path=None):
    today = datetime.date.today().isoformat()
    if path is None:
        return {"date": today, "source": source, "url": url, "file": "", "sha256_16": "",
                "size_bytes": "", "status": status, "note": note}
    with open(path, "rb") as handle:
        body = handle.read()
    return {"date": today, "source": source, "url": url,
            "file": os.path.relpath(path, ROOT), "sha256_16": retention.sha256_of(body)[:16],
            "size_bytes": len(body), "status": status, "note": note}


def archive_captures(url, near, limit=6):
    """[(capture timestamp, address of the unmodified capture)], nearest `near` first.

    Asks the archive's capture index, not its "availability" lookup: the lookup answered
    "no snapshot" for a CDM page the index lists twelve captures of."""
    api = ("https://web.archive.org/cdx/search/cdx?url=%s&output=json&filter=statuscode:200"
           "&fl=timestamp,original&collapse=digest&limit=400"
           % urllib.parse.quote(url, safe=""))
    try:      # the archive goes offline for minutes at a time; ask more than twice
        rows = json.loads(retention.get(api, attempts=4, timeout=90, pause=10.0))[1:]
    except (OSError, ValueError):
        return []
    wanted = int(near.ljust(14, "0"))
    rows.sort(key=lambda r: abs(int(r[0]) - wanted))
    # the id_ form returns the bytes as captured, without the archive's banner or rewriting
    return [(stamp, "https://web.archive.org/web/%sid_/%s" % (stamp, original))
            for stamp, original in rows[:limit]]


def acquire(key):
    source, name, url, near, cites = DOCUMENTS[key]
    try:
        body = retention.get(url, attempts=2, timeout=90)
        refused = blocked(body)
        why = ("the publisher answered with a challenge or an empty page (%d bytes)"
               % len(body)) if refused else ""
    except OSError as error:
        refused, why = True, "the publisher's address failed: %s" % str(error)[:200]
    if not refused:
        path = retention.keep(body, source, name, url, note=cites)
        log(_row(source, url, "held", cites, path))
        return "held", path
    # The archive captured this site's challenge page too, and files it as a good capture.
    # Walk outward from the date the page was read until a capture is a real page.
    captures = archive_captures(url, near)
    skipped = []
    for stamp, address in captures:
        try:
            body = retention.get(address, attempts=4, timeout=120, pause=10.0)
        except OSError as error:
            skipped.append("%s unreachable (%s)" % (stamp, str(error)[-60:]))
            continue
        if blocked(body):
            skipped.append("%s is a capture of the refusal page" % stamp)
            continue
        path = retention.keep(
            body, source, name, address, via="internet-archive",
            note="%s | Internet Archive capture %s of %s; kept because %s%s"
                 % (cites, stamp, url, why,
                    ("; nearer captures passed over: " + "; ".join(skipped)) if skipped else ""))
        log(_row(source, address, "held-archive",
                 "capture %s of %s; %s" % (stamp, url, why), path))
        return "held-archive", path
    why += ("; archive captures tried: " + "; ".join(skipped)) if skipped else \
        "; the Internet Archive lists no capture"
    status = "blocked" if "challenge" in why else "not-found"
    log(_row(source, url, status, "%s. %s. To hold it: open the address in a browser, save "
             "the page, and place it at data/raw/%s/%s" % (cites, why, source, name)))
    return status, None


def _text(path):
    """A page's text as a reader sees it: scripts, styles and tags removed."""
    import html
    import re
    with open(path, encoding="utf-8", errors="replace") as handle:
        page = handle.read()
    page = re.sub(r"(?s)<script.*?</script>|<style.*?</style>", " ", page)
    page = html.unescape(re.sub(r"<[^>]+>", " ", page))
    return re.sub(r"(?<=\d),(?=\d)", "", re.sub(r"\s+", " ", page))


def _copies(key):
    """Every held file for a document: the first one kept and any later, dated ones."""
    source, name = DOCUMENTS[key][:2]
    directory = os.path.join(retention.RAW, source)
    stem, ext = os.path.splitext(name)
    if not os.path.isdir(directory):
        return []
    return sorted(os.path.join(directory, f) for f in os.listdir(directory)
                  if f == name or (f.startswith(stem + "__") and f.endswith(ext)))


def _says(key, path):
    """The EXPECT patterns `path` does not satisfy (empty when it says everything)."""
    import re
    if key not in EXPECT:
        return []
    text = _text(path)
    return [p for p in EXPECT[key] if not re.search(p, text)]


def verify(keys=None):
    """{key: (state, detail)} from the held files alone; no network.

    state: `held` (on disk, and saying what EXPECT needs or carrying no expectation),
    `empty-of-it` (on disk without the cited content: a script shell, a consent page, or an
    address that now serves a different article), `absent` (not on disk). A document with
    several held copies is `held` if any one of them carries the content."""
    out = {}
    for key in keys or DOCUMENTS:
        source, name = DOCUMENTS[key][:2]
        copies = _copies(key)
        if not copies:
            out[key] = ("absent", "data/raw/%s/%s" % (source, name))
            continue
        good = [c for c in copies if not _says(key, c)]
        if good:
            out[key] = ("held", os.path.relpath(good[0], ROOT))
        else:
            out[key] = ("empty-of-it", "the held page does not contain: "
                        + ", ".join(_says(key, copies[0])))
    return out


def improve(key, limit=12):
    """For a page held without its cited content: look through the archive's captures,
    nearest the reading date first, for one that carries it, and keep that capture BESIDE
    the page already held (retention.keep never overwrites). Returns the path or None."""
    source, name, url, near, cites = DOCUMENTS[key]
    tried = []
    for stamp, address in archive_captures(url, near, limit=limit):
        try:
            body = retention.get(address, attempts=3, timeout=120, pause=10.0)
        except OSError:
            tried.append(stamp + " unreachable")
            continue
        if blocked(body):
            tried.append(stamp + " refusal page")
            continue
        scratch = os.path.join(retention.RAW, source, ".probe_" + name)
        os.makedirs(os.path.dirname(scratch), exist_ok=True)
        with open(scratch, "wb") as handle:
            handle.write(body)
        missing = _says(key, scratch)
        os.remove(scratch)
        if missing:
            tried.append(stamp + " without the content")
            continue
        path = retention.keep(
            body, source, name, address, via="internet-archive",
            note="%s | Internet Archive capture %s of %s, kept because the page the "
                 "publisher serves an unattended client today does not carry the cited "
                 "content" % (cites, stamp, url))
        log(_row(source, address, "held-archive",
                 "capture %s of %s carries the cited content; the live page does not"
                 % (stamp, url), path))
        return path
    log(_row(source, url, "not-found",
             "%s. No archive capture carries the cited content (%s). To hold it: open the "
             "address in a browser, save the rendered page, and place it at data/raw/%s/%s"
             % (cites, "; ".join(tried) or "no captures listed", source, name)))
    return None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--only", default="")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--improve", action="store_true",
                        help="for pages held without their cited content, look for an "
                             "archive capture that carries it")
    parser.add_argument("--verify", action="store_true",
                        help="read the held files and report held / shell / absent; no network")
    args = parser.parse_args(argv)
    keys = [k for k in args.only.split(",") if k] or list(DOCUMENTS)
    if args.improve:
        for key, (state, _detail) in verify(keys).items():
            if state == "empty-of-it":
                path = improve(key)
                print("%-34s %s" % (key, os.path.relpath(path, ROOT) if path
                                    else "no capture carries the cited content"))
        return 0
    if args.verify:
        found = verify(keys)
        for key in keys:
            print("%-34s %-11s %s" % ((key,) + found[key]))
        tally = {s.replace("-", "_"): sum(1 for v in found.values() if v[0] == s)
                 for s in ("held", "empty-of-it", "absent")}
        print("%(held)d held, %(empty_of_it)d held without the cited content, "
              "%(absent)d absent" % tally)
        return 0
    if args.list:
        for key in keys:
            print("%-24s data/raw/%s/%s" % (key, DOCUMENTS[key][0], DOCUMENTS[key][1]))
        return 0
    missing = 0
    for key in keys:
        status, path = acquire(key)
        print("%-24s %-13s %s" % (key, status,
              ("%s (%d bytes)" % (os.path.relpath(path, ROOT), os.path.getsize(path)))
              if path else "NOT HELD - see the log"))
        missing += path is None
    print("%d of %d held; attempts logged in %s"
          % (len(keys) - missing, len(keys), os.path.relpath(LOG, ROOT)))
    return 1 if missing else 0


if __name__ == "__main__":
    sys.exit(main())
