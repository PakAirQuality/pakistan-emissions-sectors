"""rc39 A10: the joint uncertainty says which number it is reporting.

`estimate_Mt` holds the MONTE CARLO MEAN. It reads as "the inventory's estimate", and an
external audit reasonably took the gap against the published total for staleness. It is not
stale: for a skewed distribution the mean and the deterministic point estimate differ on
purpose, and agriculture's differ by 0.044 Mt - managed soils alone by 0.042.

So the deterministic figure is published beside it and the divergence is a column. The
common ensemble already used exactly this convention (`deterministic_Mt` next to `mean_Mt`);
the joint uncertainty was the one product that reported one and named it the other.

WHAT IS NOT PRICED IS STILL DECLARED. Timing uncertainty is priced on field burning and
managed soils and declared-unpriced on enteric fermentation and manure management, which is
correct - those are continuous processes and a timing dispersion on them would be a number
about nothing. Rice cultivation and urea application are ALSO unpriced, and they are
genuinely time-variable, so that is a real gap rather than a physical answer. It stays
declared rather than filled: inventing a dispersion to complete the rectangle is what this
pass was explicitly asked not to do.
"""
import collections
import os
import unittest

from _support import OUTPUTS, read_rows

CONTROL_TOTAL = 223.454471
CONTINUOUS = {"Enteric fermentation", "Manure management"}
TIME_VARIABLE = {"Rice cultivation", "Urea application",
                 "Field burning of residues", "Managed soils"}


def _agriculture(resolution):
    return [r for r in read_rows(os.path.join(OUTPUTS, "pakemis_joint_uncertainty.csv"))
            if r["module"] == "agriculture" and r["resolution"] == resolution]


class TestTheDeterministicSideReconciles(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _agriculture("annual_national")

    def test_the_sweep_found_the_categories(self):
        self.assertEqual(len(self.rows), 6)

    def test_the_deterministic_total_is_the_published_control(self):
        """EXACT, because it is the same atomic table the external control reads."""
        total = sum(float(r["deterministic_Mt"]) for r in self.rows)
        self.assertAlmostEqual(total, CONTROL_TOTAL, places=5)

    def test_every_category_matches_the_atomic_product(self):
        atomic = collections.defaultdict(float)
        for row in read_rows(os.path.join(OUTPUTS, "pakemis_atomic_annual.csv")):
            if row["period_id"] != "FY2023-24" or row["sector_id"] != "agriculture":
                continue
            if row["co2e_Mt_AR5"] in ("", None):
                continue
            atomic[row["category"]] += float(row["co2e_Mt_AR5"])
        for r in self.rows:
            self.assertAlmostEqual(float(r["deterministic_Mt"]), atomic[r["category"]],
                                   places=5, msg=r["category"])

    def test_the_divergence_column_is_the_difference(self):
        for r in self.rows:
            self.assertAlmostEqual(
                float(r["estimate_Mt"]) - float(r["deterministic_Mt"]),
                float(r["mc_mean_minus_deterministic_Mt"]), places=5, msg=r["category"])

    def test_the_mc_mean_is_not_the_deterministic_estimate(self):
        """The negative control for this whole pass: if these ever coincide exactly, either
        the Monte Carlo has stopped being a Monte Carlo or the column has been quietly
        repointed at the deterministic figure, and the distinction this pass drew is gone."""
        total_mc = sum(float(r["estimate_Mt"]) for r in self.rows)
        self.assertNotAlmostEqual(total_mc, CONTROL_TOTAL, places=4)

    def test_it_agrees_with_the_common_ensemble(self):
        ensemble = {r["name"]: float(r["deterministic_Mt"])
                    for r in read_rows(os.path.join(OUTPUTS,
                                                    "pakemis_ensemble_summary.csv"))}
        for r in self.rows:
            if r["category"] in ensemble:
                self.assertAlmostEqual(float(r["deterministic_Mt"]),
                                       ensemble[r["category"]], places=4, msg=r["category"])


class TestTimingIsPricedWhereItCanBe(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _agriculture("monthly_national")

    def test_continuous_processes_carry_no_timing_dispersion(self):
        """A timing dispersion on a stock-driven process would be a number about nothing."""
        for r in self.rows:
            if r["category"] in CONTINUOUS:
                self.assertEqual(float(r["timing_pct"]), 0.0, r["category"])
                self.assertEqual(r["timing_status"], "declared-unpriced", r["category"])

    def test_every_status_is_typed(self):
        for r in self.rows:
            self.assertIn(r["timing_status"], ("priced", "declared-unpriced"), r["category"])
            if r["timing_status"] == "priced":
                self.assertTrue(r["timing_source"], r["category"])
                self.assertGreater(float(r["timing_pct"]), 0.0, r["category"])

    def test_the_unpriced_time_variable_streams_are_a_declared_gap(self):
        """Rice and urea are genuinely time-variable and carry no timing dispersion. That is
        a GAP, not a physical answer, and this test exists so it stays visible rather than
        being read as 'nothing to price here'. Pricing them needs a defensible dispersion for
        the rice calendar boundary and the fertiliser monthly profile; inventing one to fill
        the rectangle is what this pass was asked not to do."""
        unpriced = {r["category"] for r in self.rows
                    if r["category"] in TIME_VARIABLE
                    and r["timing_status"] == "declared-unpriced"}
        self.assertEqual(unpriced, {"Rice cultivation", "Urea application"},
                         "the declared timing gap has moved; if a stream was priced, say so "
                         "here, and if one stopped being priced, that is a regression")


if __name__ == "__main__":
    unittest.main()
