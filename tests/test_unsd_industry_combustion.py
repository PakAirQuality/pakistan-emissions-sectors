"""The UNSD industrial-combustion control: printed TJ pinned against the source PDFs,
the CO2 conversion using the release's own documented IPCC factors, biofuels held out
of the fossil total as a biogenic memo, and a fossil total for every parsed year."""
import csv
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(HERE), "outputs", "unsd_industry_combustion_control.csv")


def rows():
    with open(OUT, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class UnsdIndustryCombustion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = rows()
        cls.by = {(r["year"], r["fuel"]): r for r in cls.rows}

    def test_printed_terajoules_are_pinned(self):
        """The 2022 manufacturing row, verbatim from the UNSD 2023 edition."""
        self.assertEqual(self.by[("2022", "natural_gas")]["tj"], "233748")
        self.assertEqual(self.by[("2022", "primary_coal")]["tj"], "330684")
        self.assertEqual(self.by[("2022", "oil_products")]["tj"], "59330")

    def test_co2_uses_the_documented_factors(self):
        gas = self.by[("2022", "natural_gas")]
        self.assertEqual(gas["co2_ef_kg_per_tj"], "56100")
        self.assertIn("IPCC 2006", gas["ef_source"])
        self.assertAlmostEqual(float(gas["co2_Mt"]), 233748 * 56100 / 1e9, places=4)

    def test_biofuels_are_a_biogenic_memo_not_in_the_total(self):
        bio = self.by[("2022", "biofuels_waste")]
        self.assertEqual(bio["in_total"], "biogenic_memo")
        total = float(self.by[("2022", "FOSSIL_COMBUSTION_TOTAL")]["co2_Mt"])
        fossil = sum(float(r["co2_Mt"]) for r in self.rows
                     if r["year"] == "2022" and r["in_total"] == "yes")
        self.assertAlmostEqual(total, fossil, places=3)
        self.assertNotIn(float(bio["co2_Mt"]), [total])   # 15.6 must not be inside 49.3

    def test_every_year_has_a_fossil_total(self):
        years = {r["year"] for r in self.rows}
        for y in years:
            self.assertIn((y, "FOSSIL_COMBUSTION_TOTAL"), self.by, y)
        self.assertGreaterEqual(len(years), 8)   # 2015..2023


class TheBoundaryLedgerCarriesBothBenchmarks(unittest.TestCase):
    def test_edgar_and_unsd_diagnostics_both_present(self):
        ledger = os.path.join(os.path.dirname(HERE), "outputs", "pakemis_industry_boundary_ledger.csv")
        with open(ledger, encoding="utf-8") as h:
            diags = [r for r in csv.DictReader(l for l in h if not l.startswith("#"))
                     if r["boundary_status"] == "diagnostic"]
        names = {r["component"] for r in diags}
        self.assertIn("EDGAR 1.A.2 coverage gap", names)
        self.assertIn("UNSD 1.A.2 combustion benchmark", names)


if __name__ == "__main__":
    unittest.main()
