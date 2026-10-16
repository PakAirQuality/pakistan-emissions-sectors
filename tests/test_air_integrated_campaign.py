"""Regressions for actual air release defects and physical allocation boundaries."""
import collections
import json
import csv
import os
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import numpy as np

from pkinv.core import configurations as conf
from pkinv.report import air_monthly, air_uncertainty
from pkinv.report.air_records import fraction_driver


class AirConfigurationComposition(unittest.TestCase):
    def test_nested_species_are_checked_at_matching_source_boundaries(self):
        from pkinv.report.air_annual import check_species_containment
        base = dict(period_id="FY2023-24", configuration_id=conf.REFERENCE,
                    sector_id="transport", source_class_id="car", process="exhaust")
        rows = [dict(base, pollutant=p, emissions_Gg=v) for p, v in (("PM2.5", 1), ("BC", .7), ("OC", .2))]
        check_species_containment(rows)
        rows[-1]["emissions_Gg"] = .4
        with self.assertRaisesRegex(ValueError, "BC\\+OC"):
            check_species_containment(rows)
        rows[-1]["process"] = "unrelated_process"
        check_species_containment(rows)

    def test_both_axes_compose_without_dropping_shared_sectors(self):
        rows = [dict(core7="yes", sector_id=sector, configuration_id=cfg,
                     emissions_Gg=value, pollutant="NH3")
                for sector, cfg, value in (("agriculture", conf.REFERENCE, 3),
                                            ("agriculture", conf.IPCC_REFERENCE, 5),
                                            ("residential", conf.REFERENCE, 7),
                                            ("residential", conf.LEDGER, 11),
                                            ("industry", conf.REFERENCE, 13))]
        got = collections.defaultdict(float)
        for r in air_uncertainty.composed_atoms(rows):
            got[r["configuration_id"]] += r["emissions_Gg"]
        self.assertEqual(dict(got), {conf.REFERENCE: 23, conf.LEDGER: 27,
                                      conf.IPCC_REFERENCE: 25, conf.IPCC_LEDGER: 29})

    def test_filenames_identify_configuration_and_current_window(self):
        from pkinv.report.air_annual_grid import path_for
        from pkinv.core.reporting_window import CORE_SUFFIX
        names = [path_for(cfg) for cfg in conf.AIR_ALL]
        self.assertEqual(len(set(names)), 4)
        for cfg, name in zip(conf.AIR_ALL, names):
            self.assertIn(cfg.lower(), name)
            self.assertIn(CORE_SUFFIX, name)


class ProcessTiming(unittest.TestCase):
    def atom(self, **updates):
        row = dict(period_id="FY2023-24", configuration_id=conf.REFERENCE,
                   sector_id="transport", source_class_id="road:car", subitem="car",
                   support_anchor_id="road-fuel", process="exhaust", pollutant="PM2.5",
                   emissions_Gg="12.5", core7="yes", maturity="estimated")
        row.update(updates)
        return row

    def test_evaporation_and_wear_do_not_inherit_exhaust_fuel_peaks(self):
        months = air_monthly.monthly.months_for(2023)
        profile = {m: dict(share=1.0 if i == 0 else 0.0, temporal_evidence_class="TE1",
                           profile_id="fuel-sales", timing_target="fuel-combustion", source_id="OCAC")
                   for i, m in enumerate(months)}
        profiles = {("FY2023-24", "road-fuel"): profile}
        self.assertEqual(air_monthly.profile_for(self.atom(), profiles)[months[0]][0], 1)
        for process in ("evaporative", "tyre_brake_wear", "road_wear"):
            got = air_monthly.profile_for(self.atom(process=process), profiles)
            self.assertAlmostEqual(sum(r[0] for r in got.values()), 1)
            self.assertTrue(all(r[1] == "TE4" for r in got.values()))
            self.assertLess(max(r[0] for r in got.values()), 0.09)

    def test_manure_housing_is_not_fertiliser_application(self):
        row = self.atom(sector_id="agriculture", subitem="NH3 - housing (buffalo)")
        got = air_monthly.profile_for(row, {})
        self.assertEqual({r[1] for r in got.values()}, {"TE4"})
        self.assertTrue(all("management" in r[3] for r in got.values()))

    def test_months_close_each_configuration_and_pollutant(self):
        records, support = air_monthly.build([self.atom()], {})
        total = collections.defaultdict(float)
        for r in records:
            total[r["configuration_id"], r["pollutant"]] += r["emissions_Gg"]
        self.assertEqual(set(k[0] for k in total), set(conf.AIR_ALL))
        for mass in total.values():
            self.assertAlmostEqual(mass, 12.5)
        self.assertTrue(all(abs(r["mass_share"] - 1) < 1e-12 for r in support))


