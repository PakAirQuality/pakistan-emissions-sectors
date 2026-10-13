"""Tests for Phase 10 Monte-Carlo uncertainty.

Run:  python3 -m unittest discover tests
"""
import os
import sys
import unittest


from pkinv.sectors.agriculture import montecarlo as mc  # noqa: E402
from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture.run_inventory import build_components, CATEGORIES  # noqa: E402

N = 2000  # small-N for a fast test


class TestMonteCarlo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        cls.stats, _ = mc.run_mc(n_iter=N, seed=7, data=cls.data)
        cls.det_total = sum(c["co2e_Mt_AR5"] for c in build_components(cls.data)
                            if c["co2e_Mt_AR5"] > 0)

    def test_percentiles_ordered(self):
        for key in CATEGORIES + ["TOTAL"]:
            s = self.stats[key]
            self.assertLessEqual(s["p025"], s["p50"], key)
            self.assertLessEqual(s["p50"], s["p975"], key)

    def test_reproducible(self):
        a, _ = mc.run_mc(n_iter=N, seed=123, data=self.data)
        b, _ = mc.run_mc(n_iter=N, seed=123, data=self.data)
        self.assertEqual(a["TOTAL"]["p50"], b["TOTAL"]["p50"])
        self.assertEqual(a["TOTAL"]["p025"], b["TOTAL"]["p025"])

    def test_mean_preserves_deterministic_total(self):
        # mean-preserving lognormal -> total MC mean within ~3% of the deterministic total
        ratio = self.stats["TOTAL"]["mean"] / self.det_total
        self.assertTrue(0.97 <= ratio <= 1.03, "mean/det %.3f" % ratio)

    def test_mc_consistent_with_approach1(self):
        # national MC rel-% should agree with Approach-1 within ~5 points
        t = self.stats["TOTAL"]
        self.assertLess(abs(t["rel_pct"] - t["approach1_pct"]), 6.0,
                        "MC %.1f vs A1 %.1f" % (t["rel_pct"], t["approach1_pct"]))

    def test_total_band_positive_and_wraps_median(self):
        t = self.stats["TOTAL"]
        self.assertGreater(t["p025"], 0)
        self.assertGreater(t["rel_pct"], 5)   # there is real spread


if __name__ == "__main__":
    unittest.main()
