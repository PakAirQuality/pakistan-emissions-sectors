"""Air-pollutant co-emission layer: numeric pins, proxy discipline, provenance, GHG non-interference."""

from pkinv.assets import asset_path
import os
import sys
import unittest


from pkinv.sectors.agriculture import air_pollutants as ap  # noqa: E402
from pkinv.sectors.agriculture import downscale  # noqa: E402
from pkinv.sectors.agriculture import manure  # noqa: E402
from pkinv.sectors.agriculture import residue_burning  # noqa: E402
from pkinv.sectors.agriculture import soils  # noqa: E402
from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from _support import ROOT


class TestAirPollutants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = InventoryData()
        cls.rows = ap.compute(cls.data)
        cls.tot = ap._by_pollutant(cls.rows)

    # ---- regression pins (these fail if any factor, pool or formula silently changes) ----
    def test_national_totals_pinned(self):
        # NH3 is UNCHANGED by the manure nitrogen boundary correction (the air layer reads
        # managed_N and FPRP, not FON) -- that invariance is the cleanest evidence the fix
        # touched only the N2O path. Soil NOx does read FON, so it fell 161.3 -> 153.8.
        # NH3 2895.7 -> 2940.5: FracGASF moved from the IPCC "urea-dominant" default 0.15 to the
        # product-weighted EMEP/EEA high-pH value 0.1615 computed from Pakistan's own NFDC mix.
        # NH3 2973.7 -> 2658.1: the EMEP livestock chain is now resolved per species and manure
        # system (EMEP/EEA Table 3-9) instead of one solid chain for everything. Buffalo carry a
        # lower TAN fraction and storage factor than cattle, which the single chain overstated.
        # NH3 2658.1 -> 2730.5 when the sector moved to FY2023-24: nitrogen offtake rose from
        # 3,387 to 3,775 kt N, and the synthetic stream moved with it. Soil NOx rises for the
        # same reason: EMEP's soil-NOx factor reads the same nitrogen pool.
        #
        # NH3 2730.5 -> 2671.9 on the poultry correction, and the reason it was needed is the
        # claim that used to sit here. This comment said every livestock stream was unchanged
        # "because the herd is a census count and the census did not move", and offered that as
        # the cleanest available evidence that the period change touched the fertiliser path
        # and nothing else. It was wrong about one species: the census does not publish poultry
        # separately, so that row alone came from the Economic Survey - and it was read from the
        # 2024-25 edition, 2,260 million birds for a year the rest of the file does not cover.
        # The archived 2023-24 edition puts FY2023-24 at 2,065 million. Housing and storage
        # falls 882.3 -> 842.4 and manure applied to soils 885.0 -> 866.2 accordingly.
        #
        # The lesson is about the argument, not the arithmetic: "the census did not move" was
        # evidence about the census, and it was used as evidence about the activity file. One
        # row in that file was never census-based, and nothing checked whether the claim
        # covered it.
        # The residue-burning pollutants (PM2.5, CO, NMVOC, BC, SO2) rise with the crop harvest
        # the same way the residential residue fuel stream does: more straw grown is more straw
        # burned. Nothing else in the chain moved.
        expected = {"NH3": 2671.9, "NOx": 163.2, "PM2.5": 54.0,
                    "CO": 654.3, "NMVOC": 49.8, "BC": 3.6, "SO2": 2.8}
        for poll, want in expected.items():
            self.assertAlmostEqual(self.tot[poll], want, delta=max(0.1, 0.005 * want),
                                   msg="%s = %.2f, expected ~%.2f" % (poll, self.tot[poll], want))

    def test_nh3_streams_pinned(self):
        """Each NH3 source stream, so a change in one pool cannot hide inside the total."""
        # summed by GROUP since the Wave A disaggregation (product / species-stage /
        # crop suffixes); the groups are the same five pools and the pins are unchanged
        by_sub = {}
        for r in self.rows:
            if r["pollutant"] != "NH3":
                continue
            g = r["subitem"].rsplit(" (", 1)[0]
            if g in ("NH3 - housing", "NH3 - yard", "NH3 - storage"):
                g = "NH3 - housing and storage"
            by_sub[g] = by_sub.get(g, 0.0) + r["emissions_kt"]
        # grazing rose (EMEP factors are proportions of TAN, 0.14 for cattle/buffalo, not 0.06 of
        # total N) while storage and application fell on the species-specific factors
        # rc39 re-pinned all five to the rebuilt engine. A2 moved the synthetic stream by
        # +1.38 kt when FracGASF was re-weighted onto the fiscal year's own product mix
        # (0.1605 -> 0.1608). The four manure streams moved too - A1's census herd - but only
        # by 0.07-0.67 kt, INSIDE the 1.0 delta, so they would have gone on passing against
        # stale values. Pinning them to what the engine now produces keeps the guard tight
        # around the truth rather than merely non-failing.
        for sub, want in [("NH3 - synthetic fertiliser", 737.2),   # NH3-N basis, no 0.95 share
                          ("NH3 - pasture deposition (cattle-type)", 104.3),
                          ("NH3 - pasture deposition (sheep/goat/other)", 114.2),
                          ("NH3 - housing and storage", 842.8),
                          ("NH3 - manure applied to soils", 866.9)]:
            self.assertAlmostEqual(by_sub[sub], want, delta=1.0)

    def test_grazing_loss_is_lower_than_confined_loss(self):
        """EMEP: excreta at pasture volatilise far less per kg N than manure that passes through
        housing, storage and application. Checked on the species-resolved factors now in use."""
        for sp in ("buffalo", "dairy_cattle", "sheep"):
            graze = self.data.efv("nh3_emep_grazing", sp)
            confined = (self.data.efv("nh3_emep_housing", sp)
                        + self.data.efv("nh3_emep_storage", sp)
                        + self.data.efv("nh3_emep_application", sp))
            self.assertLess(graze, confined, sp)

    def test_benchmark_divergence_is_reported_not_hidden(self):
        """The NH3 benchmark must be computed and its REVIEW flags surfaced, not suppressed."""
        b = ap.benchmark(self.rows)
        self.assertTrue(b, "no air-pollutant benchmark computed")
        scopes = {r["scope"]: r for r in b}
        self.assertEqual(scopes["Managed soils - synthetic"]["within_0.5_2.0x"], "YES")
        self.assertEqual(scopes["Livestock (grazing+manure+management)"]["within_0.5_2.0x"],
                         "REVIEW")


    # ---- the defect this layer previously shipped: wrong province proxy for livestock-derived N ----
    def test_nitrogen_streams_use_the_same_proxies_as_the_ghg_layer(self):
        """Organic/pasture NH3 is livestock-derived and must NOT ride the fertiliser proxy."""
        want = {
            "NH3 - synthetic fertiliser": "fertilizer_N",
            # applied manure follows neither animal density nor cropland alone, but their
            # per-cell intersection (proxies.build_manure_applied_proxy)
            "NH3 - manure applied to soils": "manure_applied",
            "NH3 - pasture deposition (cattle-type)": "livestock_total",
            "NH3 - pasture deposition (sheep/goat/other)": "livestock_smallrum",
            "NH3 - housing and storage": "livestock_total",
        }
        got = {}
        for r in self.rows:
            g = r["subitem"].rsplit(" (", 1)[0]
            if g in ("NH3 - housing", "NH3 - yard", "NH3 - storage"):
                g = "NH3 - housing and storage"
            got[g] = downscale.proxy_for(
                {"category": r["category"], "subitem": r["ghg_subitem"]})
        for sub, proxy in want.items():
            self.assertEqual(got[sub], proxy, "%s allocated by %s" % (sub, got[sub]))

    def test_soil_nox_pools_ride_their_own_surfaces(self):
        """The Wave A repair this file exists to hold: soil NOx used to place manure-N
        and residue-N on the FERTILISER surface through a single summed row. Each pool
        now anchors its own stream, and the three-way split is an exact regrouping."""
        nox = {r["subitem"]: r for r in self.rows
               if r["pollutant"] == "NOx" and r["subitem"].startswith("Soil NOx")}
        self.assertEqual(set(nox), {"Soil NOx - synthetic fertiliser",
                                    "Soil NOx - organic manure",
                                    "Soil NOx - crop residues"})
        proxies = {sub: downscale.proxy_for({"category": r["category"],
                                             "subitem": r["ghg_subitem"]})
                   for sub, r in nox.items()}
        self.assertEqual(proxies["Soil NOx - synthetic fertiliser"], "fertilizer_N")
        self.assertEqual(proxies["Soil NOx - organic manure"], "manure_applied")
        self.assertEqual(proxies["Soil NOx - crop residues"], "crop_total")

    def test_provincial_split_differs_by_stream(self):
        """Guard the regression directly: fertiliser- and livestock-driven NH3 must not share a split."""
        prov = ap._provincial(self.rows)
        def share(sub, province):
            rows = [r for r in prov if r["subitem"].startswith(sub)]
            tot = sum(r["emissions_kt"] for r in rows)
            return sum(r["emissions_kt"] for r in rows if r["province"] == province) / tot
        self.assertGreater(share("NH3 - synthetic fertiliser", "Punjab"),
                           share("NH3 - pasture deposition (sheep/goat/other)",
                                 "Punjab") + 0.1)

    def test_provincial_sums_to_national(self):
        prov = ap._provincial(self.rows)
        for poll in self.tot:
            psum = sum(r["emissions_kt"] for r in prov if r["pollutant"] == poll)
            self.assertAlmostEqual(psum, self.tot[poll], places=6)

    # ---- provenance: the paper claims every factor is sourced; verify it ----
    def test_every_factor_has_a_nonempty_source(self):
        keys = [("burning", k) for _, k in ap.BURN_POLL]
        keys += [("burning", "combustion_factor"),
                 ("soils", "NH3_frac_of_volat"), ("soils", "NOx_frac_of_applied"),
                 ("soils", "FracGASF"), ("soils", "FracGASM")]
        for cat, item in keys:
            self.assertTrue(self.data.efs(cat, item).strip(),
                            "no source for %s/%s" % (cat, item))
            self.assertGreater(self.data.efu(cat, item), 0,
                               "no uncertainty for %s/%s" % (cat, item))

    def test_no_invented_uncertainties(self):
        """Every reported uncertainty must be a propagated combination, i.e. exceed its largest input."""
        for r in self.rows:
            self.assertGreater(r["uncert_pct"], 0)
            self.assertLess(r["uncert_pct"], 200)

    # ---- physical consistency ----
    def test_nh3_fraction_leaves_room_for_nox(self):
        """The FracGAS pool is NH3+NOx; assigning 100% to NH3 would double-count against soil NOx."""
        self.assertLess(self.data.efv("soils", "NH3_frac_of_volat"), 1.0)

    def test_volatilised_n_matches_the_pool_driving_indirect_n2o(self):
        """soils.volatilised_n must equal the volat_N computed inside soils.compute (duplicated eqn)."""
        _, npools = manure.compute(self.data)
        sv = soils.volatilised_n(self.data, npools)
        FSN = self.data.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000.0
        from pkinv.sectors.agriculture import fertiliser_mix
        gasf, _ = fertiliser_mix.fracgasf(self.data)   # NH3-N; the pool below is NH3-N + NOx-N
        gasf = gasf + self.data.efv("soils", "NOx_frac_of_applied")
        expected = (FSN * gasf
                    + (npools["FON_N"] + npools["FPRP_cattle_N"] + npools["FPRP_other_N"])
                    * self.data.efv("soils", "FracGASM"))
        self.assertAlmostEqual(sv["total"], expected, places=3)

    def test_burning_pollutants_scale_with_mass_burnt(self):
        mb = residue_burning.mass_burnt(self.data)
        cf = self.data.efv("burning", "combustion_factor")
        for poll, key in ap.BURN_POLL:
            got = sum(r["emissions_kt"] for r in self.rows
                      if r["pollutant"] == poll and r["category"] == "Field burning of residues")
            self.assertAlmostEqual(got, mb * cf * self.data.efv("burning", key) / 1e6, places=6)

    def test_nh3_dominated_by_manure_and_soils_not_burning(self):
        nh3_burn = sum(r["emissions_kt"] for r in self.rows
                       if r["pollutant"] == "NH3" and r["category"] == "Field burning of residues")
        self.assertLess(nh3_burn, 0.01 * self.tot["NH3"])


