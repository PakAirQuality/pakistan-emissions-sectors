"""The air layers honour the year they are asked about (air program Wave 1).

Four engines already took a year; three defects kept the answers wrong off-reference:
power applied the FY2023-24 lignite share to years when no Thar unit ran, dropped the
year on bagasse, and passed a fiscal-START year straight into the fiscal-END captive
panel (a silent one-year shift). Railways burned 500 ppm sulfur in years that
circulated 0.5 percent fuel - the central case is now the year's own declared regime
(data/activity/railways/diesel_sulfur_regime.csv). Residential's series slice
generalises from PM2.5 alone to every species, keyed (stream, pollutant), absent -
never zero - where the reference emits none. Aviation needed nothing: its fleet mix
carries era rows back to 2006, asserted here so a future edit cannot silently shrink
the span. Reference-year outputs are byte-identical throughout (the gate's regen
asserts that; these tests pin the off-reference behaviour).

Run:  python3 -m unittest discover tests -p "test_air_year_plumbing.py"
"""
import unittest


class TestPowerOffReference(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.power.data import PowerData
        from pkinv.sectors.power import air_pollutants
        cls.data = PowerData()
        cls.ap = air_pollutants

    def test_no_thar_lignite_before_the_fleet_existed(self):
        rows = self.ap.compute(self.data, 2015)
        lignite = [r for r in rows
                   if "lignite" in r.get("fuel_detail", "").lower()
                   and r["emissions_kt"] > 0]
        self.assertEqual(lignite, [], "FY2015-16 coal carries Thar lignite mass")

    def test_the_reference_year_keeps_the_published_share(self):
        ref = {(r["fuel"], r["fuel_detail"], r["pollutant"]): r["emissions_kt"]
               for r in self.ap.compute(self.data)}
        again = {(r["fuel"], r["fuel_detail"], r["pollutant"]): r["emissions_kt"]
                 for r in self.ap.compute(self.data, None)}
        self.assertEqual(ref, again)

    def test_bagasse_is_absent_before_its_series_starts(self):
        rows = self.ap.compute(self.data, 2015)
        self.assertEqual([r for r in rows if r["fuel"] == "Bagasse"], [],
                         "bagasse air rows exist before the generation series begins")

    def test_captive_rides_the_fiscal_end_panel_unshifted_in_the_industry_layer(self):
        # rc58: captive is priced in the industrial air layer, whose years are fiscal-END
        # like the captive panel itself - so the class's activity for FY2016-17 (fy_end
        # 2017) is captive.gas_TJ(year=2017) times its declared share, with no +1 seam.
        # The grid screening no longer carries captive at all (include_captive=False).
        from pkinv.sectors.industry import air_pollutants as ind
        from pkinv.sectors.power import captive
        ctx = ind.Context()
        cls = {c["source_class_id"]: c for c in ind.classes()}["captive_gas_engine"]
        fy_end = 2017
        m = ind.activity(cls, fy_end, ctx)
        tj = captive.gas_TJ(ctx.power, year=fy_end)
        wrong_tj = captive.gas_TJ(ctx.power, year=fy_end - 1)
        self.assertNotAlmostEqual(tj, wrong_tj, places=0,
                                  msg="the two conventions coincide; pick another year")
        self.assertAlmostEqual(m["TJ_ncv"], tj * float(cls["activity_share"]), places=6)
        self.assertFalse([r for r in self.ap.compute(self.data, fy_end - 1)
                          if r["category"] == captive.CATEGORY])


class TestRailwaysSulfurRegime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.railways.data import RailwaysData
        from pkinv.sectors.railways import air_pollutants
        cls.data = RailwaysData()
        cls.ap = air_pollutants

    def test_the_regime_is_declared_for_all_nine_panel_years(self):
        for y in range(2016, 2025):
            self.assertIn(self.ap.case_for_year(y),
                          dict(self.ap.SULFUR_CASES))

    def test_an_undeclared_year_raises(self):
        with self.assertRaises(KeyError):
            self.ap.case_for_year(2010)

    def test_the_pre_euro2_years_burn_their_own_sulfur(self):
        self.assertEqual(self.ap.case_for_year(2016), "historical_0.5pct")
        self.assertEqual(self.ap.case_for_year(2017), "historical_0.5pct")
        so2_2016 = sum(r["emissions_kt"] for r in self.ap.compute(self.data, 2016)
                       if r["pollutant"] == "SO2")
        so2_2018 = sum(r["emissions_kt"] for r in self.ap.compute(self.data, 2018)
                       if r["pollutant"] == "SO2")
        self.assertGreater(so2_2016, 5 * so2_2018,
                           "the 0.5 percent years lost their order of magnitude")

    def test_the_reference_year_decision_is_unchanged(self):
        row = next(r for r in self.ap.compute(self.data)
                   if r["fuel"] == "Diesel" and r["pollutant"] == "SO2")
        self.assertEqual(row["sulfur_case"], self.ap.REFERENCE_CASE)
        self.assertEqual(self.ap.case_for_year(None), self.ap.REFERENCE_CASE)

    def test_an_explicit_case_still_overrides(self):
        row = next(r for r in self.ap.compute(self.data, 2016,
                                              sulfur_case="euro5_import_spec")
                   if r["fuel"] == "Diesel" and r["pollutant"] == "SO2")
        self.assertEqual(row["sulfur_case"], "euro5_import_spec")


class TestResidentialAirSeries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.residential.data import ResidentialData
        from pkinv.sectors.residential import timeseries, combustion, air_pollutants
        cls.data = ResidentialData()
        cls.ts = timeseries
        cls.ref = combustion.fuel_TJ(cls.data)
        cls.engine_rows = air_pollutants.compute(cls.data)

    def test_at_the_reference_the_slice_is_the_engine(self):
        air = self.ts.air_kt(self.data, self.ref, self.ref)
        by_key = {}
        for r in self.engine_rows:
            key = (self.ts.WORD_OF[r["subitem"].split()[0]], r["pollutant"])
            by_key[key] = by_key.get(key, 0.0) + r["emissions_kt"]
        self.assertEqual(set(air), set(by_key))
        for k, v in by_key.items():
            self.assertAlmostEqual(air[k], v, places=9, msg=str(k))

    def test_absent_species_stay_absent(self):
        # EMEP's own not-applicable: gas, LPG and kerosene publish no NH3 factor
        air = self.ts.air_kt(self.data, self.ref, self.ref)
        for stream in ("Natural gas", "LPG", "Kerosene"):
            self.assertNotIn((stream, "NH3"), air, stream)

    def test_pm25_kt_is_the_pm25_slice(self):
        series = self.ts.fuel_TJ_series(self.data)
        tj = {k: v for k, v in series[2019].items() if not k.startswith("_")}
        want = sum(kt for (_s, p), kt in
                   self.ts.air_kt(self.data, tj, self.ref).items() if p == "PM2.5")
        self.assertAlmostEqual(self.ts.pm25_kt(self.data, tj, self.ref), want,
                               places=12)


class TestAviationSpansTheWindow(unittest.TestCase):
    def test_all_nine_fiscal_years_compute(self):
        from pkinv.sectors.aviation.data import AviationData
        from pkinv.sectors.aviation import air_pollutants
        data = AviationData()
        for y in range(2015, 2024):  # fiscal-START keys: FY2015-16..FY2023-24
            rows = air_pollutants.compute(data, y)
            pols = {r["pollutant"] for r in rows}
            self.assertLessEqual({"NOx", "CO", "HC", "SO2", "PM2.5", "BC"}, pols,
                                 "year %d lost species" % y)


if __name__ == "__main__":
    unittest.main()
