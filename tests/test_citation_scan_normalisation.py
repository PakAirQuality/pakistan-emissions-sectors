"""A filename is cited whatever LaTeX had to do to set it.

WHY THIS TEST EXISTS. `artifact_inventory.documents()` decides whether a manuscript names a
file by searching the .tex source for the filename. LaTeX cannot print `fugitives_x_2024.csv`
literally: the underscore must be escaped, and a 57-character monospace name must carry break
hints or it prints outside the page. The scanner normalised the escape and not the hints.

That was live, and it was caused by two of this campaign's own fixes meeting. The appendix
rewrites named the evidence tables; the layout repair then added `\\allowbreak` after each
escaped underscore in names over 40 characters, because a `description` label at 57 characters
overran by 52.2pt. The second fix silently un-cited SEVEN files the first had just cited - five
fugitives and two aviation - and the published count of the remaining debt was stale from that
moment.

It surfaced only because the cycle had written down what it expected: 34, against 51 measured.
Without the prediction the 51 would have looked like the new truth.

WHAT THIS HOLDS. Every LaTeX device that can appear inside a monospace filename must be
normalised away before the search, so that whether a file counts as cited never depends on how
wide its name happens to be. One normalisation without the others is worse than none, because
it makes the citation register's answer a function of typesetting.
"""
import io
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.report import artifact_inventory as inventory              # noqa: E402

# How a long filename actually appears in the manuscripts after the layout repair.
BROKEN = ("fugitives\\_\\allowbreak infrastructure\\_\\allowbreak segment\\_\\allowbreak "
          "timeseries\\_\\allowbreak 2016\\_2024.csv")
PLAIN = "fugitives_infrastructure_segment_timeseries_2016_2024.csv"

# The commit BEFORE cycle 36 converted the three remaining hand-rolled readers.
# The positive control reads the defective builder out of it.
BEFORE_REPAIR = "8388b9f4"


