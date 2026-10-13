"""Tables match the engine; labels match the engine.

Split from tests/test_paper_numbers.py in rc35; the shim of that name
re-exports the data and helpers. Test modules import only from the four data
modules (_common, doc_claims, tables, quantity_policy), never from each other.
"""
import collections
import csv
import io
import filecmp
import glob
import json
import math
import os
import re
import sys
import unittest

from pkinv import paths
from pkinv.core.io import read_rows
from paper_numbers._common import (
    _doc_path)
from paper_numbers.tables import (
    LABELLED_TABLES,
    TABLES,
    _constrained_round,
    _expand_generated_inputs,
    _label_text,
    _match_labelled,
    _tex_table,
    _tex_table_labelled)


class TestTablesMatchTheEngine(unittest.TestCase):
    """Row-by-row reconciliation of registered tables against the CSVs they were set from.

    The DOC_CLAIMS manifest anchors headline numbers one at a time; this covers the other
    cells, which is where stale numbers actually hid - tab:yearbook shipped 36 hand-typed
    digits with only its caption percentage anchored, and tab:factors carried no check at
    all. A missing label or a row-count mismatch is a failure for the same reason a lost
    anchor is: silence must not look like coverage.
    """

    def test_registered_tables_match(self):
        # A registry-driven test that iterates an empty registry passes green while
        # checking nothing. Every table entry here belongs to a sector document, so a
        # future move of papers/ would empty it silently - which is precisely the failure
        # mode this suite exists to prevent. Assert coverage before asserting values.
        self.assertGreater(len(TABLES), 20,
                           "the table registry has shrunk - a document moved without its "
                           "TABLES entries following it")
        problems = []
        for doc, section, label, expected_fn in TABLES:
            printed = _tex_table(doc, section, label)
            if printed is None:
                problems.append("%s/%s: no table labelled %s" % (doc, section, label))
                continue
            expected = expected_fn()
            if len(printed) != len(expected):
                problems.append("%s: %d data rows printed, %d in the output"
                                % (label, len(printed), len(expected)))
                continue
            for i, (want, got) in enumerate(zip(expected, printed)):
                if len(want) != len(got):
                    problems.append("%s row %d: %d numeric cells printed, %d in the output"
                                    % (label, i, len(got), len(want)))
                    continue
                for w, g in zip(want, got):
                    dp = len(g.split(".")[1]) if "." in g else 0
                    if abs(float(g) - w) > 0.5 * 10 ** (-dp) + 1e-9:
                        problems.append("%s row %d: printed %s, output %.6g"
                                        % (label, i, g, w))
        self.assertFalse(problems, "tables disagree with the engine:\n  "
                         + "\n  ".join(problems))


class TestCategoryGasTableSelfSums(unittest.TestCase):
    """Every printed row of tab:categorygas must add up at its own precision.

    The per-cell comparator cannot see this: 157.31, 248.58, 42.12 and 448.00 were each
    within half an ulp of the engine, and their row summed to 448.01. Exact closure is the
    paper's central claim, so the displayed row must close too -- which constrained
    rounding guarantees and independent rounding does not.

    v1.0.0 Wave 4: the table is a stored query and prints the contract's DISPLAY values
    (half-even on the exact decimal string, at the contract's precision - three decimals
    for a category cell, five for the national total). Those are rounded independently by
    the query core and are never re-rounded by a consumer, so the property that survives
    is closure to within the rounding each cell carries: a row's cells sum to its total
    within one half-ulp per cell. _row_closes keeps the old exact rule for the stored rc2
    defect; _row_closes_at_display_precision is what the generated table is held to.
    """

    # The rc2 total row and the two worst category rows, stored as the defect this class
    # was written against.
    RC2_ROWS = [["157.31", "248.58", "42.12", "448.00"],
                ["0.92", "23.78", "24.69"],
                ["1.85", "1.71", "0.26", "3.82"]]

    @staticmethod
    def _row_closes(cells):
        values = [float(c) for c in cells]
        dp = max(len(c.split(".")[1]) if "." in c else 0 for c in cells)
        return abs(sum(values[:-1]) - values[-1]) < 0.5 * 10 ** (-dp) * 1e-3

    @staticmethod
    def _row_closes_at_display_precision(cells):
        """Independently rounded display values close to within a half-ulp per cell."""
        values = [float(c) for c in cells]
        dps = [len(c.split(".")[1]) if "." in c else 0 for c in cells]
        slack = sum(0.5 * 10 ** (-dp) for dp in dps) + 1e-9
        return abs(sum(values[:-1]) - values[-1]) <= slack

    def test_every_printed_row_self_sums(self):
        printed = _tex_table("national", "06_results.tex", "tab:categorygas")
        self.assertTrue(printed, "tab:categorygas not found")
        self.assertGreater(len(printed), 15, "the table shrank; check the parse")
        problems = []
        for i, cells in enumerate(printed):
            if len(cells) < 2:
                continue
            if not self._row_closes_at_display_precision(cells):
                problems.append("row %d: %s does not sum to %s"
                                % (i, " + ".join(cells[:-1]), cells[-1]))
        self.assertFalse(problems, "printed rows do not self-sum at their own "
                                   "precision:\n  " + "\n  ".join(problems))

    def test_the_rc2_rows_fail_and_the_mechanism_reproduces_the_repair(self):
        """The stored defect must trip the check, and _constrained_round must produce the
        exact cells the table now prints for the grand-total row."""
        for cells in self.RC2_ROWS[:2]:
            self.assertFalse(self._row_closes(cells),
                             "%s no longer demonstrates the defect" % cells)
        self.assertEqual(_constrained_round([157.3072, 248.5779, 42.1195], 448.0046),
                         [157.30, 248.58, 42.12])
        # 4.C.2 rounds UP a cell: the shortfall lands on the largest remainder even when
        # plain rounding would have gone down.
        self.assertEqual(_constrained_round([1.8546, 1.7094, 0.2632], 3.8272),
                         [1.86, 1.71, 0.26])


