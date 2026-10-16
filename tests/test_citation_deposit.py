"""A file the manuscripts cite as evidence should be one a reader can open.

WHY THIS TEST EXISTS. Section 12 tells the reader that the derived quantities "are
deposited in full". The papers separately cite output files by path as the evidence behind
particular claims. Both sentences were true of different sets and nothing compared them, so
a results section could point at a table the archive does not contain and the suite stayed
green. Fifty-seven of the ninety-seven cited paths were in that position when this was first
measured.

WHAT THIS HOLDS. The undeposited count is a RATCHET and may only fall. It is not asserted to
be zero, because zero is not obviously the right answer: some of those files are working
intermediates and the right fix for them is for the paper to cite the deposited product that
carries the same numbers, not for the deposit to grow. Either fix lowers the count, which is
the point - the ceiling makes the choice visible instead of letting a new citation quietly
add to the pile.

Lowering the ceiling is free and expected. Raising it needs a written reason here, the same
discipline the uncited-artifact ratchet carries.
"""
import collections
import os
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

AUDIT = os.path.join(ROOT, "outputs", "pakemis_citation_deposit_audit.csv")

# Measured at 57 on 2026-09-30 (rc64), the round that first compared the two sets.
# Lowered to 53 in the same round: three tables with no deposited equivalent were added to
# PRODUCT_PATTERNS (the transport provincial-shape pair and waste_uncertainty_2024, which
# carries Approach-1 percentages pakemis_joint_uncertainty.csv does not hold), and the
# agriculture monthly citation was re-pointed at the nine-year product that already ships,
# of which it is the FY2023-24 slice.
#
# RE-BASED 53 -> 171 in cycle 37, and the reason is the instrument, not the tree. The audit
# matched `\texttt{outputs/x.csv}` and the sector appendices write the bare `\texttt{x.csv}`,
# so it saw 111 of the 305 files the manuscripts actually name. 194 were invisible; 118 of
# those are undeposited. Nothing got worse - the measurement got wider, and a reader cannot
# obtain a file any better for its name having been typeset with a directory in front of it.
# The 22 at the `sector_headline` tier were shipped in the same commit, because the test
# below calls that gap indefensible and it was green only through the blindness.
#
# The PRE-REPAIR ratchet is preserved exactly rather than absorbed: the path-named subset is
# still held at 53 by its own assertion, so the set the old number described cannot grow while
# the wider one is being worked down. Both may only FALL.
# rc68 replaces file-name-heavy narrative with source/coverage tables; the live
# audit now has 192 citation rows, of which 131 cite non-deposit working files.
# Lower the ratchet to that measured set so later growth remains visible.
# rc68 release repair: the held products entered the deposit, so four cited working files
# became deposited (131 -> 127).
UNDEPOSITED_CEILING = 127
PATH_NAMED_UNDEPOSITED_CEILING = 53

# No cited file may be absent from the REPOSITORY. That is a different and worse failure
# than being absent from the deposit - it means the citation points at nothing at all - and
# it is asserted at zero rather than ratcheted.
ABSENT_ENTIRELY = 0


