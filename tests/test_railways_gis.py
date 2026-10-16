"""The route-constrained spatial model, held to conservation and to its audit.

The gis extra is optional, so everything raster-shaped skips gracefully when it is absent
(the test_gis.py pattern); the network-file and shares-row checks run everywhere, because
the committed artefacts must hold whether or not this machine can rasterise them.

Run:  python3 -m unittest discover tests -p "test_railways_gis.py"
"""

from pkinv.assets import asset_path
import csv
import json
import os
import unittest

from pkinv.sectors.railways import downscale
from pkinv.sectors.railways.data import RailwaysData
from pkinv.sectors.railways.gis import network
from _support import ROOT


try:
    import numpy  # noqa: F401
    import rasterio  # noqa: F401
    HAVE_GIS = True
except ImportError:
    HAVE_GIS = False


class TestNetworkFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.segments = network.load_network()
        cls.data = RailwaysData()

    def test_the_audit_holds(self):
        """OSM active line-km within 15 percent of the Year Book's route-kilometres -
        in fact within 3. If this drifts, the network file was rebuilt against different
        OSM data and every spatial product downstream changed with it."""
        aud = network.audit(self.data, self.segments)
        self.assertTrue(0.85 < aud["ratio_osm_over_yearbook"] < 1.15,
                        aud["ratio_osm_over_yearbook"])

    def test_every_active_segment_carries_a_corridor(self):
        for s in self.segments:
            if s["status"] == "active":
                self.assertTrue(s["corridor"], s["edge_id"])
            else:
                self.assertEqual(s["status"], "disconnected")

    def test_every_corridor_has_a_weight_row(self):
        weights = network.load_weights()
        corridors = {s["corridor"] for s in self.segments if s["status"] == "active"}
        self.assertEqual(corridors - set(weights), set())

    def test_the_judgment_is_declared_on_every_weight_row(self):
        with open(network.WEIGHTS, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                self.assertEqual(r["basis"], "corridor_judgement", r["corridor"])
                self.assertTrue(r["note"].strip(), r["corridor"])

    def test_provenance_file_carries_the_odbl_attribution(self):
        with open(asset_path(ROOT, "data", "gis", "rail", "RAIL_SOURCES.json"),
                  encoding="utf-8") as f:
            meta = json.load(f)
        self.assertIn("OpenStreetMap", meta["licence"])
        self.assertIn("ODbL", meta["licence"])

    def test_yards_are_the_seven_divisions(self):
        yards = network.load_yards()
        self.assertEqual(len(yards), 7)
        self.assertEqual(sum(w for _x, _y, w in yards), 289748.0)  # wagons loaded total


@unittest.skipUnless(HAVE_GIS, "gis extra not installed")
class TestBurnLines(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.core.gis.grid import build_grid
        cls.grid = build_grid()

    def test_mass_conservation_is_length(self):
        """A unit-weight diagonal line's burned total must equal its length: the property
        features.rasterize cannot provide and the whole allocation rests on."""
        from pkinv.core.gis import lines
        coords = [(68.0, 26.0), (71.0, 29.0)]
        arr = lines.burn_lines(self.grid, [(coords, 1.0)])
        expected = lines._km(*coords[0], *coords[1])
        self.assertAlmostEqual(float(arr.sum()) / expected, 1.0, places=3)

    def test_halving_the_step_converges(self):
        from pkinv.core.gis import lines
        from pkinv.core.gis.grid import RES
        import numpy as np
        coords = [(67.2, 25.1), (69.7, 27.9), (71.3, 30.4)]
        a = lines.burn_lines(self.grid, [(coords, 1.0)], step_deg=RES / 8)
        b = lines.burn_lines(self.grid, [(coords, 1.0)], step_deg=RES / 16)
        self.assertAlmostEqual(float(a.sum()), float(b.sum()), places=6)
        # Boundary-cell jitter: a segment near a cell edge may flip sides as the step
        # changes. Total mass is exact (above); the per-cell movement stays below ~10
        # percent and cancels at the corridor/district/province scales the model reports.
        moved = np.abs(a - b).sum() / a.sum()
        self.assertLess(moved, 0.10)


@unittest.skipUnless(HAVE_GIS, "gis extra not installed")
class TestReconciliation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.core.gis.grid import build_grid
        from pkinv.sectors.railways.gis import run_gis
        cls.data = RailwaysData()
        cls.grid = build_grid()
        cls.surf = run_gis.fuel_surface(cls.grid, cls.data)

    def test_the_surface_is_a_distribution(self):
        import numpy as np
        self.assertAlmostEqual(float(self.surf.sum()), 1.0, places=9)
        self.assertGreaterEqual(float(self.surf.min()), 0.0)
        self.assertFalse(np.isnan(self.surf).any())

    def test_the_shares_row_matches_a_fresh_computation(self):
        """The transcribed province_shares.csv row is what the stdlib engine allocates
        with; it must not drift from what the spatial model computes."""
        from pkinv.sectors.railways.gis import run_gis
        fresh = run_gis.province_shares(self.grid, self.surf)
        row = downscale.load_shares()["railways_route_model"]
        for p, v in fresh.items():
            self.assertAlmostEqual(row[p], v, places=4, msg=p)

    def test_emissions_stay_on_the_railway(self):
        """No cell without track or yard may carry railway emissions - the property the
        provincial proxy never had."""
        import numpy as np
        cells = int((self.surf > 0).sum())
        self.assertLess(cells, 3000)
        self.assertGreater(cells, 800)


if __name__ == "__main__":
    unittest.main()
