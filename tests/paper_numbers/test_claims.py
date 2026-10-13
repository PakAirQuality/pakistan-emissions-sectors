"""Restated movements, semantic claims and the DOC_CLAIMS sweep.

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
from paper_numbers.doc_claims import (
    CLAIMS,
    DIRECTION_WORDS,
    DOC_CLAIMS,
    MOVEMENTS)


def _movement_problems(printed_from, printed_to, engine_from, engine_to, span=""):
    """The whole decision, as a pure function so it can be tested on strings that are not
    in any document. Returns a list of problems; empty means the restatement is faithful."""
    problems = []
    decimals = max(len(printed_from.split(".")[-1]) if "." in printed_from else 0,
                   len(printed_to.split(".")[-1]) if "." in printed_to else 0)
    want_from, want_to = round(engine_from, decimals), round(engine_to, decimals)
    got_from, got_to = float(printed_from), float(printed_to)
    if got_from != want_from:
        problems.append("starts at %s; the engine rounds to %s" % (printed_from, want_from))
    if got_to != want_to:
        problems.append("ends at %s; the engine rounds to %s" % (printed_to, want_to))
    printed_move = got_to - got_from
    engine_move = want_to - want_from
    def sign(x):
        return (x > 0) - (x < 0)
    if sign(printed_move) != sign(engine_move):
        problems.append("moves %s while the engine moves %s"
                        % ("up" if printed_move > 0 else
                           "down" if printed_move < 0 else "not at all",
                           "up" if engine_move > 0 else
                           "down" if engine_move < 0 else "not at all"))
    elif abs(printed_move - engine_move) > 1e-9:
        problems.append("moves by %.4g against the engine's %.4g"
                        % (printed_move, engine_move))
    flat = span.lower()
    for word, direction in DIRECTION_WORDS.items():
        if re.search(r"\b%s\b" % word, flat) and sign(engine_move) not in (0, direction):
            problems.append("says %r about a movement that goes the other way" % word)
            break
    return problems


class TestRestatedMovementsKeepTheirDirection(unittest.TestCase):
    """Every place the paper restates a before-and-after pair, checked as a pair."""

    def test_every_restated_movement_matches_the_engine(self):
        problems = []
        for name, doc, section, pattern, from_metric, to_metric in MOVEMENTS:
            path = _doc_path(doc, section)
            with open(path, encoding="utf-8") as handle:
                text = " ".join(handle.read().split())
            match = re.search(pattern, text)
            if match is None:
                problems.append("%s: the pattern no longer matches %s -- re-anchor it or "
                                "retire it, because an unmatched movement is unchecked"
                                % (name, section))
                continue
            # Only the sentence the pair sits in. A wider window reads direction words out
            # of neighbouring sentences -- Section 7.3 describes the SUPERSEDED edition's
            # "widening" two sentences after stating the current movement, and that is
            # reporting history, not a claim about these two numbers.
            sentence_start = max(text.rfind(". ", 0, match.start()) + 1, 0)
            span = text[sentence_start:match.end()]
            for problem in _movement_problems(match.group(1), match.group(2),
                                              from_metric(), to_metric(), span):
                problems.append("%s: %s" % (name, problem))
        self.assertFalse(problems, "restated movements disagree with the engine:\n  "
                         + "\n  ".join(problems))

    def test_the_movement_registry_is_not_empty_and_is_well_formed(self):
        """A one-group pattern would check the FROM end and leave the TO end unchecked while
        the test still passed -- which is how the conclusion's 11.1 survived in the first
        place. Both groups are required."""
        # Five until rc41 Wave 4, when the transport module stopped moving between the
        # two correlation structures and its entry became a plain two-way anchor.
        self.assertGreaterEqual(len(MOVEMENTS), 4)
        for name, doc, section, pattern, _from, _to in MOVEMENTS:
            self.assertTrue(os.path.exists(_doc_path(doc, section)),
                            "%s points at a section that does not exist" % name)
            self.assertEqual(re.compile(pattern).groups, 2,
                             "%s captures %d groups; a movement has two ends"
                             % (name, re.compile(pattern).groups))

    def test_the_guard_catches_the_conclusion_defect(self):
        """The stored positive control. Reinstating the defect is a one-off check; this
        keeps it reinstated forever."""
        problems = _movement_problems("11.2", "11.1", 11.25, 11.29)
        self.assertGreaterEqual(len(problems), 2,
                                "the historical conclusion sentence must fail on both the "
                                "endpoint and the direction, got: %r" % problems)
        # A reversal alone, with both endpoints inside any plausible tolerance.
        self.assertTrue(_movement_problems("11.3", "11.2", 11.25, 11.29),
                        "a reversed movement passed -- this guard exists for that case")
        # And the faithful restatement must pass, or the guard is just noise.
        self.assertEqual([], _movement_problems("11.2", "11.3", 11.25, 11.29))
        self.assertEqual([], _movement_problems("11.25", "11.29", 11.25, 11.29))
        # A direction word pointing the wrong way, with correct numbers.
        self.assertTrue(_movement_problems("11.2", "11.3", 11.25, 11.29, "narrows to"),
                        "a sentence saying 'narrows' about a widening passed")


class TestSemanticClaims(unittest.TestCase):
    """Comparative language, checked against the relation it asserts.

    Number-anchoring is structurally unable to catch this: every digit in "widens by half, and
    transport doubles" was current when a reviewer found it, and neither ratio was right.
    """

    def test_every_claimed_relation_holds(self):
        problems = []
        for name, doc, section, phrase, operator, reference, tol, metric in CLAIMS:
            path = _doc_path(doc, section)
            with open(path, encoding="utf-8") as handle:
                text = " ".join(handle.read().split())
            if phrase not in text:
                problems.append("%s: the phrase %r is no longer in %s - if the sentence was "
                                "rewritten, retire or restate the claim" % (name, phrase,
                                                                            section))
                continue
            actual = metric()
            if operator == "ratio_at_least" and actual < reference:
                problems.append("%s: %r claims at least %.2f, the engine gives %.3f"
                                % (name, phrase, reference, actual))
            elif operator == "ratio_within" and abs(actual - reference) > tol:
                problems.append("%s: %r claims about %.2f, the engine gives %.3f"
                                % (name, phrase, reference, actual))
            elif operator == "count_equals" and abs(actual - reference) > 1e-9:
                problems.append("%s: %r claims %g, the engine gives %g"
                                % (name, phrase, reference, actual))
            elif operator == "less_than" and not actual < reference:
                problems.append("%s: %r claims less than %.3f, the engine gives %.3f"
                                % (name, phrase, reference, actual))
        self.assertFalse(problems, "the paper's comparative language disagrees with the "
                                   "engine:\n  " + "\n  ".join(problems))

    def test_the_registry_is_not_empty_and_names_real_sections(self):
        """A registry-driven test over an empty registry passes green while checking nothing,
        and every claim must point at a document that exists."""
        self.assertGreaterEqual(len(CLAIMS), 5)
        for name, doc, section, _p, operator, _r, _t, _m in CLAIMS:
            self.assertTrue(os.path.exists(_doc_path(doc, section)),
                            "%s points at a section that does not exist" % name)
            self.assertIn(operator, ("ratio_at_least", "ratio_within", "count_equals",
                                     "less_than"))


class TestPaperNumbers(unittest.TestCase):
    def test_every_claim_still_matches_its_output(self):
        stale, unanchored = [], []
        every = [(c[1], c[0]) + c[2:] for c in DOC_CLAIMS]
        for doc, label, section, pattern, getter, tol in every:
            label = "%s/%s" % (doc, label)
            path = _doc_path(doc, section)
            if not os.path.exists(path):
                unanchored.append("%s: %s missing" % (label, section))
                continue
            m = re.search(pattern, open(path, encoding="utf-8").read())
            if not m:
                unanchored.append("%s (%s): anchor no longer matches" % (label, section))
                continue
            text = m.group(1)
            printed, actual = float(text), getter()
            dp = len(text.split(".")[1]) if "." in text else 0
            half_ulp = 0.5 * 10 ** (-dp) + 1e-9      # the paper shows a rounded number
            if abs(printed - actual) > half_ulp + tol:
                stale.append("%s (%s): paper says %s, engine says %.4g"
                             % (label, section, text, actual))
        msg = []
        if unanchored:
            msg.append("anchors lost -- re-anchor these or coverage silently disappears:\n  "
                       + "\n  ".join(unanchored))
        if stale:
            msg.append("paper disagrees with the engine:\n  " + "\n  ".join(stale))
        self.assertFalse(msg, "\n\n".join(msg))

    def test_national_paper_states_the_cross_sector_ar5_contract(self):
        from pkinv.core.gwp import GWP
        with open(_doc_path("national", "03_architecture.tex"), encoding="utf-8") as handle:
            text = handle.read()
        expected = {
            "CO2": r"CO\$_2=([\d.]+)\$",
            "CH4": r"biogenic CH\$_4=([\d.]+)\$",
            "CH4_fossil": r"fossil CH\$_4=([\d.]+)\$",
            "N2O": r"N\$_2\$O\$=([\d.]+)\$",
        }
        for key, pattern in expected.items():
            match = re.search(pattern, text)
            self.assertIsNotNone(match, "national GWP wording lost for %s" % key)
            self.assertEqual(float(match.group(1)), GWP["AR5"][key])
