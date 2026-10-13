"""The rewritten article's three documents must be built, buildable, and no older than their
own sources.

WHERE IT LIVES. The rewritten article is paper_national/versions/v3 since rc64. Until then it
was versions/v2 and this file was tests/test_v2_documents.py; v2 is now the frozen rc62
record (tests/test_frozen_versions.py), which nothing builds. The history below happened
while the article was v2 and says so.

WHY THIS TEST EXISTS, and it is two defects that hid each other. v2 is the version going to
the journal. Its technical companion answers four of the review's ten items. On 2026-10-07
its PDF was nine hours older than its own `.tex`, because `make papers` built `paper.tex` and
`submission.tex` and nothing at all built `technical_supplement.tex`. And when a target was
finally pointed at it, it did not compile: the file uses `\\SI` and `\\num` throughout and had
never loaded siunitx. Nothing compiled it, so nobody could see that it could not be compiled.

Neither defect was visible to the suite. `MANUSCRIPTS` in tests/paper_numbers/_common.py does
not list v2 - the page-overrun and shipped-PDF tests run over the main version and the nine
sector papers - and v2's PDFs are deliberately not copied into papers/pdf/, so the existing
freshness test could not have reached them even if it had known about them.

These tests check the article in place, which is where it lives, and leave its promotion into
papers/pdf/ as the separate decision the Makefile says it is.
"""
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V3 = os.path.join(ROOT, "paper_national", "versions", "v3")

# Each is a standalone copernicus document with its own PDF.
DOCUMENTS = ("paper", "submission", "technical_supplement")

# The macros these files use that only siunitx provides. A file that prints quantities
# through them and does not load it produces "Undefined control sequence" and no PDF.
SIUNITX_MACROS = re.compile(r"\\(SI|SIrange|num|numrange|ang)\b")


