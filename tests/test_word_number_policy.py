"""A quantity printed as an English WORD is outside every guard this repository has.

WHY THIS TEST EXISTS. `quantity_policy` sweeps siunitx arguments and numeric tabular cells,
so it sees \\num{12.6} and \\SI{18.0}{\\percent} and cannot see "twelve" or "eighteen
percent". DOC_CLAIMS anchors printed figures by regex, and nobody writes a regex for a word.
Between them they protect every printed quantity except the ones spelled out, and the gap has
been exercised three times:

  an IPPU contribution count read "eleven" and was wrong the moment a fifth arrived. It was
  fixed AT THAT SITE, and doc_claims still carries the note - "'eleven' cannot be repaired,
  and it was wrong the moment five arrived" - as a comment on that one claim.

  the railways paper said the CRT books "eleven times the metered fuel" in its abstract,
  introduction, discussion and conclusion. The product computed 12.615. Four sites, 13 per
  cent low, understating the paper's own finding.

  the railways paper said its quinquennial history shows a peak "five times" today's total,
  in a contribution list and a conclusion. The ratio is 5.84. Seventeen per cent low, again
  understating its own finding.

A lesson recorded as a comment on one claim protects one claim. So this is the rule.

WHAT THIS DOES. It sweeps the manuscripts for an English number word immediately before a
quantity-bearing word, and requires every site to be one of two declared things:

  EXEMPT - the word is not a quantity a product could move, and the reason is recorded here
  per site. The reasons are not one kind of exemption, which is why they are written out
  rather than counted: a constant of the calendar or the grain ("twelve times" for months); a
  methodological choice rather than a measurement (a draw count, a scenario input); a
  deliberate TEST THRESHOLD that must not track the product (rail N2O "exceeds five times the
  road value" is a floor chosen to catch a substitution); a hypothetical consequence of a
  rejected booking; external context that is not this inventory's product; a rounded
  restatement standing beside a registered exact figure; or a bound rather than a value.

  PENDING - product-backed, correct today, not yet promoted to a numeral with a claim. These
  are declared debt under a ratchet that may only fall.

Anything else fails, which inverts the burden: a NEW word-number has to be declared, and the
declaration is where somebody has to decide whether a product stands behind it.

WHAT THIS DOES NOT DO. It does not extend `quantity_policy` to all English number words.
That was considered and rejected (campaign decision D050): "one of", "a second", "half the
sector" and similar make the false-positive surface large enough that the sweep would be
argued with rather than obeyed. Naming the exceptions is the answer to that - an exemption
with a written reason is auditable, and a blanket rule with ad-hoc suppressions is not.
"""
import io
import os
from pkinv.paths import PAPER_NATIONAL_MAIN_REL, PAPER_NATIONAL_SECTIONS  # noqa: E402
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORDS = ("one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|"
         "fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|"
         "seventy|eighty|ninety|hundred|thousand|half|twice|double|triple")
UNITS = ("times|percent|per cent|fold|Mt|kt|Gg|tonnes|megatonnes|kilotonnes")
PATTERN = re.compile(r"\b(%s)[- ]?(?:\w+)?\s+(%s)\b" % (WORDS, UNITS), re.I)

# (doc, file, phrase) -> why the word is not a quantity a product could move.
EXEMPT = {
    ("railways", "04_methods.tex", "seven percent"):
        "the reason a test pins CO2e of CH4 at 30 exactly; the test is the claim",
    ("railways", "04b_emission_factors.tex", "five times"):
        "a deliberate TEST THRESHOLD - a floor chosen to catch a substitution, which must "
        "NOT track the 7.3 ratio or it would stop being a floor",
    ("railways", "05_validation.tex", "ten times"):
        "'nearly ten times the fuel' - rounded restatement; the exact ratio is registered",
    ("railways", "07_discussion.tex", "ten times"):
        "same rounded restatement in the discussion",
    ("railways", "07_discussion.tex", "three times"):
        "a count of incidents in this paper's own narrative",
    ("residential", "03_study_area_and_data.tex", "one percent"):
        "a survey-tail description; the weighted shares beside it are registered",
    ("transport", "01_introduction.tex", "six megatonnes"):
        "rounded; the 0.05 Mt net movement beside it is registered",
    ("transport", "07_discussion.tex", "six megatonnes"):
        "same figure, rounded, in the discussion",
    ("transport", "09_conclusion.tex", "six megatonnes"):
        "same figure, rounded, in the conclusion",
    ("transport", "03_study_area_and_data.tex", "one percent"):
        "a coincidence being WARNED about, not a result",
}

# Product-backed, correct today, not yet promoted. Declared debt: the ceiling may only fall.
PENDING = {
    ("aviation", "01_introduction.tex", "four times"): "resident-customer rows vs the movement estimate",
    ("fugitives", "03_study_area_and_data.tex", "thirty times"): "per-tonne factors vs the surface low",
    ("fugitives", "09_conclusion.tex", "five times"): "bracket endpoints vs the 2022 CRT",
    ("railways", "04_methods.tex", "four times"): "passenger vs freight train-kilometres",
    ("residential", "04b_emission_factors.tex", "five times"): "residential gas vs utility factor",
    ("residential", "04b_emission_factors.tex", "three times"): "kerosene ratio, same table note",
    ("residential", "05_validation.tex", "three times"): "1042274 TJ vs the filing's residential activity",
    ("transport", "03_study_area_and_data.tex", "eleven percent"): "the superseded pair's miss",
}

