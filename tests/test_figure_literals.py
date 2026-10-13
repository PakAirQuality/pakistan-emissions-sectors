"""No figure script may hold a national total as a literal. It must read the product.

WHY THIS TEST EXISTS. The 23rd review found the gridded figure's heading still printing
469.63822 Mt, the pin from before the coal re-base, on a map whose plotted CO2 was the new
account. It was the THIRD copy of that superseded number found in one round: Figure 3
labelled the deterministic reference 469.64 beside a diamond plotted from data carrying
451.86, and Figure 2 asserted `abs(v.sum()-469.64)<.05`. Three instances of one pattern is
the pattern being the defect.

The quantity sweep could not see any of them. It reads LaTeX sections - siunitx arguments
and tabular cells - and these numbers lived in Python string literals and in an assert, in
files the sweep has no reason to open. So a figure could contradict the release it was drawn
from, and the only thing that caught it was a human reading the rendered page.

THE RULE: a figure script may MENTION a pin in a comment, because explaining why a number
moved is how the next reader learns what happened. It may not hold one as a literal in code.
Comments are stripped before scanning, so the history notes in these files stay legal and
the code they describe cannot regress.

WHAT COUNTS AS A PIN: every national total the release publishes under any configuration,
and every total any previous release published, read from the products that own them. So
this test needs no list of numbers to maintain - it learns them, which is the property the
three defects lacked.
"""
import io
import os
import re
import sys
import tokenize
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import read_rows                                     # noqa: E402

from pkinv.report import manuscript_style                             # noqa: E402

# Every script that draws a figure the manuscripts include, and the style they share. The list
# is the style module's own, so a script cannot be added there and missed here.
FIGURE_SCRIPTS = manuscript_style.FIGURE_SCRIPTS + ("src/pkinv/report/manuscript_style.py",)

# A pin is only recognisable as such with enough precision to be unambiguous; two decimals
# is the coarsest form any of these documents prints (451.86, 469.64).
_NUMBER = re.compile(r"\d+\.\d{2,}")


def _strip_comments(source):
    """The source with comments removed, so a history note may name a pin and code may not."""
    out = []
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type != tokenize.COMMENT:
                out.append(tok.string)
    except (tokenize.TokenError, IndentationError):
        # An unparseable file is a different failure; fall back to the raw text so this
        # test reports a literal rather than silently passing on a tokenise error.
        return source
    return "\n".join(out)


def _pins():
    """{rounded value: where it comes from} for every national total any release published."""
    pins = {}

    def add(value, origin):
        try:
            number = float(value)
        except (TypeError, ValueError):
            return
        if number <= 0:
            return
        for places in (2, 5):
            pins.setdefault(round(number, places), origin)

    path = os.path.join(ROOT, "outputs", "national_configurations.csv")
    if os.path.exists(path):
        for row in read_rows(path):
            add(row.get("national_total_Mt"),
                "national_configurations.csv#%s" % row.get("configuration_id"))
    # THE TOTALS A RE-BASE LEFT BEHIND (rc67). A literal goes stale exactly when the pins
    # move, and at that moment the live product stops teaching this guard the number the
    # literal holds: after the rc67 re-base no product carried 451.86 or 469.64 any more, so
    # a figure script still printing either would have passed. Each declared re-base pins
    # the account it replaced under data/baselines/, and those totals stay pins here.
    import glob
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "baselines", "*",
                                              "national_configurations.csv"))):
        for row in read_rows(path):
            add(row.get("national_total_Mt"),
                "%s#%s" % (os.path.relpath(path, ROOT), row.get("configuration_id")))
    path = os.path.join(ROOT, "data", "catalog", "published_release_vintages.csv")
    if os.path.exists(path):
        for row in read_rows(path):
            for key, value in row.items():
                if "total" in key.lower() or key.lower().endswith(("_mt", "_pin")):
                    add(value, "published_release_vintages.csv#%s" % key)
    return pins


