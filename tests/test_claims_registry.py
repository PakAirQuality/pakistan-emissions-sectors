"""The machine-readable claims registry: cross-document semantics under CI.

WHY THIS EXISTS. The per-document number sweep in test_paper_numbers.py checks that
each printed quantity matches the engine, one document at a time. What it cannot see
is two documents disagreeing about the same fact: residential said 12-26 times road
exhaust for a full release while its own supplement table said 13.4-29.2, the power
paper said 33 Mt of 1A2 remained after the national paper had moved to 29, and three
papers used two different district counts with no sentence reconciling them. Every one
of those passed CI, because no guard owned the CLAIM - only its appearances.

data/claims_registry.csv owns the claims. Each row names one semantic quantity: what
it is (scope), which output resolves it (authoritative_output, via the numerator /
denominator pointers), how documents may print it (rounding), and which documents are
allowed to state it (allowed_documents). This module then enforces four directions:

  1. the row RESOLVES - the pointer arithmetic reproduces a value from the output;
  2. every ALLOWED document states that value, via the per-claim patterns below;
  3. no OTHER manuscript states a CONFLICTING value for the same pattern - the
     cross-document direction that caught nothing until this file existed;
  4. banned phrasings tied to a claim (a superseded period label, a future-work
     sentence about a product that ships) appear nowhere.

The patterns live here rather than in the CSV because they are regex mechanics, not
semantics; the CSV stays readable by machines that are not this test suite.

POINTER GRAMMAR (numerator / denominator):
  file.csv#key=value#column          one cell (keys may be comma-joined: k1=v1,k2=v2)
  PTR - PTR                          difference of two cells
  count:path.csv                     data-row count of a file (repo-relative or outputs/)
  count_unique:file.csv#column       distinct values in a column
  count_unique_excl_residual:file.csv#column   ditto, excluding values containing 'residual'
  max_abs:file.csv#column            largest absolute value in a column
Empty numerator marks a label claim (no arithmetic; patterns and bans still apply).
"""

from pkinv.assets import asset_path
import csv
import os
import re
import unittest

from paper_numbers import _common as tpn
from pkinv.core.io import read_rows

ROOT = tpn.ROOT
OUT = tpn.OUT
REGISTRY = asset_path(ROOT, "data", "claims_registry.csv")

COLUMNS = ["claim_id", "release_id", "reporting_period", "scenario", "numerator",
           "denominator", "unit", "scope", "comparator_period", "comparator_scope",
           "rounding", "authoritative_output", "allowed_documents"]

# --------------------------------------------------------------------------------------
# Per-claim appearance patterns. Each entry is a list of alternates; a document "states
# the claim" where any alternate matches, and every capture (first non-None group per
# match) must print the resolved value at the row's rounding. Claims without an entry
# are resolution-only (their appearances are already anchored one-by-one in
# test_paper_numbers DOC_CLAIMS).
# --------------------------------------------------------------------------------------
PATTERNS = {
    "residential_pm_ratio_L": [
        r"\\numrange\{\d+\}\{(\d+)\}(?: times road transport| across the two dung"
        r"| times the primary)",
        r"road-transport ratio from \\num\{(\d+)\} to \\num\{\d+\}",
    ],
    "residential_pm_ratio_S": [
        r"\\numrange\{(\d+)\}\{\d+\}(?: times road transport| across the two dung"
        r"| times the primary)",
        r"road-transport ratio from \\num\{\d+\} to \\num\{(\d+)\}",
    ],
    "district_base_census_frame": [
        r"over (\d+) census districts",
        r"covering\s*\\num\{(\d+)\} districts, with the 2023 census",
    ],
    "district_base_provincial_scope": [
        r"(?:\\num\{)?(\d+)\}? four-province districts",
        r"(\d+) administrative districts plus one residual",
        r"(\d+) district units plus one residual",
        r"(\d+) districts and one residual",
        r"(\d+) districts across the four provinces",
    ],
    "industry_1a2_remaining": [
        r"\\SI\{(\d+)\}\{\\mega\\tonne\} (?:of EDGAR's|still missing"
        r"|is specifically solid)",
    ],
    "transport_edgar_primary_ratio": [
        r"or \\num\{(0\.\d+)\} of EDGAR's fiscal-year",
        r"construction is \\num\{(0\.\d+)\} of EDGAR's",
        r"estimate is \\num\{(0\.\d+)\} of\s*it",
        r"sits at \\num\{(0\.\d+)\} of the blend",
    ],
    "transport_edgar_superseded_ratio": [
        r"led with a \\num\{(0\.\d+)\} ratio",
        r"the rc4-era \\num\{(0\.\d+)\} retained",
        r"gap between\s*\\num\{(0\.\d+)\} and \\num\{0\.\d+\} is not an engine change",
    ],
    "transport_provincial_shape_bracket": [
        # The claim's meaning moved with the re-base: it now prices the OWN-year shape's
        # drift against either neighbouring panel year, printed in the sentence that keeps
        # the number published for the next borrowing decision.
        r"against either neighbour is \\num\{([\d.]+)\} points",
    ],
    "agriculture_monthly_flat_share": [
        r"\\SI\{(\d+)\}\{\\percent\} of the sector's emissions ride a\s*flat",
    ],
    "kiln_snapshot_count": [
        r"carries (1?1\{,\}\d+)\s*kiln locations",
    ],
}

