"""The railway air-pollutant layer: EMEP/EEA 2023 ch 1.A.3.c Tier 1, held to its rules.

What these tests pin, and why each rule exists:

  * every factor comes from the data file with the chapter's citation on it - the layer was
    blocked for want of this exact chapter, so a silently substituted factor would recreate
    the failure the gap register just closed;
  * SO2 is stoichiometry (2 x S x fuel mass), not a factor, and the sulfur ladder must be
    monotone - the honest statement about Pakistani diesel sulfur is a 290-fold span, and a
    case ladder that did not order itself would mean the params rows had been mixed up;
  * BC is a component of PM2.5, PM2.5 of PM10, PM10 of TSP - mass discipline, because the
    single easiest way to fake a particulate total is to add its components together;
  * the air layer burns the same fuel as the greenhouse-gas layer, exactly - one metered
    quantity drives both, which is what makes them one inventory.

Run:  python3 -m unittest discover tests -p "test_railways_air.py"
"""

from pkinv.assets import asset_path
import os
import unittest

from pkinv.sectors.railways import air_pollutants, traction
from pkinv.sectors.railways.data import RailwaysData
from _support import ROOT



def _rows(**kw):
    return air_pollutants.compute(RailwaysData(), **kw)


def _one(rows, fuel, pollutant, category=air_pollutants.CATEGORY):
    """One row per (category, fuel, pollutant): since the air spatial Wave A traction
    split each fuel can carry a traction AND a non-traction row, so the helper names
    which side it means - the mass-discipline rules hold on each side separately."""
    matches = [r for r in rows if r["fuel"] == fuel and r["pollutant"] == pollutant
               and r["category"] == category]
    assert len(matches) == 1, (category, fuel, pollutant, len(matches))
    return matches[0]


class TestFactorProvenance(unittest.TestCase):
    def test_every_factor_cites_the_chapter(self):
        data = RailwaysData()
        for pol in air_pollutants.FACTOR_POLLUTANTS:
            src = data.efs("railway_air", pol)
            self.assertIn("EMEP/EEA", src, pol)
            self.assertIn("1.A.3.c", src, pol)
        self.assertIn("1.A.3.c", data.efs("railway_air_frac", "BC_of_PM2.5"))

    def test_no_factor_value_is_hard_coded_in_the_module(self):
        """The constraint the whole EF register exists for: a factor edited in code is a
        factor the provenance system cannot see."""
        with open(air_pollutants.__file__, encoding="utf-8") as f:
            source = f.read()
        # The module docstring may narrate the source's values; the code may not carry them.
        source = source.replace(air_pollutants.__doc__, "")
        data = RailwaysData()
        centrals = [str(data.efv("railway_air", p))
                    for p in air_pollutants.FACTOR_POLLUTANTS]
        centrals.append(str(data.efv("railway_air_frac", "BC_of_PM2.5")))
        for value in centrals:
            self.assertNotIn(value, source, "factor %s appears as a literal" % value)

    def test_the_pm_ci_defect_is_recorded_not_repaired(self):
        """The chapter prints 95% CIs for TSP/PM10/PM2.5 that do not bracket their central
        values. The rows must say so and carry the conservative width, because a repaired
        source is a source nobody can check."""
        import csv
        with open(asset_path(ROOT, "data", "emission_factors.csv"), newline="",
                  encoding="utf-8") as f:
            rows = {r["ef_id"]: r for r in csv.DictReader(f)}
        for ef_id in ("rail_air_tsp", "rail_air_pm10", "rail_air_pm25"):
            self.assertEqual(float(rows[ef_id]["uncert_pct"]), 100.0, ef_id)
        self.assertIn("does not bracket", rows["rail_air_tsp"]["note"])