def _text(name, ext):
    path = os.path.join(V3, "%s.%s" % (name, ext))
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestEveryV2DocumentIsBuilt(unittest.TestCase):
    def test_each_document_has_a_pdf(self):
        for name in DOCUMENTS:
            self.assertTrue(os.path.exists(os.path.join(V3, "%s.pdf" % name)),
                            "%s.tex has no PDF. v3 is the submission version; a document "
                            "with no artefact cannot be reviewed or hashed." % name)

    def test_no_pdf_predates_its_own_source(self):
        """The defect exactly: technical_supplement.pdf was from 07:27 and its .tex from
        17:44, with every correction of the day present only in the source."""
        stale = []
        for name in DOCUMENTS:
            tex = os.path.join(V3, "%s.tex" % name)
            pdf = os.path.join(V3, "%s.pdf" % name)
            if not (os.path.exists(tex) and os.path.exists(pdf)):
                continue
            if os.path.getmtime(pdf) < os.path.getmtime(tex) - 1:
                stale.append("%s.pdf is older than %s.tex" % (name, name))
        self.assertFalse(stale,
                         "%s - run `make papers`, which now includes paper-v3-supplement"
                         % "; ".join(stale))

    def test_a_make_target_builds_each_document(self):
        """A document no target builds is a document that drifts silently, and one of
        these three did for as long as it existed."""
        with open(os.path.join(ROOT, "Makefile"), encoding="utf-8") as handle:
            makefile = handle.read()
        for name in DOCUMENTS:
            self.assertIn("%s.tex" % name, makefile,
                          "no Makefile rule mentions %s.tex, so nothing rebuilds it and "
                          "its PDF can only be stale" % name)

    def test_papers_builds_all_three(self):
        """The rules must also be REACHED by the aggregate target the release dance runs."""
        with open(os.path.join(ROOT, "Makefile"), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("papers:"):
                    targets = line.split(":", 1)[1].split()
                    break
            else:
                self.fail("the Makefile has no `papers:` target")
        for needed in ("paper-v3", "paper-v3-review", "paper-v3-supplement"):
            self.assertIn(needed, targets,
                          "`papers` does not reach %s, so a release build leaves that "
                          "document at whatever an earlier manual run produced" % needed)


class TestEveryV2DocumentCanCompile(unittest.TestCase):
    def test_a_document_using_siunitx_loads_it(self):
        """The second defect. It is checked by reading the preamble rather than by
        compiling, so it fails in two milliseconds instead of two minutes - and compiling
        is what the suite had been relying on nobody doing."""
        for name in DOCUMENTS:
            source = _text(name, "tex")
            uses = SIUNITX_MACROS.search(source)
            if not uses:
                continue
            self.assertIn("usepackage{siunitx}", source,
                          "%s.tex prints quantities through \\%s and never loads siunitx; "
                          "it cannot compile" % (name, uses.group(1)))

    def test_siunitx_precedes_the_shared_macros(self):
        """The macros call \\DeclareSIUnit, so the order is load-bearing, and the class's
        robust \\unit must be released before siunitx v3 refuses to define over it."""
        for name in DOCUMENTS:
            source = _text(name, "tex")
            if "usepackage{siunitx}" not in source:
                continue
            self.assertIn("\\let\\unit\\relax", source,
                          "%s.tex loads siunitx without releasing the class's \\unit; "
                          "siunitx v3 refuses to define over it" % name)
            if "paper_common/macros" in source:
                self.assertLess(source.index("usepackage{siunitx}"),
                                source.index("paper_common/macros"),
                                "%s.tex inputs the shared macros before siunitx, and they "
                                "call \\DeclareSIUnit" % name)

    def test_the_last_build_left_no_latex_error(self):
        """A log full of errors beside a PDF from a previous run is how a broken document
        keeps shipping. Checked only where a log exists, so a clean checkout skips."""
        for name in DOCUMENTS:
            log = os.path.join(V3, "%s.log" % name)
            if not os.path.exists(log):
                continue
            with open(log, encoding="utf-8", errors="replace") as handle:
                errors = [l.rstrip() for l in handle if l.startswith("! ")]
            self.assertFalse(errors,
                             "%s.log carries %d LaTeX error(s); first: %s"
                             % (name, len(errors), errors[0] if errors else ""))


class TestTheSupplementIsHashed(unittest.TestCase):
    """Item 1: the release record must identify what a reader downloads."""

    def test_every_v3_pdf_is_in_the_paper_hash_sidecar(self):
        from pkinv.core.io import read_rows
        path = os.path.join(ROOT, "outputs", "pakemis_paper_hashes.csv")
        if not os.path.exists(path):
            self.skipTest("the hash sidecar has not been written in this checkout")
        hashed = {r["path"] for r in read_rows(path)}
        for name in DOCUMENTS:
            rel = "paper_national/versions/v3/%s.pdf" % name
            self.assertIn(rel, hashed,
                          "%s is not hashed anywhere in the release record. PAPER_GLOBS "
                          "named the main version's filenames literally, which is how all "
                          "three of v2's PDFs came to be unhashed while the review asked "
                          "for a hash-locked version." % rel)

    def test_the_btr_inventory_year_is_stated_correctly(self):
        """The BTR's inventory is FY2020-21 by the document's own statement (recorded in
        data/shared/evidence/btr1_national_inventory.csv); the CRT reports calendar 2022. The
        introduction had attributed 2022 to the BTR, and no numeric claim can guard a year
        string, so this does."""
        text = _text("paper", "tex")
        sentence = next((l for l in text.splitlines() if "Biennial Transparency Report" in l
                         and "inventory" in l), "")
        self.assertIn("FY2020--21", sentence, "the BTR sentence does not name FY2020--21")
        self.assertNotRegex(sentence, r"Transparency Report[^.]*inventory year 2022",
                            "the introduction attributes inventory year 2022 to the BTR")

    def test_no_document_states_a_stale_release_version(self):
        """A VERSION IS A PIN TOO, and nothing was guarding it.

        The availability statement named "PakEmis 1.0.0rc59" as the candidate dataset while
        the engine had moved to rc60 - the same defect as the three stale 469.64s the 23rd
        review found, in the one sentence a reader uses to fetch the release. The quantity
        sweep cannot see it: it is not a number, so no DOC_CLAIM can carry it.

        Checked across the manuscripts AND the hand-written reproducibility doc, because the
        two generated copies (paper_common/release_cover.tex and the generated availability
        note) already follow the manifest and the hand-written ones are the ones that drift.
        """
        import re
        from pkinv import __version__ as engine
        pattern = re.compile(r"\b1\.\d+\.\d+rc\d+\b")
        offences = []
        for relative in ("paper_national/versions/v3/paper.tex",
                         "paper_national/versions/v3/technical_supplement.tex",
                         "paper_national/versions/v3/submission.tex",
                         # \input into the supplement; carried rc60 while the cover said rc61
                         "paper_national/figures/fig_ghg_grid_provenance.tex",
                         "docs/reproducibility.md",
                         "docs/qa_qc.md"):
            path = os.path.join(ROOT, relative)
            if not os.path.exists(path):
                continue
            with open(path, encoding="utf-8") as handle:
                for found in set(pattern.findall(handle.read())):
                    if found != engine:
                        offences.append("%s states %s, engine is %s"
                                        % (relative, found, engine))
        self.assertFalse(offences,
                         "a document names a release that is not this one:\n  %s"
                         % "\n  ".join(sorted(offences)))

    def test_the_version_guard_would_catch_a_stale_version(self):
        """THE POSITIVE CONTROL. The test above passes on a tree with no version strings at
        all, which is also what it looks like if the pattern stops matching."""
        import re
        from pkinv import __version__ as engine
        self.assertRegex(engine, r"^\d+\.\d+\.\d+rc\d+$",
                         "the engine version no longer has the shape the guard matches")
        self.assertTrue(re.compile(r"\b1\.\d+\.\d+rc\d+\b").findall(
            "released as PakEmis 1.0.0rc1 for review"),
            "the version pattern no longer recognises a release string")


if __name__ == "__main__":
    sys.path.insert(0, os.path.join(ROOT, "src"))
    unittest.main()

class TestTheGriddedFiguresCarryThisRelease(unittest.TestCase):
    """The figure PDFs and their provenance must name the release they were drawn from.

    WHY. At rc61 the map figure's text layer said rc60, its provenance JSON said rc59 and the
    supplement's cover said rc61 - three versions in one document set - because
    scripts/make_fig_ghg_grid.py was wired into no build phase: a version bump rebuilt the
    papers and left the figures alone. The script reads pkinv.__version__ correctly; the
    defect was that nothing ran it. These guards fail on the artefact, which is what a
    reviewer sees, not on the script.

    THE IDENTITY MOVED FROM THE PLOT TO THE FILE (rc63). It was a 6 pt line of plot text under
    each title, read here with pdftotext, on two of the seven figures; a figure that did not
    exist was skipped, so renaming one switched the guard off. Every main figure now carries
    the release in its PDF metadata (pkinv.report.manuscript_style.save), a missing figure is a
    failure, and a release string printed ON a figure is a failure too: the caption and the
    file say it once each.
    """

    @staticmethod
    def _figures():
        from pkinv.report.manuscript_style import FIGURES
        return ["%s.pdf" % stem for stem in FIGURES]

    def _run(self, tool, name, *args):
        import subprocess
        path = os.path.join(ROOT, "paper_national", "figures", name)
        self.assertTrue(os.path.exists(path),
                        "%s is not built: run `make figures-v3`" % name)
        r = subprocess.run([tool, *args, path] + (["-"] if tool == "pdftotext" else []),
                           capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, "%s failed on %s: %s" % (tool, name, r.stderr))
        return r.stdout

    def test_each_figure_pdf_names_the_engine_version_and_no_other(self):
        from pkinv import __version__ as engine
        pattern = re.compile(r"\b1\.\d+\.\d+rc\d+\b")
        self.assertEqual(len(self._figures()), 8, "the manuscript has eight main figures")
        for name in self._figures():
            info = self._run("pdfinfo", name)
            found = set(pattern.findall(info))
            self.assertEqual(found, {engine},
                             "%s carries %s in its metadata; the engine is %s. The figure was "
                             "not regenerated for this release."
                             % (name, sorted(found) or "no version", engine))
            self.assertIn("release=%s;" % engine, info, name)

    def test_no_figure_prints_a_release_string_as_plot_text(self):
        pattern = re.compile(r"\b1\.\d+\.\d+(?:rc\d+)?\b|\bREF_\d|\brelease\b")
        for name in self._figures():
            found = pattern.findall(self._run("pdftotext", name))
            self.assertEqual(found, [], "%s prints %s on the plot; it belongs in the caption "
                                        "and the file's metadata" % (name, found))

    def test_the_provenance_json_names_the_engine_version(self):
        import json
        from pkinv import __version__ as engine
        path = os.path.join(ROOT, "paper_national", "figures", "fig_ghg_grid_provenance.json")
        if not os.path.exists(path):
            self.skipTest("provenance json not built here")
        with open(path, encoding="utf-8") as handle:
            blob = json.load(handle)
        self.assertEqual(blob.get("release_version"), engine,
                         "fig_ghg_grid_provenance.json says %r, engine is %s"
                         % (blob.get("release_version"), engine))


class TestTheGeneratedSupplementTablesAreCurrent(unittest.TestCase):
    """Two supplement tables are generated from products (v3): the coal audit table from
    pakemis_power_reference_audit.csv and the livestock table from the parameter files.
    Each generator has a --check mode that rebuilds in memory and compares bytes; a table
    edited by hand or left behind by a product change fails here."""

    def _check(self, script):
        import subprocess
        import sys
        run = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", script), "--check"],
                             cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr[-1000:])

    def test_the_coal_audit_table_is_byte_identical_to_its_product(self):
        self._check("make_coal_audit_table.py")

    def test_the_livestock_table_is_byte_identical_to_its_parameters(self):
        self._check("make_livestock_factor_table.py")

    def test_the_btr_qualified_table_is_byte_identical_to_its_data(self):
        self._check("make_btr_qualified_table.py")

    def test_the_closure_table_is_byte_identical_to_its_data(self):
        self._check("make_closure_table.py")

    def test_the_five_classes_table_is_byte_identical_to_its_product(self):
        self._check("make_five_classes_table.py")

    def test_every_generated_table_is_input_by_a_manuscript(self):
        v3 = os.path.join(ROOT, "paper_national", "versions", "v3")
        ts = open(os.path.join(v3, "technical_supplement.tex"), encoding="utf-8").read()
        paper = open(os.path.join(v3, "paper.tex"), encoding="utf-8").read()
        for name in ("tab_coal_audit", "tab_livestock_factors", "tab_closure", "tab_five_classes"):
            self.assertIn("\\input{generated/%s.tex}" % name, ts, name)
        self.assertIn("\\input{generated/tab_btr_qualified.tex}", paper)

    def test_no_generated_table_carries_a_control_character(self):
        """A Python string with a single backslash before r or a put a carriage return and a
        bell into two generated tables once; LaTeX refused them, which is the only reason
        it was noticed."""
        gen = os.path.join(ROOT, "paper_national", "versions", "v3", "generated")
        for name in sorted(os.listdir(gen)):
            if name.endswith(".tex"):
                text = open(os.path.join(gen, name), encoding="utf-8").read()
                self.assertFalse(any(ord(ch) < 32 and ch not in "\n\t" for ch in text), name)
