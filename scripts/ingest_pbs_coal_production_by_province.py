"""ANNUAL coal production by province from the held PBS "Minerals Production Data" editions.

WHY THIS EXISTS. The coal balance (data/activity/industry/coal_supply.csv) carries a national
PBS extraction lane but no by-field split, and Thar lignite has no published production series
of its own. Sindh's coal production in these PBS tables is the public proxy for Thar - before
FY2018-19 Sindh coal is Lakhra/Sonda/Jherruck, after it the Thar Block-II open pit dominates -
so the YEAR LABEL on every Sindh row has to be exactly the year PBS printed, never the year in
the file name.

THE FILE NAME IS NOT THE YEAR. Eight editions are held under data/raw/pbs/minerals/. Seven
print one fiscal year each; pbs_minerals_2020_21.xlsx is a COMPILATION whose 'mineral
production' sheet stacks twenty-one year blocks, 2002-03 .. 2022-23, each under its own
"MINERALS PRODUCTION DATA <year>" title row. The monthly ingest (scripts/ingest_pbs_minerals.py)
tagged all of them with the file-name year; here every block is labelled from ITS OWN title row,
and the file-name year is never used for anything but the source_file column.

HOW THE COAL TABLE IS FOUND, and why not by name alone. PBS prints the mineral name vertically
centred against its group, so in the PDFs the word COAL lands on a province line, on a line of
its own, or - FY2016-17 - on the LAST line of one page while the first two province rows sit
above it and the remaining rows on the next page after a repeated header. The group is therefore
assembled from the COAL label OUTWARDS: backwards over province rows until the previous
mineral's Total row, forwards over province rows (skipping repeated headers and a repeated
label) to the group's own Total row. The provinces must then sum to that Total row within one
tonne, which is what proves the rows were the coal group's and not a neighbour's.

WHAT "PRINTED TOTAL" MEANS IN EACH FORMAT - recorded per row in annual_basis:
  printed_literal              PDF year-total column, a literal PBS printed
  summed_12_printed_months     FY2021-22 PDF prints NO year-total column; the annual figure is
                               the sum of the twelve printed months and is marked as such
  workbook_formula_cached      xlsx year totals and Total rows are =SUM() formulas; the cached
                               value is read and re-computed from the twelve months, so the
                               closure is by construction and is reported as such

Absences stay EMPTY: a printed "-" is kept in printed_value with an empty production_tonnes;
a printed "0" is kept as the number PBS printed. Where two files print the same fiscal year
both rows are kept for inter-edition comparison; nothing is averaged.

Usage:  python3 scripts/ingest_pbs_coal_production_by_province.py
Writes: data/activity/industry/coal_production_by_province.csv
Prints: the fiscal_year x province matrix and a cross-check against coal_supply.csv
"""

from pkinv.assets import asset_path
import csv
import glob
import os
import re
import subprocess
import sys

from pkinv.paths import ROOT

RAW = asset_path(ROOT, "data", "raw", "pbs", "minerals")
OUT = asset_path(ROOT, "data", "activity", "industry", "coal_production_by_province.csv")
COAL_SUPPLY = asset_path(ROOT, "data", "activity", "industry", "coal_supply.csv")

CLOSURE_TOLERANCE = 1.0
MONTHS = 12

TITLE_RE = re.compile(r"MINERALS\s+PRODUCTION\s+DATA\s+(.+?)\s*\(\s*unit\s+([^)]*?)\s*\)", re.I)
YEAR_RE = re.compile(r"(\d{4})\s*-\s*(\d{2})")
MONTH_RE = re.compile(r"^(jul|aug|sep|oct|nov|dec|jan|feb|mar|apr|may|jun)[a-z]*\.?,?\s*\d{0,3}$", re.I)
NUMBER_RE = re.compile(r"^-?[\d,]+(?:\.\d+)?$")

