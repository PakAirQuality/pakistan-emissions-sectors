"""The injected national Monte Carlo (rc12): draw files, prefix reproducibility,
skew fidelity, and the CRN-island tripwire.

The eighth review's P0: waste's ledger-true rerun engine and fugitives' bounded
split-triangular engine were re-expressed as mean-preserving lognormal surrogates on
the way into the national pool, compressing waste's upper tail (sector P97.5 ~98.9 Mt
arrived nationally as 63.5) and shifting fugitives' median (25.43 -> 23.79). These
tests hold the repair together: the national rows must carry the sector engines'
own quantiles, the draw files must be exact supersets of the published sector runs,
the manifest must let a clean room re-verify every draw, and the CRN analysis that
licenses injection (no shared parameter group spans an injected module and any
other) must stay true or fail loudly.

The skew-fidelity and median guards were proven RED against the shipped rc11
national CSV before the injection landed: the waste row's (P97.5-P50)/(P50-P2.5)
read ~1.84 under the lognormal surrogate against the sector engine's ~4.25.
"""
import csv
import json
import os
import sys
import unittest


from pkinv.core import mc_draws                              # noqa: E402
from pkinv.core import montecarlo as mc_core                 # noqa: E402
from pkinv.core.io import read_rows
from _support import OUT, ROOT



def _rows(name):
    return read_rows(os.path.join(OUT, name), comments=False)


def _national(name, scenario="within_sector"):
    return next(r for r in _rows("national_uncertainty_montecarlo.csv")
                if r["scenario"] == scenario and r["aggregation_level"] == "module"
                and r["name"] == name)


class TestDrawFiles(unittest.TestCase):

    def test_the_waste_prefix_reproduces_the_published_sector_run(self):
        """The 100k draw file's first 10,000 draws ARE the published 10,000-draw
        table, bit-for-bit at the quantile level: same seed, per-parameter
        identity-seeded streams, so extending n_iter appends rather than
        reshuffles. If this fails, someone reordered the rerun loop and every
        published waste quantile silently changed meaning."""
        cols, meta = mc_draws.read("waste_parameter_rerun")
        self.assertEqual(meta["seed"], 4421)
        published = next(r for r in _rows("waste_parameter_mc_2024.csv")
                         if r["scope"] == "SECTOR")
        prefix = sorted(cols["MODULE_TOTAL"][:10000])
        for pcol, p in (("P2.5", 0.025), ("P50", 0.50), ("P97.5", 0.975)):
            self.assertAlmostEqual(mc_core.percentile(prefix, p),
                                   float(published[pcol]), places=4,
                                   msg="waste prefix %s" % pcol)

    def test_the_fugitives_prefix_reproduces_the_published_sector_run(self):
        """Same property for the sequential seed-42 stream: any reordering of the
        fugitives loop breaks the prefix and fails here rather than reshuffling
        the national row."""
        cols, meta = mc_draws.read("fugitives_bounded")
        self.assertEqual(meta["seed"], 42)
        published = next(r for r in _rows("fugitives_uncertainty_2024.csv")
                         if r["segment"] == "TOTAL")
        prefix = sorted(cols["MODULE_TOTAL"][:10000])
        self.assertAlmostEqual(mc_core.percentile(prefix, 0.50),
                               float(published["p50"]), places=3)

    def test_read_verifies_the_recorded_hash(self):
        """mc_draws.read re-hashes the CSV against its meta record - a draw file
        and its provenance cannot silently diverge."""
        for name in ("waste_parameter_rerun", "fugitives_bounded"):
            _cols, meta = mc_draws.read(name)
            path = os.path.join(mc_draws.DRAW_DIR, "%s.csv" % name)
            self.assertEqual(mc_draws.sha256(path), meta["sha256"], name)

    def test_the_module_total_column_is_the_category_sum(self):
        """Sector = sum of categories per draw index, exactly - the property that
        makes the national category pass and sector pass the same draws viewed
        two ways for the injected modules."""
        cols, _meta = mc_draws.read("waste_parameter_rerun")
        cats = [c for c in cols if c != "MODULE_TOTAL"]
        for i in (0, 137, 9999, 99999):
            self.assertAlmostEqual(sum(cols[c][i] for c in cats),
                                   cols["MODULE_TOTAL"][i], places=9)


