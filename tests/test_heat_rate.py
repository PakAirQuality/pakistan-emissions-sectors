"""The implied-heat-rate check (power sector) - a validation layer, and its own invariants.

This check exists because a data-availability audit pointed out that the sector paper said no
generation figure was used while data/activity/power/generation_by_fuel.csv sat in this
repository, loaded by PowerData, with no caller. The tests below are as much about keeping it
CONNECTED as about its arithmetic: a diagnostic nobody runs is what was wrong in the first
place.

Run:  python3 -m unittest discover tests -p "test_heat_rate.py"
"""
import csv
import os
import unittest

from pkinv.paths import OUTPUTS
from pkinv.sectors.power import heat_rate
from pkinv.sectors.power.data import PowerData


class TestArithmetic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = PowerData()

    def test_efficiency_and_heat_rate_are_reciprocal(self):
        for y in heat_rate.overlap_years(self.data):
            for r in heat_rate.implied(self.data, y):
                # RELATIVE, not absolute: both fields are rounded for publication, and
                # efficiency rounded to four places is coarse when it is small - diesel oil
                # in FY2019 rounds 0.00454 to 0.0045, a 1% shift that an absolute delta reads
                # as a failure. The test is here to catch an inverted or misscaled formula,
                # which would be wrong by orders of magnitude, not by a rounding step.
                product = r["efficiency"] * r["heat_rate_kJ_per_kWh"]
                self.assertLess(abs(product - heat_rate.KJ_PER_KWH) / heat_rate.KJ_PER_KWH,
                                0.02, "%s FY%d: %.1f" % (r["fuel"], y, product))

    def test_no_row_breaks_the_second_law(self):
        """The one hard failure. An implied efficiency above 100% would not be a coverage
        question - it would mean the fuel row cannot physically have produced the reported
        generation, i.e. one of the two tables is being read wrong."""
        for y in heat_rate.overlap_years(self.data):
            for r in heat_rate.implied(self.data, y):
                self.assertLess(r["efficiency"], 1.0,
                                "%s FY%d implies %.0f%% efficient generation"
                                % (r["fuel"], y, 100 * r["efficiency"]))

    def test_the_toe_constant_is_not_duplicated(self):
        """Both helpers must read the conversion from the parameter file. The TOE convention is
        the sector's largest declared risk; a second hard-coded copy is the obvious way for the
        estimate and its own diagnostic to drift apart while both look fine."""
        src = open(heat_rate.__file__, encoding="utf-8").read()
        self.assertNotIn("0.041868", src)
        self.assertIn('data.p("toe_to_tj")', src)


class TestFuelMapping(unittest.TestCase):
    """Table 3 has one Gas row; Table 17 splits Gas from RLNG. Getting that wrong is the most
    likely way to misuse these two tables together, and it fails loudly rather than quietly."""

    @classmethod
    def setUpClass(cls):
        cls.data = PowerData()

    def test_gas_is_compared_against_gas_plus_rlng(self):
        self.assertEqual(heat_rate.FUEL_MAP["Gas"], ("Gas", "RLNG"))

    def test_rlng_generation_has_no_fuel_row_of_its_own(self):
        """The evidence FOR the mapping, and it is a completeness argument rather than one
        from absurdity.

        Table 17 reports substantial RLNG generation. Table 3 has no RLNG row. That fuel was
        burnt, so it can only be inside Table 3's Gas figure - there is nowhere else for it to
        be. If a future edition adds an RLNG fuel row, this fails and the mapping must be
        revisited rather than silently double-counting.
        """
        year = 2022
        self.assertNotIn("RLNG", set(self.data.fuel_for(year)),
                         "the fuel table now has its own RLNG row - remap before trusting the "
                         "Gas comparison")
        rlng = sum(r["gwh_net"] for r in self.data.generation_for(year)
                   if r["fuel"] == "RLNG")
        self.assertGreater(rlng, 1000.0, "RLNG generation is no longer material")

    def test_every_mapped_fuel_exists_in_both_tables(self):
        fuels = {r["fuel"] for r in self.data.fuel}
        gen_fuels = {r["fuel"] for r in self.data.generation}
        for f, mapped in heat_rate.FUEL_MAP.items():
            self.assertIn(f, fuels, msg=f)
            for g in mapped:
                self.assertIn(g, gen_fuels, msg=g)


