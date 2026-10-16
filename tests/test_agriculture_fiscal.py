"""The agriculture history is fiscal, the source that makes it fiscal is actually read, and
the two things that were wrong before it cannot come back.

WHY THIS FILE EXISTS. Four defects, and each one has a guard here rather than a paragraph.

1. data/activity/agriculture/es_fiscal_series.csv was transcribed in August 2026 as phase B1
   of exactly this repair, registered as a source document - and READ BY NO CODE for
   eighty-eight commits. Phase B2 never ran. A source nothing consumes is the same failure as
   a value nothing can contradict: it looks like evidence and does no work.

2. The published history read FAOSTAT at the fiscal-END year for every crop. FAOSTAT labels a
   crop by its own harvest calendar year, and a Pakistani fiscal year holds the KHARIF crop
   harvested in the preceding calendar year and the RABI crop harvested in its own. So the
   mapping was right for wheat and a full year out for rice, maize, sugarcane and cotton. It
   was never argued about because nothing compared the two against a fiscal source.

3. FAOSTAT's Pakistan crop extract carries four crops; the reference year carries five. Cotton
   was absent from all eight history years and present at the anchor - 0.150 Mt appearing at
   the join from nowhere.

4. The transcription's header CLAIMED its FY2023-24 cells reproduce the anchor. Nothing
   checked it. A claim in a comment is a claim nothing can fail.

Run:  python3 -m unittest discover tests -p "test_agriculture_fiscal.py"
"""
import csv
import os
import unittest

from pkinv.paths import OUTPUTS
from pkinv.sectors.agriculture import fiscal_activity as fa
from pkinv.sectors.agriculture import fiscal_series as fs
from pkinv.sectors.agriculture.ef_library import InventoryData
from pkinv.core.io import read_rows

# The measured position as it stood when this guard was written. These are FACTS ABOUT THE
# WORLD - what the Economic Survey and FAOSTAT say - so they are asserted, not ratcheted. A
# ratchet would be right for "how far our collecting has got"; it is wrong here, because a
# change in any of these means a source moved and someone must look.
LIVESTOCK_PHASE_CEILING_PCT = 2.5      # measured worst year 1.895
MANAGED_SOILS_FISCAL_N_FLOOR_PCT = 50.0    # measured 52.9 - the reason for the `mixed` word
REFERENCE_YEAR = 2024


def _rows(name):
    return read_rows(os.path.join(OUTPUTS, name))


class TestTheFiscalSourceIsActuallyRead(unittest.TestCase):
    """The defect that let a transcribed source sit unread for eighty-eight commits.

    Not "the file parses" and not "a module mentions it" - that the PUBLISHED national series
    moves when the source moves. Nothing weaker would have caught the original.
    """

    def test_the_published_history_changes_when_the_source_changes(self):
        table = fa.activity()
        baseline = fs.series_by_category(fs.build(table))
        # Perturb one cell of the transcription in memory: FY2019-20 rice area, which drives
        # rice cultivation directly and residue nitrogen indirectly.
        moved = {year: dict(items) for year, items in table.items()}
        moved[2020]["rice_area_ha"] *= 1.10
        after = fs.series_by_category(fs.build(moved))
        self.assertNotEqual(baseline[2020]["Rice cultivation"],
                            after[2020]["Rice cultivation"],
                            "the fiscal transcription does not reach the published history - "
                            "which is exactly how it sat unread for eighty-eight commits")
        self.assertEqual(baseline[2021], after[2021], "one year's cell moved another year")

    def test_national_series_agriculture_comes_from_the_fiscal_path(self):
        from pkinv.report import national_series as ns
        fiscal = ns.agri_fiscal_series()
        published = {int(r["fiscal_end_year"]): r["co2e_Mt_AR5"]
                     for r in _rows("pakemis_national_series.csv")
                     if r["sector"] == "agriculture"}
        for fy_end, total in sorted(fiscal.items()):
            if fy_end == REFERENCE_YEAR:
                continue    # the reference year is the engine's own build, by design
            self.assertAlmostEqual(sum(a for a, _ in total.values()),
                                   float(published[fy_end]), places=4,
                                   msg="FY ending %d is not what the fiscal path computes"
                                       % fy_end)

    def test_every_backcast_year_declares_a_fiscal_basis(self):
        for row in _rows("pakemis_national_series.csv"):
            if row["sector"] != "agriculture" or row["fiscal_end_year"] == str(REFERENCE_YEAR):
                continue
            self.assertEqual(row["activity_basis"], "reconstructed-fiscal", row["period_label"])


