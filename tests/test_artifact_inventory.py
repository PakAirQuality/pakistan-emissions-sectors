"""Every shipped file has a role, and each role's promise is held or its debt is published.

WHY. 406 files ship in outputs/. Most are named in no manuscript and the release manifest
hashed 42, so most of what this release produces had no declared role at all. That is how two
defects reached a release in consecutive passes: a validation registry cited nowhere, and an
IPPU two-register agreement computed on every run and thrown away. Neither was findable
because nobody could enumerate the class.

WHAT IS ASSERTED ABSOLUTELY, and what is ratcheted, and why the difference is honest.

Absolute: every file resolves to exactly one role, and a canonical product is hashed in the
release manifest. Those are promises the release keeps today.

Ratcheted: canonical, sector_headline and diagnostic files that no manuscript names. Twelve
canonical products are uncited right now. Writing twelve paragraphs into nine papers is
editorial work, not a guard, and asserting zero today would mean either doing it badly or
weakening the role vocabulary until it said nothing. docs/product_catalog_design.md specifies
the replacement: documentation anchored per LOGICAL PRODUCT, not per filename. So the debt is COUNTED, the files are
NAMED in the failure message, and the count may only fall. A ratchet that publishes its list
is a to-do list nobody can lose; an assertion nobody can pass is a test that gets deleted.

Run:  python3 -m unittest discover tests -p "test_artifact_inventory.py"
"""
import csv
import os
import unittest

from pkinv.paths import OUTPUTS
from pkinv.report import artifact_inventory as inventory
from pkinv.core.io import read_rows
from _support import require_built  # noqa: E402

