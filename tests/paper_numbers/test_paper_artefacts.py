"""The national manuscript's tables and figures are stored queries (v1.0.0 Wave 4, part B).

paper_national/queries/paper_artefacts.csv registers every table and figure of the paper.
For each registered row this holds: the output exists and is the fresh render of its query
(result digest AND bytes), the sidecar agrees with the registry, the params are canonical
JSON, the ESSD section is 1..10; and in the other direction every \\begin{table} and
\\includegraphics the master document inputs resolves to a registry row, and no registry row
is orphaned. One Engine is opened for the whole module (the queries take under two seconds
together; opening the release is the cost, and it is paid once).
"""

from pkinv.assets import asset_path
import csv
import hashlib
import importlib.util
import json
import os
from pkinv.paths import PAPER_NATIONAL_MAIN  # noqa: E402
import re
import sys
import tempfile
import unittest

from paper_numbers._common import ROOT, _inputs_of

PAPER = PAPER_NATIONAL_MAIN
REGISTRY = os.path.join(PAPER, "queries", "paper_artefacts.csv")
SIDECAR = os.path.join(ROOT, "outputs", "pakemis_paper_artefact_hashes.csv")
SCRIPT = os.path.join(ROOT, "scripts", "make_paper_artefacts.py")

# Registry rows that are NOT yet placed in the paper, each with the reason. The goal is an
# empty set: every row here is an artefact the ESSD restructure (part A) places, or one that
# waits on something named.
PENDING_PLACEMENT = {
    "fig_architecture": "ESSD section 1; the TikZ block is written and hashed, the figure "
                        "environment and caption belong to the restructured introduction",
    "fig_months": "ESSD section 4.2; the 108-month product figure - the current "
                  "fig:seasonality keeps its TE-class shading (not expressible through "
                  "the contract) until group_by temporal_evidence_class exists",
    "fig_spatial": "ESSD section 4.3; a map needs provider credits drawn into the figure "
                   "(OpenStreetMap contributors, ODbL; boundaries under UN naming) and is "
                   "not produced this pass",
}


