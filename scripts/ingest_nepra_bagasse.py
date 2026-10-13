#!/usr/bin/env python3
"""Parse NEPRA SoIR Table 8's E3 block - bagasse/biomass grid generation - into a CSV.

WHY SO SMALL A PARSER EXISTS. Eight plants, five years, forty numbers: transcription would
be faster to write. But a parser that reconciles against the table's own printed Total row
is auditable and re-runnable against a future edition, and this repo's rule is that data
enters through code that can fail loudly, not through fingers that cannot.

WHAT THE BLOCK CARRIES BESIDES GENERATION. Two fuel columns - primary and alternate - which
are the co-firing evidence: 'Bagasse + Biomass' plants, and The Thal Industries Corporation
listing furnace oil as its alternate fuel. Those labels are preserved verbatim; what share
of each plant's generation came from the alternate fuel is NOT published, so no split is
invented downstream.

Usage:  python3 scripts/ingest_nepra_bagasse.py
Writes: data/activity/power/bagasse_generation.csv
"""

from pkinv.assets import asset_path
import csv
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = asset_path(ROOT, "sources", "Power Plants",
                   "NEPRA State of Industry Report 2024.pdf")
from pkinv.core.io import write_or_check

OUT = asset_path(ROOT, "data", "activity", "power", "bagasse_generation.csv")

# Table 8 runs FY2019-20 .. FY2023-24 left to right; repo convention year N = FY N/N+1.
YEARS = [2019, 2020, 2021, 2022, 2023]
START = "E3: Bagasse/Biomass Power Projects"
END = "Total Bagasse/Biomass Power Projects"

NUM = re.compile(r"^\(?-?[\d,]+(?:\.\d+)?\)?$")
FUEL_WORDS = {"Bagasse", "Biomass", "FO", "+"}


def _text():
    if not os.path.exists(PDF):
        sys.exit("missing source: %s" % PDF)
    return subprocess.run(["pdftotext", "-layout", PDF, "-"],
                          capture_output=True, text=True, check=True).stdout.splitlines()


def _num(tok):
    return float(tok.replace(",", "")) if NUM.match(tok) else None


def parse(lines):
    rows, total_row = [], None
    inside = False
    for line in lines:
        t = line.strip()
        if START in t:
            inside = True
            continue
        if not inside:
            continue
        if END in t:
            nums = [v for v in (_num(x) for x in t.split()) if v is not None]
            if len(nums) == len(YEARS):
                total_row = nums
            break
        toks = t.split()
        if len(toks) < 6:
            continue
        nums = [v for v in (_num(x) for x in toks) if v is not None]
        if len(nums) != len(YEARS):
            continue
        words = toks[:len(toks) - len(YEARS)]
        # Fuel labels sit at the end of the text part and come from a tiny vocabulary;
        # everything before them is the plant name ("The Thal Industries Corporation").
        fuels = []
        while words and words[-1] in FUEL_WORDS:
            fuels.insert(0, words.pop())
        name = " ".join(words)
        label = " ".join(fuels)
        if label == "Bagasse + Biomass":
            primary, alternate = "Bagasse", "Biomass"
        elif len(fuels) == 2:
            primary, alternate = fuels
        else:
            primary, alternate = label or "Bagasse", ""
        for year, gwh in zip(YEARS, nums):
            rows.append({"fiscal_year": year, "plant": name, "fuel_primary": primary,
                         "fuel_alternate": alternate, "generation_GWh": gwh,
                         "source_table": "NEPRA SoIR 2024 Table 8 (E3)"})
    return rows, total_row


def main(check=False):
    rows, total_row = parse(_text())
    if total_row is None:
        sys.exit("printed Total row not found - layout changed, re-audit")
    for i, year in enumerate(YEARS):
        got = sum(r["generation_GWh"] for r in rows if r["fiscal_year"] == year)
        if abs(got - total_row[i]) > 0.02:
            sys.exit("FY%d: parsed %.2f GWh vs printed total %.2f - re-audit"
                     % (year, got, total_row[i]))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cols = ["fiscal_year", "plant", "fuel_primary", "fuel_alternate", "generation_GWh",
            "source_table"]
    if write_or_check(OUT, cols,
                      sorted(rows, key=lambda r: (r["plant"], r["fiscal_year"])), check):
        return 1
    if check:
        print("the bagasse generation reproduces from the held document.")
        return 0
    plants = sorted({r["plant"] for r in rows})
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    print("  %d rows, %d plants; every year reconciles with the printed Total row"
          % (len(rows), len(plants)))
    cofiring = sorted({(r["plant"], r["fuel_alternate"]) for r in rows
                       if r["fuel_alternate"] and r["fuel_alternate"] != "Bagasse"})
    for p, alt in cofiring:
        print("  co-firing: %-35s alternate fuel %s" % (p, alt))


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
