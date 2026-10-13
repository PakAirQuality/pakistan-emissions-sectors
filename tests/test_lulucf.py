"""Tests for Phase 9 LULUCF land sector.

Run:  python3 -m unittest discover tests
"""
import csv
import os
import sys
import unittest

from pkinv.assets import asset_path

from pkinv.lulucf import lulucf  # noqa: E402

PARAMS = asset_path(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "lulucf_params.csv")))


class TestLulucf(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comp = lulucf.compute()
        cls.net = lulucf.net(cls.comp)
        cls.by = {c["subcategory"]: c for c in cls.comp}

    def test_forest_is_sink_in_range(self):
        forest = next(c for c in self.comp if c["code"] == "3.B.1")
        self.assertLess(forest["co2e_Mt"], 0)              # sink
        self.assertTrue(-6 < forest["co2e_Mt"] < -2, forest["co2e_Mt"])

    def test_mangrove_is_small_sink(self):
        mang = next(c for c in self.comp if c["code"] == "3.B.4")
        self.assertLess(mang["co2e_Mt"], 0)
        self.assertTrue(-1.5 < mang["co2e_Mt"] < -0.1, mang["co2e_Mt"])

    def test_net_lulucf_is_sink_in_range(self):
        self.assertTrue(-7 < self.net < -2, "net LULUCF %.2f" % self.net)

    def test_cropland_grassland_not_estimated(self):
        """rc42 (P-2): NE, not 0.0 - the notation key and the flux cannot disagree."""
        for name in ("Cropland (SOC)", "Grassland (SOC)"):
            self.assertIsNone(self.by[name]["co2e_Mt"], name)
            self.assertEqual(self.by[name]["notation"], "NE", name)

    def test_mangrove_stock_reported(self):
        mang = next(c for c in self.comp if c["code"] == "3.B.4")
        self.assertIsNotNone(mang["c_stock_Mt_co2e"])
        self.assertGreater(mang["c_stock_Mt_co2e"], 100)   # large blue-carbon stock

    def test_all_params_sourced(self):
        for r in csv.DictReader(open(PARAMS)):
            self.assertTrue(r["source"].strip(), "unsourced param: " + r["param"])

    def test_forest_near_faostat(self):
        # forest sink should be within ~0.5-2x of FAOSTAT Forestland (-3.5 Mt)
        forest = next(c for c in self.comp if c["code"] == "3.B.1")
        ratio = forest["co2e_Mt"] / -3.5
        self.assertTrue(0.5 <= ratio <= 2.0, "forest/FAOSTAT ratio %.2f" % ratio)


if __name__ == "__main__":
    unittest.main()
