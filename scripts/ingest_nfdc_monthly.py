"""Parse NFDC Table 3.4 - fertiliser offtake by product and month - into a nine-year series.

WHAT THIS BUYS, AND IT IS THE LARGEST REMAINING ITEM. Agriculture's synthetic-nitrogen months
have ridden NFDC's Annex-7 for FY2023-24 ALONE, which is why managed soils reports
`months_observed = 11.1%` while carrying 211 Mt of unobserved mass across the nine-year
product. Table 3.4 publishes the same quantity for FY2012-13 through FY2022-23, so with the
reference year already held every one of the 108 months closes.

The consolidated volume was recorded in this project's own acquisition log as "not located"
for two passes. It was in the maintainer's bundle.

WHAT A ROW IS EVIDENCE OF, unchanged by having nine years of it. Offtake is fertiliser leaving
a DEALER'S DEPOT. It is not fertiliser reaching a field and it is certainly not soil emitting,
so this feeds `timing_target = commodity_offtake` and class TE2 - a monthly administrative
record - and never TE1. Nine years of a depot ledger is nine years of a depot ledger.

TWO CONTROLS THE DOCUMENT SUPPLIES ABOUT ITSELF, both enforced:

  row closure     every row prints its own TOTAL beside its twelve months
  group closure   every product ends with a "TOTAL" source row, which must equal the agency
                  rows above it

The "TOTAL" row is the CONTROL and is never carried as an agency; carrying it would double
every product. That is the same rule `ingest_pbs_minerals.py` arrived at, and this is the
fourth parser in this repository to need it.

THE COLUMN RULE, likewise inherited rather than re-derived: ANCHOR ON THE END. The last
thirteen numeric cells are the twelve months and the printed TOTAL, whatever precedes them.
Cells are split on TWO or more spaces because pdftotext puts a single space inside "105, 992".

THE FISCAL YEAR IS PRINTED TWO WAYS - bare ("2012-13") on the early pages and parenthesised
("(2019-20)") on the later ones - so both are matched. A page whose year cannot be read is
skipped and reported rather than attributed to its neighbour.

Usage:  python3 scripts/ingest_nfdc_monthly.py
Writes: data/activity/monthly/nfdc_month_product_offtake.csv
        outputs/nfdc_monthly_quarantine.csv
        outputs/nfdc_monthly_parse_summary.csv
"""

from pkinv.assets import asset_path
import csv
import os
import re
import subprocess
import sys

from pkinv.paths import ROOT

SOURCE_PDF = asset_path(ROOT, "data", "raw", "nfdc",
                          "nfdc_fertilizer_statistics_2012_13_to_2022_23.pdf")
ACTIVITY_DIR = asset_path(ROOT, "data", "activity", "monthly")
OUT = asset_path(ACTIVITY_DIR, "nfdc_month_product_offtake.csv")
OUTPUTS = asset_path(ROOT, "outputs")
QUARANTINE = asset_path(OUTPUTS, "nfdc_monthly_quarantine.csv")
SUMMARY = asset_path(OUTPUTS, "nfdc_monthly_parse_summary.csv")

MONTHS_IN_YEAR = 12
TRAILING_CELLS = MONTHS_IN_YEAR + 1

# NFDC prints whole tonnes here, so twelve values should hit the printed total exactly. The
# allowance is for rounding in the source, not for a parse that nearly works.
ROW_TOLERANCE = 2.0
GROUP_TOLERANCE = 5.0

TABLE_MARKER = "Offtake by Product and Month"
YEAR = re.compile(r"^\(?((?:19|20)\d{2})-(\d{2})\)?$")
TOTAL_SOURCE = "TOTAL"
# The page's own bottom line, across every product. A THIRD control the document supplies and
# the first version quarantined as unparseable, because "GRAND TOTAL" occupies one cell where
# a product and an agency were expected. It is the strongest of the three: the row controls
# check a row against itself and the group controls check a product against itself, while this
# checks every product on the page against a figure none of them contributed to.
GRAND_TOTAL = "GRAND TOTAL"

