"""The covered air total says how much it leaves out at power stacks, and never adds it in.

WHY (rc69). Coal power grew from almost nothing to the largest thermal source over the core
period, and its pollutants are outside the central product. The review asked for the
consequence of the omission to be carried into totals and trends. The pair must count only
fuels the covered panel does not already hold: for SO2 that excludes furnace oil and diesel,
which are covered, so counting them would report an omission that is not one.
"""
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                     # noqa: E402
from pkinv.report import air_power_omission as module                   # noqa: E402


class TestTheOmission(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(module.OUT)
        cls.by = {(r["period_id"], r["pollutant"]): r for r in cls.rows}

    def test_it_regenerates_identically(self):
        run = subprocess.run([sys.executable, "-m", module.__name__, "--check"], cwd=ROOT,
                             capture_output=True, text=True,
                             env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr)

    def test_covered_so2_fuels_are_not_counted_as_omitted(self):
        for row in self.rows:
            if row["pollutant"] == "SO2":
                for fuel in module.COVERED_SO2_FUELS:
                    self.assertNotIn(fuel, row["omitted_fuels"].split(";"))

    def test_the_pair_is_ordered_and_coal_is_inside_it(self):
        for row in self.rows:
            low, high = float(row["omitted_power_controlled_Gg"]), float(row["omitted_power_uncontrolled_Gg"])
            self.assertLessEqual(low, high + 1e-9, row["period_id"])
            self.assertLessEqual(float(row["omitted_coal_uncontrolled_Gg"]), high + 1e-9)

    def test_the_latest_so2_omission_is_large_and_coal(self):
        row = self.by[("FY2024-25", "SO2")]
        self.assertAlmostEqual(float(row["omitted_uncontrolled_share_of_covered_pct"]), 64.18, delta=0.05)
        self.assertGreater(float(row["omitted_coal_uncontrolled_Gg"]) /
                           float(row["omitted_power_uncontrolled_Gg"]), 0.99)
        self.assertLess(float(self.by[("FY2015-16", "SO2")]["omitted_uncontrolled_share_of_covered_pct"]), 1)


if __name__ == "__main__":
    unittest.main()
