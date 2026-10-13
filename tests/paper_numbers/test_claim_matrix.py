"""The claim matrix (docs/essd_outline.md): every headline claim of the national manuscript
is a row of data/claim_matrix.csv, every row resolves against the release, the printed value
agrees with the resolved one, and the matrix covers the headline rule in both directions.

Direction one (the matrix -> the prose): every row's sentence is in its section file verbatim,
its printed value is what the section prints, and its references name things that exist.
Direction two (the prose -> the matrix): every claims_registry row the national paper may
state, every product fact printed in the body, and every number the abstract prints has a row.

The renderer repairs nothing; this is where a disagreement fails. Test modules import only
from the four data modules (_common, doc_claims, tables, quantity_policy), never from each
other; the renderer is loaded as a script through _common._load_repo_script.
"""

from pkinv.assets import asset_path
import hashlib
import inspect
import json
import os
import re
import tempfile
import unittest

from pkinv.core.io import read_rows
from paper_numbers._common import ROOT, OUT, _doc_path, _load_repo_script
from paper_numbers.doc_claims import DOC_CLAIMS
from paper_numbers.quantity_policy import _quantities

REGISTRY = asset_path(ROOT, "data", "claim_matrix.csv")
CLAIMS_REGISTRY = asset_path(ROOT, "data", "claims_registry.csv")
LIMITATIONS = "12_limitations.tex"
EVIDENCE_CLASSES = ("closure-exact", "estimated-TE1", "estimated-TE2", "estimated-TE3", "estimated-TE4",
                    "spatial-S1", "spatial-S2", "spatial-S3", "spatial-S4", "parametric", "structural",
                    "external-comparison", "coverage-count", "provenance-count")
ESSD_SECTIONS = ("abstract", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "conclusions")
CONFIGURATIONS = ("REF_2023_24", "L_2023_24", "n.a.")
TN_CODES = tuple("TN%02d" % i for i in range(1, 11))
HEADLINE_FILES = ("00_abstract.tex", "01_introduction.tex", "13_conclusion.tex", "12_limitations.tex")


def _norm(text):
    return " ".join(text.split())


def _masked(text):
    """The sentence with every number blanked: repair_claims rewrites a printed value in
    place, and a claim quoted before the repair must still be found after it."""
    return re.sub(r"\d[\d.,]*", "#", _norm(text))


def _registry():
    return read_rows(REGISTRY)


def _section(name):
    with open(_doc_path("national", name), encoding="utf-8") as handle:
        return handle.read()


def _refs(row, kind):
    return [r[len(kind) + 1:] for r in row["quantity_refs"].split(";") if r.startswith(kind + ":")]


def _national_doc_claims():
    return [c for c in DOC_CLAIMS if c[1] == "national"]


def _product_fact_claims():
    """(DOC_CLAIMS label, section, fact_id) for every national claim whose getter reads a product fact."""
    out = []
    for label, doc, section, _pattern, getter, _tol in _national_doc_claims():
        try:
            source = inspect.getsource(getter)
        except (OSError, TypeError):
            continue
        for fact_id in re.findall(r"_product_fact\(\"([^\"]+)\"\)", source):
            out.append((label, section, fact_id))
    return out