class TestNationalInjection(unittest.TestCase):
    """The published national CSV carries the sector engines' asymmetry."""

    def test_waste_skew_fidelity(self):
        """THE P0 GUARD, proven red on the rc11 CSV (surrogate skew ~1.84 vs the
        sector engine's ~4.25): the national waste row's upper-to-lower arm ratio
        must match the rerun engine's own, because they are now the same draws."""
        nat = _national("waste")
        skew = ((float(nat["P97.5_Mt"]) - float(nat["P50_Mt"]))
                / (float(nat["P50_Mt"]) - float(nat["P2.5_Mt"])))
        cols, _meta = mc_draws.read("waste_parameter_rerun")
        s = sorted(cols["MODULE_TOTAL"])
        engine_skew = ((mc_core.percentile(s, 0.975) - mc_core.percentile(s, 0.50))
                       / (mc_core.percentile(s, 0.50) - mc_core.percentile(s, 0.025)))
        self.assertAlmostEqual(skew, engine_skew, delta=0.02)
        # Through rc66 this also asserted skew > 3.0, which told the engine's ~4.25 from
        # the surrogate's ~1.84. That gap came from the effluent factor's 2006 range
        # (to 0.25). On the 2019 Refinement's range (to 0.075, rc67) the engine's own
        # skew is about 1.8, so the threshold can no longer tell the two apart and the
        # equality above is the guard: the national row IS the engine's draws.
        self.assertGreater(skew, 1.5)
        self.assertLess(skew, 2.2)

    def test_fugitives_median_is_the_sector_engines(self):
        """Red on rc11 at 23.785 (the lognormal mean-preserving median); the
        sector engine's bounded split-triangular median is ~25.43 and the national
        row now consumes those exact draws."""
        nat = _national("fugitives")
        cols, _meta = mc_draws.read("fugitives_bounded")
        s = sorted(cols["MODULE_TOTAL"])
        self.assertAlmostEqual(float(nat["P50_Mt"]),
                               mc_core.percentile(s, 0.50), delta=0.005)

    def test_distribution_ids_are_per_row_truth(self):
        """Red on rc11, where one constant claimed lognormal for every row."""
        self.assertEqual(_national("waste")["distribution_id"],
                         "parameter_rerun_ledger_true")
        self.assertEqual(_national("fugitives")["distribution_id"],
                         "bounded_split_triangular")
        self.assertEqual(_national("power")["distribution_id"],
                         "mean_preserving_lognormal")
        total = next(r for r in _rows("national_uncertainty_montecarlo.csv")
                     if r["aggregation_level"] == "national"
                     and r["scenario"] == "within_sector")
        self.assertIn("mixture", total["distribution_id"])

    def test_the_asymmetric_surface_is_published(self):
        """rel_down/rel_up and the per-quantile standard errors exist and are
        consistent with the quantiles they summarise."""
        nat = _national("waste")
        p025, p50, p975 = (float(nat["P2.5_Mt"]), float(nat["P50_Mt"]),
                           float(nat["P97.5_Mt"]))
        self.assertAlmostEqual(float(nat["rel_down_pct_95"]),
                               (p50 - p025) / p50 * 100, delta=0.01)
        self.assertAlmostEqual(float(nat["rel_up_pct_95"]),
                               (p975 - p50) / p50 * 100, delta=0.01)
        self.assertGreater(float(nat["rel_up_pct_95"]),
                           float(nat["rel_down_pct_95"]))
        self.assertTrue(nat["p975_se_Mt"])

    def test_the_sources_registry_resolves(self):
        """Every injected row's source_registry pointer resolves to a registry row
        whose draw-file hash re-verifies."""
        reg = {r["module"]: r for r in _rows("national_uncertainty_sources.csv")}
        for module, name in (("waste", "waste_parameter_rerun"),
                             ("fugitives", "fugitives_bounded")):
            row = reg[module]
            path = os.path.join(mc_draws.DRAW_DIR, "%s.csv" % name)
            self.assertEqual(row["draw_file_sha256"], mc_draws.sha256(path), module)
            self.assertTrue(int(row["n_iter"]) >= 100000)

    def test_the_manifest_publishes_seeds_and_draw_hashes(self):
        """Red on rc11: the manifest recorded only seed 42, and the waste paper
        called 4321 'private'. A clean room needs every seed and every hash."""
        with open(os.path.join(OUT, "release_manifest.json"),
                  encoding="utf-8") as f:
            mc = json.load(f)["monte_carlo"]
        self.assertEqual(mc["seeds"]["waste_structural_scenarios"], 4321)
        self.assertEqual(mc["seeds"]["waste_parameter_rerun"], 4421)
        self.assertEqual(mc["seeds"]["national_pooled"], 42)
        self.assertIn("Mersenne", mc["rng"])
        for module, name in (("waste", "waste_parameter_rerun"),
                             ("fugitives", "fugitives_bounded")):
            rec = mc["injected_draw_files"][module]
            path = os.path.join(mc_draws.DRAW_DIR, "%s.csv" % name)
            self.assertEqual(rec["sha256"], mc_draws.sha256(path), module)


