"""The completeness-mass ledger: the join is real, the sums are disciplined.

Wave 4's ledger is the first artifact that joins an absence's state to its mass, and
the first deliberate reader of the scope registry. These gates hold the properties
that make it trustworthy: it regenerates from the build, its sums exclude contained
claimants, its shared members agree with the joint-uncertainty surface, and the
validator actually refuses a registry that names configurations the release does
not ship.

Run:  python3 -m unittest discover tests -p "test_completeness_mass.py"
"""
import csv
import os
import sys
import unittest
from unittest.mock import patch


from pkinv.report import completeness_mass as cm  # noqa: E402
from pkinv.core.io import read_rows
from _support import ROOT


def _rows(path):
    return read_rows(path)


class TheLedger(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.committed = _rows(cm.OUT)
        cls.rebuilt = cm.build()

    def test_it_regenerates_identically(self):
        self.assertEqual(len(self.committed), len(self.rebuilt))
        for ours, theirs in zip(self.rebuilt, self.committed):
            self.assertEqual({k: str(v) for k, v in ours.items()}, dict(theirs))

    def test_missing_source_aggregate_is_unknown_not_a_composed_benchmark_range(self):
        summary = next(r for r in self.committed if r["row_type"] == "summary")
        self.assertEqual(summary["mass_basis"], "no_numerical_completeness_bound_declared")
        self.assertEqual(summary["mass_low_Mt"], "")
        self.assertEqual(summary["mass_high_Mt"], "")
        self.assertEqual(summary["composable"], "False")
        self.assertIn("unknown, not zero", summary["note"])

    def test_comparator_differences_are_not_missing_source_floors_or_bounds(self):
        diagnostics = [r for r in self.committed if r["row_type"] == "diagnostic"]
        self.assertEqual({r["ipcc_code"] for r in diagnostics}, {"1.A.2", "2.F"})
        for row in diagnostics:
            self.assertEqual(row["mass_low_Mt"], "")
            self.assertEqual(row["mass_high_Mt"], "")
            self.assertEqual(row["composable"], "False")
            self.assertEqual(row["mass_basis"], "comparison_not_missing_mass")

    def test_source_cases_stay_conditional_and_cannot_be_summed_as_missing_mass(self):
        cases = [r for r in self.committed if r["row_type"] == "case"]
        self.assertTrue(cases)
        for row in cases:
            self.assertEqual(row["composable"], "False", row["stream"])
            self.assertEqual(row["coverage_state"], "scenario_only")
            self.assertNotEqual(row["mass_basis"], "measured_band")
            self.assertNotIn("floor", row["mass_basis"])
            self.assertEqual(row["contained_in"], "")
            self.assertEqual(row["notation_key"], "")

    def test_ne_streams_keep_typed_absence_and_do_not_relabel_admitted_steel(self):
        streams = [r for r in self.committed if r["row_type"] == "stream"]
        for row in streams:
            self.assertEqual(row["notation_key"], "NE")
            self.assertEqual(row["mass_low_Mt"], "")
            self.assertEqual(row["mass_high_Mt"], "")
            self.assertEqual(row["composable"], "False")
        self.assertFalse([r for r in streams if r["stream"] == "Iron and steel (electric route)"])

    def test_every_named_configuration_ships(self):
        shipped = {r["configuration_id"] for r in _rows(
            os.path.join(ROOT, "outputs", "national_configurations.csv"))}
        for r in self.committed:
            if r["configuration_id"]:
                self.assertIn(r["configuration_id"], shipped, r["stream"])

    def test_every_ne_register_code_appears(self):
        """The ledger's universe is the completeness register's: an NE code with no
        ledger row would be the silence the ledger exists to remove."""
        ne_codes = {r["code"] for r in _rows(
            os.path.join(ROOT, "outputs", "completeness.csv"))
            if r["notation_key"] == "NE"}
        ledger_codes = {r["ipcc_code"] for r in self.committed
                       if r["row_type"] == "stream"}
        self.assertEqual(ne_codes - ledger_codes, set())


class TheValidator(unittest.TestCase):
    def test_a_screening_row_with_a_deleted_configuration_fails(self):
        """The positive control the plan demanded: remove the configuration a
        screening row names and the validator must refuse the registry."""
        configurations = [r for r in _rows(
            os.path.join(ROOT, "outputs", "national_configurations.csv"))
            if "in_scope" not in r["configuration_id"]]
        with self.assertRaises(SystemExit):
            cm.validate_scope_registry(configurations, residual_mt=29.42)

    def test_an_unrelated_comparator_residual_cannot_satisfy_a_screening_case(self):
        registry = [dict(category_id="test", current_status="screening", ipcc_code="2.F",
                         available_open_data="test_case", current_mass_Mt="3")]
        with patch.object(cm, "_rows", return_value=registry):
            with self.assertRaises(SystemExit):
                cm.validate_scope_registry([dict(configuration_id="test_case", national_delta_Mt="7")],
                                           residual_mt=3, stream_masses={})

    def test_a_drifted_mass_fails(self):
        """Rewritten at rc46 Wave 2 with the anchor it now guards.

        The 1A2 row used to lean on the fuel-ledger residual, so the poison was
        residual_mt=-999. The row is 'reference' now and anchors on the summed co2e of
        its activated streams in the shipped stream ledger - so the poison is a stream
        ledger that prices something else, injected through the validator's test seam.
        A registry mass agreeing with nothing the build prices is drift, whichever
        status carries it, and drift still fails the build."""
        configurations = _rows(
            os.path.join(ROOT, "outputs", "national_configurations.csv"))
        with self.assertRaises(SystemExit):
            cm.validate_scope_registry(
                configurations, residual_mt=cm._fuel_ledger_residual(),
                stream_masses={"industrial_solid_fuels_1a2": -999.0})


if __name__ == "__main__":
    unittest.main()