class TestEveryCitationIsObtainable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(AUDIT):
            raise unittest.SkipTest("the citation audit has not been built in this checkout")
        cls.rows = read_rows(AUDIT)
        cls.citations = [r for r in cls.rows if r["row_kind"] == "citation"]

    def test_no_citation_points_at_a_file_that_does_not_exist(self):
        gone = [r["artifact"] for r in self.citations
                if "ABSENT FROM THE REPOSITORY" in r["verdict"]]
        self.assertEqual(
            len(gone), ABSENT_ENTIRELY,
            "the manuscripts cite files that do not exist anywhere: %s" % gone)

    def test_the_undeposited_count_has_not_grown(self):
        live = [r["artifact"] for r in self.citations if r["in_deposit"] == "no"]
        self.assertLessEqual(
            len(live), UNDEPOSITED_CEILING,
            "cited-but-not-deposited rose to %d (ceiling %d). Either ship the file (a "
            "literal entry in release_manifest.PRODUCT_PATTERNS) or cite the deposited "
            "product that carries the same numbers - both lower the count. Raising the "
            "ceiling needs a reason written into this file.\n  %s"
            % (len(live), UNDEPOSITED_CEILING, "\n  ".join(sorted(live))))

    def test_the_pre_repair_subset_has_not_grown_either(self):
        """The old ratchet, kept on the set it actually measured.

        Re-basing a ceiling upward because the instrument improved is legitimate; quietly
        losing the old guard in the process is not. The files named WITH the outputs/ prefix
        are the set the 53 described, and 53 is still what they measure.
        """
        live = [r["artifact"] for r in self.citations
                if r["in_deposit"] == "no" and r["named_as"] in ("path", "both")]
        self.assertLessEqual(
            len(live), PATH_NAMED_UNDEPOSITED_CEILING,
            "cited-but-undeposited rose to %d among files named with the outputs/ prefix "
            "(ceiling %d). This is the ratchet that predates the notation repair; it is held "
            "separately so that widening the measurement cannot hide a regression in the part "
            "that was already being measured.\n  %s"
            % (len(live), PATH_NAMED_UNDEPOSITED_CEILING, "\n  ".join(sorted(live))))

    def test_the_audit_sees_both_notations(self):
        """A dead half leaves the gate looking healthy - the holdings-layer lesson again.

        The audit read one of the two notations the manuscripts use for a filename and nothing
        said so, so 194 citations were absent from a register whose subject is exactly which
        cited files a reader can obtain. This asserts both notations are still being found, in
        the quantities the corpus really contains, so the blindness cannot return silently.
        """
        counts = collections.Counter(r["named_as"] for r in self.citations)
        self.assertGreater(
            counts["bare"], 150,
            "only %d citations were found in the BARE notation. The sector appendices name "
            "their tables that way (itemised lists of filenames), so a collapse here means "
            "the scan stopped resolving them - which is how 194 files went missing from this "
            "register once already." % counts["bare"])
        self.assertGreater(
            counts["path"] + counts["both"], 30,
            "only %d citations were found in the PATH notation, which the national sections "
            "and agriculture's appendix use" % (counts["path"] + counts["both"]))
        self.assertFalse(
            [r["artifact"] for r in self.citations if not r["named_as"]],
            "a citation row with no notation recorded: the column is how the two halves of "
            "this register were told apart and it may not be blank")

    def test_the_ceiling_is_not_slack(self):
        """A ceiling far above the live count stops measuring anything."""
        live = sum(1 for r in self.citations if r["in_deposit"] == "no")
        self.assertGreaterEqual(
            live, UNDEPOSITED_CEILING - 3,
            "the live count is %d against a ceiling of %d; lower the ceiling to the live "
            "count so the next regression is caught" % (live, UNDEPOSITED_CEILING))

    def test_no_sector_headline_product_is_cited_without_being_deposited(self):
        """The tier where the gap is indefensible.

        An `intermediate` cited in a paper is an argument about what that file is. A
        `sector_headline` is a sector's own headline result: if a paper cites one, the
        archive must contain it, and there is nothing to debate.
        """
        bad = [r["artifact"] for r in self.citations
               if r["in_deposit"] == "no" and r["role"] == "sector_headline"]
        self.assertFalse(
            sorted(bad),
            "sector headline products cited by a paper and missing from the deposit: %s"
            % sorted(bad))

    def test_the_audit_carries_the_denominator_and_the_sections(self):
        self.assertGreaterEqual(len(self.citations), 50,
                                "the audit should cover every cited path, not a sample")
        blank = [r["artifact"] for r in self.citations if not r["cited_in"]]
        self.assertFalse(blank, "citations with no citing section recorded: %s" % blank)

    def test_the_shipped_audit_matches_a_fresh_build(self):
        r = subprocess.run(
            [sys.executable,
             os.path.join(ROOT, "scripts", "build_citation_deposit_audit.py"), "--check"],
            capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(r.returncode, 0,
                         "the citation audit is stale; rebuild it.\n%s%s"
                         % (r.stdout, r.stderr))


if __name__ == "__main__":
    unittest.main()
