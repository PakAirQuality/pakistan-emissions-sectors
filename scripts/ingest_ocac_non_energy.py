"""Ingest OCAC's "SECTORAL SALES OF NON-ENERGY PRODUCTS" page from every held annual edition.

Activity basis for IPCC 2.D (non-energy products from fuels and solvent use: 2.D.1
lubricants, 2.D.2 paraffin wax, 2.D.3 solvents / asphalt / other). The page reports
SALES (deliveries) of ASPHALT, JBO, MTT, SOLVENT, CARBON OIL, PROCESS OIL, BTX, LUBES
and GREASES by consuming sector, in metric tonnes ("UNIT: M. Tons" on every edition),
for one fiscal year, with a previous-year TOTAL column beside the current-year TOTAL
and a previous-year GRAND TOTAL row beneath the table.

Inputs (all held; nothing is downloaded - run `python3 scripts/holdings.py OCAC` first):
  data/raw/ocac/annual_controls/ocac_annual_*.pdf        (8 editions, FY2016-17 .. FY2023-24)
  sources/Aviation/ocac_annual/OCAC_FY2024_25.pdf         (9th edition; sources/ is FROZEN, read only)

Output:
  data/activity/industry/ocac_non_energy_sectoral.csv     one row per printed CELL

Method: `pdftotext -layout`, page located by its title after stripping control bytes
(pdftotext renders the "ti" ligature as \\x19 in some Pakistani PDFs); the header is
detected per page and every value is mapped to a column by its character position
against the header spans, never by a fixed index (the header set is recorded as printed
and may drift between editions). A printed "-" is an ABSENCE: the quantity cell is left
empty, never written as 0.

Closure (status column):
  verified        the row's current-year TOTAL equals the sum of its product cells within
                  1 t AND, for "Total X" / A. / B. / GRAND TOTAL rows, each column equals
                  the sum of its component rows within 1 t. Previous-year cells are
                  verified against the earlier edition's own current-year figure.
  restated        a previous-year cell that differs from the earlier edition's figure
                  (both values in the note).
  closure-failed  a closure residual larger than 1 t (residual in closure_residual).
  unchecked       a previous-year cell with no earlier edition held to check against
                  (FY2015-16, carried only by the 2016-17 edition), or whose row label
                  has no counterpart in the earlier edition.
  unidentified    a printed value whose meaning the page does not state (one cell).

Usage:  python3 scripts/ingest_ocac_non_energy.py
Prints a per-edition summary (fiscal years captured, grand total per product, closure
failures) and writes the CSV. Deterministic: two runs produce identical files.
"""

from pkinv.assets import asset_path
import csv
import os
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EDITIONS = [
    "data/raw/ocac/annual_controls/ocac_annual_2016_17.pdf",
    "data/raw/ocac/annual_controls/ocac_annual_2017_18.pdf",
    "data/raw/ocac/annual_controls/ocac_annual_2018_19.pdf",
    "data/raw/ocac/annual_controls/ocac_annual_2019_20.pdf",
    "data/raw/ocac/annual_controls/ocac_annual_fy2020_21.pdf",
    "data/raw/ocac/annual_controls/ocac_annual_fy2021_22.pdf",
    "data/raw/ocac/annual_controls/ocac_annual_fy2022_23.pdf",
    "data/raw/ocac/annual_controls/ocac_annual_fy2023_24.pdf",
    "sources/Aviation/ocac_annual/OCAC_FY2024_25.pdf",
]

OUT = asset_path(ROOT, "data", "activity", "industry", "ocac_non_energy_sectoral.csv")

COLUMNS = ["fiscal_year", "section", "sector_row", "product", "quantity",
           "unit_as_printed", "edition_file", "status", "closure_residual", "note"]

# Header tokens that are printed as two words; pdftotext -layout can run adjacent
# two-word headers together with a single space ("CARBON OIL PROCESS OIL").
MULTIWORD_HEADERS = {"CARBON OIL", "PROCESS OIL"}

TOLERANCE = 1  # tonnes


# ----------------------------------------------------------------------------- text

def _clean(line):
    """Strip control bytes (the \\x19 ligature artefact) and stray backticks, keeping
    column positions where possible (backtick -> space)."""
    line = re.sub(r"[\x00-\x08\x0b-\x1f]", "", line)
    return line.replace("`", " ").rstrip("\n")


