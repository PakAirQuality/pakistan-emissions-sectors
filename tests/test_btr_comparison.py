"""The year-matched comparison against Pakistan's own submission, guarded.

WHY THESE TESTS. The comparison is only worth anything if three separate things hold, and
each fails in its own way:

1. THE TRANSCRIPTION IS FAITHFUL. A hand-read table is the classic place for a digit to move,
   and this one is read out of a pdftotext rendering where a dash and a zero look alike. The
   document checks itself: every printed parent closes over its printed children and the four
   sector totals sum to the printed national total. If the transcription is wrong, one of
   those closures breaks. That is a stronger check than re-reading the page, and it is why
   the gas columns are recorded only where all four numbers are printed - a row that prints a
   dash for a gas leaves them blank rather than having a zero guessed into position.

2. THE CROSSWALK IS EXHAUSTIVE AND HONEST. The two accounts SWAP two codes - the submission
   books rice at 3.D and managed soils at 3.C, this inventory the other way round - so a code
   join silently compares rice against soil nitrous oxide and returns two plausible ratios.
   Every comparison is therefore an explicit entry, and a PakEmis code facing no entry would
   drop out of this product's own subtotal without anything saying so.

3. THE RESTATED ROW DOES NOT DOUBLE COUNT. Landfill and open burning are compared
   individually and then re-summed, because taken alone they read 0.49 and 17.74 while
   together they read 0.68 - the accounts disagree about the fate split of one waste stream,
   not about a factor by an order of magnitude. That re-sum must stay out of the totals, the
   same way a contained claimant stays out of the completeness-mass ledger's sums.

Run:  python3 -m unittest discover tests -p "test_btr_comparison.py"
"""
import csv
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path                                     # noqa: E402
from pkinv.core.io import read_rows                                     # noqa: E402
from pkinv.core.configurations import REFERENCE                         # noqa: E402
from pkinv.paths import DATA, OUTPUTS                                   # noqa: E402

PRODUCT = "pakemis_btr_comparison.csv"
INVENTORY = "btr1_national_inventory.csv"
RATIO_TIERS = ("exact", "aggregate", "aggregate-restated")
PRINTED_NATIONAL_TOTAL = 521.46          # the document's own printed total, not a sum


