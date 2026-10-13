"""What the per-year provincial split of grid power moved, and that it moved nothing else.

WHY THIS EXISTS. At rc66 each grid fuel stopped riding one reference-year provincial vector
and took each year's own stations (pkinv.sectors.power.province_panel). That is a re-base of
provincial numbers. outputs/pakemis_power_provincial_basis_by_year.csv is its record: one row
per fuel, fiscal year and province, with the emissions booked before (release 1.0.0rc65, held
as a pinned baseline) and after, in Mt CO2e on the AR5 basis.

These tests hold the record to three claims a reader of the manuscript will rely on.

1. NO NATIONAL TOTAL MOVED. For every fuel and year the provinces sum to the same number
   before and after. A split may move mass between provinces and may not create or lose any.
2. THE MOVEMENT IS THE ONE THE MANUSCRIPT REPORTED. The largest row is coal in Sindh in
   FY2020-21, 11.63 Mt CO2e: the figure the previous manuscript gave for the exposure of the
   fixed vector. It is now the size of the correction.
3. WHAT IS STILL BORROWED IS NAMED. A fuel-year on the reference vector carries the reason;
   there are few of them and none is coal or gas.
"""
import csv
import hashlib
import io
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

PRODUCT = os.path.join(ROOT, "outputs", "pakemis_power_provincial_basis_by_year.csv")
BASELINE = os.path.join(ROOT, "data", "baselines", "pre_rc66_power_provincial")
PROVINCES = ("Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan", "Other")


def rows():
    with io.open(PRODUCT, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def cells(table):
    out = {}
    for row in table:
        out.setdefault((row["period_id"], row["stream"]), []).append(row)
    return out


def unconserved(table, tolerance=5e-6):
    """Fuel-years whose provinces do not sum to the same total before and after.

    The tolerance is the product's own print precision: ten figures at six decimals can
    differ by 5e-6 in their sums when the quantities behind them are equal. The build makes
    the same check on the unrounded masses at 1e-6 and refuses to write on a failure."""
    out = []
    for key, group in sorted(cells(table).items()):
        before = sum(float(r["co2e_Mt_AR5_before"]) for r in group)
        after = sum(float(r["co2e_Mt_AR5_after"]) for r in group)
        if abs(before - after) > tolerance:
            out.append("%s %s: %.6f before, %.6f after" % (key + (before, after)))
    return out


class TestTheReBaseMovedProvincesAndNothingElse(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(PRODUCT):
            raise unittest.SkipTest("the product has not been built in this checkout")
        cls.rows = rows()

    def test_every_fuel_year_has_five_provinces(self):
        for key, group in cells(self.rows).items():
            self.assertEqual([r["province"] for r in group], list(PROVINCES), key)

    def test_no_national_total_moved(self):
        self.assertFalse(unconserved(self.rows), "\n  ".join(unconserved(self.rows)))

    def test_the_check_would_see_a_total_that_moved(self):
        """THE POSITIVE CONTROL: one province's mass changed and not given to another."""
        broken = [dict(r) for r in self.rows]
        broken[0]["co2e_Mt_AR5_after"] = "%.6f" % (float(broken[0]["co2e_Mt_AR5_after"]) + 0.01)
        self.assertEqual(len(unconserved(broken)), 1)

    def test_differences_are_after_minus_before_and_net_to_zero(self):
        for key, group in cells(self.rows).items():
            for r in group:
                self.assertAlmostEqual(
                    float(r["difference_Mt_CO2e"]),
                    float(r["co2e_Mt_AR5_after"]) - float(r["co2e_Mt_AR5_before"]), places=5)
            self.assertAlmostEqual(sum(float(r["difference_Mt_CO2e"]) for r in group), 0.0,
                                   places=5, msg=key)

    def test_the_largest_movement_is_the_one_the_manuscript_reported(self):
        worst = max(self.rows, key=lambda r: abs(float(r["difference_Mt_CO2e"])))
        self.assertEqual((worst["period_id"], worst["stream"], worst["province"]),
                         ("FY2020-21", "power_coal", "Sindh"))
        self.assertAlmostEqual(float(worst["difference_Mt_CO2e"]), -11.634, delta=0.01)

    def test_the_reference_year_moves_only_as_declared(self):
        """FY2023-24: coal moves by the change of calorific basis (about 0.17 Mt to
        Balochistan) and bagasse by three plants' provinces. Gas, furnace oil and diesel are
        the committed rows and must not move at all."""
        reference = [r for r in self.rows if r["period_id"] == "FY2023-24"]
        for r in reference:
            moved = abs(float(r["difference_Mt_CO2e"]))
            if r["stream"] in ("power_gas", "power_rfo", "power_hsd"):
                self.assertLess(moved, 5e-6, (r["stream"], r["province"]))
            elif r["stream"] == "power_coal":
                self.assertLess(moved, 0.2, r["province"])
            else:
                self.assertLess(moved, 0.01, r["province"])
            self.assertEqual(r["basis_class"], "reference_year_row")

    def test_what_is_still_borrowed_is_named_and_is_not_coal_or_gas(self):
        borrowed = sorted({(r["period_id"], r["stream"], r["fallback_reason"])
                           for r in self.rows if r["basis_class"] == "reference_vector_fallback"})
        for period, stream, reason in borrowed:
            self.assertTrue(reason.strip(), "%s %s is borrowed with no reason" % (period, stream))
            self.assertNotIn(stream, ("power_coal", "power_gas"),
                             "%s %s fell back to the reference vector: %s"
                             % (period, stream, reason))
        self.assertLessEqual(len(borrowed), 3, borrowed)

    def test_every_row_states_its_basis(self):
        classes = {"own_year_fuel_quantity", "own_year_booked_energy", "own_year_generation",
                   "reference_year_row", "reference_vector_fallback", "not_applicable"}
        for r in self.rows:
            self.assertIn(r["basis_class"], classes)
            if r["basis_class"] != "not_applicable":
                self.assertTrue(r["basis"].strip(), (r["period_id"], r["stream"]))

    def test_the_baseline_is_the_file_that_was_pinned(self):
        with open(os.path.join(BASELINE, "SHA256SUMS"), encoding="utf-8") as handle:
            pinned = dict(reversed(line.split()) for line in handle if line.strip())
        self.assertEqual(len(pinned), 2)
        for name, digest in pinned.items():
            with open(os.path.join(BASELINE, name), "rb") as handle:
                self.assertEqual(hashlib.sha256(handle.read()).hexdigest(), digest, name)

    def test_it_regenerates_identically(self):
        before = open(PRODUCT, "rb").read()
        run = subprocess.run([sys.executable, "-m", "pkinv.report.power_provincial_basis"],
                             cwd=ROOT, capture_output=True, text=True,
                             env=dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src")))
        self.assertEqual(run.returncode, 0, run.stderr[-2000:])
        self.assertEqual(before, open(PRODUCT, "rb").read())


if __name__ == "__main__":
    unittest.main()
