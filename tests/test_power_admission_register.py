"""The oil- and diesel-fired power SO2 admission register.

This is a COVERAGE REPAIR, and the things that can go wrong with one are specific. The register
turns sources the panel typed `NE` into sources it estimates, so every guard here is about the
estimate being smaller than the evidence rather than larger than it.

FOUR FAILURE MODES, one section each.

ONE, DOUBLE COUNTING. The register reads two sources that name the same stations differently -
the NEPRA fuel ledger says "Hub", the monthly generation panel says "Hub Power" - and the first
build of this file unioned the two name spaces. It priced several stations twice and exceeded
the national furnace-oil supply by up to 50 percent in every ledger year. Nothing in the
arithmetic objected; the only thing that caught it was asking whether a fleet can burn more fuel
than the country delivered. That question is now asked on every run, and asserted here.

TWO, A FACTOR THAT DOES NOT FIT THE EQUIPMENT. AP-42 Section 1.3's 157 lb/kgal-per-%S names
"boilers, all sizes", and rather more than half of this fleet is not boilers: nine of the
furnace-oil stations are reciprocating engines and every diesel burner is a gas turbine. A
boiler's ash retention is not available to either, so those take Sections 3.4 and 3.1, which
state that conversion is complete. A row whose factor does not match its own station type is a
defect even though the numbers look reasonable.

THREE, AN ASSUMPTION PRESENTED AS A FINDING. No SO2 removal is credited to any row. That is a
declared default and not a measurement: AP-42 Section 1.3 documents oil-fired scrubbing at 90 to
95 percent removal, so the absence of a control record in our register is not evidence of absent
equipment on these plants. Every admitted row must say which it is.

FOUR, A COVERAGE SLOPE MISREAD AS A TREND. The ledger covers FY2019-20 onward and the early
years are reconstructed from generation and heat rates. If the reconstruction were systematically
weaker, admitting power would add mass to the late years and less to the early ones, flattening a
real decline with an artefact - the exact defect this whole programme exists to remove. So the
reconstruction is MEASURED against the metered ledger on the sixty plant-years where both exist.
"""

from pkinv.assets import asset_path
import os
import statistics
import sys
import unittest
from collections import defaultdict

from _support import DATA, data_rows, scripts_on_path

REGISTER = asset_path(DATA, "activity", "power", "power_so2_admission.csv")


def rows():
    return data_rows(os.path.join("activity", "power", "power_so2_admission.csv"))


