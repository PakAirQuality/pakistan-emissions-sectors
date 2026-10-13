"""The NFDC false gap, closed: FY2023-24's own twelve offtake months from Annex-5.

THE GAP WAS NEVER REAL. The reference year's fertiliser nitrogen rode NFDC's Annex-7
April-to-March fertiliser year, so April, May and June 2024 were borrowed from 2023 and
graded T3 - and the repository's own copy of the Annual Fertilizer Review 2023-24 has
carried all twelve July-to-June months the whole time, in Annex-5 (month x product x
supplying agency, national). The sixteenth review pointed at the page. This ingest reads
it into the SAME panel Table 3.4 already fills for FY2012-13..FY2022-23
(data/activity/monthly/nfdc_month_product_offtake.csv), after which
sectors/agriculture/nfdc_monthly.covers(2023) is true and the borrowed-months branch is
never taken for the reference year - zero code change in the consumer, the same pattern
as the power panel's second lane.

THE PAGE PROVES ITSELF THREE WAYS before a row is written:
  * every (product, agency) row's twelve months meet the row's own printed TOTAL;
  * every product's printed TOTAL row equals the sum of its agency rows, per month;
  * the printed GRAND TOTAL row equals the sum of product totals, per month.
And once written, a FOURTH, cross-document check runs in the tests: the held Annex-7
transcription (province x month) rolls up to Annex-5's national months where the two
overlap - two independently printed tables of one ledger.

OFFTAKE STILL TIMES THE DEPOT. The grade is T2 and the timing target commodity_offtake,
exactly as the eight Table 3.4 years: twelve own months make the year observed; they do
not move the record any closer to when a soil emitted.

Usage:  python3 scripts/ingest_nfdc_annex5.py [--dry-run]
Writes: data/activity/monthly/nfdc_month_product_offtake.csv (FY2023-24 lane;
        Table 3.4 rows preserved)
"""

from pkinv.assets import asset_path
import argparse
import csv
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF = asset_path(ROOT, "data", "raw", "nfdc",
                   "nfdc_annual_fertilizer_review_2023_24.pdf")
PAGE = 91                     # "PAGE 2 OF ANNEX-5 ... (2023-24)"
FY_START = 2023
OUT = asset_path(ROOT, "data", "activity", "monthly",
                   "nfdc_month_product_offtake.csv")

FIELDS = ("fiscal_year_start", "month", "product", "source_agency", "tonnes",
          "annual_printed", "nitrogen_bearing", "timing_target", "temporal_method",
          "source_file", "source_page")

# The panel's closed product vocabulary and its nitrogen flags (mirrored from the
# Table 3.4 lane; NPKs/NPks normalise to NPKS). An unknown product is an error.
NITROGEN = {"UREA": "yes", "CAN": "yes", "DAP": "yes", "MAP": "yes", "MOP": "no",
            "NP": "yes", "NPKS": "yes", "SOP": "no", "SSP": "no", "TSP": "no",
            "AS": "yes"}
PRODUCT_ALIASES = {"NPKs": "NPKS", "NPks": "NPKS"}

MONTHS = ["%04d%02d" % (FY_START if m >= 7 else FY_START + 1, m)
          for m in list(range(7, 13)) + list(range(1, 7))]
NUMBER = re.compile(r"^-?[\d,]+$")


def _tokens(line):
    return line.split()


def _value(token):
    if token == "-":
        return 0.0                     # a printed dash is the source stating nil
    return float(token.replace(",", ""))


def parse_page():
    if not shutil.which("pdftotext"):
        raise SystemExit("pdftotext is not installed")
    out = subprocess.run(["pdftotext", "-layout", "-f", str(PAGE), "-l", str(PAGE),
                          PDF, "-"], check=True, stdout=subprocess.PIPE)
    text = out.stdout.decode("utf-8", "replace")
    rows, grand = [], None
    for line in text.splitlines():
        tokens = _tokens(line)
        if not tokens:
            continue
        # the printed page number can be set hard against the first column
        if tokens[0].isdigit() and len(tokens) > 1 and (
                tokens[1] in NITROGEN or tokens[1] in PRODUCT_ALIASES):
            tokens = tokens[1:]
        if tokens[0] == "GRAND" and len(tokens) >= 15 and tokens[1] == "TOTAL":
            grand = [_value(t) for t in tokens[2:15]]
            continue
        head = PRODUCT_ALIASES.get(tokens[0], tokens[0])
        if head not in NITROGEN:
            continue
        # the last 13 numeric-or-dash tokens are Jul..Jun + TOTAL; the agency name is
        # whatever sits between the product code and them
        tail = tokens[1:]
        numbers = []
        while tail and (NUMBER.match(tail[-1]) or tail[-1] == "-"):
            numbers.insert(0, tail.pop())
        if len(numbers) < 13:
            continue                   # a wrapped heading, not a data row
        if len(numbers) > 13:
            # an agency name ending in a number would land here; none does today, and
            # silence would misassign a month, so this raises
            raise SystemExit("row %r carries %d numeric tokens; expected 13"
                             % (line.strip()[:60], len(numbers)))
        agency = " ".join(tail)
        values = [_value(t) for t in numbers]
        rows.append({"product": head, "agency": agency,
                     "months": values[:12], "printed_total": values[12]})
    if grand is None:
        raise SystemExit("no GRAND TOTAL row on page %d; the layout has changed" % PAGE)
    return rows, grand


