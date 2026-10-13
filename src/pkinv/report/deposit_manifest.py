"""What the archive deposit contains, what it deliberately does not, and by whose permission.

THE PROBLEM THIS EXISTS TO FIX. sources/ holds 357 tracked files - 3.8 GB of OGRA, NEPRA, PBS,
NFDC and PCAA publications plus 580 MB of HIES microdata - and sixty of the sixty-five archived
documents in data/source_documents.csv carry a licence nobody has established. Meanwhile
LICENSE-data opens "Data, figures, model cards, and the paper text in this repository are
licensed under CC-BY-4.0" and .zenodo.json declares the deposit open. Read literally, publishing
that tree REDISTRIBUTES SIXTY THIRD-PARTY DOCUMENTS UNDER A LICENCE THIS PROJECT CANNOT GRANT,
and nothing in the release could see it. The OpenStreetMap ODbL carve-out beside it is handled
carefully and correctly; this was the gap next to it.

ONE COLUMN WAS ANSWERING TWO QUESTIONS. `licence_status` conflated them, and they have
different answers:

    inbound_use               may we read this and derive numbers from it?
    outbound_redistribution   may we republish the document itself?

For a Pakistani government PDF with no stated terms the honest answers are `permitted` and
`not-established`. Once they are separate, `not-established` stops being a deficiency to argue
away and becomes the correct, evidence-backed answer - and the deposit is designed so that
answer COSTS NOTHING. That reframing is the substance of this module: the fix is architectural,
not a campaign to chase sixty publishers for permissions the deposit does not need.

WHAT IS DEPOSITED. Code, derived products, manuscripts, and a SOURCE REGISTER: publisher,
title, retrieval instructions and sha256 for every document the deposit does not ship. Facts
are not copyrightable and the derived estimates are this project's to license; the documents
are not. A reader can therefore verify they hold the same document as this release without the
release having redistributed it.

THE COST, STATED RATHER THAN ABSORBED. A stranger cannot rebuild end to end without
re-acquiring the documents. The register with its hashes is what turns that from guesswork
into a procedure, and the manuscript says so rather than leaving a reader to discover it.

ASSEMBLED FROM AN ALLOWLIST, NEVER BY COPYING A DIRECTORY. docs/product_catalog_design.md
already recorded the rule - "no catch-all outside build/" - because a catch-all is precisely
how a new final product gets silently buried, and here it is also how an unlicensed document
would silently ship.

Usage:  python3 -m pkinv.report.deposit_manifest
Writes: outputs/pakemis_deposit_manifest.csv
        outputs/pakemis_source_register.csv
"""
import collections
import csv
import glob
import json
import os
from functools import lru_cache

from pkinv.core import manifest as manifest_core
from pkinv.paths import DATA, OUTPUTS, ROOT
from pkinv.report import release_manifest
from pkinv.core.io import read_rows
from pkinv.assets import catalog as asset_catalog, resolve, legacy_path


def storage_path(relative):
    """Current storage location; logical source IDs stay in their original fields."""
    return os.path.relpath(resolve(os.path.join(ROOT, relative), root=ROOT), ROOT)


def extract_receipts():
    """Typed receipts remain discoverable when distributed among sector folders."""
    paths = {row["path"] for row in asset_catalog(root=ROOT)
             if row["legacy_path"].startswith("data/extracted/unfccc/")
             and row["legacy_path"].endswith(".json")}
    paths.update(os.path.relpath(path, ROOT) for path in
                 glob.glob(os.path.join(DATA, "extracted", "unfccc", "*.json")))
    return sorted(paths)


def reviewer_guides():
    from pkinv.data_index import guides
    return {os.path.relpath(path, ROOT) for path in guides(ROOT)}

DEPOSIT_OUT = os.path.join(OUTPUTS, "pakemis_deposit_manifest.csv")
REGISTER_OUT = os.path.join(OUTPUTS, "pakemis_source_register.csv")
SOURCE_DOCUMENTS = os.path.join(DATA, "source_documents.csv")

# THE OUTBOUND VOCABULARY, fail-closed. An unrecognised value raises rather than defaulting,
# the same discipline coverage_matrix.BASIS_STATE keeps: a default here would let the next
# licence someone adds ship under whatever the default happened to be.
PUBLIC_LICENCE = "public-licence"          # a licence the publisher actually states
OWN_WORK = "own-work"                      # this project made it; ours to license
COMPILATION = "own-work-compilation"       # our transcription of published FACTS
NOT_ESTABLISHED = "not-established"        # lawfully obtained, terms never stated
MIXED = "mixed-per-row"                    # the file's own rows carry different licences
PROHIBITED = "prohibited"                  # the publisher forbids redistribution
OUTBOUND_VALUES = (PUBLIC_LICENCE, OWN_WORK, COMPILATION, NOT_ESTABLISHED, PROHIBITED, MIXED)

# Only these three may enter the deposit. `not-established` is not a maybe - a deposit is a
# publication, and publishing on the basis of terms nobody has read is the act this module
# exists to prevent.
DEPOSITABLE = (PUBLIC_LICENCE, OWN_WORK, COMPILATION, MIXED)

# A FILE WHOSE OWN ROWS CARRY LICENCES CANNOT HAVE ONE. Both facility registries have a
# `licence` column describing each facility's provenance, and 71 of their 12,680 rows read
# `odbl-1.0 (OpenStreetMap contributors; derivative database)` - a share-alike position this
# project cannot waive. They were shipping as plain `own-work` with the reason "this
# project's own code, product or prose", which is the exact claim the limitations section
# says this project cannot make: the deposit would have offered 71 ODbL database rows under
# a CC-BY grant. The whole-file licence is now `mixed-per-row` and the reason names the
# column, so the per-row position travels with the file instead of being overwritten by it.
#
# The DISTINCTION that makes this a short list rather than a rule: assets.csv and
# raw_manifest.csv also carry non-uniform licence columns, and theirs describe OTHER
# artefacts, not their own rows. A register's judgement about a third-party document is
# this project's own work. Only a file whose licence column qualifies ITS OWN rows belongs
# here. tests/test_deposit_licensing.py holds both halves of that split as published lists.
ROW_LICENSED = {
    "data/shared/lookups/facility_registry.csv": "licence",
    "outputs/pakemis_facility_registry.csv": "licence",
}

