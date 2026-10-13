"""A LaTeX command whose backslash was eaten still looks like prose.

WHY THIS TEST EXISTS. The national supplement shipped `\\texttt` and `\\textsubscript` with a
literal TAB where the backslash belonged - the signature of a string written through a path
that interpreted `\\t` as a tab character. LaTeX then typeset the command name as text, so the
RELEASED PDF printed

    ten sector tables ( extttair_pollutants_2024.csv and its provincial, district ...
    BC and OC inside PM extsubscript2.5, PM extsubscript2.5 inside PM extsubscript10

in the sentence that states the containment rule forbidding sums across pollutant species.
Fifteen commands were affected across eight lines. Nothing caught it: it is valid LaTeX, it
compiles without a warning, and the citation register could not see the filenames because
`\\texttt` was never there - so the files read as uncited and the defect looked like a
different problem one level up.

It is also easy to reintroduce. A patch script that writes `"\\texttt{...}"` in an ordinary
Python string produces exactly this, and cycle 40 did it twice while repairing the same file.

WHAT THIS HOLDS. No .tex file may contain a control character immediately followed by a LaTeX
command name. The check is on the class, not on the two commands that failed.
"""
import glob
import io
import os
from pkinv.paths import PAPER_NATIONAL_MAIN  # noqa: E402
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# The commands this corpus actually uses, with their leading letter dropped: what remains after
# an escape sequence has swallowed the backslash AND the first letter (\t -> tab, \n -> newline,
# \r, \f, \v, \b, \a). Matching the TAIL rather than the whole name is what makes the check
# independent of which escape did it.
SWALLOWED = re.compile(
    # \x09 (TAB) is IN the class and excluding it was this detector's own first bug: the
    # positive control below reported zero hits on the very file that shipped the defect,
    # because the defect IS a tab and the class ran \x00-\x08. Only the newline is exempt.
    r"[\x00-\x09\x0b-\x1f]"
    r"(?=(?:ext|exttt|extsubscript|extbf|extit|um\{|ty\{|abel\{|mph\{|ite\{|ef\{|rac\{))")

TEX = sorted(glob.glob(os.path.join(PAPER_NATIONAL_MAIN, "**", "*.tex"), recursive=True)
             + glob.glob(os.path.join(ROOT, "papers", "**", "*.tex"), recursive=True)
             + glob.glob(os.path.join(ROOT, "paper_common", "**", "*.tex"), recursive=True))

# The commit that still carries the defect, for the positive control.
BEFORE_REPAIR = "78ce22cf"


class TestNoCommandLostItsBackslash(unittest.TestCase):
    def test_the_corpus_is_looking_at_something(self):
        self.assertGreater(len(TEX), 50,
                           "only %d .tex files were found; the globs have moved and a scan "
                           "over nothing passes forever" % len(TEX))

    def test_no_tex_file_has_a_control_character_before_a_command_name(self):
        offenders = []
        for path in TEX:
            with io.open(path, encoding="utf-8", errors="replace") as handle:
                for n, line in enumerate(handle, 1):
                    if SWALLOWED.search(line):
                        offenders.append("%s:%d: %s"
                                         % (os.path.relpath(path, ROOT), n, line.strip()[:80]))
        self.assertFalse(
            offenders,
            "a LaTeX command's backslash has been replaced by a control character, so LaTeX "
            "will typeset the command NAME as text and the PDF will print it. This compiles "
            "cleanly and reads as prose in the source, which is why it shipped:\n  %s"
            % "\n  ".join(offenders))

    def test_the_detector_fires_on_the_shipped_defect(self):
        """A positive control read from history, not a line this test invented."""
        try:
            body = subprocess.run(
                ["git", "show", "%s:paper_national/supplement.tex" % BEFORE_REPAIR],
                cwd=ROOT, capture_output=True, text=True, timeout=60).stdout
        except (OSError, subprocess.SubprocessError):  # pragma: no cover
            raise unittest.SkipTest("git is unavailable in this checkout")
        if not body:  # pragma: no cover
            raise unittest.SkipTest("the pre-repair commit is not in this checkout")
        hits = [l for l in body.splitlines() if SWALLOWED.search(l)]
        self.assertGreaterEqual(
            len(hits), 8,
            "the detector finds %d broken lines in the version that shipped the defect; it "
            "should find the eight that were there. A control that does not fire on the real "
            "defect is the failure mode this test exists to avoid." % len(hits))


if __name__ == "__main__":
    unittest.main()
