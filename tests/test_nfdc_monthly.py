"""Gates on the NFDC Table 3.4 ingest and the nitrogen profile it extends.

WHAT MOVED. Agriculture's synthetic-nitrogen months rode NFDC's Annex-7 for FY2023-24 alone.
Table 3.4 of the consolidated volume supplies the same offtake for FY2015-16 through FY2022-23
on the inventory's own July-June fiscal year, so those eight years need no borrowed months at
all and the whole category "Urea application" reaches 100 per cent observed.

WHAT MOVED NEXT, and it was not more data. Managed soils sat unchanged for one release because
the shape may only ride the SYNTHETIC share and the annual table appeared to carry that split
for the reference year alone. It was never missing: `fiscal_series.build()` computed all
thirty-five components for every year and discarded them, while `annual_product.components_for`
returned None and said no split existed. Removing that false absence let the offtake shape reach
the synthetic share in all nine years - 90 Mt - with no annual number moving.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest
from pkinv.core.reporting_window import CORE_FY_STARTS, CORE_FY_ENDS, CORE_PERIOD_IDS, REFERENCE_PERIOD
from pkinv.core.configurations import REFERENCE
from pkinv.core.io import read_rows
from _support import ROOT


PANEL = asset_path(ROOT, "data", "activity", "monthly", "nfdc_month_product_offtake.csv")
SUMMARY = os.path.join(ROOT, "outputs", "nfdc_monthly_parse_summary.csv")
QUARANTINE = os.path.join(ROOT, "outputs", "nfdc_monthly_quarantine.csv")
ANNEX7 = asset_path(ROOT, "data", "nfdc", "annex7_province_month_product_2023-24.csv")

TABLE_YEARS = tuple(range(2015, 2023))      # FY2015-16 .. FY2022-23
ANNEX7_YEAR = 2023
MONTH_NUMBER = {"Jan": 1, "Feb": 2, "Mar": 3, "Apr": 4, "May": 5, "Jun": 6,
                "Jul": 7, "Aug": 8, "Sep": 9, "Oct": 10, "Nov": 11, "Dec": 12}


def _rows(path):
    return read_rows(path)


class ThreeControls(unittest.TestCase):
    def setUp(self):
        self.summary = _rows(SUMMARY)[0]

    def test_every_table_page_carried_a_readable_year(self):
        """A page whose year cannot be read must not be attributed to its neighbour."""
        self.assertEqual(11, int(self.summary["table_pages"]))
        self.assertEqual(0, int(self.summary["pages_without_a_readable_year"]))

    def test_every_product_year_closes_on_its_own_total_row(self):
        self.assertEqual(int(self.summary["product_years"]),
                         int(self.summary["product_years_closing_group_control"]))

    def test_the_page_grand_total_is_checked_and_nearly_always_closes(self):
        """The strongest of the three: it checks every product against a figure none of them
        contributed to, and it is what found the single-agency products that print no TOTAL
        row of their own."""
        pages = int(self.summary["pages_with_a_grand_total"])
        self.assertGreaterEqual(pages, 10)
        self.assertGreaterEqual(int(self.summary["pages_closing_the_grand_total"]), pages - 1)

    def test_the_rotation_control_is_live(self):
        detectable = int(self.summary["rotation_detectable_series"])
        total = int(self.summary["series_total"])
        self.assertGreater(detectable / total, 0.90)

    def test_the_quarantine_is_the_sources_own_arithmetic(self):
        for row in _rows(QUARANTINE):
            self.assertTrue(row["raw"].strip())
            self.assertNotEqual(row["months_sum"], row["annual_printed"])


class TheTotalRowIsNotAnAgency(unittest.TestCase):
    def test_no_row_is_carried_under_the_group_control_label(self):
        agencies = {r["source_agency"].strip().upper() for r in _rows(PANEL)}
        self.assertNotIn("TOTAL", agencies)
        self.assertNotIn("GRAND TOTAL", agencies)

    def test_phosphate_products_are_not_flagged_as_nitrogen(self):
        """SSP and TSP are superphosphates and contain no nitrogen. Flagging them would have
        carried phosphate tonnage into a nitrogen stream."""
        for row in _rows(PANEL):
            if row["product"] in ("SSP", "TSP", "SOP", "MOP"):
                self.assertEqual("no", row["nitrogen_bearing"], row["product"])


class TheTwoVintagesAgree(unittest.TestCase):
    def test_table_3_4_reproduces_annex_7_where_they_overlap(self):
        """The independent control, and the reason this series is admissible.

        Annex-7 runs April-March and Table 3.4 July-June, so April, May and June 2023 appear
        in both - transcribed from different publications by different routes. They agree to
        single tonnes on hundreds of thousands.
        """
        table = {}
        for row in _rows(PANEL):
            if row["product"] == "UREA":
                table[row["month"]] = table.get(row["month"], 0.0) + float(row["tonnes"])
        annex = {}
        for row in _rows(ANNEX7):
            key = "%s%02d" % (row["calendar_year"], MONTH_NUMBER[row["month"]])
            annex[key] = annex.get(key, 0.0) + float(row["Urea"] or 0.0)

        overlap = sorted(set(table) & set(annex))
        seam = [m for m in overlap if m < "202307"]
        self.assertEqual(["202304", "202305", "202306"], seam,
                         "the two NFDC vintages no longer overlap; the seam is unchecked")
        for month in seam:
            self.assertLess(abs(table[month] - annex[month]) / annex[month], 0.0005, month)
        # Since Pass 2 the panel's Annex-5 lane overlaps Annex-7 across the whole
        # reference year too. July-November agree to the tonne; thereafter the
        # four-province table runs up to half a percent UNDER the national ledger -
        # a boundary difference, bounded in its direction (see test_nfdc_annex5).
        for month in (m for m in overlap if m >= "202307"):
            delta = annex[month] - table[month]
            self.assertLessEqual(delta, 2.0, month)
            self.assertLessEqual(-delta, 0.006 * table[month], month)


class TheProfileUsesTheBetterSource(unittest.TestCase):
    def test_table_3_4_serves_its_eight_years_with_no_borrowed_month(self):
        from pkinv.sectors.agriculture import nfdc_monthly
        for fy_start in TABLE_YEARS:
            self.assertTrue(nfdc_monthly.covers(fy_start))
            shares, classes = nfdc_monthly.profile(fy_start)
            self.assertEqual(12, len(shares))
            self.assertAlmostEqual(1.0, sum(shares.values()), places=12)
            self.assertEqual({"T2"}, set(classes.values()),
                             "FY%d-%02d borrowed a month it should not need"
                             % (fy_start, (fy_start + 1) % 100))

    def test_the_reference_year_rides_its_own_twelve_months(self):
        """Table 3.4 stops at FY2022-23, and for two releases the reference year fell
        through to Annex-7's April-March window with three borrowed months. Since
        Pass 2 the panel's Annex-5 lane carries the year's own July-June months, so
        the reference year rides this module like every other year - and the Annex-7
        fallback stays alive underneath, still able to serve a year only it reaches."""
        from pkinv.sectors.agriculture import nfdc_monthly, monthly
        self.assertTrue(nfdc_monthly.covers(ANNEX7_YEAR))
        self.assertEqual("AFR 2023-24 Annex-5", nfdc_monthly.source_name(ANNEX7_YEAR))
        _shares, method = nfdc_monthly.profile(ANNEX7_YEAR)
        self.assertEqual({"T2"}, set(method.values()))
        # the dormant branch, exercised directly: still there, still honest
        self.assertTrue(monthly.annex7_covers(ANNEX7_YEAR))
        _shares, method = monthly.nitrogen_profile(ANNEX7_YEAR)
        self.assertEqual({"T2", "T3"}, set(method.values()))

    def test_the_years_differ_from_one_another(self):
        from pkinv.sectors.agriculture import nfdc_monthly
        shapes = {fy: tuple(round(v, 9) for _m, v in sorted(nfdc_monthly.profile(fy)[0].items()))
                  for fy in TABLE_YEARS}
        self.assertEqual(len(TABLE_YEARS), len(set(shapes.values())))


class TheGrainThatUnblockedIt(unittest.TestCase):
    """WHAT REPLACED THE BLOCKER TEST, and why the replacement is the stronger assertion.

    Last pass this class asserted that Managed soils was undivided in every year but the
    reference one, and said in its own docstring that when the annual engine gained a nine-year
    split the test would fail and should be deleted with its reason. That is what happened -
    except the split was never missing. `fiscal_series.build()` had been computing all
    thirty-five components for every year and discarding them, while
    `annual_product.components_for` returned None and claimed no split existed.

    So the assertion is inverted rather than dropped. What must now hold is that the split IS
    present in every year, because a regression to the coarse grain would silently take
    90 Mt of managed-soils nitrogen back off its observed monthly basis - and it would do it
    without moving a single annual number, which is exactly the kind of change nothing else
    here would notice.
    """

    def test_managed_soils_is_split_in_every_year(self):
        rows = [r for r in _rows(os.path.join(ROOT, "outputs", "pakemis_atomic_annual.csv"))
                if r["sector_id"] == "agriculture" and r["category"] == "Managed soils"]
        undivided = {r["period_id"] for r in rows if r["subitem"] == "(no component split)"}
        split = {r["period_id"] for r in rows if r["subitem"] != "(no component split)"}
        self.assertEqual(set(), undivided,
                         "agriculture fell back to the coarse grain for %s" % sorted(undivided))
        self.assertEqual(set(CORE_PERIOD_IDS), split)

    def test_latest_urea_profile_reads_the_held_source_months_and_annual_control(self):
        from pkinv.sectors.agriculture import nfdc_monthly
        from pkinv.core.monthly import normalise
        source = _rows(nfdc_monthly.ANNEX5)
        observations = {r["calendar_year"] + "%02d" % MONTH_NUMBER[r["month"]]:
                        float(r["offtake_product_tonnes"]) for r in source
                        if r["fiscal_year"] == "2024-25" and r["product"] == "Urea"}
        self.assertEqual(len(observations), 12)
        self.assertEqual(nfdc_monthly.series(2024), observations)
        profile, classes = nfdc_monthly.profile(2024)
        self.assertEqual(profile, normalise(observations))
        self.assertEqual(set(classes.values()), {"T2"})
        self.assertEqual(nfdc_monthly.source_name(2024), "AFR 2024-25 Annex-5")
        annual = _rows(asset_path(ROOT, "data", "nfdc", "afr2025_offtake_by_product.csv"))
        total = sum(float(r["offtake_kt"]) * 1000 for r in annual
                    if r["fiscal_year"] == "2024-25" and r["product"] == "Urea" and r["offtake_kt"])
        # Independent annual table prints whole kt; its half-unit is 500 tonnes.
        self.assertAlmostEqual(sum(observations.values()), total, delta=500)

    def test_annex5_vintage_overlap_is_compared_without_replacing_older_agency_rows(self):
        from pkinv.sectors.agriculture import nfdc_monthly
        previous = nfdc_monthly.series(2023)
        newer = {r["calendar_year"] + "%02d" % MONTH_NUMBER[r["month"]]:
                 float(r["offtake_product_tonnes"]) for r in _rows(nfdc_monthly.ANNEX5)
                 if r["fiscal_year"] == "2023-24" and r["product"] == "Urea"}
        self.assertEqual(set(previous), set(newer))
        self.assertLessEqual(max(abs(previous[m] - newer[m]) for m in previous), 1)
        self.assertEqual(nfdc_monthly.source_name(2023), "AFR 2023-24 Annex-5")

    def test_final_latest_synthetic_months_have_source_weights_and_source_identity(self):
        from pkinv.sectors.agriculture import nfdc_monthly
        expected, _classes = nfdc_monthly.profile(2024)
        rows = [r for r in _rows(os.path.join(ROOT, "outputs", "pakemis_temporal_profiles.csv"))
                if r["fiscal_year"] == "FY2024-25" and r["sector"] == "agriculture"
                and r["category"] == "Managed soils" and "synthetic" in r["subitem"].lower()]
        self.assertEqual(len(rows), 4 * 12)
        for row in rows:
            self.assertAlmostEqual(float(row["weight"]), expected[row["month"]], places=11)
            self.assertEqual(row["temporal_evidence_class"], "TE2")
            self.assertIn("annex5_national_month_product.csv", row["source_id"])

    def test_final_latest_fertiliser_nh3_closes_by_source_and_keeps_application_proxy_class(self):
        from collections import defaultdict
        from pkinv.sectors.agriculture import nfdc_monthly
        from pkinv.core.configurations import ALL
        from pkinv.report.air_annual import atom_configuration
        expected, _classes = nfdc_monthly.profile(2024)
        atoms = [r for r in _rows(os.path.join(ROOT, "outputs", "pakemis_air_atomic_annual.csv"))
                 if r["period_id"] == "FY2024-25" and r["pollutant"] == "NH3"
                 and r["source_class_id"].startswith("agriculture:fertiliser:")]
        # Annual atoms store shared agriculture under its nitrogen case once;
        # monthly products materialise each complete S/L × TAN/IPCC configuration.
        annual = {(cfg, r["source_class_id"]): float(r["emissions_Gg"])
                  for cfg in ALL for r in atoms
                  if r["configuration_id"] == atom_configuration(cfg, "agriculture")}
        placed = defaultdict(float)
        months = defaultdict(set)
        for row in _rows(os.path.join(ROOT, "outputs", "pakemis_air_monthly.csv")):
            if row["period_id"] != "FY2024-25" or row["pollutant"] != "NH3":
                continue
            key = row["configuration_id"], row["source_class_id"]
            if key not in annual:
                continue
            self.assertEqual(row["temporal_evidence_class"], "TE3")
            self.assertAlmostEqual(float(row["month_share"]), expected[row["month"]], places=11)
            self.assertAlmostEqual(float(row["emissions_Gg"]),
                                   annual[key] * expected[row["month"]], delta=1e-8)
            placed[key] += float(row["emissions_Gg"])
            self.assertNotIn(row["month"], months[key], key)
            months[key].add(row["month"])
        self.assertEqual(set(placed), set(annual))
        self.assertEqual({key[0] for key in annual}, set(ALL))
        for key, amount in annual.items():
            self.assertEqual(len(months[key]), 12)
            self.assertAlmostEqual(placed[key], amount, delta=1e-8)

    def test_the_synthetic_share_carries_the_offtake_shape_in_every_year(self):
        """The 90 Mt. Synthetic-fertiliser nitrogen is TE2 in all nine years."""
        rows = [r for r in _rows(os.path.join(ROOT, "outputs",
                                              "pakemis_temporal_profiles.csv"))
                if r["sector"] == "agriculture" and r["category"] == "Managed soils"
                and "synthetic" in r["subitem"].lower()]
        self.assertEqual(set(CORE_PERIOD_IDS), {r["fiscal_year"] for r in rows})
        self.assertEqual({"TE2"}, {r["temporal_evidence_class"] for r in rows},
                         "the synthetic share stopped carrying the offtake shape - all "
                         "nine years are own-months TE2 since the Annex-5 lane landed")

    def test_the_census_nitrogen_did_not_come_along(self):
        """The half of managed soils that must NOT have moved.

        Pasture deposition and organic manure ride a livestock count, not a dealer's
        depot. Letting the offtake shape reach them would have been the easy version of
        this change and would have claimed an observed monthly basis for mass that has
        none. Crop residues left this set deliberately in Wave 3 - they ride a harvest,
        and the mineralization kernel gives them a derived shape of their OWN (T3/TE3),
        which is asserted here so their departure stays a decision and not a drift.
        """
        rows = [r for r in _rows(os.path.join(ROOT, "outputs",
                                              "pakemis_temporal_profiles.csv"))
                if r["sector"] == "agriculture" and r["category"] == "Managed soils"
                and "synthetic" not in r["subitem"].lower()]
        self.assertTrue(rows)
        residue = [r for r in rows if "crop residues" in r["subitem"]]
        census = [r for r in rows if "crop residues" not in r["subitem"]]
        self.assertTrue(residue)
        self.assertTrue(census)
        self.assertEqual({"TE4"}, {r["temporal_evidence_class"] for r in census},
                         "census-driven nitrogen acquired a shaped profile")
        self.assertEqual({"TE3"}, {r["temporal_evidence_class"] for r in residue},
                         "the residue kernel stopped reaching its own subitems")


if __name__ == "__main__":
    unittest.main()
