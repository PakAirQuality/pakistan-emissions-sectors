"""Sector editorial structure, layout and bibliography invariants.

Split from tests/test_paper_numbers.py in rc35; the shim of that name
re-exports the data and helpers. Test modules import only from the four data
modules (_common, doc_claims, tables, quantity_policy), never from each other.
"""

from pkinv.assets import asset_path
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
from pkinv.paths import PAPER_NATIONAL_MAIN, PAPER_NATIONAL_SECTIONS  # noqa: E402
from pkinv.core.io import read_rows
from paper_numbers._common import (
    DOCS,
    MANUSCRIPTS,
    ROOT,
    _data_rows,
    _doc_path,
    _first_where,
    _inputs_of,
    _main_tex)
from paper_numbers.doc_claims import (
    _bench)


class TestFugitivesEditorialStructure(unittest.TestCase):
    def _read(self, name):
        with open(_doc_path("fugitives", name), encoding="utf-8") as handle:
            return handle.read()

    def test_the_activity_table_post_meter_cell_matches_the_register(self):
        """The eighth review found 25,209.74 in tab:activity - a value that exists
        nowhere in data/, src/ or outputs/ (the authoritative registered activity is
        25210.98364336, and every OTHER cell of the table matches its register row
        exactly). The cell survived because it carries an inline unit, which the
        printed-quantity sweep classifies as text, and tab:activity is not in
        TABLES. It gets its own comma-aware anchor instead."""
        text = self._read("03_study_area_and_data.tex")
        m = re.search(r"Post-meter industry/power & non-residential gas & "
                      r"([\d,]+\.\d+) million m\$\^3\$", text)
        self.assertIsNotNone(m, "tab:activity post-meter row lost its anchor")
        printed = float(m.group(1).replace(",", ""))
        actual = float(_first_where("fugitives_post_meter_end_use_2024.csv",
                                    "registered_activity_million_m3", include_in_ipcc_post_meter="yes"))
        self.assertAlmostEqual(printed, actual, delta=0.005)

    def test_the_class_sum_and_registered_activity_are_named_apart(self):
        """The same review caught the data-section sentence equating the class-sum
        conversion (25211.03) with the registered activity (25210.98) two lines
        before quoting their 0.042 difference. Both quantities are now named as
        themselves, and both anchor to the audit columns that publish them."""
        text = self._read("03_study_area_and_data.tex")
        m = re.search(r"converts to \\num\{([\d.]+)\} million", text)
        self.assertIsNotNone(m, "class-sum conversion lost its anchor")
        self.assertAlmostEqual(
            float(m.group(1)),
            float(_first_where("fugitives_post_meter_end_use_2024.csv",
                               "included_activity_control_million_m3",
                               include_in_ipcc_post_meter="yes")), delta=0.005)
        m = re.search(r"leak factor rides is \\num\{([\d.]+)\} million", text)
        self.assertIsNotNone(m, "registered-activity sentence lost its anchor")
        self.assertAlmostEqual(
            float(m.group(1)),
            float(_first_where("fugitives_post_meter_end_use_2024.csv",
                               "registered_activity_million_m3",
                               include_in_ipcc_post_meter="yes")), delta=0.005)

    def test_scientific_sequence_and_positive_results_headings(self):
        with open(os.path.join(ROOT, "papers", "fugitives", "paper.tex"),
                  encoding="utf-8") as handle:
            paper = handle.read()
        expected_inputs = [
            r"\input{sections/04_methods}",
            r"\input{sections/05_validation}",
            r"\input{sections/05b_external_evaluation}",
            r"\input{sections/06_results}",
        ]
        positions = [paper.index(item) for item in expected_inputs]
        self.assertEqual(positions, sorted(positions))

        results = self._read("06_results.tex")
        for heading in (
            "Segment completion matters more than factor revision",
            "Distribution and post-meter assumptions determine the range",
            "Network growth offsets declining upstream activity",
            "Physical balances and official reporting constrain magnitude",
            "Production locates sources but weakly predicts observed intensity",
        ):
            self.assertIn(heading, results)

    def test_repeated_defensive_headings_removed(self):
        discussion = self._read("07_discussion.tex")
        for old_heading in (
            "conditional, not central",
            "decomposed, not merely asserted",
            "not the whole inventory",
        ):
            self.assertNotIn(old_heading, discussion)

    def test_uncertainty_and_audit_detail_live_in_supplement(self):
        uncertainty = self._read("05_validation.tex")
        results = self._read("06_results.tex")
        supplement_path = os.path.join(ROOT, "papers", "fugitives", "supplement.tex")
        with open(supplement_path, encoding="utf-8") as handle:
            supplement = handle.read()
        self.assertIn("No probability", uncertainty)
        self.assertNotIn("No probability", results)
        self.assertIn("m(u)=", supplement)
        self.assertIn("Official-inventory and computational audit", supplement)

    def test_abstract_is_compact(self):
        abstract = self._read("00_abstract.tex")
        plain = re.sub(r"\\[A-Za-z]+(?:\[[^]]*\])?", " ", abstract)
        words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", plain)
        self.assertGreaterEqual(len(words), 180)
        self.assertLessEqual(len(words), 230)


