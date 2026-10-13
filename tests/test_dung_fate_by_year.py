"""The dung-fate account by fiscal year: the diverted dung is all accounted for, in mass and
in nitrogen, and exactly one reading of where the unresolved part went is the reference.

WHY. Since rc67 the residential reference burns the dung households report burning, in every
year of the panel, and agriculture still diverts about five times that from manure
management. Through rc66 the difference was priced for the reference year only, as a footnote
to a second configuration. It is part of what the reference leaves out now, in every year, so
the product that states it (outputs/pakemis_dung_fate_by_year.csv) is held here to the things
a reader relies on: nothing is created or lost on any row, the reference row asserts no
emission, the other rows only add, and the reference year is the reference-year file.
"""
import collections
import csv
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.report import dung_fate_by_year as fate                # noqa: E402
from pkinv.sectors.residential import timeseries                  # noqa: E402

PRODUCT = os.path.join(ROOT, "outputs", "pakemis_dung_fate_by_year.csv")
REFERENCE_YEAR_FILE = os.path.join(ROOT, "outputs", "national_dung_variants.csv")
REFERENCE_PERIOD = "FY2023-24"
VARIANTS = ("S_household_only_unallocated", "S_residual_nonhousehold_combustion",
            "S_residual_return_to_manure", "S_residual_field_application",
            "S_revised_diversion_fraction")
MASS_MT = 1e-3       # the columns print four decimals of a megatonne
NITROGEN_KT = 1e-2   # and three of a kilotonne


