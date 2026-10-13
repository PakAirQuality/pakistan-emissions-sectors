"""The annual product's contract: two views, no silent rows, closure to the series.

The tenth review asked for a nine-year product whose rows carry completeness states
rather than gaps, and whose trend-safe subset is distinguishable from its
most-complete subset. These are the properties that make the file mean that.

Run:  python3 -m unittest discover tests -p "test_annual_product.py"
"""
import csv
import os
import unittest
from pkinv.core.io import read_rows
from _support import ROOT

OUT = os.path.join(ROOT, "outputs", "pakemis_annual_fy2015_16_fy2023_24.csv")
SERIES = os.path.join(ROOT, "outputs", "pakemis_national_series.csv")

GRAINS = ("category_gas", "sector_total", "absent", "residual_no_pathway")
STATES = ("E", "NE", "NA")


def _rows(path=OUT):
    return read_rows(path, comments=False)


def _series():
    return [r for r in _rows(SERIES) if r["sector"] != "COVERED_TOTAL"]


class TestAnnualProduct(unittest.TestCase):
    def test_the_vocabularies_are_closed(self):
        for r in _rows():
            self.assertIn(r["grain"], GRAINS, r["sector"])
            self.assertIn(r["completeness_state"], STATES, r["sector"])
            self.assertIn(r["harmonized_common_scope"], ("yes", "no"), r["sector"])

    def test_every_sector_year_is_present_exactly_once(self):
        """No silent holes: every sector-year of the series appears here, either as
        detail rows, a sector-total row, or a named-gap absent row."""
        want = {(r["sector"], r["fiscal_end_year"]) for r in _series()}
        got = {(r["sector"], r["fiscal_end_year"]) for r in _rows()}
        self.assertEqual(got, want)

    def test_absent_years_carry_a_gap_and_no_number(self):
        for r in _rows():
            if r["grain"] != "absent":
                continue
            self.assertTrue(r["gap_id"].strip(), r["sector"])
            self.assertEqual(r["co2e_Mt_AR5"], "")
            self.assertEqual(r["completeness_state"], "NE")
            self.assertEqual(r["harmonized_common_scope"], "no")

    def test_detail_closes_to_the_published_series(self):
        """The product EXPANDS the series, it does not restate it: each
        sector-year's rows must sum to the cell the series published, at the
        precision the series published it."""
        from pkinv.report.annual_product import CLOSURE_TOL_MT
        published = {(r["sector"], r["fiscal_end_year"]): r["co2e_Mt_AR5"]
                     for r in _series()}
        sums = {}
        for r in _rows():
            if not r["co2e_Mt_AR5"]:
                continue
            if r["configuration_id"] != "REF_2023_24":
                continue      # the S rows close against the S register, not the series
            key = (r["sector"], r["fiscal_end_year"])
            sums[key] = sums.get(key, 0.0) + float(r["co2e_Mt_AR5"])
        for key, total in sums.items():
            self.assertAlmostEqual(
                total, float(published[key]), delta=CLOSURE_TOL_MT * 2,
                msg="%s FY%s: detail %.9f against published %s"
                    % (key[0], key[1], total, published[key]))

    def test_the_harmonized_view_is_recomputable_from_the_rule(self):
        """The view is a claim about which sector-years are trend-safe, so it must
        be derivable from the file's own basis and gap columns rather than asserted:
        a member sector must be non-absent in EVERY year from the view's start."""
        from pkinv.report import annual_product as ap
        rows = _rows()
        years = sorted({int(r["fiscal_end_year"]) for r in rows})
        absent = {(r["sector"], int(r["fiscal_end_year"])) for r in rows
                  if r["grain"] == "absent"}
        members = ap.harmonized_sectors(ap._series_rows())
        for sector in members:
            for fy in years:
                if fy < ap.HARMONIZED_FROM_FY_END:
                    continue
                self.assertNotIn((sector, fy), absent,
                                 "%s is in the harmonized view but absent in FY%d"
                                 % (sector, fy))
        # and nothing outside the derived membership is marked in
        for r in rows:
            if r["harmonized_common_scope"] == "yes":
                self.assertIn(r["sector"], members, r["sector"])
                self.assertGreaterEqual(int(r["fiscal_end_year"]),
                                        ap.HARMONIZED_FROM_FY_END)

    def test_a_sector_absent_in_the_window_is_out_of_the_harmonized_view(self):
        """The positive control, over the RULE rather than over today's membership.

        This used to pin IPPU and industry as excluded by name. Both became eligible - IPPU
        when cement reached nine years, industry when its FY2020-21 gas table was read off a
        scan - and nothing in the suite could tell, because a test that asserts two names
        are absent from a list cannot notice that the list should have grown. The rule is
        what gets tested now: an absent year inside the window disqualifies, one before it
        does not.
        """
        from pkinv.report import annual_product as ap
        window = ap.HARMONIZED_FROM_FY_END
        rows = [
            {"sector": "solid", "fiscal_end_year": str(window), "co2e_Mt_AR5": "1.0",
             "activity_basis": "observed"},
            {"sector": "solid", "fiscal_end_year": str(window + 1), "co2e_Mt_AR5": "1.0",
             "activity_basis": "observed"},
            {"sector": "holed", "fiscal_end_year": str(window), "co2e_Mt_AR5": "absent",
             "activity_basis": "absent"},
            {"sector": "holed", "fiscal_end_year": str(window + 1), "co2e_Mt_AR5": "1.0",
             "activity_basis": "observed"},
            {"sector": "early", "fiscal_end_year": str(window - 1), "co2e_Mt_AR5": "absent",
             "activity_basis": "absent"},
            {"sector": "early", "fiscal_end_year": str(window), "co2e_Mt_AR5": "1.0",
             "activity_basis": "observed"},
        ]
        self.assertEqual(ap.harmonized_sectors(rows), ("early", "solid"))

    def test_the_membership_is_what_the_rows_support(self):
        """Ten sectors today, and the number is derived rather than declared: every sector
        has a row in every year from FY2016-17, because the only two absences left in the
        product are industry and transport in FY2015-16, before the window opens."""
        from pkinv.report import annual_product as ap
        members = ap.harmonized_sectors(ap._series_rows())
        self.assertEqual(len(members), 10, members)
        for name in ("ippu", "industry"):
            self.assertIn(name, members)

    def test_the_product_regenerates_identically(self):
        from pkinv.report import annual_product as ap
        fresh = ap.build()
        shipped = _rows()
        self.assertEqual(len(fresh), len(shipped))
        for f, s in zip(fresh, shipped):
            for col in ap.FIELDS:
                self.assertEqual(str(f[col]), s[col],
                                 "%s FY%s %s.%s" % (f["sector"], f["fiscal_end_year"],
                                                    f["category"], col))

    def test_the_parquet_matches_the_csv_when_it_ships(self):
        from pkinv.report.annual_product import OUT_PARQUET as path
        if not os.path.exists(path):
            self.skipTest("no parquet beside the CSV")
        try:
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed")
        table = pq.read_table(path).to_pydict()
        rows = _rows()
        self.assertEqual(len(table["sector"]), len(rows))
        for i, r in enumerate(rows):
            self.assertEqual(table["sector"][i], r["sector"])
            self.assertEqual(table["co2e_Mt_AR5"][i], r["co2e_Mt_AR5"])


if __name__ == "__main__":
    unittest.main()
