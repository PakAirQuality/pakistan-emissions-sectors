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

    def test_the_summary_band_is_the_stream_rows_recomputed(self):
        """The bound sum is exactly the composable rows' upper bounds; the floor is
        strictly below it and excludes the floorless bases (external benchmark,
        ceiling) - the sums cannot drift from the rows they summarize."""
        streams = [r for r in self.committed if r["row_type"] == "stream"]
        summary = [r for r in self.committed if r["row_type"] == "summary"][0]
        bound = sum(float(r["mass_high_Mt"]) for r in streams
                    if r["composable"] == "True" and r["mass_high_Mt"])
        self.assertAlmostEqual(float(summary["mass_high_Mt"]), round(bound, 2),
                               places=2)
        floorless = ("external_benchmark_bound", "ceiling", "no_bound")
        floor_cap = sum(float(r["mass_low_Mt"]) for r in streams
                        if r["composable"] == "True" and r["mass_low_Mt"]
                        and r["mass_basis"] not in floorless)
        self.assertAlmostEqual(float(summary["mass_low_Mt"]),
                               round(floor_cap, 2), places=2)
        self.assertLess(float(summary["mass_low_Mt"]),
                        float(summary["mass_high_Mt"]))

    def test_contained_claimants_are_excluded_from_the_sums(self):
        """The not_composed rule: a claimant inside the 1A2 residual must never be
        summed beside its container."""
        for r in self.committed:
            if r["contained_in"]:
                self.assertEqual(r["composable"], "False", r["stream"])

    def test_the_directive_target_is_bracketed_once_activated_mass_is_added_back(self):
        """Rewritten at rc46 Wave 2, whose activation retired the old containment.

        The band used to contain the ~47 Mt directive target directly. Then 13.57 Mt of it -
        brick and cement coal - was activated into the reference estimate, so the REMAINING
        band tops out below the target, and that is the directive being paid down rather
        than lost. What must now hold: the remaining band sits strictly below the target
        (if it ever contains 47 again, either mass was de-activated or a new gap grew),
        and adding the activated mass back re-brackets it (the accounting still reaches
        the directive; nothing fell out of the ledger)."""
        summary = [r for r in self.committed if r["row_type"] == "summary"][0]
        low, high = float(summary["mass_low_Mt"]), float(summary["mass_high_Mt"])
        activated = cm.activated_reference_mt()
        self.assertGreater(activated, 13.0)
        self.assertLess(high, cm.DIRECTIVE_TARGET_MT,
                        "the remaining band contains the directive again: was mass "
                        "de-activated, or did a new gap grow?")
        self.assertLess(low + activated, cm.DIRECTIVE_TARGET_MT)
        self.assertGreater(high + activated, cm.DIRECTIVE_TARGET_MT)

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
