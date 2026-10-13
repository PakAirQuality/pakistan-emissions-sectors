"""Tests for Phase 4 gridded emission surfaces.

Uses a synthetic proxy so the suite runs offline; reconciliation must hold for ANY proxy.
Run:  python3 -m unittest discover tests
"""
import os
import sys
import tempfile
import unittest

import numpy as np


from pkinv.core.gis.grid import build_grid, PROVINCES, ADM1_PATH  # noqa: E402
from pkinv.core.gis.allocate import allocate  # noqa: E402
from pkinv.sectors.agriculture.downscale import provincial_matrix, CATEGORIES  # noqa: E402
from pkinv.core.gis import render  # noqa: E402

TOL = 1e-3  # Mt


@unittest.skipUnless(os.path.exists(ADM1_PATH),
                     "boundary cache absent - run src/pkinv/inventory/fetch + src/pkinv/gis/run_gis first")
class TestGis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid = build_grid()
        cls.matrix = provincial_matrix()
        inside = cls.grid.province_id >= 0
        idx = np.arange(cls.grid.height * cls.grid.width).reshape(
            cls.grid.height, cls.grid.width).astype(np.float64)
        # two distinct synthetic proxies to exercise per-category allocation
        cls.proxies = {"A": np.where(inside, 1.0 + (idx % 7), 0.0),
                       "B": np.where(inside, 1.0 + (idx % 5) * 3, 0.0)}
        # first three categories use A, the rest use B
        cls.cat_proxy = {c: ("A" if i < 3 else "B") for i, c in enumerate(CATEGORIES)}
        # A and B are SYNTHETIC and not in data/grid_proxy_semantics.csv, so their semantics
        # are declared here. rc45 made the allocator ask the registry what a proxy's numbers
        # ARE, and fail closed on a name that does not say - a silent default is how a
        # fraction came to be spread as though it were a count. Declaring them counts keeps
        # this fixture testing the allocation IDENTITY, which is what it is for, on raw
        # weights exactly as before.
        cls.alloc, cls.fallbacks = allocate(cls.grid, cls.proxies, cls.matrix, cls.cat_proxy,
                                            proxy_semantics={"A": "count", "B": "count"})
        cls.total = sum(cls.alloc.values())

    def test_grid_integrity(self):
        self.assertEqual(self.grid.crs, "EPSG:4326")
        minx, miny, maxx, maxy = self.grid.bounds
        self.assertTrue(minx < 62 and maxx > 76 and miny < 25 and maxy > 36)
        self.assertEqual(self.grid.province_id.shape, (self.grid.height, self.grid.width))

    def test_all_provinces_have_cells(self):
        for p in PROVINCES:
            self.assertGreater(int(self.grid.province_mask(p).sum()), 0, p)

    def test_national_reconciliation(self):
        ctrl = sum(sum(self.matrix[p].values()) for p in PROVINCES)
        self.assertAlmostEqual(float(self.total.sum()), ctrl, delta=TOL)

    def test_per_category_reconciliation(self):
        for cat in CATEGORIES:
            nat = sum(self.matrix[p][cat] for p in PROVINCES)
            self.assertAlmostEqual(float(self.alloc[cat].sum()), nat, delta=TOL, msg=cat)

    def test_per_province_reconciliation(self):
        for prov in PROVINCES:
            mask = self.grid.province_mask(prov)
            ctrl = sum(self.matrix[prov].values())
            got = float(sum(self.alloc[c][mask].sum() for c in CATEGORIES))
            self.assertAlmostEqual(got, ctrl, delta=TOL, msg=prov)

    def test_no_negative_or_nan_inside_country(self):
        inside = self.grid.province_id >= 0
        self.assertFalse(np.isnan(self.total[inside]).any())
        self.assertTrue((self.total[inside] >= 0).all())

    def test_manual_rice_proxy_when_present(self):
        from pkinv.core.gis.proxies import build_manual_proxy, get_proxy
        res = build_manual_proxy(self.grid, "spam_rice.tif")
        if res is None:
            self.skipTest("MapSPAM spam_rice.tif not supplied")
        rice, _ = res
        self.assertGreater(rice.sum(), 0)
        crop, _ = get_proxy("cropland", self.grid)
        rn, cn = rice / rice.sum(), crop / crop.sum()
        self.assertGreater(float(np.abs(rn - cn).sum()) / 2, 0.05)  # rice != generic cropland

    def test_the_fire_figure_title_names_the_fetched_season(self):
        """The ninth review found the fire figure's IN-IMAGE title still saying
        "2024-25 burning seasons" after rc13 re-fetched the period-matched
        2023-24 windows: the title was a hardcoded literal beside a caption that
        had moved on. The title must now derive from the fetched artifact's own
        sidecar, so a re-fetch under a different season key can never mislabel
        the graphic again - and the stale literal must be gone from the module."""
        import inspect
        from pkinv.sectors.agriculture.gis import run_gis, fetch_firms
        title = run_gis.fire_title()
        import json
        with open(fetch_firms.SIDECAR, encoding="utf-8") as handle:
            years = sorted({int(w[0][2:])
                            for w in json.load(handle)["windows_fetched"]})
        self.assertIn("FY%d" % years[0], title)
        self.assertIn("FY%d" % years[-1], title)
        self.assertNotIn("2024-25", inspect.getsource(run_gis))

    def test_firms_fire_proxy_when_present(self):
        from pkinv.core.gis.proxies import build_firms_fire_proxy
        res = build_firms_fire_proxy(self.grid)
        if res is None:
            self.skipTest("FIRMS firms_fire.csv not supplied")
        fire, desc = res
        self.assertGreater(fire.sum(), 0)
        self.assertIn("FIRMS", desc)
        self.assertFalse((fire[self.grid.province_id < 0] > 0).any())  # zero outside country

    def test_uniform_proxy_also_reconciles(self):
        ones = np.where(self.grid.province_id >= 0, 1.0, 0.0)
        # Declared CONSTANT, which is what an all-ones surface is, so this fixture spreads
        # per square kilometre exactly as production does. Reconciliation holds under any
        # positive weighting, which is what this test is asserting.
        alloc, _ = allocate(self.grid, {"U": ones}, self.matrix,
                            {c: "U" for c in CATEGORIES},
                            proxy_semantics={"U": "constant"})
        ctrl = sum(sum(self.matrix[p].values()) for p in PROVINCES)
        self.assertAlmostEqual(float(sum(a.sum() for a in alloc.values())), ctrl, delta=TOL)

    def test_category_specific_proxies_differ(self):
        # a category on proxy A must be spatially different from one on proxy B
        cat_a = next(c for c in CATEGORIES if self.cat_proxy[c] == "A")
        cat_b = next(c for c in CATEGORIES if self.cat_proxy[c] == "B")
        a, b = self.alloc[cat_a], self.alloc[cat_b]
        an = a / a.sum() if a.sum() else a
        bn = b / b.sum() if b.sum() else b
        tv = float(np.abs(an - bn).sum()) / 2.0   # total-variation distance
        self.assertGreater(tv, 0.05, "category maps should differ with different proxies")

    def test_geotiff_roundtrip(self):
        import rasterio
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.tif")
            render.write_geotiff(path, self.total, self.grid)
            with rasterio.open(path) as src:
                self.assertEqual(src.crs.to_epsg(), 4326)
                self.assertEqual((src.height, src.width),
                                 (self.grid.height, self.grid.width))
                data = src.read(1)
                inside = self.grid.province_id >= 0
                self.assertAlmostEqual(float(data[inside].sum()),
                                       float(self.total[inside].sum()), delta=TOL)


if __name__ == "__main__":
    unittest.main()
