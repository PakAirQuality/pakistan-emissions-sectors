"""Pakistan fertilizer PRODUCTION by product and fiscal year, from the held NFDC documents.

WHY. The ammonia (IPCC 2.B.1) activity is anchored on FY2023-24/FY2024-25 production by
manufacturer (data/nfdc/afr2025_production_by_manufacturer.csv). Back-casting it to
FY2015-16 needs the same quantity for every earlier year, and the NFDC compendium
"Pakistan Fertilizer Statistics 2012-13 to 2022-23" prints exactly that: Table 2.5,
"Domestic Production of Fertilizer by Products", fiscal-year block, tonnes, one column per
manufacturer under each product. Nothing is downloaded here; every input is held in
data/raw/nfdc/ or data/nfdc/ (checked with scripts/holdings.py NFDC).

THREE DOCUMENTS, THREE SOURCE ROWS PER OVERLAPPING YEAR. Where two editions print the same
year (FY2022-23 in the compendium and the 2023-24 review; FY2023-24 in the 2023-24 and
2024-25 reviews) BOTH rows are kept, tagged by source_file. Inter-edition differences are
printed to stdout, never averaged away.

WHAT IS TAKEN FROM EACH DOCUMENT
  * Compendium, Table 2.5 (pp. 21-23 printed / pdf pages 30-32): the FISCAL YEAR block only.
    The Kharif/Rabi season blocks are deliberately not taken (a second path to the same
    annual quantity). Urea's printed Total column is checked against its seven manufacturer
    columns; the page-3 "Grand Total of All Products" is the closure control.
  * Annual Fertilizer Review 2023-24, ANNEX-1 (pdf pages 76-77, tonnes): FY2022-23 and
    FY2023-24 by product and manufacturer, monthly, with a TOTAL column. Only the TOTAL
    column is read. Per-product TOTAL rows are checked against their manufacturer rows; the
    GRAND TOTAL is the closure control. Table 1 of the same review ('000 t) is a
    within-document check printed to stdout, not a second row.
  * Annual Fertilizer Review 2024-25 (held as text, data/nfdc/AFR_2024-25.txt), ANNEX-1:
    same layout, FY2023-24 and FY2024-25.

CLOSURE RULE. A year's rows are `verified` when the sum of the product rows equals the
printed grand total to within 1 tonne (the printed unit); otherwise
`verified-open-residual` and closure_residual_000t carries (printed - summed)/1000.

PARSING TRAPS HANDLED. pdftotext renders the "ti" ligature as \\x19 in some NFDC documents
and drops it in others, so every line is stripped of [\\x00-\\x1f] and titles are matched
loosely. Left-margin page numbers ("60", "61", "62") are glued to the front of some Annex-1
rows and are removed before the product label is read. Thousands separators and one stray
decimal ("32,725.0") are tolerated. A printed "-" is an ABSENCE and becomes an empty cell;
a printed "0" is kept as 0 in a manufacturer column but a product whose every column is
absent gets an empty production cell, never a zero. Units are recorded as printed and
converted to thousand tonnes.

Usage:  python3 scripts/ingest_nfdc_production_series.py
Writes: data/nfdc/nfdc_production_by_product_series.csv
"""
from __future__ import annotations

import csv
import io
import re
import subprocess
import sys
import tempfile
from collections import OrderedDict, defaultdict
from pathlib import Path

from pkinv.assets import resolve

ROOT = Path(__file__).resolve().parents[1]
STATS_PDF = ROOT / "data/raw/nfdc/nfdc_fertilizer_statistics_2012_13_to_2022_23.pdf"
AFR24_PDF = ROOT / "data/raw/nfdc/nfdc_annual_fertilizer_review_2023_24.pdf"
AFR25_TXT = ROOT / "data/nfdc/AFR_2024-25.txt"  # a raw rendering; raw documents did not move
# The two tables did move, and both are declared by their historical identities, so they are
# resolved rather than joined. Resolving the OUTPUT is what matters: written unresolved it
# would lay down a second vintage beside the raw PDFs while the catalog - and every reader -
# points at data/shared/activity/nfdc/.
CROSSCHECK_CSV = Path(resolve(ROOT / "data/nfdc/afr2025_production_by_manufacturer.csv"))
OUT_CSV = Path(resolve(ROOT / "data/nfdc/nfdc_production_by_product_series.csv"))

