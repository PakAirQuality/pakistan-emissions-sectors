"""Gates on the 108-month coverage report and on the evidence class it can now show.

WHAT IS BEING PROTECTED. The report is an assembly, not a computation: it reads the monthly
product's classes and the annual product's declared absences and puts them in the view the
reviewer asked for. An assembly can fail in exactly two ways - by losing mass on the way
through, or by turning an absence into a blank - and both are asserted here.

THE SECOND HALF is the evidence class. 282 rows carrying 1,515.5 Mt shipped with the field
empty, unpoliced by any test and unpublished by any output, and it stayed that way through
several releases because nothing looked. The grading is derived from the basis each category
already declares; what these tests hold is that no priced row goes back to being blank.

Run:  python3 -m unittest discover tests
"""
import collections
import csv
import os
import sys
import unittest
from pkinv.core.io import read_rows
from _support import OUT, ROOT


DETAIL = os.path.join(OUT, "pakemis_monthly_coverage.csv")
SUMMARY = os.path.join(OUT, "pakemis_monthly_coverage_summary.csv")
PRODUCT = os.path.join(OUT, "pakemis_monthly_fy2015_16_fy2023_24.csv")
ATOM = os.path.join(OUT, "pakemis_atomic_annual.csv")

# EMPTY since rc20: the last two absent sector-years (industry and transport FY2015-16)
# closed when the Pakistan Oil Report 2015-2016 was recovered from the public record.
# Still listed rather than counted so that a NEW absence appearing is a failure someone
# has to come and justify, not a number to bump.
EXPECTED_ABSENT = set()

# Rounding: the report sums per (month, sector, category, class) and rounds each group, so it
# reproduces the product to the rounding floor rather than bit-for-bit.
MASS_TOLERANCE = 1e-5


def _rows(path):
    return read_rows(path)


class TheSummaryAnswersTheQuestionAsked(unittest.TestCase):
    def setUp(self):
        self.rows = _rows(SUMMARY)

    def test_it_has_exactly_one_row_per_month_of_the_window(self):
        self.assertEqual(108, len(self.rows))
        months = [r["month"] for r in self.rows]
        self.assertEqual(len(months), len(set(months)))
        self.assertEqual("201507", min(months))
        self.assertEqual("202406", max(months))

    def test_every_month_names_a_period(self):
        for row in self.rows:
            self.assertTrue(row["period_id"], row["month"])

    def test_the_class_masses_sum_to_the_month(self):
        for row in self.rows:
            parts = sum(float(row[k]) for k in ("TE1_Mt", "TE2_Mt", "TE3_Mt", "TE4_Mt"))
            self.assertAlmostEqual(parts, float(row["co2e_Mt_AR5"]), places=4, msg=row["month"])

    def test_the_observed_concentration_is_visible_rather_than_averaged_away(self):
        """The finding a single headline would hide.

        The strong classes sit in the years OCAC's panel reaches. This asserts the report
        still SHOWS that - if every year came out alike, either the panel stopped mattering
        or the report stopped distinguishing years, and both need looking at.
        """
        by_period = collections.defaultdict(lambda: [0.0, 0.0])
        for row in self.rows:
            by_period[row["period_id"]][0] += float(row["TE1_Mt"]) + float(row["TE2_Mt"])
            by_period[row["period_id"]][1] += float(row["co2e_Mt_AR5"])
        shares = {p: 100.0 * o / t for p, (o, t) in by_period.items() if t}
        self.assertEqual(9, len(shares))
        early = max(shares[p] for p in shares if p < "FY2021-22")
        late = min(shares[p] for p in shares if p >= "FY2021-22")
        self.assertGreater(late, early,
                           "the panel years no longer show a higher observed share than the "
                           "years before it: %s" % sorted(shares.items()))


class ItLosesNothingOnTheWayThrough(unittest.TestCase):
    def test_each_month_reproduces_the_monthly_product(self):
        product = collections.defaultdict(float)
        for row in _rows(PRODUCT):
            product[row["month"]] += float(row["co2e_Mt_AR5"] or 0.0)
        report = {r["month"]: float(r["co2e_Mt_AR5"]) for r in _rows(SUMMARY)}
        self.assertEqual(set(product), set(report))
        for month, mass in sorted(product.items()):
            self.assertAlmostEqual(mass, report[month], delta=MASS_TOLERANCE, msg=month)

    def test_the_detail_and_the_summary_are_the_same_mass(self):
        detail = collections.defaultdict(float)
        for row in _rows(DETAIL):
            if row["co2e_Mt_AR5"]:
                detail[row["month"]] += float(row["co2e_Mt_AR5"])
        for row in _rows(SUMMARY):
            self.assertAlmostEqual(detail[row["month"]], float(row["co2e_Mt_AR5"]),
                                   delta=MASS_TOLERANCE, msg=row["month"])


