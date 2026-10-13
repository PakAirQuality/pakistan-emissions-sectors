"""fact_spatial_basis_year: how much of each year's mass rides geography that is its own.

The province and district year tables are mass; what their geography rests on is the weight
registry's to say, per stream-year. The only public statement of "how much of an earlier year
is reconstructed" was a count of stream-years in a limitation sentence, and the registry
outran the sentence twice. This table is the registry weighted by mass, and these tests hold
it to the two things it is made from:

  * per period it sums to the province table - nothing is dropped, nothing counted twice;
  * every row's basis is the registry's own word for that stream-year, and every stream-year
    with mass is in exactly one row.
"""
import collections
import os
import unittest
from decimal import Decimal

from pkinv.core.io import read_rows

ROOT = os.path.join(os.path.dirname(__file__), "..")
SEMANTIC = os.path.join(ROOT, "outputs", "semantic")
REGISTRY = os.path.join(ROOT, "outputs", "pakemis_spatial_weights_by_year.csv")
BASES = {"annual_observed_activity", "static_structural", "reference_shape_backcast",
         "substituted_surface", "unallocated"}


def _fact(name):
    return read_rows(os.path.join(SEMANTIC, name + ".csv"))


class TestTheBasisTableIsTheRegistryWeightedByMass(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.basis = _fact("fact_spatial_basis_year")
        cls.adm1 = _fact("fact_adm1_year")
        cls.registry = {(r["source_stream_id"], r["period_id"]): r["spatial_time_basis"]
                        for r in read_rows(REGISTRY)}

    def test_nine_periods_and_a_closed_vocabulary(self):
        self.assertEqual(len({r["period_id"] for r in self.basis}), 9)
        self.assertLessEqual({r["spatial_time_basis"] for r in self.basis}, BASES)
        self.assertEqual({r["configuration_id"] for r in self.basis}, {"REF_2023_24"})

    def test_each_period_sums_to_the_province_table(self):
        want = collections.defaultdict(Decimal)
        for r in self.adm1:
            want[r["period_id"]] += Decimal(r["co2e_Mt_AR5"])
        got = collections.defaultdict(Decimal)
        for r in self.basis:
            got[r["period_id"]] += Decimal(r["co2e_Mt_AR5"])
        self.assertEqual(set(got), set(want))
        for period in want:
            self.assertLess(abs(got[period] - want[period]), Decimal("0.000001"), period)

    def test_each_sector_sums_to_its_own_province_total(self):
        want = collections.defaultdict(Decimal)
        for r in self.adm1:
            want[(r["period_id"], r["module"], r["reporting_sector"])] += Decimal(r["co2e_Mt_AR5"])
        got = collections.defaultdict(Decimal)
        for r in self.basis:
            got[(r["period_id"], r["module"], r["reporting_sector"])] += Decimal(r["co2e_Mt_AR5"])
        self.assertEqual(set(got), set(want))
        for key in want:
            self.assertLess(abs(got[key] - want[key]), Decimal("0.000001"), key)

    def test_every_row_is_the_registrys_own_word(self):
        """Rebuilt here from the two sources, independently of the builder: the mass under each
        basis is the mass of the stream-years the registry files under it."""
        want = collections.defaultdict(Decimal)
        for r in self.adm1:
            basis = self.registry.get((r["source_stream_id"], r["period_id"]))
            self.assertIsNotNone(basis, "a stream-year with province mass and no registry row: %s %s"
                                 % (r["source_stream_id"], r["period_id"]))
            want[(r["period_id"], r["module"], r["reporting_sector"], basis)] += Decimal(r["co2e_Mt_AR5"])
        got = {(r["period_id"], r["module"], r["reporting_sector"], r["spatial_time_basis"]): Decimal(r["co2e_Mt_AR5"])
               for r in self.basis}
        self.assertEqual(set(got), set(want))
        for key, value in want.items():
            self.assertLess(abs(got[key] - value), Decimal("0.000001"), key)

    def test_the_reference_year_is_never_a_backcast_of_itself(self):
        reference = [r for r in self.basis if r["period_id"] == "FY2023-24"]
        self.assertTrue(reference)
        self.assertNotIn("reference_shape_backcast", {r["spatial_time_basis"] for r in reference})

    def test_the_retained_streams_are_typed_unallocated_in_every_year(self):
        """The cruise streams have no district geography in any year; their mass is the
        unallocated block the query serves, and it is filed under that word here."""
        retained = collections.defaultdict(Decimal)
        for r in self.basis:
            if r["spatial_time_basis"] == "unallocated":
                retained[r["period_id"]] += Decimal(r["co2e_Mt_AR5"])
        self.assertEqual(len(retained), 9)
        self.assertTrue(all(v > 0 for v in retained.values()))

    def test_it_is_a_table_of_the_contract(self):
        import json
        with open(os.path.join(SEMANTIC, "semantic_release.json"), encoding="utf-8") as handle:
            contract = json.load(handle)
        table = contract["facts"]["fact_spatial_basis_year"]
        self.assertEqual(table["primary_key"], ["configuration_id", "period_id", "module", "reporting_sector", "spatial_time_basis"])
        text = " ".join(l["message"] for l in contract["known_limitations"] if l["id"] == "adm2_history_annual_only")
        self.assertIn("fact_spatial_basis_year", text)


if __name__ == "__main__":
    unittest.main()
