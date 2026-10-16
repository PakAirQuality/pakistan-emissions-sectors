"""The residual-destination variant registry and its published pricing.

The rc2 review's section 4: configuration S leaves 46.72 Mt of diverted dung without an
observed destination, each candidate destination has different gas consequences, and the
national reading is under-described until the alternatives are published -- with no
probabilities, because conservation says the mass exists, not where it went. These tests
hold the registry and the pricing to each other both ways, and hold the pricing to the
engines it claims to reuse.

rc67 (2026-10-13): configuration S is the REFERENCE now (the two-round survey series,
10.93 Mt of household cake in FY2023-24), so the unresolved mass is the reference's own
47.81 Mt, the base variant is the published reference total (national_all_sectors.csv),
and the non-household-combustion variant lands on the configuration-L total.
Both are checked independently against the native four-configuration atoms and
the exposed rollups; obsolete release constants remain in the preserved baseline.
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest


from pkinv.report import dung_variants   # noqa: E402
from pkinv.core.io import read_rows
from _support import ROOT


def _published():
    path = os.path.join(ROOT, "outputs", "national_dung_variants.csv")
    return read_rows(path, comments=False)


def _native_total(configuration):
    return sum(float(r["co2e_Mt_AR5"]) for r in read_rows(
        os.path.join(ROOT, "outputs", "pakemis_ghg_configuration_atoms.csv"))
        if r["period_id"] == "FY2023-24" and r["configuration_id"] == configuration
        and r["co2e_Mt_AR5"])


class TestTheVariantRegistry(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.registry = dung_variants.registry()
        cls.published = _published()

    def test_the_registry_and_the_output_cover_each_other(self):
        declared = {r["variant_id"] for r in self.registry}
        published = {r["variant_id"] for r in self.published}
        self.assertEqual(declared, published)
        self.assertEqual(len(self.registry), 5)

    def test_every_variant_hangs_off_a_registered_axis(self):
        with open(asset_path(ROOT, "data", "scenarios.csv"), newline="",
                  encoding="utf-8") as f:
            axes = {r["axis"] for r in csv.DictReader(
                line for line in f if not line.startswith("#"))}
        for r in self.registry:
            self.assertIn(r["parent_axis"], axes,
                          "%s hangs off an axis scenarios.csv does not register"
                          % r["variant_id"])

    def test_no_probability_column_exists(self):
        """The reviewer's explicit constraint, held as schema: assigning likelihoods to
        the destinations would be the fiat this inventory declines everywhere else."""
        for fields in (self.registry[0].keys(), self.published[0].keys()):
            for name in fields:
                self.assertNotIn("prob", name.lower())
                self.assertNotIn("likelihood", name.lower())
                self.assertNotIn("weight", name.lower())

    def test_every_variant_conserves_the_diverted_mass(self):
        for r in self.published:
            self.assertAlmostEqual(
                float(r["household_Mt"]) + float(r["destination_Mt"])
                + float(r["unresolved_Mt"]),
                float(r["diverted_Mt"]), places=3,
                msg="%s does not conserve mass" % r["variant_id"])

    def test_the_base_variant_is_the_published_S_total_exactly(self):
        base = next(r for r in self.published
                    if r["variant_id"] == "S_household_only_unallocated")
        self.assertAlmostEqual(float(base["national_total_Mt_co2e_AR5"]),
                               _native_total("S_TAN"), delta=2e-5)
        self.assertEqual(float(base["delta_vs_S_Mt_co2e_AR5"]), 0.0)

    def test_the_base_variant_is_the_published_reference_total(self):
        """The same claim as the pin above, joined to the live file. Since rc67 the base
        variant IS the reference: households burn the survey's quantity and the rest of
        the diverted dung is a declared stock with no pathway, so its total must be
        national_all_sectors.csv's own, its delta zero, and its unresolved mass the whole
        of diverted less household."""
        base = next(r for r in self.published
                    if r["variant_id"] == "S_household_only_unallocated")
        reference = next(r for r in read_rows(
            os.path.join(ROOT, "outputs", "national_all_sectors.csv"))
            if r["row_kind"] == "national_total")
        self.assertEqual(reference["residential_dung_axis"], "S")
        self.assertEqual(base["national_total_Mt_co2e_AR5"], reference["co2e_Mt_AR5"])
        self.assertEqual(float(base["destination_Mt"]), 0.0)
        self.assertAlmostEqual(float(base["unresolved_Mt"]),
                               float(base["diverted_Mt"]) - float(base["household_Mt"]),
                               places=3)
        self.assertGreater(float(base["unresolved_Mt"]), float(base["household_Mt"]))

    def test_nonhousehold_combustion_is_the_published_ledger_total(self):
        """The same claim as the pin below, joined to the live file: the residual burned
        on the same fuel chain is what configuration L counts, so the variant must land
        on national_all_sectors_ledger.csv's total, at the half-ulp tolerance the pin
        uses. Through rc66 that total was the reference's; it is the alternative's now."""
        row = next(r for r in self.published
                   if r["variant_id"] == "S_residual_nonhousehold_combustion")
        ledger = next(r for r in read_rows(
            os.path.join(ROOT, "outputs", "national_all_sectors_ledger.csv"))
            if r["row_kind"] == "national_total")
        self.assertEqual(ledger["residential_dung_axis"], "L")
        self.assertAlmostEqual(float(row["national_total_Mt_co2e_AR5"]),
                               float(ledger["co2e_Mt_AR5"]), delta=2e-5)
        self.assertEqual(float(row["unresolved_Mt"]), 0.0)

    def test_nonhousehold_combustion_reproduces_the_L_total(self):
        """The internal check the chemistry forces: the residual burning anywhere on the
        same fuel chain emits what L already counts, so this variant must land on the L
        total -- it is a reclassification, not a new quantity. A divergence here means
        the variant grew its own arithmetic. Compared at half an ulp of the printed
        5-decimal column rather than as strings: the variant composes S + delta and the
        rollup sums components, and the two rounding paths legitimately split the last
        printed digit (447.71689 vs 447.71688 at rc19); any REAL arithmetic drift is
        orders of magnitude above this tolerance."""
        row = next(r for r in self.published
                   if r["variant_id"] == "S_residual_nonhousehold_combustion")
        self.assertAlmostEqual(float(row["national_total_Mt_co2e_AR5"]),
                               _native_total("L_TAN"), delta=2e-5)

    def test_return_and_revision_price_identically_and_say_so(self):
        """Same arithmetic, different reading of evidence -- the note must draw the
        distinction, or the two rows look like a duplicated row rather than a declared
        interpretive fork."""
        ret = next(r for r in self.published
                   if r["variant_id"] == "S_residual_return_to_manure")
        rev = next(r for r in self.published
                   if r["variant_id"] == "S_revised_diversion_fraction")
        self.assertEqual(ret["national_total_Mt_co2e_AR5"],
                         rev["national_total_Mt_co2e_AR5"])
        self.assertIn("which reading of evidence", rev["note"].lower())

    def test_every_destination_moves_the_total_upward_from_S(self):
        """Every priced destination adds emissions S does not count, so every delta is
        positive except the declared-stock base. If a destination ever prices negative,
        something is subtracting mass that S already counts."""
        for r in self.published:
            delta = float(r["delta_vs_S_Mt_co2e_AR5"])
            if r["variant_id"] == "S_household_only_unallocated":
                self.assertEqual(delta, 0.0)
            else:
                self.assertGreater(delta, 0.0, r["variant_id"])

    def test_the_shared_agriculture_instance_is_not_mutated(self):
        """The pricing runs manure and soils on copies; if the shared InventoryData were
        scaled in place, every later reader of mms shares would inherit the variant."""
        from pkinv.sectors.agriculture.ef_library import InventoryData
        before = InventoryData().mms["cattle"]["burned_fuel"]
        dung_variants.build()
        after = InventoryData().mms["cattle"]["burned_fuel"]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
