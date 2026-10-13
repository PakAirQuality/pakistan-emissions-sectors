"""The national CRT crosswalk: a join over the sectors' own extractions, and the period
column that stops it being read as a method comparison.

Run:  python3 -m unittest discover tests -p "test_crt_crosswalk.py"
"""
import unittest

from pkinv.core import period, registry
from pkinv.report import crt_crosswalk


class TestCrosswalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = crt_crosswalk.build()

    def test_it_computes_nothing(self):
        """A join, not a calculation: every engine figure must equal the registry's own
        total for that category, to the last decimal place."""
        components, _c, _s = registry.build_all()
        for r in self.rows:
            want = sum(c["co2e_Mt_AR5"] for c in components
                       if c["category"] in crt_crosswalk.ENGINE_CATEGORIES[r["ipcc_code"]])
            self.assertAlmostEqual(r["engine_Mt_co2e"], want, places=4, msg=r["ipcc_code"])

    def test_every_row_states_its_period_overlap(self):
        for r in self.rows:
            self.assertEqual(r["crt_period"], "CY2022")
            self.assertIn(r["comparison_kind"], ("method", "vintage", "no overlap"))
            self.assertIsInstance(r["overlap_months"], int)

    def test_the_overlap_is_derived_from_the_declared_periods(self):
        sectors = {s.NAME: s for s in registry.all_sectors()}
        for r in self.rows:
            s = sectors[r["sector"]]
            self.assertEqual(r["overlap_months"],
                             period.overlap_months((s.PERIOD_START, s.PERIOD_END),
                                                   crt_crosswalk.CRT_PERIOD))
            self.assertEqual(r["engine_period"],
                             period.label(s.PERIOD_START, s.PERIOD_END))

    def test_a_zero_overlap_row_is_not_labelled_a_method_comparison(self):
        """The reason this table exists. The filing is calendar 2022 and the inventory is
        FY2023-24, so for every code the two describe no shared month - a ratio across that
        gap measures how the source moved, not whether two methods agree, and the two are
        routinely confused."""
        for r in self.rows:
            if r["overlap_months"] == 0:
                self.assertEqual(r["comparison_kind"], "no overlap", r["ipcc_code"])
                self.assertIn("measures how the source changed", r["note"])

    def test_the_crosswalk_is_not_empty(self):
        """A join over an empty registry passes every test above while saying nothing."""
        self.assertGreaterEqual(len(self.rows), 4)
        for r in self.rows:
            self.assertTrue(r["crt_Mt_co2e"] != "", r["ipcc_code"])


if __name__ == "__main__":
    unittest.main()
