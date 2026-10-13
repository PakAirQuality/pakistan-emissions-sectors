"""The captive fleet's province geography, keyed by year.

data/province_shares.csv carries ONE captive_gas row and the engine applied it to all nine
fiscal periods. It is the FY2023-24 register's own split - a good measurement of that year and
a poor one of FY2020-21, when OGRA reports the SNGPL captive lane at 1 MMCFD against SSGCL's 202
and Punjab's share is nearer 0.008 than 0.340.

Four things are guarded, and each is a way this could go quietly wrong.

THE REPRODUCTION is the whole argument. Weighting each franchise by its own assigned gas must
reproduce the committed row at the reference year. If it stops, this module has drifted from the
hand arithmetic that produced the value the release shipped, and every other year it produces is
suspect with it.

THE OPT-IN. load_shares() with no period must be byte-identical to the committed table, so a
caller that knows nothing about years is unaffected.

THE FISCAL CONVENTION. captive_gas.csv is keyed by fiscal END year and the period object carries
the START. An off-by-one here shifts captive geography a whole year with nothing failing.

WHAT IS NOT SPREAD. The independent lane - 65 MMCFD in FY2015-16, reported by OGRA outside either
utility's network - has no franchise and therefore no geography. It is reported, never spread.
"""

from pkinv.assets import asset_path
import os
import unittest

from pkinv.core.io import read_rows
from pkinv.paths import DATA
from pkinv.sectors.power import captive_panel, downscale

COMMITTED = {"Punjab": 0.339982, "Sindh": 0.603083, "Khyber Pakhtunkhwa": 0.048268,
             "Balochistan": 0.006600, "Other": 0.002067}
YEARS = tuple(range(2016, 2025))


class TestTheReferenceYearReproducesTheCommittedRow(unittest.TestCase):
    def test_the_franchise_method_reproduces_what_the_release_shipped(self):
        vector = captive_panel.province_shares(2024)
        self.assertIsNotNone(vector)
        for province, expected in COMMITTED.items():
            self.assertAlmostEqual(vector[province], expected, places=4,
                                   msg="%s: the year-keyed method must reproduce the committed "
                                       "row at the reference year, or it is a different method"
                                       % province)

    def test_the_two_artefacts_reconcile_lane_by_lane_not_just_in_total(self):
        """The repository already advertises 288.01 against OGRA's 288. Grouped by franchise the
        register agrees with OGRA lane by lane, which is the stronger statement and the one this
        method actually rests on."""
        assigned, rate = captive_panel.lanes()
        whole = {lane: sum(assigned[lane].values()) / rate[lane] for lane in assigned if rate[lane]}
        totals, _row = captive_panel.published(2024)
        for lane, published in totals.items():
            self.assertAlmostEqual(whole[lane], published, delta=0.05,
                                   msg="%s: the register's own pool and OGRA's published lane "
                                       "must describe the same fleet" % lane)


class TestTheYearAxisIsOptIn(unittest.TestCase):
    def test_no_period_returns_the_committed_table_unchanged(self):
        shares = downscale.load_shares()["captive_gas"]
        for province, expected in COMMITTED.items():
            self.assertEqual(shares[province], expected,
                             "%s: a caller that passes no period must see exactly what it saw "
                             "before this module existed" % province)

    def test_a_period_moves_the_vector_where_the_evidence_does(self):
        class Period(object):
            fiscal_start_year = 2020                    # FY2020-21, the SNGPL collapse

        shares = downscale.load_shares(Period())["captive_gas"]
        self.assertLess(shares["Punjab"], 0.05,
                        "FY2020-21's SNGPL captive lane is 1 MMCFD against SSGCL's 202; Punjab "
                        "cannot still be a third of the fleet")
        self.assertGreater(shares["Sindh"], 0.9)


class TestTheFiscalConventionIsNotOffByOne(unittest.TestCase):
    def test_a_start_year_maps_to_the_following_end_year(self):
        self.assertEqual(captive_panel.panel_year(2015), "2016")
        self.assertEqual(captive_panel.panel_year(2023), "2024")
        self.assertIsNone(captive_panel.panel_year(None))

    def test_the_reference_period_selects_the_reference_row(self):
        class Period(object):
            fiscal_start_year = 2023                    # FY2023-24

        shares = downscale.load_shares(Period())["captive_gas"]
        for province, expected in COMMITTED.items():
            self.assertAlmostEqual(shares[province], expected, places=4, msg=province)


class TestWhatIsNotSpread(unittest.TestCase):
    def test_the_independent_lane_is_reported_and_never_allocated(self):
        """65 MMCFD in FY2015-16 sits outside either utility's network, so it has no franchise
        and no geography. It must be visible and it must not reach a province."""
        self.assertGreater(captive_panel.unplaced_mmcfd(2016), 60.0)
        for year in YEARS[1:]:
            self.assertEqual(captive_panel.unplaced_mmcfd(year), 0.0)

    def test_every_year_is_a_proper_share_vector(self):
        for year in YEARS:
            vector = captive_panel.province_shares(year)
            self.assertIsNotNone(vector, "no year may fall back to a silent zero: %s" % year)
            self.assertAlmostEqual(sum(vector.values()), 1.0, places=9, msg=str(year))
            for province, value in vector.items():
                self.assertGreaterEqual(value, 0.0, "%s %s" % (year, province))

    def test_no_year_silently_borrows_another(self):
        seen = {}
        for year in YEARS:
            key = tuple(round(v, 9) for _, v in sorted(captive_panel.province_shares(year).items()))
            self.assertNotIn(key, seen,
                             "FY ending %s and %s produce an identical vector; a year-keyed "
                             "surface that repeats itself is a backcast wearing a label"
                             % (year, seen.get(key)))
            seen[key] = year

    def test_a_province_the_engine_cannot_name_is_never_dropped(self):
        """The register spells Islamabad in full and the engine's vocabulary calls it Other. A
        plain lookup loses it and the vector sums to 0.999972 - small enough to pass unnoticed."""
        for year in YEARS:
            self.assertAlmostEqual(sum(captive_panel.province_shares(year).values()), 1.0,
                                   places=9, msg=str(year))


class TestTheSupersededYearIsTyped(unittest.TestCase):
    def test_fy2022_23_carries_its_restatement_note(self):
        """captive_gas.csv flags SSGCL 45 MMCFD as restated upward in a later edition. That is
        the value FY2022-23's Punjab share of 0.567 rests on, and the row must say so."""
        row = [r for r in read_rows(asset_path(DATA, "activity", "power", "captive_gas.csv"))
               if r["fiscal_year"] == "2023"]
        self.assertEqual(len(row), 1)
        self.assertIn("restated", row[0]["note"].lower())


if __name__ == "__main__":
    unittest.main()