CLOSURE_TOL_PRINTED_UNIT = 1.0  # tonnes, for the two tonnes-denominated tables

COLUMNS = [
    "fiscal_year", "product", "printed_label", "production_000t", "unit_as_printed",
    "source_file", "table_or_page", "status", "closure_residual_000t", "note",
]

PRODUCT_ORDER = ["Urea", "CAN", "NP", "DAP", "NPK", "SSP", "SOP", "AS"]

UNPARSED: list[str] = []          # "<file> <page/table>: reason"
NUM_RE = re.compile(r"^-?\d{1,3}(?:,\d{3})+(?:\.\d+)?$|^-?\d+(?:\.\d+)?$")


# --------------------------------------------------------------------------- helpers
def norm(line: str) -> str:
    """Strip control bytes (the \\x19 ligature artefact among them) and trailing space."""
    return re.sub(r"[\x00-\x1f]", "", line).rstrip()


def loose(s: str) -> str:
    """Lower-case, whitespace-free, ligature-tolerant key for title matching."""
    return re.sub(r"[^a-z0-9]", "", norm(s).lower())


def parse_num(tok: str) -> float | None:
    """'-' -> None (absence). '1,234' -> 1234.0. Anything else -> ValueError."""
    tok = tok.strip()
    if tok in {"-", "–", "—", ""}:
        return None
    if not NUM_RE.match(tok):
        raise ValueError(f"not a number: {tok!r}")
    return float(tok.replace(",", ""))


def is_num_tok(tok: str) -> bool:
    return tok in {"-", "–", "—"} or bool(NUM_RE.match(tok))


def pdf_pages(pdf: Path, tmp: Path) -> list[str]:
    out = tmp / (pdf.stem + ".txt")
    subprocess.run(["pdftotext", "-layout", str(pdf), str(out)], check=True)
    return out.read_text(encoding="utf-8", errors="replace").split("\f")


def fmt000(t: float | None) -> str:
    return "" if t is None else f"{t / 1000.0:.3f}"


def canon_product(label: str) -> str:
    key = loose(label)
    if key.startswith("urea"):
        return "Urea"
    if key.startswith("npk"):
        return "NPK"
    if key.startswith("np"):
        return "NP"
    if key.startswith("dap"):
        return "DAP"
    if key.startswith("can"):
        return "CAN"
    if key.startswith("ssp"):
        return "SSP"
    if key.startswith("sop"):
        return "SOP"
    if key.startswith("as") or "ammoniumsulph" in key:
        return "AS"
    return label.strip()


# ------------------------------------------------ compendium Table 2.5 (fiscal-year block)
# Column layouts of the three Table 2.5 pages, fiscal-year block, after the year token.
T25_LAYOUTS = {
    # (page key by header) : list of (product, printed_label, manufacturer, ncols) groups
    "urea": [("Urea", "Urea", ["Fatima Fert.", "EFERT", "FFC Pak-Saudi", "Fatima Fertilizer",
                               "Pak-Arab", "Agritech", "FFC + FFBL", "Total"])],
    "other1": [("DAP", "DAP", ["Sona (FFBL)"]),
               ("CAN", "CAN", ["PAK-ARAB", "Fatima Fertilizer"]),
               ("NP", "NP", ["PAK-ARAB", "EFERT", "Fatima Fertilizer"]),
               ("SSP", "SSP", ["Suraj Fertilizer", "LCFL", "Agritech", "Safi Chemicals"])],
    "other2": [("SOP", "SOP", ["Pacific Exim"]),
               ("NPK", "NPKs", ["EFERT", "Safi Chemicals"]),
               ("__grand__", "Grand Total of All Products", ["Grand Total"])],
}