# WHY A COMPILATION IS A SEPARATE WORD FROM THE DOCUMENT IT WAS READ FROM, and why the first
# version of this module was wrong to conflate them. data/activity/power/*.csv is not NEPRA's
# file; it is this project's transcription of figures NEPRA published. The figures are facts -
# megawatt-hours generated, tonnes of clinker produced - and a fact is not a copyrightable
# work. Applying the SOURCE DOCUMENT's redistribution status to OUR transcription of it marked
# ninety-two of this project's own files `not-established`, which would have been an odd claim
# to make about files this project wrote.
#
# THE LIMIT OF THAT POSITION, stated rather than assumed away: it rests on the extracted
# quantities being facts and the extraction not being a substantial taking of a protected
# DATABASE. The two database-right sources this inventory reads at scale - EDGAR (JRC) and
# FAOSTAT - both state open licences and are typed `public-licence` on their own rows, so the
# question does not arise for them. Pakistani official statistics carry no equivalent sui
# generis right. Where that reasoning would not hold, the row says so instead of inheriting
# this paragraph.
#
# The word is kept DISTINCT from plain own-work so the count is auditable: a reader can see
# exactly how much of the deposit is transcription and check the reasoning against it.

# licence_status (the hand-maintained judgement) -> what it implies for redistribution.
# Derived rather than hand-entered a second time: two registers of one fact are two vintages
# waiting to disagree, and this repository has paid for that lesson more than once.
OUTBOUND_OF_LICENCE = {
    "cc-by-4.0": PUBLIC_LICENCE,
    "odbl": PUBLIC_LICENCE,
    "unfccc-public": PUBLIC_LICENCE,
    "public-domain-us-government": PUBLIC_LICENCE,
    # rc47 Wave 6: OCHA COD-AB boundaries. CC BY-IGO is an attribution licence for
    # intergovernmental organisations - redistribution with attribution is permitted,
    # which is the same outbound position as CC-BY.
    "cc-by-igo": PUBLIC_LICENCE,
    "derived-from-listed-sources": OWN_WORK,
    "undetermined": NOT_ESTABLISHED,
    "": NOT_ESTABLISHED,
}

# INBOUND IS ONE DECLARED POSITION WITH ITS REASONING, not one hundred and thirty-eight
# judgements. This inventory reads PUBLISHED statistics and derives FACTS from them - tonnes
# of cement, cubic metres of gas, head of cattle - and a fact is not a copyrightable work. The
# documents were obtained from public publications. Where a publisher states research terms
# that are narrower than that, the row says so below rather than inheriting this paragraph.
INBOUND_DEFAULT = "permitted-facts-derived-from-published-statistics"
INBOUND_OVERRIDES = {
    # PBS distributes HIES microdata under registration terms that permit research use and
    # forbid onward distribution of the record-level files. The derived aggregates in
    # data/activity/residential/hies/ are this project's own work and ship; the microdata
    # archive does not, and would not have even if the deposit shipped documents.
    "sources/HIES": ("permitted-research-use-only",
                     "PBS microdata: registration terms permit research use and forbid "
                     "redistribution of record-level files"),
}

