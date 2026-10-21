"""Year-matched BTR comparison: transcription, scope, offsets and prose arithmetic.

The comparison must preserve source arithmetic, count each category once, and
exclude wider-scope categories from its exact+aggregate subtotal. Opposing
category differences are not causal evidence or independent validation.

Run: python3 -m unittest discover tests -p "test_btr_comparison.py"
"""
import collections
import importlib.util
import io
import os
import subprocess
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path                                     # noqa: E402
from pkinv.core.io import read_rows                                     # noqa: E402
from pkinv.core.configurations import REFERENCE                         # noqa: E402
from pkinv.paths import DATA, OUTPUTS                                   # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "build_btr_comparison", os.path.join(ROOT, "scripts", "build_btr_comparison.py"))
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)

PRODUCT = "pakemis_btr_comparison.csv"
OFFSETS = "pakemis_btr_category_offsets.csv"
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
        self.assertEqual(len(restated), 2, "waste-fate and residue-burning restatements expected")
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

    def test_comparable_total_excludes_the_wider_other_sectors_boundary(self):
        total = next(r for r in self.totals if r["subject"] == builder.COMPARABLE_TOTAL)
        comparable = [r for r in self.entries if r["tier"] in ("exact", "aggregate")]
        self.assertTrue(any(r["tier"] == "scope-gap" for r in self.entries))
        for column in ("btr_Mt_co2e", "pakemis_Mt_co2e", "pakemis_Mt_co2e_ch4_uniform_28"):
            self.assertAlmostEqual(float(total[column]),
                                   sum(float(r[column]) for r in comparable), places=3)
        self.assertIn("excludes 1.A.4 scope-gap", total["note"])

    def test_counted_rows_do_not_overlap_on_either_side(self):
        counted = [r for r in self.entries
                   if r["tier"] not in ("out-of-scope", "aggregate-restated")]
        for key in ("btr_codes", "pakemis_codes"):
            codes = [c for r in counted for c in r[key].split("+") if c]
            self.assertEqual(len(codes), len(set(codes)), key)
            for a in codes:
                self.assertFalse(any(b.startswith(a + ".") for b in codes), (key, a))

    def test_gap_narrative_agrees_with_the_published_numbers(self):
        headline = next(r for r in self.totals if r["subject"] == "TOTAL (excluding LULUCF)")
        subtotal = next(r for r in self.totals if r["subject"] == builder.COMPARABLE_TOTAL)
        gaps = [100 * abs(float(r["pakemis_Mt_co2e"]) - float(r["btr_Mt_co2e"]))
                / float(r["btr_Mt_co2e"]) for r in (headline, subtotal)]
        # Regression for the former prose claiming closer shared-category agreement
        # even when its own table showed the opposite.
        for gap in gaps:
            self.assertIn("%.2f%%" % gap, subtotal["note"])
        direction = "larger" if gaps[1] > gaps[0] else "smaller" if gaps[1] < gaps[0] else "equal"
        self.assertIn("subtotal difference is " + direction, subtotal["note"])
        self.assertNotIn("most of the national difference is COMPLETENESS", subtotal["note"])
        self.assertNotIn("agree far more closely", subtotal["note"])

    def test_uniform_28_changes_only_pakemis_fossil_ch4(self):
        fossil = collections.defaultdict(float)
        for r in read_rows(asset_path(OUTPUTS, "pakemis_atomic_annual.csv")):
            if (r["period_id"] == "FY2020-21" and r["configuration_id"] == REFERENCE
                    and r["gas"] == "CH4" and r["gas_origin"] == "fossil"):
                fossil[r["ipcc_code"]] += float(r["emission_native_mass"])
        for r in self.entries:
            if not r["pakemis_codes"]:
                continue
            expected = 2 * sum(fossil[c] for c in r["pakemis_codes"].split("+")) / 1000
            actual = float(r["pakemis_Mt_co2e"]) - float(r["pakemis_Mt_co2e_ch4_uniform_28"])
            self.assertAlmostEqual(actual, expected, delta=.00101, msg=r["subject"])
            if expected:
                self.assertIn("cannot be recovered", r["ch4_convention_note"])

    def test_header_uses_current_fugitives_values(self):
        with open(os.path.join(OUTPUTS, PRODUCT), encoding="utf-8") as handle:
            heading = "".join(line for line in handle if line.startswith("#"))
        r = next(r for r in self.entries if r["subject"] == "Oil and natural gas fugitives")
        self.assertIn("ratio %.2f as published" % float(r["ratio_pakemis_over_btr"]), heading)
        self.assertIn("%.2f with PakEmis CH4" % float(r["ratio_ch4_uniform_28"]), heading)
        self.assertIn("not a harmonisation or correction of BTR", heading)

    def test_offsets_close_and_preserve_opposing_differences(self):
        rows = read_rows(os.path.join(OUTPUTS, OFFSETS))
        categories = [r for r in rows if r["row_type"] == "category"]
        total = next(r for r in rows if r["row_type"] == "total")
        want = [r for r in self.entries if r["tier"] in ("exact", "aggregate")]
        self.assertEqual({r["subject"] for r in categories}, {r["subject"] for r in want})
        positive = negative = absolute = 0.0
        for r in categories:
            d = float(r["pakemis_Mt_co2e"]) - float(r["btr_Mt_co2e"])
            self.assertAlmostEqual(float(r["difference_Mt_co2e"]), d, places=3)
            positive += max(d, 0)
            negative += min(d, 0)
            absolute += abs(d)
        self.assertGreater(positive, 0)
        self.assertLess(negative, 0)
        for key, value in (("positive_difference_Mt_co2e", positive),
                           ("negative_difference_Mt_co2e", negative),
                           ("absolute_difference_Mt_co2e", absolute),
                           ("difference_Mt_co2e", positive + negative)):
            self.assertAlmostEqual(float(total[key]), value, places=3)
        subtotal = next(r for r in self.totals if r["subject"] == builder.COMPARABLE_TOTAL)
        self.assertAlmostEqual(float(total["difference_Mt_co2e"]),
                               float(subtotal["pakemis_Mt_co2e"]) - float(subtotal["btr_Mt_co2e"]),
                               places=3)

    def test_it_regenerates_identically(self):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "scripts",
                                                         "build_btr_comparison.py"), "--check"],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0,
                         "the BTR comparison is stale; run make btr-comparison.\n%s%s"
                         % (r.stdout, r.stderr))


class TestComparisonRegressionGuards(unittest.TestCase):
    def test_narrative_changes_direction_when_the_evidence_changes(self):
        self.assertIn("subtotal difference is larger", builder.comparison_note(100, 101, 50, 55))
        self.assertIn("subtotal difference is smaller", builder.comparison_note(100, 110, 50, 51))
        # A deficit is as large a disagreement as the same-sized surplus.
        self.assertIn("subtotal difference is equal", builder.comparison_note(100, 90, 50, 55))

    def test_overlap_is_rejected_before_building_totals(self):
        row = (["1.A"], ["1.A.1"], "first", "exact", "")
        duplicate = (["1.A"], ["1.A.2"], "duplicate", "exact", "")
        nested = (["1.A.1"], ["1.A.2"], "nested", "exact", "")
        for extra in (duplicate, nested):
            with self.subTest(extra=extra[2]), mock.patch.object(builder, "CROSSWALK", [row, extra]):
                with self.assertRaisesRegex(ValueError, "overlapping BTR"):
                    builder.validate_crosswalk()



if __name__ == "__main__":
    unittest.main()
