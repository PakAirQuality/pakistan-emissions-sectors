"""The release manifest: what this inventory version is, in one machine-readable file.

WHY THIS EXISTS. A reviewer found three national totals in circulation at once - 454.48,
461 and 455.14 - across the README, the national manuscript's abstract and its results
table. None of them was a calculation error; they were three vintages of the same
calculation, quoted in places nothing checked. The deeper problem was that no artefact
said which release a number belonged to, so "is this current?" had no answer short of
re-running the engine and comparing by hand.

This file is that answer. Every headline resolves to one release, one set of reference
years, one metric basis and one structural configuration, or it is not a headline.

WHAT IT DELIBERATELY DOES NOT DO. It does not recompute anything. Every figure here is
read from the outputs the sector runners and the national layer already wrote, so the
manifest cannot disagree with them by construction - if it is stale, it is stale in the
same way they are, and the staleness guards catch that. A manifest that recalculated
would be a fourth vintage waiting to happen.

Usage:  python3 -m pkinv.report.release_manifest
Writes: outputs/release_manifest.json
"""
import csv
import glob
import os
import subprocess

import pkinv
from pkinv import release
from pkinv.core import components
from pkinv.core import layers
from pkinv.core import mc_draws
from pkinv.core import montecarlo
from pkinv.core import manifest as manifest_core
from pkinv.paths import OUTPUTS, ROOT
from pkinv.report import national_rollup
from pkinv.report import uncertainty_all
from pkinv.core.io import read_rows
from pkinv.core.reporting_window import RETIRED_GHG_PANEL_PRODUCTS

OUT = os.path.join(OUTPUTS, "release_manifest.json")

# Everything a published number depends on: the factor and parameter tables, the
# committed activity data, and the benchmark register. Source PDFs and spreadsheets are
# hashed by the individual sector manifests, which this file points at rather than
# duplicating - re-hashing 57 OCAC PDFs here would double a slow step for no new fact.
SOURCE_PATTERNS = (
    "data/*.csv",
    "data/activity/**/*.csv",
    # The geospatial hash surface, absent until the fifth review's rc7 round: every
    # tracked geometry, proxy cache and derived geo product the allocation depends
    # on. The bulk snapshots they derive from (sources/OSM/) stay gitignored; their
    # digests live in the *_SOURCES.json files hashed here.
    "data/ml/*.csv",
    "data/gis/*.csv",
    "data/gis/*.geojson",
    "data/gis/*.json",
    "data/gis/*.npy",
    "data/gis/*.npy.txt",
    "data/gis/PROXY_SOURCES.md",
    "data/gis/rail/*",
    "data/gis/kilns/*",
    "data/gis/roads/*",
    "data/gis/manual/*",
    "data/gis/landfills/*",
)

# The DOCUMENTS the activity data was read from, as distinct from the data itself. Hashing
# only the CSVs let a release say "these are the exact numbers" without being able to say
# "and here is what they were read from" - which is how the largest sector in the inventory
# cited two publications that were not in the repository at all, for its whole life, with
# nothing able to see it. data/source_documents.csv classifies every activity file and
# tests/test_data_provenance.py asserts the classification; this puts the archived half in
# the manifest so a published release resolves to documents, not just to numbers.
DOCUMENT_PATTERNS = (
    "sources/**/*.pdf",
    "sources/**/*.xlsx",
    "sources/**/*.zip",
    "sources/*.xlsx",
    # The rc29 re-audit's closure: witnesses under sources/ that are not office
    # documents - SDMX/OurAirports/GPPD extracts (.csv), acquisition sidecars
    # recording the hash and flow of an extraction (.json), ELK/ERA5 rasters
    # (.nc), and plain-text transcriptions (.txt) - previously fell through
    # every pattern and were hashed nowhere, so a register row calling them
    # "archived" could not mean "hashed into the manifest".
    "sources/**/*.csv",
    "sources/**/*.json",
    "sources/**/*.nc",
    "sources/**/*.txt",
)

# DOIs are minted at archival. They are empty strings rather than invented placeholders
# so that nothing downstream can print a plausible-looking identifier that resolves to
# nothing - the same reason the transport paper refuses to synthesise a citation it
# could not locate.
DOI = {"software": "", "data": "", "documentation": ""}


def _rows(path):
    from pkinv.assets import resolve
    return read_rows(resolve(path, root=ROOT), comments=False)


def source_patterns():
    """Physical registered inputs, including tracked canonical CSVs and GIS bundles."""
    from pkinv.assets import catalog
    paths = set(SOURCE_PATTERNS)
    for asset in catalog(root=ROOT):
        paths.add(asset["path"])
        if asset.get("canonical_path"):
            paths.add(asset["canonical_path"])
    paths.add("data/catalog/assets.csv")
    return tuple(sorted(paths))


