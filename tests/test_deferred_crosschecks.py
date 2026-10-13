"""Gates on the three cross-checks that test what the inventory already depends on.

NONE OF THESE MOVES MASS, which is why they were deferred three times and why they were worth
doing. Each one asks whether something the release already rests on stands up: the temperature
series behind the residential profile, the QIM shape behind cement, and the rice calendar behind
the methane window.

WHAT THESE TESTS PROTECT is not the agreement but the CLAIM. Two of the three came back with a
narrower answer than they set out to get, and the value is in the narrowing being recorded
rather than rounded off:

  ERA5   agrees on seasonal SHAPE (r = 0.97-0.99) and disagrees on LEVEL by 3 to 6 C, because
         the volume's daily value is of an undocumented aggregation. Degree days are a function
         of level, so it validates timing and NOT the degree-day series.
  FAO    corroborates the harvest window, which the rice profile does not read - it rides the
         flooded window. So no provenance class moved.

A future edit that quietly widened either claim would be the failure worth catching.

Run:  python3 -m unittest discover tests
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import sys
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)
from pkinv.core.io import read_rows
from _support import OUT, ROOT, scripts_on_path

scripts_on_path()

ERA5 = os.path.join(OUT, "era5_degree_day_crosscheck.csv")
APCMA = os.path.join(OUT, "apcma_qim_cement_crosscheck.csv")
APCMA_PANEL = asset_path(ROOT, "data", "activity", "monthly", "apcma_month_region_dispatch.csv")
APCMA_SUMMARY = os.path.join(OUT, "apcma_dispatch_parse_summary.csv")
FAO = os.path.join(OUT, "fao_crop_calendar_crosscheck.csv")
RICE = asset_path(ROOT, "data", "rice_calendar.csv")

APCMA_YEARS = (2015, 2016, 2017, 2018, 2019)


def _rows(path):
    return read_rows(path)


class ERA5ValidatesTimingAndNotLevel(unittest.TestCase):
    def setUp(self):
        self.rows = _rows(ERA5)

    def test_it_covers_the_overlap_and_says_so(self):
        self.assertEqual(54, len({r["month"] for r in self.rows}))
        self.assertEqual(5, len({r["city"] for r in self.rows}))
        self.assertEqual("202001", min(r["month"] for r in self.rows))
        self.assertEqual("202406", max(r["month"] for r in self.rows))

    def test_every_row_states_what_it_validates(self):
        for row in self.rows:
            self.assertIn("timing", row["validates"])

    def test_the_shape_agrees(self):
        """The half that holds, and the only half the registry row claims: the two series
        track each other's seasonality almost exactly at every city."""
        import crosscheck_era5_degree_days as era5
        rows = [dict(r, era5_t2m_C=float(r["era5_t2m_C"]),
                     nasa_power_t2m_C=float(r["nasa_power_t2m_C"])) for r in self.rows]
        series = era5.by_city_series(rows)
        self.assertEqual(5, len(series))
        for city, values in sorted(series.items()):
            self.assertGreater(era5.correlation(values), 0.95,
                               "%s: the seasonal agreement this check validates is gone"
                               % city)

    def test_the_level_does_not_agree_and_that_is_recorded(self):
        """The half that does not. If this ever passed, either the volume's aggregation
        changed or someone silently applied an offset - both need a human."""
        deltas = [float(r["delta_C"]) for r in self.rows]
        mean = sum(deltas) / len(deltas)
        self.assertLess(mean, -1.0,
                        "ERA5 is no longer systematically colder than NASA POWER; the "
                        "definitional offset this check documented has changed")
        self.assertTrue(all(d < 0 for d in deltas),
                        "the offset is no longer one-signed, which would mean it is not "
                        "definitional after all")

    def test_the_sampled_cell_is_within_a_grid_step_of_the_city(self):
        for row in self.rows:
            self.assertLess(abs(float(row["lat"]) - float(row["era5_cell_lat"])), 0.1)
            self.assertLess(abs(float(row["lon"]) - float(row["era5_cell_lon"])), 0.1)


