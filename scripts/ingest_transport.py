"""Ingest registered-vehicle stock by district for the road transport sector.

Source: `Transport Data.xlsx`, sheet `Full data set`, in the pakistan-emissions-sectors
repository. Chosen over `Transport_Emissions_Inventory_Cleaned_v2.xlsx` because it has the
wider coverage — Punjab from 2003, 122 districts — and because v2's value is its
provenance flags rather than its numbers.

THIS IS CUMULATIVE STOCK, NOT NEW REGISTRATIONS. The source table titles say so outright:
"NUMBER OF MOTOR VEHICLES STOOD REGISTERED UPTO 30.06.2023", "Motor Vehicles 'Registered'
… Uptill 30th June", "DISTRICT WISE POPULATION OF MOTOR VEHICLES (REGD:)". A scrapped
vehicle stays in the total unless formally deregistered, which is why the sector runs a
survival model rather than using these counts as fleet.

Three normalisations, all recorded rather than applied silently:
  * three separate vehicle vocabularies (this file, v2, and the Punjab workbook) collapse
    to nine EI classes via vehicle_classes.csv
  * the `Pickups, delivery Vanss` double-s typo, which a naive join drops 1,506 rows on
  * two district names containing non-breaking spaces

Usage:  python3 scripts/ingest_transport.py
Writes: data/activity/transport/vehicles_district.csv
"""

from pkinv.assets import asset_path
import csv
import os
import re
import sys

import openpyxl

from pkinv.paths import ROOT, DATA
from pkinv.core.io import read_rows

# rc37: the workbook is held under sources/; the old literal was one machine's path and
# nothing else could rebuild vehicles_district.csv
SRC = asset_path(ROOT, "sources", "Transport", "Transport Data.xlsx")
OUT_DIR = asset_path(DATA, "activity", "transport")
OUT = asset_path(OUT_DIR, "vehicles_district.csv")
CLASSES = asset_path(OUT_DIR, "vehicle_classes.csv")

PROVINCE_FIX = {"KPK": "Khyber Pakhtunkhwa", "KP": "Khyber Pakhtunkhwa",
                "The Punjab": "Punjab", "Baluchistan": "Balochistan"}


def _norm_type(s):
    """Lowercase, collapse punctuation and whitespace, so the three vocabularies meet."""
    s = str(s).replace("\xa0", " ").lower()
    s = re.sub(r"[/,]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _count(v):
    """`Count` is not reliably numeric: one cell holds '11,644 1', a footnote marker
    fused to the value. Take the leading number and drop the rest."""
    if isinstance(v, (int, float)):
        return float(v)
    m = re.match(r"\s*([\d,]+)", str(v or ""))
    return float(m.group(1).replace(",", "")) if m else None


def _classes():
    return {_norm_type(r["source_type"]): r["ei_class"] for r in read_rows(CLASSES, comments=False)}


def main():
    cls = _classes()
    wb = openpyxl.load_workbook(SRC, data_only=True, read_only=True)
    rows, unresolved, dropped = {}, set(), 0

    for r in wb["Full data set"].iter_rows(min_row=2, values_only=True):
        if not r or r[0] is None:
            continue
        year, province, _div, district, vtype, _cat, count = r[:7]
        n = _count(count)
        if n is None:
            dropped += 1
            continue
        key = _norm_type(vtype)
        if key not in cls:
            unresolved.add(str(vtype))
            continue
        province = PROVINCE_FIX.get(str(province).strip(), str(province).strip())
        district = str(district).replace("\xa0", " ").strip()
        k = (int(year), province, district, cls[key])
        # Balochistan reports 32 disaggregated types where the others report 8-9, so
        # several source types sum into one EI class.
        rows[k] = rows.get(k, 0.0) + n

    if unresolved:
        raise SystemExit("vehicle types not in %s:\n  %s"
                         % (CLASSES, "\n  ".join(sorted(unresolved))))

    out = [{"year": y, "province": p, "district": d, "ei_class": c, "vehicles": round(v, 0),
            "source": "Provincial Bureaux of Statistics registered-vehicle tables "
                      "(cumulative stock); see Transport Data.xlsx Citation sheet"}
           for (y, p, d, c), v in sorted(rows.items())]
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["year", "province", "district", "ei_class",
                                          "vehicles", "source"])
        w.writeheader()
        w.writerows(out)

    yrs = sorted({r["year"] for r in out})
    print("wrote %s" % os.path.relpath(OUT, os.path.dirname(DATA)))
    print("  %d rows | %d districts | %d provinces | %d-%d"
          % (len(out), len({r["district"] for r in out}),
             len({r["province"] for r in out}), min(yrs), max(yrs)))
    if dropped:
        print("  %d rows dropped for an unparseable Count" % dropped)
    latest = max(yrs)
    by = {}
    for r in out:
        if r["year"] == latest:
            by[r["province"]] = by.get(r["province"], 0.0) + r["vehicles"]
    print("  %d registered stock: %s" % (latest, ", ".join(
        "%s %.2fM" % (p, v / 1e6) for p, v in sorted(by.items(), key=lambda x: -x[1]))))


if __name__ == "__main__":
    main()