# FILES UNDER data/ THAT THE SOURCE REGISTER DOES NOT COVER, and it covers only ACTIVITY
# files by design. Parameter tables, crosswalks, scenario registries and downloaded reference
# datasets all live under data/ and none of them is an activity input, so the register never
# had a row for them and the deposit had no rights answer for 202 files.
#
# THERE IS NO CATCH-ALL HERE, deliberately: docs/product_catalog_design.md recorded that
# ruling for products, and it matters more for licensing, because a catch-all is exactly how
# an unlicensed third-party file would ship. Anything matching no pattern raises.
#
# The first run of this table found the thing worth finding: data/climatetrace held 103
# third-party downloads that no register row mentioned and no licence covered. rc36
# found that nothing READ them either - every Climate TRACE consumer reads sources/ -
# and removed the directory; the rule that covered it went with it.
DATA_FAMILIES = (
    # rc64: preserved measurement baselines. Each file under data/baselines/ is a byte copy of
    # one of this project's OWN shipped outputs, taken at a named moment so a later change can be
    # measured against something rather than described. They ship because a comparison whose
    # baseline a reader cannot obtain is an assertion - the point of preserving them was that two
    # states are comparable without either being a commit, and that only holds if both travel.
    # They are not third-party data and carry no upstream terms; the directory's own README says
    # what state each represents and its SHA256SUMS pins them.
    ("data/baselines/*", OWN_WORK,
     "a preserved copy of this project's own output, held as the baseline of a published "
     "measurement"),
    # v1.0.0: the JSON Schemas under data/schemas/ are this project's own contracts
    ("data/schemas/*.schema.json", OWN_WORK, "this project's own contract (a JSON Schema)"),
    ("data/claim_matrix.csv", OWN_WORK, "this project's own registry of the national manuscript's headline claims"),
    # 2026-09-16: the four registries that define what the published activity tables mean. They are
    # read from no document: each row is this project's own judgement about what a source status
    # signifies, what unit a column name hides, and whether a figure may be added to its neighbours -
    # written down precisely so a reader can disagree with it.
    ("data/activity_*.csv", OWN_WORK,
     "this project's own vocabulary for publishing the activity tree: the evidence classes, the "
     "per-file and per-column declarations, and the status-to-class mapping"),
    # The geometry and raster inputs. Their licences were documented all along - in
    # data/gis/BOUNDARY_SOURCES.json and data/gis/PROXY_SOURCES.md - and nothing read them,
    # which is how three ODbL files and seven CC-BY rasters reached a deposit decision with
    # no rights answer attached. The answers are transcribed here from those files.
    ("data/gis/PAK_ADM*.geojson", PUBLIC_LICENCE,
     "geoBoundaries, declared Public Domain in data/gis/BOUNDARY_SOURCES.json "
     "(Runfola et al. 2020)"),
    ("data/gis/proxy_*.npy", PUBLIC_LICENCE,
     "WorldPop, ESA WorldCover and FAO GLW rasters, each CC-BY-4.0 per the licence column "
     "of data/gis/PROXY_SOURCES.md; attribution travels with them"),
    ("data/gis/*SOURCES*.json", OWN_WORK, "this project's provenance notes for a geometry set"),
    ("data/gis/**/*SOURCES*.json", OWN_WORK, "as above, per geometry family"),
    # rc40: the two registries the validation package stands on. Neither is read from a
    # document: one declares the primary key and coverage of every hashed product and is
    # verified against the products; the other is pointers into this project's own ledgers.
    ("data/product_schemas.csv", OWN_WORK,
     "this project's declared product schemas, verified by tests/validation/test_product_schemas.py"),
    ("data/cross_sector_ledger_map.csv", OWN_WORK,
     "this project's pointers into its own sector ledgers; no third-party value is restated"),
    ("data/cross_tree_duplicates_baseline.csv", OWN_WORK,
     "this project's own baseline of the two raw-tree duplicates, verified by "
     "tests/test_holdings_discipline.py; it restates only paths within this repository"),
    ("data/gis/PROXY_SOURCES.md", OWN_WORK, "this project's provenance notes for the proxies"),
    # rc41: three more registries of this project's own decisions - which products a build
    # cannot regenerate, which documents under sources/ the validation package ships on the
    # publisher's recorded terms, and which data tables are extracted from documents it does
    # not ship. Registers, not the things registered.
    ("data/held_products.csv", OWN_WORK,
     "this project's register of hand-run products and their release digests"),
    ("data/public_documents.csv", OWN_WORK,
     "this project's register of the documents the validation package ships, with the publisher's recorded terms"),
    ("data/consumed_derivatives.csv", OWN_WORK,
     "this project's register of tables extracted from documents the package does not ship"),
    ("data/product_columns.csv", OWN_WORK,
     "this project's typed column registry of its products, verified by tests/validation/test_product_columns.py"),
    ("data/activity/aviation/adsblol_pilot_fy2023_24.json", OWN_WORK,
     "this project's own ADS-B pilot summary (a byte copy of its sources/ original, "
     "registered in data/consumed_derivatives.csv); the raw traces it summarises are ODbL "
     "and are not held"),
    # An inventory OF third-party files is this project's own work and carries no third-party
    # rights: it records names, hashes, URLs and retrieval dates, and redistributes none of the
    # documents it describes. That distinction is the whole reason the deposit ships derived
    # tables and a register rather than the source PDFs.
    ("data/manifests/*.csv", OWN_WORK,
     "this project's register of the raw acquisitions it holds - hashes and provenance, not "
     "the documents themselves"),
    ("data/validation/*", OWN_WORK,
     "validation labels and comparisons produced by this project"),
    ("data/benchmark_splits/*", OWN_WORK, "benchmark splits defined by this project"),
    ("data/cache/**/*.json", OWN_WORK, "a download manifest this project writes"),
    # Compilations: values transcribed from published standards and statistics. Facts, and
    # the transcription is ours; the standards themselves are not redistributed.
    ("data/emission_factors.csv", COMPILATION,
     "IPCC 2006 and EMEP factor values, transcribed"),
    ("data/*_factors*.csv", COMPILATION, "published factor values, transcribed"),
    ("data/cui2021_pak_ef.csv", COMPILATION, "published Pakistan-specific factors, transcribed"),
    ("data/burning_params.csv", COMPILATION, "IPCC residue-burning parameters, transcribed"),
    ("data/residue_params.csv", COMPILATION, "IPCC residue parameters, transcribed"),
    ("data/mms_shares.csv", COMPILATION, "manure-management shares, transcribed"),
    ("data/gleam_mms.csv", COMPILATION, "FAO GLEAM shares, transcribed"),
    ("data/gleam/*", COMPILATION, "FAO GLEAM regional values, transcribed"),
    ("data/gmw/*", COMPILATION, "Global Mangrove Watch extent figures, transcribed"),
    ("data/pbs_census/*", COMPILATION, "PBS census counts, transcribed"),
    ("data/district_records/*.csv", COMPILATION,
     "provincial and federal crop-area tables, transcribed"),
    ("data/power_fuel_quality.csv", COMPILATION, "published fuel-quality values, transcribed"),
    ("data/power_coal_blend_by_year.csv", COMPILATION, "published coal blend, transcribed"),
    ("data/rice_temperature_climatology.csv", COMPILATION,
     "climatological means computed from a public reanalysis"),
    ("data/lulucf_*.csv", COMPILATION, "published LULUCF factors, transcribed"),
    # The FY2015-16 OCAC image-edition transcription (rc20): our transcription of the
    # published page-50 sectoral table, accepted only under the four identity gates in
    # sectors/transport/ocac_image_edition.py. Facts, transcribed; the page images
    # themselves stay under data/raw with the source register, not in the deposit.
    ("data/activity/transport/ocac_fy2015_16_transcription.csv", COMPILATION,
     "OCAC Pakistan Oil Report 2015-2016 page-50 sectoral sales, transcribed under "
     "identity gates"),
    # Everything else at the data root is this project's own register, parameter set or
    # configuration - files nobody else wrote.
    ("data/*_params.csv", OWN_WORK, "this project's parameter set"),
    ("data/parameters.csv", OWN_WORK, "this project's parameter registry"),
    ("data/parameter_scope*.csv", OWN_WORK, "this project's parameter scoping"),
    ("data/*calendar.csv", OWN_WORK, "this project's seasonal calendars"),
    ("data/adm2_*.csv", OWN_WORK, "this project's administrative crosswalk"),
    ("data/stream_*.csv", OWN_WORK, "this project's source-stream declarations"),
    ("data/scenario*.csv", OWN_WORK, "this project's scenario registry"),
    ("data/benchmark*.csv", OWN_WORK, "this project's benchmark registry"),
)

