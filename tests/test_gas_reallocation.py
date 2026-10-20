"""The gas-reallocation application: what its change means, held to the things a reader relies on.

WHY. The application (src/pkinv/applications/gas_reallocation/) reports a CHANGE: what moving the
two network-supplied urea plants' gas to grid power does to emissions while urea and electricity are
held fixed. A change is only as good as four properties, each tested here:
- the services really are held fixed in both states, and nothing flows backwards;
- the two states share their uncertain inputs (paired draws), so a shared parameter cancels;
- an absence stays an absence: a process with no held factor is NE in every product, never zero;
- the inventory is untouched: every factor the application uses is read from the inventory's own
  rows, and the application writes only its own products.
INTERNAL consistency (these tests) is not validation. The independent checks (NFDC against OGRA,
the company's ammonia, a second year's plant meters) are in the shipped checks table and are held
here only to have run and passed.
"""
import csv
import io
import os
import sys
import unittest

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.applications.gas_reallocation import build, inputs, model     # noqa: E402
from pkinv.core import io as core_io                                     # noqa: E402
from pkinv.core.units import TJ_PER_MMBTU                                # noqa: E402
from pkinv.sectors.ippu import ammonia_reconciliation                     # noqa: E402

OUT = os.path.join(ROOT, "outputs")
PRODUCTS = ("sources", "flows", "baselines", "matrix", "sectors", "thresholds", "conclusions", "checks")
N = 400