CANONICAL_PROVINCE = {
    "punjab": "Punjab",
    "sindh": "Sindh", "sind": "Sindh",
    "kpk": "KP", "k.p.k": "KP", "k.p.k.": "KP", "kp": "KP", "khyber pakhtunkhwa": "KP",
    "nwfp": "KP", "n.w.f.p": "KP", "n.w.f.p.": "KP",
    "balochistan": "Balochistan", "baluchistan": "Balochistan",
    "fata": "FATA", "merged districts": "FATA", "merged areas": "FATA",
    "ajk": "AJK", "azad kashmir": "AJK", "azad jammu & kashmir": "AJK",
    "gb": "GB", "gilgit baltistan": "GB", "gilgit-baltistan": "GB",
    "total": "Pakistan", "grand total": "Pakistan", "grand-total": "Pakistan",
    "pakistan": "Pakistan",
}

FIELDS = ["fiscal_year", "province", "province_canonical", "production_tonnes", "printed_value",
          "unit_as_printed", "months_sum_tonnes", "annual_basis", "source_file", "sheet_or_page",
          "printed_year_label", "status", "closure_residual_tonnes", "note"]


def canonical_province(text):
    key = re.sub(r"\s+", " ", str(text).strip().lower()).rstrip(".")
    return CANONICAL_PROVINCE.get(key) or CANONICAL_PROVINCE.get(key + ".")


def fiscal_year_of_label(label):
    found = YEAR_RE.search(label)
    if not found:
        return None
    start, end = int(found.group(1)), int(found.group(2))
    if (start + 1) % 100 != end:
        return None
    return "FY%d-%02d" % (start, end)


def unit_factor(unit_text):
    """Tonnes per printed unit. PBS prints '( unit MT )'; a '000' prefix would be thousands."""
    text = unit_text.strip().lower()
    if "000" in text or "thousand" in text:
        return 1000.0
    if text in ("mt", "m.t", "m.t.", "tonnes", "tons", "metric tons", "metric tonnes"):
        return 1.0
    raise ValueError("unrecognised unit %r" % unit_text)


def parse_number(token):
    """(float or None, printed text). '-' and blank are absences -> None, never 0."""
    if token is None:
        return None, ""
    if isinstance(token, (int, float)):
        return float(token), repr(token) if isinstance(token, float) else str(token)
    text = str(token).strip()
    if text in ("", "-", "--", "---", "—"):
        return None, text
    cleaned = text.replace(",", "")
    if NUMBER_RE.match(cleaned):
        return float(cleaned), text
    return None, text


# ----------------------------------------------------------------------------- PDF editions

def _pdf_pages(path):
    result = subprocess.run(["pdftotext", "-layout", path, "-"],
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=True)
    text = result.stdout.decode("utf-8", "replace")
    # the ligature/control-byte hazard from CLAUDE.md: strip control bytes before matching
    text = re.sub(r"[\x00-\x08\x0b\x0e-\x1f]", "", text)
    lines = []
    for page_index, page in enumerate(text.split("\f"), start=1):
        for line in page.splitlines():
            lines.append((page_index, line))
    return lines


PROVINCE_LINE_RE = re.compile(
    r"^\s*(?:\d{1,2}\s+)?(?:[A-Z][A-Z\-\. ]*?\s{2,})?"
    r"(Punjab|Sindh|Sind|KPK|K\.P\.K\.?|Khyber Pakhtunkhwa|N\.W\.F\.P\.?|NWFP|Balochistan|"
    r"Baluchistan|FATA|Fata|AJK|Azad Kashmir|Gilgit Baltistan|GB|Total|Grand[- ]Total)\s+(.*\S)\s*$")


def _province_row(line):
    """(printed province, [tokens]) if the line is a province/Total row with numeric cells."""
    found = PROVINCE_LINE_RE.match(line)
    if not found:
        return None
    province, rest = found.group(1), found.group(2)
    tokens = rest.split()
    if not tokens or not all(NUMBER_RE.match(t.replace(",", "")) or t in ("-", "--", "---")
                             for t in tokens):
        return None
    numeric = [t for t in tokens if t not in ("-", "--", "---")]
    if len(numeric) < 6:  # a header wrap or a stray label, not a data row
        return None
    return province, tokens


