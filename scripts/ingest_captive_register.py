"""Extract the captive-plant register from the source workbook into activity data.

WHY. sources/Power Plants/power_plants_data_preparation.xlsx sheet CPP_master holds 1,105
captive power plants - 1,068 of them with coordinates and a per-row confidence grade - and
until this script existed the engine read none of it: the largest geocoded facility asset in
the repository sat unread inside a source document. The seventh instance of the
present-in-own-data pattern this project keeps finding.

sources/ stays the document; data/ carries what engines read. The pollutant-tpy columns are
NOT carried across - they are derived results, and activity files carry activity.

Deterministic; --check re-derives and diffs (make_readme_tables discipline).

Usage:  python3 scripts/ingest_captive_register.py [--check]
Writes: data/activity/power/captive_register.csv
"""

from pkinv.assets import asset_path
import csv
import io
import os
import re
import sys

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKBOOK = asset_path(ROOT, "sources", "Power Plants",
                        "power_plants_data_preparation.xlsx")
OUT = asset_path(ROOT, "data", "activity", "power", "captive_register.csv")

FIELDS = ("physical_plant", "sources", "province_region", "district", "industry_fuel",
          "capacity_mw", "gas_mmcfd", "gas_basis", "latitude", "longitude",
          "coord_confidence", "merged_from",
          # rc60: the dated and fuel-resolved columns the source sheets carry and CPP_master
          # drops. The register described 1,105 plants with no time axis at all, which is
          # why src/pkinv/report/spatial_weights.py lists its surface in KNOWN_UNKEYED with
          # the reason "the captive register carries no dates" and the cube backcasts one
          # FY2023-24 pattern across eight earlier years.
          "status", "date_of_disconnection", "licence_year", "fuel_primary",
          "location_evidence", "gas_jul24_mmcfd", "gas_oct24_mmcfd", "detail_sheet")
# The identical-connection-record rule below compares rows field by field. The rc60 columns are
# EXCLUDED from that comparison on purpose: two connections of one plant share a disconnection
# date and a licence year by construction, and letting those columns into the key would not
# make the rows distinguishable - it would only make the key longer while the OGRA
# reconciliation that depends on the repeats being FOUND quietly stopped finding them.
DEDUP_EXCLUDE = ("merged_from", "status", "date_of_disconnection", "licence_year",
                 "fuel_primary", "location_evidence", "gas_jul24_mmcfd", "gas_oct24_mmcfd",
                 "detail_sheet")
# Which source sheet describes a row, by the `sources` value CPP_master already carries.
DETAIL_SHEETS = {
    "SNGPL": ("CPP_SNGPL_gas", "plant"),
    "SSGC": ("CPP_SSGC_gas", "plant"),
    "NEPRA-licensed": ("CPP_NEPRA_licensed", "plant"),
    "NEPRA+SNGPL": ("CPP_NEPRA_licensed", "plant"),
}


def _norm(name):
    """A join key that survives the spelling differences between the master and source sheets:
    M/S prefixes, Pvt/Ltd suffixes, punctuation and case."""
    lowered = re.sub(r"\b(m/s|pvt|private|ltd|limited|the|unit|units)\b", " ",
                     str(name or "").lower())
    return re.sub(r"[^a-z0-9]+", "", lowered)


def _detail(book):
    """{(sheet, normalised plant): row} for the three source sheets CPP_master summarises.

    Read per sheet and joined per the master row's own `sources` value rather than globally,
    because a name that appears in two utilities' registers is two connections, not one plant,
    and a global join would hand one of them the other's dates.
    """
    out = {}
    for sheet_name, key in sorted({v for v in DETAIL_SHEETS.values()}):
        sheet = book[sheet_name]
        header = [c.value for c in next(sheet.iter_rows(max_row=1))]
        index = {name: i for i, name in enumerate(header) if name}
        for values in sheet.iter_rows(min_row=2, values_only=True):
            name = values[index[key]] if key in index else None
            if name in (None, ""):
                continue
            out.setdefault((sheet_name, _norm(name)),
                           {k: values[i] for k, i in index.items()})
    return out