class TestTheRegistryIsWellFormed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _registry()
        cls.renderer = _load_repo_script("make_claim_matrix.py")

    def test_the_registry_is_not_small_and_ids_are_unique(self):
        self.assertGreaterEqual(len(self.rows), 70)
        ids = [r["claim_id"] for r in self.rows]
        self.assertEqual(len(ids), len(set(ids)), "duplicate claim_id")
        self.assertEqual(tuple(self.rows[0].keys()), self.renderer.REGISTRY_FIELDS)

    def test_closed_vocabularies(self):
        for r in self.rows:
            self.assertIn(r["evidence_class"], EVIDENCE_CLASSES, r["claim_id"])
            self.assertIn(r["essd_section"], ESSD_SECTIONS, r["claim_id"])
            self.assertIn(r["configuration"], CONFIGURATIONS, r["claim_id"])
            self.assertTrue(r["rounding"].isdigit(), "%s: rounding must be a digit count" % r["claim_id"])
            for tn in filter(None, r["tn_refs"].split(";")):
                self.assertIn(tn, TN_CODES, r["claim_id"])
            if r["query_function"]:
                self.assertIn(r["query_function"], self.renderer.QUERY_FUNCTIONS, r["claim_id"])
                json.loads(r["query_params"] or "{}")
            self.assertTrue(r["quantity_refs"], "%s: a headline claim references at least one quantity" % r["claim_id"])
            self.assertTrue(r["source_pointer"] or r["query_function"] or _refs(r, "claim"),
                            "%s: nothing to resolve through" % r["claim_id"])

    def test_every_limitation_label_exists(self):
        labels = set(re.findall(r"\\label\{(lim:[^}]+)\}", _section(LIMITATIONS)))
        self.assertTrue(labels, "12_limitations.tex carries no lim: labels")
        for r in self.rows:
            if r["limitation_ref"]:
                self.assertIn(r["limitation_ref"], labels, r["claim_id"])

    def test_every_reference_names_something_that_exists(self):
        claim_labels = {c[0] for c in _national_doc_claims()}
        facts = {f["fact_id"] for f in read_rows(os.path.join(OUT, "pakemis_product_facts.csv"))}
        registry_ids = {c["claim_id"] for c in read_rows(CLAIMS_REGISTRY, comments=False)}
        labels = set()
        for name in sorted(os.listdir(os.path.dirname(_doc_path("national", LIMITATIONS)))):
            if name.endswith(".tex"):
                labels |= set(re.findall(r"\\label\{([^}]+)\}", _section(name)))
        problems = []
        for r in self.rows:
            for ref in r["quantity_refs"].split(";"):
                kind, _sep, name = ref.partition(":")
                if kind == "claim" and name not in claim_labels:
                    problems.append("%s: DOC_CLAIMS has no national entry %r" % (r["claim_id"], name))
                elif kind == "fact" and name not in facts:
                    problems.append("%s: no product fact %r" % (r["claim_id"], name))
                elif kind == "registry" and name not in registry_ids:
                    problems.append("%s: no claims_registry row %r" % (r["claim_id"], name))
                elif kind == "table" and name not in labels and name != "lulucf_totals":
                    problems.append("%s: no \\label{%s} in the manuscript" % (r["claim_id"], name))
                elif kind not in ("claim", "fact", "registry", "table"):
                    problems.append("%s: unknown reference kind %r" % (r["claim_id"], ref))
            if r["artefact_ref"] and r["artefact_ref"] not in labels:
                problems.append("%s: artefact_ref %s is not a label" % (r["claim_id"], r["artefact_ref"]))
        self.assertFalse(problems, "\n  " + "\n  ".join(problems))

    def test_every_sentence_is_in_its_section_verbatim(self):
        problems = []
        for r in self.rows:
            if _masked(r["claim_text"]) not in _masked(_section(r["section_file"])):
                problems.append("%s: the sentence is no longer in %s - re-quote it" % (r["claim_id"], r["section_file"]))
        self.assertFalse(problems, "\n  " + "\n  ".join(problems))