def _is_header_noise(line):
    text = line.strip()
    if not text:
        return True
    if TITLE_RE.search(text):
        return True
    lowered = text.lower()
    return (lowered.startswith(("name of", "provinces", "grand-", "s.no", "s.", "mineral", "n", "o"))
            and not _province_row(line)) or lowered in ("total", "coal")


def parse_pdf(path):
    source = os.path.basename(path)
    lines = _pdf_pages(path)
    titles = [(i, TITLE_RE.search(l)) for i, (_, l) in enumerate(lines) if TITLE_RE.search(l)]
    if not titles:
        raise RuntimeError("%s: no MINERALS PRODUCTION DATA title" % source)
    labels = {re.sub(r"\s+", " ", m.group(1)).strip() for _, m in titles}
    units = {m.group(2).strip() for _, m in titles}
    if len(labels) != 1 or len(units) != 1:
        raise RuntimeError("%s: mixed year labels %s / units %s" % (source, labels, units))
    label, unit = labels.pop(), units.pop()

    coal_index = next(i for i, (_, l) in enumerate(lines) if re.search(r"\bCOAL\b", l)
                      and not re.search(r"\bCOAL\s+(TAR|GAS)", l, re.I))

    group = []
    # the label line itself may carry a province row (FY2021-22, FY2022-23, FY2023-24)
    own = _province_row(re.sub(r"\bCOAL\b", "  ", lines[coal_index][1]))
    if own:
        group.append((coal_index, own))
    # backwards to the previous mineral's Total row
    i = coal_index - 1
    while i >= 0:
        row = _province_row(lines[i][1])
        if row:
            if canonical_province(row[0]) == "Pakistan":
                break
            group.insert(0, (i, row))
        elif not _is_header_noise(lines[i][1]):
            break
        i -= 1
    # forwards to the group's own Total row
    i = coal_index + 1
    while i < len(lines):
        row = _province_row(re.sub(r"\bCOAL\b", "  ", lines[i][1]))
        if row:
            group.append((i, row))
            if canonical_province(row[0]) == "Pakistan":
                break
        elif not _is_header_noise(lines[i][1]):
            break
        i += 1

    pages = sorted({lines[i][0] for i, _ in group})
    where = "p.%s" % ("-".join(str(p) for p in (pages[0], pages[-1])) if len(pages) > 1
                      else pages[0])
    if len(pages) > 1:
        where += " (table split across page break)"

    widths = [len(tokens) for _, (_, tokens) in group]
    width = max(set(widths), key=widths.count)
    has_total_column = width == MONTHS + 1
    rows = []
    for _, (province, tokens) in group:
        if len(tokens) != width:
            raise RuntimeError("%s %s row has %d cells, edition prints %d"
                               % (source, province, len(tokens), width))
        month_tokens = tokens[:MONTHS]
        month_values = [parse_number(t)[0] for t in month_tokens]
        months_sum = sum(v for v in month_values if v is not None) if any(
            v is not None for v in month_values) else None
        if has_total_column:
            value, printed = parse_number(tokens[MONTHS])
            basis = "printed_literal"
        else:
            value, printed = months_sum, ""
            basis = "summed_12_printed_months"
        rows.append({"province": province, "value": value, "printed": printed,
                     "months_sum": months_sum, "basis": basis})
    return [{"label": label, "unit": unit, "where": where, "rows": rows, "source": source}]


# ----------------------------------------------------------------------------- xlsx editions