# Phrasings a claim bans everywhere - the stale sentence the claim replaced, kept as a
# tripwire so it cannot be pasted back. Scoped to (documents, pattern, why).
FORBID = {
    "transport_reporting_period": (
        ("transport", "transport-supplement"),
        r"FY2021--22[^.]{0,60}the sector's reference (?:year|period)"
        r"|the sector's reference (?:year|period)[^.]{0,60}FY2021--22"
        r"|machinery for 2022 on",
        "the sector reports FY2023-24; FY2021-22 may appear only as named history "
        "(brackets, superseded constructions), never as the reference period"),
    "agriculture_monthly_flat_share": (
        ("agriculture",),
        r"monthly\s*temporal profiles would make the surfaces usable",
        "the monthly layer ships; calling it future work was the defect"),
    "transport_edgar_superseded_ratio": (
        ("transport", "transport-supplement", "national", "national-supplement"),
        r"is \\num\{0\.70?\} of EDGAR|\\num\{0\.70?\} of EDGAR's fiscal-year",
        "0.70 may be narrated as superseded history but never printed as the "
        "current EDGAR comparison"),
}


def _registry():
    return read_rows(REGISTRY, comments=False)


def _read_rows(path):
    return read_rows(path, comments=False)


def _parse_matchers(keys):
    """k1=v1,k2=v2 - where a VALUE may itself contain commas. A bare
    keys.split(",") shifted any pointer whose row-key value carried a comma
    (e.g. a Sensitivity row named "...(NE, screened)"); a comma-segment without
    an equals sign therefore belongs to the previous value, never to a new key."""
    matchers = []
    for part in keys.split(","):
        if "=" in part:
            matchers.append(list(part.split("=", 1)))
        elif matchers:
            matchers[-1][1] += "," + part
        else:
            raise ValueError("pointer key segment before any k=v pair: %r" % keys)
    return matchers


def _resolve_pointer(ptr):
    """One cell: file.csv#k1=v1,k2=v2#column. Files resolve under outputs/."""
    fname, keys, col = ptr.split("#")
    matchers = _parse_matchers(keys)
    for r in _read_rows(os.path.join(OUT, fname)):
        if all(r[k] == v for k, v in matchers):
            return float(r[col])
    raise KeyError(ptr)