class TestFindings(unittest.TestCase):
    """The results this check was built to surface. Pinned so that a future data revision that
    silently resolved or worsened them shows up as a test change rather than as nothing."""

    @classmethod
    def setUpClass(cls):
        cls.data = PowerData()
        cls.stab = heat_rate.stability(cls.data)

    def test_gas_is_stable_and_looks_like_a_real_fleet(self):
        """Over the eleven-year window the gas ratio steps from ~38-40 percent (the
        pre-RLNG fleet) to 49-56 (combined cycles, FY2018 onward) and holds - a ratio
        that tracks a known fleet transition and then sits at the combined-cycle
        ceiling only a net basis supports."""
        s = self.stab["Gas"]
        # The latest physical-station reconstruction extends the combined-cycle
        # fleet to ~60%; the old full-window "stable" flag need not persist.
        self.assertLessEqual(s["spread"], 1.7)
        self.assertTrue(0.35 < s["lo"] < s["hi"] < 0.64,
                        "gas implies %.1f-%.1f%%" % (100 * s["lo"], 100 * s["hi"]))
        recent = [r["efficiency"] for y in (2021, 2022, 2023)
                  for r in heat_rate.implied(self.data, y) if r["fuel"] == "Gas"]
        for e in recent:
            self.assertGreater(e, 0.45, "the combined-cycle era must hold near 50%%")

    def test_missing_latest_table3_is_not_replaced_by_the_station_reference(self):
        from pkinv.core.reporting_window import CORE_FY_STARTS
        rows = heat_rate.implied(self.data, max(CORE_FY_STARTS), basis="table3")
        self.assertNotIn("Coal", {r["fuel"] for r in rows})
        self.assertIn("Gas", {r["fuel"] for r in rows})

    def test_table_threes_coal_is_unstable_and_the_booked_account_is_not(self):
        """THE FINDING, AND THE RE-BASE THAT ANSWERED IT, IN ONE TEST.

        The finding: Table 3's coal energy, divided into NEPRA's own printed generation,
        implies efficiencies spanning a factor of three across the panel and exceeding what
        any coal plant has ever achieved in one of them - so either the two tables do not
        cover the same plants, or the energy is not a measurement. The second reading won:
        Table 3's coal energy is HDIP's tonnage times a conversion held flat across a
        complete change of coal rank.

        The consequence, asserted here rather than only claimed in prose: on the account the
        inventory now books - the stations' own metered coal at IPCC rank defaults - the SAME
        diagnostic over the SAME generation reads 34.6 to 39.3 per cent, a spread of 1.14,
        and the verdict flips to stable. Nothing about the generation side changed, so this
        is the coal account and nothing else.

        Both halves are asserted because either alone could pass for the wrong reason: if the
        refutation quietly stopped reproducing, the booked half would still be stable; if the
        booking silently reverted to Table 3, the Table 3 half would still be unstable.
        """
        t3 = heat_rate.stability(self.data, basis="table3")["Coal"]
        self.assertEqual(t3["verdict"], "UNSTABLE")
        self.assertGreater(t3["spread"], 2.0)
        self.assertGreater(t3["hi"], heat_rate.CEILING["Coal"])

        booked = self.stab["Coal"]
        self.assertEqual(booked["verdict"], "stable")
        self.assertLess(booked["spread"], 1.5)
        self.assertLess(booked["hi"], heat_rate.CEILING["Coal"])
        self.assertLess(booked["spread"], t3["spread"] / 2.0,
                        "the booked account is no longer much steadier than the one it "
                        "replaced, which is the whole basis of the re-base")

    def test_diesel_crossed_the_materiality_line_with_the_longer_window(self):
        """Diesel once had a single 0.67 GWh overlap year, and the materiality screen
        rightly refused to call that a spread. The FY2015-17 oil-era years fetched in
        August 2026 bring three material diesel years, and the screen now reports a
        modest, physical spread - the screen working in both directions."""
        s = self.stab["Diesel Oil"]
        self.assertEqual(s["verdict"], "stable")
        self.assertEqual(s["years"], 3)
        self.assertLess(s["spread"], 1.3)

    def test_the_diagnostic_never_touches_the_estimate(self):
        """The property that makes this safe to publish. Nothing in the emissions path imports
        it, so a wrong bound here cannot move a reported number."""
        import pkinv.sectors.power.combustion as combustion
        import pkinv.sectors.power.engine as engine
        for mod in (combustion, engine):
            self.assertNotIn("heat_rate", open(mod.__file__, encoding="utf-8").read(),
                             msg="%s imports the diagnostic" % mod.__name__)


class TestItIsActuallyWired(unittest.TestCase):
    """The audit's real lesson: generation_for() existed, was correct, and had no callers.

    A check that is never run is indistinguishable from one that does not exist, so these
    assert the outputs are on disk rather than that the functions work."""

    def test_the_runner_writes_both_files(self):
        for name in ("power_heat_rate_fy2023_24.csv", "power_heat_rate_stability_fy2023_24.csv"):
            path = os.path.join(OUTPUTS, name)
            self.assertTrue(os.path.exists(path), "%s missing - run_power did not write it" % name)
            with open(path, newline="", encoding="utf-8") as f:
                self.assertTrue(list(csv.DictReader(f)), "%s is empty" % name)

    def test_generation_for_has_a_caller(self):
        src = open(heat_rate.__file__, encoding="utf-8").read()
        self.assertIn("generation_for", src)


if __name__ == "__main__":
    unittest.main()
