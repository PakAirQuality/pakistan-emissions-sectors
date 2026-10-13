#!/usr/bin/env python3
"""WAVE 1 OF THE INDUSTRIAL BOUNDARY PROGRAM: OGRA's own sector-wise gas classes,
extracted per fiscal year from the State of the Regulated Petroleum Industry
reports - the classification that keeps fertilizer FEEDSTOCK, captive power and
general industry apart, which is exactly the misclassification the 1.A.2 balance
closure needs to avoid.

One combined whole-country table per edition ("Sector-wise Gas Consumption for
FY ...": classes x SNGPL / SSGCL / Independent / Total MMCFD / share). pdftotext
DROPS the "ti" ligature in most editions ("Cap ve" or "Capve" for Captive,
"Fer lizer"/"Ferlizer"), so class matching is ligature-tolerant by construction.
The FY2020-21 edition is a page scan with no text layer; its year is a TYPED GAP
here, never a zero - the row says so.

Reads:  data/raw/ogra/state_of_industry/ogra_petroleum_industry_report_<fy>.pdf
Writes: outputs/ogra_gas_class_series.csv
"""
import csv
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path
from pkinv.paths import OUTPUTS  # noqa: E402

ROOT = os.path.dirname(OUTPUTS)
# The nine FY2015-16..FY2023-24 editions were ALREADY HELD in sources/OGRA before
# this sweep (the 2026-09-10 re-download duplicated them and was removed); only
# the FY2024-25 edition is newly acquired under data/raw.
HELD = asset_path(ROOT, "sources", "OGRA")
RAW = asset_path(ROOT, "data", "raw", "ogra", "state_of_industry")
OUT = asset_path(OUTPUTS, "ogra_gas_class_series.csv")

EDITIONS = ["2015_16", "2016_17", "2017_18", "2018_19", "2019_20", "2020_21",
            "2021_22", "2022_23", "2023_24", "2024_25"]
SCANNED = {"2020_21"}   # no text layer; the year stays a typed gap

# the ti ligature may vanish with or without a space; every pattern tolerates both
# Labels drift across editions (2022-23 says "Domestic", bare "Industry" and
# "Fertilizer Feed", and drops Cement), so each class carries every observed
# spelling and the PRINTED label is recorded beside the mapped one.
CLASSES = [
    ("residential",      r"residen(?:ti)?al|domes(?:ti)?c"),
    ("commercial",       r"commercial"),
    ("general_industry", r"^(?:\d{1,2}\.?)?(?:general)?industry\d"),
    ("fertilizer",       r"fer(?:ti)?lizer(?:feed)?"),
    ("cement",           r"^(?:\d{1,2}\.?)?cement"),
    ("captive_power",    r"cap(?:ti)?vepower"),
    ("power",            r"^(?:\d{1,2}\.?)?power"),
    ("transport_cng",    r"transport(?:\(cng\))?|\bcng\b"),
]
OPTIONAL = {"cement"}   # 2022-23 reports no separate cement row

FIELDS = ("period_id", "gas_class", "mmcfd_sngpl", "mmcfd_ssgcl",
          "mmcfd_independent", "mmcfd_total", "share_pct", "status",
          "class_comparable", "edition_source", "note")

# The FY2022-23 edition RECLASSIFIES its table (bare "Industry" bundles more than
# the general-industry class; "Fertilizer Feed" excludes fuel gas; Domestic for
# Residential; no Cement row), so its cells are the edition's own prints but NOT
# comparable to the class series - data/activity/industry/gas_consumption.csv
# restates the class-comparable values from the 2023-24 edition's comparison
# columns (general industry 282) and supersedes these cells for that use.
DRIFTED = {"FY2022-23"}


def fy_label(fy):
    a, b = fy.split("_")
    return "FY%s-%s" % (a, b)


def norm(line):
    """Lowercased, whitespace-free, CONTROL-CHAR-FREE: pdftotext renders the ti
    ligature as \x19 in some editions and drops it in others."""
    return re.sub(r"[\s\x00-\x1f]+", "", line).lower()


def numbers(line):
    return [float(t.replace(",", "")) for t in re.findall(r"-?\d[\d,]*\.?\d*", line)]


def edition_path(fy):
    held = asset_path(HELD, "ogra_state_of_industry_%s.pdf" % fy.replace("_", "-"))
    if os.path.exists(held):
        return held
    return asset_path(RAW, "ogra_petroleum_industry_report_%s.pdf" % fy)


