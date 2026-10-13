"""Re-read the hand-typed cells of the activity files from the documents they were typed from.

WHY. 80 committed activity CSVs were typed by hand from held documents (rc36 presence
audit). Their documents are hashed, so the bytes a number was read FROM are verifiable; the
reading itself is not - only two files (the OGRA 2020-21 scan via ocr_ogra_2020_21.py and
the cement rows of ippu/national_activity.csv via extract_psyb_cement.py) had any automated
comparison against their source, and both skip silently without pdftotext/tesseract. This
generalises that pattern into a register: one row per checked cell, saying which document,
which page or table, what the document says, what the CSV says, and how the document was
read. The sector passes populate it; this script re-runs every automatable row.

data/transcription_checks.csv columns:
  data_file        the committed activity file
  row_key          which row: the value of the file's FIRST column, or - where that
                   column does not identify a row - `column=value;column=value` pairs.
                   The fiscal series needs the second form (its first column is the year
                   and it carries eleven items per year); an ambiguous key is a failure,
                   never a silent first-match
  column           the checked column
  committed_value  what the CSV holds (re-read here from the file, not trusted from the row)
  document         the held document, repo-relative (sources/... or data/raw/...)
  locator          page number, table id, or "p12 T2.3 row Wheat" - enough for a person
  extracted_value  what the document says
  method           pdftotext | ocr | read   ("read" = a person re-read it; not re-run here)
  extractor        for pdftotext/ocr rows: a regex applied to the page text, group(1) is the value
  checked_on       ISO date
  document_scale   the multiplier from the DOCUMENT's units to the CSV's: 1000 where a
                   table publishes "000 hectares" or "thousand tonnes" against a CSV in
                   hectares or tonnes. Blank means 1. The scale is declared per row rather
                   than inferred, because inferring a factor of a thousand from a
                   disagreement of a thousand is how a real error gets absorbed.
  declared_by      empty, or the register that already explains a known document/CSV
                   difference (e.g. fiscal_activity.ANCHOR_PARITY_EXCEPTIONS) - such a row
                   is reported as declared, never as a disagreement

WHAT COUNTS AS A DISAGREEMENT. Numbers are compared after removing thousands separators
and unit suffixes; a difference beyond half an ulp at the CSV's printed precision fails.
A failure is reported with the document and locator; nothing is rewritten - a transcription
that disagrees with its document is a finding for a person, because either side may be the
error (the CSV, the locator, or a revised edition of the document).

Usage:  python3 scripts/check_transcriptions.py [--sector NAME] [--verbose]
Exit:   1 on any disagreement; skips (tool missing, document missing) are PRINTED per row
        and counted in the summary, never silent.
"""

from pkinv.assets import asset_path
import csv
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTER = asset_path(ROOT, "data", "transcription_checks.csv")
FIELDS = ("data_file", "row_key", "column", "committed_value", "document", "locator",
          "extracted_value", "method", "extractor", "document_scale", "checked_on",
          "declared_by")

_PAGE = re.compile(r"^p(\d+)")


def _rows(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(l for l in f if not l.startswith("#")))


def _find_row(table, row_key):
    """(row, None) or (None, reason). See row_key in the module docstring."""
    if "=" in row_key:
        want = dict(pair.split("=", 1) for pair in row_key.split(";"))
        missing = [k for k in want if k not in table[0]]
        if missing:
            return None, "row key names column(s) %s that do not exist" % missing
        hits = [t for t in table if all(t[k] == v for k, v in want.items())]
    else:
        first = list(table[0].keys())[0]
        hits = [t for t in table if t[first] == row_key]
    if not hits:
        return None, "row %r not found" % row_key
    if len(hits) > 1:
        return None, "row key %r matches %d rows" % (row_key, len(hits))
    return hits[0], None