# THE DATA ROOT IS ENUMERATED, NOT GLOBBED, and this is the correction that matters most in
# this module. The first version ended with `data/*.csv -> own-work`, which IS a catch-all -
# it would have declared any third-party CSV dropped at the data root to be this project's
# own work, silently, which is the exact act the rest of the file is built to prevent. The
# test that proved it (`test_an_unknown_data_file_raises`) failed on the first run and was
# right to.
#
# The cost of enumeration is one line when a registry file is added, and that cost is the
# feature: adding a file at the data root should require saying what it is.
DATA_ROOT_OWN_WORK = frozenset((
    "acquisition_attempts.csv",
    # This project's canonical table/field contracts and download presentation metadata.
    "canonical_tables.csv", "canonical_columns.csv", "canonical_consumers.csv",
    "download_catalog.json",
    "allowed_grid_fallbacks.csv", "artifact_roles.csv", "availability_matrix.csv",
    "aviation_engine_map.csv", "aviation_fleet_mix.csv", "bridge_configurations.csv",
    "claims_registry.csv", "data_gaps.csv", "dependency_group_rules.csv",
    "edgar_domain_map.csv", "facility_registry.csv", "geometry_sets.csv",
    "member_bindings.csv", "method_registry.csv",
    "monthly_data_requests.csv", "months.csv", "periods.csv",
    "province_shares.csv", "raw_manifest.csv", "release_heights.csv",
    "not_retained_register.csv",
    # rc65, the retention sweep: which held file is behind each cited document, and the
    # append-only list of held documents with their digests. Both are this project's own
    # registers ABOUT third-party documents; neither contains a byte of one.
    "cited_documents.csv", "document_retention.csv",
    "residual_classes.csv", "scope_registry.csv", "source_documents.csv",
    "source_keys.csv", "source_search_log.csv", "temporal_driver_registry.csv",
    "temporal_profiles.csv", "uncertainty_reconciliation.csv",
    "validation_catalog.csv",
    "transcription_checks.csv",   # rc37: the hand-typed-cell re-read register
    # rc44: what each grid proxy's numbers ARE - count, fraction, feature weight or constant.
    # This project's own reading of rasters it does not redistribute; every tag is measured
    # against an independent national control or argued from the quantity's dimensions, and
    # the row says which.
    "grid_proxy_semantics.csv",
    # The two registries the external verification bundle stands on: which held documents each
    # sector's zip carries, and which activity views it publishes beside the results. Registers
    # of this project's own selection - neither restates a third-party value - and the documents
    # they point AT keep their own rows here and in data/source_documents.csv.
    "verification_bundle_sources.csv", "verification_activity_views.csv",
    # And which shipped artifact answers each stage of a sector's source-to-result walk. A
    # register of pointers into this project's own outputs; it restates no third-party value.
    "verification_chain.csv",
    # rc53: which PUBLISHED PRINT of HDIP's coal-by-sector allocation the engine books for each
    # year and consumer, and why. It restates no third-party value - it names estimate ids in
    # data/activity/industry/coal_by_sector_vintages.csv, which carries its own source rows - and
    # it is the release's own editorial decision, which is exactly why it is written down.
    "coal_booking_policy.csv",
    # rc53: where IPCC 2006 files each stream, beside the module that computes it. A reading of
    # the Guidelines applied to this project's own category vocabulary; it carries no third-party
    # data at all.
    "stream_reporting_sector.csv",
    # rc58: the air coverage matrix's typed absences as data, and the physical-source register that
    # links one emitter's greenhouse-gas and air classifications - both this project's own judgement
    "air_coverage_absences.csv", "physical_sources.csv",
    "air_source_classes.csv",     # rc59: the cross-module source-class register (moved from data/activity/industry/)
))


def data_family(relative):
    """(licence, reason) for a data/ file the source register does not cover. Raises if none."""
    physical = relative
    relative = legacy_path(relative, root=ROOT)
    if relative in ("data/catalog/assets.csv", "data/catalog/migrations.csv"):
        return OWN_WORK, "this project's explicit data asset identities, locations and redistribution decisions"
    if (relative.endswith("/README.md") or relative == "data/catalog/by-purpose.md") and physical in reviewer_guides():
        return OWN_WORK, "this project's reviewer index, generated from the declared data asset catalog"
    import fnmatch
    for pattern, licence, reason in DATA_FAMILIES:
        if fnmatch.fnmatch(relative, pattern):
            return licence, reason
    if os.path.dirname(relative) == "data" and os.path.basename(relative) in DATA_ROOT_OWN_WORK:
        return OWN_WORK, "this project's own register, crosswalk or configuration"
    for asset in asset_catalog(root=ROOT):
        if asset["path"] == physical and asset.get("license") in DEPOSITABLE:
            return asset["license"], "explicit per-asset redistribution decision in data/catalog/assets.csv"
    raise KeyError(
        "%s ships in the deposit and matches no row in data/source_documents.csv and no "
        "family in deposit_manifest.DATA_FAMILIES. There is no catch-all here on purpose: "
        "say where it came from and whether this project may republish it." % relative)


# WHAT THE DEPOSIT SHIPS, as globs, in the order a reader would meet them. Every pattern is
# here because someone decided it belongs; nothing is swept in.
DEPOSIT_PATTERNS = (
    # the data products - the reason the deposit exists
    ("product", release_manifest.PRODUCT_PATTERNS),
    # the engine that produced them, and the contract it is held to
    ("code", ("src/pkinv/**/*.py", "scripts/*.py", "run_all.py", "tests/**/*.py")),
    # what a reader needs to interpret and rebuild
    ("build", ("Makefile", "pyproject.toml", "requirements.lock", ".github/workflows/*.yml")),
    ("documentation", ("README.md", "docs/*.md", "CITATION.cff", ".zenodo.json",
                       "LICENSE", "LICENSE-data")),
    ("manuscript", ("papers/pdf/*.pdf",)),
    # The provenance record. It was missing, which was incoherent: the deposit pointed at
    # release_manifest.json as the artefact holding the digests of everything this file
    # cannot digest, and then did not ship it. Both are context-stamped, so neither is
    # digested here - they are the record, not a rebuild target.
    ("provenance", ("outputs/release_manifest.json", "outputs/pakemis_test_run.json")),
    # the inputs that are ours or openly licensed. data/ is enumerated by the register
    # below rather than swept, because that is where a third-party file would hide.
    # The geometry inputs are here because leaving them out was a silent choice, not a
    # decision: the register's first run showed three ODbL files "not part of the deposit
    # allowlist" purely because the patterns stopped at .csv/.json/.md. They are openly
    # licensed, the cube needs them, and their ODbL share-alike obligation travels with them
    # through LICENSE-data.
    ("input", ("data/*.csv", "data/**/*.csv", "data/**/*.json", "data/**/*.md",
               "data/**/*.geojson", "data/**/*.npy")),
)