def _rows(name):
    with open(os.path.join(OUT, build.PREFIX + name + ".csv"), encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rec = model.Records()


class InventoryIsReadNotCopied(Base):
    def test_every_inventory_reference_resolves_to_the_inventory_value(self):
        for row in inputs.table("parameter_ranges.csv"):
            if row["inventory_ref"]:
                self.assertEqual(row["value"], "", "%s carries a typed copy of an inventory factor"
                                 % row["parameter_id"])
                value, _pct = inputs.inventory_value(row["inventory_ref"])
                self.assertEqual(self.rec.params[row["parameter_id"]]["value"], value)

    def test_ipcc_gas_range_is_the_inventory_pair(self):
        p = self.rec.params
        self.assertEqual(p["ammonia_ef_ipcc_gas"]["low"], p["ammonia_ef_modern"]["value"])
        self.assertEqual(p["ammonia_ef_ipcc_gas"]["high"], p["ammonia_ef_total_energy"]["value"])

    def test_urea_carbon_constant_is_the_inventory_constant(self):
        self.assertIs(model.UREA_CO2, ammonia_reconciliation.UREA_CO2_RECOVERY)

    def test_reference_fertilizer_reading_is_the_inventory_method(self):
        """FA1 per tonne of urea is the 2.B.1 engine's identity: 0.567 x 1.815 - 44/60."""
        d = model.Draws(self.rec.params, self.rec.factors, 10)
        st = model.state(d, self.rec, ("FA1", "PA1", "R1", "D1", "F1"), 1.0, 0.0)
        expect = self.rec.urea_kt * (self.rec.params["nh3_per_urea"]["value"] * d.get("ammonia_ef_calibrated")
                                     - 44.0 / 60.0)
        np.testing.assert_allclose(st["2B1"]["CO2"], expect)

    def test_application_writes_only_its_own_products(self):
        written = []
        real = build.write_table
        build.write_table = lambda path, *a, **k: written.append(path)
        try:
            build.main(["--draws", "200"])
        finally:
            build.write_table = real
        self.assertEqual(len(written), len(PRODUCTS))
        for path in written:
            self.assertTrue(os.path.basename(path).startswith(build.PREFIX), path)
            self.assertEqual(os.path.dirname(os.path.abspath(path)), os.path.abspath(OUT))


class Units(Base):
    def test_mmcf_times_btu_per_scf_is_mmbtu_and_pj(self):
        d = model.Draws(self.rec.params, self.rec.factors, 50)
        st = model.state(d, self.rec, ("FA1", "PA1", "R1", "D1", "F1"), 1.0, 1.0)
        mmcf = self.rec.feed + self.rec.fuel
        np.testing.assert_allclose(st["flows"]["gas_moved_pj_hhv"],
                                   mmcf * d.get("hhv_network_btu_scf") * TJ_PER_MMBTU / 1e3)
        self.assertAlmostEqual(TJ_PER_MMBTU, 1.05505585262e-3)

    def test_heating_value_mode_is_the_plants_own_records(self):
        mode = model.hhv_mode(self.rec.params)
        gas = self.rec.gas["Fatimafert"]
        index = (28.93 + 28.70) / 2
        self.assertAlmostEqual(mode, index * 1e6 / ((gas["feed"] + gas["fuel"]) / self.rec.urea["Fatimafert"] * 1000))
        self.assertTrue(900 <= mode <= 1000)

    def test_ledger_and_heat_rate_readings_agree_at_the_rlng_stations(self):
        """PA1 and PA2 are two records of the same stations; at R1 they agree within 6%."""
        rows = {(r["baseline_id"], r["axis"]): float(r["p50"]) for r in _rows("baselines") if r["p50"]}
        pa1, pa2 = rows[("PA1", "power_conversion:R1")], rows[("PA2", "power_conversion:R1")]
        self.assertLess(abs(pa1 - pa2) / pa2, 0.06)


class Services(Base):
    def test_services_held_and_flows_non_negative_in_every_case(self):
        for case, _role in build.cases():
            base, tran, _d = model.run(self.rec, case, 1.0, N)
            fb, ft = base["flows"], tran["flows"]
            np.testing.assert_allclose(fb["urea_domestic_kt"] + fb["urea_imported_kt"],
                                       ft["urea_domestic_kt"] + ft["urea_imported_kt"], atol=1e-9)
            np.testing.assert_allclose(fb["gwh_receiving"] + fb["gwh_displaced_running"],
                                       ft["gwh_receiving"] + ft["gwh_displaced_running"], atol=1e-6)
            for flows in (fb, ft):
                for name, value in flows.items():
                    self.assertTrue(np.all(np.asarray(value) >= -1e-9), "%s %s negative" % (case, name))

    def test_oil_stations_cannot_absorb_all_the_gas(self):
        """An operating limit the records impose: FY2023-24 oil generation is smaller than the GWh
        the plants' gas would make, so D1 and D2 are feasible only for part of the gas."""
        flows = [r for r in _rows("flows") if r["item"] == "case"]
        for r in flows:
            displaced = r["name"].split()[2]
            if displaced in ("D1", "D2"):
                self.assertLess(float(r["max_feasible_fraction"]), 1.0, r["name"])
                self.assertEqual(r["feasible_at_full_scope"], "no")

    def test_urea_application_is_unchanged(self):
        base, tran, _d = model.run(self.rec, ("FA2", "PA2", "R2", "D3", "F2"), 1.0, N)
        for gas in ("CO2", "N2O", "NH3"):
            np.testing.assert_array_equal(base["3C_urea"][gas], tran["3C_urea"][gas])


class Accounting(Base):
    def test_zero_intervention_is_zero_change(self):
        for case, _role in build.cases():
            base, tran, _d = model.run(self.rec, case, 0.0, 50)
            for key, *_ in model.SECTORS:
                for pol, vb in base[key].items():
                    vt = tran[key][pol]
                    if vb is not None and vt is not None:
                        np.testing.assert_array_equal(vb, vt)

    def test_the_same_case_twice_is_the_same_result(self):
        a = model.run(self.rec, ("FA1", "PA2", "R1", "D2", "F1"), 1.0, 300)
        b = model.run(self.rec, ("FA1", "PA2", "R1", "D2", "F1"), 1.0, 300)
        np.testing.assert_array_equal(model.co2e(a[1]["1A1a_disp"]), model.co2e(b[1]["1A1a_disp"]))

    def test_carbon_balance_of_the_gas_reading(self):
        d = model.Draws(self.rec.params, self.rec.factors, 200)
        st = model.state(d, self.rec, ("FA2", "PA1", "R1", "D1", "F1"), 1.0, 0.0)
        h, g2n, ls = d.get("hhv_network_btu_scf"), d.get("gross_to_net"), self.rec.leak_share
        carbon = (self.rec.feed + self.rec.fuel * (1 - ls)) * h * TJ_PER_MMBTU * g2n * d.get("ef_co2_gas") / 1e6
        np.testing.assert_allclose(carbon, st["2B1"]["CO2"] + self.rec.urea_kt * 44.0 / 60.0)

    def test_urea_bound_carbon_is_counted_once(self):
        """The exporter books its ammonia CO2 net of the CO2 bound into urea; that CO2 is released on
        Pakistani fields (3.C.3), which do not change, so it is in neither the external term twice nor
        the territorial term."""
        d = model.Draws(self.rec.params, self.rec.factors, 100)
        nh3 = d.get("nh3_per_urea")
        gross = nh3 * d.get("ammonia_ef_ipcc_gas", use="exporter") + nh3 * d.get(
            "ammonia_fuel_req_gas", use="exporter") * d.get("wtt_natural_gas") / 1e3
        np.testing.assert_allclose(model.import_factor(d, "F1"), gross - 44.0 / 60.0)

    def test_process_fuel_co2_is_not_booked_twice(self):
        base, _tran, _d = model.run(self.rec, ("FA1", "PA1", "R1", "D1", "F1"), 1.0, 50)
        self.assertNotIn("CO2", base["2B1_fuel"])

    def test_paired_draws_give_a_narrower_change_than_independent_ones(self):
        case = ("FA2", "PA1", "R1", "D1", "F1")
        widths = []
        for paired in (True, False):
            base, tran, _d = model.run(self.rec, case, 1.0, 3000, paired=paired)
            delta, *_ = build._aggregate(base, tran, "territorial", "CO2e_AR5")
            widths.append(np.percentile(delta, 97.5) - np.percentile(delta, 2.5))
        self.assertLess(widths[0], widths[1])

    def test_identical_fuel_on_both_sides_cancels(self):
        """Under D4 no station changes, so station combustion cancels exactly."""
        base, tran, _d = model.run(self.rec, ("FA1", "PA1", "none", "D4", "F1"), 1.0, 100)
        for key in ("1A1a_recv", "1A1a_disp"):
            np.testing.assert_array_equal(model.co2e(base[key]), model.co2e(tran[key]))

    def test_a_fraction_outside_the_plants_gas_is_refused(self):
        with self.assertRaises(ValueError):
            model.run(self.rec, ("FA1", "PA1", "R1", "D1", "F1"), 1.5, 10)


class Absences(Base):
    def test_not_estimated_stays_not_estimated(self):
        base, tran, _d = model.run(self.rec, ("FA1", "PA1", "R1", "D1", "F1"), 1.0, 50)
        self.assertIsNone(base["1A1a_recv"]["BC"])           # EMEP prints no gas-turbine BC
        delta, _b, _t, missing = build._aggregate(base, tran, "territorial", "BC")
        self.assertIn("1A1a_recv", [k for k, _d in missing])
        for row in _rows("matrix"):
            if row["coverage"] == "NE":
                self.assertEqual(row["delta_mean"], "")
            if row["delta_mean"] == "":
                self.assertEqual(row["coverage"], "NE")

    def test_a_not_estimated_part_that_could_reverse_the_sign_makes_it_unresolved(self):
        rows = {(r["boundary"], r["pollutant"], r["scope"]): r for r in _rows("conclusions")}
        bc = rows[("territorial", "BC", "all evidence pathways")]
        self.assertEqual(bc["classification"], "unresolved")
        self.assertIn("not-estimated", bc["condition"])


class Products(unittest.TestCase):
    def test_every_product_exists_with_a_banner(self):
        for name in PRODUCTS:
            path = os.path.join(OUT, build.PREFIX + name + ".csv")
            with open(path, encoding="utf-8") as handle:
                self.assertTrue(handle.readline().startswith("# PAKEMIS GAS-REALLOCATION APPLICATION"), name)

    def test_shipped_products_are_the_reported_run_and_reproduce(self):
        captured = {}
        real = build.write_table
        build.write_table = lambda path, fields, rows, banner=None, **k: captured.__setitem__(
            path, core_io.table_text(fields, rows, banner))
        try:
            code = build.main([])
        finally:
            build.write_table = real
        self.assertEqual(code, 0, "a check in the checks table failed")
        for path, text in captured.items():
            with open(path, encoding="utf-8", newline="") as handle:
                self.assertEqual(handle.read(), text, "%s does not reproduce; rebuild with make gas-pilot" % path)
        self.assertNotIn("DEVELOPMENT SAMPLE", "".join(captured.values()))

    def test_every_check_passed(self):
        for row in _rows("checks"):
            self.assertIn(row["result"], ("PASS", "INFO"), row["check"])

    def test_classification_vocabulary_is_closed(self):
        allowed = {"robust reduction", "robust increase", "conditional", "unresolved", "no change",
                   "trade-off", "no trade-off"}
        for row in _rows("conclusions"):
            self.assertIn(row["classification"], allowed)

    def test_no_probability_is_put_on_a_baseline_or_pathway(self):
        """p_reduction is conditional on one case; nothing averages over cases."""
        for name in PRODUCTS:
            header = _rows(name)[0].keys() if _rows(name) else ()
            for column in header:
                self.assertNotIn("weight", column)
                self.assertNotIn("pooled", column)


if __name__ == "__main__":
    unittest.main()