class TestCRNIsland(unittest.TestCase):

    def test_no_dependency_group_spans_an_injected_module_and_any_other(self):
        """THE TRIPWIRE that licenses injection. Waste and fugitives are
        CRN-islands: every dependency group touching them is theirs alone, so
        replacing their lognormal surrogates with pre-drawn vectors severs zero
        cross-module correlation. If this ever fails - someone shared a
        population or fuel group into an injected module - injection is no longer
        free: either replay the group's z-stream inside the sector engine by the
        same stream_seed key, or declare the decorrelation in the sources
        registry. Do not silence this test without doing one of those."""
        from pkinv.core import parameters as param_core
        from pkinv.core import registry
        from pkinv.report.uncertainty_all import INJECTED_MODULES
        components, _cats, _sector_of = registry.build_all()
        modules_by_group = {}
        for c, shared, _resid, _over in param_core.decompose(components):
            for g in shared:
                modules_by_group.setdefault(g, set()).add(c.get("_sector"))
        # Wave 6 note: the per-draw gas coupling is NOT a dependency group and
        # does not weaken this invariant - it is a deterministic parameter
        # channel (uncertainty_all.COUPLING_COLUMNS) that re-expresses a draw
        # the island already made, consuming no randomness and sharing no
        # z-stream. The group invariant below still holds exactly.
        offenders = {g: mods for g, mods in modules_by_group.items()
                     if any(m in INJECTED_MODULES for m in mods) and len(mods) > 1}
        self.assertFalse(
            offenders,
            "dependency groups span an injected module and another module - "
            "injection now severs correlation and must be redesigned: %s"
            % offenders)

    def test_injection_leaves_every_other_module_bit_identical(self):
        """Seed discipline, shown not assumed: excluding the injected modules from
        the parameter plan must not move anyone else's draws, because every
        remaining stream is identity-seeded. Run small-N with and without
        injection and compare a non-injected module's samples bit-for-bit."""
        from pkinv.core import registry
        from pkinv.report import uncertainty_all
        components, categories, _sector_of = registry.build_all()
        for c in components:
            c["_mc_key"] = "%s|%s|%s" % (c["category"], c["subitem"], c["gas"])
        n = 200
        injected = {}
        for module, (name, _dist) in uncertainty_all.INJECTED_MODULES.items():
            cols, _meta = mc_draws.read(name)
            skip = ("MODULE_TOTAL",) + uncertainty_all.COUPLING_COLUMNS.get(
                module, ())
            for cat, draws in cols.items():
                if cat not in skip:
                    injected[cat] = draws[:n]
        with_inj = mc_core.run(components, categories, n_iter=n, seed=42,
                               stream="parameter", return_samples=True,
                               injected=injected)
        without = mc_core.run(components, categories, n_iter=n, seed=42,
                              stream="parameter", return_samples=True)
        cat = "Electricity and heat production"
        self.assertEqual(with_inj[2][cat], without[2][cat],
                         "a non-injected module's draws moved under injection")


