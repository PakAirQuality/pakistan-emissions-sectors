"""The per-stream ADM2 reference product (Wave B of the air spatial lane): the cube's own
stream_shape accumulation, published annually for every placed stream. Closure: each stream's
shapes + OUTSIDE == its ADM1-year annual mass. Streams explicitly retained at ADM1 in
the current source-geometry ledger must be absent from the placed district product."""
import collections
import csv
import io
import os
import unittest
from pkinv.core import configurations as conf
from pkinv.core.io import read_rows
from pkinv.report.grid_cube import NO_NATIVE_GEOMETRY

ROOT = os.path.join(os.path.dirname(__file__), "..")
REF = os.path.join(ROOT, "outputs", "pakemis_adm2_stream_reference.csv")
ADM1 = os.path.join(ROOT, "outputs", "semantic", "fact_adm1_year.csv")
RTOL = 1e-9


class TestAdm2StreamReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with io.open(REF, encoding="utf-8") as handle:
            lines = [line for line in handle if not line.startswith("#")]
        cls.rows = list(csv.DictReader(lines))
        cls.by_stream = collections.defaultdict(float)
        for r in cls.rows:
            if r["emissions_Gg"]:
                cls.by_stream[r["source_stream_id"]] += float(r["emissions_Gg"])
        cls.adm1 = collections.defaultdict(float)
        with open(ADM1, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["period_id"] == "FY2023-24" and r["configuration_id"] == conf.REFERENCE:
                    cls.adm1[r["source_stream_id"]] += float(r["emissions_Gg"])
        cls.unallocated = {r["source_stream_id"] for r in read_rows(
            os.path.join(ROOT, "outputs", "pakemis_source_streams.csv"))
            if r["geometry_id"] == NO_NATIVE_GEOMETRY}

    def test_every_placed_stream_closes_to_its_adm1_mass(self):
        for sid, national in self.adm1.items():
            if sid in self.unallocated:
                continue
            self.assertIn(sid, self.by_stream, sid)
            if national > 0:
                rel = abs(self.by_stream[sid] - national) / national
                self.assertLess(rel, RTOL, "%s: %.6g vs %.6g" % (sid, self.by_stream[sid], national))

    def test_only_the_current_adm1_retained_streams_are_absent(self):
        absent = set(self.adm1) - set(self.by_stream)
        self.assertEqual(absent, self.unallocated)

    def test_statuses_are_the_frame_vocabulary(self):
        self.assertEqual({r["allocation_status"] for r in self.rows},
                         {"one_to_one", "shared_shape", "outside_all_shapes"})


if __name__ == "__main__":
    unittest.main()
