"""The main figures are drawn at their printed size, and say what their tables say.

WHY THIS FILE EXISTS. Two size failures reached a reviewer and no test could see either. A
single-column figure was included at \\columnwidth, which is the whole text block in the review
layout, and its labels were set at 16.9 pt. A tall figure was shrunk by a height cap, by a
different factor in each layout, to 4.6 pt in one and 5.2 pt in the other. Both were invisible in
the plotting script, which was correct, and in LaTeX, which compiled.

So the checks are made on the artefacts a reader holds: the figure PDFs (one font, embedded,
nothing under the floor, under the journal's size limit) and the two compiled logs (every figure
placed at the size it was drawn). The second half holds each figure's companion table to the
identities the caption states.
"""
import csv
import json
import os
import re
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.report import manuscript_style as S                          # noqa: E402
from pkinv.core.reporting_window import CORE_PERIOD_IDS

FIGDIR = os.path.join(ROOT, "paper_national", "figures")
V3 = os.path.join(ROOT, "paper_national", "versions", "v3")
PT_PER_INCH = 72.0
JOURNAL_PDF_LIMIT = 2 * 1024 * 1024               # ESSD: a PDF figure is at most 2 MB


def _tool(tool, *args):
    r = subprocess.run([tool, *args], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError("%s %s failed: %s" % (tool, " ".join(args), r.stderr))
    return r.stdout


def _path(stem):
    path = os.path.join(FIGDIR, stem + ".pdf")
    if not os.path.exists(path):
        raise AssertionError("%s.pdf is not built: run `make figures-v3`" % stem)
    return path


def _rows(name):
    with open(os.path.join(FIGDIR, name), newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class TestEveryFigureIsDrawnAtItsPrintedSize(unittest.TestCase):

    def test_the_page_is_one_of_the_two_widths_and_fits_the_review_page(self):
        for stem in S.FIGURES:
            m = re.search(r"Page size:\s+([\d.]+) x ([\d.]+) pts", _tool("pdfinfo", _path(stem)))
            width, height = float(m.group(1)) / PT_PER_INCH, float(m.group(2)) / PT_PER_INCH
            want = S.COLUMN_WIDTH if stem in S.NARROW else S.FULL_WIDTH
            self.assertAlmostEqual(width, want, places=2, msg=stem)
            self.assertLessEqual(height, S.MAX_HEIGHT + 1e-6, stem)

    def test_one_font_embedded_and_nothing_else(self):
        for stem in S.FIGURES:
            lines = _tool("pdffonts", _path(stem)).splitlines()[2:]
            self.assertEqual(len(lines), 1, "%s embeds %d fonts; the journal counts each weight "
                                            "and each maths face as one: %s" % (stem, len(lines), lines))
            self.assertIn("DejaVuSans", lines[0], stem)
            fields = lines[0].split()
            emb = fields[-5]                                # emb sub uni object ID
            self.assertEqual(emb, "yes", "%s: the font is not embedded" % stem)

    def test_no_text_is_smaller_than_the_floor(self):
        """Measured in the PDF, not read from the script: a size set in one place and scaled in
        another is how the 4.6 pt legend was made. The size is the operand of every text-font
        operator in the page's content stream, so rotated labels are read like any other."""
        import zlib
        for stem in S.FIGURES:
            with open(_path(stem), "rb") as handle:
                raw = handle.read()
            sizes = []
            for m in re.finditer(rb"stream\r?\n(.*?)\r?\nendstream", raw, re.S):
                try:
                    content = zlib.decompress(m.group(1))
                except zlib.error:
                    continue
                sizes += [float(x) for x in re.findall(rb"/F\d+ ([\d.]+) Tf", content)]
            self.assertGreater(len(sizes), 5, "%s has no text operators; text must stay text" % stem)
            self.assertGreaterEqual(min(sizes), S.SIZE_FLOOR,
                                    "%s sets text at %.2f pt, under the %.1f pt floor"
                                    % (stem, min(sizes), S.SIZE_FLOOR))
            self.assertLessEqual(max(sizes), S.SIZE_HEAD, stem)

    def test_each_file_is_inside_the_journal_limit(self):
        for stem in S.FIGURES:
            self.assertLess(os.path.getsize(_path(stem)), JOURNAL_PDF_LIMIT, stem)

    def test_both_layouts_place_every_figure_at_the_size_it_was_drawn(self):
        """The two-column paper and the one-column review manuscript share one set of figure
        blocks. Neither may rescale a figure, in either direction."""
        pattern = re.compile(r"<\.\./\.\./figures/(f\d{2}_[a-z0-9_]+)\.pdf, id=\d+, ([\d.]+)pt x "
                             r"([\d.]+)pt>.*?Requested size: ([\d.]+)pt x ([\d.]+)pt")
        for doc in ("paper_national", "submission"):
            log = os.path.join(V3, doc + ".log")
            self.assertTrue(os.path.exists(log), "%s.log is absent: run `make paper-v3 paper-v3-review`" % doc)
            with open(log, encoding="utf-8", errors="ignore") as handle:
                text = handle.read().replace("\n", "")
            placed = {m.group(1): float(m.group(4)) / float(m.group(2)) for m in pattern.finditer(text)}
            self.assertEqual(sorted(placed), sorted(S.FIGURES),
                             "%s.pdf does not include exactly the declared main figures" % doc)
            for stem, scale in placed.items():
                self.assertAlmostEqual(scale, 1.0, places=2,
                                       msg="%s is placed at %.3f of its drawn size in %s.pdf"
                                           % (stem, scale, doc))


class TestTheManuscriptCitesEveryFigureInOrder(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(V3, "paper.tex"), encoding="utf-8") as handle:
            cls.tex = handle.read()

    def test_declared_figures_each_with_one_label_and_one_file(self):
        files = re.findall(r"\\includegraphics\[width=([^\]]+)\]\{\.\./\.\./figures/([a-z0-9_]+)\.pdf\}", self.tex)
        self.assertEqual([f for _, f in files], list(S.FIGURES))
        for width, stem in files:
            # a fixed width: \columnwidth is the text block in the review layout
            self.assertEqual(width, "85mm" if stem in S.NARROW else "\\textwidth", stem)
        self.assertNotIn("keepaspectratio", self.tex, "a height cap rescales a figure per layout")

    def test_every_figure_label_is_cited_in_the_text_before_or_at_its_number(self):
        labels = re.findall(r"\\label\{(fig:[a-z_]+)\}", self.tex)
        self.assertEqual(len(labels), len(S.FIGURES))
        body = re.sub(r"\\caption\{.*?\}\n\\label", "", self.tex, flags=re.S)
        first = {label: body.find("\\ref{%s}" % label) for label in labels}
        for label, at in first.items():
            self.assertGreaterEqual(at, 0, "%s is never cited in the text" % label)
        self.assertEqual(sorted(labels, key=first.get), labels,
                         "figures are not numbered in the order the text first cites them")

    def test_the_compiled_documents_have_no_unresolved_reference(self):
        for doc in ("paper", "submission", "technical_supplement"):
            text = _tool("pdftotext", os.path.join(V3, doc + ".pdf"), "-")
            self.assertNotIn("??", text, "%s.pdf has an unresolved reference" % doc)


class TestTheCompanionTablesHoldTheCaptionsIdentities(unittest.TestCase):

    def test_evidence_shares_are_a_partition_of_each_gas_year(self):
        classes = [label for _, label, _, _ in S.EVIDENCE]
        rows = _rows("fig_ghg_grid_evidence.csv")
        self.assertEqual({(r["period_id"], r["gas"]) for r in rows},
                         {(period, gas) for period in CORE_PERIOD_IDS
                          for gas in ("CO2", "CH4", "N2O")})
        self.assertEqual(len(rows), 3 * len(CORE_PERIOD_IDS))
        for r in rows:
            self.assertAlmostEqual(sum(float(r[c]) for c in classes), 100.0, places=6,
                                   msg="%s %s" % (r["gas"], r["period_id"]))
            self.assertIn("province-retained mass included", r["denominator"])

    def test_surface_shares_are_a_partition_and_name_no_wrong_vintage(self):
        groups = [label for _, label, _ in S.PROXY]
        for r in _rows("fig_ghg_grid_proxy.csv"):
            self.assertAlmostEqual(sum(float(r[g]) for g in groups), 100.0, places=6)
        surfaces = {(r["surface"], r["surface_vintage"]) for r in _rows("fig_ghg_grid_proxy_surfaces.csv")}
        vintage = dict(surfaces)
        # the two labels that were wrong in the released table until rc63
        self.assertEqual(vintage["cropland"], "ESA WorldCover 2021")
        self.assertEqual(vintage["spam_rice"], "MapSPAM 2020")
        self.assertNotIn("SPAM 2020", {v for _, v in surfaces})

    def test_placed_plus_unallocated_is_the_national_mass_for_every_gas_and_year(self):
        with open(os.path.join(FIGDIR, "fig_ghg_grid_provenance.json"), encoding="utf-8") as handle:
            blob = json.load(handle)
        self.assertEqual(sorted(blob["figures"]), ["f04_gas_maps.pdf", "f05_spatial_evidence.pdf",
                                                   "f06_proxy_concentration.pdf"])
        checked = 0
        for gas, rows in blob["closure_detail"].items():
            for r in rows:
                # float32 cells summed in float64: parts per million, not a disagreement
                self.assertLess(abs(r["residual_ppm_of_ledger"]), 0.5, "%s %s" % (gas, r["period_id"]))
                checked += 1
        self.assertEqual(checked, 3 * len(CORE_PERIOD_IDS))
        self.assertEqual({r["period_id"] for values in blob["closure_detail"].values()
                          for r in values}, set(CORE_PERIOD_IDS))
        for gas in ("CO2", "CH4", "N2O"):
            facts = blob["maps"][gas]
            self.assertAlmostEqual(facts["placed_Gg"] + blob["unallocated_not_on_map"][gas.lower() + "_Gg"],
                                   blob["national_ledger_Gg"][gas],
                                   delta=1e-6 * blob["national_ledger_Gg"][gas])

    def test_the_map_states_match_the_cells_it_draws(self):
        """A zero is a state of a valid cell, not a small number and not an absence."""
        with open(os.path.join(FIGDIR, "fig_ghg_grid_provenance.json"), encoding="utf-8") as handle:
            blob = json.load(handle)
        cells = _rows("fig_ghg_grid_cells_fy2023_24.csv")
        self.assertEqual(len(cells), blob["in_country_cells"])
        for gas, column in (("CO2", "co2_Gg"), ("CH4", "ch4_Gg"), ("N2O", "n2o_Gg")):
            values = [float(r[column]) for r in cells]
            facts = blob["maps"][gas]
            low, high = facts["log_limits_Gg"]
            self.assertEqual(sum(1 for v in values if v == 0.0), facts["zero_cells"], gas)
            self.assertEqual(sum(1 for v in values if 0.0 < v < low), facts["cells_below_lower_limit"], gas)
            self.assertLessEqual(max(values), high, "%s: a cell is above the top of the colour scale" % gas)
            self.assertTrue(all(v >= 0.0 for v in values), gas)

    def test_half_mass_counts_are_read_off_the_whole_ranked_population(self):
        with open(os.path.join(FIGDIR, "fig_ghg_grid_provenance.json"), encoding="utf-8") as handle:
            blob = json.load(handle)
        cells = _rows("fig_ghg_grid_cells_fy2023_24.csv")
        for gas, column in (("CO2", "co2_Gg"), ("CH4", "ch4_Gg"), ("N2O", "n2o_Gg")):
            values = sorted((float(r[column]) for r in cells), reverse=True)
            total, running, count = sum(values), 0.0, 0
            for v in values:
                running += v
                count += 1
                if running >= 0.5 * total:
                    break
            self.assertEqual(count, blob["half_mass_cells"][gas], gas)
        table = {(r["gas"], r["mass_fraction"]): int(r["cells"]) for r in _rows("fig_ghg_grid_concentration.csv")}
        # every positive cell is needed to reach the whole: the float32 running sum stopped short
        self.assertEqual(table[("CO2", "1.0")], blob["in_country_cells"])
        self.assertEqual(table[("CH4", "1.0")], blob["in_country_cells"])


class TestEveryPlottedValueIsTheProductsValue(unittest.TestCase):

    def test_the_independent_re_read_finds_no_disagreement(self):
        """scripts/verify_manuscript_figures.py opens the released products itself, without
        going through either plot-table builder, and compares what it reads with what is drawn."""
        env = dict(os.environ, PYTHONPATH=os.path.join(ROOT, "src"), PKINV_ROOT=ROOT)
        r = subprocess.run([sys.executable, "-B", os.path.join(ROOT, "scripts", "verify_manuscript_figures.py")],
                           capture_output=True, text=True, cwd=ROOT, env=env)
        self.assertEqual(r.returncode, 0, r.stdout[-1500:] + r.stderr[-1500:])
        self.assertRegex(r.stdout, r"\d{3,} values checked against their products; 0 disagree")


if __name__ == "__main__":
    unittest.main()
