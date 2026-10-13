"""Configuration L on the grid: the same dispatch, two masses, and every gas conserved.

WHY (rc41, the nineteenth review's S-1). The second configuration's ADM2 product was every
residential row rescaled by one per-province CO2e ratio built on a proxy the reference no
longer used; it moved CO2 by -3,206.85 Gg, CH4 by +101.47 Gg and N2O by +1.35 Gg against
its monthly product while its CO2e aggregate looked right. grid_cube now builds the second
configuration through the same per-stream loop as the reference with the residential
streams' own masses, and these tests hold what that must mean: the weights are the
reference's by identity, L - REF is the two dung-cake streams' difference and nothing
else, CO2 is bit-identical, and the shipped L products close per gas at every level
(grid, ADM1, ADM2 + OUTSIDE).

rc67 (2026-10-13). Through rc66 the second configuration was S, the survey reading, and
the reference was the ledger. The roles swapped: the reference carries the survey's dung
and the second configuration is L, the ledger. This file was test_grid_cube_ledger.py;
every "S" below became "L", and the one thing that is not a rename is the SIGN - L burns
more dung than the reference, so L - REF is positive where S - REF was negative.
"""

from pkinv.assets import asset_path
import os
import unittest

from pkinv.core.io import read_rows
from _support import DATA, OUT
from _support import cached_build

try:
    import numpy as np
    HAVE_NUMPY = True
except ImportError:
    HAVE_NUMPY = False

CACHES = all(os.path.exists(asset_path(DATA, "gis", "proxy_%s_267x340.npy" % n))
             for n in ("cropland", "builtup", "population", "glw_livestock", "manure_applied"))


def _rows(name):
    return read_rows(os.path.join(OUT, name))