if __name__ == "__main__":
    unittest.main()


class TestPerDrawGasCoupling(unittest.TestCase):
    """Wave 6: the physical-atmosphere identity holds inside every draw.

    The combustion sectors book delivered gas NET of the post-meter leak share;
    fugitives draws that same factor +/-60% inside its island. The coupling
    scales every net-of-leak component by its draw's own combusted fraction, so
    a draw where the network leaks more burns correspondingly less. These gates
    hold the channel's exact arithmetic and the positive control the plan
    demanded: with the coupling severed, the identity visibly fails.
    """

    N = 200

    @classmethod
    def setUpClass(cls):
        from pkinv.core import mc_draws
        from pkinv.report import uncertainty_all as ua
        cls.ua = ua
        cls.components, cls.categories, _ = ua.pooled(False)
        for c in cls.components:
            c["_mc_key"] = "%s|%s|%s" % (c["category"], c["subitem"], c["gas"])
        columns, _meta = mc_draws.read("fugitives_bounded")
        cls.mult = columns["POST_METER_INDUSTRIAL_MULTIPLIER"][:cls.N]

    def _run(self, coupled):
        from pkinv.core import montecarlo as mc_core
        cat_all, _s, _m, coupling = self.ua._load_injected(self.components)
        injected = {k: v[:self.N] for k, v in cat_all.items()}
        scalers = (self.ua.gas_coupling_scalers(self.components, coupling, self.N)
                   if coupled else None)
        _stats, _tot, samples = mc_core.run(
            self.components, self.categories, n_iter=self.N,
            seed=mc_core.SEED, has_sinks=False, stream="parameter",
            return_samples=True, cross_sector=False, injected=injected,
            component_scalers=scalers)
        return samples

    def test_the_scale_is_the_draws_own_combusted_fraction(self):
        from pkinv.sectors.fugitives import post_meter
        leak = post_meter.whole_gas_leak_share()
        coupled = self._run(True)
        severed = self._run(False)
        cat = "Captive gas self-generation (1A2)"
        for i in (0, 7, 42, 199):
            expected = (1.0 - leak * self.mult[i]) / (1.0 - leak)
            self.assertAlmostEqual(coupled[cat][i] / severed[cat][i], expected,
                                   places=9,
                                   msg="draw %d does not carry its own "
                                       "combusted fraction" % i)

    def test_severing_the_coupling_breaks_the_identity(self):
        """The positive control: without the channel the netted mass is fixed
        while the leak draw moves, so the two runs must differ on every draw
        where the multiplier is not 1."""
        coupled = self._run(True)
        severed = self._run(False)
        cat = "Captive gas self-generation (1A2)"
        moved = sum(1 for i in range(self.N)
                    if abs(coupled[cat][i] - severed[cat][i]) > 1e-12)
        self.assertGreater(moved, self.N * 0.95,
                           "the coupling changed almost nothing - the channel "
                           "is not reaching the netted components")

    def test_the_channel_consumes_no_randomness(self):
        """Non-gas categories are bit-identical with and without the coupling:
        the channel is deterministic and touches no z-stream."""
        coupled = self._run(True)
        severed = self._run(False)
        for cat in ("Enteric fermentation", "Road transport", "Cement production"):
            self.assertEqual(coupled[cat], severed[cat], cat)
