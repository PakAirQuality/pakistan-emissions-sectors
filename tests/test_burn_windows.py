"""The burning windows and the attribution ladder: derived, wrap-safe, and honest.

Wave 3 moved the fire windows from two date literals to a derivation over the FAO
calendar's own harvest dates, and put an attribution ladder between the raw VIIRS
record and the profile. These gates hold the parts that failed on the way in: the
sugarcane season wraps the calendar year (naive min/max turned Nov-Mar into
Feb-Dec), and the fetch box necessarily includes Indian Punjab, whose fires are
most of the raw record and must never weight Pakistan's months again.

Run:  python3 -m unittest discover tests -p "test_burn_windows.py"
"""
import os
import sys
import unittest
from datetime import date


from pkinv.sectors.agriculture import burn_windows  # noqa: E402
from _support import ROOT


class TestTheWindows(unittest.TestCase):
    def test_every_ledger_crop_has_a_window(self):
        crops = {crop for crop, _s, _e in burn_windows.windows(2023)}
        self.assertEqual({"rice", "wheat", "cotton", "maize", "sugarcane"}, crops)

    def test_the_cane_wrap_is_resolved_by_dates_not_tuples(self):
        """Sugarcane is cut November into the new year; its window must OPEN in the
        fiscal year's autumn, not in February - the tuple-min failure mode."""
        cane = [(s, e) for crop, s, e in burn_windows.windows(2023)
                if crop == "sugarcane"]
        self.assertTrue(cane)
        self.assertEqual(11, min(s for s, _e in cane).month)

    def test_windows_stay_inside_the_fiscal_year(self):
        for _crop, start, end in burn_windows.windows(2020):
            self.assertGreaterEqual(start, date(2020, 7, 1))
            self.assertLessEqual(end, date(2021, 6, 30))
            self.assertLessEqual(start, end)

    def test_a_shifted_calendar_moves_the_windows(self):
        """The directive's positive control: the windows are DERIVED, so a changed
        harvest date must change them."""
        original = burn_windows.harvest_sessions
        try:
            burn_windows.harvest_sessions = lambda: [
                (crop, (early[0] % 12 + 1, early[1]), (late[0] % 12 + 1, late[1]))
                for crop, early, late in original()]
            shifted = burn_windows.windows(2023)
        finally:
            burn_windows.harvest_sessions = original
        self.assertNotEqual(sorted(shifted), sorted(burn_windows.windows(2023)))


class TestTheAttributionLadder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.agriculture import monthly as am
        if not am.firms_covers(2023):
            raise unittest.SkipTest("no fire record for the reference year")
        cls.weights, cls.counts = am.burning_attribution(2023)

    def test_the_rungs_partition_the_years_detections(self):
        c = self.counts
        self.assertEqual(c["detections_in_year"],
                         c["out_of_window"] + c["outside_pakistan"]
                         + c["near_kiln"] + c["off_cropland"] + c["attributed"])
        self.assertGreater(c["attributed"], 0)

    def test_the_indian_fires_never_weight_pakistans_months(self):
        """The correction this ladder exists for: the fetch box includes Indian
        Punjab and its stubble fires dominate the raw record. If the
        outside-the-country count collapses while the box is unchanged, the mask
        stopped working - not the geography."""
        self.assertGreater(self.counts["outside_pakistan"],
                           self.counts["attributed"],
                           "the national mask went quiet; India's fires are most "
                           "of the raw record inside this fetch box")

    def test_unattributed_is_counted_never_forced(self):
        """Weights come only from attributed detections: the weight total must be
        consistent with a strict subset of the record."""
        self.assertGreater(sum(self.weights.values()), 0.0)
        self.assertLess(self.counts["attributed"],
                        self.counts["detections_in_year"])


if __name__ == "__main__":
    unittest.main()


class TestTheDerivedSessionTableIsTheCalendar(unittest.TestCase):
    """rc40: the engine reads data/activity/agriculture/fao_harvest_sessions.csv, a derived
    table, because the FAO JSON is a publisher document a validation package cannot carry.
    Whenever the JSON IS present the table must equal what the parser reads from it, so the
    derivative can never drift from its document unnoticed."""

    def test_the_table_equals_a_fresh_parse_of_the_json(self):
        import os
        from pkinv.sectors.agriculture import burn_windows as bw
        if not os.path.exists(bw.CALENDAR):
            self.skipTest("the FAO calendar JSON is not held here; the committed table stands")
        parsed = [(c, e, l) for c, _fao, _i, e, l in bw.sessions_from_calendar()]
        self.assertEqual(parsed, bw.harvest_sessions())

    def test_the_table_has_every_ledger_crop(self):
        from pkinv.sectors.agriculture import burn_windows as bw
        self.assertEqual({c for c, _e, _l in bw.harvest_sessions()},
                         set(bw.FAO_CROPS.values()))
