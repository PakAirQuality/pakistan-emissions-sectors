"""rc39 A3: the reference year's urea mass is a measurement, the backcast's is a reconstruction.

Eq. 11.13 needs a mass of urea. For the reference year NFDC prints one - 6,578,838 t over
Jul-2023..Jun-2024 - and the engine used to reconstruct it instead, as
N_total * urea_N_share / urea_N_content, landing 13,621 t low. The repo had already noticed:
ippu/ammonia_reconciliation.py carried a "3.H method note" row whose status was "deferred; see
the urea-fertiliser-co2 gap". This pass discharges it.

The two bases are 0.207% apart, which is exactly why they are asserted rather than trusted: a
wrong choice between them is invisible in the output. So the tests below pin WHICH basis each
year uses, not only what it produces.
"""
import csv
import os
import unittest

from _support import OUTPUTS, read_rows

from pkinv.sectors.agriculture import liming_urea
from pkinv.sectors.agriculture.ef_library import InventoryData

DIRECT_UREA_T = 6578838.0
DIRECT_CO2_MT = 4.824481
RECONSTRUCTED_T = 6565217.0          # 3,775,000 * 0.80 / 0.46


class TestTheReferenceYearReadsTheOfftake(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()

    def test_the_mass_is_the_printed_national_row(self):
        mass, basis = liming_urea.urea_mass_t(self.data)
        self.assertAlmostEqual(mass, DIRECT_UREA_T, delta=0.5)
        self.assertEqual(basis, "direct_product_offtake")

    def test_it_produces_the_audited_co2(self):
        urea = next(c for c in liming_urea.compute(self.data)
                    if c["subitem"] == "Urea application CO2")
        self.assertAlmostEqual(urea["emissions_Gg"] / 1000.0, DIRECT_CO2_MT, places=6)

    def test_the_component_row_keeps_the_closed_v3_schema(self):
        """The basis is deliberately NOT a key on the component. core.components v3 is closed,
        and its own comment records why a provenance field only some sectors set is worse than
        none: it describes the rows that bothered. The basis is published per year instead."""
        from pkinv.core.components import ALL_KEYS
        urea = next(c for c in liming_urea.compute(self.data)
                    if c["subitem"] == "Urea application CO2")
        self.assertTrue(set(urea) <= ALL_KEYS, "unexpected: %s" % (set(urea) - ALL_KEYS))

    def test_the_reconstruction_would_have_been_lower(self):
        """The size of what was being papered over: 0.207%, or 0.009989 Mt CO2. Small enough
        to hide and large enough to matter at the fifth decimal the release pins."""
        n = self.data.fertilizer["nitrogen_N_offtake"]["value_t"]
        recon = n * self.data.p("urea_N_share") / self.data.p("urea_N_content")
        self.assertAlmostEqual(recon, RECONSTRUCTED_T, delta=1.0)
        self.assertGreater(DIRECT_UREA_T - recon, 13000.0)
        self.assertAlmostEqual(100.0 * (DIRECT_UREA_T - recon) / DIRECT_UREA_T, 0.207,
                               places=2)


class TestTheBackcastKeepsTheReconstruction(unittest.TestCase):
    """A historical year has a FAOSTAT total-N figure and no product split, so it MUST
    reconstruct - and must say so rather than silently inheriting the reference year's
    measured mass, which would be the same defect pointing the other way."""

    def test_a_stamped_year_reconstructs_and_declares_it(self):
        data = InventoryData()
        data.faostat_basis_year = 2019
        data.fertilizer["nitrogen_N_offtake"]["value_t"] = 3500000.0
        mass, basis = liming_urea.urea_mass_t(data)
        self.assertEqual(basis, "reconstructed_from_total_N_and_share")
        self.assertAlmostEqual(
            mass, 3500000.0 * data.p("urea_N_share") / data.p("urea_N_content"), places=3)

    def test_the_backcast_does_not_reuse_the_reference_mass(self):
        data = InventoryData()
        data.faostat_basis_year = 2019
        data.fertilizer["nitrogen_N_offtake"]["value_t"] = 3500000.0
        mass, _ = liming_urea.urea_mass_t(data)
        self.assertNotAlmostEqual(mass, DIRECT_UREA_T, delta=1000.0)

    def test_the_anchor_is_not_stamped(self):
        """The discriminator itself: a fresh InventoryData is the reference year."""
        self.assertIsNone(getattr(InventoryData(), "faostat_basis_year", None))


class TestThePublishedBasisTable(unittest.TestCase):
    """Nine fiscal years, each saying which urea mass Eq. 11.13 used and why."""

    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(os.path.join(OUTPUTS, "agriculture_urea_basis.csv"))

    def test_every_fiscal_year_is_present(self):
        self.assertEqual(len(self.rows), 9)

    def test_only_the_reference_year_is_measured(self):
        direct = [r for r in self.rows
                  if r["urea_activity_basis"] == "direct_product_offtake"]
        self.assertEqual([r["fiscal_year"] for r in direct], ["FY2023-24"])

    def test_the_reference_year_carries_the_printed_mass_and_its_co2(self):
        ref = next(r for r in self.rows if r["fiscal_year"] == "FY2023-24")
        self.assertAlmostEqual(float(ref["urea_mass_t"]), DIRECT_UREA_T, delta=0.5)
        self.assertAlmostEqual(float(ref["co2_Mt"]), DIRECT_CO2_MT, places=6)

    def test_every_reconstructed_year_says_why(self):
        for row in self.rows:
            if row["urea_activity_basis"] == "reconstructed_from_total_N_and_share":
                self.assertIn("no product split", row["source"], row["fiscal_year"])


class TestEveryBackcastPathDeclaresItself(unittest.TestCase):
    """There are TWO constructors that build a historical InventoryData by mutation, and the
    first version of this pass stamped only one.

    timeseries._apply_year (calendar/FAOSTAT) was stamped; fiscal_activity.data_for_fiscal_year
    (the fiscal backcast) was not - so every fiscal history year silently took the REFERENCE
    year's measured urea mass, moving eight years by up to 1.42 Mt while the year the pass was
    actually about moved by 0.01. Testing the two constructors by name is the point: a third one
    added later must appear here, because the failure mode is a path nobody remembered.
    """

    def test_the_fiscal_backcast_reconstructs(self):
        from pkinv.sectors.agriculture import fiscal_activity
        data = fiscal_activity.data_for_fiscal_year(2019)
        self.assertEqual(getattr(data, "faostat_basis_year", None), 2019)
        _, basis = liming_urea.urea_mass_t(data)
        self.assertEqual(basis, "reconstructed_from_total_N_and_share")

    def test_the_calendar_backcast_reconstructs(self):
        from pkinv.sectors.agriculture import timeseries
        data = timeseries.data_for_year(2019)
        self.assertEqual(getattr(data, "faostat_basis_year", None), 2019)
        _, basis = liming_urea.urea_mass_t(data)
        self.assertEqual(basis, "reconstructed_from_total_N_and_share")

    def test_both_anchors_are_the_reference_year(self):
        """Each constructor short-circuits fy 2024 to a fresh InventoryData; both must land on
        the measured offtake, or the reference year would differ between the two histories."""
        from pkinv.sectors.agriculture import fiscal_activity, timeseries
        for data in (fiscal_activity.data_for_fiscal_year(2024), timeseries.data_for_year(2024)):
            self.assertIsNone(getattr(data, "faostat_basis_year", None))
            mass, basis = liming_urea.urea_mass_t(data)
            self.assertEqual(basis, "direct_product_offtake")
            self.assertAlmostEqual(mass, DIRECT_UREA_T, delta=0.5)


class TestTheDeclaredGapIsDischarged(unittest.TestCase):
    """The reconciliation ledger declared this gap and deferred it. A pass that fixes the
    code and leaves the ledger saying 'deferred' has moved the defect into the paperwork."""

    def test_the_ledger_row_is_closed_and_carries_the_new_mass(self):
        rows = read_rows(os.path.join(OUTPUTS, "ippu_urea_co2_bridge_2025.csv"))
        note = [r for r in rows if r.get("flow") == "3.H method note"]
        self.assertEqual(len(note), 1, "the 3.H method note row has gone")
        row = note[0]
        self.assertIn("closed", row["status"])
        self.assertAlmostEqual(float(row["urea_kt"]), DIRECT_UREA_T / 1000.0, delta=0.01)

    def test_no_module_still_claims_the_reconstruction_reproduces_the_offtake(self):
        """The specific sentence that made a 0.2% gap sound like agreement."""
        import subprocess
        from pkinv.paths import ROOT
        out = subprocess.run(["grep", "-rn", "--include=*.py", "reproduces NFDC offtake",
                              os.path.join(ROOT, "src")], capture_output=True, text=True)
        self.assertFalse(out.stdout.strip(), out.stdout)


if __name__ == "__main__":
    unittest.main()
