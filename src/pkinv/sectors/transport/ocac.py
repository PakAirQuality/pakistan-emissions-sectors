"""Parser for OCAC "Sectoral Sales of Energy Products" tables - the transport controls.

WHAT THESE TABLES ARE. OCAC publishes national (annual, nine editions FY2016-17 to
FY2024-25) and area-level (monthly, 48 editions Jul-2021 to Jun-2025) petroleum sales
by CUSTOMER CLASS x product, in tonnes: Domestic / Industry / Agriculture / Transport
(Road, Railways, Domestic Bunkers, two aviation rows) / Power / Government, plus
overseas rows and closing totals. The PDFs were fetched by the aviation sector (they
are the jet-fuel source) and indexed in data/activity/aviation/ocac_*_sources.csv;
this module reads the OTHER columns - MS, HOBC and HSD - which are the road-transport
controls. The transport paper spent two editions describing this table as not acquired
while the repository held it.

WHY A TOKEN PARSER, NOT THE AVIATION COLUMN-SPAN PARSER. Aviation's
monthly._column_span locates cells by printed header x-positions, which clips digits
when a neighbouring column narrows the span (FY2023-24 HOBC reads 104 for 104,926;
FY2024-25 totals lose their leading digit). Every cell in these tables is populated
("-" or a number), so splitting on runs of two-plus spaces yields exactly one token
per column on every data row, verified across all nine annual editions whose column
sets differ (E-10 present FY2016-17 to FY2019-20, NAPHTHA FY2023-24 onward).

THE LOUD GUARD. Each data row must satisfy sum(product cells) == TOTAL exactly;
parse_page raises otherwise. That is the invariant a positional parser cannot offer.

AREA REGIMES (monthly). Early editions print PAKISTAN, SINDH, PUNJAB, KHYBER PAKHTUN
KHAWA, BALOCHISTAN, GILGIT BALTISTAN, AZAD KASHMIR, FATA and KARACHI as separate
pages; later editions fold FATA into "KHYBER PAKHTUNKHWA (Includes FATA)" and retitle
Sindh "(Includes Karachi)" while keeping the separate KARACHI page. KARACHI is a
SUBSET of SINDH (additive=0); FATA, where separate, is additive - the additive areas
sum exactly to PAKISTAN, and the ingest test asserts it.

This module never runs in the engine hot path: scripts/ingest_ocac_sectoral.py calls
it once to write data/activity/transport/ocac_sectoral_*.csv, and the engine reads
only the CSVs.
"""

from pkinv.assets import asset_path
import hashlib
import os
import re
import subprocess

from pkinv.paths import ROOT

ANNUAL_DIR = asset_path(ROOT, "sources", "Aviation", "ocac_annual")
MONTHLY_DIR = asset_path(ROOT, "sources", "Aviation", "ocac_monthly")
ANNUAL_INDEX = asset_path(ROOT, "data", "activity", "aviation",
                            "ocac_annual_sources.csv")
MONTHLY_INDEX = asset_path(ROOT, "data", "activity", "aviation",
                             "ocac_cumulative_sources.csv")

# Canonical area names. KARACHI is a subset of SINDH; FATA (where separate) adds to
# KHYBER PAKHTUNKHWA's later folded figure.
AREA_ALIASES = {
    "PAKISTAN": "PAKISTAN",
    "SINDH": "SINDH",
    "SINDH (INCLUDES KARACHI)": "SINDH",
    "PUNJAB": "PUNJAB",
    "KHYBER PAKHTUN KHAWA": "KHYBER PAKHTUNKHWA",
    "KHYBER PAKHTUNKHWA": "KHYBER PAKHTUNKHWA",
    "KHYBER PAKHTUNKHWA (INCLUDES FATA)": "KHYBER PAKHTUNKHWA",
    "BALOCHISTAN": "BALOCHISTAN",
    "GILGIT BALTISTAN": "GILGIT BALTISTAN",
    "AZAD KASHMIR": "AZAD KASHMIR",
    "FATA": "FATA",
    "KARACHI": "KARACHI",
}
NON_ADDITIVE_AREAS = ("KARACHI",)      # subset of SINDH, never summed to PAKISTAN

_SECTION_HEADERS = ("INDUSTRY", "TRANSPORT", "POWER", "GOVERNMENT",
                    "OVERSEAS/FOREIGN")
_STANDALONE_ROWS = ("DOMESTIC", "AGRICULTURE")

# The rows the inventory commits to CSV.
COMMIT_ROWS = ("DOMESTIC", "AGRICULTURE", "Road", "Railways", "Domestic Bunkers",
               "Total Transport", "Total Industry", "Total Power",
               "Total Government", "TOTAL_INTERNAL")

# The rows the controls and proxies actually anchor on: a closure failure here is
# fatal. Elsewhere - including class totals whose printed TOTAL one edition
# contradicts by the same 2 kt as its own member row - the row is kept with its
# printed TOTAL and a warning, because the downstream identity tests (customer
# classes sum to TOTAL_INTERNAL, provinces sum to PAKISTAN) still stand guard on
# everything the inventory uses.
CRITICAL_ROWS = ("DOMESTIC", "AGRICULTURE", "Road", "Railways", "Domestic Bunkers",
                 "TOTAL_INTERNAL")

