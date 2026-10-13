"""Extract EDGAR's Pakistani INDUSTRIAL series - Industrial Combustion and Processes - to a
tracked CSV, every gas the booklet carries (CO2, CH4, N2O and, for Processes, the F-gases).

WHY. The industrial-boundary program compares the engine's 1.A.2 (industry module + the captive
generation the power module computes) and its covered industrial aggregate against EDGAR for ALL
NINE fiscal years, not the reference year alone: the divergence's SHAPE is the diagnostic (at the
fiscal blend the two 1.A.2 series differ by -4.6..+6.6 Mt, alternating in sign, from FY2015-16
through FY2021-22, then the engine falls 17.9 and 17.5 Mt BELOW EDGAR in FY2022-23 and FY2023-24).
EDGAR is calendar; the fiscal blend (half of each adjacent column) is built downstream in
scripts/build_industry_edgar_divergence.py, the transport lane's convention.

WHAT EDGAR IS NOT. Its energy sectors are IEA-balance-derived, and the IEA balance for Pakistan
is HDIP-fed, so this is not an independent check on the HDIP coal series - it is a diagnostic
of where the two compilations part, and its 2023-2024 columns are preliminary.

Reads:  sources/EDGAR/EDGAR_2025_GHG_booklet_2025.xlsx (sheet GHG_by_sector_and_country)
Writes: data/activity/industry/edgar_pak_industry_series.csv
"""
import csv
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, ROOT  # noqa: E402

XLSX = asset_path(ROOT, "sources", "EDGAR", "EDGAR_2025_GHG_booklet_2025.xlsx")
SHEET = "GHG_by_sector_and_country"
OUT = asset_path(DATA, "activity", "industry", "edgar_pak_industry_series.csv")
SECTORS = ("Industrial Combustion", "Processes")
YEARS = tuple(range(2015, 2025))
GAS_COLUMNS = {"CO2": "co2_Mt", "GWP_100_AR5_CH4": "ch4_co2e_Mt", "GWP_100_AR5_N2O": "n2o_co2e_Mt",
               "GWP_100_AR5_F-gases": "fgas_co2e_Mt"}
FIELDS = ("year", "sector", "co2_Mt", "ch4_co2e_Mt", "n2o_co2e_Mt", "fgas_co2e_Mt",
          "total_Mt_co2e_AR5", "gwp", "release", "sheet", "source_file", "source_sha256", "note")
NOTES = {
    "Industrial Combustion": ("EDGAR's 'Industrial Combustion' is IPCC 1.A.2 manufacturing and construction "
                              "fuel combustion, all fuels, including industry's own generation; the booklet "
                              "carries no fuel or subsector split. IEA-balance-derived, HDIP-fed upstream: a "
                              "diagnostic beside the engine's 1.A.2, not an independent check on the coal series"),
    "Processes": ("EDGAR's 'Processes' is IPCC 2 (IPPU) in full - minerals, chemicals, metals, non-energy "
                  "products and the F-gases - where the engine prices cement 2.A.1 alone; the F-gas column is "
                  "kept apart so a covered-boundary comparison can exclude it"),
}


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build(xlsx=XLSX):
    import openpyxl
    wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
    rows = list(wb[SHEET].iter_rows(values_only=True))
    header = next(r for r in rows[:20] if r and any(c == 2015 for c in r))
    col = {c: i for i, c in enumerate(header)}
    digest, name = _sha256(xlsx), os.path.basename(xlsx)
    values = {}                                     # (sector, year) -> {gas_col: Mt}
    for r in rows:
        if not r or "PAK" not in r or r[1] not in SECTORS or r[0] not in GAS_COLUMNS:
            continue
        for y in YEARS:
            v = r[col[y]] if y in col else None
            if v is not None:
                values.setdefault((r[1], y), {})[GAS_COLUMNS[r[0]]] = float(v)
    out = []
    for sector in SECTORS:
        for y in YEARS:
            g = values.get((sector, y))
            if not g:
                continue
            total = sum(g.values())
            out.append({"year": y, "sector": sector,
                        "co2_Mt": round(g.get("co2_Mt", 0.0), 4),
                        "ch4_co2e_Mt": round(g.get("ch4_co2e_Mt", 0.0), 4),
                        "n2o_co2e_Mt": round(g.get("n2o_co2e_Mt", 0.0), 4),
                        "fgas_co2e_Mt": round(g["fgas_co2e_Mt"], 4) if "fgas_co2e_Mt" in g else "",
                        "total_Mt_co2e_AR5": round(total, 4), "gwp": "AR5",
                        "release": "EDGAR 2025 GHG booklet", "sheet": SHEET,
                        "source_file": name, "source_sha256": digest, "note": NOTES[sector]})
    return out


def main():
    if not os.path.exists(XLSX):
        print("EDGAR booklet not held at %s; nothing written" % os.path.relpath(XLSX, ROOT))
        return 1
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("wrote %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(rows)))
    for r in rows:
        if r["year"] in (2015, 2020, 2023, 2024):
            print("  %s %s %8.2f" % (r["year"], r["sector"][:22].ljust(22), r["total_Mt_co2e_AR5"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
