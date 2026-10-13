"""One FIRMS attribution ladder for the temporal profile and the spatial raster (rc42, S-3).

rc41's raster kept every in-Pakistan detection (65,910, FRP + 1) while the temporal profile
attributed 52,428 (burning window, cropland, away from kilns, bare FRP): 17.35 % of the
raster's weight rode detections the temporal method rejected. Both call
pkinv.core.gis.firms.attribute now; the counts they publish are the same counts.
"""
import unittest

from _support import rows


class TestOneLadder(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from pkinv.core.gis import firms
        from pkinv.sectors.agriculture import burn_windows, monthly
        windows = burn_windows.windows(2023)
        cls.hits, cls.counts = firms.attribute(2023, lambda when: burn_windows.in_window(windows, when))
        cls.weights, cls.profile_counts = monthly.burning_attribution(2023)

    def test_the_temporal_profile_publishes_the_ladders_counts(self):
        self.assertEqual(self.counts, self.profile_counts)
        self.assertEqual(self.counts["attributed"], len(self.hits))
        self.assertGreater(self.counts["attributed"], 40000)

    def test_the_raster_carries_exactly_the_attributed_weight(self):
        import numpy as np
        from pkinv.core.gis.grid import build_grid
        from pkinv.core.gis.proxies import build_firms_fire_proxy
        grid = build_grid()
        raster, description = build_firms_fire_proxy(grid)
        self.assertAlmostEqual(float(raster.sum()), sum(frp for _r, _c, frp, _m in self.hits), places=1)
        self.assertAlmostEqual(float(raster.sum()), sum(self.weights.values()), places=1)
        self.assertIn("%d attributed" % self.counts["attributed"], description)
        self.assertNotIn("in-grid", description)

    def test_a_rejected_detection_carries_no_weight(self):
        """Every rung rejects something in this year - the ladder is not a no-op."""
        for rung in ("near_kiln", "off_cropland", "outside_pakistan"):
            self.assertGreater(self.counts[rung], 0, rung)


if __name__ == "__main__":
    unittest.main()
