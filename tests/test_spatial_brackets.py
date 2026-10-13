"""The spatial-alternatives registry and its bracket product.

Four directions: every registry row matches at least one ledger stream (a row
matching nothing is a bracket on air); every S4 no-native-geometry stream is covered
by a no-alternative row (the admission must be complete, not sampled); the priced
brackets reproduce from their named sources; and the product regenerates identically
from the live registry. The brackets carry no probabilities - a spread between two
defensible readings, never a distribution - and the transport rows are allocation
disagreement, not error against an observation (validation registry,
geo-transport-proxy).
"""
import csv
import os
import unittest
from pkinv.core.io import read_rows
from _support import OUT, ROOT



def _rows(path):
    return read_rows(path)


class TestSpatialBrackets(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.report import spatial_brackets
        cls.sb = spatial_brackets
        cls.registry = spatial_brackets.registry()
        cls.product = _rows(os.path.join(OUT, "pakemis_spatial_brackets.csv"))
        cls.streams = _rows(os.path.join(OUT, "pakemis_source_streams.csv"))

    def test_every_registry_row_matches_a_stream(self):
        for entry in self.registry:
            matched = self.sb._matched_streams(entry, self.streams)
            self.assertTrue(matched, entry["alternative_id"])

    def test_every_s4_stream_carries_the_no_alternative_admission(self):
        s4 = {s["source_stream_id"] for s in self.streams
              if s["geometry_id"] == "S4:no-native-geometry"}
        self.assertTrue(s4)
        admitted = set()
        for row in self.product:
            if row["status"] == "no_alternative_declared":
                for sid in s4:
                    if sid in row["note"]:
                        admitted.add(sid)
        self.assertEqual(admitted, s4,
                         "S4 streams missing the no-alternative admission: %s"
                         % sorted(s4 - admitted))

    def test_the_registration_bracket_reproduces_from_its_source(self):
        source = {r["province"]: r for r in _rows(
            os.path.join(OUT, "transport_provincial_proxy_comparison_2024.csv"))}
        for row in self.product:
            if row["alternative_id"] != "transport_diesel_registration" \
                    or row["province"] == "MAX_ABS":
                continue
            s = source[row["province"]]
            expected = (float(s["diesel_share_fuel"])
                        - float(s["share_registration"])) * 100.0
            self.assertAlmostEqual(float(row["spread_pp"]), expected, delta=6e-4,
                                   msg=row["province"])

    def test_the_shape_bracket_matches_the_transport_product(self):
        worst = max(abs(float(r["spread_pp"])) for r in _rows(
            os.path.join(OUT, "transport_provincial_shape_brackets.csv")))
        row = next(r for r in self.product
                   if r["alternative_id"] == "transport_shape_year"
                   and r["province"] == "MAX_ABS")
        self.assertAlmostEqual(float(row["spread_pp"]), worst, places=3)

    def test_no_probability_like_column(self):
        with open(os.path.join(OUT, "pakemis_spatial_brackets.csv"), newline="",
                  encoding="utf-8") as handle:
            header = next(csv.reader(handle))
        for col in header:
            for word in ("probability", "prob", "weight", "likelihood", "prior"):
                self.assertNotIn(word, col.lower())

    def test_the_product_regenerates_identically(self):
        fresh = self.sb.build()
        self.assertEqual(len(fresh), len(self.product))
        for f_row, s_row in zip(fresh, self.product):
            for col in self.sb.FIELDS:
                self.assertEqual(str(f_row[col]), s_row[col],
                                 "%s/%s.%s" % (f_row["alternative_id"],
                                               f_row["province"], col))

    def test_non_province_rows_state_where_their_bracket_lives(self):
        """rc9 flipped the two within-province rows: the captive alternative is
        priced at ADM2 and the residential one is structurally invariant there -
        each seed row must point at the ADM2 product rather than deferring vaguely."""
        special = [r for r in self.product
                   if r["status"] in ("priced_adm2",
                                      "structurally_invariant_at_adm2",
                                      "declared_deferred")]
        self.assertTrue(special)
        for row in special:
            self.assertTrue("pakemis_spatial_brackets_adm2.csv" in row["note"]
                            or "share-constrained" in row["note"], row["status"])


if __name__ == "__main__":
    unittest.main()
