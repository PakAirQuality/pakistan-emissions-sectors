"""A file a registered claim reads is not a working file, whatever the register calls it.

WHY THIS TEST EXISTS. data/catalog/artifact_roles.csv types every shipped file by pattern, and
its vocabulary is a set of promises:

    canonical        a product the release is FOR. Must be hashed in the manifest AND named
                     in a manuscript.
    diagnostic       evidence behind a claim; must be named somewhere.
    intermediate     a working file. NO READER-FACING CLAIM RESTS ON IT.

The register has always enforced that in one direction: a canonical product must be cited, and
tests/test_artifact_inventory.py fails if it is not. It never enforced the other direction -
nothing asked whether a file called a working file has a reader-facing claim resting on it.
That is the third asymmetry of this shape the campaign has found, and the register's own header
explains why the first one mattered: "a canonical product cited nowhere was indistinguishable
from a diagnostic nobody needed".

The other direction is testable, because a claim getter in tests/paper_numbers/ reads a product
BY NAME and the manuscript prints the figure computed from it. If a getter reads a file, a
reader-facing claim demonstrably rests on it and `intermediate` is factually wrong. Measured on
2026-09-30: 135 of the 248 products a claim or table getter reads are typed `intermediate`, and
every one of them fell through the `*` catch-all rather than being typed deliberately.

THAT CATCH-ALL IS THE ROOT CAUSE, and it is worth naming precisely. Its row reads

    *,intermediate,varies,a working file the build needs and no reader-facing claim rests on

so the role a file receives when NOBODY HAS CLASSIFIED IT carries a substantive claim about it.
A file no pattern names is not thereby a working file. The catch-all asserts where it should
defer, and 135 files inherit the assertion.

WHAT THIS DOES. It holds the set at its measured size and refuses new members, rather than
asserting zero, because the fix is not one edit:

  The 51 that were named in a manuscript are GONE from this set, and not by writing 51 pattern
  rows: the catch-all now derives `diagnostic` from the citation itself, so they left the
  moment the derivation landed. That is why the pattern route was abandoned - the fall-through
  files share no naming structure, and a validated cover needed 61 patterns to reach 74 files.

  83 are named NOWHERE, and those cannot be re-typed honestly at all, because `diagnostic`
  REQUIRES being named somewhere. They are a different defect - a printed figure computed from
  a file no manuscript names, so a reader cannot reach the evidence - and each needs a citation
  or the retirement of a claim. A programme, not a cycle. With the citable ones gone the two
  ceilings below now coincide, which is the honest shape: what remains is exactly the residue.

NOT ASSERTED: that every claim-read file should be `canonical`. That role additionally commits
the release to shipping the file, and the deposit is curated on purpose.
"""
import io
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                      # noqa: E402

INVENTORY = os.path.join(ROOT, "outputs", "pakemis_artifact_inventory.csv")
REGISTRY_DIR = os.path.join(ROOT, "tests", "paper_numbers")
REGISTRY_FILES = ("doc_claims.py", "tables.py", "labelled_tables.py",
                  "quantity_policy.py", "_common.py")

# Only real reader calls. Matching any quoted filename would count a name in a comment, and a
# comment is not a claim. Checked both ways on the audit subset: same 23 files either way.
READER = re.compile(
    r"_(?:rows|rows_banner|cell|data_rows|data_rows_nocomment|csv_rows|first_where|"
    r"max_where|min_where|sum_where|sum_prefix)\(\s*[\"']([\w./-]+\.csv)[\"']")