class TestEveryRowResolvesAndAgrees(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            import duckdb  # noqa: F401
        except ImportError:
            raise unittest.SkipTest("duckdb not installed; the stored queries cannot run")
        cls.renderer = _load_repo_script("make_claim_matrix.py")
        cls.resolved = cls.renderer.build(ROOT)

    def test_every_row_resolves(self):
        self.assertEqual(len(self.resolved), len(_registry()))
        for r in self.resolved:
            self.assertNotEqual(r["resolved_value"], "", r["claim_id"])
            self.assertNotEqual(r["printed_value"], "", r["claim_id"])

    def test_printed_agrees_with_resolved(self):
        """The DOC_CLAIMS rule: half an ulp at the printed precision plus the claim's registered
        tolerance. The renderer records the verdict and repairs nothing; this is where it fails."""
        stale = ["%s (%s): prints %s, the release resolves %s (tolerance %s)"
                 % (r["claim_id"], r["section_file"], r["printed_value"], r["resolved_value"], r["tolerance"])
                 for r in self.resolved if r["agrees"] != "yes"]
        self.assertFalse(stale, "headline claims disagree with the release:\n  " + "\n  ".join(stale))

    def test_the_shipped_outputs_match_a_fresh_render(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.renderer.write_all(self.resolved, tmp)
            for rel in (self.renderer.OUT_CSV, self.renderer.OUT_MD, self.renderer.OUT_TEX):
                held = asset_path(ROOT, rel)
                self.assertTrue(os.path.exists(held), "%s has not been rendered" % rel)
                with open(held, "rb") as a, open(os.path.join(tmp, rel), "rb") as b:
                    self.assertEqual(a.read(), b.read(), "%s differs from a fresh render" % rel)

    def test_query_hashes_are_current(self):
        shipped = {r["claim_id"]: r for r in read_rows(asset_path(ROOT, self.renderer.OUT_CSV))}
        for r in _registry():
            expected = (hashlib.sha256(self.renderer.canonical_params(r["query_params"]).encode("utf-8")).hexdigest()
                        if r["query_params"] else "")
            self.assertEqual(shipped[r["claim_id"]]["query_hash"], expected, r["claim_id"])
            if r["query_function"]:
                self.assertTrue(shipped[r["claim_id"]]["receipt"], "%s: a query row carries its receipt" % r["claim_id"])


class TestTheHeadlineRuleInBothDirections(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _registry()

    def test_every_claims_registry_row_allowed_for_the_national_paper_has_a_row(self):
        wanted = {c["claim_id"] for c in read_rows(CLAIMS_REGISTRY, comments=False)
                  if "national" in c["allowed_documents"].split(";")}
        have = {name for r in self.rows for name in _refs(r, "registry")}
        self.assertFalse(wanted - have, "claims_registry rows the national paper may state with no matrix row: %s"
                         % sorted(wanted - have))

    def test_every_product_fact_printed_in_the_body_has_a_row(self):
        have = {(r["section_file"], name) for r in self.rows for name in _refs(r, "fact")}
        missing = sorted("%s prints %s (%s)" % (section, fact_id, label)
                         for label, section, fact_id in _product_fact_claims()
                         if (section, fact_id) not in have)
        self.assertFalse(missing, "product facts printed in the body with no matrix row:\n  " + "\n  ".join(missing))

    def test_every_number_the_abstract_prints_has_a_row(self):
        # the printed values live in the rendered CSV (the registry carries the pattern)
        rendered = os.path.join(OUT, "pakemis_claim_matrix.csv")
        self.assertTrue(os.path.exists(rendered), "outputs/pakemis_claim_matrix.csv has not been rendered")
        printed = {r["printed_value"] for r in read_rows(rendered) if r["section_file"] == "00_abstract.tex"}
        missing = sorted({value for value, _line in _quantities("national", "00_abstract.tex")} - printed)
        self.assertFalse(missing, "the abstract prints these with no matrix row: %s" % missing)

    def test_every_bold_limitation_paragraph_is_labelled_and_claimed(self):
        text = re.sub(r"(?m)^\s*%.*$", "", _section(LIMITATIONS))
        leads = []
        for paragraph in re.split(r"\n\s*\n", text):
            paragraph = paragraph.strip()
            if not paragraph.startswith("\\textbf{"):
                continue
            depth, i = 1, len("\\textbf{")
            while depth:
                depth += (paragraph[i] == "{") - (paragraph[i] == "}")
                i += 1
            m = re.match(r"\\label\{(lim:[^}]+)\}", paragraph[i:])
            leads.append(m.group(1) if m else "")
        self.assertGreaterEqual(len(leads), 12)
        unlabelled = [lead for lead in leads if not lead]
        self.assertFalse(unlabelled, "%d bold limitation paragraphs carry no \\label{lim:...}" % len(unlabelled))
        claimed = {r["limitation_ref"] for r in self.rows}
        # every labelled paragraph is bounded by at least one row, or is one of the label-only
        # paragraphs the registry names here with the reason
        LABEL_ONLY = {"lim:soft-partitions": "its one figure (the 50.3 percent collection rate) is a derived rate no product carries as a cell",
                      "lim:air-pollutants": "a statement about which layers exist, with no number",
                      "lim:tier1": "a statement about method tier, with no number"}
        missing = [lead for lead in leads if lead not in claimed and lead not in LABEL_ONLY]
        self.assertFalse(missing, "labelled limitation paragraphs no matrix row is bounded by: %s" % missing)

    def test_every_headline_file_contributes_rows(self):
        files = {r["section_file"] for r in self.rows}
        for name in HEADLINE_FILES:
            self.assertIn(name, files)


if __name__ == "__main__":
    unittest.main()