# CONTEXT-STAMPED ARTEFACTS: they ship, and this file may not record their digest.
#
# THE CIRCULARITY, WHICH I INTRODUCED AND THE CLEAN-ROOM REBUILD CAUGHT. This manifest listed
# ITSELF with its own bytes and sha256 - a fixpoint that cannot close, because writing the row
# changes the file the row describes. The same applies to everything written AFTER this step:
# the sixteen PDFs that `make release-fixpoint` builds, the paper-hash sidecar written after
# them, and release_manifest.json, which stamps the commit it describes and therefore differs
# between a maintainer's tree and a fresh clone by construction.
#
# release_manifest.py already states the rule this violated - "everything listed here is
# byte-stable and is a rebuild target" - and already solves the same problem the same way, by
# moving the PDF digests into a sidecar written after the build. So these rows keep their
# place in the deposit (a reader needs the papers and the manifest) and carry no digest of
# their own; `hash_recorded_in` says which artefact does hold it.
CONTEXT_STAMPED = (
    ("outputs/pakemis_deposit_manifest.csv", "release_manifest.json",
     "this file; a row describing itself changes the file it describes"),
    ("outputs/pakemis_source_register.csv", "release_manifest.json",
     "written by this step, so its digest is one generation stale here"),
    ("outputs/release_manifest.json", "itself",
     "stamps the commit it describes, so it differs between a working tree and a clone by "
     "construction and is not a rebuild target"),
    ("outputs/pakemis_paper_hashes.csv", "itself",
     "written after the papers, which are built after this file"),
    ("outputs/pakemis_test_run.json", "itself",
     "written after the suite that tests this file"),
    # rc41: the product facts read THIS manifest (deposited-file counts), so they are
    # written after it; digesting them here was one generation stale by construction.
    ("outputs/pakemis_product_facts.csv", "release_manifest.json",
     "written after this step (the product facts read this manifest), so its digest is "
     "one generation stale here"),
    # rc43: the same position as the product facts above, and found the same way - by a
    # reproduction from an EMPTY outputs/. The claim matrix is written at phase 115 and this
    # manifest at 113, so its digest here is one generation stale; on a warm tree the file
    # already exists and is hashed by the ordinary enumeration, so the guard never fires and
    # the ordering never shows. Its digest lives in the release manifest, which is the whole
    # point of the context-stamped class.
    ("outputs/pakemis_claim_matrix.csv", "release_manifest.json",
     "written after this step (phase 115 against 113), so its digest is one generation "
     "stale here"),
    ("papers/pdf/*.pdf", "outputs/pakemis_paper_hashes.csv",
     "built by the release fixpoint after this file, and LaTeX stamps a creation date into "
     "every one, so no digest recorded here could ever be reproduced"),
)


def context_stamped(relative):
    """(where the hash lives, reason) or None. The one class this file may not digest."""
    import fnmatch
    for pattern, holder, reason in CONTEXT_STAMPED:
        if fnmatch.fnmatch(relative, pattern):
            return holder, reason
    return None


# NOT DEPOSITED, and each says why in the register rather than in this comment alone.
EXCLUDED_TREES = {
    "sources/": "third-party publications; redistribution terms are not established for "
                "most of them, and the source register carries their hashes instead",
    # The same rule as sources/, for the tree that did not exist when that rule was written.
    # 135 official PDFs, spreadsheets and survey archives from five publishers were acquired
    # into data/raw/ and every one carries redistribution_status = not-established in
    # data/manifests/source_manifest.csv. Nothing here changed the DECISION - it was already
    # taken - only which paths it reaches; and until this line existed the deposit was
    # walking into them one file at a time and raising, which is the guard working.
    "data/raw/": "third-party official publications acquired for this inventory; "
                 "redistribution is not established for any of them, and "
                 "data/manifests/source_manifest.csv carries their hashes and URLs instead",
    "outputs/figures/": "regenerable from the deposited code and products",
    "build/": "regenerable intermediates",
}


def _rows(path):
    return read_rows(resolve(path, root=ROOT))


def source_documents():
    return [dict(row, data_file=storage_path(row["data_file"]),
                 archived_path=storage_path(row["archived_path"]) if row.get("archived_path") else "")
            for row in _rows(SOURCE_DOCUMENTS)]


def outbound_of(row):
    """(outbound, reason). Raises on a licence_status this module has never been taught."""
    status = (row.get("licence_status") or "").strip()
    if status not in OUTBOUND_OF_LICENCE:
        raise KeyError(
            "licence_status %r in data/source_documents.csv is not mapped to a "
            "redistribution answer. Decide whether it means the publisher STATES a licence "
            "(public-licence), the file is this project's own work (own-work), the terms "
            "were never established (not-established), or redistribution is forbidden "
            "(prohibited)." % status)
    outbound = OUTBOUND_OF_LICENCE[status]
    if outbound == PUBLIC_LICENCE:
        return outbound, "publisher states %s" % status
    if outbound == OWN_WORK:
        return outbound, "built from files already in this repository"
    return outbound, "lawfully obtained from a public publication; no terms stated"


def inbound_of(row):
    """(inbound, reason). One declared position, with named exceptions."""
    archived = (row.get("archived_path") or "")
    for prefix, (value, reason) in INBOUND_OVERRIDES.items():
        if archived.startswith(prefix):
            return value, reason
    return INBOUND_DEFAULT, "facts derived from published statistics"


def deposit_files():
    """[(kind, repo-relative path)] - the allowlist, resolved and de-duplicated."""
    seen, out = set(), []
    for kind, patterns in DEPOSIT_PATTERNS:
        for pattern in patterns:
            for path in sorted(glob.glob(os.path.join(ROOT, pattern), recursive=True)):
                if not os.path.isfile(path):
                    continue
                relative = os.path.relpath(path, ROOT)
                if relative in seen or _excluded(relative):
                    continue
                seen.add(relative)
                out.append((kind, relative))
    # rc41: the products this phase and every LATER phase declare they write (run_all.py) -
    # this manifest and the source register included - listed by
    # declaration so a first run from an empty outputs/ deposits the same set as the
    # fixpoint. Every such file is context-stamped - the digest lives in the release
    # manifest - so no byte of it is read here.
    from pkinv.run_all import declared_writes_after
    import fnmatch
    for relative in sorted(declared_writes_after("Deposit manifest", inclusive=True)):
        if relative in seen or _excluded(relative):
            continue
        if any(fnmatch.fnmatch(relative, pattern) for pattern in release_manifest.PRODUCT_PATTERNS):
            if not context_stamped(relative):
                raise ValueError("%s is written after the deposit manifest and is not "
                                 "context-stamped; its digest here would be one generation "
                                 "stale - add it to CONTEXT_STAMPED or move its phase" % relative)
            seen.add(relative)
            out.append(("product", relative))
    return sorted(out, key=lambda pair: pair[1])


