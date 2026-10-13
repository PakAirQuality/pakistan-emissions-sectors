"""Tests for Phase 5 Tier 2 country-specific factors.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest


from pkinv.sectors.agriculture.ef_library import InventoryData, DATA_DIR  # noqa: E402
from pkinv.sectors.agriculture.run_inventory import build_components, soils_total  # noqa: E402

# Tier 2 parameters that must be sourced, not assumptions
SOURCED_PARAMS = ["dairy_cattle_share", "tam_buffalo", "tam_camels",
                  "irrigated_cropland_fraction", "rice_cultivation_period_days"]


class TestTier2(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        cls.comp = build_components(cls.data)

    def test_dairy_share_is_faostat(self):
        # FAOSTAT-derived cattle dairy share ~0.295, not the old 0.40 assumption
        self.assertAlmostEqual(self.data.p("dairy_cattle_share"), 0.295, places=2)

    def test_key_parameters_are_sourced(self):
        rows = {r["param"]: r["source"] for r in
                csv.DictReader(open(asset_path(DATA_DIR, "parameters.csv")))}
        for p in SOURCED_PARAMS:
            self.assertIn(p, rows, p)
            self.assertNotIn("ASSUMPTION", rows[p].upper(),
                             "%s still marked ASSUMPTION: %s" % (p, rows[p]))

    def test_buffalo_nex_raised_vs_tier1(self):
        # Tier 1 buffalo TAM was 295; Tier 2 herd-average is higher -> Nex up
        nex = self.data.nex_per_head("buffalo")
        tier1_nex = 0.32 * 295 * 365 / 1000.0
        self.assertGreater(nex, tier1_nex * 1.15)

    def test_rice_n_split_present(self):
        soils = [c["subitem"] for c in self.comp if c["category"] == "Managed soils"]
        self.assertTrue(any("rice EF1FR" in s for s in soils))
        self.assertTrue(any("upland" in s for s in soils))

    def test_ef1_sensitivity_increases_soils(self):
        # EF1=0.010 (aggregate) must give higher soils than the dry 0.005 default
        base_soils = soils_total(self.comp)
        hi = build_components(self.data, ef1_override=self.data.efv("soils", "EF1_agg"))
        self.assertGreater(soils_total(hi), base_soils)

    def test_total_in_plausible_band(self):
        total = sum(c["co2e_Mt_AR5"] for c in self.comp)
        self.assertTrue(200 < total < 250, "Tier 2 total %.1f outside band" % total)


if __name__ == "__main__":
    unittest.main()