class TestTheTranscriptionChecksItself(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(asset_path(DATA, INVENTORY))
        cls.total = {r["btr_code"]: float(r["total_Mt_co2e"]) for r in cls.rows}

    def test_every_parent_closes_over_its_printed_children(self):
        problems = []
        checked = 0
        for code in sorted(self.total):
            kids = [c for c in self.total
                    if c.startswith(code + ".") and c.count(".") == code.count(".") + 1]
            if not kids:
                continue
            checked += 1
            summed = sum(self.total[k] for k in kids)
            # The published table rounds each cell to 2 dp, so a parent may differ from its
            # children's sum by the accumulated rounding - never by more.
            if abs(summed - self.total[code]) > 0.005 * len(kids) + 0.011:
                problems.append("%s prints %.3f, its %d children sum to %.3f"
                                % (code, self.total[code], len(kids), summed))
        self.assertGreater(checked, 8,
                           "only %d parents had children to close over; the transcription has "
                           "lost its hierarchy and this check is vacuous" % checked)
        self.assertFalse(problems, "the transcription does not reproduce the document's own "
                                   "arithmetic:\n  " + "\n  ".join(problems))

    def test_the_four_sectors_sum_to_the_printed_national_total(self):
        summed = sum(self.total[c] for c in ("1", "2", "3", "4"))
        self.assertAlmostEqual(
            summed, PRINTED_NATIONAL_TOTAL, delta=0.02,
            msg="the four sector totals sum to %.2f against the document's printed %.2f"
                % (summed, PRINTED_NATIONAL_TOTAL))

    def test_each_row_cites_the_line_it_was_read_from(self):
        for r in self.rows:
            self.assertTrue(r["source_line"].isdigit() and int(r["source_line"]) > 0,
                            "%s cites no source line" % r["btr_code"])

    def test_a_gas_split_is_recorded_only_where_all_four_numbers_are_printed(self):
        """A dash is not a zero. A row printing three numbers has one gas dashed, and which
        one cannot be recovered from the rendering, so the split is left blank."""
        for r in self.rows:
            gases = [r["co2_Mt_co2e"], r["ch4_Mt_co2e"], r["n2o_Mt_co2e"]]
            if int(r["printed_columns"]) == 4:
                self.assertTrue(all(g != "" for g in gases),
                                "%s prints four numbers but records no gas split"
                                % r["btr_code"])
            else:
                self.assertTrue(all(g == "" for g in gases),
                                "%s prints %s numbers, so a gas was dashed, yet a split is "
                                "recorded - a zero has been guessed into place"
                                % (r["btr_code"], r["printed_columns"]))


class TestTheComparisonIsHonest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.path.join(OUTPUTS, PRODUCT)
        if not os.path.exists(path):
            raise unittest.SkipTest("%s has not been generated here" % PRODUCT)
        cls.rows = read_rows(path)
        cls.entries = [r for r in cls.rows if r["tier"] != "total"]
        cls.totals = [r for r in cls.rows if r["tier"] == "total"]

    def test_every_pakemis_code_faces_a_crosswalk_entry(self):
        """A code with no entry would vanish from this product's own subtotal in silence."""
        mapped = {c for r in self.entries for c in r["pakemis_codes"].split("+") if c}
        present = {r["ipcc_code"] for r in read_rows(
            asset_path(OUTPUTS, "pakemis_atomic_annual.csv"))
            if r["period_id"] == "FY2020-21" and r["configuration_id"] == REFERENCE}
        self.assertTrue(present, "no FY2020-21 reference rows to compare against")
        self.assertFalse(sorted(present - mapped),
                         "these PakEmis codes face no crosswalk entry and would be dropped "
                         "from the comparison's own subtotal: %s"
                         % sorted(present - mapped))

    def test_a_ratio_is_printed_only_where_the_boundaries_support_one(self):
        for r in self.entries:
            if r["tier"] in RATIO_TIERS:
                self.assertNotEqual(r["ratio_pakemis_over_btr"], "",
                                    "%s is tier %s and prints no ratio"
                                    % (r["subject"], r["tier"]))
            else:
                self.assertEqual(r["ratio_pakemis_over_btr"], "",
                                 "%s is tier %s - a ratio across those boundaries is not "
                                 "admissible and must stay blank" % (r["subject"], r["tier"]))

    def test_the_restated_row_is_excluded_from_both_totals(self):
        """The whole point of the restated tier: it re-sums rows already counted."""
        restated = [r for r in self.entries if r["tier"] == "aggregate-restated"]
        self.assertTrue(restated, "the solid-waste fate row is gone; without it the 0.49 and "
                                  "17.74 ratios read as an order-of-magnitude error in "
                                  "opposite directions on adjacent categories")
        counted = [r for r in self.entries
                   if r["tier"] not in ("out-of-scope", "aggregate-restated")]
        for total in self.totals:
            if total["subject"] != "TOTAL (excluding LULUCF)":
                continue
            want = sum(float(r["btr_Mt_co2e"]) for r in counted if r["btr_Mt_co2e"] != "")
            self.assertAlmostEqual(
                float(total["btr_Mt_co2e"]), want, delta=0.02,
                msg="the headline total is %s but the rows it may count sum to %.2f - the "
                    "restated solid-waste row is being double counted"
                    % (total["btr_Mt_co2e"], want))

    def test_lulucf_is_held_and_excluded(self):
        land = [r for r in self.entries if r["tier"] == "out-of-scope"]
        self.assertTrue(land, "the submission's land-use block is not even listed; a reader "
                              "cannot see what the scope difference is worth")
        self.assertEqual(land[0]["pakemis_Mt_co2e"], "",
                         "this inventory has no LULUCF estimate to put beside it")

    def test_both_totals_are_published(self):
        """The decomposition is the result, not the headline ratio."""
        subjects = {r["subject"] for r in self.totals}
        self.assertIn("TOTAL (excluding LULUCF)", subjects)
        self.assertIn("TOTAL on categories both accounts estimate", subjects,
                      "without the like-for-like total the product cannot say whether the "
                      "national difference is completeness or estimation, which is the one "
                      "question a single ratio cannot answer")

    def test_it_regenerates_identically(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts",
                                                         "build_btr_comparison.py"), "--check"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0,
                         "the BTR comparison is stale; run make btr-comparison.\n%s%s"
                         % (r.stdout, r.stderr))


if __name__ == "__main__":
    unittest.main()
