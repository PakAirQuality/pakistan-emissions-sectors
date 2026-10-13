"""Tests for the MMS (manure-management) GLEAM cross-check + sensitivity.

Guarantees: GLEAM MMS shares are well-formed (sum to 1 per species); the cross-check computes both the
current (primary) and GLEAM manure N2O and finds GLEAM materially higher (the dry-lot mismatch); and the
layer changes NO control total (the current split stays primary, national total unchanged).
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest
from _support import ROOT


GLEAM_CSV = asset_path(ROOT, "data", "gleam_mms.csv")


class TestGleamMmsData(unittest.TestCase):
    def test_shares_sum_to_one_per_species(self):
        by_sp = {}
        for r in csv.DictReader(open(GLEAM_CSV)):
            by_sp.setdefault(r["species"], 0.0)
            by_sp[r["species"]] += float(r["share"])
        self.assertTrue(by_sp)
        for sp, s in by_sp.items():
            self.assertAlmostEqual(s, 1.0, delta=1e-3, msg=sp)

    def test_cattle_drylot_dominant(self):
        # the crux: GLEAM puts most cattle manure in dry lot (unlike the current split)
        rows = [r for r in csv.DictReader(open(GLEAM_CSV)) if r["species"] == "cattle"]
        drylot = sum(float(r["share"]) for r in rows if r["system"] == "drylot")
        self.assertGreater(drylot, 0.4)


class TestCrossCheck(unittest.TestCase):
    def test_gleam_higher_and_no_magnitude_change(self):
        from pkinv.sectors.agriculture import mms_sensitivity as M
        card = M.compute()
        self.assertFalse(card["adds_magnitude"])
        self.assertGreater(card["gleam"]["direct_n2o_Gg"], card["current"]["direct_n2o_Gg"])
        self.assertGreater(card["gleam_vs_current_direct_n2o_ratio"], 1.5)   # ~2.6x
        # current stays closer to FAOSTAT than GLEAM (why it's primary)
        f = card["faostat_manure_Mt_co2e"]
        self.assertLess(abs(card["current"]["manure_total_Mt_co2e"] - f),
                        abs(card["gleam"]["manure_total_Mt_co2e"] - f))

    def test_primary_inventory_unchanged(self):
        # the cross-check must not mutate the shipped mms_shares.csv / control totals
        from pkinv.sectors.agriculture.ef_library import InventoryData
        from pkinv.sectors.agriculture import manure
        data = InventoryData()
        comps, _ = manure.compute(data)
        direct = sum(c["emissions_Gg"] for c in comps if c["gas"] == "N2O" and "Direct" in c["subitem"])
        self.assertAlmostEqual(direct, 23.34, delta=0.5)                   # primary split, not GLEAM's 61


if __name__ == "__main__":
    unittest.main()
