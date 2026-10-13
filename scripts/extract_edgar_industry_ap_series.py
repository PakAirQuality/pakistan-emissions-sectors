#!/usr/bin/env python3
"""EDGAR v8.1 air pollutants, Pakistan, the industrial categories, 2015-2022 - extracted, not
interpreted (rc58 W3).

Reads the seven country x sector workbooks held under data/raw/edgar/ (SO2, CO, NMVOC, NH3,
BC - acquired 2026-09-17) and sources/EDGAR/ (NOx, PM2.5 - held since the transport lane),
IPCC 2006 sheet, and writes one row per (species, IPCC category, fossil|bio, calendar year) for
1.A.2 Manufacturing Industries and Construction and 2.A.1-2.A.3 Mineral Industry. EDGAR keeps
fuel and biomass apart (fossil_bio); both are kept, because the engine's industry layer prices
fossil fuels and typed absents bagasse - the comparison must know which half it is looking at.

Nothing here is a benchmark verdict; scripts/build_industry_air_edgar_comparison.py does the
matched-year comparison and a test holds every register byte-identical across it.

Usage:  python3 scripts/extract_edgar_industry_ap_series.py
Reads:  data/raw/edgar/EDGAR_{SO2_v2,CO,NMVOC,NH3,BC}_1970_2022.zip, sources/EDGAR/EDGAR_{NOx,PM25}_1970_2022.zip
Writes: data/activity/industry/edgar_pak_industry_ap_series.csv
"""

from pkinv.assets import asset_path
import csv
import io
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = asset_path(ROOT, "data", "activity", "industry", "edgar_pak_industry_ap_series.csv")
ZIPS = (
    ("SO2", "data/raw/edgar/EDGAR_SO2_1970_2022_v2.zip"),
    ("CO", "data/raw/edgar/EDGAR_CO_1970_2022.zip"),
    ("NMVOC", "data/raw/edgar/EDGAR_NMVOC_1970_2022.zip"),
    ("NH3", "data/raw/edgar/EDGAR_NH3_1970_2022.zip"),
    ("BC", "data/raw/edgar/EDGAR_BC_1970_2022.zip"),
    ("NOx", "sources/EDGAR/EDGAR_NOx_1970_2022.zip"),
    ("PM2.5", "sources/EDGAR/EDGAR_PM25_1970_2022.zip"),
)
CODES = ("1.A.2", "2.A.1", "2.A.2", "2.A.3",
         "2.B", "2.C", "1.B.2")     # rc59: the IPPU process and fugitive comparisons
YEARS = tuple(range(2015, 2023))
FIELDS = ("species", "ipcc_code_2006", "ipcc_name", "fossil_bio", "calendar_year",
          "emissions_Gg", "edgar_release", "source_file")


def _sheet_rows(zpath):
    import openpyxl
    with zipfile.ZipFile(asset_path(ROOT, zpath)) as z:
        names = [n for n in z.namelist() if n.endswith(".xlsx")]
        if len(names) != 1:
            raise SystemExit("%s: expected one workbook, found %s" % (zpath, names))
        wb = openpyxl.load_workbook(io.BytesIO(z.read(names[0])), read_only=True)
        ws = wb["IPCC 2006"]
        header = None
        for row in ws.iter_rows(values_only=True):
            if row and row[0] == "IPCC_annex":
                header = list(row)
                continue
            if header and row[2] == "PAK":
                yield names[0], dict(zip(header, row))


def main():
    out = []
    for species, zpath in ZIPS:
        for fname, r in _sheet_rows(zpath):
            code = r["ipcc_code_2006_for_standard_report"]
            if code not in CODES:
                continue
            if r["Substance"] not in (species, species.replace(".", "")):
                raise SystemExit("%s: substance %r in the %s workbook" % (zpath, r["Substance"], species))
            for y in YEARS:
                v = r.get("Y_%d" % y)
                out.append({"species": species, "ipcc_code_2006": code,
                            "ipcc_name": r["ipcc_code_2006_for_standard_report_name"],
                            "fossil_bio": r["fossil_bio"], "calendar_year": y,
                            "emissions_Gg": "" if v is None else "%.6f" % float(v),
                            "edgar_release": "EDGAR v8.1 (1970-2022), August 2024",
                            "source_file": "%s::%s" % (os.path.basename(zpath), fname)})
    out.sort(key=lambda r: (r["species"], r["ipcc_code_2006"], r["fossil_bio"], r["calendar_year"]))
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write("# EDGAR v8.1 air pollutants for PAKISTAN, industrial categories, calendar 2015-2022, Gg -\n"
                "# extracted from the JRC country x sector workbooks (IPCC 2006 sheet), fuel (fossil) and\n"
                "# biomass (bio) rows kept apart as EDGAR keeps them. A comparison input, never an activity\n"
                "# and never a residual to insert; the engine's industry layer is fiscal and fossil-only.\n"
                "# Users of the data are obliged to acknowledge the source with a reference to the EDGARv8.1\n"
                "# air pollutant website (edgar.jrc.ec.europa.eu/dataset_ap81). scripts/extract_edgar_industry_ap_series.py\n")
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    print("EDGAR industry AP series -> %s (%d rows)" % (os.path.relpath(OUT), len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
