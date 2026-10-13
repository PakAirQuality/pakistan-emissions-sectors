"""The decision record's SHAPE — never its verdict.

rc53's version of this file asserted `decision.startswith("OFFICIAL STAYS BOOKED")` on every row.
That made a scientific conclusion un-falsifiable by the suite: a build in which the evidence had
changed its mind would have failed the tests. It was the only place in the tree where a verdict was
pinned rather than a number, and it is retracted here. What is guarded instead is that the record
cannot LIE about what its tests established:

  - every test result carries one of three kinds, and the kinds mean what the policy says;
  - an `untested` result never appears as a reason to prefer either estimate;
  - a `constraint` is scored against the OFFICIAL series too, not only the candidate;
  - a decision states which of the two refusals it is making, and the one it may not make is
    "inadmissible because no annual survey exists" (IPCC 2006 Vol 1 Ch 5 permits a surrogate
    relationship developed from a single year).
"""
import csv
import os
import re
import unittest

from _support import OUTPUTS

OUT = os.path.join(OUTPUTS, "pakemis_industrial_coal_decision.csv")
PERIODS = ["%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024)]
STREAMS = ("Brick-kiln coal", "Cement-sector coal")
KINDS = ("constraint", "validation", "untested")


def rows():
    with open(OUT, encoding="utf-8") as h:
        return list(csv.DictReader(l for l in h if not l.startswith("#")))


def tests():
    return [r for r in rows() if r["test"] != "DECISION"]


def decisions():
    return [r for r in rows() if r["test"] == "DECISION"]


class TheRecordsShape(unittest.TestCase):
    def test_every_stream_year_is_decided_and_every_result_is_kinded(self):
        self.assertEqual({(r["stream"], r["fiscal_year"]) for r in decisions()},
                         {(s, fy) for s in STREAMS for fy in PERIODS})
        for r in tests():
            self.assertIn(r["kind"], KINDS, "%s %s %s" % (r["stream"], r["fiscal_year"], r["test"]))
            self.assertTrue(r["finding"].strip())

    def test_the_three_kinds_are_all_used(self):
        """A policy that never records an absence has not separated absence from failure."""
        used = {r["kind"] for r in tests()}
        self.assertEqual(used, set(KINDS))

    def test_a_constraint_names_who_it_is_scored_against(self):
        for r in tests():
            if r["kind"] == "constraint":
                self.assertIn(r["subject"], ("the OFFICIAL series", "the CANDIDATE", "both"))

    def test_the_official_series_is_scored_on_constraints_too(self):
        """The asymmetry rc53 had: only the candidate was ever scored. Where the official value
        violates a bound, the record must say so."""
        official = [r for r in tests()
                    if r["kind"] == "constraint" and r["subject"] == "the OFFICIAL series"]
        self.assertTrue(official)
        violated = [r for r in official if r["result"].startswith("VIOLATED")]
        self.assertTrue(violated, "no constraint is scored against the official series at all")
        for r in violated:
            self.assertIn("conditional", r["result"] + r["finding"],
                          "a violation asserted without its conditions is a claim, not a finding")

    def test_an_untested_result_never_favours_either_estimate(self):
        """The defect this policy exists to remove: rc53 wrote 'no company clinker is held' into a
        sentence concluding the candidate had failed."""
        for r in tests():
            if r["kind"] != "untested":
                continue
            text = (r["result"] + " " + r["finding"]).lower()
            # whole words: "closes" contains "loses", and the tonnage account does close
            words = set(re.findall(r"[a-z]+", text))
            for word in ("fails", "failed", "beaten", "loses", "lost", "wins", "won"):
                self.assertNotIn(word, words, "%s %s: an absence phrased as a failure"
                                 % (r["stream"], r["fiscal_year"]))
            self.assertNotIn("inadmissible because", text)

    def test_no_decision_rests_on_an_absence_being_a_failure(self):
        for r in decisions():
            self.assertIn("about the CANDIDATE's coverage rather than a test it failed", r["why"])

    def test_the_blocking_objection_is_the_defensible_one(self):
        """'One cross-section does not establish the trend' blocks adoption as a SERIES.
        'No reconstruction without an annual survey' would not be defensible, and must not appear."""
        blocking = [r for r in tests()
                    if r["test"] == "year-to-year activity" and r["kind"] == "untested"]
        self.assertEqual(len(blocking), len(PERIODS))
        for r in blocking:
            self.assertIn("does not make a surrogate reconstruction inadmissible", r["finding"])
            self.assertIn("Vol 1 Ch 5", r["finding"])

    def test_the_supply_and_use_result_is_not_called_evidence_where_it_is_not(self):
        """It closes because the two published tables balance by construction. Three of the nine
        years say so, and they must be typed `untested`, not scored."""
        closes = [r for r in tests() if r["test"] == "supply and use" and "NOT A TEST" in r["result"]]
        self.assertTrue(closes)
        for r in closes:
            self.assertEqual(r["kind"], "untested")
            self.assertIn("by construction", r["finding"])

    def test_the_record_carries_its_policy_version(self):
        self.assertEqual({r["policy_version"] for r in rows()}, {"rc54"})


if __name__ == "__main__":
    unittest.main()