def _git_commit():
    """The commit whose tree this manifest was generated from, or None outside a checkout.

    Necessarily the PARENT of the commit that carries the file: a manifest cannot record
    the hash of the commit it is committed in without an infinite regress. So the field is
    named for what it can honestly mean - the tree that was read - and `tree_dirty` says
    whether that tree had uncommitted changes at the time. Regenerate after committing and
    the pair reads correctly: describes_commit is the release content, tree_dirty is false.

    The regenerates-identically test ignores this block for the same reason: it is
    environmental, not a property of the release contents.
    """
    try:
        sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                      stderr=subprocess.DEVNULL).decode().strip()
        dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT,
                                             stderr=subprocess.DEVNULL).decode().strip())
        record = {"describes_commit": sha, "tree_dirty": dirty}
    except (OSError, subprocess.CalledProcessError):
        record = {"describes_commit": None, "tree_dirty": None}
    # rc69: development moved to the public repository and the documents stayed in the
    # private checkout mounted beside it (pkinv.core.layers). The documents block above is
    # hashed from that checkout, so the record names its commit too.
    record["restricted_layers"] = layers.describe(ROOT)
    return record


def _sectors(path):
    out, total = [], None
    for r in _rows(path):
        row = {"sector": r["sector"], "reference_year": r["year"],
               "year_convention": r["year_convention"],
               "period_start": r["period_start"], "period_end": r["period_end"],
               "period_label": r["period_label"],
               "scenario_id": r["scenario_id"],
               "residential_dung_axis": r["residential_dung_axis"],
               "co2e_Mt_AR5": float(r["co2e_Mt_AR5"]),
               "co2e_Mt_AR6": float(r["co2e_Mt_AR6"]),
               "uncert_pct_95": float(r["uncert_pct_95"]),
               "share_pct": float(r["share_pct"])}
        if r["row_kind"] == "national_total":
            total = row
        else:
            out.append(row)
    return out, total


def _completeness():
    counts = {}
    rows = _rows(os.path.join(OUTPUTS, "completeness.csv"))
    for r in rows:
        counts[r["notation_key"]] = counts.get(r["notation_key"], 0) + 1
    return {"rows": len(rows),
            "by_notation_key": dict(sorted(counts.items())),
            "ipcc_codes": len({r["code"] for r in rows})}


def _sector_manifests():
    """The per-sector run manifests this release points at, rather than duplicating."""
    return sorted(os.path.basename(p)
                  for p in glob.glob(os.path.join(OUTPUTS, "*manifest*.json"))
                  if os.path.basename(p) != os.path.basename(OUT))


def _reporting_period(sectors):
    """The span the release covers, and whether it is one span or several.

    A consumer of this manifest needs to know whether adding the sector totals gives a
    single-period national inventory or a sum across vintages. That is a property of the
    rows, so it is read off them.
    """
    spans = sorted({(s["period_start"], s["period_end"]) for s in sectors})
    common = len(spans) == 1
    return {
        "harmonised": common,
        "start": spans[0][0],
        "end": spans[-1][1],
        "label": (sectors[0]["period_label"] if common
                  else "spans %s to %s" % (spans[0][0], spans[-1][1])),
        "note": ("every sector reports the same twelve months, so the national total is a "
                 "single-period inventory" if common else
                 "sectors report different spans, so the national total is a sum across "
                 "vintages"),
    }


def _core_reporting_period():
    """The supported fiscal product window, separate from the reference-year totals."""
    from pkinv.core.reporting_window import CORE_PERIOD_IDS, CORE_SUFFIX
    from pkinv.assets import asset_path
    rows = read_rows(asset_path(OUTPUTS, "pakemis_annual_" + CORE_SUFFIX + ".csv"))
    actual = sorted({row["period_label"] for row in rows})
    if actual != list(CORE_PERIOD_IDS):
        raise ValueError("annual release period differs from the supported core: %s" % actual)
    return dict(harmonised=True, start="2015-07-01", end="2025-06-30",
                label="July 2015--June 2025 (ten fiscal years)",
                period_ids=actual, fiscal_year_count=len(actual),
                note="Common supported fiscal window; source coverage is separately documented. "
                     "FY2025-26 is a partial provisional extension, outside common national totals.")


