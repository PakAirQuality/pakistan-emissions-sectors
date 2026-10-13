"""Ingest Pakistan CAA airport traffic into the aviation activity panel.

Source: the 18 "MAJOR TRAFFIC FLOWS BY AIRPORTS DURING THE YEAR" PDFs published by the
CAA Statistics Branch, FY2006-07 through FY2023-24, in the pakistan-emissions-sectors
repository under Aviation/.

We parse the PDFs rather than the accompanying spreadsheet. The spreadsheet reconciles to
the PDF grand totals exactly for 2006-2015, but from 2016 it silently dropped the smaller
airfields -- 14 airport rows in FY2023 against 37 in the source. That omission is what
produces the apparent 89% collapse in non-commercial movements at 2016, which is a
transcription artefact rather than a real change in traffic. Parsing the PDFs also yields
the IATA and ICAO codes the spreadsheet lacks, which is what makes the 55 airport-name
variants resolve unambiguously.

YEARS ARE FISCAL, July to June. The PDF header reads "From July <N> / To June <N+1>", so
year 2023 means Jul 2023 - Jun 2024. This is nowhere recorded in the spreadsheet. It
matters twice: any join to a calendar-year series is six months out, and the COVID trough
is FY2020, not FY2019 (FY2019 already contains the March-June 2020 shutdown).

Two PDF layouts:
  2006-07 .. 2015-16   airport name only, marked PROVISIONAL DATA
  2016-17 .. 2023-24   "IATA - ICAO - NAME" per row

Usage:  python3 scripts/ingest_aviation.py [path/to/Aviation]
Writes: data/activity/aviation/movements_airport.csv
"""

from pkinv.assets import asset_path
import csv
import os
import re
import subprocess
import sys

from pkinv.paths import ROOT, DATA

DEFAULT_SRC = asset_path(ROOT, "sources", "Aviation")   # rc37: the held directory
OUT_DIR = asset_path(DATA, "activity", "aviation")
OUT = asset_path(OUT_DIR, "movements_airport.csv")
ALIASES = asset_path(OUT_DIR, "airport_aliases.csv")

# "From July 2023" in the header block gives the fiscal year.
FY_RE = re.compile(r"From\s+July\s+(\d{4})")
# New layout: "  KHI - OPKC - KARACHI JIAP   16,495  25,259 ..."
CODED_RE = re.compile(r"^\s+([A-Z0-9]{3})\s+-\s+([A-Z0-9]{3,4})\s+-\s+(.+?)\s{2,}(.*)$")
# Old layout: "BAHAWALPUR   634   0   634  1,075 ..."
PLAIN_RE = re.compile(r"^\s*([A-Z][A-Za-z0-9 ,.()/\-']*?)\*?\s{2,}([\d,\s.]+)$")
NUM_RE = re.compile(r"-?[\d,]+(?:\.\d+)?")

# Columns after the airport name, in PDF order. Derived totals are skipped, while
# cargo and mail are retained as independent controls for the anchor-year ledger.
#   com_dom, com_intl, [com_total], noncom, [grand_total], pax_dom, pax_intl,
#   [pax_total], cargo_dom, cargo_intl, [cargo_total], mail_dom, mail_intl, [mail_total]
WANTED = {"com_dom": 0, "com_intl": 1, "noncom": 3,
          "pax_dom": 5, "pax_intl": 6,
          "cargo_dom_t": 8, "cargo_intl_t": 9,
          "mail_dom_t": 11, "mail_intl_t": 12}


def _nums(text):
    return [float(m.group(0).replace(",", "")) for m in NUM_RE.finditer(text)]