def classify_t25_page(page: str) -> str | None:
    lines = [norm(l) for l in page.splitlines()]
    head = loose("".join(lines[:12]))
    if "table25" not in head or "domesticproduction" not in head:
        return None
    if "urea" in loose("".join(lines[:4])):
        return "urea"
    if "dap" in head and "can" in head:
        return "other1"
    if "sop" in head and "grandtotal" in head:
        return "other2"
    return None


def fiscal_block_rows(page: str) -> list[tuple[str, list[str]]]:
    """Rows of the 'Fiscal Year' block: (year, tokens)."""
    rows, inside = [], False
    for raw in page.splitlines():
        line = norm(raw)
        if loose(line) == "fiscalyear":
            inside = True
            continue
        if not inside:
            continue
        if "continued" in loose(line):
            break
        m = re.match(r"^\s*(20\d\d-\d\d)\s+(.*)$", line)
        if m:
            rows.append((m.group(1), m.group(2).split()))
    return rows


def parse_table_2_5(pages: list[str], source_file: str) -> tuple[dict, dict]:
    """Return per-year dict: {year: {product: (tonnes|None, printed_label, note)}},
    and {year: grand_total_tonnes}."""
    unit = None
    by_year: dict[str, OrderedDict] = defaultdict(OrderedDict)
    grand: dict[str, float] = {}
    found = set()
    for pno, page in enumerate(pages, 1):
        kind = classify_t25_page(page)
        if not kind:
            continue
        found.add(kind)
        um = re.search(r"\(\s*('?000\s*)?tonnes\s*\)", norm(page), re.I)
        unit = um.group(0).strip("() ") if um else "tonnes"
        layout = T25_LAYOUTS[kind]
        ncols = sum(len(g[2]) for g in layout)
        rows = fiscal_block_rows(page)
        if not rows:
            UNPARSED.append(f"{source_file} pdf-page {pno} (Table 2.5 {kind}): no fiscal-year block found")
            continue
        for year, toks in rows:
            if len(toks) != ncols:
                UNPARSED.append(f"{source_file} pdf-page {pno} (Table 2.5 {kind}) {year}: "
                                f"{len(toks)} numeric tokens, expected {ncols}: {toks}")
                continue
            try:
                vals = [parse_num(t) for t in toks]
            except ValueError as e:
                UNPARSED.append(f"{source_file} pdf-page {pno} (Table 2.5 {kind}) {year}: {e}")
                continue
            i = 0
            for product, printed, mans in layout:
                cols = vals[i:i + len(mans)]
                i += len(mans)
                if product == "__grand__":
                    grand[year] = cols[0]
                    continue
                notes = []
                if product == "Urea":
                    man_sum = sum(v for v in cols[:-1] if v is not None)
                    printed_total = cols[-1]
                    if printed_total is None or abs(man_sum - printed_total) > CLOSURE_TOL_PRINTED_UNIT:
                        notes.append(f"printed Urea Total {printed_total:,.0f} vs manufacturer sum {man_sum:,.0f}")
                    value = printed_total
                else:
                    present = [v for v in cols if v is not None]
                    value = sum(present) if present else None
                    if value is None:
                        notes.append("all manufacturer columns printed '-' (no production; empty, not zero)")
                    absent = [m for m, v in zip(mans, cols) if v is None]
                    if absent and value is not None:
                        notes.append("printed '-' for " + ", ".join(absent))
                by_year[year][product] = (value, printed, "; ".join(notes), f"pdf-page {pno}")
    for kind in T25_LAYOUTS:
        if kind not in found:
            UNPARSED.append(f"{source_file}: Table 2.5 page '{kind}' not found")
    return {"by_year": by_year, "grand": grand, "unit": unit or "tonnes"}, grand