# The debt as it stood when this guard was written. Each may only fall. Lowering one of these
# means a file was cited or re-roled; raising one means a product was shipped without a home,
# and the diff says so.
# diagnostic 31 since rc20: the F-gas screening file and the monthly survey view
# shipped cited-by-changelog-and-register but not yet by a manuscript section;
# the ratchet holds them until the papers name them.
# diagnostic 31 -> 33 at Pass 2 Wave 2: pakemis_fertilizer_timing_variant.csv (the
# priced-refusal lag configurations) and power_sir_pbs_overlap.csv (the two-vintage
# validation) are deliberate diagnostics; the manuscripts cite them at conversion.
# diagnostic 33 -> 35 at rc30: pakemis_bagasse_timing_variant.csv and
# ippu_fgas_bounded_bank_2024.csv (both deliberately uncited working diagnostics)
# diagnostic 35 -> 43 at rc34: the runner contract gave every sector a QA
# table (nine new *_qa_* files; the guard test asserts them, no manuscript
# names them - they are the build's self-checks, not results).
# diagnostic 43 -> 45 at rc37: pakemis_data_provenance.csv, the data/ counterpart of the
# outputs audit (the build's self-check; no manuscript names a self-check), and
# pakemis_validation_sector_scorecard.csv, the (module x property) projection the
# sector passes turn and the manuscripts cite at conversion.
# canonical rose 12 -> 13 on 2026-09-10: the UNSD industrial-combustion control ships
# ahead of the next release's prose (paper frozen at rc49); cited by the boundary
# roadmap and the next manuscript revision.
# canonical rose 13 -> 16 on 2026-09-10: the industrial-coal reconstruction's three Wave 1
# products - unsd_coal_supply_control.csv (the independent supply control),
# pakemis_coal_source_reconciliation.csv and pakemis_coal_balance.csv (the official series
# held open against held evidence, H1/H2 tested per year) - ship ahead of the next
# release's prose (paper frozen at rc49). They move no total; the Wave 4 replacement
# bridge and the next manuscript revision cite them.
# canonical rose 16 -> 17 on 2026-09-11: pakemis_cement_kiln_coal_reconstruction.csv (Wave 2b,
# cement kiln coal from clinker as a band per year - the independent activity constraint on
# HDIP's cement column), likewise ahead of the frozen paper's prose and cited by the bridge.
# canonical rose 17 -> 18 on 2026-09-11: pakemis_industrial_coal_bridge.csv (Wave 4, the
# replacement bridge and reference decision per component) - the product the rc50 CHANGELOG
# and the next manuscript revision cite; the paper is frozen at rc49 until that mint.
# diagnostic 45 -> 46 on 2026-09-14: pakemis_industrial_coal_scenarios.csv, the conditional
# alternatives rebuilt from an external reconstruction on this release's own factor chain.
# It is uncited BY DESIGN and should stay that way until the coal origin is resolved: every
# row is a scenario, none is a candidate estimate, and a manuscript that named one would be
# quoting a conditional as a finding. The paper is frozen at rc49 regardless.
# canonical rose 27 -> 35 on 2026-09-16: the eight fact_activity_* tables - the activity data
# behind the estimates (petroleum sales national and by area, livestock, crops, fertiliser,
# plant-level power, monthly power generation, household fuel), normalised from the hand-verified
# ingest tree under one declared evidence vocabulary so it can be used without running PakEmis.
# They are canonical because semantic/*.csv is, and no manuscript names them: they are a data
# product for readers who are not reading the papers, and the contract each carries in
# semantic_release.json - "fuel sold is not fuel burned", "offtake is distribution", "generation,
# not fuel" - is where their claims live instead.
#
# intermediate rose 283 -> 291 the same day: the eight outputs/activity/*.csv the semantic layer
# republishes. The shipped artefact is the semantic table; these are the build files it reads.
# canonical rose 35 -> 44 on 2026-09-16 (same day, second wave): the nine remaining fact_activity_*
# tables - industrial fuel and production, gas supply and network, waste services and waste flows,
# railway, aviation and registered-vehicle activity. Same reasoning as the first eight: semantic/*.csv
# is canonical, no manuscript names them, and the claim each makes lives in its semantic_release.json
# contract - "unaccounted-for gas is not an emission figure", "cumulative registered stock, not an
# active fleet", "modelled, not measured municipal tonnage".
#
# intermediate rose 291 -> 300 the same day: the nine outputs/activity/*.csv they are republished from.
# canonical rose 44 -> 46 on 2026-09-17: fact_activity_source_details (the twenty technical fields
# behind every readable activity row, verbatim, joined on Record ID) and dim_activity_columns (what
# every column of the readable tables means). The seventeen fact_activity_* tables themselves did not
# change count - they changed SHAPE, from the machine's vocabulary to a reader's, following the
# reshaping the user did by hand; the record moved to the companion, and nothing was lost.
#
# intermediate rose 300 -> 319 the same day: the seventeen outputs/activity/public/*.csv the readable
# semantic tables are read from, plus activity_source_details.csv and activity_column_guide.csv.
#
# diagnostic rose 46 -> 47 on 2026-09-17 (rc58): pakemis_industry_air_edgar_comparison.csv, the
# industry air layer against EDGAR v8.1 at matched years - uncited BY DESIGN, like the coal
# scenarios: it is evidence about where two compilations part, never a number a manuscript quotes.
#
# canonical rose 46 -> 48 on 2026-09-17 (rc58): semantic/fact_air_industry.csv (the industrial combustion
# air layer at source-class grain - estimates, typed absences and IE pointers, the panel's industry atoms;
# renamed fact_air_source_classes.csv at rc59 when ippu and fugitives joined the register, count unchanged)
# and semantic/fact_air_lahore.csv (Lahore District by sector beside the national unplaced remainder).
# Their generating products are cited in the supplement; the semantic tables themselves, like every
# fact_* table before them, are named by the API rather than a manuscript.
#
# canonical FELL 48 -> 47 on 2026-09-30: pakemis_air_provincial_external_comparison.csv entered
# canonical and Section 10 cites it in the same round, so the new product arrived already
# documented and the ratchet tightens by one. A fall needs no reason the way a rise does, but
# it is recorded because a ceiling that only ever climbs stops measuring anything.
# diagnostic 52 -> 49 (cycle 24): railways_official_comparison_2024.csv is now named in
# Section 10. It carried FIVE official railway benchmarks while the national paper quoted
# one, and the register's own vocabulary says a diagnostic is "evidence behind a claim;
# must be named somewhere" - so an uncited one is not a harmless working file, it is a
# comparison nobody can find. Tightened to the live count: a ratchet with slack cannot
# catch the next regression, and slack is what let this sit.
# diagnostic 49 -> 44 (rc64), and this one TIGHTENS for the same reason the other loosens:
# five diagnostics named only in a supplement - the fugitives and railways CRT cell audits
# among them, which are literally "evidence behind a claim" - were being counted as named
# nowhere. Fixing DOC_GLOBS found them where they always were.
# diagnostic 44 -> 47 (rc64, same cycle). RAISED, and the raise is the debt becoming VISIBLE
# rather than growing. Three air products - the 1990-2024 series, aviation's and residential's
# - were typed `intermediate` while release_manifest.PRODUCT_PATTERNS names them LITERALLY as
# deposited products, which meant their build tier excluded them from the archive the manifest
# says they are in. Typing them from the manifest's own decision moves them to `diagnostic`,
# where "must be named somewhere" applies and they are not named. So three files that were
# hidden in the wrong bucket now count in the right one. The citation debt is real and it was
# always there; it is now in a place that reports it.
# sector_headline 39 -> 34 and diagnostic 47 -> 46 (cycle 34): the railways appendix now
# names the sector's own reported numbers. That role's definition carries a MUST - "a
# sector's own reported numbers; must be named in that sector's paper" - and 39 files
# across all ten sectors did not meet it, capped at exactly the live count and never
# worked. Five were railways'. The remaining 34 are Q33.
# sector_headline 34 -> 28 and diagnostic 46 -> 42 (cycle 35): residential's appendix now
# names its own reported numbers and its evidence tables. Six sector_headline files and four
# diagnostics, from one glob.
# sector_headline 28 -> 15 -> 6 (cycles 38 and 39). Cycle 38 drove the live count from 28 to
# 15 and did not lower this, which left the guard accepting a thirteen-file regression in
# silence - the quiet half of the same mistake: working a number down and leaving the ratchet
# where it was. Cycle 39 closed aviation's five (absent from BOTH of its appendix's lists) and
# industry's four (named in the national paper, since industry is the one covered sector with
# no paper of its own). The remaining six are power 2 and air, railways, transport, waste 1
# each, and each one shipped as a product in the same commit that named it, because a cited
# sector_headline file that the archive lacks is the gap test_citation_deposit refuses.
# sector_headline 6 -> 0 (cycle 40). The contract closes: every file the register types as a
# sector's headline result is now named in a manuscript, and each was deposited in the same
# commit that named it. An EXACT gate from here - one new headline product that no paper names
# fails the suite - which is what the role was always asserting and never enforcing.
# diagnostic 42 -> 41 in the same cycle, and not by an edit to prose: repairing the
# supplement's swallowed backslashes made a filename visible to the scanner that had been
# sitting inside a command LaTeX was typesetting as text.
# canonical ROSE 47 -> 48 on 2026-10-06: semantic/fact_spatial_basis_year.csv, the weight
# registry weighted by mass - how much of each year's province total rides own-year geography,
# a timeless surface, or the reference year's pattern rescaled. It is canonical because the
# contract's adm2_history_annual_only limitation points at it INSTEAD of quoting a count of
# stream-years (the count it replaced went stale twice while the sentence stood), and a
# limitation that names a table nobody ships would be worse than the count. No manuscript
# names it yet: the papers are frozen at the released rc and say "most historical district
# geography is reconstructed" in prose. Citing it there is a next-mint edit, and the ceiling
# comes back down when it is made.
# canonical 47 -> 0 and diagnostic 41 -> 53 (rc68, 15 October 2026). The citation scan now
# matches a file's name as a WHOLE token: a bare substring test had counted every
# activity/activity_*.csv working file as cited because the papers name
# semantic/fact_activity_*.csv. The v3 technical supplement now lists every canonical product
# (scripts/make_v3_product_list.py), which closes the canonical debt, and three files that a
# canonical pattern swept up were re-typed: the two nine-year air views are format variants of
# the ten-year panels, and the rc42 spatial re-base is dated history beside the current rc44.
# THE DIAGNOSTIC RAISE IS A REAL LOSS, stated as one. The rc68 integration rewrote the long
# national paper (v1) as a compact article and rewrote the sector notes; together they stopped
# naming 37 diagnostics. The technical supplement and the agriculture appendix were given the
# evidence tables behind the checks they still describe (the parse controls and quarantines,
# the coal, gas, nitrogen, wastewater, power-control and licence audits), which recovered 25.
# The twelve still uncited are about subjects the rewritten texts no longer discuss - the
# Lahore power register, the pass-2 and validation scorecards, the axis fingerprints, the
# forest-flux screening, the chemical-tier gates, the 1990-2024 air series, the grid stream
# surfaces, the citation pointer audit and the sector-note fact file - and naming a table in
# prose that makes no claim on it would be a citation without a claim. One more is the rc42
# re-base re-typed above. Lowering it is free.
UNCITED_CEILING = {"canonical": 0, "sector_headline": 0, "diagnostic": 53}
# THE OTHER DIRECTION OF THE SAME RULE, which nothing checked until rc64.
#
# The register enforces that a `canonical` artifact must be named in a manuscript - that is
# what UNCITED_CEILING is for. It never enforced the converse, and the converse is written
# into the vocabulary just as plainly: `intermediate` means "a working file. No
# reader-facing claim rests on it." A file a manuscript NAMES has a reader-facing claim
# resting on it, so "intermediate" and "cited" cannot both be true of the same file.
#
# 77 files are in exactly that position, 46 of them in the national paper, and they are not
# marginal: national_key_categories.csv, national_variance_attribution.csv (151 rows),
# residential_district_2024.csv (1,201), waste_district_2024.csv (402), timeseries_
# validation.csv (204). `intermediate` has been serving as the default bucket for anything
# outside the canonical family, and because the rule was enforced in one direction only,
# nothing said so.
#
# Held rather than fixed. Deciding what each of the 77 actually is - canonical, diagnostic,
# or genuinely a working file a paper should stop naming - is a release-planning judgement
# per file, not a sweep, and the wrong sweep would make the register less true rather than
# more. The ceiling stops the set growing while that happens. Lowering it is free.
# 77 -> 84 (rc64). THIS RAISE IS THE DETECTOR GETTING BETTER, NOT THE TREE GETTING WORSE,
# which is the only reason a raise here is defensible. artifact_inventory.DOC_GLOBS scanned
# papers/*/sections/*.tex and not papers/*/*.tex, so anything named only in a sector
# supplement's own body was recorded as cited by nobody - and four of the five supplements are
# partly monolithic. Seventeen artifacts were affected, seven of them intermediates, so seven
# files that were always cited are now counted as cited. Not one citation was added and not
# one file changed role. The honest reading is that this ceiling was set on under-counted data
# for every release that carried it, and the set it bounds was larger than the number said.
# 84 -> 10 (rc64). The catch-all learned to DEFER: a fall-through file a manuscript names is
# evidence behind a claim, not a working file, and the role is now derived from that fact
# instead of asserted in its absence. 74 files moved in one change, with no pattern rows to
# rot - which is why more patterns were the wrong fix, the fall-through set having no shared
# naming structure (a validated cover needed 61 patterns for 74 files).
# 10 -> 11 (rc63). docs/deposit_rebuild_limits.md names transport_class_fuel_weights_2024.csv as
# one of the build-tier intermediates the archive deposit does not ship. That is a statement that
# the file IS a working file and that its absence is what stops a rebuild from the deposit - the
# document's subject - not a reader-facing claim resting on it. The role is right and so is the
# citation; of the two remedies the guard offers, re-typing it canonical would be false and
# not naming it would hide the dependency the document exists to report.
# 11 -> 6 (rc68). Lowered to the live count: the six are run and release records a paper names
# as records (release_manifest.json, pakemis_test_run.json, three sector run manifests) and the
# per-class air uncertainty table, all cited before; the whole-name scan removed false matches.
CITED_INTERMEDIATE_CEILING = 6
# 51 -> 52 (rc62): pakemis_brick_kiln_fleet_by_year.csv, the brick fleet's dated observations on
# the year axis beside a production-based coal band. Uncited BY DESIGN and staying so: it books
# nothing - HDIP's column is still what the engine burns - and it exists so the shape of what is
# missing is inspectable. Its findings reach the manuscript through
# outputs/pakemis_industrial_coal_decision.csv, which is where a reader is meant to meet them.
# 50 -> 51 (rc60): pakemis_air_power_admission_bridge.csv, the account of what the power SO2
# admission moved - the panel before, the increment split by the equipment class that priced
# it, the panel after, and the narrowed remaining-power scenario band. Uncited BY DESIGN and
# staying so: it exists so a reader can audit a step in a published series that no input
# explains, which is evidence about a coverage decision rather than a number to quote. Raised
# deliberately rather than by citing it somewhere it does not belong.
# 49 -> 50 (rc60 Package 4): pakemis_air_lahore_power_register.csv, the Lahore grid power
# units and the SO2 this release does not publish. Uncited BY DESIGN and staying so: it is
# evidence about the size of a typed absence, not a number any manuscript may quote.
# 47 -> 49 (rc60): the two Lahore SO2 diagnosis tables - the channel decomposition of the
# published district decline and the district-level comparison against EDGAR's own gridmaps.
# Both are uncited BY DESIGN and stay that way: they are evidence about how a curve was made
# and where two compilations part, not numbers a manuscript quotes. Raised deliberately
# rather than by citing them somewhere they do not belong.
# 23 -> 22 at rc52: the claims repair cited one more canonical product from the manuscript
# 22 -> 23 (boundary program Wave B3): pakemis_hfc_bank_series.csv, the household equipment bank
# as a band from the HIES stock indicator; ships ahead of the next manuscript's prose
# 26 -> 27 (rc54): pakemis_adm2_stream_by_year.csv, the per-stream district vector for all
# nine periods - the evidence the district reporting-sector partition rests on; ships ahead
# of the next manuscript's prose
# 25 -> 26 (rc53 Wave E): pakemis_industrial_coal_decision.csv, the decision record that
# adopts nothing and says why; ships ahead of the next manuscript's prose
# 24 -> 25 (rc53 Wave D): pakemis_brick_activity_reconstruction.csv, brick coal from a kiln
# count and a measured fuel rate; ships ahead of the next manuscript's prose
# 23 -> 24 (rc53 Wave A3): pakemis_industrial_change_attribution.csv, the channel decomposition
# of the industrial decline; ships ahead of the next manuscript's prose
# 22 -> 23 (rc53 Wave A1): pakemis_coal_vintage_ledger.csv, the source-vintage ledger that
# separates a reporting reallocation from a change in consumption; ships ahead of the next
# manuscript's prose
# 20 -> 22 (boundary program Wave B2-B6): pakemis_ammonia_nitric_series.csv and
# pakemis_industrial_screening_series.csv, the nine-year series the gate decisions read;
# ship ahead of the next manuscript's prose
# 19 -> 20 (boundary program Wave B1): pakemis_brick_coal_alternatives.csv, the bounded brick-coal
# alternatives with HDIP's residual footnote; ships ahead of the next manuscript's prose
# 18 -> 19 (boundary program Wave A): pakemis_industry_edgar_divergence.csv, the nine-year
# engine-vs-EDGAR industrial diagnostic; ships ahead of the next manuscript's prose
# 276 since Wave 6: agriculture_water_regime_2024.csv, the water-regime
# axis's machinery file (cited by the scenario registry, not a manuscript)
# 276 -> 282 at rc36: the inventory became recursive over every file under
# outputs/ (617 rows, one per shipped file, where it had seen 461 top-level
# csv/nc/json/parquet). The six newcomers in this tier are working files
# the scan had never seen - the mc_draws/ sidecars and the .txt notes; the
# figures, prose reports, dashboard, Tier-3 and eval-lane files went to
# their own roles, and the canonical/headline/diagnostic debts are unchanged.
# intermediate rose 319 -> 321 on 2026-09-17 (rc58): pakemis_air_industry_uncertainty_by_year.csv
# and pakemis_air_industry_cy2023.csv, the industry air layer's working files behind the panel.
# intermediate rose 321 -> 322 on 2026-09-17 (rc59): pakemis_kiln_frame_adm2_by_type.csv, the brick-kiln
# frame by kiln type (the FCBK and ZZ district vectors the air sink rides) - a working file the spatial
# support ledger's pattern hashes point at, cited by the technical note rather than a manuscript.
# 322 -> 323 on rc61: pakemis_power_admission_adm2_by_class.csv, the per-class per-period
# district vectors the admitted power SO2 rides. It is the exact sibling of the kiln frame
# product that raised this ceiling last - a working frame of the spatial sink, published so
# the support ledger's pattern hashes resolve to shares a reader can check, and so the
# Lahore attribution reads the share rather than inferring it from the wrong vector.
INTERMEDIATE_CEILING = 323   # rc41: +1, the within-fuel weights split out of the transport class table (one table per file)