class TestTheOffByOneCannotComeBack(unittest.TestCase):
    """The finding this pass did not expect, held as a test rather than a paragraph."""

    @classmethod
    def setUpClass(cls):
        cls.alignment = {(r["crop"], r["field"]): r for r in fs.crop_calendar_alignment()}

    def test_kharif_crops_align_one_calendar_year_back(self):
        """Rice, maize and sugarcane agree with the fiscal tables at fy_end MINUS ONE.

        Asserted as a comparison between the two offsets rather than against a fixed
        percentage: what matters is which mapping is right, and a threshold would have to be
        re-tuned every time FAOSTAT revises.
        """
        for crop in ("rice", "maize", "sugarcane"):
            for field in ("area_ha", "production_t"):
                row = self.alignment[(crop, field)]
                self.assertEqual(row["season"], "kharif")
                self.assertEqual(row["best_offset"], -1,
                                 "%s %s no longer aligns one year back" % (crop, field))
                self.assertLess(float(row["mean_abs_pct_at_fiscal_start_year"]),
                                float(row["mean_abs_pct_at_fiscal_end_year"]),
                                "%s %s" % (crop, field))

    def test_wheat_aligns_at_the_fiscal_end_year(self):
        """The control. If wheat ever flipped too, the finding would be an artefact of the
        comparison rather than a fact about the cropping calendar."""
        for field in ("area_ha", "production_t"):
            row = self.alignment[("wheat", field)]
            self.assertEqual(row["season"], "rabi")
            self.assertEqual(row["best_offset"], 0, "wheat %s" % field)

    def test_the_offset_the_old_history_used_is_recorded(self):
        """The published mapping is a column in the product, so a reader can see what was
        wrong without reading this test or a changelog entry."""
        for row in self.alignment.values():
            self.assertEqual(row["offset_the_published_history_used"], 0)


class TestTheAnchorAndTheHistoryAreOneBasis(unittest.TestCase):
    def test_every_reference_year_cell_reproduces_the_anchor(self):
        """The transcription's own claim, checked at last. One declared exception."""
        disagreements = [(cell, mine, theirs)
                         for cell, mine, theirs, status in fa.anchor_parity()
                         if status == "DISAGREES"]
        self.assertFalse(disagreements,
                         "the fiscal series and the anchor disagree at FY2023-24: %s"
                         % disagreements)

    def test_the_declared_exception_is_still_the_only_one(self):
        declared = {cell for cell, _m, _t, status in fa.anchor_parity()
                    if status == "declared-exception"}
        self.assertEqual(declared, {"maize.area_ha"},
                         "an exception was added or removed without a reason being written "
                         "into ANCHOR_PARITY_EXCEPTIONS")
        for reason in fa.ANCHOR_PARITY_EXCEPTIONS.values():
            self.assertGreater(len(reason), 60, "an exception without a reason is a silence")

    def test_the_cotton_factor_is_checked_across_two_independent_files(self):
        """Deriving the factor from the anchor would make the parity test above pass by
        construction. It is stated once and crossed against the transcription's bale count,
        which is where a retyped digit shows up."""
        bales = fa.activity()[REFERENCE_YEAR]["cotton_bales_000"]
        anchor = InventoryData().crops["cotton"]["production_t"]
        self.assertAlmostEqual(bales * fa.SEED_COTTON_T_PER_1000_BALES / anchor, 1.0,
                               delta=fa.COTTON_FACTOR_TOL)

    def test_no_history_year_carries_fewer_crops_than_the_anchor(self):
        """The cotton defect, generalised so the NEXT missing crop names itself."""
        scope = fa.crop_scope_parity()
        self.assertEqual(scope["fiscal"], scope["anchor"],
                         "crops in one and not the other: %s"
                         % sorted(scope["fiscal"] ^ scope["anchor"]))
        self.assertIn("cotton", scope["anchor"] - scope["calendar_faostat"],
                      "the calendar history gained cotton, so the comparison this test "
                      "documents no longer describes the two sources")


class TestTheCompromiseIsMeasuredAndNotAsserted(unittest.TestCase):
    """Enteric fermentation and manure management keep a calendar driver. These are the
    numbers that license that, and the numbers that would withdraw the licence."""

    def test_the_livestock_phase_error_stays_small_enough_to_keep_them(self):
        envelope = fs.livestock_phase_envelope()
        self.assertTrue(envelope, "the phase envelope measured nothing")
        worst = max(abs(row["phase_error_pct"]) for row in envelope)
        self.assertLess(worst, LIVESTOCK_PHASE_CEILING_PCT,
                        "the six-month phase error on the two categories that keep a "
                        "calendar driver reached %.3f%%. Above this the honest answer is to "
                        "bar them from the trend-safe view, NOT to widen this ceiling."
                        % worst)

    def test_managed_soils_earns_the_word_mixed(self):
        share, pools = fs.managed_soils_n_split()
        self.assertGreater(share, MANAGED_SOILS_FISCAL_N_FLOOR_PCT,
                           "fiscal pools fell to %.1f%% of managed-soils direct N2O (%s); "
                           "below half, `observed_fiscal_mixed` is the wrong word and the "
                           "category should say so" % (share, pools))
        self.assertEqual(fa.DRIVER["Managed soils"][1], "observed_fiscal_mixed")

    def test_the_two_livestock_categories_declare_a_calendar_basis(self):
        for category in ("Enteric fermentation", "Manure management"):
            self.assertEqual(fa.DRIVER[category][1], fa.CALENDAR_BASIS, category)


