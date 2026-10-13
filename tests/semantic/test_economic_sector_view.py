"""The economic-sector view: a derived group key over the same atoms.

`group_by: ["economic_sector"]` regroups fact_annual by what the activity IS: 'industrial' = the
industry and ippu REPORTING sectors (data/stream_reporting_sector.csv) - 1.A.2 manufacturing
combustion including the captive generation the power module computes, which enters through the
reporting axis rather than a code match, + every 2.x process category; every other sector keeps
its module. Three things must
hold, every period: the two views sum to the same national total (additive regrouping, nothing
invented); the industrial aggregate equals the boundary ledger's PRICED total ("covered direct
industrial sources" - the ledger is the engine-side truth the view must reproduce); and railways'
unresolved '1.A.2/1.A.4.c' code is NOT swept into industry by a bare prefix match."""
import csv
import io
import os
import unittest
from collections import defaultdict
from decimal import Decimal

from pkinv.paths import OUTPUTS
from pakemis_query.models import QueryEmissions

from semantic._golden import open_engine

LEDGER = os.path.join(OUTPUTS, "pakemis_industry_boundary_ledger.csv")


def _ledger_priced():
    with open(LEDGER, encoding="utf-8") as h:
        text = "\n".join(l for l in h.read().splitlines() if not l.startswith("#"))
    priced = defaultdict(Decimal)
    for r in csv.DictReader(io.StringIO(text)):
        if r["boundary_status"].startswith("priced") and r["co2e_Mt"]:
            priced[r["period_id"]] += Decimal(r["co2e_Mt"])
    return priced


class EconomicSectorView(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = open_engine()
        cls.periods = tuple(p["period_id"] for p in cls.engine.release.dim("dim_period") if p["basis"] == "fiscal")

    def _cells(self, key):
        out = self.engine.query_emissions(QueryEmissions(periods=self.periods, group_by=("period_id", key)))
        return {(c["group"]["period_id"], c["group"][key]): Decimal(c["exact"]) for c in out["values"]}, out

    def test_both_views_sum_to_the_same_total_every_period(self):
        ipcc, _ = self._cells("sector_id")
        econ, _ = self._cells("economic_sector")
        for p in self.periods:
            a = sum(v for (pp, _), v in ipcc.items() if pp == p)
            b = sum(v for (pp, _), v in econ.items() if pp == p)
            self.assertEqual(a, b, p)

    def test_industrial_is_the_covered_direct_boundary_the_ledger_prices(self):
        econ, _ = self._cells("economic_sector")
        priced = _ledger_priced()
        self.assertEqual(set(priced), set(self.periods))
        for p in self.periods:
            # the ledger's 6-dp cells sum to n x half-ulp of the exact atoms
            self.assertLess(abs(econ[(p, "industrial")] - priced[p]), Decimal("0.00005"), p)
        self.assertAlmostEqual(float(econ[("FY2023-24", "industrial")]), 53.666, places=2)   # rc52: + ammonia, steel, lubricants
        self.assertAlmostEqual(float(econ[("FY2015-16", "industrial")]), 62.580, places=2)

    def test_industrial_is_module_industry_plus_captive_plus_ippu_and_nothing_else(self):
        ipcc, _ = self._cells("sector_id")
        econ, _ = self._cells("economic_sector")
        codes = self.engine.query_emissions(QueryEmissions(periods=("FY2023-24",), group_by=("sector_id", "ipcc_code")))
        # captive is the stream the REPORTING axis files under industry while the power module
        # computes it: selected by the axis, and it must be the same mass the code view names
        keyed = self.engine.query_emissions(QueryEmissions(periods=("FY2023-24",),
                                                           group_by=("sector_id", "reporting_sector")))
        captive = sum(Decimal(c["exact"]) for c in keyed["values"]
                      if c["group"]["sector_id"] == "power" and c["group"]["reporting_sector"] == "industry")
        by_code = sum(Decimal(c["exact"]) for c in codes["values"]
                      if c["group"]["sector_id"] == "power" and c["group"]["ipcc_code"] == "1.A.2")
        self.assertEqual(captive, by_code)
        self.assertGreater(captive, 0)
        rail_split = [c for c in codes["values"] if c["group"]["ipcc_code"].startswith("1.A.2/")]
        self.assertTrue(rail_split, "the railways split code is the guard's reason to exist")
        self.assertEqual(econ[("FY2023-24", "industrial")],
                         ipcc[("FY2023-24", "industry")] + ipcc[("FY2023-24", "ippu")] + captive)
        self.assertEqual(econ[("FY2023-24", "power")], ipcc[("FY2023-24", "power")] - captive)
        self.assertEqual(econ[("FY2023-24", "railways")], ipcc[("FY2023-24", "railways")])
        self.assertNotIn(("FY2023-24", "industry"), econ)
        self.assertNotIn(("FY2023-24", "ippu"), econ)

    def test_the_view_names_its_limitation(self):
        _, out = self._cells("economic_sector")
        ids = [l["id"] for l in out["limitations_hit"]]
        self.assertIn("economic_sector_view", ids)
        # the economic view is an expression over the reporting axis and inherits its limitation
        self.assertIn("reporting_sector_view", ids)


if __name__ == "__main__":
    unittest.main()