class TestTableLayout(unittest.TestCase):
    """Wide tables must be full-width floats, or they overrun the column and print on top of
    the prose beside them.

    No value check can see this: the numbers are right, the page is unreadable. Two tables
    shipped that way, both widened by edits that were themselves correct. The rule is crude on
    purpose -- it flags for review rather than trying to model LaTeX's layout.

    IT IS NO LONGER THE AUTHORITY, and should not be treated as one. A column count is a proxy
    for width, and the proxy missed the worst case in the repository: tab:sectors WAS a
    full-width table*, satisfied this rule, and overran by 104.5pt. What the page actually did
    is in the compiler's log, and test_nothing_overruns_the_page reads it. This survives as a
    design-time check - it catches a table that will not fit before anyone compiles it."""

    MAX_COLS_IN_SINGLE_COLUMN = 5

    # Boxes wider than this are visible on the page. Small overruns are ordinary TeX
    # justification noise and flagging them would make the check unusable.
    # Zero, with a hair of slack for engine differences: the manuscripts compile with
    # latexmk locally and tectonic in CI, and a sub-half-point disagreement between them is
    # not a layout defect. Every document currently reports NO overfull box at all, so a
    # 5pt allowance -- which is what this was -- would have gone on permitting the defects
    # it exists to catch. It permitted four of them.
    MAX_OVERFULL_PT = 0.5

    def test_nothing_overruns_the_page(self):
        """Read from the LaTeX log, which is an output nobody was reading.

        The heuristic below counts columns and demands table* for wide ones. It cannot see
        the actual defect: tab:sectors WAS a table*, was full-width, and still overran by
        104.5pt, printing its share and uncertainty columns off the edge of the page. Nothing
        in the suite could tell, because every test read the .tex source and the source was
        correct - the numbers were right and the page was unreadable.

        The compiler already reports it. This reads what it reported.
        """
        offenders = set()
        seen = set()
        roots = set()
        for _doc, root, _cls, mainname in MANUSCRIPTS:
            roots.add(root)
            for log in sorted(glob.glob(os.path.join(root, "*.log"))):
                if log in seen:                      # two documents can share a directory
                    continue
                seen.add(log)
                with open(log, encoding="utf-8", errors="replace") as handle:
                    text = handle.read()
                # pdftex hard-wraps the log at 79 columns, mid-token and without a hyphen, so
                # a path or a message can be split across lines. Un-wrapping first is what
                # lets one regex see either. (It also glues "lines" to its numbers, which is
                # why the pattern below allows no space there.)
                text = text.replace("\n", "")
                # The log reports line numbers without saying which file they are in; it
                # names the file when it opens it, as "(./sections/06_results.tex". Track
                # that, or every report says "lines 20--20" of nothing in particular.
                # The MOST RECENTLY OPENED .tex, not a balanced stack: the log's parentheses
                # are not reliably balanced (font and box traces emit their own), and a stray
                # close would pop past the file and report "?" for everything after it.
                current = "?"
                # TWO MESSAGE FORMS, and this read one. Text sets "in paragraph at lines
                # A--B"; DISPLAY MATH sets "detected at line N". An equation 4.6pt too wide
                # for its column sat in the waste report unreported, because the guard could
                # not see the sentence the compiler used to describe it.
                for token in re.finditer(
                        r"\((\.?\/?[^\s()]+\.tex)|Overfull \\hbox \(([\d.]+)pt too wide\)"
                        r"(?: in paragraph at lines\s*(\d+--\d+)| detected at line\s*(\d+))",
                        text):
                    opened, width, lines, at_line = token.groups()
                    lines = lines or at_line
                    if opened:
                        # Package and font files are opened constantly and are never where
                        # the defect is; letting one become "current" attributes an overrun
                        # in the manuscript to tikzlibrarybackgrounds.code.tex.
                        if "texmf" in opened or "texlive" in opened:
                            continue
                        current = opened
                    elif float(width) > self.MAX_OVERFULL_PT:
                        offenders.add("%s %s lines %s: %.1fpt over"
                                      % (os.path.relpath(os.path.dirname(log), ROOT),
                                         current, lines, float(width)))
        offenders = sorted(offenders)
        # THE POSITIVE CONTROL, and it was missing. This test reads the compiler's logs,
        # which are build artefacts: `rm paper_national/*.log` leaves `offenders` empty and
        # the test GREEN, so a routine clean of a paper directory silently disarms the one
        # guard that can see a table running off the page. Demonstrated, not supposed - the
        # logs were deleted and this test still passed. Every manuscript root must now have
        # contributed at least one log, which fails loudly and says to run `make papers`.
        unread = sorted(r for r in roots
                        if not glob.glob(os.path.join(r, "*.log")))
        self.assertFalse(
            unread,
            "no LaTeX log in %s, so this guard read nothing and would have passed on an "
            "unbuilt tree. Run `make papers` before the suite - the overrun it detects is "
            "invisible in the .tex source."
            % ", ".join(os.path.relpath(r, ROOT) for r in unread))
        self.assertFalse(
            offenders,
            "content is printing outside the page. Narrow the table, widen the float, or "
            "wrap the column:\n  " + "\n  ".join(offenders))

    def test_wide_tables_are_full_width_floats(self):
        problems = []
        # Only TWO-COLUMN documents can have a table overrun its column. The sector notes
        # compile single-column (3p), where a six-column table is perfectly legible, so
        # applying this rule to them would flag correct layout as broken.
        #
        # The file set comes from what each document actually \inputs, not from a glob
        # over sections/: transport's supplement lives in the same directory as its
        # paper and compiles single-column, so a glob would judge the supplement's
        # tables by the two-column rule and demand table* where table is correct.
        paths = []
        for doc, root, cls, mainname in MANUSCRIPTS:
            if cls != "5p":
                continue
            paths += _inputs_of(_main_tex(root, mainname), root)
        for path in paths:
            text = open(path, encoding="utf-8").read()
            # the argument contains nested @{} groups, so a lazy [^}]* stops at the first brace
            # and silently counts zero columns -- which is how this guard first passed vacuously
            for m in re.finditer(r"\\begin\{tabular\}\{((?:[^{}]|\{[^{}]*\})*)\}", text):
                spec = re.sub(r"@\{[^}]*\}", "", m.group(1))
                # p/m/b take a width argument, and \linewidth contains an "l". Counting
                # characters without stripping the argument makes p{0.25\linewidth} two
                # columns, which turned every table narrowed to fit into a false positive.
                spec = re.sub(r"[pmb]\{[^{}]*\}", "p", spec)
                ncols = sum(1 for ch in spec if ch in "lrcp")
                if ncols <= self.MAX_COLS_IN_SINGLE_COLUMN:
                    continue
                start = text.rfind("\\begin{table", 0, m.start())
                env = text[start:start + 20]
                if "table*" not in env:
                    label = re.search(r"\\label\{(tab:[^}]*)\}", text[m.start():m.start() + 3000])
                    problems.append("%s: %s has %d columns but is not a table*"
                                    % (os.path.basename(path),
                                       label.group(1) if label else "<unlabelled>", ncols))
        self.assertFalse(problems,
                         "wide tables must use table* or they collide with the adjacent column:\n  "
                         + "\n  ".join(problems))