def _reference_year_convention(sectors):
    conventions = sorted({s["year_convention"] for s in sectors})
    harmonised = len({(s["period_start"], s["period_end"]) for s in sectors}) == 1
    if harmonised:
        return ("every sector is on one reporting period; the integer reference_year is "
                "each sector's own label for it and means different things under different "
                "conventions (%s), so read reporting_period, not the year"
                % ", ".join(conventions))
    return ("each sector reports the latest year its sources support, so the national total "
            "is a sum across reference years and not a single-year inventory")


def _mc_seeds():
    """Every Monte-Carlo seed in the release, by stream. The clean-room list: a
    reproduction should never have to read source code to learn a seed."""
    from pkinv.sectors.waste import uncertainty as waste_unc
    from pkinv.sectors.fugitives import uncertainty as fug_unc
    return {
        "national_pooled": montecarlo.SEED,
        "waste_structural_scenarios": waste_unc.SCENARIO_SEED,
        "waste_parameter_rerun": waste_unc.RERUN_SEED,
        "fugitives_sector": fug_unc.SEED,
    }


def _draw_files():
    """Path + sha256 + seed of every injected draw file, re-read (and therefore
    re-hash-verified) at manifest time."""
    out = {}
    for module, (name, dist) in sorted(uncertainty_all.INJECTED_MODULES.items()):
        _cols, meta = mc_draws.read(name)
        out[module] = {"file": "outputs/" + meta["file"], "sha256": meta["sha256"],
                       "seed": meta["seed"], "n_iter": meta["n_iter"],
                       "distribution_id": dist}
    return out


def _common_ensemble():
    """The common draw ensemble's three layers, from their sidecars (rc18): the
    draw_id contract's provenance rides the manifest exactly as the injected
    files' does."""
    import json as _json
    from pkinv.report import common_ensemble
    out = {}
    for label, path in (("annual", common_ensemble.ANNUAL_OUT),
                        ("monthly", common_ensemble.MONTHLY_OUT),
                        ("spatial", common_ensemble.SPATIAL_OUT)):
        with open(path.rsplit(".", 1)[0] + ".meta.json", encoding="utf-8") as f:
            meta = _json.load(f)
        out[label] = {"file": "outputs/" + meta["file"],
                      "sha256": meta["sha256"], "seed": meta["seed"],
                      "n_iter": meta["n_iter"], "scenario": meta["scenario"]}
    return out


def _one(rows, field):
    """A field every scenario row agrees on. Disagreement is a defect, not a first-row pick."""
    values = {r[field] for r in rows.values()}
    if len(values) != 1:
        raise ValueError("%s differs across scenarios: %s" % (field, sorted(values)))
    return values.pop()


