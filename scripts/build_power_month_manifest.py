"""The 108-service-month power manifest: every month typed, nothing counted by search hits.

THE FIFTEENTH REVIEW'S POWER LANE, first stage. The reviewer's rule: completeness is
measured against an EXPECTED manifest of service months (July 2015 - June 2024), never
against what a search happened to return. This builds that manifest from three source
lanes and types every (service month x lane) cell:

  pbs_ingested         the month is inside the PBS lane of the plant-month panel
                       (data/activity/power/generation_monthly.csv, FY2015-16..FY2020-21);
  sir_listing_ingested the month is inside the SIR lane of the same panel - the archive's
                       company LISTING sheets carry the whole plant-month table and
                       scripts/ingest_sir_generation.py reads them (FY2021-22..FY2023-24);
  sir_discovered       NEPRA's "Detail of Generation" repository serves a plant-month PDF
                       archive for the month (URL-enumerated from the held listings;
                       ~1,500 PDFs per fiscal year; the ingested months keep this lane
                       too, because the per-plant dailies remain the verification and
                       arbitration instrument);
  untyped_gap          no lane covers the month - the FCA corpus is the named next
                       source for it.

The lane a panel month belongs to is read from the panel rows' own source_file column,
never decided by fiscal year, so the label cannot drift when either lane's window moves.

THE DISCOVERY IS ITSELF A FINDING. The SIR archive's GENCO directories are Guddu
(CPGCL), Jamshoro (JPCL) and Muzaffargarh (NPGCL) - exactly the stations whose fuel PBS
never labels in FY2016-17 and FY2017-18, so the archive is also the named source for
that crosswalk. And the archive's months (FY2021-22 onward) are exactly the years the
PBS panel stops covering.

WHAT THIS DELIBERATELY DOES NOT DO. It does not download the ~4,600 plant-month PDFs
(that is the staged backfill, tracked by download_status/parse_status columns), and it
does not derive any emission or share - a manifest is acquisition metadata. The evidence
grades stay where they are until parsed, reconciled rows land in the generation panel.

OFFLINE BY DEFAULT: reads the held listing files; --fetch refreshes them from
nepra.org.pk first (network, never run by the build or the tests).

Usage:  python3 scripts/build_power_month_manifest.py [--fetch]
Writes: data/manifests/power_month_manifest.csv
        data/manifests/power_sir_document_manifest.csv (one row per discovered PDF)
"""

from pkinv.assets import asset_path
import csv
import hashlib
import os
import re
import sys
import urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIR_DIR = asset_path(ROOT, "data", "raw", "nepra", "sir_detail")
# Where the daily reports land - the verification sample's fetches and the Wave-1 bulk
# campaign's alike. A held document is DOWNLOADED by the tree's own testimony; it is
# NOT thereby parsed: the bulk campaign acquires without reading, so parse_status stays
# pending and the parse outcomes live where the parses happen (the verification sample
# CSV today, the CPPA parse ledgers to come). Deriving "parsed" from mere presence
# shipped 1,251 false rows for one commit, which is why this comment exists.
DAILY_STORE = asset_path(SIR_DIR, "daily_reports")
GEN_PANEL = asset_path(ROOT, "data", "activity", "power", "generation_monthly.csv")
MONTH_OUT = asset_path(ROOT, "data", "manifests", "power_month_manifest.csv")
DOC_OUT = asset_path(ROOT, "data", "manifests", "power_sir_document_manifest.csv")

BASE = ("https://nepra.org.pk/publications/State%20of%20Industry%20Reports/"
        "Detail%20of%20Generation")
LISTINGS = {
    2021: "sir_companies_2021_22.htm",
    2022: "sir_companies_2022_23.htm",
    2023: "sir_companies_2023_24.htm",
}
FIRST_FY_START, LAST_FY_START = 2015, 2023

MONTHS = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
          "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def service_months():
    out = []
    for fy in range(FIRST_FY_START, LAST_FY_START + 1):
        for m in list(range(7, 13)) + list(range(1, 7)):
            year = fy if m >= 7 else fy + 1
            out.append((fy, "%04d-%02d" % (year, m)))
    return out


