"""The NFDC false gap stays closed: the reference year's own twelve months, gated.

The sixteenth review's first Pass-2 science change: the Annual Fertilizer Review
2023-24's Annex-5 carries all twelve July-June FY2023-24 offtake months, so nothing is
borrowed for the reference year any more. These tests re-derive the page's identities
from the held PDF, hold the shipped panel to a rebuild, prove the consumer flipped to
the own-months lane, and bound the Annex-7 provincial cross-check by what it measures.

Run:  python3 -m unittest discover tests -p "test_nfdc_annex5.py"
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest

from _support import ROOT, scripts_on_path
scripts_on_path()

import ingest_nfdc_annex5 as annex5  # noqa: E402
from pkinv.sectors.agriculture import nfdc_monthly  # noqa: E402
from pkinv.core.io import read_rows

PANEL = asset_path(ROOT, "data", "activity", "monthly", "nfdc_month_product_offtake.csv")
ANNEX7 = asset_path(ROOT, "data", "nfdc", "annex7_province_month_product_2023-24.csv")
MONTH_NUMBER = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _panel_rows():
    return read_rows(PANEL)


class TestThePageProvesItself(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(annex5.PDF):
            raise unittest.SkipTest("the AFR 2023-24 PDF is not held")
        cls.rows, cls.grand = annex5.parse_page()

    def test_the_three_identities_hold(self):
        annex5.prove(self.rows, self.grand)   # raises on failure

    def test_the_shipped_lane_matches_a_rebuild(self):
        built, _rows, _grand = annex5.build()
        shipped = [r for r in _panel_rows() if r["fiscal_year_start"] == "2023"]
        self.assertEqual(len(built), len(shipped))
        for ours, theirs in zip(built, shipped):
            for field in annex5.FIELDS:
                self.assertEqual(str(ours[field]), theirs[field],
                                 "%s %s %s" % (ours["product"],
                                               ours["source_agency"], field))

    def test_the_grand_total_is_the_printed_ten_point_three_million(self):
        self.assertAlmostEqual(self.grand[12], 10275168.0, delta=2.0)


class TestTheConsumerFlipped(unittest.TestCase):
    def test_the_reference_year_is_covered_by_the_own_months_lane(self):
        self.assertTrue(nfdc_monthly.covers(2023))
        self.assertEqual(nfdc_monthly.source_name(2023), "AFR 2023-24 Annex-5")

    def test_every_reference_month_is_observed_T2(self):
        shares, methods = nfdc_monthly.profile(2023)
        self.assertEqual(len(shares), 12)
        self.assertEqual(set(methods.values()), {"T2"})
        self.assertAlmostEqual(sum(shares.values()), 1.0, places=9)

    def test_no_borrowed_basis_survives_in_the_reference_layer(self):
        path = os.path.join(ROOT, "outputs", "agriculture_monthly_2024.csv")
        if not os.path.exists(path):
            raise unittest.SkipTest("layer not generated")
        with open(path, newline="", encoding="utf-8") as handle:
            bases = {r["basis"] for r in csv.DictReader(handle)}
        self.assertFalse([b for b in bases if "borrowed from the opening year" in b],
                         "the reference layer still carries a borrowed-months basis")
        self.assertTrue([b for b in bases if "Annex-5" in b])

    def test_the_historical_years_still_ride_table_3_4(self):
        """The lane column exists so provenance is per-year: FY2015-16..FY2022-23
        must keep naming the consolidated volume, not the Review."""
        for year in (2015, 2018, 2022):
            self.assertEqual(nfdc_monthly.source_name(year), "Table 3.4", year)


class TestTheAnnex7CrossCheck(unittest.TestCase):
    """Two independently printed tables of one ledger. July-November agree to the
    tonne; from December the four-province table runs UNDER the national one by up to
    half a percent - a boundary difference (the provincial table excludes offtake the
    national ledger counts), bounded here in the direction it runs rather than hidden
    behind a symmetric tolerance."""

    @classmethod
    def setUpClass(cls):
        if not (os.path.exists(ANNEX7) and os.path.exists(annex5.PDF)):
            raise unittest.SkipTest("both annexes are needed")
        with open(ANNEX7, newline="", encoding="utf-8") as handle:
            cls.a7 = {}
            for row in csv.DictReader(handle):
                key = "%s%02d" % (row["calendar_year"], MONTH_NUMBER[row["month"]])
                cls.a7[key] = cls.a7.get(key, 0.0) + float(row["Urea"] or 0)
        rows, _grand = annex5.parse_page()
        total = next(r for r in rows
                     if r["product"] == "UREA" and r["agency"] == "TOTAL")
        cls.a5 = dict(zip(annex5.MONTHS, total["months"]))

    def test_the_overlap_agrees_within_the_boundary_difference(self):
        for month in annex5.MONTHS:
            self.assertIn(month, self.a7,
                          "Annex-7 lost fiscal month %s" % month)
            delta = self.a7[month] - self.a5[month]
            self.assertLessEqual(delta, 2.0,
                                 "%s: the provincial table EXCEEDS the national one "
                                 "by %.0f t - not a boundary difference" % (month,
                                                                            delta))
            self.assertLessEqual(-delta, 0.006 * self.a5[month],
                                 "%s: provinces run %.0f t under national - beyond "
                                 "the measured boundary gap" % (month, -delta))

    def test_the_first_five_months_agree_to_the_tonne(self):
        for month in annex5.MONTHS[:5]:
            self.assertLessEqual(abs(self.a7[month] - self.a5[month]), 1.5, month)


class TestTheLagVariantIsPricedAndNotApplied(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, "outputs", "pakemis_fertilizer_timing_variant.csv")
        if not os.path.exists(path):
            raise unittest.SkipTest("variant not generated")
        with open(path, newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(handle))

    def test_each_lag_sums_to_one(self):
        import collections
        totals = collections.defaultdict(float)
        for row in self.rows:
            totals[row["profile_variant"]] += float(row["variant_share"])
        self.assertEqual(len(totals), 3)
        for name, total in totals.items():
            self.assertAlmostEqual(total, 1.0, places=4, msg=name)

    def test_lag_zero_is_the_reference(self):
        for row in self.rows:
            if row["profile_variant"].endswith("lag0"):
                self.assertEqual(row["variant_share"], row["reference_share"])

    def test_no_lag_reaches_the_registry_or_the_product(self):
        with open(asset_path(ROOT, "data", "temporal_profiles.csv"),
                  encoding="utf-8") as handle:
            registry = handle.read()
        self.assertNotIn("application_lag", registry)
        self.assertNotIn("fertilizer_application", registry)

    def test_no_lag_improves_on_the_reference_against_agronomy(self):
        """The measured licence for refusing the lag model: shifting the depot shape
        a whole month does not move it toward the crops' calendar, so the lag would
        add a free parameter and no fidelity. If a lag ever DOES improve, this fails
        and the refusal must be re-argued rather than silently kept."""
        worst = {row["profile_variant"]: float(row["worst_gap_to_agronomy_pp"])
                 for row in self.rows}
        self.assertLessEqual(worst["fertilizer_application_lag0"],
                             min(worst.values()) + 1e-9)


if __name__ == "__main__":
    unittest.main()