class TestLabelsAndValuesMatchTheEngine(unittest.TestCase):
    """Each value beside the label it belongs to (rc41, the nineteenth review's M-1/M-8).

    TestTablesMatchTheEngine zips numeric rows ordinally and TestPrintedLabelsMatchTheEngine
    checks a name against its code; neither reads a name together with the number beside
    it. tab:keycat shipped rc40 with "Manure management ... 21.82" and "Cement production
    ... 21.23" - the engine's cement (21.816) and manure (21.228) in each other's rows, in
    the CSV's own order - and both tests passed. The registry below joins BY LABEL.
    """

    def test_registered_labelled_tables_match(self):
        # rc42 (M-7): 6 originals + 68 promoted; power tab:captive is the one ordinal table
        # left (its identity column is a number), so the ratchet sat at 74. v1.0.0 Wave 4
        # retired two national entries (tab:categorygas, tab:completeness are stored queries
        # held by test_paper_artefacts.py), so it sits at 73.
        self.assertGreaterEqual(len(LABELLED_TABLES), 73, "the labelled registry shrank")
        problems = []
        for doc, section, label, expected_fn in LABELLED_TABLES:
            printed = _tex_table_labelled(doc, section, label)
            if printed is None:
                problems.append("%s/%s: no table labelled %s" % (doc, section, label))
                continue
            problems += _match_labelled(printed, expected_fn(), label)
        self.assertFalse(problems, "labels and values disagree with the engine:\n  "
                         + "\n  ".join(problems))

    def test_the_rc40_swap_fails_by_name(self):
        """The stored defect: the two rows as rc40 printed them, against the engine's
        rows. The ordinal comparison is satisfied; the labelled one names both rows."""
        printed = [(["Manure management", "3.B", "agriculture"], ["21.82", "4.8", "0.16"]),
                   (["Cement production", "2.A.1", "ippu"], ["21.23", "4.7", "1.90"])]
        expected = [("Cement production", [21.816, 4.82, 0.16]),
                    ("Manure management", [21.228, 4.69, 1.90])]
        ordinal = [abs(float(g) - w) <= 0.5 * 10 ** (-len(g.split(".")[1])) + 1e-9
                   for (_t, got), (_n, want) in zip(printed, expected)
                   for g, w in zip(got, want)]
        self.assertTrue(all(ordinal), "the defect no longer passes the ordinal comparison")
        problems = _match_labelled(printed, expected, "tab:keycat")
        self.assertGreaterEqual(len(problems), 2, problems)
        self.assertTrue(any("'Cement production'" in p for p in problems), problems)
        self.assertTrue(any("'Manure management'" in p for p in problems), problems)

    def test_label_text_reduces_the_manuscripts_decoration(self):
        self.assertEqual(_label_text(r"Oil and gas fugitives$^{e}$"), "Oil and gas fugitives")
        self.assertEqual(_label_text(r"\textbf{Agriculture total}"), "Agriculture total")
        self.assertEqual(_label_text(r"\quad diverted as dung-cake fuel (to Energy)"),
                         "diverted as dung-cake fuel (to Energy)")
        self.assertEqual(_label_text(r"\NHthree{}-N + \NOx{}-N ($\mathrm{Frac_{GasMS}}$)"),
                         "NH3-N + NOx-N (Frac_GasMS)")
        self.assertEqual(_label_text(r"leaching, N\textsubscript{2}, and \NtwoO{}-N"),
                         "leaching, N2, and N2O-N")


