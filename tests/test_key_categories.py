"""Tests for the Key Category Analysis (IPCC 2006 Vol 1 Ch 4, Approach 1).

Reads the generated outputs/, so it skips cleanly if the inventory has not been run.

Run:  python3 -m unittest discover tests
"""
import os
import sys
import unittest


from pkinv.sectors.agriculture import key_categories as kc  # noqa: E402

OUT = os.path.join(os.path.dirname(__file__), "..", "outputs")
HAVE_LEVEL = os.path.exists(os.path.join(OUT, "national_totals_2024.csv"))


@unittest.skipUnless(HAVE_LEVEL, "run the national inventory first")
class TestKeyCategories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.level_rows, cls.trend_rows = kc.compute()

    def test_level_shares_sum_to_100(self):
        total = sum(share for _, share, _, _ in self.level_rows)
        self.assertAlmostEqual(total, 1.0, places=6)

    def test_level_cumulative_monotonic_and_ends_at_100(self):
        cums = [cum for _, _, cum, _ in self.level_rows]
        self.assertEqual(cums, sorted(cums))            # non-decreasing
        self.assertAlmostEqual(cums[-1], 1.0, places=6)

    def test_enteric_is_top_and_key(self):
        top_name, _, _, top_key = self.level_rows[0]
        self.assertEqual(top_name, "Enteric fermentation")
        self.assertTrue(top_key)

    def test_key_set_is_the_dominant_categories(self):
        key_by_level = {n for n, _, _, k in self.level_rows if k}
        key_by_trend = {n for n, _, _, k in self.trend_rows if k}
        all_key = key_by_level | key_by_trend
        # the four dominant agriculture categories must all be key
        for expected in ("Enteric fermentation", "Manure management",
                         "Rice cultivation", "Managed soils"):
            self.assertIn(expected, all_key, expected)
        # a tiny category (residue burning) must NOT be key
        self.assertNotIn("Field burning of residues", all_key)

    def test_trend_present_and_normalised(self):
        self.assertTrue(self.trend_rows, "trend needs the 1990-2024 time series")
        total = sum(share for _, share, _, _ in self.trend_rows)
        self.assertAlmostEqual(total, 1.0, places=6)


if __name__ == "__main__":
    unittest.main()