def parse_xlsx(path):
    import openpyxl
    source = os.path.basename(path)
    workbook = openpyxl.load_workbook(path, data_only=True)
    tables = []
    for sheet in workbook.worksheets:
        grid = [[c for c in row] for row in sheet.iter_rows(values_only=True)]
        label = unit = None
        month_cols, total_col, name_cols, prov_col = [], None, [], None
        r = 0
        while r < len(grid):
            row = grid[r]
            joined = " ".join(str(v) for v in row if v is not None)
            title = TITLE_RE.search(joined)
            if title:
                label = re.sub(r"\s+", " ", title.group(1)).strip()
                unit = title.group(2).strip()
                month_cols, total_col = [], None
                r += 1
                continue
            texts = [(c, str(v).strip()) for c, v in enumerate(row) if isinstance(v, str)]
            if any(t.lower() == "provinces" for _, t in texts):
                prov_col = next(c for c, t in texts if t.lower() == "provinces")
                month_cols = [c for c, t in texts if MONTH_RE.match(t)]
                total_col = next((c for c, t in texts if re.search(r"total", t, re.I)
                                  and not re.search(r"quarter", t, re.I)), None)
                name_cols = [c for c, t in texts if re.match(r"name\s+of\s+mineral", t, re.I)]
                r += 1
                continue
            is_coal = any(isinstance(row[c], str) and row[c].strip().upper() == "COAL"
                          for c in name_cols) if name_cols else False
            if is_coal and label and len(month_cols) == MONTHS:
                rows, start = [], r
                while r < len(grid):
                    cells = grid[r]
                    province = cells[prov_col] if prov_col < len(cells) else None
                    if not isinstance(province, str) or not canonical_province(province):
                        break
                    month_values = [parse_number(cells[c])[0] for c in month_cols]
                    months_sum = sum(v for v in month_values if v is not None) if any(
                        v is not None for v in month_values) else None
                    if total_col is not None:
                        value, printed = parse_number(cells[total_col])
                        basis = "workbook_formula_cached"
                    else:
                        value, printed, basis = months_sum, "", "summed_12_printed_months"
                    rows.append({"province": province.strip(), "value": value,
                                 "printed": printed, "months_sum": months_sum, "basis": basis})
                    r += 1
                    if canonical_province(province) == "Pakistan":
                        break
                tables.append({"label": label, "unit": unit, "source": source,
                               "where": "sheet '%s' rows %d-%d" % (sheet.title, start + 1, r),
                               "rows": rows})
                continue
            r += 1
    workbook.close()
    return tables


# ----------------------------------------------------------------------------- assembly

def assemble(table):
    label, unit = table["label"], table["unit"]
    fiscal_year = fiscal_year_of_label(label)
    factor = unit_factor(unit)
    rows = table["rows"]
    total = [r for r in rows if canonical_province(r["province"]) == "Pakistan"]
    provinces = [r for r in rows if canonical_province(r["province"]) != "Pakistan"]
    if len(total) != 1:
        raise RuntimeError("%s %s: %d Total rows in coal group" % (table["source"], label, len(total)))
    total = total[0]
    provinces_sum = sum(r["value"] for r in provinces if r["value"] is not None) * factor
    pakistan = None if total["value"] is None else total["value"] * factor
    residual = None if pakistan is None else provinces_sum - pakistan
    closed = residual is not None and abs(residual) <= CLOSURE_TOLERANCE
    status = "verified" if closed else "verified-open-residual"
    if fiscal_year is None:
        status = "unlabelled"

    notes = []
    if total["basis"] == "workbook_formula_cached":
        notes.append("xlsx year totals and Total row are =SUM() formulas: closure is by "
                     "construction; cached values re-summed from the twelve months")
    if total["basis"] == "summed_12_printed_months":
        notes.append("edition prints no year-total column; annual = sum of 12 printed months")
    for r in rows:
        if r["value"] is not None and r["months_sum"] is not None \
                and abs(r["value"] - r["months_sum"]) > CLOSURE_TOLERANCE:
            notes.append("%s: 12 months sum %.2f vs year total %.2f"
                         % (r["province"], r["months_sum"], r["value"]))
    seen = {canonical_province(r["province"]) for r in provinces}
    if "FATA" not in seen and fiscal_year and fiscal_year >= "FY2018-19":
        notes.append("no FATA row printed (merged into KP after 2018)")

    out = []
    for r in rows:
        value = None if r["value"] is None else r["value"] * factor
        out.append({
            "fiscal_year": fiscal_year or "",
            "province": r["province"],
            "province_canonical": canonical_province(r["province"]),
            "production_tonnes": "" if value is None else ("%.0f" % value if float(value).is_integer()
                                                           else "%.2f" % value),
            "printed_value": r["printed"],
            "unit_as_printed": unit,
            "months_sum_tonnes": "" if r["months_sum"] is None else (
                "%.0f" % (r["months_sum"] * factor) if float(r["months_sum"] * factor).is_integer()
                else "%.2f" % (r["months_sum"] * factor)),
            "annual_basis": r["basis"],
            "source_file": table["source"],
            "sheet_or_page": table["where"],
            "printed_year_label": label,
            "status": status,
            "closure_residual_tonnes": "" if residual is None else "%.2f" % residual,
            "note": "; ".join(notes),
        })
    return out


