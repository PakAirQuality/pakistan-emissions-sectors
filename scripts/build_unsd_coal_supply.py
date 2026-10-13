#!/usr/bin/env python3
"""WAVE 1 OF THE INDUSTRIAL-COAL RECONSTRUCTION: the UN Statistics Division energy
balance's PRIMARY COAL supply block for Pakistan, per calendar year - the only
independent (non-HDIP) supply-side control this repository holds.

WHY. The reference's brick-kiln and cement-sector coal are HDIP's coal-by-consumer
ALLOCATION (data/activity/industry/coal_by_consumer.csv). Its own supply side
(coal_supply.csv: Supplement Tables 14.3 and 3.1A) reproduces the consumption total
by construction, so that closure cannot test the allocation. UNSD compiles Pakistan's
balance from national submissions but publishes the parts the Supplement omits:
exports, stock changes (printed '..' - NOT AVAILABLE, carried typed here and never as
zero), a statistical difference, the transformation into electricity plants, and
final consumption BY BRANCH - where UNSD books essentially all of Pakistan's final
coal under "Non-metallic minerals" (cement + bricks) with "Industries n.e.s" at zero.
That branch split is the independent check on whether the Supplement's "Cement"
column (the Survey's "Cement/Others", the PEY's "Cement/Other Industry") is doing work.

WHAT THIS IS NOT. A control, not an estimate. UNSD's calendar years straddle two
fiscal years (the balance builder joins each fiscal year to BOTH calendar years and
says so); UNSD's own '*' marks its estimates (carried in the flags column); and the
statistical difference is large (-40,001 TJ in CY2021, -191,264 TJ in CY2022) - it
is published, never allocated to a sector. Nothing here enters any total.

PARSING. Each edition prints Pakistan's balance as a block headed by the bare line
"Pakistan", a bare year line, then labelled rows whose FIRST numeric column is
"Primary coal and peat" in terajoules. Rows are matched by their printed label;
".." is a typed absence; a leading "*" is UNSD's estimate flag. One row per
(edition, calendar year): later editions revise earlier years and the reader sees
the vintages side by side rather than one silently overwriting another.

Reads:  data/raw/unsd/energy_balances/unsd_energy_balances_<edition>_countries_M_Q.pdf
Writes: outputs/unsd_coal_supply_control.csv
Usage:  python3 scripts/build_unsd_coal_supply.py [--check]
"""
import csv
import glob
import io
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path
from pkinv.paths import OUTPUTS  # noqa: E402

ROOT = os.path.dirname(OUTPUTS)
RAW = asset_path(ROOT, "data", "raw", "unsd", "energy_balances")
OUT = asset_path(OUTPUTS, "unsd_coal_supply_control.csv")

# printed label prefix -> output column (first numeric slot = primary coal and peat, TJ)
ROWS = (
    ("Primary production", "primary_production_TJ"),
    ("Imports", "imports_TJ"),
    ("Exports", "exports_TJ"),
    ("Stock changes", "stock_changes_TJ"),
    ("Total energy supply", "total_energy_supply_TJ"),
    ("Statistical difference", "statistical_difference_TJ"),
    ("Transformation", "transformation_TJ"),
    ("Electricity plants", "transformation_electricity_plants_TJ"),
    ("Final consumption", "final_consumption_TJ"),
    ("Manufacturing, const., mining", "final_manufacturing_TJ"),
    ("Iron and steel", "final_iron_and_steel_TJ"),
    ("Chemical and petrochemical", "final_chemical_TJ"),
    ("Non-metallic minerals", "final_non_metallic_minerals_TJ"),
    ("Industries n.e.s", "final_industries_nes_TJ"),
)
FIELDS = ("edition", "calendar_year") + tuple(c for _, c in ROWS) + ("estimated_flags", "note")

BANNER = (
    "# UNSD energy balances - Pakistan PRIMARY COAL AND PEAT supply block, TJ, per edition x calendar year.",
    "# The independent supply-side control for the industrial-coal reconstruction (Wave 1): exports, stock",
    "# changes ('..' = not available, typed EMPTY here, never zero), statistical difference and final",
    "# consumption BY BRANCH, which the Finance Division Supplement does not print. A control, never an",
    "# estimate; calendar years straddle two fiscal years; '*' = UNSD's own estimate (estimated_flags).",
    "# See scripts/build_unsd_coal_supply.py.",
)


def numbers(line):
    """The row's numbers left-to-right; '..' is a held slot (None) so columns stay aligned."""
    toks = re.findall(r"\*?-?\d[\d,]*\.?\d*|\.\.", line)
    return [None if t == ".." else float(t.lstrip("*").replace(",", "")) for t in toks]


def first_slot(line):
    """(value, estimated) for the first numeric column of a labelled row."""
    body = line.strip()
    # strip the label: everything up to the first digit, '*', '-' followed by digit, or '..'
    m = re.search(r"(\*?-?\d|\.\.)", body)
    if not m:
        return None, False
    tail = body[m.start():]
    tok = re.match(r"(\*?-?\d[\d,]*\.?\d*|\.\.)", tail).group(1)
    if tok == "..":
        return None, False
    return float(tok.lstrip("*").replace(",", "")), tok.startswith("*")


def parse_edition(path):
    txt = subprocess.run(["pdftotext", "-layout", path, "-"], capture_output=True, text=True, check=True).stdout
    lines = txt.splitlines()
    out = []
    for start in [i for i, l in enumerate(lines) if l.strip() == "Pakistan"]:
        window = lines[start:start + 70]
        year = None
        for l in window:
            m = re.match(r"\s*(20\d{2})\s*$", l)
            if m:
                year = int(m.group(1))
                break
        if year is None:
            continue
        row, flags = {}, []
        for label, col in ROWS:
            line = next((l for l in window if l.strip().startswith(label)), None)
            if line is None:
                row[col] = ""
                continue
            val, est = first_slot(line)
            row[col] = "" if val is None else ("%d" % val if float(val).is_integer() else "%s" % val)
            if est:
                flags.append(col)
        out.append((year, row, flags))
    return out


def build():
    rows = []
    for path in sorted(glob.glob(asset_path(RAW, "unsd_energy_balances_*_countries_M_Q.pdf"))):
        edition = re.search(r"balances_(\d{4})_", os.path.basename(path)).group(1)
        for year, vals, flags in parse_edition(path):
            note = []
            if vals.get("stock_changes_TJ", "") == "":
                note.append("stock changes not published ('..')")
            if vals.get("final_industries_nes_TJ", "") in ("", "0"):
                note.append("Industries n.e.s zero/absent: all final coal booked to Non-metallic minerals")
            rows.append(dict({"edition": edition, "calendar_year": str(year)}, **vals,
                             estimated_flags=";".join(flags), note="; ".join(note)))
    rows.sort(key=lambda r: (int(r["calendar_year"]), int(r["edition"])))
    return rows


def render(rows):
    buf = io.StringIO()
    for b in BANNER:
        buf.write(b + "\n")
    w = csv.DictWriter(buf, fieldnames=list(FIELDS), lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    text = render(build())
    if "--check" in argv:
        held = open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        same = held == text
        print("unsd coal supply control: %s" % ("byte-identical" if same else "DIFFERS"))
        return 0 if same else 1
    with open(OUT, "w", encoding="utf-8", newline="") as h:
        h.write(text)
    n = text.count("\n") - len(BANNER) - 1
    print("unsd coal supply control -> %s (%d edition-years)" % (OUT, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
