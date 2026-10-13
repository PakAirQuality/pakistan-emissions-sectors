"""The census companies whose clinker had no point to sit on (rc44, A5).

Three of the sixteen producer-census companies appeared with no located works: Bestway
(14.54 percent of national clinker), Power (5.45) and Flying (0.77). Until rc44 their tonnage
was not merely unplaced - the province share was renormalised over the works that ARE located,
so 20.75 percent of national clinker was placed on other companies' plants, and
ippu_register_points documented itself as failing loudly on exactly this while the check it
described only caught a company missing from the token map.

rc44 priced it, and this commit resolves all but Flying from gem_cement_pak.csv - a table the
repository already carried. Flying is refused: GEM's coordinate for it lands 4.8 km inside
Chakwal while the registry, and Flying's own annual report, place the works in Khushab.
"""

from pkinv.assets import asset_path
import csv
import json
import os
import unittest

from _support import DATA, data_rows, rows

REGISTRY = "facility_registry.csv"
GEM = os.path.join("activity", "industry", "gem_cement_pak.csv")
WIRED = ("cement_bestway_hattar", "cement_bestway_farooqia", "cement_bestway_chakwal",
         "cement_bestway_kallar_kahar", "cement_power_nooriabad")


def _districts():
    """[(adm2_id, polygons, bbox)] for every canonical district shape."""
    canon = {r["shape_id"]: r["adm2_id"] for r in data_rows("adm2_canonical.csv")
             if r["shape_id"]}
    with open(asset_path(DATA, "gis", "PAK_ADM2.geojson"), encoding="utf-8") as handle:
        features = json.load(handle)["features"]
    out = []
    for f in features:
        adm2 = canon.get(f["properties"]["shapeID"])
        if not adm2:
            continue
        geom = f["geometry"]
        polys = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        xs = [c[0] for p in polys for ring in p for c in ring]
        ys = [c[1] for p in polys for ring in p for c in ring]
        out.append((adm2, polys, (min(xs), max(xs), min(ys), max(ys))))
    return out


def _in_ring(point, ring):
    x, y = point
    inside = False
    for i in range(len(ring)):
        x1, y1 = ring[i][:2]
        x2, y2 = ring[(i + 1) % len(ring)][:2]
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside
    return inside


def _locate(districts, lon, lat):
    for adm2, polys, (x0, x1, y0, y1) in districts:
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            continue
        for poly in polys:
            if _in_ring((lon, lat), poly[0]) and not any(_in_ring((lon, lat), h)
                                                         for h in poly[1:]):
                return adm2
    return None