class TestSulfurStoichiometry(unittest.TestCase):
    def test_so2_is_two_times_the_sulfur_mass(self):
        # summed over the traction split: the stoichiometry is a property of the whole
        # fuel account, and the split moves mass between categories, never in total
        data = RailwaysData()
        tonnes = air_pollutants.fuel_tonnes(data)
        total = sum(r["emissions_kt"] for r in _rows()
                    if r["fuel"] == "Diesel" and r["pollutant"] == "SO2")
        s = data.p("diesel_sulfur_ppm_reference") / 1e6
        self.assertAlmostEqual(total, 2.0 * s * tonnes["Diesel"] / 1e3, places=12)

    def test_the_traction_split_conserves_every_pollutant(self):
        """Air spatial Wave A: the split is a regrouping. Per (fuel, pollutant), the
        traction and non-traction rows sum to the whole-account mass, and in a year
        whose detail table reports NIL locomotive furnace oil the traction side is
        ABSENT, not zero - that absence is what keeps 54 historical atoms off a
        stream the greenhouse-gas panel marks not_present."""
        data = RailwaysData()
        rows16 = air_pollutants.compute(data, 2016)
        self.assertEqual([r for r in rows16
                          if r["fuel"] == "Furnace oil"
                          and r["category"] == air_pollutants.CATEGORY], [])
        self.assertTrue([r for r in rows16
                         if r["fuel"] == "Furnace oil"
                         and r["category"] == air_pollutants.NON_TRACTION_CATEGORY])
        loco = traction.locomotive_fraction(data, "Diesel", 2024)
        t_row = _one(_rows(), "Diesel", "NOx")
        n_row = _one(_rows(), "Diesel", "NOx",
                     category=air_pollutants.NON_TRACTION_CATEGORY)
        self.assertAlmostEqual(t_row["emissions_kt"] / (t_row["emissions_kt"]
                               + n_row["emissions_kt"]), loco, places=9)

    def test_the_sulfur_ladder_is_monotone(self):
        cases = air_pollutants.sulfur_cases(RailwaysData())
        ppms = [ppm for _c, ppm, _kt in cases]
        so2 = [kt for _c, _p, kt in cases]
        self.assertEqual(ppms, sorted(ppms))
        self.assertEqual(so2, sorted(so2))
        self.assertEqual([c for c, _p, _k in cases][0], "euro5_import_spec")

    def test_the_reference_case_is_what_the_main_output_reports(self):
        row = _one(_rows(), "Diesel", "SO2")
        self.assertEqual(row["sulfur_case"], air_pollutants.REFERENCE_CASE)

    def test_the_span_is_the_message(self):
        """10 ppm to 10,000 ppm of the same fuel: the top of the ladder must be about 290
        times the bottom (the furnace-oil floor keeps it just under 1000x), because if it
        is not, someone has averaged the cases - the one treatment the docstring forbids."""
        cases = dict((c, kt) for c, _p, kt in air_pollutants.sulfur_cases(RailwaysData()))
        ratio = cases["historical_1.0pct"] / cases["euro5_import_spec"]
        self.assertGreater(ratio, 250)
        self.assertLess(ratio, 1000)


class TestMassDiscipline(unittest.TestCase):
    def test_bc_is_a_fraction_of_pm25(self):
        data = RailwaysData()
        rows = _rows()
        for fuel in ("Diesel", "Furnace oil"):
            bc = _one(rows, fuel, "BC")["emissions_kt"]
            pm = _one(rows, fuel, "PM2.5")["emissions_kt"]
            self.assertEqual(bc, pm * data.efv("railway_air_frac", "BC_of_PM2.5"))
            self.assertLess(bc, pm)

    def test_pm_nests(self):
        rows = _rows()
        for fuel in ("Diesel", "Furnace oil"):
            pm25 = _one(rows, fuel, "PM2.5")["emissions_kt"]
            pm10 = _one(rows, fuel, "PM10")["emissions_kt"]
            tsp = _one(rows, fuel, "TSP")["emissions_kt"]
            self.assertLess(pm25, pm10)
            self.assertLess(pm10, tsp)

    def test_mass_only_never_co2e(self):
        for r in _rows():
            self.assertNotIn("co2e_Mt_AR5", r)
            self.assertNotIn("co2e", " ".join(r.keys()))


