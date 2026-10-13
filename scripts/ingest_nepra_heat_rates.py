#!/usr/bin/env python3
"""Parse NEPRA State of Industry Report heat-rate tables into a versioned CSV.

WHY THIS EXISTS. The plant fuel ledger (Tables 18/21/26, scripts/ingest_nepra_plants.py)
meters coal in mass and gas in energy, which leaves the sector's largest open question -
what calorific value turns the national coal mass into the national coal energy - resting
on a single diagnostic ratio. Tables 20, 23 and 28 carry the third channel that arbitrates
it: per-plant heat rates in Btu/kWh, five fiscal years, for GENCOs, IPPs and K-Electric.
Heat rate x generation is fuel energy; fuel energy over the ledger's coal mass is a
calorific value, plant by plant. heat_rate.py's docstring says resolving the coal
instability "needs the plant-level tables SIR 20/23/28, still unparsed" - this is that
parse.

THE BASIS IS PRINTED, ONCE. Table 28's footnote [1]: "Since most of the IPPs report heat
rates on LHV basis, hence KE is also reporting on LHV using HHV-LHV factors for like to
like comparison." So the channel is NET-calorific, and any calorific value derived from it
is an NCV, directly comparable to IPCC Table 1.2. The footnote sits in Table 28 and
testifies about Tables 20/23; the hr_basis column preserves that distinction (printed
versus testified) rather than flattening it.

HOW THE LAYOUT IS PARSED. Same block rule as the fuel tables: a plant is a run of
ascending fiscal years, its name is every text scrap left of those rows, joined. Two
differences from the fuel parser:

  'n.p.' IS A POSITION, NOT NOISE. The fuel parser reads the first two numbers of a row,
  which is immune to trailing n.p. Here the four columns are positional (HR gross, HR net,
  eff gross, eff net) and Sahiwal prints 'n.p.' in its net columns for four of five years -
  dropping the token would slide efficiency into the heat-rate slot. So tokens parse to
  float-or-None and the row keeps its shape.

  THE GAS/HSD SUB-TABLE IS WIDTH-DETECTED. Table 23 ends with four dual-fuel plants (Saif,
  Orient, Sapphire, Halmore) whose rows carry eight values - Gas and HSD sub-columns under
  each heading. Eight tokens means two output rows, fuel_column 'Gas' and 'HSD'; four means
  one row with fuel_column blank.

WHAT IS SCREENED, WHAT IS KEPT VERBATIM. Free-text rows ("Plant de-licensed.", GTPS
Faisalabad 2022-23) are skipped and counted. 0.00 rows (Hub, KAPCO, Jamshoro 2023-24) are
kept - they mean "did not run", and downstream joins carry no generation for them anyway.
Physically impossible values are NOTED, NEVER CORRECTED: Thar Coal Block-I prints a net
heat rate BELOW its gross one in both years (8,648.63 against 8,749.00), which no plant
can do; the note column says so and the cells stay as printed, because a parser that
improves its source is a parser that cannot be audited against it.

Usage:  python3 scripts/ingest_nepra_heat_rates.py
Writes: data/activity/power/plant_heat_rates.csv
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

OUT = asset_path(ROOT, "data", "activity", "power", "plant_heat_rates.csv")

# (table, system, hr_basis). The LHV footnote is PRINTED in Table 28 and covers the IPP
# convention by its own wording; 20/23 carry the distinct 'testified' label.
TABLES = {20: ("GENCO", "LHV-per-KE-footnote"),
          23: ("IPP", "LHV-per-KE-footnote"),
          28: ("K-Electric", "LHV")}

YEAR_ROW = re.compile(r"^(?P<name>.*?)(?P<year>(?:19|20)\d{2}-\d{2})\s+(?P<rest>.*)$")
NUM = re.compile(r"^-?[\d,]+(?:\.\d+)?$")

# Same furniture filters as the fuel parser, extended with this table's own headers.
NOT_A_NAME = re.compile(
    r"^(?:power|station|year|units?|generated|quantity|cost|average|overall|net|table"
    r"|statistical data|state of the industry|fuel|gen\.|consumption|rs\.|million|\d+"
    r"|heat rate|plant efficiency|on gross|on net|generation|to ntdc|basis|source"
    r"|gas\s+hsd)\b", re.IGNORECASE)
HEADER_TOKENS = re.compile(
    r"Btu/kWh|Efficiency|On Gross|On Net|NTDC|Source:|LHV|HHV|Heat Rate|commissioning"
    r"|de-licensed", re.IGNORECASE)
FOOTNOTE = re.compile(r"\[\d+\]")

# A heat rate below 3,412.14 Btu/kWh is over unity efficiency; above 30,000 is under 11
# percent. Outside the band is a misparse, not a plant.
HR_LO, HR_HI = 3412.14, 30000.0


def _text():
    if not os.path.exists(PDF):
        sys.exit("missing source: %s" % PDF)
    return subprocess.run(["pdftotext", "-layout", PDF, "-"],
                          capture_output=True, text=True, check=True).stdout.splitlines()


def _table_bounds(lines):
    marks = [(i, int(m.group(1)))
             for i, l in enumerate(lines)
             if (m := re.match(r"^\s+TABLE (\d+)\s*$", l))]
    out = {}
    for idx, (i, n) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        out[n] = (i, end)
    return out


def _fy(token):
    """'2023-24' -> 2023, the repo's power convention (year N = FY N/N+1)."""
    return int(token.split("-")[0])


