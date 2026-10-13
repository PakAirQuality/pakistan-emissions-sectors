"""Wave 1 of the industrial-coal reconstruction: the three products hold the diagnosis
OPEN with held evidence and move nothing.

The reference's Industry (1.A.2) series falls -11.69 Mt over the window on HDIP's
coal-by-consumer allocation. These products publish (1) the UNSD supply block, the one
independent supply-side control, (2) the source reconciliation - official value, edition,
actual reporting period, the label as three publications print it, the evidence held,
a BAND only where evidence supports one - and (3) the coal balance with the two
hypotheses TESTED per year. This module guards the properties that make them honest:
absences typed never zero, bands never collapsed to a point, verdicts present for every
year a metered lane exists, the official series untouched, and the national pins unmoved.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from _support import OUTPUTS, ROOT

SUPPLY = asset_path(ROOT, "data", "activity", "industry", "coal_supply.csv")
CONSUMERS = asset_path(ROOT, "data", "activity", "industry", "coal_by_consumer.csv")
UNSD = os.path.join(OUTPUTS, "unsd_coal_supply_control.csv")
RECON = os.path.join(OUTPUTS, "pakemis_coal_source_reconciliation.csv")
BALANCE = os.path.join(OUTPUTS, "pakemis_coal_balance.csv")
NEPRA_YEARS = ("2019-20", "2020-21", "2021-22", "2022-23", "2023-24")


def rows(path):
    with open(path, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class TestTheSupplyIngest(unittest.TestCase):
    def test_two_lanes_kept_apart_and_the_forced_closure_reproduced(self):
        """Lane 1 (Petroleum Division) reproduces the consumption total to <1 kt in every
        year but FY2015-16 (-203.8, the vintage diagnosis) - BY CONSTRUCTION, which is why
        it is a transcription check and not an allocation check. Lane 2 (PBS) is its own
        column and is never averaged into lane 1."""
        sup = {r["fiscal_year"]: r for r in rows(SUPPLY)
               if r["period_coverage"] == "full_year" and r["revision_status"] != "superseded_provisional"}
        con = {r["fiscal_year"]: float(r["coal_kt"]) for r in rows(CONSUMERS)
               if r["consumer"] == "total" and r["revision_status"] in ("final", "provisional")}
        for fy in ("2016-17", "2019-20", "2020-21", "2022-23", "2023-24"):
            s = float(sup[fy]["coal_imports_kt"]) + float(sup[fy]["coal_production_kt_petroleum_division"])
            self.assertLess(abs(s - con[fy]), 1.0, fy)
        s16 = float(sup["2015-16"]["coal_imports_kt"]) + float(sup["2015-16"]["coal_production_kt_petroleum_division"])
        self.assertAlmostEqual(s16 - con["2015-16"], -203.8, places=1)
        # the two production lanes disagree in the early years and the file says so
        self.assertNotEqual(sup["2015-16"]["coal_production_kt_petroleum_division"],
                            sup["2015-16"]["coal_production_kt_pbs_extraction"])

    def test_the_partial_period_footnotes_travel_with_fy2023_24(self):
        r = next(r for r in rows(SUPPLY) if r["fiscal_year"] == "2023-24"
                 and r["period_coverage"] == "full_year" and r["revision_status"] == "final")
        for phrase in ("Balochistan", "March 2024", "Punjab", "February 2024", "January 2024"):
            self.assertIn(phrase, r["reporting_period_note"])

    def test_the_superseded_print_is_retained_typed(self):
        sup = [r for r in rows(SUPPLY) if r["fiscal_year"] == "2023-24" and r["revision_status"] == "superseded_provisional"]
        self.assertEqual(len(sup), 1)
        self.assertEqual(sup[0]["coal_production_kt_petroleum_division"], "19693")


class TestTheUnsdControl(unittest.TestCase):
    def test_stock_changes_are_typed_absent_never_zero(self):
        for r in rows(UNSD):
            self.assertEqual(r["stock_changes_TJ"], "", r["calendar_year"])
            self.assertIn("not published", r["note"])

    def test_the_statistical_difference_is_published_not_allocated(self):
        by = {(r["edition"], r["calendar_year"]): r for r in rows(UNSD)}
        self.assertEqual(by[("2023", "2022")]["statistical_difference_TJ"], "-191264")
        self.assertEqual(by[("2023", "2023")]["statistical_difference_TJ"], "-103220")
        # all final coal sits in Non-metallic minerals; Industries n.e.s carries none
        self.assertEqual(by[("2022", "2021")]["final_non_metallic_minerals_TJ"], "389710")
        self.assertIn(by[("2022", "2021")]["final_industries_nes_TJ"], ("", "0"))


class TestTheSourceReconciliation(unittest.TestCase):
    def test_the_official_series_is_untouched_and_the_bands_are_bands(self):
        """Every official value equals coal_by_consumer.csv; the brick and cement rows carry
        a JOINT band (low != high) where a metered lane exists and no single-valued central."""
        off = {(r["fiscal_year"], r["consumer"]): r["coal_kt"] for r in rows(CONSUMERS)
               if r["revision_status"] in ("final", "provisional")}
        for r in rows(RECON):
            if r["official_kt"]:
                self.assertEqual(float(r["official_kt"]), float(off[(r["fiscal_year"], r["consumer"])]))
            if r["consumer"] in ("brick_kilns", "cement") and r["fiscal_year"] in NEPRA_YEARS:
                self.assertTrue(r["proposed_low_kt"] and r["proposed_high_kt"], r["fiscal_year"])
                self.assertNotEqual(r["proposed_low_kt"], r["proposed_high_kt"])
                self.assertTrue(r["decision_rule_row"].startswith("3"))
                self.assertIn("JOINT", r["proposed_basis"])

    def test_power_is_the_row_two_candidate_on_the_metered_lane(self):
        for r in rows(RECON):
            if r["consumer"] == "power" and r["fiscal_year"] in NEPRA_YEARS:
                self.assertTrue(r["decision_rule_row"].startswith("2"), r["fiscal_year"])
                self.assertTrue(r["independent_kt"])
                self.assertIn("NEPRA", r["independent_evidence"])

    def test_the_three_labels_are_recorded_on_the_cement_rows(self):
        for r in rows(RECON):
            if r["consumer"] == "cement":
                for label in ("Cement/Others", "Cement/Other Industry"):
                    self.assertIn(label, r["category_scope"])


class TestTheCoalBalance(unittest.TestCase):
    def setUp(self):
        self.by = {r["fiscal_year"]: r for r in rows(BALANCE)}

    def test_every_metered_year_carries_both_verdicts_and_the_residual_flips_sign(self):
        for fy in NEPRA_YEARS:
            r = self.by[fy]
            self.assertTrue(r["h1_verdict"].startswith(("MATCH", "BREAK")), fy)
            self.assertIn("residual", r["h2_verdict"])
        self.assertLess(float(self.by["2020-21"]["power_residual_hdip_minus_nepra_kt"]), 0)
        self.assertGreater(float(self.by["2023-24"]["power_residual_hdip_minus_nepra_kt"]), 0)

    def test_h1_is_a_pattern_not_a_law(self):
        """The strict rule matches in some years and breaks in others - the table records
        both, which is what makes it a test rather than an assumption."""
        verdicts = [self.by[fy]["h1_verdict"][:5] for fy in self.by]
        self.assertIn("MATCH", verdicts)
        self.assertIn("BREAK", verdicts)

    def test_stock_change_is_never_zero_and_the_band_is_a_band(self):
        for r in self.by.values():
            self.assertEqual(r["stock_change_kt"], "")
            self.assertIn("never zero", r["statistical_discrepancy_note"])
        r = self.by["2023-24"]
        self.assertIn("BAND", r["h2_verdict"])
        self.assertIn("PARTIAL", r["note"])

    def test_the_energy_lane_carries_an_origin_band(self):
        r = self.by["2023-24"]
        lig, obc = float(r["hdip_nonpower_TJ_if_lignite"]), float(r["hdip_nonpower_TJ_if_other_bituminous"])
        self.assertLess(lig, obc)
        self.assertEqual(r["hdip_nonpower_TJ_engine_ncv"], r["hdip_nonpower_TJ_if_other_bituminous"])

    def test_nothing_moved_the_reference(self):
        import subprocess, sys
        rc = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_pins.py")],
                            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(rc.returncode, 0, rc.stdout + rc.stderr)


if __name__ == "__main__":
    unittest.main()


class TheIdentityAndItsRetainedResidual(unittest.TestCase):
    """rc53 Wave B: P + M - X - dS = C_power + C_cement + C_brick + C_other + R, with R a COLUMN.

    The decisive question is which correction the evidence supports - is industrial coal missing
    from the account, or is the available coal divided wrongly between users? They need different
    corrections, so the balance must answer it per year rather than leave it to a reader.
    """

    def setUp(self):
        self.rows = {r["fiscal_year"]: r for r in rows(BALANCE)}

    def test_the_residual_is_retained_and_never_allocated_to_a_user(self):
        for fy, r in self.rows.items():
            self.assertNotEqual(r["identity_residual_R_kt"], "", fy)
            # every consumption lane equals HDIP's own print; none of them absorbs R
            for lane, column in (("hdip_brick_kt", "hdip_brick_kt"), ("hdip_cement_others_kt", "hdip_cement_others_kt")):
                self.assertEqual(r[lane], r[column], fy)

    def test_exports_and_stock_change_are_typed_not_zeroed(self):
        for fy, r in self.rows.items():
            self.assertIn("not_published", r["identity_exports_kt"], fy)
            self.assertIn("not_published", r["identity_stock_change_kt"], fy)
            self.assertEqual(r["stock_change_kt"], "", fy)

    def test_the_power_lane_is_a_band_wherever_both_lanes_are_published(self):
        """Neither lane is held fixed: holding HDIP's allocation fixed would make industry absorb
        the seam, and holding NEPRA's metered burn fixed would do the reverse."""
        for fy, r in self.rows.items():
            if not r["nepra_power_kt"] or not r["hdip_power_kt"]:
                continue
            lo, hi = float(r["power_lane_low_kt"]), float(r["power_lane_high_kt"])
            self.assertLessEqual(lo, hi, fy)
            self.assertEqual({lo, hi}, {float("%.0f" % float(r["nepra_power_kt"])),
                                        float("%.0f" % float(r["hdip_power_kt"]))}, fy)
            self.assertIn("NEPRA metered burn .. HDIP allocation", r["power_lane_basis"], fy)

    def test_the_tonnage_closure_is_labelled_a_transcription_check(self):
        """It closes because the two published tables balance by construction; a reader must not
        be allowed to mistake that for independent evidence that nothing is missing."""
        for fy, r in self.rows.items():
            if r["supply_use_reading"].startswith("CLOSES"):
                self.assertIn("BY CONSTRUCTION", r["supply_use_reading"], fy)
                self.assertIn("transcription check", r["supply_use_reading"], fy)

    def test_the_energy_band_is_reported_as_a_width_because_it_cannot_fail(self):
        """Two of the three calorific values are IPCC defaults spanning lignite to bituminous, so
        the band is tens of percent wide and spans zero for any plausible allocation. Reporting it
        as a passed test would manufacture confidence the evidence does not support."""
        for fy, r in self.rows.items():
            if not r["supply_TJ_low"]:
                continue
            lo, hi = float(r["residual_R_TJ_low"]), float(r["residual_R_TJ_high"])
            self.assertLess(lo, hi, fy)
            if r["supply_use_reading"].startswith("CLOSES"):
                self.assertIn("too wide to fail", r["supply_use_reading"], fy)

    def test_the_two_spike_years_read_as_misdivided_not_missing(self):
        """FY2019-20 and FY2020-21: the account closes in tonnes while the brick column exceeds all
        domestic coal mined outside the Thar plants' burn. That is a division failure, and it is a
        different defect from coal being absent - so the verdict says which."""
        for fy in ("2019-20", "2020-21"):
            self.assertTrue(self.rows[fy]["supply_use_reading"].startswith("MISDIVIDED"), fy)
        for fy in ("2021-22", "2022-23", "2023-24"):
            self.assertTrue(self.rows[fy]["supply_use_reading"].startswith("CLOSES"), fy)
