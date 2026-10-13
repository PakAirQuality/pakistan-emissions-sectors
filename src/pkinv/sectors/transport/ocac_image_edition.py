"""The OCAC Pakistan Oil Report 2015-2016: an image-only edition, identity-gated.

WHY THIS MODULE EXISTS. The FY2015-16 product split was this inventory's last
absent sector-year pair - two NE cells (road transport and industrial combustion)
carried for four releases with their observed totals in the unallocated-controls
ledger and a 16-source search logged negative. The fifteenth review pointed out
that the edition is publicly hosted after all: ocac.org.pk serves the Pakistan
Oil Report 2015-2016 as a 242-page DearFlip flipbook of 602x781-pixel JPEG page
images, and page 50 is the product-by-sector table. The search log's negative
row was about the statistics page, which links only current-year files - the
flipbook pages sat one directory over.

WHY IT IS NOT PARSED LIKE THE OTHER EDITIONS. Every other OCAC annual edition is
a text PDF read by pdftotext through sectors/transport/ocac.py. This edition has
no text layer, and at 602 pixels a general OCR misreads digits freely. The
repository's pattern for that situation is scripts/ocr_ogra_2020_21.py: commit a
transcription and accept it ONLY when the table's own arithmetic closes over it.
This table is unusually rich in closing arithmetic - four independent identity
families - and the transcription in
data/activity/transport/ocac_fy2015_16_transcription.csv is accepted only when
ALL of them hold exactly:

  1. ROW CLOSURE      every row's product cells sum to its printed TOTAL;
  2. BLOCK CLOSURE    member rows sum to their class total per product
                      (Cement+Others = Total Industry, five transport rows =
                      Total Transport, five power rows = Total Power, three
                      government rows = Total Government);
  3. COLUMN CLOSURE   the six class totals sum to TOTAL_INTERNAL per product;
  4. TWO-DOCUMENT     the Road and Total Industry TOTALs equal the FY2016-17
                      edition's independently held prior-year column - the two
                      numbers the unallocated-controls ledger has carried since
                      the twelfth review (12,440,195 and 2,023,377 t).

A transcription edit that corrupts any digit breaks at least one gate and the
load RAISES - the same contract as the OGRA OCR script, with a stronger gate set.

Cells whose printed digits sit below the 602-pixel glyph floor carry
read_basis=identity: their values are the unique solution of the closing system
given the legible cells. Once the gates hold, every committed cell has the same
epistemic status; the basis column records how each was obtained. The FY2014-15
comparison column is deliberately NOT committed (below the glyph floor with a
residual ambiguity, and consumed by nothing).
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows

TRANSCRIPTION = asset_path(DATA, "activity", "transport",
                             "ocac_fy2015_16_transcription.csv")
ANNUAL_CSV = asset_path(DATA, "activity", "transport",
                          "ocac_sectoral_annual.csv")
PAGE_DIR = asset_path(DATA, "raw", "ocac", "oil_report_2015_16")
PAGE_FILE = "Artboard-50.jpg"

FISCAL_YEAR_START = 2015
FY_LABEL = "FY2015-16"
INVENTORY_YEAR = 2016

PRODUCTS = ("100 LL", "HOBC", "MS", "JP-8", "JP-1", "KERO", "HSD", "LDO", "FO")

# member rows -> class total, keyed (section, sector_row) because the table
# reuses row names across sections ("Others" appears under both INDUSTRY and
# GOVERNMENT, "Bunkers" under TRANSPORT and GOVERNMENT)
BLOCKS = {
    ("INDUSTRY", "Total Industry"): (("INDUSTRY", "Cement"),
                                     ("INDUSTRY", "Others")),
    ("TRANSPORT", "Total Transport"): (("TRANSPORT", "Road"),
                                       ("TRANSPORT", "Railways"),
                                       ("TRANSPORT", "Domestic Bunkers"),
                                       ("TRANSPORT", "Domestic Avi-PIA"),
                                       ("TRANSPORT", "Domestic Avi-Others")),
    ("POWER", "Total Power"): (("POWER", "K-Electric"), ("POWER", "PEPCO"),
                               ("POWER", "HUBCO/Hub Narowal"),
                               ("POWER", "Private Power"),
                               ("POWER", "KAPCO (LSFO)")),
    ("GOVERNMENT", "Total Government"): (("GOVERNMENT", "Aviation"),
                                         ("GOVERNMENT", "Bunkers"),
                                         ("GOVERNMENT", "Others")),
}
CLASS_ROWS = (("DOMESTIC", "DOMESTIC"), ("AGRICULTURE", "AGRICULTURE"),
              ("INDUSTRY", "Total Industry"), ("TRANSPORT", "Total Transport"),
              ("POWER", "Total Power"), ("GOVERNMENT", "Total Government"))

READ_BASES = ("glyph", "glyph_identity", "identity")


class TranscriptionError(SystemExit):
    pass


def _rows():
    return read_rows(TRANSCRIPTION)


def load():
    """{(sector_row): {product: tonnes}} for the whole page, gates enforced."""
    table = {}
    for r in _rows():
        if r["read_basis"] not in READ_BASES:
            raise TranscriptionError(
                "ocac 2015-16: unknown read_basis %r on %s/%s"
                % (r["read_basis"], r["sector_row"], r["product"]))
        cell = table.setdefault((r["section"], r["sector_row"]), {})
        if r["product"] in cell:
            raise TranscriptionError(
                "ocac 2015-16: duplicate cell %s/%s"
                % (r["sector_row"], r["product"]))
        cell[r["product"]] = float(r["tonnes"])

    # 1. row closure
    for key, vals in table.items():
        if "TOTAL" not in vals:
            raise TranscriptionError("ocac 2015-16: %s/%s has no TOTAL" % key)
        parts = sum(v for p, v in vals.items() if p != "TOTAL")
        if parts != vals["TOTAL"]:
            raise TranscriptionError(
                "ocac 2015-16 row closure broken: %s/%s sums to %.0f against "
                "its printed TOTAL %.0f" % (key + (parts, vals["TOTAL"])))

    # 2. block closure, per product including TOTAL
    for cls, members in BLOCKS.items():
        for product in PRODUCTS + ("TOTAL",):
            got = sum(table[m].get(product, 0.0) for m in members)
            want = table[cls].get(product, 0.0)
            if got != want:
                raise TranscriptionError(
                    "ocac 2015-16 block closure broken: %s %s members sum to "
                    "%.0f against the class %.0f"
                    % (cls[1], product, got, want))

    # 3. column closure onto TOTAL_INTERNAL
    for product in PRODUCTS + ("TOTAL",):
        got = sum(table[c].get(product, 0.0) for c in CLASS_ROWS)
        want = table[("TOTAL_INTERNAL", "TOTAL_INTERNAL")].get(product, 0.0)
        if got != want:
            raise TranscriptionError(
                "ocac 2015-16 column closure broken: %s classes sum to %.0f "
                "against TOTAL_INTERNAL %.0f" % (product, got, want))

    # 4. two-document gate against the FY2016-17 edition's prior-year column
    prior = {r["sector_row"]: float(r["tonnes"])
             for r in _activity_rows(ANNUAL_CSV, comments=False)
             if r["fiscal_year_start"] == "2016"
             and r["product"] == "TOTAL_PRIOR"
             and r["sector_row"] in ("Road", "Total Industry")}
    section_of_gate = {"Road": "TRANSPORT", "Total Industry": "INDUSTRY"}
    for row in ("Road", "Total Industry"):
        if row not in prior:
            raise TranscriptionError(
                "ocac 2015-16: the FY2016-17 edition's prior-year %s row is "
                "not in %s - the two-document gate cannot run" % (row, ANNUAL_CSV))
        got = table[(section_of_gate[row], row)]["TOTAL"]
        if got != prior[row]:
            raise TranscriptionError(
                "ocac 2015-16 two-document gate broken: %s TOTAL %.0f against "
                "the FY2016-17 edition's prior-year column %.0f"
                % (row, got, prior[row]))
    return table


def _sha256():
    import hashlib
    with open(asset_path(PAGE_DIR, PAGE_FILE), "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def annual_rows(commit_rows):
    """Rows for ocac_sectoral_annual.csv, same schema as the parsed editions."""
    table = load()
    digest = _sha256()
    # commit rows are unique by name within the committed set; resolve each to
    # its (section, row) key and refuse ambiguity
    by_name = {}
    for key in table:
        by_name.setdefault(key[1], []).append(key)
    out = []
    for row in commit_rows:
        keys = by_name.get(row, [])
        if len(keys) != 1:
            raise TranscriptionError(
                "ocac 2015-16: commit row %r resolves to %d table rows"
                % (row, len(keys)))
        section = keys[0][0]
        # printed dashes are zeros: emit the full product set so the schema
        # matches the parsed editions (their rows carry explicit 0.0 cells)
        vals = {p_: table[keys[0]].get(p_, 0.0) for p_ in PRODUCTS + ("TOTAL",)}
        for product, tonnes in sorted(vals.items()):
            out.append({
                "fiscal_year_start": FISCAL_YEAR_START,
                "fy_label": FY_LABEL,
                "inventory_year": INVENTORY_YEAR,
                "section": section,
                "sector_row": row,
                "product": product,
                "tonnes": round(tonnes, 1),
                "source_file": PAGE_FILE,
                "source_sha256": digest,
            })
    return out
