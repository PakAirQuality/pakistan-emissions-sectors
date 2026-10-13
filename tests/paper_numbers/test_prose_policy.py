"""Title, headings and prose may not state what the engine denies.

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
    MANUSCRIPTS,
    OUT,
    ROOT,
    _csv_rows,
    _data_rows_nocomment,
    _first_where,
    _inputs_of,
    _main_tex,
    _rows)
from paper_numbers.doc_claims import (
    _closure_count,
    _closures_crossing_modules,
    _decomposed_component_count,
    _mc_scenario_pairs,
    _multi_group_component_count,
    _over_decomposed_component_count,
    _product_fact)


def _max_mc_move():
    """The largest |within_sector -> cross_sector| half-width move, in points, anywhere."""
    return max(abs(v["cross_sector"][0] - v["within_sector"][0])
               for v in _mc_scenario_pairs().values())


class TestTheTitleIsAccurate(unittest.TestCase):
    """A title is a claim, and this one made two that were wrong.

    "Ten-Sector" named ten SOFTWARE MODULES as though they were IPCC sectors; they span four
    broad IPCC sectors and eighteen detailed categories. "Cross-Sector Closure" described four
    closures of which two are between categories inside a single module. Neither was catchable
    by any numeric check, and the title is the most-read sentence in the paper.
    """

    def _title(self, path):
        with open(path, encoding="utf-8") as handle:
            text = " ".join(handle.read().split())
        match = re.search(r"\\title\{(.*?)\}\s*\\author", text)
        if match is None:
            match = re.search(r"\\title\{(.*?)\}", text)
        return match.group(1)

    def test_the_title_does_not_count_sectors(self):
        title = self._title(_main_tex(PAPER_NATIONAL_MAIN))
        for forbidden in ("Ten-Sector", "ten-sector", "Nine-Sector"):
            self.assertNotIn(forbidden, title,
                             "the title counts software modules as if they were IPCC sectors")

    def test_the_title_does_not_call_every_closure_cross_sector(self):
        title = self._title(_main_tex(PAPER_NATIONAL_MAIN))
        self.assertNotIn("Cross-Sector", title,
                         "two of the four closures are between categories inside one module")

    def test_every_document_that_cites_the_title_uses_the_current_one(self):
        """The supplement and the bibliography both spell the title out. A retitle that
        reaches only the manuscript leaves two documents citing a paper that no longer
        exists under that name."""
        title = self._title(_main_tex(PAPER_NATIONAL_MAIN))
        head = " ".join(title.split())[:48]
        for path in (os.path.join(PAPER_NATIONAL_MAIN, "supplement.tex"),
                     os.path.join(ROOT, "paper_common", "references.bib")):
            with open(path, encoding="utf-8") as handle:
                text = " ".join(handle.read().split())
            self.assertIn(head, text,
                          "%s cites a superseded title" % os.path.relpath(path, ROOT))


# ---------------------------------------------------------------------------
# HEADINGS AND OPENING SENTENCES
#
# TestTheTitleIsAccurate bans "Cross-Sector" -- in the TITLE. Section 4 stayed headed "Four
# Cross-Sector Closures", and opened "Four quantities in this inventory are shared between two
# sectors", for three rounds underneath it, because that guard reads \title{} and nothing
# else. The mechanism was right and the scope was the defect.
#
# Two reasons a heading is the worst place for a stale claim to hide. It carries its count as
# a WORD, so _quantities() -- which reads \SI, \num and numeric table cells -- is structurally
# unable to see it. And it is the most-read sentence of its section.
#
# The ban is CONDITIONAL ON THE ENGINE rather than a blocklist of forbidden words: a phrase is
# illegal only while a predicate over the registry says it is false, so if a later round makes
# all four closures cross a module, the phrase becomes legal again without anyone editing a
# list. Each entry carries the historical string it was written for, and a test asserts the
# pattern still matches that string -- a regex that no longer recognises its own defect is
# dead, and this makes that a failure rather than a silent pass.
def _headings_and_openings(path):
    """Yield (lineno, kind, text) for every heading in a file and the sentence after it."""
    with open(path, encoding="utf-8") as handle:
        lines = handle.readlines()
    found = []
    if path.endswith(".md"):
        pattern = re.compile(r"\s{0,3}#{1,6}\s+(.*)")
    else:
        pattern = re.compile(r"\s*\\(?:sub){0,2}section\*?\{(.*)")
    for i, line in enumerate(lines):
        match = pattern.match(line)
        if match is None:
            continue
        heading = match.group(1).rstrip()
        if heading.endswith("}"):
            heading = heading[:-1]
        found.append((i + 1, "heading", heading.strip()))
        for j in range(i + 1, min(i + 12, len(lines))):
            following = lines[j].strip()
            if not following or following.startswith("%") or following.startswith("\\label"):
                continue
            opening = " ".join(" ".join(lines[j:j + 3]).split())
            found.append((j + 1, "opening", opening))
            break
    return found


# (pattern, predicate -> True while the phrase is FALSE, why, the string it was written for)
BANNED_WHILE = [
    (r"[Cc]ross-[Ss]ector [Cc]losures",
     lambda: _closures_crossing_modules() != _closure_count(),
     "two of the four closures are between categories inside one module",
     "\\section{Four Cross-Sector Closures}"),
    (r"quantities in this inventory are shared between two sectors",
     lambda: _closures_crossing_modules() != _closure_count(),
     "the waste fate partition and the road/off-road split are each inside one module",
     "Four quantities in this inventory are shared between two sectors. In each case the"),
]


# (id, banned pattern, predicate -> True while the sentence is FALSE, why, stored example)
ARCHITECTURE_CLAIMS = [
    ("one group per component", r"machinery gives a component one group",
     lambda: _multi_group_component_count() > 0,
     "components carry several dependency groups at once",
     "this machinery gives a component one group, so they keep the sector's own declaration"),
    ("a component carries one group", r"A component carries one correlation group",
     lambda: _multi_group_component_count() > 0,
     "components carry several dependency groups at once",
     "A component carries one correlation group, and a real emissions row depends on several"),
    ("one string-valued group", r"One string-valued group per row cannot express that",
     lambda: _multi_group_component_count() > 0,
     "the parameter model expresses exactly that",
     "One string-valued group per row cannot express that, which is why the power module"),
    ("parameters are the next revision",
     r"[Rr]epresenting the parameters rather than the rows is the next revision",
     lambda: _published_stream() == "parameter",
     "the published national run already samples parameters",
     "Representing the parameters rather than the rows is the next revision of this machinery"),
]


def _published_stream():
    from pkinv.report import uncertainty_all
    return uncertainty_all.NATIONAL_STREAM


class TestTheUncertaintyProseDescribesTheLiveModel(unittest.TestCase):
    """The paper may not describe a model the engine replaced."""

    def test_the_live_model_is_not_degenerate(self):
        """Two-sided, where tests/test_parameters.py asserts only a floor. If every row
        carried several groups, or none did, the count would be true by construction and the
        claims anchored to it would mean nothing."""
        multi, total = _multi_group_component_count(), _decomposed_component_count()
        self.assertGreater(multi, 0, "no row carries more than one dependency group")
        self.assertLess(multi, total, "every row carries several groups, which would make "
                                      "the distinction the paper draws vacuous")

    def test_over_decomposition_is_reported_and_does_not_grow_silently(self):
        """Rows whose marginal is DERIVED from the parameter graph.

        The count sat at 23 while a silent clamp zeroed their residuals and the sampler
        drew more variance than their sectors declared. The audit
        (data/uncertainty_reconciliation.csv) found most of the 23 were resolver defects
        -- a median summarising a multi-member group with another row's width -- and after
        their repair 8 rows remained, each derived under a named per-row cause. rc40 G3b
        raised the count to 20 DELIBERATELY: the herd and crop draws were scoped to the
        thirteen manure and soils N2O rows they physically drive, and twelve of those rows'
        declared widths turned out to be the factor's width alone (0.481 of manure Direct
        N2O's 0.4858 was the EF group) - the same stale_row_sigma cause the residential
        and railways rows carry - so the graph is authoritative for them too. The ceiling
        is deliberately the current value, not a round number: this is a defect budget
        that may shrink and may not grow without someone changing this line, the registry
        and the prose together. decompose() RAISES on an excess with no disposition, so
        the ceiling here cannot be exceeded silently even without this test.
        """
        over, total = _over_decomposed_component_count(), _decomposed_component_count()
        self.assertGreater(total, 100, "the decomposition is empty; nothing is being checked")
        # rc41 Wave 4 raised the ceiling from 20 to 37 DELIBERATELY: scoping the other
        # nine sectors' factor, conversion and activity groups to their streams exposed
        # seventeen more rows whose declared width was written before those groups were
        # multiplied in (waste open burning and wastewater, residential biomass, industry
        # liquid fuels), each dispositioned in the registry and counted in the prose.
        self.assertLessEqual(over, 37,
                             "%d rows are derived from the graph, up from 37. Either a "
                             "sector narrowed its declared uncertainty or a parameter "
                             "scope now claims a row it does not drive; audit the row and "
                             "extend the reconciliation registry deliberately." % over)
        self.assertGreater(over, 0,
                           "no row is derived. That would be good news, but the paper "
                           "says 37 -- update the prose and this ceiling together.")

    def test_each_banned_sentence_still_matches_its_own_example(self):
        self.assertGreaterEqual(len(ARCHITECTURE_CLAIMS), 4)
        for name, pattern, _predicate, _why, example in ARCHITECTURE_CLAIMS:
            self.assertRegex(example, pattern,
                             "%s: the pattern no longer matches the sentence it was written "
                             "for" % name)

    def test_no_document_describes_the_superseded_uncertainty_model(self):
        live = [(name, re.compile(p), why)
                for name, p, predicate, why, _ex in ARCHITECTURE_CLAIMS if predicate()]
        self.assertTrue(live, "every superseded sentence is currently permitted -- the "
                              "predicates have all flipped and this guard checks nothing")
        paths = sorted(glob.glob(os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex")))
        paths.append(os.path.join(PAPER_NATIONAL_MAIN, "supplement.tex"))
        for _doc, root, _cls, mainname in MANUSCRIPTS:
            paths.extend(_inputs_of(_main_tex(root, mainname), root))
        paths.extend(sorted(glob.glob(os.path.join(ROOT, "docs", "*.md"))))
        problems = []
        for path in sorted(set(p for p in paths if os.path.exists(p))):
            text = " ".join(open(path, encoding="utf-8").read().split())
            for name, pattern, why in live:
                if pattern.search(text):
                    problems.append("%s: %s -- %s"
                                    % (os.path.relpath(path, ROOT), name, why))
        self.assertFalse(problems, "documents describe the superseded row-level uncertainty "
                                   "model:\n  " + "\n  ".join(problems))


# ---------------------------------------------------------------------------
# SENTENCES THE ENGINE DENIES, ANYWHERE IN THE PROSE
#
# BANNED_WHILE sweeps headings and the first sentence beneath each; ARCHITECTURE_CLAIMS bans
# descriptions of the superseded uncertainty model. The rc3 review found three false
# sentences that both had missed, every one of them MID-PARAGRAPH: "moves by nearly seven"
# (no scope moves by more than 0.62 points), "Cross-sector boundaries can be closed" (two of
# the four closures never cross a module), and "so every external comparator agrees" (the
# comparators are CO2e-based, so a trace-gas error moves them). Each survived because it was
# a number in words, or a phrase outside the swept span.
#
# This registry is the full-text version: same shape as ARCHITECTURE_CLAIMS, swept over
# every manuscript section and docs/*.md, with the historical sentence stored so the pattern
# is proven against the defect it was written for.
def _temporal_method_share(scope, method):
    for r in _csv_rows("temporal_profile.csv"):
        if r["scope"] == scope and r["temporal_method"] == method:
            return float(r["share_of_scope_pct"])
    return 0.0


FALSE_WHILE = [
    # (id, banned pattern, predicate -> True while the sentence is FALSE, why, example)
    # --- the sixteenth review's window audit -----------------------------------------
    ("transport fuel series still called nine years",
     r"nine-year fuel[- ]based (?:national )?series|Road rows exist for\s+nine fiscal "
     r"years|nine-year fuel series",
     lambda: len({r["fy_label"]
                  for r in _csv_rows("transport_fuel_series.csv")}) != 9,
     "the fuel series gained its tenth year when FY2015-16 was recovered at rc20; "
     "calling it nine describes the pre-recovery file",
     "a nine-year fuel-based series and per-fuel provincial allocations follow at no "
     "further modelling cost."),
    # --- the fourteenth review's first defect ----------------------------------------
    ("cement years still called a trend requirement",
     r"further years of national cement",
     lambda: _product_fact("ippu_years_estimated") == 9,
     "all nine IPPU fiscal years are estimated (the facts registry says so from the "
     "annual product itself), so no further cement year is a requirement of the "
     "trend; since rc20 the panel has no missing annual cells at all",
     "What a \\emph{complete} ten-sector trend still requires is four further years "
     "of national cement ACTIVITY and the two absent industry years."),
    # The rc19 sentence this ban's sibling anchored - "still requires the FY2015-16
    # product splits" - became false at rc20 when the splits were recovered; ban it
    # the same way its predecessor was banned.
    ("the panel still called incomplete",
     r"still requires the FY2015--16 product splits",
     lambda: _product_fact("annual_ne_sector_years") == 0,
     "the FY2015-16 product splits were recovered from the Pakistan Oil Report "
     "2015-2016 at rc20 and the annual product carries zero NE sector-years; a "
     "sentence requiring them describes the pre-recovery panel",
     "A \\emph{complete} nine-year ten-sector panel still requires the FY2015--16 "
     "product splits for road transport and industrial combustion."),
    # --- the thirteenth review's contradictions, banned with the evidence ------------
    ("cement borrows a calendar shape", r"borrows a monthly production shape from calendar",
     lambda: _temporal_method_share("ippu", "T2") >= 99.9,
     "cement rides its own fiscal months in every year (all nine QIM editions parsed, "
     "wholly TE2); the borrowed calendar-2022 shape is a retired vintage",
     "cement borrows a monthly production shape from calendar 2022, the nearest year "
     "that has one."),
    ("rice raster called absent", r"MapSPAM([~ ]2020)? is\s+(NOT HELD|\\emph\{not held\}|not held)",
     lambda: os.path.exists(asset_path(ROOT, "data", "gis", "manual", "spam_rice.tif")),
     "the raster landed at rc26, hash-pinned, its fallback class deleted "
     "fail-closed - fourteen prose sites kept saying it was absent for two "
     "releases (seventeenth review, defect 4, in the direction the reviewer "
     "did not know)",
     "MapSPAM 2020 is NOT HELD, so rice spreads on the cropland fallback."),
    ("unallocated called gridded", r"reaches the grid from nowhere",
     lambda: any(float(r["co2e_Mt_AR5"] or 0) > 0
                 for r in _csv_rows("pakemis_spatial_unallocated.csv")),
     "the 24 industry streams are retained at ADM1 and never enter the grid - "
     "the unallocated ledger carries their mass; saying they reach the grid "
     "asserts the invented placement rc26 removed (seventeenth review, defect 3)",
     "A further 2.01% reaches the grid from nowhere."),
    ("fertiliser called borrowed", r"remaining three are borrowed",
     lambda: not any(r["borrowed_from_year"]
                     for r in _csv_rows("pakemis_temporal_profiles.csv")),
     "the consolidated NFDC table gives every year its own twelve fiscal months; "
     "zero rows in the shipped profiles carry borrowed_from_year - the "
     "seventeenth review's first defect, a sentence two releases stale",
     "nine months are observed and the remaining three are borrowed from the "
     "opening year."),
    ("waste called flat throughout", r"Waste remains flat throughout",
     lambda: _temporal_method_share("waste", "T3") > 0.0,
     "the SWDS FOD state engine times the disposal stream (waste T3 24.2% of the "
     "sector) - the exact sibling of the banned fugitives sentence, added at the "
     "Wave-6 freeze when the sentence outlived the engine by three releases",
     "Waste remains flat throughout."),
    ("ippu facilities called awaited", r"await plant-level activity and locations",
     lambda: any(r["geometry_id"] == "facilities:ippu_register"
                 and r["within_province_placement"] == "object_partial_activity"
                 for r in _data_rows_nocomment("geometry_sets.csv")),
     "the Wave-5 flip consumed the register: located cement works carry census "
     "clinker and the class is earned S2 - a sentence saying the products still "
     "await locations describes a superseded release",
     "facility-resolved products await plant-level activity and locations."),
    ("fugitives called flat throughout", r"fugitives are flat throughout",
     lambda: _temporal_method_share("fugitives", "T2") > 0.0,
     "the upstream fugitive streams ride PBS monthly gas and crude series (40.9% of the "
     "reference year at TE2); only the demand side is flat, deliberately",
     "Waste and fugitives are flat throughout."),
    ("transport provincial called borrowed",
     r"borrows its provincial and fleet",
     lambda: any(r["fuel"] == "petrol" and r["province"] == "Punjab"
                 and r["reference_shape_year"] == "FY2023-24"
                 for r in _csv_rows("transport_provincial_shape_brackets.csv")),
     "the provincial shape is the reference year's own twelve direct OCAC area pages; "
     "only the fleet/class composition is borrowed",
     "transport borrows its provincial and fleet shares from neighbouring years"),
    ("a module moves by nearly seven", r"moves by nearly seven",
     lambda: _max_mc_move() < 5.0,
     "the largest scenario move anywhere in the Monte Carlo table is under five points; the "
     "seven-point move belonged to the superseded single-group model",
     "The national band moves by \\SI{0.04}{} points while one of its modules moves by "
     "nearly seven."),
    ("all four closures called cross-sector", r"[Cc]ross-[Ss]ector boundaries can be closed",
     lambda: _closures_crossing_modules() != _closure_count(),
     "only some of the closures cross a module; the accurate name is accounting boundaries, "
     "and the paper's own Section 4 says so",
     "Cross-sector boundaries can be closed by construction."),
    # The ban is deliberately narrower than the word "exhaustive": the D+U=G mass
    # identity IS exhaustive and both the national closures section and the transport
    # fuel-share partition state true versions. What is banned is tying exhaustiveness
    # to the two EMISSIONS categories, which the unresolved fate row refutes.
    ("waste partition called exhaustive",
     r"exhaustive partition\} of a single national"
     r"|exhaustive partition of one waste stream"
     r"|partitioned exhaustively"
     r"|open burning together account for exactly",
     lambda: _first_where("waste_ledger_2024.csv", "Mt_wet",
                          claimant="UNRESOLVED - dumped to land and waterways, "
                                   "unburned") > 0,
     "the fate ledger carries an unresolved row above zero: uncollected, unburned "
     "waste with no GHG pathway applied, so disposal and burning do NOT exhaust the "
     "stream; the mass balance closes (D+U=G) but the emissions coverage does not, "
     "and the prose may only claim the identity that holds",
     "disposal and open burning are computed as an \\emph{exhaustive partition} of a "
     "single national waste-generation figure"),
    ("transport band said to double",
     # `it doubles` excludes the idiom "doubles AS" - a sentence saying one thing serves
     # also as another has nothing to do with an uncertainty band, and the bare alternative
     # fired on "_mc_key doubles as the category anchor". The other three alternatives all
     # require the word band or transport, so coverage of the real claim is unchanged.
     r"band (?:roughly |more than )?doubles|it doubles\b(?! as\b)|band more than doubles"
     r"|doubles the transport (?:sector's )?band",
     lambda: abs(float(next(r for r in _rows("national_uncertainty_montecarlo.csv")
                            if r["scenario"] == "within_sector"
                            and r["name"] == "transport")["rel_uncert_pct_MC_95"])
                 - float(next(r for r in _rows("national_uncertainty_montecarlo.csv")
                              if r["scenario"] == "cross_sector"
                              and r["name"] == "transport")["rel_uncert_pct_MC_95"]))
             < 1.0,
     "the common-random-numbers rebuild made the cross-sector correlation scenario a "
     "no-op for this sector - the pooled Monte Carlo prints the same band under both "
     "treatments, and the supplement's own table and no-op sentence say so; a "
     "sentence claiming the band doubles describes the pre-CRN engine",
     "This sector's band doubles under an assumption that most published inventories "
     "leave undeclared"),
    ("sector spatial products said absent",
     r"gridded (?:emission )?products (?:will be evaluated|therefore await)"
     r"|no gridded product|no district or grid product",
     lambda: os.path.exists(os.path.join(OUT, "pakemis_grid_0p05_monthly.nc"))
             and any(r["module"] == "ippu"
                     for r in _rows("pakemis_source_streams.csv")),
     "the cube ships every stream, including this sector's, on its declared proxy; "
     "what a sector may truthfully say is the two-claims form - a 0.05-degree "
     "surface ships for it on proxy X, and no native geometry supports its "
     "within-province pattern - not that gridded products do not exist",
     "Facility, district and gridded products will be evaluated once plant-level "
     "activity is available"),
    ("every comparator said to agree", r"so every external comparator agrees",
     lambda: "benchmark_Mt_co2e" in
             next(iter(_rows("national_benchmark_comparison.csv")), {}),
     "the benchmarks compare CO2e, not CO2, so a comparator that weighted native CH4 or "
     "N2O would NOT agree; what a factor-table swap leaves unchanged is CO2-dominated "
     "comparisons and fuel-carbon checks, which is what the careful sites already say",
     "the plausible wrong table leaves \\COtwo{} exactly correct---so every external "
     "comparator agrees---while moving the affected category"),
]


class TestNoProseStatesWhatTheEngineDenies(unittest.TestCase):
    """A sentence the engine can refute may not appear anywhere in the prose."""

    def test_each_banned_phrase_still_matches_its_own_example(self):
        self.assertGreaterEqual(len(FALSE_WHILE), 1)
        for name, pattern, _predicate, _why, example in FALSE_WHILE:
            self.assertRegex(example, pattern,
                             "%s: the pattern no longer matches the sentence it was "
                             "written for" % name)

    def test_no_document_states_what_the_engine_denies(self):
        live = [(name, re.compile(p), why)
                for name, p, predicate, why, _ex in FALSE_WHILE if predicate()]
        self.assertTrue(live, "every banned sentence is currently permitted -- the "
                              "predicates have all flipped and this guard checks nothing")
        paths = sorted(glob.glob(os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex")))
        paths.append(os.path.join(PAPER_NATIONAL_MAIN, "supplement.tex"))
        for _doc, root, _cls, mainname in MANUSCRIPTS:
            paths.extend(_inputs_of(_main_tex(root, mainname), root))
        paths.extend(sorted(glob.glob(os.path.join(ROOT, "docs", "*.md"))))
        problems = []
        for path in sorted(set(p for p in paths if os.path.exists(p))):
            text = " ".join(open(path, encoding="utf-8").read().split())
            for name, pattern, why in live:
                if pattern.search(text):
                    problems.append("%s: %s -- %s"
                                    % (os.path.relpath(path, ROOT), name, why))
        self.assertFalse(problems, "prose states what the engine denies:\n  "
                                   + "\n  ".join(problems))


# ---------------------------------------------------------------------------
# A PART NAMING THE WHOLE
#
# The national total is conditional on thirteen structural choices, registered together as the
# scenario REF_2023_24 in data/scenarios.csv. The letter L names ONE of them -- which reading
# of the dung evidence the residential sector takes. Quoting the whole inventory "under
# configuration L" names one axis of what produced it.
#
# The distinction is not pedantry: L and S differ by 5.13 Mt, while the power coal-energy axis
# alone is worth 19.4. A reader given the letter has no way to know the other twelve exist.
#
# So a sentence may use L only where it is CONTRASTING the two readings of the dung axis --
# which is what the air-pollutant supplement does legitimately, and what the four national
# sites did not.
def _qualifier_problems(text, path=""):
    """Sites where the letter L qualifies something larger than the axis it names."""
    problems = []
    for match in re.finditer(r"configuration~?([LS])\b", text):
        start = max(text.rfind(". ", 0, match.start()) + 1, 0)
        end = text.find(". ", match.end())
        sentence = text[start:end if end > 0 else min(len(text), match.end() + 200)]
        neighbourhood = text[max(0, match.start() - 220):match.end() + 220]
        # The letter is legitimate where the sentence is CONTRASTING the two readings of the
        # dung axis, which is the only thing L and S name. The supplement does this properly:
        # "41.4 kt of black carbon under configuration L (20.5 kt under S)".
        contrasting = re.search(r"configuration~?S\b|\bunder S\b|\bS\b.{0,40}(survey|demand)"
                                r"|(survey|demand).{0,40}\bS\b", neighbourhood)
        if contrasting:
            continue
        if "REF\\_2023\\_24" in sentence:
            continue
        problems.append("%s: %r names one axis of the scenario"
                        % (path or "text", " ".join(sentence.split())[:90]))
    return problems


class TestTheScenarioIsNamedRatherThanOneOfItsAxes(unittest.TestCase):
    """The letter may name its axis; only the scenario may name the inventory."""

    def _paths(self):
        paths = sorted(glob.glob(os.path.join(PAPER_NATIONAL_SECTIONS, "*.tex")))
        paths.append(os.path.join(PAPER_NATIONAL_MAIN, "supplement.tex"))
        paths.extend(sorted(glob.glob(os.path.join(ROOT, "docs", "*.md"))))
        paths.append(os.path.join(ROOT, "README.md"))
        return [p for p in paths if os.path.exists(p)]

    def test_the_letter_names_fewer_axes_than_the_scenario(self):
        """The guard's own premise, as a test. If the scenario ever collapses to one axis,
        the letter would name the whole and this guard should stop being right."""
        from pkinv.report import national_rollup
        axes = national_rollup.scenario_registry()
        self.assertGreater(len(axes), 1,
                           "the scenario has one axis, so naming it by that axis is honest "
                           "and this guard is obsolete")
        self.assertEqual(len(national_rollup.CONFIGURATIONS), 2,
                         "the L/S letters no longer describe a two-reading axis")

    def test_no_national_total_is_qualified_by_one_axis(self):
        problems = []
        for path in self._paths():
            text = " ".join(open(path, encoding="utf-8").read().split())
            problems.extend(_qualifier_problems(text, os.path.relpath(path, ROOT)))
        self.assertFalse(problems, "the letter L is naming more than its own axis:\n  "
                         + "\n  ".join(problems))

    def test_the_guard_catches_the_conclusion_sentence(self):
        """Stored positive control, from the sentence this round removed."""
        historical = ("We have presented a ten-sector national greenhouse-gas inventory for "
                      "Pakistan totalling \\SI{448.00}{\\mega\\tonne} \\COe{} on AR5 under "
                      "configuration~L, built as a modular software system.")
        self.assertTrue(_qualifier_problems(historical),
                        "the historical conclusion sentence no longer trips this guard")
        # And the legitimate contrast must pass, or the guard would ban honest prose.
        legitimate = ("Residential emissions are \\SI{29.46}{\\mega\\tonne} under "
                      "configuration~L and \\SI{24.33}{\\mega\\tonne} under configuration~S.")
        self.assertEqual([], _qualifier_problems(legitimate))


class TestHeadingsAndOpeningsAreUnderTheSameRuleAsTheTitle(unittest.TestCase):
    """The title guard, extended to every heading and the sentence beneath it."""

    def _swept(self):
        paths = []
        for _doc, root, _cls, mainname in MANUSCRIPTS:
            main = _main_tex(root, mainname)
            paths.append(main)
            paths.extend(_inputs_of(main, root))
        paths.extend(sorted(glob.glob(os.path.join(ROOT, "docs", "*.md"))))
        paths.append(os.path.join(ROOT, "README.md"))
        return sorted(set(p for p in paths if os.path.exists(p)))

    def test_the_sweep_reads_the_documents(self):
        """A sweep over nothing passes. This is the reason the guard below means something."""
        paths = self._swept()
        self.assertGreater(len(paths), 15, "the manuscript walk collapsed")
        headings = sum(1 for p in paths for _l, kind, _t in _headings_and_openings(p)
                       if kind == "heading")
        self.assertGreater(headings, 50,
                           "only %d headings found across %d files -- the heading parser has "
                           "stopped matching" % (headings, len(paths)))

    def test_each_banned_phrase_still_matches_its_own_example(self):
        """The strongest thing a regex sweep can assert about itself.

        Every entry stores the exact historical string it was written to catch. If a pattern
        stops matching it -- because the pattern was 'tidied', or the escaping drifted -- the
        entry is dead and the sweep silently covers one thing less. Round 8 found four checks
        in this state; this makes the state a failure.
        """
        self.assertGreaterEqual(len(BANNED_WHILE), 2)
        for pattern, _predicate, _why, example in BANNED_WHILE:
            self.assertRegex(example, pattern,
                             "the pattern %r no longer matches the defect it was written "
                             "for (%r)" % (pattern, example))

    def test_no_heading_or_opening_states_what_the_engine_denies(self):
        live = [(re.compile(p), why) for p, predicate, why, _ex in BANNED_WHILE if predicate()]
        self.assertTrue(live, "every banned phrase is currently permitted -- the predicates "
                              "have all flipped, so this guard is checking nothing")
        problems = []
        for path in self._swept():
            for lineno, kind, text in _headings_and_openings(path):
                for pattern, why in live:
                    if pattern.search(text):
                        problems.append("%s:%d (%s) %r -- %s"
                                        % (os.path.relpath(path, ROOT), lineno, kind,
                                           text[:70], why))
        self.assertFalse(problems, "headings or opening sentences state what the engine "
                                   "denies:\n  " + "\n  ".join(problems))
