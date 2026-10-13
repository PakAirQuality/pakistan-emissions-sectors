"""The SIR listing parse: every row proves itself, every label is stated or bounded.

The NEPRA Detail-of-Generation listing sheets carry the plant-month table for the three
years PBS stops short of - including the reference year every headline is quoted for. The
parse is licensed by identities the sheets themselves supply, and these tests re-derive
each one from the shipped files rather than trusting the ingest's own report:

  * every plant row's twelve months meet its printed Sum, or the row is in the typed
    discrepancy ledger with an arbitration outcome from the plant's own daily reports;
  * a mixed fuel label (RLNG/HSD) is never split and never guessed - it is assigned only
    where the OTHER candidate fuels' entire annual control cannot account for five percent
    of the group, and any subitem carrying bound-assigned mass is capped at TE3;
  * coverage rows exist for Coal and Gas ONLY, because the liquid fuels already ride the
    OCAC panel with T1/T2 months a TE3 generation shape would displace.

Run:  python3 -m unittest discover tests -p "test_sir_generation.py"
"""

from pkinv.assets import asset_path
import csv
import os
import sys
import unittest

from _support import require_documents  # noqa: E402  (rc42: the documents gate)

from _support import ROOT, scripts_on_path
scripts_on_path()

import ingest_pbs_generation as pbs  # noqa: E402
import ingest_sir_generation as sir  # noqa: E402
from pkinv.core.io import read_rows

PANEL = asset_path(ROOT, "data", "activity", "power", "generation_monthly.csv")
COVERAGE = asset_path(ROOT, "data", "activity", "power", "generation_monthly_coverage.csv")
LEDGER = asset_path(ROOT, "data", "activity", "power", "sir_row_discrepancies.csv")
SAMPLE = os.path.join(ROOT, "outputs", "power_sir_verification_sample.csv")

SIR_YEARS = ("FY2021-22", "FY2022-23", "FY2023-24")


def _csv(path):
    return read_rows(path, comments=False)


