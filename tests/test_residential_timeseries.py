"""The residential time series and the synthetic monthly layer.

The strongest pin: the reference year in the series IS the engine, byte-identical -
the one place a time series can silently disagree with the reported sector is at its
own reference year, and that disagreement is forbidden by construction and by test.

Run:  python3 -m unittest discover tests -p "test_residential_timeseries.py"
"""

from pkinv.assets import asset_path
import csv
import os
import unittest
from pkinv.core.reporting_window import CORE_FY_STARTS, CORE_FY_ENDS, CORE_PERIOD_IDS, REFERENCE_PERIOD
from pkinv.core.configurations import REFERENCE

from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.residential import combustion, engine, hies, monthly, timeseries
from pkinv.sectors.residential.data import ResidentialData


class TestSeries(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.series = timeseries.fuel_TJ_series(cls.data)

    def test_the_reference_year_is_the_engine(self):
        ref = combustion.fuel_TJ(self.data)
        year = self.series[self.data.year]
        for stream, tj in ref.items():
            self.assertEqual(year[stream], tj, stream)
        total = sum(c["co2e_Mt_AR5"] for c in engine.build_components(self.data))
        self.assertAlmostEqual(timeseries.co2e_Mt(self.data, year), total, places=6)

    def test_the_interpolated_gas_year_is_labelled_and_bracketed(self):
        gas = timeseries.gas_mmcfd()
        self.assertAlmostEqual(gas[2021], (gas[2020] + gas[2022]) / 2.0, places=6)
        rows = [r for r in csv.DictReader(open(asset_path(DATA, "activity", "residential", "fuel_supply_history.csv")))
            if r["fuel"] == "Natural Gas"]
        basis = {int(r["fiscal_year"]): r["basis"] for r in rows}
        self.assertEqual(basis[2021], "interpolated")
        self.assertTrue(all(b == "reported" for y, b in basis.items() if y != 2021))

    def test_firewood_reproduces_the_survey_at_its_own_anchor(self):
        """At the 2018-19 round's year, the series must return exactly the round's
        design-weighted total - the anchor is the measurement, not a fit through it."""
        self.assertAlmostEqual(timeseries.firewood_air_dry_kg(2019),
                               hies.firewood_air_dry_kg("hies2019"), places=3)

    def test_scales_are_unity_at_the_reference_year(self):
        self.assertAlmostEqual(timeseries.herd_scale(self.data.year), 1.0, places=9)
        self.assertAlmostEqual(timeseries.residue_scale(self.data.year), 1.0,
                               places=9)

    def test_held_streams_say_so(self):
        for y, tj in self.series.items():
            if y == self.data.year:
                continue
            for stream in ("LPG", "Kerosene", "Coal", "Charcoal", "Generators"):
                self.assertIn("HELD", tj["_basis"][stream], "%s %s" % (y, stream))

    def test_the_series_starts_where_the_gas_archive_starts(self):
        """A sector series longer than its largest CO2 stream's source would mislead;
        the module docstring commits to this boundary and the years enforce it."""
        self.assertEqual(min(timeseries.YEARS), 2016)
        self.assertEqual(tuple(timeseries.YEARS), CORE_FY_ENDS)
        self.assertEqual(set(timeseries.gas_mmcfd()), set(CORE_FY_ENDS))

    def test_matched_cy_is_the_straddle_mean(self):
        m = timeseries.matched_cy(2022, self.data, self.series)
        own = [timeseries.co2e_Mt(self.data, self.series[y]) for y in (2022, 2023)]
        self.assertAlmostEqual(m["co2e_Mt_AR5"], sum(own) / 2.0, places=9)
        self.assertIn("FY2021-22", m["fiscal_years"])


class TestTheDungSeries(unittest.TestCase):
    """rc67 (2026-10-13): the dung stream of the reference series is the household
    survey's in all nine years. Through rc66 the reference series scaled the nitrogen
    ledger by the herd and the survey series existed only as the air panel's second
    configuration; the two exchanged places, and the ledger series is the alternative
    (fuel_TJ_series(dung_basis="ledger"), configuration L_HERD1624 in the air panel)."""

    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.series = timeseries.fuel_TJ_series(cls.data)
        cls.ledger = timeseries.fuel_TJ_series(cls.data, dung_basis="ledger")
        path = os.path.join(OUTPUTS, "residential_configurations_by_year.csv")
        with open(path, newline="", encoding="utf-8") as f:
            cls.shipped = {(int(r["fiscal_end_year"]), r["configuration_id"]): r
                           for r in csv.DictReader(f)}

    def test_dung_reproduces_the_survey_at_both_anchors(self):
        """Firewood's construction, held the same way: at each round's year the series
        returns the round's design-weighted total (6.504 and 11.967 Mt)."""
        self.assertAlmostEqual(timeseries.dung_survey_air_dry_kg(2019),
                               hies.national_quantity("dung_cake", "hies2019")[0],
                               places=3)
        self.assertAlmostEqual(timeseries.dung_survey_air_dry_kg(2025),
                               hies.national_quantity("dung_cake", "hies2025")[0],
                               places=3)
        self.assertAlmostEqual(timeseries.dung_survey_air_dry_kg(2019) / 1e9, 6.504,
                               places=3)
        self.assertAlmostEqual(timeseries.dung_survey_air_dry_kg(2025) / 1e9, 11.967,
                               places=3)

    def test_the_reference_year_is_interpolated_not_the_later_round(self):
        """FY2023-24 lies between the rounds: 10.933 Mt, below the 2024-25 round's own
        11.967. One construction for every year of the panel."""
        kg = timeseries.dung_survey_air_dry_kg(self.data.year)
        self.assertAlmostEqual(kg / 1e9, 10.933, places=3)
        self.assertLess(kg, hies.national_quantity("dung_cake", "hies2025")[0])
        self.assertEqual(combustion.dung_air_dry_kg(self.data), kg)
        self.assertEqual(timeseries.dung_survey_basis(self.data.year),
                         "survey_anchored_interpolation")

    def test_the_rate_is_held_flat_before_the_first_round(self):
        rates = {y: timeseries.dung_survey_air_dry_kg(y) / timeseries.households(y)
                 for y in timeseries.YEARS}
        for y in (2016, 2017, 2018):
            self.assertAlmostEqual(rates[y], rates[2019], places=9)
            self.assertEqual(timeseries.dung_survey_basis(y),
                             "survey_anchored_extrapolated_flat")
        for y in range(2020, 2025):
            self.assertGreater(rates[y], rates[y - 1])
            self.assertEqual(timeseries.dung_survey_basis(y),
                             "survey_anchored_interpolation")

    def test_the_reference_series_burns_the_survey_and_the_ledger_series_the_herd(self):
        ref_tj = combustion.fuel_TJ(self.data)["Dung cake"]
        led_tj = combustion.fuel_TJ(self.data, dung_basis="ledger")["Dung cake"]
        self.assertEqual(self.ledger[self.data.year]["Dung cake"], led_tj)
        for y in timeseries.YEARS:
            self.assertAlmostEqual(
                self.series[y]["Dung cake"],
                ref_tj * timeseries.dung_survey_air_dry_kg(y)
                / timeseries.dung_survey_air_dry_kg(self.data.year), places=6, msg=y)
            self.assertAlmostEqual(self.ledger[y]["Dung cake"],
                                   led_tj * timeseries.herd_scale(y), places=6, msg=y)
            self.assertGreater(self.ledger[y]["Dung cake"],
                               4 * self.series[y]["Dung cake"], y)
            # nothing but dung differs between the two series
            for stream, tj in self.series[y].items():
                if stream not in ("Dung cake", "_basis"):
                    self.assertEqual(self.ledger[y][stream], tj, (y, stream))
        self.assertIn("HIES", self.series[2016]["_basis"]["Dung cake"])
        self.assertIn("herd-scaled nitrogen ledger",
                      self.ledger[2016]["_basis"]["Dung cake"])

    def test_an_unnamed_basis_is_refused(self):
        with self.assertRaises(ValueError):
            timeseries.fuel_TJ_series(self.data, dung_basis="hies")

    def test_the_shipped_configurations_by_year_carry_the_new_roles(self):
        """residential_configurations_by_year.csv: REF_2023_24 is the survey series and
        L_HERD1624 the herd-scaled ledger, every year, with the retired S_HIES1925 gone.
        Both configurations burn the same cake, so the dung PM2.5 per tonne is one number
        across all eighteen rows. Through rc66 it was not: the survey rows carried the
        2024-25 round's 11.97 Mt in their PM2.5 beside a mass column that said 10.93
        (87.41 kt where 79.86 belongs)."""
        self.assertEqual({cfg for _y, cfg in self.shipped}, {"S_TAN", "L_TAN"})
        self.assertEqual(len(self.shipped), 2 * len(timeseries.YEARS))
        led_kg = combustion.dung_air_dry_kg(self.data, basis="ledger")
        per_tonne = set()
        for y in timeseries.YEARS:
            ref, led = self.shipped[(y, "S_TAN")], self.shipped[(y, "L_TAN")]
            self.assertEqual(ref["dung_activity_basis"], timeseries.dung_survey_basis(y))
            self.assertEqual(led["dung_activity_basis"], "herd_scaled_nitrogen_ledger")
            self.assertAlmostEqual(float(ref["dung_air_dry_Mt"]),
                                   timeseries.dung_survey_air_dry_kg(y) / 1e9, places=4)
            self.assertAlmostEqual(float(led["dung_air_dry_Mt"]),
                                   led_kg * timeseries.herd_scale(y) / 1e9, places=4)
            self.assertGreater(float(led["dung_pm25_kt"]), float(ref["dung_pm25_kt"]))
            for row in (ref, led):
                per_tonne.add(round(float(row["dung_pm25_kt"])
                                    / float(row["dung_air_dry_Mt"]), 2))
        self.assertEqual(per_tonne, {7.3})
        factor_per_airdry_tonne = (self.data.efv("residential_biofuel", "Gef_PM25_Dung")
                                  * (1 - self.data.p("dung_cake_moisture_ar")))
        self.assertAlmostEqual(float(self.shipped[(2024, "S_TAN")]["dung_pm25_kt"]),
                               timeseries.dung_survey_air_dry_kg(2024) / 1e9 * factor_per_airdry_tonne,
                               places=3)
        self.assertAlmostEqual(float(self.shipped[(2024, "L_TAN")]["dung_pm25_kt"]),
                               led_kg / 1e9 * factor_per_airdry_tonne, places=3)


class TestMonthly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = ResidentialData()
        cls.rows = monthly.monthly_rows(cls.data)

    def test_annual_closure_is_exact(self):
        monthly.check(self.rows, self.data)   # raises on failure

    def test_every_row_is_labelled_synthetic(self):
        for r in self.rows:
            self.assertIn(monthly.LABEL, r["basis"])

    def test_gas_peaks_in_winter(self):
        def share(stream, months):
            return sum(r["share"] for r in self.rows
                       if r["stream"] == stream and r["month"][4:] in months)
        winter = ("12", "01", "02")
        summer = ("06", "07", "08")
        self.assertGreater(share("Natural gas", winter),
                           1.5 * share("Natural gas", summer))

    def test_generators_peak_in_summer(self):
        """The one stream whose season inverts: gensets run against load-shedding,
        which peaks with cooling demand, not cold."""
        def share(stream, months):
            return sum(r["share"] for r in self.rows
                       if r["stream"] == stream and r["month"][4:] in months)
        self.assertGreater(share("Generators", ("06", "07", "08")),
                           3 * share("Generators", ("12", "01", "02")))

    def test_the_winter_pm_signal_exists(self):
        jan = sum(r["pm25_kt"] for r in self.rows if r["month"] == "202401")
        jun = sum(r["pm25_kt"] for r in self.rows if r["month"] == "202406")
        self.assertGreater(jan, 2 * jun)

    def test_the_degree_days_are_sourced(self):
        """Ten core fiscal years plus the precursor weather year.

        This asserted 60 rows - five provinces of the reference year - which was right
        while the residential layer had one year to profile. Every other year would have
        had to wear FY2023-24's winter, and winters are precisely what differs: Lahore's
        heating demand runs 179 to 482 HDD across these years.
        """
        path = asset_path(DATA, "activity", "residential", "monthly_degree_days.csv")
        rows = list(csv.DictReader(open(path)))
        months = sorted({r["month"] for r in rows})
        self.assertEqual(len(months), 132)       # July2014 through June2025
        self.assertEqual(months[0], "201407")
        self.assertEqual(months[-1], "202506")
        self.assertEqual(len(rows), 5 * len(months))
        for r in rows:
            self.assertIn("NASA POWER", r["source"])

    def test_every_fiscal_year_has_its_own_winter(self):
        """The point of holding ten years: the shapes must actually differ. Two years
        whose January share matched to four decimals would mean the reader had been given
        one year's weather under nine labels."""
        from pkinv.sectors.residential import monthly as res_monthly
        january = {}
        for fy_start in range(2015, 2024):
            hdd, _cdd = res_monthly.degree_day_shapes(fy_start=fy_start)
            january[fy_start] = round(hdd["%d01" % (fy_start + 1)], 4)
        self.assertEqual(len(set(january.values())), len(january), january)


if __name__ == "__main__":
    unittest.main()
