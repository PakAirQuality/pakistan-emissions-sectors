"""The per-stream ADM2 reference product (Wave B of the air spatial lane): the cube's own
stream_shape accumulation, published annually for every placed stream. Closure: each stream's
shapes + OUTSIDE == its ADM1-year annual mass; the only absent streams are the three aviation
cruise streams, unallocated below ADM1 by construction."""
import collections
import csv
import io
import os
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
REF = os.path.join(ROOT, "outputs", "pakemis_adm2_stream_reference.csv")
ADM1 = os.path.join(ROOT, "outputs", "semantic", "fact_adm1_year.csv")
CRUISE = {
    "aviation|domestic-aviation|domestic-aviation-cruise-ch4|ch4",
    "aviation|domestic-aviation|domestic-aviation-cruise-co2|co2",
    "aviation|domestic-aviation|domestic-aviation-cruise-n2o|n2o",
}
RTOL = 1e-9


class TestAdm2StreamReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lines = [l for l in io.open(REF, encoding="utf-8") if not l.startswith("#")]
        cls.rows = list(csv.DictReader(lines))
        cls.by_stream = collections.defaultdict(float)
        for r in cls.rows:
            if r["emissions_Gg"]:
                cls.by_stream[r["source_stream_id"]] += float(r["emissions_Gg"])
        cls.adm1 = collections.defaultdict(float)
        with open(ADM1, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r["period_id"] == "FY2023-24":
                    cls.adm1[r["source_stream_id"]] += float(r["emissions_Gg"])

    def test_every_placed_stream_closes_to_its_adm1_mass(self):
        for sid, national in self.adm1.items():
            if sid in CRUISE:
                continue
            self.assertIn(sid, self.by_stream, sid)
            if national > 0:
                rel = abs(self.by_stream[sid] - national) / national
                self.assertLess(rel, RTOL, "%s: %.6g vs %.6g" % (sid, self.by_stream[sid], national))

    def test_only_the_cruise_streams_are_absent(self):
        absent = set(self.adm1) - set(self.by_stream)
        self.assertEqual(absent, CRUISE)

    def test_statuses_are_the_frame_vocabulary(self):
        self.assertEqual({r["allocation_status"] for r in self.rows},
                         {"one_to_one", "shared_shape", "outside_all_shapes"})


if __name__ == "__main__":
    unittest.main()
