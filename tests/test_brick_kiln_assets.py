"""The brick-kiln asset table and its declared coverage mask.

The contract: every held kiln appears exactly once under a CONTENT-derived id (so the
source re-sorting cannot renumber the fleet); the district join resolves all but the
declared outside-boundary remainder; the coverage file partitions the active canonical
ADM2 frame into observed_kilns and not_covered_by_survey - and the mask's semantics
(absence means unsurveyed, never zero kilns) are stated on every uncovered row. The
table is prospective geometry: the facility-registry discipline test asserts no
estimated stream touches it, and nothing here changes a reported tonne.
"""

from pkinv.assets import asset_path
import csv
import hashlib
import json
import os
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

KILNS = asset_path(ROOT, "data", "gis", "kilns")
SOURCE = asset_path(ROOT, "data", "ml", "brick_kilns_pk.csv")


def _rows(name, root=KILNS):
    return read_rows(asset_path(root, name), comments=False)


class TestBrickKilnAssets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assets = _rows("pak_brick_kiln_assets.csv")
        cls.coverage = _rows("pak_brick_kiln_coverage.csv")
        with open(os.path.join(KILNS, "BRICK_KILN_SOURCES.json"),
                  encoding="utf-8") as handle:
            cls.provenance = json.load(handle)
        with open(SOURCE, newline="", encoding="utf-8") as handle:
            cls.source = list(csv.DictReader(handle))

    def test_every_source_kiln_ships_exactly_once(self):
        self.assertEqual(len(self.assets), len(self.source))
        ids = [a["kiln_id"] for a in self.assets]
        self.assertEqual(len(ids), len(set(ids)), "kiln ids collide")

    def test_ids_are_content_derived_not_positional(self):
        """Recompute one id from its own row: the hash of (lat, lon, type), never a
        row number. This is what makes the id survive a re-sort of the source."""
        a = self.assets[0]
        digest = hashlib.sha1(("%s,%s,%s" % (a["latitude"], a["longitude"],
                                             a["kiln_type"])).encode()).hexdigest()
        self.assertEqual(a["kiln_id"], "kiln_%s" % digest[:10])

    def test_the_district_join_resolves_all_but_the_declared_remainder(self):
        outside = [a for a in self.assets
                   if a["adm2_status"] == "unresolved-outside-simplified-boundary"]
        self.assertEqual(len(outside), self.provenance["outside_boundary_points"])
        self.assertLessEqual(len(outside), 5)
        for a in self.assets:
            if a not in outside:
                self.assertTrue(a["adm2_ids"].strip(), a["kiln_id"])

    def test_the_province_mapping_is_the_engine_vocabulary(self):
        from pkinv.core.geography import PROVINCES
        for a in self.assets:
            self.assertIn(a["province"], PROVINCES, a["kiln_id"])
        others = {a["source_province"] for a in self.assets
                  if a["province"] == "Other"}
        self.assertEqual(others, {"Azad Kashmir", "Islamabad"})

    def test_the_coverage_mask_partitions_the_active_frame(self):
        from pkinv.core import adm2 as adm2_core
        active = {k for k, v in adm2_core.load_canonical().items()
                  if v["status"] in ("active", "territory")}
        covered = {c["adm2_id"] for c in self.coverage}
        self.assertEqual(covered, active)
        for c in self.coverage:
            self.assertIn(c["coverage"], ("observed_kilns", "not_covered_by_survey"))
            if c["coverage"] == "not_covered_by_survey":
                self.assertIn("unsurveyed, not zero kilns", c["note"])
            else:
                self.assertGreater(int(c["observed_kilns"]), 0)

    def test_the_coverage_counts_are_the_asset_join(self):
        """The mask is derived from the same join, shared shapes attributing their
        count to every member - asserted by recomputation."""
        expected = {}
        for a in self.assets:
            if not a["adm2_ids"]:
                continue
            for member in a["adm2_ids"].split(";"):
                expected[member] = expected.get(member, 0) + 1
        got = {c["adm2_id"]: int(c["observed_kilns"]) for c in self.coverage
               if c["coverage"] == "observed_kilns"}
        self.assertEqual(got, expected)

    def test_the_provenance_hash_matches_the_held_snapshot(self):
        with open(SOURCE, "rb") as handle:
            sha = hashlib.sha256(handle.read()).hexdigest()
        self.assertEqual(self.provenance["held_snapshot_sha256"], sha)
        self.assertEqual(self.provenance["held_rows"], len(self.source))
        self.assertEqual(self.provenance["licence"], "CC-BY-4.0")

    def test_the_operational_geometry_set_count_is_real(self):
        """points:pak_brick_kilns (rc13) declares expected_members=11272 with the
        asset CSV as member_source. The registry-wide count validator only
        resolves facility_set counts drawn from data/facility_registry.csv, so
        this set's count would be decorative without an explicit check - this is
        that check, asserted here beside the table it counts."""
        import csv as _csv
        with open(asset_path(ROOT, "data", "geometry_sets.csv"),
                  newline="", encoding="utf-8") as handle:
            row = next(r for r in _csv.DictReader(handle)
                       if r["geometry_id"] == "points:pak_brick_kilns")
        self.assertEqual(row["member_source"],
                         "data/gis/kilns/pak_brick_kiln_assets.csv")
        self.assertEqual(int(row["expected_members"]), len(self.source))

    def test_the_snapshot_is_pinned_to_a_zenodo_version(self):
        """The rc11 version pin: 'Zenodo record 14038648' names a version whose
        Main.csv has 11,277 rows, while the held snapshot has 11,272 - a versioned
        dataset cited without a version. The audit matched the held (lat, lon, type)
        key set exactly to version 14718244; the provenance must carry that pin,
        with the version file's own md5 so a re-fetch can prove identity."""
        self.assertEqual(self.provenance["version_record"],
                         "Zenodo version 14718244")
        self.assertEqual(self.provenance["version_doi"],
                         "10.5281/zenodo.14718244")
        self.assertEqual(self.provenance["version_file"],
                         "Brick_Kilns_IGP_PK-Main.csv")
        self.assertEqual(self.provenance["version_file_md5"],
                         "e96975b1749e1f453d8a4f898ebe88bc")

    def test_the_table_regenerates_identically(self):
        try:
            import shapely  # noqa: F401
        except ImportError:
            self.skipTest("shapely absent; the committed table is still validated "
                          "by the other tests")
        import subprocess
        import sys as _sys
        proc = subprocess.run(
            [_sys.executable, os.path.join(ROOT, "scripts",
                                           "build_brick_kiln_assets.py"), "--check"],
            capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
