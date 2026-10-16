"""A passage that states a total and then lists its parts must agree with itself.

WHY THIS TEST EXISTS. The IPPU study-area section said, in one sentence:

    \\num{24} facilities now carry resolved coordinates---one from an independently verified
    site geocode, seven from named OSM industrial polygons and eleven from the Global Energy
    Monitor cement tracker

One plus seven plus eleven is nineteen. The passage contradicted itself by five, and it shipped
that way. Two sections later the same breakdown read one, seven and a registered \\num{16},
which sums to 24 and is right against the registry.

WHAT MAKES THIS DIFFERENT FROM THE CLAIMS REGISTRY. A claim anchors a printed figure to a
product; this anchors a sentence to itself, and needs no product at all. Every component of
that IPPU sentence was individually unregistered, so the claims registry had nothing to say
about any of them - and the sentence was still checkably wrong from its own contents. The two
guards catch different things and the overlap is not the point.

It is also a different miss from the word-number rule. tests/test_word_number_policy.py would
have forced `\\num{}` on "one", "seven" and "eleven", and the registration that follows would
then have caught the value - but only because somebody went on to register them. The
arithmetic was wrong before any of that, and free to check.

WHAT THIS DOES. It sweeps the national paper and every sector paper for a stated total followed
by an em-dash breakdown of three or more numeric parts, and requires the parts to sum to the
total. Measured on 2026-09-30, three passages match the shape across ten papers - so the
candidate set is small enough to read, which is what makes an allow-list honest rather than a
mute button. Two of the three are false positives of recognisable classes, declared below with
the reason:

  A REMAINDER CLAUSE. "1, 7 and 16 ... the remaining 10 are retained at locality level" - the
  10 is the complement of the total, not a part of it, and a window wide enough to catch the
  parts also catches it.
  AN EXPLICIT IDENTITY. A passage doing arithmetic out loud, "130988+1599=132587", where
  summing the numerals is meaningless because the sentence already states their relation.

NOT ASSERTED: that every total in the manuscripts has a listed breakdown, or that a breakdown
must be exhaustive. Only that where a passage does both, the two agree.
"""
import io
import os
from pkinv.paths import PAPER_NATIONAL_SECTIONS  # noqa: E402
import re
import glob
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
         "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
         "nineteen": 19, "twenty": 20}
NUMBER = re.compile(r"\\num\{(\d+)\}|\b(%s)\b" % "|".join(WORDS), re.I)
# A stated total, then an em-dash, then the breakdown up to the sentence end.
PASSAGE = re.compile(r"\\num\{(\d+)\}[^.]{0,80}?---([^.]{0,320}?)(?:\.|;)", re.S)
MIN_PARTS = 3

# (file, total) -> why its parts do not sum to it. Both classes are recognisable and neither
# is a defect; see the module docstring.
DECLARED = {
    ("08_limitations.tex", 130988):
        "an EXPLICIT IDENTITY: the passage states 130988 + 1599 = 132587 out loud, so summing "
        "its numerals double-counts the sentence's own arithmetic",
}
# Measured 2026-09-30: three passages match the shape across ten papers. If this grows a lot,
# the window is catching prose rather than breakdowns and should be narrowed, not declared
# around - an allow-list is only honest while the candidate set is readable.
CANDIDATE_CEILING = 8


def _value(match):
    return int(match.group(1)) if match.group(1) else WORDS[match.group(2).lower()]


