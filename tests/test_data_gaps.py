"""The gap register, and the guard that stops "no data exists" being written about an unopened PDF.

A data-availability audit of the nine sector papers found the same error in every one of them:
claims of the form "no Pakistani source reports X" where the truth was "X has not been acquired,
extracted or reconciled here." Those are different statements. The first is about the world and
is almost never checkable; the second is about this inventory and always is.

Several were wrong from inside this repository. The power paper said no generation figure was
used while data/activity/power/generation_by_fuel.csv sat loaded and never read. The transport
paper called CNG's absence "a data-availability problem" when the transport row is in the same
OGRA table this inventory already reads for residential gas. The cement paper said no Pakistani
source reported the clinker fraction; listed producers publish clinker and cement separately.

Prose alone could not hold the correction - it was prose that drifted. So the classification
lives in data/data_gaps.csv, and these tests make it load-bearing:

  * every NE row in the completeness table has exactly one register entry, both ways;
  * nonexistence wording is permitted ONLY where claim_class says the datum does not exist;
  * an unverified lead cannot be cited as a source in any activity file.

Run:  python3 -m unittest discover tests -p "test_data_gaps.py"
"""
import csv
import glob
import os
from pkinv.paths import PAPER_NATIONAL_SECTIONS  # noqa: E402
import re
import unittest

from pkinv.report import completeness
from _support import ROOT

GAPS = completeness.load_data_gaps()