def _excluded(relative):
    # rc41: the validation package's presentation copies and views under data/ are the
    # package's reading index, not deposit content (pkinv.core.presentation).
    from pkinv.core import presentation
    # The archive carries the complete source/schema recipe and catalog hashes.
    # Canonical CSVs are reconstructed offline before calculations; depositing
    # their duplicate values adds no evidence. Undeclared files still fail closed.
    return (relative in _canonical_source_paths()
            or any(relative.startswith(tree) for tree in EXCLUDED_TREES)
            or relative in presentation.layer())


def licence_of_deposited(relative, by_data_file):
    """(licence, reason) for one deposited file.

    Three cases, and the middle one is the one the first version of this module got wrong.

      registered activity input   OUR transcription of published figures - a compilation of
                                  facts, ours to license. The source document's own
                                  redistribution status is a different question and is
                                  answered on its own row in the source register.
      an openly licensed input    ships under the licence its publisher states, which for
                                  ODbL carries share-alike this project cannot waive.
      everything else             this project's code, products or prose.

    UNREGISTERED DATA FILES RAISE. That is deliberate and it is the fail-closed direction: a
    third-party file dropped into data/ would otherwise inherit `own-work` by default, which
    is precisely the silent path this module exists to close.
    """
    relative = storage_path(relative)
    mixed = _row_licence_summary(relative)
    if mixed is not None:
        return MIXED, mixed
    if relative == storage_path("data/canonical/catalog.json"):
        return OWN_WORK, "this project's canonical input schemas, lineage and byte digests"
    if relative in _canonical_source_paths():
        # Readability and lossless conversion do not change the source's licence. In
        # particular an ODbL input must retain its share-alike position in this copy.
        source = _canonical_source_paths()[relative]
        licence, reason = licence_of_deposited(source, by_data_file)
        return licence, "%s; lossless canonical copy of %s" % (reason, source)
    if legacy_path(relative, root=ROOT).startswith("data/extracted/unfccc/"):
        return _extract_licences()[relative]
    row = by_data_file.get(relative)
    if row is None:
        if relative.startswith("data/"):
            return data_family(relative)
        return OWN_WORK, "this project's own code, product or prose"
    outbound, reason = outbound_of(row)
    if outbound == PUBLIC_LICENCE:
        return outbound, reason
    # not-established / prohibited describe THE DOCUMENT, not our transcription of it.
    return COMPILATION, ("this project's compilation of facts published in %s; that "
                         "document's own redistribution status is %s and it is not shipped"
                         % (row["primary_source"].split(",")[0][:60], outbound))


def _row_licence_summary(relative):
    """The reason string for a declared row-licensed file, or None if it is not one.

    Reads the file's own licence column and names every distinct value with its count, so
    a reader of the manifest sees the share-alike rows without opening the file and a
    diff shows it the moment one appears or disappears.
    """
    column = ROW_LICENSED.get(relative) or ROW_LICENSED.get(legacy_path(relative, root=ROOT))
    if column is None:
        return None
    path = os.path.join(ROOT, relative)
    if not os.path.exists(path):
        raise ValueError("%s is declared row-licensed and is not on disk; the declaration "
                         "cannot be checked and must not be guessed" % relative)
    counts = collections.Counter()
    with open(path, encoding="utf-8") as handle:
        reader = csv.DictReader(line for line in handle if not line.startswith("#"))
        if column not in (reader.fieldnames or []):
            raise ValueError("%s is declared row-licensed on column %r and has no such "
                             "column; the declaration is stale" % (relative, column))
        for row in reader:
            value = (row.get(column) or "").strip()
            if value:
                counts[value] += 1
    if len(counts) < 2:
        raise ValueError("%s is declared row-licensed and its %r column is uniform (%s); "
                         "a single-licence file must carry that single licence, not "
                         "mixed-per-row" % (relative, column, dict(counts)))
    parts = ", ".join("%d %s" % (n, name) for name, n in sorted(counts.items()))
    return ("the rows carry their own licences in the %r column (%s); the file ships as "
            "the union of them and the share-alike rows keep their position" % (column, parts))


@lru_cache(maxsize=1)
def _canonical_source_paths():
    """Explicit canonical copies; an undeclared file does not inherit permission."""
    result = {}
    for row in _rows(os.path.join(DATA, "canonical_tables.csv")):
        source = row.get("storage_path") or storage_path(row["source_path"])
        if source.startswith("data/canonical/"):
            raise ValueError("Canonical licensing must resolve to an upstream input: %s" % source)
        result[row["path"]] = source
    return result


def canonical_recipe_inputs():
    """Files a runnable archive needs to reconstruct and interpret canonical inputs."""
    return (set(_canonical_source_paths().values()) | set(_extract_licences()) | {storage_path(path) for path in (
        "data/canonical/catalog.json", "data/canonical_tables.csv",
        "data/canonical_columns.csv", "data/canonical_consumers.csv", "data/download_catalog.json",
    )} | {"data/catalog/assets.csv"})


@lru_cache(maxsize=1)
def _extract_licences():
    """Materialized CRT facts inherit the already recorded public document licence.

    Receipt schemas and source digests must agree with the existing inventories.
    The extraction's type/lineage receipts are this project's metadata. A new
    file in this directory alone is insufficient to grant redistribution rights.
    """
    public = {row["path"]: row for row in _rows(os.path.join(DATA, "public_documents.csv"))}
    registered_inputs = set(_canonical_source_paths().values())
    result = {}
    for relative_receipt in extract_receipts():
        path = os.path.join(ROOT, relative_receipt)
        with open(path, encoding="utf-8") as handle:
            receipt = json.load(handle)
        if receipt.get("schema") != "pkinv.source_extract/v1":
            raise ValueError("Unknown source extract receipt: %s" % path)
        source = receipt["source"]
        document = public[source]
        if (receipt["source_sha256"] != document["sha256"]
                or receipt["source_sha256"] != _held_manifest_hashes().get(source)):
            raise ValueError("Source extract licensing proof disagrees with source inventory: %s" % path)
        licence, reason = outbound_of(document)
        if licence != PUBLIC_LICENCE:
            raise ValueError("Source extract has no declared public document licence: %s" % source)

        def collect(node):
            if node["kind"] == "tuple":
                for child in node["items"]:
                    collect(child)
                return
            name = node["path"]
            if os.path.basename(name) != name:
                raise ValueError("Source extract receipt escapes its directory: %s" % path)
            logical_receipt = legacy_path(relative_receipt, root=ROOT)
            relative = storage_path(os.path.join(os.path.dirname(logical_receipt), name))
            if relative not in registered_inputs:
                raise KeyError("Source extract is not a declared canonical input: %s" % relative)
            result[relative] = (licence, "%s; verified factual extract of %s" % (reason, source))

        collect(receipt["result"])
        result[os.path.relpath(path, ROOT)] = (
            OWN_WORK, "this project's type and provenance receipt for a verified source extract")
    return result