def _rows():
    path = os.path.join(OUTPUTS, "pakemis_artifact_inventory.csv")
    return read_rows(path)


def _facts():
    path = os.path.join(OUTPUTS, "pakemis_product_facts.csv")
    return read_rows(path)


class TestTheCountsReconcile(unittest.TestCase):
    """Asserted before anything is concluded from them.

    An architectural review challenged this inventory on arithmetic rather than on
    architecture, and it was right to: I reported 405 files against a role table summing to
    403, and 13 uncited canonical products where 43 minus 31 is 12. The REGISTER was
    consistent both times. My summary was not - it quoted an audit taken before the inventory
    file itself existed alongside a role table corrected after it. A number a person can
    retype is a number that will be retyped wrong, so the identities are asserted here and
    the figures are published as facts rather than prose.
    """

    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()

    def test_the_roles_sum_to_the_files_discovered(self):
        import collections
        counts = collections.Counter(r["role"] for r in self.rows)
        self.assertEqual(sum(counts.values()), len(self.rows),
                         "roles sum to %d over %d rows" % (sum(counts.values()),
                                                           len(self.rows)))

    def test_a_cited_file_is_not_declared_a_working_file(self):
        """`intermediate` says no reader-facing claim rests on it; a citation says one does.

        This is UNCITED_CEILING's missing direction. Without it the register could be made
        to pass by typing anything awkward `intermediate`, which is the failure mode the
        role comment already warns about for the count - "declaring everything intermediate
        to silence the guard shows up in a diff" - but which nothing detected for the
        contradiction itself.
        """
        live = sorted(r["artifact"] for r in self.rows
                      if r["role"] == "intermediate"
                      and r["cited_in"] and r["cited_in"] != "none")
        self.assertLessEqual(
            len(live), CITED_INTERMEDIATE_CEILING,
            "files typed `intermediate` that a manuscript names rose to %d (ceiling %d). "
            "Either the role is wrong or the citation is - re-type the file, or stop naming "
            "it. Raising this ceiling needs a written reason.\n  %s"
            % (len(live), CITED_INTERMEDIATE_CEILING, "\n  ".join(live)))

    def test_that_ceiling_is_not_slack(self):
        live = sum(1 for r in self.rows if r["role"] == "intermediate"
                   and r["cited_in"] and r["cited_in"] != "none")
        self.assertGreaterEqual(
            live, CITED_INTERMEDIATE_CEILING - 5,
            "the live count is %d against a ceiling of %d; lower the ceiling so the next "
            "regression is caught" % (live, CITED_INTERMEDIATE_CEILING))

    def test_uncited_is_exactly_canonical_minus_documented(self):
        canonical = [r for r in self.rows if r["role"] == "canonical"]
        cited = [r for r in canonical if r["cited_in"] != "none"]
        uncited = [r for r in canonical if r["cited_in"] == "none"]
        self.assertEqual(len(uncited), len(canonical) - len(cited),
                         "the identity that my summary broke")
        self.assertEqual(len(uncited), UNCITED_CEILING["canonical"],
                         "the ceiling is not the live count; a ratchet set loose is a "
                         "ratchet that permits one silent regression")

    def test_the_published_count_matches_the_inventory_it_names(self):
        """THE GUARD THAT WAS MISSING, and the clean-room rebuild is what found its absence.

        `artifact_count` exists so nobody retypes the number wrong. It was wrong anyway - 409
        published against an inventory holding 411 - for a reason no test could see:
        product_facts ran BEFORE artifact_inventory in all three build definitions, so it read
        the file the PREVIOUS run had left behind and published it as current. A fact that
        cannot be retyped wrong can still be COMPUTED wrong by a build order nobody declared.

        The order is fixed. This asserts the property rather than the order, because the next
        way to break it will not be an ordering.
        """
        facts = {r["fact_id"]: r["value"] for r in _facts()}
        self.assertEqual(int(facts["artifact_count"]), len(self.rows),
                         "pakemis_product_facts.csv publishes artifact_count=%s against an "
                         "inventory of %d rows; the facts registry is describing a different "
                         "run" % (facts["artifact_count"], len(self.rows)))
        canonical = sum(1 for r in self.rows if r["role"] == "canonical")
        self.assertEqual(int(facts["canonical_count"]), canonical)

    def test_every_artifact_carries_exactly_one_tier(self):
        allowed = set(inventory.TIER_OF_ROLE.values())
        for row in self.rows:
            self.assertIn(row["release_tier"], allowed, row["artifact"])
            self.assertEqual(row["release_tier"],
                             inventory.TIER_OF_ROLE[row["role"]], row["artifact"])

    # Several files are claimed by two rules apiece, and ORDER decides which wins. The order
    # correct in all three cases - the cross-sector `pakemis_*` family is claimed before the
    # generic sector suffixes, and the paper-hash sidecar before both - but "correct because
    # the rows happen to be in this order" is not a decision anyone recorded. Declared here
    # is declared here with its reason, so a NEW collision fails instead of inheriting the
    # precedent. The count is deliberately not stated: it was "three" while the dict held
    # more, which is the same staleness this round spent its time removing.
    DECLARED_OVERLAPS = {
        # rc68: ten explicit rows placed ahead of pakemis_*.csv so that none of them is read as
        # a canonical emissions product. Each is a diagnostic, an evaluation lane or a record
        # of the release itself; the first-match order is the decision, stated here.
        "pakemis_air_annual_fy2015_16_fy2023_24.csv":
            "matches pakemis_*.csv too; format_variant wins because it is the first nine years "
            "of the ten-year air panel under its older name, not a second product",
        "pakemis_air_source_classes_fy2015_16_fy2023_24.csv":
            "matches pakemis_*.csv too; format_variant wins because it is the first nine years "
            "of the ten-year source-class table under its older name, not a second product",
        "pakemis_spatial_rebase_rc42.csv":
            "matches pakemis_*.csv too; diagnostic wins because it is a dated re-base "
            "measurement kept as history beside the current rc44 one",
        "pakemis_air_htap_species_comparison.csv":
            "matches pakemis_*.csv too; eval_lane wins because it compares this inventory with "
            "HTAPv3.2 process by process and species by species; it books no emission",
        "pakemis_air_htap_comparison.csv":
            "matches pakemis_*.csv too; the explicit eval_lane rule must win because it is a "
            "matched-year comparison against an external inventory, not an emissions product",
        "pakemis_htap_nh3_annual.csv":
            "matches pakemis_*.csv too; eval_lane wins because these are HTAP's own published "
            "values for Pakistan, carried as a comparator and never as this inventory's estimate",
        "pakemis_htap_nh3_monthly.csv":
            "matches pakemis_*.csv too; eval_lane wins because these are HTAP's own published "
            "monthly values, a comparator for timing and never this inventory's estimate",
        "pakemis_air_power_control_evidence.csv":
            "matches pakemis_*.csv too; diagnostic wins because it records public plant design "
            "controls as evidence and books no emission; demonstrated operation is not inferred",
        "pakemis_air_power_design_cases.csv":
            "matches pakemis_*.csv too; eval_lane wins because its estimates are scenario-only "
            "design and sulfur cases, kept apart from the central totals by construction",
        "pakemis_nitrogen_partition_sensitivity.csv":
            "matches pakemis_*.csv too; diagnostic wins because it is a deterministic chemical "
            "attribution case with no probability, never a second central nitrogen account",
        "pakemis_pass2_scorecard.csv":
            "matches pakemis_*.csv too; diagnostic wins because it reports retired internal "
            "targets beside current metrics and is not a release-completion verdict or a product",
        "pakemis_primary_geography_licence_audit.csv":
            "matches pakemis_*.csv too; diagnostic wins because it records which geography "
            "inputs the primary package may use under their licences; it books no emission",
        "pakemis_release_change_summary.csv":
            "matches pakemis_*.csv too; diagnostic wins because it compares this release with "
            "the preserved previous one; read as canonical it would be a second, older account",
        "pakemis_sector_note_facts.csv":
            "matches pakemis_*.csv too; diagnostic wins because it is generated text facts for "
            "the sector notes, every value of which is read from a canonical product elsewhere",
        "pakemis_power_provincial_basis_by_year.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because this "
            "table books no emission: it sets the provincial split of grid power under the "
            "reference-year vector beside the split each year's stations give, and the "
            "national total on both sides is the same by construction. Read as canonical "
            "it would be a second provincial power product disagreeing with "
            "pakemis_adm1_by_year.csv in its `before` column (rc66)",
        "pakemis_wastewater_method_comparison.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because this "
            "table books no emission: it sets the reference method for wastewater nitrous "
            "oxide beside the method it replaced, on the same draws. Half its rows are the "
            "alternative's; read as canonical it would publish a second wastewater "
            "estimate and a second national total (rc67)",
        "pakemis_dung_fate_by_year.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because this "
            "table books no emission: for each year it sets the dung agriculture diverts "
            "beside what households are observed burning and prices each destination of "
            "the difference. The reference applies none of those prices; read as "
            "canonical the table would assert a destination (rc67)",
        "pakemis_gas_flow_crosswalk.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because this "
            "table books no emission: it classifies each delivered gas stream by the kind "
            "of flow it is and names the category that books its carbon. Its volumes are "
            "the regulator's and its one emission column restates the post-meter leak the "
            "fugitives ledger already books; read as canonical it would be a second gas "
            "account (rc67)",
        "pakemis_dung_balance.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because this "
            "table books no emission and deliberately resolves nothing - it states the "
            "ASYMMETRY between the two dung configurations term by term and the falsifiable "
            "implication of the larger one, while the mass it is about stays unresolved and "
            "the four candidate destinations stay priced one at a time in "
            "national_dung_variants.csv. A canonical reading would assert a destination "
            "(2026-10-08, the 23rd review's item 6)",
        "pakemis_faostat_nitrogen_flows.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because "
            "this compares two compilations flow by flow and books nothing (rc64)",
        "pakemis_category_crosswalk.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because this "
            "carries no emission at all - its cells are the mapping between two classification "
            "schemes, and the one quantity column exists so a reader can check the mapping "
            "rather than to report anything (2026-10-06)",
        "pakemis_coal_sector_reallocation.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because it prices the CONSEQUENCE of a re-base that has not happened - every quantity in it is conditional on a pin movement, and a canonical reading would assert the movement (2026-10-06)",
        "pakemis_uncertainty_drivers.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because every "
            "row is a property of the ensemble's DISTRIBUTION - a share of variance, a share "
            "of a tail, an interval under a condition. The Mt columns restate draws the "
            "ensemble already publishes; read as canonical it would be a second "
            "uncertainty product (rc67)",
        "pakemis_power_coal_rebase_ledger.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because it "
            "MEASURES a pin movement rather than reporting an emission - its national columns "
            "are the published series' own before and after, taken from the legacy axis, and a "
            "canonical reading would make the ledger a second place the total is declared "
            "(2026-10-07)",
        "pakemis_power_coal_configurations.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because these are four CANDIDATE activity accounts, three of which the inventory does not use - a canonical reading of a candidate would be a claim this file exists to avoid making (2026-10-06)",
        "pakemis_power_fuel_reconciliation.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because it reconciles three accounts of an ACTIVITY quantity and books nothing - the inventory's coal energy still comes from the engine, not from here (2026-10-06)",
        "pakemis_power_reference_audit.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because every "
            "cell is a verdict about whether a PUBLISHED source survives a physical audit - a "
            "rescue requirement, an identity, a band membership - and not one of them is an "
            "emission this inventory reports (2026-10-06)",
        "pakemis_coal_allocation_identity.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because "
            "this tests whether a BOOKED activity split is a measurement and books "
            "nothing itself (rc64)",
        "pakemis_minerals_panel_screening.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because this "
            "prices a defect in an ACTIVITY panel's completeness and books nothing - the "
            "canonical family is for numbers the inventory reports (2026-10-05)",
        "pakemis_citation_pointer_audit.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because "
            "every cell is a judgement about a CITATION rather than a quantity, and the "
            "canonical family is for numbers the inventory reports (2026-10-05)",
        "pakemis_release_axis_fingerprints.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because this "
            "carries no inventory quantity at all - its cells are digests of other "
            "releases' aggregates, and a canonical reading of a digest is meaningless "
            "(2026-10-05)",
        "pakemis_fgas_leak_rate_adjudication.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win for the same "
            "reason as the other two adjudications - it prices a parameter decision inside "
            "a category that contributes zero to every total, so there is no canonical "
            "number here to be the family's (2026-10-05)",
        "pakemis_forest_flux_adjudication.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because this "
            "is a SCREENING outside every total - LULUCF is excluded by declared scope - and "
            "the canonical family is for numbers the inventory reports. It prices a "
            "disagreement about the direction of the forest flux and books nothing "
            "(2026-10-05)",
        "pakemis_power_coal_energy_adjudication.csv":
            "matches pakemis_*.csv and the power_* sector family too; the explicit "
            "diagnostic rule must win because this adjudicates between two published "
            "readings and books nothing - the sector family is for the power module's "
            "own reported numbers, which this is not (rc64)",
        "pakemis_citation_deposit_audit.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because "
            "this audits the PACKAGING - which cited paths the archive contains - and "
            "carries no emissions quantity at all (rc64)",
        "pakemis_power_province_boundary_audit.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because "
            "this is a metadata audit of where stations are placed, not a product any "
            "reader verifies against the panel - it carries station geography and a "
            "generation exposure share, and no emissions quantity at all (rc64)",
        "pakemis_air_provincial_external_comparison.csv":
            "matches pakemis_*.csv and *_provincial_*.csv too; the explicit diagnostic rule must "
            "win because this is a comparison of two compilations at ADM1 and nothing in it "
            "enters a total - the provincial suffix rule is for the release's own provincial "
            "products, which this is not, and the cross-sector pakemis_* family is for products "
            "a reader verifies against the panel (rc59 campaign)",
        "pakemis_brick_kiln_fleet_by_year.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because this is "
            "the fleet's own evidence laid beside the booked series rather than a panel period "
            "a reader verifies - nothing in it enters a total (rc62)",
        "pakemis_power_admission_adm2_by_class.csv":
            "matches pakemis_*.csv too; the explicit intermediate rule must win because these "
            "are the sink's own working frames - the per-class, per-period district vectors the "
            "admitted power SO2 rides - published so the support ledger's pattern hashes "
            "resolve to inspectable shares, exactly as the kiln frame vectors are (rc61)",
        "pakemis_air_power_admission_bridge.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because the "
            "bridge is the audit trail of a coverage decision - what entered the panel, from "
            "which equipment class, and what stayed in the scenario - and not a panel period a "
            "reader verifies (rc60)",
        "pakemis_air_industry_cy2023.csv":
            "matches pakemis_*.csv too; the explicit intermediate rule must win because the "
            "calendar composition is machinery for a campaign comparison, not a panel period a "
            "reader verifies (rc58)",
        "pakemis_air_source_class_uncertainty_by_year.csv":
            "matches pakemis_*.csv too; the explicit intermediate rule must win because the "
            "per-sector, per-period uncertainty is the register layer's working file behind the "
            "panel, cited by the technical note rather than a manuscript (rc58; renamed rc59)",
        "pakemis_kiln_frame_adm2_by_type.csv":
            "matches pakemis_*.csv too; the explicit intermediate rule must win because the "
            "kiln-type district vectors are the sink's working frame, published so the support "
            "ledger's pattern hashes resolve to inspectable shares (rc59)",
        "pakemis_industry_air_edgar_comparison.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because every row "
            "is a matched-year comparison of two compilations, evidence about where they part "
            "and never a number a reader quotes as an estimate (rc58)",
        "pakemis_air_lahore_so2_attribution.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because every row is "
            "a decomposition of a change this release already published - it explains a curve and "
            "adds no estimate, and a canonical role would invite a reader to quote a channel "
            "effect as though it were an emission (rc60)",
        "pakemis_air_lahore_external_comparison.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because every row is "
            "a district-level comparison against another compilation, evidence about where two "
            "inventories attribute the same air to different sectors and never a number a reader "
            "quotes as an estimate (rc60)",
        "pakemis_air_lahore_power_register.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because the table "
            "enters no total by construction - power SO2 is typed NE - and exists to measure what "
            "that refusal costs at one district, which is evidence about a coverage decision and "
            "not an emission a reader may quote (rc60)",
        "pakemis_industrial_coal_scenarios.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because every row "
            "is a CONDITIONAL scenario measured against the reported series, not a canonical "
            "product a reader verifies - and a canonical role would be the first step to one of "
            "them being quoted as an estimate (2026-09-14)",
        "pakemis_monthly_ledger_2024.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because the "
            "view is a single-sector conditional slice, not a canonical cross-sector product",
        "pakemis_bagasse_timing_variant.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win for the "
            "same reason as the fertilizer variant beside it (rc30)",
        "pakemis_fertilizer_timing_variant.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because the "
            "lag configurations are priced-and-refused readings, never a shipped product",
        "pakemis_grid_provincial_check.csv":
            "matches *_provincial_* too; it is a cross-sector product, not a sector's own "
            "provincial allocation, so the pakemis_ rule must win",
        "pakemis_monthly_fy2015_16_fy2024_25.csv":
            "matches *_monthly_fy* too; it is the ten-year cross-sector layer, not a "
            "sector's monthly file",
        "pakemis_paper_hashes.csv":
            "matches pakemis_*.csv too; its explicit rule must win because it is written "
            "after the manifest and cannot be a canonical hashed product",
        "pakemis_completeness_mass.csv":
            "matches *_completeness_*.csv too; the pakemis_ rule must win because the "
            "Wave-4 ledger is the cross-sector completeness product itself, not a "
            "sector's completeness view",
        "pakemis_data_provenance.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because the "
            "provenance audit is the build's self-check over data/, not a canonical product "
            "a reader verifies (rc37)",
        "pakemis_grid_stream_surfaces.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win because the "
            "cube's dispatch record is the build's own account of what it did, read by "
            "spatial_decomposition, not a product a reader verifies (rc41)",
        "pakemis_validation_sector_scorecard.csv":
            "matches pakemis_*.csv too; the explicit diagnostic rule must win until a "
            "manuscript cites the projection - a canonical file no paper names would move "
            "the assertEqual ceiling for a scoreboard, not a product (rc37)",
    }

    def test_pattern_overlaps_are_declared_and_do_not_grow(self):
        """First-match-wins HIDES a double match, so the classification of an overlapping
        file depends on the order of rows in a CSV. That is a real decision and it should be
        written down rather than inherited. The reviewer asked for this to fail closed; it
        fails closed on anything not on the list above."""
        by_pattern = {p: r for p, r, _o, _d in inventory.roles()}
        overlapping = {}
        for row in self.rows:
            patterns = [p for p in row["matching_patterns"].split(";") if p != "*"]
            roles_hit = {by_pattern[p] for p in patterns}
            if len(roles_hit) > 1 and any("/" in p for p in patterns):
                # rc36, ONE declared class rather than fifteen per-file entries: a file in
                # a subdirectory matches its directory rule ("gis/*", "eval/validation/*")
                # AND a top-level rule ("*.png", "*_totals_*.csv") because fnmatch's `*`
                # crosses `/`. The directory rules are placed first in the table precisely
                # so that they win; here that placement is asserted rather than inherited.
                self.assertIn("/", row["matched_pattern"],
                              "%s: a top-level rule %s outranked its directory rule"
                              % (row["artifact"], row["matched_pattern"]))
                continue
            if len(roles_hit) > 1:
                overlapping[row["artifact"]] = sorted(roles_hit)
        self.assertEqual(set(overlapping), set(self.DECLARED_OVERLAPS),
                         "undeclared rule collisions %s; resolved-but-undeclared %s"
                         % (sorted(set(overlapping) - set(self.DECLARED_OVERLAPS)),
                            sorted(set(self.DECLARED_OVERLAPS) - set(overlapping))))
        for reason in self.DECLARED_OVERLAPS.values():
            self.assertGreater(len(reason), 60)

    def test_the_first_matching_rule_is_the_one_recorded(self):
        """Whatever the order says, the inventory must have applied it - not some other
        pattern that also matched."""
        table = inventory.roles()
        for row in self.rows:
            first = next(p for p, _r, _o, _d in table
                         if p in row["matching_patterns"].split(";"))
            self.assertEqual(row["matched_pattern"], first, row["artifact"])