# Sections whose prose is checked for absolute claims. The manuscripts are the surface a reader
# actually meets, so a claim corrected in the completeness table and left standing in a paper is
# only half corrected - which is the state the audit found this inventory in.
MANUSCRIPTS = sorted(glob.glob(os.path.join(ROOT, "papers", "*", "sections", "*.tex"))
                     + glob.glob(os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex")))

# Absolute wording is legitimate about things other than data availability - "no memo stream",
# "no electric traction", "no external comparator". The guard fires on a phrase only when it is
# followed closely by a data noun, and this list is what makes it specific rather than a
# vocabulary ban. Deliberately narrow: a guard that flags everything gets switched off.
DATA_NOUNS = (r"statistic", r"source", r"dataset", r"data\b", r"figure", r"series", r"survey",
              r"quantity", r"table", r"measurement", r"census", r"record")


def _absolute_claims(text):
    """(phrase, window) for each nonexistence phrase sitting next to a data noun.

    A hit is suppressed when the same sentence qualifies the claim to this inventory, because
    that is the corrected form rather than a violation of it.
    """
    hits = []
    flat = re.sub(r"\s+", " ", text)
    needs_noun = {p: True for p in completeness.ABSOLUTE_CLAIM_PHRASES}
    needs_noun.update({p: False for p in completeness.ABSOLUTE_CLAIM_PHRASES_STRICT})
    for phrase, noun_required in needs_noun.items():
        for m in re.finditer(re.escape(phrase), flat, re.IGNORECASE):
            window = flat[m.start():m.start() + 120]
            if noun_required and not any(re.search(n, window, re.IGNORECASE)
                                         for n in DATA_NOUNS):
                continue
            # The qualifier can precede the phrase as easily as follow it - "this
            # inventory holds no nationally measured parameter" - so look both ways.
            sentence = flat[max(0, m.start() - 120):m.start() + 120]
            if any(q in sentence.lower() for q in completeness.ACQUISITION_QUALIFIERS):
                continue
            hits.append((phrase, window))
    return hits


class TestRegisterShape(unittest.TestCase):
    def test_every_row_is_complete(self):
        required = ("gap_id", "kind", "code", "category", "claim_class", "verified", "note")
        for g in GAPS:
            for col in required:
                self.assertTrue((g.get(col) or "").strip(),
                                "%s: empty %s" % (g.get("gap_id"), col))

    def test_gap_ids_are_unique(self):
        ids = [g["gap_id"] for g in GAPS]
        self.assertEqual(len(ids), len(set(ids)), "duplicate gap_id")

    def test_claim_classes_and_kinds_are_from_the_vocabulary(self):
        for g in GAPS:
            self.assertIn(g["claim_class"], completeness.CLAIM_CLASSES, msg=g["gap_id"])
            # "closed" is a third kind, not a status column: an entry that WAS a gap and has
            # been resolved stays in the register so the resolution is on the record rather
            # than vanishing with the problem. Closed rows take no part in the NE sync, which
            # keys on "gap" alone.
            self.assertIn(g["kind"], ("gap", "weak-input", "closed"), msg=g["gap_id"])
            self.assertIn(g["verified"], ("yes", "no"), msg=g["gap_id"])

    def test_access_is_declared_where_a_dataset_is_named(self):
        """A lead without an access route is not actionable - it is a wish."""
        for g in GAPS:
            if g["dataset"] and g["claim_class"] != "no-data-exists":
                self.assertIn(g["access"], ("public", "registration", "paid", "request"),
                              msg="%s names a dataset with no access route" % g["gap_id"])

    ARTEFACTS = ("pkinv.", "outputs/", "scripts/")

    def test_closed_entries_say_where_the_resolution_lives(self):
        """A row marked closed must point at the code or output that closed it, or the claim
        that it is done rests on nothing.

        `scripts/` counts, and did not until a gap was closed by one. The FY2020-21 gas gap
        was closed by rendering an image scan and reading it - the artefact that matters is
        the reader, because it is what lets anyone repeat the read and what would catch a
        later edition disagreeing. A guard that accepted only modules and outputs would have
        pushed that pointer out of the register.
        """
        for g in GAPS:
            if g["kind"] == "closed":
                self.assertTrue("CLOSED" in g["note"] and
                                any(a in g["note"] for a in self.ARTEFACTS),
                                "%s is closed but names no artefact" % g["gap_id"])

    def test_no_data_exists_names_no_obtainable_dataset(self):
        """The class means nobody has measured it. If a holder can be named, it is obtainable
        and belongs in one of the other four classes."""
        for g in GAPS:
            if g["claim_class"] == "no-data-exists":
                self.assertFalse(g["holder"].strip(),
                                 "%s is classed no-data-exists but names a holder (%s)"
                                 % (g["gap_id"], g["holder"]))


class TestRegisterMatchesCompleteness(unittest.TestCase):
    def test_bidirectional_sync(self):
        """Delegates to the module so the build and the suite cannot disagree about it."""
        completeness._check_gaps()

    def test_every_ne_row_carries_its_class_into_the_output(self):
        with open(os.path.join(ROOT, "outputs", "completeness.csv"),
                  newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        ne = [r for r in rows if r["notation_key"] == "NE"]
        self.assertTrue(ne)
        for r in ne:
            self.assertTrue(r["claim_class"], "NE row without a claim_class: %s" % r["category"])
            self.assertTrue(r["gap_id"])


class TestAbsoluteClaims(unittest.TestCase):
    """The guard the audit's finding exists to make un-repeatable."""

    # Each entry must be answerable with a no-data-exists register row or a reason the
    # sentence is not a data-availability claim at all. Adding a line here without one is
    # how the guard would be hollowed out.
    ALLOWED = tuple(sorted({
        # -- backed by a no-data-exists register row --
        "no national dataset records",              # air-power-controlled
        "no Pakistani source reports the hydraulic condition",   # wastewater-sewer-mcf
        "no Pakistani source does, is the hydraulic condition",  # wastewater-sewer-mcf
        "No national survey measures how excreted nitrogen",     # mms-distribution
        # -- not claims about data availability --
        # "Inventories that estimate landfilling and open burning independently have no
        # such constraint" - about a method, not about a dataset.
        "no such constraint",
        # "a number supported by no source at all" - about a hypothetical figure nobody
        # would be able to cite, in the railway BUR-1 refutation.
        "supported by no source at all",
        # -- verbatim quotations of this inventory's OWN earlier documentation --
        # The national paper quotes the warnings that the closures were built from. A
        # quotation rewritten to match current wording is no longer a quotation, and the
        # point of those passages is that the old wording was as it was.
        "no national figure to remove them by''",
        # railways/reconcile.py RETRACTS the claim it quotes, in the next sentence: the
        # detailed table on p.163 does separate the fuel. A retraction has to be able to
        # state what it retracts.
        'and "is not separable". That was a claim about the source and it was wrong',
    }))


    def test_justifications_do_not_assert_nonexistence_unless_true(self):
        allowed = {(g["code"], g["category"]) for g in GAPS
                   if g["claim_class"] == "no-data-exists"}
        problems = []
        for code, cat, _gas, key, _eng, why in completeness.ROWS:
            if key != "NE" or (code, cat) in allowed:
                continue
            for phrase, window in _absolute_claims(why):
                problems.append("%s / %s says %r but is not classed no-data-exists:\n      %s"
                                % (code, cat, phrase, window))
        self.assertFalse(problems,
                         "completeness justifications assert a datum does not exist for gaps "
                         "that are merely unobtained. Say what this inventory did instead "
                         "(\"not obtained here\"), or reclassify the register row:\n  "
                         + "\n  ".join(problems))

    def test_manuscripts_do_not_assert_nonexistence(self):
        """Same rule over the prose a reader actually meets.

        The allowlist is keyed to the sentence, not to a file: a paper may state that a datum
        does not exist where a register row says so, and the register is the place to argue
        about it.
        """
        allowed = self.ALLOWED
        problems = []
        for path in MANUSCRIPTS:
            text = open(path, encoding="utf-8").read()
            for phrase, window in _absolute_claims(text):
                if any(a.lower() in window.lower() for a in allowed):
                    continue
                problems.append("%s: %r\n      %s"
                                % (os.path.relpath(path, ROOT), phrase, window.strip()))
        self.assertFalse(problems,
                         "manuscript prose asserts a datum does not exist. Either say what "
                         "this inventory did (\"not obtained here\"), or add the sentence to "
                         "the allowlist with a no-data-exists register row behind it:\n  "
                         + "\n  ".join(problems))

    # Claims stronger than the inventory's own evidence, each with the phrasing that is
    # supportable. These are not vocabulary bans: every one was in the flagship manuscript
    # while the same manuscript's limitations section contradicted it.
    OVERREACH = [
        (r"\bcomplete ten-sector\b",
         "the completeness table names ~45 Mt of absent sources - say which sources are "
         "covered, or quote the EDGAR coverage ratio"),
        (r"every activity figure traced to a published national",
         "several inputs are international defaults, proxies, survey-derived or assumed - "
         "say that every input carries a provenance and evidence-status record instead"),
        (r"particulate exposure",
         "the inventory estimates emitted mass, not exposure; exposure needs ventilation, "
         "proximity and time-activity, none of which is modelled here"),
        (r"every property an inventory compiler would otherwise check by reading is asserted",
         "the suite asserts a defined set of properties, not every property - the stale "
         "firewood, rail-closure and uncertainty prose are the proof"),
    ]

    def test_no_claim_outruns_the_inventorys_own_evidence(self):
        problems = []
        for path in MANUSCRIPTS:
            flat = re.sub(r"\s+", " ", open(path, encoding="utf-8").read())
            for pattern, why in self.OVERREACH:
                if re.search(pattern, flat, re.IGNORECASE):
                    problems.append("%s: %s\n      %s"
                                    % (os.path.relpath(path, ROOT), pattern, why))
        self.assertFalse(problems, "a claim outruns the evidence this inventory reports:\n  "
                                   + "\n  ".join(problems))


    def test_module_docstrings_do_not_assert_nonexistence(self):
        """The third surface, and the one the other two are written from.

        Every claim corrected above began life in a module docstring - this inventory writes its
        method prose there and the papers quote it. Covering only the papers would leave the
        source of the drift unguarded.

        MODULE docstrings only, via ast: scanning whole files flags exception messages like
        "GLW unavailable: %s", which are runtime diagnostics rather than claims about Pakistani
        statistics, and a guard that cries wolf on those gets muted.
        """
        import ast
        problems = []
        for path in sorted(glob.glob(os.path.join(ROOT, "src", "pkinv", "**", "*.py"),
                                     recursive=True)):
            try:
                doc = ast.get_docstring(ast.parse(open(path, encoding="utf-8").read())) or ""
            except SyntaxError:
                continue
            for phrase, window in _absolute_claims(doc):
                if any(a.lower() in window.lower() for a in self.ALLOWED):
                    continue
                problems.append("%s: %r\n      %s"
                                % (os.path.relpath(path, ROOT), phrase, window.strip()))
        self.assertFalse(problems,
                         "a module docstring asserts a datum does not exist. The papers are "
                         "written from these, so this is where the claim gets in:\n  "
                         + "\n  ".join(problems))


class TestLeadsCannotLeakIntoData(unittest.TestCase):
    """An unread document must not become a citation.

    The whole point of reclassifying is to distinguish what has been read from what has been
    heard about. That distinction survives only if a `verified: no` lead cannot appear in a
    source column, where it would be indistinguishable from a document someone actually opened.
    """

    def test_unverified_datasets_are_not_cited_as_sources(self):
        unverified = [g for g in GAPS if g["verified"] == "no" and g["dataset"].strip()]
        self.assertTrue(unverified, "the register has no unverified leads - is it loaded?")
        # Distinctive names only: "Economic Survey" and "OGRA" are already legitimately cited
        # by data this inventory has read, so matching on them would flag correct rows.
        # "HIES" left this set in August 2026 when both microdata rounds were fetched,
        # hash-pinned and processed (sources/HIES/MANIFEST.csv) - it is a read document now.
        # "Pakistan Energy Yearbook" left the set at rc13 the same way HIES did: the PEY
        # Table 4.4 coal tables WERE read and transcribed (gap pey-coal-table,
        # verified=yes, data/activity/industry/brick_kiln_coal.csv) - the Yearbook is a
        # read-not-kept document now, not a lead. "HDIP" stays: the institution's OTHER
        # products (the industrial energy balance behind 1A2-industrial-fuel) remain
        # unread, and a bare HDIP citation still means a lead leaked.
        #
        # "APCMA" left the set in August 2026, on the same standard: the five monthly despatch
        # pages were fetched, hash-pinned in data/manifests/source_manifest.csv, parsed under
        # three of the publication's own controls and cross-checked against PBS QIM
        # (scripts/ingest_apcma_dispatches.py). The DESPATCH pages are a read document now.
        #
        # THIS IS NARROWER THAN IT LOOKS, and the narrowness is the point. The gap
        # `cement-provincial-allocation` still reads verified=no and still names APCMA,
        # because what it wants is PROVINCIAL plant output and what was read is a NORTH/SOUTH
        # zone split - two regions are not four provinces. That gap is unclosed and the
        # register says so; what changed is only that a bare "APCMA" string is no longer
        # evidence on its own that a lead leaked.
        needles = {"PSLM", "Urban Unit", "PPIS", "PCRWR", "HDIP"}
        cited = []
        for path in glob.glob(os.path.join(ROOT, "data", "**", "*.csv"), recursive=True):
            if os.path.basename(path) == "data_gaps.csv":
                continue
            with open(path, newline="", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    src = " ".join(str(row.get(c) or "") for c in ("source", "source_edition"))
                    for n in needles:
                        for m in re.finditer(re.escape(n), src, re.IGNORECASE):
                            # "NEPRA SoIR Table 3 (from HDIP Pakistan Energy Yearbook)" is a
                            # PROVENANCE CHAIN, not a claim to have opened the Yearbook: the
                            # document read is NEPRA's, which names its own upstream source.
                            # Naming where a verified document got its figures is good practice
                            # and must not be what this guard punishes.
                            if "from" in src[max(0, m.start() - 24):m.start()].lower():
                                continue
                            cited.append("%s cites %r" % (os.path.relpath(path, ROOT), n))
        self.assertFalse(sorted(set(cited)),
                         "activity data cite a document the register marks unverified. Read it "
                         "and set verified=yes, or stop citing it:\n  "
                         + "\n  ".join(sorted(set(cited))))


if __name__ == "__main__":
    unittest.main()