class PhysicalConditionalDraws(unittest.TestCase):
    def test_fertiliser_record_names_the_factor_actually_sampled(self):
        from pkinv.report import air_records
        from pkinv.sectors.agriculture import air_pollutants as agriculture
        from pkinv.sectors.agriculture.fiscal_activity import data_for_fiscal_year
        data = data_for_fiscal_year(2024)
        row = next(row for row in agriculture.compute(data)
                   if row["subitem"].startswith("NH3 - synthetic fertiliser (Urea)"))
        record = air_records.enrich("agriculture", 2024, row)
        declared = {entry["id"] for entry in json.loads(record["parameter_drivers"])
                    if entry["id"].startswith("factor:fert_nh3_highpH:")}
        draws = air_uncertainty.Draws(n=2)
        air_uncertainty.nitrogen_realisations(2024, draws)
        sampled = {identity for identity in draws.registry
                   if identity.startswith("factor:fert_nh3_highpH:")}
        self.assertEqual(declared, sampled)
        self.assertEqual(declared, {"factor:fert_nh3_highpH:shared_table"})

    def test_gas_combustion_reuses_the_native_post_meter_leak_draw(self):
        from pkinv.sectors.fugitives import post_meter
        leak = post_meter.whole_gas_leak_share()
        multiplier = np.array([0., 1., 2., 3.])
        atom = dict(core7="yes", sector_id="industry", configuration_id=conf.REFERENCE,
                    emissions_Gg="10", pollutant="NOx", period_id="FY2023-24",
                    source_class_id="test:gas-combustion", nitrogen_recipe="",
                    uncertainty_model="shared_net_gas_combustion", parameter_drivers="[]")
        expected = 10 * (1 - leak * multiplier) / (1 - leak)
        with patch.object(air_uncertainty, "fugitives_realisations",
                          return_value={"post_meter_factor_multiplier": multiplier}) as native:
            levels = air_uncertainty.build([atom], n=4,
                       dependence_cases=("persistent_parameters",))[0]
        native.assert_called_once()
        for row in levels:
            self.assertAlmostEqual(row["mean_Gg"], expected.mean())
            self.assertAlmostEqual(row["P2_5_Gg"], np.quantile(expected, .025))
            self.assertAlmostEqual(row["P97_5_Gg"], np.quantile(expected, .975))

    def test_bc_fraction_and_retention_stay_physical_in_wide_draws(self):
        draws = air_uncertainty.Draws(n=5000)
        bc = draws.multiplier(fraction_driver("test:BC", 0.7, 100), 2024) * 0.7
        emitted = draws.multiplier(fraction_driver("test:retention", 0.6, 100, complement=True), 2024) * 0.4
        self.assertTrue(np.all((bc >= 0) & (bc <= 1)))
        self.assertTrue(np.all((emitted >= 0) & (emitted <= 1)))

    def test_parameter_identity_replays_shared_species_and_paired_years(self):
        draws = air_uncertainty.Draws(n=1000)
        entry = dict(id="activity:coal:brick_kilns", kind="activity", uncert_pct=30)
        self.assertTrue(np.array_equal(draws.multiplier(entry, 2020), draws.multiplier(entry, 2024)))
        independent = air_uncertainty.Draws(n=1000, dependence="annual_activity_errors")
        self.assertFalse(np.array_equal(independent.multiplier(entry, 2020), independent.multiplier(entry, 2024)))

    def test_unknown_nitrogen_recipe_fails_instead_of_becoming_zero(self):
        atom = dict(core7="yes", sector_id="agriculture", configuration_id=conf.REFERENCE,
                    emissions_Gg="1", pollutant="NH3", period_id="FY2023-24",
                    source_class_id="test:missing-pool", nitrogen_recipe=json.dumps({"pool": "missing"}),
                    parameter_drivers="[]")
        with patch.object(air_uncertainty, "nitrogen_realisations", return_value=({}, 0)):
            with self.assertRaisesRegex(ValueError, "unknown nitrogen"):
                air_uncertainty.build([atom], n=10, dependence_cases=("persistent_parameters",))


