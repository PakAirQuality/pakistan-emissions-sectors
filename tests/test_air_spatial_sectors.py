"""The all-sector air spatial products (Wave C): every pollutant row inherits its own
stream's shipped allocation. Closures per (sector, pollutant); the inheritance assertion
(a sector's ADM1 vector is its stream's declared vector); aviation cruise placed at ADM1
and typed-absent at ADM2; grades from the support ledger; the canonical shape frame."""
import collections
import csv
import os
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")


def read(path):
    with open(os.path.join(ROOT, "outputs", path), encoding="utf-8") as f:
        return [r for r in csv.DictReader(l for l in f if not l.startswith("#"))]


class TestAirSpatialSectors(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.adm1 = read("air_pollutants_adm1.csv")
        cls.adm2 = read("air_pollutants_adm2.csv")

    def test_covered_sectors_are_placed_only_at_supported_levels(self):
        want = {"agriculture", "aviation", "power", "railways", "residential", "transport", "waste"}
        self.assertEqual({r["sector_id"] for r in self.adm1}, want)
        self.assertEqual({r["sector_id"] for r in self.adm2}, want - {"railways"})
        rail = [r for r in self.adm1 if r["sector_id"] == "railways"]
        self.assertTrue(rail)
        self.assertTrue(all(r["share_status"] == "unallocated_below_adm1" for r in rail))
        self.assertGreater(sum(float(r["emissions_kt"]) for r in rail), 0)

    def test_adm1_closes_to_the_national_layer_per_sector_pollutant(self):
        from pkinv.report import air_spatial_sectors as asx
        national = collections.defaultdict(float)
        for sector, fname in asx.AIR_FILES.items():
            for r in asx._read(fname):
                national[(sector, r["pollutant"])] += float(r["emissions_kt"])
        a1 = collections.defaultdict(float)
        for r in self.adm1:
            a1[(r["sector_id"], r["pollutant"])] += float(r["emissions_kt"])
        for key, nat in national.items():
            if nat <= 0:
                continue
            tol = 0.05 if key[0] == "agriculture" else nat * 1e-6
            self.assertLessEqual(abs(a1[key] - nat), tol, key)

    def test_the_inheritance_is_the_streams_own_vector(self):
        # waste rides one stream: its ADM1 shares must equal the declared vector exactly
        declared = {}
        for r in read("pakemis_grid_provincial_check.csv"):
            if r["source_stream_id"].startswith("waste|open-burning"):
                declared[r["province"]] = float(r["declared_share"])
        got = collections.defaultdict(float)
        total = 0.0
        for r in self.adm1:
            if r["sector_id"] == "waste" and r["pollutant"] == "PM2.5":
                got[r["province"]] += float(r["emissions_kt"])
                total += float(r["emissions_kt"])
        for province, share in declared.items():
            self.assertAlmostEqual(got[province] / total, share, places=8, msg=province)

    def test_cruise_is_placed_at_adm1_and_absent_at_adm2(self):
        cruise1 = [r for r in self.adm1 if r["sector_id"] == "aviation"
                   and r["share_status"] == "unallocated_below_adm1"]
        self.assertTrue(cruise1, "cruise pollutants carry ADM1 rows on the LTO vector")
        self.assertTrue(all("cruise" in r["subitem"] for r in cruise1))
        self.assertFalse([r for r in self.adm2 if r["sector_id"] == "aviation"
                          and "cruise" in r["subitem"]],
                         "cruise is unallocated below ADM1; its absence is typed, never zeroed")

    def test_grades_come_from_the_support_ledger(self):
        ledger = {r["source_stream_id"]: r["evidence_grade"]
                  for r in read("pakemis_stream_support_ledger.csv")
                  if r["period_id"] == "FY2023-24"}
        power_grades = {r["evidence_grade"] for r in self.adm1 if r["sector_id"] == "power"}
        self.assertIn(ledger["power|electricity-and-heat-production|coal-co2|co2"], power_grades)
        self.assertTrue(all(g != "" for g in power_grades))

    def test_the_shape_frame_is_canonical(self):
        from pkinv.core import adm2 as adm2_core
        frame = set(adm2_core.shape_to_adm2())
        for r in self.adm2:
            if r["shape_id"]:
                self.assertIn(r["shape_id"], frame)

    def test_the_key_is_unique(self):
        keys = [(r["sector_id"], r["period_id"], r["shape_id"], r["unit_name"], r["category"],
                 r["subitem"], r["proxy"], r["pollutant"]) for r in self.adm2]
        self.assertEqual(len(keys), len(set(keys)))


if __name__ == "__main__":
    unittest.main()
