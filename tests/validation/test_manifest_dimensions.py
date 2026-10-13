"""Every count in VALIDATION_MANIFEST.json is re-derived here from the packaged files.

The manifest is generated mechanically by the packager; this test is the independent
recount, in a different process, against the files as shipped. A count that cannot be
reproduced from the package is a count the reviewer should not trust.
"""

from pkinv.assets import asset_path
import json
import os
import unittest

from _support import ROOT
from validation._package import IN_PACKAGE, data_rows, manifest, sha256


class TestTheManifestCountsAreReproducible(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not IN_PACKAGE:
            raise unittest.SkipTest("only inside a built validation package")
        cls.m = manifest()
        cls.dims = cls.m["expected_dimensions"]

    def rows(self, rel):
        return data_rows(asset_path(ROOT, rel))

    def test_fiscal_years_and_months(self):
        self.assertEqual(self.dims["fiscal_years"], len(self.rows("data/periods.csv")))
        self.assertEqual(self.dims["months"], len(self.rows("data/months.csv")))

    def test_sectors(self):
        with open(os.path.join(ROOT, "outputs", "release_manifest.json"), encoding="utf-8") as h:
            self.assertEqual(self.dims["sectors"], len(json.load(h)["sectors"]))
        self.assertEqual(self.dims["sectors"], len(self.rows("registries/sectors.csv")))

    def test_row_counts(self):
        self.assertEqual(self.dims["annual_atomic_rows"], len(self.rows("outputs/pakemis_atomic_annual.csv")))
        self.assertEqual(self.dims["monthly_rows"],
                         len(self.rows("outputs/pakemis_monthly_fy2015_16_fy2023_24.csv")))
        self.assertEqual(self.dims["source_streams"], len(self.rows("outputs/pakemis_source_streams.csv")))
        self.assertEqual(self.dims["completeness_rows"], len(self.rows("outputs/completeness.csv")))
        self.assertEqual(self.dims["structural_axes"], len(self.rows("outputs/national_axis_register.csv")))
        self.assertEqual(self.dims["named_configurations"],
                         len(self.rows("outputs/national_configurations.csv")))

    def test_every_annual_atom_has_twelve_months(self):
        atoms = {(r["period_id"], r["component_id"], r["configuration_id"], r["geography_id"])
                 for r in self.rows("outputs/pakemis_atomic_annual.csv") if r["estimate_status"] == "E"}
        months = {}
        for r in self.rows("outputs/pakemis_monthly_fy2015_16_fy2023_24.csv"):
            months.setdefault((r["period_id"], r["component_id"], r["configuration_id"],
                               r["geography_id"]), set()).add(r["month"])
        self.assertEqual(self.dims["monthly_rows"], 12 * len(months))
        short = {k: len(v) for k, v in months.items() if len(v) != 12}
        self.assertEqual(short, {})
        self.assertTrue(set(months) <= atoms or len(set(months) - atoms) == 0,
                        "monthly rows for components absent from the atomic table: %s"
                        % sorted(set(months) - atoms)[:5])

    def test_draw_counts(self):
        try:
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow not installed")
        table = pq.read_table(os.path.join(ROOT, "outputs", "mc_draws", "pakemis_ensemble_annual.parquet"),
                              columns=["draw_id"])
        self.assertEqual(self.dims["common_draws"], table.num_rows)
        mc = self.rows("outputs/national_uncertainty_montecarlo.csv")
        self.assertEqual({int(r["n_iter"]) for r in mc}, {self.dims["national_monte_carlo_draws"]})

    def test_release_identity_is_uniform(self):
        rel = self.m["release"]
        with open(os.path.join(ROOT, "outputs", "release_manifest.json"), encoding="utf-8") as h:
            rm = json.load(h)
        self.assertEqual(rel["version"], rm["version"])
        # the release manifest describes the CONTENT commit; the package's commit is the
        # record commit that follows the fixpoint (see release.commit_rule)
        self.assertEqual(rel["content_commit"], rm["git"]["describes_commit"])
        self.assertRegex(rel["git_commit_full"], r"^[0-9a-f]{40}$")
        self.assertFalse(rm["git"]["tree_dirty"])
        self.assertFalse(rel["git_dirty"])
        atoms = {r["release_id"] for r in self.rows("outputs/pakemis_atomic_annual.csv")}
        self.assertEqual(atoms, {rel["version"]})
        streams = {r["release_version"] for r in self.rows("outputs/pakemis_source_streams.csv")}
        self.assertEqual(streams, {rel["version"]})

    def test_the_recorded_hashes_match_the_files(self):
        rel = self.m["release"]
        self.assertEqual(rel["release_manifest_sha256"],
                         sha256(os.path.join(ROOT, "outputs", "release_manifest.json")))
        self.assertEqual(rel["source_manifest_sha256"],
                         sha256(asset_path(ROOT, "data", "SOURCE_MANIFEST.csv")))
        self.assertEqual(rel["product_manifest_sha256"],
                         sha256(os.path.join(ROOT, "outputs", "pakemis_product_catalog.csv")))
        with open(os.path.join(ROOT, "SHA256SUMS"), encoding="utf-8") as h:
            lines = [l for l in h if not l.rstrip("\n").endswith("  VALIDATION_MANIFEST.json")]
        import hashlib
        self.assertEqual(rel["sha256sums_sha256"], hashlib.sha256("".join(lines).encode("utf-8")).hexdigest())

    def test_every_product_entry_hash_and_row_count(self):
        for p in self.m["products"]:
            path = asset_path(ROOT, p["relative_path"])
            self.assertTrue(os.path.exists(path), p["relative_path"])
            self.assertEqual(p["sha256"], sha256(path), p["relative_path"])
            if p["format"] == "csv":
                self.assertEqual(p["row_count"], len(data_rows(path)), p["relative_path"])


if __name__ == "__main__":
    unittest.main()