class AnAbsenceIsStatedNotBlank(unittest.TestCase):
    def setUp(self):
        self.rows = _rows(DETAIL)

    def test_the_missing_sector_years_are_exactly_the_declared_ones(self):
        found = {(r["sector_id"], r["period_id"]) for r in self.rows
                 if r["temporal_evidence_class"] == "missing"}
        self.assertEqual(EXPECTED_ABSENT, found)

    def test_each_absence_covers_all_twelve_of_its_months_and_carries_a_reason(self):
        missing = [r for r in self.rows if r["temporal_evidence_class"] == "missing"]
        self.assertEqual(12 * len(EXPECTED_ABSENT), len(missing))
        by_year = collections.Counter((r["sector_id"], r["period_id"]) for r in missing)
        for key, count in by_year.items():
            self.assertEqual(12, count, key)
        for row in missing:
            self.assertTrue(row["state_basis"].strip(),
                            "a missing cell with no reason is the blank this report exists "
                            "to remove: %s" % row)
            self.assertEqual("", row["co2e_Mt_AR5"])

    def test_a_missing_sector_year_has_no_priced_row_anywhere(self):
        priced = {(r["sector_id"], r["period_id"]) for r in self.rows
                  if r["temporal_evidence_class"] != "missing"}
        self.assertEqual(set(), priced & EXPECTED_ABSENT)

    def test_the_class_vocabulary_is_closed(self):
        """`missing` left the live vocabulary with the last absent sector-year
        (rc20); the closed set is asserted so a fifth class cannot appear
        silently, and `missing` returns to it with the next partial year."""
        self.assertEqual({"TE1", "TE2", "TE3", "TE4"},
                         {r["temporal_evidence_class"] for r in self.rows})


class TheEvidenceClassSilenceIsClosed(unittest.TestCase):
    def setUp(self):
        self.rows = _rows(ATOM)

    def test_no_priced_row_carries_an_empty_evidence_class(self):
        """1,515.5 Mt across 282 rows used to. Nothing tested it and nothing published it."""
        blank = [r for r in self.rows if r["co2e_Mt_AR5"] and not r["evidence_class"]]
        self.assertEqual([], blank,
                         "%d priced rows carry no evidence class: %s"
                         % (len(blank), sorted({(r["sector_id"], r["period_id"])
                                                for r in blank})))

    def test_the_only_ungraded_rows_are_the_ones_with_nothing_to_grade(self):
        """The other direction. A declared-absent sector-year has no quantity, so filling its
        class would be the same overclaim pointing the other way."""
        blank = {(r["sector_id"], r["period_id"]) for r in self.rows
                 if not r["evidence_class"]}
        self.assertEqual(EXPECTED_ABSENT, blank)

    def test_the_class_is_derived_from_the_declared_basis_not_the_reference_year(self):
        """Enteric fermentation is an ENUMERATION in the census year and a PROJECTION in the
        other eight. If the history ever came out at the reference year's grade, something is
        stamping it from `engine.build_components` again."""
        from pkinv.sectors.agriculture import fiscal_series
        self.assertEqual("E3", fiscal_series.evidence_class_for("Enteric fermentation", ""))
        self.assertEqual("E2", fiscal_series.evidence_class_for("Rice cultivation", ""))
        self.assertEqual("E2", fiscal_series.evidence_class_for(
            "Managed soils", "Direct N2O - synthetic fertiliser (upland)"))
        self.assertEqual("E3", fiscal_series.evidence_class_for(
            "Managed soils", "Indirect N2O - volatilisation (pasture, cattle-type)"))

    def test_an_unknown_nitrogen_pool_raises_rather_than_defaulting(self):
        """The positive control. A silent default is how an unclassified stream would come
        back without anyone noticing."""
        from pkinv.sectors.agriculture import fiscal_series
        with self.assertRaises(KeyError):
            fiscal_series.evidence_class_for("Managed soils", "Direct N2O - seaweed")


if __name__ == "__main__":
    unittest.main()
