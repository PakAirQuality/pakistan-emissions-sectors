"""The year-on-year coal decomposition closes, agrees with the GHG split, and says what moved SO2.

WHY (rc69). The review asked how much of the latest-year coal revision is physical activity
and how much is source vintage and consumer allocation. The GHG split could not answer it for
air pollutants: one industrial intensity makes a brick-versus-cement reallocation invisible
to CO2, while brick-kiln SO2 follows booked brick coal and cement SO2 follows clinker. These
tests hold the decomposition to its identity on every row and to the published GHG split, and
pin the FY2024-25 SO2 answer.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                     # noqa: E402
from pkinv.sectors.industry import coal_change_decomposition as module  # noqa: E402

TERMS = ("d_source_vintage", "d_supply_balance", "d_allocation_seam", "d_consumer_split",
         "d_factor", "d_power_station_coal", "d_household_coal")


class TestTheDecomposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(module.OUT)
        cls.by = {(r["period_id"], r["species"]): r for r in cls.rows}

    def test_every_row_closes_on_its_terms(self):
        self.assertGreaterEqual(len(self.rows), 9 * 6)
        for r in self.rows:
            total = sum(float(r[t]) for t in TERMS)
            self.assertAlmostEqual(total, float(r["d_coal_emissions"]), delta=1e-4,
                                   msg="%s %s" % (r["period_id"], r["species"]))

    def test_the_ghg_terms_reproduce_the_published_split(self):
        """GHG cannot see the consumer split (one intensity), and its physical and seam terms
        are the published supply-balance and seam changes."""
        published = {r["period_id"]: r for r in read_rows(module.REALLOCATION)}
        # the published kt columns are whole kilotonnes, so the two splits can differ by about
        # one kt at the industrial intensity (0.0025 Mt); the totals agree exactly (closure)
        tol = 0.003
        for r in self.rows:
            if r["species"] != module.GHG:
                continue
            p = published[r["period_id"]]
            self.assertAlmostEqual(float(r["d_consumer_split"]), 0.0, delta=1e-6)
            self.assertAlmostEqual(
                float(r["d_supply_balance"]) + float(r["d_power_station_coal"])
                + float(r["d_household_coal"]), float(p["d_supply_balance_yoy_Mt"]), delta=tol)
            self.assertAlmostEqual(
                float(r["d_allocation_seam"]) + float(r["d_source_vintage"])
                + float(r["d_factor"]), float(p["d_allocation_seam_yoy_Mt"]), delta=tol)

    def test_cement_coal_carries_no_air_factor(self):
        for r in self.rows:
            if r["species"] != module.GHG:
                self.assertEqual(float(r["factor_other"]), 0.0)

    def test_the_latest_year_so2_rise_is_allocation_not_activity(self):
        r = self.by[("FY2024-25", "SO2")]
        self.assertAlmostEqual(float(r["d_coal_emissions"]), 173.21, delta=0.01)
        self.assertAlmostEqual(float(r["d_source_vintage"]), 9.26, delta=0.01)
        self.assertAlmostEqual(float(r["d_supply_balance"]), -6.08, delta=0.01)
        self.assertAlmostEqual(float(r["d_allocation_seam"]), 50.50, delta=0.01)
        self.assertAlmostEqual(float(r["d_consumer_split"]), 119.53, delta=0.01)
        self.assertLess(float(r["national_change_without_allocation"]), 0)

    def test_the_ghg_seam_is_the_manuscripts_69_percent(self):
        r = self.by[("FY2024-25", module.GHG)]
        self.assertAlmostEqual(float(r["allocation_share_of_national_change_pct"]), 69.0, delta=0.05)

    def test_it_regenerates_identically(self):
        run = subprocess.run([sys.executable, "-m", module.__name__, "--check"], cwd=ROOT,
                             capture_output=True, text=True,
                             env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)


if __name__ == "__main__":
    unittest.main()