def _squash(text):
    return re.sub(r"[\s\x00-\x1f]", "", text).upper()


def pdftotext_pages(pdf_path):
    out = subprocess.run(["pdftotext", "-layout", pdf_path, "-"],
                         check=True, capture_output=True)
    text = out.stdout.decode("utf-8", errors="replace")
    return text.split("\f")


def locate_page(pages):
    hits = [p for p in pages if "NON-ENERGYPRODUCTS" in _squash(p) or "NONENERGYPRODUCTS" in _squash(p)]
    if len(hits) != 1:
        raise SystemExit("expected exactly one NON-ENERGY PRODUCTS page, found %d" % len(hits))
    return hits[0]


def fiscal_year_from_text(text):
    """'JULY 2016 - JUNE 2017', 'JULY - JUNE 2017-18', 'JULY ~ JUNE 2019-2020',
    'JUL~JUN 2015-16', 'JUL 21 - JUN 22'  ->  '2016-17' style label, or None."""
    t = text.upper()
    m = re.search(r"JULY?\s*(\d{4})\s*[-~]\s*JUNE?\s*(\d{4})", t)
    if m:
        return "%s-%s" % (m.group(1), m.group(2)[2:])
    m = re.search(r"(\d{4})\s*[-~]\s*(\d{4})", t)
    if m:
        return "%s-%s" % (m.group(1), m.group(2)[2:])
    m = re.search(r"(\d{4})\s*[-~]\s*(\d{2})\b", t)
    if m:
        return "%s-%s" % (m.group(1), m.group(2))
    m = re.search(r"JUL\s*(\d{2})\s*[-~]\s*JUN\s*(\d{2})\b", t)
    if m:
        return "20%s-%s" % (m.group(1), m.group(2))
    return None


def previous_fy(label):
    start = int(label[:4])
    return "%d-%02d" % (start - 1, start % 100)


# --------------------------------------------------------------------------- header

class Column:
    def __init__(self, name, start, end):
        self.name = name
        self.start = start
        self.end = end
        self.fy_label = None  # only the TOTAL columns carry a sub-header year

    @property
    def center(self):
        return (self.start + self.end) / 2.0

    def __repr__(self):
        return "Column(%r,%d-%d,%r)" % (self.name, self.start, self.end, self.fy_label)


def parse_header(line):
    """Header spans by character position. Adjacent two-word headers run together by
    -layout are split on the known multi-word vocabulary; anything else is recorded
    exactly as printed."""
    cols = []
    for m in re.finditer(r"\S+(?: \S+)*", line):
        words = m.group(0).split(" ")
        pos = m.start()
        i = 0
        while i < len(words):
            pair = " ".join(words[i:i + 2]).upper()
            if pair in MULTIWORD_HEADERS:
                name, n = pair, 2
            else:
                name, n = words[i].upper(), 1
            # locate this token's own span inside the line
            seg = " ".join(words[i:i + n])
            start = line.index(seg, pos)
            end = start + len(seg)
            cols.append(Column(name, start, end))
            pos = end
            i += n
    if not cols or cols[0].name != "SECTOR":
        raise SystemExit("header does not start with SECTOR: %r" % line)
    return cols[1:]  # drop the SECTOR label column


def nearest(cols, start, end):
    center = (start + end) / 2.0
    return min(cols, key=lambda c: abs(c.center - center))


# ----------------------------------------------------------------------------- rows

VALUE_TOKEN = re.compile(r"^(-|\d{1,3}(?:,\d{3})*|\d+)$")


def tokenize(line, boundary):
    """Split a body line into (label, [(token, start, end), ...]). Value tokens are
    numbers or a dash; any other token right of the label boundary is label spill."""
    label = line[:boundary].strip()
    values = []
    for m in re.finditer(r"\S+", line[boundary:]):
        tok = m.group(0)
        if VALUE_TOKEN.match(tok):
            values.append((tok, boundary + m.start(), boundary + m.end()))
        else:
            label = (label + " " + tok).strip()
    return label, values


