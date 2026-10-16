"""Primary allocation cannot inherit excluded ODbL geography silently."""
import unittest
from pkinv.core import primary_geography as policy
from pkinv.core.gis import firms
from pkinv.activity.store import read_rows


class PrimaryGeography(unittest.TestCase):
    def test_coordinate_rows_are_selected_by_provenance_not_relicensed(self):
        rows = [{"facility_id": "a", "licence": "cc-by-4.0", "coordinate_source": "GEM"},
                {"facility_id": "b", "licence": "odbl-1.0", "coordinate_source": "OSM"},
                {"facility_id": "c", "licence": "", "coordinate_source": "OpenStreetMap"}]
        self.assertEqual(["a"], [r["facility_id"] for r in policy.compatible_facilities(rows)])
        self.assertEqual("odbl-1.0", rows[1]["licence"])

    def test_rail_is_retained_above_adm2_without_licensed_route_geometry(self):
        for geometry in policy.RAIL_GEOMETRIES:
            original = {"geometry_id": geometry, "spatial_profile_id": "railways_route_model",
                        "spatial_view": "physical", "emissions_Gg": 12.3}
            revised = policy.primary_stream(original)
            self.assertEqual("S4:no-native-geometry", revised["geometry_id"])
            self.assertEqual("railways_freight_div", revised["spatial_profile_id"])
            self.assertEqual("accounting", revised["spatial_view"])
            self.assertEqual(12.3, revised["emissions_Gg"])
            self.assertEqual(geometry, original["geometry_id"])

    def test_fire_attribution_kiln_coordinates_have_independent_licences(self):
        """The FIRMS exclusion changes primary weights, so its kiln inputs matter."""
        kilns = [r for r in read_rows(firms.FACILITY_REGISTRY, comments=True)
                 if "kiln" in r["facility_id"].lower() and r["latitude"]]
        self.assertGreater(len(kilns), 10000)
        self.assertEqual(len(kilns), len(policy.compatible_facilities(kilns)))
        self.assertTrue(all("Hamdani" in r["coordinate_source"] and
                            "cc-by-4.0" in r["licence"].lower() for r in kilns))


if __name__ == "__main__":
    unittest.main()
