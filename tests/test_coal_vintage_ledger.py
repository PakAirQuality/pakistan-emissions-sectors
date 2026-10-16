"""The source-vintage ledger: every print kept, every inter-edition move classified, and the booking
policy holding the engine to exactly what it booked before (rc53 Wave A1).

The claim under test is the one the ledger exists to make: the July-March FY2023-24 brick collapse
between two Economic Survey editions is a REALLOCATION inside an unchanged total, not a physical
change - and reversing it could not repair the combined industrial decline, because brick plus
cement/others is invariant across it.
"""

from pkinv.assets import asset_path
import csv
import os
import unittest

from pkinv.paths import DATA, OUTPUTS, ROOT
from pkinv.sectors.industry import solid_fuels

VINTAGES = asset_path(DATA, "activity", "industry", "coal_by_sector_vintages.csv")
LEDGER = os.path.join(OUTPUTS, "pakemis_coal_vintage_ledger.csv")
POLICY = asset_path(DATA, "coal_booking_policy.csv")
CONSUMERS = asset_path(DATA, "activity", "industry", "coal_by_consumer.csv")
from pkinv.core.reporting_window import CORE_FY_STARTS
PERIODS = ["%d-%02d" % (y, (y + 1) % 100) for y in CORE_FY_STARTS]