# The fiscal years this inventory reports. The table stops at FY2022-23; FY2023-24 comes from
# the Annex-7 file already held, which is why the two are compared at their seam rather than
# assumed continuous.
WINDOW = tuple(range(2015, 2024))

# The nitrogen-bearing products the agriculture module's synthetic-N stream is about. Others
# are parsed and published - the denominator matters - but carry no canonical name.
#
# SSP AND TSP ARE NOT HERE, and were in the first version. Single and triple superphosphate are
# phosphate fertilisers with no nitrogen in them, so a nitrogen flag on them would have carried
# phosphate tonnage into a nitrogen stream. The flag is about what the compound contains, not
# about it being a fertiliser.
NITROGEN_PRODUCTS = ("UREA", "CAN", "AS", "NP", "DAP", "NPK", "NPKS", "MAP")


def _number(cell):
    cleaned = str(cell).replace(",", "").replace(" ", "").strip()
    if cleaned in ("-", "", "—", "None"):
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return None


def _cells(line):
    return [c for c in re.split(r"\s{2,}", line.strip()) if c]


def _trailing_numbers(cells):
    run = []
    for cell in reversed(cells):
        value = _number(cell)
        if value is None:
            break
        run.insert(0, value)
    return run


def _page_text(path, page):
    result = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page),
                             path, "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    return result.stdout.decode("utf-8", "replace")


def _page_count(path):
    result = subprocess.run(["pdfinfo", path], stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL, check=True)
    for line in result.stdout.decode("utf-8", "replace").splitlines():
        if line.startswith("Pages:"):
            return int(line.split()[1])
    raise ValueError("pdfinfo reports no page count for %s" % path)


def months_for(fy_start):
    return (["%04d%02d" % (fy_start, m) for m in range(7, 13)]
            + ["%04d%02d" % (fy_start + 1, m) for m in range(1, 7)])


def table_pages(path):
    """[(page number, fiscal year start)] for every page carrying Table 3.4."""
    out = []
    for page in range(1, _page_count(path) + 1):
        text = _page_text(path, page)
        if TABLE_MARKER not in text:
            continue
        found = None
        for line in text.splitlines():
            match = YEAR.match(line.strip())
            if match:
                found = int(match.group(1))
                break
        out.append((page, found))
    return out


