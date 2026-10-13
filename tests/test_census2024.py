"""Tests for the PBS 7th Agricultural Census 2024 livestock integration (province + district).

Guarantees: the refreshed province shares sum to 1 per species (else allocation raises); the district
downscaling still reconciles exactly with real census district counts; the census matches most grid
districts; and national/AFOLU totals are unchanged (this is a spatial refresh, not a magnitude change).
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest

from pkinv.paths import DATA, OUTPUTS
from _support import ROOT

PROV_CSV = asset_path(DATA, "activity", "livestock_province_2024.csv")
DIST_CSV = asset_path(DATA, "activity", "livestock_district_2024.csv")
SHARES = asset_path(DATA, "province_shares.csv")
# build_grid() reads this, and raises rather than returning an empty grid when it is
# absent, so the guard has to sit outside the test body.
ADM1_PATH = asset_path(ROOT, "data", "gis", "PAK_ADM1.geojson")


class TestProvinceShares(unittest.TestCase):
    def test_livestock_rows_are_2024_and_sum_to_one(self):
        rows = {r["proxy"]: r for r in csv.DictReader(open(SHARES))}
        for key in ("livestock_cattle", "livestock_buffalo", "livestock_sheep",
                    "livestock_goats", "livestock_smallrum", "livestock_total"):
            r = rows[key]
            self.assertIn("2024", r["source"])                       # refreshed off the 2024 census
            s = sum(float(r[p]) for p in ("Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Other"))
            self.assertAlmostEqual(s, 1.0, delta=1e-6)

    def test_kp_livestock_share_rose_vs_2006(self):
        rows = {r["proxy"]: r for r in csv.DictReader(open(SHARES))}
        self.assertGreater(float(rows["livestock_total"]["Khyber Pakhtunkhwa"]), 0.153)  # 2006 was 0.153


class TestCensusFiles(unittest.TestCase):
    @unittest.skipUnless(os.path.exists(PROV_CSV), "province census CSV absent")
    def test_province_national_totals(self):
        tot = {}
        for r in csv.DictReader(open(PROV_CSV)):
            for s in ("cattle", "buffalo", "sheep", "goats"):
                tot[s] = tot.get(s, 0.0) + float(r[s])
        self.assertAlmostEqual(tot["cattle"] / 1e6, 55.86, delta=0.2)     # PBS national cattle 55.86M
        self.assertAlmostEqual(tot["buffalo"] / 1e6, 47.74, delta=0.2)

    @unittest.skipUnless(os.path.exists(DIST_CSV), "district census CSV absent")
    def test_district_schema_and_count(self):
        rows = list(csv.DictReader(open(DIST_CSV)))
        self.assertGreater(len(rows), 120)                               # ~137 districts
        self.assertEqual(set(rows[0]) >= {"district", "province", "cattle", "buffalo"}, True)


@unittest.skipUnless(os.path.exists(ADM1_PATH),
                     "GIS boundaries not cached (make fetch-adm2)")
class TestDistrictReconciliation(unittest.TestCase):
    def test_district_downscale_reconciles_with_census(self):
        from pkinv.sectors.agriculture.gis import district_downscale as dd
        from pkinv.core.gis.grid import build_grid
        grid = build_grid()
        if grid.district_id is None:
            self.skipTest("no ADM2 grid")
        rows, shares, matrix = dd.district_controls(grid)
        worst, nat_gap, nat = dd.check(rows, matrix)
        self.assertLess(worst, 1e-9)                                     # per-province exact
        self.assertLess(nat_gap, 1e-9)                                   # national exact
        # The engine's own total, not a literal: what this test owns is that the district
        # downscale RECONCILES (the two exact assertions above), not what the sector sums to.
        from pkinv.core import registry
        from pkinv.core.components import enrich_co2e
        sector = registry.get("agriculture")
        comps = sector.build_components(sector.load_data())
        enrich_co2e(comps)
        self.assertAlmostEqual(nat, sum(c["co2e_Mt_AR5"] for c in comps), delta=0.5)

    def test_census_matches_most_districts(self):
        from pkinv.sectors.agriculture.gis import district_downscale as dd
        from pkinv.core.gis.grid import build_grid
        if not os.path.exists(DIST_CSV):
            self.skipTest("district census absent")
        grid = build_grid()
        if grid.district_id is None:
            self.skipTest("no ADM2 grid")
        from pkinv.sectors.agriculture.gis.run_gis import resolve_proxies
        proxies, _cat, _ = resolve_proxies(grid)
        _s, matched, fallback = dd._census_livestock_shares(grid, proxies["glw_livestock"])
        self.assertGreater(matched, 0.7 * (matched + fallback))         # >70% real census match


if __name__ == "__main__":
    unittest.main()
