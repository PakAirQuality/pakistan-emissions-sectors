"""A fresh compiled-input rebuild owns every compared product explicitly.

The rc68 source repairs replace the old GHG panel files. Keeping their former
numbers as live compatibility products would preserve known errors. Their archived
rc67 CSVs remain immutable, while actual regenerated AP compatibility views stay
in the current product family.
"""
import hashlib
import json
from pathlib import Path
import unittest

from pkinv.build import DEPOSIT_SOURCE_PHASES, phases_for_group
from pkinv.core.io import read_rows
from pkinv.core.reporting_window import RETIRED_GHG_PANEL_PRODUCTS
from pkinv.report import deposit_manifest, release_manifest
from pkinv.run_all import PHASES
from validation.compare_outputs import targets
from _support import ROOT


class CleanTargetOwnership(unittest.TestCase):
    def test_retirement_is_exactly_the_four_superseded_ghg_panel_files(self):
        self.assertEqual(RETIRED_GHG_PANEL_PRODUCTS, {
            "outputs/pakemis_annual_fy2015_16_fy2023_24.csv",
            "outputs/pakemis_annual_fy2015_16_fy2023_24.parquet",
            "outputs/pakemis_monthly_fy2015_16_fy2023_24.csv",
            "outputs/pakemis_monthly_fy2015_16_fy2023_24.parquet",
        })

    def test_retired_panels_are_not_advertised_or_deposited_as_current_products(self):
        release = {r["path"] for r in release_manifest._products()}
        deposit = {path for _kind, path in deposit_manifest.deposit_files()}
        compared = set(targets(ROOT))
        for name, paths in (("release", release), ("deposit", deposit),
                            ("comparison", compared)):
            self.assertFalse(paths & RETIRED_GHG_PANEL_PRODUCTS, name)
        for path in ("outputs/pakemis_annual_fy2015_16_fy2024_25.csv",
                     "outputs/pakemis_monthly_fy2015_16_fy2024_25.csv",
                     "outputs/pakemis_air_annual_fy2015_16_fy2023_24.csv"):
            self.assertIn(path, release)
            self.assertIn(path, deposit)

    def test_archived_rc67_panels_still_match_the_preserved_source_manifest(self):
        base = Path(ROOT) / "data/baselines/rc67_integrated_campaign"
        manifest = json.loads((base / "baseline.json").read_text())
        self.assertEqual(manifest["version"], "1.0.0rc67")
        hashes = {r["path"]: r["sha256"] for r in manifest["files"]}
        deposit = {path for _kind, path in deposit_manifest.deposit_files()}
        for relative in sorted(p for p in RETIRED_GHG_PANEL_PRODUCTS if p.endswith(".csv")):
            archived = base / relative
            self.assertEqual(hashlib.sha256(archived.read_bytes()).hexdigest(),
                             hashes[relative], relative)
            self.assertIn(str(archived.relative_to(ROOT)), deposit)

    def test_actual_secondary_writers_are_declared_before_the_clean_build(self):
        expected = {
            "Fugitive oil and gas": {"outputs/fugitives_post_meter_end_use_2024.csv"},
            "Industrial processes": {"outputs/ippu_urea_co2_bridge_2025.csv"},
            "Road transport": {"outputs/transport_fuel_ledger_2024.csv"},
            "Parameter decomposition": {"outputs/national_uncertainty_parameters.csv"},
            "National uncertainty": {"outputs/national_uncertainty_sources.csv"},
            "Fugitives MC draw file": {"outputs/mc_draws/fugitives_bounded.meta.json"},
            "Common draw ensemble": {"outputs/mc_draws/pakemis_ensemble_%s.meta.json" % k
                                     for k in ("annual", "monthly", "spatial")},
            "Air annual panel (supported fiscal panel)": {
                "outputs/pakemis_air_annual_fy2015_16_fy2023_24.csv"},
            "Air source classes (supported fiscal panel)": {
                "outputs/pakemis_air_source_classes_fy2015_16_fy2023_24.csv"},
        }
        phases = {p.label: p for p in PHASES}
        for label, writes in expected.items():
            self.assertTrue(writes <= set(phases[label].writes), label)

    def test_every_clean_comparison_target_is_written_or_explicitly_seeded(self):
        held = {r["path"] for r in read_rows(str(Path(ROOT) / "data/catalog/held_products.csv"))}
        seeded = held | {path for p in PHASES if p.label in DEPOSIT_SOURCE_PHASES
                         for path in p.writes if path.startswith("outputs/")}
        written = {path for p in phases_for_group("deposit") for path in p.writes}
        uncovered = [path for path in targets(ROOT, seeded)
                     if path not in seeded and path not in written
                     and not any(w.endswith("/") and path.startswith(w) for w in written)]
        self.assertEqual(uncovered, [])

    def test_pbs_source_control_seed_has_a_real_nonmutating_extraction_check(self):
        held = {r["path"]: r for r in read_rows(
            str(Path(ROOT) / "data/catalog/held_products.csv"))}
        row = held["outputs/pakemis_minerals_controls.csv"]
        self.assertEqual(row["verify_mode"], "checks")
        self.assertEqual(row["verify_command"], "python3 scripts/ingest_pbs_minerals.py --check")
        self.assertEqual(hashlib.sha256((Path(ROOT) / row["path"]).read_bytes()).hexdigest(),
                         row["sha256_at_release"])


if __name__ == "__main__":
    unittest.main()