def panel_months():
    """{service month: {lanes}} from the panel itself, laned by each row's source_file."""
    covered = {}
    if not os.path.exists(GEN_PANEL):
        return covered
    with open(GEN_PANEL, newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            month = (r.get("month") or "").strip()
            if re.match(r"\d{6}$", month):          # the panel writes YYYYMM
                month = "%s-%s" % (month[:4], month[4:])
            elif not re.match(r"\d{4}-\d{2}$", month):
                continue
            lane = ("sir_listing_ingested" if "sir_detail" in r.get("source_file", "")
                    else "pbs_ingested")
            covered.setdefault(month, set()).add(lane)
    return covered


def sir_documents():
    """One row per discovered plant-month PDF across the held listings."""
    rows = []
    for fy_start, name in sorted(LISTINGS.items()):
        path = asset_path(SIR_DIR, name)
        with open(path, encoding="windows-1252", errors="replace") as f:
            text = f.read()
        digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
        for href in sorted(set(re.findall(r'href="(\.\./[^"]+\.pdf)"', text, re.I))):
            decoded = urllib.parse.unquote(href)
            parts = decoded.split("/")
            group = parts[1] if len(parts) > 2 else ""
            plant = parts[2] if len(parts) > 3 else parts[-1]
            fname = parts[-1]
            match = re.search(r"([A-Z][a-z]{2})[a-z]*[\s,._-]+(\d{4})", fname)
            if match and match.group(1) in MONTHS:
                month = "%04d-%02d" % (int(match.group(2)), MONTHS[match.group(1)])
            else:
                month = ""
            label = "FY%d-%02d" % (fy_start, (fy_start + 1) % 100)
            local = asset_path(
                DAILY_STORE, label, parts[-2] if len(parts) > 1 else "", fname)
            held = os.path.exists(local)
            rows.append({
                "fiscal_year_start": fy_start,
                "service_month": month,
                "group": group,
                "plant": plant,
                "document": fname,
                "url": BASE + "/" + urllib.parse.quote(decoded[3:]),
                "listing_file": name,
                "listing_sha256": digest,
                "download_status": "downloaded" if held else "discovered",
                "parse_status": "pending",
                "sha256": (hashlib.sha256(open(local, "rb").read()).hexdigest()
                           if held else ""),
            })
    return rows


def month_rows(docs):
    panel = panel_months()
    by_month = {}
    for d in docs:
        if d["service_month"]:
            by_month.setdefault(d["service_month"], 0)
            by_month[d["service_month"]] += 1
    out = []
    for fy, month in service_months():
        lanes = []
        for lane in ("pbs_ingested", "sir_listing_ingested"):
            if lane in panel.get(month, ()):
                lanes.append(lane)
        if by_month.get(month):
            lanes.append("sir_discovered")
        status = "+".join(lanes) if lanes else "untyped_gap"
        out.append({
            "fiscal_year_start": fy,
            "service_month": month,
            "status": status,
            "sir_documents": by_month.get(month, 0),
            "note": ("" if lanes else
                     "no ingested PBS month and no discovered SIR document; the "
                     "CPPA-G/NEPRA FCA corpus is the named next source"),
        })
    return out


def fetch():
    import urllib.request
    index = ("https://nepra.org.pk/publications/State%20of%20Industry%20Reports.php")
    targets = {"sir_publications_index.html": index}
    for fy, name in LISTINGS.items():
        label = "%d-%02d" % (fy, (fy + 1) % 100)
        targets[name] = (BASE + "/List%20of%20Companies%20Genenration%20wise%20"
                         + label + "_files/sheet001.htm")
    os.makedirs(SIR_DIR, exist_ok=True)
    for name, url in targets.items():
        with urllib.request.urlopen(url, timeout=120) as resp:
            blob = resp.read()
        with open(asset_path(SIR_DIR, name), "wb") as f:
            f.write(blob)
        print("fetched %s (%d bytes)" % (name, len(blob)))


def main(argv):
    if "--fetch" in argv:
        fetch()
    docs = sir_documents()
    months = month_rows(docs)
    os.makedirs(os.path.dirname(MONTH_OUT), exist_ok=True)
    with open(DOC_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(docs[0].keys()))
        w.writeheader()
        w.writerows(docs)
    with open(MONTH_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(months[0].keys()))
        w.writeheader()
        w.writerows(months)
    n_gap = sum(1 for m in months if m["status"] == "untyped_gap")
    n_both = sum(1 for m in months if m["status"] == "pbs_ingested+sir_discovered")
    print("power month manifest -> %s" % os.path.relpath(MONTH_OUT, ROOT))
    print("  %d service months: %d typed, %d untyped gaps; %d covered by both "
          "lanes (the PBS-overlap validation set)"
          % (len(months), len(months) - n_gap, n_gap, n_both))
    print("  %d SIR documents discovered across %d listings"
          % (len(docs), len(LISTINGS)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