def build_deposit():
    by_data_file = {r["data_file"]: r for r in source_documents()}
    rows = []
    for kind, relative in deposit_files():
        licence, reason = licence_of_deposited(relative, by_data_file)
        # Hashed from the RESOLVED allowlist rather than by re-globbing the patterns: the
        # deposit's promise is about the files it ships, and re-deriving that set a second
        # way is how the two answers drift.
        stamped = context_stamped(relative)
        digest = ("" if stamped
                  else manifest_core.sha256_file(os.path.join(ROOT, relative)))
        rows.append({
            "path": relative,
            "kind": kind,
            "outbound_licence": licence,
            "licence_reason": reason,
            # Size is omitted with the digest for the same reason: it is one generation
            # stale for anything written after this step, and a stale number that looks
            # current is worse than a blank that says why.
            "bytes": "" if stamped else os.path.getsize(os.path.join(ROOT, relative)),
            "sha256": digest,
            "hash_recorded_in": stamped[0] if stamped else "",
            "not_digested_because": stamped[1] if stamped else "",
        })
    return rows


def build_register():
    """[row] - every registered source, whether it ships, and how to obtain it if not.

    EXCLUSION MUST BE VISIBLE. The artefact inventory found the same shape a pass ago: the
    defect was never the silence, it was that silence was indistinguishable from omission. A
    document left out of a deposit with no row saying so is a document a reader cannot know
    to look for.
    """
    deposited = {path for _kind, path in deposit_files()}
    rows = []
    for row in source_documents():
        outbound, outbound_reason = outbound_of(row)
        inbound, inbound_reason = inbound_of(row)
        archived = (row.get("archived_path") or "").strip()
        ships = row["data_file"] in deposited
        rows.append({
            "data_file": row["data_file"],
            "primary_source": row["primary_source"],
            "archival_state": row["archival_state"],
            "archived_path": archived,
            "inbound_use": inbound,
            "inbound_reason": inbound_reason,
            "outbound_redistribution": outbound,
            "outbound_reason": outbound_reason,
            # TWO DIFFERENT FILES, and the register must not blur them. The derived file is
            # this project's transcription and it ships; the DOCUMENT is the publisher's and
            # it does not. An earlier column reported only the first and read as though the
            # documents were in the deposit.
            "derived_file_in_deposit": "yes" if ships else "no",
            "document_in_deposit": "no",
            "document_not_deposited_because": _why_not(row, outbound),
            "document_sha256": _document_hash(archived),
            "how_to_obtain": _how_to_obtain(row, archived),
        })
    return rows


def _why_not(row, outbound):
    """Why the DOCUMENT is not in the deposit. Never blank - an unexplained absence is the
    thing this register exists to prevent."""
    state = row["archival_state"]
    if state == "derived":
        return "no external document: this file is built from others in this repository"
    if state == "not-archived":
        return ("the document was used and not kept; %s"
                % (row.get("gap_id") or "no gap row names it"))
    if (row.get("archived_path") or "").startswith("sources/"):
        return EXCLUDED_TREES["sources/"]
    if outbound not in DEPOSITABLE:
        return "redistribution terms are %s" % outbound
    return "not part of the deposit allowlist"


def _how_to_obtain(row, archived):
    """What a reader has to do to hold what this release read.

    A `derived` file has no external document to obtain and must not echo a publication name
    as though it did - six of them carried scraped cell values ('0.0', 'sahiwal') because the
    register's seeder matches crudely and says so in its own docstring. Those cells are
    repaired; this branch is what stops the class returning.
    """
    source = row["primary_source"] or "no source recorded"
    if row["archival_state"] == "derived":
        return "built from other files in this repository; nothing to obtain"
    if archived:
        return "%s -- obtain from the publisher; this release read the copy under %s, and " \
               "document_sha256 is how you check you hold the same one" % (source, archived)
    nr = _not_retained_row(row["data_file"])
    if nr:
        detail = "data/not_retained_register.csv row %s records the exact URL, access " \
                 "date, page/table coordinates, retrieval script and hash-or-reason" \
                 % nr["source_id"]
    else:
        detail = "gap %s in data/data_gaps.csv records what that costs" % (
            row.get("gap_id") or "(unnamed)")
    return "%s -- obtain from the publisher; this release did not keep a copy, and %s" % (
        source, detail)


def _not_retained_row(data_file, _cache={}):
    """The rc29 register's row for one not-archived activity file, or None."""
    if not _cache:
        path = resolve(os.path.join(DATA, "not_retained_register.csv"), root=ROOT)
        if os.path.exists(path):
            with open(path, newline="", encoding="utf-8") as f:
                for r in csv.DictReader(f):
                    for covered in r["data_files"].split(";"):
                        _cache[storage_path(covered.strip())] = r
        _cache.setdefault(None, None)
    return _cache.get(data_file)