# Measured 2026-10-14 after the integrated manuscript and note revisions. May only fall.
PENDING_CEILING = 8


def _sites():
    roots = [PAPER_NATIONAL_SECTIONS]
    papers = os.path.join(ROOT, "papers")
    if os.path.isdir(papers):
        roots += [os.path.join(papers, d, "sections") for d in sorted(os.listdir(papers))
                  if os.path.isdir(os.path.join(papers, d, "sections"))]
    found = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        doc = ("national" if root.endswith(os.path.join(PAPER_NATIONAL_MAIN_REL, "sections"))
               else os.path.basename(os.path.dirname(root)))
        for name in sorted(os.listdir(root)):
            if not name.endswith(".tex"):
                continue
            with io.open(os.path.join(root, name), encoding="utf-8") as handle:
                for number, line in enumerate(handle, 1):
                    for match in PATTERN.finditer(line):
                        found.append((doc, name, match.group(0).lower(), number))
    current_main = os.path.join(ROOT, "paper_national", "versions", "v3", "paper.tex")
    if os.path.isfile(current_main):
        with io.open(current_main, encoding="utf-8") as handle:
            for number, line in enumerate(handle, 1):
                for match in PATTERN.finditer(line):
                    found.append(("integrated_main", "paper.tex", match.group(0).lower(), number))
    return found


class TestEveryWordNumberIsDeclared(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sites = _sites()

    def test_the_sweep_still_finds_something(self):
        """A dead detector leaves the gate looking healthy - the holdings-layer lesson."""
        self.assertGreater(
            len(self.sites), 15,
            "the word-number sweep found %d sites, which is too few to be real: the pattern "
            "or the manuscript paths have probably moved, and a sweep that finds nothing "
            "passes forever" % len(self.sites))

    def test_every_site_is_exempt_or_declared_pending(self):
        undeclared = sorted({(d, f, p) for d, f, p, _ in self.sites
                             if (d, f, p) not in EXEMPT and (d, f, p) not in PENDING})
        self.assertFalse(
            undeclared,
            "these printed quantities are spelled out as WORDS and declared nowhere. "
            "quantity_policy sweeps siunitx arguments and numeric tabular cells, so it "
            "cannot see them, and DOC_CLAIMS cannot anchor them. If a product stands behind "
            "the number, print it as \\num{} or \\SI{} and register a claim; if it does not, "
            "add it to EXEMPT with the reason it cannot go stale:\n  %s"
            % "\n  ".join("%s / %s: %r" % s for s in undeclared))

    def test_the_pending_debt_only_shrinks(self):
        live = sorted({(d, f, p) for d, f, p, _ in self.sites if (d, f, p) in PENDING})
        self.assertLessEqual(
            len(live), PENDING_CEILING,
            "word-numbers awaiting promotion rose to %d (ceiling %d). Promote the new one "
            "instead of raising this." % (len(live), PENDING_CEILING))

    def test_the_ceiling_is_not_slack(self):
        live = sum(1 for d, f, p, _ in self.sites if (d, f, p) in PENDING)
        self.assertGreaterEqual(
            live, PENDING_CEILING - 3,
            "the live pending count is %d against a ceiling of %d; lower the ceiling so the "
            "next regression is caught" % (live, PENDING_CEILING))

    def test_no_declaration_is_stale(self):
        """A declared site that no longer exists is a rule nobody is following.

        Both dictionaries are documentation as much as configuration: an entry for a phrase
        that has been promoted or rewritten reads as an exemption still in force.
        """
        live = {(d, f, p) for d, f, p, _ in self.sites}
        gone = sorted((set(EXEMPT) | set(PENDING)) - live)
        self.assertFalse(
            gone,
            "these sites are declared here and no longer present. Remove the entry - a "
            "stale exemption is a claim about the manuscripts that is not true:\n  %s"
            % "\n  ".join("%s / %s: %r" % s for s in gone))

    def test_every_exemption_gives_a_reason(self):
        thin = sorted(k for k, v in EXEMPT.items() if len(v.strip()) < 25)
        self.assertFalse(
            thin, "exemptions with no substantive reason: %s" % thin)

    def test_the_phrases_this_campaign_corrected_do_not_return(self):
        """The three specific regressions, named, because each one shipped.

        "eleven times the metered fuel" was 13 per cent low at four sites including an
        abstract; "five times its present total" was 17 per cent low in a contribution list
        and a conclusion. Both understated the paper's own finding, which is the direction
        that makes a wrong number comfortable to leave alone.
        """
        banned = ("eleven times the metered", "five times its present total",
                  "peak five times today")
        offenders = []
        papers = os.path.join(ROOT, "papers")
        roots = [PAPER_NATIONAL_SECTIONS]
        if os.path.isdir(papers):
            roots += [os.path.join(papers, d, "sections") for d in sorted(os.listdir(papers))
                      if os.path.isdir(os.path.join(papers, d, "sections"))]
        for root in roots:
            if not os.path.isdir(root):
                continue
            for name in sorted(os.listdir(root)):
                if not name.endswith(".tex"):
                    continue
                with io.open(os.path.join(root, name), encoding="utf-8") as handle:
                    text = handle.read()
                for phrase in banned:
                    if phrase in text:
                        offenders.append("%s: %r" % (name, phrase))
        self.assertFalse(
            offenders,
            "a phrase this campaign corrected has returned as a word: %s" % offenders)


if __name__ == "__main__":
    unittest.main()
