"""The plant-side energy closure, and the evidence classes it must keep apart.

The power sector's largest declared risk is that NEPRA's TOE convention may be gross rather
than net calorific - worth 10 percent on gas - and the paper has been saying the answer needs
the HDIP Energy Yearbook. It does not: some plant fuel is metered in MMBTU, which is already
energy, so those plants can be asked what efficiency they imply with no calorific assumption at
all, and efficiency is bounded by physics.

These tests exist mostly to stop the three evidence classes being pooled. An exact leg, a leg
resting on an unpinned heating value, and a leg resting on IPCC defaults for a fuel as unusual
as Thar lignite are not the same kind of number, and presenting them as one would waste the
only assumption-free measurement in the sector.

Run:  python3 -m unittest discover tests -p "test_plant_closure.py"
"""
import unittest

from pkinv.sectors.power import plant_ledger
from pkinv.sectors.power.data import PowerData


class TestTheAssumptionFreeLeg(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = PowerData()

    def test_mmbtu_plants_imply_a_real_combined_cycle_efficiency(self):
        """THE RESULT. 48.7 percent net is what a modern CCGT fleet achieves. Read as gross the
        same fuel would imply 54.1, at the ceiling of any fleet average - so the plant meters
        behave as net, which is evidence on the TOE convention arrived at without consulting
        the TOE table."""
        eff = plant_ledger.implied_efficiency(self.data)
        self.assertTrue(0.44 < eff < 0.53, "MMBTU plants imply %.1f%%" % (100 * eff))

    def test_it_agrees_with_the_toe_side_diagnostic(self):
        """Two independent routes: this one from plant meters, the heat-rate check from the
        national fuel table. Both land near 49 percent. Agreement is the point - a gross-basis
        TOE table would have put the two several points apart."""
        from pkinv.sectors.power import heat_rate
        gas = heat_rate.stability(self.data)["Gas"]
        eff = plant_ledger.implied_efficiency(self.data)
        self.assertTrue(gas["lo"] <= eff <= gas["hi"],
                        "plant %.3f outside the TOE-side band %.3f-%.3f"
                        % (eff, gas["lo"], gas["hi"]))

    def test_the_exact_leg_uses_no_heating_value(self):
        """If the exact leg ever moved with the heating value it would no longer be exact."""
        a = plant_ledger.legs(self.data, hhv_btu=900)
        b = plant_ledger.legs(self.data, hhv_btu=1000)
        self.assertEqual(a["exact_TJ"], b["exact_TJ"])
        self.assertNotEqual(a["assumed_TJ"], b["assumed_TJ"])


class TestEvidenceClassesStayApart(unittest.TestCase):
    def test_all_three_legs_are_material(self):
        """If any leg were negligible the separation would be decoration. Each is a real share
        of fleet energy, so pooling them would genuinely mislead."""
        L = plant_ledger.legs(PowerData())
        total = L["exact_TJ"] + L["assumed_TJ"] + L["default_TJ"]
        for key in ("exact_TJ", "assumed_TJ", "default_TJ"):
            self.assertGreater(L[key] / total, 0.10, "%s is only %.1f%% of energy"
                               % (key, 100 * L[key] / total))

    def test_default_ncvs_never_reach_the_emissions_path(self):
        """IPCC defaults for Thar lignite are the weakest evidence here. They are fine for a
        diagnostic and must not become activity data.

        The check is for a real dependency - an import or an attribute access - not for the
        NAME. It used to be a bare substring search, and that forbade the emissions path
        from even explaining why it keeps the closure at arm's length: when the per-year
        coal blend was moved into data/power_coal_blend_by_year.csv precisely so this
        separation would hold, the docstring saying so tripped the guard. A rule that
        punishes writing down its own reason is a rule that will eventually be deleted by
        someone who cannot see the point of it."""
        import re
        import pkinv.sectors.power.combustion as combustion
        import pkinv.sectors.power.engine as engine
        dependency = re.compile(r"(?:^\s*(?:from[\w. ]*\s)?import[\w., ]*\bplant_ledger\b"
                                r"|\bplant_ledger\s*\.)", re.M)
        for mod in (combustion, engine):
            source = open(mod.__file__, encoding="utf-8").read()
            self.assertIsNone(dependency.search(source),
                              msg="%s depends on the closure" % mod.__name__)


class TestWhatDoesNotClose(unittest.TestCase):
    """Reported as a residual rather than absorbed into an adjustment."""

    def test_plant_gas_exceeds_the_national_row(self):
        c = plant_ledger.gas_closure(PowerData())
        self.assertGreater(c["ratio"], 1.0)
        self.assertLess(c["ratio"], 1.2, "the gap has grown - re-examine before quoting it")

    def test_the_reconciling_heating_value_is_implausible(self):
        """Equality would need about 760 Btu/scf, below anything pipeline gas reaches. So the
        gap is NOT explained by the heating value, and calling it one would be fitting an
        assumption to a discrepancy."""
        c = plant_ledger.gas_closure(PowerData())
        self.assertLess(c["implied_hhv_btu_per_scf"], 900,
                        "the gap is now explicable by heating value alone - restate the claim")


class TestCoalBlend(unittest.TestCase):
    """The lignite share, read from the plants instead of inferred from an older fleet."""

    @classmethod
    def setUpClass(cls):
        cls.data = PowerData()
        cls.b = plant_ledger.coal_blend(cls.data)

    def test_the_parameter_is_the_midpoint_of_the_lucky_bounds(self):
        """0.79 is not a judgement, it is the midpoint of the two readings of the one plant
        whose name states no origin. If the ledger moves, the parameter must move with it or
        this fails - which is the point."""
        mid = self.b["gen_weighted_mid"]
        self.assertAlmostEqual(self.data.p("coal_lignite_share"), mid, delta=0.005,
                               msg="parameter %.3f vs ledger midpoint %.3f"
                                   % (self.data.p("coal_lignite_share"), mid))

    def test_the_two_routes_overlap(self):
        """Generation weighting assumes comparable efficiencies; mass x NCV assumes IPCC rank
        defaults. They rest on different assumptions, so their overlap is what makes the range
        defensible. If they ever separate, the blend is not decidable from the ledger alone."""
        self.assertLess(max(self.b["gen_weighted_lo"], self.b["ncv_route_lo"]),
                        min(self.b["gen_weighted_hi"], self.b["ncv_route_hi"]))

    def test_the_residual_is_visible_and_bounded(self):
        """Lucky Electric. If the residual grows past a quarter of coal generation the bounds
        stop being informative; if it vanishes someone has assigned it and must show why."""
        r = self.b["residual_share_of_generation"]
        self.assertGreater(r, 0.0, "the residual has been assumed away")
        self.assertLess(r, 0.25)

    def test_the_uncertainty_spans_both_routes(self):
        """The 10 percent band must cover the union of the two routes around the central
        value, or the published bounds exceed the propagated uncertainty."""
        central = self.data.p("coal_lignite_share")
        u = self.data.pu("coal_lignite_share") / 100.0
        lo = min(self.b["gen_weighted_lo"], self.b["ncv_route_lo"])
        hi = max(self.b["gen_weighted_hi"], self.b["ncv_route_hi"])
        self.assertLessEqual(central * (1 - u), lo + 1e-9)
        self.assertGreaterEqual(central * (1 + u), hi - 1e-9)


class TestCoalNCVDiagnostic(unittest.TestCase):
    """The control-total question. Published, never acted on."""

    def test_the_discrepancy_is_large_and_pinned(self):
        """Table 3's coal energy over the ledger's coal mass is bituminous-grade NCV for a
        fleet over ninety percent lignite by mass. Pinned so a data revision that silently
        resolved or worsened it shows up as a test change."""
        n = plant_ledger.coal_ncv_diagnostic(PowerData())
        self.assertGreater(n["ratio"], 1.5)
        self.assertLess(n["ratio"], 2.5)

    def test_it_does_not_touch_the_estimate(self):
        """Acting on it would cut coal CO2 by a third on a diagnostic's authority. The
        emissions path must not import any of this."""
        import pkinv.sectors.power.combustion as combustion
        self.assertNotIn("coal_ncv", open(combustion.__file__, encoding="utf-8").read())


if __name__ == "__main__":
    unittest.main()
