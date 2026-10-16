"""Conserved nitrogen releases shared by GHGs and air pollutants."""
import unittest

from pkinv.sectors.agriculture.ef_library import InventoryData
from pkinv.sectors.agriculture import manure, soils


class CommonNitrogenFate(unittest.TestCase):
    def setUp(self):
        self.data = InventoryData()

    def test_management_fate_closes_and_indirect_n2o_uses_actual_release(self):
        for method in manure.NITROGEN_METHODS:
            components, pools = manure.compute(self.data, method=method)
            for row in pools["by_system"]:
                fate = sum(row[k] for k in ("NH3_N", "NOx_N", "leach_N", "n2_N", "n2o_N", "applied_N"))
                self.assertAlmostEqual(row["excreted_N"], fate, delta=1e-6)
            direct = next(c for c in components if c["subitem"] == "Indirect N2O (volatilisation)")
            actual = pools["managed_NH3_N"] + pools["managed_NOx_N"]
            expected = actual * self.data.efv("soils", "EF4_dry") * 44 / 28 / 1e6
            self.assertAlmostEqual(direct["emissions_Gg"], expected)

    def test_field_fluxes_match_soil_indirect_and_direct_keeps_gross_fon(self):
        for method in manure.NITROGEN_METHODS:
            _, pools = manure.compute(self.data, method=method)
            volatilised = soils.volatilised_n(self.data, pools)
            for source in ("organic", "pasture_cattle", "pasture_other"):
                self.assertAlmostEqual(volatilised[source], pools["field_volat_NH3_N"][source]
                                       + pools["field_volat_NOx_N"][source])
            components = soils.compute(self.data, pools)
            direct = next(c for c in components if c["subitem"] == "Direct N2O - organic manure")
            expected = pools["FON_N"] * self.data.efv("soils", "EF1_dry") * 44 / 28 / 1e6
            self.assertAlmostEqual(direct["emissions_Gg"], expected)

    def test_native_parameter_rerun_conserves_fate_in_each_realisation(self):
        for scale in (0.7, 1.0, 1.3):
            for ef in (0.05, 0.15, 0.3):
                _, pools = manure.rerun_nitrogen(
                    self.data, livestock_scales={"cattle": scale, "buffalo": 2 - scale},
                    factor_values={("nh3_emep_storage", "buffalo"): ef})
                losses = sum(pools[k] for k in ("volat_managed_N", "leach_managed_N",
                                               "n2_managed_N", "n2o_managed_N", "FON_N"))
                self.assertAlmostEqual(pools["managed_N"], losses, delta=2e-6)

    def test_other_losses_reduce_surviving_tan_before_application(self):
        _, pools = manure.compute(self.data)
        for row in pools["by_system"]:
            if row["leach_N"] + row["n2_N"] + row["n2o_N"] > 0:
                stage_end = row["stage_detail"][-1]["remaining_TAN_N"]
                self.assertLess(row["TAN_after_management_N"], stage_end)
            self.assertLessEqual(row["application_NH3_N"], row["TAN_after_management_N"])

    def test_invalid_method_or_factor_is_not_silently_clipped(self):
        with self.assertRaises(ValueError):
            manure.compute(self.data, method="averaged")
        with self.assertRaises(ValueError):
            manure.rerun_nitrogen(self.data, factor_values={("nh3_emep_storage", "buffalo"): 1.1})

    def test_complete_ipcc_alternative_preserves_formulation(self):
        _, pools = manure.compute(self.data, method="ipcc")
        for row in pools["by_system"]:
            factor = self.data.efv("manure_fracgasms", row["class"] + "_" + row["system"])
            self.assertAlmostEqual(row["volat_N"], row["excreted_N"] * factor)


if __name__ == "__main__":
    unittest.main()
