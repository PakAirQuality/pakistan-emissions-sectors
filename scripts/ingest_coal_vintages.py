"""Every published estimate of HDIP's coal-by-sector allocation, ONE ROW PER PRINT - the source-vintage
ledger the industrial-coal reconstruction stands on (rc53 Wave A1).

WHY. The same reference period is printed more than once, and the prints differ. Economic Survey
2023-24 Table 14.11 gives July-March FY2024 as brick 2,572.26 / cement-others 2,800.00 kt; Economic
Survey 2024-25 Table 14.10 reprints the SAME nine months as 1,072.3 / 4,300 with power and the total
unchanged - a reallocation of 1,500 kt between users, not a physical change. The full-year FY2023-24
print moved 1,564 -> 1,129 between Supplement editions; FY2024-25 moved 3,483/5,155 (Supplement
2024-25) -> 3,616/5,022 (Survey 2025-26 annex) with an identical total. A series that books "the
latest final row" hides all of this. This table keeps every print with its edition, table, page,
reference period, printed label, unit and provisional mark, so that

    reference year  !=  publication year  !=  length of the reporting period

is enforced by columns. Nothing here is a selection; the booking policy lives in
data/coal_booking_policy.csv and the engine reads that.

SOURCES (all held; sha256 in data/raw_manifest.csv):
  Statistical Supplement 2023-24 ch.14, Table 14.1 sec. 4 Coal (000 metric ton)**   [** : Estimated]
  Statistical Supplement 2024-25, Table 14.1 sec. 4                                 [** : Estimated]
  Economic Survey 2025-26 ch.14 Energy: statistical annex Table 14.1 sec. 4 (full years FY2014-15..
    FY2024-25, then July-March FY2025** and FY2026(P)***) and narrative Table 14.10 (July-March)
  Economic Survey 2023-24 ch.14 Energy: Table 14.11 (July-March FY2024)
  Economic Survey 2024-25 ch.14 Energy: Table 14.10 (July-March FY2024 REPRINTED, and FY2025)
  PBS Compendium on Environment Statistics 2015 / 2020, Table A-45 (HDIP PEY reprint, tonnes) -
    via data/activity/industry/coal_by_sector_pey_compendium.csv
  Pakistan Energy Yearbook 2018 / 2021 / 2022 editions, Table 4.4 brick-kiln row (the PEY PDFs are
    NOT held; cells transcribed from secondary carriers, data/activity/industry/brick_kiln_coal.csv)

LABELS. The Supplement prints the second industrial column as "Cement"; the Survey as "Cement/Others";
the PEY/Compendium as "Cement/Other Industry". The printed label is carried beside the mapped sector.
The Compendium carries two columns the Supplement drops: Domestic (household) and Pak Steel.

CLOSURE. Every full-table row is checked against its printed total (|residual| <= 1.5 kt allows the
integer-printed components of the later editions); the residual is carried, never absorbed.

Reads:  the five PDFs under data/raw/finance_division/ and the two ingests named above
Writes: data/activity/industry/coal_by_sector_vintages.csv
"""
import csv
import hashlib
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, ROOT  # noqa: E402

FD = asset_path(DATA, "raw", "finance_division")
DOCS = {
    "sup24": ("supplement_2023_24/Supl-14_E.pdf", "Finance Division", "Statistical Supplement 2023-24 ch.14 Energy", 2024),
    "sup25": ("supplement_2024_25/supplement_2024-25.pdf", "Finance Division", "Statistical Supplement 2024-25", 2025),
    "es24": ("survey_2023_24/14_Energy.pdf", "Finance Division", "Pakistan Economic Survey 2023-24 ch.14 Energy", 2024),
    "es25": ("survey_2024_25/14_Energy.pdf", "Finance Division", "Pakistan Economic Survey 2024-25 ch.14 Energy", 2025),
    "es26": ("survey_2025_26/14_Energy.pdf", "Finance Division", "Pakistan Economic Survey 2025-26 ch.14 Energy", 2026),
}
COMPENDIUM = asset_path(DATA, "activity", "industry", "coal_by_sector_pey_compendium.csv")
PEY_BRICK = asset_path(DATA, "activity", "industry", "brick_kiln_coal.csv")
OUT = asset_path(DATA, "activity", "industry", "coal_by_sector_vintages.csv")

FIELDS = ("estimate_id", "publisher", "publication", "edition_year", "table_id", "page",
          "reference_fiscal_year", "period_coverage", "months_covered", "sector_label_printed",
          "sector_mapped", "value", "unit", "provisional_flag", "closure_residual", "status",
          "source_file", "sha256_16", "note")
