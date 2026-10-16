"""Make, CI and developer commands share the executable task registry."""

from pkinv.assets import asset_path
import os
import re
import unittest
import contextlib
import io

from pkinv.paths import ROOT
from pkinv import build, run_all


class TestOneBuildDefinition(unittest.TestCase):
    def test_make_default_and_sector_commands_use_registry(self):
        with open(os.path.join(ROOT, "Makefile"), encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn(".DEFAULT_GOAL := build", text)
        for target in ("build", "national", "agriculture", "waste", "aviation", "power",
                       "transport", "railways", "fugitives", "ippu", "industry", "residential"):
            body = re.search(r"^" + target + r":\n((?:\t.*\n)+)", text, re.M)
            self.assertIsNotNone(body, target)
            self.assertIn("python3 -m pkinv.build", body.group(1), target)

    def test_ci_executes_shared_registry_without_developer_cache(self):
        # rc69: two workflows. The public checks rebuild from the verified tables with the
        # deposit group; the complete reproduction is the strict full build.
        with open(os.path.join(ROOT, ".github", "workflows", "public-checks.yml"),
                  encoding="utf-8") as handle:
            public = handle.read()
        with open(os.path.join(ROOT, ".github", "workflows", "reproduce.yml"),
                  encoding="utf-8") as handle:
            full = handle.read()
        self.assertIn("python3 -m pkinv.build --group deposit --full", public)
        self.assertIn("python3 -m pkinv.build --group full --full --strict", full)
        text = public + full
        self.assertNotIn("python3 -m pkinv.sectors.", text)
        self.assertNotIn("python3 -m pkinv.report.", text)

    def test_groups_are_views_of_one_registry(self):
        full = build.phases_for_group("full")
        self.assertEqual(full, run_all.PHASES)
        self.assertGreater(len(full), 100)
        self.assertEqual(build.phases_for_group("ci"),
                         [p for p in full if p.label not in build.CI_EXCLUDED])

    def test_dev_keeps_semantic_products_and_omits_release_finalization(self):
        labels = {p.label for p in build.phases_for_group("dev")}
        self.assertIn("Semantic release", labels)
        self.assertIn("Canonical activity tables", labels)
        self.assertFalse(labels & build.FINALIZATION)

    def test_canonical_snapshot_follows_its_staging_producers(self):
        labels = [p.label for p in run_all.PHASES]
        canonical = labels.index("Canonical activity tables")
        for producer in ("ADM2 reporting units", "Power SO2 admission register",
                         "Brick kiln fleet observations", "Power plant workbooks"):
            self.assertLess(labels.index(producer), canonical)
        self.assertLess(canonical, labels.index("Agriculture"))

    def test_waste_summary_follows_the_draw_pool(self):
        labels = [p.label for p in run_all.PHASES]
        self.assertLess(labels.index("Waste MC draw file"), labels.index("Waste uncertainty"))

    def test_sector_aliases_keep_main_and_independent_outputs_cold_and_learned(self):
        phases = build.phases_for_group("dev")
        learned = {"phases": {p.label: {"observation_complete": True} for p in phases}}
        for cache in ({"phases": {}}, learned):
            for sector, expected in (
                    ("transport", {"outputs/transport_totals_2024.csv",
                                   "outputs/transport_provincial_shape_brackets.csv"}),
                    ("waste", {"outputs/waste_totals_2024.csv",
                               "outputs/waste_uncertainty_2024.csv"})):
                selected, _ = build.select(phases, build.sector_targets(phases, [sector]), cache)
                actual = {path for phase in selected for path in phase.writes}
                self.assertTrue(expected <= actual, (sector, expected - actual))

    def test_strict_refuses_partial_sector_selection(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as caught:
            build.main(["--strict", "--sector", "transport", "--dry-run"])
        self.assertEqual(caught.exception.code, 2)


class TestEveryPhaseRequirementIsPinned(unittest.TestCase):
    """rc42 (the twentieth review's R1). The aviation fallback study imported openap
    unconditionally while requirements.lock did not pin it, so the package's reproduce.sh
    stopped at that phase on a locked environment. A phase now DECLARES the third-party
    packages it needs (Phase.requires) and run_all refuses a strict run whose interpreter
    lacks one; this test holds the declaration to the lock and to the source."""

    LOCK = os.path.join(ROOT, "requirements.lock")
    # import name -> distribution name in the lock, where they differ
    ALIASES = {"yaml": "PyYAML", "netCDF4": "netCDF4", "PIL": "pillow", "sklearn": "scikit-learn",
               "osgeo": "GDAL", "cv2": "opencv-python", "shapely": "shapely"}

    def _pinned(self):
        with open(self.LOCK, encoding="utf-8") as handle:
            return {line.split("==")[0].strip().lower() for line in handle if "==" in line}

    def test_every_declared_requirement_is_in_the_lock(self):
        from pkinv import run_all
        pinned = self._pinned()
        for phase in run_all.PHASES:
            for module in phase.requires:
                name = self.ALIASES.get(module, module).lower()
                self.assertIn(name, pinned, "%s requires %s, which requirements.lock does not pin"
                              % (phase.label, module))

    def test_unconditional_third_party_imports_are_declared_or_pinned(self):
        """Every top-level `import x` / `from x import` in a phase's target module that is
        neither stdlib nor pkinv must be pinned in the lock (or declared on the phase)."""
        import ast
        import sys
        from pkinv import run_all
        pinned = self._pinned()
        stdlib = set(sys.stdlib_module_names)
        local = set()
        for top in ("src", "scripts"):
            for folder, _dirs, names in os.walk(asset_path(ROOT, top)):
                local.update(n[:-3] for n in names if n.endswith(".py"))
        problems = []
        for phase in run_all.PHASES:
            path = os.path.join(ROOT, "src", *phase.target.split(".")) + ".py"
            if not os.path.exists(path):
                path = os.path.join(ROOT, "src", *phase.target.split("."), "__main__.py")
            if not os.path.exists(path):
                continue
            tree = ast.parse(open(path, encoding="utf-8").read())
            for node in tree.body:
                names = []
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                    names = [node.module.split(".")[0]]
                for name in names:
                    if name in stdlib or name == "pkinv" or name in ("_support",):
                        continue
                    # a repository module imported by bare name (the eval scripts put a
                    # directory of their own on sys.path) is ours, not a distribution's
                    if name in local:
                        continue
                    dist = self.ALIASES.get(name, name).lower()
                    if dist not in pinned and name not in phase.requires:
                        problems.append("%s: %s imports %s (not in requirements.lock, not declared)"
                                        % (phase.label, os.path.relpath(path, ROOT), name))
        self.assertEqual(problems, [], "\n".join(problems))

    def test_a_missing_requirement_is_named_before_the_first_phase(self):
        from pkinv import run_all
        phase = next(p for p in run_all.PHASES if "openap" in p.requires)
        self.assertEqual(phase.label, "Aviation fallback study")
        self.assertIn("missing_requirements", open(os.path.join(ROOT, "src", "pkinv", "run_all.py"),
                                                   encoding="utf-8").read())
        self.assertEqual(run_all.missing_requirements(quick=True), [],
                         "this interpreter lacks a declared requirement; install requirements.lock")
