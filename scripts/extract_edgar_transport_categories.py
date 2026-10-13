"""Extract EDGAR's Pakistani transport source-category structure from the AP files.

WHY THIS EXISTS. The EDGAR GHG booklet defines its Transport sector only as "Mobile
combustion (road & rail & ship & aviation)" - no per-country category mapping. The
in-repo EDGAR air-pollutant files (v8.1, 1970-2022) DO carry ipcc_code_2006 rows per
country, and they are the only in-repo evidence of which transport modes EDGAR
actually models for Pakistan. The finding they encode: Pakistan has NO 1.A.3.d
(water-borne navigation) row at all, and 1.A.3.e (other transportation) is nil - so
EDGAR's Pakistani transport is road + rail + civil aviation, which is what the
paper's scope-matched comparison must match. CAVEAT, carried on every row: the AP
release (v8.1) is not the 2025 GHG booklet release; this is structural evidence
about EDGAR's Pakistani source-category coverage, not a read of the booklet's own
GHG allocation.

Deterministic; never in the engine hot path.

Usage:  python3 scripts/extract_edgar_transport_categories.py
Writes: data/activity/transport/edgar_pak_transport_categories.csv
"""

from pkinv.assets import asset_path
import csv
import io
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = asset_path(ROOT, "data", "activity", "transport",
                   "edgar_pak_transport_categories.csv")
ZIPS = (("NOx", asset_path(ROOT, "sources", "EDGAR", "EDGAR_NOx_1970_2022.zip")),
        ("PM2.5", asset_path(ROOT, "sources", "EDGAR", "EDGAR_PM25_1970_2022.zip")))
YEAR = "2022"
TRANSPORT_PREFIX = "1.A.3"
CAVEAT = ("EDGAR v8.1 AP release (1970-2022), not the 2025 GHG booklet - structural "
          "evidence of category coverage, stated as such")

MODES = {"1.A.3.a": "civil aviation", "1.A.3.b_noRES": "road (no resuspension)",
         "1.A.3.b_RES": "road resuspension (PM only)", "1.A.3.c": "railways",
         "1.A.3.d": "water-borne navigation", "1.A.3.e": "other transportation"}


def _rows_from_zip(pollutant, path):
    with zipfile.ZipFile(path) as z:
        xlsx_name = next(n for n in z.namelist() if n.endswith(".xlsx"))
        data = z.read(xlsx_name)
    import openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb["IPCC 2006"]
    it = ws.iter_rows(values_only=True)
    # The header row sits below a metadata block; find it by its first cell.
    for raw in it:
        if raw and str(raw[0]) == "IPCC_annex":
            hdr = [str(c) if c is not None else "" for c in raw]
            break
    else:
        raise SystemExit("header row not found in %s" % xlsx_name)
    code_i = hdr.index("ipcc_code_2006_for_standard_report")
    country_i = hdr.index("Country_code_A3")
    year_i = hdr.index("Y_" + YEAR)
    # Rows are split fossil/bio; sum them per category.
    found = {}
    for row in it:
        if row[country_i] == "PAK" and str(row[code_i]).startswith(TRANSPORT_PREFIX):
            code = str(row[code_i])
            value = row[year_i] or 0.0
            found[code] = found.get(code, 0.0) + float(value)
    return found, xlsx_name


def main():
    out = []
    for pollutant, path in ZIPS:
        found, src = _rows_from_zip(pollutant, path)
        for code, mode in MODES.items():
            present = code in found
            value = found.get(code)
            out.append({
                "ipcc_code_2006": code, "mode": mode, "pollutant": pollutant,
                "year": YEAR,
                "value_Gg": "" if value is None else round(float(value), 6),
                "present": "yes" if present else "ABSENT",
                "source_file": "%s::%s" % (os.path.basename(path), src),
                "note": CAVEAT,
            })
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    print("wrote %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(out)))
    for r in out:
        if r["pollutant"] == "NOx":
            print("  NOx %-14s %-28s %s %s"
                  % (r["ipcc_code_2006"], r["mode"], r["present"], r["value_Gg"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