def parse_page(path, page, fy_start):
    """([row dicts], [quarantine dicts], [group dicts]) for one fiscal year's page."""
    months = months_for(fy_start)
    rows, bad, groups, group = [], [], [], []
    grand = None
    for line in _page_text(path, page).splitlines():
        cells = _cells(line)
        if len(cells) < 3:
            continue
        run = _trailing_numbers(cells)
        if len(run) < TRAILING_CELLS:
            continue
        head = cells[:len(cells) - len(run)]
        # THE PRINTED PAGE NUMBER SITS IN THE LEFT MARGIN and pdftotext glues it to the front
        # of whichever row it lines up with - "67   SSP   Agri Tech Limited (PAFL)". That row
        # was booked under product "67", which dropped one agency out of SSP's group in eight
        # of eleven years and was the only reason the group control failed anywhere.
        if head and head[0].strip().isdigit():
            head = head[1:]
        if head and " ".join(head).strip().upper().startswith(GRAND_TOTAL):
            grand = run[-1] if len(run) > MONTHS_IN_YEAR else sum(run[-MONTHS_IN_YEAR:])
            continue
        if len(head) < 2:
            # A row whose product and source cannot both be read is not attributed to
            # whatever preceded it; it is quarantined so the group control stays meaningful.
            bad.append({"fiscal_year_start": fy_start, "product": "", "source_agency": "",
                        "reason": "product and source not separable",
                        "months_sum": round(sum(run[-TRAILING_CELLS:-1]), 2),
                        "annual_printed": round(run[-1], 2),
                        "raw": re.sub(r"\s+", " ", line.strip())})
            continue
        product = head[0].strip().upper()
        agency = " ".join(head[1:]).strip()

        values, printed = run[-TRAILING_CELLS:-1], run[-1]
        if abs(sum(values) - printed) > ROW_TOLERANCE:
            bad.append({"fiscal_year_start": fy_start, "product": product,
                        "source_agency": agency, "reason": "row does not close on its own total",
                        "months_sum": round(sum(values), 2),
                        "annual_printed": round(printed, 2),
                        "raw": re.sub(r"\s+", " ", line.strip())})
            continue

        if agency.strip().upper() == TOTAL_SOURCE:
            declared = sum(r["tonnes"] for r in group if r["product"] == product)
            groups.append({"fiscal_year_start": fy_start, "product": product,
                           "agencies_sum": round(declared, 2),
                           "total_row_printed": round(printed, 2),
                           "closed": abs(declared - printed) <= GROUP_TOLERANCE})
            group = [r for r in group if r["product"] != product]
            continue

        for month, tonnes in zip(months, values):
            row = {"fiscal_year_start": fy_start, "month": month, "product": product,
                   "source_agency": agency, "tonnes": tonnes, "annual_printed": printed,
                   "nitrogen_bearing": "yes" if product in NITROGEN_PRODUCTS else "no",
                   "timing_target": "commodity_offtake", "temporal_method": "T2",
                   "source_file": os.path.basename(path), "source_page": page}
            rows.append(row)
            group.append(row)
    # THE PAGE CONTROL, checked once the page is read. Every product TOTAL must sum to the
    # printed GRAND TOTAL; a product silently dropped would pass both earlier controls and
    # fail only here.
    page_control = None
    if grand is not None:
        # NOT EVERY PRODUCT PRINTS A TOTAL ROW. A product supplied by a single agency - TSP,
        # SOP, MAP, MOP, NPKs, AS on most pages - has nothing to subtotal, so it goes straight
        # into the GRAND TOTAL with no group row of its own. Summing only the group rows
        # therefore came up short on all ten pages by between one and seven per cent, which
        # looked like missing data and was a missing ROW KIND. What is left in `group` after
        # every TOTAL has drained its product is exactly those single-agency products.
        declared = (sum(g["total_row_printed"] for g in groups)
                    + sum(r["tonnes"] for r in group))
        page_control = {"fiscal_year_start": fy_start, "products_sum": round(declared, 2),
                        "grand_total_printed": round(grand, 2),
                        "closed": abs(declared - grand) <= GROUP_TOLERANCE * 4}
    return rows, bad, groups, page_control


def shift_mutation_caught(rows):
    """Series whose twelve months are distinguishable from a rotation of themselves.

    The positive control. A parse that closed every row while reading the same twelve values
    everywhere would report a perfect rate, and a profile built on it would be flat while
    claiming to be observed. Flat series are counted separately rather than hidden.
    """
    series = {}
    for row in rows:
        series.setdefault((row["fiscal_year_start"], row["product"], row["source_agency"]),
                          []).append(row["tonnes"])
    detectable = sum(1 for v in series.values() if v[1:] + v[:1] != v)
    return detectable, len(series) - detectable, len(series)


