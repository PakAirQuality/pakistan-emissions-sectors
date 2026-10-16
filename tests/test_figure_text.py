"""A figure's own words, checked against the data the figure plots.

WHY THIS FILE EXISTS. The national uncertainty figure labelled its x-axis "10,000-draw Monte
Carlo" for a full release after the published run moved to 100,000 draws. Every other
statement of that number was right: the caption above the figure, the body of Section 7, the
`n_iter` column of the CSV the figure reads, and the test that asserts that column equals
`NATIONAL_N_ITER`. Only the axis label, typed once into `pkinv.report.figures`, was wrong.

Nothing could have caught it. `TestFiguresAreCurrent` compares shipped PNG *bytes* against
freshly generated ones, so a figure that is stale in the same way in both places matches. The
manuscript tests read `.tex` and never open the plotting source. The number lived in a Python
string literal, which is the one place in this project a release quantity had no guard.

So the rule this file enforces is: a plotting function may READ a number or COMPUTE one, and
may not SPELL one. `figures._run_note()` exists to make that easy for the case at hand.

The exemption list is deliberately not a debt list. This repo retired its coverage-debt list
on the grounds that a list of known-unchecked things becomes a place to put things; every
entry here must be a reason the literal CANNOT go stale, and a companion test rejects any
entry that also appears as a value in a file the figures read.
"""
import ast
import csv
import re
import glob
import os
from pkinv.paths import PAPER_NATIONAL_SECTIONS  # noqa: E402
import sys
import unittest


from pkinv.core import gwp, montecarlo                    # noqa: E402
from pkinv.report import figures, uncertainty_all         # noqa: E402
from pkinv.core.io import read_rows
from _support import OUT, ROOT

FIGURES_PY = os.path.join(ROOT, "src", "pkinv", "report", "figures.py")

# Calls whose string arguments are rendered into the image.
TEXT_SETTERS = {"set_xlabel", "set_ylabel", "set_title", "suptitle", "annotate", "text",
                "set_xticklabels", "set_yticklabels", "legend"}

# literal -> why it cannot go stale. NOT a list of things to fix later.
FIGURE_TEXT_CONSTANTS = {
    "0.75": "the IPCC Tier 1 clinker fraction, a published default rather than a result",
    "0.95": "the IPCC all-Portland clinker upper default",
    "95": "the confidence level the intervals are reported at, fixed by choice not by data",
    "2.5": "the PM size cut, part of the pollutant's name",
    "5": "the AR5/AR6 metric generation, part of the metric's name",
    "6": "the AR6 metric generation, part of the metric's name",
    "2": "the CO2/PM2.5 subscript, part of a chemical name",
    "1": "an axis or panel index",
}


def _rows(name):
    path = os.path.join(OUT, name)
    if not os.path.exists(path):
        return []
    return read_rows(path, comments=False)


def _display_literals():
    """Every string literal that reaches the rendered image, via ast rather than regex.

    A line-based regex would miss implicit concatenation across lines and, more importantly,
    the left operand of a `%` format -- which is exactly where a number hides in
    `"...%.0f Mt, 10,000 draws" % value`.
    """
    with open(FIGURES_PY, encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=FIGURES_PY)
    found = []

    def strings_in(node):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                found.append(sub.value)

    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if name in TEXT_SETTERS:
                for arg in node.args:
                    strings_in(arg)
            for keyword in node.keywords:
                if keyword.arg in ("label", "title", "xlabel", "ylabel"):
                    strings_in(keyword.value)
    return found


def _release_quantities():
    """Numbers this release publishes, gathered from the engine rather than typed.

    Deliberately NARROW. An earlier draft of this guard swept every category total in the
    national rollup, which made "FY2023-24" and "(4C2)" collide with real values and buried
    the one finding in thirty false ones. A guard nobody can read is a guard nobody keeps.
    What belongs here is the set of quantities that (a) a figure might plausibly want to
    state in words and (b) move between releases.
    """
    values = {}
    values[float(montecarlo.N_ITER)] = "the sector Monte Carlo draw count"
    values[float(uncertainty_all.NATIONAL_N_ITER)] = "the national Monte Carlo draw count"
    for basis, table in gwp.GWP.items():
        for gas in ("CH4", "CH4_fossil", "N2O"):
            values[float(table[gas])] = "the %s GWP of %s" % (basis, gas)
    for row in _rows("national_uncertainty_montecarlo.csv"):
        if row.get("scope") != "national":
            continue
        values[float(row["rel_uncert_pct_MC_95"])] = "a published national half-width"
        for col in ("P2.5_Mt", "P50_Mt", "P97.5_Mt"):
            values[round(float(row[col]), 2)] = "a published national percentile"
    for row in _rows("national_all_sectors.csv"):
        if row.get("category") == "TOTAL" or row.get("sector") == "TOTAL":
            values[round(float(row["co2e_Mt_AR5"]), 2)] = "the national total"
    return values


# A printf conversion is a placeholder, not a number: "%.0f" spells no quantity.
_CONVERSION = re.compile(r"%[-+ #0]*[\d.]*[a-zA-Z]")