def _script():
    spec = importlib.util.spec_from_file_location("make_paper_artefacts", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        h.update(handle.read())
    return h.hexdigest()


class _Shared:
    mod = None
    rows = None
    release = None
    engine = None
    sidecar = None

    @classmethod
    def load(cls):
        if cls.mod is None:
            cls.mod = _script()
            cls.rows = cls.mod.read_registry(ROOT)
            cls.release = cls.mod.Release.open(asset_path(ROOT, cls.mod.SEMANTIC), verify=True)
            cls.engine = cls.mod.Engine(cls.release)
            with open(SIDECAR, newline="", encoding="utf-8") as handle:
                cls.sidecar = {r["artefact_id"]: r for r in csv.DictReader(handle)}
        return cls


class TestEveryRegistryRowIsFresh(unittest.TestCase):
    def setUp(self):
        self.s = _Shared.load()

    def test_the_registry_is_well_formed(self):
        ids = [r["artefact_id"] for r in self.s.rows]
        self.assertEqual(len(ids), len(set(ids)), "duplicate artefact ids")
        self.assertGreaterEqual(len(ids), 15)
        for row in self.s.rows:
            params = json.loads(row["query_params"])
            self.assertEqual(self.s.mod.canonical(params), row["query_params"],
                             "%s: query_params is not canonical JSON" % row["artefact_id"])
            self.assertIn(row["kind"], self.s.mod.KINDS)
            self.assertTrue(1 <= int(row["essd_section"]) <= 10, row["artefact_id"])
            if row["kind"] == "static":
                self.assertEqual(row["query_function"], "static", row["artefact_id"])
            else:
                self.assertNotEqual(row["query_function"], "static", row["artefact_id"])
                self.assertTrue(row["renderer"], row["artefact_id"])
            if row["kind"] == "figure":
                self.assertTrue(row["image_file"], row["artefact_id"])
                self.assertEqual(os.path.basename(row["output_file"]), row["image_file"])

    def test_the_sidecar_matches_the_registry(self):
        self.assertEqual(sorted(self.s.sidecar), sorted(r["artefact_id"] for r in self.s.rows))
        for row in self.s.rows:
            side = self.s.sidecar[row["artefact_id"]]
            self.assertEqual(side["kind"], row["kind"], row["artefact_id"])
            self.assertEqual(side["query_function"], row["query_function"], row["artefact_id"])
            self.assertEqual(side["output_file"], row["output_file"], row["artefact_id"])
            self.assertEqual(side["params_sha256"], self.s.mod.sha256_text(row["query_params"]),
                             row["artefact_id"])

    def test_every_query_row_reproduces_its_result_and_its_bytes(self):
        """Re-run every stored query and compare the result digest, the receipt and the
        output bytes against the shipped artefact - the receipt is REPLAYED, never trusted."""
        mod = self.s.mod
        problems = []
        tmp = tempfile.mkdtemp(prefix="paper_artefacts_test_")
        try:
            fresh = mod.build(ROOT, tmp, self.s.engine, self.s.release, self.s.rows)
            for entry in fresh:
                side = self.s.sidecar[entry["artefact_id"]]
                for key in ("result_sha256", "receipt", "output_sha256", "image_sha256"):
                    if side[key] != entry[key]:
                        problems.append("%s: %s shipped %s, fresh %s"
                                        % (entry["artefact_id"], key, side[key][:12],
                                           entry[key][:12]))
            problems += mod.check(ROOT, tmp)
        finally:
            import shutil
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertFalse(problems, "paper artefacts are stale:\n  " + "\n  ".join(problems))

    def test_every_generated_table_carries_its_provenance_header(self):
        for row in self.s.rows:
            if row["kind"] != "table":
                continue
            path = os.path.join(PAPER, row["output_file"])
            first = open(path, encoding="utf-8").readline()
            self.assertTrue(first.startswith("% GENERATED by scripts/make_paper_artefacts.py"), path)
            self.assertIn("release=%s" % self.s.release.release_id, first)
            self.assertIn("receipt=%s" % self.s.sidecar[row["artefact_id"]]["receipt"], first)

    def test_static_rows_hash_the_source_they_stand_in_for(self):
        for row in self.s.rows:
            if row["kind"] != "static":
                continue
            params = json.loads(row["query_params"])
            if not params.get("source"):
                self.assertIn(row["artefact_id"], PENDING_PLACEMENT,
                              "%s has no source and is not declared pending" % row["artefact_id"])
                continue
            self.assertEqual(self.s.sidecar[row["artefact_id"]]["result_sha256"],
                             self.s.mod.static_hash(ROOT, row), row["artefact_id"])


class TestThePaperAndTheRegistryAgree(unittest.TestCase):
    def setUp(self):
        self.s = _Shared.load()
        self.master = os.path.join(PAPER, "paper_national.tex")
        self.sections = _inputs_of(self.master, PAPER)

    def _blocks(self):
        """(section, label, block text) for every table environment the master inputs."""
        out = []
        for path in self.sections:
            text = re.sub(r"(?m)^\s*%.*$", "", open(path, encoding="utf-8").read())
            for m in re.finditer(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", text, re.S):
                label = re.search(r"\\label\{([^}]*)\}", m.group(0))
                out.append((os.path.basename(path), label.group(1) if label else "", m.group(0)))
        return out

    def test_every_table_in_the_paper_resolves_to_a_registry_row(self):
        by_label = {json.loads(r["query_params"]).get("label"): r for r in self.s.rows
                    if r["kind"] == "static"}
        by_input = {os.path.splitext(r["output_file"])[0]: r for r in self.s.rows
                    if r["kind"] == "table"}
        # tables the paper carries that are prose, not numbers, and stay outside the registry
        PROSE_TABLES = {"tab:contract": "the 32 contract invariants - text",
                        "tab:factortrap": "four instances of the parallel-table trap - text",
                        "tab:closurekinds": "the four closures by boundary kind - text",
                        "tab:qa": "defects shipped and what prevents each - text",
                        "tab:railmatched": "the matched railway comparison - a sector "
                                           "supplement's table repeated; migrates with "
                                           "tab:benchmarks when benchmarks become a fact table"}
        unresolved = []
        for section, label, block in self._blocks():
            inputs = re.findall(r"\\input\{([^}]*)\}", block)
            if any(i in by_input for i in inputs):
                continue
            if label in by_label or label in PROSE_TABLES:
                continue
            unresolved.append("%s: %s" % (section, label or "(no label)"))
        self.assertFalse(unresolved, "tables outside the registry:\n  " + "\n  ".join(unresolved))

    def test_every_figure_in_the_paper_resolves_to_a_registry_row(self):
        images = {r["image_file"] for r in self.s.rows if r["image_file"]}
        unresolved = []
        for path in self.sections:
            text = re.sub(r"(?m)^\s*%.*$", "", open(path, encoding="utf-8").read())
            for m in re.finditer(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}", text):
                if m.group(1) not in images:
                    unresolved.append("%s: %s" % (os.path.basename(path), m.group(1)))
        self.assertFalse(unresolved, "figures outside the registry:\n  " + "\n  ".join(unresolved))

    def test_no_registry_row_is_an_orphan(self):
        text = "".join(open(p, encoding="utf-8").read() for p in self.sections)
        text = re.sub(r"(?m)^\s*%.*$", "", text)
        orphans = []
        for row in self.s.rows:
            if row["artefact_id"] in PENDING_PLACEMENT:
                continue
            params = json.loads(row["query_params"])
            if row["kind"] == "table":
                used = "\\input{%s}" % os.path.splitext(row["output_file"])[0] in text
            elif row["image_file"]:
                used = "{%s}" % row["image_file"] in text
            else:
                used = "\\label{%s}" % params.get("label") in text
            if not used:
                orphans.append(row["artefact_id"])
        self.assertFalse(orphans, "registry rows nothing in the paper uses: %s" % orphans)

    def test_the_pending_list_names_only_registry_rows(self):
        ids = {r["artefact_id"] for r in self.s.rows}
        self.assertTrue(set(PENDING_PLACEMENT) <= ids, set(PENDING_PLACEMENT) - ids)

    def test_retired_table_entries_are_gone_from_the_hand_registry(self):
        """A migrated table's TABLES / LABELLED_TABLES entry must be retired, or the old
        comparator keeps asserting a table that no longer prints those cells."""
        from paper_numbers.tables import LABELLED_TABLES, TABLES
        retired = {r["retires"] for r in self.s.rows if r["retires"]}
        self.assertTrue(retired)
        live = {(doc, label) for doc, _s, label, _fn in list(TABLES) + list(LABELLED_TABLES)}
        for label in retired:
            self.assertNotIn(("national", label), live, "%s is migrated and still registered" % label)


if __name__ == "__main__":
    unittest.main()
