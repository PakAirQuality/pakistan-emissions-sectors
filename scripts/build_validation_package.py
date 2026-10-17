"""Build the national validation package: one release, one commit, one tree, two files.

    dist/pakemis_<version>_full_validation.zip
    dist/pakemis_<version>_validation_manifest.json        (byte-identical to the copy inside)

WHAT THE PACKAGE IS. The package root is a repo-shaped tree - src/, scripts/, data/, outputs/,
tests/, docs/, the manuscripts - filtered by the deposit manifest, so the engine and the
release suite run in it unmodified with PKINV_ROOT pointing at it. On top of that tree sit the
folders the reviewer's specification names by role (registries/, outputs/annual/, manuscripts/,
code/, environment/, logs/). Every file in those folders is either a byte COPY of a canonical
file (recorded as presentation_copy with its source) or a VIEW computed from canonical files by
pkinv.report.validation_views (recorded with its generator). A slot in the specification that
no shipped product honestly fills is DECLARED in omitted_artifacts, never filled with an
invented table.

WHAT MAY BE COPIED is decided once, by the repository's existing custody machinery, not here:
a file enters the package iff outputs/pakemis_deposit_manifest.csv lists it with an outbound
licence in deposit_manifest.DEPOSITABLE, or it belongs to this project's own trees, or - for
the consumed rasters under data/gis/manual - its sidecar *_SOURCES.json declares an open
licence by name. Everything else (the 3.8 GB of source documents under sources/, the raw
publisher documents under data/raw, the ODbL flight archive under data/cache, PBS microdata)
enters as a REGISTER ROW with its SHA-256, size, publisher, retrieval date and the way to obtain
it. No licence is asserted at packaging time.

WHAT IS RUN, INSIDE THE BUILT TREE, BEFORE HASHING: validate.sh --quick, validate.sh --full,
reproduce.sh (a rebuild in a temporary copy compared against the packaged outputs) and,
when --docker is given, the same two validations in the shipped container. Their logs and
exit codes are part of the package; a failing test is recorded in KNOWN_EXCEPTIONS.json with
its name, never excluded to make the package green.

Usage:
  python3 scripts/build_validation_package.py [--docker] [--rehearse] [--allow-dirty] [--out DIR]
    --rehearse     build the tree and the records but do not run validations (layout work)
    --docker       run validate.sh --quick and --full inside environment/container/Dockerfile;
                   waits for the Docker daemon if it is not up
    --allow-dirty  permit a dirty working tree (rehearsals only; the record says so)
"""
import csv
import datetime as dt
import glob
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pkinv                                           # noqa: E402
from pkinv.report import deposit_manifest as deposit   # noqa: E402
from pkinv.report import validation_views as views     # noqa: E402
from pkinv.assets import catalog as asset_catalog, resolve, legacy_path

VERSION = pkinv.__version__
NAME = "pakemis_%s_validation" % VERSION
TEMPLATES = os.path.join(ROOT, "validation_package")

# The runnable tree: every tracked file under these, minus the hash-only trees below.
OWN_TREES = ("src", "scripts", "tests", "docs", "paper_national", "papers", "paper_common",
             "outputs", "validation_package", "capsule", ".github")
ROOT_FILES = ("Makefile", "pyproject.toml", "run_all.py", "CHANGELOG.md", "CITATION.cff", "README.md",
              "requirements.txt", "requirements.lock", "LICENSE", "LICENSE-data", ".zenodo.json",
              ".gitignore")   # two tests read it (dist/ is ignored); the package is not a checkout but says so
# Documents and external caches: register rows, never bytes (see module docstring).
HASH_ONLY = ("sources/", "data/cache/", "data/raw/")
RESTRICTED_PACKAGES = ("restricted-microdata",)
OPEN_LICENCE_WORDS = ("cc-by", "cc by", "public domain", "odbl", "open data")

THEMES = (("integrity", r"release_identity|release_integrity|build_definition|artifact_inventory|capsule|"
                        r"outputs_audit|deposit_licensing|csv_terminators|runner|build_order|validation_package|"
                        r"validation/"),
          ("source_extraction", r"transcription|ocac|pbs_|nfdc|trade_evidence|raw_data|source_streams|"
                                r"data_provenance|data_rederivation|census2024|gem_audit|climatetrace"),
          ("annual", r"annual|atomic|district_annual|national_rollup|national_series|timeseries|test_inventory|"
                     r"agriculture_fiscal"),
          ("monthly", r"monthly|period_labels|burn_windows|fertiliser_window|agriculture_timing|power_month"),
          ("spatial", r"grid_cube|adm2|spatial|downscale|test_gis|air_spatial|railways_gis|residential_gis|"
                      r"road_|district_records|manure_proxy|brick_kiln"),
          ("uncertainty", r"montecarlo|mc_draws|common_ensemble|uncertainty|ensemble_drivers|"
                          r"sensitivity|mms_sensitivity"),
          ("configurations", r"configuration|axis_register|scenario_variants|basis_vocabulary|parameters|"
                             r"method_registry|factor_table"),
          ("cross_sector", r"ledger|gas_closure|flatness_crosswalk|crt_crosswalk|unallocated_controls|"
                           r"cross_sector"),
          ("completeness", r"completeness|coverage_matrix|ne_categories|data_gaps|key_categories|"
                           r"validation_registry|validation_catalog|sector_contract|sector_qa|deferred"),
          ("manuscripts", r"paper_numbers|claims|figure_text|manuscript|_paper|table3"),
          ("clean_room", r"clean_room"))


def log(msg):
    stamp = dt.datetime.now().strftime("%H:%M:%S")
    line = "[%s] %s" % (stamp, msg)
    print(line, flush=True)
    with open(BUILD_LOG, "a", encoding="utf-8") as handle:
        handle.write(line + "\n")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def data_rows(path):
    with open(resolve(path, root=ROOT), encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True, text=True).stdout


def write_csv(path, fieldnames, rows, banner=None):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        if banner:
            for line in banner.splitlines():
                handle.write("# " + line + "\n")
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ----------------------------------------------------------------------------- custody

class Custody:
    """Per-file licence and inclusion, from the repository's own registers."""

    def __init__(self):
        self.deposit = {r["path"]: r for r in data_rows(os.path.join(ROOT, "outputs", "pakemis_deposit_manifest.csv"))}
        self.register = {deposit.storage_path(r["data_file"]): r for r in data_rows(os.path.join(ROOT, "outputs", "pakemis_source_register.csv"))}
        self.documents = {r["data_file"]: r for r in deposit.source_documents()}
        self.provenance = {deposit.storage_path(r["data_file"]): r for r in data_rows(os.path.join(ROOT, "outputs", "pakemis_data_provenance.csv"))}
        self.raw = {r["path"]: r for r in data_rows(os.path.join(ROOT, "data", "raw_manifest.csv"))}
        self.source_manifest = data_rows(os.path.join(ROOT, "data", "manifests", "source_manifest.csv"))
        # rc41: documents under sources/ the package SHIPS on the publisher's recorded
        # terms (path, sha256, licence_status, publisher, source_url, statement, read_by).
        # The digest is verified before the copy: a register row whose bytes changed is
        # a finding, not a licence.
        self.public_documents = {}
        for row in data_rows(os.path.join(ROOT, "data", "public_documents.csv")):
            if deposit.OUTBOUND_OF_LICENCE.get(row["licence_status"]) != deposit.PUBLIC_LICENCE:
                raise SystemExit("data/public_documents.csv: %s is typed %r, which the deposit "
                                 "vocabulary does not map to public-licence" % (row["path"], row["licence_status"]))
            held = os.path.join(ROOT, row["path"])
            if os.path.exists(held) and sha256(held) != row["sha256"]:
                raise SystemExit("data/public_documents.csv: %s does not match its registered "
                                 "sha256 - re-register the document before shipping it" % row["path"])
            self.public_documents[row["path"]] = row
        with open(os.path.join(ROOT, "outputs", "release_manifest.json"), encoding="utf-8") as handle:
            self.release_manifest = json.load(handle)
        self.hashed_documents = {d["path"]: d["sha256"] for d in self.release_manifest["source_documents"]}
        self.hashed_sources = {d["path"]: d["sha256"] for d in self.release_manifest["sources"]}
        self.sidecars = self._sidecars()

    def _sidecars(self):
        """Per-member licences from GIS sidecars, preserving original bundle scope."""
        out = {}
        assets = asset_catalog(root=ROOT)
        paths = {row["legacy_path"] for row in assets if row["legacy_path"].startswith("data/gis/")
                 and row["legacy_path"].endswith("_SOURCES.json")}
        # The safety net for a sidecar the catalog does not know. It used to walk
        # data/gis/, which the sector layout emptied; walking the CURRENT gis folders and
        # mapping each find back through legacy_path() keeps this loop's legacy keying
        # (the member match below compares against legacy_path) while the net stays real.
        roots = {os.path.dirname(row["path"]) for row in assets
                 if row["legacy_path"].startswith("data/gis/")}
        for root in sorted(roots):
            for folder, _dirs, names in os.walk(os.path.join(ROOT, root)):
                paths.update(
                    legacy_path(os.path.join(folder, name), root=ROOT) for name in names
                    if name.endswith("_SOURCES.json"))
        for relative in sorted(paths):
            folder = os.path.dirname(relative)
            with open(resolve(os.path.join(ROOT, relative), root=ROOT), encoding="utf-8") as handle:
                try:
                    doc = json.load(handle)
                except ValueError:
                    continue
            folder_licence = doc.get("licence") or doc.get("license") or ""
            for key, value in doc.items():
                if isinstance(value, dict):
                    lic = value.get("licence") or value.get("license") or ""
                    out[deposit.storage_path(os.path.join(folder, key))] = lic
                    for sub, subval in value.items():
                        if isinstance(subval, dict):
                            out[deposit.storage_path(os.path.join(folder, sub))] = (
                                subval.get("licence") or subval.get("license") or folder_licence)
            if folder_licence:
                members = [row["path"] for row in assets
                           if os.path.dirname(row["legacy_path"]) == folder]
                old_folder = os.path.join(ROOT, folder)
                if os.path.isdir(old_folder):
                    members.extend(os.path.join(folder, other) for other in os.listdir(old_folder))
                for rel in members:
                    out.setdefault(rel, folder_licence)
        return out

    def disposition(self, rel):
        """('copy'|'hash_only', licence_status, redistribution_status, reason)."""
        dep = self.deposit.get(rel)
        if dep is not None:
            if dep["outbound_licence"] in deposit.DEPOSITABLE:
                return ("copy", dep["outbound_licence"], "redistributable (deposit manifest)", dep["licence_reason"])
            return ("hash_only", dep["outbound_licence"], "not redistributed", dep["licence_reason"])
        if rel.startswith(HASH_ONLY):
            raw = self.raw.get(rel, {})
            reg = self.register.get(rel) or self.documents.get(rel)
            lic = (reg or {}).get("outbound_redistribution") or (reg or {}).get("licence_status") or raw.get("licence", "")
            if raw.get("package") in RESTRICTED_PACKAGES:
                return ("hash_only", lic or "restricted-microdata", "prohibited (registration terms)",
                        "PBS microdata under registration terms; facts derived are in data/activity")
            return ("hash_only", lic or deposit.NOT_ESTABLISHED, "not redistributed",
                    "publisher document or external cache; hash and acquisition recorded")
        if legacy_path(rel, root=ROOT).startswith("data/gis/manual/"):
            lic = self.sidecars.get(rel, "")
            if any(w in lic.lower() for w in OPEN_LICENCE_WORDS):
                return ("copy", "public-licence", "redistributable (sidecar: %s)" % lic,
                        "consumed raster; licence declared in its *_SOURCES.json sidecar")
            return ("hash_only", lic or deposit.NOT_ESTABLISHED, "not redistributed",
                    "consumed raster whose sidecar states no open licence: %r" % lic)
        if rel.startswith("data/"):
            doc = self.documents.get(rel)
            if doc is not None:
                out = deposit.OUTBOUND_OF_LICENCE.get(doc.get("licence_status", ""), deposit.NOT_ESTABLISHED)
                if out in deposit.DEPOSITABLE:
                    return ("copy", out, "redistributable", "listed in data/source_documents.csv")
                prov = self.provenance.get(rel, {})
                if prov.get("class", "").startswith("hand:") or prov.get("class") == "producer":
                    return ("copy", deposit.COMPILATION, "redistributable (own transcription of published facts)",
                            "this project's transcription; the document itself is registered, not shipped")
                return ("hash_only", out, "not redistributed", "document terms not established")
            prov = self.provenance.get(rel, {})
            if prov.get("class", "").startswith("hand:held-source"):
                return ("copy", deposit.COMPILATION, "redistributable (own transcription of published facts)",
                        "this project's transcription; the document itself is registered, not shipped")
            return ("copy", deposit.OWN_WORK, "redistributable", "this project's own data file")
        return ("copy", deposit.OWN_WORK, "redistributable", "this project's own code, product or prose")


# ----------------------------------------------------------------------------- the tree

def tracked_files():
    """Tracked files plus declared inputs and the owned-code package allowlist.

    data/gis is enumerated from DISK, as the deposit manifest enumerates it: .gitignore
    excludes most of it and re-includes the consumed grids by name, and the rc32 exact-area
    partition (adm2_intersections_267x340.csv) is consumed by the cube, listed in the deposit
    as this project's own compilation, and gitignored - so a git-only universe left the
    package unable to build its ADM2 marginals."""
    # An unstaged deletion is absent from this working-tree snapshot, even
    # though git's index still lists its former path. Required declared assets
    # added below retain their normal missing-input checks.
    files = [p for p in git("ls-files").splitlines()
             if p and os.path.lexists(os.path.join(ROOT, p))]
    # An authorized working-tree rehearsal must include new modules before the
    # user stages them. Reuse the deposit's explicit owned-file patterns; never
    # sweep arbitrary untracked files into a package.
    for kind, patterns in deposit.DEPOSIT_PATTERNS:
        if kind not in {"code", "build", "documentation"}:
            continue
        for pattern in patterns:
            files.extend(os.path.relpath(path, ROOT)
                         for path in glob.glob(os.path.join(ROOT, pattern), recursive=True)
                         if os.path.isfile(path))
    # All relocations are catalogued before they are staged in git. This also
    # retains declared ignored GIS companions in an unpacked checkout.
    for asset in asset_catalog(root=ROOT):
        files.append(asset["path"])
        if asset.get("canonical_path"):
            files.append(asset["canonical_path"])
    files.append("data/catalog/assets.csv")
    files.append("data/catalog/migrations.csv")
    files.extend(deposit.reviewer_guides())
    gis = os.path.join(ROOT, "data", "gis")
    if os.path.isdir(gis):
        for folder, _dirs, names in os.walk(gis):
            for name in names:
                if name.startswith("."):
                    continue
                rel = os.path.relpath(os.path.join(folder, name), ROOT)
                if rel not in files:
                    files.append(rel)
    return sorted(set(files))


