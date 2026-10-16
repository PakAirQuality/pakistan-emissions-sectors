"""Original HTAP controls survive extraction and partial fiscal years stay absent."""
import collections
import unittest

from pkinv.core import configurations as conf
from pkinv.core.io import read_rows
from pkinv.core.reporting_window import CORE_FY_ENDS
from pkinv.report import air_external_htap as htap


class HTAPSourceControls(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.annual = read_rows(htap.ANNUAL)
        cls.monthly = read_rows(htap.MONTHLY)

    def test_exported_months_close_to_the_printed_source_annual_controls(self):
        sums = collections.defaultdict(float)
        for row in self.monthly:
            sums[int(row["month"][:4]), row["sector"]] += float(row["emissions_Mg"])
        self.assertEqual(len(sums), len(self.annual))
        for row in self.annual:
            expected = float(row["annual_Mg"])
            self.assertAlmostEqual(sums[int(row["calendar_year"]), row["sector"]], expected,
                                   delta=max(1e-7, abs(expected)*1e-10))
            self.assertTrue(row["source_sha256"] and row["source_row"])

    def test_specific_original_cell_and_provider_survive(self):
        # Publisher XLSX data sheet: Pakistan, 2015, livestock, Annual column.
        # This independent source control is not calculated by the inventory.
        hits = [r for r in self.annual if r["calendar_year"] == "2015"
                and r["sector"] == "HTAPv3_8.2_Agriculture_livestock"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["provider"], "REAS")
        self.assertAlmostEqual(float(hits[0]["annual_Mg"]), 490327.17, places=6)

    def test_fiscal_matching_uses_twelve_months_and_refuses_partial_latest_years(self):
        panel = [dict(fiscal_end_year=str(year), configuration_id=cfg, pollutant="NH3",
                      sector_id=sector, emissions_Gg="2000")
                 for year in CORE_FY_ENDS for cfg in conf.AIR_ALL
                 for sector in ("agriculture", "transport", "residential", "waste")]
        result = htap.comparison(self.monthly, panel)
        for row in result:
            start = int(row["period_id"][2:6])
            if start >= 2020:
                self.assertEqual(row["htap_Gg"], "")
                self.assertEqual(row["ratio_pakemis_over_htap"], "")
                self.assertEqual(row["comparison_status"], "no_complete_external_fiscal_period")
            elif row["comparison_sector"] in ("residential", "waste"):
                self.assertTrue(row["htap_Gg"])
                self.assertEqual(row["ratio_pakemis_over_htap"], "")
                self.assertEqual(row["comparison_status"], "boundary_difference_context_only")
        broken = [r for r in self.monthly if r["month"] != "201507"]
        with self.assertRaisesRegex(ValueError, "incomplete HTAP"):
            htap.comparison(broken, panel)


if __name__ == "__main__":
    unittest.main()
