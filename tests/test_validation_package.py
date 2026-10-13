"""rc40: the national validation package builder is held to what it promises, without building.

The package is several gigabytes and its builder runs the full suite and a rebuild inside the
assembled tree, so these tests do not build it. They hold the SHIPPED templates, the layout
map and the custody rule to their commitments - the parts that rot silently between releases:
that inclusion is decided by the deposit manifest and not here; that every specification slot
is either mapped or declared; that the scripts run offline and never write into the packaged
outputs; that no secret name appears as a value anywhere in the templates.
"""

from pkinv.assets import asset_path
import os
import re
import unittest

from _support import ROOT

BUILDER = os.path.join(ROOT, "scripts", "build_validation_package.py")
VIEWS = os.path.join(ROOT, "src", "pkinv", "report", "validation_views.py")
TEMPLATES = os.path.join(ROOT, "validation_package")
SPEC_ROOT = ("VALIDATION_MANIFEST.json", "VALIDATION_MANIFEST.schema.json", "FILE_INVENTORY.csv", "SHA256SUMS",
             "README_VALIDATION.md", "KNOWN_EXCEPTIONS.json", "EXPECTED_RESULTS.json", "validate.sh", "reproduce.sh")
SPEC_SLOTS = (
    "registries/periods.csv", "registries/sectors.csv", "registries/ipcc_scope.csv", "registries/components.csv",
    "registries/configurations.csv", "registries/structural_axes.csv", "registries/invalid_configuration_combinations.csv",
    "registries/methods.csv", "registries/uncertainty_models.csv", "registries/uncertainty_parameters.csv",
    "registries/correlation_groups.csv", "registries/temporal_profiles.csv", "registries/geographies.csv",
    "registries/geometry_crosswalk.csv", "registries/source_documents.csv", "registries/source_streams.csv",
    "registries/emission_factors.csv", "registries/units.csv", "registries/gwp.csv", "registries/licences.csv",
    "registries/notation_keys.csv",
    "outputs/annual/pakemis_atomic_annual.csv", "outputs/annual/pakemis_atomic_annual.parquet",
    "outputs/annual/sector_totals.csv", "outputs/annual/category_totals.csv", "outputs/annual/gas_totals.csv",
    "outputs/annual/configuration_totals.csv", "outputs/annual/national_ar5_ar6_bridge.csv",
    "outputs/annual/annual_closure_report.csv", "outputs/annual/annual_method_basis_seams.csv",
    "outputs/monthly/pakemis_monthly_fy2015_16_fy2023_24.parquet", "outputs/monthly/annual_monthly_closure.csv",
    "outputs/monthly/temporal_evidence_by_stream.csv", "outputs/monthly/temporal_evidence_by_sector.csv",
    "outputs/monthly/temporal_profile_values.csv", "outputs/monthly/temporal_validation.csv",
    "outputs/monthly/variable_but_unobserved_mass.csv", "outputs/monthly/monthly_exceptions.csv",
    "outputs/spatial/spatial_decomposition.csv", "outputs/spatial/spatial_unallocated.csv",
    "outputs/spatial/spatial_exceptions.csv", "outputs/spatial/source_stream_spatial_metadata.csv",
    "outputs/spatial/adm1_closure.csv", "outputs/spatial/adm2_nesting_check.csv", "outputs/spatial/grid_closure.csv",
    "outputs/spatial/geometry_coverage.csv", "outputs/spatial/proxy_fallbacks.csv", "outputs/spatial/spatial_validation.csv",
    "outputs/uncertainty/uncertainty_parameter_registry.csv", "outputs/uncertainty/uncertainty_montecarlo.csv",
    "outputs/uncertainty/national_uncertainty.csv", "outputs/uncertainty/national_uncertainty_reconciliation.csv",
    "outputs/uncertainty/correlation_matrix.csv", "outputs/uncertainty/common_draw_annual.parquet",
    "outputs/uncertainty/common_draw_monthly.parquet", "outputs/uncertainty/common_draw_spatial.parquet",
    "outputs/uncertainty/common_draw_summary.csv", "outputs/uncertainty/trend_uncertainty.csv",
    "outputs/uncertainty/key_category_uncertainty.csv", "outputs/uncertainty/uncertainty_exceptions.csv",
    "outputs/configurations/structural_axes.csv", "outputs/configurations/national_structural_bridge.csv",
    "outputs/configurations/national_configurations.csv", "outputs/configurations/configuration_dependencies.csv",
    "outputs/configurations/invalid_combinations.csv", "outputs/configurations/configuration_trajectories_nine_years.csv",
    "outputs/cross_sector/cross_sector_closure_registry.csv", "outputs/cross_sector/dung_transfer.csv",
    "outputs/cross_sector/crop_residue_transfer.csv", "outputs/cross_sector/delivered_gas_combustion_fugitive_ledger.csv",
    "outputs/cross_sector/generator_petrol_transfer.csv", "outputs/cross_sector/road_diesel_offroad_partition.csv",
    "outputs/cross_sector/waste_fate_ledger.csv", "outputs/cross_sector/fertiliser_feedstock_combustion_urea_ledger.csv",
    "outputs/cross_sector/cross_sector_closure_report.csv",
    "outputs/completeness/completeness.csv", "outputs/completeness/completeness_matrix.csv",
    "outputs/completeness/completeness_mass.csv", "outputs/completeness/unbounded_gaps.csv",
    "outputs/completeness/bounded_gaps.csv", "outputs/completeness/ie_destination_registry.csv",
    "outputs/completeness/scope_exclusions.csv", "outputs/completeness/lulucf_scope_decision.csv",
    "outputs/completeness/completeness_validation.csv",
    "outputs/validation/validation_catalogue.csv", "outputs/validation/comparison_independence_matrix.csv",
    "outputs/validation/annual_benchmarks.csv", "outputs/validation/spatial_benchmarks.csv",
    "outputs/validation/temporal_benchmarks.csv", "outputs/validation/source_extraction_audit.csv",
    "outputs/validation/withheld_validation.csv", "outputs/validation/benchmark_results.csv",
    "outputs/validation/validation_limitations.csv",
)