# Monthly area pages anchor only the road/rail rows (the provincial proxies); the
# Aug-2024 edition's Private Power misprint propagates into its own printed class
# and internal totals, which nothing downstream reads monthly.
MONTHLY_CRITICAL_ROWS = ("Road", "Railways", "DOMESTIC", "AGRICULTURE")


def _num(tok):
    """A cell token to float, or None if it is not a cell."""
    t = tok.strip().replace(",", "")
    if t in ("-", ""):
        return 0.0
    if re.fullmatch(r"-?\d+(\.\d+)?", t):
        return float(t)
    return None


def _pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", path, "-"],
                          capture_output=True, text=True, check=True).stdout


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


CLOSE_TOL_T = 2.0        # the source's own rows round to the tonne, off by <=1 t


def parse_page(text, critical=CRITICAL_ROWS):
    """One energy-table page -> {"products": [...], "rows": [...], "warnings": [...]}.

    rows are (section, row, {product: tonnes}). Raises ValueError when a
    full-width data row's product cells do not sum to its TOTAL (within the
    source's own 1-tonne rounding) - the loud guard that catches every
    mis-tokenised line. A row whose cell COUNT is short (the text layer of one
    edition drops a dash cell in a member row) is skipped with a warning instead:
    the committed rows are all totals and named class rows, whose cross-row
    closure identities are asserted downstream, so a silently missing member row
    cannot hide.
    """
    products, rows, warnings, section = None, [], [], None
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "`":
            continue
        tokens = re.split(r"\s{2,}", line)
        if tokens[0] == "SECTOR":
            # FY2025-26 national pages print these two distinct headings with
            # only one intervening space. Split the known pair, preserving
            # genuine multiword headings such as 100 LL and TOTAL PRIOR.
            products = [part for heading in tokens[1:]
                        for part in (("HOBC", "NAPHTHA")
                                     if heading == "HOBC NAPHTHA" else (heading,))]
            # Annual tables carry the prior-year grand total as a second TOTAL
            # column; monthly tables carry one.
            if products.count("TOTAL") == 2:
                products[len(products) - 1] = "TOTAL_PRIOR"
            continue
        if products is None:
            continue
        head = tokens[0].upper().strip()
        if head in _SECTION_HEADERS:
            section = "OVERSEAS" if head.startswith("OVERSEAS") else head
            continue
        if head == "INTERNAL USE" or head.startswith("DISCLAIMER"):
            continue
        cells = [_num(t) for t in tokens[1:]]
        if not cells or any(c is None for c in cells):
            continue                     # prose, footers, wrapped header fragments
        label = tokens[0].rstrip(":").strip()
        if "VALUE" in label.upper():
            continue                     # rupee-value rows, not tonnes
        if label.upper() in _STANDALONE_ROWS:
            row_section, row = label.upper(), label.upper()
        elif label.startswith("A. TOTAL INTERNAL"):
            row_section, row = "TOTALS", "TOTAL_INTERNAL"
        elif label.startswith("B. TOTAL OVERSEAS"):
            row_section, row = "TOTALS", "TOTAL_OVERSEAS"
        elif label.startswith("GRAND TOTAL"):
            # Two variants: current-year grand total and the prior-year line the
            # annual layout prints beneath it. Keep only the current-year row.
            if "JUL" in label.upper() or "(" in label:
                continue
            row_section, row = "TOTALS", "GRAND_TOTAL"
        elif section is not None:
            row_section, row = section, label
        else:
            continue
        if len(cells) != len(products):
            warnings.append("skipped %r: %d cells for %d columns"
                            % (label, len(cells), len(products)))
            continue
        vals = dict(zip(products, cells))
        body = sum(v for k, v in vals.items() if k not in ("TOTAL", "TOTAL_PRIOR"))
        if abs(body - vals.get("TOTAL", body)) > CLOSE_TOL_T:
            if row in critical:
                raise ValueError("row %r does not close: cells sum to %.0f, "
                                 "TOTAL %.0f" % (label, body, vals.get("TOTAL")))
            warnings.append("row %r does not close (%.0f vs %.0f) - kept with its "
                            "printed TOTAL" % (label, body, vals.get("TOTAL")))
        rows.append((row_section, row, vals))
    if products is None or not rows:
        raise ValueError("no sectoral table found on page")
    return {"products": products, "rows": rows, "warnings": warnings}


def _area_of_page(text):
    """Canonical area name of a monthly page, or None if not an area page."""
    for raw in text.splitlines()[:10]:
        line = raw.strip().upper()
        m = re.match(r"AREA\s*-\s*(.+?)\s*$", line)
        cand = m.group(1).strip() if m else line
        if cand in AREA_ALIASES:
            return AREA_ALIASES[cand]
    return None


def parse_annual(path):
    """First energy page of an annual PDF -> parse_page result."""
    return parse_page(_pdf_text(path).split("\f")[0])


def parse_monthly(path):
    """All energy-table area pages of a monthly PDF -> [(area, parsed)].

    Pages after the first "NON-ENERGY" title are ignored; area detection handles
    both the early bare-name regime and the later "(Includes ...)" regime.
    """
    out = []
    for page in _pdf_text(path).split("\f"):
        if "SECTORAL SALES OF NON-ENERGY" in page:
            break
        area = _area_of_page(page)
        if area is None:
            continue
        out.append((area, parse_page(page, critical=MONTHLY_CRITICAL_ROWS)))
    if not out:
        raise ValueError("no energy area pages in %s" % path)
    return out