def _tokens(rest):
    """float-or-None per cell, preserving 'n.p.' as a positional placeholder.

    Any other word (free text like 'Plant de-licensed.') yields an empty list so the row
    is counted as text, not silently mistaken for a short data row.
    """
    out = []
    for tok in rest.split():
        if NUM.match(tok):
            out.append(float(tok.replace(",", "")))
        elif tok in ("n.p.", "n.p"):
            out.append(None)
        else:
            return []
    return out


def _screen(vals, note_parts):
    """HR plausibility; impossible net<gross noted, kept verbatim."""
    for v in vals[:2]:
        if v is not None and v != 0.0 and not (HR_LO <= v <= HR_HI):
            return False
    g, n = vals[0], vals[1]
    if g and n and n < g:
        note_parts.append("net HR below gross - physically impossible, kept as printed")
    return True


def parse(lines):
    bounds = _table_bounds(lines)
    rows, freetext_skipped, screened_out = [], 0, []
    for table, (system, basis) in sorted(TABLES.items()):
        if table not in bounds:
            continue
        start, end = bounds[table]
        block, prev_year, pending = [], None, []

        def flush():
            if not block:
                return
            scraps = []
            for f, _y, _v in block:
                f = FOOTNOTE.sub("", f).strip()
                if f and not HEADER_TOKENS.search(f) and not NOT_A_NAME.match(f):
                    scraps.append(f)
            name = re.sub(r"\s+", " ", " ".join(scraps)).strip() or "UNNAMED"
            for _f, year, vals in block:
                note_parts = []
                if not _screen(vals, note_parts):
                    screened_out.append("%s FY%d: HR outside (%.0f, %.0f)"
                                        % (name, year, HR_LO, HR_HI))
                    continue
                if len(vals) == 4:
                    fuel_cols = [("", vals)]
                elif len(vals) == 8:
                    # Gas/HSD sub-columns: positions 0,2,4,6 are Gas, 1,3,5,7 HSD.
                    fuel_cols = [("Gas", vals[0::2]), ("HSD", vals[1::2])]
                else:
                    screened_out.append("%s FY%d: %d values, expected 4 or 8"
                                        % (name, year, len(vals)))
                    continue
                for fuel_col, v in fuel_cols:
                    rows.append({
                        "fiscal_year": year, "system": system, "plant": name,
                        "fuel_column": fuel_col,
                        "hr_gross_btu_kwh": "" if v[0] is None else v[0],
                        "hr_net_btu_kwh": "" if v[1] is None else v[1],
                        "eff_gross_pct": "" if v[2] is None else v[2],
                        "eff_net_pct": "" if v[3] is None else v[3],
                        "hr_basis": basis, "note": "; ".join(note_parts),
                        "source_table": "NEPRA SoIR 2024 Table %d" % table,
                    })

        for raw in lines[start:end]:
            line = raw.rstrip()
            ym = YEAR_ROW.match(line)
            if not ym:
                text = FOOTNOTE.sub("", line).strip()
                if (text and not NOT_A_NAME.match(text) and not NUM.match(text)
                        and not HEADER_TOKENS.search(text)):
                    pending.append(text)
                continue
            year = _fy(ym.group("year"))
            vals = _tokens(ym.group("rest"))
            if not vals:
                freetext_skipped += 1      # "Plant de-licensed." and header spillover
                # the name fragment on such a line still belongs to the block
                frag = ym.group("name").strip()
                if frag:
                    pending.append(frag)
                continue
            if prev_year is not None and year <= prev_year:
                flush()
                block = []
            block.append((" ".join(pending + [ym.group("name")]), year, vals))
            pending = []
            prev_year = year
        flush()
        block, prev_year, pending = [], None, []
    return rows, freetext_skipped, screened_out


def main(check=False):
    rows, freetext, screened = parse(_text())
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    cols = ["fiscal_year", "system", "plant", "fuel_column", "hr_gross_btu_kwh",
            "hr_net_btu_kwh", "eff_gross_pct", "eff_net_pct", "hr_basis", "note",
            "source_table"]
    if write_or_check(OUT, cols,
                      sorted(rows, key=lambda r: (r["system"], r["plant"], r["fuel_column"],
                                            r["fiscal_year"])), check):
        return 1
    if check:
        print("the per-plant heat rates reproduces from the held document.")
        return 0
    plants = {(r["system"], r["plant"]) for r in rows}
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    print("  %d rows, %d plants, FY%d-FY%d"
          % (len(rows), len(plants), min(r["fiscal_year"] for r in rows),
             max(r["fiscal_year"] for r in rows)))
    for system in sorted(s for s, _b in TABLES.values()):
        sub = [r for r in rows if r["system"] == system]
        print("  %-11s %3d rows, %2d plants" % (system, len(sub),
                                                len({r["plant"] for r in sub})))
    noted = [r for r in rows if r["note"]]
    print("  rows with notes (impossible values kept verbatim): %d" % len(noted))
    for r in noted:
        print("      FY%s %s: %s" % (r["fiscal_year"], r["plant"], r["note"]))
    print("  free-text/header year rows skipped: %d" % freetext)
    print("  rows dropped by the plausibility screen: %d" % len(screened))
    for m in screened:
        print("      %s" % m)


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
