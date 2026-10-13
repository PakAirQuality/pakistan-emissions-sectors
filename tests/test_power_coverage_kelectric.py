"""K-Electric is a COVERAGE alternative, kept apart from coal-property alternatives.

WHY. Through rc66 the power family held four members of three different kinds and the
manuscript's abstract quoted the family's minimum and maximum as one range, from a member
whose energy is circular to an account that had been superseded, passing through K-Electric,
which is not a statement about fuel properties at all. The review asked for the three to be
separated and for the K-Electric question to be stated as what it is: whether the national
fuel statistic already contains that fuel is not established. rc67 gives every family member a
kind, prices the K-Electric system for all nine years, and forbids ranges across kinds.
"""
import csv
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.report import national_configurations as nc          # noqa: E402
from pkinv.sectors.power import engine, ke_leg                  # noqa: E402

CONFIGURATIONS = os.path.join(ROOT, "outputs", "national_configurations.csv")
TRAJECTORIES = os.path.join(ROOT, "outputs", "pakemis_structural_trajectories.csv")
BACK_YEARS = os.path.join(ROOT, "data", "sectors", "power", "activity",
                          "ke_station_fuel_back_years.csv")


def _rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheFamilyKinds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(CONFIGURATIONS)
        cls.by = {r["configuration_id"]: r for r in cls.rows}

    def test_every_family_member_has_a_kind_from_the_closed_vocabulary(self):
        for r in self.rows:
            self.assertEqual(bool(r["family_id"]), bool(r["family_kind"]),
                             r["configuration_id"])
            if r["family_kind"]:
                self.assertIn(r["family_kind"], nc.FAMILY_KINDS, r["configuration_id"])

    def test_the_power_family_has_three_kinds_beside_the_reference(self):
        kinds = {r["configuration_id"]: r["family_kind"] for r in self.rows
                 if r["family_id"] == "power_grid_control"}
        self.assertEqual(kinds, {
            "inventory_reference": "reference",
            "power_plant_physical_coal": "fuel_property_alternative",
            "power_with_kelectric": "coverage_alternative",
            "power_table3_legacy_control": "legacy_published_account"})

    def test_a_range_is_formed_within_one_kind_only(self):
        """The fuel-property range is the reference and the heat-rate member; it contains
        neither the K-Electric total nor the legacy account's."""
        low, high = nc.range_within_kind(self.rows, "power_grid_control",
                                         "fuel_property_alternative")
        reference = float(self.by["inventory_reference"]["national_total_Mt"])
        circular = float(self.by["power_plant_physical_coal"]["national_total_Mt"])
        self.assertEqual((low, high), (min(reference, circular), max(reference, circular)))
        for other in ("power_with_kelectric", "power_table3_legacy_control"):
            value = float(self.by[other]["national_total_Mt"])
            self.assertFalse(low <= value <= high,
                             "%s lies inside the fuel-property range" % other)
        with self.assertRaises(ValueError):
            nc.range_within_kind(self.rows, "power_grid_control", "a_new_kind")

    def test_the_roles_say_what_each_member_is(self):
        self.assertIn("COVERAGE", self.by["power_with_kelectric"]["family_role"])
        self.assertIn("not established", self.by["power_with_kelectric"]["family_role"])
        self.assertIn("circular", self.by["power_plant_physical_coal"]["family_role"])
        self.assertIn("LEGACY", self.by["power_table3_legacy_control"]["family_role"])
        self.assertIn("NOT established", nc.POWER_SELECTION_RULE)
        self.assertNotIn("57.82", nc.POWER_SELECTION_RULE,
                         "the rule quoted the superseded grid figure through rc66")


class TestTheCoverageSeries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = engine.load_data()
        cls.series = {r["fiscal_year"]: r for r in ke_leg.coverage_series(cls.data)}

    def test_nine_years(self):
        self.assertEqual(sorted(self.series), list(range(2015, 2024)))

    def test_the_ledger_years_are_the_existing_leg(self):
        for row in ke_leg.series(self.data):
            self.assertEqual(self.series[row["fiscal_year"]]["co2_Mt"], row["co2_Mt"])
        self.assertAlmostEqual(self.series[2023]["co2_Mt"], ke_leg.fy2023_case(self.data),
                               places=12)

    def test_the_unprinted_cells_stay_typed_and_are_estimated_beside(self):
        """Three furnace-oil cells are printed n.p. The table keeps them empty; the series
        carries the printed-fuel floor and the estimate separately, and names the cells."""
        rows = _rows(BACK_YEARS)
        absent = [r for r in rows if r["status"] == "not_provided_by_source"]
        self.assertEqual(sorted((int(r["fiscal_year"]), r["plant"]) for r in absent),
                         [(2015, "Gul Ahmed"), (2015, "Tapal Energy"),
                          (2018, "Bin Qasim TPS-I")])
        for r in absent:
            self.assertEqual(r["quantity"], "", "an absence is typed, never a zero")
            self.assertGreater(float(r["generation_GWh"]), 0.0)
        for year in (2015, 2018):
            row = self.series[year]
            self.assertLess(row["co2_Mt_printed_fuel_only"], row["co2_Mt"])
            self.assertTrue(row["estimated_cells"])
        for year in (2016, 2017):
            row = self.series[year]
            self.assertEqual(row["co2_Mt_printed_fuel_only"], row["co2_Mt"])
            self.assertEqual(row["estimated_cells"], "")

    def test_own_stations_are_part_of_the_system(self):
        for year, row in self.series.items():
            self.assertGreater(row["co2_Mt_own_stations"], 0.0, year)
            self.assertLessEqual(row["co2_Mt_own_stations"], row["co2_Mt"] + 1e-12, year)

    def test_the_scope_axis_is_priced_for_every_year(self):
        """Refused for eight of nine years through rc66."""
        rows = [r for r in _rows(TRAJECTORIES) if r["axis"] == "power scope"]
        self.assertEqual(len(rows), 9)
        for r in rows:
            self.assertIn(r["status"], ("priced", "priced_reference_register"),
                          r["fiscal_end_year"])
            year = int(r["fiscal_end_year"]) - 1
            self.assertAlmostEqual(float(r["delta_Mt"]), self.series[year]["co2_Mt"],
                                   places=4, msg=r["fiscal_end_year"])
        flagged = [r for r in rows if "not provided" in r["reason"]]
        self.assertEqual(sorted(r["fiscal_end_year"] for r in flagged), ["2016", "2019"])


if __name__ == "__main__":
    unittest.main()
