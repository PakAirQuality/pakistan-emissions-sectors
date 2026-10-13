"""The unallocated block of a province or district answer is the block for the scope ASKED.

`fact_unallocated` - the mass retained at ADM1 and placed no finer - is the reference year's
table and has no period column. The query core attached it, whole, to an answer for ANY year,
gas or spatial view: FY2015-16 said 0.25 Mt retained where that year's own figure is 0.40,
all nine years read the same, a methane answer carried the all-gas block, and the `physical`
view - which retains nothing - carried the accounting view's.

The engine now reads another year's block from the province table (the retained streams are
ordinary rows of it). Three independent statements hold it here:

  * the release's closure, per period, gas and view: ADM1 == ADM2 + the block;
  * the by-year product the spatial build writes for exactly this mass
    (outputs/pakemis_spatial_unallocated_by_year.csv), which the block must equal per period
    and per province;
  * the reference year's block is fact_unallocated's rows, unchanged.

Written to FAIL on the tree before the change.
"""
import collections
import csv
import os
import sys
import unittest
from decimal import Decimal

ROOT = os.path.join(os.path.dirname(__file__), "..")
BY_YEAR = os.path.join(ROOT, "outputs", "pakemis_spatial_unallocated_by_year.csv")
TOL = Decimal("0.00005")


class TestTheBlockIsTheScopesOwn(unittest.TestCase):
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
        cls.periods = sorted(r["period_id"] for r in cls.engine._fetch("SELECT DISTINCT period_id FROM fact_adm1_year"))
        with open(BY_YEAR, newline="", encoding="utf-8") as handle:
            cls.product = list(csv.DictReader(l for l in handle if not l.startswith("#")))

    def ask(self, **fields):
        from pakemis_query.models import QueryEmissions
        return self.engine.query_emissions(QueryEmissions(**fields))

    @staticmethod
    def cells(env):
        return sum(Decimal(v["exact"]) for v in env["values"])

    @staticmethod
    def retained(env):
        return sum(Decimal(r["exact"]) for r in env["unallocated"]["by_province"])

    def test_nine_periods(self):
        self.assertEqual(len(self.periods), 9)
        self.assertIn(self.reference, self.periods)

    def test_every_period_closes_on_its_own_block(self):
        seen = set()
        for period in self.periods:
            adm1 = self.ask(geography_level="adm1", periods=(period,), group_by=("province",))
            adm2 = self.ask(geography_level="adm2", periods=(period,), group_by=("province",))
            self.assertEqual(adm1["unallocated"]["periods"], [period])
            self.assertEqual(self.retained(adm1), self.retained(adm2))
            self.assertLess(abs(self.cells(adm1) - self.cells(adm2) - self.retained(adm1)), TOL, period)
            seen.add(self.retained(adm1).quantize(Decimal("0.0001")))
        self.assertEqual(len(seen), len(self.periods), "nine periods, nine different figures - not one table repeated")

    def test_the_block_equals_the_by_year_product(self):
        """The spatial build writes this mass per period itself; the query must agree with it."""
        want = collections.defaultdict(Decimal)
        for r in self.product:
            want[(r["period_id"], r["province"])] += Decimal(r["co2e_Mt_AR5"])
        self.assertEqual({p for p, _ in want}, set(self.periods))
        for period in self.periods:
            env = self.ask(geography_level="adm1", periods=(period,), group_by=("province",))
            got = {r["province"]: Decimal(r["exact"]) for r in env["unallocated"]["by_province"]}
            self.assertEqual(set(got), {prov for p, prov in want if p == period})
            for province, value in got.items():
                self.assertLess(abs(value - want[(period, province)]), Decimal("0.000001"), (period, province))

    def test_the_reference_year_is_fact_unallocated_unchanged(self):
        env = self.ask(geography_level="adm1", group_by=("province",))
        self.assertEqual(env["unallocated"]["table"], "fact_unallocated")
        rows = self.engine._fetch("SELECT province, SUM(CAST(co2e_Mt_AR5 AS DECIMAL(38,18))) AS exact FROM fact_unallocated "
                                  "WHERE configuration_id = 'REF_2023_24' GROUP BY province")
        self.assertEqual({r["province"]: r["exact"] for r in env["unallocated"]["by_province"]},
                         {r["province"]: str(r["exact"]) for r in rows})

    def test_another_year_names_the_table_it_was_read_from(self):
        env = self.ask(geography_level="adm1", periods=("FY2015-16",), group_by=("province",))
        self.assertEqual(env["unallocated"]["table"], "fact_adm1_year")
        self.assertIn("fact_adm1_year", [t["table"] for t in env["provenance"]["tables"]])

    def test_the_block_is_for_the_gas_and_the_view_asked(self):
        for period in ("FY2015-16", self.reference):
            for gas in ("CO2", "CH4", "N2O"):
                a = self.ask(geography_level="adm1", periods=(period,), gases=(gas,), group_by=("province",))
                b = self.ask(geography_level="adm2", periods=(period,), gases=(gas,), group_by=("province",))
                self.assertLess(abs(self.cells(a) - self.cells(b) - self.retained(a)), TOL, (period, gas))
            whole = self.retained(self.ask(geography_level="adm1", periods=(period,), group_by=("province",)))
            for view in ("physical", "origin", "accounting"):
                a = self.ask(geography_level="adm1", periods=(period,), spatial_view=view, group_by=("province",))
                b = self.ask(geography_level="adm2", periods=(period,), spatial_view=view, group_by=("province",))
                self.assertLess(abs(self.cells(a) - self.cells(b) - self.retained(a)), TOL, (period, view))
                # every retained row is in the accounting view: the others retain NOTHING, and
                # an empty list says so (never a zero row)
                if view == "accounting":
                    self.assertEqual(self.retained(a), whole)
                else:
                    self.assertEqual(a["unallocated"]["by_province"], [])
        methane = self.retained(self.ask(geography_level="adm1", gases=("CH4",), group_by=("province",)))
        self.assertLess(methane, Decimal("0.001"))

    def test_another_warming_potential_basis_gets_the_block_in_that_basis(self):
        ar6 = self.ask(geography_level="adm1", gwp_basis="AR6", group_by=("province",))
        ar5 = self.ask(geography_level="adm1", group_by=("province",))
        self.assertEqual(ar6["unallocated"]["table"], "fact_adm1_month")
        self.assertNotEqual(self.retained(ar6), self.retained(ar5))

    def test_the_block_stays_outside_the_result_digest(self):
        """It describes the cells and is not one of them: the receipt of a province answer is
        the same whichever table the block was read from."""
        env = self.ask(geography_level="adm1", periods=("FY2015-16",), group_by=("province",))
        from pakemis_query.envelope import result_digest, digest_context
        self.assertEqual(env["result_sha256"], result_digest(env["values"], digest_context(env["context"])))


if __name__ == "__main__":
    unittest.main()