HEADER = """\
# PBS coal production by PROVINCE, annual, in tonnes - every fiscal year the held PBS "Minerals
# Production Data" editions print, labelled from EACH TABLE'S OWN TITLE ROW (never the file name).
# PURPOSE: Sindh's coal production is the public proxy for Thar lignite - the by-field production
#   the coal balance (coal_supply.csv) does not carry - so the year labels here must be exact.
# FILES (data/raw/pbs/minerals/): pbs_minerals_2016_17.pdf, 2021_22.pdf, 2022_23.pdf, 2023_24.pdf
#   (one year each, layout PDFs); pbs_minerals_2017_18.xlsx, 2018_19.xlsx, 2019_20.xlsx (one year
#   each); pbs_minerals_2020_21.xlsx is a COMPILATION whose 'mineral production' sheet stacks 21
#   year blocks 2002-03..2022-23 - each block carries its own printed label here.
# CLOSURE RULE: the province rows must sum to the table's own Total row within 1 tonne ->
#   status=verified; otherwise verified-open-residual with closure_residual_tonnes = provinces
#   minus Total. annual_basis says what the Total is: printed_literal (PDF literal),
#   summed_12_printed_months (FY2021-22 PDF prints no year-total column), or
#   workbook_formula_cached (xlsx =SUM() formulas - closure by construction, cached values
#   re-summed from the twelve months as a freshness check).
# ABSENCES are EMPTY, never 0: a printed '-' is kept in printed_value with production_tonnes
#   empty; a printed 0 is the number PBS printed. unit_as_printed is PBS's '( unit MT )' =
#   metric tonnes, factor 1. Where two files print the same fiscal year BOTH rows are kept
#   (inter-edition comparison; nothing is averaged). KPK -> KP; FATA is printed separately
#   through 2017-18 and is absent (merged into KP) from 2018-19.
# Built by scripts/ingest_pbs_coal_production_by_province.py.
"""