class TestNoFigureScriptPinsANationalTotal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pins = _pins()

    def test_the_pin_set_is_not_empty(self):
        """A guard that learned no pins would pass on everything. The products that teach it
        are shipped, so an empty set means the products moved, not that there are no pins."""
        self.assertGreaterEqual(
            len(self.pins), 2,
            "no national totals were found in national_configurations.csv or "
            "published_release_vintages.csv, so this test is checking nothing")

    def test_no_script_holds_a_pin_as_a_literal(self):
        offences = []
        for relative in FIGURE_SCRIPTS:
            path = os.path.join(ROOT, relative)
            # a missing script used to be skipped, which let a renamed one leave the guard
            self.assertTrue(os.path.exists(path), "%s is listed as a figure script and is absent" % relative)
            with open(path, encoding="utf-8") as handle:
                code = _strip_comments(handle.read())
            for found in set(_NUMBER.findall(code)):
                # MATCHED AT BOTH PRECISIONS, and matching only at five decimals would have
                # missed the defect this test was written for. The map held 469.63822 while
                # the configurations product carries 469.63823 - one digit apart, because
                # the pin was transcribed at a different rounding - so an exact five-place
                # comparison saw no pin at all. Two decimals catches the family; five
                # catches an exact copy. A literal of national-total magnitude in a figure
                # script should be read from a product whichever form it is written in.
                value = float(found)
                hit = next((p for p in (round(value, 5), round(value, 2))
                            if p in self.pins), None)
                if hit is not None:
                    offences.append("%s holds %s as a literal (matches %s from %s)"
                                    % (relative, found, hit, self.pins[hit]))
        self.assertFalse(
            offences,
            "a figure script states a national total instead of reading it:\n  %s\n"
            "Read it from the product. A literal cannot follow a re-base, and the three "
            "that shipped in October 2026 each drew the right data under the wrong number."
            % "\n  ".join(sorted(offences)))

    def test_a_planted_literal_is_caught(self):
        """THE POSITIVE CONTROL. Without it this test passes on a scanner that matches
        nothing - and a comment-stripping bug would do exactly that."""
        # 469.63822 is the form the map actually held: a five-decimal transcription that
        # differs from the product's own fifth digit. The control plants THAT, not a value
        # copied out of the pin set, because a control built from the set cannot fail the
        # way the real defect did.
        planted = "# a history note mentioning 469.63822 is legal\nx = 469.63822\n"
        code = _strip_comments(planted)
        self.assertNotIn("history note", code, "comments were not stripped")
        hits = [f for f in set(_NUMBER.findall(code))
                if round(float(f), 2) in self.pins or round(float(f), 5) in self.pins]
        self.assertTrue(hits,
                        "the scanner missed a planted 469.63822 - the exact literal the "
                        "gridded figure shipped, which a five-decimal-only match cannot see")

    def test_a_comment_mentioning_a_pin_is_allowed(self):
        """The counterpart: the explanation of why a number moved must stay sayable."""
        pin = sorted(self.pins)[0]
        code = _strip_comments("# this line used to read %s before the re-base\ny = 1\n" % pin)
        hits = [f for f in set(_NUMBER.findall(code)) if round(float(f), 5) in self.pins]
        self.assertFalse(hits, "a pin named only in a comment was reported as a literal")


if __name__ == "__main__":
    unittest.main()

class TestTheGriddedFigureScriptIsMathematicallyAndEditoriallyHonest(unittest.TestCase):
    """Two source-level guards on scripts/make_fig_ghg_grid.py.

    WHY (uniform reference). Panel (g) plots cumulative placed mass against cumulative
    in-country cells on a symlog x-axis, and drew its "uniform: no spatial information"
    reference as ax.plot([0.01, 100], [0.01, 100]) - a straight segment in DISPLAY space.
    On a log-x/linear-y axis the uniform case (mass fraction == cell fraction) is a curve;
    the straight segment is wrong by construction and reads 1 % of cells as holding far more
    than 1 % of mass. The reference must be sampled on the plotted grid (y = x evaluated at
    many x), so that at 1 % and 10 % of cells it gives 1 % and 10 % of mass.

    WHY (plot text). "release pin", "shipped cube" and "nothing recomputed" are internal
    register and release assurance; they belong in metadata and captions, not in a figure a
    reviewer reads. They cannot be removed by editing the manuscripts because they are
    printed by the script.
    """
    SCRIPT = os.path.join(ROOT, "scripts", "make_fig_ghg_grid.py")

    def _code(self):
        with open(self.SCRIPT, encoding="utf-8") as handle:
            return _strip_comments(handle.read())

    def test_the_uniform_reference_is_sampled_not_a_two_point_segment(self):
        code = self._code()
        two_point = re.search(r"plot\(\s*\[\s*0\.01\s*,\s*100\s*\]\s*,\s*\[\s*0\.01\s*,\s*100\s*\]", code)
        self.assertIsNone(two_point, "the uniform reference is still a two-point segment on a symlog axis")
        # \s* because _strip_comments puts each token on its own line
        self.assertIsNotNone(re.search(r"logspace\s*\(", code),
                             "the uniform reference must be sampled on the log grid (np.logspace) so y = x holds at every x")

    def test_no_internal_register_in_plot_text(self):
        """Checked on the PDF text layer, not the source: the module docstring may explain
        what a release pin is; the figure a reviewer reads may not print it."""
        import subprocess
        for name in ["%s.pdf" % stem for stem in manuscript_style.FIGURES]:
            path = os.path.join(ROOT, "paper_national", "figures", name)
            self.assertTrue(os.path.exists(path), "%s is not built: run `make figures-v3`" % name)
            text = subprocess.run(["pdftotext", path, "-"], capture_output=True, text=True).stdout
            for phrase in ("release pin", "shipped cube", "nothing recomputed"):
                self.assertFalse(phrase in text,
                                 "%s prints %r; move provenance to metadata/caption" % (name, phrase))