def parse_edition(fy):
    path = edition_path(fy)
    txt = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True,
                         text=True, check=True).stdout
    lines = txt.splitlines()
    start = None
    for i, l in enumerate(lines):
        n = norm(l)
        if re.search(r"sector-?wisegasconsump(?:ti)?on.{0,14}(?:for|during)fy", n):
            start = i
            break
    if start is None:
        raise SystemExit("no combined sector table found in %s" % path)
    rows = {}
    for l in lines[start:start + 40]:
        n = norm(l)
        if n.startswith(("subtotal", "sub-total", "total", "grandtotal")) and rows:
            break
        for key, pat in CLASSES:
            if key in rows:
                continue
            if re.search(pat, n):
                # serial-numbered rows ("7. Power ...") would pollute the columns
                stripped = re.sub(r"^\s*\d{1,2}\.?\s+", "", l)
                nums = numbers(stripped)
                # a class row carries SNGPL, SSGCL, [Independent], Total, Share
                if len(nums) >= 4:
                    if len(nums) == 4:          # a dash where Independent has none
                        nums = nums[:2] + [0.0] + nums[2:]
                    label = re.sub(r"[\x00-\x1f]", "", stripped).strip()
                    label = re.split(r"\s{2,}|\s(?=[\d-])", label)[0].strip()
                    rows[key] = (nums[:5], label)
                break
    missing = [k for k, _ in CLASSES if k not in rows and k not in OPTIONAL]
    if missing:
        raise SystemExit("%s: classes not parsed: %s" % (fy, missing))
    return rows


def main():
    out_rows = []
    for fy in EDITIONS:
        period = fy_label(fy)
        src = os.path.relpath(edition_path(fy), ROOT)
        if fy in SCANNED:
            for key, _ in CLASSES:
                out_rows.append({"period_id": period, "gas_class": key,
                                 "mmcfd_sngpl": "", "mmcfd_ssgcl": "",
                                 "mmcfd_independent": "", "mmcfd_total": "",
                                 "share_pct": "", "status": "typed_gap_scanned_edition",
                                 "class_comparable": "gap",
                                 "edition_source": src,
                                 "note": "the FY2020-21 edition is a page scan with no text "
                                         "layer; empty cells are a typed gap, never zeros - "
                                         "the held ingest carries OCR-verified values for "
                                         "general industry and captive power"})
            continue
        parsed = parse_edition(fy)
        for key, _ in CLASSES:
            if key not in parsed:
                out_rows.append({"period_id": period, "gas_class": key,
                                 "mmcfd_sngpl": "", "mmcfd_ssgcl": "",
                                 "mmcfd_independent": "", "mmcfd_total": "",
                                 "share_pct": "", "status": "not_reported_separately",
                                 "class_comparable": "gap",
                                 "edition_source": src,
                                 "note": "this edition prints no separate row for the class"})
                continue
            (sn, g, i, t, share), label = parsed[key]
            drifted = period in DRIFTED
            note = "printed label: %s" % label
            if drifted:
                note += ("; the edition reclassifies its table, so this is the edition's "
                         "own print, NOT the class series - the held ingest restates the "
                         "class-comparable value from the next edition's comparison columns")
            out_rows.append({"period_id": period, "gas_class": key,
                             "mmcfd_sngpl": "%g" % sn, "mmcfd_ssgcl": "%g" % g,
                             "mmcfd_independent": "%g" % i, "mmcfd_total": "%g" % t,
                             "share_pct": "%g" % share,
                             "status": "extracted_drifted_vocabulary" if drifted else "extracted",
                             "class_comparable": "no" if drifted else "yes",
                             "edition_source": src, "note": note})
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write("# OGRA's sector-wise gas classes per fiscal year (MMCFD, average daily),\n"
                "# from the combined whole-country table of each State of the Regulated\n"
                "# Petroleum Industry edition. THE CLASSES ARE THE POINT: fertilizer\n"
                "# feedstock, captive power and general industry stay apart, which is the\n"
                "# misclassification the 1.A.2 balance closure must avoid (roadmap step 1).\n"
                "# FY2020-21 is a typed gap (scanned edition) and FY2022-23's reclassified\n"
                "# table is marked class_comparable=no. This product VALIDATES and extends\n"
                "# the held ingests (data/activity/industry/gas_consumption.csv and\n"
                "# data/activity/power/captive_gas.csv): its new content is the fertilizer\n"
                "# (feedstock), residential, commercial, power and transport classes and the\n"
                "# FY2024-25 edition. Values are OGRA's own prints.\n")
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)
    done = sorted({r["period_id"] for r in out_rows if r["status"] == "extracted"})
    print("ogra gas class series -> %s (%d rows; %d fiscal years extracted, 1 typed gap)"
          % (os.path.relpath(OUT), len(out_rows), len(done)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
