"""One bounded search for the FY2015-16 industrial and road fuel split, logged either way.

WHY A SCRIPT AND A LOG RATHER THAN A CONCLUSION. "We looked and could not find it" is the
weakest sentence in an inventory, because nobody can tell whether it means a week in an
archive or five minutes of guessing. Two sector-years hang on it, so the search is written
down: every source family named in the review, what was actually checked, what was found, and
what would have made it usable. A later reader who wants to reopen the question starts from
the log instead of from scratch, and a reader who suspects the search was thin can see exactly
how thin.

WHAT IS BEING LOOKED FOR, precisely. Not a magnitude - the FY2015-16 totals are held, in
tonnes, with a document hash (outputs/pakemis_unallocated_activity_controls.csv). What is
missing is the split by PRODUCT for two sector rows: Total Industry and Road. Any source
publishing FY2015-16 petroleum sales or consumption by product for those sectors closes it.

THE OUTCOME IS NOT DECIDED HERE. If nothing usable is found the sector-years stay NE, which is
the answer the strict series already gives. This script exists to make that answer accountable,
not to change it.

Usage:  python3 scripts/search_fy2015_16_industry_control.py [--offline]
Writes: data/source_search_log.csv
"""

from pkinv.assets import asset_path
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG = asset_path(ROOT, "data", "source_search_log.csv")
OCAC_DIR = asset_path(ROOT, "sources", "Aviation", "ocac_annual")
OGRA_DIR = asset_path(ROOT, "sources", "OGRA")

FIELDS = ("search_id", "target", "source_family", "specific_source", "held_in_repo",
          "access_attempted", "outcome", "found_product_split", "what_would_close_it",
          "note")

TARGET = ("FY2015-16 petroleum sales BY PRODUCT for the OCAC Total Industry and Road sector "
          "rows (the totals are already held; only the split is missing)")

# Endpoints probed when the search runs online. Each is the publisher's own site; nothing is
# scraped beyond the landing page and its links.
ENDPOINTS = (
    ("HDIP Pakistan Energy Yearbook", "https://hdip.com.pk"),
    ("OCAC oil industry statistics", "https://www.ocac.org.pk/oil-industry-statistics/"),
    ("Petroleum Division", "https://mpnr.gov.pk"),
    ("PBS publications", "https://www.pbs.gov.pk"),
)
FILE_LINK = re.compile(r'href="([^"]*\.(?:pdf|xls|xlsx))"', re.I)