def _resolve(expr):
    """The full numerator/denominator grammar from the module docstring."""
    expr = expr.strip()
    if expr.startswith("count:"):
        path = expr[len("count:"):]
        full = path if os.path.isabs(path) else asset_path(ROOT, path)
        if not os.path.exists(full):
            full = os.path.join(OUT, path)
        return float(len(_read_rows(full)))
    if expr.startswith("count_unique_excl_residual:"):
        fname, col = expr[len("count_unique_excl_residual:"):].split("#")
        return float(len({r[col] for r in _read_rows(os.path.join(OUT, fname))
                          if "residual" not in r[col]}))
    if expr.startswith("count_unique:"):
        fname, col = expr[len("count_unique:"):].split("#")
        return float(len({r[col] for r in _read_rows(os.path.join(OUT, fname))}))
    if expr.startswith("max_abs:"):
        fname, col = expr[len("max_abs:"):].split("#")
        return max(abs(float(r[col])) for r in _read_rows(os.path.join(OUT, fname)))
    if " - " in expr:
        a, b = expr.split(" - ", 1)
        return _resolve_pointer(a) - _resolve_pointer(b)
    return _resolve_pointer(expr)


def _resolved_value(row):
    num = _resolve(row["numerator"])
    if row["denominator"].strip():
        return num / _resolve(row["denominator"])
    return num


def _doc_text(doc):
    """Every source line of one manuscript, concatenated raw (patterns use \\s* to
    cross line breaks, mirroring the DOC_CLAIMS convention)."""
    if doc == "references.bib":
        with open(os.path.join(ROOT, "paper_common", "references.bib"),
                  encoding="utf-8") as f:
            return f.read()
    for name, root, _cls, mainname in tpn.MANUSCRIPTS:
        if name == doc:
            main = tpn._main_tex(root, mainname)
            texts = [main] + tpn._inputs_of(main, root)
            return "\n".join(open(p, encoding="utf-8").read()
                             for p in texts if os.path.exists(p))
    raise KeyError("unknown document %r" % doc)


def _captures(text, alternates):
    """Every value any alternate captures in text: first non-None group per match."""
    found = []
    for pat in alternates:
        for m in re.finditer(pat, text):
            group = next((g for g in m.groups() if g is not None), None)
            if group is not None:
                found.append(group)
    return found


def _as_float(captured):
    """Printed capture -> float, tolerating LaTeX thousand separators like 11{,}272."""
    return float(re.sub(r"[^\d.]", "", captured))


