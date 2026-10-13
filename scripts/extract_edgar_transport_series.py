"""Extract EDGAR's Pakistani transport series to a tracked CSV.

WHY A CSV. The EDGAR booklet is a large XLSX that this repository deliberately does not
track (.gitignore: EDGAR_*_booklet_*.xlsx), but the paper's headline external comparison
is computed from it. Anything a published number depends on has to be reproducible from
the repository, so the few numbers that matter are extracted here into a committed CSV
with the source file's hash beside them.

WHY A SERIES AND NOT ONE YEAR. This sector's reference year is FISCAL: July 2021 to June
2022. EDGAR reports calendar years. Comparing FY2021-22 against EDGAR's calendar 2022
alone and calling it "year-matched" overstates the alignment - half the fiscal year is
in EDGAR's 2021 column. With both years in hand the paper can report the fiscal-year
blend (half of each) as its primary comparison and say exactly what it is.

Writes: data/activity/transport/edgar_pak_transport_series.csv
"""

from pkinv.assets import asset_path
import csv
import hashlib
import os
import sys

from pkinv.paths import DATA, ROOT
from pkinv.report import parse_edgar

OUT = asset_path(DATA, "activity", "transport", "edgar_pak_transport_series.csv")
SECTOR = "Transport"
YEARS = tuple(range(2015, 2025))
FIELDS = ("year", "sector", "co2_Mt", "ch4_co2e_Mt", "n2o_co2e_Mt",
          "total_Mt_co2e_AR5", "gwp", "release", "sheet", "source_file",
          "source_sha256", "note")


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(xlsx=None):
    xlsx = parse_edgar.DEFAULT_XLSX if xlsx is None else xlsx
    digest = _sha256(xlsx)
    name = os.path.basename(xlsx)
    rows = []
    for year in YEARS:
        try:
            y, sectors = parse_edgar.extract_all(xlsx, year=year)
        except ValueError:
            continue                      # year outside the booklet's series
        v = sectors.get(SECTOR)
        if not v:
            continue
        rows.append({
            "year": y, "sector": SECTOR,
            "co2_Mt": round(v["co2"], 4),
            "ch4_co2e_Mt": round(v["ch4"], 4),
            "n2o_co2e_Mt": round(v["n2o"], 4),
            "total_Mt_co2e_AR5": round(v["total"], 4),
            "gwp": "AR5", "release": "EDGAR 2025 GHG booklet",
            "sheet": "GHG_by_sector_and_country",
            "source_file": name, "source_sha256": digest,
            "note": "EDGAR's 'Transport' sector is mobile combustion across road, "
                    "rail, ship and aviation; the booklet carries no IPCC-category "
                    "split. Which Pakistani categories that covers is evidenced "
                    "separately in edgar_pak_transport_categories.csv.",
        })
    return rows


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    xlsx = argv[0] if argv else parse_edgar.DEFAULT_XLSX
    if not os.path.exists(xlsx):
        print("EDGAR booklet not found at %s\n"
              "Download 'EDGAR GHG emissions' (XLSX) from "
              "edgar.jrc.ec.europa.eu and pass its path. Nothing was written."
              % os.path.relpath(xlsx, ROOT))
        return 1
    rows = build(xlsx)
    if not rows:
        print("No Pakistani Transport rows found in %s. Nothing was written." % xlsx)
        return 1
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(FIELDS))
        w.writeheader()
        w.writerows(rows)
    print("wrote %s (%d years, %s-%s)"
          % (os.path.relpath(OUT, ROOT), len(rows), rows[0]["year"],
             rows[-1]["year"]))
    for r in rows[-4:]:
        print("  %s  %8.4f Mt CO2e AR5" % (r["year"], r["total_Mt_co2e_AR5"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