def main():
    os.makedirs(ACTIVITY_DIR, exist_ok=True)
    os.makedirs(OUTPUTS, exist_ok=True)
    if not os.path.exists(SOURCE_PDF):
        print("NFDC consolidated volume not held at %s" % SOURCE_PDF)
        return 1

    pages = table_pages(SOURCE_PDF)
    unlabelled = [p for p, y in pages if y is None]
    rows, bad, groups, pages_control = [], [], [], []
    for page, fy_start in pages:
        if fy_start is None:
            continue
        parsed, failed, closed, page_control = parse_page(SOURCE_PDF, page, fy_start)
        rows += parsed
        bad += failed
        groups += closed
        if page_control is not None:
            pages_control.append(page_control)

    if not rows:
        print("Table 3.4 found on %d pages but no row parsed" % len(pages))
        return 1

    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write("# NFDC monthly fertiliser OFFTAKE by product and supplying agency, "
                     "from Table 3.4 of the consolidated volume.\n")
        handle.write("# OFFTAKE TIMES THE DEPOT, NOT THE SOIL: this records fertiliser "
                     "leaving a dealer, not nitrogen reaching a field and not\n")
        handle.write("# a soil emitting. Every row carries timing_target=commodity_offtake "
                     "and class T2 for that reason.\n")
        handle.write("# The per-product 'TOTAL' row is the group control and is NOT carried "
                     "as an agency.\n")
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    if bad:
        with open(QUARANTINE, "w", newline="", encoding="utf-8") as handle:
            handle.write("# Rows that did not close on the total the SAME ROW prints, or "
                         "whose product and agency could not be separated.\n")
            handle.write("# Kept with raw text, never repaired.\n")
            writer = csv.DictWriter(handle, fieldnames=list(bad[0]))
            writer.writeheader()
            writer.writerows(bad)

    held = sorted({r["fiscal_year_start"] for r in rows})
    in_window = [y for y in held if y in WINDOW]
    detectable, flat, series = shift_mutation_caught(rows)
    summary = [{
        "table_pages": len(pages),
        "pages_without_a_readable_year": len(unlabelled),
        "fiscal_years_parsed": len(held),
        "fiscal_years_in_window": len(in_window),
        "window_years_from_this_table": ";".join("FY%d-%02d" % (y, (y + 1) % 100)
                                                 for y in in_window),
        "window_years_from_elsewhere": ";".join(
            "FY%d-%02d" % (y, (y + 1) % 100) for y in WINDOW if y not in in_window) or "none",
        "month_rows": len(rows),
        "rows_quarantined": len(bad),
        "product_years": len(groups),
        "product_years_closing_group_control": sum(1 for g in groups if g["closed"]),
        "pages_with_a_grand_total": len(pages_control),
        "pages_closing_the_grand_total": sum(1 for c in pages_control if c["closed"]),
        "rotation_detectable_series": detectable,
        "rotation_flat_series": flat,
        "series_total": series,
    }]
    with open(SUMMARY, "w", newline="", encoding="utf-8") as handle:
        handle.write("# THE NFDC PARSE'S OWN ACCOUNTING, one row. "
                     "window_years_from_elsewhere is a declared literal: the table stops at\n")
        handle.write("# FY2022-23 and the reference year comes from the Annex-7 file already "
                     "held, which is a seam and not a silence.\n")
        writer = csv.DictWriter(handle, fieldnames=list(summary[0]))
        writer.writeheader()
        writer.writerows(summary)

    open_groups = [g for g in groups if not g["closed"]]
    print("NFDC monthly offtake -> %s" % os.path.relpath(OUT, ROOT))
    print("  Table 3.4 on %d pages, %d without a readable year" % (len(pages), len(unlabelled)))
    print("  %d fiscal years parsed, %d of them in the 108-month window"
          % (len(held), len(in_window)))
    print("  %d month rows, %d quarantined" % (len(rows), len(bad)))
    print("  group control: %d of %d product-years close on their own TOTAL row"
          % (len(groups) - len(open_groups), len(groups)))
    for group in open_groups[:8]:
        print("    FY%s %-10s agencies %.0f vs TOTAL row %.0f"
              % (group["fiscal_year_start"], group["product"][:10],
                 group["agencies_sum"], group["total_row_printed"]))
    open_pages = [c for c in pages_control if not c["closed"]]
    print("  page control:  %d of %d pages close on their own GRAND TOTAL"
          % (len(pages_control) - len(open_pages), len(pages_control)))
    for control in open_pages[:6]:
        print("    FY%s products %.0f vs GRAND TOTAL %.0f"
              % (control["fiscal_year_start"], control["products_sum"],
                 control["grand_total_printed"]))
    print("  rotation control: %d of %d series distinguishable from their own rotation (%d flat)"
          % (detectable, series, flat))
    print("  window years from this table: %s" % summary[0]["window_years_from_this_table"])
    print("  window years from elsewhere:  %s" % summary[0]["window_years_from_elsewhere"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