@unittest.skipUnless(HAVE_NUMPY and CACHES, "gis extra or committed proxy caches absent")
class TestConfigurationLOnTheGrid(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        from pkinv.report import grid_cube
        cls.gc = grid_cube
        cls.ref = cached_build()
        cls.led = cls.ref["ledger"]

    def _dung_delta(self):
        """{(gas, month): L - REF} from the two L streams against their reference streams."""
        ref = {s["source_stream_id"]: s for s in self.ref["streams"]}
        out = {}
        for s in self.led["streams"]:
            if s["module"] != "residential":
                continue
            base = ref[s["source_stream_id"]]
            for month in self.gc.MONTHS:
                out[(s["gas"], month)] = out.get((s["gas"], month), 0.0) + (
                    s["emissions_Gg"] - base["emissions_Gg"]) * s["monthly_share"].get(month, 0.0)
        return out

    def test_l_differs_in_exactly_two_streams(self):
        ref = {s["source_stream_id"]: s["emissions_Gg"] for s in self.ref["streams"]}
        moved = sorted(s["source_stream_id"] for s in self.led["streams"]
                       if abs(s["emissions_Gg"] - ref[s["source_stream_id"]]) > 1e-9)
        self.assertEqual(moved, ["residential|residential-fuel-combustion|dung-cake-ch4|ch4",
                                 "residential|residential-fuel-combustion|dung-cake-n2o|n2o"])

    def test_the_weights_are_the_reference_weights(self):
        """Asserted inside build() by identity; re-asserted through the marginals so a
        refactor that rebuilt a weight for L would fail here too."""
        for sid, marginals in self.led["marginals"].items():
            self.assertEqual(marginals, self.ref["marginals"][sid], sid)

    def test_l_minus_ref_is_the_dung_difference_per_gas_and_month(self):
        delta = self._dung_delta()
        for gas in self.gc.GASES:
            for index, month in enumerate(self.gc.MONTHS):
                got = float((self.led["gas_month"][gas][index] - self.ref["gas_month"][gas][index]).sum())
                self.assertLess(abs(got - delta.get((gas, month), 0.0)), 1e-9,
                                "%s %s: L - REF %.9f vs dung difference %.9f"
                                % (gas, month, got, delta.get((gas, month), 0.0)))

    def test_l_is_the_larger_side_in_every_month(self):
        """The sign of the swap. The ledger burns 58.74 Mt of cake and the reference the
        survey's 10.93, so both dung streams are larger under L by the same ratio, and
        the CH4 and N2O layers exceed the reference in every month. Through rc66 the
        second configuration was the smaller side; a build that still returned it under
        the new key would pass every conservation test in this file and fail here."""
        ref = {s["source_stream_id"]: s["emissions_Gg"] for s in self.ref["streams"]}
        ratios = [s["emissions_Gg"] / ref[s["source_stream_id"]]
                  for s in self.led["streams"] if "dung-cake" in s["source_stream_id"]]
        self.assertEqual(len(ratios), 2)
        for ratio in ratios:
            self.assertAlmostEqual(ratio, 58.7414 / 10.9334, places=3)
        for gas in ("CH4", "N2O"):
            for index, month in enumerate(self.gc.MONTHS):
                self.assertGreater(float(self.led["gas_month"][gas][index].sum()),
                                   float(self.ref["gas_month"][gas][index].sum()),
                                   "%s %s" % (gas, month))

    def test_the_two_cubes_name_their_own_dung_axis(self):
        """residential_dung_axis is "S" on the reference file and "L" on the ledger file,
        and the delta between them is published as ledger_configuration_delta (positive,
        5.24626 Mt CO2e AR5, the residential difference). Through rc66 the attribute was
        survey_configuration_delta and the axis letters were the other way round."""
        try:
            from netCDF4 import Dataset
        except ImportError:
            self.skipTest("netCDF4 not installed")
        with Dataset(os.path.join(OUT, "pakemis_grid_0p05_monthly.nc")) as ds:
            self.assertEqual(ds.scenario_id, "REF_2023_24")
            self.assertEqual(ds.residential_dung_axis, "S")
            reference_delta = float(ds.ledger_configuration_delta_Mt_co2e_AR5)
            self.assertFalse(hasattr(ds, "survey_configuration_delta_Mt_co2e_AR5"))
        with Dataset(os.path.join(OUT, "pakemis_grid_0p05_monthly_ledger.nc")) as ds:
            self.assertEqual(ds.scenario_id, "L_2023_24")
            self.assertEqual(ds.residential_dung_axis, "L")
            self.assertIn("configuration L", ds.title)
            self.assertFalse(hasattr(ds, "survey_configuration_delta_Mt_co2e_AR5"))
            self.assertEqual(float(ds.ledger_configuration_delta_Mt_co2e_AR5),
                             reference_delta)
        self.assertGreater(reference_delta, 0.0)
        self.assertAlmostEqual(reference_delta, 5.24626, places=5)

    def test_co2_is_bit_identical(self):
        self.assertTrue(np.array_equal(self.led["gas_month"]["CO2"], self.ref["gas_month"]["CO2"]))
        for key, surface in self.ref["category_annual"].items():
            if key[2] == "CO2":
                self.assertTrue(np.array_equal(surface, self.led["category_annual"][key]), key)

    def test_non_residential_cells_are_bit_identical(self):
        for key, surface in self.ref["category_annual"].items():
            if key[0] != "residential":
                self.assertTrue(np.array_equal(surface, self.led["category_annual"][key]), key)

    def test_the_shipped_l_cube_closes_to_adm1_per_gas_and_month(self):
        try:
            from netCDF4 import Dataset
        except ImportError:
            self.skipTest("netCDF4 not installed")
        adm1 = {}
        for r in _rows("pakemis_adm1_ledger_2024.csv"):
            adm1[(r["gas"], r["month"])] = adm1.get((r["gas"], r["month"]), 0.0) + float(r["emissions_Gg"])
        national = {}
        for r in _rows("pakemis_monthly_ledger_2024.csv"):
            national[(r["gas"], r["month"])] = national.get((r["gas"], r["month"]), 0.0) + float(r["emissions_Gg"])
        ref_monthly = {}
        for r in _rows("national_monthly_2024.csv"):
            if r["sector"] != "residential":
                ref_monthly[(r["gas"], r["month"])] = ref_monthly.get((r["gas"], r["month"]), 0.0) + float(r["emissions_Gg"])
        unallocated = {}
        for r in _rows("pakemis_spatial_unallocated.csv"):
            unallocated[(r["gas"], r["month"])] = unallocated.get((r["gas"], r["month"]), 0.0) + float(r["emissions_Gg"])
        with Dataset(os.path.join(OUT, "pakemis_grid_0p05_monthly_ledger.nc")) as ds:
            self.assertEqual(ds.scenario_id, "L_2023_24")
            self.assertIn("dung-cake", ds.differs_from_reference)
            for gas in self.gc.GASES:
                layer = ds.variables[gas.lower() + "_Gg"][:]
                for index, month in enumerate(self.gc.MONTHS):
                    # the L grid == every non-residential stream at the reference + residential
                    # at L, less the unallocated mass (none is residential)
                    expected = ref_monthly[(gas, month)] + national[(gas, month)] - unallocated.get((gas, month), 0.0)
                    got = float(layer[index].sum())
                    self.assertLess(abs(got - expected), max(1e-5 * expected, 1e-5),
                                    "%s %s: L grid %.6f vs %.6f" % (gas, month, got, expected))
                    # the national L is the 8-dp product's sum; ADM1 is the engine's mass at
                    # the reference shares - relative tolerance, the in-memory tier
                    self.assertLess(abs(adm1[(gas, month)] - national[(gas, month)]),
                                    max(1e-6 * national[(gas, month)], 1e-6),
                                    "%s %s: ADM1 L does not close to the national L" % (gas, month))

    def test_the_shipped_l_adm2_rows_close_to_adm1_per_stream(self):
        adm1 = {}
        for r in _rows("pakemis_adm1_ledger_2024.csv"):
            key = (r["source_stream_id"], r["month"])
            adm1[key] = adm1.get(key, 0.0) + float(r["emissions_Gg"])
        adm2 = {}
        for r in _rows("pakemis_adm2_ledger_2024.csv"):
            if r["absence_reason"]:
                self.assertEqual(r["emissions_Gg"], "")
                continue
            key = (r["source_stream_id"], r["month"])
            adm2[key] = adm2.get(key, 0.0) + float(r["emissions_Gg"])
        self.assertEqual(set(adm1), set(adm2))
        for key, total in adm1.items():
            self.assertLess(abs(adm2[key] - total), max(1e-6 * total, 1e-6), key)


if __name__ == "__main__":
    unittest.main()
