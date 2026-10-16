"""Ingest the OCAC sectoral-sales tables into committed transport activity CSVs.

Reads the nine annual and 48 monthly PDFs the aviation sector fetched (indexed in
data/activity/aviation/ocac_annual_sources.csv and ocac_cumulative_sources.csv) via
pkinv.sectors.transport.ocac, and writes:

  data/activity/transport/ocac_sectoral_annual.csv      (9 years x rows x products)
  data/activity/transport/ocac_sectoral_provincial.csv  (area pages, direct months)

The engine reads only these CSVs; pdftotext never runs in the engine or test hot
path. Deterministic: running twice produces identical files.

COVERAGE NOTE, monthly. The 22 cumulative-kind editions (Aug-2022 to Jun-2024
period-to-date reports) carry a PAKISTAN page only - no provincial pages exist in
THOSE PDFs. For a release this was read as "no provincial pages exist for those
months", and the transport paper borrowed FY2024-25's provincial shape on the
strength of it. The claim was true of the cumulative editions and false of the
publication: OCAC also issued DIRECT single-month editions of the same months,
with full area pages, and the repository holds all 36 under
data/raw/ocac/monthly_sector_province/ (fetched and hash-pinned by
scripts/fetch_ocac_monthly.py). This ingest reads their area pages for exactly
the months the cumulative editions cannot serve, which completes the provincial
panel for FY2022-23 and FY2023-24 - the reference year now carries its own
twelve provincial months and nothing is borrowed.

Their PAKISTAN pages ARE written, report_kind=monthly, for one reason: they are
the document's own control over its area pages, and the additive-areas closure
test needs the same-document national row to hold the provinces to. This is not
a second national vintage in the two-vintages sense - the differenced cumulative
months and these direct months were verified identical to the tonne
(outputs/ocac_direct_edition_crosscheck.csv), the rows carry distinct
report_kind and source documents, and core/ocac_monthly.tonnes() prefers the
cumulative bucket wherever both exist, so no consumer's numbers move. Cumulative
national rows remain period-to-date, not monthly, quantities.

Usage:  python3 scripts/ingest_ocac_sectoral.py
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.sectors.transport import ocac  # noqa: E402
from pkinv.core.io import read_rows

OUT_DIR = asset_path(ROOT, "data", "activity", "transport")
ANNUAL_OUT = asset_path(OUT_DIR, "ocac_sectoral_annual.csv")
PROV_OUT = asset_path(OUT_DIR, "ocac_sectoral_provincial.csv")

# Products worth committing (energy products the inventory can use; TOTAL retained
# as the row-closure witness).
PRODUCTS = ("100 LL", "HOBC", "MS", "JP-8", "JP-1", "KERO", "HSD", "LDO", "FO",
            "TOTAL", "TOTAL_PRIOR")


def _index(path):
    return read_rows(path, comments=False)


def annual_rows():
    out = []
    for entry in _index(ocac.ANNUAL_INDEX):
        path = asset_path(ocac.ANNUAL_DIR, entry["local_file"])
        parsed = ocac.parse_annual(path)
        for w in parsed["warnings"]:
            print("  %s: %s" % (entry["local_file"], w))
        digest = ocac.sha256(path)
        fy_start = int(entry["fiscal_year"])
        for section, row, vals in parsed["rows"]:
            if row not in ocac.COMMIT_ROWS:
                continue
            for product in PRODUCTS:
                if product not in vals:
                    continue
                out.append({
                    "fiscal_year_start": fy_start,
                    "fy_label": entry["period_label"],
                    "inventory_year": fy_start + 1,
                    "section": section,
                    "sector_row": row,
                    "product": product,
                    "tonnes": round(vals[product], 1),
                    "source_file": entry["local_file"],
                    "source_sha256": digest,
                })
    return out


def provincial_rows():
    out = []
    for entry in _index(ocac.MONTHLY_INDEX):
        path = asset_path(ocac.MONTHLY_DIR, entry["local_file"])
        pages = ocac.parse_monthly(path)
        digest = ocac.sha256(path)
        areas = {a for a, _p in pages}
        note = ""
        if entry["period_end"] == "2021-07":
            note = "OCAC coverage note: Hascol data missing this month"
        for area, parsed in pages:
            for w in parsed["warnings"]:
                print("  %s %s: %s" % (entry["local_file"], area, w))
            for section, row, vals in parsed["rows"]:
                if row not in ocac.COMMIT_ROWS:
                    continue
                for product in PRODUCTS:
                    if product not in vals:
                        continue
                    out.append({
                        "fiscal_year_start": entry["fiscal_year"],
                        "month": entry["period_end"],
                        "area": area,
                        "additive": 0 if area in ocac.NON_ADDITIVE_AREAS
                        else (0 if area == "PAKISTAN" else 1),
                        "fata_separate": 1 if "FATA" in areas else 0,
                        "section": section,
                        "sector_row": row,
                        "product": product,
                        "tonnes": round(vals[product], 1),
                        "report_kind": entry["report_kind"],
                        "coverage_note": note,
                        "source_file": entry["local_file"],
                        "source_sha256": digest,
                    })
    return out


DIRECT_DIR = asset_path(ROOT, "data", "raw", "ocac", "monthly_sector_province")


def direct_provincial_rows(already_covered):
    """Area-page rows from the held direct editions, for months the panel lacks.

    `already_covered` is the set of YYYY-MM months whose provincial pages the sources/
    editions supply; a direct edition for one of those months is skipped rather than
    written twice, so a month's provincial rows have exactly one source document.
    """
    import glob
    import re
    out = []
    for path in sorted(glob.glob(asset_path(DIRECT_DIR,
                                              "ocac_sector_province_*.pdf"))):
        match = re.search(r"_(\d{4})_(\d{2})\.pdf$", path)
        year, mo = int(match.group(1)), int(match.group(2))
        month = "%04d-%02d" % (year, mo)
        if month in already_covered:
            continue
        pages = ocac.parse_monthly(path)
        digest = ocac.sha256(path)
        areas = {a for a, _p in pages}
        for area, parsed in pages:
            for w in parsed["warnings"]:
                print("  %s %s: %s" % (os.path.basename(path), area, w))
            for section, row, vals in parsed["rows"]:
                if row not in ocac.COMMIT_ROWS:
                    continue
                for product in PRODUCTS:
                    if product not in vals:
                        continue
                    out.append({
                        "fiscal_year_start": year if mo >= 7 else year - 1,
                        "month": month,
                        "area": area,
                        "additive": 0 if (area in ocac.NON_ADDITIVE_AREAS
                                          or area == "PAKISTAN") else 1,
                        "fata_separate": 1 if "FATA" in areas else 0,
                        "section": section,
                        "sector_row": row,
                        "product": product,
                        "tonnes": round(vals[product], 1),
                        "report_kind": "monthly",
                        "coverage_note": "area pages from the direct single-month edition; "
                                         "the cumulative edition of this month prints "
                                         "PAKISTAN only",
                        "source_file": os.path.basename(path),
                        "source_sha256": digest,
                    })
    return out


CLASSES = ("DOMESTIC", "AGRICULTURE", "Total Transport", "Total Industry", "Total Power",
           "Total Government")

# THE CORRECTIONS THE RULE BELOW IS EXPECTED TO APPLY, declared so that a change in what it
# finds fails the ingest instead of moving a booked quantity silently. The declaration lives in
# pkinv.sectors.transport.ocac_corrections, which the transport diagnostics read too; it is
# re-exported here for scripts/ingest_release_extension.py, which reports it as applied.
from pkinv.sectors.transport.ocac_corrections import DECLARED_PUBLISHER_CORRECTIONS  # noqa: E402


def publisher_corrections(rows):
    """Restore a first print's non-additive cell where the next edition restores it (rc68).

    OCAC's FY2017-18 edition prints an HSD grand total of 9,038,298 t while its customer
    classes sum to 8,516,476 t: 521,822 t are missing from one class. The FY2018-19 edition
    restates FY2017-18 Road as 15,454,576 t, exactly 521,822 t above the first print, with the
    grand total unchanged. HSD is the only product whose classes fail its own total, and by
    the same amount, so the missing tonnes are Road HSD. Through rc67 the engine booked the
    short figure. The rule applied here is general and fails closed: a cell is corrected only
    when ONE product's classes fall short of its own printed total by g, and ONE customer row
    is restated in the next edition by g with the grand total unchanged (both within 2 t of
    printed rounding). The corrected value is derivable from the first print's own total;
    the next edition only names the row. Returns the corrections applied.
    """
    def val(year, section, row, product):
        for r in rows:
            if (int(r["fiscal_year_start"]), r["section"], r["sector_row"], r["product"]) == \
                    (year, section, row, product):
                return r
        return None

    applied = []
    years = sorted({int(r["fiscal_year_start"]) for r in rows})
    for year in years:
        products = {r["product"] for r in rows if int(r["fiscal_year_start"]) == year} \
            - {"TOTAL", "TOTAL_PRIOR"}
        gaps = {}
        for prod in products:
            total = val(year, "TOTALS", "TOTAL_INTERNAL", prod)
            if total is None:
                continue
            classes = sum(float(r["tonnes"]) for r in rows
                          if int(r["fiscal_year_start"]) == year and r["product"] == prod
                          and r["sector_row"] in CLASSES)
            gap = float(total["tonnes"]) - classes
            if abs(gap) > 2:
                gaps[prod] = gap
        if len(gaps) != 1:
            continue
        (prod, gap), = gaps.items()
        grand_first = val(year, "TOTALS", "TOTAL_INTERNAL", "TOTAL")
        grand_next = val(year + 1, "TOTALS", "TOTAL_INTERNAL", "TOTAL_PRIOR")
        if grand_first is None or grand_next is None or \
                abs(float(grand_next["tonnes"]) - float(grand_first["tonnes"])) > 2:
            continue
        restated = []
        for r in rows:
            if int(r["fiscal_year_start"]) != year or r["product"] != "TOTAL" or \
                    r["sector_row"] in CLASSES or r["section"] == "TOTALS":
                continue
            nxt = val(year + 1, r["section"], r["sector_row"], "TOTAL_PRIOR")
            if nxt is not None and abs(float(nxt["tonnes"]) - float(r["tonnes"]) - gap) <= 2:
                restated.append(r)
        if len(restated) != 1:
            continue
        row = restated[0]
        section, name = row["section"], row["sector_row"]
        aggregate = {"TRANSPORT": "Total Transport"}.get(section)
        targets = [(section, name, prod), (section, name, "TOTAL")]
        if aggregate:
            targets += [(section, aggregate, prod), (section, aggregate, "TOTAL")]
        for key in targets:
            cell = val(year, *key)
            if cell is None:
                raise SystemExit("publisher correction for FY%d %s: no %s cell" % (year, prod, key))
            before = float(cell["tonnes"])
            cell["tonnes"] = "%.1f" % (before + gap)
            applied.append((year, key, before, before + gap))
    return applied


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    a = annual_rows()
    # The FY2015-16 edition is image-only (a 602-px flipbook, no text layer), so
    # it enters through the identity-gated transcription rather than pdftotext -
    # see sectors/transport/ocac_image_edition.py for the four gate families.
    # Its rows are PREPENDED so the file stays sorted by fiscal_year_start.
    from pkinv.sectors.transport import ocac_image_edition
    a = ocac_image_edition.annual_rows(ocac.COMMIT_ROWS) + a
    applied = publisher_corrections(a)
    found = {(year,) + key: (before, after - before) for year, key, before, after in applied
             if key[2] not in ("TOTAL",) and key[1] not in ("Total Transport",)}
    declared = {k: (v["first_print_tonnes"], v["gap_tonnes"])
                for k, v in DECLARED_PUBLISHER_CORRECTIONS.items()}
    if {k: (round(b), round(g)) for k, (b, g) in found.items()} != \
            {k: (round(b), round(g)) for k, (b, g) in declared.items()}:
        raise SystemExit("publisher corrections found %r differ from those declared %r"
                         % (found, declared))
    for year, key, before, after in applied:
        print("publisher correction FY%d %s: %.0f -> %.0f t" % (year, " / ".join(key),
                                                             before, after))
    with open(ANNUAL_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(a[0].keys()))
        w.writeheader()
        w.writerows(a)
    print("wrote %s (%d rows, %d years)"
          % (os.path.relpath(ANNUAL_OUT, ROOT), len(a),
             len({r["fiscal_year_start"] for r in a})))

    p = provincial_rows()
    covered = {r["month"] for r in p if r["area"] != "PAKISTAN"}
    direct = direct_provincial_rows(covered)
    p = sorted(p + direct, key=lambda r: (r["month"], r["area"], r["sector_row"],
                                          r["product"]))
    print("direct editions supplied %d provincial rows for %d months the cumulative "
          "editions could not serve"
          % (len(direct), len({r["month"] for r in direct})))
    with open(PROV_OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(p[0].keys()))
        w.writeheader()
        w.writerows(p)
    months_with_prov = {r["month"] for r in p if r["area"] != "PAKISTAN"}
    print("wrote %s (%d rows, %d months, %d with provincial pages)"
          % (os.path.relpath(PROV_OUT, ROOT), len(p),
             len({r["month"] for r in p}), len(months_with_prov)))
    return 0


if __name__ == "__main__":
    from pkinv.activity.store import staging_inputs
    with staging_inputs():
        sys.exit(main())