def table_2_7_grand_totals(pages: list[str]) -> dict[str, float]:
    """Within-document check: Table 2.7's GRAND TOTAL / G. TOTAL per fiscal year."""
    out = {}
    for page in pages:
        head = loose("".join(page.splitlines()[:6]))
        if "table27" not in head:
            continue
        year = None
        for raw in page.splitlines():
            line = norm(raw)
            m = re.match(r"^\s*\((20\d\d-\d\d)\)\s*$", line)
            if m:
                year = m.group(1)
            if year and re.match(r"^\s*(GRAND\s*TOTAL|G\.\s*TOTAL)\b", line, re.I):
                toks = line.split()
                try:
                    out[year] = parse_num(toks[-1])
                except ValueError:
                    pass
    return out


# ------------------------------------------------------------------- AFR ANNEX-1 (tonnes)
PRODUCT_LABEL_RE = re.compile(
    r"^(UREA(?:\s*\([A-Za-z.]+\))?|NPKs?|NP|SSP|CAN|DAP|SOP|AS)\s+(.+)$")


def parse_annex1(pages: list[str], source_file: str, table_name: str) -> dict:
    """Return {year: {'products': OrderedDict(product -> dict), 'grand': float|None,
    'page': str}} from the ANNEX-1 style monthly table; only the TOTAL column is read."""
    result: dict[str, dict] = {}
    for pno, page in enumerate(pages, 1):
        lines = [norm(l) for l in page.splitlines()]
        head = loose("".join(lines[:8]))
        if "fertilizerproductionbyproductandmanufacturerduring" not in head:
            continue
        if "kharif" in head or "rabi" in head:
            continue  # seasonal annexes: not taken
        year = None
        for l in lines[:12]:
            m = re.match(r"^\s*\((20\d\d-\d\d)\)\s*$", l)
            if m:
                year = m.group(1)
        if not year:
            UNPARSED.append(f"{source_file} page {pno} ({table_name}): no fiscal-year header")
            continue
        unit = "Tonnes" if re.search(r"\(\s*tonnes\s*\)", "".join(lines[:10]), re.I) else "?"
        products: OrderedDict[str, dict] = OrderedDict()
        grand = None
        current = None
        for l in lines:
            if re.match(r"^\s*NUTRIENTS\b", l):
                break
            l2 = re.sub(r"^\s*\d{1,3}\s+(?=[A-Za-z])", "", l)  # margin page number glued to row
            s = l2.strip()
            if not s:
                continue
            gm = re.match(r"^GRAND\s*TOTAL\s+(.*)$", s, re.I)
            if gm:
                toks = gm.group(1).split()
                grand = parse_num(toks[-1])
                continue
            pm = PRODUCT_LABEL_RE.match(s)
            if pm:
                label, rest = pm.group(1), pm.group(2)
                product = canon_product(label)
                toks = rest.split()
                # manufacturer = leading non-numeric tokens
                k = 0
                while k < len(toks) and not is_num_tok(toks[k]):
                    k += 1
                man = " ".join(toks[:k])
                nums = toks[k:]
                if not nums:
                    continue
                try:
                    total = parse_num(nums[-1])
                except ValueError as e:
                    UNPARSED.append(f"{source_file} page {pno} ({table_name}) {year} {label} {man}: {e}")
                    continue
                entry = products.setdefault(product, {"labels": [], "rows": [], "printed_total": None})
                current = product
                if loose(man) == "total":
                    entry["printed_total"] = total
                else:
                    if label not in entry["labels"]:
                        entry["labels"].append(label)
                    entry["rows"].append((man, total))
                continue
            tm = re.match(r"^TOTAL\s+(.*)$", s, re.I)
            if tm and current:
                toks = tm.group(1).split()
                products[current]["printed_total"] = parse_num(toks[-1])
                continue
        if not products:
            UNPARSED.append(f"{source_file} page {pno} ({table_name}) {year}: no product rows parsed")
            continue
        result[year] = {"products": products, "grand": grand, "page": f"page {pno}", "unit": unit}
    if not result:
        UNPARSED.append(f"{source_file}: {table_name} not found")
    return result


