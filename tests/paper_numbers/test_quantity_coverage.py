"""Every printed quantity is protected.

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
    DOCS,
    ROOT,
    _doc_path,
    active_sections,
    _rows)
from paper_numbers.quantity_policy import (
    COVERED_DOCUMENTS,
    GENERATED_SECTIONS,
    MANUSCRIPT_CONSTANTS,
    SHARED_CONSTANTS,
    TIER1_FLOOR,
    _covered_values,
    _document_registered_values,
    _quantities)


class TestEveryPrintedQuantityIsProtected(unittest.TestCase):
    """Two tiers, and the second is not a weakening.

    TIER 1 is a DOC_CLAIMS or TABLES entry: the value is checked against the engine in the
    place it is printed, so it is verified to mean what its sentence says.

    TIER 2 is a repeat elsewhere in the same document of a value that IS registered
    somewhere in it - `\\SI{5.61}{\\mega\\tonne}` recurring in three sections when the
    abstract's copy is anchored. This still catches drift, and the mechanism is worth
    stating because it is the whole reason the tier is admissible: if the engine moves,
    the registered site fails, it gets re-anchored to the new value, and at that moment the
    old value is no longer registered anywhere in the document - so every unrepaired repeat
    becomes uncovered and THIS test fails. The two tiers ratchet against each other.

    What tier 2 does not do is check that the repeat is used correctly - a sentence could
    attach a correctly-current number to the wrong noun. Promoting a repeat to tier 1 is
    therefore always an improvement, and the counts below are reported so it is visible how
    much of the paper rests on each.
    """

    def _survey(self):
        """{doc: (tier1, tier2, generated, constants, uncovered)}, each a list of
        section:line value strings."""
        by_doc = {}
        for doc in COVERED_DOCUMENTS:
            tier1, tier2, generated, constants, uncovered = [], [], [], [], []
            registered = _document_registered_values(doc)
            for section in sorted(active_sections(doc)):
                if not section.endswith(".tex"):
                    continue
                if (doc, section) in GENERATED_SECTIONS:
                    generated += ["%s:%d  %s" % (section, lineno, value)
                                  for value, lineno in _quantities(doc, section)]
                    continue
                here = _covered_values(doc, section)
                for value, lineno in _quantities(doc, section):
                    where = "%s:%d  %s" % (section, lineno, value)
                    if value in here:
                        tier1.append(where)
                    elif value in SHARED_CONSTANTS or (doc, value) in MANUSCRIPT_CONSTANTS:
                        constants.append(where)
                    elif value in registered:
                        tier2.append(where)
                    else:
                        uncovered.append(where)
            by_doc[doc] = (tier1, tier2, generated, constants, uncovered)
        return by_doc

    def test_no_quantity_is_unregistered(self):
        """Every printed quantity is checked, with no declared-debt exemption.

        This replaced a pair of tests that bounded a shrinking list of unprotected numbers.
        The list was honest about what it contained and useless as a guard: a stale gas
        decomposition sat in it for three releases, 7 Mt out, while both bounding tests
        passed - because neither compared a listed entry against anything. See the note
        above the constants table for the full account.

        There is no third state now. A quantity is registered against an output, or it is a
        constant with a reason, or this fails.
        """
        uncovered = [u for tallies in self._survey().values() for u in tallies[4]]
        keys = sorted({u.split(":")[0] + ":" + u.split()[-1] for u in uncovered})
        self.assertFalse(
            keys,
            "%d printed quantities are checked against nothing. Register each in DOC_CLAIMS "
            "or TABLES, or add it to MANUSCRIPT_CONSTANTS with the reason it cannot go "
            "stale. If it has no output behind it, generate one:\n  %s"
            % (len(keys), "\n  ".join(keys)))

    def test_tier_one_coverage_does_not_regress(self):
        """A ratchet on quality, not just on correctness. Tier 2 is admissible but weaker,
        so the share of the paper verified in place must not fall - otherwise the easy way
        to add a number would be to lean on a repeat somewhere else."""
        for doc, (tier1, tier2, generated, constants, uncovered) in \
                self._survey().items():
            total = (len(tier1) + len(tier2) + len(generated) + len(constants)
                     + len(uncovered))
            in_place = len(tier1) + len(generated)
            if total == 0:
                # The maintained v1 supplement now routes details through
                # qualitative/source-account appendices. Current v3 quantities
                # have their own macro/product audit, not a fabricated denominator.
                self.assertEqual(doc, "national-supplement")
                continue
            self.assertIn(doc, TIER1_FLOOR,
                          "%s is swept but has no declared tier-1 floor" % doc)
            # The ratchet concerns reported model quantities. Literature values
            # and declared method constants are checked as such, and adding a
            # factor/source table must not lower the result-coverage fraction.
            results = total - len(constants)
            if results == 0:
                self.assertFalse(uncovered)
                continue
            self.assertGreaterEqual(
                in_place / results, TIER1_FLOOR[doc],
                "%s: in-place coverage has fallen to %d/%d (floor %.2f); tier 2 repeats "
                "are %d and constants %d"
                % (doc, in_place, total, TIER1_FLOOR[doc], len(tier2), len(constants)))

    def test_the_whitelist_does_not_shadow_a_result(self):
        """The way this guard would be defeated: park a real result in the constants list.

        A constant that also appears as a value in an engine output is not a constant, it is
        a result somebody exempted, and the exemption would silence exactly the drift the
        test exists to catch.
        """
        # MAGNITUDE columns only. Shares, ratios and percentage bands are bounded, so at two
        # decimal places they collide with IPCC factor constants by coincidence rather than
        # by anyone hiding a result - 3.9 kg/TJ against a 3.9 percent share, 0.71 oxidation
        # against a 0.71 benchmark ratio. A result parked as a constant would have to be a
        # quantity, and this is where a quantity lives.
        MAGNITUDE_COLUMNS = ("co2e_Mt_AR5", "co2e_Mt_AR6", "emissions_Gg",
                             "level_Mt_co2e_AR5", "mean_Mt", "P50_Mt",
                             "benchmark_Mt_co2e", "engine_Mt_co2e")
        engine = set()
        for name in ("national_all_sectors.csv", "national_key_categories.csv",
                     "national_uncertainty_montecarlo.csv",
                     "national_benchmark_comparison.csv"):
            for row in _rows(name):
                for column, cell in row.items():
                    cell = (cell or "").strip()
                    if column in MAGNITUDE_COLUMNS and re.fullmatch(r"\d+\.\d+", cell):
                        # Two decimal places stop being an identity below ~0.05 Mt:
                        # the rc11 rail re-base's 0.005 Mt category made every small
                        # IPCC factor constant "shadow" a magnitude cell that rounds
                        # to 0.00 or 0.01, which is coincidence of scale, not a
                        # parked result. A real parked result at that size would be
                        # invisible at any threshold this comparison can express.
                        if float(cell) < 0.05:
                            continue
                        engine.add("%.2f" % float(cell))
        # A constant whose own justification declares it a share, fraction or ratio
        # cannot be a parked magnitude - the rc11 rail re-base's 0.384 Mt median
        # collided with residential's 0.38 household-share constant, a coincidence
        # of decimal representation between two different kinds of quantity.
        dimensionless = {v for (_doc, v), why in MANUSCRIPT_CONSTANTS.items()
                         if any(w in why.lower() for w in ("share", "fraction", "ratio"))}
        declared = (set(SHARED_CONSTANTS)
                    | {v for _doc, v in MANUSCRIPT_CONSTANTS}) - dimensionless
        shadowed = [v for v in declared
                    if re.fullmatch(r"\d+\.\d+", v) and "%.2f" % float(v) in engine]
        self.assertFalse(shadowed,
                         "these are engine results, not constants: %s" % shadowed)

    def test_every_generated_section_has_a_live_generator(self):
        """An unbacked GENERATED exemption would be the constants defect in a new shape:
        a section skipped on the claim of byte-equality that nothing enforces."""
        for (doc, section), script in GENERATED_SECTIONS.items():
            self.assertTrue(os.path.exists(_doc_path(doc, section)),
                            "(%s, %s) is exempted but does not exist" % (doc, section))
            script_path = os.path.join(ROOT, "scripts", script)
            self.assertTrue(os.path.exists(script_path),
                            "(%s, %s): generator %s does not exist"
                            % (doc, section, script))
            self.assertIn(section, open(script_path, encoding="utf-8").read(),
                          "%s does not name %s as its output" % (script, section))

    def test_the_registry_covers_the_flagship(self):
        """A coverage test over an empty document list passes while checking nothing."""
        self.assertIn("national", COVERED_DOCUMENTS)
        total = sum(len(_quantities("national-v3", s)) for s in active_sections("national-v3"))
        self.assertGreaterEqual(total, 30, "the integrated article's native/GWP/air quantitative macros vanished")