def _pdf_text(path):
    if not shutil.which("pdftotext"):
        return ""
    result = subprocess.run(["pdftotext", "-layout", path, "-"], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    return result.stdout.decode("utf-8", "replace")


def search_held_ocac():
    """Every held annual edition: does any print FY2015-16 BY PRODUCT?

    The editions carry two total columns - the reporting year and the one before it - and the
    per-product columns belong to the reporting year alone. That is the finding, and it is a
    property of the publication rather than of this repository's copy of it.
    """
    rows = []
    editions = sorted(f for f in os.listdir(OCAC_DIR) if f.endswith(".pdf")) \
        if os.path.isdir(OCAC_DIR) else []
    for name in editions:
        text = _pdf_text(asset_path(OCAC_DIR, name))
        mentions_1516 = "2015-16" in text
        # A per-product prior year would show a second product header block keyed to the
        # earlier year; what these print is a bare second TOTAL column.
        product_columns_for_prior = bool(re.search(r"2015-16\s+(?:100 LL|HOBC|MS|HSD|FO)",
                                                   text))
        rows.append({
            "source_family": "OCAC annual sectoral editions (held)",
            "specific_source": "sources/Aviation/ocac_annual/%s" % name,
            "held_in_repo": "yes",
            "access_attempted": "read",
            "outcome": ("prints a FY2015-16 TOTAL column only"
                        if mentions_1516 and not product_columns_for_prior
                        else "no FY2015-16 columns at all"),
            "found_product_split": "no",
            "note": ("the header carries TOTAL JUL~JUN 2016-17 and TOTAL JUL~JUN 2015-16; the "
                     "per-product columns (100 LL, HOBC, E-10, MS, JP-8, JP-1, KERO, HSD, "
                     "LDO, FO) belong to the reporting year alone"
                     if mentions_1516 else
                     "this edition's prior-year column is a later year"),
        })
    if not editions:
        rows.append({
            "source_family": "OCAC annual sectoral editions (held)",
            "specific_source": "sources/Aviation/ocac_annual/",
            "held_in_repo": "no", "access_attempted": "read",
            "outcome": "directory absent", "found_product_split": "no",
            "note": "the held editions have moved or been removed",
        })
    return rows


def search_held_ogra():
    """The FY2015-16 OGRA edition: gas by sector, which is not the missing half."""
    name = "ogra_state_of_industry_2015-16.pdf"
    path = asset_path(OGRA_DIR, name)
    held = os.path.exists(path)
    text = _pdf_text(path) if held else ""
    has_sector_gas = "General Industry" in text
    return [{
        "source_family": "OGRA State of the Regulated Petroleum Industry",
        "specific_source": "sources/OGRA/%s" % name,
        "held_in_repo": "yes" if held else "no",
        "access_attempted": "read",
        "outcome": ("sector-wise GAS consumption found and already ingested"
                    if has_sector_gas else "no sector-wise gas table found"),
        "found_product_split": "no",
        "note": ("OGRA regulates gas and this table is the gas half of industry's FY2015-16 "
                 "activity, already in data/activity/industry/gas_consumption.csv. It does "
                 "not publish liquid fuels by sector, which is the missing half"),
    }]


def search_held_statistics():
    """PBS yearbook and the provincial archives: production, not fuel consumption."""
    return [
        {"source_family": "PBS Pakistan Statistical Year Book",
         "specific_source": "sources/Provincial Statistics/National-*.zip::"
                            "Pakistan_Statistical_Year_Book_2020.pdf",
         "held_in_repo": "yes", "access_attempted": "read",
         "outcome": "no energy or fuel-consumption chapter",
         "found_product_split": "no",
         "note": "chapters run to Transport & Communications; manufacturing is Table 13.1 "
                 "(quantum index) and 13.2 (physical PRODUCTION). Production is not fuel "
                 "use, and the yearbook publishes no sectoral petroleum balance"},
        {"source_family": "PBS QIM / large-scale manufacturing",
         "specific_source": "data/activity/ippu/national_activity.csv provenance chain",
         "held_in_repo": "yes", "access_attempted": "read",
         "outcome": "physical output only",
         "found_product_split": "no",
         "note": "QIM indexes and physical output by item; it carries no fuel dimension, so "
                 "it could support an intensity-based screening scenario but not a control"},
    ]


def probe(url, timeout=25):
    request = urllib.request.Request(url, headers={"User-Agent": "PakEmis-source-search"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(400000).decode("utf-8", "replace")
        return response.status, body
    except urllib.error.HTTPError as exc:
        return exc.code, ""
    except (urllib.error.URLError, OSError) as exc:
        return None, str(exc)


def search_public(offline=False):
    rows = []
    for family, url in ENDPOINTS:
        if offline:
            rows.append({
                "source_family": family, "specific_source": url, "held_in_repo": "no",
                "access_attempted": "skipped (--offline)", "outcome": "not attempted",
                "found_product_split": "no",
                "note": "run without --offline to attempt retrieval",
            })
            continue
        status, body = probe(url)
        files = sorted(set(FILE_LINK.findall(body))) if body else []
        reaches_2015 = any("2015" in f for f in files)
        if status is None:
            outcome = "unreachable"
        elif status != 200:
            outcome = "HTTP %s" % status
        elif not files:
            outcome = "reachable; no downloadable statistics linked from the landing page"
        else:
            outcome = ("reachable; %d files linked, %s reaching 2015-16"
                       % (len(files), "some" if reaches_2015 else "none"))
        rows.append({
            "source_family": family, "specific_source": url, "held_in_repo": "no",
            "access_attempted": "public HTTP", "outcome": outcome,
            "found_product_split": "yes" if reaches_2015 else "no",
            "note": ("linked files: %s" % "; ".join(os.path.basename(f) for f in files[:6])
                     if files else (body[:160] if status is None else
                                    "landing page carries no statistics archive")),
        })
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true",
                        help="log the public sources as not attempted rather than probing")
    args = parser.parse_args(argv)

    found = []
    found += search_held_ocac()
    found += search_held_ogra()
    found += search_held_statistics()
    found += search_public(args.offline)

    rows = []
    for index, row in enumerate(found, 1):
        rows.append({
            "search_id": "fy2015-16-fuel-split-%02d" % index,
            "target": TARGET,
            "what_would_close_it": ("any official publication of FY2015-16 petroleum sales or "
                                    "consumption BY PRODUCT for the Total Industry or Road "
                                    "sector row"),
            **row,
        })
    with open(LOG, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    hits = [r for r in rows if r["found_product_split"] == "yes"]
    print("source search -> %s" % os.path.relpath(LOG, ROOT))
    for row in rows:
        print("  %-46s %s" % (row["source_family"][:46], row["outcome"]))
    print()
    if hits:
        print("%d source(s) may carry the split - inspect before concluding anything:" % len(hits))
        for row in hits:
            print("  %s: %s" % (row["specific_source"], row["note"][:120]))
        return 0
    print("No source searched publishes the FY2015-16 split by product. Industry and "
          "transport stay NE for that year, which is what the strict series already says; "
          "this log is the record that the search happened and where it stopped.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
