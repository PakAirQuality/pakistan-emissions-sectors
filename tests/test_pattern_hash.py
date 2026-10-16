"""The pattern a stream-year was placed on, measured instead of asserted.

WHY THIS FILE EXISTS. pakemis_spatial_weights_by_year.csv says, per stream-year, whether a
period's within-province pattern is its own or the reference year's carried back. Until now
that column was DERIVED FROM WHAT THE ENGINE CAN READ - a (surface, district_panel) pair
checked against a table of which periods each pair resolves. That is the right rule, and it is
still a statement about the build rather than a measurement of it. The module's own header
records how it failed once: the plant fleet satisfied the surface half of the rule while
failing the panel half for a whole pass, invisibly, and every consumer counted those
stream-years as measured in their own year.

pattern_hash is the measurement. It digests the normalised weight vector at the dispatch site
where the vector is used, so two stream-years that hash equal WERE placed on the same pattern
whatever any column claims. What this file holds is the agreement between the two: where the
registry says a period used its own evidence, the hash must not be the reference year's.
"""
import csv
import os
import unittest
from collections import Counter

from pkinv.paths import OUTPUTS
from pkinv.core.reporting_window import CORE_PERIOD_IDS

REGISTRY = os.path.join(OUTPUTS, "pakemis_spatial_weights_by_year.csv")
SURFACES = os.path.join(OUTPUTS, "pakemis_grid_stream_surfaces_by_year.csv")
REFERENCE = "FY2023-24"


def _rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(l for l in handle if not l.startswith("#")))


@unittest.skipUnless(os.path.exists(REGISTRY), "the weight registry has not been built")
class TestTheHashAgreesWithTheClaim(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows(REGISTRY)

    def test_no_period_claims_its_own_evidence_while_reusing_the_reference_pattern(self):
        """The overclaim this column exists to make impossible.

        A stream-year graded annual_observed_activity is counted, everywhere downstream, as
        spatially measured in its own year. If its weight vector hashes identical to the
        reference year's, it was not: it was the reference pattern under a label that says
        otherwise, and no amount of reading the grading rule would reveal it. This is the one
        assertion that could not have been written before the hash existed.
        """
        bad = [r for r in self.rows
               if r["spatial_time_basis"] == "annual_observed_activity"
               and r["period_id"] != REFERENCE
               and r["temporal_operator"] == "reference_pattern_reused"]
        self.assertFalse(
            bad, "%d stream-years claim their own year's evidence while carrying the reference "
                 "year's pattern: %s" % (len(bad), [r["source_stream_id"] for r in bad[:5]]))

    def test_every_backcast_really_is_one(self):
        """The claim in the other direction, which is just as falsifiable.

        reference_shape_backcast says the reference year's pattern was rescaled to this year's
        control. If the hash differs from the reference year's, the label is understating what
        the build did - the period had its own pattern and the registry gave the reader no way
        to know. Both directions are held because a grading that can only be wrong one way is
        a grading nobody checks.
        """
        wrong = [r for r in self.rows
                 if r["spatial_time_basis"] == "reference_shape_backcast"
                 and r["temporal_operator"] != "reference_pattern_reused"]
        self.assertFalse(
            wrong, "%d stream-years are labelled a backcast but were placed on a pattern that "
                   "is not the reference year's: %s"
                   % (len(wrong), [(r["source_stream_id"], r["period_id"]) for r in wrong[:5]]))

    def test_mass_that_was_never_placed_carries_no_pattern(self):
        """An S4 stream stops at the provincial control, so it has no within-province pattern.

        weight_for returns a vector for it anyway, and hashing that vector recorded a pattern
        that was computed and then not used - which read out as 189 unallocated stream-years
        "reusing the reference pattern" when what they had done was decline to place the mass
        at all. The hash answers "what was this mass placed on"; for mass never placed below
        ADM1 the answer is none.
        """
        for row in self.rows:
            if row["spatial_time_basis"] in ("unallocated", "not_present"):
                self.assertEqual(row["pattern_hash"], "", row["source_stream_id"])
                self.assertEqual(row["temporal_operator"], "not_placed", row["source_stream_id"])

    def test_the_operator_vocabulary_is_closed_and_every_value_is_produced(self):
        """Derived, never declared: a value no build emits makes the vocabulary vacuous."""
        seen = Counter(r["temporal_operator"] for r in self.rows)
        self.assertEqual(set(seen), {"own_period_pattern", "reference_pattern_reused",
                                     "reference_period", "not_placed"})
        for name, count in seen.items():
            self.assertGreater(count, 0, name)


@unittest.skipUnless(os.path.exists(SURFACES), "the by-year surfaces have not been built")
class TestTheSurfacesAreNowPerPeriod(unittest.TestCase):

    def test_the_registry_reads_every_supported_period(self):
        """The defect this product was added to fix.

        pakemis_grid_stream_surfaces.csv is the reference year's, and the registry read it for
        every period - so the surface, placement and district panel reported against FY2015-16
        were FY2023-24's. For most streams they coincide, which is why it went unnoticed. This
        asserts the by-year file actually distinguishes the periods it claims to.
        """
        rows = _rows(SURFACES)
        periods = {r["period_id"] for r in rows}
        self.assertEqual(periods, set(CORE_PERIOD_IDS))
        by_stream = {}
        for row in rows:
            by_stream.setdefault(row["source_stream_id"], set()).add(row["pattern_hash"])
        varying = [s for s, hashes in by_stream.items() if len(hashes) > 1]
        self.assertTrue(
            varying, "no stream's pattern differs across the supported periods, which would mean "
                     "the by-year file is the reference year repeated and the join that reads "
                     "it gains nothing")

    def test_a_hash_is_stable_across_two_reads_of_the_same_build(self):
        rows = _rows(SURFACES)
        again = _rows(SURFACES)
        self.assertEqual([r["pattern_hash"] for r in rows],
                         [r["pattern_hash"] for r in again])
        for row in rows:
            if row["pattern_hash"]:
                self.assertEqual(len(row["pattern_hash"]), 16, row["source_stream_id"])
                int(row["pattern_hash"], 16)


if __name__ == "__main__":
    unittest.main()