def _read(path):
    with open(path, encoding="utf-8") as handle:
        return handle.read()


class TestTheBuilderIsHonestAboutInclusion(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.builder = _read(BUILDER)

    def test_inclusion_is_decided_by_the_deposit_manifest(self):
        """The one custody decision this repository has tested is the deposit's; the packager
        consumes it and does not make its own."""
        self.assertIn("deposit.DEPOSITABLE", self.builder)
        self.assertIn("pakemis_deposit_manifest.csv", self.builder)
        self.assertIn("No licence is asserted at packaging time", self.builder)

    def test_documents_are_registered_never_copied(self):
        for tree in ('"sources/"', '"data/cache/"', '"data/raw/"'):
            self.assertIn(tree, self.builder)
        self.assertIn("hash_only", self.builder)
        self.assertIn("restricted_source_registry.csv", self.builder)
        self.assertIn("SOURCE_MANIFEST.csv", self.builder)

    def test_every_specification_slot_is_mapped_or_declared(self):
        """A slot counts as mapped if the layout names it literally, by basename (the
        loops that copy a list of canonical files under one folder), or as a `%s` template
        (the three common-draw files)."""
        def mapped(slot):
            base = os.path.basename(slot)
            templated = re.sub(r"annual|monthly|spatial", "%s", base)
            return slot in self.builder or base in self.builder or templated in self.builder
        missing = [slot for slot in SPEC_SLOTS if not mapped(slot)]
        self.assertEqual(missing, [], "specification slots the layout neither maps nor declares")
        for name in SPEC_ROOT:
            self.assertIn(name, self.builder + "".join(os.listdir(TEMPLATES)), name)

    def test_failures_are_recorded_not_excluded(self):
        self.assertIn("tests_failing_in_the_packaged_run", self.builder)
        self.assertIn("never excluded", self.builder)

    def test_the_manifest_hash_rule_is_stated(self):
        self.assertIn("sha256sums_sha256_rule", self.builder)
        self.assertIn("VALIDATION_MANIFEST.json line removed", self.builder)

    def test_the_zip_is_checked_for_one_top_level_folder_and_an_identical_manifest(self):
        self.assertIn("exactly one top-level folder", self.builder)
        self.assertIn("inside != outside", self.builder)

    def test_a_dirty_tree_is_refused_by_default(self):
        self.assertIn('git("status", "--porcelain")', self.builder)
        self.assertIn("run the release fixpoint", self.builder)
        self.assertIn("ARTIFACT_PATTERNS", self.builder)   # the fixpoint's own contract, not a stricter one


class TestTheShippedScripts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validate = _read(os.path.join(TEMPLATES, "validate.sh"))
        cls.reproduce = _read(os.path.join(TEMPLATES, "reproduce.sh"))
        cls.docker = _read(os.path.join(TEMPLATES, "Dockerfile"))
        cls.envvars = _read(os.path.join(TEMPLATES, "environment_variables.md"))

    def test_both_scripts_run_offline(self):
        for text in (self.validate, self.reproduce):
            self.assertIn('http_proxy="http://127.0.0.1:9"', text)
            self.assertIn("unset FIRMS_MAP_KEY", text)

    def test_both_scripts_set_the_root_explicitly(self):
        self.assertIn('export PKINV_ROOT="$ROOT"', self.validate)
        self.assertIn('PKINV_ROOT="$TREE"', self.reproduce)

    def test_canonical_bootstrap_precedes_model_validation_and_reproduction(self):
        self.assertLess(self.validate.index('step "canonical-inputs"'),
                        self.validate.index('step "package-tests"'))
        self.assertLess(self.reproduce.index('-m pkinv.activity.build'),
                        self.reproduce.index('$PYTHON run_all.py'))
        builder = _read(BUILDER)
        self.assertIn("recipe = deposit.canonical_recipe_inputs()", builder)
        self.assertLess(builder.index('timed("reconstruct canonical inputs offline"'),
                        builder.index('timed("environment/"'))
        self.assertIn('artifact_role="canonical_input"', builder)

    def test_reproduce_never_writes_into_the_packaged_outputs(self):
        self.assertIn("mktemp -d", self.reproduce)
        self.assertIn("NEVER OVERWRITES THE PACKAGED OUTPUTS", self.reproduce)
        self.assertNotRegex(self.reproduce, r'run_all\.py[^\n]*"\$ROOT"')

    def test_validate_runs_the_release_suite_unmodified_in_full_mode(self):
        self.assertIn("run_suite.py", self.validate)
        self.assertIn("python3 -m unittest discover tests", _read(os.path.join(ROOT, "tests", "validation", "run_suite.py")))

    def test_every_step_records_its_exit_code(self):
        self.assertIn("exit_codes.txt", self.validate)
        self.assertIn("command_timings.csv", self.validate)
        self.assertIn("exit_codes.txt", self.reproduce)

    def test_the_container_runs_without_network(self):
        self.assertIn("--network=none", self.docker)
        self.assertIn("requirements.lock", self.docker)

    def test_no_secret_value_anywhere_in_the_templates(self):
        """Names of variables may appear; values may not. A FIRMS key is 32 hex characters."""
        # Dotfiles are not templates. macOS drops a binary .DS_Store into any directory Finder
        # opens, and reading it as UTF-8 raises - which would turn a secret scan into a crash
        # that says nothing about secrets. The scan is over the package's own files.
        for name in sorted(n for n in os.listdir(TEMPLATES) if not n.startswith(".")):
            text = _read(os.path.join(TEMPLATES, name))
            self.assertNotRegex(text, r"FIRMS_MAP_KEY\s*=\s*[0-9a-fA-F]{20,}", name)
            self.assertNotRegex(text, r"\b[0-9a-f]{32}\b(?!.*sha)", name)


class TestTheViewsAreProjectionsOnly(unittest.TestCase):
    def test_every_view_declares_itself_a_view_in_its_banner(self):
        text = _read(VIEWS)
        self.assertIn("A VIEW IS NOT A PRODUCT", text)
        self.assertIn("VIEW: a mechanical projection", text)

    def test_the_correlation_matrix_is_labelled_implied(self):
        self.assertIn("NOT AN ESTIMATED MATRIX", _read(VIEWS))

    def test_views_read_products_they_do_not_recompute_emissions(self):
        """A view may sum, filter, join and project. It must not import an engine."""
        text = _read(VIEWS)
        self.assertNotRegex(text, r"from pkinv\.sectors|import pkinv\.sectors")
        self.assertNotRegex(text, r"pkinv\.core\.montecarlo|pkinv\.core\.uncertainty")


class TestTheRegistriesTheBuilderDependsOn(unittest.TestCase):
    def test_the_schema_registry_and_ledger_map_exist_and_are_read(self):
        from pkinv.assets import resolve
        for name in ("product_schemas.csv", "cross_sector_ledger_map.csv"):
            self.assertTrue(os.path.exists(resolve(asset_path(ROOT, "data", name), root=ROOT)))
            self.assertIn(name, _read(BUILDER))

    def test_the_package_tests_ship_with_the_repository_suite(self):
        folder = os.path.join(ROOT, "tests", "validation")
        for name in ("__init__.py", "_package.py", "check_sha256sums.py", "run_suite.py", "summarise_logs.py",
                     "compare_outputs.py", "claim_registry.py", "test_presentation_identity.py",
                     "test_product_schemas.py", "test_manifest_dimensions.py", "test_sha256sums_coverage.py",
                     "test_cross_sector_ledger.py"):
            self.assertTrue(os.path.exists(os.path.join(folder, name)), name)

    def test_dist_is_ignored(self):
        self.assertIn("/dist/", _read(os.path.join(ROOT, ".gitignore")))


if __name__ == "__main__":
    unittest.main()


class TestTheRc42PackagerSequence(unittest.TestCase):
    """The twentieth review's R3/R5/R6 and gate 14, held on the builder and its templates
    without building the package."""

    def _text(self, rel):
        # inside a built package the templates sit at the root (validate.sh, reproduce.sh)
        # and the builder is not shipped; a test that needs the builder skips there
        path = asset_path(ROOT, rel)
        if not os.path.exists(path) and rel.startswith("validation_package/"):
            path = asset_path(ROOT, rel[len("validation_package/"):])
        if not os.path.exists(path):
            self.skipTest("%s is not part of this tree (the builder is not shipped)" % rel)
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_the_records_are_written_before_the_validations_and_again_after(self):
        text = self._text("scripts/build_validation_package.py")
        self.assertIn('write_records("pre")', text)
        self.assertIn('write_records("final")', text)
        reproduce = text.index('cmd = ["sh", os.path.join(pkg, "reproduce.sh")]')
        validate = text.index('run(["sh", os.path.join(pkg, "validate.sh"), mode]')
        self.assertLess(text.index('write_records("pre")'), reproduce)
        self.assertLess(reproduce, validate,
                        "reproduce.sh must run before validate.sh so the ledger tests have a ledger")

    def test_the_manifest_is_schema_validated_by_the_packager(self):
        self.assertIn("jsonschema.Draft202012Validator(schema).validate(manifest)",
                      self._text("scripts/build_validation_package.py"))

    def test_the_packagers_trailing_logs_are_not_hashed_and_the_check_is_strict(self):
        text = self._text("scripts/build_validation_package.py")
        for name in ("logs/build_tail.log", "logs/sha256_check_at_packaging.log", "logs/records_gate.log",
                     "logs/command_timings.csv", "logs/exit_codes.txt"):
            self.assertIn(name, text)
        # the rewritten release manifest is compared outside the checkout-only blocks
        compare = self._text("tests/validation/compare_outputs.py")
        for block in ("git", "source_documents", "sources"):
            self.assertIn('"%s"' % block, compare)
        self.assertIn("_release_manifest_masked_equal", compare)
        self.assertIn('"--strict"', text)
        checker = self._text("tests/validation/check_sha256sums.py")
        self.assertIn("PACKAGER_TAIL_LOGS", checker)
        self.assertIn("--strict", checker)

    def test_the_exception_lifetime_is_the_enum(self):
        text = self._text("scripts/build_validation_package.py")
        self.assertIn('perm, horizon = "permanent", perm[len("permanent for "):]', text)

    def test_the_documents_gate_exists_and_reports_not_executed_without_a_vault(self):
        validate = self._text("validation_package/validate.sh")
        self.assertIn("--documents", validate)
        self.assertIn("exit 3", validate)
        self.assertIn("verify_vault.py", validate)
        self.assertIn("--sources", self._text("validation_package/reproduce.sh"))
        self.assertIn("def require_documents", self._text("tests/_support.py"))
        self.assertIn("document vault not mounted", self._text("tests/validation/summarise_logs.py"))
        self.assertTrue(os.path.exists(os.path.join(ROOT, "tests", "validation", "verify_vault.py")))

    def test_the_ledger_copies_reach_the_container(self):
        text = self._text("scripts/build_validation_package.py")
        self.assertIn('"reproduction_ledger.json", "reproduction_report.csv"', text)
