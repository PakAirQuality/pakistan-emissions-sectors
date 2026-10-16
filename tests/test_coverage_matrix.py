"""The coverage matrix: does it have a denominator, and does every cell take a position?

The product this file guards exists because absence was previously unrepresentable. The
annual product enumerates 396 rows it HAS; nothing said how many it should have, so "385
of 405 cells" was a number only an audit could produce. These tests hold the two properties
that make the matrix worth shipping: the universe is the completeness register rather than
the realized set, and no cell is ever blank or outside the closed vocabulary.

Run:  python3 -m unittest discover tests -p "test_coverage_matrix.py"
"""
import collections
import csv
import os
import unittest

from pkinv.paths import OUTPUTS
from pkinv.report import coverage_matrix as cm
from pkinv.core.io import read_rows
from pkinv.core import configurations as conf
from pkinv.core.reporting_window import CORE_SUFFIX, CORE_FY_ENDS, REFERENCE_FY_START


def _rows(name):
    return read_rows(os.path.join(OUTPUTS, name), comments=False)


class TestTheUniverseIsDeclared(unittest.TestCase):
    """The denominator must come from the register, not from what happened to be built."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_coverage_matrix.csv")
        cls.base = [r for r in cls.rows
                    if r["configuration_id"] == cm.REFERENCE_CONFIGURATION]
        cls.completeness = _rows("completeness.csv")
        cls.series = _rows("pakemis_national_series.csv")

    def test_every_register_cell_appears_in_every_year(self):
        years = {int(r["fiscal_end_year"]) for r in self.series}
        expected = sum(len(cm._gases(e["gas"])) for e in self.completeness)
        self.assertGreater(expected, 0)
        per_year = collections.Counter(int(r["fiscal_end_year"]) for r in self.base)
        for year in years:
            self.assertEqual(per_year[year], expected,
                             "year %d carries %d base cells, the register declares %d"
                             % (year, per_year[year], expected))

    def test_the_denominator_exceeds_the_realized_set(self):
        """If the matrix only covered what the annual product built, it would be the
        circularity it exists to break: 45 realized cells cannot tell you 20 are missing."""
        annual = _rows("pakemis_annual_" + CORE_SUFFIX + ".csv")
        realized = {(r["category"], r["gas"]) for r in annual
                    if r["grain"] == "category_gas"}
        declared = {(r["category"], r["gas"]) for r in self.base}
        self.assertGreater(len(declared), len(realized))

    def test_air_pollutants_are_not_counted_as_greenhouse_gases(self):
        self.assertEqual(cm._gases("PM2.5/BC/CO/NOx/NMVOC/SO2/NH3"), [])
        self.assertEqual(cm._gases("CO2/CH4/N2O"), ["CO2", "CH4", "N2O"])
        for row in self.rows:
            self.assertIn(row["gas"], cm.GHG)


class TestNoCellIsSilent(unittest.TestCase):
    """A blank state would reintroduce the silence the product removes."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_coverage_matrix.csv")

    def test_every_state_is_in_the_closed_vocabulary(self):
        self.assertEqual({r["state"] for r in self.rows} - set(cm.STATES), set())

    def test_no_state_is_blank(self):
        self.assertFalse([r for r in self.rows if not r["state"].strip()])

    def test_every_state_declares_where_it_came_from(self):
        """The closed vocabulary behind the state. Without it, "NE" alone cannot tell a
        category this inventory never estimates from a sector-year waiting on evidence."""
        for row in self.rows:
            self.assertIn(row["state_basis"], cm.STATE_BASES,
                          "%s %s: %r" % (row["period_label"], row["category"],
                                         row["state_basis"]))

    def test_every_unresolved_cell_names_its_reason(self):
        for row in self.rows:
            if row["state"] == "unresolved":
                self.assertTrue(row["evidence"].strip(),
                                "%s %s %s is unresolved with no reason"
                                % (row["period_label"], row["category"], row["gas"]))

    def test_absent_sector_years_are_cells_not_one_collapsed_row(self):
        """The annual product answers an absent sector-year with ONE row carrying empty
        category and gas. That is the defect this matrix repairs: cement is absent in eight
        years and must appear eight times, not once, and industry's two absent years must
        cost six cells rather than two.

        The state is NE, not `unresolved`: a sector-year with no number because its evidence
        is not held is not estimated, which is what NE means. It was `unresolved` for one
        release, which read as a loose end in a product that otherwise has a number and
        invited the opposite error - filling the hole from a neighbouring year.
        """
        def absent(code):
            return [r for r in self.rows
                    if r["ipcc_code"] == code and r["state"] == "NE"
                    and r["state_basis"] == "sector-year-absent"
                    and r["configuration_id"] == cm.REFERENCE_CONFIGURATION]

        # state_basis is what keeps the two kinds of NE apart: 1.A.2 also carries register
        # NE rows for categories this inventory never estimates, and counting those as
        # absent sector-years would read as a much larger closeable gap than exists.
        # NONE for either since rc20: cement closed when trade and the yearbook years
        # landed, and industry's FY2015-16 - "blocked on an OCAC edition nobody holds" -
        # closed when the Pakistan Oil Report 2015-2016 turned out to be publicly served
        # as an image flipbook and its page-50 split was recovered.
        cement, industry = absent("2.A.1"), absent("1.A.2")
        self.assertEqual(len(cement), 0)
        self.assertEqual(len(industry), 0)
        for row in cement + industry:
            self.assertTrue(row["gap_id"].strip(),
                            "%s %s is NE with no gap naming what would close it"
                            % (row["period_label"], row["category"]))


