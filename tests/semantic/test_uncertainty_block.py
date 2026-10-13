"""The envelope's uncertainty block: what it carries, and what it REFUSES to carry.

THE DEFECT THIS FILE EXISTS BECAUSE OF. `Engine._uncertainty_for` selected
`resolution = 'annual'` for a national request and the bare geography level otherwise, producing
'annual', 'adm1' or 'adm2'. The vocabulary is annual_national / monthly_national / annual_adm2 /
monthly_adm2, so none of the three ever matched and EVERY envelope this engine produced carried an
empty block. Nothing failed, because nothing asserted that a row ever came back - the block was
optional-looking and an empty one reads as "no uncertainty at this grain". So the first test here
is the boring one that was missing: rows exist.

THE REFUSALS. fact_uncertainty is keyed on (category, module, resolution) and nothing else. It
carries the reference period and the reference configuration only, and it has no gas column. Every
axis a caller can filter on that the table does not carry is a refusal, because returning the
category envelope for a request about one gas, one other year, one other configuration or one
stream would answer a question the release has not answered - in a block indistinguishable from a
real one. Each refusal names the axis that is missing; an empty block with no reason is what let
the resolution defect hide.
"""
import unittest

from pakemis_query.models import QueryEmissions

from semantic._golden import open_engine


class TheBlockCarriesRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = open_engine()
        cls.reference = cls.engine.release.defaults["period_id"]

    def block(self, **kw):
        kw.setdefault("periods", (self.reference,))
        return self.engine.query_emissions(QueryEmissions(**kw))["uncertainty"]

    def test_each_real_resolution_returns_rows(self):
        """The assertion whose absence let an always-empty block ship."""
        for label, kw, expected in (
                ("national annual", {}, "annual_national"),
                ("national monthly", {"months": ("202307",)}, "monthly_national"),
                ("district annual", {"geography_level": "adm2"}, "annual_adm2"),
                ("district monthly", {"geography_level": "adm2", "months": ("202307",)}, "monthly_adm2")):
            with self.subTest(label):
                block = self.block(**kw)
                self.assertEqual(block["resolution"], expected)
                self.assertTrue(block["rows"], "%s carries no uncertainty row" % label)
                self.assertIn(expected, block["interpretation"])

    def test_the_rows_are_categories_and_say_they_do_not_add_up(self):
        rows = self.block()["rows"]
        self.assertTrue(all(r.get("category") for r in rows))
        self.assertIn("quadrature", self.block()["interpretation"])
        self.assertTrue(all("never add" in (r.get("aggregation_rule") or "").lower()
                            or "never" in (r.get("aggregation_rule") or "").lower() for r in rows))

    def test_a_category_filter_narrows_to_that_category(self):
        """The block must answer the question that was asked. The Explorer's sidecar used to do
        this filtering itself, because this block was always empty; a fixed block that returned
        all 23 categories would be less useful than the workaround it replaced."""
        one = self.block(categories=("Enteric fermentation",))["rows"]
        self.assertEqual([r["category"] for r in one], ["Enteric fermentation"])

    def test_a_sector_filter_narrows_the_rows(self):
        everything = self.block()["rows"]
        one = self.block(sectors=("agriculture",))["rows"]
        self.assertTrue(one)
        self.assertLess(len(one), len(everything))
        self.assertEqual({r["module"] for r in one}, {"agriculture"})


class TheBlockRefusesWhatTheReleaseDoesNotPublish(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = open_engine()
        cls.reference = cls.engine.release.defaults["period_id"]

    def refusal(self, **kw):
        kw.setdefault("periods", (self.reference,))
        block = self.engine.query_emissions(QueryEmissions(**kw))["uncertainty"]
        self.assertEqual(block["rows"], [], "this grain has no published interval and returned rows")
        self.assertIsNone(block["resolution"])
        return block["interpretation"].lower()

    def test_no_provincial_interval_exists(self):
        """The one a reader is most likely to want. There is no adm1 resolution at any grain, and
        the national interval may not stand in for a province."""
        self.assertIn("adm1", self.refusal(geography_level="adm1"))

    def test_no_per_gas_interval_exists(self):
        self.assertIn("gas", self.refusal(gases=("CH4",)))

    def test_no_interval_for_another_configuration(self):
        """The refusal names the configuration it was asked for. Since rc67 that is
        L_2023_24, the ledger dung basis; S_2023_24 is retired (what it named is the
        reference, which does have an interval) and must not be what the reason says."""
        reason = self.refusal(configuration_id="L_2023_24")
        self.assertIn("configuration", reason)
        self.assertIn("l_2023_24", reason)
        self.assertNotIn("s_2023_24", reason)

    def test_no_category_interval_for_another_period(self):
        """Only the national covered total has a per-year interval, and it lives in a different
        table. Handing back the reference year's category envelope for FY2019-20 would be a
        different year's answer wearing this one's label."""
        reason = self.refusal(periods=("FY2019-20",))
        self.assertIn(self.reference.lower(), reason)
        self.assertIn("fact_uncertainty_series", reason)

    def test_no_per_stream_interval_exists(self):
        streams = [s["source_stream_id"] for s in self.engine.release.dim("dim_stream")][:1]
        self.assertIn("category", self.refusal(streams=tuple(streams)))

    def test_every_refusal_says_what_is_missing(self):
        """A refusal with no reason is indistinguishable from a lookup miss, which is how the
        resolution defect survived."""
        for kw in ({"geography_level": "adm1"}, {"gases": ("CH4",)},
                   {"configuration_id": "L_2023_24"}, {"periods": ("FY2019-20",)}):
            with self.subTest(str(kw)):
                self.assertGreater(len(self.refusal(**kw)), 60)


if __name__ == "__main__":
    unittest.main()
