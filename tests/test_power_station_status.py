"""The coal fleet's commissioning check is a measurement, and it currently measures zero.

The 23rd review read the power geography as the FY2023-24 station pattern applied to every
year. pakemis_power_station_status.csv joins each period's ACTUAL station pool to GEM unit
start and retired years; these guards hold the product to its own claims - every period
present, every pooled station checked, no station carrying coal outside its GEM window -
and the exposure table to the registry it summarises.
"""
import csv
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS = os.path.join(ROOT, "outputs", "pakemis_power_station_status.csv")
PERIODS = os.path.join(ROOT, "data", "shared", "lookups", "periods.csv")


def rows(path):
    with io.open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheCommissioningCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.status = rows(STATUS)
        cls.periods = [r["period_id"] for r in rows(PERIODS)]

    # rc66: THE PROVINCIAL HALF OF THIS FILE IS GONE, ON PURPOSE. It tested
    # pakemis_power_fixed_pattern_exposure.csv, the measurement of how far the fixed
    # reference-year provincial vector sat from each period's own coal stations, and one of
    # its tests was a tripwire: "the historical exposure has vanished; either the provincial
    # vector is year-keyed now (good: retire this guard with the re-base) or the pool stopped
    # measuring". The vector is year-keyed now (pkinv.sectors.power.province_panel). The
    # guard is retired with the re-base, as it asked, and what moved is held by
    # tests/test_power_provincial_basis.py.

    def test_no_station_carries_coal_outside_its_gem_window(self):
        bad = [(r["period_id"], r["station"], r["window_check"]) for r in self.status
               if r["window_check"] in ("before_gem_start", "after_gem_retired")]
        self.assertEqual(bad, [], "coal placed on a station GEM says was not operating")
        for r in self.status:
            self.assertIn(r["window_check"], ("inside_window", "no_gem_window"))

    def test_every_pooled_station_with_mass_has_a_gem_window(self):
        """A station the check cannot see is a station the claim does not cover."""
        unseen = [(r["period_id"], r["station"]) for r in self.status
                  if r["window_check"] == "no_gem_window" and float(r["pool_share"]) > 0]
        self.assertEqual(unseen, [])
        # Jamshoro Coal Power Unit-1 burned testing coal in FY2024-25. Until rc68 GEM's
        # "Jamshoro power station" was not joined to NEPRA's unit name and the station had
        # no window; the join is now declared (gem_audit.GEM_TO_LEDGER) and the unit sits
        # inside GEM's operating window. Keep the independently sourced consumption.
        from pkinv.assets import asset_path
        from pkinv.paths import DATA
        from pkinv.core.io import read_rows
        held = read_rows(asset_path(DATA, "activity", "power", "plant_fuel_2024_25.csv"))
        jamshoro = [r for r in held if "Jamshoro" in r["plant"] and r["fuel"] == "Coal"]
        self.assertEqual(len(jamshoro), 1)
        self.assertAlmostEqual(float(jamshoro[0]["quantity"]), 158.031, places=3)

    def test_pool_shares_sum_to_one_per_period(self):
        for p in self.periods:
            share = sum(float(r["pool_share"]) for r in self.status if r["period_id"] == p)
            self.assertAlmostEqual(share, 1.0, places=5, msg=p)

    def test_it_regenerates_identically(self):
        before = open(STATUS, "rb").read()
        run = subprocess.run([sys.executable, "-m", "pkinv.report.power_station_status"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertEqual(before, open(STATUS, "rb").read())


if __name__ == "__main__":
    unittest.main()
