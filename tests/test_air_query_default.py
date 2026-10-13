"""query_air answers a request that names no period for the REFERENCE period, and says so.

Until 2026-10 the function had no default here; it had a fork. With `periods` it answered from
the covered-sources family (the national panel and its province and district marginals), where
a source that is only screened rides beside the values. Without `periods` it answered from the
pre-rc48 single-year layers, where grid power's UNCONTROLLED SCREENING BOUND is a row like any
other - most of a "national SO2 total" that the completeness rule forbids summing - and nothing
in the envelope said which had answered. One omitted field changed the product, silently, and a
public explorer served the result as a sector breakdown for a month.

Every air golden named a period, so the fork had no test at all. These are the tests: written
to FAIL on the tree before the default.
"""
import os
import sys
import unittest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SINGLE_YEAR_LAYERS = ("fact_air_annual", "fact_air_adm1", "fact_air_adm2")


class TestAirQueryDefaultsItsPeriod(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import duckdb  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("duckdb not installed")
        sys.path.insert(0, os.path.join(ROOT, "tests"))
        from semantic._golden import open_engine
        cls.engine = open_engine()
        cls.reference = cls.engine.release.defaults["period_id"]

    def ask(self, **fields):
        from pakemis_query.models import QueryAir
        return self.engine.query_air(QueryAir(**fields))

    def test_no_period_is_the_reference_period_and_is_disclosed(self):
        for extra, table in (({}, "fact_air_panel"),
                             ({"geography_level": "adm1"}, "fact_air_adm1_year"),
                             ({"geography_level": "adm2"}, "fact_air_adm2_year")):
            for pollutant in ("SO2", "PM2.5", "NH3"):
                bare = self.ask(pollutants=(pollutant,), **extra)
                named = self.ask(pollutants=(pollutant,), periods=(self.reference,), **extra)
                self.assertEqual(bare["calculation"]["table"], table, (pollutant, extra))
                self.assertNotIn(bare["calculation"]["table"], SINGLE_YEAR_LAYERS)
                self.assertEqual(tuple(bare["context"]["periods"]), (self.reference,))
                self.assertIn("periods", bare["context"]["defaults_applied"])
                self.assertNotIn("periods", named["context"]["defaults_applied"])
                # the same cells as asking for the reference period by name. (The digest differs,
                # as it does for query_emissions: it covers `defaults_applied`, and one was.)
                self.assertEqual(bare["values"], named["values"])
                self.assertIn("air_covered_sources", [l["id"] for l in bare["limitations_hit"]])

    def test_a_defaulted_answer_carries_the_screening_block_beside_its_values(self):
        """What the single-year layer put INSIDE the total rides beside it here: power's scenario
        pair is in `completeness`, and no cell of the answer is as large as its uncontrolled end
        added to the covered sum would make it."""
        env = self.ask(pollutants=("SO2",), group_by=("sector_id",))
        pair = [r for r in env["completeness"] if r["sector_id"] == "power"]
        self.assertEqual(len(pair), 1)
        self.assertTrue(pair[0]["scenario_uncontrolled_kt"])
        total = float(self.ask(pollutants=("SO2",))["values"][0]["exact"])
        self.assertAlmostEqual(sum(float(v["exact"]) for v in env["values"]), total, places=6)
        self.assertLess(total, float(pair[0]["scenario_uncontrolled_kt"]) + total)   # the bound is not in it
        # and whatever power holds in the covered panel is an ESTIMATE, smaller than its own screening bound
        power = [v for v in env["values"] if v["group"]["sector_id"] == "power"]
        for v in power:
            self.assertLess(float(v["exact"]), float(pair[0]["scenario_uncontrolled_kt"]))

    def test_a_trend_is_not_defaulted_to_one_year(self):
        from pakemis_query import errors as E
        for grouping in (("period_id",), ("year",)):
            with self.assertRaises(E.GrainUnavailable) as raised:
                self.ask(pollutants=("NH3",), group_by=grouping)
            self.assertIn("name the", str(raised.exception))

    def test_the_calendar_series_is_untouched(self):
        env = self.ask(pollutants=("NH3",), years=("2000", "2010"), group_by=("year",))
        self.assertEqual(env["calculation"]["table"], "fact_air_timeseries")
        self.assertEqual(tuple(env["context"]["periods"] or ()), ())
        self.assertNotIn("periods", env["context"]["defaults_applied"])

    def test_no_request_reaches_the_single_year_layers(self):
        """The fork is gone, not merely defaulted around: the function's source names none of
        the three tables any more."""
        import inspect
        from pakemis_query.engine import Engine
        source = inspect.getsource(Engine.query_air)
        code = "\n".join(line for line in source.split('"""', 2)[2].splitlines() if not line.strip().startswith("#"))
        for table in SINGLE_YEAR_LAYERS:
            self.assertNotRegex(code, r'"%s"' % table)

    def test_a_refusal_names_the_sectors_the_grain_holds_from_its_table(self):
        """The provincial refusal listed industry, IPPU and fugitives as absent after all three
        had a provincial layer; it reads the list from the table it is about to query."""
        from pakemis_query import errors as E
        have = {r["sector_id"] for r in self.engine._fetch("SELECT DISTINCT sector_id FROM fact_air_adm1_year")}
        for sector in ("industry", "ippu", "fugitives"):
            self.assertIn(sector, have)
            self.ask(pollutants=("PM2.5",), sectors=(sector,), geography_level="adm1")   # answered, not refused
        absent = sorted(set(Engine_sectors()) - have)
        for sector in absent:
            with self.assertRaises(E.GrainUnavailable) as raised:
                self.ask(pollutants=("PM2.5",), sectors=(sector,), geography_level="adm1")
            for held in have:
                self.assertIn(held, str(raised.exception))


def Engine_sectors():
    from pakemis_query.engine import Engine
    return Engine.AIR_SECTORS


if __name__ == "__main__":
    unittest.main()
