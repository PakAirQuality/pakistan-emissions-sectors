"""Matched uncertainty blocks: native annual ensembles and legacy category envelopes."""
import unittest

from pakemis_query.models import QueryEmissions
from pkinv.core import configurations as conf
from pkinv.core.io import read_rows
from pkinv.paths import OUTPUTS
from semantic._golden import open_engine


class ConditionalAnnualBlocks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = open_engine()
        cls.reference = cls.engine.release.defaults["period_id"]
        cls.source = read_rows(OUTPUTS + "/pakemis_ghg_conditional_uncertainty.csv")

    def query(self, **kw):
        kw.setdefault("periods", (self.reference,))
        return self.engine.query_emissions(QueryEmissions(**kw))

    def test_annual_block_reads_the_actual_configuration_period_and_metric(self):
        for cfg, period in (("S_TAN", self.reference), ("L_2023_24", "FY2019-20"),
                            ("S_IPCC", "FY2024-25"), ("L_IPCC", "FY2015-16")):
            with self.subTest(cfg=cfg, period=period):
                output = self.query(configuration_id=cfg, periods=(period,))
                block = output["uncertainty"]
                self.assertTrue(block["available"])
                self.assertEqual(block["kind"], "conditional_parameter_percentiles")
                self.assertEqual(block["table"], "fact_ghg_conditional")
                self.assertEqual({r["dependence_case"] for r in block["rows"]},
                                 {"persistent_parameters", "annual_activity_errors"})
                expected = {r["dependence_case"]: r for r in self.source
                            if r["period_id"] == period and r["configuration_id"] == conf.canonical(cfg)
                            and r["sector_id"] == "national_covered" and r["species_or_metric"] == "CO2e_AR5"}
                for row in block["rows"]:
                    self.assertEqual(row["period_id"], period)
                    self.assertEqual(row["configuration_id"], conf.canonical(cfg))
                    for key in ("deterministic_quantity", "P2_5_quantity", "P50_quantity", "P97_5_quantity", "draws", "seed"):
                        self.assertEqual(row[key], expected[row["dependence_case"]][key])
                self.assertIn("not additive", block["note"])

    def test_sector_filter_selects_its_own_conditional_mass(self):
        for sector in ("agriculture", "residential", "power"):
            output = self.query(sectors=(sector,))
            rows = output["uncertainty"]["rows"]
            self.assertEqual({r["sector_id"] for r in rows}, {sector})
            self.assertEqual(len(rows), 2)
            exact = sum(float(v["exact"]) for v in output["values"])
            for row in rows:
                self.assertAlmostEqual(float(row["deterministic_quantity"]), exact, delta=1e-5)


class CategoryAllocationEnvelopes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = open_engine()
        cls.reference = cls.engine.release.defaults["period_id"]

    def block(self, **kw):
        kw.setdefault("periods", (self.reference,))
        return self.engine.query_emissions(QueryEmissions(**kw))["uncertainty"]

    def test_supported_category_and_allocation_resolutions_return_typed_rows(self):
        for label, kw, resolution in (
                ("national category", {"categories": ("Enteric fermentation",)}, "annual_national"),
                ("national month", {"months": ("202307",)}, "monthly_national"),
                ("district annual", {"geography_level": "adm2"}, "annual_adm2"),
                ("district month", {"geography_level": "adm2", "months": ("202307",)}, "monthly_adm2")):
            with self.subTest(label):
                block = self.block(**kw)
                self.assertEqual(block["resolution"], resolution)
                self.assertTrue(block["rows"])
                self.assertTrue(all(r.get("category") for r in block["rows"]))
                self.assertIn("NEVER combined", block["interpretation"])
                self.assertTrue(all("never" in r["aggregation_rule"].lower() for r in block["rows"]))

    def test_category_and_sector_filters_narrow_the_envelope(self):
        block = self.block(categories=("Enteric fermentation",), sectors=("agriculture",))
        self.assertEqual([r["category"] for r in block["rows"]], ["Enteric fermentation"])
        self.assertEqual({r["module"] for r in block["rows"]}, {"agriculture"})

    def refusal(self, **kw):
        block = self.block(**kw)
        self.assertEqual(block["rows"], [])
        self.assertIsNone(block["resolution"])
        self.assertGreater(len(block["interpretation"]), 60)
        return block["interpretation"].lower()

    def test_an_aggregate_interval_cannot_substitute_for_an_unsupported_grain(self):
        checks = (({"geography_level": "adm1"}, "adm1"),
                  ({"gases": ("CH4",)}, "gas"),
                  ({"categories": ("Enteric fermentation",), "configuration_id": "L_TAN"}, "configuration"),
                  ({"categories": ("Enteric fermentation",), "periods": ("FY2019-20",)}, "category"),
                  ({"spatial_view": "physical"}, "view"))
        for request, word in checks:
            with self.subTest(request):
                self.assertIn(word, self.refusal(**request))

    def test_no_per_stream_envelope_is_inferred_from_a_category(self):
        stream = self.engine.release.dim("dim_stream")[0]["source_stream_id"]
        self.assertIn("stream", self.refusal(streams=(stream,)))


if __name__ == "__main__":
    unittest.main()
