"""The OSM road products: committed artifacts validated without the 317 MB rebuild.

The contract: the density raster and the ADM2 road-km table are two aggregations of
one extraction and must close on each other; the provenance file carries the snapshot
hash (the rail precedent's missing piece, now present in both SOURCES files); and the
products are DIAGNOSTIC - no stream registry row may point at them, because the
road-transport magnitude is set by fuel controls that geometry must never move. The
full regeneration (--check on the script) reads the 317 MB shapefile and is a manual
gate, not a suite member; what the suite pins is the internal consistency and the
discipline of the committed artifacts.
"""

from pkinv.assets import asset_path
import csv
import json
import os
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

ROADS = asset_path(ROOT, "data", "gis", "roads")
ADM2_CSV = os.path.join(ROOT, "outputs", "pakemis_road_length_adm2.csv")

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False


def _rows(path):
    return read_rows(path, comments=False)


class TestRoadProducts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adm2 = _rows(ADM2_CSV)
        with open(os.path.join(ROADS, "ROAD_SOURCES.json"),
                  encoding="utf-8") as handle:
            cls.provenance = json.load(handle)

    def test_the_provenance_names_the_snapshot_and_its_hash(self):
        for field in ("source_url", "snapshot_timestamp", "download_date",
                      "snapshot_zip_sha256", "fclass_filter", "class_km",
                      "total_km", "licence"):
            self.assertIn(field, self.provenance)
        self.assertEqual(len(self.provenance["snapshot_zip_sha256"]), 64)
        self.assertEqual(self.provenance["licence"], "ODbL")

    def test_the_rail_snapshot_carries_the_same_hash(self):
        """One snapshot family, one digest: the rail network was extracted from the
        same Geofabrik zip, and its SOURCES file was dated but unhashed until now."""
        with open(asset_path(ROOT, "data", "gis", "rail", "RAIL_SOURCES.json"),
                  encoding="utf-8") as handle:
            rail = json.load(handle)
        self.assertEqual(rail.get("snapshot_zip_sha256"),
                         self.provenance["snapshot_zip_sha256"])

    def test_the_adm2_table_closes_on_the_class_totals(self):
        """Per class: ADM2 rows + the declared outside-every-polygon row must sum to
        the provenance's class_km within rounding of the row count."""
        by_class = {}
        for row in self.adm2:
            by_class[row["fclass"]] = by_class.get(row["fclass"], 0.0) \
                + float(row["road_km"])
        for fclass, declared in self.provenance["class_km"].items():
            self.assertAlmostEqual(by_class[fclass], declared, delta=1.0, msg=fclass)

    @unittest.skipUnless(HAVE_NUMPY, "numpy absent")
    def test_the_raster_closes_on_the_total(self):
        arr = np.load(os.path.join(ROADS, "pak_road_density_267x340.npy"))
        self.assertEqual(arr.shape, (267, 340))
        self.assertEqual(arr.dtype, np.float32)
        self.assertGreaterEqual(float(arr.min()), 0.0)
        self.assertAlmostEqual(float(arr.sum()), self.provenance["total_km"],
                               delta=2.0)

    def test_primary_allocation_excludes_odbl_road_and_building_diagnostics(self):
        """The compatible primary uses settlement weights, while ODbL-derived
        road products remain separately identified diagnostics/alternatives.
        A preserved raster's existence cannot admit it into primary allocation.
        """
        with open(asset_path(ROOT, "data", "stream_grid_proxy.csv"),
                  encoding="utf-8") as handle:
            rows = [row for row in csv.DictReader(
                line for line in handle if not line.startswith("#"))]
        road_rows = [r for r in rows if "road" in r["raster_proxy"]]
        self.assertFalse(road_rows, "ODbL road weights entered compatible primary allocation")
        transport = [r for r in rows if r["module"] == "transport" and r["category"] == "Road transport"]
        self.assertTrue(transport)
        self.assertEqual({r["raster_proxy"] for r in transport}, {"builtup"})
        for r in rows:
            self.assertNotIn("building", r["raster_proxy"],
                             "a stream rasterises on the OSM building diagnostic")
        with open(asset_path(ROOT, "data", "stream_geometry.csv"),
                  encoding="utf-8") as handle:
            geometries = {row["geometry_id"] for row in csv.DictReader(
                line for line in handle if not line.startswith("#"))}
        for geometry in geometries:
            self.assertNotIn("road", geometry,
                             "a stream claims the road network as native geometry")

    def test_the_outside_polygon_slack_is_small(self):
        outside = sum(float(r["road_km"]) for r in self.adm2
                      if r["adm2_id"] == "outside_every_polygon")
        self.assertLess(outside, 0.05 * self.provenance["total_km"],
                        "more than 5%% of road km outside every district polygon")


if __name__ == "__main__":
    unittest.main()
