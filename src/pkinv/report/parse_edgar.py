"""Extract the EDGAR Pakistan benchmarks, every sector, from the JRC EDGAR GHG booklet.

Source: edgar.jrc.ec.europa.eu -> Datasets -> GHG -> "EDGAR GHG emissions" (XLSX). The
"GHG_by_sector_and_country" sheet gives per-substance, per-sector, per-country annual series; the
CH4/N2O columns are ALREADY expressed as CO2e via AR5 GWP-100 (substance labels GWP_100_AR5_*). We
read every Pakistani sector for the latest year and sum CO2 + CH4(CO2e) + N2O(CO2e).

EDGAR's sectors are NOT the IPCC categories this inventory reports, and the mismatch is the
whole difficulty of using it as a benchmark. "Transport" is every mode; "Buildings" is
residential plus commercial plus stationary agriculture; "Waste" includes wastewater, which
this inventory does not yet estimate. Each benchmark row therefore carries a scope_detail
saying what it actually covers, and a comparison that ignores those notes will read real
scope differences as errors.

The booklet is TRACKED at sources/EDGAR/ since rc11 (4.6 MB): the benchmark register
pins its EDGAR rows to the file by sha256, so the source has to travel with the claim.
This module extracts, and the numbers live in the tracked data/benchmarks.csv.

Usage:  python3 -m pkinv.report.parse_edgar [path-to.xlsx]   # prints every sector
"""

from pkinv.assets import asset_path
import os
import sys

from pkinv.paths import ROOT

DEFAULT_XLSX = asset_path(ROOT, "sources", "EDGAR",
                            "EDGAR_2025_GHG_booklet_2025.xlsx")
BENCH = asset_path(ROOT, "data", "benchmarks.csv")
COUNTRY = "Pakistan"


def extract(xlsx, sector="Agriculture", year=None):
    """Return (year, co2, ch4_co2e, n2o_co2e, total) for one EDGAR sector."""
    year, sectors = extract_all(xlsx, year=year)
    v = sectors.get(sector, {})
    return (year, v.get("co2", 0.0), v.get("ch4", 0.0), v.get("n2o", 0.0), v.get("total", 0.0))


def extract_all(xlsx, year=None):
    """Return (year, {sector: {co2, ch4, n2o, total}}) for every Pakistani sector.

    year=None reads the latest column, the historic behaviour. Passing a year reads
    that column instead - the booklet's series reaches back decades, and a benchmark
    is only a benchmark when it is read at the inventory's own reference year.
    """
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    ws = wb["GHG_by_sector_and_country"]
    rows = ws.iter_rows(values_only=True)
    hdr = list(next(rows))
    years = [c for c in hdr if isinstance(c, int)]
    latest = max(years) if year is None else year
    if latest not in years:
        raise ValueError("year %s not in the booklet's series (%d-%d)"
                         % (latest, min(years), max(years)))
    ycol = hdr.index(latest)
    raw = {}
    for r in rows:
        if r[3] == COUNTRY:
            raw.setdefault(r[1], {})[r[0]] = r[ycol] or 0.0
    out = {}
    for sector, vals in raw.items():
        co2 = vals.get("CO2", 0.0)
        ch4 = vals.get("GWP_100_AR5_CH4", 0.0)   # already CO2e (AR5)
        n2o = vals.get("GWP_100_AR5_N2O", 0.0)   # already CO2e (AR5)
        out[sector] = {"co2": co2, "ch4": ch4, "n2o": n2o, "total": co2 + ch4 + n2o}
    return latest, out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    append = "--append" in argv
    paths = [a for a in argv if not a.startswith("--")]
    xlsx = paths[0] if paths else DEFAULT_XLSX
    if not os.path.exists(xlsx):
        print("EDGAR xlsx not found at %s -- download 'EDGAR GHG emissions' (XLSX) from "
              "edgar.jrc.ec.europa.eu and pass its path." % xlsx)
        return 1
    year, sectors = extract_all(xlsx)
    print("EDGAR Pakistan %d (AR5 CO2e), every sector:" % year)
    for name in sorted(sectors, key=lambda n: -sectors[n]["total"]):
        v = sectors[name]
        print("  %-24s CO2 %7.2f  CH4 %7.2f  N2O %6.2f  = %7.2f Mt"
              % (name, v["co2"], v["ch4"], v["n2o"], v["total"]))
    print("  %-24s %36s   %7.2f Mt"
          % ("TOTAL", "", sum(v["total"] for v in sectors.values())))
    co2, ch4, n2o, tot = (sectors["Agriculture"][k] for k in ("co2", "ch4", "n2o", "total"))
    if append:
        row = ('EDGAR,TOTAL,"Agriculture sector Pakistan (CO2 %.1f + CH4 %.1f + N2O %.1f)",%.1f,%d,'
               'AR5,EDGAR_2025_GHG booklet GHG_by_sector_and_country (2025 release; year-matched to '
               'this inventory; 2025 release revises Pakistan agri-CH4 history vs 2024 release)\n'
               % (co2, ch4, n2o, tot, year))
        with open(BENCH, encoding="utf-8") as f:
            existing = f.read()
        if "EDGAR_2025_GHG" not in existing:
            with open(BENCH, "a", encoding="utf-8") as f:
                f.write(row)
            print("  appended EDGAR-2025 TOTAL (%.1f Mt, %d) to data/benchmarks.csv" % (tot, year))
        else:
            print("  EDGAR-2025 row already present -- not duplicated")
    return 0


if __name__ == "__main__":
    sys.exit(main())