def in_runnable_tree(rel):
    top = rel.split("/")[0]
    return (top in OWN_TREES or rel in ROOT_FILES or rel.startswith("data/")) and not rel.startswith("dist/")


def copy_runnable_tree(pkg, custody):
    inventory, registered = [], []
    # Documents the source register types PUBLIC-LICENCE (EDGAR, FAOSTAT, UNFCCC, US
    # government) ARE copied, from the register's own per-document decision: the deposit
    # excludes all of sources/ as a rule about the Zenodo deposit's shape, but the licence
    # answer is per document and this package ships what the publisher permits.
    # rc41: data/public_documents.csv is the second, explicit list - documents build
    # phases read from sources/ whose publisher's terms the repository already records
    # (the UNFCCC CRT zip that six official_reporting modules open). One fact, one
    # place: the packager copies exactly the register's public-licence rows plus these.
    public_paths = tuple(r["archived_path"].rstrip("/") for r in custody.register.values()
                         if r.get("outbound_redistribution") == deposit.PUBLIC_LICENCE and r.get("archived_path"))
    public_paths += tuple(r["path"].rstrip("/") for r in custody.public_documents.values())
    # Source/schema recipe inputs may be generated or not yet tracked. Copy only
    # this explicit addition to the existing package scope, under deposit custody.
    recipe = deposit.canonical_recipe_inputs()
    missing = recipe - set(custody.deposit)
    if missing:
        raise RuntimeError("canonical recipe is absent from deposit manifest: %s" % sorted(missing))
    declared_assets = {row["path"] for row in asset_catalog(root=ROOT)}
    missing_files = {path for path in recipe | declared_assets
                     if not os.path.isfile(os.path.join(ROOT, path))}
    if missing_files:
        raise RuntimeError("declared package inputs are missing: %s" % sorted(missing_files))
    canonical_copies = deposit._canonical_source_paths()
    for rel in sorted(set(tracked_files()) | recipe):
        if rel in canonical_copies:
            continue                         # rebuilt from the deposited recipe below
        if not in_runnable_tree(rel):
            if rel.startswith("sources/") and any(rel == p or rel.startswith(p + "/") for p in public_paths):
                dst = os.path.join(pkg, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(os.path.join(ROOT, rel), dst)
                inventory.append((rel, deposit.PUBLIC_LICENCE, "redistributable (publisher's stated licence, per the source register)",
                                  "source_document", ""))
                continue
            # sources/ and the other document trees live outside the runnable tree; they
            # are REGISTERED with their custody answer so the source manifest can name them
            if rel.startswith(HASH_ONLY):
                action, licence, redistribution, reason = custody.disposition(rel)
                registered.append((rel, licence, redistribution, reason))
            continue
        if rel.startswith(("data/gis/",)) and rel.endswith((".npy.txt",)):
            pass
        action, licence, redistribution, reason = custody.disposition(rel)
        src = os.path.join(ROOT, rel)
        if os.path.islink(src):
            raise RuntimeError("symlink in the tree: %s" % rel)
        if not os.path.exists(src):
            continue
        if action == "copy":
            dst = os.path.join(pkg, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
            inventory.append((rel, licence, redistribution, "product" if rel.startswith("outputs/") else "source", ""))
        else:
            registered.append((rel, licence, redistribution, reason))
    return inventory, registered


# ----------------------------------------------------------------------------- presentation layer

def layout(pkg):
    """[(package path, kind, source-or-generator)] for the specification's folders.

    kind: 'copy' (byte copy of a canonical file inside the package), 'view' (a callable
    (root, out) -> rows from validation_views), 'text' (a literal written here)."""
    P = []
    def copy(dst, src): P.append((dst, "copy", deposit.storage_path(src)))
    def view(dst, fn): P.append((dst, "view", fn))

    # registries/
    copy("registries/periods.csv", "data/periods.csv")
    copy("registries/months.csv", "data/months.csv")
    view("registries/sectors.csv", views.sectors_registry)
    copy("registries/ipcc_scope.csv", "data/scope_registry.csv")
    view("registries/components.csv", views.components_registry)
    copy("registries/configurations.csv", "outputs/national_configurations.csv")
    copy("registries/bridge_configurations.csv", "data/bridge_configurations.csv")
    copy("registries/structural_axes.csv", "outputs/national_axis_register.csv")
    copy("registries/scenarios.csv", "data/scenarios.csv")
    view("registries/invalid_configuration_combinations.csv", views.invalid_combinations)
    copy("registries/methods.csv", "data/method_registry.csv")
    view("registries/uncertainty_models.csv", views.uncertainty_models_registry)
    copy("registries/uncertainty_parameters.csv", "outputs/national_uncertainty_parameters.csv")
    copy("registries/uncertainty_sources.csv", "outputs/national_uncertainty_sources.csv")
    copy("registries/parameters.csv", "data/parameters.csv")
    copy("registries/correlation_groups.csv", "data/dependency_group_rules.csv")
    copy("registries/parameter_scope.csv", "data/parameter_scope.csv")
    copy("registries/parameter_scope_exclusions.csv", "data/parameter_scope_exclusions.csv")
    copy("registries/member_bindings.csv", "data/member_bindings.csv")
    copy("registries/uncertainty_reconciliation.csv", "data/uncertainty_reconciliation.csv")
    copy("registries/temporal_profiles.csv", "data/temporal_profiles.csv")
    copy("registries/temporal_driver_registry.csv", "data/temporal_driver_registry.csv")
    copy("registries/spatial_profiles_grid_proxy.csv", "data/stream_grid_proxy.csv")
    copy("registries/spatial_profiles_geometry.csv", "data/stream_geometry.csv")
    copy("registries/spatial_profiles_alternatives.csv", "data/stream_spatial_alternatives.csv")
    copy("registries/allowed_grid_fallbacks.csv", "data/allowed_grid_fallbacks.csv")
    copy("registries/geographies.csv", "data/adm2_canonical.csv")
    copy("registries/province_shares.csv", "data/province_shares.csv")
    copy("registries/geometry_crosswalk.csv", "data/adm2_crosswalk.csv")
    copy("registries/geometry_sets.csv", "data/geometry_sets.csv")
    copy("registries/source_documents.csv", "data/source_documents.csv")
    copy("registries/source_streams.csv", "outputs/pakemis_source_streams.csv")
    copy("registries/emission_factors.csv", "data/emission_factors.csv")
    view("registries/units.csv", views.units_registry)
    view("registries/gwp.csv", views.gwp_registry)
    view("registries/licences.csv", views.licences_registry)
    view("registries/notation_keys.csv", views.notation_keys_registry)
    copy("registries/product_schemas.csv", "data/product_schemas.csv")
    copy("registries/product_columns.csv", "data/product_columns.csv")
    copy("registries/cross_sector_ledger_map.csv", "data/cross_sector_ledger_map.csv")
    copy("registries/validation_catalog.csv", "data/validation_catalog.csv")
    copy("registries/benchmark_tasks.csv", "data/benchmark_tasks.csv")
    copy("registries/claims_registry.csv", "data/claims_registry.csv")

    # outputs/annual
    for name in ("pakemis_atomic_annual.csv", "pakemis_atomic_annual.parquet", "pakemis_atomic_annual_aggregates.csv",
                 "pakemis_annual_fy2015_16_fy2024_25.csv", "pakemis_annual_fy2015_16_fy2024_25.parquet",
                 "pakemis_national_series.csv", "pakemis_national_series_coverage.csv", "national_all_sectors.csv",
                 "national_all_sectors_ledger.csv", "pakemis_agriculture_basis_change.csv",
                 "pakemis_series_splice_agriculture.csv", "pakemis_coverage_summary.csv"):
        copy("outputs/annual/%s" % name, "outputs/%s" % name)
    view("outputs/annual/sector_totals.csv", views.sector_totals)
    view("outputs/annual/category_totals.csv", views.category_totals)
    view("outputs/annual/gas_totals.csv", views.gas_totals)
    view("outputs/annual/configuration_totals.csv", views.configuration_totals)
    view("outputs/annual/national_ar5_ar6_bridge.csv", views.ar5_ar6_bridge)
    view("outputs/annual/annual_closure_report.csv", views.annual_closure_report)
    copy("outputs/annual/annual_method_basis_seams.csv", "outputs/pakemis_agriculture_basis_change.csv")

    # outputs/monthly
    for name in ("pakemis_monthly_fy2015_16_fy2024_25.csv", "pakemis_monthly_fy2015_16_fy2024_25.parquet",
                 "pakemis_monthly_coverage.csv", "pakemis_monthly_coverage_summary.csv", "pakemis_monthly_controls.csv",
                 "pakemis_temporal_profiles.csv", "pakemis_monthly_evidence.csv", "pakemis_temporal_decomposition.csv",
                 "pakemis_monthly_data_requests.csv", "pakemis_flatness_crosswalk.csv", "monthly_crosschecks.csv",
                 "benchmark_temporal_hindcast.csv"):
        copy("outputs/monthly/%s" % name, "outputs/%s" % name)
    copy("outputs/monthly/monthly_coverage.csv", "outputs/pakemis_monthly_coverage_summary.csv")
    view("outputs/monthly/annual_monthly_closure.csv", views.annual_monthly_closure)
    copy("outputs/monthly/temporal_evidence_by_stream.csv", "outputs/pakemis_temporal_profiles.csv")
    copy("outputs/monthly/temporal_evidence_by_sector.csv", "outputs/pakemis_monthly_evidence.csv")
    copy("outputs/monthly/temporal_profile_values.csv", "data/temporal_profiles.csv")
    copy("outputs/monthly/temporal_validation.csv", "outputs/benchmark_temporal_hindcast.csv")
    copy("outputs/monthly/variable_but_unobserved_mass.csv", "outputs/pakemis_temporal_decomposition.csv")
    view("outputs/monthly/monthly_exceptions.csv", views.monthly_exceptions)

    # outputs/spatial
    copy("outputs/spatial/national/national_all_sectors.csv", "outputs/national_all_sectors.csv")
    copy("outputs/spatial/national/national_totals_2024.csv", "outputs/national_totals_2024.csv")
    copy("outputs/spatial/adm1/provincial_totals_2024.csv", "outputs/provincial_totals_2024.csv")
    copy("outputs/spatial/adm1/provincial_by_category.csv", "outputs/provincial_by_category.csv")
    copy("outputs/spatial/adm1/pakemis_spatial_unallocated.csv", "outputs/pakemis_spatial_unallocated.csv")
    copy("outputs/spatial/adm1/pakemis_adm1_ledger_2024.csv", "outputs/pakemis_adm1_ledger_2024.csv")
    copy("outputs/spatial/stream_surfaces.csv", "outputs/pakemis_grid_stream_surfaces.csv")
    for name in ("pakemis_adm2_monthly.csv", "pakemis_adm2_monthly_sector.csv", "pakemis_adm2_ledger_2024.csv",
                 "pakemis_adm2_crosswalk.csv", "district_totals_2024.csv", "pakemis_kiln_allocation_adm2.csv",
                 "pakemis_road_length_adm2.csv", "pakemis_road_weights_adm2.csv"):
        copy("outputs/spatial/adm2/%s" % name, "outputs/%s" % name)
    copy("outputs/spatial/adm2/district_totals_by_year.csv", "outputs/districts/district_totals_by_year.csv")
    copy("outputs/spatial/native_geometries/PAK_ADM1.geojson", "data/gis/PAK_ADM1.geojson")
    copy("outputs/spatial/native_geometries/PAK_ADM2.geojson", "data/gis/PAK_ADM2.geojson")
    copy("outputs/spatial/native_geometries/BOUNDARY_SOURCES.json", "data/gis/BOUNDARY_SOURCES.json")
    copy("outputs/spatial/native_geometries/pakemis_road_links.parquet", "outputs/pakemis_road_links.parquet")
    copy("outputs/spatial/native_geometries/pakemis_facility_registry.csv", "outputs/pakemis_facility_registry.csv")
    copy("outputs/spatial/native_geometries/pak_rail_network.geojson", "data/gis/rail/pak_rail_network.geojson")
    copy("outputs/spatial/grid_005deg/pakemis_grid_0p05_monthly.nc", "outputs/pakemis_grid_0p05_monthly.nc")
    copy("outputs/spatial/grid_005deg/pakemis_grid_0p05_monthly_ledger.nc", "outputs/pakemis_grid_0p05_monthly_ledger.nc")
    copy("outputs/spatial/grid_005deg/PROXY_SOURCES.md", "data/gis/PROXY_SOURCES.md")
    copy("outputs/spatial/spatial_decomposition.csv", "outputs/pakemis_spatial_decomposition.csv")
    copy("outputs/spatial/spatial_unallocated.csv", "outputs/pakemis_spatial_unallocated.csv")
    copy("outputs/spatial/spatial_exceptions.csv", "outputs/pakemis_spatial_exceptions.csv")
    view("outputs/spatial/source_stream_spatial_metadata.csv", views.source_stream_spatial_metadata)
    copy("outputs/spatial/adm1_closure.csv", "outputs/pakemis_grid_provincial_check.csv")
    copy("outputs/spatial/adm2_nesting_check.csv", "outputs/pakemis_adm2_nesting_check.csv")
    view("outputs/spatial/grid_closure.csv", views.grid_closure)
    copy("outputs/spatial/geometry_coverage.csv", "outputs/pakemis_product_coverage.csv")
    copy("outputs/spatial/proxy_fallbacks.csv", "outputs/pakemis_grid_fallbacks.csv")
    copy("outputs/spatial/spatial_validation.csv", "outputs/benchmark_spatial_allocation.csv")
    for name in ("pakemis_spatial_brackets.csv", "pakemis_spatial_brackets_adm2.csv",
                 "pakemis_rice_geography_crosscheck.csv", "pakemis_builtup_comparison_adm2.csv",
                 "benchmark_kiln_allocation.csv"):
        copy("outputs/spatial/%s" % name, "outputs/%s" % name)

    # outputs/uncertainty
    copy("outputs/uncertainty/uncertainty_parameter_registry.csv", "outputs/national_uncertainty_parameters.csv")
    copy("outputs/uncertainty/uncertainty_montecarlo.csv", "outputs/national_uncertainty_montecarlo.csv")
    copy("outputs/uncertainty/national_uncertainty.csv", "outputs/national_uncertainty_montecarlo.csv")
    copy("outputs/uncertainty/national_uncertainty_reconciliation.csv", "outputs/national_uncertainty_reconciliation.csv")
    view("outputs/uncertainty/correlation_matrix.csv", views.correlation_matrix)
    for name in ("annual", "monthly", "spatial"):
        copy("outputs/uncertainty/common_draw_%s.parquet" % name, "outputs/mc_draws/pakemis_ensemble_%s.parquet" % name)
        copy("outputs/uncertainty/common_draw_%s.meta.json" % name, "outputs/mc_draws/pakemis_ensemble_%s.meta.json" % name)
    copy("outputs/uncertainty/common_draw_summary.csv", "outputs/pakemis_ensemble_summary.csv")
    copy("outputs/uncertainty/common_draw_ledger_summary.csv", "outputs/pakemis_ensemble_ledger_summary.csv")
    copy("outputs/uncertainty/common_draw_spatial_conditionals.csv", "outputs/pakemis_ensemble_spatial_conditionals.csv")
    copy("outputs/uncertainty/trend_uncertainty.csv", "outputs/pakemis_trend_uncertainty.csv")
    copy("outputs/uncertainty/key_category_uncertainty.csv", "outputs/national_key_categories.csv")
    view("outputs/uncertainty/uncertainty_exceptions.csv", views.uncertainty_exceptions)
    for name in ("national_uncertainty_decomposition.csv", "pakemis_uncertainty_drivers.csv",
                 "national_uncertainty_convergence.csv", "pakemis_joint_uncertainty.csv",
                 "pakemis_longitudinal_uncertainty.csv", "national_uncertainty_sources.csv"):
        copy("outputs/uncertainty/%s" % name, "outputs/%s" % name)

    # outputs/configurations
    copy("outputs/configurations/structural_axes.csv", "outputs/national_axis_register.csv")
    copy("outputs/configurations/national_structural_bridge.csv", "outputs/national_structural_bridge.csv")
    copy("outputs/configurations/national_configurations.csv", "outputs/national_configurations.csv")
    view("outputs/configurations/configuration_dependencies.csv", views.configuration_dependencies)
    view("outputs/configurations/invalid_combinations.csv", views.invalid_combinations)
    copy("outputs/configurations/bridge_configurations.csv", "outputs/pakemis_bridge_configurations.csv")
    copy("outputs/configurations/configuration_trajectories_nine_years.csv", "outputs/pakemis_structural_trajectories.csv")
    for name in ("residential_configurations_2024.csv", "commercial_scope_configuration_2024.csv",
                 "fugitives_structural_scenarios_2024.csv", "national_dung_variants.csv",
                 "national_gas_closure_variant.csv", "aviation_carrier_share_scenarios.csv",
                 "ippu_cement_valid_structural_2024.csv"):
        copy("outputs/configurations/sector/%s" % name, "outputs/%s" % name)

    # outputs/cross_sector
    view("outputs/cross_sector/cross_sector_closure_registry.csv", views.cross_sector_registry)
    view("outputs/cross_sector/cross_sector_closure_report.csv", views.cross_sector_closure_report)
    copy("outputs/cross_sector/dung_transfer.csv", "outputs/residential_dung_ledger_2024.csv")
    copy("outputs/cross_sector/dung_variants.csv", "outputs/national_dung_variants.csv")
    copy("outputs/cross_sector/crop_residue_transfer.csv", "outputs/agriculture_crop_residue_ledger_2024.csv")
    copy("outputs/cross_sector/delivered_gas_combustion_fugitive_ledger.csv", "outputs/national_gas_closure.csv")
    copy("outputs/cross_sector/post_meter_end_use.csv", "outputs/fugitives_post_meter_end_use_2024.csv")
    copy("outputs/cross_sector/generator_petrol_transfer.csv", "outputs/transport_fuel_ledger_2024.csv")
    copy("outputs/cross_sector/road_diesel_offroad_partition.csv", "outputs/transport_fuel_ledger_2024.csv")
    copy("outputs/cross_sector/waste_fate_ledger.csv", "outputs/waste_ledger_2024.csv")
    copy("outputs/cross_sector/fertiliser_feedstock_combustion_urea_ledger.csv", "outputs/ippu_urea_co2_bridge_2025.csv")
    copy("outputs/cross_sector/urea_basis.csv", "outputs/agriculture_urea_basis.csv")
    copy("outputs/cross_sector/nitrogen_ledger.csv", "outputs/n_ledger_2024.csv")
    copy("outputs/cross_sector/unallocated_activity_controls.csv", "outputs/pakemis_unallocated_activity_controls.csv")

    # outputs/completeness
    copy("outputs/completeness/completeness.csv", "outputs/completeness.csv")
    copy("outputs/completeness/completeness_matrix.csv", "outputs/pakemis_coverage_matrix.csv")
    copy("outputs/completeness/completeness_mass.csv", "outputs/pakemis_completeness_mass.csv")
    view("outputs/completeness/unbounded_gaps.csv", lambda r, o: views.gaps(r, o, bounded=False))
    view("outputs/completeness/bounded_gaps.csv", lambda r, o: views.gaps(r, o, bounded=True))
    view("outputs/completeness/ie_destination_registry.csv", views.ie_destination_registry)
    copy("outputs/completeness/scope_exclusions.csv", "data/scope_registry.csv")
    view("outputs/completeness/lulucf_scope_decision.csv", views.lulucf_scope_decision)
    copy("outputs/completeness/completeness_validation.csv", "outputs/pakemis_pass2_scorecard.csv")
    copy("outputs/completeness/data_gaps.csv", "data/data_gaps.csv")
    copy("outputs/completeness/lulucf_report.md", "outputs/lulucf_report.md")

    # outputs/validation
    copy("outputs/validation/validation_catalogue.csv", "outputs/pakemis_validation_catalog.csv")
    view("outputs/validation/comparison_independence_matrix.csv", views.independence_matrix)
    copy("outputs/validation/annual_benchmarks.csv", "outputs/national_benchmark_comparison.csv")
    copy("outputs/validation/spatial_benchmarks.csv", "outputs/benchmark_spatial_allocation.csv")
    copy("outputs/validation/temporal_benchmarks.csv", "outputs/benchmark_temporal_hindcast.csv")
    copy("outputs/validation/source_extraction_audit.csv", "data/transcription_checks.csv")
    copy("outputs/validation/withheld_validation.csv", "data/benchmark_tasks.csv")
    view("outputs/validation/benchmark_results.csv", views.benchmark_results)
    view("outputs/validation/validation_limitations.csv", views.validation_limitations)
    for name in ("pakemis_validation_scorecard.csv", "pakemis_validation_sector_scorecard.csv",
                 "national_benchmark_scope_coverage.csv", "timeseries_validation.csv", "benchmark_kiln_allocation.csv",
                 "benchmark_air_comparison.csv", "aviation_independence_matrix.csv"):
        copy("outputs/validation/%s" % name, "outputs/%s" % name)

    # manuscripts/
    for name in os.listdir(os.path.join(pkg, "papers", "pdf")):
        if name.endswith(".pdf"):
            dst = "manuscripts/%s" % name if name.startswith("national_") else "manuscripts/sector_reports/%s" % name
            copy(dst, "papers/pdf/%s" % name)
    copy("manuscripts/README.md", "papers/pdf/README.md")
    copy("manuscripts/paper_hashes.csv", "outputs/pakemis_paper_hashes.csv")
    copy("manuscripts/release_cover.tex", "paper_common/release_cover.tex")
    for folder, _dirs, names in os.walk(os.path.join(pkg, "paper_national")):
        for name in names:
            if name.endswith((".tex", ".bib")):
                rel = os.path.relpath(os.path.join(folder, name), pkg)
                copy("manuscripts/paper_sources/%s" % rel, rel)
    for folder, _dirs, names in os.walk(os.path.join(pkg, "papers")):
        for name in names:
            if name.endswith((".tex", ".bib")):
                rel = os.path.relpath(os.path.join(folder, name), pkg)
                copy("manuscripts/paper_sources/%s" % rel, rel)
    for name in ("preamble.tex", "references.bib"):
        copy("manuscripts/paper_sources/paper_common/%s" % name, "paper_common/%s" % name)
    figures = os.path.join(pkg, "outputs", "figures")
    if os.path.isdir(figures):
        for name in sorted(os.listdir(figures)):
            copy("manuscripts/generated_figures/%s" % name, "outputs/figures/%s" % name)

    # code/
    for tree in ("src", "scripts"):
        for folder, dirs, names in os.walk(os.path.join(pkg, tree)):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in names:
                rel = os.path.relpath(os.path.join(folder, name), pkg)
                copy("code/%s" % rel, rel)
    for name in ("Makefile", "pyproject.toml", "run_all.py"):
        copy("code/%s" % name, name)
    for name in ("requirements.txt", "requirements.lock", ".github/workflows/ci.yml"):
        copy("code/configs/%s" % os.path.basename(name), name)
    copy("code/paper_sources/README.md", "papers/pdf/README.md")
    return P


# ----------------------------------------------------------------------------- execution

def run(cmd, cwd, log_path=None, env=None, timeout=None):
    start = time.time()
    with open(log_path, "a", encoding="utf-8") if log_path else open(os.devnull, "w") as out:
        proc = subprocess.run(cmd, cwd=cwd, stdout=out, stderr=subprocess.STDOUT, env=env, timeout=timeout)
    return proc.returncode, round(time.time() - start, 1)


def docker_ready():
    return subprocess.run(["docker", "info"], capture_output=True).returncode == 0


def write_sha256sums(pkg, skip=("SHA256SUMS", "VALIDATION_MANIFEST.json")):
    """SHA256SUMS over every file in pkg except `skip`; returns the sorted (path, digest) list."""
    sums = []
    for folder, dirs, names in os.walk(pkg):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(names):
            rel = os.path.relpath(os.path.join(folder, name), pkg)
            if rel in skip:
                continue
            sums.append((rel, sha256(os.path.join(folder, name))))
    sums.sort()
    with open(os.path.join(pkg, "SHA256SUMS"), "w", encoding="utf-8") as h:
        h.write("".join("%s  %s\n" % (d, r) for r, d in sums))
    return sums


def write_inventory(pkg, presentation, inventory_rows):
    """FILE_INVENTORY.csv over every file present in pkg now. Called twice: before the
    in-tree validations (the enumeration tests read it to know the reading index) and,
    authoritatively, after everything is written. Returns (copied, pres)."""
    artifact = {r["artifact"]: r for r in data_rows(os.path.join(ROOT, "outputs", "pakemis_artifact_inventory.csv"))}
    pres = {dst: (kind, src) for dst, kind, src in presentation}
    copied = {rel: (lic, redist, gen) for rel, lic, redist, gen, _ in inventory_rows}
    schemas = {r["relative_path"]: r for r in data_rows(os.path.join(ROOT, "data", "product_schemas.csv"))}
    canonical_sources = deposit._canonical_source_paths()
    source_documents = {r["data_file"]: r for r in deposit.source_documents()}
    inv = []
    for folder, dirs, names in os.walk(pkg):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(names):
            rel = os.path.relpath(os.path.join(folder, name), pkg)
            if rel in ("SHA256SUMS", "FILE_INVENTORY.csv", "VALIDATION_MANIFEST.json"):
                continue
            path = os.path.join(folder, name)
            row = {"relative_path": rel, "size_bytes": os.path.getsize(path), "sha256": sha256(path),
                   "artifact_role": "", "source_or_product_id": "", "required_for_validation": "yes",
                   "licence_status": "own-work", "redistribution_status": "redistributable",
                   "generated_or_source": "", "generation_command": ""}
            if rel in pres:
                kind, src = pres[rel]
                if kind == "copy":
                    row.update(artifact_role="presentation_copy", source_or_product_id=src, generated_or_source="presentation_copy",
                               required_for_validation="no", generation_command="copy of %s" % src)
                    if src in copied:
                        row.update(licence_status=copied[src][0], redistribution_status=copied[src][1])
                else:
                    row.update(artifact_role="view", source_or_product_id="pkinv.report.validation_views.%s" % getattr(src, "__name__", "view"),
                               generated_or_source="view", required_for_validation="no",
                               generation_command="python3 -c 'from pkinv.report import validation_views as v; v.%s(ROOT, %r)'"
                               % (getattr(src, "__name__", "view"), rel))
            elif rel in canonical_sources:
                licence, reason = deposit.licence_of_deposited(rel, source_documents)
                row.update(artifact_role="canonical_input", source_or_product_id=canonical_sources[rel],
                           licence_status=licence, redistribution_status="redistributable (%s)" % reason,
                           generated_or_source="generated",
                           generation_command="python3 -m pkinv.activity.build")
            elif rel in copied:
                lic, redist, gen = copied[rel]
                role = artifact.get(rel.replace("outputs/", ""), {}).get("role", "") if rel.startswith("outputs/") else ""
                row.update(artifact_role=role or ("product" if rel.startswith("outputs/") else rel.split("/")[0]),
                           source_or_product_id=schemas.get(rel, {}).get("product_id", rel), licence_status=lic,
                           redistribution_status=redist, generated_or_source=gen,
                           generation_command="python3 run_all.py" if rel.startswith("outputs/") else "")
            elif rel.startswith("logs/"):
                row.update(artifact_role="log", generated_or_source="generated", required_for_validation="no",
                           generation_command="written by validate.sh / reproduce.sh / the packager")
            elif rel.startswith("environment/"):
                row.update(artifact_role="environment", generated_or_source="generated", generation_command="scripts/build_validation_package.py")
            elif rel.startswith(("data/SOURCE_MANIFEST", "data/restricted_sources/", "data/source_extracts/", "tests/test_catalogue", "manuscripts/paper_claim")):
                inputs = {"data/SOURCE_MANIFEST": "data/source_documents.csv;outputs/pakemis_source_register.csv;data/raw_manifest.csv;data/manifests/source_manifest.csv;outputs/release_manifest.json",
                          "data/restricted_sources/": "data/source_documents.csv;outputs/pakemis_source_register.csv",
                          "data/source_extracts/": "outputs/pakemis_data_provenance.csv;data/transcription_checks.csv",
                          "tests/test_catalogue": "tests/",
                          "manuscripts/paper_claim": "tests/paper_numbers/doc_claims.py;data/claims_registry.csv"}
                source = next(v for k, v in inputs.items() if rel.startswith(k))
                row.update(artifact_role="register", generated_or_source="view", source_or_product_id=source,
                           required_for_validation="yes" if "SOURCE_MANIFEST" in rel else "no",
                           generation_command="scripts/build_validation_package.py (%s)" % (
                               "restricted_and_source_manifest" if rel.startswith("data/") and "extract" not in rel
                               else "source_extract_index" if "extract" in rel
                               else "tests/validation/claim_registry.py" if "claim" in rel else "validation_views.test_catalogue"))
            else:
                row.update(artifact_role="record", generated_or_source="generated", generation_command="scripts/build_validation_package.py")
            inv.append(row)
    inv.sort(key=lambda r: r["relative_path"])
    inv_fields = ["relative_path", "size_bytes", "sha256", "artifact_role", "source_or_product_id", "required_for_validation",
                  "licence_status", "redistribution_status", "generated_or_source", "generation_command"]
    for record in ("VALIDATION_MANIFEST.json", "FILE_INVENTORY.csv", "SHA256SUMS"):
        inv.append({"relative_path": record, "size_bytes": "", "sha256": "", "artifact_role": "record",
                    "source_or_product_id": "", "required_for_validation": "yes", "licence_status": "own-work",
                    "redistribution_status": "redistributable", "generated_or_source": "generated",
                    "generation_command": "scripts/build_validation_package.py (self-referential: hash in SHA256SUMS)"})
    write_csv(os.path.join(pkg, "FILE_INVENTORY.csv"), inv_fields, inv)
    return copied, pres


DOCUMENT_TRACES = ("sources/", "data/raw", "data/cache", "pdftotext", "not archived", "not held",
                   "no OCAC files", "missing source", "is missing:", "matches no held file", "adsblol",
                   "ODbL payloads", "disagree with the scan", "disagree with the yearbook",
                   "release_manifest.json is stale", "daily_reports/", "is not true : ", ".pdf", ".PDF",
                   ".xlsx", ".zip", ".sav",
                   # rc41: test_release_integrity's manifest comparison names the blocks that
                   # differ in a tree that registers documents instead of holding them
                   "blocks that differ: source_documents, sources")
# ("is not true : <filename>" is unittest's assertTrue(os.path.exists(document), document) - a
#  held document asserted present by name; the file-extension tokens catch the same shape)
GIT_TRACES = ("'git'", "git ls-files", "git status", "git checkout", ".gitignore")


def classify_failing_tests(pkg, failing):
    """{class: [test names]} - WHY each test failed inside the package, from its own
    traceback in logs/full_validation.log.

    A test that could not open a document the package deliberately does not carry
    (sources/, data/raw, data/cache, the microdata) or a tool that reads one (pdftotext)
    is a statement about custody, not a defect; one that shells out to git likewise.
    Anything else is unexplained and is the finding. The module's text is the fallback
    when a traceback names neither."""
    classes = {"needs_held_documents": [], "needs_git_checkout": [], "unexplained": []}
    try:
        with open(os.path.join(pkg, "logs", "full_validation.log"), encoding="utf-8", errors="replace") as h:
            log = h.read()
    except OSError:
        log = ""
    blocks = {}
    for block in re.split(r"\n={60,}\n", log):
        m = re.match(r"(FAIL|ERROR): (\S+) \(([^)]+)\)", block)
        if m:
            # Python 3.11 prints "FAIL: test_x (module.Class.test_x)"; 3.10 "(module.Class)"
            where, method = m.group(3), m.group(2)
            blocks[where if where.endswith("." + method) else "%s.%s" % (where, method)] = block
    for name in failing:
        block = blocks.get(name, "")
        module = name.split(".")[0]
        if module in ("paper_numbers", "validation"):
            module = ".".join(name.split(".")[:2])
        try:
            with open(os.path.join(pkg, "tests", module.replace(".", os.sep) + ".py"), encoding="utf-8") as h:
                text = h.read()
        except OSError:
            text = ""
        if any(t in block for t in DOCUMENT_TRACES) or (not block and any(
                t in text for t in ("sources/", "data/raw", "data/cache", "pdftotext", "microdata"))):
            classes["needs_held_documents"].append(name)
        elif any(t in block for t in GIT_TRACES) or (not block and ".git" in text):
            classes["needs_git_checkout"].append(name)
        else:
            classes["unexplained"].append(name)
    return classes


def failed_phases(pkg):
    """[(phase, key output, reason)] from the reproduction's run ledger (rc41), falling back
    to the run_all summary table of the log when no ledger was written."""
    out = []
    ledger = os.path.join(pkg, "logs", "reproduction_ledger.json")
    if os.path.exists(ledger):
        with open(ledger, encoding="utf-8") as h:
            for phase in json.load(h).get("phases", []):
                if phase["status"] not in ("OK", "SKIP (quick)"):
                    out.append((phase["label"], phase["key_output"],
                                " | ".join(phase.get("stderr_tail") or []) or phase["status"]))
        return out
    try:
        with open(os.path.join(pkg, "logs", "reproduction.log"), encoding="utf-8", errors="replace") as h:
            log = h.read()
    except OSError:
        return out
    reasons = re.findall(r"\[FAIL\] (.*)", log)
    for m in re.finditer(r"^(\S[^\n]*?)\s+FAIL\s+[\d.]+\s+(outputs/\S+)", log, re.M):
        out.append((m.group(1).strip(), m.group(2), reasons.pop(0) if reasons else ""))
    return out


def seeded_products(pkg):
    """The held products the reproduction seeded, from its ledger."""
    ledger = os.path.join(pkg, "logs", "reproduction_ledger.json")
    if not os.path.exists(ledger):
        return []
    with open(ledger, encoding="utf-8") as h:
        return json.load(h).get("seeded", [])


def environment_folder(pkg):
    env = os.path.join(pkg, "environment")
    os.makedirs(os.path.join(env, "container"), exist_ok=True)
    with open(os.path.join(env, "python_version.txt"), "w") as h:
        h.write(sys.version + "\n")
    with open(os.path.join(env, "platform.txt"), "w") as h:
        h.write("%s\n%s\n" % (platform.platform(), " ".join(os.uname())))
    freeze = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True, text=True).stdout
    with open(os.path.join(env, "pip_freeze.txt"), "w") as h:
        h.write(freeze)
    for name in ("pyproject.toml", "requirements.lock"):
        shutil.copy2(os.path.join(ROOT, name), os.path.join(env, name))
    with open(os.path.join(env, "system_dependencies.txt"), "w") as h:
        h.write("python >= 3.10 (verified with CPython %s)\n" % platform.python_version())
        h.write("poppler-utils (pdftotext): source-extraction re-checks only; three tests skip without it\n")
        h.write("git-lfs: one raw-data test skips without it; the package itself needs no git\n")
        h.write("latexmk + TeX Live, or tectonic: reproduce.sh --papers only; CI uses tectonic\n")
        h.write("GDAL: transitively via rasterio/fiona in requirements.lock; not needed for the shipped .npy proxies\n")
        for tool in ("latexmk", "tectonic", "pdftotext", "git-lfs", "docker"):
            h.write("%-10s on the packaging machine: %s\n" % (tool, shutil.which(tool) or "absent"))
    for name in ("environment_variables.md",):
        shutil.copy2(os.path.join(TEMPLATES, name), os.path.join(env, name))
    shutil.copy2(os.path.join(TEMPLATES, "Dockerfile"), os.path.join(env, "container", "Dockerfile"))


def known_exceptions(pkg, registered, execution, custody):
    atoms = data_rows(os.path.join(pkg, "outputs", "pakemis_atomic_annual.csv"))
    unresolved = [r for r in atoms if r["estimate_status"] == "E" and
                  (r["method_id"] in ("", "unresolved") or r["uncertainty_model_id"] in ("", "unresolved"))]
    ref_unres = [r for r in unresolved if r["period_id"] == "FY2023-24" and r["configuration_id"] == "S_TAN"]
    sectors_unres = sorted({r["sector_id"] for r in unresolved})
    docs = data_rows(os.path.join(pkg, "data", "source_documents.csv"))
    not_archived = [d["data_file"] for d in docs if d["archival_state"] == "not-archived"]
    undetermined = [d["data_file"] for d in docs if d["licence_status"] == "undetermined"]
    fallbacks = data_rows(os.path.join(pkg, "outputs", "pakemis_grid_fallbacks.csv"))
    exceptions_sp = data_rows(os.path.join(pkg, "outputs", "pakemis_spatial_exceptions.csv"))
    streams = data_rows(os.path.join(pkg, "outputs", "pakemis_source_streams.csv"))
    unresolved_ids = [(s["source_stream_id"], c) for s in streams for c in
                      ("activity_parameter_ids", "conversion_parameter_ids", "factor_parameter_ids", "factor_identity_ids")
                      if s.get(c, "") == "unresolved"]
    summary = execution.get("full_suite", {})
    failing = summary.get("failing", [])
    skipped = summary.get("skipped_tests", [])
    by_tree = {}
    for rel, lic, redist, reason in registered:
        top = "/".join(rel.split("/")[:2]) if rel.startswith("data/") else rel.split("/")[0]
        by_tree.setdefault(top, []).append(rel)
    exc = []

    def add(eid, severity, products, reason, quantity, perm, path, status, tests=()):
        # rc42 (R6): the schema's enum is temporary | permanent; "for this release" is a
        # horizon, recorded in its own field rather than appended to the enum value
        horizon = ""
        if perm.startswith("permanent for"):
            perm, horizon = "permanent", perm[len("permanent for "):]
        exc.append({"exception_id": eid, "severity": severity, "affected_products": products, "reason": reason,
                    "quantified_mass_or_rows": quantity, "temporary_or_permanent": perm, "horizon": horizon,
                    "resolution_path": path, "test_status": status, "tests": list(tests)})

    add("method_ids_unresolved_outside_agriculture", "major",
        ["outputs/pakemis_atomic_annual.csv", "registries/methods.csv"],
        "data/method_registry.csv names the IPCC equation and uncertainty model behind every AGRICULTURE atom "
        "(rc39 A7); the other sectors' atoms carry method_id/uncertainty_model_id = unresolved. Their methods are "
        "documented in the sector reports and encoded in the sector engines, not registered per atom.",
        "%d of %d estimated atoms (all periods, both configurations); %d reference-year atoms; %.3f Mt CO2e AR5 of "
        "the reference-year L total; sectors: %s" % (len(unresolved), sum(1 for r in atoms if r["estimate_status"] == "E"),
                                                       len(ref_unres), sum(float(r["co2e_Mt_AR5"] or 0) for r in ref_unres),
                                                       ", ".join(sectors_unres)),
        "permanent for this release", "per-sector method registries (the agriculture pattern) in a later release",
        "declared; no test asserts resolution outside agriculture", ["tests.test_method_registry"])
    add("source_stream_parameter_ids_unresolved", "minor" if len(unresolved_ids) < 40 else "major",
        ["outputs/pakemis_source_streams.csv"],
        "source streams whose activity/conversion/factor/identity parameter ids are unresolved in the ledger "
        "(rc40 G3/G3b resolved agriculture's; the remainder is listed here)",
        "%d (stream, column) pairs: %s" % (len(unresolved_ids), "; ".join("%s:%s" % p for p in unresolved_ids[:40])),
        "permanent for this release", "per-sector parameter scoping", "declared", ["tests.test_source_streams"])
    add("source_documents_not_shipped", "informational",
        ["data/SOURCE_MANIFEST.csv", "data/restricted_sources/restricted_source_registry.csv"],
        "third-party documents are not redistributed: the deposit position (tests/test_deposit_licensing.py) is that "
        "`not-established` is the correct answer for a government PDF with no stated terms, and a package is a "
        "publication. Every document's SHA-256, size, publisher, retrieval and the way to obtain it are registered; "
        "every fact transcribed from them is in data/ with its transcription check.",
        "%d files registered and not shipped, by tree: %s" % (len(registered), ", ".join(
            "%s (%d)" % (k, len(v)) for k, v in sorted(by_tree.items()))),
        "permanent", "obtain the documents via data/SOURCE_MANIFEST.csv how_to_obtain; verify hashes",
        "declared; tests/test_deposit_licensing.py asserts the position", ["tests.test_deposit_licensing"])
    add("source_documents_not_archived", "minor", ["data/source_documents.csv"],
        "documents the inventory cites whose file was never held locally (archival_state=not-archived)",
        "%d documents: %s" % (len(not_archived), "; ".join(not_archived[:30])), "permanent",
        "data/not_retained_register.csv gives exact URL, access date and legal reason per document", "declared")
    add("inbound_licence_undetermined", "informational", ["data/source_documents.csv", "registries/licences.csv"],
        "documents whose publisher states no terms carry licence_status=undetermined, which maps to outbound "
        "not-established; nothing is asserted", "%d of %d documents" % (len(undetermined), len(docs)), "permanent",
        "none; facts derived from published statistics are used under the declared inbound position", "declared")
    add("reproduction_excludes_the_firms_network_phase", "informational", ["outputs/agriculture_*", "data/gis/manual/firms_fire.csv"],
        "reproduce.sh runs run_all.py --quick, which skips the one phase that fetches NASA FIRMS detections over the "
        "network with a key; its cached product ships and is compared like every other input",
        "1 of 106 phases", "permanent", "set FIRMS_MAP_KEY and run the phase to refresh the cache", "declared")
    add("grid_proxy_fallbacks", "minor", ["outputs/spatial/proxy_fallbacks.csv"],
        "streams gridded on a declared fallback surface rather than their preferred raster",
        "%d rows in outputs/pakemis_grid_fallbacks.csv" % len(fallbacks), "permanent for this release",
        "data/allowed_grid_fallbacks.csv lists what is allowed and why", "asserted by tests/test_grid_cube.py")
    add("spatial_exceptions", "minor", ["outputs/spatial/spatial_exceptions.csv"],
        "shared geometries, missing polygons, uniform fallbacks and proxy-empty shapes, each with its mass",
        "%d rows, %.3f Mt CO2e AR5 affected" % (len(exceptions_sp), sum(float(r.get("affected_mass_Mt_AR5") or 0) for r in exceptions_sp)),
        "permanent for this release", "outputs/pakemis_spatial_exceptions.csv resolution column per row",
        "asserted by tests/test_spatial_exceptions.py")
    add("adm2_nesting_check_is_agriculture_only", "minor", ["outputs/spatial/adm2_nesting_check.csv"],
        "the published ADM2-into-ADM1 nesting check covers the agriculture view; the national cube's provincial "
        "closure is outputs/spatial/adm1_closure.csv (per stream) and grid_closure.csv (per month)",
        "6 rows", "permanent for this release", "extend the nesting check to every module's ADM2 view", "declared")
    add("method_basis_seams_are_agriculture_only", "informational", ["outputs/annual/annual_method_basis_seams.csv"],
        "the only cross-vintage basis-change register is agriculture's (calendar FAOSTAT vs fiscal); other sectors' "
        "seams are stated in their reports", "54 rows", "permanent for this release", "a national seam register", "declared")
    add("longitudinal_scenarios_draw_declared_widths", "minor",
        ["outputs/uncertainty/pakemis_longitudinal_uncertainty.csv", "outputs/uncertainty/trend_uncertainty.csv"],
        "of the longitudinal module's three time-correlation scenarios, only parameter_typed draws through the "
        "parameter graph (so a graph-derived row is as wide there as in the national Monte Carlo); "
        "time_correlated and time_independent draw each row's DECLARED width. Found by rc40 G3b, when the "
        "twelve newly derived N2O rows made the typed level 0.67-0.95 points wider than the other two in "
        "every year. tests/test_longitudinal_uncertainty.py asserts the structure as it is.",
        "20 graph-derived rows; typed minus time_correlated level width 0.67-0.95 points at 20,000 draws",
        "permanent for this release", "draw the declared-width scenarios through the graph as well (a "
        "longitudinal re-base, not a packaging change)", "asserted", ["tests.test_longitudinal_uncertainty"])
    add("draw_prefix_bit_identity_is_per_platform", "informational",
        ["outputs/uncertainty/common_draw_annual.parquet", "outputs/uncertainty/common_draw_monthly.parquet",
         "outputs/uncertainty/common_draw_spatial.parquet"],
        "the shipped 10,000-draw ensemble is the bit-identical prefix of the published 100,000-draw run, both "
        "produced in one environment (macOS 15.6 / CPython 3.11.10 / numpy 2.2.6). A rerun on another platform "
        "reproduces the same draws to 1e-12 relative, not bit for bit: summation order and libm differ (measured "
        "on Linux aarch64 in the shipped container: last-bit differences at the 1e-16 level). "
        "tests/test_common_ensemble.py asserts bit identity where it holds and 1e-12 elsewhere.",
        "10,000 draws x 20 categories; max relative difference observed cross-platform < 1e-12",
        "permanent", "none; the identity is a property of one run, stated as such", "asserted",
        ["tests.test_common_ensemble"])
    add("single_uncertainty_model_id", "informational", ["registries/uncertainty_models.csv"],
        "one uncertainty model id exists repo-wide (product_lognormal_activity_x_ef); the engine is one "
        "mean-preserving lognormal on activity x factor with dependency-group correlation", "1 id", "permanent",
        "none required", "declared")
    add("bridge_configurations_declared_not_populated", "informational", ["registries/bridge_configurations.csv"],
        "the FY2015-16 full-scope bridge is declared with a weights-refusing validator and populated nowhere, by design",
        "2 rows", "permanent", "none; a bridge would require weights the evidence does not support", "declared")
    add("invalid_combinations_beyond_families", "informational", ["outputs/configurations/invalid_combinations.csv"],
        "the only combination rule the release encodes is family exclusivity; cross-family combinations were not "
        "evaluated and carry no claim", "see the view", "permanent for this release", "a combination register", "declared")
    add("monthly_exception_ledger_is_a_view", "informational", ["outputs/monthly/monthly_exceptions.csv"],
        "the release keeps no separate monthly exception ledger; the view aggregates the panel's own flags", "see the view",
        "permanent for this release", "none required", "declared")
    add("correlation_matrix_is_implied_not_estimated", "informational", ["outputs/uncertainty/correlation_matrix.csv"],
        "the correlation structure is a dependency-group rule (1 within, 0 across); no matrix was estimated", "see the view",
        "permanent", "none required", "declared")
    for name, key in (("linux_container_validation", "docker"),):
        rec = execution.get(key)
        if not rec or rec.get("result") == "not_executed":
            add(name, "major", ["environment/container/Dockerfile"],
                "the Linux container run was not executed when this package was built (Docker daemon unavailable)",
                "0 runs", "temporary", "docker build -f environment/container/Dockerfile . && docker run --network=none ...",
                "not_executed")
    phases = failed_phases(pkg)
    if phases:
        add("reproduction_phases_that_could_not_run", "blocker",
            ["logs/reproduction.log", "logs/reproduction_ledger.json", "logs/reproduction_report.csv"]
            + sorted({p[1] for p in phases}),
            "phases of run_all.py --quick --strict that did not exit 0 in the temporary copy; a strict "
            "reproduction stops at the first, so every later product is reported not_rebuilt. The reproduction "
            "gate is failed until the named input is obtained or the phase reads a shipped derivative.",
            "; ".join("%s -> %s: %s" % p for p in phases), "temporary",
            "obtain the named input (data/SOURCE_MANIFEST.csv) or ship its consumed derivative; re-run ./reproduce.sh",
            "phase_failed")
    seeded = seeded_products(pkg)
    if seeded:
        add("seeded_products_not_rebuilt", "informational",
            ["logs/reproduction_ledger.json", "data/held_products.csv"] + sorted(s["path"] for s in seeded),
            "products no build phase writes (data/held_products.csv names the hand-run script, the input it needs "
            "and why it is outside the build); the reproduction seeds them into its empty outputs/ from the "
            "package, verifies each against its release digest, and records them as seeded rather than rebuilt",
            "%d products: %s" % (len(seeded), "; ".join("%s (%s)" % (s["path"], s.get("reason_held", "")[:60]) for s in seeded)),
            "permanent for this release", "run the named producer script with its input (verify_command in the registry)",
            "seeded_and_verified")
    if failing:
        classes = classify_failing_tests(pkg, failing)
        if classes["needs_held_documents"]:
            add("tests_needing_documents_the_package_does_not_carry", "informational",
                ["logs/full_validation.log", "logs/test_summary.json", "data/SOURCE_MANIFEST.csv"],
                "tests that re-read the source documents, raw publisher files, external caches or PBS "
                "microdata (registered with hashes and acquisition paths, not redistributed); each failed "
                "or errored inside the package for want of those bytes and passes in the repository, "
                "where outputs/pakemis_test_run.json records the same suite green on the release tree",
                "%d tests" % len(classes["needs_held_documents"]), "permanent",
                "obtain the documents via data/SOURCE_MANIFEST.csv how_to_obtain and re-run ./validate.sh --full",
                "failed_in_package_by_design", classes["needs_held_documents"])
        if classes["needs_git_checkout"]:
            add("tests_needing_the_git_checkout", "informational", ["logs/full_validation.log"],
                "tests that compare against the git index or history; a package carries no .git",
                "%d tests" % len(classes["needs_git_checkout"]), "permanent",
                "run in a clone of the release commit", "failed_in_package_by_design", classes["needs_git_checkout"])
        if classes["unexplained"]:
            add("tests_failing_in_the_packaged_run", "blocker", ["logs/full_validation.log", "logs/test_summary.json"],
                "tests that failed inside this package and whose module reads neither the held documents nor git; "
                "none excluded - these are findings", "%d tests" % len(classes["unexplained"]),
                "temporary", "fix at the root and re-release", "failed", classes["unexplained"])
    if skipped:
        add("tests_skipped_in_the_packaged_run", "informational", ["logs/test_summary.json"],
            "tests that skipped in the packaged run, each with its stated reason (optional package, external "
            "binary, held document, git checkout)", "%d tests" % len(skipped), "temporary",
            "provision the named dependency (environment/container/Dockerfile carries most)", "skipped", skipped)
    return exc


def restricted_and_source_manifest(pkg, custody, registered):
    """data/SOURCE_MANIFEST.csv and data/restricted_sources/restricted_source_registry.csv."""
    reg_rows, restricted = [], []
    shipped = set()
    for folder, _d, names in os.walk(pkg):
        for n in names:
            shipped.add(os.path.relpath(os.path.join(folder, n), pkg))
    sm = {r["local_path"]: r for r in custody.source_manifest}
    # rc41 (the nineteenth review's P-2): the registers that DO hold a document's URL, date
    # and locator, joined on the key each is actually keyed by - the raw manifest on the
    # acquisition's local_path, the not-retained register on the data file it feeds, the
    # transcription register on the data file whose cells it re-reads. retrieval_date is an
    # acquisition timestamp or blank, never a file's mtime.
    not_retained = {}
    for r in data_rows(os.path.join(ROOT, "data", "not_retained_register.csv")):
        for data_file in (r.get("data_files") or "").split(";"):
            if data_file.strip():
                not_retained.setdefault(deposit.storage_path(data_file.strip()), r)
    locators = {}
    for r in data_rows(os.path.join(ROOT, "data", "transcription_checks.csv")):
        locators.setdefault(deposit.storage_path(r["data_file"]), set()).add("%s %s" % (os.path.basename(r["document"]), r["locator"]))
    def host(url):
        parts = (url or "").split("/")
        return parts[2] if len(parts) > 2 else ""
    def hex64(*candidates):
        # rc42 (the twentieth review's R8): a digest column carries a 64-hex digest or
        # nothing - never the prose the source register uses for directories
        for value in candidates:
            if value and len(value) == 64 and all(c in "0123456789abcdef" for c in value):
                return value
        return ""
    def locator_text(rel):
        found = sorted(locators.get(rel, ()))
        if not found:
            return ""
        return "; ".join(found[:6]) + ("; +%d more" % (len(found) - 6) if len(found) > 6 else "")
    for d in custody.documents.values():
        rel = d["data_file"]
        archived = d.get("archived_path", "")
        reg = custody.register.get(rel, {})
        raw = custody.raw.get(archived or rel, {})
        srcm = sm.get(archived or rel, {})
        included = rel in shipped
        # rc42 (R8): the row names the DATA FILE, so its sha256 and size are the data file's -
        # rc41 took the source document's digest and byte count first, and 106 of 169 shipped
        # rows carried another file's hash or a sentence. The document's own digest has its
        # own column now; prose never enters a digest column (hex64).
        doc_sha = hex64(reg.get("document_sha256"), custody.hashed_documents.get(archived),
                        raw.get("sha256"), srcm.get("sha256"))
        if included:
            sha = sha256(os.path.join(pkg, rel))
            size = str(os.path.getsize(os.path.join(pkg, rel)))
        else:
            sha = hex64(custody.hashed_sources.get(rel), doc_sha)
            size = raw.get("bytes") or srcm.get("bytes") or ""
            if not size and os.path.exists(os.path.join(ROOT, archived or rel)):
                size = str(os.path.getsize(os.path.join(ROOT, archived or rel)))
        nr = not_retained.get(rel, {})
        url = srcm.get("source_url", "") or nr.get("exact_url", "")
        register_publisher = srcm.get("publisher", "") or nr.get("publisher", "")
        if register_publisher:
            publisher, publisher_basis = register_publisher, "register"
        elif host(url):
            publisher, publisher_basis = host(url), "url-host"
        elif archived.startswith("sources/") and archived.count("/") >= 1:
            publisher, publisher_basis = archived.split("/")[1], "folder"
        else:
            publisher, publisher_basis = "", ""
        row = {"source_document_id": legacy_path(rel, root=ROOT), "relative_path_or_not_included": rel if included else "NOT INCLUDED",
               "sha256": sha, "document_sha256": doc_sha, "size_bytes": size,
               "publisher": publisher, "publisher_basis": publisher_basis,
               "title": d.get("primary_source", ""), "edition": srcm.get("revision_status", ""),
               "reference_period": "%s..%s" % (srcm.get("coverage_start", ""), srcm.get("coverage_end", "")) if srcm else "",
               "document_type": raw.get("package", "") or ("data table" if rel.endswith(".csv") else ""),
               "source_url": url, "retrieval_date": srcm.get("retrieved_at_utc", "") or nr.get("access_date_utc", ""),
               "archive_state": d.get("archival_state", ""), "licence_status": d.get("licence_status", ""),
               "redistribution_status": reg.get("outbound_redistribution", ""),
               "consuming_modules": custody.provenance.get(rel, {}).get("readers", ""),
               "extraction_script": custody.provenance.get(rel, {}).get("producer", ""),
               "extraction_table": rel if rel.endswith(".csv") else "",
               "page_or_cell_range": nr.get("page_table_coords", "") or locator_text(rel),
               "evidence_class": custody.provenance.get(rel, {}).get("class", ""),
               "notes": " | ".join(x for x in (d.get("note", ""), reg.get("how_to_obtain", ""),
                                                nr.get("how_to_obtain", "")) if x)}
        reg_rows.append(row)
        # The restricted registry is about the DOCUMENT behind a data file, not the data
        # file (this project's transcription, which ships). A document is restricted here
        # when it is an archived or never-archived third-party publication whose bytes are
        # not in the package - whatever the reason recorded in the source register.
        document_shipped = bool(archived) and archived in shipped
        is_document = d.get("archival_state") in ("archived", "not-archived")
        if is_document and not document_shipped:
            restricted.append({"source_document_id": legacy_path(rel, root=ROOT), "exact_filename": archived or "(never held; see notes)",
                               "sha256": sha,
                               "size_bytes": size, "source_url": srcm.get("source_url", ""),
                               "retrieval_date": srcm.get("retrieved_at_utc", ""),
                               "pages_or_cells_consumed": "see data/transcription_checks.csv locator column for this data_file",
                               "extraction_outputs": rel, "reason_absent": reg.get("document_not_deposited_because", "")
                               or reg.get("outbound_reason", "") or "terms not established"})
    for rel, lic, redist, reason in registered:
        if rel not in custody.documents:
            raw = custody.raw.get(rel, {})
            srcm = sm.get(rel, {})      # rc41: the raw acquisition register, keyed on the same path
            doc_sha = hex64(raw.get("sha256"), custody.hashed_documents.get(rel), custody.hashed_sources.get(rel))
            reg_rows.append({"source_document_id": legacy_path(rel, root=ROOT), "relative_path_or_not_included": "NOT INCLUDED",
                             "sha256": doc_sha, "document_sha256": doc_sha,
                             "size_bytes": raw.get("bytes", ""),
                             "publisher": srcm.get("publisher", "") or host(srcm.get("source_url", "")),
                             "publisher_basis": "register" if srcm.get("publisher") else ("url-host" if host(srcm.get("source_url", "")) else ""),
                             "title": srcm.get("original_filename", "") or raw.get("origin", ""),
                             "edition": srcm.get("revision_status", ""),
                             "reference_period": "%s..%s" % (srcm.get("coverage_start", ""), srcm.get("coverage_end", "")) if srcm else "",
                             "document_type": raw.get("package", ""),
                             "source_url": srcm.get("source_url", ""),
                             # an acquisition timestamp where the register holds one; never the file's mtime
                             "retrieval_date": srcm.get("retrieved_at_utc", ""), "archive_state": "held locally",
                             "licence_status": lic, "redistribution_status": redist, "consuming_modules": "",
                             "extraction_script": "", "extraction_table": "", "page_or_cell_range": "",
                             "evidence_class": "", "notes": reason})
    fields = ["source_document_id", "relative_path_or_not_included", "sha256", "document_sha256", "size_bytes",
              "publisher", "publisher_basis", "title",
              "edition", "reference_period", "document_type", "source_url", "retrieval_date", "archive_state",
              "licence_status", "redistribution_status", "consuming_modules", "extraction_script", "extraction_table",
              "page_or_cell_range", "evidence_class", "notes"]
    write_csv(os.path.join(pkg, "data", "SOURCE_MANIFEST.csv"), fields, reg_rows,
              banner="THE SOURCE MANIFEST of the validation package: every source document and held input the "
                     "release reads, shipped or not. Generated by scripts/build_validation_package.py from "
                     "data/source_documents.csv, outputs/pakemis_source_register.csv, data/raw_manifest.csv, "
                     "data/manifests/source_manifest.csv and outputs/release_manifest.json; nothing hand-entered.")
    write_csv(os.path.join(pkg, "data", "restricted_sources", "restricted_source_registry.csv"),
              ["source_document_id", "exact_filename", "sha256", "size_bytes", "source_url", "retrieval_date",
               "pages_or_cells_consumed", "extraction_outputs", "reason_absent"], restricted,
              banner="DOCUMENTS THE PACKAGE DOES NOT CARRY, with hash, URL, retrieval date and the extraction "
                     "tables that carry their facts. See data/transcription_checks.csv for the cell-level checks.")
    return len(reg_rows), len(restricted)


def data_presentation(pkg):
    """The specification's data/ folders that do not already exist in the tree: small copies and indexes."""
    P = []
    def copy(dst, src): P.append((dst, "copy", deposit.storage_path(src)))
    for name in ("parameters.csv",):
        copy("data/parameters/%s" % name, "data/%s" % name)
    parameters = {os.path.basename(row["legacy_path"]) for row in asset_catalog(root=ROOT)
                  if row["legacy_path"].startswith("data/") and row["legacy_path"].endswith("_params.csv")}
    parameters.update(name for name in os.listdir(os.path.join(pkg, "data")) if name.endswith("_params.csv"))
    for name in sorted(parameters):
        copy("data/parameters/%s" % name, "data/%s" % name)
    # The LULUCF transition-factor table is deliberately NOT presented here: the LULUCF
    # module reads its parameter store instead, and that file is a declared orphan
    # (tests/test_data_provenance_audit.ORPHANS; naming it here would make this script its
    # "reader") - presenting it as an emission-factor registry would dress a retirement
    # candidate as an input.
    for name in ("emission_factors.csv", "fugitives_ipcc2019_factors.csv", "cui2021_pak_ef.csv"):
        if os.path.exists(resolve(os.path.join(pkg, "data", name), root=pkg)):
            copy("data/emission_factors/%s" % name, "data/%s" % name)
    copy("data/source_documents/source_documents.csv", "data/source_documents.csv")
    copy("data/source_documents/source_register.csv", "outputs/pakemis_source_register.csv")
    copy("data/source_documents/source_manifest_held_files.csv", "data/manifests/source_manifest.csv")
    copy("data/source_documents/raw_manifest.csv", "data/raw_manifest.csv")
    copy("data/transcription_registers/transcription_checks.csv", "data/transcription_checks.csv")
    copy("data/transcription_registers/not_retained_register.csv", "data/not_retained_register.csv")
    copy("data/transcription_registers/source_keys.csv", "data/source_keys.csv")
    copy("data/transcription_registers/data_provenance.csv", "outputs/pakemis_data_provenance.csv")
    for name in ("acquisition_attempts.csv", "source_search_log.csv", "data_gaps.csv"):
        if os.path.exists(resolve(os.path.join(pkg, "data", name), root=pkg)):
            copy("data/acquisition_records/%s" % name, "data/%s" % name)
    copy("data/boundaries/PAK_ADM1.geojson", "data/gis/PAK_ADM1.geojson")
    copy("data/boundaries/PAK_ADM2.geojson", "data/gis/PAK_ADM2.geojson")
    copy("data/boundaries/BOUNDARY_SOURCES.json", "data/gis/BOUNDARY_SOURCES.json")
    copy("data/crosswalks/adm2_crosswalk.csv", "data/adm2_crosswalk.csv")
    copy("data/crosswalks/adm2_canonical.csv", "data/adm2_canonical.csv")
    copy("data/crosswalks/geometry_sets.csv", "data/geometry_sets.csv")
    copy("data/crosswalks/pakemis_adm2_crosswalk.csv", "outputs/pakemis_adm2_crosswalk.csv")
    return P


def source_extract_index(pkg, custody):
    rows = []
    for rel, p in sorted(custody.provenance.items()):
        if p.get("class", "").startswith("hand:") and os.path.exists(os.path.join(pkg, rel)):
            doc = custody.documents.get(rel, {})
            rows.append({"extraction_table": rel, "class": p["class"], "source_document": doc.get("primary_source", ""),
                         "archived_path": doc.get("archived_path", ""), "readers": p.get("readers", ""),
                         "transcription_checks": sum(1 for _ in ())})
    checks = data_rows(resolve(os.path.join(pkg, "data", "transcription_checks.csv"), root=pkg))
    counts = {}
    for c in checks:
        relative = deposit.storage_path(c["data_file"])
        counts[relative] = counts.get(relative, 0) + 1
    for r in rows:
        r["transcription_checks"] = counts.get(r["extraction_table"], 0)
    write_csv(os.path.join(pkg, "data", "source_extracts", "INDEX.csv"),
              ["extraction_table", "class", "source_document", "archived_path", "readers", "transcription_checks"], rows,
              banner="EVERY HAND-EXTRACTED TABLE in the package (data_provenance class hand:*), the document it was "
                     "read from and how many of its cells data/transcription_checks.csv re-extracts. The tables "
                     "themselves are at their canonical paths; this is an index, not a copy.")
    return rows


# ----------------------------------------------------------------------------- main

def main(argv):
    global BUILD_LOG
    docker = "--docker" in argv
    rehearse = "--rehearse" in argv
    allow_dirty = "--allow-dirty" in argv
    out_dir = os.path.join(ROOT, "dist")
    if "--out" in argv:
        out_dir = os.path.abspath(argv[argv.index("--out") + 1])
    pkg = os.path.join(out_dir, NAME)
    if os.path.exists(pkg):
        shutil.rmtree(pkg)
    os.makedirs(os.path.join(pkg, "logs"))
    BUILD_LOG = os.path.join(pkg, "logs", "build.log")
    timings = []

    def timed(step, fn, *args):
        t = time.time()
        result = fn(*args)
        timings.append((step, round(time.time() - t, 1)))
        log("%s (%.1f s)" % (step, time.time() - t))
        return result

    # 0. identity
    porcelain = git("status", "--porcelain")
    head = git("rev-parse", "HEAD").strip()
    dirty = bool(porcelain.strip())
    log("release %s at %s%s" % (VERSION, head[:12], "  TREE DIRTY" if dirty else ""))
    if dirty and not allow_dirty:
        raise SystemExit("the working tree is dirty; a validation package describes one commit:\n" + porcelain)
    with open(os.path.join(ROOT, "outputs", "release_manifest.json"), encoding="utf-8") as handle:
        rm = json.load(handle)
    # THE FIXPOINT'S OWN CONTRACT: the manifest describes the CONTENT commit - the one that
    # was HEAD when it was generated - and the artifacts commit and the test-run record
    # commit follow it. HEAD is therefore the record commit, and the only files that may
    # differ between the described commit and HEAD are the regenerable artifacts the
    # fixpoint writes (scripts/release_fixpoint.ARTIFACT_PATTERNS). Anything else changed
    # since means content was committed after the fixpoint, and the manifest is stale.
    content_commit = rm["git"]["describes_commit"]
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    from release_fixpoint import ARTIFACT_PATTERNS  # noqa: E402
    changed = [p for p in git("diff", "--name-only", content_commit, "HEAD").splitlines() if p]
    non_artifact = [p for p in changed if not any(re.match(pat, p) for pat in ARTIFACT_PATTERNS)]
    if not allow_dirty and (rm["git"]["tree_dirty"] or non_artifact):
        raise SystemExit("outputs/release_manifest.json describes %s%s; HEAD %s differs from it in "
                         "non-artifact files:\n  %s\nrun the release fixpoint on the current content first"
                         % (content_commit[:12], " (TREE DIRTY)" if rm["git"]["tree_dirty"] else "",
                            head[:12], "\n  ".join(non_artifact[:20]) or "(none)"))
    log("manifest describes content commit %s; %d artifact files changed since (fixpoint + record)"
        % (content_commit[:12], len(changed)))
    with open(os.path.join(pkg, "logs", "git_status.txt"), "w") as h:
        h.write("HEAD %s\n%s\n%s" % (head, git("log", "--oneline", "-5"), porcelain or "(clean)\n"))
    with open(os.path.join(pkg, "logs", "git_diff_stat.txt"), "w") as h:
        h.write(git("diff", "--stat", "HEAD") or "(no uncommitted changes)\n")

    # 1. the runnable tree
    custody = Custody()
    inventory_rows, registered = timed("copy the runnable tree", copy_runnable_tree, pkg, custody)
    log("  %d files copied, %d registered without bytes" % (len(inventory_rows), len(registered)))
    # Model adapters used by the claim/view checks require the readable inputs.
    # This uses deposited extracts only, and write_inventory records their source
    # paths and inherited licences as generated inputs, never as raw documents.
    from pkinv.activity.build import build as build_canonical
    timed("reconstruct canonical inputs offline", build_canonical, pkg)
    for name in ("validate.sh", "reproduce.sh", "VALIDATION_MANIFEST.schema.json"):
        shutil.copy2(os.path.join(TEMPLATES, name), os.path.join(pkg, name))
    os.chmod(os.path.join(pkg, "validate.sh"), 0o755)
    os.chmod(os.path.join(pkg, "reproduce.sh"), 0o755)
    # The container build only COPYs environment/requirements.lock; without this the
    # whole package (gigabytes) is sent to the daemon as build context on every build.
    with open(os.path.join(pkg, ".dockerignore"), "w", encoding="utf-8") as h:
        h.write("*\n!environment/\n")
    shutil.copy2(os.path.join(TEMPLATES, "entrypoints.md"), os.path.join(pkg, "code", "entrypoints.md")) \
        if os.path.isdir(os.path.join(pkg, "code")) else None
    timed("environment/", environment_folder, pkg)

    # 2. presentation layer
    presentation = layout(pkg) + data_presentation(pkg)
    os.makedirs(os.path.join(pkg, "code"), exist_ok=True)
    shutil.copy2(os.path.join(TEMPLATES, "entrypoints.md"), os.path.join(pkg, "code", "entrypoints.md"))
    view_rows = {}
    for dst, kind, src in presentation:
        target = os.path.join(pkg, dst)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if kind == "copy":
            source = os.path.join(pkg, src)
            if not os.path.exists(source):
                log("  presentation copy skipped, source absent: %s -> %s" % (src, dst))
                continue
            shutil.copy2(source, target)
        else:
            try:
                rows = src(pkg, target)
                view_rows[dst] = len(rows)
            except Exception as exc:                        # noqa: BLE001 - a view that cannot be built is declared
                log("  VIEW FAILED %s: %s" % (dst, exc))
                view_rows[dst] = None
                with open(target, "w", encoding="utf-8") as h:
                    h.write("# VIEW NOT BUILT: %s\n" % exc)
    log("presentation layer: %d entries (%d views)" % (len(presentation), len(view_rows)))
    n_sources, n_restricted = timed("SOURCE_MANIFEST + restricted registry", restricted_and_source_manifest, pkg, custody, registered)
    timed("source extract index", source_extract_index, pkg, custody)
    views.test_catalogue(pkg, os.path.join(pkg, "tests", "test_catalogue.csv"), THEMES)
    # tests/clean_room: the clean-room scripts and a note
    os.makedirs(os.path.join(pkg, "tests", "clean_room"), exist_ok=True)
    for name in ("clean_room_full.sh", "clean_rebuild.sh"):
        if os.path.exists(os.path.join(pkg, "scripts", name)):
            shutil.copy2(os.path.join(pkg, "scripts", name), os.path.join(pkg, "tests", "clean_room", name))
    with open(os.path.join(pkg, "tests", "clean_room", "README.md"), "w") as h:
        h.write("Clean-room reconstruction is `./reproduce.sh` at the package root (a rebuild in a temporary copy, "
                "compared with the packaged outputs). The two scripts here are the repository's own clean-room "
                "gates, which need a git clone; the package needs none.\n")

    # 3. claim registry
    env = dict(os.environ, PKINV_ROOT=pkg, PYTHONPATH=os.pathsep.join(
        [os.path.join(pkg, "src"), os.path.join(pkg, "tests"), os.path.join(pkg, "tests", "paper_numbers")]))
    os.makedirs(os.path.join(pkg, "manuscripts"), exist_ok=True)
    code, secs = run([sys.executable, os.path.join(pkg, "tests", "validation", "claim_registry.py"), pkg,
                      os.path.join(pkg, "manuscripts", "paper_claim_registry.csv"),
                      os.path.join(pkg, "manuscripts", "paper_claim_test_report.csv")],
                     cwd=pkg, log_path=os.path.join(pkg, "logs", "claim_registry.log"), env=env)
    timings.append(("claim registry", secs))
    log("claim registry exit %d (%.1f s)" % (code, secs))
    for src_tex in ("paper_national/versions/v1/sections/generated_coverage.tex", "paper_national/versions/v1/sections/generated_products.tex"):
        if os.path.exists(os.path.join(pkg, src_tex)):
            os.makedirs(os.path.join(pkg, "manuscripts", "generated_tables"), exist_ok=True)
            shutil.copy2(os.path.join(pkg, src_tex), os.path.join(pkg, "manuscripts", "generated_tables", os.path.basename(src_tex)))
            presentation.append(("manuscripts/generated_tables/%s" % os.path.basename(src_tex), "copy", src_tex))
    for folder, _d, names in os.walk(os.path.join(pkg, "papers")):
        for n in names:
            if n.startswith("S") and n.endswith(".tex") and "sections" in folder:
                rel = os.path.relpath(os.path.join(folder, n), pkg)
                dst = "manuscripts/generated_tables/%s_%s" % (rel.split("/")[1], n)
                shutil.copy2(os.path.join(pkg, rel), os.path.join(pkg, dst))
                presentation.append((dst, "copy", rel))

    # 4/5. RECORDS FIRST, THEN THE VALIDATIONS, THEN THE RECORDS AGAIN (rc42, the twentieth
    #    review's R3/R5/R6). rc41 wrote VALIDATION_MANIFEST.json last, so tests/validation's
    #    IN_PACKAGE was False during every packaged run and six package-only test classes
    #    skipped in every shipped log; it ran validate.sh before reproduce.sh, so the ledger
    #    test had nothing to read; and it hashed logs/build.log then appended to it, so a
    #    plain sha256sum -c failed on one file. Now: a first, complete set of records with
    #    every gate `not_executed`; reproduce.sh FIRST; validate.sh --quick and --full against
    #    the real ledger; the container runs with the ledger copied in; the final records;
    #    and a records gate that re-runs tests/validation over the finished tree.
    execution = {"packaging_machine": {"platform": platform.platform(), "python": platform.python_version()}}
    for key in ("quick", "full", "reproduce", "docker", "documents"):
        execution[key] = {"result": "not_executed", "reason": "records written before the validations ran"}
    schema_path = os.path.join(pkg, "VALIDATION_MANIFEST.schema.json")
    with open(schema_path, encoding="utf-8") as h:
        schema = json.load(h)
    timings_path = os.path.join(pkg, "logs", "command_timings.csv")
    sums_skip = ("SHA256SUMS", "VALIDATION_MANIFEST.json", "logs/build_tail.log",
                 "logs/sha256_check_at_packaging.log", "logs/records_gate.log",
                 # rc42 rehearsal: validate.sh and reproduce.sh append to these two, so a
                 # reviewer who runs them and then `sha256sum -c` would see a mismatch
                 "logs/command_timings.csv", "logs/exit_codes.txt")

    def write_records(stage):
        global BUILD_LOG
        exceptions = known_exceptions(pkg, registered, execution, custody)
        with open(os.path.join(pkg, "KNOWN_EXCEPTIONS.json"), "w", encoding="utf-8") as h:
            json.dump({"schema": "pakemis.known_exceptions/1.0", "release": VERSION, "commit": head,
                       "stage": stage, "exceptions": exceptions}, h, indent=2, sort_keys=True)
            h.write("\n")
        totals = rm["national_totals"]
        expected = {"schema": "pakemis.expected_results/1.0", "release": VERSION, "commit": head,
                    "national_totals_Mt_CO2e": totals, "baseline_configuration": rm["baseline_configuration"],
                    "completeness": rm["completeness"], "monte_carlo": rm.get("monte_carlo", {}),
                    "test_run_recorded_at_release": None, "packaged_run": execution.get("full_suite"),
                    "closure_tolerances": {"annual_vs_monthly_relative": 1e-9, "draw_wise_relative": 1e-9,
                                           "cross_sector_ledgers_absolute": 2e-4, "reproduction_numeric_relative": 1e-9}}
        tr = os.path.join(pkg, "outputs", "pakemis_test_run.json")
        if os.path.exists(tr):
            with open(tr, encoding="utf-8") as h:
                expected["test_run_recorded_at_release"] = json.load(h)
        with open(os.path.join(pkg, "EXPECTED_RESULTS.json"), "w", encoding="utf-8") as h:
            json.dump(expected, h, indent=2, sort_keys=True)
            h.write("\n")
        if stage == "final":
            if not os.path.exists(timings_path):      # validate.sh writes the header when it creates the file
                with open(timings_path, "w", encoding="utf-8") as h:
                    h.write("mode,step,command,seconds,exit_code\n")
            with open(timings_path, "a", encoding="utf-8") as h:
                for step, secs in timings:
                    h.write('packager,%s,"",%d,0\n' % (step, secs))
        # README from the template with the measured facts
        readme = open(os.path.join(TEMPLATES, "README_VALIDATION.md"), encoding="utf-8").read()
        facts = {"version": VERSION, "commit": head, "commit_short": head[:12], "generated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                 "n_copied": len(inventory_rows), "n_registered": len(registered), "n_views": len(view_rows),
                 "n_sources": n_sources, "n_restricted": n_restricted,
                 "content_commit": content_commit[:12],
                 "quick": execution["quick"]["result"], "full": execution["full"]["result"],
                 "reproduce": execution["reproduce"]["result"], "docker": execution["docker"]["result"],
             "documents": execution["documents"]["result"],
                 "platform": platform.platform(), "python": platform.python_version(),
                 "L": totals["L"]["co2e_Mt_AR5"], "S": totals["S"]["co2e_Mt_AR5"]}
        for k, v in facts.items():
            readme = readme.replace("{{%s}}" % k, str(v))
        with open(os.path.join(pkg, "README_VALIDATION.md"), "w", encoding="utf-8") as h:
            h.write(readme)
        copied, pres = write_inventory(pkg, presentation, inventory_rows)
        if stage == "final":
            # everything logged from here goes to a tail file SHA256SUMS does not list, so
            # the sums describe a tree that does not change under the packager's own hand
            BUILD_LOG = os.path.join(pkg, "logs", "build_tail.log")
        sums = []
        for folder, dirs, names in os.walk(pkg):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in sorted(names):
                rel = os.path.relpath(os.path.join(folder, name), pkg)
                if rel in sums_skip:
                    continue
                sums.append((rel, sha256(os.path.join(folder, name))))
        sums.sort()
        sums_text = "".join("%s  %s\n" % (d, r) for r, d in sums)
        sums_sha = hashlib.sha256(sums_text.encode("utf-8")).hexdigest()
        # the manifest
        atoms = data_rows(os.path.join(pkg, "outputs", "pakemis_atomic_annual.csv"))
        months = data_rows(resolve(os.path.join(pkg, "data", "months.csv"), root=pkg))
        products = []
        for r in data_rows(os.path.join(ROOT, "data", "product_schemas.csv")):
            rel = r["relative_path"]
            path = os.path.join(pkg, rel)
            if not os.path.exists(path):
                continue
            tests = sorted({os.path.relpath(os.path.join(f, n), pkg) for f, _d, ns in os.walk(os.path.join(pkg, "tests"))
                            for n in ns if n.endswith(".py") and os.path.basename(rel).split(".")[0] in open(os.path.join(f, n), encoding="utf-8", errors="replace").read()})
            fmt = rel.rsplit(".", 1)[-1]
            products.append({"product_id": r["product_id"], "relative_path": rel, "format": fmt, "sha256": sha256(path),
                             "schema_id": r["schema_id"], "primary_key": r["primary_key"],
                             "row_count": len(data_rows(path)) if fmt == "csv" else None, "units": r["units"],
                             "gwp_basis": r["gwp_basis"], "configuration_coverage": r["configuration_coverage"],
                             "period_coverage": r["period_coverage"], "geography_coverage": r["geography_coverage"],
                             "producer_command": "python3 run_all.py (phase writing %s; see src/pkinv/run_all.py PHASES)" % os.path.basename(rel),
                             "validation_tests": tests, "licence": copied.get(rel, ("own-work",))[0]})
        manifest = {
            "schema_version": "1.0",
            "release": {"release_id": "PakEmis %s" % VERSION, "version": VERSION, "git_commit_full": head,
                        "git_commit_short": head[:12], "git_dirty": dirty,
                        "content_commit": content_commit,
                        "commit_rule": "git_commit_full is the release's final (test-run record) commit; "
                                       "outputs/release_manifest.json describes content_commit, the commit "
                                       "whose content the fixpoint regenerated the artifacts against; only "
                                       "fixpoint artifacts differ between the two",
                        "generated_utc": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        "source_manifest_sha256": sha256(os.path.join(pkg, "data", "SOURCE_MANIFEST.csv")),
                        "release_manifest_sha256": sha256(os.path.join(pkg, "outputs", "release_manifest.json")),
                        "product_manifest_sha256": sha256(os.path.join(pkg, "outputs", "pakemis_product_catalog.csv")),
                        "sha256sums_sha256": sums_sha,
                        "sha256sums_sha256_rule": "SHA-256 of SHA256SUMS with the VALIDATION_MANIFEST.json line removed "
                                                  "(the manifest cannot contain the hash of a file that contains its own hash)"},
            "scope": {"country": "Pakistan", "iso3": "PAK", "inventory_scope": "non-LULUCF",
                      "period_start": "2015-07-01", "period_end": "2024-06-30",
                      "reference_period_start": "2023-07-01", "reference_period_end": "2024-06-30",
                      "period_registry": "registries/periods.csv", "sector_registry": "registries/sectors.csv",
                      "ipcc_scope_registry": "registries/ipcc_scope.csv",
                      "lulucf_treatment": "excluded from the national total; experimental lane reported beside it "
                                          "(outputs/completeness/lulucf_scope_decision.csv)"},
            "metrics": {"ar5_gwp_registry": "registries/gwp.csv (basis=AR5)", "ar6_gwp_registry": "registries/gwp.csv (basis=AR6)",
                        "reference_configuration": rm["baseline_configuration"],
                        "alternative_reference_configurations": [c["configuration_id"] for c in
                                                                 data_rows(os.path.join(pkg, "outputs", "national_configurations.csv"))
                                                                 if c["configuration_id"] != "inventory_reference"]},
            "expected_dimensions": {
                "fiscal_years": len(data_rows(resolve(os.path.join(pkg, "data", "periods.csv"), root=pkg))), "months": len(months),
                "sectors": len(rm["sectors"]), "annual_atomic_rows": len(atoms),
                "monthly_rows": len(data_rows(os.path.join(pkg, "outputs", "pakemis_monthly_fy2015_16_fy2024_25.csv"))),
                "source_streams": len(data_rows(os.path.join(pkg, "outputs", "pakemis_source_streams.csv"))),
                "completeness_rows": len(data_rows(os.path.join(pkg, "outputs", "completeness.csv"))),
                "structural_axes": len(data_rows(os.path.join(pkg, "outputs", "national_axis_register.csv"))),
                "named_configurations": len(data_rows(os.path.join(pkg, "outputs", "national_configurations.csv"))),
                "common_draws": _draws(pkg), "national_monte_carlo_draws": int(
                    data_rows(os.path.join(pkg, "outputs", "national_uncertainty_montecarlo.csv"))[0]["n_iter"])},
            "commands": {"environment_setup": "python3 -m venv .venv && .venv/bin/pip install -r environment/requirements.lock "
                                              "(optional: the stdlib alone runs the engine and most of the suite)",
                         "quick_validation": "./validate.sh --quick", "full_validation": "./validate.sh --full",
                         "full_reproduction": "./reproduce.sh"},
            "products": products,
            "source_custody": {"source_manifest": "data/SOURCE_MANIFEST.csv", "rows": n_sources,
                               "restricted_registry": "data/restricted_sources/restricted_source_registry.csv",
                               "restricted_rows": n_restricted, "files_registered_without_bytes": len(registered),
                               "inclusion_rule": "a file is copied iff outputs/pakemis_deposit_manifest.csv lists it with an "
                                                 "outbound licence in DEPOSITABLE, or it is this project's own code, product or "
                                                 "prose, or (consumed rasters under data/gis/manual) its *_SOURCES.json sidecar "
                                                 "names an open licence; everything else is registered with its hash",
                               "transcription_register": "data/transcription_registers/transcription_checks.csv"},
            "validation_gates": [
                {"gate_id": "integrity", "what_it_tests": "SHA-256 of every packaged file", "command": "./validate.sh --quick (step integrity)",
                 "result": execution["quick"]["result"], "exit_code": execution["quick"].get("exit_code"), "log": "logs/quick_validation.log"},
                {"gate_id": "quick", "what_it_tests": "identity, schemas, keys, arithmetic closure", "command": "./validate.sh --quick",
                 "result": execution["quick"]["result"], "exit_code": execution["quick"].get("exit_code"), "log": "logs/quick_validation.log"},
                {"gate_id": "full", "what_it_tests": "the complete release suite", "command": "./validate.sh --full",
                 "result": execution["full"]["result"], "exit_code": execution["full"].get("exit_code"), "log": "logs/full_validation.log"},
                {"gate_id": "reproduction", "what_it_tests": "rebuild in a temporary copy and compare", "command": execution["reproduce"].get("command", "./reproduce.sh"),
                 "result": execution["reproduce"]["result"], "exit_code": execution["reproduce"].get("exit_code"), "log": "logs/reproduction.log"},
                {"gate_id": "linux_container", "what_it_tests": "validate.sh --quick and --full in python:3.11-slim, no network",
                 "command": "docker build ... && docker run --network=none ...", "result": execution["docker"]["result"],
                 "exit_code": None, "log": "logs/linux_validation.log"}],
            "known_exceptions": [{k: v for k, v in e.items() if k != "tests"} for e in exceptions],
            "omitted_artifacts": [
                {"requested_role": "registries/invalid_configuration_combinations.csv (as a register)", "status": "view",
                 "reason": "no register exists; the family rule is the only encoded rule", "nearest_packaged_artifact": "outputs/configurations/invalid_combinations.csv"},
                {"requested_role": "outputs/uncertainty/correlation_matrix.csv (estimated)", "status": "view",
                 "reason": "correlation is structural (dependency groups), never estimated", "nearest_packaged_artifact": "outputs/uncertainty/correlation_matrix.csv"},
                {"requested_role": "outputs/monthly/monthly_exceptions.csv (ledger)", "status": "view",
                 "reason": "no ledger kept; the panel's flags are aggregated", "nearest_packaged_artifact": "outputs/monthly/monthly_exceptions.csv"},
                {"requested_role": "outputs/spatial/grid_005deg (Zarr)", "status": "omitted",
                 "reason": "the cube ships as CF NetCDF only; no Zarr twin exists", "nearest_packaged_artifact": "outputs/spatial/grid_005deg/pakemis_grid_0p05_monthly.nc"},
                {"requested_role": "GeoParquet for ADM boundaries", "status": "omitted",
                 "reason": "boundaries ship as the GeoJSON the engine reads (geoBoundaries, public domain); road links ship as GeoParquet",
                 "nearest_packaged_artifact": "outputs/spatial/native_geometries/"},
                {"requested_role": "sources/ (3.8 GB of documents)", "status": "registered_not_shipped",
                 "reason": "redistribution not established; see known_exceptions.source_documents_not_shipped",
                 "nearest_packaged_artifact": "data/SOURCE_MANIFEST.csv"},
                {"requested_role": "data/raw and data/cache (publisher documents, ODbL flight archive, PBS microdata)", "status": "registered_not_shipped",
                 "reason": "as above; every derived table ships", "nearest_packaged_artifact": "data/SOURCE_MANIFEST.csv"}],
            "presentation_layer": {"rule": "package root = runnable repo-shaped tree; the specification's folders are copies "
                                           "(presentation_copy, hashed against their source by tests/validation/test_presentation_identity.py) "
                                           "or views (pkinv.report.validation_views)", "copies": sum(1 for k, s in pres.values() if k == "copy"),
                                   "views": {k: v for k, v in view_rows.items()}},
            "execution_record": execution,
        }
        manifest["release"]["stage"] = stage
        manifest["release"]["byte_identity"] = (
            "asserted on the locked interpreter (CPython 3.11, environment/requirements.lock, the "
            "container); the writers accumulate float sums sequentially (pkinv.core.io.seq_sum) "
            "since rc42, because CPython 3.12 changed the built-in sum() and a published cell on "
            "a rounding tie printed differently there")
        manifest["release"]["sha256sums_sha256_rule"] = (
            "SHA-256 of SHA256SUMS with the VALIDATION_MANIFEST.json line removed (the manifest cannot "
            "contain the hash of a file that contains its own hash); SHA256SUMS does not list the "
            "logs the packager and the package's own scripts write after it exists: %s"
            % ", ".join(sums_skip[2:]))
        manifest["validation_gates"].append(
            {"gate_id": "documents", "what_it_tests": "the tests that re-read the source documents the "
             "package registers and does not carry (./validate.sh --documents DIR with a mounted vault)",
             "command": "./validate.sh --documents DIR", "result": execution["documents"]["result"],
             "exit_code": execution["documents"].get("exit_code"), "log": "logs/documents_validation.log"})
        import jsonschema
        jsonschema.Draft202012Validator(schema).validate(manifest)
        manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
        with open(os.path.join(pkg, "VALIDATION_MANIFEST.json"), "w", encoding="utf-8") as h:
            h.write(manifest_text)
        manifest_sha = hashlib.sha256(manifest_text.encode("utf-8")).hexdigest()
        sums.append(("VALIDATION_MANIFEST.json", manifest_sha))
        sums.sort()
        with open(os.path.join(pkg, "SHA256SUMS"), "w", encoding="utf-8") as h:
            h.write("".join("%s  %s\n" % (d, r) for r, d in sums))
        log("records (%s): %d exceptions, %d products, %d SHA256SUMS entries; manifest schema-valid"
            % (stage, len(exceptions), len(products), len(sums)))
        return len(sums)

    write_records("pre")
    if rehearse:
        for key in ("quick", "full", "reproduce", "docker", "documents"):
            execution[key] = {"result": "not_executed", "reason": "--rehearse"}
        log("REHEARSAL: validations not run")
    else:
        papers = "--papers" if shutil.which("latexmk") or shutil.which("tectonic") else ""
        cmd = ["sh", os.path.join(pkg, "reproduce.sh")] + ([papers] if papers else [])
        code, secs = run(cmd, cwd=pkg, log_path=os.path.join(pkg, "logs", "reproduce.stdout"))
        execution["reproduce"] = {"command": " ".join(["./reproduce.sh"] + ([papers] if papers else [])),
                                  "exit_code": code, "result": "passed" if code == 0 else "failed", "seconds": secs,
                                  "log": "logs/reproduction.log", "report": "logs/reproduction_report.csv"}
        timings.append(("reproduce", secs))
        log("reproduce.sh exit %d (%.0f s)" % (code, secs))
        # rc42: the suites run here against the PRE-stage records (the final records are
        # written after them, and the records gate below asserts the shipped stage); the
        # stage test reads this variable and skips, so a pre-stage run cannot fail on it
        pre_env = dict(os.environ, PKINV_PACKAGER_STAGE="pre")
        for mode, key in (("--quick", "quick"), ("--full", "full")):
            code, secs = run(["sh", os.path.join(pkg, "validate.sh"), mode], cwd=pkg,
                             log_path=os.path.join(pkg, "logs", "validate_%s.stdout" % key), env=pre_env)
            execution[key] = {"command": "./validate.sh %s" % mode, "exit_code": code,
                              "result": "passed" if code == 0 else "failed", "seconds": secs,
                              "log": "logs/%s_validation.log" % key}
            timings.append(("validate %s" % mode, secs))
            log("validate.sh %s exit %d (%.0f s)" % (mode, code, secs))
        summary_path = os.path.join(pkg, "logs", "test_summary.json")
        if os.path.exists(summary_path):
            with open(summary_path, encoding="utf-8") as h:
                execution["full_suite"] = json.load(h)
        execution["documents"] = {"result": "not_executed",
                                  "reason": "no source vault mounted at packaging; run ./validate.sh --documents DIR"}
        if docker:
            waited = 0
            while not docker_ready() and waited < 7200:
                log("waiting for the Docker daemon (%d s)" % waited)
                time.sleep(60)
                waited += 60
            if docker_ready():
                dlog = os.path.join(pkg, "logs", "linux_validation.log")
                code_b, secs_b = run(["docker", "build", "-t", "pakemis-validation", "-f",
                                      "environment/container/Dockerfile", "."], cwd=pkg, log_path=dlog)
                results = {"build_exit": code_b, "build_seconds": secs_b}
                if code_b == 0:
                    # the container's logs go to logs/linux/ - mounted over /package/logs - so
                    # the packaging machine's own run logs are not overwritten by the second run;
                    # the reproduction's ledger and report are copied in so the ledger tests
                    # run there too (rc42)
                    linux_logs = os.path.join(pkg, "logs", "linux")
                    os.makedirs(linux_logs, exist_ok=True)
                    for name in ("reproduction_ledger.json", "reproduction_report.csv", "seeded_products.json"):
                        src_log = os.path.join(pkg, "logs", name)
                        if os.path.exists(src_log):
                            shutil.copy2(src_log, os.path.join(linux_logs, name))
                    for mode in ("--quick", "--full"):
                        code_r, secs_r = run(["docker", "run", "--rm", "--network=none",
                                              "-e", "PKINV_PACKAGER_STAGE=pre",
                                              "-v", "%s:/package" % pkg,
                                              "-v", "%s:/package/logs" % linux_logs,
                                              "pakemis-validation", "./validate.sh", mode], cwd=pkg, log_path=dlog)
                        results[mode] = {"exit_code": code_r, "seconds": secs_r}
                        timings.append(("docker validate %s" % mode, secs_r))
                ok = code_b == 0 and all(v["exit_code"] == 0 for k, v in results.items() if k.startswith("--"))
                execution["docker"] = {"result": "passed" if ok else "failed", "log": "logs/linux_validation.log",
                                       "run_logs": "logs/linux/ (the container's quick_validation.log, "
                                                   "full_validation.log, test_summary.json, exit_codes.txt)",
                                       "image": "python:3.11-slim + environment/requirements.lock", "details": results,
                                       "network": "--network=none"}
                log("docker validation %s" % execution["docker"]["result"])
            else:
                execution["docker"] = {"result": "not_executed", "reason": "Docker daemon not available after 2 h"}
        else:
            execution["docker"] = {"result": "not_executed", "reason": "--docker not given"}

    n_sums = write_records("final")
    # the records gate: the package's own tests over the FINISHED tree, with the final
    # records in place; its log is one of the three SHA256SUMS does not list
    env = dict(os.environ, PKINV_ROOT=pkg, PYTHONPATH=os.pathsep.join(
        [os.path.join(pkg, "src"), os.path.join(pkg, "tests"), os.path.join(pkg, "tests", "paper_numbers")]))
    code, secs = run([sys.executable, "-m", "unittest", "discover", "-s", os.path.join(pkg, "tests", "validation"),
                      "-t", os.path.join(pkg, "tests"), "-p", "test_*.py"], cwd=pkg,
                     log_path=os.path.join(pkg, "logs", "records_gate.log"), env=env)
    log("records gate (tests/validation over the finished tree) exit %d (%.0f s)" % (code, secs))
    if code != 0 and not allow_dirty:
        raise SystemExit("the package's own tests fail over the finished tree; see logs/records_gate.log")
    if code != 0:
        log("records gate failed under --allow-dirty (a dirty tree fails the identity test by design); not fatal here")
    # verify with the shipped checker before zipping - strict: every listed logs/ entry too
    code, _ = run([sys.executable, os.path.join(pkg, "tests", "validation", "check_sha256sums.py"), pkg, "--strict"],
                  cwd=pkg, log_path=os.path.join(pkg, "logs", "sha256_check_at_packaging.log"))
    log("SHA256SUMS strict self-check exit %d (%d entries)" % (code, n_sums))
    if code != 0:
        raise SystemExit("SHA256SUMS did not verify after writing; see logs/sha256_check_at_packaging.log")

    # 6. zip + the standalone manifest
    zip_path = os.path.join(out_dir, "pakemis_%s_full_validation.zip" % VERSION)
    manifest_out = os.path.join(out_dir, "pakemis_%s_validation_manifest.json" % VERSION)
    shutil.copy2(os.path.join(pkg, "VALIDATION_MANIFEST.json"), manifest_out)
    if os.path.exists(zip_path):
        os.remove(zip_path)
    t = time.time()
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
        for folder, dirs, names in os.walk(pkg):
            dirs[:] = sorted(d for d in dirs if d != "__pycache__")
            for name in sorted(names):
                full = os.path.join(folder, name)
                zf.write(full, os.path.join(NAME, os.path.relpath(full, pkg)))
    with zipfile.ZipFile(zip_path) as zf:
        inside = zf.read("%s/VALIDATION_MANIFEST.json" % NAME)
        tops = {n.split("/")[0] for n in zf.namelist()}
    with open(manifest_out, "rb") as h:
        outside = h.read()
    if inside != outside:
        raise SystemExit("the manifest inside the zip differs from the standalone copy")
    if tops != {NAME}:
        raise SystemExit("the zip does not expand to exactly one top-level folder: %s" % tops)
    log("zip -> %s (%.1f MB, %.0f s); manifest -> %s (byte-identical inside)"
        % (os.path.relpath(zip_path, ROOT), os.path.getsize(zip_path) / 1e6, time.time() - t, os.path.relpath(manifest_out, ROOT)))
    return 0


def _draws(pkg):
    try:
        import pyarrow.parquet as pq
        return pq.read_metadata(os.path.join(pkg, "outputs", "mc_draws", "pakemis_ensemble_annual.parquet")).num_rows
    except Exception:                                   # noqa: BLE001
        with open(os.path.join(pkg, "outputs", "mc_draws", "pakemis_ensemble_annual.meta.json"), encoding="utf-8") as h:
            return int(json.load(h).get("n_iter", 0))


BUILD_LOG = os.path.join(ROOT, "dist", "build_validation_package.log")

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