def column_anchors(token_rows, n_cols):
    """Right-edge anchor per column ordinal, from the page's own full rows.

    -layout right-aligns every value under its header but the header spans themselves
    drift (adjacent two-word headers are run together), so header centres cannot place
    values. Every full row prints one token per column ("-" for an absence), so the
    median right edge of the k-th token over full rows anchors column k; sparse rows
    (the previous-year GRAND TOTAL row) are then mapped to the nearest anchor."""
    full = [vals for vals in token_rows if len(vals) == n_cols]
    if len(full) < 3:
        raise SystemExit("fewer than 3 full rows to anchor %d columns" % n_cols)
    anchors = []
    for k in range(n_cols):
        ends = sorted(v[k][2] for v in full)
        anchors.append(ends[len(ends) // 2])
    gaps = [b - a for a, b in zip(anchors, anchors[1:])]
    if min(gaps) < 6:
        raise SystemExit("column anchors too close to separate: %r" % anchors)
    return anchors


def assign(values, anchors):
    """{column index: int|None} by nearest right-edge anchor; a collision is an error."""
    cells = {}
    for tok, _s, e in values:
        idx = min(range(len(anchors)), key=lambda k: abs(anchors[k] - e))
        if abs(anchors[idx] - e) > 8:
            raise SystemExit("token %r at %d is %d chars from the nearest column anchor"
                             % (tok, e, abs(anchors[idx] - e)))
        if idx in cells:
            raise SystemExit("two tokens mapped to column %d (%r)" % (idx, tok))
        cells[idx] = None if tok == "-" else int(tok.replace(",", ""))
    return cells


class Row:
    def __init__(self, section, label, cells, kind):
        self.section = section
        self.label = label
        self.cells = cells            # index -> int|None
        self.kind = kind              # 'row' | 'subtotal' | 'total_a' | 'total_b' | 'grand' | 'prior'
        self.components = []          # rows this total should equal
        self.row_residual = None
        self.col_residuals = {}       # index -> residual
        self.fails = []

    def value(self, idx):
        return self.cells.get(idx)


def parse_page(page, edition_rel):
    lines = [_clean(l) for l in page.splitlines()]
    # title year
    title_fy = None
    for l in lines[:6]:
        title_fy = title_fy or fiscal_year_from_text(l)
    unit = None
    for l in lines:
        m = re.search(r"UNIT\s*:\s*(.+?)\s*$", l, re.I)
        if m:
            unit = m.group(1).strip()
            break
    if unit is None:
        raise SystemExit("%s: no UNIT statement found on the page" % edition_rel)

    # header + sub-header
    h_idx = next(i for i, l in enumerate(lines) if re.search(r"\bSECTOR\b", l) and "TOTAL" in l)
    cols = parse_header(lines[h_idx])
    sub_idx = next(i for i in range(h_idx + 1, len(lines)) if lines[i].strip())
    totals = [c for c in cols if c.name == "TOTAL"]
    for m in re.finditer(r"\S+(?: \S+)*", lines[sub_idx]):
        fy = fiscal_year_from_text(m.group(0))
        if fy:
            nearest(totals, m.start(), m.end()).fy_label = fy
    if not totals or totals[0].fy_label is None:
        raise SystemExit("%s: could not read the fiscal year under the TOTAL column" % edition_rel)
    current_fy = totals[0].fy_label
    if title_fy and title_fy != current_fy:
        raise SystemExit("%s: title year %s != TOTAL column year %s" % (edition_rel, title_fy, current_fy))
    if len(totals) > 1 and totals[1].fy_label != previous_fy(current_fy):
        raise SystemExit("%s: second TOTAL column is labelled %s, expected %s"
                         % (edition_rel, totals[1].fy_label, previous_fy(current_fy)))
    if len(totals) > 2:
        raise SystemExit("%s: more than two TOTAL columns" % edition_rel)
    cur_total_idx = cols.index(totals[0])
    prior_total_idx = cols.index(totals[1]) if len(totals) > 1 else None
    product_idx = [i for i, c in enumerate(cols) if c.name != "TOTAL"]

    # body: tokenize every line first, anchor the columns on the page's own full rows,
    # then classify
    boundary = max(0, cols[0].start - 8)
    body = []
    for l in lines[sub_idx + 1:]:
        if not l.strip():
            continue
        if l.strip().upper().startswith("DISCLAIMER"):
            break
        label, values = tokenize(l, boundary)
        if label:
            body.append((label, values, len(l) - len(l.lstrip())))
    anchors = column_anchors([v for _l, v, _i in body if v], len(cols))
    header_order = [c.start for c in cols]
    if header_order != sorted(header_order):
        raise SystemExit("%s: header spans are not left-to-right" % edition_rel)

    rows = []
    skipped_value_rows = 0
    footnotes = []
    section = None
    for label, values, indent in body:
        up = label.upper()
        if "VALUE" in up and "RS" in up:
            skipped_value_rows += 1  # rupee rows: not a quantity
            continue
        if up.startswith("NOTE") or "*" in label:
            # a printed footnote (FY2024-25 carries the energy page's FO-export note, with
            # tonnages embedded in its prose): recorded in the summary, never as a row
            footnotes.append(label)
            continue
        if not values:
            section = label.rstrip(":").strip()
            continue
        cells = assign(values, anchors)
        clean = label.rstrip(":").strip()
        if up.startswith("A.") and "TOTAL" in up:
            rows.append(Row("INTERNAL USE", clean, cells, "total_a"))
        elif up.startswith("B.") and "TOTAL" in up:
            rows.append(Row("OVERSEAS/FOREIGN", clean, cells, "total_b"))
        elif up.startswith("GRAND TOTAL") and "(A+B)" in up.replace(" ", ""):
            rows.append(Row("GRAND TOTAL", clean, cells, "grand"))
        elif up.startswith("GRAND TOTAL"):
            rows.append(Row("GRAND TOTAL", clean, cells, "prior"))
        elif clean.upper().startswith("TOTAL "):
            rows.append(Row(section, clean, cells, "subtotal"))
        elif indent == 0:
            # DOMESTIC, AGRICULTURE: a section printed as its own single row at the left
            # margin (sub-rows are indented; PEPCO / HUBCO / KAPCO are upper-case sub-rows)
            rows.append(Row(clean, clean, cells, "row"))
        else:
            rows.append(Row(section, clean, cells, "row"))

    # components for the column closures
    plain_by_section = {}
    for r in rows:
        if r.kind == "row":
            plain_by_section.setdefault(r.section, []).append(r)
    internal_components = []
    a_row = b_row = grand_row = None
    for r in rows:
        if r.kind == "subtotal":
            r.components = plain_by_section.get(r.section, [])
        if r.kind == "total_a":
            a_row = r
        elif r.kind == "total_b":
            b_row = r
            r.components = plain_by_section.get("OVERSEAS/FOREIGN", [])
        elif r.kind == "grand":
            grand_row = r
    seen_a = False
    for r in rows:
        if r.kind == "total_a":
            seen_a = True
        if seen_a:
            continue
        if r.kind == "subtotal":
            internal_components.append(r)
        elif r.kind == "row" and r.section == r.label:   # DOMESTIC, AGRICULTURE
            internal_components.append(r)
    if a_row:
        a_row.components = internal_components
    if grand_row:
        grand_row.components = [x for x in (a_row, b_row) if x]

    # closures
    for r in rows:
        if r.kind != "prior":
            r.row_residual = _row_residual(r, product_idx, cur_total_idx)
            if r.row_residual is not None and abs(r.row_residual) > TOLERANCE:
                r.fails.append("row TOTAL - sum(products) = %+d" % r.row_residual)
        else:
            r.row_residual = _row_residual(r, product_idx, cur_total_idx)
            if r.row_residual is not None and abs(r.row_residual) > TOLERANCE:
                r.fails.append("prior-year row TOTAL - sum(products) = %+d" % r.row_residual)
        if r.components:
            for idx in range(len(cols)):
                total = r.value(idx)
                parts = [c.value(idx) for c in r.components]
                if total is None and all(p is None for p in parts):
                    continue
                res = (total or 0) - sum(p or 0 for p in parts)
                r.col_residuals[idx] = res
                if abs(res) > TOLERANCE:
                    r.fails.append("%s column: %s - sum(components) = %+d"
                                   % (_colname(cols[idx]), r.label, res))

    return {
        "edition": edition_rel,
        "unit": unit,
        "cols": cols,
        "cur_total_idx": cur_total_idx,
        "prior_total_idx": prior_total_idx,
        "product_idx": product_idx,
        "current_fy": current_fy,
        "prior_fy": totals[1].fy_label if len(totals) > 1 else None,
        "rows": rows,
        "skipped_value_rows": skipped_value_rows,
        "footnotes": footnotes,
    }


def _colname(col):
    return col.name if col.fy_label is None else "%s %s" % (col.name, col.fy_label)


def _row_residual(row, product_idx, total_idx):
    total = row.value(total_idx)
    parts = [row.value(i) for i in product_idx]
    if total is None and all(p is None for p in parts):
        return None
    return (total or 0) - sum(p or 0 for p in parts)


# ----------------------------------------------------------------------- emission

def _fmt(v):
    return "" if v is None else str(v)


def emit_rows(ed, previous):
    """CSV dict rows for one parsed edition; `previous` is the parsed earlier edition
    (or None) used to verify this edition's previous-year cells."""
    out = []
    cols = ed["cols"]
    cur, prior = ed["current_fy"], ed["prior_fy"]
    ti, pi = ed["cur_total_idx"], ed["prior_total_idx"]
    prev_rows = {}
    prev_grand_by_name = {}   # earlier edition's GRAND TOTAL (A+B) row, keyed by header NAME
    if previous:
        for r in previous["rows"]:
            if r.kind != "prior":
                prev_rows[(r.section, r.label)] = r
            if r.kind == "grand":
                for i, c in enumerate(previous["cols"]):
                    if c.name == "TOTAL" and i != previous["cur_total_idx"]:
                        continue
                    prev_grand_by_name[c.name] = r.value(i)

    for r in ed["rows"]:
        for idx, col in enumerate(cols):
            if idx not in r.cells:
                continue
            q = r.cells[idx]
            note_bits = []
            if q is None:
                note_bits.append("printed '-'")
            residual = ""
            if r.kind == "prior":
                # previous-year GRAND TOTAL row: every product cell belongs to the prior year
                fy = prior or previous_fy(cur)
                if idx == pi:
                    # a value in the previous-year TOTAL column of the previous-year row
                    # would refer to two years back; the page does not say what it is.
                    fy2 = previous_fy(fy)
                    status = "unidentified"
                    note_bits.append("value printed in the %s TOTAL column of the %s row; "
                                     "position implies %s but it matches no figure in the "
                                     "held editions - not for use" % (prior, fy, fy2))
                    out.append(_cell(fy2, r, col, q, ed, status, "", note_bits))
                    continue
                status, xnote = _check_prior(q, col.name, prev_grand_by_name, previous)
                if idx == ti:
                    residual = _fmt(r.row_residual)
                    if r.row_residual is not None and abs(r.row_residual) > TOLERANCE:
                        status = "closure-failed"
                if xnote:
                    note_bits.append(xnote)
                out.append(_cell(fy, r, col, q, ed, status, residual, note_bits))
                continue

            if idx == pi:
                fy = prior
                prev = prev_rows.get((r.section, r.label))
                if previous is None:
                    status, xnote = "unchecked", "no earlier edition held to verify against"
                elif prev is None:
                    status, xnote = "unchecked", "row label has no counterpart in the %s edition" % previous["current_fy"]
                else:
                    pv = prev.value(previous["cur_total_idx"])
                    status, xnote = _compare(q, pv, previous["current_fy"])
                note_bits.append("previous-year TOTAL comparison column printed beside %s" % cur)
                if xnote:
                    note_bits.append(xnote)
                if idx in r.col_residuals:
                    residual = _fmt(r.col_residuals[idx])
                    if abs(r.col_residuals[idx]) > TOLERANCE:
                        status = "closure-failed"
                out.append(_cell(fy, r, col, q, ed, status, residual, note_bits))
                continue

            # cell-precise status: this cell fails only on its own column closure or on
            # the row's TOTAL closure (which involves every cell of the row)
            status = "verified"
            row_fail = r.row_residual is not None and abs(r.row_residual) > TOLERANCE
            col_res = r.col_residuals.get(idx)
            col_fail = col_res is not None and abs(col_res) > TOLERANCE
            if idx == ti:
                residual = _fmt(r.row_residual)
                if col_res is not None and not col_fail:
                    note_bits.append("column closure residual %+d" % col_res)
            elif col_res is not None:
                residual = _fmt(col_res)
            if row_fail:
                status = "closure-failed"
                note_bits.append("row closure: TOTAL - sum(products) = %+d" % r.row_residual)
            if col_fail:
                status = "closure-failed"
                note_bits.append("column closure: this cell - sum(its component rows) = %+d; "
                                 "the page does not say where the difference sits" % col_res)
            out.append(_cell(cur, r, col, q, ed, status, residual, note_bits))
    return out


def _compare(q, pv, prev_fy):
    if q is None and pv is None:
        return "verified", "matches the %s edition (both absent)" % prev_fy
    if q is not None and pv is not None and abs(q - pv) <= TOLERANCE:
        return "verified", "matches the %s edition's own figure" % prev_fy
    return "restated", "%s edition printed %s; this edition prints %s" % (prev_fy, _fmt(pv) or "'-'", _fmt(q) or "'-'")


def _check_prior(q, name, prev_grand_by_name, previous):
    """Verify a previous-year GRAND TOTAL cell against the earlier edition's own GRAND
    TOTAL (A+B) row, matched by column NAME (headers may drift between editions)."""
    if previous is None:
        return "unchecked", "previous-year GRAND TOTAL row; no earlier edition held to verify against"
    if name not in prev_grand_by_name:
        return "unchecked", ("previous-year GRAND TOTAL row; column %s absent from the %s edition"
                             % (name, previous["current_fy"]))
    status, xnote = _compare(q, prev_grand_by_name[name], previous["current_fy"])
    return status, "previous-year GRAND TOTAL row; " + xnote


def _cell(fy, row, col, q, ed, status, residual, note_bits):
    return {
        "fiscal_year": fy,
        "section": row.section,
        "sector_row": row.label,
        "product": col.name,
        "quantity": _fmt(q),
        "unit_as_printed": ed["unit"],
        "edition_file": ed["edition"],
        "status": status,
        "closure_residual": residual,
        "note": "; ".join(note_bits),
    }


HEADER_COMMENT = """\
# OCAC "SECTORAL SALES OF NON-ENERGY PRODUCTS" (titled "PAKISTAN - NON-ENERGY PRODUCTS" under
# "SECTORAL SALES / CONSUMPTION OF POL PRODUCTS" in the FY2016-17..FY2019-20 editions): the
# annual Pakistan page, one row per printed CELL (sector row x product column), from every held
# annual edition. Activity basis for IPCC 2.D - lubricants (LUBES, GREASES), other non-energy
# products (ASPHALT, JBO, MTT, SOLVENT, CARBON OIL, PROCESS OIL, BTX).
#
# THESE ARE SALES (deliveries by OCAC member companies to consuming sectors), NOT combustion:
# the 2.D activity is the quantity of product placed in use, to which an oxidised fraction
# (ODU) is applied; none of these tonnes belong in 1.A fuel combustion.
#
# UNIT: as printed on every page, "M. Tons" (metric tonnes). Rupee rows ("VALUE '000' Rs.") are
# not quantities and are NOT transcribed.
#
# EDITIONS (edition_file): %(editions)s
# Each edition prints its OWN fiscal year in every product column plus (a) a previous-year TOTAL
# comparison column and (b) a previous-year GRAND TOTAL row by product. Those previous-year cells
# are written under THEIR OWN fiscal_year (so FY2015-16 appears, from the 2016-17 edition alone)
# and are verified against the earlier edition's own current-year figure where it is held.
#
# CLOSURE: status=verified when the row's current-year TOTAL equals the sum of its product cells
# within 1 t and, for "Total X" / A. TOTAL INTERNAL / B. TOTAL OVERSEAS / GRAND TOTAL (A+B) rows,
# each column equals the sum of its component rows within 1 t (closure_residual carries the
# difference: the row residual on TOTAL cells, the column residual on total-row product cells).
# closure-failed otherwise; restated = a previous-year cell differing from the earlier edition;
# unchecked = a previous-year cell with nothing held to check it against; unidentified = a printed
# value whose meaning the page does not state.
#
# FINDING (as printed, not corrected here): in the FY2017-18, FY2018-19 and FY2019-20 editions the
# GOVERNMENT rows print "-" (or a few tonnes of LUBES) while A. TOTAL INTERNAL VOLUME still contains
# Government asphalt and lubes, so A. TOTAL exceeds the sum of its sector rows by 118,311 / 78,853 /
# 67,889 t (ASPHALT 116,064 / 76,409 / 67,423; LUBES 2,196 / 2,378 / 417). GRAND TOTAL (A+B) closes
# against A+B in every edition, so the national product totals stand; only the sector split of those
# three years is short. The FY2018-19 and FY2020-21 editions' previous-year TOTAL columns restate the
# FY2017-18 and FY2019-20 Government rows (Others 17 -> 118,311; 15 -> 67,888: status restated, under
# those fiscal years); the FY2018-19 gap is restated in no held edition. The FY2024-25 edition prints
# one value (165,588) in the previous-year TOTAL column of the previous-year GRAND TOTAL row that
# matches no figure in the held editions: status unidentified, not for use.
#
# A printed "-" is an ABSENCE: quantity is EMPTY, never 0. Printed sector labels are kept verbatim
# (they drift: "HUBCO (BAL) / HUBCO (NAROWAL)" becomes "HUBCO" + "Narowal Energy" from FY2018-19);
# rows are never merged. Product columns are mapped by header position per page, never by index.
#
# written by scripts/ingest_ocac_non_energy.py (pdftotext -layout); re-run to re-derive.
"""


def main():
    parsed = []
    for rel in EDITIONS:
        path = asset_path(ROOT, rel)
        if not os.path.exists(path):
            raise SystemExit("not held: %s (run scripts/holdings.py OCAC)" % rel)
        pages = pdftotext_pages(path)
        page = locate_page(pages)
        parsed.append(parse_page(page, rel))

    # chronological order by the edition's own fiscal year
    parsed.sort(key=lambda e: e["current_fy"])

    all_rows = []
    previous = None
    for ed in parsed:
        rows = emit_rows(ed, previous)
        all_rows.extend(rows)
        _print_summary(ed, rows)
        previous = ed

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        fh.write(HEADER_COMMENT % {"editions": "; ".join(e["edition"] for e in parsed)})
        w = csv.DictWriter(fh, fieldnames=COLUMNS, lineterminator="\n")
        w.writeheader()
        for r in all_rows:
            w.writerow(r)
    years = sorted({r["fiscal_year"] for r in all_rows})
    print("\nwrote %d rows to %s" % (len(all_rows), os.path.relpath(OUT, ROOT)))
    print("fiscal years covered: %s" % ", ".join(years))
    failures = [r for r in all_rows if r["status"] == "closure-failed"]
    print("closure failures: %d cell(s)" % len(failures))


def _print_summary(ed, rows):
    print("=" * 78)
    print("%s  (%s)" % (ed["edition"], ed["unit"]))
    years = sorted({r["fiscal_year"] for r in rows})
    print("  fiscal years captured: %s  (own year %s)" % (", ".join(years), ed["current_fy"]))
    print("  header as printed: %s" % ", ".join(c.name for c in ed["cols"]))
    print("  rupee VALUE rows skipped: %d" % ed["skipped_value_rows"])
    for f in ed["footnotes"]:
        print("  footnote skipped: %s" % f)
    grand = [r for r in ed["rows"] if r.kind == "grand"]
    if grand:
        g = grand[0]
        print("  GRAND TOTAL (A+B) VOLUME, %s:" % ed["current_fy"])
        for i, c in enumerate(ed["cols"]):
            fy = ed["current_fy"] if i != ed["prior_total_idx"] else ed["prior_fy"]
            v = g.value(i)
            print("    %-12s %-8s %s" % (c.name, fy, "-" if v is None else format(v, ",")))
    fails = [r for r in ed["rows"] if r.fails]
    if fails:
        print("  CLOSURE FAILURES:")
        for r in fails:
            for f in r.fails:
                print("    [%s] %s: %s" % (r.section, r.label, f))
    else:
        print("  closure: every row and every total closes within %d t" % TOLERANCE)
    odd = [r for r in rows if r["status"] in ("unidentified", "restated")]
    for r in odd:
        print("  %s: %s / %s / %s %s = %s -- %s" % (r["status"].upper(), r["fiscal_year"], r["section"],
                                                   r["sector_row"], r["product"], r["quantity"] or "'-'", r["note"]))


if __name__ == "__main__":
    main()
