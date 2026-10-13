#!/usr/bin/env python3
"""Parse NEPRA SoIR Table 5 - plant-wise capacity WITH LOCATIONS - into a CSV.

WHY. The provincial allocation has run on one aggregate share for all fuels, because the
national fuel table has no geography. The plants do: Table 5 prints every station's
location as "Town, Province". Joined to the fuel ledger, that turns the sector's province
split from a single all-thermal surrogate into per-fuel point-source geography - Thar coal
is wholly Sindh, the RLNG corridor is Punjab, and blending them was the previous proxy's
known weakness (its own docstring called per-fuel proxies the obvious next refinement).

WHAT IS AND IS NOT A ROW. A data line carries "Location, ProvinceToken" followed by a
plant-type string and capacity numbers. Three of the newest Thar plants print BLANK
location cells (Thar Energy, Thar Coal Block-1, ThalNova) - they are skipped here and
resolved downstream by the mine-mouth rule, because a parser that fills blanks in its
source is inventing data. Name wrapping is the one layout trick: Huaneng's name spans the
lines above and below its data line, so a text fragment after an emitted row attaches to
that row when the next data line names itself.

Usage:  python3 scripts/ingest_nepra_locations.py
Writes: data/activity/power/plant_locations.csv
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

OUT = asset_path(ROOT, "data", "activity", "power", "plant_locations.csv")

# Province tokens as Table 5 prints them. Karachi appears as a location's own right
# ("Bin Qasim Town, Karachi") and is Sindh.
PROVINCE = {"Punjab": "Punjab", "Sindh": "Sindh", "Balochistan": "Balochistan",
            "KPK": "Khyber Pakhtunkhwa", "Karachi": "Sindh",
            "AJ&K": "Azad Jammu & Kashmir", "AJK": "Azad Jammu & Kashmir"}

# The layout is columnar: name | location | type | capacities, separated by runs of two
# or more spaces. Splitting on the gap is what keeps "Rousch Power   Sidhnai, Punjab"
# from being read as one long town name.
GAP = re.compile(r"\s{2,}")
LOC = re.compile(r"^(?P<town>.+),\s*(?P<prov>%s)$"
                 % "|".join(re.escape(p) for p in PROVINCE))
NUM = re.compile(r"-?[\d,]+")

HEADER = re.compile(r"Power Station|Plant Location|Dependable|Capacity|TABLE|^\s*$"
                    r"|Total |STATISTICAL DATA|STATE OF THE INDUSTRY|^\s*\d+\s*$"
                    r"|^[A-F]\d?:|Major Hydro|Small Hydro", re.IGNORECASE)


def _text():
    if not os.path.exists(PDF):
        sys.exit("missing source: %s" % PDF)
    return subprocess.run(["pdftotext", "-layout", PDF, "-"],
                          capture_output=True, text=True, check=True).stdout.splitlines()


def _bounds(lines):
    marks = [(i, int(m.group(1))) for i, l in enumerate(lines)
             if (m := re.match(r"^\s+TABLE (\d+)\s*$", l))]
    out = {}
    for idx, (i, n) in enumerate(marks):
        end = marks[idx + 1][0] if idx + 1 < len(marks) else len(lines)
        out[n] = (i, end)
    return out


def parse(lines):
    start, end = _bounds(lines)[5]
    rows, pending, skipped_blank = [], [], 0
    for raw in lines[start:end]:
        fields = [f for f in GAP.split(raw.strip()) if f]
        loc_idx = next((i for i, f in enumerate(fields) if LOC.match(f)), None)
        if loc_idx is not None and any(NUM.fullmatch(f.replace(",", ""))
                                       for f in fields[loc_idx + 1:]):
            m = LOC.match(fields[loc_idx])
            name = " ".join(fields[:loc_idx]).strip()
            if not name:
                name = " ".join(pending)
            elif pending and rows:
                # A trailing fragment above belongs to the row before it (Huaneng's
                # "(Sahiwal Imported Coal)" line) when this line names itself.
                rows[-1]["plant"] = "%s %s" % (rows[-1]["plant"], " ".join(pending))
            pending = []
            after = fields[loc_idx + 1:]
            station = after[0] if after and not NUM.fullmatch(
                after[0].replace(",", "")) and after[0] != "--" else ""
            rows.append({"plant": re.sub(r"\s+", " ", name).strip(),
                         "town": m.group("town").strip(),
                         "province": PROVINCE[m.group("prov")],
                         "station_type": station,
                         "source_table": "NEPRA SoIR 2024 Table 5"})
            continue
        t = raw.strip()
        if not t or HEADER.search(t):
            pending = []
            continue
        if NUM.search(t):
            # Numbers but no parseable location: the blank-location Thar plants.
            # Counted, never guessed; their name fragments must not leak into pending.
            skipped_blank += 1
            pending = []
        else:
            pending.append(t)
    return rows, skipped_blank


def main(check=False):
    rows, skipped_blank = parse(_text())
    seen, deduped = set(), []
    for r in rows:
        if r["plant"] and r["plant"] not in seen:
            seen.add(r["plant"])
            deduped.append(r)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    if write_or_check(OUT, ["plant", "town", "province", "station_type", "source_table"],
                      sorted(deduped, key=lambda r: r["plant"]), check):
        return 1
    if check:
        print("the plant locations reproduces from the held document.")
        return 0
    print("wrote %s" % os.path.relpath(OUT, ROOT))
    print("  %d located plants; %d rows with numbers but no printed location "
          "(the blank-location Thar plants land here and are resolved downstream)"
          % (len(deduped), skipped_blank))
    by_prov = {}
    for r in deduped:
        by_prov[r["province"]] = by_prov.get(r["province"], 0) + 1
    for p, n in sorted(by_prov.items(), key=lambda kv: -kv[1]):
        print("  %-24s %3d" % (p, n))


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