class TestTheCementWorksAreLocated(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.districts = _districts()
        cls.cement = [r for r in data_rows(REGISTRY)
                      if r["module"] == "ippu" and r["facility_id"].startswith("cement_")]
        cls.gem = {}
        with open(asset_path(DATA, GEM), encoding="utf-8") as handle:
            for r in csv.DictReader(handle):
                cls.gem[r["Plant name (English)"]] = r

    def test_the_five_works_carry_their_gem_coordinate_exactly(self):
        """Not near it: the registry value must BE the tracker's, to the digit it publishes."""
        expected = {
            "cement_bestway_hattar": "Bestway Cement Hattar Cement Plant",
            "cement_bestway_farooqia": "Bestway Cement Farooqia Cement Plant",
            "cement_bestway_chakwal": "Bestway Cement Chakwal Cement Plant",
            "cement_bestway_kallar_kahar": "Bestway Cement Kallar Kahar Cement Plant",
            "cement_power_nooriabad": "Power Cement Jamshoro Cement Plant",
        }
        by_id = {r["facility_id"]: r for r in self.cement}
        for facility_id, plant in expected.items():
            row = by_id[facility_id]
            lat, lon = [v.strip() for v in self.gem[plant]["Coordinates"].split(",")]
            self.assertEqual(float(row["latitude"]), float(lat), facility_id)
            self.assertEqual(float(row["longitude"]), float(lon), facility_id)
            self.assertEqual(self.gem[plant]["Coordinate accuracy"], "exact", facility_id)
            self.assertEqual(row["geocode_status"], "exact_coordinate_resolved", facility_id)

    def test_power_cement_is_joined_by_OWNER_not_by_site_name(self):
        """The registry calls Power's works Nooriabad; GEM calls it Jamshoro and puts a
        NOORIABAD plant under a different owner, Dadabhoy, 3 km away. Nooriabad is a town
        inside Jamshoro district, so both names describe one place - but a join on the site
        name would have handed 5.45 percent of national clinker to another company's plant.
        The registry's own declared district settles it, and this test pins the choice."""
        row = next(r for r in self.cement if r["facility_id"] == "cement_power_nooriabad")
        dadabhoy = self.gem["Dadabhoy Cement Industries Nooriabad Cement Plant"]
        d_lat, d_lon = [float(v) for v in dadabhoy["Coordinates"].split(",")]
        self.assertNotAlmostEqual(float(row["latitude"]), d_lat, places=3)
        self.assertNotAlmostEqual(float(row["longitude"]), d_lon, places=3)
        self.assertEqual(row["adm2_id"], "sindh_jamshoro")

    def test_every_located_work_lands_in_the_district_it_declares(self):
        """THE CORROBORATION GATE. A coordinate and a declared district are two independent
        statements about where a works is; wiring a coordinate that contradicts the district
        already on the row moves district mass on an unresolved disagreement. Every located
        cement work passed this before rc44 and every one passes after - which is what makes
        Flying's refusal a finding rather than a preference."""
        misplaced = []
        for row in self.cement:
            if not row["latitude"].strip() or row["adm2_id"] in ("", "unresolved"):
                continue
            landed = _locate(self.districts, float(row["longitude"]), float(row["latitude"]))
            if landed != row["adm2_id"]:
                misplaced.append("%s: declares %s, point lands in %s"
                                 % (row["facility_id"], row["adm2_id"], landed))
        self.assertFalse(misplaced, "\n  ".join(misplaced))

    def test_every_gem_coordinate_belongs_to_ITS_OWN_COMPANY(self):
        """THE TEST THAT THE DISTRICT GATE CANNOT BE (rc44). The corroboration gate above asks
        whether a point falls in the district the register declares, and that is necessary and
        not sufficient: where one district holds two companies' works it cannot separate them.
        Haripur holds Bestway's Hattar plant and Dewan's Kamilpur plant 1.1 km apart, and
        cement_dewan_hattar had been carrying BESTWAY's coordinate since the override was
        written - accepted, its own note says, "because the point falls inside kp_haripur".

        Adding Bestway's own works this release would have put two facilities on one point with
        one of them demonstrably wrong. The owner is the discriminator the district cannot
        provide, so it is asserted: the GEM plant sitting on a facility's coordinate must be
        owned by that facility's company."""
        from pkinv.report import grid_cube
        generic = {"cement", "company", "limited", "ltd", "co", "factory", "pakistan",
                   "industries", "the"}

        def tokens(text):
            keep = "".join(c if c.isalnum() or c.isspace() else " " for c in text.lower())
            return {t for t in keep.split() if t and t not in generic}

        census = {token: name for name, token in grid_cube.CEMENT_COMPANY_TOKENS.items()}
        by_point = {}
        for g in self.gem.values():
            if g["Coordinates"].strip():
                lat, lon = [round(float(v), 5) for v in g["Coordinates"].split(",")]
                by_point[(lat, lon)] = g
        checked = 0
        for row in self.cement:
            if not row["latitude"].strip():
                continue
            key = (round(float(row["latitude"]), 5), round(float(row["longitude"]), 5))
            plant = by_point.get(key)
            if plant is None:          # not a GEM-sourced coordinate (OSM, Nominatim)
                continue
            company = census.get(row["facility_id"].split("_")[1])
            self.assertIsNotNone(company, row["facility_id"])
            owner = plant["Owner (English)"].split(" [")[0]
            self.assertTrue(tokens(company) & tokens(owner),
                            "%s is a %s works but sits on GEM's %r, owned by %s"
                            % (row["facility_id"], company,
                               plant["Plant name (English)"], owner))
            checked += 1
        self.assertGreater(checked, 10, "the sweep found almost no GEM-sourced points")

    def test_flying_is_refused_and_stays_declared(self):
        """GEM's Flying plant is 'Khushab Cement Plant, formerly Zaman Cement' - an acquired
        site - and its coordinate lands 4.8 km inside Chakwal, while the registry and Flying's
        annual report both say Khushab. Two sources disagree about the district, the stake is
        0.77 percent of clinker, and the honest answer is a declared fallback."""
        from pkinv.report import grid_cube
        flying = next(r for r in self.cement if r["facility_id"] == "cement_flying_mangowal")
        self.assertEqual(flying["latitude"].strip(), "")
        self.assertEqual(flying["adm2_id"], "punjab_khushab")
        self.assertEqual(grid_cube.ippu_unlocated_companies(), ["Flying"])
        self.assertAlmostEqual(grid_cube.ippu_located_share(), 0.99231, places=4)

    def test_the_fallback_names_the_company_it_still_has(self):
        """DERIVED, not written down: the reason string named Bestway, Power and Flying, and
        this commit located two of them. A hand-written list would still name all three."""
        ippu = [r for r in rows("pakemis_grid_fallbacks.csv")
                if r["declared"] == "ippu register points"]
        self.assertTrue(ippu)
        for row in ippu:
            self.assertIn("Flying", row["reason"])
            self.assertNotIn("Bestway", row["reason"])
            self.assertNotIn("Power", row["reason"])


if __name__ == "__main__":
    unittest.main()
