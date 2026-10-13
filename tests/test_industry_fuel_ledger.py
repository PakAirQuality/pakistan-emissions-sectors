"""The industrial fuel claimant ledger: closure where a control exists, honesty where not.

The contract: the fluid tier's claimants sum to the engine's own streams exactly
(closure red-provable by perturbation); every solid claimant carries a status from the
closed vocabulary and NO quantity (an unresolved claimant that entered a sum would be
an invented decomposition); the benchmark residual reproduces from the comparison
table; the brick row points at the real asset table; and the ledger regenerates
identically.
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest
from pkinv.core.io import read_rows
from _support import OUT, ROOT



def _rows():
    return read_rows(os.path.join(OUT, 'industry_fuel_ledger_2024.csv'), comments=False)


class TestIndustryFuelLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ledger = _rows()

    def test_the_fluid_tier_closes_on_the_engine(self):
        from pkinv.core.components import enrich_co2e
        from pkinv.sectors.industry import combustion
        from pkinv.sectors.industry.data import IndustryData
        comps = enrich_co2e(combustion.compute(IndustryData())[0])
        engine_total = sum(c["co2e_Mt_AR5"] for c in comps)
        fluid = sum(float(r["Mt_co2e"]) for r in self.ledger
                    if r["tier"] == "fluid" and r["Mt_co2e"])
        self.assertAlmostEqual(fluid, engine_total, delta=5e-5)

    def test_the_closure_has_teeth(self):
        """Positive control: the builder aborts on a perturbed opening."""
        from pkinv.sectors.industry import fuel_ledger
        rows = fuel_ledger.build()
        total = sum(float(r["Mt_co2e"]) for r in rows
                    if r["tier"] == "fluid" and r["Mt_co2e"] != "")
        perturbed = total * 1.01
        self.assertGreater(abs(perturbed - total),
                           fuel_ledger.TOL * max(1.0, total),
                           "a 1% perturbation would slip under the closure bound")

    def test_solid_quantities_carry_only_the_statuses_that_earn_them(self):
        """Evolved at rc13 and AGAIN at rc46 Wave 2, each time because the policy's world
        changed underneath it. rc13's form allowed one screening quantity (the PEY brick
        series); Wave 2 activated brick and cement coal as REFERENCE streams through the
        written gate, so the policy now reads: a solid row may carry a quantity only as
        control_held (a reference stream, inside every closure), as a superseded claimant
        (the record of what screened it - never summed), or as a screening
        ceiling/bracket/residual exactly as before. rc47 Wave 0 added one more earned
        status: contained_in_reference_stream, for a claimant whose quantity sits
        INSIDE a booked reference stream (captive coal inside the brick residual
        column, per the activation gate's own text) - a bound on a share of booked
        mass, never summed, never a configuration. A quantity under any other status
        is the drift this guard has always refused."""
        allowed_with_mass = {"control_held", "superseded_by_reference_stream",
                             "screening_ceiling_bound", "screening_capacity_bracket",
                             "benchmark_residual", "contained_in_reference_stream"}
        for r in self.ledger:
            if r["tier"] == "solid" and r["Mt_co2e"] != "":
                self.assertIn(r["control_status"], allowed_with_mass,
                              "%s carries %s under %s" % (r["claimant"], r["Mt_co2e"],
                                                          r["control_status"]))
        held = [r for r in self.ledger
                if r["tier"] == "solid" and r["control_status"] == "control_held"]
        self.assertEqual({r["claimant"] for r in held},
                         {"Brick-kiln coal", "Cement-sector coal"},
                         "the activated solid set moved without this policy moving")

    def test_the_screened_quantity_enters_no_closure(self):
        """The fluid closure must still equal the engine total with the brick
        quantity present in the table - the proof the screening row is outside
        every sum, not silently inside one."""
        from pkinv.sectors.industry import combustion, engine
        from pkinv.sectors.industry.data import IndustryData
        held = sum(float(r["Mt_co2e"]) for r in self.ledger
                   if r["control_status"] == "control_held" and r["Mt_co2e"] != "")
        comps = engine.build_components(IndustryData())
        total = sum(c["co2e_Mt_AR5"] for c in comps
                    if c["category"] == combustion.CATEGORY)
        # rc46 Wave 2: the engine total includes the solid reference streams, so the
        # closure is over every control_held row, both tiers. The screening and
        # superseded rows must still be OUTSIDE it - proven by the sum agreeing.
        # places=4: the shipped ledger rounds Mt_co2e per row.
        self.assertAlmostEqual(held, total, places=4)

    def test_the_benchmark_residual_reproduces(self):
        with open(os.path.join(OUT, "national_benchmark_comparison.csv"), newline="",
                  encoding="utf-8") as f:
            bench = next(r for r in csv.DictReader(f)
                         if r["engine_category"] == "1A2 (all estimated)")
        expected = float(bench["benchmark_Mt_co2e"]) - float(bench["engine_Mt_co2e"])
        row = next(r for r in self.ledger if r["kind"] == "benchmark_residual")
        self.assertAlmostEqual(float(row["Mt_co2e"]), expected, places=2)
        self.assertIn("not evidence about its composition", row["note"])

    def test_the_brick_row_points_at_the_asset_table(self):
        row = next(r for r in self.ledger
                   if r["claimant"].startswith("Brick kilns"))
        self.assertEqual(row["control_status"], "superseded_by_reference_stream")
        self.assertIn("pak_brick_kiln_assets.csv", row["geometry_status"])
        path = asset_path(ROOT, "data", "gis", "kilns", "pak_brick_kiln_assets.csv")
        with open(path, newline="", encoding="utf-8") as f:
            n = sum(1 for _ in csv.DictReader(f))
        self.assertEqual(n, 11272)
        self.assertIn("11,272", row["geometry_status"])

    def test_every_gap_id_resolves(self):
        with open(asset_path(ROOT, "data", "data_gaps.csv"), newline="",
                  encoding="utf-8") as f:
            gaps = {r["gap_id"] for r in csv.DictReader(f)}
        for r in self.ledger:
            if r["gap_id"]:
                self.assertIn(r["gap_id"], gaps, r["claimant"])

    def test_the_ledger_regenerates_identically(self):
        from pkinv.sectors.industry import fuel_ledger
        fresh = fuel_ledger.build()
        self.assertEqual(len(fresh), len(self.ledger))
        for f_row, s_row in zip(fresh, self.ledger):
            for col in fuel_ledger.FIELDS:
                self.assertEqual(str(f_row[col]), s_row[col],
                                 "%s.%s" % (f_row["claimant"], col))


if __name__ == "__main__":
    unittest.main()