class TestSameActivityAsGHG(unittest.TestCase):
    def test_fuel_mass_matches_the_activity_file_exactly(self):
        data = RailwaysData()
        tonnes = air_pollutants.fuel_tonnes(data)
        self.assertEqual(tonnes["Diesel"],
                         data.quantity("Gas/Diesel Oil") * 1000.0
                         * data.p("hsd_density_kg_per_l") / 1000.0)
        self.assertEqual(tonnes["Furnace oil"], data.quantity("Residual Fuel Oil"))

    def test_energy_agrees_with_the_greenhouse_gas_layer(self):
        """Same combustion, both layers: tonnes x NCV must reproduce traction's TJ."""
        data = RailwaysData()
        tonnes = air_pollutants.fuel_tonnes(data)
        tj = traction.fuel_TJ(data)
        for (stream, item, _d, _u) in traction.FUELS:
            self.assertAlmostEqual(
                tonnes[stream] / 1000.0 * data.efv("railway_ncv", item),
                tj[stream], places=9, msg=stream)


class TestWearPM(unittest.TestCase):
    """The exploratory wear layer: alongside the exhaust inventory, never inside it."""

    @classmethod
    def setUpClass(cls):
        from pkinv.sectors.railways import wear_pm
        cls.wear_pm = wear_pm
        cls.rows = wear_pm.compute(RailwaysData())

    def test_every_row_is_labelled_exploratory(self):
        for r in self.rows:
            self.assertIn("EXPLORATORY", r["label"])
            self.assertIn("never added", r["label"])

    def test_wear_mass_nests(self):
        kt = {r["pollutant"]: r["emissions_kt"] for r in self.rows}
        self.assertLess(kt["PM2.5"], kt["PM10"])
        self.assertLess(kt["PM10"], kt["TSP"])

    def test_wear_stays_out_of_the_exhaust_output(self):
        """The one treatment the layer forbids: summation. The exhaust CSV must carry
        exactly the EMEP Tier 1 masses, unmoved by the wear module's existence."""
        import csv as _csv
        path = os.path.join(ROOT, "outputs", "railways_air_pollutants_2024.csv")
        exhaust = {}
        with open(path, newline="", encoding="utf-8") as f:
            for r in _csv.DictReader(f):
                key = (r["fuel"], r["pollutant"])
                exhaust[key] = exhaust.get(key, 0.0) + float(r["emissions_kt"])
        data = RailwaysData()
        expected = (data.quantity("Gas/Diesel Oil") * 1000.0
                    * data.p("hsd_density_kg_per_l") / 1000.0
                    * data.efv("railway_air", "PM10") / 1e6)
        self.assertAlmostEqual(exhaust[("Diesel", "PM10")], expected, places=5)

    def test_wear_is_a_minor_companion_not_a_rival(self):
        kt = {r["pollutant"]: r["emissions_kt"] for r in self.rows}
        self.assertTrue(0.02 < kt["PM10"] / 0.1614 < 0.5, kt["PM10"])

    def test_the_source_inconsistency_is_recorded(self):
        frac_row = next(r for r in self.rows if r["pollutant"] == "PM2.5")
        data = RailwaysData()
        note_holder = data.efs("railway_wear_frac", "PM2.5_of_PM10")
        self.assertIn("25%", note_holder)


class TestOutputContract(unittest.TestCase):
    def test_the_figures_contract_columns_exist(self):
        import csv
        path = os.path.join(ROOT, "outputs", "railways_air_pollutants_2024.csv")
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        self.assertTrue(rows)
        for col in ("pollutant", "emissions_kt"):
            self.assertIn(col, rows[0])
        # Only the reference sulfur case may appear here: figures.sector_air sums rows by
        # pollutant, so a second case in this file would double-count SO2 on the chart.
        cases = {r["sulfur_case"] for r in rows if r["pollutant"] == "SO2"}
        self.assertEqual(cases, {air_pollutants.REFERENCE_CASE})

    def test_the_layer_is_registered_for_figures(self):
        figures_py = os.path.join(ROOT, "src", "pkinv", "report", "figures.py")
        with open(figures_py, encoding="utf-8") as f:
            self.assertIn("railways_air_pollutants_2024.csv", f.read())


if __name__ == "__main__":
    unittest.main()
