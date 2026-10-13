"""The SIR listing parse, verified against the archive's own per-plant daily reports.

WHY A SAMPLE AND NOT A PARSE. The listing sheets carry the whole plant-month table and every
row proves itself against its own printed Sum (scripts/ingest_sir_generation.py). The 4,644
per-plant daily PDFs therefore do not need to be parsed to build the panel - but they are the
only instrument that can ARBITRATE the five FY2021-22 rows whose printed Sum disagrees with
their own twelve months, and an independent read of a few high-mass plant-months is cheap
insurance against a systematic sheet error the row identity could not see.

TWO IDENTITIES PER DOCUMENT. Each daily report prints one row per day and its own monthly
Total. The day rows must sum to that Total (the document proves itself), and the Total is
then compared to the listing sheet's cell for the same plant-month (the two documents must
agree). A document failing its own identity is recorded and never used to arbitrate anything.

THE SAMPLE. All twelve months for the five discrepant FY2021-22 plants; two months each for
the largest coal and RLNG plants across the three years; the Guddu 5-13 January 2024
zero-generation month that was this lane's original pilot.

Usage:  python3 scripts/fetch_sir_verification_sample.py [--offline]
Writes: outputs/power_sir_verification_sample.csv
Stores: data/raw/nepra/sir_detail/daily_reports/<FY>/<plant>/<file>.pdf
"""
import argparse
import csv
import hashlib
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pkinv.assets import asset_path
import ingest_sir_generation as sir  # noqa: E402
from pkinv.core.io import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = asset_path(ROOT, "data", "manifests", "power_sir_document_manifest.csv")
STORE = asset_path(ROOT, "data", "raw", "nepra", "sir_detail", "daily_reports")
OUT = asset_path(ROOT, "outputs", "power_sir_verification_sample.csv")

FIELDS = ("fiscal_year", "plant", "month", "sheet_gwh", "daily_total_gwh",
          "daily_sum_gwh", "delta_gwh", "outcome", "document", "url", "sha256")

# sheet plant name (as parsed from the listing) -> the URL fragment that identifies the
# plant's directory in the archive, per fiscal year. Written by hand from the manifest's own
# URL inventory; a fragment matching nothing is an error, never a silent skip.
ARBITRATION = {
    # the five FY2021-22 rows whose printed Sum disagrees with their own months
    ("FY2021-22", "UCH-II Power (Pvt) Ltd."): "/Tharmal/UCH-II/",
    ("FY2021-22", "FFC Energy Ltd."): "/Wind/FFCEL/",
    ("FY2021-22", "Foundation Wind Energy-I Ltd. (FWEL-II)"): "/Wind/FWEL-II/",
    ("FY2021-22", "Daral Khwar (Behren) Hydropower Project"): "/Hydel/Daral Khwar/",
    ("FY2021-22", "Jamshoro Power Generation Company Limited."): "/JPCL/Jamshoro'/",
}
# high-mass spot checks: (fiscal_year, sheet plant substring, url fragment, [YYYYMM...])
SPOT = (
    ("FY2023-24", "Huaneng", "/Sahiwal/", ["202308", "202401"]),
    ("FY2023-24", "Balloki", "/Balloki/", ["202308", "202401"]),
    ("FY2022-23", "China", "/China Hub", ["202208", "202301"]),
    ("FY2023-24", "Guddu 5-13", "/Guddu 5-13/", ["202401"]),
    ("FY2021-22", "Port Qasim", "/Port Qasim/", ["202108"]),
)

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
          "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
          "january": 1, "february": 2, "march": 3, "april": 4, "june": 6, "july": 7,
          "august": 8, "september": 9, "october": 10, "november": 11, "december": 12}
FILE_MONTH = re.compile(r"([A-Za-z]{3,9})\s*[' ]?\s*(\d{2,4})(?:'|%27)?\.pdf$", re.I)
DAY_ROW = re.compile(r"^\s{0,4}(\d{1,2})\s")
TOTAL_ROW = re.compile(r"^\s*Total\b", re.I)
NUMBER = re.compile(r"-?[\d,]+\.\d+")


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def month_of(url):
    """YYYYMM from the document's file name, or None where it is a Summary."""
    name = urllib.parse.unquote(url.rsplit("/", 1)[1])
    match = FILE_MONTH.search(name)
    if not match:
        return None
    word = match.group(1).lower()
    if word not in MONTHS:
        return None
    year = int(match.group(2))
    year = year + 2000 if year < 100 else year
    return "%04d%02d" % (year, MONTHS[word])


def documents():
    return read_rows(MANIFEST, comments=False)


def fetch(url, path, offline):
    if os.path.exists(path):
        return True
    if offline:
        return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(request, timeout=90) as response, \
                open(path + ".part", "wb") as handle:
            shutil.copyfileobj(response, handle)
    except Exception as error:  # noqa: BLE001 - recorded, never fatal
        if os.path.exists(path + ".part"):
            os.remove(path + ".part")
        print("    FAILED %s (%s)" % (url, error))
        return False
    os.replace(path + ".part", path)
    time.sleep(1.0)
    return True


