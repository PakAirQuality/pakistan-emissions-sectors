"""The implied-coal-CV channel - the invariants that make the arbitration citable.

Three layers, in evidentiary order: the PDF is the audited one; the parser reproduces
printed cells before anything consumes them; and the findings themselves - the circularity
structure and the arbitration direction - are regression-pinned so a silent change in an
input turns into a loud test failure rather than a quietly different conclusion.

Run:  python3 -m unittest discover tests -p "test_power_implied_cv.py"
"""
import csv
import hashlib
import os
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)

from pkinv.paths import DATA
from pkinv.sectors.power import implied_cv
from pkinv.sectors.power.data import PowerData
from pkinv.core.io import read_rows

PDF = os.path.join(os.path.dirname(DATA), "sources", "Power Plants",
                   "NEPRA State of Industry Report 2024.pdf")

# Pinned from the committed source. A hash mismatch is a re-audit instruction: every
# printed-cell pin below was read from THIS file.
EXPECTED_SHA256 = "ba8acb6b7ed04cda"


def _hr():
    return read_rows(implied_cv.HR_CSV, comments=False)


def _cell(rows, plant, year, col, fuel_column=""):
    for r in rows:
        if (r["plant"] == plant and int(r["fiscal_year"]) == year
                and r["fuel_column"] == fuel_column):
            return r[col]
    return None


