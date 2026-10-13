"""The documented uncertainty inputs must match the Monte-Carlo's lognormal parameterisation."""
import os
import sys
import unittest


from pkinv.eval import uncertainty_inputs as ui  # noqa: E402


class TestUncertaintyInputs(unittest.TestCase):
    def setUp(self):
        self.rows = ui.derive()
        self.by = {r["category"]: r for r in self.rows}

    def test_sigma_matches_montecarlo_convention(self):
        """sigma = sqrt(ln(1 + rel_sd^2)), rel_sd = (u/100)/Z95 - core.montecarlo's
        exact CV inversion. The rc7 edition of this register used the linear shortcut
        (u/100)/Z95, one of the three conventions the sixth review's harmonisation
        collapsed to one; this test pinned the outlier and now pins the convention."""
        import math
        for r in self.rows:
            rel_sd = (r["combined_uncert_pct_95"] / 100.0) / ui.Z95
            expected = math.sqrt(math.log(1.0 + rel_sd * rel_sd))
            self.assertAlmostEqual(r["lognormal_sigma"], round(expected, 4), places=4)

    def test_all_lognormal_independent(self):
        for r in self.rows:
            self.assertEqual(r["distribution"], "lognormal")
            self.assertEqual(r["correlation"], "independent")

    def test_total_present_and_95pct(self):
        self.assertIn("TOTAL", self.by)
        self.assertAlmostEqual(self.by["TOTAL"]["combined_uncert_pct_95"], 19.2, delta=0.5)


if __name__ == "__main__":
    unittest.main()
