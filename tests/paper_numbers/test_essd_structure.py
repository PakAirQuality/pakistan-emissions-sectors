"""The national article is an ESSD data-description article, and says so in its structure.

WHY THIS FILE EXISTS. docs/essd_outline.md re-targets paper_national/ from a modelling
journal to Earth System Science Data: a Copernicus one-column manuscript with numbered
sections, generated availability statements, a number-free short summary, and a controlled
vocabulary (a "public-data reconstruction" that is "evidence-graded", never an "official
national inventory" or a "definitive" one). None of that is a number, so the numeric
apparatus in this package cannot see it drift. This file holds the structure: the class,
the vocabulary both ways, the summary, the master's banned commands, the one-document rule
for every section fragment, and the vendored class files with their recorded digest.

The vocabulary lists are the outline's and are not to be watered down. Where today's prose
violates one (the prose rewrite is the NEXT pass), the check is marked expectedFailure with
the offending lines in its docstring, so that it starts failing loudly the moment it should
pass - unittest reports an unexpected success - rather than being skipped.
"""
import glob
import os
from pkinv.paths import PAPER_NATIONAL_MAIN  # noqa: E402
from pkinv.paths import PAPER_NATIONAL_CURRENT  # noqa: E402
import re
import unittest

from paper_numbers._common import ROOT, _inputs_of


NATIONAL = PAPER_NATIONAL_MAIN
MASTER = os.path.join(NATIONAL, "paper_national.tex")
SUPPLEMENT = os.path.join(NATIONAL, "supplement.tex")
SECTIONS = os.path.join(NATIONAL, "sections")
SUMMARY = os.path.join(NATIONAL, "short_summary.txt")
VENDORED = os.path.join(ROOT, "paper_common", "copernicus")
VENDORED_FILES = ("copernicus.cls", "copernicus.cfg", "copernicus.bst",
                  "pdfscreen.sty", "pdfscreencop.sty", "template_reference.txt",
                  "README_copernicus_package_7_15.txt", "VENDORED.md")
# The publisher's archive, as downloaded on 2026-08-29 (version 7.15).
VENDORED_ZIP_SHA256 = "f31563e860a42c6bb980de4f29c670881eccca42b31f084fc11b7f0070040767"

# docs/essd_outline.md, "Vocabulary the manuscript uses, and avoids". Case-insensitive.
BANNED = ("official national inventory", "definitive", "complete inventory",
          "observed gridded emissions", "true national emissions", "live emissions system",
          "AI-derived")
REQUIRED = ("public-data reconstruction", "evidence-graded", "reference configuration",
            "spatial allocation", "monthly estimate")

SUMMARY_MAX_CHARS = 500


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


def _uncommented(text):
    return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in text.splitlines())


def prose_files(root=ROOT):
    """The master and every sections/*.tex, generated fragments included: the vocabulary
    rule applies to whatever the article prints."""
    national = os.path.join(root, "paper_national", "versions", PAPER_NATIONAL_CURRENT)
    return ([os.path.join(national, "paper_national.tex")]
            + sorted(glob.glob(os.path.join(national, "sections", "*.tex"))))


def banned_hits(root=ROOT):
    """[(relative path, line number, phrase, line)] for every banned phrase in the prose."""
    hits = []
    for path in prose_files(root):
        for lineno, line in enumerate(_read(path).splitlines(), 1):
            plain = re.sub(r"(?<!\\)%.*", "", line)
            for phrase in BANNED:
                if phrase.lower() in plain.lower():
                    hits.append((os.path.relpath(path, root), lineno, phrase, plain.strip()))
    return hits


def required_counts(root=ROOT):
    text = "\n".join(_uncommented(_read(p)) for p in prose_files(root)).lower()
    return {phrase: text.count(phrase.lower()) for phrase in REQUIRED}


def fragment_input_counts(root=ROOT):
    """How many times each hand-written sections/*.tex is \\input across the article and
    its supplement, following the containers' nested inputs."""
    national = os.path.join(root, "paper_national", "versions", PAPER_NATIONAL_CURRENT)
    counts = {}
    for name in sorted(os.listdir(os.path.join(national, "sections"))):
        if not name.endswith(".tex") or name.startswith(("generated_", "gen_")):
            continue
        counts[name] = 0
    for main in ("paper_national.tex", "supplement.tex"):
        for path in _inputs_of(os.path.join(national, main), national):
            name = os.path.basename(path)
            if os.path.dirname(path) == os.path.join(national, "sections") and name in counts:
                counts[name] += 1
    return counts