# 13 -> 9 (cycle 35): residential, the second glob case - its appendix listed twelve tables
# by description and named them collectively as residential_*.csv, so a reader was told what
# exists and given no filename for any of it. 18 of its 27 outputs were named nowhere. All
# three predictions matched exactly (9, 28, 42).
# 21 -> 13 (cycle 34): railways. Its appendix cited its outputs with a GLOB - "seventeen
# railways_* files" - and the count was contradicted by the run manifest named in the same
# clause, which lists 21 generated_outputs. All three predictions matched exactly (13, 34, 46),
# and five sector_headline files met their role's "must be named in that sector's paper" for the
# first time.
# 34 -> 21 (cycle 33): power's appendix, which is a different case from the other three - it
# already named its six headline products and never mentioned its thirteen evidence tables at
# all, so this ADDED a paragraph rather than completing one. Predicted 21 and measured 21, the
# first prediction in this group to match on the first attempt; \allowbreak now goes on every
# name rather than only names over 40 characters, so the layout is safe without depending on
# nobody adding a longer filename.
# 47 -> 34 (cycle 32): the aviation appendix, which described its outputs BY ROW COUNT and
# named none. ⚠ AND A CORRECTION: the 47 recorded below was true when measured and then went
# stale within the same cycle. Cycle 31's layout repair added \allowbreak inside every filename
# over 40 characters - necessary, since a 57-character name overran by 52.2pt - and the citation
# scanner normalised the escaped underscore but not the break hint, so SEVEN files it had just
# been taught to see went quietly back to uncited. The true figure after cycle 31 was 52, not
# 47. It surfaced because this cycle predicted 34 and measured 51; the scanner now normalises
# every device a filename must carry, through one shared function, and
# tests/test_citation_scan_normalisation.py holds it.
# 67 -> 47 (cycle 31): the fugitives "Reproduction and generated products" section, which had
# gone so far as to explain the registered filenames' suffix convention without printing a
# single filename. Twenty tables named, each described from its own columns. THREE sector
# appendices now share this defect (IPPU, fugitives, aviation) and a fourth paper's, power's,
# already named six of its own - so this is a house style that describes outputs instead of
# naming them, not three oversights.
# 81 -> 67 (cycle 30): the IPPU reproduction appendix was titled "Reproduction and generated
# outputs" and described fourteen evidence tables without naming any of them. It now names them,
# each described from its own columns rather than from the paragraph's phrasing, so all fourteen
# left this set at once. The one phrase whose file could not be identified with confidence - the
# CRT activity-factor bridge - was deliberately left unpaired: a wrong filename beside a right
# description is worse than silence.
# 83 -> 81 (cycle 29): naming ippu_facility_registry.csv and
# ippu_cement_producer_census_2024.csv in the IPPU study-area section - where the prose already
# described both - moved them out of this set entirely, since the catch-all now types a named
# fall-through file `diagnostic`. That is the shape the remaining debt closes in: one citation
# where the paper already discusses the table, not a sweep of filenames into prose.
# Measured 2026-09-30 (rc64), after the DOC_GLOBS repair AND the deferring catch-all: 81
# claim-read products are typed `intermediate` and ALL 83 are named nowhere. The 51 that were
# named in a manuscript are gone from this set entirely - the catch-all now types them
# `diagnostic` from the citation itself - which collapses the two ceilings onto each other and
# leaves exactly the residue that re-typing cannot fix. Both may only FALL.
# 9 -> 0 (cycle 36): the last nine, each named in the sentence that already discussed it -
# agriculture's appendix (the nitrogen stage-flow ledger, the IPCC/EMEP stage comparison, the
# air Monte Carlo intervals), the national uncertainty decomposition beside its "34 of 202
# component rows", the waste release assignment beside its already-named candidates, the two
# transport CNG tables inside the clause that invoked their epistemic class, the industry
# captive screening beside the 5.55 Mt figure, and the delivered-gas closure variant. That
# closes at ZERO the set that was 83 at cycle 29. Both ceilings are now exact gates rather
# than ratchets: a single new claim-read working file fails the suite. `test_neither_ceiling_is
# _slack` is vacuous at zero, which is right - zero cannot be slack.
CLAIM_READ_INTERMEDIATE_CEILING = 0
CLAIM_READ_INTERMEDIATE_UNCITED_CEILING = 0


def _claim_read_names():
    text = ""
    for name in REGISTRY_FILES:
        path = os.path.join(REGISTRY_DIR, name)
        if os.path.exists(path):
            with io.open(path, encoding="utf-8") as handle:
                text += handle.read()
    return set(READER.findall(text))


