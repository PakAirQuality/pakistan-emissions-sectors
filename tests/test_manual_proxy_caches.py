"""The committed grid caches of the manual rice rasters are exactly what the rasters give.

WHY (rc69). The SPAM 2020 rice rasters are restricted layers, so a public clone does not hold
them. Before the caches existed such a clone placed rice on a fallback surface and could not
price the water-regime axis, yet nothing failed: the cube's fallback is declared, not
refused. Every reader takes only the raster's resample to the inventory grid, so that resample
is committed. A cache is only as good as its agreement with its raster: where the raster is
mounted it must reproduce byte for byte, and without it the reader must return the cache, not
nothing.
"""
import os
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np                                                     # noqa: E402

from pkinv.assets import asset_path                                    # noqa: E402
from pkinv.core.gis import proxies                                     # noqa: E402
from pkinv.core.gis.grid import build_grid                             # noqa: E402
from _support import require_layers                                    # noqa: E402


class TestTheManualCaches(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grid = build_grid()

    def test_every_cached_raster_has_its_cache(self):
        for filename in proxies.MANUAL_CACHED:
            cache = proxies.manual_cache_path(self.grid, filename)
            self.assertTrue(os.path.exists(cache), cache)
            array = np.load(cache)
            self.assertEqual(array.shape, (self.grid.height, self.grid.width))
            self.assertGreater(float(array.sum()), 0)

    def test_each_cache_is_the_rasters_own_resample(self):
        require_layers("the SPAM rasters the caches are compared with")
        for filename in proxies.MANUAL_CACHED:
            path = asset_path(proxies.MANUAL_DIR, filename)
            fresh, _ = proxies._resample_manual(self.grid, path, filename)
            cached = np.load(proxies.manual_cache_path(self.grid, filename))
            self.assertEqual(cached.dtype, fresh.dtype, filename)
            self.assertEqual(cached.tobytes(), fresh.tobytes(),
                             "%s: run python3 scripts/build_manual_proxy_caches.py" % filename)

    def test_without_the_raster_the_reader_returns_the_cache(self):
        with tempfile.TemporaryDirectory() as empty, \
                mock.patch.object(proxies, "MANUAL_DIR", empty):
            for filename in proxies.MANUAL_CACHED:
                built = proxies.build_manual_proxy(self.grid, filename)
                self.assertIsNotNone(built, filename)
                cached = np.load(proxies.manual_cache_path(self.grid, filename))
                self.assertEqual(built[0].tobytes(), cached.tobytes())
                self.assertEqual(built[1], "manual: data/gis/manual/%s" % filename)

    def test_an_uncached_raster_is_still_absent(self):
        with tempfile.TemporaryDirectory() as empty, \
                mock.patch.object(proxies, "MANUAL_DIR", empty):
            self.assertIsNone(proxies.build_manual_proxy(self.grid, "not_a_raster.tif"))


if __name__ == "__main__":
    unittest.main()
