"""The road link table and the building diagnostic: shipped-file invariants.

Validated without the 317 MB rebuild, like test_road_products: the link count and
maxspeed coverage match ROAD_SOURCES; per-class link lengths close on the class
totals; the GeoParquet is readable and row-matched to the CSV; the building
comparison partitions to 1 on both columns; and the diagnostic raster is the shape
and dtype of the proxy family without being a member of it.
"""

from pkinv.assets import asset_path
import csv
import json
import os
import unittest
from pkinv.core.io import read_rows
from _support import OUT, ROOT


try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def _rows(path):
    return read_rows(path, comments=False)


class TestRoadLinks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.links = _rows(os.path.join(OUT, "pakemis_road_links.csv"))
        with open(asset_path(ROOT, "data", "gis", "roads", "ROAD_SOURCES.json"),
                  encoding="utf-8") as handle:
            cls.provenance = json.load(handle)

    def test_count_and_coverage_match_the_provenance(self):
        self.assertEqual(len(self.links), self.provenance["link_count"])
        coverage = 100.0 * sum(1 for r in self.links
                               if int(r["maxspeed"]) > 0) / len(self.links)
        self.assertAlmostEqual(coverage, self.provenance["maxspeed_coverage_pct"],
                               delta=0.1)
        self.assertIn("no lanes", self.provenance["no_lanes_statement"])

    def test_link_lengths_close_on_the_class_totals(self):
        by_class = {}
        for r in self.links:
            base = r["fclass"].replace("_link", "")
            by_class[base] = by_class.get(base, 0.0) + float(r["length_km"])
        for fclass, declared in self.provenance["class_km"].items():
            # link lengths are whole-way geodesic sums; class_km is the on-grid
            # raster mass - they differ by the off-grid sliver only
            self.assertAlmostEqual(by_class[fclass], declared,
                                   delta=max(5.0, 0.002 * declared), msg=fclass)

    def test_oneway_vocabulary_is_normalised(self):
        values = {r["oneway"] for r in self.links}
        self.assertLessEqual(values, {"two_way", "oneway", "oneway_reversed"})

    def test_the_geoparquet_is_readable_and_row_matched(self):
        try:
            import geopandas as gpd
        except ImportError:
            self.skipTest("geopandas absent")
        frame = gpd.read_parquet(os.path.join(OUT, "pakemis_road_links.parquet"))
        self.assertEqual(len(frame), len(self.links))
        self.assertEqual(frame.crs.to_epsg(), 4326)
        self.assertIn("length_km", frame.columns)


class TestBuildingDiagnostic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.comparison = _rows(os.path.join(OUT,
                                            "pakemis_builtup_comparison_adm2.csv"))

    def test_both_share_columns_partition(self):
        wc = sum(float(r["worldcover_builtup_share"]) for r in self.comparison)
        osm = sum(float(r["osm_building_share"]) for r in self.comparison)
        self.assertAlmostEqual(wc, 1.0, places=3)
        self.assertAlmostEqual(osm, 1.0, places=3)

    @unittest.skipUnless(HAVE_NUMPY, "numpy absent")
    def test_the_raster_is_diagnostic_shaped(self):
        arr = np.load(asset_path(ROOT, "data", "gis", "osm_building_fraction_267x340.npy"))
        self.assertEqual(arr.shape, (267, 340))
        self.assertEqual(arr.dtype, np.float32)
        self.assertGreaterEqual(float(arr.min()), 0.0)
        self.assertLess(float(arr.max()), 1.0)

    def test_the_diagnostic_is_not_a_proxy(self):
        """Structural: the cube's raster vocabulary must not learn this surface."""
        from pkinv.core.gis import cube as cube_core
        for name in cube_core.RASTER_NAMES:
            self.assertNotIn("building", name)


if __name__ == "__main__":
    unittest.main()