class TestNoClaimRestsOnAWorkingFile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not os.path.exists(INVENTORY):
            raise unittest.SkipTest("the artifact inventory has not been built here")
        cls.inventory = {r["artifact"]: r for r in read_rows(INVENTORY)}
        cls.names = _claim_read_names()
        # PATH-EXACT, not by basename. 17 basenames appear at two paths (activity/X versus
        # activity/public/X), and a getter passes the outputs-relative path, so an exact match
        # removes the ambiguity rather than tolerating it. Checked: exact and basename
        # matching returned the same 135, so nothing here depends on the choice - but the next
        # collision might.
        cls.claim_read = [cls.inventory[n] for n in sorted(cls.names) if n in cls.inventory]

    def test_the_detector_still_finds_the_registry(self):
        """A dead detector leaves the gate looking healthy - the holdings-layer lesson."""
        self.assertGreater(
            len(self.names), 150,
            "the claim-read sweep found only %d product names. Either the reader helpers were "
            "renamed or tests/paper_numbers moved, and a sweep that finds nothing passes "
            "forever." % len(self.names))
        self.assertGreater(
            len(self.claim_read), 150,
            "only %d of %d claim-read names resolve to an inventory row; the inventory's "
            "`artifact` column is outputs-relative and a getter passes the same form, so a "
            "large shortfall means one of the two changed shape"
            % (len(self.claim_read), len(self.names)))

    def test_the_set_of_claim_read_working_files_only_shrinks(self):
        bad = sorted(r["artifact"] for r in self.claim_read if r["role"] == "intermediate")
        self.assertLessEqual(
            len(bad), CLAIM_READ_INTERMEDIATE_CEILING,
            "%d products are typed `intermediate` - 'no reader-facing claim rests on it' - "
            "while a registered claim reads them (ceiling %d). Type the new one `diagnostic` "
            "if a manuscript names it, and if none does, that is the deeper problem: a "
            "printed figure whose evidence file a reader cannot find.\n  %s"
            % (len(bad), CLAIM_READ_INTERMEDIATE_CEILING, "\n  ".join(bad[:10])))

    def test_the_uncitable_subset_only_shrinks(self):
        """The 84 that cannot be re-typed, because `diagnostic` requires being named."""
        bad = sorted(r["artifact"] for r in self.claim_read
                     if r["role"] == "intermediate" and r["cited_in"] == "none")
        self.assertLessEqual(
            len(bad), CLAIM_READ_INTERMEDIATE_UNCITED_CEILING,
            "%d products are read by a registered claim and named in NO manuscript (ceiling "
            "%d). A reader cannot reach the evidence behind the printed figure. Cite the file "
            "or retire the claim - re-typing cannot fix this one, because `diagnostic` "
            "requires being named somewhere.\n  %s"
            % (len(bad), CLAIM_READ_INTERMEDIATE_UNCITED_CEILING, "\n  ".join(bad[:10])))

    def test_neither_ceiling_is_slack(self):
        live = sum(1 for r in self.claim_read if r["role"] == "intermediate")
        self.assertGreaterEqual(
            live, CLAIM_READ_INTERMEDIATE_CEILING - 20,
            "the live count is %d against a ceiling of %d; lower the ceiling so the next "
            "regression is caught" % (live, CLAIM_READ_INTERMEDIATE_CEILING))

    def test_the_catch_all_is_last_and_is_the_only_bulk_source_of_this(self):
        """The root cause, asserted so a future edit cannot quietly widen it.

        The file is first-match-wins and its `*` row must stay last - sorting it once put the
        catch-all first and it swallowed every artifact, reporting 886 intermediates and zero
        uncited. This asserts the ordering AND that the claim-read intermediates really are
        falling through rather than being typed on purpose, because those are different
        problems with different fixes.
        """
        with io.open(os.path.join(ROOT, "data", "catalog", "artifact_roles.csv"),
                     encoding="utf-8") as handle:
            lines = handle.read().splitlines()
        rows = [line.split(",")[0] for line in lines
                if line and not line.startswith("#")]
        body = [r for r in rows if r != "pattern"]
        self.assertEqual(body[-1], "*",
                         "the `*` catch-all is no longer the last pattern. First match wins, "
                         "so a catch-all anywhere else swallows everything after it.")
        typed = sorted(r["artifact"] for r in self.claim_read
                       if r["role"] == "intermediate" and r["matched_pattern"] != "*")
        self.assertFalse(
            typed,
            "these claim-read products are typed `intermediate` by a SPECIFIC pattern rather "
            "than by the catch-all, which means somebody declared that no reader-facing claim "
            "rests on them while a claim reads them. That is a contradiction to resolve, not "
            "a backlog item:\n  %s" % "\n  ".join(typed))


if __name__ == "__main__":
    unittest.main()