def _document_hash(archived):
    """How a reader checks they hold the same document, from upstream source inventories.

    ARCHIVED_PATH IS A DIRECTORY IN 63 OF 65 ROWS - `sources/Aviation`, not a named PDF. The
    first version of this function looked up a single file hash and returned empty for all
    sixty-three, then printed a NOTE about "63 archived documents carry no hash", which read
    as a hole in the archival record and was in fact a hole in the lookup. The documents are
    hashed; the register was asking the wrong question of them.

    A directory therefore answers with its file count and points at the manifest, which is
    the honest granularity: the register says WHICH ARCHIVE holds the publication, and
    release_manifest.json will publish a sha256 per file inside it. The registered digests
    already live upstream in data/raw_manifest.csv; no prior release is read here.
    """
    if not archived:
        return ""
    hashes = _manifest_hashes()
    if archived in hashes:
        return hashes[archived]
    prefix = archived.rstrip("/") + "/"
    inside = [path for path in hashes if path.startswith(prefix)]
    if inside:
        return "see release_manifest.json: %d hashed files under %s" % (len(inside), archived)
    # THE SAME LOOKUP HOLE AS ABOVE, ONE TREE LATER. The release manifest hashes what the
    # release SHIPS, and data/raw/ is deliberately excluded from the deposit - so a source
    # archived there resolved to no hash and printed as a gap in the archival record. It is
    # not one: every file under data/raw/ is hashed in data/manifests/source_manifest.csv,
    # which is the manifest that owns that tree. Asking the right manifest is the fix; hashing
    # the tree a third time here would be a third vintage of one answer.
    raw = _raw_manifest_hashes()
    # rc47 Wave 6: a FILE-precise archived_path under the raw tree (the COD-AB rows)
    # answers with its own digest - the prefix branches below serve directories.
    if archived in raw:
        return raw[archived]
    inside = [path for path in raw if path.startswith(prefix)]
    if inside:
        return ("see data/manifests/source_manifest.csv: %d hashed files under %s"
                % (len(inside), archived))
    # rc37: the transcription directories (data/pbs_census, data/district_records,
    # data/gleam, data/gmw, data/nfdc) hold their documents beside the CSVs typed from
    # them, and data/raw_manifest.csv is the manifest that hashes those trees since rc37
    # (and data/gis since rc36). Same rule: ask the manifest that owns the tree.
    held = _held_manifest_hashes()
    # A FILE-precise archived_path under a held tree (the COD-AB geojsons under data/gis)
    # answers with its own digest, the same rule the raw-tree branch above applies; the
    # prefix branch below serves the directory rows.
    if archived in held:
        return held[archived]
    inside = [path for path in held if path.startswith(prefix)]
    if inside:
        return "see data/catalog/raw_manifest.csv: %d hashed files under %s" % (len(inside), archived)
    return ""


_HELD_HASHES = {}


def _held_manifest_hashes():
    """{path: sha256} for every raw byte data/raw_manifest.csv lists."""
    if not _HELD_HASHES:
        path = resolve(os.path.join(ROOT, "data", "raw_manifest.csv"), root=ROOT)
        if os.path.exists(path):
            for row in _rows(path):
                if row.get("path"):
                    _HELD_HASHES[storage_path(row["path"])] = row.get("sha256", "")
    return _HELD_HASHES


_RAW_HASHES = {}


def _raw_manifest_hashes():
    """{local_path: sha256} for the acquisitions tree, from its own manifest."""
    if not _RAW_HASHES:
        path = resolve(os.path.join(ROOT, "data", "manifests", "source_manifest.csv"), root=ROOT)
        if os.path.exists(path):
            for row in _rows(path):
                if row.get("local_path"):
                    _RAW_HASHES[row["local_path"]] = row.get("sha256", "")
    return _RAW_HASHES


_MANIFEST_HASHES = {}


def _manifest_hashes():
    """Registered upstream digests in the release's declared document scope.

    Directory references retain the release manifest's file scope and wording, but
    their membership and exact-file hashes come solely from data/raw_manifest.csv.
    This works before a release exists and without retaining the raw documents.
    """
    if not _MANIFEST_HASHES:
        import fnmatch
        for relative, digest in _held_manifest_hashes().items():
            if any(fnmatch.fnmatch(relative, pattern)
                   for pattern in release_manifest.DOCUMENT_PATTERNS):
                _MANIFEST_HASHES[relative] = digest
    return _MANIFEST_HASHES


def _write(path, rows, header_lines):
    os.makedirs(OUTPUTS, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        for line in header_lines:
            handle.write("# %s\n" % line)
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    deposit = build_deposit()
    register = build_register()

    _write(DEPOSIT_OUT, deposit, [
        "Every file the archive deposit ships, with the licence under which it ships.",
        "Assembled from an explicit allowlist. sources/ is NOT in it: those are third-party "
        "publications whose redistribution terms are, for most of them, not established, and "
        "a deposit is a publication.",
        "Every row must carry an outbound licence this project can actually grant - "
        "public-licence or own-work. tests/test_deposit_licensing.py holds that absolutely.",
    ])
    _write(REGISTER_OUT, register, [
        "Every registered source: whether the deposit ships it, and if not, how to obtain it.",
        "This is what replaces redistributing the documents. A reader re-acquires the "
        "publication from its publisher and checks document_sha256 against this row to "
        "confirm they hold the same file this release read.",
        "inbound_use and outbound_redistribution are DIFFERENT QUESTIONS and are answered "
        "separately. Deriving facts from a published statistic is not republishing it.",
    ])

    import collections
    by_kind = collections.Counter(r["kind"] for r in deposit)
    by_licence = collections.Counter(r["outbound_licence"] for r in deposit)
    total = sum(r["bytes"] for r in deposit if r["bytes"] != "")
    print("deposit manifest -> %s" % os.path.relpath(DEPOSIT_OUT))
    print("  %d files, %.1f MB" % (len(deposit), total / 1e6))
    for kind, count in sorted(by_kind.items()):
        print("    %-14s %4d" % (kind, count))
    print("  outbound licence: %s"
          % ", ".join("%s %d" % kv for kv in sorted(by_licence.items())))

    derived = sum(1 for r in register if r["derived_file_in_deposit"] == "yes")
    archived = sum(1 for r in register if r["archival_state"] == "archived")
    print("\nsource register -> %s" % os.path.relpath(REGISTER_OUT))
    print("  %d registered sources; %d derived files ship, %d source DOCUMENTS do not "
          "and are re-acquired from their publisher" % (len(register), derived, archived))
    outbound = collections.Counter(r["outbound_redistribution"] for r in register)
    for value, count in sorted(outbound.items()):
        print("    %-18s %4d" % (value, count))
    unhashed = [r for r in register
                if r["archival_state"] == "archived" and not r["document_sha256"]]
    if unhashed:
        print("  NOTE: %d archived sources resolve to no hashed document. That is a real "
              "hole in the archival record, not a formatting problem:" % len(unhashed))
        for row in unhashed[:10]:
            print("    %s -> %s" % (row["data_file"], row["archived_path"] or "(no path)"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
