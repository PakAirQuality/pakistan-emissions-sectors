"""Gates on the OCAC direct-edition cross-check: the differencing identity, measured.

WHAT IS BEING PROTECTED. core/ocac_monthly.py recovers a month by subtracting one cumulative
year-to-date edition from the next, and transport, railways, power and industry all shape
their years with the result. The identity is sound on paper. These tests hold it to OCAC's
independently published single-month editions of the same months, so that "it should hold"
stays "it does hold" as the panel and the parser both change.

WHY THE EXPECTATIONS ARE LISTED RATHER THAN COUNTED. Every declared set here - the quarantined
rows, the superseded edition - is written out in full. A test that asserted only a COUNT would
pass when one defect was fixed and another appeared, and a list is a to-do nobody can lose.

Run:  python3 -m unittest discover tests
"""
import csv
import os
import shutil
import subprocess
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)
from pkinv.core.io import read_rows
from _support import ROOT

CROSSCHECK = os.path.join(ROOT, "outputs", "ocac_direct_edition_crosscheck.csv")
CURRENCY = os.path.join(ROOT, "outputs", "ocac_edition_currency.csv")
QUARANTINE = os.path.join(ROOT, "outputs", "ocac_direct_edition_quarantine.csv")
SCRIPT = os.path.join(ROOT, "scripts", "ingest_ocac_monthly.py")

# The two rows where OCAC's OWN arithmetic does not close: the products printed on the row do
# not sum to the total printed on the same row. Both are Balochistan. They are listed, not
# counted, because a new failure elsewhere must not be absorbed by one of these being fixed.
EXPECTED_QUARANTINE = {("202212", "Balochistan", "Cement"),
                       ("202307", "Balochistan", "Road")}

# The one month where the shipped panel is built on an edition OCAC has since restated.
EXPECTED_SUPERSEDED = {"202307"}

# Four customer classes x three fiscal years x twelve months.
EXPECTED_COMPARISONS = 144


def _rows(path):
    return read_rows(path)


class DifferencingAgreesWithPublishedMonths(unittest.TestCase):
    def setUp(self):
        self.rows = [r for r in _rows(CROSSCHECK) if r["agrees"] in ("yes", "NO")]

    def test_every_case_was_actually_compared(self):
        """A comparison the panel could not serve must not read as agreement."""
        unserved = [r for r in _rows(CROSSCHECK) if r["agrees"] == "panel-cannot-serve"]
        self.assertEqual([], unserved,
                         "the panel failed to serve a case the check depends on: %s" % unserved)
        self.assertEqual(EXPECTED_COMPARISONS, len(self.rows))

    def test_no_disagreement_between_differenced_and_published_months(self):
        bad = [(r["month"], r["sector_row"], r["products"], r["relative_delta"])
               for r in self.rows if r["agrees"] != "yes"]
        self.assertEqual([], bad,
                         "the differencing identity disagrees with OCAC's own published "
                         "months: %s" % bad)

    def test_most_months_agree_to_the_tonne(self):
        """Not a tolerance - a floor on how EXACT the agreement is, so it cannot rot into
        'within half a per cent' one rounding change at a time."""
        exact = sum(1 for r in self.rows if float(r["delta_t"]) == 0.0)
        self.assertGreaterEqual(exact, 130, "only %d of %d comparisons are exact"
                                % (exact, len(self.rows)))

    def test_the_check_covers_both_t_classes(self):
        """A check that only ever saw directly published months would not be testing the
        differencing at all, which is the entire point of it."""
        classes = {r["panel_t_class"] for r in self.rows}
        self.assertIn("T2", classes)
        self.assertIn("T1", classes)


class EditionCurrency(unittest.TestCase):
    def setUp(self):
        self.rows = _rows(CURRENCY)

    def test_every_fetched_month_is_accounted_for(self):
        self.assertEqual(36, len(self.rows))
        self.assertEqual(set(), {r["status"] for r in self.rows} - {
            "identical", "identical-numbers-different-bytes", "cumulative-form",
            "SUPERSEDED", "not-in-panel"})

    def test_the_superseded_editions_are_exactly_the_declared_ones(self):
        found = {r["month"] for r in self.rows if r["status"] == "SUPERSEDED"}
        self.assertEqual(EXPECTED_SUPERSEDED, found,
                         "the set of months whose panel edition OCAC has restated changed; "
                         "this is a finding to act on, not a number to update")

    def test_the_superseded_month_is_sized(self):
        """A restatement recorded without its magnitude cannot be triaged."""
        for row in self.rows:
            if row["status"] == "SUPERSEDED":
                self.assertNotEqual("", row["delta_t"])
                self.assertNotEqual(0.0, float(row["delta_t"]))


class DocumentControls(unittest.TestCase):
    def test_quarantine_is_exactly_the_rows_the_source_gets_wrong(self):
        found = {(r["month"], r["area"], r["sector"]) for r in _rows(QUARANTINE)}
        self.assertEqual(EXPECTED_QUARANTINE, found)

    def test_quarantined_rows_keep_their_raw_text(self):
        for row in _rows(QUARANTINE):
            self.assertTrue(row["raw"].strip(),
                            "a quarantined row with no raw text cannot be adjudicated")
            self.assertNotEqual(row["products_sum"], row["printed_total"])


class Reparse(unittest.TestCase):
    """The slow test: re-run the parser and require both published controls to close."""

    @unittest.skipUnless(shutil.which("pdftotext"), "pdftotext not installed")
    def test_both_published_controls_close_on_all_thirty_six_months(self):
        require_documents("data/raw/ocac/monthly_sector_province", "sources/Aviation/ocac_monthly")
        result = subprocess.run(["python3", SCRIPT], cwd=ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        output = result.stdout.decode("utf-8", "replace")
        self.assertIn("national sector closure (A. TOTAL INTERNAL): 36 of 36", output, output)
        self.assertIn("memo-item closure (B. TOTAL OVERSEAS):      36 of 36", output, output)
        self.assertEqual(0, result.returncode, output)


if __name__ == "__main__":
    unittest.main()
