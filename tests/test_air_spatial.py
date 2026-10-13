"""Air-pollutant spatial/temporal/uncertainty products: parity with the GHG layer's guarantees."""

from pkinv.assets import asset_path
import collections
import os
import sys
import unittest


from pkinv.sectors.agriculture import air_pollutants as ap  # noqa: E402
from pkinv.sectors.agriculture import air_key_categories as akc  # noqa: E402
from pkinv.sectors.agriculture import air_timeseries as ats  # noqa: E402
from pkinv.sectors.agriculture import air_uncertainty as au  # noqa: E402
from _support import ROOT

ADM1 = asset_path(ROOT, "data", "gis", "PAK_ADM1.geojson")


@unittest.skipUnless(os.path.exists(ADM1), "no GIS boundaries")
class TestAirSpatial(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.agriculture.gis import air_spatial as asp
        cls.asp = asp
        cls.rasters, cls.district_rows, cls.prov_totals, cls.scopes = asp.build()
        cls.national = {p: sum(v.values()) for p, v in cls.prov_totals.items()}

    def test_grid_reconciles_to_national_per_pollutant(self):
        for poll, arr in self.rasters.items():
            nat = self.national[poll]
            self.assertAlmostEqual(float(arr.sum()) / nat, 1.0, places=9,
                                   msg="%s grid %.4f vs national %.4f" % (poll, arr.sum(), nat))

    def test_districts_reconcile_to_national_per_pollutant(self):
        tot = collections.defaultdict(float)
        for r in self.district_rows:
            tot[r["pollutant"]] += r["emissions_kt"]
        for poll, nat in self.national.items():
            self.assertAlmostEqual(tot[poll] / nat, 1.0, places=9)

    def test_provinces_match_the_published_province_split(self):
        prov = ap._provincial(ap.compute())
        want = collections.defaultdict(float)
        for r in prov:
            want[r["pollutant"]] += r["emissions_kt"]
        for poll, nat in self.national.items():
            self.assertAlmostEqual(nat, want[poll], places=6)

    def test_livestock_streams_grid_on_livestock_not_cropland(self):
        """The sub-item fidelity that motivated this layer: manure NH3 must not ride cropland."""
        from pkinv.sectors.agriculture.gis.run_gis import resolve_proxies
        from pkinv.core.gis.grid import build_grid
        proxies, _, _ = resolve_proxies(build_grid())
        manure = self.asp._gis_proxy("livestock_total", "Manure management", proxies)
        fert = self.asp._gis_proxy("fertilizer_N", "Managed soils", proxies)
        self.assertEqual(manure, "glw_livestock")
        self.assertEqual(fert, "cropland")
        self.assertNotEqual(manure, fert)

    def test_burning_uses_the_fire_raster_when_available(self):
        from pkinv.sectors.agriculture.gis.run_gis import resolve_proxies
        from pkinv.core.gis.grid import build_grid
        proxies, _, _ = resolve_proxies(build_grid())
        got = self.asp._gis_proxy("crop_total", "Field burning of residues", proxies)
        self.assertEqual(got, "firms_fire" if "firms_fire" in proxies else "cropland")


class TestAirTimeSeries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.series, cls.years = ats.build_series()

    def test_covers_1990_to_2024(self):
        self.assertEqual(min(self.years), 1990)
        self.assertEqual(max(self.years), 2024)

    def test_anchor_matches_the_standalone_2024_run(self):
        anchor = self.series[2024]
        rows = ap.compute()
        want = collections.defaultdict(float)
        for r in rows:
            want[r["pollutant"]] += r["emissions_kt"]
        for poll, cats in anchor.items():
            self.assertAlmostEqual(sum(cats.values()), want[poll], places=6)

    def test_activity_driven_growth(self):
        """Factors are constant, so every pollutant should grow with activity over 1990-2024."""
        for poll in ats.POLLUTANTS:
            a = sum(self.series[1990].get(poll, {}).values())
            b = sum(self.series[2024].get(poll, {}).values())
            self.assertGreater(b, a, poll)


class TestAirUncertainty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = ap.compute()
        cls.stats, _ = au.run_mc(n_iter=2000, rows=cls.rows)

    def test_mean_reproduces_the_deterministic_total(self):
        det = ap._by_pollutant(self.rows)
        for poll, s in self.stats.items():
            self.assertAlmostEqual(s["mean"] / det[poll], 1.0, delta=0.05, msg=poll)

    def test_percentiles_ordered(self):
        for poll, s in self.stats.items():
            self.assertLess(s["p025"], s["p50"])
            self.assertLess(s["p50"], s["p975"])

    def test_mc_agrees_with_approach1(self):
        for poll, s in self.stats.items():
            self.assertLess(abs(s["rel_pct"] - s["approach1_pct"]), 15.0, poll)


class TestAirKeyCategories(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # compute() returns (ranking, mc_map, sources_per_pollutant) since the
        # rankings became uncertainty-aware in rc10
        cls.result, cls.mc_map, cls.n_sources = akc.compute()

    def test_level_shares_sum_to_one(self):
        for poll, d in self.result.items():
            if d["level"]:
                self.assertAlmostEqual(sum(s for _, s, _, _ in d["level"]), 1.0, places=6, msg=poll)

    def test_nh3_has_multiple_key_sources(self):
        nh3 = self.result["NH3"]["level"]
        self.assertGreater(len(nh3), 3)
        self.assertGreater(len([1 for _, _, _, k in nh3 if k]), 1)

    def test_every_pollutant_analysed(self):
        for poll in ("NH3", "NOx", "CO", "PM2.5", "NMVOC", "BC", "SO2"):
            self.assertIn(poll, self.result)

    def test_rank_stability_is_honest_about_degeneracy(self):
        """The interval columns exist to expose soft rankings, and NH3's top
        sources ARE soft (they hold their point ranks in under two thirds of
        draws) - while a single-stream pollutant's 100% must never be read as
        certainty, which is why its rows carry the coverage note."""
        top_nh3 = [v for (p, _n), v in self.mc_map.items() if p == "NH3"]
        self.assertTrue(any(stab < 66.0 for _lo, _hi, stab in top_nh3))
        for poll in ("PM2.5", "CO", "NMVOC", "BC", "SO2"):
            self.assertEqual(self.n_sources[poll], 1)
            (_lo, _hi, stab), = [v for (p, _n), v in self.mc_map.items()
                                 if p == poll]
            self.assertEqual(stab, 100.0)


if __name__ == "__main__":
    unittest.main()
