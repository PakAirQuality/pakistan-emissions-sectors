"""The pre-July-2021 monthly gap is the SOURCE's boundary, not an acquisition nobody made.

WHY THIS TEST EXISTS. Section 12 grades the historical monthly product below A- and prices
the one acquisition that would fix it: OCAC's monthly sectoral-sales editions for July 2015 to
June 2021, worth 283.2 Mt of nine-year mass and the difference between 21.62 and 14.68 per
cent against a 15 per cent gate. For several releases the paper said only that those editions
"are not held" and that the request was "drafted and unsent". Both true, and together they
read as a download nobody had got round to.

They were never published. OCAC's archive index lists monthly editions from the current month
back to July 2021 and stops; before that date it carries fiscal-year compilations only, back
to FY2016-17, which this inventory already holds as its annual controls (verified 2026-09-30,
logged in data/raw/ACQUISITION_LOG_ocac_monthly_pre2021.csv). So no acquisition of a published
file closes the gap - only a request to the compiler does, which is a different kind of
limitation and is now what the paper says.

WHAT THIS HOLDS. The two facts the paragraph rests on, both read from the tree rather than
transcribed: that the held monthly series really does begin at July 2021 and run contiguously,
and that the request still records WHY it is necessary. If a pre-2021 edition ever lands, the
first test fails and the paragraph must be rewritten - which is the point, because a caveat
that outlives its reason is the defect this campaign keeps finding in itself.

NOT ASSERTED: that OCAC will never publish them. The claim is about what the archive holds on
a stated date, and the acquisition log carries that date.
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MONTHLY_DIR = os.path.join(ROOT, "sources", "Aviation", "ocac_monthly")
LOG = os.path.join(ROOT, "data", "raw", "ACQUISITION_LOG_ocac_monthly_pre2021.csv")
REGISTER = os.path.join(ROOT, "data", "shared", "requests", "monthly_request_register.csv")

FIRST_HELD = (2021, 7)


def _held_months():
    if not os.path.isdir(MONTHLY_DIR):
        return []
    out = []
    for name in sorted(os.listdir(MONTHLY_DIR)):
        match = re.fullmatch(r"OCAC_(\d{4})_(\d{2})\.pdf", name)
        if match:
            out.append((int(match.group(1)), int(match.group(2))))
    return sorted(out)


class TestTheMonthlyBoundaryIsTheSources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.months = _held_months()
        if not cls.months:
            raise unittest.SkipTest("the OCAC monthly cache is not in this checkout")

    def test_the_held_series_begins_where_the_archive_does(self):
        self.assertEqual(
            self.months[0], FIRST_HELD,
            "the held OCAC monthly series now begins at %s, not %s. If an EARLIER edition has "
            "arrived, Section 12's paragraph is wrong twice over - the gap is no longer the "
            "source's boundary, and the 21.62 per cent grade may now be closable. Rewrite it "
            "rather than adjusting this." % (self.months[0], FIRST_HELD))

    def test_the_held_series_is_contiguous(self):
        """A hole inside the held span would be an acquisition gap, which is the OPPOSITE claim."""
        gaps = []
        for previous, current in zip(self.months, self.months[1:]):
            expected = (previous[0] + 1, 1) if previous[1] == 12 else (previous[0], previous[1] + 1)
            if current != expected:
                gaps.append("%s -> %s" % (previous, current))
        self.assertFalse(
            gaps,
            "the held monthly series has holes: %s. Section 12 says the pre-July-2021 months "
            "are flat BECAUSE the editions were never published; a hole after July 2021 would "
            "be a different thing entirely - an edition that exists and is missing here."
            % gaps)

    def test_the_negative_is_logged_with_its_date_and_its_reason(self):
        self.assertTrue(os.path.exists(LOG),
                        "the verified negative is not logged. Every acquisition attempt gets a "
                        "row - hits, negatives and blocked sources alike.")
        with open(LOG, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("archives", text,
                      "the log does not name the index that was read, so the negative cannot "
                      "be rechecked")
        self.assertRegex(text, r"\d{4}-\d{2}-\d{2}",
                         "the log carries no date, and a claim about what an archive holds is "
                         "only true on a date")
        self.assertIn("never published", text,
                      "the log does not distinguish this negative from a dead site or a wrong "
                      "address - three different facts this project has conflated before")

    def test_the_request_records_why_it_is_necessary(self):
        with open(REGISTER, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("MON-OCAC-01", text, "the request row is gone")
        row = [line for line in text.splitlines() if line.startswith("MON-OCAC-01")]
        self.assertTrue(row, "MON-OCAC-01 is not a register row")
        self.assertIn(
            "back to July 2021", row[0],
            "MON-OCAC-01 no longer records that OCAC's archive begins at July 2021. Without "
            "it the row says only that later editions are held, which reads as a request "
            "nobody has sent rather than a request that is the only route.")


if __name__ == "__main__":
    unittest.main()