def annex_rows(parsed: dict, source_file: str, table_name: str) -> list[dict]:
    rows = []
    for year, blk in parsed.items():
        prods = blk["products"]
        values = {}
        notes = {}
        for product, e in prods.items():
            present = [t for _, t in e["rows"] if t is not None]
            val = sum(present) if present else None
            n = []
            absent = [m for m, t in e["rows"] if t is None]
            if val is None:
                n.append("all manufacturer rows printed '-' (no production; empty, not zero)")
            elif absent:
                n.append("printed '-' for " + ", ".join(absent))
            pt = e["printed_total"]
            if pt is not None and val is not None and abs(pt - val) > CLOSURE_TOL_PRINTED_UNIT:
                n.append(f"printed {product} TOTAL {pt:,.0f} vs manufacturer sum {val:,.0f}")
            values[product] = val
            notes[product] = "; ".join(n)
        summed = sum(v for v in values.values() if v is not None)
        grand = blk["grand"]
        if grand is None:
            status, resid = "verified-open-residual", None
            UNPARSED.append(f"{source_file} {blk['page']} ({table_name}) {year}: GRAND TOTAL not read")
        else:
            resid = grand - summed
            status = "verified" if abs(resid) <= CLOSURE_TOL_PRINTED_UNIT else "verified-open-residual"
            if status != "verified":
                cn = f"year does not close: product rows sum {summed:,.0f} t vs printed GRAND TOTAL {grand:,.0f} t"
                notes = {k: "; ".join(x for x in (v, cn) if x) for k, v in notes.items()}
        for product in sorted(values, key=lambda p: PRODUCT_ORDER.index(p) if p in PRODUCT_ORDER else 99):
            rows.append({
                "fiscal_year": year, "product": product,
                "printed_label": "|".join(prods[product]["labels"]),
                "production_000t": fmt000(values[product]),
                "unit_as_printed": blk["unit"],
                "source_file": source_file,
                "table_or_page": f"{table_name}, {blk['page']}",
                "status": status,
                "closure_residual_000t": "" if resid is None else f"{resid / 1000.0:.3f}",
                "note": notes[product],
            })
    return rows


# ------------------------------------------------------- AFR Table 1 ('000 t) as a check
def parse_afr_table1(text: str) -> dict[str, dict[str, float]]:
    """{year: {product: '000 t}} from the 'Domestic fertilizer production during YYYY-YY'
    summary table (two fiscal-year columns). Reads product 'Total' rows and the single-row
    products (DAP-SONA, NPK). Used only as a within-document check."""
    lines = [norm(l) for l in text.splitlines()]
    out: dict[str, dict[str, float]] = {}
    i = 0
    while i < len(lines):
        if re.match(r"^\s*Table\s*1\.\s+Domestic\s+fertilizer\s+production\s+during", lines[i], re.I):
            years = None
            j = i
            prev_label = None
            while j < len(lines) and j < i + 60:
                l = lines[j]
                ym = re.findall(r"\b(20\d\d-\d\d)\b", l)
                if years is None and len(ym) == 2:
                    years = ym
                if re.match(r"^\s*NUTRIENTS", l):
                    break
                m = re.match(r"^\s*([A-Za-z][A-Za-z \-()./]*?)\s{2,}(Total|FFC|EFERT)\s+(.*)$", l)
                if m and years:
                    label, man, rest = m.group(1).strip(), m.group(2), m.group(3).split()
                    nums = [t for t in rest if is_num_tok(t)]
                    product = canon_product(label)
                    take = (man == "Total") or (product in {"DAP", "NPK"})
                    if label.lower().startswith("all products"):
                        product, take = "__all__", True
                    if take and len(nums) >= 4:
                        # capacity, prev prod, prev share, cur prod, cur share, ...
                        try:
                            prev_v = parse_num(nums[1]); cur_v = parse_num(nums[3])
                        except ValueError:
                            prev_v = cur_v = None
                        if prev_v is not None:
                            out.setdefault(years[0], {})[product] = prev_v
                        if cur_v is not None:
                            out.setdefault(years[1], {})[product] = cur_v
                j += 1
            i = j
        i += 1
    return out