class TestFigureTextIsDerived(unittest.TestCase):
    """No release quantity may be spelled into the text a figure renders."""

    def test_the_parser_sees_the_figure_module(self):
        """A sweep over an empty list passes. This is what stops that.

        If matplotlib's API moves, or the plotting calls are wrapped in a helper this walk
        does not recognise, every assertion below would hold vacuously.
        """
        literals = _display_literals()
        self.assertGreater(len(literals), 60,
                           "only %d display strings found -- the AST walk has stopped "
                           "matching the plotting calls" % len(literals))
        self.assertTrue(any("Mt CO$_2$e (AR5)" in s for s in literals),
                        "a known axis label is missing from the walk")

    def test_no_release_quantity_is_typed_into_figure_text(self):
        published = _release_quantities()
        problems = []
        for literal in _display_literals():
            for token in re.findall(r"\d[\d,]*(?:\.\d+)?", _CONVERSION.sub("", literal)):
                bare = token.replace(",", "")
                if bare in FIGURE_TEXT_CONSTANTS:
                    continue
                value = float(bare)
                if value < 10:                      # panel indices, subscripts, size cuts
                    continue
                decimals = len(bare.split(".")[1]) if "." in bare else 0
                for known, what in published.items():
                    if round(known, decimals) == value:
                        problems.append("%r spells %s -- %s. Read it from the rows the "
                                        "figure already reads."
                                        % (literal[:60], token, what))
                        break
        self.assertFalse(problems, "release quantities typed into figure text:\n  "
                         + "\n  ".join(problems))

    def test_the_constants_are_not_shadowing_a_result(self):
        """An exemption that is also a published value is a result someone exempted."""
        published = _release_quantities()
        for literal, why in FIGURE_TEXT_CONSTANTS.items():
            self.assertTrue(why and len(why) > 20,
                            "%s is exempted without a reason it cannot go stale" % literal)
            value = float(literal)
            decimals = len(literal.split(".")[1]) if "." in literal else 0
            shadowed = [p for p in published if round(p, decimals) == value]
            self.assertFalse(shadowed,
                             "%s is exempted as a constant but the engine publishes it (%s)"
                             % (literal, ", ".join(published[p] for p in shadowed)))

    def test_the_uncertainty_figure_states_the_draw_count_it_plotted(self):
        """The instance, kept reinstated."""
        rows = figures._read("national_uncertainty_montecarlo.csv")
        national = [r for r in rows if r["scope"] == "national"]
        self.assertTrue(national, "no national rows to describe")
        self.assertEqual(figures._run_note(national),
                         "{:,}-draw".format(uncertainty_all.NATIONAL_N_ITER))
        # Checked against the DISPLAY LITERALS, not the whole source: the helper's own
        # docstring names the superseded label to explain the defect, and a source-wide grep
        # would be immunised by its own explanation -- the trap scripts/audit_outputs.py had
        # to be taught to exclude itself from.
        self.assertNotIn("10,000-draw", " | ".join(_display_literals()),
                         "the superseded draw count is back in the figure text")

    def test_run_note_rejects_a_column_that_disagrees_with_itself(self):
        """Proves the helper is not a pass-through.

        A version that returned the first row's value would satisfy every other test here
        while describing a mixed-provenance figure as though it were one run.
        """
        with self.assertRaises(ValueError):
            figures._run_note([{"n_iter": "10000"}, {"n_iter": "100000"}])
        with self.assertRaises(ValueError):
            figures._run_note([])
        self.assertEqual("100,000-draw", figures._run_note([{"n_iter": "100000"}]))

    # The caption that shipped with rc2, kept so the ban below is proven against the
    # defect it was written for: two interval bars were captioned as distributions with a
    # mode and tails, and no guard compared the caption's chart vocabulary to the chart.
    RC2_UNCERTAINTY_CAPTION = (
        "Distribution of the national total under both correlation assumptions. The "
        "distributions share a mode and differ in their tails: correlated fossil-carbon "
        "factors cannot cancel across sectors, so the aggregate inherits the full width "
        "of the factor's own range rather than a partially averaged version of it.")

    def test_the_uncertainty_caption_describes_interval_bars(self):
        """A caption may not describe a chart the code does not draw.

        national_uncertainty() reads the P2.5/P97.5 percentile columns and plots [lo, hi]
        segments -- interval bars, no histogram, no density. While that is what it draws,
        the caption beneath it may not call the chart a distribution. If the figure is
        ever redrawn as a distribution plot, this test fails on its first assertion and
        must be rewritten with the caption, together.
        """
        import importlib.util
        import inspect
        # The active joint manuscript separates interval bars and structural points.
        spec = importlib.util.spec_from_file_location(
            "integrated_figures", os.path.join(ROOT, "scripts", "build_integrated_figures.py"))
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        src = inspect.getsource(builder.sensitivity)
        self.assertTrue('"P2_5_Gg"' in src and '"P97_5_Gg"' in src and 'S.interval(' in src
                        and not any(w in src for w in ("hist(", "kde", "violin",
                                                       "fill_between")),
                        "sensitivity() no longer draws percentile interval bars; "
                        "rewrite the caption and this guard together")
        path = os.path.join(PAPER_NATIONAL_SECTIONS, "07_uncertainty.tex")
        with open(path, encoding="utf-8") as handle:
            text = " ".join(handle.read().split())
        m = re.search(r"f12_air_sensitivity\.pdf\}\s*\\caption\{(.*?)\}\s*"
                      r"\\label\{fig:uncertainty\}", text)
        self.assertTrue(m, "the uncertainty figure block or its caption moved; re-anchor")
        self.assertNotRegex(m.group(1), r"[Dd]istribution",
                            "the caption calls the chart a distribution while the code "
                            "draws interval bars")
        # The stored rc2 caption must trip the same check, or the pattern has drifted off
        # the defect it exists to catch.
        self.assertRegex(self.RC2_UNCERTAINTY_CAPTION, r"[Dd]istribution")


if __name__ == "__main__":
    unittest.main()
