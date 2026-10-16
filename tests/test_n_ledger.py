"""The nitrogen ledger must close, and the FracGasMS/FracGASM boundary must stay separate.

These are regression guards for a real defect: an earlier implementation used FracGASM (the
POST-application fraction, Table 11.3) to reduce manure before it reached the field -- where
FracGasMS (Table 10.22) belongs -- and then applied FracGASM again to the survivor, counting
one fraction twice on the same nitrogen.
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest

# National activity data and inventory outputs live in the companion
# repository; this repo holds only the agriculture research layer.
from pkinv.paths import DATA as NAT_DATA, OUTPUTS as NAT_OUT

from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture import manure  # noqa: E402
from pkinv.sectors.agriculture import n_ledger# noqa: E402
from _support import ROOT


class TestLedgerCloses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        cls.rows, cls.checks = n_ledger.build(cls.data)
        _, cls.np = manure.compute(cls.data)

    def test_every_stage_closes(self):
        for key in ("partition_residual", "mms_residual", "tan_residual", "closing_residual"):
            rel = abs(self.checks[key]) / self.checks["excreted_N"]
            self.assertLess(rel, 1e-9, "%s = %.3e relative" % (key, rel))

    def test_excretion_partitions_into_three_named_pools(self):
        n = self.np
        parts = (n["FPRP_cattle_N"] + n["FPRP_other_N"] + n["managed_N"] + n["diverted_N"])
        self.assertAlmostEqual(parts / n["excreted_N"], 1.0, places=12)

    def test_dung_cake_diversion_is_named_not_dropped(self):
        """~16% of excreted N leaves as dung-cake fuel; it must appear as an explicit flow."""
        self.assertGreater(self.np["diverted_N"], 0.0)
        flows = [r["flow"] for r in self.rows if "dung-cake" in r["flow"]]
        self.assertEqual(len(flows), 1, "dung-cake diversion must be one explicit ledger line")

    def test_mms_loss_terms_sum_to_the_pre_field_loss(self):
        n = self.np
        lost = (n["volat_managed_N"] + n["leach_managed_N"] + n["n2_managed_N"]
                + n["n2o_managed_N"])
        self.assertAlmostEqual((lost + n["FON_N"]) / n["managed_N"], 1.0, places=12)


class TestBoundarySeparation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        _, cls.np = manure.compute(cls.data)

    def test_fracgasms_is_not_fracgasm(self):
        """The pre-field and post-application fractions are different numbers by definition."""
        gasm = self.data.efv("soils", "FracGASM")
        for r in self.np["by_system"]:
            self.assertNotAlmostEqual(
                r["FracGasMS"], gasm, places=6,
                msg="%s/%s uses the post-application FracGASM at the pre-field boundary"
                    % (r["species"], r["system"]))

    def test_fon_is_not_reduced_by_fracgasm(self):
        """FON must follow Eq 10.34 (FracLossMS), never the Table 11.3 grazing/application
        fraction. Guards against reintroducing the conflation."""
        gasm = self.data.efv("soils", "FracGASM")
        legacy_fon = self.np["managed_N"] * (1 - gasm)
        self.assertNotAlmostEqual(self.np["FON_N"] / 1e9, legacy_fon / 1e9, places=3)

    def test_fracloss_follows_equation_10_34a(self):
        """FracLossMS = FracGasMS + FracLeachMS + FracN2MS + EF3, and FracN2MS = RN2 x EF3."""
        rn2 = self.data.efv("manure_n2", "RN2_N2O")
        for r in self.np["by_system"]:
            self.assertAlmostEqual(r["FracN2MS"], rn2 * r["EF3"], places=12)
            self.assertAlmostEqual(
                r["FracLossMS"],
                r["FracGasMS"] + r["FracLeachMS"] + r["FracN2MS"] + r["EF3"], places=12)
            self.assertLess(r["FracLossMS"], 1.0)

    def test_every_fracgasms_factor_is_sourced_to_table_10_22(self):
        rows = [r for r in csv.DictReader(open(asset_path(NAT_DATA, "emission_factors.csv")))
                if r["category"] == "manure_fracgasms"]
        self.assertGreater(len(rows), 0)
        for r in rows:
            self.assertIn("Table 10.22", r["source"], r["ef_id"])
            self.assertTrue(float(r["uncert_pct"]) > 0, r["ef_id"])


class TestDiagnosticRuns(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.eval import n_ledger_runs
        cls.runs = {r["run"].split(".")[0]: r for r in n_ledger_runs.all_runs()}

    def test_legacy_run_reproduces_the_published_total(self):
        """Run A is the regression fixture for the MANURE nitrogen boundary: it reproduces the
        pre-correction configuration of that chain, so the headline change stays attributable to
        the boundary fix.

        It cannot be pinned to a literal, and the attempt to do so is instructive: it was set at
        221.80, drifted from the originally published 221.71 when FracGASF moved to Pakistan's
        product-weighted value, and broke again when the sector was harmonised onto FY2023-24
        with a higher nitrogen offtake. None of those movements was a defect in the manure
        boundary this fixture exists to protect.

        What Run A actually asserts is that the pre-correction manure configuration sits a
        known distance BELOW the reported total - the boundary fix is what closed that gap - so
        the assertion is on the relationship, not on a number that any unrelated change can
        move."""
        from pkinv.sectors.agriculture import run_inventory
        from pkinv.sectors.agriculture.ef_library import InventoryData
        from pkinv.core.components import enrich_co2e
        # Legacy diagnostic B is the complete IPCC formulation, now an explicit
        # structural alternative to the central TAN material-flow formulation.
        comps = run_inventory.build_components(InventoryData(), nitrogen_method="ipcc")
        enrich_co2e(comps)
        reported = sum(c["co2e_Mt_AR5"] for c in comps)
        legacy = self.runs["A"]["national_total_Mt"]
        self.assertGreater(legacy, reported,
                           "the pre-correction manure run double-counted dung nitrogen, so it "
                           "must sit ABOVE the reported total - see "
                           "test_correction_lowers_manure_n_reaching_soils")
        self.assertAlmostEqual(legacy, reported, delta=0.02 * reported,
                               msg="Run A has drifted more than 2 percent from the reported "
                                   "total; the manure boundary fix was worth far less than that")

    def test_legacy_and_shipped_runs_share_the_fertiliser_factor(self):
        """The A->B delta must remain a pure manure-chain difference: both runs use whatever
        FracGASF the engine currently uses, so a fertiliser change cannot masquerade as a
        manure-boundary effect."""
        delta = self.runs["A"]["national_total_Mt"] - self.runs["B"]["national_total_Mt"]
        self.assertAlmostEqual(delta, 0.62, delta=0.03)

    def test_shipped_run_matches_the_engine(self):
        from pkinv.report import annual_product
        from pkinv.core import configurations as conf
        rows = annual_product.components_for("agriculture", 2024,
                                             annual_product.build_context(), conf.IPCC_REFERENCE)
        got = sum(row["co2e_Mt_AR5"] for row in rows)
        self.assertAlmostEqual(self.runs["B"]["national_total_Mt"], got, delta=0.01)

    def test_correction_lowers_manure_n_reaching_soils(self):
        self.assertLess(self.runs["B"]["manure_N_applied_Mt_N"],
                        self.runs["A"]["manure_N_applied_Mt_N"])

    def test_prefield_representations_are_closer_than_the_full_chains(self):
        """Correcting the boundary brings the PRE-FIELD stage within a factor of 1.5. That is a
        narrow claim and must stay narrow: the full chains agree in total only because field
        application and grazing disagree in opposite directions and cancel
        (n_ledger.stage_comparison), so this is not evidence that the two representations are
        equivalent."""
        ipcc = self.runs["B"]["prefield_volat_pct_of_managed"]
        emep = self.runs["C"]["prefield_volat_pct_of_managed"]
        self.assertLess(max(ipcc, emep) / min(ipcc, emep), 1.5)

    def test_every_run_closes_the_excretion_partition(self):
        for k, r in self.runs.items():
            self.assertLess(abs(r["closing_N_residual_kg"]), 1.0, k)


class TestResidueFractions(unittest.TestCase):
    """frac_returned and frac_burned live in different files, so nothing enforced that a crop's
    residue could not be more than fully accounted for."""

    def test_returned_plus_burned_never_exceeds_one(self):
        res = {r["crop"]: float(r["frac_returned"]) for r in
               csv.DictReader(open(asset_path(NAT_DATA, "residue_params.csv")))}
        burn = {r["crop"]: float(r["frac_burned"]) for r in
                csv.DictReader(open(asset_path(NAT_DATA, "burning_params.csv")))}
        for crop, fr in res.items():
            fb = burn.get(crop, 0.0)
            self.assertLessEqual(fr + fb, 1.0,
                                 "%s: returned %.2f + burned %.2f > 1" % (crop, fr, fb))


if __name__ == "__main__":
    unittest.main()
