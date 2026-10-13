"""Product-weighted FracGASF, the crop-residue NH3 term, and the one-fraction-two-layers guarantee."""
import os
import sys
import unittest


from pkinv.sectors.agriculture import air_pollutants as ap  # noqa: E402
from pkinv.sectors.agriculture import fertiliser_mix as fm  # noqa: E402
from pkinv.sectors.agriculture import manure  # noqa: E402
from pkinv.sectors.agriculture import soils  # noqa: E402
from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402


class TestFertiliserMix(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()

    def test_the_annex7_fifteen_month_trap_is_still_detectable(self):
        """The Annex-7 extraction carries FIFTEEN months. Summing it whole double-counts a
        season and inflates nitrogen by ~19%, which would silently distort every share
        derived from it.

        MOVED IN rc39 A2, not retired. The NATIONAL factor no longer comes from Annex-7 -
        it is weighted over Annex-5's Jul-Jun window - so this trap cannot reach it any
        more and asserting it through national_shares() would test nothing. It still
        reaches the PROVINCIAL factors, which are the one thing Annex-5 cannot give, so the
        guard moves to the path that still carries the hazard. A guard whose hazard has
        moved must move with it or it becomes a passing test over a dead code path."""
        fy = fm.product_nitrogen(self.data)                     # FY_SEASONS
        every = fm.product_nitrogen(self.data, seasons=None)    # all fifteen months
        fy_n = sum(sum(p.values()) for p in fy.values())
        all_n = sum(sum(p.values()) for p in every.values())
        self.assertGreater(all_n / fy_n, 1.15, "the 15-month trap is no longer detectable")

    def test_the_national_window_lands_on_the_audited_activity(self):
        """rc39 A2: Annex-5's own nitrogen over Jul-Jun is 0.756% below the audited datum.
        Close, and deliberately NOT reconciled - the annexe supplies composition only."""
        _, fy_n = fm.national_shares(self.data)
        audited = self.data.fertilizer["nitrogen_N_offtake"]["value_t"]
        self.assertAlmostEqual(fy_n / audited, 1.0, delta=0.05,
                               msg="FY window %.0f vs audited %.0f t N" % (fy_n, audited))

    def test_shares_sum_to_one_and_urea_dominates(self):
        shares, _ = fm.national_shares(self.data)
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=9)
        self.assertGreater(shares["Urea"], 0.75)

    def test_weighted_factor_supersedes_the_ipcc_default(self):
        """Pinned to four decimals since rc12. This test used to assert 0.1615 with
        delta=0.002 - a tolerance wide enough to pass at the engine's actual 0.1605,
        which is exactly how the agriculture paper's equation drifted to a value no
        engine path reproduces and nothing noticed for eight releases (the eighth
        review's NH3 item). The engine value is the anchor now, not a remembered one."""
        value, source = fm.fracgasf(self.data)
        self.assertAlmostEqual(value, 0.160524, delta=0.0005)
        self.assertIn("product-weighted", source)
        self.assertNotAlmostEqual(value, self.data.efv("soils", "FracGASF"), places=3)

    def test_uncertainty_treats_the_eea_table_as_one_correlated_source(self):
        """Every product factor comes from the same EEA table and shares its systematic error.
        Combining them in quadrature would report ~26% instead of the correct 30%, understating the
        uncertainty purely because the table has many rows."""
        self.assertAlmostEqual(fm.fracgasf_uncert(self.data), 30.0, delta=0.5)

    def test_shares_are_robust_to_the_window_even_though_levels_are_not(self):
        """Justifies deriving the factor from shares while keeping the audited total as activity."""
        fy, _ = fm.national_shares(self.data)
        allw, _ = fm.national_shares(self.data, seasons=None)
        self.assertAlmostEqual(fy["Urea"], allw["Urea"], delta=0.02)

    def test_provinces_differ_in_implied_factor(self):
        prov = fm.provincial_fracgasf(self.data)
        self.assertEqual(len(prov), 4)
        self.assertGreater(max(prov.values()) - min(prov.values()), 0.001)


class TestOneFractionTwoLayers(unittest.TestCase):
    """The air layer's synthetic NH3 and the GHG layer's synthetic indirect N2O must be driven by the
    SAME volatilisation fraction. Letting them drift onto different numbers for the same nitrogen is
    precisely the defect the shared nitrogen ledger was built to eliminate."""

    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        _, cls.npools = manure.compute(cls.data)

    def test_both_layers_derive_from_the_same_product_factor(self):
        """They share f_NH3; the greenhouse-gas pool additionally carries the NOx-N term, because
        Eq 11.9 is defined on NH3-N + NOx-N while the air layer reports the NH3-N part."""
        FSN = self.data.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000.0
        f_nh3, _ = fm.fracgasf(self.data)
        f_no = self.data.efv("soils", "NOx_frac_of_applied")
        self.assertAlmostEqual(
            soils.volatilised_n(self.data, self.npools, basis="NH3")["synthetic"],
            FSN * f_nh3, places=3)
        self.assertAlmostEqual(
            soils.volatilised_n(self.data, self.npools)["synthetic"],
            FSN * (f_nh3 + f_no), places=3)

    def test_air_and_ghg_synthetic_terms_scale_together(self):
        """A change in the product factor must move BOTH layers -- that is the guarantee. Each term
        is linear in its own basis, so the implied factors must reconstruct exactly."""
        nh3_pool = soils.volatilised_n(self.data, self.npools, basis="NH3")["synthetic"]
        total_pool = soils.volatilised_n(self.data, self.npools)["synthetic"]
        rows = ap.compute(self.data)
        nh3 = sum(r["emissions_kt"] for r in rows
                  if r["subitem"].startswith("NH3 - synthetic fertiliser"))
        comps = soils.compute(self.data, self.npools)
        n2o = [c for c in comps
               if c["subitem"] == "Indirect N2O - volatilisation (synthetic fertiliser)"][0]
        self.assertAlmostEqual(nh3 / nh3_pool * 1e6, 17.0 / 14.0, places=9)
        self.assertAlmostEqual(n2o["emissions_Gg"] / total_pool * 1e6,
                               self.data.efv("soils", "EF4_dry") * 44.0 / 28.0, places=9)