class TestTheConfigurationAxisIsHonest(unittest.TestCase):
    """Four complete configurations differ from reference-only source cases."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows("pakemis_coverage_matrix.csv")
        cls.reference_year = REFERENCE_FY_START + 1

    def test_integrated_configurations_have_all_years_and_actual_annual_support(self):
        integrated = [r for r in self.rows if r["configuration_id"] in conf.ALL]
        annual = _rows("pakemis_annual_" + CORE_SUFFIX + ".csv")
        annual_support = {(r["configuration_id"], r["sector"], int(r["fiscal_end_year"]), r["gas"])
                          for r in annual if r["grain"] == "category_gas" and r["co2e_Mt_AR5"]}
        self.assertEqual({(r["configuration_id"], int(r["fiscal_end_year"])) for r in integrated},
                         {(cfg, year) for cfg in conf.ALL for year in CORE_FY_ENDS})
        reference = {(r["fiscal_end_year"], r["ipcc_code"], r["category"], r["gas"], r["sector"]): r
                     for r in integrated if r["configuration_id"] == conf.REFERENCE}
        for row in integrated:
            key = (row["fiscal_end_year"], row["ipcc_code"], row["category"], row["gas"], row["sector"])
            self.assertIn(key, reference)
            for field in ("state", "state_basis", "activity_basis", "gap_id"):
                self.assertEqual(row[field], reference[key][field], (key, field))
            if row["state_basis"] == "annual-product-row":
                self.assertIn((row["configuration_id"], row["sector"], int(row["fiscal_end_year"]), row["gas"]),
                              annual_support)
                self.assertIn("annual product row", row["evidence"])

    def test_other_structural_cases_are_priced_only_at_the_actual_reference_year(self):
        alternatives = [r for r in self.rows
                        if r["configuration_id"] not in conf.ALL]
        self.assertTrue(alternatives)
        for row in alternatives:
            priced = int(row["fiscal_end_year"]) == self.reference_year
            self.assertEqual(row["state"] == "estimated", priced, row["configuration_id"])
            if not priced:
                self.assertIn("priced at the reference year only", row["evidence"])

    def test_configurations_stay_inside_their_own_module(self):
        configurations = {c["configuration_id"]: c["module"]
                          for c in _rows("national_configurations.csv") if c["module"]}
        for row in self.rows:
            module = configurations.get(row["configuration_id"])
            if module:
                self.assertEqual(row["sector"], module)


class TestItRegeneratesIdentically(unittest.TestCase):
    def test_the_matrix_regenerates_identically(self):
        fresh = cm.build()
        shipped = _rows("pakemis_coverage_matrix.csv")
        self.assertEqual(len(fresh), len(shipped))
        for got, want in zip(fresh, shipped):
            for column in cm.FIELDS:
                self.assertEqual(str(got[column]), want[column],
                                 "%s drifted for %s" % (column, want["period_label"]))

    def test_the_summary_agrees_with_the_matrix(self):
        base = [r for r in _rows("pakemis_coverage_matrix.csv")
                if r["configuration_id"] == cm.REFERENCE_CONFIGURATION]
        counts = collections.Counter((int(r["fiscal_end_year"]), r["state"]) for r in base)
        for row in _rows("pakemis_coverage_summary.csv"):
            year = int(row["fiscal_end_year"])
            for state in cm.STATES:
                self.assertEqual(int(row[state]), counts.get((year, state), 0),
                                 "%d %s" % (year, state))


if __name__ == "__main__":
    unittest.main()
