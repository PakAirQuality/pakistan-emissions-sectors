"""The air emission-factor register (rc58 W1): every row cites a held page, converts to a
physical unit, and the rows that duplicate the power module's transcriptions equal them -
one factor, two consumers, no drift."""

from pkinv.assets import asset_path
import os
import unittest

from pkinv.core import air_factors

ROOT = os.path.join(os.path.dirname(__file__), "..")

# register ef_id -> (power dict, key): the AP-42 1.3/1.4 rows both layers transcribed
POWER_ROWS = {
    "ap42_1.4_gas_large_boiler_nox": ("GAS_LB_PER_MMSCF", "NOx"),
    "ap42_1.4_gas_boiler_co": ("GAS_LB_PER_MMSCF", "CO"),
    "ap42_1.4_gas_so2": ("GAS_LB_PER_MMSCF", "SO2"),
    "ap42_1.4_gas_pm_total": ("GAS_LB_PER_MMSCF", "PM"),
    "ap42_1.4_gas_voc": ("GAS_LB_PER_MMSCF", "VOC"),
    "ap42_1.3_no6_util_boiler_nox": ("OIL_LB_PER_KGAL", "NOx"),
    "ap42_1.3_no6_ind_boiler_co": ("OIL_LB_PER_KGAL", "CO"),
    "ap42_1.3_no6_so2_157S": ("OIL_LB_PER_KGAL", "SO2"),
}


class TestTheRegister(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reg = air_factors.load()

    def test_every_held_row_cites_a_document_that_exists_with_its_digest(self):
        import hashlib
        seen = {}
        for r in self.reg.values():
            if r["status"] == "absent" or r["activity_basis"] == "sulfur_balance":
                continue
            path = asset_path(ROOT, r["source_path"])
            self.assertTrue(os.path.exists(path), "%s cites %s, not on disk" % (r["ef_id"], r["source_path"]))
            if path not in seen:
                h = hashlib.sha256()
                with open(path, "rb") as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                seen[path] = h.hexdigest()[:16]
            self.assertEqual(r["source_sha256"], seen[path], "%s: the document changed under its citation" % r["ef_id"])
            self.assertTrue(r["source_table"] and r["source_page"], r["ef_id"])

    def test_every_held_row_converts_to_a_physical_unit(self):
        for r in self.reg.values():
            if r["status"] == "absent":
                with self.assertRaises(air_factors.AbsentFactor):
                    air_factors.kg_per_unit(r)
                continue
            k, unit = air_factors.kg_per_unit(r)
            self.assertGreater(k, 0.0, r["ef_id"])
            self.assertIn(unit, ("TJ_ncv", "TJ_hhv", "t_fuel", "t_brick", "t_clinker", "share_of_PM2.5", "kg_S",
                                 "t_product", "e3m3_gas", "m3_oil"))   # rc59: process, gas-volume and oil-volume bases

    def test_the_rows_the_power_module_also_transcribed_are_equal(self):
        from pkinv.sectors.power import air_pollutants as pap
        for ef_id, (dname, key) in POWER_ROWS.items():
            value = getattr(pap, dname)[key][0]
            self.assertEqual(float(self.reg[ef_id]["value"]), value, ef_id)

    def test_control_states_are_declared_and_closed(self):
        states = {r["control_state"] for r in self.reg.values() if r["status"] != "absent"}
        self.assertTrue(states <= {"uncontrolled", "controlled", "fleet_typical"}, states)
        for r in self.reg.values():
            if r["control_state"] == "controlled":
                self.assertTrue(r["control_device"], "%s: controlled by what?" % r["ef_id"])

    def test_the_uncertainty_is_never_blank_for_a_held_row(self):
        for r in self.reg.values():
            if r["status"] != "absent":
                self.assertGreaterEqual(air_factors.uncert_pct(r), 0.0, r["ef_id"])


if __name__ == "__main__":
    unittest.main()