class TestChemicalBasis(unittest.TestCase):
    """The two volatilisation bases must stay distinct and must conserve nitrogen between them.

    An earlier version applied the NH3 share (0.95) to the EMEP/EEA product factor, which is already
    published as NH3-N. That both understated ammonia by ~5% and left the IPCC indirect-N2O pool
    missing its NOx-N term, so f_NH3*0.95 + f_NO no longer equalled the volatilised total -- the
    split silently stopped conserving N, in a paper whose central claim is a shared nitrogen ledger.
    """

    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        _, cls.npools = manure.compute(cls.data)
        cls.total = soils.volatilised_n(cls.data, cls.npools)
        cls.nh3 = soils.volatilised_n(cls.data, cls.npools, basis="NH3")
        cls.FSN = cls.data.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000.0

    def test_synthetic_split_conserves_nitrogen(self):
        """NH3-N + NOx-N must equal the total volatilised N, exactly."""
        nox = self.total["synthetic"] - self.nh3["synthetic"]
        f_nh3, _ = fm.fracgasf(self.data)
        f_no = self.data.efv("soils", "NOx_frac_of_applied")
        self.assertAlmostEqual(self.nh3["synthetic"], self.FSN * f_nh3, places=3)
        self.assertAlmostEqual(nox, self.FSN * f_no, places=3)
        self.assertAlmostEqual(self.total["synthetic"], self.FSN * (f_nh3 + f_no), places=3)

    def test_product_factor_is_not_discounted_by_the_nh3_share(self):
        """The specific regression: the EEA factor is NH3-N, so the 0.95 share must NOT be applied."""
        share = self.data.efv("soils", "NH3_frac_of_volat")
        f_nh3, _ = fm.fracgasf(self.data)
        self.assertNotAlmostEqual(self.nh3["synthetic"], self.FSN * f_nh3 * share, places=3)

    def test_ipcc_streams_do_take_the_nh3_share(self):
        """Conversely FracGASM covers NH3+NOx, so the organic and pasture streams must be reduced."""
        share = self.data.efv("soils", "NH3_frac_of_volat")
        for stream in ("organic", "pasture_cattle", "pasture_other"):
            self.assertAlmostEqual(self.nh3[stream], self.total[stream] * share, places=3)

    def test_basis_argument_is_explicit(self):
        with self.assertRaises(ValueError):
            soils.volatilised_n(self.data, self.npools, basis="NH4")


class TestCropResidueNH3(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        cls.total, cls.detail = ap.crop_residue_nh3(cls.data)

    def test_zero_is_computed_not_assumed(self):
        """Every Pakistani crop sits below the residue-N threshold, so the term is genuinely zero --
        but it must be evaluated, so a reader can tell a real zero from an omission."""
        self.assertEqual(len(self.detail), 5)
        self.assertAlmostEqual(self.total, 0.0, places=9)
        for d in self.detail:
            self.assertFalse(d["above_threshold"], d["crop"])
            self.assertEqual(d["EF_g_per_kg_DM"], 0.0)

    def test_cotton_is_the_closest_to_the_threshold(self):
        threshold = self.data.efv("crop_residue_nh3", "N_threshold")
        closest = max(self.detail, key=lambda d: d["n_ag_frac"])
        self.assertEqual(closest["crop"], "cotton")
        self.assertLess(closest["n_ag_frac"], threshold)

    def test_the_zero_is_robust_to_residue_nitrogen_error(self):
        """Cotton sits within 10% of the threshold, so an exact zero could be a threshold artefact.
        Perturbing every residue nitrogen content by +/-50% shows the consequence of being wrong is
        negligible -- which is the useful statement, not the bare zero."""
        rows = ap.crop_residue_nh3_sensitivity(self.data, spread=0.5)
        by = {r["n_content_factor"]: r for r in rows}
        self.assertEqual(by[1.0]["NH3_kt"], 0.0)
        self.assertEqual(by[0.5]["NH3_kt"], 0.0)
        self.assertEqual(by[1.5]["crops_above_threshold"], ["cotton"])
        self.assertLess(by[1.5]["NH3_kt"], 1.0, "even a 50% error must stay negligible")

    def test_a_crop_above_the_threshold_would_emit(self):
        """Guard the branch that never fires on current data: if a future crop or a revised residue
        nitrogen content crosses 0.0132, the term must stop being zero."""
        import copy
        d = copy.deepcopy(self.data)
        d.residue = dict(d.residue)
        d.residue["wheat"] = dict(d.residue["wheat"])
        d.residue["wheat"]["n_ag_frac"] = 0.02          # above the threshold
        total, detail = ap.crop_residue_nh3(d)
        wheat = [x for x in detail if x["crop"] == "wheat"][0]
        self.assertTrue(wheat["above_threshold"])
        self.assertGreater(wheat["EF_g_per_kg_DM"], 0.0)
        self.assertGreater(total, 0.0)


if __name__ == "__main__":
    unittest.main()