class TestTheCitationScanSeesWhatAReaderSees(unittest.TestCase):
    def test_an_escaped_underscore_is_normalised(self):
        text = self._normalise("a \\texttt{power\\_fuel\\_fy2023\\_24.csv} reference")
        self.assertIn("power_fuel_fy2023_24.csv", text)

    def test_a_break_hint_inside_a_filename_is_normalised(self):
        """The defect: `\\allowbreak` survived and the filename stopped matching."""
        text = self._normalise("a \\texttt{%s} reference" % BROKEN)
        self.assertIn(
            PLAIN, text,
            "a filename carrying LaTeX break hints is no longer recognised. A long monospace "
            "name MUST carry them - without them it prints outside the page - so a scanner "
            "that cannot see through them makes 'is this file cited?' depend on how wide its "
            "name is.")

    def test_the_other_break_devices_are_normalised_too(self):
        for device, shown in (("\\-", "discretionary hyphen"), ("\\/", "italic correction")):
            text = self._normalise("\\texttt{power%sfuel.csv}" % device)
            self.assertIn("powerfuel.csv", text,
                          "%s survives the normalisation" % shown)

    def test_the_manuscripts_actually_exercise_this(self):
        """A guard on a case the corpus never contains is a guard on nothing.

        If the appendices stop using break hints the test above still passes and proves
        nothing, so this asserts the corpus still contains the shape it protects.
        """
        docs = inventory.documents()
        self.assertTrue(docs, "no manuscripts were read")
        found = [label for label, text in docs.items() if PLAIN in text]
        self.assertTrue(
            found,
            "no manuscript names %s any more. If the appendix lost it the citation register "
            "will report the file uncited, which is what this whole guard is about." % PLAIN)

    # The device->replacement pairs that mean "a reader is normalising a printed name".
    # These are VALUES, not source text: the guard parses the file and reads the arguments of
    # every `.replace(a, b)` call, because two earlier text-matching versions both failed -
    # the first was one backslash short of anything on disk, and the second flagged the
    # COMMENTS that quote the banned form while explaining the ban.
    #
    # A writer that ADDS a device is untouched by design: make_transport_factor_table.py
    # writes `.replace("\\_", "\\_\\allowbreak ")` to build the printed name, and its
    # replacement is not the plain form, so it is not a reader normalising one.
    # Scoped to the devices that make a printed NAME unrecognisable - the escape and the
    # break hints. `\%`, `\&` and `~` are in the shared function for the callers that need
    # them, but they are deliberately NOT banned here: the first version of this list included
    # them and immediately caught tests/paper_numbers/tables.py, which normalises a whole
    # LaTeX table CELL for comparison and maps `~` to a SPACE rather than to nothing. That is
    # a different job with a different right answer, and a guard that has to be argued with is
    # a guard that gets deleted.
    BANNED_PAIRS = (("\\_", "_"), ("\\allowbreak ", ""), ("\\allowbreak", ""),
                    ("\\-", ""), ("\\/", ""))
    HOME = os.path.join("src", "pkinv", "report", "artifact_inventory.py")

    @classmethod
    def _offending_calls(cls, body):
        """[(device, replacement)] for every `.replace(device, replacement)` call in `body`."""
        import ast
        try:
            tree = ast.parse(body)
        except SyntaxError:  # pragma: no cover - a file this repository would not ship
            return []
        found = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and node.func.attr == "replace"
                    and len(node.args) == 2
                    and all(isinstance(a, ast.Constant) and isinstance(a.value, str)
                            for a in node.args)):
                pair = (node.args[0].value, node.args[1].value)
                if pair in cls.BANNED_PAIRS:
                    found.append(pair)
        return found

    def test_no_module_normalises_a_printed_name_by_hand(self):
        """The class, not the instance. Cycle 36's defect, and the guard that catches the next.

        Cycle 32 created `as_a_reader_sees_it` and converted ONE caller. Three other readers of
        a printed name kept their own hand-rolled escape and stayed blind to the break hints:
        the citation-deposit audit builder (which then reported three freshly cited files
        ABSENT FROM THE REPOSITORY - its most serious verdict), the module-credit sweep, and
        the supplement-citation getter whose answer Section 12 prints, which was overcounted by
        five. A shared function nobody is required to use is a convention, not a fix.

        So this forbids the hand-rolled call anywhere but in the shared function itself. A
        reader needing one more device adds it there, where every other reader gets it.
        """
        offenders = []
        mine = os.path.relpath(os.path.abspath(__file__), ROOT)
        for base in ("src", "scripts", "tests"):
            for dirpath, _dirnames, filenames in os.walk(os.path.join(ROOT, base)):
                if "__pycache__" in dirpath:
                    continue
                for name in sorted(filenames):
                    if not name.endswith(".py"):
                        continue
                    relative = os.path.relpath(os.path.join(dirpath, name), ROOT)
                    if relative in (self.HOME, mine):
                        continue
                    with io.open(os.path.join(dirpath, name), encoding="utf-8",
                                 errors="replace") as handle:
                        body = handle.read()
                    for pair in self._offending_calls(body):
                        offenders.append("%s: .replace(%r, %r)" % (relative, pair[0], pair[1]))
        self.assertFalse(
            offenders,
            "these modules normalise a printed LaTeX name by hand instead of calling "
            "pkinv.report.artifact_inventory.as_a_reader_sees_it. Each hand-rolled copy "
            "handles the devices its author happened to think of, and the ones it misses turn "
            "'is this file cited?' into a question about typesetting:\n  %s"
            % "\n  ".join(offenders))

    def test_the_detector_fires_on_the_defect_it_was_written_for(self):
        """A positive control read from HISTORY, not from a string this test invented.

        The first control asserted the banned form against an inline line this file wrote
        itself, which is a tautology - and it passed while the pattern was one backslash short
        of anything on disk. This reads the real pre-repair builder out of git instead, so the
        detector is proved against source that actually existed in this repository.
        """
        import subprocess
        try:
            body = subprocess.run(
                ["git", "show", "%s:scripts/build_citation_deposit_audit.py" % BEFORE_REPAIR],
                cwd=ROOT, capture_output=True, text=True, timeout=60).stdout
        except (OSError, subprocess.SubprocessError):  # pragma: no cover
            raise unittest.SkipTest("git is unavailable in this checkout")
        if not body:  # pragma: no cover - a shallow clone without that commit
            raise unittest.SkipTest("the pre-repair commit is not in this checkout")
        self.assertIn(
            ("\\_", "_"), self._offending_calls(body),
            "the detector does not fire on the very file the defect was found in. That is "
            "this control's whole purpose: a banned form that matches nothing on disk leaves "
            "the guard green forever, which is exactly what happened twice while writing it.")

    def test_the_writers_that_add_a_device_are_not_caught(self):
        """The guard must not forbid BUILDING a printed name, only reading one by hand.

        A negative control, and the reason the check reads argument values rather than text:
        the transport factor table legitimately writes `.replace("\\_", "\\_\\allowbreak ")`
        to insert the break hints in the first place, and a guard that failed on that would be
        removed rather than obeyed.
        """
        writer = os.path.join(ROOT, "scripts", "make_transport_factor_table.py")
        with io.open(writer, encoding="utf-8") as handle:
            body = handle.read()
        self.assertIn(
            "allowbreak", body,
            "this control reads the real writer; if it no longer inserts break hints, point "
            "the control at whichever module does rather than deleting it")
        self.assertFalse(
            self._offending_calls(body),
            "the guard fires on a writer that ADDS break hints, which is not the defect")

    @staticmethod
    def _normalise(text):
        """THE REAL FUNCTION, not a copy of it.

        A second implementation here would be the defect this file guards against - the
        escape normalised in one place and the break hints in another, diverging silently.
        """
        return inventory.as_a_reader_sees_it(text)


if __name__ == "__main__":
    unittest.main()