def _rows(path):
    with open(path, encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class TestTheFateAccount(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(PRODUCT)
        cls.by_period = collections.defaultdict(list)
        for row in cls.rows:
            cls.by_period[row["period_id"]].append(row)

    def test_nine_periods_by_five_variants(self):
        self.assertEqual(list(self.rows[0]), list(fate.FIELDS))
        self.assertEqual(len(self.rows), 45)
        self.assertEqual(len(self.by_period), 9)
        self.assertEqual(sorted(self.by_period)[0], "FY2015-16")
        self.assertEqual(sorted(self.by_period)[-1], REFERENCE_PERIOD)
        for period, rows in self.by_period.items():
            self.assertEqual([r["variant_id"] for r in rows], list(VARIANTS), period)

    def test_every_row_conserves_the_diverted_mass_and_its_nitrogen(self):
        """Household + destination + unresolved = diverted, twice over. The nitrogen
        identity is the one that matters for the two agriculture destinations: a variant
        that moved the mass and left the nitrogen behind would price volatile solids
        and N2O from different quantities of dung."""
        for row in self.rows:
            where = "%s %s" % (row["period_id"], row["variant_id"])
            self.assertAlmostEqual(
                float(row["household_Mt"]) + float(row["destination_Mt"])
                + float(row["unresolved_Mt"]), float(row["diverted_Mt"]),
                delta=MASS_MT, msg=where)
            self.assertAlmostEqual(
                float(row["household_N_kt"]) + float(row["destination_N_kt"])
                + float(row["unresolved_N_kt"]), float(row["diverted_N_kt"]),
                delta=NITROGEN_KT, msg=where)
            for column in ("household_Mt", "destination_Mt", "unresolved_Mt",
                           "household_N_kt", "destination_N_kt"):
                self.assertGreaterEqual(float(row[column]), 0.0, "%s %s" % (where, column))

    def test_the_masses_are_the_years_and_not_the_variants(self):
        """What agriculture diverts and what households burn are facts about the year.
        A variant only says where the rest went, so those four columns are one value
        across a period's five rows."""
        for period, rows in self.by_period.items():
            for column in ("diverted_Mt", "household_Mt", "diverted_N_kt",
                           "household_N_kt", "household_basis",
                           "reference_national_Mt_co2e_AR5"):
                self.assertEqual(len({r[column] for r in rows}), 1,
                                 "%s: %s differs between variants" % (period, column))

    def test_exactly_one_reference_row_a_period_and_it_asserts_nothing(self):
        """The reference takes the row that applies no emission to the unresolved dung:
        zero delta, no gas, and a national total that is the national series' own."""
        for period, rows in self.by_period.items():
            reference = [r for r in rows if r["is_reference"] == "yes"]
            self.assertEqual(len(reference), 1, period)
            self.assertEqual({r["is_reference"] for r in rows}, {"yes", "no"}, period)
            row = reference[0]
            self.assertEqual(row["variant_id"], fate.REFERENCE_VARIANT)
            self.assertEqual(float(row["delta_Mt_co2e_AR5"]), 0.0, period)
            self.assertEqual(row["national_total_Mt_co2e_AR5"],
                             row["reference_national_Mt_co2e_AR5"], period)
            self.assertEqual(float(row["destination_Mt"]), 0.0, period)
            for gas in ("ch4_Gg", "n2o_Gg", "biogenic_co2_memo_Gg"):
                self.assertEqual(float(row[gas]), 0.0, "%s %s" % (period, gas))

    def test_every_total_is_the_reference_plus_its_own_delta(self):
        for row in self.rows:
            self.assertAlmostEqual(
                float(row["reference_national_Mt_co2e_AR5"])
                + float(row["delta_Mt_co2e_AR5"]),
                float(row["national_total_Mt_co2e_AR5"]), delta=6e-5,
                msg="%s %s" % (row["period_id"], row["variant_id"]))

    def test_the_unresolved_mass_is_positive_and_most_of_the_diversion(self):
        """In every year the survey leaves most of the diverted dung without a household
        to burn it. If a year's unresolved mass ever reached zero the reference and
        configuration L would be the same account, and this product would have nothing
        to state."""
        for period, rows in self.by_period.items():
            row = next(r for r in rows if r["is_reference"] == "yes")
            self.assertGreater(float(row["unresolved_Mt"]), 0.0, period)
            self.assertGreater(float(row["unresolved_N_kt"]), 0.0, period)
            self.assertGreater(float(row["unresolved_Mt"]),
                               0.5 * float(row["diverted_Mt"]), period)
            for other in rows:
                if other["is_reference"] == "no":
                    self.assertAlmostEqual(float(other["destination_Mt"]),
                                           float(row["unresolved_Mt"]), delta=MASS_MT,
                                           msg="%s %s" % (period, other["variant_id"]))

    def test_burning_it_elsewhere_is_the_most_any_destination_costs(self):
        """Non-household combustion is configuration L by another name, and it is the
        largest delta in every period. Every destination adds emissions the reference
        does not count, so no priced delta is negative or zero."""
        for period, rows in self.by_period.items():
            delta = {r["variant_id"]: float(r["delta_Mt_co2e_AR5"]) for r in rows}
            largest = max(delta, key=delta.get)
            self.assertEqual(largest, "S_residual_nonhousehold_combustion", period)
            for variant, value in delta.items():
                if variant != fate.REFERENCE_VARIANT:
                    self.assertGreater(value, 0.0, "%s %s" % (period, variant))
            self.assertEqual(delta["S_residual_return_to_manure"],
                             delta["S_revised_diversion_fraction"], period)

    def test_the_household_mass_is_the_survey_series(self):
        """The household column is residential.timeseries' two-round survey series, year
        for year, and wears that series' own basis label: the per-household rate of the
        2018-19 round held flat up to it, interpolated toward the 2024-25 round after."""
        for period, rows in self.by_period.items():
            year = int(period[2:6]) + 1
            for row in rows:
                self.assertAlmostEqual(float(row["household_Mt"]),
                                       timeseries.dung_survey_air_dry_kg(year) / 1e9,
                                       delta=6e-5, msg=period)
                self.assertEqual(row["household_basis"],
                                 timeseries.dung_survey_basis(year), period)
        reference = self.by_period[REFERENCE_PERIOD][0]
        self.assertAlmostEqual(float(reference["household_Mt"]),
                               timeseries.dung_survey_air_dry_kg(2024) / 1e9, delta=6e-5)
        self.assertAlmostEqual(float(reference["household_Mt"]), 10.9334, places=4)

    def test_the_reference_year_is_the_reference_year_file(self):
        """outputs/national_dung_variants.csv prices the same five destinations for
        FY2023-24 alone. The two files are written by different phases from one pricing
        function, and a reader holding both must find one number."""
        shipped = {r["variant_id"]: r for r in _rows(REFERENCE_YEAR_FILE)}
        here = {r["variant_id"]: r for r in self.by_period[REFERENCE_PERIOD]}
        self.assertEqual(set(shipped), set(here))
        for variant, row in here.items():
            other = shipped[variant]
            self.assertAlmostEqual(float(row["national_total_Mt_co2e_AR5"]),
                                   float(other["national_total_Mt_co2e_AR5"]),
                                   delta=2e-5, msg=variant)
            for column in ("diverted_Mt", "household_Mt", "destination_Mt",
                           "unresolved_Mt"):
                self.assertAlmostEqual(float(row[column]), float(other[column]),
                                       delta=6e-5, msg="%s %s" % (variant, column))

    def test_the_build_reproduces_the_shipped_file(self):
        """Row for row and cell for cell. The build re-runs agriculture for each year, so
        this is also the check that nothing upstream moved under a file that was not
        regenerated."""
        fresh = fate.build()
        self.assertEqual(len(fresh), len(self.rows))
        for built, shipped in zip(fresh, self.rows):
            self.assertEqual({k: str(v) for k, v in built.items()}, shipped,
                             "%s %s" % (shipped["period_id"], shipped["variant_id"]))


if __name__ == "__main__":
    unittest.main()