def prove(rows, grand):
    """The three identities, each a hard failure."""
    for row in rows:
        delta = sum(row["months"]) - row["printed_total"]
        # NFDC's printed columns disagree with their own sums by a tonne or two on
        # hundreds of thousands (the Table 3.4 lane measured the same property when
        # two transcriptions differed by two tonnes on four hundred thousand); five
        # tonnes is far below any transcription error a shifted cell would produce.
        if abs(delta) > 5.0:
            raise SystemExit("%s / %s: months sum %.0f vs printed %.0f"
                             % (row["product"], row["agency"], sum(row["months"]),
                                row["printed_total"]))
    products = {}
    for row in rows:
        products.setdefault(row["product"], []).append(row)
    for product, group in products.items():
        totals = [r for r in group if r["agency"] == "TOTAL"]
        agencies = [r for r in group if r["agency"] != "TOTAL"]
        if totals:
            for index in range(13):
                printed = (totals[0]["months"] + [totals[0]["printed_total"]])[index]
                summed = sum((r["months"] + [r["printed_total"]])[index]
                             for r in agencies)
                if abs(printed - summed) > 1.0:
                    raise SystemExit("%s TOTAL disagrees with its agencies in column %d:"
                                     " %.0f vs %.0f" % (product, index, printed, summed))
    for index in range(13):
        month_grand = grand[index]
        summed = 0.0
        for product, group in products.items():
            totals = [r for r in group if r["agency"] == "TOTAL"]
            source = totals[0] if totals else group[0]
            summed += (source["months"] + [source["printed_total"]])[index]
        if abs(month_grand - summed) > 2.0:
            raise SystemExit("GRAND TOTAL column %d: printed %.0f vs product sum %.0f"
                             % (index, month_grand, summed))


def build():
    rows, grand = parse_page()
    prove(rows, grand)
    out = []
    for row in rows:
        if row["agency"] == "TOTAL":
            continue                   # the group control, not an agency - panel rule
        for index, month in enumerate(MONTHS):
            out.append({
                "fiscal_year_start": FY_START, "month": month,
                "product": row["product"], "source_agency": row["agency"],
                "tonnes": row["months"][index],
                "annual_printed": row["printed_total"],
                "nitrogen_bearing": NITROGEN[row["product"]],
                "timing_target": "commodity_offtake", "temporal_method": "T2",
                "source_file": os.path.basename(PDF), "source_page": PAGE,
            })
    return out, rows, grand


def main(argv=None):
    parser = argparse.ArgumentParser(description="Ingest NFDC Annex-5 FY2023-24.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    out, rows, grand = build()
    urea = sum(r["tonnes"] for r in out if r["product"] == "UREA")
    print("NFDC AFR 2023-24 Annex-5 (page %d) -> FY2023-24 month x product x agency"
          % PAGE)
    print("  %d agency rows over %d products; grand total %.0f t; urea %.0f t"
          % (len({(r['product'], r['source_agency']) for r in out}),
             len({r['product'] for r in out}), grand[12], urea))
    if args.dry_run:
        print("--dry-run: nothing written.")
        return 0

    with open(OUT, newline="", encoding="utf-8") as handle:
        comments = [l for l in open(OUT) if l.startswith("#")]
        preserved = [r for r in csv.DictReader(l for l in open(OUT)
                                               if not l.startswith("#"))
                     if r["fiscal_year_start"] != str(FY_START)]
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.writelines(comments)
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(preserved)
        writer.writerows(out)
    print("wrote %s (+%d FY2023-24 rows)" % (os.path.relpath(OUT, ROOT), len(out)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
