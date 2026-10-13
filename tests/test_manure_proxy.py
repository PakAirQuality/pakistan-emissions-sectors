"""The manure_applied proxy has two representations that must not drift apart.

It is defined as a per-cell intersection (cropland x livestock density). The grid layer uses that
array directly; the province layer uses a row in data/province_shares.csv derived from it. Those are
one definition in two forms, unlike every other proxy where the two are independent measurements --
so the derivation has to be checked, not assumed.
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest

from pkinv.paths import DATA, OUTPUTS
from _support import ROOT

SHARES = asset_path(DATA, "province_shares.csv")
PROVS = ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Other"]


def _row(proxy):
    for r in csv.DictReader(open(SHARES, newline="", encoding="utf-8")):
        if r["proxy"] == proxy:
            return {p: float(r[p]) for p in PROVS}
    return None


class TestManureAppliedShares(unittest.TestCase):
    def setUp(self):
        self.row = _row("manure_applied")
        self.assertIsNotNone(self.row, "manure_applied missing from province_shares.csv")

    def test_shares_sum_to_one(self):
        """downscale.allocate_rows rejects anything off by more than 1e-6, so the rounding in the
        writer has to be absorbed, not left to chance."""
        self.assertAlmostEqual(sum(self.row.values()), 1.0, places=9)

    def test_matches_the_grid_derivation(self):
        try:
            from pkinv.core.gis.grid import build_grid
            from pkinv.sectors.agriculture.gis import derive_manure_proxy as dmp
            # build_grid reads the cached boundary geojson and raises when it is absent,
            # so it belongs inside the guard alongside the imports.
            grid = build_grid()
        except Exception as e:                                  # rasterio/grid/boundaries unavailable
            self.skipTest("GIS stack unavailable: %s" % e)
        if grid.province_id is None:
            self.skipTest("no province grid")
        try:
            derived = dmp.derive(grid)
        except ValueError as exc:
            self.skipTest("required cropland/livestock rasters unavailable: %s" % exc)
        for p in PROVS:
            self.assertAlmostEqual(self.row[p], derived[p], places=5,
                                   msg="%s: shipped %.6f vs derived %.6f"
                                       % (p, self.row[p], derived[p]))

    def test_is_not_reproducible_from_province_shares_alone(self):
        """The whole point of deriving from the grid: multiplying province shares and renormalising
        is a different operation. If this ever stops being true the derivation is not doing anything
        and the extra machinery should go."""
        crop, live = _row("crop_total"), _row("livestock_total")
        prod = {p: crop[p] * live[p] for p in PROVS}
        tot = sum(prod.values())
        naive = {p: prod[p] / tot for p in PROVS}
        worst = max(abs(naive[p] - self.row[p]) for p in PROVS)
        self.assertGreater(worst, 0.05,
                           "per-cell and province-level blends have converged (worst %.3f)" % worst)

    def test_sits_where_the_geography_implies_not_between_its_parents(self):
        """A dasymetric intersection is not an interpolation. Sindh should exceed BOTH parents (its
        cropland and its herds are the same Indus belt) and Balochistan should fall below both (its
        livestock are on rangeland far from any cropland)."""
        crop, live = _row("crop_total"), _row("livestock_total")
        self.assertGreater(self.row["Sindh"], max(crop["Sindh"], live["Sindh"]))
        self.assertLess(self.row["Balochistan"], min(crop["Balochistan"], live["Balochistan"]))


if __name__ == "__main__":
    unittest.main()
