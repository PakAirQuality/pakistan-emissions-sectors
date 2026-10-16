"""Every mineral x year of the FINAL PBS minerals export, scanned for the rc67 failure modes.

The FY2021-22 oil/gas defect was one province-month holding many times its own row's level
(KPK gas August 8.4x, Balochistan oil March 36x). This scans the exported panel - not the
parser - for that signature in every canonical mineral-year and requires each hit either to
be withdrawn from timing or to be a reviewed, named source anomaly in a mineral that drives
no emission timing. It also holds the coverage rules on the export itself.
"""
import collections
import statistics
import unittest

from pkinv.assets import asset_path
from pkinv.core.io import read_rows
from pkinv.core import pbs_minerals as pm
from _support import ROOT

PANEL = asset_path(ROOT, "data/activity/monthly/pbs_minerals_month_province.csv")
CONTROLS = asset_path(ROOT, "outputs/pakemis_minerals_controls.csv")
SPIKE = 5.0           # a province-month at five times its own row's median
# Reviewed 2026-10-15: FATA limestone November 2016 prints 1,291,304 t against a row median
# of 149,845 t (8.6x); both held editions (compiled workbook and 2016-17 PDF) carry it, no
# witness corrects it. Limestone timing is a cement cross-check only and shapes no emission.
REVIEWED = {(2016, "limestone", "FATA", "201611")}
TIMING_DRIVERS = {"natural_gas", "crude_oil"}   # the only minerals fugitives/monthly.py consumes


class MineralsAnomalyScan(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = read_rows(PANEL)
        cls.groups = collections.defaultdict(list)
        for r in cls.rows:
            cls.groups[(int(r["fiscal_year_start"]), r["canonical_mineral"])].append(r)

    def test_single_cell_spikes_are_withdrawn_or_reviewed(self):
        hits = set()
        for (year, mineral), members in self.groups.items():
            by_province = collections.defaultdict(dict)
            for r in members:
                by_province[r["province"]][r["month"]] = float(r["quantity"])
            for province, months in by_province.items():
                median = statistics.median(months.values())
                for month, value in months.items():
                    if median > 0 and value / median > SPIKE:
                        hits.add((year, mineral, province, month))
                        usable = {r["timing_usable"] for r in members}
                        if (year, mineral, province, month) not in REVIEWED:
                            self.assertEqual({"no"}, usable, "%s %s %s %s is %.1fx its row median "
                                             "and still drives timing" % (year, mineral, province,
                                                                          month, value / median))
                            self.assertTrue(all(r["quality_note"] for r in members))
                        else:
                            self.assertNotIn(mineral, TIMING_DRIVERS)
        # the scan must still see the defect it was written for
        self.assertIn((2021, "natural_gas", "KPK", "202108"), hits)
        self.assertIn((2021, "crude_oil", "Balochistan", "202203"), hits)
        self.assertEqual(hits - REVIEWED, {h for h in hits if h[0] == 2021})

    def test_served_timing_has_no_dominant_month(self):
        for (year, mineral), members in self.groups.items():
            if mineral not in TIMING_DRIVERS:
                continue
            shares, _methods, covered = pm.profile_or_flat(mineral, year, self.rows)
            self.assertLess(max(shares.values()), 0.10, "%s FY%d" % (mineral, year))
            self.assertEqual(covered, members[0]["timing_usable"] == "yes")

    def test_no_province_manufactured_no_zero_filled_and_coverage_typed(self):
        for (year, mineral), members in self.groups.items():
            expected = set(members[0]["source_expected_provinces"].split(";"))
            self.assertLessEqual({r["province"] for r in members}, expected)
            self.assertEqual(12 * len({r["province"] for r in members}), len(members))
            for r in members:
                self.assertNotEqual("", r["quantity"])            # empty cells never exported as data
                if float(r["quantity"]) == 0:
                    self.assertEqual("observed_zero", r["observation_status"])
                self.assertIn(r["national_coverage"], ("complete", "incomplete"))
                if r["timing_usable"] != "yes":
                    self.assertTrue(r["quality_note"])
                    self.assertEqual("T4", r["temporal_method"])

    def test_monthly_rows_close_on_printed_annual_controls(self):
        for (year, mineral), members in self.groups.items():
            per_province = collections.defaultdict(float)
            printed = {}
            for r in members:
                per_province[r["province"]] += float(r["quantity"])
                printed[r["province"]] = float(r["year_total_printed"])
            for province, total in per_province.items():
                self.assertAlmostEqual(printed[province], total, delta=1.0,
                                       msg="%s FY%d %s" % (mineral, year, province))

    def test_every_control_group_states_why_it_was_selected_or_excluded(self):
        controls = read_rows(CONTROLS)
        selected = collections.Counter()
        for c in controls:
            self.assertTrue(c["selection_reason"])
            if c["closed"] != "yes":
                self.assertTrue(c["quality_note"])
            if c["selected"] == "yes":
                selected[(c["fiscal_year_start"], c["canonical_mineral"])] += 1
        self.assertEqual(36, len(selected))
        self.assertEqual({1}, set(selected.values()))


if __name__ == "__main__":
    unittest.main()
