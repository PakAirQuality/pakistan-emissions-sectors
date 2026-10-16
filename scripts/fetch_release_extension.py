"""Retain the public documents used for the FY2025 core/FY2026 extension.

Run holdings.py first. Existing files are reused without a network request;
publisher revisions are never written over held bytes. No private access is used.
"""
from __future__ import annotations

import csv
import datetime
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pkinv.core.retention import fetch_and_keep, sha256_of

LOG = ROOT / "data/raw/ACQUISITION_LOG_release_extension_20261014.csv"
FIELDS = ("retrieved_utc", "url", "local_path", "status", "sha256", "bytes", "note")
DOCUMENTS = (
    ("pcaa/extension_2025", "major-traffic-flows-by-airports-during-the-year-2024-25.pdf",
     "https://pcaawebadmin.pcaa.gov.pk/media/xaehjqwn/major-traffic-flows-by-airports-during-the-year-2024-25.pdf",
     "Full July2024-June2025 airport domestic/international/noncommercial movement and passenger controls"),
    ("finance_division/survey_2025_26", "2_Agriculture.pdf",
     "https://www.finance.gov.pk/survey/chapter_26/2_Agriculture.pdf",
     "Full FY2025 crops; provisional FY2026 crops; FY2026 nutrient offtake is July-March only"),
    ("pbs/qim/extension_2026", "Table-2-June-26.xlsx",
     "https://www.pbs.gov.pk/wp-content/uploads/2020/07/Table-2-June-26.xlsx",
     "Physical monthly output Jul2025-Jun2026; aggregate index rows must not be treated as tonnes"),
    ("pbs/qim/extension_2026", "Table-3-2024-25-6.xlsx",
     "https://www.pbs.gov.pk/wp-content/uploads/2020/07/Table-3-2024-25-6.xlsx",
     "Revised overlapping physical output Jul2024-Jun2025 accompanying June2026 release"),
    ("ocac/extension_2026", "archives_20261014.html",
     "https://www.ocac.org.pk/oil-industry-statistics/archives/",
     "Publisher index for the annual and direct monthly editions"),
    ("ocac/extension_2026", "Jul-Jun-2025-26-ENE-Pak-2.pdf",
     "https://www.ocac.org.pk/wp-content/uploads/2022/05/Jul-Jun-2025-26-ENE-Pak-2.pdf",
     "Full FY2026 energy/non-energy sectoral sales; FY2025 overlap is revised"),
) + tuple(("nasa_power", "T2M_monthly_%s_2024_2025.json" % city,
           "https://power.larc.nasa.gov/api/temporal/monthly/point?parameters=T2M&community=RE&longitude=%s&latitude=%s&start=2024&end=2025&format=JSON" % (lon, lat),
           "Own-year residential weather shape Jul2024-Jun2025; earlier weather source vintage remains unchanged")
          for city, lat, lon in (("Lahore",31.55,74.35), ("Karachi",24.86,67.01),
                                 ("Peshawar",34.01,71.58), ("Quetta",30.18,66.99), ("Islamabad",33.68,73.05)))


def acquire(source, name, url, note):
    target = ROOT / "data/raw" / source / name
    status = "held-reused"
    if not target.exists():
        try:
            target = Path(fetch_and_keep(url, source, name, note=note, timeout=60, attempts=2))
            status = "acquired"
        except OSError as error:
            return {"retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "url": url, "local_path": "", "status": "blocked", "sha256": "",
                    "bytes": "", "note": str(error)}
    body = target.read_bytes()
    if name.endswith(".pdf") and not body.startswith(b"%PDF"):
        status = "not-a-pdf"
    return {"retrieved_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "url": url, "local_path": target.relative_to(ROOT).as_posix(),
            "status": status, "sha256": sha256_of(body), "bytes": len(body), "note": note}


def main():
    records = [acquire(*entry) for entry in DOCUMENTS]
    archive = ROOT / "data/raw/ocac/extension_2026/archives_20261014.html"
    if archive.exists():
        html = archive.read_text()
        links = re.findall(r'href=["\x27]([^"\x27]+)["\x27][^>]*>(.*?)</a>', html, re.S)
        month_names = ("july", "august", "september", "october", "november", "december",
                       "january", "february", "march", "april", "may", "june")
        for index, month in enumerate(month_names):
            year = 2025 if index < 6 else 2026
            # Match the link's text as well as its URL: filenames are irregular.
            matches = [(url, re.sub("<[^>]+>", " ", label)) for url, label in links
                       if "sectoral sales / consumption" in re.sub("<[^>]+>", " ", label).lower()
                       and re.search(r"\b%s\s+%d\b" % (month, year),
                                     re.sub("<[^>]+>", " ", label), re.I)]
            if len(matches) != 1:
                raise ValueError("Expected one publisher link for %s %d, found %d" % (month, year, len(matches)))
            url, _ = matches[0]
            records.append(acquire("ocac/extension_2026", "ocac_sector_province_%d_%02d.pdf" %
                                   (year, (index + 6) % 12 + 1), url,
                                   "Direct single-month sector/product/province sales; not combustion observation"))
    prior = []
    if LOG.exists():
        with LOG.open(newline="") as handle:
            prior = list(csv.DictReader(handle))
    seen = {(r["url"], r["sha256"], r["status"]) for r in prior}
    fresh = [r for r in records if (r["url"], r["sha256"], r["status"]) not in seen]
    with LOG.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        if not prior:
            writer.writeheader()
        writer.writerows(fresh)
    for row in records:
        print(row["status"], row["local_path"] or row["url"], row["bytes"])
    return int(any(r["status"] in ("blocked", "not-a-pdf") for r in records))


if __name__ == "__main__":
    raise SystemExit(main())
