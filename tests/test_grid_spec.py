"""The 0.05-degree lattice is a published coordinate system, not a consequence of an input file.

Until rc45 the extent was whatever data/gis/PAK_ADM1.geojson's total_bounds implied, snapped
outward to a multiple of 0.05 and recomputed on every call. Replace that boundary with a
differently-generalised one and every cell renumbers silently: the cached rasters' 267x340
filenames stop matching, the intersection table stops aligning, and a published product's cell
ids stop meaning what the release that shipped them said they meant.

The lattice is declared now and build_grid asserts against it. A revised boundary makes a new
MASK version, not a new lattice.
"""
import unittest

from _support import DATA  # noqa: F401  (import shape shared with the other GIS tests)
from pkinv.assets import asset_path


class TestTheLatticeIsFrozen(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from pkinv.core.gis.grid import build_grid
        cls.grid = build_grid()

    def test_the_built_grid_matches_the_declared_spec(self):
        from pkinv.core.gis.grid import GRID_SPEC
        minx, miny, maxx, maxy = self.grid.bounds
        self.assertAlmostEqual(minx, GRID_SPEC["west"], places=10)
        self.assertAlmostEqual(maxx, GRID_SPEC["east"], places=10)
        self.assertAlmostEqual(miny, GRID_SPEC["south"], places=10)
        self.assertAlmostEqual(maxy, GRID_SPEC["north"], places=10)
        self.assertEqual((self.grid.height, self.grid.width),
                         (GRID_SPEC["height"], GRID_SPEC["width"]))
        self.assertEqual(self.grid.height * self.grid.width, GRID_SPEC["cells"])
        self.assertEqual(self.grid.crs, GRID_SPEC["crs"])

    def test_a_moved_extent_RAISES_rather_than_reshaping_the_grid(self):
        """The guard has to be shown failing on the thing it prevents. A spec that disagrees
        with the boundary file by one cell must stop the build, not renumber it."""
        from pkinv.core.gis import grid as grid_mod
        original = dict(grid_mod.GRID_SPEC)
        try:
            grid_mod.GRID_SPEC["north"] = original["north"] + grid_mod.RES
            with self.assertRaises(ValueError) as caught:
                grid_mod.build_grid()
            message = str(caught.exception)
            self.assertIn("pk_0p05_epsg4326_v1", message)
            self.assertIn("MASK version", message)
        finally:
            grid_mod.GRID_SPEC.clear()
            grid_mod.GRID_SPEC.update(original)
        # and the real spec still builds
        grid_mod.build_grid()

    def test_row_zero_is_the_northernmost_row(self):
        from pkinv.core.gis.grid import GRID_SPEC
        self.assertEqual(GRID_SPEC["row_zero"], "north")
        top_left_lat = self.grid.transform * (0, 0)
        self.assertAlmostEqual(top_left_lat[1], GRID_SPEC["north"], places=10)


class TestThePakistanFractionIsExact(unittest.TestCase):
    """A published land fraction, so a consumer can turn Gg per cell into a flux per square
    kilometre OF LAND. It is not what the allocator uses and must not become that:
    cube._fraction_matrix renormalises the OUTSIDE share away on purpose, because a coastal
    cell's field value is land activity and splitting it to the sea would dilute a known
    facility into the water."""

    @classmethod
    def setUpClass(cls):
        from pkinv.core.gis.grid import build_grid, cell_area_km2, pakistan_fraction
        cls.grid = build_grid()
        cls.area = cell_area_km2(cls.grid)
        cls.fraction = pakistan_fraction(cls.grid)

    def test_the_fraction_is_a_fraction(self):
        self.assertGreaterEqual(float(self.fraction.min()), 0.0)
        self.assertLessEqual(float(self.fraction.max()), 1.0)

    def test_it_closes_against_the_national_area(self):
        """geoBoundaries' Pakistan, AJK and GB included, is about 881,913 km2."""
        land = float((self.fraction * self.area).sum())
        self.assertAlmostEqual(land / 881913.0, 1.0, delta=0.02)

    def test_it_is_STRICTLY_BETTER_than_the_boolean_mask(self):
        """The label rasters are all_touched, so a cell the boundary merely clips counts whole.
        That is right for placing a facility and wrong for reporting an area, and the gap is
        the reason this variable is published rather than left to the consumer."""
        control = 881913.0
        exact = float((self.fraction * self.area).sum())
        boolean = float(self.area[self.grid.province_id >= 0].sum())
        self.assertLess(abs(exact - control), abs(boolean - control))
        self.assertGreater(boolean, exact)      # all_touched can only over-count

    def test_land_and_outside_partition_every_cell(self):
        import csv
        import os
        import numpy as np
        from pkinv.core.gis.grid import DATA_GIS
        total = np.zeros((self.grid.height, self.grid.width))
        path = asset_path(DATA_GIS, "adm2_intersections_%dx%d.csv"
                          % (self.grid.height, self.grid.width))
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(l for l in handle if not l.startswith("#")):
                total[int(row["row"]), int(row["col"])] += float(row["area_fraction"])
        self.assertAlmostEqual(float(total.min()), 1.0, places=5)
        self.assertAlmostEqual(float(total.max()), 1.0, places=5)


if __name__ == "__main__":
    unittest.main()


class TestEdgarAlignment(unittest.TestCase):
    """rc47 Wave 6, the twenty-first review's alignment finding made arithmetic.

    Three of the frozen lattice's four edges are ODD multiples of 0.05 - EDGAR cell
    CENTRES - so an even-index 2x2 block sum is offset by one fine cell on both axes,
    an odd-index 2x2 tiles EDGAR exactly (interior 266x338 -> 133x169), and neither
    dimension is even so no naive reshape works either way. The derived product
    outputs/pakemis_grid_0p1_edgar_aligned.nc carries the exact aggregation with the
    three half-covered boundary strips declared in coverage_fraction."""

    def test_the_edge_parity_is_what_the_aggregation_assumes(self):
        from pkinv.core.gis.grid import GRID_SPEC as GRID
        west, east = GRID["west"], GRID["east"]
        south, north = GRID["south"], GRID["north"]
        for name, edge, odd in (("west", west, True), ("east", east, True),
                                ("north", north, True), ("south", south, False)):
            k = round(edge / 0.05)
            self.assertAlmostEqual(edge, k * 0.05, places=9,
                                   msg="%s edge off the 0.05 lattice" % name)
            self.assertEqual(k % 2 == 1, odd,
                             "%s edge parity moved; the odd-parity 2x2 identity and "
                             "the NH3 aggregation's assertions both rest on it" % name)
        # width is even but offset (an even reshape lands on the WRONG parity),
        # height is odd (no clean reshape at all) - both facts the aggregation
        # in build_grid_01deg.py routes around cell-by-cell
        self.assertEqual((GRID["width"] % 2, GRID["height"] % 2), (0, 1))
        # the interior tiling counts, exactly: columns 1..338 and rows 1..266
        self.assertEqual(((GRID["width"] - 2) // 2, (GRID["height"] - 1) // 2),
                         (169, 133))