class APCMACorroboratesTheCementShape(unittest.TestCase):
    def setUp(self):
        self.rows = _rows(APCMA)
        self.summary = _rows(APCMA_SUMMARY)[0]

    def test_it_covers_five_fiscal_years_of_months(self):
        self.assertEqual(60, len(self.rows))
        self.assertEqual(set(APCMA_YEARS),
                         {int(r["fiscal_year_start"]) for r in self.rows})

    def test_both_shares_are_normalised(self):
        by_year = collections.defaultdict(lambda: [0.0, 0.0])
        for row in self.rows:
            by_year[row["fiscal_year_start"]][0] += float(row["apcma_despatch_share"])
            by_year[row["fiscal_year_start"]][1] += float(row["qim_production_share"])
        for year, (ours, theirs) in by_year.items():
            self.assertAlmostEqual(1.0, ours, places=4, msg=year)
            self.assertAlmostEqual(1.0, theirs, places=4, msg=year)

    def test_the_two_shapes_agree_closely(self):
        worst = max(abs(float(r["difference_pp"])) for r in self.rows)
        mean = sum(abs(float(r["difference_pp"])) for r in self.rows) / len(self.rows)
        self.assertLess(mean, 0.5, "the despatch and production shapes have diverged")
        self.assertLess(worst, 3.0)

    def test_every_row_says_it_compares_shape_only(self):
        for row in self.rows:
            self.assertIn("shape only", row["compares"])

    def test_the_duplicate_year_control_ran(self):
        """Five in-window years are published twice across the five pages. The control is only
        meaningful if it actually compared them, so the count is asserted to be live."""
        self.assertGreater(int(self.summary["duplicate_year_clashes"]), 0,
                           "no duplicate-year comparison happened; either the pages stopped "
                           "carrying a prior year or the control stopped running")

    def test_every_in_window_year_is_complete(self):
        counts = collections.Counter(int(r["fiscal_year_start"]) for r in _rows(APCMA_PANEL))
        for year in APCMA_YEARS:
            self.assertEqual(48, counts[year],
                             "FY%d-%02d has %d cells, not 12 months x 4 columns"
                             % (year, (year + 1) % 100, counts[year]))

    def test_nothing_reads_apcma_as_a_profile(self):
        """Cement takes its months from QIM. This is a check, and a check that quietly became
        an input would be a second vintage of the same shape."""
        import subprocess
        result = subprocess.run(
            ["grep", "-rl", "apcma_month_region_dispatch", "--include=*.py",
             os.path.join(ROOT, "src")],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.assertEqual([], [x for x in result.stdout.decode().split() if x.strip()])


class FAOCorroboratesAnEndpointTheProfileDoesNotRead(unittest.TestCase):
    def setUp(self):
        self.rows = _rows(FAO)

    def test_it_compares_harvest_only(self):
        for row in self.rows:
            self.assertIn("harvest only", row["compared"])

    def test_most_zones_agree_on_harvest_end(self):
        agreed = [r for r in self.rows if r["agrees"] == "yes"]
        self.assertGreaterEqual(len(agreed), 3)
        self.assertEqual(4, len(self.rows))

    def test_a_disagreement_is_kept_rather_than_resolved(self):
        disagreed = [r for r in self.rows if r["agrees"] == "NO"]
        self.assertTrue(disagreed, "the disagreement this check found has vanished")
        for row in disagreed:
            self.assertIn("keeps its values", row["provenance_outcome"])

    def test_the_corroborated_column_is_now_the_one_the_profile_reads(self):
        """THE RESTRAINT, RESOLVED THE OTHER WAY (Wave 3). This test used to assert
        that NO provenance class moved, because FAO corroborated harvest_end_week
        while the profile read the flooded window - upgrading on an unread column
        would have been the overclaim. The Wave-3 rewrite moved the profile onto the
        cultivation window (transplant -> harvest end), so the corroboration now
        covers a column the profile actually reads. What this asserts instead: the
        classes still say working-pointer (the CITATION is still unresolved - FAO
        corroborates the value, it does not become the source), and the profile's
        window really does end at the corroborated column."""
        classes = {r["province"]: r["provenance_class"] for r in _rows(RICE)}
        for row in self.rows:
            self.assertEqual("working-pointer", classes[row["province"]],
                             "%s: corroboration is not a citation; the provenance "
                             "gap stays open until a retrievable source is named"
                             % row["province"])
        from pkinv.sectors.agriculture import monthly as am
        shares = am.rice_profile(2023)
        self.assertGreater(shares.get("202311", 0.0), 0.0,
                           "the profile no longer reaches the corroborated harvest "
                           "window - November should carry cultivation days")
        self.assertEqual(shares.get("202312", 0.0), 0.0,
                         "the window overruns every calendar's harvest end")

    def test_an_unmapped_zone_raises_rather_than_defaulting(self):
        require_documents("data/raw/fao_crop_calendar/Pakistan_crop_calendar.json")
        import crosscheck_fao_crop_calendar as fao
        original = dict(fao.ZONE_PROVINCE)
        try:
            fao.ZONE_PROVINCE["Zone That Does Not Exist"] = "Punjab"
            with self.assertRaises(KeyError):
                fao.build()
        finally:
            fao.ZONE_PROVINCE.clear()
            fao.ZONE_PROVINCE.update(original)


if __name__ == "__main__":
    unittest.main()