class TestPrintedLabelsMatchTheEngine(unittest.TestCase):
    """Table LABELS, not only table numbers.

    TestTablesMatchTheEngine compares numeric cells and drops every text cell, which is
    correct for what it does and is exactly how a stale label survives. The category table
    printed "Urea application and liming" for 3.H for a full round after IPCC_CATEGORY_NAMES
    was corrected to "Urea application" - the numbers in that row were right, and liming is
    3.G, which the same release reports as NE. A label is a claim.
    """

    def _label_column(self, doc, section, label, code_col=0, name_col=1):
        """(code, printed name) for every row of a table whose first two cells are both text
        and are therefore invisible to the numeric comparison."""
        path = _doc_path(doc, section)
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
        block = None
        for m in re.finditer(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", text, re.S):
            if "\\label{%s}" % label in m.group(0):
                block = m.group(0)
                break
        self.assertIsNotNone(block, "no table labelled %s in %s" % (label, section))
        block = _expand_generated_inputs(block, path)
        body = re.search(r"\\begin\{tabular\}\{[^}]*\}(.*?)\\end\{tabular\}",
                         block, re.S).group(1)
        out = []
        for chunk in body.split("\\\\"):
            cells = [c.strip() for c in
                     re.sub(r"\\(top|mid|bottom)rule", "", chunk).strip().split("&")]
            if len(cells) <= max(code_col, name_col) or not cells[code_col]:
                continue
            code = cells[code_col]
            if not re.fullmatch(r"[\d.]+[A-Za-z.\d]*", code):
                continue
            name = re.sub(r"\$\^\{?(?:\\dagger|\\ddagger|e)\}?\$", "",
                          cells[name_col]).strip()
            out.append((code, name))
        return out

    def test_the_category_table_prints_the_declared_IPCC_names(self):
        from pkinv.report import category_ledger
        SHORT = {"Fugitive emissions, oil and natural gas":
                 "Fugitive emissions from oil and natural gas",
                 "Domestic wastewater": "Domestic wastewater treatment and discharge",
                 "Agriculture/forestry/fishing (off-road)":
                 "Agriculture/forestry/fishing/fish farms",
                 "Field burning of residues": "Field burning of agricultural residues"}
        printed = self._label_column("national", "06_results.tex", "tab:categorygas")
        self.assertGreaterEqual(len(printed), 18)
        for code, name in printed:
            declared = category_ledger.IPCC_CATEGORY_NAMES[code]
            self.assertEqual(SHORT.get(name, name), declared,
                             "%s is printed as %r and declared as %r" % (code, name, declared))

    def test_the_key_category_table_prints_the_declared_IPCC_names(self):
        from pkinv.report import category_ledger
        SHORT = {"Public electricity and heat": "Public electricity and heat production",
                 "Domestic wastewater": "Domestic wastewater treatment and discharge",
                 "Fugitive emissions, oil and gas":
                 "Fugitive emissions from oil and natural gas",
                 "Manufacturing and construction":
                 "Manufacturing industries and construction",
                 "Field burning of residues": "Field burning of agricultural residues",
                 "Agriculture/forestry/fishing": "Agriculture/forestry/fishing/fish farms"}
        printed = self._label_column("national", "08_key_categories.tex", "tab:keycat",
                                     code_col=1, name_col=0)
        self.assertGreaterEqual(len(printed), 18)
        for code, name in printed:
            declared = category_ledger.IPCC_CATEGORY_NAMES[code]
            self.assertEqual(SHORT.get(name, name), declared,
                             "%s is printed as %r and declared as %r" % (code, name, declared))