def main():
    files = sorted(glob.glob(asset_path(RAW, "pbs_minerals_*.pdf"))
                   + glob.glob(asset_path(RAW, "pbs_minerals_*.xlsx")))
    if not files:
        print("no minerals files under %s" % RAW)
        return 1
    tables = []
    for path in files:
        tables += parse_pdf(path) if path.endswith(".pdf") else parse_xlsx(path)

    # Within ONE workbook, working sheets that re-state the primary sheet's year are cross-checks,
    # not rows: pbs_minerals_2017_18.xlsx carries '17-18' (primary, FATA separate) plus 'Sheet1'
    # (quarterly working sheet, FATA folded into KPK). The first sheet is kept; the rest are
    # compared on the Pakistan total and reported.
    kept, secondary = [], []
    seen = set()
    for table in tables:
        key = (table["source"], table["label"])
        (secondary if key in seen else kept).append(table)
        seen.add(key)

    rows = []
    for table in kept:
        rows += assemble(table)
    rows.sort(key=lambda r: (r["fiscal_year"], r["source_file"],
                             ["Punjab", "Sindh", "KP", "FATA", "Balochistan", "AJK", "GB",
                              "Pakistan"].index(r["province_canonical"])))

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write(HEADER)
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print("PBS coal by province -> %s  (%d rows, %d tables from %d files)"
          % (os.path.relpath(OUT, ROOT), len(rows), len(kept), len(files)))

    # ------------------------------------------------------------------ the matrix
    provinces = ["Punjab", "Sindh", "KP", "FATA", "Balochistan", "Pakistan"]
    print("\nfiscal_year x province, tonnes (one line per source table)")
    print("%-10s %-26s %-12s" % ("fy", "source", "label") + "".join("%14s" % p for p in provinces)
          + "  %-22s %s" % ("status", "residual"))
    by_table = {}
    for r in rows:
        by_table.setdefault((r["fiscal_year"], r["source_file"], r["printed_year_label"]), {})[
            r["province_canonical"]] = r
    for (fy, src, label), cells in sorted(by_table.items()):
        any_row = next(iter(cells.values()))
        line = "%-10s %-26s %-12s" % (fy, src, label[:12])
        for p in provinces:
            cell = cells.get(p)
            line += "%14s" % ("" if cell is None else (cell["production_tonnes"] or "-"))
        line += "  %-22s %s" % (any_row["status"], any_row["closure_residual_tonnes"])
        print(line)

    # ------------------------------------------------------------------ secondary sheets
    for table in secondary:
        primary = next(t for t in kept if (t["source"], t["label"]) == (table["source"], table["label"]))
        p_total = next(r["value"] for r in primary["rows"] if canonical_province(r["province"]) == "Pakistan")
        s_total = next(r["value"] for r in table["rows"] if canonical_province(r["province"]) == "Pakistan")
        s_prov = {canonical_province(r["province"]): r["value"] for r in table["rows"]}
        print("\nsecondary sheet NOT carried: %s %s %s -> Pakistan %.0f vs primary %.0f (%s); provinces %s"
              % (table["source"], table["where"], table["label"], s_total, p_total,
                 "agree" if abs(s_total - p_total) <= CLOSURE_TOLERANCE else "DISAGREE",
                 {k: v for k, v in s_prov.items() if k != "Pakistan"}))

    # ------------------------------------------------------------------ cross-check
    print("\ncross-check: Pakistan total here (kt) minus coal_supply.csv coal_production_kt_pbs_extraction")
    supply = {}
    with open(COAL_SUPPLY, encoding="utf-8") as handle:
        for rec in csv.DictReader(l for l in handle if not l.startswith("#")):
            if rec["coal_production_kt_pbs_extraction"].strip():
                supply["FY" + rec["fiscal_year"]] = float(rec["coal_production_kt_pbs_extraction"])
    print("%-10s %-26s %14s %12s %10s" % ("fy", "source", "pbs_here_kt", "supply_kt", "diff_kt"))
    for (fy, src, label), cells in sorted(by_table.items()):
        pk = cells.get("Pakistan")
        if pk is None or not pk["production_tonnes"]:
            continue
        here_kt = float(pk["production_tonnes"]) / 1000.0
        ref = supply.get(fy)
        print("%-10s %-26s %14.3f %12s %10s" % (
            fy, src, here_kt, "" if ref is None else "%.0f" % ref,
            "n/a" if ref is None else "%+.3f" % (here_kt - ref)))

    anomalies = [r for r in rows if r["status"] != "verified"]
    print("\nrows not 'verified': %d" % len(anomalies))
    for r in anomalies:
        if r["province_canonical"] == "Pakistan":
            print("  %s %s %s -> %s residual %s" % (r["fiscal_year"] or "UNLABELLED", r["source_file"],
                                                   r["printed_year_label"], r["status"],
                                                   r["closure_residual_tonnes"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
