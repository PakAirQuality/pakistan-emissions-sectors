"""The 2024 livestock census reaches the grid through the canonical crosswalk (rc42, S-2).

rc41 name-matched the census to grid shapes with a bare normaliser and left 15 shapes to a
GLW proxy (25.5 Mt of enteric and manure mass) while 38 census districts went unread. The
join now resolves every census district to its canonical unit; units with a polygon land
on their shape (several on one shape sum), the two without a polygon (Cholistan Area,
Larkana District) are named rows of the panel, and a named-province shape the census does
not reach is a build failure.
"""
import os
import unittest

from _support import DATA, OUTPUTS, data_rows, rows

CENSUS = os.path.join("activity", "livestock_district_2024.csv")
LIVESTOCK = ("Enteric fermentation", "Manure management")


class TestEveryCensusDistrictIsConsumedOnce(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from pkinv.core import adm2
        cls.adm2 = adm2
        cls.canonical = adm2.load_canonical()
        cls.census = data_rows(CENSUS, comments=False)
        cls.panel = rows("district_totals_2024.csv")

    def test_every_census_district_resolves_to_a_named_province_unit_or_is_outside(self):
        for r in self.census:
            unit = self.canonical[self.adm2.resolve(r["district"])]
            self.assertIn(unit["province_id"], ("Punjab", "Sindh", "Khyber Pakhtunkhwa",
                                                "Balochistan", "Other"), r["district"])

    def test_the_two_no_polygon_units_are_named_rows_of_the_panel(self):
        names = {r["district"] for r in self.panel if r["category"] in LIVESTOCK}
        for unit in ("Cholistan Area", "Larkana District"):
            self.assertIn(unit, names, "%s should carry its own census share as a row" % unit)
        for r in self.panel:
            if r["district"] in ("Cholistan Area", "Larkana District"):
                self.assertIn(r["category"], LIVESTOCK, r["district"])
                self.assertGreater(float(r["co2e_Mt_AR5"]), 0.0)
                self.assertEqual(self.canonical[r["adm2_id"]]["shape_id"], "", r["district"])

    def test_no_grid_shape_rides_a_proxy_for_livestock(self):
        from pkinv.sectors.agriculture.gis import district_downscale as dd
        from pkinv.core.gis.grid import build_grid
        from pkinv.sectors.agriculture.gis.run_gis import resolve_proxies
        grid = build_grid()
        proxies, _cat_proxy, _ = resolve_proxies(grid)
        shares, matched, no_shape = dd._census_livestock_shares(grid, proxies["glw_livestock"])
        self.assertGreater(matched, 100)
        self.assertEqual(no_shape, 2)
        for prov in dd.NAMED:
            total = sum(shares[d] for d in grid.districts_in(prov)) + sum(dd.NO_SHAPE[prov].values())
            self.assertAlmostEqual(total, 1.0, places=9, msg=prov)

    def test_the_province_controls_are_unchanged_by_the_join(self):
        """The join moves mass between shapes inside a province and nowhere else."""
        matrix = {}
        for r in self.panel:
            matrix[(r["province"], r["category"])] = matrix.get((r["province"], r["category"]), 0.0) \
                + float(r["co2e_Mt_AR5"])
        provincial = {(r["province"], c): float(r[c]) for r in rows("provincial_totals_2024.csv")
                      for c in r if c not in ("province", "TOTAL")}
        for (prov, cat), value in matrix.items():
            key = (prov if prov != "Other" else "Other", cat)
            if key in provincial:
                self.assertAlmostEqual(value, provincial[key], places=3, msg=str(key))


if __name__ == "__main__":
    unittest.main()