def build():
    if layers.mode(ROOT) == "absent":
        # The documents block would hash nothing and still look like a manifest.
        raise SystemExit("the restricted layers are not mounted here, so a release manifest "
                         "built now would list none of its source documents. Run "
                         "python3 scripts/overlay.py link PATH first.")
    baseline_path = os.path.join(OUTPUTS, "national_all_sectors.csv")
    ledger_path = os.path.join(OUTPUTS, "national_all_sectors_ledger.csv")
    sectors, total = _sectors(baseline_path)
    _alt_sectors, alt_total = _sectors(ledger_path)
    # The two national totals are keyed by the LETTER of the dung basis each file carries,
    # read from the rollup's own constants. Through rc66 the keys were typed here as "L"
    # for the baseline file and "S" for the second; when the baseline became the survey at
    # rc67 those typed keys would have printed each total under the other's letter.
    baseline_code = national_rollup.CONFIGURATIONS[national_rollup.BASELINE]
    alternative_code = national_rollup.CONFIGURATIONS[national_rollup.ALTERNATIVE]
    mc = {r["scenario"]: r for r in _rows(
        os.path.join(OUTPUTS, "national_uncertainty_montecarlo.csv"))
        if r["name"] == "national" or r["name"] == "TOTAL"}

    return {
        "schema": release.SCHEMA,
        # The COMPONENT contract version, distinct from this manifest's own. It went to v2
        # when the six provenance keys became required, and a consumer needs to know which:
        # a v1 row may say nothing about how it was resolved in time or space.
        "component_schema": components.SCHEMA_VERSION,
        "version": pkinv.__version__,
        "git": _git_commit(),
        "inventory": "Pakistan national greenhouse-gas and air-pollutant inventory, "
                     "ten sectors, excluding LULUCF",
        "gwp_basis": {"reported": "AR5 GWP-100", "secondary": "AR6 GWP-100",
                      "note": "fossil and biogenic CH4 carry distinct AR5 values; see "
                              "pkinv.core.gwp"},
        "reporting_period": _core_reporting_period(),
        "reference_reporting_period": _reporting_period(sectors),
        "reference_years": {
            # DERIVED, not asserted. This said "the national total is a sum across
            # reference years and not a single-year inventory" for a release in which every
            # sector was on FY2023-24, in the same file as the periods that proved it wrong.
            "convention": _reference_year_convention(sectors),
            "by_sector": {s["sector"]: s["reference_year"] for s in sectors},
            "year_conventions": {s["sector"]: s["year_convention"] for s in sectors},
        },
        # THE WHOLE SCENARIO, not the letter. "configuration L" names ONE of the axes below;
        # a consumer that recorded only the letter could not reconstruct the baseline this
        # release was run under. The count is not restated here, because it was restated as
        # "nine" in this comment while the registry held ten.
        "scenario": {
            "scenario_id": national_rollup.SCENARIO_ID,
            "axes": [{"axis": r["axis"], "module": r["module"], "setting": r["setting"],
                      "alternative": r["alternative"]}
                     for r in national_rollup.scenario_registry()],
            "note": "each axis is a fork in the evidence rather than a parameter with a "
                    "distribution; outputs/national_structural_bridge.csv prices the "
                    "alternatives, outputs/national_configurations.csv publishes the "
                    "policy-facing named configurations (one axis moved at a time, no "
                    "probabilities), and the parametric interval contains none of them",
        },
        "baseline_configuration": {
            "code": national_rollup.CONFIGURATIONS[national_rollup.BASELINE],
            "basis": national_rollup.BASELINE,
            "description": national_rollup.CONFIG_NOTE[national_rollup.BASELINE],
            "why": "the residential row measures what households burn, and the household "
                   "survey is what observes it; nothing held supports the fivefold "
                   "survey under-count the ledger reading would need",
        },
        "national_totals": {
            "period_id": "FY2023-24",
            baseline_code: {"co2e_Mt_AR5": total["co2e_Mt_AR5"],
                            "co2e_Mt_AR6": total["co2e_Mt_AR6"],
                            "uncert_pct_95": total["uncert_pct_95"]},
            alternative_code: {"co2e_Mt_AR5": alt_total["co2e_Mt_AR5"],
                               "co2e_Mt_AR6": alt_total["co2e_Mt_AR6"],
                               "uncert_pct_95": alt_total["uncert_pct_95"]},
            "note": "S (household dung as the survey observes it) is the baseline since "
                    "release 1.0.0rc67; L (all the dung agriculture diverts, burned in "
                    "households) is a destination assumption and the baseline of every "
                    "earlier release. Under S the rest of the diverted dung has no "
                    "observed destination and is outside the total: the fate account is "
                    "outputs/residential_dung_ledger_2024.csv and each candidate "
                    "destination is priced for every year in "
                    "outputs/pakemis_dung_fate_by_year.csv. A national figure quoted "
                    "without its configuration is ambiguous.",
        },
        "monte_carlo": {
            # The RUN, beside its results. The bands were recorded here and the draw count
            # was not, so a figure could label itself 10,000-draw beside a 100,000-draw
            # band and the manifest had nothing to say about it. Since rc12 the block
            # also carries EVERY seed in the release (the waste paper called one
            # "private" and the eighth review correctly read that as unpublished),
            # the RNG identity, and the sha256 of each injected draw file - the
            # clean-room contract for the asymmetric national quantiles.
            "n_iter": int(_one(mc, "n_iter")),
            "seed": montecarlo.SEED,
            "seeds": _mc_seeds(),
            "rng": mc_draws.RNG_IDENTITY,
            "stream": uncertainty_all.NATIONAL_STREAM,
            "injected_draw_files": _draw_files(),
            "common_ensemble": _common_ensemble(),
            "scenarios": {
                scenario: {"rel_uncert_pct_95": float(r["rel_uncert_pct_MC_95"]),
                           "rel_down_pct_95": float(r["rel_down_pct_95"]),
                           "rel_up_pct_95": float(r["rel_up_pct_95"]),
                           "P2.5_Mt": float(r["P2.5_Mt"]),
                           "P50_Mt": float(r["P50_Mt"]),
                           "P97.5_Mt": float(r["P97.5_Mt"])}
                for scenario, r in sorted(mc.items())
            },
        },
        "product": {"name": release.PRODUCT, "family": release.FAMILY,
                    "package": release.PACKAGE, "repository": release.REPO_URL,
                    "repository_note": release.REPOSITORY_NOTE,
                    "explorer": release.EXPLORER_URL,
                    "cite_as": release.cite_name(),
                    # data, not prose: the READMEs' submission sentences are
                    # sweep-checked against these two fields (rc19)
                    "manuscript_status": release.MANUSCRIPT_STATUS,
                    "submission_identifier": release.SUBMISSION_IDENTIFIER},
        "sectors": sectors,
        "completeness": _completeness(),
        "doi": DOI,
        # NOT one licence for the whole tree (the tenth review's ESSD gate): the
        # OSM-derived tables are DERIVATIVE DATABASES under ODbL and this repo's
        # CC-BY grant cannot waive their share-alike. Mirrors LICENSE-data, plus
        # the geocoding overrides that list had missed. A primary CC-BY data
        # record must exclude or replace these, which is a submission decision,
        # so the manifest states it rather than leaving it to be discovered.
        "licences": {
            "code": "MIT",
            "data_and_text": "CC-BY-4.0 for project-owned primary products and text; per-file upstream terms retained",
            # THE PATHS ARE THE PUBLISHED IDENTITIES (legacy_path), which is this
            # project's convention - and the deposit ships each file at its PHYSICAL
            # path, so a reader who searched the deposit for "data/gis/rail/yards.csv"
            # found nothing and could reasonably conclude the carve-out was honoured by
            # exclusion. It is not: all seven ship, correctly typed public-licence with
            # the reason "publisher states odbl". Both names are given so the legal
            # statement and the archive can be checked against each other.
            "odbl_carveouts": _odbl_carveouts(),
            "odbl_note": "OpenStreetMap (c) contributors. ODbL source databases, mixed facility "
                         "registries, preserved baselines and potentially affected legacy spatial "
                         "products are in a separate companion. The primary geographic products "
                         "are rebuilt without OSM geometry or weights. See LICENSE-data, "
                         "LICENSE-ODbL and pakemis_primary_geography_licence_audit.csv; removing "
                         "a source file alone does not remove derivative-database obligations.",
            "undetermined": "UNEP MARS plume observations carry no licence "
                            "declaration in the record. They are EVALUATION "
                            "evidence only - no MARS quantity enters any "
                            "emission total, factor or allocation - and are "
                            "excluded from any primary data record until the "
                            "rights are established.",
        },
        "sector_manifests": _sector_manifests(),
        "sources": manifest_core.sha256_sources(source_patterns()),
        "source_documents": manifest_core.sha256_sources(DOCUMENT_PATTERNS),
        "products": _products(),
    }