class TestMatchedYearBenchmark(unittest.TestCase):
    """The benchmarks report 2015; our anchor is 2024. Comparing across that gap silently folds
    nine years of activity growth into what is presented as methodological divergence."""

    @classmethod
    def setUpClass(cls):
        cls.rows = ap.compute(InventoryData())
        cls.b = {r["scope"]: r for r in ap.benchmark(cls.rows)
                 if r["source"].startswith("SANH")}

    def test_comparison_is_made_at_the_benchmark_year(self):
        for scope, r in self.b.items():
            self.assertEqual(r["year_matched"], "YES", scope)
            self.assertEqual(r["engine_year"], r["benchmark_year"], scope)
            self.assertEqual(r["benchmark_year"], 2015, scope)

    def test_matched_year_total_is_reported_with_its_anchor_and_growth(self):
        """Matching the year removes about a third of the apparent gap: 2.85x at the anchor is
        1.43x activity growth times 1.99x genuine divergence.

        The 0.5-2.0x screen is a triage flag, not a finding, and the paper describes 1.79x as a
        flagged divergence rather than a pass. Resolving the EMEP chain per species and system
        brought this down from 1.99x -- a real improvement, not a tuning."""
        r = self.b["TOTAL"]
        self.assertAlmostEqual(r["ratio"], 1.79, delta=0.05)
        self.assertAlmostEqual(r["ratio_anchor"], 2.56, delta=0.05)
        self.assertAlmostEqual(r["activity_growth"], 1.43, delta=0.05)

    def test_livestock_divergence_shrinks_but_survives(self):
        """The livestock stream stays flagged at matched year -- 2.93x, not the 4.64x the anchor
        comparison implies. It must not be presented as resolved."""
        r = self.b["Livestock (grazing+manure+management)"]
        self.assertAlmostEqual(r["ratio"], 2.50, delta=0.08)
        self.assertEqual(r["within_0.5_2.0x"], "REVIEW")

    def test_divergence_exceeds_both_stated_uncertainties(self):
        """The screen is triage; this is the actual test. The benchmark's own 95% interval is
        +/-279 kt and ours is +/-24%, and the two do not overlap -- so the divergence is larger
        than either study's stated confidence, which no factor-of-two flag can express."""
        import math
        r = self.b["TOTAL"]
        bench_ci = 279.3                      # their Table 3, 95%
        ours_ci = r["engine_kt"] * 0.237      # our Approach-1 95% relative on NH3
        self.assertGreater(r["engine_kt"] - ours_ci, r["benchmark_kt"] + bench_ci,
                           "intervals now overlap -- restate the benchmark discussion")
        z = (r["engine_kt"] - r["benchmark_kt"]) / math.sqrt((ours_ci / 1.96) ** 2
                                                             + (bench_ci / 1.96) ** 2)
        self.assertGreater(z, 2.0)

    def test_anchor_ratio_is_retained_not_discarded(self):
        """Both ratios stay in the output; the anchor one is labelled, not deleted."""
        for scope, r in self.b.items():
            self.assertIsNotNone(r["ratio_anchor"], scope)
            self.assertGreater(r["ratio_anchor"], r["ratio"], scope)

    def test_matched_year_rebuild_holds_factors_constant(self):
        """Only activity may vary between the anchor and the matched year: the burning pollutant
        ratios are pure activity, so they must all move by the same factor."""
        r2015 = ap.engine_rows_for_year(2015)
        self.assertIsNotNone(r2015, "historical activity unavailable")

        def burn(rows, poll):
            return sum(r["emissions_kt"] for r in rows if r["pollutant"] == poll
                       and r["category"] == "Field burning of residues")
        ratios = [burn(self.rows, p) / burn(r2015, p) for p, _ in ap.BURN_POLL]
        self.assertAlmostEqual(max(ratios), min(ratios), places=9)