def rows(path):
    with open(path, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


class Vintages(unittest.TestCase):
    def test_every_print_cites_a_held_file_or_is_typed_secondary(self):
        for r in rows(VINTAGES):
            self.assertTrue(os.path.exists(asset_path(ROOT, r["source_file"])), r["estimate_id"])
            if r["status"] == "transcribed_from_secondary":
                self.assertIn("not held", r["note"])
            else:
                self.assertIn(r["status"], ("verified", "verified-ocr", "not_printed"), r["estimate_id"])

    def test_reference_year_publication_year_and_period_length_are_separate_columns(self):
        for r in rows(VINTAGES):
            self.assertIn(r["period_coverage"], ("full_year", "july_march"))
            self.assertEqual(r["months_covered"], "12" if r["period_coverage"] == "full_year" else "9")
            # a nine-month print is always published in or after its own reference year
            self.assertGreaterEqual(int(r["edition_year"]), int(r["reference_fiscal_year"][:4]))

    def test_the_same_nine_months_are_printed_twice_with_different_splits(self):
        jm = {(r["publication"], r["sector_mapped"]): r["value"] for r in rows(VINTAGES)
              if r["reference_fiscal_year"] == "2023-24" and r["period_coverage"] == "july_march"}
        first, second = "Pakistan Economic Survey 2023-24 ch.14 Energy", "Pakistan Economic Survey 2024-25 ch.14 Energy"
        self.assertEqual(jm[(first, "brick_kilns")], "2572.26")
        self.assertEqual(jm[(second, "brick_kilns")], "1072.3")
        self.assertEqual(jm[(first, "cement_other")], "2800")
        self.assertEqual(jm[(second, "cement_other")], "4300")
        self.assertEqual(float(jm[(first, "power")]), float(jm[(second, "power")]))
        self.assertAlmostEqual(float(jm[(first, "total")]), float(jm[(second, "total")]), places=1)


class Ledger(unittest.TestCase):
    def test_no_pair_differences_a_nine_month_print_against_a_full_year(self):
        for r in rows(LEDGER):
            self.assertEqual(r["months_covered"], "12" if r["period_coverage"] == "full_year" else "9")

    def test_both_reallocations_are_flagged_and_the_industrial_pair_is_invariant(self):
        flagged = [r for r in rows(LEDGER) if r["revision_kind"] == "reallocation_within_total"]
        pairs = {(r["reference_fiscal_year"], r["period_coverage"]) for r in flagged}
        self.assertEqual(pairs, {("2023-24", "july_march"), ("2024-25", "full_year")})
        by = {(r["reference_fiscal_year"], r["sector_mapped"]): r for r in flagged}
        self.assertAlmostEqual(float(by[("2023-24", "brick_kilns")]["delta_kt"]), -1499.96, places=2)
        self.assertAlmostEqual(float(by[("2023-24", "cement_other")]["delta_kt"]), +1500.0, places=2)
        self.assertAlmostEqual(float(by[("2024-25", "brick_kilns")]["delta_kt"]), +133.0, places=2)
        self.assertAlmostEqual(float(by[("2024-25", "cement_other")]["delta_kt"]), -133.0, places=2)
        for r in flagged:
            self.assertEqual(r["industrial_pair_invariant"], "yes", r["reference_fiscal_year"])
            self.assertLess(abs(float(r["pair_total_delta_kt"])), 1.5)

    def test_reversing_a_reallocation_cannot_repair_the_combined_industrial_series(self):
        """The point of the invariance column: brick + cement/others is the same number on both
        sides, so the move redistributes between subsectors and changes no industrial total."""
        for r in rows(LEDGER):
            if r["revision_kind"] != "reallocation_within_total":
                continue
            self.assertAlmostEqual(float(r["industrial_pair_kt_earlier"]),
                                   float(r["industrial_pair_kt_later"]), delta=1.5)
            if r["sector_mapped"] in ("brick_kilns", "cement_other"):
                self.assertIn("invariant", r["note"])

    def test_the_supplement_folds_pak_steel_into_its_cement_column(self):
        folded = [r for r in rows(LEDGER) if r["revision_kind"] == "column_folded_into_cement"]
        self.assertEqual({r["reference_fiscal_year"] for r in folded}, {"2013-14", "2014-15"})
        for r in folded:
            self.assertIn("pak_steel", r["note"])
            self.assertLess(abs(float(r["pair_total_delta_kt"])), 1.5)
        # and the column is zero for every year the inventory reports, so nothing is contaminated
        steel = {r["reference_fiscal_year"]: r["value"] for r in rows(VINTAGES)
                 if r["sector_mapped"] == "pak_steel" and r["edition_year"] == "2020"}
        for fy in PERIODS:
            if fy in steel:
                self.assertEqual(float(steel[fy]), 0.0, fy)

    def test_the_fy2015_16_brick_revision_moved_the_printed_total_with_it(self):
        """Not a reallocation: brick rose 204 kt and the total rose with it - which is why the older
        vintage closes the supply balance and the revision breaks it."""
        r = next(x for x in rows(LEDGER) if x["reference_fiscal_year"] == "2015-16"
                 and x["sector_mapped"] == "brick_kilns" and x["revision_kind"] == "level_revision")
        self.assertAlmostEqual(float(r["delta_kt"]), 204.0, places=1)
        self.assertAlmostEqual(float(r["pair_total_delta_kt"]), 204.01, places=1)


class BookingPolicy(unittest.TestCase):
    def test_the_policy_books_one_print_per_period_and_consumer(self):
        pol = rows(POLICY)
        self.assertEqual(sorted({(r["reference_fiscal_year"], r["consumer"]) for r in pol}),
                         sorted([(fy, c) for fy in PERIODS for c in ("brick_kilns", "cement")]))
        for r in pol:
            self.assertIn(r["rule"], ("supplement_vintage", "older_vintage_closes_balance", "latest_full_year_revision"))

    def test_no_july_march_print_can_be_booked(self):
        prints = {r["estimate_id"]: r for r in rows(VINTAGES)}
        for r in rows(POLICY):
            self.assertEqual(prints[r["booked_estimate_id"]]["period_coverage"], "full_year")

    def test_the_policy_reproduces_what_the_release_already_booked(self):
        """rc53 declares the choice; it does not change it. Every booked value equals the
        transcribed series to the gram, so no national number moves."""
        source_prints = {r["estimate_id"]: r for r in rows(VINTAGES)}
        series = {(r["fiscal_year"], r["consumer"]): r for r in rows(CONSUMERS)
                  if r["revision_status"] in ("final", "provisional")}
        for fy in PERIODS:
            for consumer in ("brick_kilns", "cement"):
                kt, estimate_id, rule = solid_fuels.booking(fy, consumer)
                if rule == "older_vintage_closes_balance":
                    self.assertEqual((fy, consumer), ("2015-16", "brick_kilns"))
                    self.assertAlmostEqual(kt, 3337.102, places=3)
                    continue
                if rule == "latest_full_year_revision":
                    source = source_prints[estimate_id]
                    self.assertEqual(source["reference_fiscal_year"], fy)
                    self.assertEqual(source["period_coverage"], "full_year")
                    self.assertEqual(source["edition_year"], "2026")
                    self.assertEqual(source["table_id"], "annex Table 14.1 sec.4")
                    self.assertAlmostEqual(kt, float(source["value"]), places=6)
                    continue
                self.assertAlmostEqual(kt, float(series[(fy, consumer)]["coal_kt"]), places=6,
                                       msg="%s %s booked %s" % (fy, consumer, estimate_id))

    def test_a_booked_estimate_must_name_the_period_and_sector_it_claims(self):
        with self.assertRaises(KeyError):
            solid_fuels._booked()["nonexistent"]
        for fy in PERIODS:
            kt, estimate_id, _ = solid_fuels.booking(fy, "cement")
            self.assertIn(fy, estimate_id)
            self.assertTrue(estimate_id.endswith("cement_other"))


if __name__ == "__main__":
    unittest.main()