# ------------------------------------------------------------------------------ main
def main(check: bool = False) -> int:
    for p in (STATS_PDF, AFR24_PDF, AFR25_TXT, CROSSCHECK_CSV):
        if not p.exists():
            print(f"MISSING held input: {p}", file=sys.stderr)
            return 2

    rows: list[dict] = []
    stdout_checks: list[str] = []

    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        stats_pages = pdf_pages(STATS_PDF, tmp)
        afr24_pages = pdf_pages(AFR24_PDF, tmp)
    afr25_text = AFR25_TXT.read_text(encoding="utf-8", errors="replace")
    afr25_pages = afr25_text.split("\f")

    stats_src = STATS_PDF.relative_to(ROOT).as_posix()
    afr24_src = AFR24_PDF.relative_to(ROOT).as_posix()
    afr25_src = AFR25_TXT.relative_to(ROOT).as_posix()

    # ---- 1. compendium Table 2.5
    t25, _ = parse_table_2_5(stats_pages, stats_src)
    t27_grand = table_2_7_grand_totals(stats_pages)
    for year in sorted(t25["by_year"]):
        prods = t25["by_year"][year]
        summed = sum(v for v, *_ in prods.values() if v is not None)
        grand = t25["grand"].get(year)
        if grand is None:
            status, resid = "verified-open-residual", None
            UNPARSED.append(f"{stats_src} Table 2.5 {year}: Grand Total not read")
        else:
            resid = grand - summed
            status = "verified" if abs(resid) <= CLOSURE_TOL_PRINTED_UNIT else "verified-open-residual"
        g27 = t27_grand.get(year)
        if g27 is not None and grand is not None:
            stdout_checks.append(f"  within-document  Table 2.5 grand {grand:>12,.0f} t  vs Table 2.7 G.TOTAL "
                                 f"{g27:>12,.0f} t  {year}  diff {grand - g27:+,.0f}")
        pages_used = sorted({p for *_, p in prods.values()})
        closure_note = ""
        if status != "verified" and grand is not None:
            closure_note = (f"year does not close: product rows sum {summed:,.0f} t vs printed "
                            f"Grand Total {grand:,.0f} t (Table 2.7 G. TOTAL also prints {g27:,.0f} t)"
                            if g27 is not None else
                            f"year does not close: product rows sum {summed:,.0f} t vs printed Grand Total {grand:,.0f} t")
        for product in sorted(prods, key=lambda p: PRODUCT_ORDER.index(p) if p in PRODUCT_ORDER else 99):
            val, printed, note, page = prods[product]
            note = "; ".join(x for x in (note, closure_note) if x)
            rows.append({
                "fiscal_year": year, "product": product, "printed_label": printed,
                "production_000t": fmt000(val), "unit_as_printed": t25["unit"],
                "source_file": stats_src,
                "table_or_page": f"Table 2.5 (Domestic Production of Fertilizer by Products), fiscal-year block, {page}",
                "status": status,
                "closure_residual_000t": "" if resid is None else f"{resid / 1000.0:.3f}",
                "note": note,
            })

    # ---- 2. AFR 2023-24 ANNEX-1
    a24 = parse_annex1(afr24_pages, afr24_src, "ANNEX-1")
    rows += annex_rows(a24, afr24_src, "ANNEX-1")
    # ---- 3. AFR 2024-25 ANNEX-1 (held text)
    a25 = parse_annex1(afr25_pages, afr25_src, "ANNEX-1")
    rows += annex_rows(a25, afr25_src, "ANNEX-1")

    # ---- within-document checks: AFR Table 1 ('000 t) vs Annex-1 sums
    for label, pages, parsed in (("AFR 2023-24", afr24_pages, a24), ("AFR 2024-25", afr25_pages, a25)):
        t1 = parse_afr_table1("\f".join(pages))
        for year, prods in sorted(t1.items()):
            if year not in parsed:
                continue
            ann = parsed[year]["products"]
            for product, v000 in prods.items():
                if product == "__all__":
                    g = parsed[year]["grand"]
                    if g is not None:
                        stdout_checks.append(f"  within-document  {label} Table 1 All Products {v000:>8,.1f} kt vs "
                                             f"ANNEX-1 GRAND TOTAL {g / 1000:>10,.3f} kt  {year}  diff {v000 - g / 1000:+.3f}")
                    continue
                if product in ann:
                    s = sum(t for _, t in ann[product]["rows"] if t is not None)
                    stdout_checks.append(f"  within-document  {label} Table 1 {product:<4} {v000:>8,.1f} kt vs "
                                         f"ANNEX-1 sum {s / 1000:>10,.3f} kt  {year}  diff {v000 - s / 1000:+.3f}")

    # ---- write CSV with header comment block
    header = [
        "# NFDC domestic fertilizer PRODUCTION by product and fiscal year (thousand tonnes of product), FY2012-13..FY2024-25.",
        "# Built by scripts/ingest_nfdc_production_series.py from HELD documents only:",
        f"#   (a) {stats_src} - NFDC 'Pakistan Fertilizer Statistics 2012-13 to 2022-23', Table 2.5 fiscal-year block (tonnes);",
        f"#   (b) {afr24_src} - NFDC 'Annual Fertilizer Review 2023-24', ANNEX-1 TOTAL column (tonnes), FY2022-23 and FY2023-24;",
        f"#   (c) {afr25_src} - NFDC 'Annual Fertilizer Review 2024-25' (held text), ANNEX-1 TOTAL column (tonnes), FY2023-24 and FY2024-25.",
        "# One row per (fiscal_year, product, source_file). Years printed by two editions carry BOTH rows; nothing is averaged.",
        "# product is the mapped class; printed_label is the label(s) as printed. production_000t = printed tonnes / 1000, 3 dp.",
        "# An absence (printed '-') is an EMPTY cell, never 0. AS (ammonium sulphate) is not domestically produced and is not printed.",
        "# CLOSURE RULE: status=verified when the year's product rows sum to the printed grand total within 1 tonne (the printed unit);",
        "#   otherwise verified-open-residual with closure_residual_000t = (printed grand total - sum of product rows)/1000.",
        "# Sub-closures (printed product Total vs manufacturer sum) that fail by more than 1 tonne are named in note.",
    ]
    buffer = io.StringIO(newline="")
    for h in header:
        buffer.write(h + "\n")
    w = csv.DictWriter(buffer, fieldnames=COLUMNS, lineterminator="\n")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    payload = buffer.getvalue()

    # --check proves the re-derivation without writing, which is what lets this producer
    # stand in tests/test_data_rederivation.py. Without it the guard would rewrite the
    # very file it is meant to certify.
    if check:
        held = OUT_CSV.read_text(encoding="utf-8") if OUT_CSV.exists() else None
        if held != payload:
            print(f"{OUT_CSV.relative_to(ROOT)} does not reproduce from the held documents",
                  file=sys.stderr)
            return 1
        print(f"Checked {OUT_CSV.relative_to(ROOT)}  ({len(rows)} data rows) - identical\n")
    else:
        OUT_CSV.write_text(payload, encoding="utf-8", newline="")
        print(f"Wrote {OUT_CSV.relative_to(ROOT)}  ({len(rows)} data rows)\n")
    print("FIRST 20 ROWS")
    print(",".join(COLUMNS))
    for r in rows[:20]:
        print(",".join(str(r[c]) for c in COLUMNS))

    # ---- coverage summary
    print("\nCOVERAGE BY YEAR (products with a value; [] = printed absent; source count)")
    cov: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        cov[r["fiscal_year"]][r["source_file"]].append(r)
    for year in sorted(cov):
        for src, rs in cov[year].items():
            got = [r["product"] if r["production_000t"] else f"[{r['product']}]" for r in rs]
            st = {r["status"] for r in rs}
            res = {r["closure_residual_000t"] for r in rs}
            print(f"  {year}  {Path(src).name:<55} {' '.join(got):<45} {'/'.join(sorted(st))} resid={'/'.join(sorted(res))} kt")

    # ---- inter-edition comparisons
    print("\nINTER-EDITION COMPARISONS (same year printed by two documents; kt of product)")
    by_key: dict[tuple, dict[str, str]] = defaultdict(dict)
    for r in rows:
        by_key[(r["fiscal_year"], r["product"])][r["source_file"]] = r["production_000t"]
    for (year, product), srcs in sorted(by_key.items()):
        if len(srcs) > 1:
            items = sorted(srcs.items())
            vals = [float(v) if v else None for _, v in items]
            d = "" if any(v is None for v in vals) else f"diff {vals[1] - vals[0]:+.3f}"
            print(f"  {year} {product:<4} " + "  ".join(f"{Path(s).name}={v or 'empty'}" for s, v in items) + f"  {d}")

    print("\nWITHIN-DOCUMENT CHECKS")
    for line in stdout_checks:
        print(line)

    # ---- the requested cross-check vs afr2025_production_by_manufacturer.csv
    print(f"\nCROSS-CHECK vs {CROSSCHECK_CSV.relative_to(ROOT)} (sum over manufacturers, production_000t)")
    print("  NOTE: that CSV was transcribed from the 2024-25 review's Table 1 ('000 t). Against the 2023-24 review's ANNEX-1")
    print("  this is an inter-edition comparison; against the 2024-25 review's own ANNEX-1 it is a same-document check")
    print("  (tonnes annex vs rounded '000 t summary), not independent evidence.")
    mf: dict[tuple, float] = defaultdict(float)
    mf_n: dict[tuple, int] = defaultdict(int)
    with CROSSCHECK_CSV.open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["production_000t"].strip():
                mf[(r["fiscal_year"], r["product"])] += float(r["production_000t"])
                mf_n[(r["fiscal_year"], r["product"])] += 1
    for year in ("2023-24", "2024-25"):
        for src in (afr24_src, afr25_src):
            mine = {r["product"]: r for r in rows if r["fiscal_year"] == year and r["source_file"] == src}
            if not mine:
                continue
            print(f"  {year}  series source {src}")
            tot_mine = tot_mf = 0.0
            for product in PRODUCT_ORDER:
                if product not in mine and (year, product) not in mf:
                    continue
                mv = mine.get(product, {}).get("production_000t", "")
                fv = mf.get((year, product))
                if mv == "" and fv is None:
                    print(f"     {product:<4} series=empty   manufacturers=empty")
                    continue
                mvf = float(mv) if mv else None
                if mvf is not None:
                    tot_mine += mvf
                if fv is not None:
                    tot_mf += fv
                d = "" if (mvf is None or fv is None) else f"diff {mvf - fv:+.3f} kt ({(mvf - fv) / fv * 100:+.2f}%)" if fv else ""
                print(f"     {product:<4} series={mv or 'empty':>9}  manufacturers={'' if fv is None else f'{fv:.1f}':>8} "
                      f"(n={mf_n.get((year, product), 0)})  {d}")
            print(f"     ALL  series={tot_mine:9.3f}  manufacturers={tot_mf:8.1f}  diff {tot_mine - tot_mf:+.3f} kt")

    print("\nTABLES NOT PARSED / ANOMALIES")
    if UNPARSED:
        for u in UNPARSED:
            print("  " + u)
    else:
        print("  none")
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv[1:]))