def _cell(row, *names):
    """The first of several spellings a sheet might use, as text; "" when absent or blank."""
    for name in names:
        if row and row.get(name) not in (None, ""):
            value = row[name]
            if hasattr(value, "date"):
                return value.date().isoformat()
            if isinstance(value, float) and value.is_integer():
                return str(int(value))
            return str(value).strip()
    return ""


def build():
    book = openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)
    detail = _detail(book)
    sheet = book["CPP_master"]
    header = [c.value for c in next(sheet.iter_rows(max_row=1))]
    index = {name: i for i, name in enumerate(header)}
    rows = []
    for values in sheet.iter_rows(min_row=2, values_only=True):
        if values[index["physical_plant"]] in (None, ""):
            continue
        row = {}
        for field in FIELDS:
            if field not in index:
                row[field] = ""
                continue
            value = values[index[field]]
            row[field] = "" if value is None else str(value).strip()
        # the source sheet's own detail, joined on the master row's declared `sources`
        sheet_name, key = DETAIL_SHEETS.get(row["sources"], (None, None))
        found = detail.get((sheet_name, _norm(row["physical_plant"]))) if sheet_name else None
        row["detail_sheet"] = sheet_name if found else ""
        row["status"] = _cell(found, "status")
        row["date_of_disconnection"] = _cell(found, "date_of_disconnection")
        row["licence_year"] = _cell(found, "licence_year")
        row["fuel_primary"] = _cell(found, "fuel_primary")
        row["location_evidence"] = _cell(found, "location_evidence", "coord_method")
        row["gas_jul24_mmcfd"] = _cell(found, "gas_jul24_mmcfd")
        row["gas_oct24_mmcfd"] = _cell(found, "gas_oct24_mmcfd")
        # One vocabulary: the sheet grades coordinates high/medium/low but spells medium
        # two ways ('medium' 154 rows, 'med' 127). Normalised here so the registry's
        # confidence column has three values, not four.
        if row["coord_confidence"] == "med":
            row["coord_confidence"] = "medium"
        rows.append(row)
    # rc42 (the twentieth review's S-4, REVERSED on the evidence). The workbook carries 25
    # rows that repeat another row field for field (21 plants; `Mannan Shahid` three times at
    # one coordinate), and the review read them as duplicates the cube counted twice. They
    # are connection records: the register's metered gas sums to 288.01 MMCFD against the
    # 288 MMCFD OGRA publishes independently (data/activity/power/captive_gas.csv, verified)
    # ONLY with every row - collapsing them leaves 275.14, 12.86 MMCFD short, which is the
    # gas those connections draw. A plant with two identical connections appears twice and
    # carries twice the gas, and the cube is right to weight it so. The repeats are NAMED
    # here (merged_from) rather than removed, and tests/test_captive_register.py holds the
    # OGRA reconciliation as the guard: it fails the moment a row is dropped.
    counts = {}
    for row in rows:
        key = tuple(row[f] for f in FIELDS if f not in DEDUP_EXCLUDE)
        counts[key] = counts.get(key, 0) + 1
    ordinal = {}
    for row in rows:
        key = tuple(row[f] for f in FIELDS if f not in DEDUP_EXCLUDE)
        if counts[key] > 1:
            ordinal[key] = ordinal.get(key, 0) + 1
            note = ("identical connection record %d of %d; retained - the register reconciles "
                    "to OGRA's 288 MMCFD only with every row" % (ordinal[key], counts[key]))
            row["merged_from"] = (row["merged_from"] + "; " if row["merged_from"] else "") + note
    rows.sort(key=lambda r: (r["province_region"], r["district"], r["physical_plant"]))
    return rows


def render(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(FIELDS), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(check=False):
    text = render(build())
    if check:
        if not os.path.exists(OUT) or open(OUT, encoding="utf-8").read() != text:
            print("%s is stale; run python3 scripts/ingest_captive_register.py"
                  % os.path.relpath(OUT, ROOT))
            return 1
        print("captive register is current.")
        return 0
    open(OUT, "w", encoding="utf-8").write(text)
    rows = build()
    geocoded = sum(1 for r in rows if r["latitude"].strip())
    print("wrote %s: %d plants, %d geocoded"
          % (os.path.relpath(OUT, ROOT), len(rows), geocoded))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