class TestPayload(unittest.TestCase):
    def test_the_pdf_is_the_audited_one(self):
        require_documents("sources/Power Plants/NEPRA State of Industry Report 2024.pdf")
        h = hashlib.sha256()
        with open(PDF, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        self.assertEqual(h.hexdigest()[:16], EXPECTED_SHA256)


class TestParser(unittest.TestCase):
    """Printed cells, reproduced. Each pin was read by eye from the layout text."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _hr()

    def test_operational_coal_row(self):
        self.assertEqual(_cell(self.rows, "Engro Powergen Thar", 2022,
                               "hr_gross_btu_kwh"), "8799.7")
        self.assertEqual(_cell(self.rows, "Engro Powergen Thar", 2022,
                               "hr_net_btu_kwh"), "9716.1")

    def test_np_cells_stay_positional(self):
        """Sahiwal prints n.p. in its net columns; dropping the token would slide
        efficiency into the heat-rate slot."""
        self.assertEqual(_cell(self.rows, "Huaneng Shandong Ruyi (Sahiwal Imported Coal)",
                               2019, "hr_gross_btu_kwh"), "8749.08")
        self.assertEqual(_cell(self.rows, "Huaneng Shandong Ruyi (Sahiwal Imported Coal)",
                               2019, "hr_net_btu_kwh"), "")
        self.assertEqual(_cell(self.rows, "Huaneng Shandong Ruyi (Sahiwal Imported Coal)",
                               2021, "eff_net_pct"), "42.94")

    def test_the_impossible_rows_are_noted_not_corrected(self):
        """Thar Coal Block-I prints net BELOW gross in both years. The cells stay as
        printed and the note says why that cannot be physics."""
        for year in (2022, 2023):
            self.assertEqual(_cell(self.rows, "Thar Coal Block-I", year,
                                   "hr_gross_btu_kwh"), "8749.0")
            self.assertEqual(_cell(self.rows, "Thar Coal Block-I", year,
                                   "hr_net_btu_kwh"), "8648.63")
            self.assertIn("impossible", _cell(self.rows, "Thar Coal Block-I", year, "note"))

    def test_the_dual_fuel_subtable_splits(self):
        self.assertEqual(_cell(self.rows, "Saif", 2023, "hr_gross_btu_kwh", "Gas"),
                         "6466.0")
        self.assertEqual(_cell(self.rows, "Saif", 2023, "hr_gross_btu_kwh", "HSD"),
                         "6825.0")

    def test_the_delicensed_row_is_absent(self):
        """GTPS Faisalabad 2022-23 prints 'Plant de-licensed.' - free text, not data."""
        self.assertIsNone(_cell(self.rows, "GTPS Faisalabad (GENCO-III)", 2022,
                                "hr_gross_btu_kwh"))

    def test_the_basis_distinction_is_preserved(self):
        """Table 28 prints LHV; for 20/23 the footnote testifies it. Not the same claim."""
        self.assertEqual(_cell(self.rows, "Bin Qasim TPS-III", 2023, "hr_basis"), "LHV")
        self.assertEqual(_cell(self.rows, "Uch", 2023, "hr_basis"),
                         "LHV-per-KE-footnote")


class TestCoverage(unittest.TestCase):
    def test_27_of_29_coal_plant_years(self):
        """Every ledger coal plant-year joins a heat-rate row except Engro Powergen Thar
        FY2019 and FY2020, which Table 23 simply does not print."""
        rows = implied_cv.implied_coal_cv(PowerData())
        self.assertEqual(len(rows), 29)
        missing = [(r["plant"], r["fiscal_year"]) for r in rows
                   if r["evidence_class"] == "no-hr"]
        self.assertEqual(sorted(missing),
                         [("Engro Powergen Thar", 2019), ("Engro Powergen Thar", 2020)])


class TestFindings(unittest.TestCase):
    """The conclusions, pinned. If an input changes under these, the paper's claims are
    stale and the failure message says which one."""

    @classmethod
    def setUpClass(cls):
        cls.data = PowerData()
        cls.cv = implied_cv.implied_coal_cv(cls.data)
        cls.circ = implied_cv.circularity(cls.data)

    def test_cv_sanity_band_with_exactly_the_two_known_outliers(self):
        outliers = sorted((r["plant"], r["fiscal_year"]) for r in self.cv
                          if r["evidence_class"] == "outlier")
        self.assertEqual(outliers,
                         [("China Power Hub", 2023),
                          ("Huaneng Shandong Ruyi (Sahiwal Imported Coal)", 2021)])
        for r in self.cv:
            if r["evidence_class"] in ("operational-net", "design-flat", "gross-only"):
                self.assertTrue(5.0 <= float(r["implied_cv_TJ_per_Gg"]) <= 30.0,
                                msg="%s FY%d" % (r["plant"], r["fiscal_year"]))

    def test_thar_lands_on_ipcc_lignite(self):
        """The arbitration's core: NEPRA's own heat-rate channel puts Thar coal at an IPCC
        lignite NCV, not the bituminous-like value Table 3's conversion implies."""
        f = implied_cv.fleet_cv(self.data, 2023)
        self.assertTrue(10.5 <= f["thar_cv"] <= 12.5, "Thar CV %.2f" % f["thar_cv"])
        self.assertTrue(19.0 <= f["imported_cv"] <= 25.0)

    def test_the_direction_of_the_disagreement(self):
        """FY2022 and FY2023 - the two years with ~full coverage - both put Table 3's
        implied NCV far above the plant channel."""
        for year, floor in ((2022, 1.4), (2023, 1.7)):
            f = implied_cv.fleet_cv(self.data, year)
            self.assertGreater(f["covered_share"], 0.98, "FY%d coverage" % year)
            self.assertGreater(f["table3_over_fleet"], floor, "FY%d" % year)

    def test_lucky_electric_reads_lignite(self):
        """The ledger's one unresolved coal origin: its implied CV sits in the lignite
        band all three years, evidence for the blend's upper bound."""
        for r in self.cv:
            if r["plant"] == "Lucky Electric" and r["implied_cv_TJ_per_Gg"]:
                self.assertTrue(10.5 <= float(r["implied_cv_TJ_per_Gg"]) <= 13.0,
                                msg="FY%d" % r["fiscal_year"])

    def test_circularity_structure(self):
        """Three behaviours, each pinned: exactly three plants are fully circular (their
        printed net HR IS the ledger ratio); Uch/Uch-II sit on the gas HHV/LHV factor; and
        no coal plant is in the circular set (coal HRs are not recomputed fuel rows)."""
        identical = {c["plant"] for c in self.circ if c["verdict"] == "identical"}
        self.assertEqual(identical,
                         {"Liberty Daharki", "Sindh Nooriabad-I", "Sindh Nooriabad-II"})
        for c in self.circ:
            if c["plant"] in ("Uch", "Uch-II"):
                self.assertEqual(c["verdict"], "same-meters-LHV",
                                 msg="%s FY%d" % (c["plant"], c["fiscal_year"]))
                self.assertTrue(1.09 <= float(c["ratio_net"]) <= 1.12)

    def test_the_ledger_heat_rate_is_derived_not_independent(self):
        """plant_fuel_ledger's implied_heat_rate column is quantity/GWh by construction.
        Anyone treating it as a second channel would be counting one meter twice."""
        from pkinv.sectors.power import plant_ledger
        for r in plant_ledger.rows(2023):
            if r["implied_heat_rate_kJ_per_kWh"] and r["quantity_unit"] == "MMBTU":
                q, g = float(r["quantity"]), float(r["net_generation_GWh"])
                derived = q * 1.05505585262e-3 * 1e9 / (g * 1e6)
                self.assertAlmostEqual(float(r["implied_heat_rate_kJ_per_kWh"]) / derived,
                                       1.0, places=3, msg=r["plant"])

    def test_the_sensitivity_is_a_row_not_the_estimate(self):
        """The restated-coal case must appear in power_totals as a labelled sensitivity, and
        the headline categories must not move with it.

        THE GAP THIS USED TO ASSERT HAS CLOSED, AND THAT IS THE RESULT. While the reference
        was NEPRA Table 3's coal energy the heat-rate restatement sat 19.4 Mt below it, and
        "far below the headline" was the honest description. The reference is now the
        stations' own metered coal at IPCC rank defaults, and the restatement sits 1.59 Mt
        below THAT - because the two routes take the same mass and differ only in where the
        calorific value comes from. A threshold of 10 Mt would now be asserting that the
        re-base did not happen.

        What still has to hold is the thing the test is named for: the restatement is a
        LABELLED ROW and not the estimate, and it is a distinct number from the headline.
        """
        path = os.path.join(os.path.dirname(DATA), "outputs", "power_totals_fy2023_24.csv")
        with open(path, newline="", encoding="utf-8") as f:
            rows = {r["category"]: float(r["co2e_Mt_AR5"])
                    for r in csv.DictReader(f) if r["co2e_Mt_AR5"]}
        self.assertIn("Sensitivity: coal at ledger mass x implied CV", rows)
        restated = rows["Sensitivity: coal at ledger mass x implied CV"]
        grid = rows["Electricity and heat production"]
        self.assertLess(restated, grid, "the restatement is not a row of its own any more")
        self.assertGreater(grid - restated, 0.5,
                           "the two routes have converged to within half a megatonne; if "
                           "that is real the circularity finding needs restating, and if it "
                           "is a wiring error the sensitivity is reading the reference")
        self.assertGreater(restated, 30.0)


class TestIsolation(unittest.TestCase):
    def test_the_emissions_path_never_reads_this_channel(self):
        import inspect

        from pkinv.sectors.power import combustion, engine
        for mod in (combustion, engine):
            src = inspect.getsource(mod)
            self.assertNotIn("implied_cv", src)
            self.assertNotIn("plant_heat_rates", src)


if __name__ == "__main__":
    unittest.main()