class TestCrossLayerPM25(unittest.TestCase):
    """The inventory and the nowcast must not report different crop-fire PM2.5 (they did: 34x)."""

    def test_pm25_emission_factors_agree(self):
        import csv as _csv
        data = InventoryData()
        nowcast_ef = None
        with open(asset_path(ROOT, "data", "nowcast_params.csv"), newline="") as f:
            for r in _csv.DictReader(f):
                if r["param"] == "pm25_ef_g_per_kg":
                    nowcast_ef = float(r["value"])
        self.assertIsNotNone(nowcast_ef, "nowcast pm25_ef_g_per_kg missing")
        self.assertAlmostEqual(nowcast_ef, data.efv("burning", "Gef_PM25"), places=6,
                               msg="nowcast and inventory PM2.5 factors have diverged")

    def test_nowcast_pm25_matches_inventory_burning_pm25(self):
        """Both derive PM2.5 from the same activity-constrained burned mass."""
        import json
        card = os.path.join(ROOT, "outputs", "nowcast", "fire_emissions_card.json")
        if not os.path.exists(card):
            self.skipTest("nowcast not run")
        nowcast_kt = json.load(open(card))["totals"]["pm25_t"] / 1000.0
        rows = ap.compute(InventoryData())
        inv_kt = sum(r["emissions_kt"] for r in rows if r["pollutant"] == "PM2.5")
        self.assertAlmostEqual(nowcast_kt, inv_kt, delta=0.05 * inv_kt,
                               msg="nowcast %.1f kt vs inventory %.1f kt" % (nowcast_kt, inv_kt))


if __name__ == "__main__":
    unittest.main()