class TestTheRowsProveThemselves(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for path in sir.LISTINGS.values():
            if not os.path.exists(path):
                raise unittest.SkipTest("the SIR listing sheets are not present")
        cls.rows, cls.coverage, cls.ledger, _report = sir.build()

    def test_every_row_closes_or_is_in_the_ledger(self):
        """The row identity, re-derived: after arbitration the panel's months either meet
        the printed Sum or the ledger holds the discrepancy with its resolution."""
        flagged = {(r["fiscal_year"], r["plant"]) for r in self.ledger}
        by_plant = {}
        for row in self.rows:
            key = (row["fiscal_year"], row["plant"])
            by_plant.setdefault(key, 0.0)
            by_plant[key] += float(row["gwh"])
        # rebuild the printed sums straight from the sheets
        for fy_start, path in sir.LISTINGS.items():
            label = "FY%d-%02d" % (fy_start, (fy_start + 1) % 100)
            plants, _excluded = sir.parse_sheet(path)
            for plant in plants:
                key = (label, plant["plant"])
                delta = by_plant[key] - plant["printed_sum"]
                slack = max(sir.CLOSURE_SLACK, 0.001 * abs(plant["printed_sum"]))
                if key in flagged:
                    continue
                self.assertLessEqual(abs(delta), slack,
                                     "%s %s misses its printed Sum by %+.2f GWh and is "
                                     "not in the discrepancy ledger" % (label, key[1],
                                                                        delta))

    def test_every_ledger_row_carries_an_arbitration_outcome(self):
        """rc21 fetched the five discrepant plants' own daily reports: four rows have one
        corrected month cell (the corrected row closes), one has a confirmed Sum typo
        (every month independently corroborated). 'Awaiting arbitration' would mean the
        corrections file stopped reaching the ingest."""
        self.assertEqual(len(self.ledger), 5)
        for row in self.ledger:
            self.assertIn("arbitrated", row["resolution"], row["plant"])

    def test_the_ledger_mass_is_immaterial(self):
        total = sum(float(r["gwh"]) for r in self.rows)
        disputed = sum(abs(float(r["delta_gwh"])) for r in self.ledger)
        self.assertLess(disputed / total, 0.001)

    def test_the_shipped_files_match_a_rebuild(self):
        """The panel's SIR lane and coverage rows equal what the ingest derives from the
        held sheets - the same drift guard the PBS lane has, for this lane."""
        shipped = [r for r in _csv(PANEL) if r["fiscal_year"] in SIR_YEARS]
        self.assertEqual(len(shipped), len(self.rows))
        for ours, theirs in zip(self.rows, shipped):
            for field in pbs.FIELDS:
                self.assertEqual(str(ours[field]), theirs[field],
                                 "%s %s %s" % (ours["fiscal_year"], ours["plant"], field))
        shipped_cov = [r for r in _csv(COVERAGE) if r["fiscal_year"] in SIR_YEARS]
        self.assertEqual([{k: str(v) for k, v in r.items()} for r in self.coverage],
                         shipped_cov)


class TestNoMixedLabelIsGuessed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.panel = [r for r in _csv(PANEL) if r["fiscal_year"] in SIR_YEARS]
        cls.coverage = [r for r in _csv(COVERAGE) if r["fiscal_year"] in SIR_YEARS]
        cls.controls = pbs.control_by_fuel()

    def test_the_bound_is_rederived_from_the_annual_control(self):
        """A bound-assigned group must survive the arithmetic that licensed it: even the
        ENTIRE annual control of every other candidate fuel leaves at least DOMINANT of
        the group's generation on the assigned fuel."""
        groups = {}
        for row in self.panel:
            if row["fuel_source"].startswith("sir_annual_control_bound"):
                key = (row["fiscal_year"], row["note"].split("'")[1], row["fuel"])
                groups.setdefault(key, 0.0)
                groups[key] += float(row["gwh"])
        self.assertTrue(groups, "no bound-assigned group survives in the panel")
        for (label, sheet_label, fuel), total in groups.items():
            fy_start = int(label[2:6])
            candidates = sir.MIXED_FUEL[sheet_label.lower()]
            self.assertIn(fuel, candidates)
            ceiling = sum(self.controls[fy_start].get(f, 0.0)
                          for f in candidates if f != fuel)
            self.assertGreaterEqual((total - ceiling) / total, pbs.DOMINANT,
                                    "%s %s" % (label, sheet_label))

    def test_an_unforceable_group_is_unassigned_and_says_why(self):
        """FY2021-22's RLNG/HSD group misses the 95 percent rule by one point - the
        honest refusal this lane's design turns on. If this row acquires a fuel, either
        the control moved or someone weakened the bound."""
        unassigned = [r for r in self.panel
                      if r["fiscal_year"] == "FY2021-22" and r["fuel_source"] == "unassigned"
                      and "RLNG/HSD" in r["note"]]
        self.assertTrue(unassigned)
        for row in unassigned:
            self.assertEqual(row["fuel"], "")
            self.assertIn("excluded from the fuel-specific", row["note"])

    def test_gas_is_capped_at_TE3_wherever_bound_mass_contributes(self):
        for row in self.coverage:
            if row["subitem"] == "Gas" and "annual-control bound" in row["decision"]:
                self.assertEqual(row["temporal_class"], "TE3", row["fiscal_year"])

    def test_coverage_rows_exist_for_coal_and_gas_only(self):
        """The deliberate scope: a TE3 SIR shape for furnace oil would DISPLACE the OCAC
        panel's T1/T2 months under the monthly layer's precedence - an evidence downgrade
        wearing an upgrade's clothes."""
        self.assertEqual({r["subitem"] for r in self.coverage}, {"Coal", "Gas"})
        for label in SIR_YEARS:
            self.assertEqual(len([r for r in self.coverage
                                  if r["fiscal_year"] == label]), 2, label)


class TestThePbsOverlapValidation(unittest.TestCase):
    """FY2017-18..FY2020-21 exist in BOTH plant-month records. Compare, never sum."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, "outputs", "power_sir_pbs_overlap.csv")
        if not os.path.exists(path):
            raise unittest.SkipTest("overlap not generated")
        with open(path, newline="", encoding="utf-8") as handle:
            cls.rows = list(csv.DictReader(line for line in handle
                                           if not line.startswith("#")))

    def test_it_regenerates_identically(self):
        for missing in sir.VALIDATION_LISTINGS.values():
            if not os.path.exists(missing):
                raise unittest.SkipTest("validation sheets not all held")
        rebuilt = sir.overlap_rows()
        self.assertEqual([{k: str(v) for k, v in r.items()} for r in rebuilt],
                         [dict(r) for r in self.rows])

    def test_every_shape_pair_sums_to_one_on_both_sides(self):
        import collections
        sums = collections.defaultdict(lambda: [0.0, 0.0])
        for row in self.rows:
            key = (row["fiscal_year"], row["subitem"])
            sums[key][0] += float(row["sir_share"])
            sums[key][1] += float(row["pbs_share"])
        for key, (sir_total, pbs_total) in sums.items():
            self.assertAlmostEqual(sir_total, 1.0, places=3, msg=key)
            self.assertAlmostEqual(pbs_total, 1.0, places=3, msg=key)

    def test_the_two_vintages_agree_within_the_measured_band(self):
        """Worst monthly share gap measured 4.6 pp (FY2020-21 Furnace Oil) when the
        validation landed. The bound is that measurement plus margin: if a future
        reparse pushes the two records further apart than six points of a month, that
        is a finding about a source, not noise to widen past."""
        worst = max(abs(float(r["delta_pp"])) for r in self.rows)
        self.assertLessEqual(worst, 6.0)

    def test_no_validation_year_entered_the_panel_twice(self):
        """The compare-never-sum rule, structurally: the panel's SIR-lane years and
        the PBS years stay disjoint, so no fiscal year carries two vintages of mass."""
        panel = _csv(PANEL)
        by_year = {}
        for row in panel:
            lane = "sir" if "sir_detail" in row["source_file"] else "pbs"
            by_year.setdefault(row["fiscal_year"], set()).add(lane)
        for year, lanes in by_year.items():
            self.assertEqual(len(lanes), 1, "%s carries both lanes" % year)


class TestTheImmutableFuelCarry(unittest.TestCase):
    """The coal-only carried-sheet lane (Wave-2 remainder): Sahiwal's commissioning year.

    A COAL label from the nearest later listing sheet may reach an earlier year because
    a coal boiler cannot convert away from coal - and ONLY because of that. The lane's
    whole licence is the immutability of the fuel plus the year's own control staying
    consistent, so these tests hold both, and hold the lane to coal alone."""

    @classmethod
    def setUpClass(cls):
        cls.panel = _csv(PANEL)
        cls.carried = [r for r in cls.panel
                       if r["fuel_source"].startswith("sir_sheet_label_carried")]

    def test_the_carried_lane_is_coal_only(self):
        self.assertTrue(self.carried, "the carried lane vanished")
        self.assertEqual({r["fuel"] for r in self.carried}, {"Coal"})
        for fuel in pbs.__dict__.get("IMMUTABLE_FUELS", ()):
            self.assertEqual(fuel, "Coal",
                             "IMMUTABLE_FUELS grew past coal - a conversion-capable "
                             "fuel in this lane recreates the 580-percent RLNG failure")

    def test_the_carry_stays_inside_the_years_own_control(self):
        """The control-exclusion argument, re-derived: the carried year's coal coverage
        must sit under COVERAGE_IMPOSSIBLE - a carry violating the year's own control
        is the exact failure the RLNG history records."""
        for row in _csv(COVERAGE):
            if row["fiscal_year"] == "FY2016-17" and row["subitem"] == "Coal":
                self.assertLessEqual(float(row["coverage"]), pbs.COVERAGE_IMPOSSIBLE)
                self.assertEqual(row["temporal_class"], "TE2")

    def test_the_carry_reaches_only_years_before_the_sheets(self):
        years = {r["fiscal_year"] for r in self.carried}
        self.assertTrue(all(y < "FY2017-18" for y in years), years)


class TestTheDailyReportsCorroborateTheSheet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(SAMPLE):
            raise unittest.SkipTest("the verification sample has not been fetched")
        cls.sample = _csv(SAMPLE)

    def test_the_sample_is_not_empty_and_mostly_agrees(self):
        judged = [r for r in self.sample
                  if r["outcome"] in ("agrees", "disagrees")]
        agrees = [r for r in judged if r["outcome"] == "agrees"]
        self.assertGreaterEqual(len(judged), 60)
        self.assertGreaterEqual(len(agrees) / len(judged), 0.9)

    def test_every_disagreement_is_resolved_by_a_correction(self):
        """The four cells where the daily record contradicts the sheet are exactly the
        four month-cell corrections the ingest applies - an unresolved disagreement would
        mean the sample found a defect the panel still carries."""
        corrections = sir.corrections()
        corrected = {(fix["fiscal_year"], fix["month"])
                     for fixes in corrections.values() for fix in fixes
                     if fix["kind"] == "month_cell"}
        disagreements = {(r["fiscal_year"], r["month"]) for r in self.sample
                         if r["outcome"] == "disagrees"}
        self.assertEqual(disagreements, corrected)

    def test_every_arbitrating_document_is_held_and_hash_pinned(self):
        require_documents("data/raw/nepra/sir_detail")
        for fixes in sir.corrections().values():
            for fix in fixes:
                held = asset_path(ROOT, "data", "raw", "nepra", "sir_detail", fix["basis_document"])
                self.assertTrue(os.path.exists(held), fix["basis_document"])
                self.assertEqual(len(fix["basis_sha256"]), 64)


if __name__ == "__main__":
    unittest.main()