def _aliases():
    with open(ALIASES, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_name = {r["source_name"].upper(): r for r in rows}
    by_icao = {r["icao"]: r for r in rows if r["icao"]}
    return by_name, by_icao


def parse_pdf(path):
    """Return (fiscal_year, [row dicts], grand_totals or None)."""
    text = subprocess.run(["pdftotext", "-layout", path, "-"],
                          capture_output=True, text=True, check=True).stdout
    m = FY_RE.search(text)
    if not m:
        raise SystemExit("no 'From July YYYY' header in %s" % path)
    year = int(m.group(1))

    rows, grand = [], None
    for line in text.split("\n"):
        if re.match(r"\s*Grand\s+Totals", line, re.I):
            v = _nums(line)
            if len(v) >= 13:
                grand = {k: v[i] for k, i in WANTED.items()}
            continue
        cm = CODED_RE.match(line)
        if cm:
            iata, icao, name, rest = cm.groups()
            v = _nums(rest)
            if len(v) < 13:
                continue
            rows.append(dict(iata=iata, icao=icao, name=name.strip(),
                             **{k: v[i] for k, i in WANTED.items()}))
            continue
        pm = PLAIN_RE.match(line)
        if pm:
            name, rest = pm.groups()
            v = _nums(rest)
            if len(v) < 13 or not name.strip():
                continue
            rows.append(dict(iata="", icao="", name=name.strip(),
                             **{k: v[i] for k, i in WANTED.items()}))
    return year, rows, grand


def main(src=DEFAULT_SRC):
    by_name, by_icao = _aliases()
    pdfs = sorted(f for f in os.listdir(src) if f.lower().endswith("-apt.pdf")
                  or f.lower().startswith("major-traffic-flow-airports-"))
    out, unresolved, recon = [], set(), []

    for fn in pdfs:
        year, rows, grand = parse_pdf(asset_path(src, fn))
        for r in rows:
            a = by_icao.get(r["icao"]) or by_name.get(r["name"].upper())
            if a is None:
                unresolved.add("%s (%s, FY%d)" % (r["name"], r["icao"] or "no ICAO", year))
                continue
            out.append({
                "year": year, "icao": a["icao"], "iata": a["iata"],
                "airport": a["airport"], "province": a["province"],
                "com_dom_mv": int(r["com_dom"]), "com_intl_mv": int(r["com_intl"]),
                "noncom_mv": int(r["noncom"]),
                "pax_dom": int(r["pax_dom"]), "pax_intl": int(r["pax_intl"]),
                "cargo_dom_t": r["cargo_dom_t"], "cargo_intl_t": r["cargo_intl_t"],
                "mail_dom_t": r["mail_dom_t"], "mail_intl_t": r["mail_intl_t"],
                "source": "Pakistan CAA Statistics Branch, Major Traffic Flows by Airports, FY%d-%02d"
                          % (year, (year + 1) % 100),
            })
        if grand:
            got = {k: sum(r[k] for r in rows) for k in WANTED}
            recon.append((year, grand, got, len(rows)))

    if unresolved:
        raise SystemExit("airports not in %s:\n  %s" % (ALIASES, "\n  ".join(sorted(unresolved))))

    out.sort(key=lambda r: (r["year"], r["icao"]))
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, lineterminator="\n", fieldnames=["year", "icao", "iata", "airport", "province",
                                          "com_dom_mv", "com_intl_mv", "noncom_mv",
                                          "pax_dom", "pax_intl", "cargo_dom_t",
                                          "cargo_intl_t", "mail_dom_t", "mail_intl_t",
                                          "source"])
        w.writeheader()
        w.writerows(out)

    print("wrote %s" % os.path.relpath(OUT, os.path.dirname(DATA)))
    print("  %d rows | %d airports | FY%d-FY%d"
          % (len(out), len({r["icao"] for r in out}),
             min(r["year"] for r in out), max(r["year"] for r in out)))
    print("\n  reconciliation against the CAA printed Grand Totals:")
    bad = 0
    for year, grand, got, n in recon:
        diffs = [k for k in WANTED if abs(grand[k] - got[k]) > 0.5]
        flag = "OK " if not diffs else "DIFF %s" % ",".join(diffs)
        if diffs:
            bad += 1
        print("    FY%d  %2d airports  %s" % (year, n, flag))
    print("  %d of %d years reconcile exactly" % (len(recon) - bad, len(recon)))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SRC)