class ExportedPowerActivity(unittest.TestCase):
    def test_admitted_power_coordinates_cannot_bypass_primary_licensing(self):
        from pkinv.report import power_admission_vectors as vectors
        rows = [dict(name="plant", module="power", longitude="70", latitude="30",
                     licence="ODbL-1.0", coordinate_source="OpenStreetMap"),
                dict(name="plant", module="power", longitude="71", latitude="31",
                     licence="CC-BY-4.0", coordinate_source="GEM"),
                dict(name="excluded", module="power", longitude="72", latitude="32",
                     licence="", coordinate_source="OSM polygon")]
        with patch.object(vectors, "read_rows", return_value=rows):
            self.assertEqual(vectors.held_points(), {"plant": (71., 31.)})

    def test_fy2025_station_consumption_reaches_final_admission_panel(self):
        from pkinv.paths import ROOT
        from pkinv.core.io import read_rows
        sources = read_rows(os.path.join(ROOT, "data/sectors/power/activity/plant_fuel_2024_25.csv"))
        exported = read_rows(os.path.join(ROOT, "data/sectors/power/activity/power_so2_admission.csv"))
        panel = {(r["plant"], r["fuel"]): r for r in exported if r["period_id"] == "FY2024-25"}
        for source in sources:
            if source["fuel"] not in ("RFO", "HSD"):
                continue
            key = (source["plant"], source["fuel"])
            self.assertIn(key, panel, "source station was lost from exported admission")
            row = panel[key]
            expected = float(source["quantity"])
            if source["quantity_unit"] == "000 L":
                expected *= .84 / 1000  # independently applied kg/L -> kt
            self.assertAlmostEqual(float(row["fuel_mass_kt"]), expected, delta=.000051)
            if source["system"] == "K-Electric":
                self.assertEqual(row["disposition"], "scenario_only")
                self.assertEqual(row["so2_Gg"], "")
        kapco = panel["KAPCO", "HSD"]
        self.assertEqual(float(kapco["generation_gwh"]), 0)
        self.assertGreater(float(kapco["fuel_mass_kt"]), 0)


class BurnedGasActivity(unittest.TestCase):
    def test_industrial_and_captive_classes_use_burned_not_delivered_gas(self):
        from pkinv.sectors.industry import air_pollutants as ind, combustion
        from pkinv.sectors.power import captive
        from pkinv.sectors.fugitives import post_meter
        ctx = ind.Context()
        classes = [row for row in ind.classes() if row["status"] == "estimate"
                   and (row["activity_function"].startswith("industry.gas_TJ:")
                        or row["activity_function"] == "power.captive_gas_TJ")]
        self.assertGreater(len(classes), 3)
        for year in ind.YEARS:
            for row in classes:
                share, _ = ind.share_of(row, ctx)
                fn = row["activity_function"]
                if fn.startswith("industry.gas_TJ:"):
                    delivered = combustion.gas_TJ(ctx.data, fn.split(":", 1)[1], year)
                else:
                    delivered = captive.gas_TJ(ctx.power, year=year)
                got = ind.activity(row, year, ctx)
                if delivered == 0:
                    self.assertIsNone(got)
                    continue
                self.assertAlmostEqual(got["value"],
                    delivered * share * post_meter.combusted_fraction(), places=8)
                self.assertLess(got["value"], delivered * share)


class NativeAirGrid(unittest.TestCase):
    def test_each_configuration_writes_its_actual_period_and_native_mass(self):
        from netCDF4 import Dataset
        from pkinv.report.air_annual_grid import AirAnnualGridWriter
        def frame(ds, grid, periods):
            ds.createDimension("time", len(periods))
            ds.createDimension("lat", grid.height)
            ds.createDimension("lon", grid.width)
        grid = SimpleNamespace(height=2, width=2, province_id=np.array([[0, 0], [0, -1]]))
        periods = [("FY2024-25", 0, 365, 182.5)]
        with tempfile.TemporaryDirectory() as directory, \
                patch("pkinv.report.annual_grid.write_frame", side_effect=frame), \
                patch("pkinv.report.air_annual_grid.covered_sectors", return_value={"transport": ["NOx"]}):
            for cfg in conf.AIR_ALL:
                path = os.path.join(directory, cfg + ".nc")
                with AirAnnualGridWriter(path, grid, periods, cfg) as writer:
                    writer.write_period("FY2024-25", {"NOx": np.array([[1., 2.], [3., 0.]])})
                with Dataset(path) as ds:
                    self.assertEqual(ds.configuration_id, cfg)
                    self.assertIn("FY2024-25", ds.title)
                    self.assertNotIn("FY2023-24", ds.title)
                    self.assertEqual(ds.variables["nox_emissions"].units, "Gg")
                    self.assertAlmostEqual(float(ds.variables["nox_emissions"][:].sum()), 6.)
                    self.assertEqual(ds.variables["nox_emissions"][:].mask.sum(), 1)


if __name__ == "__main__":
    unittest.main()