def _sections():
    out = sorted(glob.glob(os.path.join(ROOT, "papers", "*", "sections", "*.tex")))
    out += sorted(glob.glob(os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex")))
    return out


def _candidates():
    found = []
    for path in _sections():
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        for match in PASSAGE.finditer(text):
            total = int(match.group(1))
            parts = [_value(m) for m in NUMBER.finditer(match.group(2))]
            if len(parts) >= MIN_PARTS:
                found.append((os.path.basename(path), total, parts,
                              " ".join(match.group(2).split())[:120]))
    return found


class TestAPassageAgreesWithItself(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not _sections():
            raise unittest.SkipTest("no manuscript sections in this checkout")
        cls.candidates = _candidates()

    def test_the_sweep_still_finds_breakdowns(self):
        """A dead detector leaves the gate looking healthy - the holdings-layer lesson."""
        self.assertTrue(
            self.candidates,
            "the passage sweep found no total-with-breakdown at all. Either the manuscripts "
            "moved or the pattern no longer matches how they are written, and a sweep that "
            "finds nothing passes forever.")

    def test_every_breakdown_sums_to_its_stated_total(self):
        bad = []
        for name, total, parts, tail in self.candidates:
            if sum(parts) == total or (name, total) in DECLARED:
                continue
            bad.append("%s: states %d, parts %s sum to %d\n      %s"
                       % (name, total, parts, sum(parts), tail))
        self.assertFalse(
            bad,
            "%d passage(s) contradict themselves - a stated total and a breakdown that does "
            "not add up to it. This needs no product to check and no claim to be registered; "
            "the sentence is wrong from its own contents. If the breakdown is legitimately "
            "not a partition of the total, declare it in DECLARED with the reason:\n  %s"
            % (len(bad), "\n  ".join(bad)))

    def test_the_candidate_set_stays_readable(self):
        self.assertLessEqual(
            len(self.candidates), CANDIDATE_CEILING,
            "the sweep now matches %d passages (ceiling %d). An allow-list is only honest "
            "while somebody can read the candidates; if the window has started catching prose "
            "rather than breakdowns, narrow the pattern instead of declaring around it."
            % (len(self.candidates), CANDIDATE_CEILING))

    def test_no_declaration_is_stale(self):
        """A declared exception for a passage that now sums is an untrue claim about the text."""
        live = {(name, total) for name, total, _parts, _tail in self.candidates}
        summing = {(name, total) for name, total, parts, _tail in self.candidates
                   if sum(parts) == total}
        gone = sorted(k for k in DECLARED if k not in live or k in summing)
        self.assertFalse(
            gone,
            "these passages are declared as not-a-partition and either no longer match the "
            "sweep or now sum correctly. Remove the entry:\n  %s"
            % "\n  ".join("%s / %d" % k for k in gone))

    def test_every_declaration_gives_a_reason(self):
        thin = sorted(k for k, v in DECLARED.items() if len(v.strip()) < 25)
        self.assertFalse(thin, "declared exceptions with no substantive reason: %s" % thin)

    def test_the_ippu_registry_passage_is_the_regression_case(self):
        """Named specifically, because it shipped wrong and the general test would pass a
        version of it that had lost its breakdown entirely."""
        path = os.path.join(ROOT, "papers", "ippu", "sections",
                            "03_study_area_and_data.tex")
        if not os.path.exists(path):
            self.skipTest("the IPPU study-area section is not in this checkout")
        with io.open(path, encoding="utf-8") as handle:
            text = handle.read()
        self.assertNotIn(
            "eleven from the Global Energy Monitor", text,
            "the stale spelled-out count is back. It was five short of the registry and of "
            "the registered figure in 04_methods.tex, and its own sentence's parts summed to "
            "19 against the 24 it stated.")
        # The current note describes provenance and licence-compatible placement
        # rather than the superseded coordinate-count paragraph. Preserve the actual
        # arithmetic regression as a positive control for the same detector.
        stale = r"\num{24} resolved coordinates---\num{1} from reports, \num{7} from maps and eleven from the Global Energy Monitor."
        match = PASSAGE.search(stale)
        self.assertIsNotNone(match)
        parts = [_value(m) for m in NUMBER.finditer(match.group(2))]
        self.assertEqual(parts, [1, 7, 11])
        self.assertNotEqual(sum(parts), int(match.group(1)))
        repaired = stale.replace("eleven", r"\num{16}")
        match = PASSAGE.search(repaired)
        self.assertEqual(sum(_value(m) for m in NUMBER.finditer(match.group(2))),
                         int(match.group(1)))


if __name__ == "__main__":
    unittest.main()
