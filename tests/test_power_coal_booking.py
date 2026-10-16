"""Current final coal booking must follow station source records and bounds."""
import unittest

from pkinv.core.io import read_rows
from pkinv.sectors.power import coal_booking, coal_configurations
from pkinv.assets import asset_path
from pkinv.paths import DATA


class CurrentCoalBooking(unittest.TestCase):
    def test_final_export_matches_current_station_reconstruction(self):
        exported = {int(r["fiscal_year"]): r for r in read_rows(coal_booking.OUT, comments=True)}
        configs = coal_configurations.build()
        for r in configs:
            if r["configuration_id"] != "C1_stations_rank_default":
                continue
            booked = exported[int(r["fiscal_start_year"])]
            lo, hi = float(r["coal_energy_lo_TJ"]), float(r["coal_energy_hi_TJ"])
            # The diagnostic prints whole TJ; the booking retains 0.1 toe.
            self.assertAlmostEqual(float(booked["booked_lo_toe"]) * coal_booking.TOE_TJ, lo, delta=.5021)
            self.assertAlmostEqual(float(booked["booked_hi_toe"]) * coal_booking.TOE_TJ, hi, delta=.5021)
            self.assertAlmostEqual(float(booked["booked_toe"]) * coal_booking.TOE_TJ, (lo + hi) / 2, delta=.5021)

    def test_reconstruction_bound_is_not_a_confidence_interval(self):
        for r in read_rows(coal_booking.OUT, comments=True):
            if r["evidence_grade"] == "reconstructed_interval":
                self.assertLess(float(r["booked_lo_toe"]), float(r["booked_hi_toe"]))
                self.assertIn("conditional bounds", r["note"])
                self.assertIn("not a 95% interval", r["note"])

    def test_reference_export_matches_independently_transcribed_station_mass(self):
        # The held NEPRA physical table is independent of both generated account
        # tables. Include actual commissioning/testing consumption.
        source = read_rows(asset_path(DATA, "activity", "power", "plant_fuel_2024_25.csv"), comments=True)
        expected = sum(float(r["quantity"]) * (11.9 if r["fuel_origin"] == "Thar lignite"
                       or r["plant"] == "Lucky Electric" else 25.8)
                       for r in source if r["fuel"] == "Coal" and r["system"] != "K-Electric")
        exported = next(r for r in read_rows(coal_booking.OUT, comments=True)
                        if r["fiscal_year"] == "2024")
        self.assertAlmostEqual(float(exported["booked_toe"]) * coal_booking.TOE_TJ,
                               expected, delta=.0021)

    def test_latest_export_does_not_invent_a_superseded_control(self):
        from pkinv.core.reporting_window import CORE_FY_STARTS
        latest = next(r for r in read_rows(coal_booking.OUT, comments=True)
                      if int(r["fiscal_year"]) == max(CORE_FY_STARTS))
        self.assertEqual(latest["superseded_toe"], "")
        self.assertEqual(latest["ratio_to_superseded"], "")
        self.assertIn("no Table 3", latest["superseded_source"])
        historical = next(r for r in read_rows(coal_booking.OUT, comments=True)
                          if int(r["fiscal_year"]) == max(CORE_FY_STARTS) - 1)
        self.assertGreater(float(historical["superseded_toe"]), 0)
        self.assertGreater(float(historical["ratio_to_superseded"]), 0)

    def test_pre_thar_lakhra_keeps_its_actual_origin_and_rank_default(self):
        source = [r for r in coal_booking.station_accounts() if r["period_id"] == "FY2015-16"]
        self.assertEqual(len(source), 1)
        self.assertIn("Lakhra", source[0]["plant"])
        self.assertEqual(source[0]["fuel_rank"], "Lakhra coal (lignite default)")
        self.assertEqual(float(source[0]["ncv_TJ_per_Gg"]), 11.9)
        self.assertAlmostEqual(float(source[0]["mass_kt"]), 152.22)

    def test_final_factor_register_names_the_actual_rank_heat_inputs(self):
        from pkinv.paths import OUTPUTS
        rows = read_rows(asset_path(OUTPUTS, "power_uncertainty_inputs_fy2023_24.csv"))
        by = {r["variable"]: r for r in rows}
        self.assertNotIn("Coal TOE row", by)
        mass = by["Coal station consumption mass"]
        source = [r for r in coal_booking.station_accounts() if r["period_id"] == "FY2023-24"]
        self.assertAlmostEqual(float(mass["central_value"]), sum(float(r["mass_kt"]) for r in source), places=5)
        self.assertEqual(mass["correlation_group"], "activity:coal:power_station_mass")
        share = by["Lignite heat share of coal"]
        self.assertEqual(share["distribution"], "derived; not independently sampled")
        self.assertEqual(share["uncert_pct_95"], "")
        for rank in ("Lignite", "Other Bituminous Coal"):
            self.assertEqual(by["Coal rank NCV: " + rank]["correlation_group"], "factor:ncv:" + rank)

    def test_rank_factors_are_weighted_by_fuel_heat(self):
        from pkinv.sectors.power.data import PowerData
        from pkinv.sectors.power import combustion
        data = PowerData()
        for year, rows in data.coal_rank_account.items():
            expected = sum(float(r["energy_TJ"]) * data.efv("power_combustion_co2", r["fuel_rank"])
                           / 1e6 for r in rows)
            energy = sum(float(r["energy_TJ"]) for r in rows)
            actual = energy * combustion.coal_co2_factor(data, year=year) / 1e6
            self.assertAlmostEqual(actual, expected, places=7)


if __name__ == "__main__":
    unittest.main()