def read_daily(path):
    """(printed monthly Total GWh, sum of the day rows) - or (None, None) unreadable."""
    if not shutil.which("pdftotext"):
        raise SystemExit("pdftotext is not installed")
    out = subprocess.run(["pdftotext", "-layout", path, "-"], check=True,
                         stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    text = out.stdout.decode("utf-8", "replace")
    days, total = {}, None
    for line in text.splitlines():
        if TOTAL_ROW.match(line):
            numbers = NUMBER.findall(line)
            if numbers:
                # Total row: Installed, Dependable, --, --, Energy GWh, %age. The GWh is
                # the second-to-last figure with decimals; capacity columns print integers.
                total = float(numbers[-2].replace(",", "")) if len(numbers) >= 2 \
                    else float(numbers[0].replace(",", ""))
            continue
        match = DAY_ROW.match(line)
        if match:
            day = int(match.group(1))
            numbers = NUMBER.findall(line)
            if 1 <= day <= 31 and numbers and len(numbers) >= 2:
                days[day] = float(numbers[-2].replace(",", ""))
    return total, (sum(days.values()) if days else None)


def sheet_months():
    """{(fiscal_year, plant): {YYYYMM: gwh}} straight from the parsed listing sheets."""
    out = {}
    for fy_start, path in sir.LISTINGS.items():
        label = "FY%d-%02d" % (fy_start, (fy_start + 1) % 100)
        plants, _excluded = sir.parse_sheet(path)
        keys = sir.pbs.months_for(fy_start)
        for plant in plants:
            out[(label, plant["plant"])] = dict(zip(keys, plant["months"]))
    return out


def sample(docs):
    """[(fiscal_year, sheet plant, YYYYMM, manifest row)] for every wanted document."""
    wanted = []
    for (label, plant), fragment in ARBITRATION.items():
        rows = [d for d in docs
                if fragment in urllib.parse.unquote(d["url"])
                and d["fiscal_year_start"] == label[2:6]]
        dated = [(month_of(d["url"]), d) for d in rows]
        dated = [(m, d) for m, d in dated if m]
        if len(dated) < 12:
            raise SystemExit("%s %s: %d dated documents under %r; expected 12"
                             % (label, plant, len(dated), fragment))
        wanted.extend((label, plant, m, d) for m, d in sorted(dated))
    for label, plant_sub, fragment, months in SPOT:
        rows = [d for d in docs
                if fragment in urllib.parse.unquote(d["url"])
                and d["fiscal_year_start"] == label[2:6]]
        for month in months:
            found = [d for d in rows if month_of(d["url"]) == month]
            if not found:
                raise SystemExit("%s %r %s: no document in the manifest"
                                 % (label, fragment, month))
            wanted.append((label, plant_sub, month, found[0]))
    return wanted


def main(argv=None):
    parser = argparse.ArgumentParser(description="Fetch and verify the SIR daily sample.")
    parser.add_argument("--offline", action="store_true",
                        help="parse what is already held; fetch nothing")
    args = parser.parse_args(argv)

    docs = documents()
    sheets = sheet_months()
    results = []
    for label, plant, month, doc in sample(docs):
        url = doc["url"]
        name = urllib.parse.unquote(url.rsplit("/", 1)[1])
        plant_dir = urllib.parse.unquote(url.rsplit("/", 2)[1])
        path = asset_path(STORE, label, plant_dir, name)
        held = fetch(url, path, args.offline)

        # the sheet cell this document must agree with
        cell = None
        for (sheet_label, sheet_plant), months in sheets.items():
            if sheet_label == label and (plant == sheet_plant or plant in sheet_plant):
                cell = months.get(month)
                break
        row = {"fiscal_year": label, "plant": plant, "month": month,
               "sheet_gwh": "" if cell is None else round(cell, 2),
               "daily_total_gwh": "", "daily_sum_gwh": "", "delta_gwh": "",
               "outcome": "", "document": name, "url": url,
               "sha256": _sha256(path) if held else ""}
        if not held:
            row["outcome"] = "not_fetched"
            results.append(row)
            continue
        total, day_sum = read_daily(path)
        row["daily_total_gwh"] = "" if total is None else round(total, 2)
        row["daily_sum_gwh"] = "" if day_sum is None else round(day_sum, 2)
        if total is None or day_sum is None:
            row["outcome"] = "unreadable"
        elif abs(day_sum - total) > 0.05:
            row["outcome"] = "document_fails_own_identity"
        elif cell is None:
            row["outcome"] = "no_sheet_cell"
        else:
            row["delta_gwh"] = round(total - cell, 2)
            row["outcome"] = "agrees" if abs(total - cell) <= 0.05 else "disagrees"
        results.append(row)
        print("  %-10s %-40s %s sheet %8s daily %8s -> %s"
              % (label, plant[:40], month, row["sheet_gwh"], row["daily_total_gwh"],
                 row["outcome"]))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(results)
    outcomes = {}
    for row in results:
        outcomes[row["outcome"]] = outcomes.get(row["outcome"], 0) + 1
    print("verification sample -> %s" % os.path.relpath(OUT, ROOT))
    print("  " + ", ".join("%s: %d" % kv for kv in sorted(outcomes.items())))
    return 0


if __name__ == "__main__":
    sys.exit(main())