class TestBibliographyIsWellFormed(unittest.TestCase):
    """The shared bibliography must parse, and every cited key must exist.

    BibTeX has no in-entry comment syntax: a `%` between the braces of an entry is a parse
    error, not a comment. One was introduced here and survived a full local build, because
    latexmk cached the failure from a previous invocation and reported the PDF as
    up-to-date - the compile "passed" while the bibliography was broken. Nothing in the
    suite read a .blg file, so the only symptom was an exit code inside `make papers`.
    """

    BIB = os.path.join(ROOT, "paper_common", "references.bib")

    def _entries(self):
        """{key: body} for every entry, by brace matching rather than by regex - entries
        contain nested braces and a lazy pattern stops at the first one."""
        text = open(self.BIB, encoding="utf-8").read()
        out = {}
        for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
            start = text.index("{", m.start())
            depth, i = 0, start
            while i < len(text):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                i += 1
            out[m.group(2)] = text[start:i + 1]
        return out

    def test_no_entry_contains_a_percent_comment(self):
        offenders = []
        for key, body in self._entries().items():
            for line in body.splitlines():
                stripped = line.lstrip()
                if stripped.startswith("%"):
                    offenders.append("%s: %s" % (key, stripped[:60]))
        self.assertFalse(
            offenders,
            "BibTeX treats %% inside an entry as literal text, not a comment, and the "
            "entry fails to parse. Move the note above the @entry line:\n  "
            + "\n  ".join(offenders))

    def test_every_cited_key_is_defined(self):
        import glob
        defined = set(self._entries())
        cited, sources = set(), {}
        for path in (glob.glob(os.path.join(ROOT, "papers", "*", "sections", "*.tex"))
                     + glob.glob(os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex"))):
            text = open(path, encoding="utf-8").read()
            for m in re.finditer(r"\\cite[a-zA-Z]*\{([^}]*)\}", text):
                for key in m.group(1).split(","):
                    key = key.strip()
                    if key:
                        cited.add(key)
                        sources.setdefault(key, os.path.basename(path))
        missing = sorted(cited - defined)
        self.assertFalse(missing, "cited but not defined in references.bib: "
                         + ", ".join("%s (%s)" % (k, sources[k]) for k in missing))

    def test_no_document_declares_a_bibliography_it_never_cites(self):
        """An empty citation list makes BibTeX report an error on every build, which is
        noise that trains a reader to ignore .blg files."""
        import glob
        problems = []
        for tex in glob.glob(os.path.join(ROOT, "papers", "*", "*.tex")) + \
                glob.glob(os.path.join(PAPER_NATIONAL_MAIN, "*.tex")):
            root = os.path.dirname(tex)
            text = open(tex, encoding="utf-8").read()
            if "\\bibliography{" not in text:
                continue
            body = text
            for m in re.finditer(r"\\input\{([^}]*)\}", text):
                path = asset_path(root, m.group(1))
                path = path if path.endswith(".tex") else path + ".tex"
                if os.path.exists(path):
                    body += open(path, encoding="utf-8").read()
            if not re.search(r"\\cite[a-zA-Z]*\{", body):
                problems.append(os.path.relpath(tex, ROOT))
        self.assertFalse(problems, "declares a bibliography but cites nothing: "
                         + ", ".join(problems))


class TestPowerFamilyPolicy(unittest.TestCase):
    """The configurations file's own rule: every quote of the 57.82 Mt grid
    figure (net of the rc19 post-meter gas share) carries the
    power_grid_control family beside it. The tenth review found nine bare
    quotes of its 58.00 predecessor, including a table labelling the reference
    'the estimate' while the conclusion calls all three members provisional.
    The sweep: any 57.82 in the power or national tex must have a family
    marker within 400 characters."""

    # ^{f} is the table form: a dagger on the row whose definition - the full
    # family sentence - lives in that table's caption. The dagger is the
    # in-window marker; the caption test cannot be beaten by table length.
    MARKERS = ("power\\_grid\\_control", "structural family", "grid family",
               "38.45", "61.83", "family beside", "family reference",
               "alternatives named beside", "^{f}")

    def test_no_bare_grid_headline(self):
        import glob as _glob
        offenders = []
        roots = (os.path.join(ROOT, "papers", "power", "sections", "*.tex"),
                 os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex"))
        for pattern in roots:
            for path in sorted(_glob.glob(pattern)):
                text = " ".join(open(path, encoding="utf-8").read().split())
                for m in re.finditer(r"(?<![\d.])57\.82(?![\d])", text):
                    # Inside a floating table the caption is the marker's home
                    # and may sit further than any fixed window on a long
                    # table, so the whole table environment is the window.
                    tbl_start = text.rfind("\\begin{table", 0, m.start())
                    tbl_end = text.find("\\end{table", m.end())
                    if (tbl_start != -1 and tbl_end != -1
                            and "\\end{table" not in text[tbl_start:m.start()]):
                        window = text[tbl_start:tbl_end]
                    else:
                        window = text[max(0, m.start() - 400):m.end() + 400]
                    if not any(mk in window for mk in self.MARKERS):
                        offenders.append("%s @%d: ...%s..."
                                         % (os.path.basename(path), m.start(),
                                            text[max(0, m.start() - 60):m.end() + 60]))
        self.assertFalse(offenders,
                         "bare 57.82 quotes without the family beside them:\n  "
                         + "\n  ".join(offenders))


class TestFugitivesEnvelopePolicy(unittest.TestCase):
    def test_the_standing_disclaimer_cannot_silently_regress(self):
        """The seventeenth review's framing ask, made positive (rc28): the
        fugitives abstract and conclusion must each SAY the reference is an
        upper-practice conservative configuration and not an empirically
        centred best estimate, with the no-probability statement beside it -
        the envelope markers alone guard quotes, not the standing claim."""
        for section in ("00_abstract.tex", "09_conclusion.tex"):
            text = open(os.path.join(ROOT, "papers", "fugitives", "sections",
                                     section), encoding="utf-8").read()
            self.assertIn("empirically centred", text, section)
            self.assertIn("upper-practice", text, section)
            self.assertIn("probability attaches to any point", text, section)

    """The configurations file's other selection rule, enforced on the
    manuscripts the way the power family already is: the 24.694 reference sits
    at the TOP of its own 9.601-24.694 structural envelope by construction, and
    the twelfth review found it travelling bare in four national-paper tables -
    a structural maximum reading as a neutral centre. Any 24.69 quote must have
    an envelope marker within 400 characters (or within its own table
    environment, where the caption is the marker's home)."""

    MARKERS = ("fugitives\\_structural\\_envelope", "structural envelope",
               "envelope's top", "envelope private", "9.60", "16.088", "16.09",
               "18.87", "^{e}")

    def test_no_bare_twenty_four_sixty_nine(self):
        import glob as _glob
        offenders = []
        roots = (os.path.join(ROOT, "papers", "fugitives", "sections", "*.tex"),
                 os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex"))
        for pattern in roots:
            for path in sorted(_glob.glob(pattern)):
                text = " ".join(open(path, encoding="utf-8").read().split())
                for m in re.finditer(r"(?<![\d.])24\.69\d?(?![\d])", text):
                    tbl_start = text.rfind("\\begin{table", 0, m.start())
                    tbl_end = text.find("\\end{table", m.end())
                    if (tbl_start != -1 and tbl_end != -1
                            and "\\end{table" not in text[tbl_start:m.start()]):
                        window = text[tbl_start:tbl_end]
                    else:
                        window = text[max(0, m.start() - 400):m.end() + 400]
                    if not any(mk in window for mk in self.MARKERS):
                        offenders.append("%s @%d: ...%s..."
                                         % (os.path.basename(path), m.start(),
                                            text[max(0, m.start() - 60):m.end() + 60]))
        self.assertFalse(offenders,
                         "bare 24.69 quotes without the envelope beside them:\n  "
                         + "\n  ".join(offenders))


class TestAgricultureEditorialStructure(unittest.TestCase):
    """The tenth review found the agriculture supplement contradicting the main
    paper AND the engine about its own Monte Carlo: S3 said "Correlations are not
    modelled" while the engine gives the volatilised- and leached-N groups one
    shared deviate per draw (corr_group soils_volat/soils_leach), and both S3 and
    the appendix said the MC "draws each category total" while the engine samples
    COMPONENTS (mc_core.run over build_components). Both claims are banned."""

    def _text(self, name):
        path = os.path.join(DOCS["agriculture"], name)
        return " ".join(open(path, encoding="utf-8").read().split())

    def test_the_supplement_cannot_deny_the_modelled_correlation(self):
        for name in ("S3_uncertainty.tex", "10_appendix.tex"):
            self.assertNotIn("Correlations are not modelled", self._text(name),
                             name)

    def test_the_category_draw_claim_is_banned(self):
        # rc16: swept over the WHOLE agriculture document set, not two files -
        # the eleventh review found the methods section and a table caption still
        # describing category-level sampling twenty lines from the corrected prose.
        import glob as _glob
        names = [os.path.basename(p) for p in
                 _glob.glob(os.path.join(DOCS["agriculture"], "*.tex"))]
        for name in names:
            text = self._text(name)
            for phrase in ("draws each \\emph{category total}",
                           "draws each \\emph{category}",
                           "represents each category total with a mean-preserving",
                           "aggregates the sampled category",
                           "all lognormal, sampled independently",
                           "does not sample the individual input rows"):
                self.assertNotIn(phrase, text, "%s still claims category-level "
                                               "draws: %r" % (name, phrase))


class TestTransportEditorialStructure(unittest.TestCase):
    """The wording invariants of the August 2026 rounds, pinned so a partial edit
    cannot reintroduce them: the stale CNG-absence claim, the OCAC not-obtained
    claim (now false in the other direction - the tables are integrated), the
    unconditional road-total framing, the EMEP misattribution of the air factors,
    and the policy claims the demoted air diagnostic must not carry."""

    def _read(self, name):
        with open(_doc_path("transport", name), encoding="utf-8") as handle:
            return handle.read()

    def test_cng_is_never_described_as_absent(self):
        data = self._read("03_study_area_and_data.tex")
        self.assertNotIn("absent from this sector entirely", data)
        self.assertIn("third fuel control", data)

    def test_the_ocac_tables_are_integrated_not_unobtained(self):
        """Round 1 pinned 'published but not obtained'; the re-anchor flipped the
        truth again. No section may claim the sectoral tables were not obtained,
        and the data section must carry the customer-class semantics."""
        for name in ("03_study_area_and_data.tex", "04_methods.tex",
                     "05_validation.tex", "08_limitations.tex"):
            text = self._read(name)
            self.assertNotIn("not been obtained here", text, name)
            self.assertNotIn("not been acquired here", text, name)
            self.assertNotIn("have not been obtained", text, name)
        data = " ".join(self._read("03_study_area_and_data.tex").split())
        self.assertIn("customer class", data)
        self.assertIn("in the repository throughout", data)

    def test_the_road_figure_is_a_conditional_residual(self):
        for name in ("00_abstract.tex", "06_results.tex", "09_conclusion.tex"):
            text = " ".join(self._read(name).split())
            self.assertIn("conditional road residual", text, name)
        for name in ("00_abstract.tex", "01_introduction.tex", "04_methods.tex",
                     "05_validation.tex", "06_results.tex", "07_discussion.tex",
                     "08_limitations.tex", "09_conclusion.tex"):
            text = self._read(name)
            self.assertNotIn("upper bound by construction", text, name)
            self.assertNotIn("checks with teeth", text, name)

    def test_the_superseded_control_is_a_named_scenario(self):
        # Round 3 moved the superseded pair from tab:boundary into its own
        # provenance-audit table; S1's scenario walk now points at that table
        # rather than naming the row, so that is what it must keep doing.
        for name, token in (("03_study_area_and_data.tex", "legacy\\_pes\\_control"),
                            ("06_results.tex", "Superseded PES control"),
                            ("S1_uncertainty.tex", "provenance-audit bridges")):
            text = " ".join(self._read(name).split())
            self.assertIn(token.replace("\\\\", "\\"), text, name)

    def test_construction_machinery_is_mapped_to_1a2(self):
        related = self._read("02_related_work.tex")
        self.assertIn("1A2", related)
        limitations = self._read("08_limitations.tex")
        self.assertIn("1A2\\,gvii", limitations)
        self.assertIn("Mixed off-road", limitations)

    def test_air_factors_credit_the_held_guidebook_and_distinguish_superseded_workbook(self):
        """Current Tier1 factors come from held EMEP tables; the superseded
        workbook g/km block must retain its narrower provenance label.
        """
        from pkinv.sectors.transport import air_pollutants
        self.assertTrue(air_pollutants.factors())
        current = self._read("06b_air_pollutants.tex")
        self.assertIn("EMEP/EEA", current)
        self.assertIn("Tier~1", current)
        self.assertNotIn("emep2019", current, "the crop-burning chapter is not a road factor source")
        factors = " ".join(self._read("S2_factors.tex").split())
        self.assertIn("SUPERSEDED per-kilometre factors", factors)
        self.assertIn("no primary citation was ever located", factors)

    def test_the_air_layer_is_an_appendix_with_stated_bases_and_bounded_claims(self):
        """The demotion guard's successor (air program Wave 2): the layer is no longer
        an exploratory diagnostic - its factors are the cited EMEP/EEA Tier 1 chapters
        and its fuel is OCAC-anchored - but the editorial discipline it enforced
        survives translated: the section stays after \\appendix, states the
        NO2-equivalent and NMVOC bases, presents the old-vs-new comparison rather
        than silently replacing history, and confines what a claim may ride on it
        (a placement, never a technology claim) in its own words."""
        with open(os.path.join(ROOT, "papers", "transport", "paper.tex"),
                  encoding="utf-8") as handle:
            paper = handle.read()
        self.assertLess(paper.index("\\appendix"),
                        paper.index("sections/06b_air_pollutants"))
        air = self._read("06b_air_pollutants.tex")
        self.assertIn("EMEP/EEA Tier~1", air)
        self.assertIn("does not validate a transferred PM or NO$_x$ factor", air)
        self.assertIn("not universal pump-level compliance", air)
        self.assertIn("resuspension stays out", air)
        self.assertIn("NO$_2$-equivalent", air)
        self.assertIn("NMVOC", air)
        for name in ("00_abstract.tex", "07_discussion.tex", "09_conclusion.tex",
                     "06b_air_pollutants.tex"):
            text = " ".join(self._read(name).split())
            self.assertNotIn("should not start here", text, name)
            self.assertNotIn("CO problem", text, name)

    def test_the_transport_bibliography_points_at_the_energy_volume(self):
        for name in ("02_related_work.tex", "10_appendix.tex"):
            text = self._read(name)
            self.assertNotIn(r"\citep{ipcc2006}", text, name)
        appendix = self._read("10_appendix.tex")
        self.assertIn("ipcc2006energy", appendix)
        self.assertNotIn(r"\citep{econsurvey}", appendix)
        for key in ("naveedpunjab", "guttikunda2024", "pakrailyearbook2024",
                    "provregstats", "ocacarchive", "hies2025", "goppetrol"):
            self.assertIn(key, appendix, key)

    def test_round3_stale_strings_are_banned(self):
        """Round 3's submission blocker was stale generated appendices contradicting
        the re-anchored method. These are the exact strings the reviewer caught -
        the subtracted-rail description, the registration-proxy caveats, the retired
        off-road label - plus the cross-reference doubling: after elsarticle's
        \\appendix, \\thesection already reads "Appendix X", so a literal
        "Appendix~\\ref" prints "Appendix Appendix"."""
        import glob
        for path in sorted(glob.glob(os.path.join(DOCS["transport"], "*.tex"))):
            text = open(path, encoding="utf-8").read()
            name = os.path.basename(path)
            self.assertNotIn("net of railway diesel", text, name)
            self.assertNotIn("pending fuel-sales-based controls", text, name)
            self.assertNotIn("lower bound for Sindh", text, name)
            self.assertNotIn("Off-road machinery (1A4c ii)", text, name)
            self.assertNotIn("Appendix~\\ref", text, name)

    def test_retired_nh3_values_are_banned(self):
        """The eighth review's NH3 item: 0.1615 and 0.1685 survived in the equation,
        both supplements and the provenance appendix for eight releases because the
        printed-quantity sweep reads only \\SI/\\num/numeric cells - bare digits in
        display and inline math are invisible to it (a structural blind spot, noted
        at _quantities). The retired values are banned by literal instead: the
        engine computes 0.1605, the Eq. 11.9 sum is 0.1675, and no agriculture
        document may print the values they replaced."""
        import glob
        for path in sorted(glob.glob(os.path.join(DOCS["agriculture"], "*.tex"))):
            text = open(path, encoding="utf-8").read()
            name = os.path.basename(path)
            self.assertNotIn("0.1615", text, name)
            self.assertNotIn("0.1685", text, name)

    def test_stale_rail_booking_claims_are_banned(self):
        """The eighth review found the rc11 rail re-base half-described: the ENGINE
        books 0.38939 at strict 1A3c and 0.00498 at its own non-traction category,
        but the railways conclusion still said 'traction emitted 0.394', the
        limitations section contradicted itself thirteen lines apart, and the
        national completeness table's IE row still enumerated 'railway non-traction
        fuel declared inside 1A3c'. One canonical statement now, and the stale
        phrasings are banned across BOTH document sets - the transport-only version
        of this test is why they survived there and nowhere else."""
        import glob
        for docdir in (DOCS["railways"], DOCS["national"]):
            for path in sorted(glob.glob(os.path.join(docdir, "*.tex"))):
                text = open(path, encoding="utf-8").read()
                name = os.path.basename(path)
                self.assertNotIn("left in 1A3c", text, name)
                self.assertNotIn("declared inside 1A3c", text, name)
                self.assertNotIn("railway traction emitted", text.lower(), name)
                self.assertNotIn("inside the traction figure", text, name)

    def test_round4_stale_strings_are_banned(self):
        """Round 4 corrected the class allocation, and correcting it changed what the
        paper can say. These are the claims that were true under distance-only
        weighting and are false under energy weighting, plus the two the reviewer
        found unsupported."""
        import glob
        for path in sorted(glob.glob(os.path.join(DOCS["transport"], "*.tex"))):
            text = " ".join(open(path, encoding="utf-8").read().split())
            name = os.path.basename(path)
            self.assertNotIn("robust enough in direction", text, name)
            self.assertNotIn("least well characterised quantity in any", text, name)
            self.assertNotIn("each sector's air estimate computed from the same "
                             "activity data as its greenhouse gases", text, name)
            # the superseded magnitudes, which must not survive a partial edit
            self.assertNotIn("21.89", text, name)
            self.assertNotIn("0.785849", text, name)
            self.assertNotIn("788.5", text, name)
            self.assertNotIn("0.099985", text, name)
            # The ninth review's find: the methods prose said the two-wheeler
            # petrol weight fell "from 0.786 to 0.563" - and 0.563 has NO source
            # anywhere in the outputs (the energy-weighted value is 0.6100, per
            # Table S8's 0.609992). The stale pair survived four rounds because
            # this ban-list banned the CORRECT raw weight (0.785849) while the
            # wrong prose pair went unguarded.
            self.assertNotIn("0.563", text, name)

    def test_year_matched_is_never_claimed_of_the_edgar_comparison(self):
        """A fiscal year cannot be year-matched to a calendar one, and saying so was
        the reviewer's second submission blocker. The ban is proximity-based, not a
        blanket one: "year-matched" is CORRECT of the rail cross-check, where both
        figures are FY2021-22, and those uses must survive - so this asserts they are
        still there, or the ban could be satisfied by deleting the right ones."""
        import glob
        near = re.compile(r"(year-matched[^.]{0,140}EDGAR)|(EDGAR[^.]{0,140}year-matched)")
        for path in sorted(glob.glob(os.path.join(DOCS["transport"], "*.tex"))):
            text = " ".join(open(path, encoding="utf-8").read().split())
            self.assertIsNone(near.search(text),
                              "%s claims a year-matched EDGAR comparison"
                              % os.path.basename(path))
        rail = " ".join(self._read("05_validation.tex").split())
        self.assertIn("year-matched", rail)
        self.assertIn("fiscal-year blended", " ".join(
            self._read("05_validation.tex").split()))

    def test_the_national_share_is_a_common_period_share(self):
        """The caveat this test used to enforce is retired, and the retirement is the point.

        The shares were computed over sectors reporting different years, so every one of
        them was a sum across four fiscal years wearing a single-year label. This sector was
        the reason: it reported FY2021-22 while eight others reported FY2023-24. Now that it
        is on the common period, the qualifier would be false rather than cautious - and the
        movement it was concealing was large, a share of 12.2 percent against 9.0 and a drop
        from the second largest category to the third.

        What must survive is the accounting for that movement. A reader comparing editions
        is owed the reason a headline share fell by a quarter, and the previous edition's
        own prediction of it.
        """
        results = " ".join(self._read("06_results.tex").split())
        self.assertIn("COMMON-PERIOD shares", results)
        self.assertIn("9.43", results)            # the prediction the previous edition made
        self.assertIn("third largest category", results)
        self.assertNotIn("latest-supported-year nowcast", results)
        # The superseded ranking must not survive anywhere in the document.
        for name in ("06_results.tex", "07_discussion.tex", "09_conclusion.tex"):
            text = " ".join(self._read(name).split())
            self.assertNotIn("second largest category", text, name)

    def test_the_class_split_is_described_as_energy_weighted(self):
        """The composition reversal has to be visible in the paper, not just in the
        outputs: the reweighting changed which class is largest, and a reader
        comparing editions is owed the reason."""
        results = " ".join(self._read("06_results.tex").split())
        self.assertIn("energy-weighted", results)
        methods = " ".join(self._read("04_methods.tex").split())
        self.assertIn("energy intensity", methods)
        self.assertIn("declared engineering judgement", methods)
        limits = " ".join(self._read("08_limitations.tex").split())
        self.assertIn("none of them measured in the country", limits)

    def test_the_supplement_and_the_paper_partition_the_sections(self):
        """Two documents share one sections/ directory. Every section file must belong
        to exactly one of them - a file in neither is dead, and a file in both prints
        twice under different numbering."""
        import glob
        root = os.path.join(ROOT, "papers", "transport")
        # _inputs_of normalises what it returns (it has to, to resolve ../.. inputs), so
        # both sides of this comparison are normalised or none of them are.
        sections_dir = os.path.normpath(os.path.join(root, "sections")) + os.sep
        # _inputs_of returns EVERY input a document takes, shared preamble and release
        # cover included, because PDF staleness has to watch those too. This test is
        # about the shared sections/ directory alone, so it scopes to that directory -
        # paper_common files are inputted by both documents by design and are not a
        # partition violation.
        def sections_of(name):
            return {p for p in _inputs_of(asset_path(root, name), root)
                    if p.startswith(sections_dir)}
        paper = sections_of("paper.tex")
        supp = sections_of("supplement.tex")
        on_disk = {os.path.normpath(p)
                   for p in glob.glob(os.path.join(root, "sections", "*.tex"))}
        self.assertFalse(paper & supp, "a section is inputted by both documents")
        self.assertEqual(paper | supp, on_disk,
                         "sections/ and the two documents disagree about what exists")

    def test_no_reference_crosses_between_the_two_documents(self):
        """\ref across documents silently prints ?? under nonstopmode, so the split
        uses textual pointers. This checks none crept back."""
        import glob
        root = os.path.join(ROOT, "papers", "transport")
        sides = {}
        for doc in ("paper.tex", "supplement.tex"):
            files = _inputs_of(asset_path(root, doc), root)
            text = "".join(open(f, encoding="utf-8").read() for f in files)
            text += open(asset_path(root, doc), encoding="utf-8").read()
            sides[doc] = (set(re.findall(r"\\label\{([^}]*)\}", text)),
                          set(re.findall(r"\\ref\{([^}]*)\}", text)))
        for doc, (labels, refs) in sides.items():
            other = sides["supplement.tex" if doc == "paper.tex" else "paper.tex"][0]
            crossing = (refs - labels) & other
            self.assertFalse(crossing,
                             "%s references labels defined only in the other "
                             "document: %s" % (doc, sorted(crossing)))

    def test_appendix_floats_are_barriered(self):
        """Wide table* floats cannot be placed on the page that introduces them, so an
        unbarriered run of appendix \input lines queues them across near-blank pages
        away from their own headings. Both 5p papers with appendices must barrier."""
        for doc in ("transport", "residential"):
            path = os.path.join(ROOT, "papers", doc, "paper.tex")
            body = open(path, encoding="utf-8").read().split("\\appendix", 1)[-1]
            lines = [l.strip() for l in body.splitlines() if l.strip()
                     and not l.strip().startswith("%")]
            for i, line in enumerate(lines):
                if not line.startswith("\\input{sections/"):
                    continue
                following = lines[i + 1:i + 3]
                self.assertTrue(
                    any(f.startswith(("\\FloatBarrier", "\\clearpage"))
                        for f in following),
                    "%s: %s is not followed by a float barrier" % (doc, line))

    def test_the_supplement_clears_between_notes(self):
        root = os.path.join(ROOT, "papers", "transport")
        text = open(os.path.join(root, "supplement.tex"), encoding="utf-8").read()
        chunks = re.split(r"\\input\{sections/", text)[1:]
        for chunk in chunks[:-1]:
            self.assertIn("\\clearpage", chunk,
                          "supplementary notes must be separated by \\clearpage")
        title = re.search(r"\\title\{(.*?)\n\n", text, re.S)
        paper = open(os.path.join(root, "paper.tex"), encoding="utf-8").read()
        headline = re.search(r"\\title\{(.*?)\}", paper, re.S).group(1)
        # v1.0.0: the title opens with the Sector Technical Note banner line; the
        # headline the supplement must name is what follows it.
        headline = headline.split("\\\\[4pt]\n")[-1]
        self.assertIn(headline.split(":")[0].strip(), text,
                      "the supplement must name the paper it accompanies")

    def test_the_sector_count_is_ten_everywhere(self):
        """Round 3 found three sector counts in circulation: "ten sectors", "other
        eight sectors", and a companion citation titled "Nine-Sector". One number:
        the registry has ten sectors, so companions are "the other nine", and the
        ahmad2026national title must match the national manuscript's actual title."""
        self.assertIn("other nine sectors", self._read("01_introduction.tex"))
        for doc in ("transport", "residential"):
            text = open(_doc_path(doc, "01_introduction.tex"),
                        encoding="utf-8").read()
            self.assertNotIn("other eight sectors", text, doc)
        with open(os.path.join(ROOT, "paper_common", "references.bib"),
                  encoding="utf-8") as handle:
            bib = handle.read()
        entry = re.search(r"@\w+\{ahmad2026national.*?\n\}", bib, re.S)
        self.assertIsNotNone(entry, "ahmad2026national entry lost")
        with open(_main_tex(PAPER_NATIONAL_MAIN),
                  encoding="utf-8") as handle:
            national = handle.read()
        # The bibliography entry must carry the manuscript's CURRENT title, whatever it is,
        # rather than a fixed string: pinning "Ten-Sector" here is what made a retitle fail
        # this test instead of the stale citation it was meant to catch. The title itself is
        # checked for accuracy in TestTheTitleIsAccurate.
        title = re.search(r"\\title\{(.*?)\}\s*\\author", " ".join(national.split()))
        self.assertIsNotNone(title, "the national manuscript has no title")
        import pkinv
        headline = title.group(1).replace(r"\PakEmisRelease{}", pkinv.__version__).replace(r"\PakEmisRelease", pkinv.__version__)
        head = " ".join(headline.split()).replace("{", "").replace("}", "")[:48]
        citation = " ".join(entry.group(0).split()).replace("{", "").replace("}", "")
        self.assertIn(head, citation,
                      "references.bib cites a superseded title")
        for text, where in ((entry.group(0), "references.bib"),
                            (national, "paper_national.tex")):
            self.assertNotIn("Nine-Sector", text, where)


class TestWasteEditorialStructure(unittest.TestCase):
    """Waste analogues of the transport wording invariants, pinned after the
    August 2026 repair round: the air factors are Andreae 2019 garbage burning
    (not EMEP/EEA 3.F, which is the crop-residue chapter), the guideline citation
    is Volume 5 (the bare ipcc2006 key is Volume 4 AFOLU), the census citation is
    the population census (pbscensus2024 is the agricultural census), and the
    EDGAR comparison is year-matched to the 2023 reference year."""

    ALL = ("00_abstract.tex", "01_introduction.tex", "02_related_work.tex",
           "03_study_area_and_data.tex", "04_methods.tex",
           "04b_emission_factors.tex", "05_validation.tex", "06_results.tex",
           "06b_air_pollutants.tex", "07_discussion.tex", "08_limitations.tex",
           "09_conclusion.tex", "10_appendix.tex", "S1_uncertainty.tex")

    def _read(self, name):
        with open(_doc_path("waste", name), encoding="utf-8") as handle:
            return handle.read()

    def test_air_factors_are_never_attributed_to_emep(self):
        """The factors are Andreae 2019 ACP Table 1 "garbage burning" (so say the
        factor rows and the module docstring); EMEP/EEA 3.F covers field burning
        of agricultural residues and its road chapter was never the source."""
        for name in self.ALL:
            self.assertNotIn("emep2019", self._read(name), name)
        self.assertIn("andreae2019", self._read("06b_air_pollutants.tex"))
        self.assertIn("andreae2019", self._read("10_appendix.tex"))

    def test_the_waste_bibliography_points_at_the_waste_volume(self):
        for name in self.ALL:
            text = self._read(name)
            self.assertNotIn(r"\citep{ipcc2006}", text, name)
            self.assertNotIn(r"\citet{ipcc2006}", text, name)
        appendix = self._read("10_appendix.tex")
        self.assertIn("ipcc2006waste", appendix)
        self.assertIn("pbscensus2023", appendix)
        self.assertNotIn("pbscensus2024", appendix)
        self.assertIn("jmp2023", appendix)
        self.assertIn("pakepa1996", appendix)

    def test_the_generation_rates_credit_the_primary_survey(self):
        """kaza2018 re-bins the Pak-EPA 1996 eight-city survey; the rates must be
        credited to the survey, with kaza2018 supplying only collection coverage."""
        for name in ("02_related_work.tex", "03_study_area_and_data.tex",
                     "10_appendix.tex"):
            self.assertIn("pakepa1996", self._read(name), name)

    def test_the_edgar_comparison_is_year_matched(self):
        self.assertEqual(
            26.57, _bench("EDGAR", "waste", "benchmark_Mt_co2e", year=2023))
        rows = [r for r in _data_rows("benchmarks.csv")
                if r["source"] == "EDGAR" and r["engine_category"] == "waste"]
        self.assertIn("2023", [r["year"] for r in rows])
        matched = next(r for r in rows if r["year"] == "2023")
        self.assertIn("YEAR-MATCHED", matched["note"])
        validation = self._read("05_validation.tex")
        self.assertNotIn("for 2024 \\citep{edgar2024}", validation)
        self.assertIn("for 2023", validation)
        self.assertIn("edgar2025booklet", validation)

    def test_the_mc_scenario_is_labelled(self):
        """The round that found S1's three Monte-Carlo numbers all wrong also found
        the paper never said WHICH pooled treatment its headline band was. The pin
        evolved at rc12: the pooled lognormal surrogate is retired, so the label
        the reader needs is that the NATIONAL rows are the sector's own injected
        rerun draws, on the published seed."""
        s1 = " ".join(self._read("S1_uncertainty.tex").split())
        self.assertIn("reruns the disposal-history, wastewater and burning calculations", s1)
        self.assertIn("same burned dry mass realisations", s1)
        self.assertIn("does not sample population, collection or burn fraction a second time", s1)
        from pkinv.core.shared_parameter_draws import SEED
        self.assertIn("seed \\num{%d}" % SEED, s1)
        self.assertIn("earlier standalone sector ensemble remains a named diagnostic", s1)