# (published identity, the file as the deposit ships it). The second is resolved rather
# than written down: asset_path is what every reader in this project already uses, so a
# future migration moves both halves together instead of stranding the legal statement.
ODBL_CARVEOUTS = (
    "data/gis/landfills/pak_landfill_assets.csv",
    "data/gis/landfills/pak_landfill_coverage.csv",
    "data/gis/rail/pak_rail_network.geojson",
    "data/gis/rail/yards.csv",
    "data/gis/roads/pak_road_density_267x340.npy",
    "data/gis/osm_building_fraction_267x340.npy",
    "data/activity/ippu/facility_geocoding_overrides.csv",
)


def _odbl_carveouts():
    """The carve-out list, each entry naming the published identity AND the shipped path."""
    from pkinv.assets import asset_path as _asset_path
    out = []
    for published in ODBL_CARVEOUTS:
        shipped = os.path.relpath(_asset_path(ROOT, published), ROOT)
        out.append(published if shipped == published
                   else "%s (ships at %s)" % (published, shipped))
    out.append("the odbl-1.0 rows of data/facility_registry.csv and "
               "outputs/pakemis_facility_registry.csv, which ship as mixed-per-row in "
               "the deposit manifest with the per-row counts in their reason")
    return out


PRODUCT_PATTERNS = (
    "outputs/pakemis_*.csv",
    # The PakEmis-Air beta (rc48 lane): named literally, like the cubes, because none is
    # called pakemis_* - which is exactly how a companion product stayed unhashed while the
    # manifest's own description claimed an "air-pollutant inventory".
    "outputs/pakemis_adm2_stream_reference.csv",
    # The industrial-boundary program's Wave 1 extraction (2026-09-10): named
    # literally for the same reason - it is not called pakemis_*.
    "outputs/ogra_gas_class_series.csv",
    "outputs/unsd_industry_combustion_control.csv",
    "outputs/unsd_coal_supply_control.csv",
    "outputs/air_pollutants_adm1.csv",
    "outputs/air_pollutants_adm2.csv",
    "outputs/air_pollutants_2024.csv",
    "outputs/air_pollutants_provincial_2024.csv",
    "outputs/air_pollutants_district_2024.csv",
    "outputs/air_pollutants_timeseries_1990_2024.csv",
    "outputs/residential_air_pollutants_2024.csv",
    "outputs/transport_air_pollutants_2024.csv",
    "outputs/power_air_pollutants_fy2023_24.csv",
    "outputs/power_air_screening_fy2015_16_fy2024_25.csv",
    # rc58: industry's covered air layer at class grain (the screening it replaces is retired)
    "outputs/railways_air_pollutants_2024.csv",
    "outputs/waste_air_pollutants_2024.csv",
    "outputs/aviation_air_pollutants_fy2023_24.csv",
    "outputs/national_all_sectors*.csv",
    "outputs/completeness.csv",
    "outputs/pakemis_grid_0p05_monthly.nc",
    "outputs/pakemis_grid_0p05_monthly_ledger.nc",
    # rc45: the nine-period annual cube. Named literally beside the monthly pair rather than
    # globbed as outputs/*.nc, because a glob would silently hash whatever NetCDF happened to
    # be in outputs/ - which is how a superseded vintage gets a release digest and a reader
    # gets two grids with equal standing.
    "outputs/pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc",
    "outputs/pakemis_ghg_grid_0p05_annual_*_fy2015_16_fy2024_25.nc",
    # the air family's nine-period cubes (air spatial Wave B): literal for the
    # same reason as the pair above
    "outputs/pakemis_air_grid_0p05_*_*_fy2015_16_fy2024_25.nc",
    # rc47 Wave 6: the EDGAR-aligned derived aggregation, named for the same reason
    "outputs/pakemis_grid_0p1_edgar_aligned.nc",
    # v1.0.0: the semantic layer - the canonical CSVs (the identity of every fact and
    # dimension table) and the byte-stable contract; the Parquet twins stay unhashed, as
    # the annual and monthly twins do
    "outputs/semantic/*.csv",
    "outputs/semantic/semantic_release.json",
    # v1.0.0 Wave 4: the cells the national manuscript's figures draw - stored queries
    # against the semantic layer, one canonical CSV per registered figure
    "outputs/paper_figure_data/*.csv",
    # rc64: three tables the SECTOR PAPERS cite as evidence in a results or supplement
    # section while the deposit did not ship them, found by comparing every \texttt{outputs/...}
    # citation against the deposit manifest (outputs/pakemis_citation_deposit_audit.csv).
    # These three are the ones with no deposited equivalent: the transport pair is the
    # provincial-shape evidence behind the re-base, and the waste table carries the
    # Approach-1 independent and grouped percentages, which pakemis_joint_uncertainty.csv
    # does not hold. A fourth, agriculture_monthly_2024.csv, needed no entry - it is the
    # FY2023-24 slice of the nine-year monthly product that already ships, and the citation
    # was re-pointed at that instead.
    "outputs/transport_provincial_proxy_comparison_2024.csv",
    "outputs/transport_provincial_shape_brackets.csv",
    "outputs/waste_uncertainty_2024.csv",
    # A fourth, added on the second pass. Re-pointing its citation at the nine-year product
    # left a sector_headline table that no manuscript names, which trades one inconsistency
    # for another; the agriculture paper cites its own sector's monthly table and the
    # archive should hold it.
    "outputs/agriculture_monthly_2024.csv",
    # cycle 36, the same rule applied to nine more - and this time the citations came FIRST.
    # Closing the claim-read register at zero meant naming, in the sentence that already
    # discussed each one, nine files a registered claim reads and no manuscript named. Every
    # one of them was then cited-but-undeposited, so the debt moved one level down rather
    # than closing: a reader could find the name and not the file. Re-pointing the citation
    # at a deposited sibling - the fix used for agriculture_monthly_2024.csv above - is NOT
    # available here, because what makes these nine reader-facing is that a claim reads THIS
    # path and the paper prints the figure computed from it; a citation to a different file
    # would be a citation to different numbers. So the archive holds them.
    "outputs/air_uncertainty_montecarlo.csv",
    "outputs/industry_captive_screening_2024.csv",
    "outputs/n_ledger_2024.csv",
    "outputs/n_ledger_stage_comparison.csv",
    "outputs/national_gas_closure_variant.csv",
    "outputs/national_uncertainty_decomposition.csv",
    "outputs/transport_cng_2024.csv",
    "outputs/transport_cng_crosscheck_2024.csv",
    "outputs/waste_release_assignment_2024.csv",
    # cycle 37: the 22 the repository had ALREADY ruled on. tests/test_citation_deposit.py
    # calls a cited-but-undeposited `sector_headline` product "indefensible... there is
    # nothing to debate" - and that test was green only because the audit could not see the
    # notation the sector papers use. It matched \texttt{outputs/x.csv}, while the fugitives,
    # ippu, aviation, railways, residential, power, transport and waste appendices write the
    # bare \texttt{x.csv}, so 194 named files were invisible to it, 22 of them at this tier.
    # These are each sector's own headline outputs - totals, by-stream, provincial, monthly,
    # uncertainty - named in that sector's own paper. Re-citing a deposited sibling is not
    # available: the national products do not carry a sector's own stream split.
    "outputs/power_by_stream_fy2023_24.csv",
    "outputs/power_provincial_fy2023_24.csv",
    "outputs/power_totals_fy2023_24.csv",
    "outputs/railways_by_stream_2024.csv",
    "outputs/railways_monthly_2024.csv",
    "outputs/railways_provincial_2024.csv",
    "outputs/railways_totals_2024.csv",
    "outputs/railways_uncertainty_2024.csv",
    "outputs/residential_by_stream_2024.csv",
    "outputs/residential_configurations_by_year.csv",
    "outputs/residential_emissions_monthly_2024.csv",
    "outputs/residential_monthly_2024.csv",
    "outputs/residential_provincial_2024.csv",
    "outputs/residential_totals_2024.csv",
    "outputs/residential_uncertainty_2024.csv",
    "outputs/transport_by_stream_2024.csv",
    "outputs/transport_provincial_2024.csv",
    "outputs/transport_totals_2024.csv",
    "outputs/transport_uncertainty_2024.csv",
    "outputs/waste_by_stream_2024.csv",
    "outputs/waste_provincial_2024.csv",
    "outputs/waste_totals_2024.csv",
    # cycle 38: fugitives' and ippu's headline families, for the same reason one round later.
    # Their appendices DESCRIBED these tables and named none of them - "the process-matched
    # provincial allocation", "the completeness matrix", "national and provincial totals" -
    # so they were the uncited half of the same `sector_headline` gap. Naming them without
    # shipping them would move them straight into the tier this project's own test calls
    # indefensible, so the naming and the deposit land in one commit.
    "outputs/fugitives_by_stream_2024.csv",
    "outputs/fugitives_completeness_2024.csv",
    "outputs/fugitives_monthly_2024.csv",
    "outputs/fugitives_observation_provincial_evaluation_2024.csv",
    "outputs/fugitives_provincial_2024.csv",
    "outputs/fugitives_totals_2024.csv",
    "outputs/fugitives_uncertainty_2024.csv",
    "outputs/ippu_by_stream_2024.csv",
    "outputs/ippu_completeness_2024.csv",
    "outputs/ippu_fertilizer_gas_monthly_2024.csv",
    "outputs/ippu_monthly_2024.csv",
    "outputs/ippu_provincial_2024.csv",
    "outputs/ippu_totals_2024.csv",
    # cycle 39: aviation's and industry's headline families, closing the same gap for the two
    # remaining large cases. Aviation's five were in NEITHER of its appendix's lists - absent
    # rather than described-and-unnamed - and industry is the one covered sector with no paper
    # of its own, so its four are named in the national paper, where the 1.A.2 passage already
    # discusses the industry module by name.
    "outputs/aviation_by_stream_fy2023_24.csv",
    "outputs/aviation_completeness_fy2023_24.csv",
    "outputs/aviation_fuel_constrained_by_stream_fy2023_24.csv",
    "outputs/aviation_monthly_fy2023_24.csv",
    "outputs/aviation_provincial_fy2023_24.csv",
    "outputs/industry_by_stream_2024.csv",
    "outputs/industry_monthly_2024.csv",
    "outputs/industry_provincial_2024.csv",
    "outputs/industry_totals_2024.csv",
    # cycle 40: the last six, closing the sector_headline citation contract at zero. Power's
    # two were missing from the evidence list its own appendix already had; railways' GIS
    # provincial comes from the [gis] entry point and is a HELD product, not a phase output;
    # transport's and waste's monthly layers were absent from the sentence that lists what
    # their runners write; and the air provincial table was the described sibling in "and its
    # provincial, district and 1990-2024 timeseries siblings" - the fourth appearance of that
    # one shape, which reads as precise and is why nobody re-reads it.
    "outputs/power_monthly_fy2023_24.csv",
    "outputs/power_uncertainty_fy2023_24.csv",
    "outputs/railways_gis_provincial_2024.csv",
    "outputs/transport_monthly_2024.csv",
    "outputs/waste_monthly_2024.csv",
    # rc68: the evidence tables the rewritten manuscripts name. The rc68 rewrite stopped naming
    # them; restoring the citations (the v3 supplement's source-check paragraph, the
    # agriculture and waste appendices) made each one cited-but-undeposited, which is the
    # failure this list exists to close. Each is the evidence for a check the text describes -
    # a parse's own controls, the rows it quarantined, a cross-source shape comparison, the
    # coal and wastewater reconciliations, agriculture's own Monte Carlo and key categories -
    # so citing a deposited sibling would cite different numbers. The archive holds them.
    "outputs/agriculture_crop_residue_ledger_2024.csv",
    "outputs/agriculture_timing_classes.csv",
    "outputs/apcma_dispatch_parse_summary.csv",
    "outputs/apcma_dispatch_quarantine.csv",
    "outputs/apcma_qim_cement_crosscheck.csv",
    "outputs/era5_degree_day_crosscheck.csv",
    "outputs/fao_crop_calendar_crosscheck.csv",
    "outputs/key_categories.csv",
    "outputs/limestone_qim_cement_crosscheck.csv",
    "outputs/nfdc_monthly_parse_summary.csv",
    "outputs/nfdc_monthly_quarantine.csv",
    "outputs/ocac_direct_edition_crosscheck.csv",
    "outputs/ocac_direct_edition_quarantine.csv",
    "outputs/ocac_edition_currency.csv",
    "outputs/ocac_parse_summary.csv",
    "outputs/pbs_minerals_parse_summary.csv",
    "outputs/pbs_minerals_quarantine.csv",
    "outputs/pbs_qim_parse_summary.csv",
    "outputs/pbs_qim_quarantine.csv",
    "outputs/power_table3_hypotheses.csv",
    "outputs/power_toe_reconciliation.csv",
    "outputs/uncertainty_montecarlo.csv",
    "outputs/waste_uncertainty_inputs_2024.csv",
    "outputs/waste_uncertainty_scenarios_2024.csv",
)


