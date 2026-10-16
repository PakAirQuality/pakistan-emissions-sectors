"""The transcription-check register and its checker: every automatable row re-runs, and a wrong cell is caught.

data/transcription_checks.csv holds one row per hand-typed activity cell re-read from the
document it was typed from (rc37; the sector passes populate it). scripts/check_transcriptions.py
re-extracts every pdftotext/ocr row and compares. What is asserted here: the shipped register
parses, its rows point at files, columns, row keys and documents that exist, the checker's
number parsing is what the agreement rule needs, and - the detector tested - a planted
disagreement fails and a planted agreement passes, with the page text canned so the test
needs neither pdftotext nor a document.

Run:  python3 -m unittest discover tests -p "test_transcription_checks.py"
"""

from pkinv.assets import asset_path
import csv
import io
import os
import unittest

from _support import ROOT, load_script, read_rows
from _support import readable  # noqa: E402

checker = load_script("check_transcriptions.py")
REGISTER = asset_path(ROOT, "data", "transcription_checks.csv")
RESTRICTED = asset_path(ROOT, "data", "restricted_sources", "restricted_source_registry.csv")


def _registered_absent():
    """Documents a validation package deliberately does not carry: the registry's
    exact_filename column, which is a file or - as in 63 of 65 source rows - the archive
    DIRECTORY the document lives in. Empty in the repository, where every document exists."""
    if not os.path.exists(RESTRICTED):
        return set()
    return {r["exact_filename"].rstrip("/") for r in read_rows(RESTRICTED)}


def _is_registered_absent(document):
    return any(document == p or document.startswith(p + "/") for p in _registered_absent())


class TestTheRegisterIsWellFormed(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(REGISTER)

    def test_the_columns_are_the_contract(self):
        with open(REGISTER, encoding="utf-8") as f:
            header = next(l for l in f if not l.startswith("#")).strip().split(",")
        self.assertEqual(tuple(header), checker.FIELDS)

    def test_every_row_points_at_things_that_exist(self):
        for r in self.rows:
            path = asset_path(ROOT, r["data_file"])
            self.assertTrue(os.path.exists(path), r["data_file"])
            table = read_rows(path)
            self.assertIn(r["column"], table[0], "%s has no column %s" % (r["data_file"], r["column"]))
            row, why = checker._find_row(table, r["row_key"])
            self.assertIsNotNone(row, "%s: %s" % (r["data_file"], why))
            # Inside a validation package the documents are deliberately absent and each
            # is registered as such with its hash; the register then points at the
            # registry row rather than at bytes. In the repository every document exists.
            self.assertTrue(os.path.exists(asset_path(ROOT, r["document"]))
                            or _is_registered_absent(r["document"])
                            or not readable(r["document"]), r["document"])
            self.assertIn(r["method"], ("pdftotext", "ocr", "read"))
            if r["method"] != "read":
                self.assertTrue(r["extractor"], "%s: an automatable row needs an extractor"
                                % r["data_file"])

    def test_the_shipped_register_agrees_with_its_documents(self):
        """The real run: every automatable row re-extracted. Skips are printed by the
        checker itself; a disagreement is a finding, and it fails here."""
        self.assertEqual(checker.check(), 0)


class TestTheCheckerCatchesAWrongCell(unittest.TestCase):
    """The detector, tested with canned page text."""

    def _run(self, committed, page_value, method="pdftotext", declared_by="", scale="",
             extractor=r"Urea\s+([\d,\.]+)"):
        tmp_csv = os.path.join(ROOT, "outputs", "zz_transcription_selftest.csv")
        # The checker resolves data_file relative to ROOT, so the scratch table must live
        # under outputs/. A validation package mounted read-only cannot take it: the
        # self-tests then skip with the reason rather than error on the mount.
        if not os.access(os.path.join(ROOT, "outputs"), os.W_OK):
            raise unittest.SkipTest("outputs/ is read-only here (a read-only package mount); the checker "
                                    "self-tests need a scratch table under it")
        with open(tmp_csv, "w", encoding="utf-8", newline="") as f:
            f.write("item,value\nurea,%s\n" % committed)
        reg = io.StringIO()
        w = csv.DictWriter(reg, fieldnames=checker.FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerow({"data_file": "outputs/zz_transcription_selftest.csv", "row_key": "urea",
                    "column": "value", "committed_value": committed,
                    "document": "README.md", "locator": "p1 T1", "extracted_value": page_value,
                    "method": method, "extractor": extractor,
                    "document_scale": scale, "checked_on": "2026-08-25",
                    "declared_by": declared_by})
        original_rows, original_page = checker._rows, checker._page_text
        try:
            checker._rows = lambda path: (list(csv.DictReader(io.StringIO(reg.getvalue())))
                                          if path == checker.REGISTER else original_rows(path))
            checker._page_text = lambda document, page, method: ("Urea   %s  tonnes" % page_value, None)
            return checker.check()
        finally:
            checker._rows, checker._page_text = original_rows, original_page
            os.remove(tmp_csv)

    def test_an_agreeing_cell_passes(self):
        self.assertEqual(self._run("3144392", "3,144,392"), 0)

    def test_a_wrong_cell_fails(self):
        self.assertEqual(self._run("3144329", "3,144,392"), 1)

    def test_a_declared_difference_is_reported_not_failed(self):
        """The maize-area lesson: a difference a declared seam already explains is not a
        finding. It is printed as DECLARED and the run passes."""
        self.assertEqual(self._run("3144329", "3,144,392",
                                   declared_by="fiscal_activity.ANCHOR_PARITY_EXCEPTIONS"), 0)

    def test_half_an_ulp_at_printed_precision_is_the_rule(self):
        self.assertEqual(self._run("2.40", "2.404"), 0)
        self.assertEqual(self._run("2.40", "2.46"), 1)

    def test_a_document_in_thousands_is_scaled_not_flagged(self):
        """The Economic Survey publishes 000 hectares against a CSV in hectares. The
        multiplier is declared per row; a row that forgets it must FAIL rather than be
        absorbed, which is why the scale is never inferred from the disagreement."""
        self.assertEqual(self._run("9632000", "9,632", scale="1000"), 0)
        self.assertEqual(self._run("9632000", "9,632"), 1)

    def test_a_dash_is_none_reported_only_where_the_extractor_admits_it(self):
        self.assertEqual(self._run("0", "-", extractor=r"Urea\s+([\d,\.]+|-)"), 0)
        self.assertEqual(self._run("0", "-"), 1)

    def test_a_composite_row_key_selects_exactly_one_row(self):
        """The fiscal series' first column is the year and it carries eleven items per
        year, so `column=value;column=value` is the only honest way to name a cell. An
        ambiguous key must fail rather than silently take the first match."""
        table = [{"year": "2016", "item": "wheat", "v": "1"},
                 {"year": "2016", "item": "rice", "v": "2"}]
        row, why = checker._find_row(table, "year=2016;item=rice")
        self.assertEqual((row or {}).get("v"), "2", why)
        self.assertIsNone(checker._find_row(table, "year=2016")[0])
        self.assertIsNone(checker._find_row(table, "year=2016;item=maize")[0])
        self.assertIsNone(checker._find_row(table, "no_such_column=x")[0])

    def test_a_missing_tool_is_a_printed_skip_not_a_pass_or_a_fail(self):
        original = checker._page_text
        try:
            checker._page_text = lambda d, p, m: (None, "pdftotext not installed")
            # a skip leaves ok == bad == 0: exit 0, and the SKIPPED line is printed
            self.assertEqual(self._run("1", "1"), 0)
        finally:
            checker._page_text = original
