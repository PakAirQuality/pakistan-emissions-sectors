"""The flatness crosswalk: the two flat-share statements joined, and the join closes.

The sixteenth review asked for the published bridge between the TE-class flat share
(TE4 at cell grain, the coverage summary's figure) and the physical decomposition
(43.4% correctly flat + 21.0% variable-but-unobserved). The bridge exists arithmetically
in the two source outputs; these tests hold the published crosswalk to both of them.
rc42 (the twentieth review's T-1): the join is at the atom grain, so the table reproduces
the coverage summary's TE4 exactly and can contain no cell the definitions forbid.

Run:  python3 -m unittest discover tests -p "test_flatness_crosswalk.py"
"""
import csv
import os
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

OUT = os.path.join(ROOT, "outputs", "pakemis_flatness_crosswalk.csv")


def _rows(path):
    return read_rows(path)


class TestTheCrosswalkCloses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(OUT):
            raise unittest.SkipTest("crosswalk not generated")
        cls.rows = _rows(OUT)
        cls.cells = [r for r in cls.rows if r["row_kind"] == "cell"]
        cls.buckets = {r["flatness_bucket"]: float(r["co2e_Mt_AR5"])
                       for r in cls.rows if r["row_kind"] == "bucket_total"}

    def test_the_three_buckets_partition_the_monthly_mass(self):
        shares = [float(r["share_of_monthly_mass_pct"]) for r in self.rows
                  if r["row_kind"] == "bucket_total"]
        self.assertEqual(len(shares), 3)
        self.assertAlmostEqual(sum(shares), 100.0, delta=0.05)

    def test_cells_sum_to_their_buckets(self):
        for name, total in self.buckets.items():
            cells = sum(float(r["co2e_Mt_AR5"]) for r in self.cells
                        if r["flatness_bucket"] == name)
            self.assertAlmostEqual(cells, total, delta=0.01, msg=name)

    def test_it_matches_the_decomposition_headlines(self):
        decomposition = _rows(os.path.join(ROOT, "outputs",
                                           "pakemis_temporal_decomposition.csv"))
        total = sum(float(r["co2e_Mt_AR5"]) for r in decomposition)
        unobserved = sum(float(r["unobserved_Mt_AR5"]) for r in decomposition)
        self.assertAlmostEqual(self.buckets["variable_unobserved"], unobserved,
                               delta=0.01)
        appropriate = sum(float(r["co2e_Mt_AR5"]) for r in decomposition
                          if r["flatness_physically_appropriate"] == "yes")
        self.assertAlmostEqual(self.buckets["flat_physically_appropriate"],
                               appropriate, delta=0.01)
        self.assertAlmostEqual(sum(self.buckets.values()), total, delta=0.05)

    def test_the_grain_difference_reconciles_to_the_coverage_summary(self):
        """This table's TE4 == the coverage summary's TE4, and the printed grain
        difference is zero: since rc42 the join is at the month-row grain, the same grain
        the summary grades, so the published flat share is READ from this table, not
        reached by adding a remainder to it."""
        te4 = next(float(r["co2e_Mt_AR5"]) for r in self.rows
                   if r["row_kind"] == "te_total")
        difference = next(r for r in self.rows if r["row_kind"] == "grain_difference")
        summary = _rows(os.path.join(ROOT, "outputs",
                                     "pakemis_monthly_coverage_summary.csv"))
        coverage_te4 = sum(float(r["TE4_Mt"]) for r in summary)
        self.assertAlmostEqual(te4, coverage_te4, delta=0.01)
        self.assertAlmostEqual(float(difference["co2e_Mt_AR5"]), 0.0, delta=0.01)
        self.assertAlmostEqual(float(difference["share_of_monthly_mass_pct"]), 0.0, delta=0.01)

    def test_no_cell_the_definitions_forbid(self):
        """variable_unobserved IS time-variable mass carried on a TE4 profile, and
        variable_timed is time-variable mass carried on any other grade - so the first
        cannot appear outside TE4 and the second cannot appear inside it. rc41 published
        159.6 Mt of the first and 246.2 Mt of the second, from joining a component's
        dominant grade to its buckets."""
        for r in self.cells:
            if r["flatness_bucket"] == "variable_unobserved":
                self.assertEqual(r["te_class"], "TE4", r)
            if r["flatness_bucket"] == "variable_timed":
                self.assertNotEqual(r["te_class"], "TE4", r)

    def test_te4_contains_both_kinds_of_flat(self):
        """The whole point of the table: TE4 is not one thing."""
        te4_appropriate = sum(float(r["co2e_Mt_AR5"]) for r in self.cells
                              if r["te_class"] == "TE4"
                              and r["flatness_bucket"] == "flat_physically_appropriate")
        te4_unobserved = sum(float(r["co2e_Mt_AR5"]) for r in self.cells
                             if r["te_class"] == "TE4"
                             and r["flatness_bucket"] == "variable_unobserved")
        self.assertGreater(te4_appropriate, 1000.0)
        self.assertGreater(te4_unobserved, 100.0)


if __name__ == "__main__":
    unittest.main()