def _number(s):
    s = (s or "").strip().replace(",", "").replace(" ", "").replace(" ", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    return float(m.group(0)) if m else None, m.group(0) if m else ""


_PAGES = {}


def _page_text(document, page, method):
    """The text of one page, cached: rendering it once per row would spawn one
    subprocess per CELL, and a register that grows to thousands of cells across ten
    sectors would make the suite unusable. Keyed by (document, page, method) because an
    OCR read of a page is a different text from a pdftotext read of it."""
    key = (document, page, method)
    if key not in _PAGES:
        _PAGES[key] = _render(document, page, method)
    return _PAGES[key]


def _render(document, page, method):
    src = asset_path(ROOT, document)
    if method == "pdftotext":
        if not shutil.which("pdftotext"):
            return None, "pdftotext not installed"
        out = subprocess.run(["pdftotext", "-layout", "-f", str(page), "-l", str(page),
                              src, "-"], capture_output=True, text=True)
        return out.stdout, None
    if method == "ocr":
        for tool in ("pdftoppm", "tesseract"):
            if not shutil.which(tool):
                return None, "%s not installed" % tool
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            stem = asset_path(tmp, "page")
            subprocess.run(["pdftoppm", "-r", "300", "-f", str(page), "-l", str(page),
                            "-png", src, stem], check=True, capture_output=True)
            png = next(asset_path(tmp, n) for n in sorted(os.listdir(tmp)) if n.endswith(".png"))
            out = subprocess.run(["tesseract", png, "-", "--psm", "6"],
                                 capture_output=True, text=True)
            return out.stdout, None
    return None, "method %r is not re-run here" % method


def check(sector=None, verbose=False):
    register = _rows(REGISTER)
    if sector:
        register = [r for r in register if ("/%s/" % sector) in r["data_file"]
                    or r["data_file"].endswith("/%s.csv" % sector)]
    ok, bad, skipped, read_only, declared = 0, [], [], 0, []
    csv_cache = {}
    for r in register:
        if r["method"] == "read":
            read_only += 1
            continue
        path = asset_path(ROOT, r["data_file"])
        if r["data_file"] not in csv_cache:
            csv_cache[r["data_file"]] = _rows(path)
        table = csv_cache[r["data_file"]]
        row, why = _find_row(table, r["row_key"])
        if row is None:
            bad.append((r, "%s in %s" % (why, r["data_file"])))
            continue
        committed, printed = _number(row[r["column"]])
        if not os.path.exists(asset_path(ROOT, r["document"])):
            skipped.append((r, "document not held"))
            continue
        m = _PAGE.match(r["locator"])
        if not m:
            skipped.append((r, "locator %r names no page" % r["locator"]))
            continue
        text, why = _page_text(r["document"], int(m.group(1)), r["method"])
        if text is None:
            skipped.append((r, why))
            continue
        # re.M as well as re.S: a table extractor anchors on the start of the row's LINE
        # ("^BANNU DISTRICT\s+([\d,]+)"), and with re.S alone `^` matches only at the start
        # of the page - which reported all 719 agriculture rows as "extractor found
        # nothing" the first time the register was loaded.
        hit = re.search(r["extractor"], text, re.M | re.S)
        if not hit:
            bad.append((r, "extractor found nothing on %s" % r["locator"]))
            continue
        raw = hit.group(1).strip()
        # A dash is the census tables' "none reported". Read as zero ONLY when the
        # extractor explicitly admits it, so a stray dash matched by a loose pattern
        # somewhere else can never become a silent zero.
        if raw == "-" and "-" in r["extractor"]:
            extracted = 0.0
        else:
            extracted, _ = _number(raw)
        scale = float(r.get("document_scale") or 1)
        if extracted is not None and scale != 1:
            extracted *= scale
        decimals = len(printed.split(".")[1]) if "." in printed else 0
        if extracted is None or abs(extracted - committed) > 0.5 * 10 ** (-decimals) + 1e-9:
            if r.get("declared_by"):
                declared.append((r, "document says %s, CSV holds %s; declared by %s"
                                 % (hit.group(1), row[r["column"]], r["declared_by"])))
                continue
            bad.append((r, "document says %s, CSV holds %s" % (hit.group(1), row[r["column"]])))
            continue
        ok += 1
        if verbose:
            print("  ok  %s[%s].%s = %s (%s %s)" % (r["data_file"], r["row_key"], r["column"],
                                                    row[r["column"]], r["document"], r["locator"]))
    print("transcription checks: %d rows; %d agree, %d DISAGREE, %d declared, %d skipped, "
          "%d read-by-a-person" % (len(register), ok, len(bad), len(declared), len(skipped),
                                   read_only))
    for r, why in declared:
        print("  DECLARED %s[%s].%s: %s" % (r["data_file"], r["row_key"], r["column"], why))
    for r, why in skipped:
        print("  SKIPPED %s[%s].%s: %s" % (r["data_file"], r["row_key"], r["column"], why))
    for r, why in bad:
        print("  DISAGREE %s[%s].%s: %s (%s %s)" % (r["data_file"], r["row_key"], r["column"],
                                                  why, r["document"], r["locator"]))
    return 1 if bad else 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    sector = argv[argv.index("--sector") + 1] if "--sector" in argv else None
    raise SystemExit(check(sector=sector, verbose="--verbose" in argv))
