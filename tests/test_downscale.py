"""Tests for Phase 3 provincial downscaling.

Run:  python3 -m unittest discover tests
"""
import os
import sys
import unittest


from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture.run_inventory import build_components  # noqa: E402
from pkinv.sectors.agriculture import downscale  # noqa: E402


class TestDownscale(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        cls.components = build_components(cls.data)
        cls.shares = downscale.load_shares()

    def test_every_proxy_sums_to_one(self):
        for proxy, sh in self.shares.items():
            self.assertAlmostEqual(sum(sh.values()), 1.0, places=6, msg=proxy)

    def test_all_proxies_referenced_exist(self):
        # every proxy the map can emit must be present in province_shares.csv
        used = set(downscale.PROXY_MAP.values()) | set(downscale.PROXY_FALLBACK.values())
        for proxy in used:
            self.assertIn(proxy, self.shares, "missing proxy row: " + proxy)

    def test_every_component_maps_to_a_proxy(self):
        for c in self.components:
            proxy = downscale.proxy_for(c)
            self.assertIn(proxy, self.shares)

    def test_national_reconciliation(self):
        # sum over provinces of allocated emissions == national total
        national = sum(c["co2e_Mt_AR5"] for c in self.components)
        allocated = 0.0
        for c in self.components:
            proxy = downscale.proxy_for(c)
            for prov in downscale.PROVINCES:
                allocated += c["co2e_Mt_AR5"] * self.shares[proxy][prov]
        self.assertAlmostEqual(national, allocated, places=6)

    def test_per_category_reconciliation(self):
        # each category reconciles independently
        cats = {}
        for c in self.components:
            cats.setdefault(c["category"], 0.0)
            cats[c["category"]] += c["co2e_Mt_AR5"]
        alloc = {k: 0.0 for k in cats}
        for c in self.components:
            proxy = downscale.proxy_for(c)
            share_sum = sum(self.shares[proxy][p] for p in downscale.PROVINCES)
            alloc[c["category"]] += c["co2e_Mt_AR5"] * share_sum
        for k in cats:
            self.assertAlmostEqual(cats[k], alloc[k], places=6, msg=k)

    def test_punjab_is_largest(self):
        prov_tot = {p: 0.0 for p in downscale.PROVINCES}
        for c in self.components:
            proxy = downscale.proxy_for(c)
            for p in downscale.PROVINCES:
                prov_tot[p] += c["co2e_Mt_AR5"] * self.shares[proxy][p]
        self.assertEqual(max(prov_tot, key=prov_tot.get), "Punjab")


if __name__ == "__main__":
    unittest.main()
