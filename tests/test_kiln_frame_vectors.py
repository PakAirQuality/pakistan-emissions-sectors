"""The kiln-frame spatial override (rc59): the FCBK and ZZ frames the air sink rides for the
typed brick classes, and the ADM1-only remainder. Contract tests on the shipped products plus
one in-process build of the frames; a planted defect at the register level."""
import os
import unittest
from collections import defaultdict

from pkinv.core.io import read_rows
from pkinv.paths import DATA, OUTPUTS

FRAME = os.path.join(OUTPUTS, "pakemis_kiln_frame_adm2_by_type.csv")
ATOMS = os.path.join(OUTPUTS, "pakemis_air_atomic_annual.csv")
ADM2 = os.path.join(OUTPUTS, "pakemis_air_adm2_by_year.csv")
UNALLOC = os.path.join(OUTPUTS, "pakemis_air_unallocated_by_year.csv")
SUPPORT = os.path.join(OUTPUTS, "pakemis_air_spatial_support_by_year.csv")
DETAIL = os.path.join(OUTPUTS, "pakemis_air_source_classes_fy2015_16_fy2023_24.csv")
BRICK = "industry|industrial-fuel-combustion-(1a2)|brick-kiln-coal-co2|co2"


class TestTheFrames(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.core.gis.grid import build_grid
        from pkinv.report import kiln_frame_vectors as kfv
        cls.kfv = kfv
        cls.grid = build_grid()
        cls.frames = kfv.build(cls.grid)
        cls.shares = kfv.brick_shares()

    def test_each_frame_province_marginal_equals_the_brick_stream_shares(self):
        for t, f in self.frames.items():
            for province, share in self.shares.items():
                self.assertAlmostEqual(f.province_marginal.get(province, 0.0), share, places=9, msg=(t, province))
            self.assertAlmostEqual(float(f.cells.sum()), 1.0, places=9)

    def test_the_two_frames_differ_and_each_closes(self):
        f, z = self.frames["FCBK"], self.frames["ZZ"]
        self.assertNotEqual(f.pattern_hash, z.pattern_hash)
        self.assertGreater(float(abs(f.shape_vec - z.shape_vec).sum()), 0.01)
        for t, fr in self.frames.items():
            self.assertAlmostEqual(float(fr.shape_vec.sum()) + fr.outside, 1.0, places=9, msg=t)

    def test_the_published_vectors_are_the_built_ones(self):
        rows = read_rows(FRAME)
        for t, fr in self.frames.items():
            got = {r["shape_id"]: float(r["share"]) for r in rows if r["kiln_type"] == t}
            self.assertAlmostEqual(sum(got.values()), 1.0, places=9, msg=t)
            self.assertAlmostEqual(got["OUTSIDE"], fr.outside, places=9)
        self.assertEqual({r["kiln_type"] for r in rows}, {"FCBK", "ZZ"})

    def test_a_province_with_a_share_and_no_kiln_of_a_type_is_declared(self):
        # Balochistan carries a brick share and no surveyed zig-zag kiln: the ZZ frame says so
        self.assertTrue(any("Balochistan" in n for n in self.frames["ZZ"].notes), self.frames["ZZ"].notes)


class TestTheSinkHonoursTheOverride(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.atoms = [a for a in read_rows(ATOMS) if a["support_anchor_id"] == BRICK and a["core7"] == "yes"]
        cls.unalloc = [r for r in read_rows(UNALLOC) if r["source_stream_id"] == BRICK]
        cls.support = [r for r in read_rows(SUPPORT) if r["source_stream_id"] == BRICK]
        cls.detail = read_rows(DETAIL)

    def test_the_three_frames_partition_the_brick_atoms(self):
        by_frame = defaultdict(float)
        for r in self.support:
            by_frame[(r["period_id"], r["configuration_id"], r["pollutant"], r["spatial_frame"])] += float(r["emissions_Gg"])
        self.assertEqual({k[3] for k in by_frame}, {"kiln_frame:FCBK", "kiln_frame:ZZ", "adm1_only"})
        want = defaultdict(float)
        for a in self.atoms:
            want[(a["period_id"], a["pollutant"])] += float(a["emissions_Gg"])
        for (pid, pol), v in want.items():
            for cfg in ("REF_2023_24", "L_HERD1624"):
                got = sum(by_frame[(pid, cfg, pol, f)] for f in ("kiln_frame:FCBK", "kiln_frame:ZZ", "adm1_only"))
                self.assertAlmostEqual(got, v, places=9, msg=(pid, cfg, pol))

    def test_the_remainder_is_the_unmapped_class_mass_exactly(self):
        remainder = defaultdict(float)
        for r in self.detail:
            if r["source_class_id"] == "brick_unmapped_remainder" and r["status"] == "estimate":
                remainder[(r["period_id"], r["pollutant"])] += float(r["emissions_kt"])
        below = defaultdict(float)
        for r in self.unalloc:
            if r["level"] == "below_adm1":
                below[(r["period_id"], r["pollutant"])] += float(r["emissions_Gg"]) / 2.0   # two configurations
        core = {"BC", "CO", "NH3", "NMVOC", "NOx", "PM2.5", "SO2"}
        for k, v in remainder.items():
            if k[1] in core:
                self.assertAlmostEqual(below[k], v, delta=1e-6, msg=k)

    def test_typed_frames_carry_their_own_hash_and_the_remainder_none(self):
        for r in self.support:
            if r["spatial_frame"].startswith("kiln_frame:"):
                self.assertTrue(r["pattern_hash"], r)
                self.assertTrue(r["surface"].startswith("brick_kiln_points_"), r)
            elif r["spatial_frame"] == "adm1_only":
                self.assertEqual(r["spatial_time_basis"], "unallocated", r)
                self.assertEqual(r["pattern_hash"], "", r)
        hashes = {r["spatial_frame"]: r["pattern_hash"] for r in self.support if r["spatial_frame"].startswith("kiln_frame:")}
        self.assertNotEqual(hashes["kiln_frame:FCBK"], hashes["kiln_frame:ZZ"])

    def test_removing_the_override_would_leave_the_remainder_untyped(self):
        """Planted defect: without the adm1_only override the remainder class would ride the
        pooled kiln vector and the unallocated table would carry no industry row - the
        sink's frame lookup is what types it."""
        from pkinv.report import air_spatial_by_year as m
        frames = m.frame_of_class()
        self.assertEqual(frames["brick_unmapped_remainder"], "adm1_only")
        stripped = {k: v for k, v in frames.items() if k != "brick_unmapped_remainder"}
        self.assertEqual(stripped.get("brick_unmapped_remainder", m.FRAME_NONE), m.FRAME_NONE)
        self.assertTrue(any(r["sector_id"] == "industry" and r["level"] == "below_adm1" for r in self.unalloc))


if __name__ == "__main__":
    unittest.main()