class TestClaimsRegistry(unittest.TestCase):
    def test_schema_is_exactly_the_reviewer_columns(self):
        with open(REGISTRY, newline="", encoding="utf-8") as f:
            header = next(csv.reader(f))
        self.assertEqual(header, COLUMNS)
        rows = _registry()
        ids = [r["claim_id"] for r in rows]
        self.assertEqual(len(ids), len(set(ids)), "duplicate claim_id")
        for r in rows:
            for col in ("claim_id", "release_id", "scope", "authoritative_output",
                        "allowed_documents"):
                self.assertTrue(r[col].strip(),
                                "%s: empty %s" % (r["claim_id"], col))
            if r["numerator"].strip():
                self.assertTrue(r["rounding"].strip(),
                                "%s: numeric claim with no rounding" % r["claim_id"])

    def test_release_id_is_the_current_version(self):
        """A registry describing a previous release is a registry describing nothing:
        the rows assert what THIS release's documents say."""
        import pkinv
        for r in _registry():
            self.assertEqual(r["release_id"], pkinv.__version__, r["claim_id"])

    def test_every_authoritative_output_exists(self):
        for r in _registry():
            path = r["authoritative_output"]
            self.assertTrue(os.path.exists(asset_path(ROOT, path)),
                            "%s: %s missing" % (r["claim_id"], path))

    def test_every_numeric_claim_resolves(self):
        for r in _registry():
            if not r["numerator"].strip():
                continue
            value = _resolved_value(r)
            self.assertTrue(value == value and abs(value) < 1e12, r["claim_id"])

    def test_every_allowed_document_states_the_value(self):
        """Direction 2: each allowed document must actually print the resolved value.
        A claim whose pattern matches nothing in an allowed document is a lost anchor,
        exactly like a DOC_CLAIMS regex going dark."""
        problems = []
        for r in _registry():
            if r["claim_id"] not in PATTERNS or not r["numerator"].strip():
                continue
            expected = round(_resolved_value(r), int(r["rounding"]))
            half_ulp = 0.5 * 10 ** -int(r["rounding"]) + 1e-9
            for doc in r["allowed_documents"].split(";"):
                caught = _captures(_doc_text(doc), PATTERNS[r["claim_id"]])
                if not caught:
                    problems.append("%s: no appearance in allowed document %s"
                                    % (r["claim_id"], doc))
                    continue
                for c in caught:
                    if abs(_as_float(c) - expected) > half_ulp:
                        problems.append("%s: %s prints %s, engine resolves %s"
                                        % (r["claim_id"], doc, c, expected))
        self.assertFalse(problems, "\n  " + "\n  ".join(problems))

    def test_no_other_manuscript_states_a_conflicting_value(self):
        """Direction 3, the one that caught nothing until now: a manuscript OUTSIDE
        allowed_documents that matches a claim's pattern must agree with the engine.
        (Agreement outside the allowed list is tolerated - the list is about semantic
        ownership, and the conflict direction is what ships wrong numbers.)"""
        problems = []
        all_docs = [name for name, _root, _cls, _main in tpn.MANUSCRIPTS]
        for r in _registry():
            if r["claim_id"] not in PATTERNS or not r["numerator"].strip():
                continue
            expected = round(_resolved_value(r), int(r["rounding"]))
            half_ulp = 0.5 * 10 ** -int(r["rounding"]) + 1e-9
            allowed = set(r["allowed_documents"].split(";"))
            for doc in all_docs:
                if doc in allowed:
                    continue
                for c in _captures(_doc_text(doc), PATTERNS[r["claim_id"]]):
                    if abs(_as_float(c) - expected) > half_ulp:
                        problems.append("%s: %s (not an allowed document) prints %s "
                                        "against the engine's %s"
                                        % (r["claim_id"], doc, c, expected))
        self.assertFalse(problems, "\n  " + "\n  ".join(problems))

    def test_forbidden_phrasings_are_dead(self):
        problems = []
        registry_ids = {r["claim_id"] for r in _registry()}
        for claim_id, (docs, pattern, why) in FORBID.items():
            self.assertIn(claim_id, registry_ids,
                          "FORBID entry for a claim the registry does not carry")
            for doc in docs:
                for m in re.finditer(pattern, _doc_text(doc)):
                    problems.append("%s in %s: %r -- %s"
                                    % (claim_id, doc, m.group(0)[:70], why))
        self.assertFalse(problems, "\n  " + "\n  ".join(problems))

    def test_every_pattern_belongs_to_a_registry_row(self):
        """A pattern with no row is a guard with no owner; a patterned row whose
        allowed documents all lost the phrase is caught above, but a PATTERNS key
        orphaned by a registry edit would silently guard nothing."""
        registry_ids = {r["claim_id"] for r in _registry()}
        for claim_id in PATTERNS:
            self.assertIn(claim_id, registry_ids, claim_id)



class TestPointerGrammarSurvivesCommaValues(unittest.TestCase):
    """Proven red against the bare keys.split(",") this replaced: a row-key
    value containing a comma silently became a phantom key and the pointer
    raised KeyError on a row that existed."""

    def test_comma_bearing_value_parses_as_one_matcher(self):
        self.assertEqual(_parse_matchers("category=Sensitivity: kiln (NE, screened),gas=CO2"),
                         [["category", "Sensitivity: kiln (NE, screened)"],
                          ["gas", "CO2"]])

    def test_plain_pairs_are_unchanged(self):
        self.assertEqual(_parse_matchers("a=1,b=2"), [["a", "1"], ["b", "2"]])

    def test_a_leading_bare_segment_is_an_error(self):
        with self.assertRaises(ValueError):
            _parse_matchers("no-equals-here,a=1")


if __name__ == "__main__":
    unittest.main()