class TestNoStationIsPricedTwice(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = rows()
        cls.priced = [r for r in cls.rows if r["disposition"] == "provisional_estimate"]

    def test_one_row_per_station_fuel_and_period(self):
        seen = defaultdict(int)
        for r in self.rows:
            seen[(r["plant"], r["fuel"], r["period_id"])] += 1
        repeats = {k: n for k, n in seen.items() if n > 1}
        self.assertEqual(repeats, {}, "the same source-year appears more than once")

    def test_no_year_burns_more_fuel_than_the_country_supplied(self):
        """THE GUARD THAT CAUGHT THE ORIGINAL DEFECT.

        The national furnace-oil row covers the CPPA side only - the boundary audit behind
        data/power_params.csv activity_uncert_fo establishes that - so K-Electric's mass is
        excluded from the comparison rather than being measured against a total that never
        contained it. On the CPPA side the register must stay UNDER the national supply, and
        the remainder it leaves is the population the screening keeps.
        """
        scripts_on_path()
        import build_power_admission_register as reg
        for period, cppa, _ke, national, ratio in reg.national_control(self.priced):
            self.assertGreater(national, 0, period)
            self.assertLessEqual(ratio, 1.0,
                                 "%s: the register's CPPA furnace oil is %.1f kt against a "
                                 "national supply of %.1f kt. A fleet cannot burn more than was "
                                 "delivered; this is what double counting looks like."
                                 % (period, cppa, national))
            self.assertGreater(ratio, 0.4,
                               "%s: CPPA coverage fell to %.3f. The register is not double "
                               "counting, it is losing stations - check the name join."
                               % (period, ratio))

    def test_the_panel_and_the_ledger_speak_one_vocabulary(self):
        """The join key itself, asserted rather than trusted.

        `station()` is what collapses the two name spaces onto NEPRA Table 5's spelling. If it
        ever stops resolving a station, that station silently becomes two.
        """
        scripts_on_path()
        import build_power_admission_register as reg
        names = reg.canonical_names()
        for ledger_name, table5 in (("Hub", "Hub Power"), ("Nishat", "Nishat Power"),
                                    ("Atlas", "Atlas Power"), ("Lal Pir", "Lal Pir Power"),
                                    ("Saba", "Saba Power"), ("Pak Gen.", "Pak Gen. Power")):
            self.assertEqual(reg.station(ledger_name, names), table5)
        # and the panel's own spellings reach the same place
        for panel_name in ("HUBCO", "AES Lal Pir"):
            self.assertIn(reg.station(panel_name, names), ("Hub Power", "Lal Pir Power"))


class TestTheFactorMatchesTheEquipment(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.priced = [r for r in rows() if r["disposition"] == "provisional_estimate"]

    def test_the_station_type_decides_the_class(self):
        from pkinv.sectors.power.point_sources import equipment_class
        for station_type, expected in (("ST", "oil_fired_boiler"), ("STs", "oil_fired_boiler"),
                                       ("DEs+ST", "reciprocating_engine"),
                                       ("DE+ST", "reciprocating_engine"),
                                       ("DGs+ST", "reciprocating_engine"),
                                       ("REs+ST", "reciprocating_engine"),
                                       ("GTs", "gas_turbine"),
                                       ("GTs+ST", "gas_turbine"),
                                       ("GTs+CCPPs", "gas_turbine"),
                                       ("GTs+HRSGs+ST", "gas_turbine"),
                                       ("", None)):
            self.assertEqual(equipment_class(station_type), expected, station_type)

    def test_only_a_boiler_is_credited_with_ash_retention(self):
        """A retention above zero on an engine or a turbine contradicts both AP-42 sections."""
        for r in self.priced:
            retention = float(r["retention_frac"])
            if r["equipment_class"] == "oil_fired_boiler":
                self.assertAlmostEqual(retention, 0.050480, places=5, msg=r["plant"])
                self.assertEqual(r["factor_id"], "ap42_1.3_no6_so2_157S")
            else:
                self.assertEqual(retention, 0.0,
                                 "%s is a %s; AP-42 3.4 and 3.1 both state that conversion is "
                                 "complete, so no retention may be credited"
                                 % (r["plant"], r["equipment_class"]))

    def test_every_diesel_row_is_a_turbine_and_says_which_section_covers_it(self):
        hsd = [r for r in self.priced if r["fuel"] == "HSD"]
        self.assertTrue(hsd)
        for r in hsd:
            self.assertEqual(r["equipment_class"], "gas_turbine", r["plant"])
            self.assertIn("3.1", r["factor_basis"])

    def test_a_station_with_no_readable_type_is_never_priced(self):
        for r in rows():
            if not r["equipment_class"]:
                self.assertEqual(r["disposition"], "scenario_only", r["plant"])
                self.assertEqual(r["so2_Gg"], "")


class TestEveryAssumptionIsDeclared(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.priced = [r for r in rows() if r["disposition"] == "provisional_estimate"]

    def test_the_control_default_is_never_dressed_up_as_a_finding(self):
        for r in self.priced:
            self.assertEqual(r["control_type"], "none credited", r["plant"])
            self.assertIn("DECLARED DEFAULT, NOT A FINDING", r["control_basis"])
            self.assertIn("90-95", r["control_basis"],
                          "the basis must carry the removal efficiency that an installed "
                          "control would achieve, or the reader cannot size the assumption")

    def test_every_priced_row_carries_a_dated_sulfur_evidence_id(self):
        for r in self.priced:
            self.assertTrue(r["sulfur_evidence_id"], r["plant"])
            self.assertTrue(r["sulfur_basis"], r["plant"])
            lo, mid, hi = (float(r["s_pct_lo"]), float(r["s_pct_central"]), float(r["s_pct_hi"]))
            self.assertLessEqual(lo, mid)
            self.assertLessEqual(mid, hi)

    def test_furnace_oil_takes_the_one_row_that_prices_this_fuel(self):
        """THIS TEST ASSERTED THE OPPOSITE UNTIL rc63, AND THE REVERSAL IS THE POINT.

        It read `test_furnace_oil_uses_the_power_row_and_never_industrys_ceiling`, and its reason
        was: "fo_hsfo_grade_mix is 3.0 percent on basis `regulatory_max`. It is a CEILING, it names
        industrial classes in applies_to, and pricing a power station at it overstates that station
        by 2.3 times against the power module's own held fuel quality."

        The objection was sound in shape and wrong in fact. It compared the industry row against
        `power_rfo_spec_range`, whose 1.3229 percent was the unweighted geometric middle of a
        0.5-3.5 specification span - a midpoint, not a measurement, and the "held fuel quality" it
        invoked was that same span. Item 3 transcribed the furnace-oil IMPORT GRADE SPLIT from a
        document the repository already held (PBS Compendium Table B-10, now
        data/activity/industry/furnace_oil_grade_mix.csv): the national pool is 85.3-100 percent
        HIGH-sulphur grade across the four panel years it covers. A pool that is almost all HSFO
        sits near the top of that span, not in the middle of it, so the midpoint understated the
        fleet rather than the ceiling overstating it.

        One national fuel cannot carry two centrals. `power_rfo_spec_range` is retired - kept, with
        its reasoning preserved, but naming no class and resolving for no year - and the power RFO
        classes now cite the same row as industry. Equipment still changes the RETENTION, which is
        per class and untouched: the boiler keeps AP-42 1.3's 5.05 percent ash retention, the
        engine and turbine keep none.

        What this test now guards is the merge: RFO must price from the single live furnace-oil
        row, and must never quietly reacquire a second one."""
        self.assertTrue(any(r["fuel"] == "RFO" for r in self.priced))
        for r in self.priced:
            if r["fuel"] == "RFO":
                self.assertEqual(r["sulfur_evidence_id"], "fo_hsfo_grade_mix", r["plant"])
                self.assertNotEqual(r["sulfur_evidence_id"], "power_rfo_spec_range",
                                    "%s reacquired the retired row" % r["plant"])

    def test_diesel_takes_the_regime_its_own_year_falls_in(self):
        for r in self.priced:
            if r["fuel"] != "HSD":
                continue
            expected = ("hsd_pre_euro2" if int(r["fiscal_start_year"]) + 1 <= 2017
                        else "hsd_euro2_onward")
            self.assertEqual(r["sulfur_evidence_id"], expected, r["period_id"])

    def test_the_band_travels_with_every_central(self):
        for r in self.priced:
            lo, mid, hi = float(r["so2_Gg_lo"]), float(r["so2_Gg"]), float(r["so2_Gg_hi"])
            self.assertLessEqual(lo, mid)
            self.assertLessEqual(mid, hi)

    def test_an_absence_is_typed_and_never_a_zero(self):
        for r in rows():
            if r["disposition"] == "scenario_only":
                self.assertEqual(r["so2_Gg"], "", r["plant"])
                self.assertTrue(r["disposition_reason"].strip(), r["plant"])

    def test_a_weaker_activity_route_says_so_on_the_row(self):
        for r in self.priced:
            self.assertIn(r["activity_route"], ("ledger_quantity", "generation_x_heat_rate"))
            if r["activity_route"] == "generation_x_heat_rate":
                self.assertTrue(r["heat_rate_basis"].strip(), r["plant"])
                self.assertTrue(r["heat_rate_kJ_per_kWh"], r["plant"])
            else:
                self.assertIn("read directly", r["activity_basis"])


class TestTheBackcastIsMeasuredAgainstMeteredFuel(unittest.TestCase):
    """The reconstruction used for FY2015-16..FY2018-19, checked where it can be checked.

    The ledger and the generation panel overlap on sixty furnace-oil plant-years. Running the
    reconstruction on those and comparing it with the metered quantity is the only direct
    evidence that the four backcast years are not systematically low or high - and a systematic
    bias there would show up as a slope in the admitted series rather than as an error anyone
    would notice. The median ratio is 1.011.
    """

    @classmethod
    def setUpClass(cls):
        scripts_on_path()
        import build_power_admission_register as reg
        cls.reg = reg
        names = reg.canonical_names()
        gen, hr, fleet = (reg.generation_by_fuel(names), reg.plant_heat_rates(names),
                          reg.national_rfo_heat_rates())
        cls.ratios = []
        for r in rows():
            if (r["disposition"] != "provisional_estimate" or r["fuel"] != "RFO"
                    or r["activity_route"] != "ledger_quantity"):
                continue
            gwh, months = gen.get((r["plant"], "RFO", r["period_id"]), (0.0, {}))
            if not months or any(v != 12 for v in months.values()) or gwh <= 0:
                continue
            start = int(r["fiscal_start_year"])
            rate = hr.get((r["plant"], start)) or (fleet.get(start) or (None,))[0]
            if not rate:
                continue
            reconstructed = gwh * 1e6 * rate / 1e9 / reg.RFO_NCV_TJ_PER_GG
            cls.ratios.append(reconstructed / float(r["fuel_mass_kt"]))

    def test_there_are_enough_overlapping_years_to_conclude_anything(self):
        self.assertGreaterEqual(len(self.ratios), 55)

    def test_the_reconstruction_reproduces_the_metered_quantity(self):
        median = statistics.median(self.ratios)
        self.assertAlmostEqual(median, 1.011, delta=0.03,
                               msg="the generation route no longer reproduces metered fuel; the "
                                   "four backcast years rest on this agreement")
        self.assertAlmostEqual(statistics.mean(self.ratios), 1.012, delta=0.05)

    def test_it_is_not_systematically_low_or_high(self):
        """A bias here becomes a slope in the admitted series, which is the artefact this
        programme exists to remove rather than to introduce."""
        high = sum(1 for x in self.ratios if x > 1.10)
        low = sum(1 for x in self.ratios if x < 0.90)
        self.assertLess(high + low, 0.15 * len(self.ratios),
                        "%d of %d plant-years miss the metered quantity by more than a tenth"
                        % (high + low, len(self.ratios)))


class TestTheRegisterIsDeterministicAndPlaced(unittest.TestCase):

    def test_check_mode_says_the_file_is_current(self):
        scripts_on_path()
        import build_power_admission_register as reg
        built = reg.build()
        on_disk = rows()
        self.assertEqual(len(built), len(on_disk))
        for a, b in zip(built, on_disk):
            self.assertEqual(str(a["so2_Gg"]), b["so2_Gg"])
            self.assertEqual(a["plant"], b["plant"])

    def test_every_admitted_row_carries_a_district(self):
        """The whole point is a district panel, and an unplaced row cannot enter one. If a
        station ever loses its district this must fail loudly rather than quietly drop it."""
        for r in rows():
            if r["disposition"] == "provisional_estimate":
                self.assertTrue(r["adm2_id"], "%s has no district" % r["plant"])
                self.assertNotIn("NO RESOLVED DISTRICT", r["geography_basis"])

    def test_nothing_here_has_entered_a_total_yet(self):
        """This register is an input. Until the engine admits it, power SO2 stays NE, and a
        test that assumes otherwise would hide a half-finished migration."""
        power = [r for r in data_rows(os.path.join("..", "outputs",
                                                   "pakemis_air_coverage_matrix.csv"))
                 if r.get("sector_id") == "power" and r.get("pollutant") == "SO2"]
        self.assertEqual(len(power), 9)


if __name__ == "__main__":
    unittest.main()
