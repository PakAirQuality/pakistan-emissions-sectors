"""The Tier 2 service split: a decomposition, never a second estimate.

The EMEP chapter's own instruction - component estimates 'should be scaled to the national
fuel statistic' - is the sector's reconciliation invariant, so the first test is exact
equality with the control. The rest pin what the split rests on: published train-km for the
line-haul division, a declared (never silent) assumption for shunting, and railcars NO.

Run:  python3 -m unittest discover tests -p "test_railways_tier2.py"
"""
import unittest

from pkinv.sectors.railways import tier2, traction
from pkinv.sectors.railways.data import RailwaysData


class TestReconciliation(unittest.TestCase):
    def test_the_split_reproduces_the_control_exactly(self):
        data = RailwaysData()
        s = tier2.split(data)
        self.assertEqual(round(sum(s.values()), 9),
                         round(traction.diesel_kt(data), 9))

    def test_the_split_is_a_decomposition_for_every_year_with_service_stats(self):
        data = RailwaysData()
        for year in (2024, 2025):
            s = tier2.split(data, year)
            self.assertEqual(round(sum(s.values()), 9),
                             round(traction.diesel_kt(data, year), 9))


class TestBasis(unittest.TestCase):
    def test_rates_and_share_come_from_params_not_literals(self):
        data = RailwaysData()
        self.assertEqual(data.p("emep_rate_line_haul_kg_per_h"), 219.0)
        self.assertEqual(data.p("emep_rate_shunting_kg_per_h"), 90.9)
        self.assertIn("Table 3-5", data.ps("emep_rate_line_haul_kg_per_h"))
        self.assertIn("ASSUMED", data.ps("shunting_fuel_share"))
        with open(tier2.__file__, encoding="utf-8") as f:
            source = f.read().replace(tier2.__doc__, "")
        for literal in ("219", "90.9", "53.6", "0.05"):
            self.assertNotIn(literal, source,
                             "rate %s appears as a literal in tier2.py" % literal)

    def test_shares_are_sane(self):
        data = RailwaysData()
        s = tier2.split(data)
        control = traction.diesel_kt(data)
        self.assertGreater(s["line_haul_passenger"], s["line_haul_freight"])
        self.assertLess(s["shunting"] / control, 0.15)
        self.assertGreater((s["line_haul_passenger"] + s["line_haul_freight"]) / control,
                           0.85)

    def test_railcars_are_not_occurring(self):
        stats = tier2.service_stats(2024)
        self.assertEqual(float(stats["railcar"]["value"]), 0.0)
        self.assertNotIn("railcar", tier2.split(RailwaysData()))


class TestAirDiagnostic(unittest.TestCase):
    def test_duty_cycle_moves_pollutants_in_both_directions(self):
        """The reason the diagnostic exists: a nearly-all-line-haul fleet pushes NOx and CO
        above the Tier 1 fleet average and PM below it. If these inequalities ever flip,
        the factor rows have been edited and the paper's discussion is stale."""
        diag = {r["pollutant"]: r for r in tier2.air_diagnostic(RailwaysData())}
        self.assertGreater(diag["NOx"]["ratio_t2_over_t1"], 1.1)
        self.assertGreater(diag["CO"]["ratio_t2_over_t1"], 1.3)
        self.assertLess(diag["PM2.5"]["ratio_t2_over_t1"], 0.95)

    def test_the_diagnostic_never_replaces_tier1(self):
        """The reported air CSV must stay Tier 1: the Tier 2 categories may appear only in
        the diagnostic output."""
        import csv
        import os
        path = os.path.join(os.path.dirname(__file__), "..", "outputs",
                            "railways_air_pollutants_2024.csv")
        with open(path, newline="", encoding="utf-8") as f:
            sources = {r["emep_source"] for r in csv.DictReader(f)}
        self.assertFalse([s for s in sources if "Table 3-2" in s or "Table 3-3" in s],
                         "Tier 2 factors leaked into the reported air inventory")


if __name__ == "__main__":
    unittest.main()
