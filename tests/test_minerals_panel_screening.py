"""The corrected screening must describe final exports, never preserve defects."""
import os
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

class MineralsScreening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(os.path.join(ROOT, "outputs/pakemis_minerals_panel_screening.csv"))

    def test_all_36_supported_cells_close_on_independent_month_controls(self):
        self.assertEqual(36, len(self.rows))
        for row in self.rows:
            self.assertEqual("yes", row["control_agrees_with_panel"])
            self.assertEqual("none", row["provinces_missing"])
            self.assertLessEqual(float(row["max_month_control_residual"]), 1)
            self.assertLessEqual(int(row["rows_per_month"]), 5)

    def test_fallback_is_a_source_quality_decision_with_complete_activity(self):
        fallback = {(r["canonical_mineral"], r["fiscal_year_start"]) for r in self.rows if r["served_as_covered"] == "no"}
        self.assertEqual({("crude_oil", "2021"), ("natural_gas", "2021")}, fallback)
        for row in self.rows:
            if row["served_as_covered"] == "no":
                self.assertEqual("source-quality fallback", row["verdict"])
                self.assertEqual("T4", row["served_timing_method"])
                self.assertLess(float(row["served_worst_month_share_pct"]), 9)
            else:
                self.assertEqual("T2", row["served_timing_method"])

    def test_displayed_profiles_close_at_display_precision(self):
        for row in self.rows:
            self.assertAlmostEqual(100, sum(float(x) for x in row["served_profile_pct"].split(";")), delta=.0001)

if __name__ == "__main__":
    unittest.main()