class TestEveryShippedFileHasARole(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = _rows()

    def test_the_inventory_covers_the_outputs_directory(self):
        """Every file under outputs/, recursively, named by its path relative to outputs/.

        Until rc36 the scan saw only top-level csv/nc/json/parquet and this test agreed
        with it, so 203 shipped files - every .md, .png, .html and every subdirectory -
        had no role and no test noticed. The universe is now the directory itself."""
        require_built()
        from _support import ROOT, presentation_layer
        index = presentation_layer()        # a validation package's reading index; empty here
        on_disk = set()
        for folder, _dirs, names in os.walk(OUTPUTS):
            for name in names:
                if name == ".DS_Store":
                    continue
                if os.path.normpath(os.path.relpath(os.path.join(folder, name), ROOT)) in index:
                    continue
                on_disk.add(os.path.relpath(os.path.join(folder, name), OUTPUTS)
                            .replace(os.sep, "/"))
        self.assertEqual({r["artifact"] for r in self.rows}, on_disk,
                         "the inventory and outputs/ disagree about what ships")

    def test_every_role_is_from_the_vocabulary(self):
        allowed = {r["role"] for r in inventory._rows(inventory.ROLES)}
        for row in self.rows:
            self.assertIn(row["role"], allowed, row["artifact"])

    def test_a_new_output_cannot_escape_a_role(self):
        """The catch-all must be last and must match anything. Without it a new product
        raises KeyError deep in a build instead of being classified - and with it in the
        wrong position it would swallow every pattern above it."""
        table = inventory.roles()
        self.assertEqual(table[-1][0], "*", "the catch-all is no longer the last pattern")
        role, _owner, _desc, pattern = inventory.role_of("a_file_nobody_has_written_yet.csv",
                                                         table)
        self.assertEqual(pattern, "*")
        self.assertEqual(role, "intermediate")

    def test_a_canonical_product_is_hashed_in_the_release_manifest(self):
        """Held absolutely. A canonical product the manifest does not hash is a product a
        reader cannot verify, and that is the one promise this tier already keeps."""
        missing = sorted(r["artifact"] for r in self.rows
                         if r["role"] == "canonical" and r["in_release_manifest"] != "yes")
        self.assertFalse(missing, "canonical products absent from the release manifest: %s"
                                  % missing)

    def test_the_uncitedness_debt_does_not_grow(self):
        """Ratcheted, and the message is the to-do list."""
        for role, ceiling in sorted(UNCITED_CEILING.items()):
            uncited = sorted(r["artifact"] for r in self.rows
                             if r["role"] == role and r["cited_in"] == "none")
            self.assertLessEqual(
                len(uncited), ceiling,
                "%s files no manuscript names rose to %d (ceiling %d). Either cite them or "
                "re-declare the role honestly:\n  %s"
                % (role, len(uncited), ceiling, "\n  ".join(uncited)))

    def test_declaring_everything_intermediate_would_be_visible(self):
        """The escape hatch, closed. `intermediate` is the only role with no citation
        promise, so the cheapest way to silence the ratchet above is to re-declare a product
        as a working file. The count is bounded so that doing it shows up in a diff."""
        count = sum(1 for r in self.rows if r["role"] == "intermediate")
        self.assertLessEqual(count, INTERMEDIATE_CEILING,
                             "the intermediate tier grew to %d; a product moved into it, or "
                             "a genuinely new working file needs this ceiling raised on "
                             "purpose" % count)

    def test_a_format_variant_points_at_a_twin_that_exists(self):
        """A .parquet inherits its .csv's citation, which is only honest if the twin ships."""
        names = {r["artifact"] for r in self.rows}
        for row in self.rows:
            if row["role"] != "format_variant":
                continue
            twin = row["artifact"].rsplit(".", 1)[0] + ".csv"
            self.assertIn(twin, names,
                          "%s inherits a citation from %s, which does not ship"
                          % (row["artifact"], twin))

    def test_every_role_pattern_still_matches_something(self):
        """A pattern matching nothing is a rule about a file that no longer exists, and it
        would go on looking correct forever."""
        used = {r["matched_pattern"] for r in self.rows}
        for pattern, role, _owner, _desc in inventory.roles():
            if pattern == "*":
                continue
            self.assertIn(pattern, used,
                          "pattern %r (%s) matches no shipped file" % (pattern, role))

    def test_every_row_explains_what_the_file_is(self):
        for row in self.rows:
            self.assertGreater(len(row["description"]), 25, row["artifact"])


if __name__ == "__main__":
    unittest.main()
