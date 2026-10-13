"""The residential spatial hierarchy: strata -> district -> grid.

The gis extra is optional, so everything raster-shaped skips gracefully when it is
absent; the strata and district layers are pure-CSV arithmetic and always run.

Run:  python3 -m unittest discover tests -p "test_residential_gis.py"
"""
import unittest

from pkinv.sectors.residential import downscale, engine, hies
from pkinv.sectors.residential.data import ResidentialData
from pkinv.sectors.residential.gis import district_downscale as dd

try:
    import rasterio  # noqa: F401
    import numpy  # noqa: F401
    HAVE_GIS = True
except ImportError:
    HAVE_GIS = False


class TestStrata(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.comps = engine.build_components(cls.data)
        cls.rows = downscale.strata_rows(cls.data, cls.comps)

    def test_allocated_streams_sum_to_their_engine_totals(self):
        for fuel, word in (("firewood", "Firewood"), ("dung_cake", "Dung"),
                           ("lpg", "LPG")):
            allocated = sum(r["allocated_Mt_co2e"] for r in self.rows
                            if r["fuel"] == fuel and r["allocated_Mt_co2e"] != "")
            stream = sum(c["co2e_Mt_AR5"] for c in self.comps
                         if c["subitem"].split()[0] == word)
            self.assertAlmostEqual(allocated, stream, places=3, msg=fuel)

    def test_the_dung_the_strata_allocate_is_the_surveys(self):
        """rc67: the strata allocate the reference dung stream, and the reference burns
        what the household survey reports (1.19979 Mt CO2e; through rc66 the same rows
        allocated the whole diverted supply, 6.44605, which is configuration L now)."""
        allocated = sum(r["allocated_Mt_co2e"] for r in self.rows
                        if r["fuel"] == "dung_cake" and r["allocated_Mt_co2e"] != "")
        self.assertAlmostEqual(allocated, 1.19979, places=3)
        ledger = sum(c["co2e_Mt_AR5"]
                     for c in engine.build_components(self.data, dung_basis="ledger")
                     if c["subitem"].split()[0] == "Dung")
        self.assertAlmostEqual(ledger, 6.44605, places=5)
        self.assertGreater(ledger, 5 * allocated)

    def test_diagnostic_rows_do_not_carry_an_allocation(self):
        """Publishing the survey's gas distribution is a diagnostic; the engine rides
        metered connections, and a filled column here would claim otherwise."""
        for r in self.rows:
            if r["fuel"] in ("natural_gas", "kerosene", "charcoal", "coal",
                             "generator_fuel", "agricultural_waste", "cotton_sticks"):
                self.assertEqual(r["allocated_Mt_co2e"], "", r["fuel"])
                self.assertIn("diagnostic", r["basis"])

    def test_firewood_is_rural_and_gas_is_urban_in_the_survey(self):
        """The stratification the whole layer exists to carry: if these ever invert,
        the ingester's region coding flipped."""
        wood = hies.strata_shares("firewood")
        gas = hies.strata_shares("natural_gas")
        wood_rural = sum(v for (p, reg), v in wood.items() if reg == "rural")
        gas_urban = sum(v for (p, reg), v in gas.items() if reg == "urban")
        self.assertGreater(wood_rural, 0.6)
        self.assertGreater(gas_urban, 0.6)


class TestDistrict(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.rows, cls.prov_totals = dd.district_rows(cls.data)

    def test_reconciliation_is_exact(self):
        self.assertLess(dd.check(self.rows, self.prov_totals), dd.TOL)

    def test_every_stream_reaches_the_district_layer(self):
        words = {c["subitem"].split()[0]
                 for c in engine.build_components(self.data)}
        self.assertEqual({r["stream"] for r in self.rows}, words)

    def test_gas_concentrates_in_cities_and_firewood_does_not(self):
        """Lahore should hold a visibly larger share of Punjab's gas than of its
        firewood - the urban/rural strata doing real work at district level."""
        def punjab_share(stream, district):
            dist = sum(r["co2e_Mt_AR5"] for r in self.rows
                       if r["stream"] == stream and r["district"] == district)
            prov = sum(r["co2e_Mt_AR5"] for r in self.rows
                       if r["stream"] == stream and r["province"] == "Punjab")
            return dist / prov
        self.assertGreater(punjab_share("Natural", "Lahore District"),
                           2 * punjab_share("Firewood", "Lahore District"))

    def test_the_other_province_stays_a_residual(self):
        others = [r for r in self.rows if r["province"] == "Other"]
        for r in others:
            self.assertIn("residual", r["district"])

    def test_the_basis_column_says_what_each_split_is(self):
        for r in self.rows:
            self.assertTrue(r["basis"], r["stream"])


@unittest.skipUnless(HAVE_GIS, "gis extra not installed")
class TestGrid(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.core.gis.grid import build_grid
        from pkinv.core.gis.proxies import get_proxy
        from pkinv.sectors.residential.gis import run_gis
        cls.run_gis = run_gis
        cls.data = ResidentialData()
        cls.grid = build_grid()
        cls.proxies = {name: get_proxy(name, cls.grid)[0]
                       for name in sorted(set(run_gis.STREAM_PROXY.values()))}
        cls.matrix = run_gis.province_stream_matrix(cls.data)
        cls.surfaces = run_gis.stream_surfaces(cls.grid, cls.matrix, cls.proxies)

    def test_every_stream_has_a_surface_proxy(self):
        words = {c["subitem"].split()[0]
                 for c in engine.build_components(self.data)}
        self.assertEqual(words, set(self.run_gis.STREAM_PROXY))

    def test_the_grid_reconciles_to_the_engine(self):
        total = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data))
        placed = sum(float(a.sum()) for a in self.surfaces.values())
        self.assertAlmostEqual(placed, total, places=6)

    def test_each_province_holds_its_control(self):
        from pkinv.core.geography import PROVINCES
        for prov in PROVINCES:
            mask = self.grid.province_mask(prov)
            if int(mask.sum()) == 0:
                continue
            for word, arr in self.surfaces.items():
                self.assertAlmostEqual(float(arr[mask].sum()),
                                       self.matrix[prov].get(word, 0.0), places=9,
                                       msg="%s/%s" % (prov, word))

    def test_dung_and_gas_ride_different_surfaces(self):
        """The whole point of per-stream proxies: the dung surface must not correlate
        cell-for-cell with the gas surface (herd country is not the gas network)."""
        import numpy as np
        dung = self.surfaces["Dung"].ravel()
        gas = self.surfaces["Natural"].ravel()
        both = (dung > 0) & (gas > 0)
        corr = np.corrcoef(dung[both], gas[both])[0, 1]
        self.assertLess(corr, 0.9)




class TestDistrictMapAudit(unittest.TestCase):
    """rc14 (the ninth review's crosswalk item): the map must paint every
    boundary polygon whose allocation the CSV carries - the canonical ADM2
    package resolves all 27 previously-unmatched names - and every unpainted
    polygon must carry a declared reason in the audit product. Grey stopped
    meaning "name-match failure" and now means exactly one thing: the GB/AJK/ICT
    units covered by the single residual row, declared as such."""

    STATUSES = ("painted", "residual_declared")

    def setUp(self):
        import csv, os
        path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "outputs",
            "residential_district_map_audit_2024.csv")
        with open(path, newline="", encoding="utf-8") as handle:
            self.rows = list(csv.DictReader(handle))

    def test_every_boundary_polygon_is_accounted_for(self):
        self.assertEqual(len(self.rows), 126)
        for r in self.rows:
            self.assertIn(r["status"], self.STATUSES, r["shape_name"])
            self.assertTrue(r["reason"].strip(), r["shape_name"])

    def test_no_polygon_is_lost_to_name_matching(self):
        painted = sum(1 for r in self.rows if r["status"] == "painted")
        residual = sum(1 for r in self.rows if r["status"] == "residual_declared")
        self.assertEqual(painted, 114,
                         "a polygon with a real allocation went unpainted - the "
                         "99-of-126 defect returning")
        self.assertEqual(residual, 12)

    def test_karachi_paints_the_sum_of_its_seven_census_rows(self):
        karachi = next(r for r in self.rows if r["shape_name"] == "Karachi")
        self.assertEqual(karachi["status"], "painted")
        self.assertGreaterEqual(len(karachi["adm2_ids"].split(";")), 7)


if __name__ == "__main__":
    unittest.main()