# the annex/supplement coal block: household, power, brick, cement, other govt, total
ANNEX_LABELS = (("Household", "household"), ("Power", "power"), ("Brick Kilns", "brick_kilns"),
                (None, "cement_other"), ("Other Govt.", "other_govt"), ("Total", "total"))
FIRST_YEAR = "2013-14"                      # earlier years live in the Compendium ingest
TOL_KT = 1.5


def _text(path):
    out = subprocess.run(["pdftotext", "-layout", path, "-"], check=True, capture_output=True).stdout
    return out.decode("utf-8", "replace")


def _pages(text):
    return text.split("\f")


def _sha16(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def _num(tok):
    tok = tok.replace(",", "").strip()
    if tok in ("-", "", "–"):
        return None
    return float(tok)


def _coal_block_rows(page_text):
    """Rows of the 'Coal (000 metric ton)' block on a Supplement/annex page: the LAST six numeric
    tokens of each fiscal-year line are the coal block (the electricity block precedes it)."""
    rows = []
    for line in page_text.split("\n"):
        line = re.sub(r"[\x00-\x08\x0b\x0e-\x1f]", "", line)
        m = re.match(r"^\s*(20\d\d-\d\d)\s*(P|\*\*\*?|\(P\)\*{0,3})?\s+(.*)$", line)
        if not m:
            continue
        toks = re.findall(r"-(?=\s|$)|\d[\d,]*\.?\d*", m.group(3))
        if len(toks) < 6:
            continue
        # the electricity block (GWh) ends at the row's largest number - its Total (80,000+ GWh
        # against coal totals below 30,000 kt); the coal block is everything after it. A blank
        # Other Govt. cell (later editions print nothing, not '-') leaves five tokens.
        vals = [_num(t) for t in toks]
        anchor = max(range(len(vals)), key=lambda i: (vals[i] or 0))
        coal = toks[anchor + 1:]
        if len(coal) == 5:
            coal = coal[:4] + ["-"] + coal[4:]
        if len(coal) != 6:
            continue
        rows.append((m.group(1), (m.group(2) or "").strip(), coal))
    return rows


def _find_page(pages, pattern):
    """1-based page number of the first page matching `pattern` (the table header), and its text."""
    for i, pg in enumerate(pages):
        if re.search(pattern, pg):
            return i + 1, pg
    raise SystemExit("no page matches %r" % pattern)


def _fmt(v):
    return "" if v is None else ("%.4f" % v).rstrip("0").rstrip(".")


def _annex_rows(key, cement_label, table_id, page_no, page_text, july_march_after=None):
    doc, publisher, publication, ed = DOCS[key]
    rel = asset_path("data", "raw", "finance_division", doc)
    sha = _sha16(asset_path(FD, doc))
    out = []
    coverage = "full_year"
    for fy, flag, toks in _coal_block_rows(page_text):
        if fy < FIRST_YEAR:
            continue
        if july_march_after and fy == july_march_after[0] and flag == july_march_after[1]:
            coverage = "july_march"
        elif july_march_after and coverage == "july_march" and fy > july_march_after[0]:
            coverage = "july_march"
        vals = [_num(t) for t in toks]
        comps = [v for v in vals[:5] if v is not None]
        total = vals[5]
        residual = "" if total is None else "%.1f" % (sum(comps) - total)
        if total is not None and abs(sum(comps) - total) > TOL_KT:
            raise SystemExit("%s %s %s: components %.1f vs printed total %.1f" % (key, fy, flag, sum(comps), total))
        months = "9" if coverage == "july_march" else "12"
        prov = "P" if "P" in flag else ("asterisked" if "*" in flag else "final")
        for (label, mapped), v in zip(ANNEX_LABELS, vals):
            printed = cement_label if mapped == "cement_other" else label
            out.append({
                "estimate_id": "%s:%s:%s:%s" % (key, table_id.replace(" ", ""), fy + ("JM" if coverage == "july_march" else ""), mapped),
                "publisher": publisher, "publication": publication, "edition_year": ed,
                "table_id": table_id, "page": page_no, "reference_fiscal_year": fy,
                "period_coverage": coverage, "months_covered": months,
                "sector_label_printed": printed, "sector_mapped": mapped,
                "value": _fmt(v), "unit": "000 metric ton",
                "provisional_flag": prov, "closure_residual": residual if mapped == "total" else "",
                "status": "verified" if v is not None else "not_printed",
                "source_file": rel, "sha256_16": sha,
                "note": ("printed '-' (no consumption booked)" if v is None else
                         ("the row's ** / *** footnotes concern the electricity block (AJK data), not coal"
                          if coverage == "july_march" else "")),
            })
    return out


def _narrative_rows(key, table_id, page_no, page_text, columns):
    """The narrative July-March table: `columns` = ((reference_fy, column_index), ...)."""
    doc, publisher, publication, ed = DOCS[key]
    rel = asset_path("data", "raw", "finance_division", doc)
    sha = _sha16(asset_path(FD, doc))
    labels = {"Power": "power", "Brick Kilns": "brick_kilns", "Cement/Others": "cement_other",
              "Household": "household", "Total": "total"}
    found = {}
    for line in page_text.split("\n"):
        line = re.sub(r"[\x00-\x08\x0b\x0e-\x1f]", "", line)
        for printed, mapped in labels.items():
            if re.match(r"^\s*%s\b" % re.escape(printed), line):
                toks = re.findall(r"-(?=\s|$)|\d[\d,]*\.?\d*", line[len(printed) + line.find(printed):])
                found[mapped] = (printed, toks)
    out = []
    for fy, col in columns:
        comps, total = [], None
        rows = []
        for mapped in ("household", "power", "brick_kilns", "cement_other", "total"):
            if mapped not in found:
                continue
            printed, toks = found[mapped]
            if mapped == "total":
                # the Total line prints values only (a trailing 100.0 share at most): value columns
                # are at col // 2 once the share tokens are dropped
                toks = [t for t in toks if _num(t) not in (100.0,)]
                idx = col // 2
            else:
                idx = col
            v = _num(toks[idx]) if idx < len(toks) else None
            if mapped == "total":
                total = v
            elif v is not None:
                comps.append(v)
            rows.append((printed, mapped, v))
        residual = "" if total is None else "%.2f" % (sum(comps) - total)
        if total is not None and abs(sum(comps) - total) > TOL_KT:
            raise SystemExit("%s %s: narrative components %.2f vs total %.2f" % (key, fy, sum(comps), total))
        for printed, mapped, v in rows:
            out.append({
                "estimate_id": "%s:%s:%sJM:%s" % (key, table_id.replace(" ", ""), fy, mapped),
                "publisher": publisher, "publication": publication, "edition_year": ed,
                "table_id": table_id, "page": page_no, "reference_fiscal_year": fy,
                "period_coverage": "july_march", "months_covered": "9",
                "sector_label_printed": printed, "sector_mapped": mapped,
                "value": _fmt(v), "unit": "000 metric tonnes",
                "provisional_flag": "final", "closure_residual": residual if mapped == "total" else "",
                "status": "verified" if v is not None else "not_printed",
                "source_file": rel, "sha256_16": sha,
                "note": "printed '-'" if v is None else "",
            })
    return out


def _compendium_rows():
    out = []
    with open(COMPENDIUM, encoding="utf-8") as h:
        for r in csv.DictReader(l for l in h if not l.startswith("#")):
            fy = r["fiscal_year"].replace("FY", "")
            if fy < FIRST_YEAR:
                continue
            ed = r["compendium_edition"]
            cols = (("Power (WAPDA)", "power", "power_wapda_t"), ("Brick-Kiln Industry*", "brick_kilns", "brick_kiln_t"),
                    ("Domestic", "household", "domestic_t"), ("Cement/Other Industry**", "cement_other", "cement_other_industry_t"),
                    ("Pak Steel***", "pak_steel", "pak_steel_t"), ("Total", "total", "total_printed_t"))
            for printed, mapped, col in cols:
                v = r[col]
                out.append({
                    "estimate_id": "comp%s:A-45:%s:%s" % (ed, fy, mapped),
                    "publisher": "Pakistan Bureau of Statistics (reprinting HDIP PEY)",
                    "publication": "Compendium on Environment Statistics %s" % ed, "edition_year": ed,
                    "table_id": r["table"], "page": "", "reference_fiscal_year": fy,
                    "period_coverage": "full_year", "months_covered": "12",
                    "sector_label_printed": printed, "sector_mapped": mapped,
                    "value": _fmt(None if v in ("", None) else float(v) / 1000.0), "unit": "000 metric ton (printed in tonnes)",
                    "provisional_flag": "asterisked" if mapped in ("brick_kilns", "cement_other", "pak_steel") else "final",
                    "closure_residual": _fmt(float(r["closure_residual_t"]) / 1000.0) if mapped == "total" and r["closure_residual_t"] else "",
                    "status": r["status"], "source_file": r["source_file"], "sha256_16": "",
                    "note": {"brick_kilns": r["footnote_brick"], "cement_other": r["footnote_cement_other"],
                             "pak_steel": r["footnote_pak_steel"]}.get(mapped, ""),
                })
    return out


def _pey_rows():
    out = []
    with open(PEY_BRICK, encoding="utf-8") as h:
        for r in csv.DictReader(l for l in h if not l.startswith("#")):
            y = int(r["fiscal_year"])
            fy = "%d-%02d" % (y - 1, y % 100)
            if fy < FIRST_YEAR:
                continue
            for ed in re.findall(r"20\d\d", r["edition_provenance"]):
                out.append({
                    "estimate_id": "pey%s:T4.4:%s:brick_kilns" % (ed, fy),
                    "publisher": "HDIP", "publication": "Pakistan Energy Yearbook %s" % ed, "edition_year": ed,
                    "table_id": "Table 4.4", "page": "", "reference_fiscal_year": fy,
                    "period_coverage": "full_year", "months_covered": "12",
                    "sector_label_printed": "Brick-Kiln Industry", "sector_mapped": "brick_kilns",
                    "value": _fmt(float(r["coal_tonnes"]) / 1000.0), "unit": "000 metric ton (printed in tonnes)",
                    "provisional_flag": "asterisked", "closure_residual": "",
                    "status": "transcribed_from_secondary", "source_file": PEY_BRICK.replace(ROOT + os.sep, ""),
                    "sha256_16": "", "note": "PEY PDF not held (gap pey-coal-table); %s" % r["note"],
                })
    return out


def build():
    rows = []
    COAL_HDR = r"Coal\s*\(000 metric ton"
    t = _pages(_text(asset_path(FD, DOCS["sup24"][0])))
    rows += _annex_rows("sup24", "Cement", "Table 14.1 sec.4", *_find_page(t, COAL_HDR))
    t = _pages(_text(asset_path(FD, DOCS["sup25"][0])))
    rows += _annex_rows("sup25", "Cement", "Table 14.1 sec.4", *_find_page(t, COAL_HDR))
    t = _pages(_text(asset_path(FD, DOCS["es26"][0])))
    rows += _annex_rows("es26", "Cement", "annex Table 14.1 sec.4", *_find_page(t, COAL_HDR), july_march_after=("2024-25", "**"))
    rows += _narrative_rows("es26", "Table 14.10", *_find_page(t, r"Table 14\.10: Sector-wise Consumption of Coal"), columns=(("2024-25", 0), ("2025-26", 2)))
    t = _pages(_text(asset_path(FD, DOCS["es24"][0])))
    rows += _narrative_rows("es24", "Table 14.11", *_find_page(t, r"Table 14\.11: Sector-wise Consumption of Coal"), columns=(("2023-24", 0),))
    t = _pages(_text(asset_path(FD, DOCS["es25"][0])))
    rows += _narrative_rows("es25", "Table 14.10", *_find_page(t, r"Table 14\.10: Sector-wise Consumption of Coal"), columns=(("2023-24", 0), ("2024-25", 2)))
    rows += _compendium_rows()
    rows += _pey_rows()
    ids = [r["estimate_id"] for r in rows]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        raise SystemExit("duplicate estimate ids: %s" % sorted(dup)[:5])
    return rows


HEADER = """\
# EVERY PUBLISHED ESTIMATE OF HDIP'S COAL-BY-SECTOR ALLOCATION, ONE ROW PER PRINT (rc53 Wave A1).
# Reference year != publication year != reporting-period length: all three are columns. Values are kt
# (000 metric ton) as printed; Compendium/PEY tonnes are divided by 1000 (unit column says so). The
# printed sector label sits beside the mapped sector ('Cement' / 'Cement/Others' / 'Cement/Other
# Industry' are ONE HDIP column). provisional_flag: P = the edition's own provisional mark; asterisked =
# the publisher's '**: Estimated' / residual footnote; final = neither. closure_residual on the total
# row = sum of printed components minus printed total (carried, never absorbed). Nothing here selects a
# value; data/coal_booking_policy.csv does. Generated by scripts/ingest_coal_vintages.py.
"""


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    by_doc = {}
    for r in rows:
        by_doc[r["publication"]] = by_doc.get(r["publication"], 0) + 1
    print("coal vintages -> %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(rows)))
    for k, v in sorted(by_doc.items()):
        print("  %-60s %4d" % (k, v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
