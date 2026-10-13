"""One release, one year, one metric: the shipped tree describes itself.

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

from _support import require_documents  # noqa: E402  (rc42: the documents gate)

from pkinv import paths
from pkinv.paths import PAPER_NATIONAL_MAIN, PAPER_NATIONAL_SECTIONS  # noqa: E402
from pkinv.core.io import read_rows
from paper_numbers._common import (
    DOCS,
    MANUSCRIPTS,
    OUT,
    ROOT,
    SECTORS,
    _cell,
    _csv_rows,
    _data_rows_nocomment,
    _doc_path,
    _figures_of,
    _inputs_of,
    _load_repo_script,
    _main_tex,
    _rows,
    _sector,
    _sector_alt,
    _transport_year,
    _waste_year)
from paper_numbers.doc_claims import (
    CLOSURES,
    _bench,
    _closure_count,
    _closures_crossing_modules)


class TestProductCoverageMatrix(unittest.TestCase):
    """The coverage matrix regenerates identically, and covers every module.

    Both directions on purpose: a committed fragment that drifts from the generator is
    a stale table wearing a GENERATED header, and a generator that silently drops a
    module is coverage disappearing without a diff a reader would notice.
    """

    def test_the_product_table_matches_a_fresh_render(self):
        """The supplement's product table is generated, in both directions.

        It was hand-maintained and drifted: its uncertainty row said "reference year only" and
        that no time-correlated ensemble was published, while two longitudinal products shipped
        and the main paper described their three scenarios. Prose could contradict a file
        because no test could compare the two. Now it can.
        """
        from pkinv.report import product_catalog
        committed = open(os.path.join(PAPER_NATIONAL_SECTIONS,
                                      "generated_products.tex"), encoding="utf-8").read()
        self.assertEqual(committed, product_catalog.render(product_catalog.catalog()))

    def test_every_catalogued_product_has_an_artifact_and_an_anchor(self):
        """Exit criteria 5 and 6 of docs/product_catalog_design.md, for the catalogued slice."""
        from pkinv.report import product_catalog
        self.assertEqual([], product_catalog.missing_artifacts())
        for row in product_catalog.catalog():
            self.assertTrue(row["documentation_anchor"].strip(), row["product_id"])
            self.assertEqual(1, len(row["product_family"].split(";")), row["product_id"])

    def test_no_manuscript_mixes_the_two_temporal_vocabularies(self):
        """One scale, one name, in everything a reader sees.

        The codebase carries both: `temporal_method` is T1-T4, what a sector's monthly layer
        did, and `temporal_evidence_class` is TE1-TE4, the grade the products publish. They map
        one to one, which is exactly why printing one in a paper and the other in the CSV
        beside it reads as two different scales. Every SHIPPED column says TE, so the
        manuscripts say TE; T stays inside the layers where it means something narrower.
        """
        import glob
        import re
        offenders = []
        for path in (glob.glob(os.path.join(PAPER_NATIONAL_MAIN, "*.tex"))
                     + glob.glob(os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex"))):
            text = open(path, encoding="utf-8").read()
            # A bare T1..T4 that is not part of TE1..TE4.
            if re.search(r"(?<![A-Za-z])T[1-4](?![0-9])", text):
                offenders.append(os.path.basename(path))
        self.assertEqual([], offenders,
                         "these print the layer-internal T vocabulary where a reader expects "
                         "the published TE one: %s" % offenders)

    def test_the_supplement_no_longer_denies_its_own_products(self):
        """The specific contradiction, pinned so it cannot come back by another route."""
        text = open(os.path.join(PAPER_NATIONAL_MAIN, "supplement.tex"),
                    encoding="utf-8").read()
        for banned in ("reference year only", "There is no time-correlated"):
            self.assertNotIn(banned, text,
                             "the supplement is describing the uncertainty family as it was "
                             "before the longitudinal products shipped")

    def test_committed_fragment_matches_a_fresh_render(self):
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import make_product_coverage as mpc
        committed = open(os.path.join(PAPER_NATIONAL_SECTIONS,
                                      "generated_coverage.tex"),
                         encoding="utf-8").read()
        self.assertEqual(committed, mpc.render(mpc.rows()))

    def test_the_availability_fragments_match_a_fresh_render(self):
        """The ESSD availability statements, the abstract's DOI sentence and the technical
        notes' paragraph are generated from the release manifest (identifiers, licences,
        version), so that no document can name a placeholder DOI or a previous release. Both
        directions: a committed fragment equal to a fresh render, and a render that carries
        the manifest's version and cites no deposit whose identifier is still empty."""
        import json
        mod = _load_repo_script("make_availability.py")
        with open(os.path.join(OUT, "release_manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        fresh = mod.render(manifest)
        self.assertEqual(sorted(fresh), sorted([mod.AVAILABILITY, mod.ABSTRACT_DOI,
                                                mod.TN_PARAGRAPH]))
        for rel, text in fresh.items():
            committed = open(asset_path(ROOT, rel), encoding="utf-8").read()
            self.assertEqual(committed, text, "%s is stale; run python3 "
                             "scripts/make_availability.py" % rel)
            self.assertNotIn("zenodo.XXXX", text)
        self.assertIn(manifest["version"], fresh[mod.AVAILABILITY])
        for kind, key in mod.BIBKEYS.items():
            cited = any(key in text for text in fresh.values())
            self.assertEqual(cited, bool(manifest["doi"].get(kind)),
                             "%s is cited iff its identifier is minted" % key)

    def test_ocac_edition_inventory_matches_the_holdings(self):
        """rc18: two true edition counts of two different populations read as a
        contradiction until the inventory distinguished them - and a count that
        drifts from the holdings would re-create it."""
        require_documents("sources/Aviation/ocac_monthly", "data/raw/ocac/monthly_sector_province",
                          "data/raw/ocac/annual_controls", "data/raw/ocac/alternate_uploads")
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import make_ocac_edition_inventory as moi
        committed = {r["kind"]: int(r["count"])
                     for r in _csv_rows("ocac_edition_inventory.csv")}
        fresh = {r["kind"]: r["count"] for r in moi.build()}
        self.assertEqual(committed, fresh)
        self.assertEqual(committed["direct_monthly"], 36)
        self.assertEqual(committed["cumulative_monthly"], 48)

    def test_fugitives_conditional_table_matches_a_fresh_render(self):
        """rc18: the hand-written predecessor shipped without the central
        member the paper itself describes - the thirteenth review's finding.
        Generated now, so a configuration cannot ship and be absent from it."""
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        import make_fugitives_conditional_table as mfc
        committed = open(os.path.join(ROOT, "papers", "fugitives", "sections",
                                      "S6_conditional_table.tex"),
                         encoding="utf-8").read()
        self.assertEqual(committed, mfc.render())
        self.assertIn("Central (geometric-mean practice)", committed)

    def test_every_module_appears_once(self):
        rows = _rows("pakemis_product_coverage.csv")
        from pkinv.core import registry
        names = sorted(s.NAME for s in registry.all_sectors())
        self.assertEqual(sorted(r["module"] for r in rows), names)
        for r in rows:
            self.assertTrue(r["cube_allocation_bases"],
                            "%s: no cube allocation basis recorded" % r["module"])


class TestFiguresAreCurrent(unittest.TestCase):
    """A figure that does not match the output it plots is a stale result shipped as a picture,
    invisible to every numeric check. Some shipped a month behind before this existed, because the
    sync script pointed only at the companion paper's directory."""

    # The agriculture paper shortened two air-pollutant chart names on import, so those two
    # need an explicit mapping or basename matching finds no source and the stale copy ships.
    # Both were stale for weeks for exactly that reason.
    ALIASES = {"air_trend.png": "air_trend_chart.png",
               "air_uncertainty.png": "air_uncertainty_distribution.png"}

    # Empty, and it should stay that way. The nowcasting paper's four ML figures - whose
    # generator writes into an uncommitted model directory - live in the companion repository
    # along with that paper. Every figure in this repo is regenerable from outputs/, which is
    # the property that makes this check worth running at all.
    UNSOURCED_BY_DESIGN = set()

    def test_no_caption_contains_a_blank_line(self):
        r"""A blank line inside \caption{} ends the paragraph mid-argument and LaTeX stops
        with "Paragraph ended before \caption@prepareanchor was complete".

        Two long captions written in this round did exactly that, and the manuscript did not
        compile for two days without anything failing: the test suite reads .tex as text, and
        the only check that would have noticed - the shipped-PDF freshness guard - was already
        failing for the ordinary reason that the sources were newer. A second red light on an
        already-red lamp tells no one anything, so the syntax is checked directly.
        """
        offenders = []
        for doc, root, _cls, mainname in MANUSCRIPTS:
            for path in _inputs_of(_main_tex(root, mainname), root):
                with open(path, encoding="utf-8") as f:
                    text = f.read()
                pos = 0
                while True:
                    start = text.find("\\caption{", pos)
                    if start < 0:
                        break
                    depth, i = 0, start + len("\\caption")
                    while i < len(text):
                        if text[i] == "{":
                            depth += 1
                        elif text[i] == "}":
                            depth -= 1
                            if depth == 0:
                                break
                        i += 1
                    body = text[start:i]
                    if re.search(r"\n[ \t]*\n", body):
                        line = text[:start].count("\n") + 1
                        offenders.append("%s: %s:%d"
                                         % (doc, os.path.basename(path), line))
                    pos = i + 1
        self.assertFalse(offenders,
                         "blank line inside a caption -- the document will not compile:\n  "
                         + "\n  ".join(offenders))

    def test_every_declared_figure_source_still_exists(self):
        """The other half of currency: a figure that stopped being DRAWN is not stale, it is
        absent, and comparing it against a source it no longer has cannot see that.

        This is not hypothetical. The figure tables named their sources with the year in the
        filename - waste_by_stream_2023.csv, transport_fuel_2022.csv - and when every sector
        moved onto FY2023-24 the engine began writing _2024 files. The reader returned None,
        the drawing functions returned None, outputs/figures/ kept the PNGs it already had,
        and the currency test above compared each manuscript's stale copy against the equally
        stale output and found them identical. Seven declarations were dead; the transport and
        waste manuscripts shipped pre-harmonisation figures for two rounds.

        resolve() now raises instead of returning None, and this asserts every declaration
        resolves - including the ones no figure in any current manuscript happens to use.
        """
        from pkinv.report import figures as F
        declared = set()
        for value in list(F.SECTOR_FILES.values()):
            declared.update(x for x in value if x)
        declared.update(F.TOTALS_FILES.values())
        declared.update(F.AIR_FILES.values())
        declared.update(v[0] for v in F.ACTIVITY_FILES.values())
        self.assertGreater(len(declared), 20, "the declaration tables did not load")
        dead = []
        for name in sorted(declared):
            try:
                F.resolve(name)
            except F.MissingOutput as exc:
                dead.append(str(exc))
        self.assertFalse(dead, "figure sources that no longer exist:\n  " + "\n  ".join(dead))

    def test_the_air_beta_table_prints_the_assurance_the_figure_draws(self):
        """The manuscript's beta table and the PM figure classify the same seven layers, and
        one of them is hand-written LaTeX. Whichever drifts, a reader is told two things."""
        from pkinv.report import figures as F
        # The table moved to the national supplement when the air layer became a labelled
        # beta; the check follows it rather than passing vacuously on a section that no
        # longer contains it.
        with open(_doc_path("national-supplement", "supplement.tex"), encoding="utf-8") as f:
            text = f.read()
        table = text[:text.index("label{tab:airbeta}")]
        for sector, assurance in sorted(F.AIR_ASSURANCE.items()):
            self.assertIn(assurance, table,
                          "the beta table does not carry %s's class %r"
                          % (sector, assurance))

    def test_no_shipped_figure_predates_its_source(self):
        index = {}
        for dp, _, files in os.walk(OUT):
            for fn in files:
                if fn.endswith(".png"):
                    index.setdefault(fn, os.path.join(dp, fn))
        stale, unsourced, checked = [], [], 0
        # EVERY manuscript, not just one. Nine documents had no figure check at all until
        # this loop replaced a hardcoded single-directory path.
        for doc, root, _cls, mainname in MANUSCRIPTS:
            figs = os.path.join(root, "figures")
            if not os.path.isdir(figs):
                continue
            for fn in sorted(os.listdir(figs)):
                if not fn.endswith(".png"):
                    continue
                checked += 1
                src = index.get(self.ALIASES.get(fn, fn))
                if src is None:
                    if fn not in self.UNSOURCED_BY_DESIGN:
                        unsourced.append("%s: %s" % (doc, fn))
                    continue
                # Compare CONTENT, not timestamps: a figure regenerated to an identical image is
                # not stale, and an mtime check would fail on it while a genuinely superseded
                # figure that happened to be touched would pass. Content is what matters.
                if not filecmp.cmp(src, os.path.join(figs, fn), shallow=False):
                    stale.append("%s: %s differs from %s"
                                 % (doc, fn, os.path.relpath(src, ROOT)))
        self.assertGreater(checked, 0, "no manuscript figures found -- the walk is broken")
        msg = []
        if stale:
            msg.append("figures older than their source (run scripts/sync_figures.py):\n  "
                       + "\n  ".join(stale))
        if unsourced:
            msg.append("figures with no output source -- add an alias if the paper renamed one:\n  "
                       + "\n  ".join(unsourced))
        self.assertFalse(msg, "\n\n".join(msg))


class TestEverySectorShipsWhatItComputes(unittest.TestCase):
    """The staleness guard, for every registered sector rather than two of them.

    Transport once shipped outputs a run behind its own engine - the manuscript, the
    committed CSVs and the anchors all agreed with each other and disagreed with the code
    by 0.18 Mt, because `make transport` had not been re-run after an edit landed. A
    per-sector version of that check existed for transport and waste only; this is the
    other eight, driven off the registry so a new sector is covered the day it registers.

    Two invariants per sector: the committed totals file equals a fresh in-process build,
    and it equals the national rollup's row for that sector. The second is the cheap
    cross-command check - those two files are written by different commands, so drift
    between them means a partial re-run shipped.

    The first invariant was, until the Round 8 rebuild, running on three sectors of nine.
    It looked for a row labelled TOTAL, six files do not carry one, and the absence was a
    `continue` rather than a failure. A guard whose coverage is decided by a naming
    accident, and which reports the same result either way, is the shape of defect the rest
    of this file exists to catch, so it is worth saying plainly that it was in here too.
    """

    # Sectors whose committed totals file is not named <sector>_totals_<YEAR>.csv, or
    # which do not write one at all. Listed rather than skipped silently.
    #
    # This map used to send fugitives to fugitives_totals_2020.csv, a vintage the build had
    # stopped writing when the sectors were harmonised onto one reporting period. The file
    # was still in outputs/ and still parsed, and it has no TOTAL row, so the check below
    # fell through to `continue` and the fugitives half of this guard did nothing at all -
    # a live test reading a dead artefact and passing. The vintage is retired and the entry
    # with it; NO_TOTAL_ROW now names the fall-through explicitly instead.
    TOTALS_FILE = {}
    # Agriculture's totals live in national_totals_2024.csv rather than an
    # agriculture_totals file; mapping it here brought the sector under the
    # fresh-build check after its paper spent a round riding five stale Aug-5
    # artifacts that an exemption by name had made invisible.
    TOTALS_FILE_EXTRA = {"agriculture": "national_totals_2024.csv"}
    # WHICH ROWS ARE THE INVENTORY. Six of the nine totals files carry no row labelled
    # TOTAL, and the check used to read one, so for six sectors it found nothing, hit
    # `continue`, and asserted precisely nothing. It reported passing all the same.
    #
    # Summing the file instead would be wrong in the other direction: these files print the
    # sector's reportable categories BESIDE its sensitivities, diagnostics and excluded
    # memo items - residential's configuration S, railways' road-factor diagnostic,
    # aviation's international LTO - and adding those in double-counts or imports an
    # excluded number. The rows that are the inventory are the ones the registry declares
    # as that sector's reporting categories, so that is what this sums. Nine sectors
    # reconcile on it; a sector that renamed a category without renaming it in the registry
    # would now fail here rather than quietly stop being checked.

    def _sectors(self):
        from pkinv.core import registry
        return registry.all_sectors()

    def test_shipped_sector_totals_equal_a_fresh_build(self):
        problems = []
        for sector in self._sectors():
            # rc15: the fiscal-start sectors' files carry the PERIOD suffix, the
            # rest still carry their (unambiguous, fiscal-end) year - so ask the
            # period module for the name rather than assuming either form.
            from pkinv.core import period as _period
            default = "%s_totals_%s.csv" % (
                sector.NAME, _period.file_suffix(sector.YEAR, sector.YEAR_CONVENTION))
            if not os.path.exists(os.path.join(OUT, default)):
                default = "%s_totals_%d.csv" % (sector.NAME, sector.YEAR)
            fname = self.TOTALS_FILE_EXTRA.get(
                sector.NAME, self.TOTALS_FILE.get(sector.NAME, default))
            path = os.path.join(OUT, fname)
            if not os.path.exists(path):
                problems.append("%s: %s missing" % (sector.NAME, fname))
                continue
            comps = sector.build_components(sector.load_data())
            engine = sum(c["co2e_Mt_AR5"] for c in comps)
            declared = set(sector.CATEGORIES)
            matched = [r for r in _rows(fname)
                       if r.get("category") in declared and r.get("co2e_Mt_AR5")]
            if not matched:
                problems.append("%s: %s carries none of the sector's declared categories "
                                "(%s), so nothing here compares it against the engine"
                                % (sector.NAME, fname, sorted(declared)))
                continue
            shipped = sum(float(r["co2e_Mt_AR5"]) for r in matched)
            # national_totals prints category rows at 2 dp, so its sum can sit up
            # to half an ulp per row from the engine; the sector's own files are
            # written at full precision and keep the tight tolerance.
            tol = 0.02 if sector.NAME in self.TOTALS_FILE_EXTRA else 1e-4
            if abs(shipped - engine) > tol:
                problems.append("%s: shipped %.5f vs engine %.5f - run make %s"
                                % (sector.NAME, shipped, engine, sector.NAME))
        self.assertFalse(problems, "shipped sector outputs are stale:\n  "
                         + "\n  ".join(problems))

    def test_every_sector_matches_the_national_rollup(self):
        problems = []
        for sector in self._sectors():
            comps = sector.build_components(sector.load_data())
            engine = sum(c["co2e_Mt_AR5"] for c in comps)
            rolled = _sector(sector.NAME)
            if abs(rolled - engine) > 1e-4:
                problems.append("%s: rollup %.5f vs engine %.5f - run make national"
                                % (sector.NAME, rolled, engine))
        self.assertFalse(problems, "the national rollup disagrees with the engine:\n  "
                         + "\n  ".join(problems))

    def test_the_two_configurations_differ_only_in_residential(self):
        """S is a residential reading, so every other sector must be identical between
        the two rollups. If another sector moves, the configuration is leaking."""
        for sector in self._sectors():
            if sector.NAME == "residential":
                self.assertNotAlmostEqual(_sector(sector.NAME),
                                          _sector_alt(sector.NAME), places=3)
                continue
            self.assertAlmostEqual(_sector(sector.NAME), _sector_alt(sector.NAME),
                                   places=6, msg=sector.NAME)


class TestSectorRegistriesAgree(unittest.TestCase):
    """The sector list is written down in three places that never check each other.

    Makefile:SECTORS drives which papers compile, scripts/sync_figures.py:SECTORS drives
    which figure directories are synced, and this file's SECTORS drives DOCS and
    MANUSCRIPTS. Each loop is existence-guarded, so a directory that moves does not fail
    anything - `make sector-papers` prints "collected 1 PDFs" and exits 0, and the figure
    sync quietly covers one directory instead of ten. The sector reports are about to be
    reorganised, and this is the test that makes that reorganisation loud.
    """

    def _makefile_sectors(self):
        with open(os.path.join(ROOT, "Makefile"), encoding="utf-8") as handle:
            for line in handle:
                if line.startswith("SECTORS"):
                    return tuple(line.split("=", 1)[1].split())
        raise AssertionError("Makefile has no SECTORS assignment")

    def _sync_figures_sectors(self):
        mod = _load_repo_script("sync_figures.py")
        return tuple(mod.SECTORS)

    def test_all_three_lists_agree(self):
        here, mk, sync = set(SECTORS), set(self._makefile_sectors()), set(self._sync_figures_sectors())
        self.assertEqual(here, mk,
                         "tests and Makefile disagree: %s" % (here ^ mk))
        self.assertEqual(here, sync,
                         "tests and sync_figures disagree: %s" % (here ^ sync))

    def test_every_listed_sector_has_a_document_on_disk(self):
        missing = [s for s in SECTORS
                   if not os.path.isfile(os.path.join(ROOT, "papers", s, "paper.tex"))]
        self.assertFalse(missing,
                         "listed but absent: %s - if these moved, update SECTORS in "
                         "tests/paper_numbers/, scripts/sync_figures.py and the "
                         "Makefile together" % missing)

    def test_no_document_on_disk_is_unlisted(self):
        import glob
        on_disk = {os.path.basename(os.path.dirname(p))
                   for p in glob.glob(os.path.join(ROOT, "papers", "*", "paper.tex"))}
        self.assertFalse(on_disk - set(SECTORS),
                         "present but unlisted, so untested: %s" % (on_disk - set(SECTORS)))


class TestReleaseIntegrity(unittest.TestCase):
    """One release, one year set, one metric, one configuration.

    A reviewer found three national totals in simultaneous circulation - 454.48, 461 and
    455.14 - across the README, the national abstract and its results table. None was a
    calculation error; they were three vintages quoted in places nothing read. Every test
    here exists because some artefact was allowed to state a number that no code checked.
    """

    def test_stamped_products_carry_the_current_version(self):
        """The rc10 clean-room run caught the source-stream ledger stamped 1.0.0rc3 and
        the facility registry stamped 1.0.0rc8 inside an rc9 tree: version bumps had
        outrun their writers for six releases and nothing compared the stamp to
        pkinv.__version__. Every shipped product with a release_version column must
        stamp the version it ships in."""
        import pkinv
        for name in ("pakemis_source_streams.csv", "pakemis_facility_registry.csv"):
            rows = _rows(name)
            stamps = {r["release_version"] for r in rows}
            self.assertEqual(stamps, {pkinv.__version__},
                             "%s stamps %s inside a %s tree - its writer was not "
                             "rerun after the version bump"
                             % (name, sorted(stamps), pkinv.__version__))

    def test_configuration_S_is_introduced_with_its_unresolved_residual(self):
        """The rename that must not revert site by site (the rc3 review's section 4).

        The survey reading (configuration S through rc66, THE REFERENCE since rc67) is
        not a closed inventory reading: it is a household-demand observation, and most
        of the dung agriculture diverts has no observed destination under it. Every
        machine-readable site that INTRODUCES it must say so and point at the fate
        account. A rename applied in one site and reverted in another is the
        multiple-vintages defect wearing words instead of numbers.
        """
        from pkinv.report import national_rollup
        note = national_rollup.CONFIG_NOTE["survey"]
        for token in ("household demand", "no observed destination",
                      "residential_dung_ledger", "national_dung_variants"):
            self.assertIn(token, note, "CONFIG_NOTE lost %r" % token)

        dung_axis = next(r for r in _data_rows_nocomment("scenarios.csv")
                         if r["axis"] == "residential dung basis")
        # rc67 wording: the axis note says the rest of the supply "has no observed fate"
        # and names the per-year product that prices each destination
        self.assertIn("no observed fate", dung_axis["note"])
        self.assertIn("pakemis_dung_fate_by_year", dung_axis["note"])

        manifest = json.loads(open(os.path.join(ROOT, "outputs",
                                                "release_manifest.json"),
                                   encoding="utf-8").read())
        self.assertIn("no observed destination",
                      manifest["national_totals"]["note"],
                      "the manifest introduces S without its open question")

        readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
        self.assertIn("no observed destination", readme,
                      "the README's headline introduces S without its open question")

        # rc67, the other half of the same rename: configuration L is introduced as what
        # it is, a destination assumption for the diverted dung, and never as a reading
        # of household use or as the baseline.
        ledger_note = national_rollup.CONFIG_NOTE["ledger"]
        self.assertIn("destination assumption", ledger_note,
                      "CONFIG_NOTE introduces configuration L without saying what it is")
        self.assertIn("destination assumption", dung_axis["note"])
        self.assertTrue(dung_axis["setting"].startswith("survey"),
                        "the dung axis no longer names the survey as its reference")
        self.assertTrue(dung_axis["alternative"].startswith("ledger"),
                        "the dung axis no longer names the ledger as its alternative")

        # The national abstract introduces both in one sentence: the reference as the
        # household survey reading with its remainder unresolved, and L as the
        # destination assumption. "co-equal" was the rc66 wording for a pairing that no
        # longer holds, and a reverted abstract would carry it.
        abstract = " ".join(open(_doc_path("national", "00_abstract.tex"),
                                 encoding="utf-8").read().split())
        sentence = next((s for s in abstract.split(". ")
                         if "destination assumption~L" in s), "")
        self.assertTrue(sentence, "the abstract does not introduce configuration L as "
                                  "the destination assumption")
        for token in ("household survey", "unresolved"):
            self.assertIn(token, sentence,
                          "the abstract introduces the reference without %r" % token)
        self.assertNotIn("co-equal", abstract)
        self.assertNotIn("household-demand reading", abstract)

    def test_the_committed_release_artifacts_claim_a_clean_tree(self):
        """The rc3 release shipped every PDF with "Commit feb9fac (working tree
        modified)" in its provenance box: the manifest was regenerated mid-work and
        committed as-is, so the printed commit did not identify the tree that built the
        papers. The committed artifacts may never say that. The assertion reads HEAD's
        BLOBS, not the working tree, so the transient dirty state during the
        release-fixpoint dance (scripts/release_fixpoint.py) passes and only COMMITTING
        the defect fails."""
        import subprocess
        try:
            cover = subprocess.check_output(
                ["git", "show", "HEAD:paper_common/release_cover.tex"],
                cwd=ROOT, stderr=subprocess.DEVNULL).decode()
            manifest = json.loads(subprocess.check_output(
                ["git", "show", "HEAD:outputs/release_manifest.json"],
                cwd=ROOT, stderr=subprocess.DEVNULL))
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        self.assertNotIn("(working tree modified)", cover,
                         "the committed release cover admits a dirty build tree; run "
                         "make release-fixpoint and commit the regenerated artifacts")
        self.assertNotIn("\\texttt{uncommitted}", cover)
        self.assertFalse(manifest["git"]["tree_dirty"],
                         "the committed manifest was generated on a dirty tree")

    # WHY THERE IS NO TEST HERE FOR THE RECORD'S COMMIT ORDER, having briefly added one.
    #
    # The defect is real: on 2026-10-05 a record taken against one artifacts commit was still
    # in the working tree when the next CONTENT commit ran `git add -A`, so it shipped inside
    # that content describing a tree two commits old - 3455 executed where the tree it shipped
    # with ran 3459. Nothing caught it, because the record is fixpoint-written and carries no
    # digest.
    #
    # A test in THIS suite cannot express it. The record is produced by running this suite on
    # the artifacts commit, and at that moment the committed record is necessarily the
    # PREVIOUS release's - it is the thing about to be replaced. So a test asserting "the
    # record's commit follows the manifest's" fails during every legitimate record, and the
    # record then captures its own failure. The first version did exactly that and wrote
    # FAILED into the artifact it was meant to protect.
    #
    # The property is about commit ORDER after the dance completes, which no test running
    # inside the recorded run can observe. It lives in scripts/check_release_sequence.py,
    # which the release path runs after the record is committed.

    def test_the_commit_the_artifacts_name_is_reachable(self):
        """THE ASSERTION THAT WAS MISSING, and what its absence cost.

        The release dance is content commit, then `make release-fixpoint`, then an
        artifacts-only commit, so the shipped cover names the CONTENT commit. Recovering
        from a mistake by amending the artifacts commit breaks that: the fixpoint had
        already recorded the pre-amend hash, and the amend left that hash on no branch.
        1.0.0rc59 shipped a cover and a manifest naming b719b0170680, which
        `git branch --contains` could not place anywhere - so a reader who cloned the
        repository could not resolve the commit the papers print.

        Every one of the other assertions here passed, because they compare the manifest
        against HEAD's CONTENT by hash and never ask whether the commit it names still
        exists. Reachability from HEAD is the property that was violated, and it holds at
        every stage of the dance, which is why it is the one asserted.
        """
        import subprocess
        try:
            manifest = json.loads(subprocess.check_output(
                ["git", "show", "HEAD:outputs/release_manifest.json"],
                cwd=ROOT, stderr=subprocess.DEVNULL))
            cover = subprocess.check_output(
                ["git", "show", "HEAD:paper_common/release_cover.tex"],
                cwd=ROOT, stderr=subprocess.DEVNULL).decode()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        named = manifest["git"]["describes_commit"]
        reachable = subprocess.run(
            ["git", "merge-base", "--is-ancestor", named, "HEAD"],
            cwd=ROOT, stderr=subprocess.DEVNULL).returncode == 0
        self.assertTrue(reachable,
                        "the committed manifest names %s, which is not an ancestor of HEAD - "
                        "an amended or discarded commit. Re-run make release-fixpoint on the "
                        "clean content commit and commit the artifacts it produces." % named[:12])
        # The cover prints the same commit in short form; a disagreement means one of the two
        # was regenerated without the other.
        self.assertIn(named[:12], cover,
                      "the cover does not print the commit the manifest names (%s)" % named[:12])

    def test_the_committed_manifest_describes_the_committed_content(self):
        """THE ASSERTION NOTHING MADE, and the rc15/rc16 defect is what its absence cost.

        Every shipped PDF declared release 1.0.0rc15, commit 53f307c and manifest digest
        706f8e90a2bcea6e while three commits of content had landed behind them: the
        manifest at HEAD was byte-identical to the rc15 artifact, and regenerating it
        moved 191 source hashes and every Monte-Carlo quantile. Four guards were blind at
        once. The manifest test compared the ON-DISK file to a fresh build, but CI
        regenerates the manifest before the tests run, so it compared fresh to fresh;
        release_manifest.json was not in CI's git-diff list; the commit and digest lines
        are excluded from the cover's --check because they move on every push; and PDF
        staleness only watched sections/ inputs, so a regenerated cover never marked a
        paper stale. Between them nothing asked whether the manifest COMMITTED at HEAD
        was generated from HEAD's CONTENT.

        This reads HEAD's blob, like the clean-tree check above, so the transient dirty
        state of the release-fixpoint dance passes and only committing a stale manifest
        fails. The git block itself is dropped: describes_commit is by construction the
        PARENT of the commit carrying the manifest, and tree_dirty is environmental -
        both are covered by the clean-tree assertion instead."""
        import subprocess
        from pkinv.report import release_manifest as rm
        try:
            committed = json.loads(subprocess.check_output(
                ["git", "show", "HEAD:outputs/release_manifest.json"],
                cwd=ROOT, stderr=subprocess.DEVNULL))
            top = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=ROOT,
                                          stderr=subprocess.DEVNULL).decode().strip()
        except (OSError, subprocess.CalledProcessError):
            self.skipTest("not a git checkout")
        # rc42: a validation package built inside the repository (dist/) is not a checkout of
        # its own - git walks up to the parent and this compares a vault-less package tree
        # against the release's manifest. Extracted anywhere else the package skips above;
        # inside the repository it must skip for the same reason, not fail by location.
        if os.path.realpath(top) != os.path.realpath(ROOT):
            self.skipTest("this tree is not its own git checkout (a package inside another "
                          "checkout); the committed manifest belongs to the parent")
        fresh = rm.build()
        committed.pop("git", None)
        fresh.pop("git", None)
        if committed == fresh:
            return
        drift = sorted(k for k in set(committed) | set(fresh)
                       if committed.get(k) != fresh.get(k))
        detail = []
        if "sources" in drift:
            was = {r["path"]: r["sha256"] for r in committed.get("sources", [])}
            now = {r["path"]: r["sha256"] for r in fresh.get("sources", [])}
            added = sorted(set(now) - set(was))
            changed = sorted(p for p in set(was) & set(now) if was[p] != now[p])
            detail.append("sources: %d added, %d re-hashed (%s)"
                          % (len(added), len(changed),
                             "; ".join((added + changed)[:4])))
        self.fail(
            "the committed release manifest does not describe the committed content - "
            "blocks that differ: %s. %s Run: commit your content, then "
            "make release-fixpoint, then commit the regenerated artifacts."
            % (", ".join(drift), " ".join(detail)))

    def test_every_manuscript_reference_resolves(self):
        """The railways paper shipped a literal "Section ??" on page 4: \\ref named a
        label no file defines, LaTeX warned in a log no test reads, and CI builds only
        two of the eleven documents so the log-based route is absent exactly where it is
        needed. Static check instead: every compile unit's refs against its labels, no
        build required."""
        ref_re = re.compile(r"\\(?:ref|cref|Cref|autoref|eqref)\{([^}]*)\}")
        label_re = re.compile(r"\\label\{([^}]*)\}")

        def _strip_comments(text):
            return "\n".join(re.sub(r"(?<!\\)%.*", "", line) for line in
                             text.splitlines())

        roots = sorted({root for _doc, root, _cls, _main in MANUSCRIPTS})
        problems = []
        for root in roots:
            for main in sorted(glob.glob(os.path.join(root, "*.tex"))):
                with open(main, encoding="utf-8") as handle:
                    if "\\documentclass" not in handle.read():
                        continue
                labels, refs = set(), []
                for path in [main] + _inputs_of(main, root):
                    if not os.path.exists(path):
                        continue
                    text = _strip_comments(open(path, encoding="utf-8").read())
                    labels.update(label_re.findall(text))
                    for match in ref_re.finditer(text):
                        for target in match.group(1).split(","):
                            refs.append((os.path.relpath(path, ROOT), target.strip()))
                # xr: a unit that declares \externaldocument[prefix][nocite]{other} resolves the
                # other unit's labels (prefixed) from its .aux - the ESSD article and its
                # supplement do this for the fragments that moved between them, until the
                # prose pass replaces those \ref with textual pointers.
                main_text = _strip_comments(open(main, encoding="utf-8").read())
                for prefix, other in re.findall(
                        r"\\externaldocument(?:\[([^\]]*)\])?(?:\[[^\]]*\])?\{([^}]+)\}", main_text):
                    other_main = asset_path(root, other + ".tex")
                    if not os.path.exists(other_main):
                        continue
                    for path in [other_main] + _inputs_of(other_main, root):
                        text = _strip_comments(open(path, encoding="utf-8").read())
                        labels.update(prefix + l for l in label_re.findall(text))
                for source, target in refs:
                    if target and target not in labels:
                        problems.append("%s -> %s (unit %s)"
                                        % (source, target,
                                           os.path.relpath(main, ROOT)))
        self.assertFalse(problems, "references that will print as ??:\n  "
                                   + "\n  ".join(sorted(set(problems))))

    def test_the_national_abstract_is_compact(self):
        """The rc2 abstract ran to 538 words and tried to contain the whole paper:
        architecture, totals, scenarios, closures, the factor trap, the uncertainty
        redesign, Sobol attribution, monthly classes, structural alternatives,
        completeness and the release string. A flagship data-paper abstract carries the
        gap, the product, the construction, the headline, validation, uncertainty,
        completeness and access -- and stops. Same word formula as the fugitives guard."""
        text = open(_doc_path("national", "00_abstract.tex"), encoding="utf-8").read()
        plain = re.sub(r"\\[A-Za-z]+(?:\[[^]]*\])?", " ", text)
        words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*", plain)
        self.assertGreaterEqual(len(words), 230, "the abstract has been hollowed out")
        self.assertLessEqual(len(words), 310,
                             "%d words -- the abstract is reabsorbing the paper"
                             % len(words))

    def test_counts_spelled_out_in_words_match_the_registry(self):
        """Numbers written as words are invisible to every numeric check in this file.

        "Five of the nine sector modules burn fossil fuel" opened the paper's central
        finding and was wrong twice: the registry holds ten modules, and six of them report
        CO2 under a 1.A code once industrial fuel combustion was added. No claim, no table
        and no coverage test could see it, because it contains no digits.
        """
        from pkinv.core import registry
        from pkinv.report import uncertainty_all
        words = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six",
                 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve",
                 17: "seventeen", 18: "eighteen", 19: "nineteen", 20: "twenty",
                 21: "twenty-one", 22: "twenty-two", 23: "twenty-three", 24: "twenty-four", 25: "twenty-five"}
        sectors = len(registry.all_sectors())
        fuel = len(uncertainty_all.FUEL_SECTORS)

        text = " ".join(open(_doc_path("national", "07_uncertainty.tex"),
                             encoding="utf-8").read().split())
        expected = "%s of the %s sector modules report" % (
            words[fuel].capitalize(), words[sectors])
        self.assertIn(expected, text,
                      "the correlation section's module counts disagree with the registry "
                      "(%d fuel-combustion of %d sectors)" % (fuel, sectors))

        # The same count appears 130 lines later in the bound-not-estimate paragraph, and
        # said "the five modules" for a full release while line 29 said six: this test
        # checked one sentence and the defect lived in the other.
        self.assertIn("the %s modules do share an IPCC default" % words[fuel], text,
                      "the bound-not-estimate paragraph's module count disagrees with the "
                      "registry (%d fuel-combustion modules)" % fuel)

        # The conclusion's closure taxonomy, in words, against the closure registry: how
        # many of the four transfers actually cross a module is a derived count, and the
        # sentence that used to sit here called all four cross-sector.
        conclusion = " ".join(open(_doc_path("national", "13_conclusion.tex"),
                                   encoding="utf-8").read().split())
        self.assertIn("%s are transfers between modules"
                      % words[int(_closures_crossing_modules())], conclusion,
                      "the conclusion's cross-module closure count disagrees with the "
                      "registry (%d of %d)"
                      % (int(_closures_crossing_modules()), int(_closure_count())))

        for section in ("00_abstract.tex", "01_introduction.tex", "12_limitations.tex"):
            prose = " ".join(open(_doc_path("national", section),
                                  encoding="utf-8").read().split())
            self.assertNotIn("nine sector", prose, section)

        # The release record says it too, in words, and it said "seven sectors" for several
        # releases after there were ten.
        record = " ".join(open(_doc_path("release-record", "qa_qc.md"),
                               encoding="utf-8").read().split())
        self.assertIn("test functions across %s sectors" % words[sectors], record,
                      "docs/qa_qc.md's sector count disagrees with the registry (%d)"
                      % sectors)

        # The abstract's spelled-out CATEGORY count, for the same reason. It moved from
        # nineteen to eighteen when the key-category screen was rebased onto IPCC categories,
        # and a word is invisible to every numeric check here.
        categories = len(_rows("national_key_categories.csv"))
        abstract = " ".join(open(_doc_path("national", "00_abstract.tex"),
                                 encoding="utf-8").read().split())
        self.assertIn("over %s IPCC" % words[categories], abstract,
                      "the abstract's spelled-out category count is not the %d the screen "
                      "reports" % categories)

    def test_prose_about_a_parameter_matches_that_parameter(self):
        """Numbers were anchored; the scientific status around them was not.

        The limitations section said firewood carried 60 percent activity uncertainty and
        that FAOSTAT was the only national quantity available, for a full release after the
        residential sector re-anchored on the HIES 2024-25 design-weighted estimate and cut
        the spread to 35 percent with FAOSTAT demoted to a named structural case. Every
        number in the paragraph passed its own check; the paragraph was still describing a
        superseded state of the evidence.

        Each entry pins a sentence to the parameter it is about, so the prose cannot drift
        away from the value it describes.
        """
        import csv as _csv
        params = {}
        with open(asset_path(ROOT, "data", "residential_params.csv"),
                  newline="", encoding="utf-8") as handle:
            for row in _csv.DictReader(handle):
                params[row["param"]] = row["value"]

        text = " ".join(open(_doc_path("national", "12_limitations.tex"),
                             encoding="utf-8").read().split())
        wood = params["activity_uncert_woodfuel"]
        self.assertIn(r"reported at \SI{%s}{\percent}" % wood, text,
                      "the firewood limitation does not quote activity_uncert_woodfuel")
        self.assertNotIn("the only national quantity available is FAOSTAT", text,
                         "FAOSTAT is a structural case now, not the firewood anchor")

        arch = " ".join(open(_doc_path("national", "03_architecture.tex"),
                             encoding="utf-8").read().split())
        self.assertIn(r"$-\SI{%s}{\percent}$" % wood, arch,
                      "the architecture section quotes a superseded firewood sensitivity")

    def test_every_described_closure_has_a_live_relay(self):
        """A closure cannot outlive the code that performs it.

        The abstract and Section 4 described railway diesel being carved out of the road
        control total for a full release after transport was re-anchored on OCAC customer
        classes and stopped doing it - fuel_ledger.py says in as many words that Railways is
        its own row and no deduction applies. The prose described an architecture that no
        longer existed, and nothing could tell, because a closure is a claim about code
        rather than a number.

        Each entry names the section that describes the closure and the accessor that must
        exist and return a positive quantity for that description to be true.
        """
        text = open(_doc_path("national", "04_closures.tex"), encoding="utf-8").read()
        problems = []
        for name, label, _producer, _consumer, _pf, _pt, accessor in CLOSURES:
            if "\\label{%s}" % label not in text:
                problems.append("%s: no subsection labelled %s" % (name, label))
                continue
            try:
                value = accessor()
            except Exception as exc:                       # noqa: BLE001 - report, not raise
                problems.append("%s: relay accessor failed (%s)" % (name, exc))
                continue
            if not value > 0:
                problems.append("%s: relay returns %r" % (name, value))
        self.assertFalse(problems, "described closures without live code:\n  "
                                   + "\n  ".join(problems))

    def test_the_closure_registry_is_not_a_constant(self):
        """The count the manuscript prints must be computed from the registry, and the
        registry must be able to disagree with the manuscript.

        `_closures_crossing_modules` was `return 2.0` for three rounds: a literal behind a
        lambda, registered in CLAIMS as though it were a metric. It could not have caught a
        closure that changed ends, because nothing about it depended on the closures. This
        asserts the two properties that make the derived version load-bearing: the answer is
        strictly between "none cross" and "all cross" -- so neither degenerate reading passes
        silently -- and every module named is one the engine actually registers, so a rename
        breaks the registry rather than quietly re-partitioning the count.
        """
        crossing = _closures_crossing_modules()
        self.assertGreater(crossing, 0, "no closure crosses a module -- the registry is "
                                        "degenerate and the count means nothing")
        self.assertLess(crossing, _closure_count(),
                        "every closure crosses a module, so 'cross-sector' would be the "
                        "right name after all -- check the registry before the prose")
        from pkinv.core import registry
        known = {s.NAME for s in registry.all_sectors()}
        for name, _label, producer, consumer, phys_from, phys_to, _accessor in CLOSURES:
            for role, module in (("producer", producer), ("consumer", consumer),
                                 ("physical_from", phys_from), ("physical_to", phys_to)):
                self.assertIn(module, known,
                              "%s names %s %r, which is not a registered sector"
                              % (name, role, module))
            # A closure crosses a module in the software direction exactly when it crosses
            # one physically: the ENDS may swap (generator petrol) but the kind may not.
            self.assertEqual(producer != consumer, phys_from != phys_to,
                             "%s: the software dependency and the physical transfer "
                             "disagree about whether a module boundary is crossed" % name)

    # The closure-table row that shipped in rc2, stored so the arrow guard below is proven
    # against the defect it was written for: the software arrow printed under a column whose
    # definition is the physical one.
    RC2_GENERATOR_ROW = ("Household-generator petrol, carved out of the road control & "
                         "Cross-module transfer & Residential $\\rightarrow$ Transport")

    def test_the_printed_closure_arrows_are_the_physical_direction(self):
        """The table's own definition -- "a quantity leaves one sector's books and must
        arrive on another's" -- fixes what an arrow in it means. The generator-petrol row
        printed Residential -> Transport, which is the direction of the function call:
        residential computes the estimate and transport subtracts it. The petrol itself
        moves the other way, out of transport's road control and onto residential's books.
        Nothing compared the printed arrow against anything, so the two conventions sat in
        one column, one per row.
        """
        text = " ".join(open(_doc_path("national", "04_closures.tex"),
                             encoding="utf-8").read().split())
        arrow = r"([A-Z][a-z]+)\s*\$\\rightarrow\$\s*([A-Z][a-z]+)"
        checked = 0
        for name, _label, producer, consumer, phys_from, phys_to, _a in CLOSURES:
            if producer == consumer:
                continue
            prefix = {"dung-cake nitrogen": "Dung-cake nitrogen",
                      "household-generator petrol": "Household-generator petrol"}[name]
            m = re.search(re.escape(prefix) + r"[^&]*&[^&]*&\s*" + arrow, text)
            self.assertTrue(m, "%s: no arrow row found in tab:closurekinds" % name)
            self.assertEqual((m.group(1).lower(), m.group(2).lower()),
                             (phys_from, phys_to),
                             "%s: the printed arrow is not the physical direction" % name)
            checked += 1
        self.assertEqual(checked, 2, "the cross-module rows the guard exists for are gone")
        # The stored rc2 row must fail the same comparison, or the guard has drifted off
        # the defect it exists to catch.
        m = re.search(arrow, self.RC2_GENERATOR_ROW)
        self.assertTrue(m)
        self.assertNotEqual((m.group(1).lower(), m.group(2).lower()),
                            ("transport", "residential"),
                            "the stored rc2 row no longer demonstrates the defect")

    def test_no_document_still_describes_the_retired_rail_closure(self):
        """The specific regression, checked in EVERY manuscript rather than in one.

        Railways is its own OCAC customer-class row, so there is nothing to carve out of the
        road control. The national paper was corrected when the re-anchoring landed; the
        railways report was not, and went on presenting the deduction as a principal
        contribution and as a numbered method subsection for two more rounds. The check read
        two sections of one document, so it could not have noticed. It reads all of them now.
        """
        # Widened from three literal phrases to a pattern family after the railways
        # paper spent two more rounds presenting the closure as a live deliverable in
        # five sections the literals never matched. Each pattern stores the sentence
        # it was written against as a positive control; honest HISTORICAL descriptions
        # (the methods section's record of why the deduction was retired) deliberately
        # do not match any of them.
        family = (
            (r"of railway diesel carved out",
             "with 112 kt of railway diesel carved out of the road control"),
            (r"road transport deducts this sector's diesel",
             "road transport deducts this sector's diesel, litre for litre"),
            (r"The road sector now subtracts this sector's diesel",
             "The road sector now subtracts this sector's diesel from its control"),
            (r"exact diesel closure against road",
             "a parametric-plus-structural uncertainty system; an exact "
             "diesel closure against road transport; and a route-constrained"),
            (r"boundar(?:y|ies) (?:it|they) close",
             "because the boundary it closes against road transport is worth roughly "
             "a third of a megatonne"),
            (r"closures they carry",
             "Small categories and the closures they carry"),
            (r"road-transport closure of Section",
             "The road-transport closure of Section~\\ref{sec:closure} is checked "
             "from the other side as well"),
            (r"road control total is strictly less",
             "that the road control total is strictly less than its gross value"),
            (r"Railways is worth\s+about a third of a megatonne to road",
             "Railways is worth about a third of a megatonne to road transport, "
             "because the national diesel figure covers both"),
        )
        offenders = []
        for pattern, example in family:
            self.assertRegex(" ".join(example.split()), pattern,
                             "positive control no longer matches: %s" % pattern)
        for doc, root, _cls, mainname in MANUSCRIPTS:
            for path in _inputs_of(_main_tex(root, mainname), root):
                flat = " ".join(open(path, encoding="utf-8").read().split())
                for pattern, _example in family:
                    if re.search(pattern, flat):
                        offenders.append("%s: %s still matches %r"
                                         % (doc, os.path.basename(path), pattern))
        self.assertFalse(offenders,
                         "the retired rail-diesel deduction is still described:\n  "
                         + "\n  ".join(offenders))

    def test_every_technical_report_carries_the_release_it_documents(self):
        """Nine reports, one generated provenance block, and a check that they all input it.

        A printed sector report said nothing about which release it described, which is how
        the transport and waste papers could ship pre-harmonisation figures beside a current
        national manuscript without contradiction being visible on the page. The block is
        generated from outputs/release_manifest.json; this asserts it is current and that
        every report actually carries it.
        """
        mod = _load_repo_script("make_release_cover.py")
        cover_path = os.path.join(ROOT, "paper_common", "release_cover.tex")
        with open(cover_path, encoding="utf-8") as handle:
            self.assertEqual(mod._stable(handle.read()), mod._stable(mod.render()),
                             "the release cover block is stale; run "
                             "python3 scripts/make_release_cover.py")
        missing = []
        for doc, root, _cls, mainname in MANUSCRIPTS:
            if root == PAPER_NATIONAL_MAIN and doc == "national":
                continue           # the submission, not a technical report
            with open(_main_tex(root, mainname), encoding="utf-8") as handle:
                if "\\ReleaseCover" not in handle.read():
                    missing.append(doc)
        self.assertFalse(missing, "technical reports with no release block: %s"
                         % ", ".join(missing))

    def test_the_release_block_states_the_period_the_manifest_records(self):
        """The block is generated, so it cannot disagree with the manifest by construction -
        but only if what it prints is READ from the manifest rather than formatted from
        something else. This asserts the printed period is the manifest's, which is the field
        a technical report most needs to be right about: it is how a reader knows whether the
        document in front of them describes the run the national paper describes."""
        import json
        mod = _load_repo_script("make_release_cover.py")
        with open(os.path.join(OUT, "release_manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        rendered = mod.render()
        self.assertIn(manifest["reporting_period"]["label"], rendered)
        self.assertIn(manifest["reporting_period"]["start"], rendered)
        self.assertIn(manifest["reporting_period"]["end"], rendered)
        self.assertIn(manifest["version"], rendered)
        self.assertIn("%.2f" % manifest["national_totals"]["L"]["co2e_Mt_AR5"], rendered)
        self.assertIn("%.2f" % manifest["national_totals"]["S"]["co2e_Mt_AR5"], rendered)

    def test_every_distributed_pdf_is_newer_than_its_sources(self):
        """papers/pdf/ is what a reader actually downloads, and it is version-controlled,
        so a stale file there ships.

        The national manuscript's Makefile target compiled in place and never copied, so
        papers/pdf/national_paper.pdf was left at whatever an earlier manual copy had put
        there while every test passed against the source. The same directory had already
        handed a reviewer a README quoting superseded sector totals. Nothing in the suite
        could see either, because both tests read the source rather than the artefact.
        """
        # The national supplement is a second document in the same directory, so it needs its
        # own shipped name and its own source list; taking paper_national.tex's would compare
        # the supplement's PDF against the paper's sections and pass on the wrong evidence.
        shipped_name = {"national": "national_paper.pdf",
                        "national-supplement": "national_supplement.pdf"}
        shipped_name.update({"%s-supplement" % n: "%s_supplement.pdf" % n
                             for n in ("agriculture", "aviation", "fugitives",
                                       "railways", "transport")})
        stale = []
        for name, root, _cls, mainname in MANUSCRIPTS:
            shipped = os.path.join(ROOT, "papers", "pdf",
                                   shipped_name.get(name, "%s_paper.pdf" % name))
            if not os.path.exists(shipped):
                stale.append("%s: no PDF in papers/pdf/" % name)
                continue
            built = os.path.getmtime(shipped)
            main = _main_tex(root, mainname)
            texts = [main] + _inputs_of(main, root)
            for source in texts + _figures_of(texts, root):
                if os.path.exists(source) and os.path.getmtime(source) > built:
                    stale.append("%s: %s is newer than the shipped PDF"
                                 % (name, os.path.relpath(source, ROOT)))
                    break
        # The check above is only as good as the source list it walks, and a resolver that
        # quietly matched nothing would make it pass forever. Every manuscript in this
        # repository draws figures, so an empty list is a broken resolver, not a plain paper.
        for name, root, _cls, mainname in MANUSCRIPTS:
            main = _main_tex(root, mainname)
            texts = [main] + _inputs_of(main, root)
            if not any("includegraphics" in open(x, encoding="utf-8").read()
                       for x in texts if os.path.exists(x)):
                continue           # a supplement may legitimately draw no figures
            self.assertTrue(_figures_of(texts, root),
                            "%s resolved no figures - the staleness check is walking an "
                            "empty source list" % name)
        self.assertFalse(stale, "shipped PDFs are stale; run make papers:\n  "
                                + "\n  ".join(stale))

    def test_the_readme_prose_outside_the_generated_blocks_is_current(self):
        """The generated blocks are checked by regeneration; the PROSE around them is not,
        and it quotes the same quantities. Both READMEs were left describing industrial
        combustion as gas-only at 5.67 Mt with 33 Mt outstanding after the liquid fuels
        moved it to 9.07 and 29 - the generated-block check passed throughout, because the
        stale numbers were in sentences no generator owns.
        """
        covered = sum(_sector(s) for s in ("industry",)) + 5.549      # + captive gas (1A2, net since rc19)
        edgar = _bench("EDGAR", "1A2 (all estimated)", "benchmark_Mt_co2e")
        expected = {
            "1A2 covered": "%.1f" % covered,
            "1A2 remaining": "%.0f" % round(edgar - covered),
            "industry sector": "%.2f" % _sector("industry"),
        }
        root_readme = open(os.path.join(ROOT, "README.md"), encoding="utf-8").read()
        pdf_readme = open(os.path.join(ROOT, "papers", "pdf", "README.md"),
                          encoding="utf-8").read()
        self.assertIn("%s Mt of it" % expected["1A2 covered"], root_readme)
        self.assertIn("roughly %s Mt" % expected["1A2 remaining"], root_readme)
        self.assertIn("roughly %s Mt of industrial combustion" % expected["1A2 remaining"],
                      root_readme)
        self.assertIn("(1A2, %s Mt)" % expected["industry sector"], pdf_readme)

    def test_readme_generated_blocks_match_a_regeneration(self):
        """The README carried its own vintage for months, including a sector table whose
        rows summed to 448.80 against its own printed total of 454.48. Its numeric blocks
        are generated now, and this is the check that they are current."""
        mod = _load_repo_script("make_readme_tables.py")
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as handle:
            current = handle.read()
        self.assertEqual(current, mod.render(current),
                         "README generated blocks are stale; run "
                         "python3 scripts/make_readme_tables.py")
        # And the sector-paper index, which was hand-maintained and two rounds behind:
        # agriculture 221.22, waste 36.96, a residential PM figure from before the
        # configuration split, and a railways line advertising a retired carve-out.
        with open(os.path.join(ROOT, "papers", "pdf", "README.md"), encoding="utf-8") as h:
            pdf = h.read()
        self.assertEqual(pdf, mod.render(pdf, mod.PDF_BLOCKS),
                         "the sector-paper index is stale; run "
                         "python3 scripts/make_readme_tables.py")

    def test_the_readme_sector_table_sums_to_its_own_total(self):
        """The defect that made the old table self-evidently wrong, pinned directly."""
        rows = [r for r in _rows("national_all_sectors.csv") if r["sector"] != "TOTAL"]
        total = _sector("TOTAL")
        self.assertAlmostEqual(sum(float(r["co2e_Mt_AR5"]) for r in rows), total, places=4)

    def test_the_release_manifest_regenerates_identically(self):
        """Byte-equality apart from nothing: the manifest carries no timestamp precisely
        so that this test can be exact. If it drifts, an output moved without the release
        record moving with it."""
        from pkinv.report import release_manifest
        import json
        # rc42: the manifest hashes every source document; without the vault the documents
        # block cannot regenerate, so this is a documents-gate test inside a package. The
        # package's own reading layer (data/SOURCE_MANIFEST.csv and the other views under
        # data/) is subtracted from the sources block: it is the package's index, not content.
        from pkinv.core import documents
        require_documents(*sorted(p for p in documents.registered() if p.startswith("sources/")))
        with open(os.path.join(OUT, "release_manifest.json"), encoding="utf-8") as handle:
            shipped = json.load(handle)
        fresh = release_manifest.build()
        fresh.setdefault("schema", shipped.get("schema"))
        from _support import presentation_layer
        layer = presentation_layer()
        if layer:
            fresh["sources"] = [s for s in fresh["sources"] if s["path"] not in layer]
        # git state is environmental, not a property of the release contents
        for d in (shipped, fresh):
            d.pop("git", None)
        self.assertEqual(shipped, fresh,
                         "release_manifest.json is stale; run "
                         "python3 -m pkinv.report.release_manifest")

    def test_the_manifest_version_is_the_package_version(self):
        import json
        import pkinv
        with open(os.path.join(OUT, "release_manifest.json"), encoding="utf-8") as handle:
            shipped = json.load(handle)
        self.assertEqual(shipped["version"], pkinv.__version__)

    def test_every_national_headline_names_the_scenario_that_produced_it(self):
        """A national total quoted without saying what produced it is ambiguous.

        THIS GUARD WAS DEAD FOR THREE ROUNDS. It used to fire only on a total matching
        `\\SI{45x.xx}{\\mega\\tonne}` -- the vintage in circulation when it was written. Round 5
        harmonised the inventory to 448.00 and the pattern stopped matching anything, so the
        assertion body never ran again and the test reported passing while checking nothing.
        That is exactly the shape Round 8 found four times, in a new place: a guard whose
        TRIGGER is pinned to a superseded number goes quiet without failing.

        The trigger now comes from the engine, so it cannot go stale. It also asks for more
        than the old one did: a letter names one of the scenario's axes, so a whole-
        inventory total must name the scenario, not the letter.

        rc67 swapped the roles on the dung axis and the guard follows. The reference total
        is the survey reading's and must be beside REF_2023_24 itself: the word
        "configuration" no longer qualifies, because the only configuration these
        sections name by letter is now L, the alternative. And the alternative's total
        must travel with its name in the same sentence, so 450.20 can never be read as a
        second headline.
        """
        total = _sector("TOTAL")
        pattern = re.compile(r"\\SI\{%.2f\}\{\\mega\\tonne\}" % total)
        alt_total = _sector_alt("TOTAL")
        self.assertNotEqual("%.2f" % total, "%.2f" % alt_total,
                            "the two configurations print the same total; the guard "
                            "cannot tell the reference from configuration L")
        alt_pattern = re.compile(r"\\SI\{%.2f\}\{\\mega\\tonne\}" % alt_total)
        fired = alt_fired = 0
        for name in ("00_abstract.tex", "01_introduction.tex", "13_conclusion.tex",
                     "06_results.tex", "12_limitations.tex"):
            text = " ".join(open(_doc_path("national", name), encoding="utf-8").read().split())
            if pattern.search(text):
                fired += 1
                self.assertIn("REF\\_2023\\_24", text,
                              "%s quotes the national total without naming the scenario "
                              "that produced it" % name)
            for sentence in re.split(r"(?<=[.;])\s", text):
                if not alt_pattern.search(sentence):
                    continue
                alt_fired += 1
                self.assertTrue("configuration~L" in sentence
                                or "destination assumption~L" in sentence,
                                "%s quotes configuration L's total without naming it: %s"
                                % (name, sentence[:160]))
                self.assertNotIn("reference scenario", sentence,
                                 "%s puts configuration L's total beside the reference "
                                 "scenario's name" % name)
        self.assertGreater(fired, 0,
                           "no section quotes the national total as \\SI{%.2f}{\\mega\\tonne}"
                           " -- this guard has gone quiet the way its predecessor did" % total)
        self.assertGreater(alt_fired, 0,
                           "no section quotes configuration L's total as "
                           "\\SI{%.2f}{\\mega\\tonne} -- the second half of this guard has "
                           "gone quiet" % alt_total)

    def test_no_document_states_a_draw_count_the_engine_does_not_run(self):
        """The prose half of the figure-label defect.

        The axis label said 10,000 draws while the published run was 100,000 (fixed, and
        guarded in tests/test_figure_text.py). Three release documents said the same thing,
        and one attributed it to the NATIONAL run by name. Sector runs really do use other
        counts, so a flat ban would be wrong. Two things are checkable: a stated count must
        be one the engine somewhere runs, and a count attributed to the national run must be
        the national one.

        The permitted set is READ FROM THE SOURCE rather than listed here, so a sector that
        changes its draw count does not turn this guard into a liar.
        """
        from pkinv.report import uncertainty_all
        declared = set()
        for source in glob.glob(os.path.join(ROOT, "src", "pkinv", "**", "*.py"),
                                recursive=True):
            body = open(source, encoding="utf-8").read()
            declared.update(int(n) for n in re.findall(r"n_iter\s*=\s*(\d{3,})", body))
            declared.update(int(n) for n in re.findall(r"N_ITER\s*=\s*(\d{3,})", body))
        self.assertIn(uncertainty_all.NATIONAL_N_ITER, declared,
                      "the national draw count was not found in the source -- this sweep "
                      "would permit anything")

        pattern = re.compile(r"(?:\\num\{)?([\d][\d,]*)\}?\s*(?:seeded\s+)?"
                             r"(?:draw|iteration|realisation)", re.IGNORECASE)
        paths = sorted(glob.glob(os.path.join(ROOT, "docs", "*.md")))
        paths.append(os.path.join(ROOT, "README.md"))
        for _doc, root, _cls, mainname in MANUSCRIPTS:
            paths.extend(_inputs_of(_main_tex(root, mainname), root))
        found, problems = 0, []
        for path in sorted(set(p for p in paths if os.path.exists(p))):
            where = os.path.relpath(path, ROOT)
            national_document = where.startswith("docs") or where.startswith("paper_national")
            text = " ".join(open(path, encoding="utf-8").read().split())
            for match in pattern.finditer(text):
                count = int(match.group(1).replace(",", ""))
                if count < 100:              # "Approach 2 draws each component" is not a count
                    continue
                found += 1
                if count not in declared:
                    problems.append("%s: %s draws, which no run in the engine uses"
                                    % (where, match.group(1)))
                    continue
                lead = text[max(0, match.start() - 40):match.start()].lower()
                if national_document and "national" in lead \
                        and count != uncertainty_all.NATIONAL_N_ITER:
                    problems.append("%s: attributes %s draws to the national run, which runs "
                                    "at %s" % (where, match.group(1),
                                               uncertainty_all.NATIONAL_N_ITER))
        self.assertGreater(found, 5,
                           "only %d draw counts found across the documents -- the sweep has "
                           "stopped matching" % found)
        self.assertFalse(problems, "documents state draw counts the engine does not run:\n  "
                         + "\n  ".join(problems))

    def test_no_superseded_vintage_survives_anywhere(self):
        """The specific numbers that were in circulation from older releases. A grep is
        crude, but these are exact strings that should never reappear, and the round that
        removed them touched fifty sites by hand."""
        import glob
        banned = {
            "454.48": "the pre-transport-round national total",
            "455.19": "a rounding of the national total that never existed in an output",
            "461.4": "the pre-rebaseline residential PM2.5",
            "5180": "the pre-rebaseline residential CO",
            "\\num{79}": "the pre-expansion completeness row count",
            "\\num{63}": "an older completeness row count",
            # The thirteenth review's dead numbers and phrases.
            "-7.43": "a superseded trend run's lower bound, quoted as though "
                     "current for a full release",
            "117.33": "the same superseded run's upper bound",
            "168 structural": "the pre-feedstock-leg factorial count (224 since "
                              "rc17)",
            "will be published as scenario rows": "the class-composition cases "
                                                  "ship in the published table",
            # rc19's dead vintages: the gross-booking totals, retired when the
            # net-of-leakage booking became canonical. Full precision only -
            # the two-decimal forms survive legitimately as the gross
            # ALTERNATIVE view (448.00455 is one ulp below the old reference).
            "448.00456": "the pre-rc19 gross-booking national total L",
            "442.87788": "the pre-rc19 gross-booking survey total S",
            "57.99582": "the pre-rc19 gross-booking grid power total",
            "38.62717": "the pre-rc19 gross-booking plant-physical-coal member",
            "62.00975": "the pre-rc19 gross-booking with-K-Electric member",
            "gas\\_combustion\\_net\\_of\\_leakage":
                "the retired configuration id; the boundary inverted at rc19 "
                "and the named alternative is gross\\_delivered\\_gas\\_accounting",
        }
        # rc18: widened from paper_national+README to EVERY manuscript (via its
        # own \input graph) plus docs/*.md - the thirteenth review found a dead
        # count surviving in a sector supplement this sweep never read.
        paths = [os.path.join(ROOT, "README.md")]
        paths += glob.glob(os.path.join(ROOT, "docs", "*.md"))
        for _name, root, _cls, main_tex in MANUSCRIPTS:
            main_path = asset_path(root, main_tex)
            paths.append(main_path)
            paths += _inputs_of(main_path, root)
        problems = []
        for path in sorted(paths):
            text = open(path, encoding="utf-8").read()
            for token, why in banned.items():
                if token in text:
                    problems.append("%s: %r (%s)"
                                    % (os.path.basename(path), token, why))
        self.assertFalse(problems, "superseded vintages resurfaced:\n  "
                         + "\n  ".join(problems))

    def test_prose_claims_of_non_estimation_resolve_to_the_registry(self):
        """The class of error no numeric test can catch.

        The power paper said PM2.5 was 'not reported at all' while its own results section
        reported 30.9 kt; the national paper said power-sector pollutants were NE while the
        power paper had already retracted that diagnosis in the same words. Both survived
        because a sentence about coverage is not a number. This asserts the weaker but
        checkable property: any sector whose prose claims a pollutant is not estimated must
        not also ship that pollutant in its air-pollutant output.
        """
        import glob
        claims = re.compile(
            r"(PM\\textsubscript\{2\.5\}|PM2\.5|SO\\textsubscript\{2\}|NO\\textsubscript\{x\})"
            r"[^.]{0,80}?(is not reported|are not reported|is not estimated|are not estimated)")
        problems = []
        for sector, out in (("power", "power_air_pollutants_fy2023_24.csv"),
                            ("residential", "residential_air_pollutants_2024.csv"),
                            ("transport", "transport_air_pollutants_%d.csv" % _transport_year()),
                            ("waste", "waste_air_pollutants_%d.csv" % _waste_year())):
            shipped = {r["pollutant"] for r in _rows(out)}
            for path in sorted(glob.glob(os.path.join(DOCS[sector], "*.tex"))):
                text = " ".join(open(path, encoding="utf-8").read().split())
                for match in claims.finditer(text):
                    token = match.group(1)
                    pollutant = ("PM2.5" if "2" in token and "PM" in token else
                                 "SO2" if "SO" in token else "NOx")
                    if pollutant in shipped:
                        problems.append("%s/%s claims %s is not estimated, but %s ships it"
                                        % (sector, os.path.basename(path), pollutant, out))
        self.assertFalse(problems, "coverage prose contradicts the shipped outputs:\n  "
                         + "\n  ".join(problems))


class TestShippedTransportOutputsMatchTheEngine(unittest.TestCase):
    """The staleness guard. The August 2026 round found the shipped transport CSVs
    were a run behind the engine - the generator-petrol carve-out had landed in
    road.py but make transport had not been re-run, so the manuscript, the shipped
    outputs and the anchors agreed with each other and disagreed with the code by
    0.18 Mt. This test builds the sector in-process and compares."""

    def test_shipped_totals_equal_a_fresh_engine_build(self):
        from pkinv.core import registry
        sector = registry.get("transport")
        comps = sector.build_components(sector.load_data())
        by_cat = {}
        for c in comps:
            by_cat[c["category"]] = by_cat.get(c["category"], 0.0) + c["co2e_Mt_AR5"]
        for category, engine_value in by_cat.items():
            shipped = _cell("transport_totals_%d.csv" % _transport_year(), "category", category,
                            "co2e_Mt_AR5")
            self.assertAlmostEqual(
                shipped, engine_value, places=4,
                msg="%s: shipped %.5f vs engine %.5f - outputs are stale, run "
                    "make transport" % (category, shipped, engine_value))
        self.assertAlmostEqual(
            _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR5"),
            sum(by_cat.values()), places=4)

    def test_shipped_totals_equal_the_national_rollup(self):
        """The cheap cross-command invariant: transport_totals and
        national_all_sectors are written by different commands, so drift between
        them means a partial re-run shipped."""
        self.assertAlmostEqual(
            _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR5"),
            _sector("transport"), places=4)
        self.assertAlmostEqual(
            _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR6"),
            _sector("transport", "co2e_Mt_AR6"), places=4)


class TestShippedWasteOutputsMatchTheEngine(unittest.TestCase):
    """The staleness guard, cloned from transport: build the sector in-process
    and compare against the shipped CSVs, so a code change that lands without
    `make waste` fails here rather than shipping a stale manuscript."""

    def test_shipped_totals_equal_a_fresh_engine_build(self):
        from pkinv.core import registry
        sector = registry.get("waste")
        comps = sector.build_components(sector.load_data())
        by_cat = {}
        for c in comps:
            by_cat[c["category"]] = by_cat.get(c["category"], 0.0) + c["co2e_Mt_AR5"]
        for category, engine_value in by_cat.items():
            shipped = _cell("waste_totals_%d.csv" % _waste_year(), "category", category,
                            "co2e_Mt_AR5")
            self.assertAlmostEqual(
                shipped, engine_value, places=4,
                msg="%s: shipped %.5f vs engine %.5f - outputs are stale, run "
                    "make waste" % (category, shipped, engine_value))
        self.assertAlmostEqual(
            _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"),
            sum(by_cat.values()), places=4)

    def test_shipped_totals_equal_the_national_rollup(self):
        self.assertAlmostEqual(
            _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"),
            _sector("waste"), places=4)
        self.assertAlmostEqual(
            _cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR6"),
            _sector("waste", "co2e_Mt_AR6"), places=4)