class TestThePriceOfTheChangeIsPublished(unittest.TestCase):
    def test_the_decomposition_is_exact(self):
        """difference = basis + scope, to the precision the file publishes. A single
        `difference` column would let a reader attribute a scope break to a timing fix."""
        for row in _rows("pakemis_agriculture_basis_change.csv"):
            if row["comparison_status"] == "archived_calendar_comparator_absent":
                self.assertEqual(row["calendar_faostat_Mt"], "")
                self.assertEqual(row["difference_Mt"], "")
                self.assertEqual(row["basis_term_Mt"], "")
                continue
            self.assertAlmostEqual(
                float(row["difference_Mt"]),
                float(row["basis_term_Mt"]) + float(row["scope_term_Mt"]), places=5,
                msg="%s %s" % (row["fiscal_label"], row["category"]))

    def test_livestock_basis_difference_is_the_adopted_census_reconstruction(self):
        """Cotton removal does not alter livestock; source/anchor changes can alter them."""
        for row in _rows("pakemis_agriculture_basis_change.csv"):
            if row["category"] not in ("Enteric fermentation", "Manure management"):
                continue
            # Fiscal category totals and component sums follow separate six-decimal
            # export paths; their two half-unit rounding errors can sum to 1e-6 Mt.
            self.assertAlmostEqual(float(row["scope_term_Mt"]), 0.0, delta=1.5e-6)
            if row["comparison_status"] == "compared_to_archived_calendar":
                self.assertAlmostEqual(float(row["basis_term_Mt"]),
                    float(row["fiscal_Mt"]) - float(row["calendar_faostat_Mt"]), places=5)
            self.assertEqual(row["driver_basis"], fa.CALENDAR_BASIS)

    def test_missing_archive_year_is_typed_in_final_export_and_keeps_fiscal_scope(self):
        archive = fs._calendar_by_category()
        for row in _rows("pakemis_agriculture_basis_change.csv"):
            year = int(row["fiscal_end_year"])
            has_comparator = row["category"] in archive.get(year, {})
            self.assertEqual(row["comparison_status"], "compared_to_archived_calendar"
                             if has_comparator else "archived_calendar_comparator_absent")
            self.assertGreater(float(row["fiscal_Mt"]), 0)
            self.assertNotEqual(row["scope_term_Mt"], "")
            if not has_comparator:
                self.assertEqual(row["calendar_faostat_Mt"], "")
                self.assertEqual(row["basis_term_Mt"], "")
                self.assertEqual(row["difference_Mt"], "")

    def test_the_cotton_scope_term_is_present_in_every_backcast_year(self):
        by_year = {}
        for row in _rows("pakemis_agriculture_basis_change.csv"):
            by_year[row["fiscal_end_year"]] = (by_year.get(row["fiscal_end_year"], 0.0)
                                               + float(row["scope_term_Mt"]))
        for year, total in sorted(by_year.items()):
            if int(year) == REFERENCE_YEAR:
                continue
            self.assertGreater(total, 0.0,
                               "FY ending %s shows no cotton, so either the calendar history "
                               "gained it or the decomposition stopped separating scope from "
                               "basis" % year)

    def test_the_splice_file_says_what_it_does_not_price(self):
        """The diagnostic that reported 1e-5 because it compared the anchor with itself.
        It still ships - manuscripts cite it - but it can no longer be read as evidence that
        the two bases agreed."""
        rows = _rows("pakemis_series_splice_agriculture.csv")
        self.assertTrue(rows)
        for row in rows:
            self.assertIn("reference-year only", row["what_this_prices"])
            self.assertIn("pakemis_agriculture_basis_change.csv", row["what_this_prices"])


class TestTheReferenceYearDidNotMove(unittest.TestCase):
    """The invariant every pass in this repository has to clear. The reference year is
    anchored in roughly seventy places, and a history that moved it would be a fourth
    national vintage."""

    def test_the_fiscal_path_returns_the_census_anchor_untouched(self):
        anchor = InventoryData()
        mine = fa.data_for_fiscal_year(REFERENCE_YEAR)
        self.assertEqual(mine.crops, anchor.crops)
        self.assertEqual(mine.livestock, anchor.livestock)
        self.assertEqual(mine.fertilizer["nitrogen_N_offtake"]["value_t"],
                         anchor.fertilizer["nitrogen_N_offtake"]["value_t"])

    def test_the_published_reference_year_equals_the_engine(self):
        from pkinv.sectors.agriculture.run_inventory import build_components
        engine = sum(c["co2e_Mt_AR5"] for c in build_components(InventoryData()))
        published = next(float(r["co2e_Mt_AR5"])
                         for r in _rows("pakemis_national_series.csv")
                         if r["sector"] == "agriculture"
                         and r["fiscal_end_year"] == str(REFERENCE_YEAR))
        self.assertEqual(round(engine, 5), published)


if __name__ == "__main__":
    unittest.main()
