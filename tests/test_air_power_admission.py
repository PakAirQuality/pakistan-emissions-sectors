"""The power SO2 admission, end to end: register -> panel -> bridge.

tests/test_power_admission_register.py guards the register as a document - its arithmetic, its
dispositions, its declared assumptions. This file guards what happens when the engine consumes
it, which is a different set of risks. A coverage repair moves a published series while every
input stays the same, so the things that can go wrong are all about the seam:

  the increment does not equal its sources        the panel gained mass the register cannot account for
  the screening was not narrowed                  the same fuel is both estimated and screened
  a sector that should not have moved, moved      this is a power-only patch and must stay one
  the greenhouse-gas layer moved                  the air panel is one-directional; a pin that
                                                  shifts means this change reached the wrong layer
"""
import os
import unittest
from collections import defaultdict

from _support import DATA, OUTPUTS, data_rows, rows, scripts_on_path
from pkinv.core import configurations as conf
from pkinv.core.reporting_window import CORE_FY_STARTS, CORE_SUFFIX

PERIODS = tuple("FY%d-%02d" % (y, (y + 1) % 100) for y in CORE_FY_STARTS)


def admission():
    return data_rows(os.path.join("activity", "power", "power_so2_admission.csv"))


class TestTheIncrementEqualsItsSources(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.bridge = rows("pakemis_air_power_admission_bridge.csv")
        cls.atoms = rows("pakemis_air_atomic_annual.csv")
        cls.admission = admission()

    def test_the_bridge_covers_every_period(self):
        self.assertEqual([r["period_id"] for r in self.bridge], list(PERIODS))

    def test_panel_after_minus_before_is_exactly_the_admitted_mass(self):
        """The identity the whole repair rests on. If these differ, the panel gained SO2 from
        somewhere the register cannot account for, which would be far worse than gaining none."""
        for r in self.bridge:
            self.assertAlmostEqual(
                float(r["panel_so2_after_kt"]) - float(r["panel_so2_before_kt"]),
                float(r["increment_total_kt"]), places=4,
                msg="%s: the step in the panel is not the sum of the admitted rows" % r["period_id"])

    def test_the_increment_is_the_registers_own_sum(self):
        by_period = defaultdict(float)
        for a in self.admission:
            if a["disposition"] == "provisional_estimate":
                by_period[a["period_id"]] += float(a["so2_Gg"])
        for r in self.bridge:
            self.assertAlmostEqual(float(r["increment_total_kt"]),
                                   by_period[r["period_id"]], places=5, msg=r["period_id"])

    def test_the_panel_atoms_reproduce_the_register(self):
        panel = defaultdict(float)
        for a in self.atoms:
            if a["sector_id"] == "power" and conf.canonical(a["configuration_id"]) == conf.REFERENCE:
                panel[a["period_id"]] += float(a["emissions_Gg"])
        register = defaultdict(float)
        for a in self.admission:
            if a["disposition"] == "provisional_estimate":
                register[a["period_id"]] += float(a["so2_Gg"])
        for period in PERIODS:
            self.assertAlmostEqual(panel[period], register[period], places=4, msg=period)

    def test_the_equipment_split_adds_up(self):
        """Half this mass rests on a boiler factor and half on the complete-conversion
        sections, and a reader is entitled to see which - so the split must be published and
        must reconcile."""
        for r in self.bridge:
            parts = sum(float(r[k]) for k in
                        ("increment_rfo_boiler_kt", "increment_rfo_engine_kt",
                         "increment_rfo_turbine_kt", "increment_hsd_turbine_kt"))
            self.assertAlmostEqual(parts, float(r["increment_total_kt"]), places=6, msg=r["period_id"])
        engine = sum(float(r["increment_rfo_engine_kt"]) for r in self.bridge)
        boiler = sum(float(r["increment_rfo_boiler_kt"]) for r in self.bridge)
        self.assertGreater(engine, 0.2 * (engine + boiler),
                           "the reciprocating-engine share has collapsed; the equipment rule or "
                           "the station types behind it have changed")


class TestTheRepairIsPowerOnly(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.atoms = rows("pakemis_air_atomic_annual.csv")

    def test_no_other_sector_gained_an_so2_atom_from_this(self):
        """A coverage patch that reaches another sector is not a coverage patch. The check that
        can be made from the shipped table alone: every non-power SO2 atom still anchors a
        stream of its own module, and nothing anchors the grid streams but power."""
        for a in self.atoms:
            if a["pollutant"] != "SO2" or a["sector_id"] == "power":
                continue
            self.assertNotIn("furnace-oil", a.get("source_stream_id", ""),
                             "%s anchors a grid furnace-oil stream" % a["sector_id"])

    def test_the_admission_never_reached_the_greenhouse_gas_layer(self):
        """The air panel is one-directional and the pins do not move. A power SO2 row appearing
        in a greenhouse-gas product would mean this change crossed a boundary it must not."""
        national = rows("national_all_sectors.csv")
        self.assertFalse([r for r in national if "SO2" in str(r.values())],
                         "an SO2 row reached the greenhouse-gas national table")

    def test_other_power_pollutants_are_untouched(self):
        power = [a for a in self.atoms if a["sector_id"] == "power"]
        self.assertEqual({a["pollutant"] for a in power}, {"SO2"})


class TestTheScreeningWasActuallyNarrowed(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.screening = rows("power_air_screening_%s.csv" % CORE_SUFFIX)

    def test_the_narrowed_rows_say_they_are_a_remainder(self):
        """Only where something WAS admitted that year. Diesel is not burned at grid scale
        before FY2018-19, so those rows are screened whole and correctly say nothing - a
        narrowing note on a year with no admission would be the defect, not the absence of one.
        """
        admitted = {(r["period_id"], {"RFO": "Furnace Oil", "HSD": "Diesel Oil"}[r["fuel"]])
                    for r in admission() if r["disposition"] == "provisional_estimate"}
        narrowed = [r for r in self.screening
                    if r["pollutant"] == "SO2" and (r["period_id"], r["fuel"]) in admitted]
        self.assertGreaterEqual(len(narrowed), 20)
        for r in narrowed:
            self.assertIn("REMAINDER ONLY", r["basis"],
                          "%s %s screens oil SO2 without saying it is the unadmitted remainder; "
                          "a scenario standing beside an estimate of the same fuel is a double "
                          "count waiting to be read as one" % (r["period_id"], r["fuel"]))

    def test_everything_else_is_screened_whole(self):
        for r in self.screening:
            if r["pollutant"] == "SO2" and r["fuel"] in ("Furnace Oil", "Diesel Oil"):
                continue
            self.assertNotIn("REMAINDER ONLY", r["basis"],
                             "%s %s %s was narrowed; only oil and diesel SO2 is admitted"
                             % (r["period_id"], r["fuel"], r["pollutant"]))

    def test_the_controlled_case_no_longer_claims_to_be_the_controlled_fleet(self):
        """It credits coal FGD and leaves oil removal exactly as it was, so for an oil station
        the two scenario ends coincide - which was once offered as a reason to admit oil and is
        not one. The name has to say what the scenario does."""
        from pkinv.sectors.power.air_pollutants import CONTROLLED_BASIS
        self.assertIn("COAL-CONTROL SCENARIO, OIL REMOVAL UNCHANGED", CONTROLLED_BASIS)
        self.assertIn("90 to 95 percent", CONTROLLED_BASIS)


class TestTheBridgeRegenerates(unittest.TestCase):

    def test_check_mode_says_the_shipped_bridge_is_current(self):
        scripts_on_path()
        import build_power_admission_bridge as bridge
        built = bridge.build()
        shipped = rows("pakemis_air_power_admission_bridge.csv")
        self.assertEqual(len(built), len(shipped))
        for a, b in zip(built, shipped):
            self.assertEqual(a["period_id"], b["period_id"])
            self.assertAlmostEqual(float(a["increment_total_kt"]),
                                   float(b["increment_total_kt"]), places=6)

    def test_the_admission_makes_the_national_decline_steeper_not_shallower(self):
        """Stated in the plan and worth pinning, because the opposite would be the signature of
        the coverage artefact this change exists to avoid: if the admission reached only the
        late years it would flatten a real decline. Furnace-oil generation collapsed across the
        panel, so the mass admitted to FY2015-16 is several times that admitted to FY2023-24."""
        b = {r["period_id"]: r for r in rows("pakemis_air_power_admission_bridge.csv")}
        first, last = b["FY2015-16"], b["FY2023-24"]
        before = 1.0 - float(last["panel_so2_before_kt"]) / float(first["panel_so2_before_kt"])
        after = 1.0 - float(last["panel_so2_after_kt"]) / float(first["panel_so2_after_kt"])
        self.assertGreater(after, before,
                           "admitting power made the national SO2 decline SHALLOWER (%.3f -> "
                           "%.3f), which means the admission is weighted to the late years - a "
                           "coverage slope, not a measurement" % (before, after))


if __name__ == "__main__":
    unittest.main()