class TestTheArticleIsACopernicusManuscript(unittest.TestCase):

    def test_the_master_uses_the_essd_manuscript_class(self):
        text = _uncommented(_read(MASTER))
        self.assertIn(r"\documentclass[essd, manuscript]{copernicus}", text,
                      "the national article must compile as an ESSD one-column manuscript")

    def test_the_master_carries_no_banned_layout_commands(self):
        """placeins is not loadable under the class (\\FloatBarrier), a data paper has no
        appendix (its detail is the supplement), and \\paragraph run-in headings are not an
        ESSD level."""
        text = _uncommented(_read(MASTER))
        for command in (r"\FloatBarrier", r"\appendix", r"\paragraph"):
            self.assertNotIn(command, text, "%s in the master" % command)

    def test_the_availability_statements_are_generated_and_input(self):
        text = _uncommented(_read(MASTER))
        self.assertIn(r"\input{generated/availability}", text)
        self.assertIn(r"\input{generated/abstract_doi}", text)
        generated = _read(os.path.join(NATIONAL, "generated", "availability.tex"))
        self.assertTrue(r"\dataavailability{" in generated
                        or r"\codedataavailability{" in generated)
        self.assertTrue(r"\codeavailability{" in generated
                        or r"\codedataavailability{" in generated)


class TestTheVocabularyIsTheOutlines(unittest.TestCase):

    @unittest.expectedFailure
    def test_no_banned_phrase_appears(self):
        """TODO (prose pass): today's fragments still carry banned vocabulary. Offending
        lines when this guard was written (2026-08-29):

            paper_national/sections/07_uncertainty.tex:412  "definitive"
                ("... \\texttt{outputs/national\\_axis\\_register.csv} is the definitive
                one-row-per-axis table ...")

        Remove the decorator when the prose pass clears them; an unexpected success here
        is the signal that it has."""
        hits = banned_hits()
        self.assertFalse(hits, "banned vocabulary in the article:\n  " + "\n  ".join(
            "%s:%d %r: %s" % (path, lineno, phrase, line[:100])
            for path, lineno, phrase, line in hits))

    def test_the_banned_sweep_still_sees_its_own_control(self):
        """A control for the sweep: the exact line the expected failure documents. When
        the prose pass removes it, retire this control together with the decorator."""
        path = os.path.join(SECTIONS, "07_uncertainty.tex")
        self.assertIn("definitive", _read(path).lower())

    def test_every_required_phrase_appears(self):
        counts = required_counts()
        missing = [phrase for phrase, n in counts.items() if n == 0]
        self.assertFalse(missing, "the article never says: %s" % ", ".join(missing))

    def test_the_title_names_the_product_and_its_nature(self):
        text = " ".join(_uncommented(_read(MASTER)).split())
        title = re.search(r"\\title\{(.*?)\}", text).group(1)
        self.assertTrue(title.startswith("PakEmis v1.0:"), title)
        self.assertIn("evidence-graded public-data reconstruction", title)


class TestTheShortSummary(unittest.TestCase):
    """ESSD asks for a short, non-technical summary of at most 500 characters. It is for a
    lay reader, so it carries no number at all - a number without its evidence class is the
    thing the article spends its pages qualifying."""

    def test_it_exists_fits_and_carries_no_digit(self):
        self.assertTrue(os.path.exists(SUMMARY), "paper_national/short_summary.txt is missing")
        text = _read(SUMMARY).strip()
        self.assertTrue(text, "the short summary is empty")
        self.assertLessEqual(len(text), SUMMARY_MAX_CHARS,
                             "%d characters; ESSD allows %d" % (len(text), SUMMARY_MAX_CHARS))
        self.assertFalse(re.search(r"\d", text), "the short summary contains a digit")


class TestEveryFragmentIsPrintedOnce(unittest.TestCase):
    """Two documents share sections/. A fragment in neither is dead prose; a fragment in
    both prints twice under two numberings and the number tests would hold one value in
    two places. The containers nest their inputs, and the graph is followed."""

    def test_each_section_file_is_input_exactly_once_across_both_documents(self):
        counts = fragment_input_counts()
        self.assertGreaterEqual(len(counts), 15, "the sections/ listing went blind")
        wrong = {name: n for name, n in counts.items() if n != 1}
        self.assertFalse(wrong, "fragments not input exactly once across the article and "
                                "its supplement: %s" % wrong)


class TestTheClassIsVendored(unittest.TestCase):

    def test_the_vendored_files_exist(self):
        missing = [f for f in VENDORED_FILES if not os.path.exists(os.path.join(VENDORED, f))]
        self.assertFalse(missing, "paper_common/copernicus/ lacks: %s" % missing)

    def test_the_vendoring_note_records_the_archive_digest(self):
        note = _read(os.path.join(VENDORED, "VENDORED.md"))
        self.assertIn(VENDORED_ZIP_SHA256, note)
        self.assertIn("7.15", note)
        self.assertIn("publications.copernicus.org", note)


if __name__ == "__main__":
    unittest.main()