def _products():
    """Hash what a reader downloads, not only what the engine read.

    The manifest hashed its INPUTS and nothing else, so a reader could verify the
    activity data behind a release and had no way to check that the data product in their
    hands was the one this release shipped. An external review asked for hashes on every
    paper and data artifact; the data half is here.

    THE PAPERS CANNOT BE. Hashing a PDF into this file would be circular: the release
    cover prints THIS file's digest, every paper inputs that cover, so a manifest
    containing PDF hashes changes the cover, which changes the PDFs, which changes their
    hashes. No fixpoint exists. The papers are hashed in outputs/pakemis_paper_hashes.csv
    instead, written after the build that produces them - and because LaTeX stamps a
    /CreationDate into every file, those hashes identify the DISTRIBUTED artifact rather
    than a target anyone can rebuild to. Everything listed here is byte-stable and is a
    rebuild target.
    """
    rows = [r for r in manifest_core.sha256_sources(PRODUCT_PATTERNS)
            # The paper-hash sidecar is written AFTER the papers, which are built after
            # this manifest - hashing it here reopens the same circle one level down and
            # the manifest can never describe its own tree. It is a product of the
            # release dance, not an input to it. pakemis_test_run.json is excluded for the
            # same reason and it is the sharper case: the suite tests this manifest, so a
            # manifest carrying the suite's result would depend on a run that depends on it.
            if not r["path"].endswith(("pakemis_paper_hashes.csv", "pakemis_test_run.json"))
            and r["path"] not in RETIRED_GHG_PANEL_PRODUCTS]
    for row in rows:
        row["byte_stable"] = True
    return rows


def main():
    body = build()
    manifest_core.write_manifest(OUT, body)
    total = body["national_totals"]
    print("Release manifest -> %s" % os.path.relpath(OUT, ROOT))
    print("  version %s  commit %s%s"
          % (body["version"], (body["git"]["describes_commit"] or "n/a")[:12],
             "  (TREE DIRTY)" if body["git"]["tree_dirty"] else ""))
    code = body["baseline_configuration"]["code"]
    other = next(k for k, value in total.items() if k != code and isinstance(value, dict))
    print("  baseline %s: %.2f Mt AR5   second configuration %s: %.2f Mt AR5"
          % (code, total[code]["co2e_Mt_AR5"], other, total[other]["co2e_Mt_AR5"]))
    print("  %d archived source documents hashed" % len(body["source_documents"]))
    print("  %d sectors, completeness %d rows %s, %d sources hashed, %d sector manifests"
          % (len(body["sectors"]), body["completeness"]["rows"],
             body["completeness"]["by_notation_key"], len(body["sources"]),
             len(body["sector_manifests"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
