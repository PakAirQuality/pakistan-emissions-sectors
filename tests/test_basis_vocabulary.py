"""A manuscript may not describe the panel with a basis word the products have retired.

THE DEFECT THIS CLOSES. The agriculture history moved from a FAOSTAT-calendar reconstruction
to a Pakistani fiscal one. Section 6 was rewritten to say so. Section 12 and Section 8 were
not, and went on asserting that agriculture carries "a declared change of basis", that "every
year before the reference year runs on FAOSTAT calendar-year activity - crops, fertiliser and
livestock stocks alike", and that the record is therefore "a hybrid diagnostic series, not a
trend-safe one". Every clause of that was false, and the same paper said the opposite two
sections earlier - about half the inventory.

WHY NOTHING CAUGHT IT. DOC_CLAIMS binds QUANTITIES: a regex, a getter and a tolerance. "Hybrid
diagnostic series" is a qualitative assertion with no number to bind to, and
data/claims_registry.csv holds only numerator-over-denominator claims. So a vocabulary the
products retired could survive in prose indefinitely, and did. This repository has now paid
twice for the same shape - a supplement sentence that denied a shipped product, and this - and
the answer both times is a guard rather than one more careful edit.

WHAT IS ASSERTED. The live vocabulary is DERIVED from the published series and the annual
product, never listed here; the RETIRED terms are declared below with the release that retired
them and what replaced them. A retired term may still appear, but only inside a supersession
window - a sentence that marks it as history, the same licence MANUSCRIPT_CONSTANTS gives a
superseded figure quoted to show what a rejected method would have produced. Anywhere else it
is a live claim and fails.

Run:  python3 -m unittest discover tests -p "test_basis_vocabulary.py"
"""

from pkinv.assets import asset_path
import csv
import glob
import os
import re
import unittest

from pkinv.paths import OUTPUTS, ROOT
from pkinv.core.io import read_rows

SERIES = "pakemis_national_series.csv"
ANNUAL = "pakemis_annual_fy2015_16_fy2024_25.csv"

# Where a reader meets a claim about the national panel. Sector papers are excluded on
# purpose: agriculture's own 1990-2024 diagnostic series IS still FAOSTAT-calendar driven and
# still says so correctly, and a guard that could not tell those two documents apart would
# force a true sentence to be deleted.
PANEL_DOCUMENTS = ("paper_national/versions/v1/sections/*.tex", "paper_national/versions/v1/supplement.tex")

# TERMS THE PRODUCTS RETIRED, each with the release that retired it and what took its place.
# Not a blocklist of bad words - a record of vocabulary changes, so the next basis rename
# inherits this guard instead of re-learning it.
RETIRED = {
    "change of basis": ("1.0.0rc17", "reconstructed-fiscal",
                        "agriculture's history stopped being a source-and-time-basis break "
                        "when crops and nitrogen moved to the Economic Survey's fiscal "
                        "tables in all nine years"),
    "change-of-basis": ("1.0.0rc17", "reconstructed-fiscal", "the machine-readable form of "
                        "the same retired label"),
    "hybrid diagnostic series": ("1.0.0rc17", "a fiscal reconstruction with a declared "
                                 "calendar-driven livestock half",
                                 "the pre-anchor record is no longer a diagnostic splice; "
                                 "what remains calendar-driven is named and its phase error "
                                 "is measured"),
    "calendar_faostat": ("1.0.0rc17", "reconstructed-fiscal",
                         "still the correct label for agriculture's separate 1990-2024 "
                         "diagnostic series, which is why only panel documents are searched"),
}

# A retired term is allowed within this many characters of a marker that frames it as history.
# Generous on purpose: the point is to catch an ASSERTION, not to police sentence length.
SUPERSESSION_WINDOW = 400
SUPERSESSION_MARKERS = ("superseded", "earlier releases", "earlier edition", "used to",
                        "no longer", "previously", "formerly", "that description is")


def _documents():
    out = {}
    for pattern in PANEL_DOCUMENTS:
        for path in sorted(glob.glob(asset_path(ROOT, pattern))):
            with open(path, encoding="utf-8") as handle:
                out[os.path.relpath(path, ROOT)] = handle.read()
    return out


def _rows(name):
    return read_rows(os.path.join(OUTPUTS, name))


def live_bases():
    """Every activity_basis word the shipped products actually use, derived not declared."""
    out = {r["activity_basis"] for r in _rows(SERIES) if r.get("activity_basis")}
    out |= {r["activity_basis"] for r in _rows(ANNUAL) if r.get("activity_basis")}
    return out - {""}


class TestTheRetiredVocabularyIsGone(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.documents = _documents()

    def test_no_retired_term_is_asserted_as_current(self):
        offences = []
        for path, text in sorted(self.documents.items()):
            lowered = text.lower()
            for term in RETIRED:
                for match in re.finditer(re.escape(term), lowered):
                    start = max(0, match.start() - SUPERSESSION_WINDOW)
                    window = lowered[start:match.end() + SUPERSESSION_WINDOW]
                    if any(marker in window for marker in SUPERSESSION_MARKERS):
                        continue
                    line = text[:match.start()].count("\n") + 1
                    offences.append("%s:%d uses %r" % (path, line, term))
        self.assertFalse(offences,
                         "manuscript passages assert a basis vocabulary the products "
                         "retired:\n  %s\nEither restate them against the published "
                         "activity_basis, or mark the mention as history."
                         % "\n  ".join(offences))

    def test_every_retired_term_is_actually_retired(self):
        """A term listed here that the products still USE would silence a true sentence.
        The live vocabulary is read from the products, so this cannot drift."""
        live = live_bases()
        for term, (_release, replacement, _reason) in RETIRED.items():
            self.assertNotIn(term, live,
                             "%r is listed as retired and the published series still uses "
                             "it; the replacement was declared as %r" % (term, replacement))

    def test_every_retirement_names_its_release_and_its_replacement(self):
        for term, entry in RETIRED.items():
            release, replacement, reason = entry
            self.assertRegex(release, r"^\d+\.\d+\.\d+", term)
            self.assertTrue(replacement, term)
            self.assertGreater(len(reason), 40,
                               "%r is retired without a reason anyone can check" % term)

    def test_the_replacement_vocabulary_is_the_one_in_use(self):
        """The positive half. Retiring a word is only half a statement; the guard is worth
        little if what replaced it is not what the products say."""
        live = live_bases()
        self.assertIn("reconstructed-fiscal", live,
                      "the series no longer publishes `reconstructed-fiscal`, so the "
                      "retirements recorded here describe a vocabulary change that did not "
                      "happen or has been undone")
        self.assertIn("observed", live)


class TestThePanelIsDescribedAsItIsBuilt(unittest.TestCase):
    """Two assertions the products can settle, held so the sections cannot drift apart
    again in the direction that matters: understating what is still calendar-driven."""

    @classmethod
    def setUpClass(cls):
        cls.text = " ".join(_documents().values()).lower()

    def test_the_census_reconstruction_and_extrapolation_are_disclosed(self):
        """Stocks retain source/anchor limitations; the old projection level is not current."""
        for phrase in ("livestock", "census", "reconstruct", "extrapolat"):
            self.assertIn(phrase, self.text)

    def test_agriculture_is_not_called_wholly_fiscal(self):
        for claim in ("agriculture is reconstructed on fiscal activity in every category",
                      "the whole sector is fiscal"):
            self.assertNotIn(claim, self.text)


if __name__ == "__main__":
    unittest.main()
