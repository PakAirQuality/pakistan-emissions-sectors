"""Public functions retain configuration, period and dependence boundaries."""
import dataclasses
import os
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

import netCDF4
import numpy as np

from pakemis_query import errors
from pakemis_query import functions
from pakemis_query.models import GridCellRequest, QueryEmissions, TimeseriesRequest, UncertaintyRequest


class Release:
    defaults = {"configuration_id": "S_TAN", "period_id": "FY2023-24"}
    release_id = "test-release"
    limitations = {}
    tables = ("fact_ghg_conditional", "fact_ghg_trend")

    def context(self, fields):
        return dict(fields, release_id=self.release_id)

    def product_digest(self, path):
        return "test-file-digest"

    def dim(self, name):
        if name == "dim_period":
            return [{"period_id": p, "basis": "fiscal"} for p in ("FY2015-16", "FY2024-25")]
        return []


class Engine:
    def __init__(self):
        self.release = Release()
        self.decimals = {"emissions_Gg": 6}
        self.con = sqlite3.connect(":memory:")

    def _fetch(self, query):
        result = self.con.execute(query)
        names = [col[0] for col in result.description]
        return [dict(zip(names, map(str, row))) for row in result.fetchall()]

    def _provenance(self, tables):
        return {"tables": list(tables)}

    def _fill(self, query):
        return dataclasses.replace(query, basis=query.basis or "fiscal")


class ConfigurationFunctions(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def tearDown(self):
        self.engine.con.close()

    def test_all_four_timeseries_reach_the_engine_with_own_configuration(self):
        for cfg in ("S_TAN", "L_TAN", "S_IPCC", "L_IPCC"):
            request = TimeseriesRequest(QueryEmissions(configuration_id=cfg))
            with patch.object(self.engine, "query_emissions", create=True,
                              return_value={"receipt": "old", "citation": "old", "result_sha256": "digest"}) as query:
                output = functions.get_timeseries(self.engine, request)
            asked = query.call_args.args[0]
            self.assertEqual(cfg, asked.configuration_id)
            self.assertEqual(("FY2015-16", "FY2024-25"), asked.periods)
            self.assertNotEqual("old", output["receipt"])

    def create_uncertainty(self):
        columns = ("period_id", "configuration_id", "sector_id", "species_or_metric", "unit",
                   "dependence_case", "deterministic_quantity", "P2_5_quantity", "P50_quantity",
                   "P97_5_quantity", "interval_kind", "limitations", "result_row_id")
        self.engine.con.execute("CREATE TABLE fact_ghg_conditional (" +
                                ",".join(name + " VARCHAR" for name in columns) + ")")
        values = []
        for cfg, central in (("S_TAN", 100), ("L_TAN", 200), ("S_IPCC", 300), ("L_IPCC", 400)):
            for period in ("FY2023-24", "FY2024-25"):
                for case in ("persistent_parameters", "annual_activity_errors"):
                    values.append((period, cfg, "national_covered", "CO2e_AR5", "Mt_CO2e", case,
                                   str(central), str(central-10), str(central), str(central+10),
                                   "conditional_parameter_percentiles", "unestimated sources excluded", cfg+period+case))
        self.engine.con.executemany("INSERT INTO fact_ghg_conditional VALUES (" + ",".join("?" for _ in columns) + ")", values)
        self.engine.con.execute("CREATE TABLE fact_ghg_trend AS SELECT 'FY2023-24' AS start_period, "
                                "period_id AS end_period, configuration_id, sector_id, species_or_metric, unit, "
                                "dependence_case, deterministic_quantity AS deterministic_change, "
                                "'-3' AS P2_5_quantity, '2' AS P50_quantity, '7' AS P97_5_quantity, "
                                "'paired_change_parameter_percentiles' AS interval_kind, limitations, "
                                "'trend' || result_row_id AS result_row_id FROM fact_ghg_conditional "
                                "WHERE period_id='FY2024-25'")

    def test_uncertainty_filters_configuration_and_retains_separate_dependence_cases(self):
        self.create_uncertainty()
        output = functions.get_uncertainty(self.engine,
            UncertaintyRequest(configuration_id="L_IPCC", period_id="FY2024-25"))
        self.assertEqual(2, len(output["values"]))
        self.assertEqual({400.}, {v["value"] for v in output["values"]})
        self.assertEqual({"FY2024-25"}, {v["period_id"] for v in output["values"]})
        self.assertEqual({"persistent_parameters", "annual_activity_errors"},
                         {v["dependence_case"] for v in output["values"]})

    def test_series_returns_paired_changes_rather_than_difference_of_quantiles(self):
        self.create_uncertainty()
        output = functions.get_uncertainty(self.engine,
            UncertaintyRequest(scope="series", configuration_id="L_TAN", period_id="FY2024-25"))
        trends = [v for v in output["values"] if v["kind"] == "paired_change"]
        self.assertEqual(2, len(trends))
        self.assertEqual({2.}, {v["value"] for v in trends})
        self.assertEqual({"-3"}, {v["quantiles"]["P2.5"] for v in trends})
        self.assertEqual({"FY2023-24", "FY2024-25"}, set(output["context"]["periods"]))
        with self.assertRaises(errors.NotEstimated):
            functions.get_uncertainty(self.engine, UncertaintyRequest(period_id="FY2025-26"))
        with self.assertRaises(errors.GrainUnavailable):
            functions.get_uncertainty(self.engine, UncertaintyRequest(category="Managed soils"))


class ConfigurationGrid(unittest.TestCase):
    def test_annual_files_are_selected_by_configuration_and_verify_declared_identity(self):
        engine = Engine()
        with tempfile.TemporaryDirectory() as directory:
            paths = {}
            for index, cfg in enumerate(("S_TAN", "L_TAN", "S_IPCC", "L_IPCC"), 1):
                path = os.path.join(directory, cfg + ".nc")
                with netCDF4.Dataset(path, "w") as ds:
                    for dimension, size in (("time", 2), ("spatial_view", 3), ("lat", 2), ("lon", 2)):
                        ds.createDimension(dimension, size)
                    ds.createVariable("lat", "f4", ("lat",))[:] = [30, 31]
                    ds.createVariable("lon", "f4", ("lon",))[:] = [70, 71]
                    ds.createVariable("period_id", str, ("time",))[:] = np.array(["FY2015-16", "FY2024-25"], dtype=object)
                    ds.createVariable("spatial_view", str, ("spatial_view",))[:] = np.array(["physical", "origin", "accounting"], dtype=object)
                    ds.createVariable("co2_emissions", "f8", ("time", "spatial_view", "lat", "lon"))[:] = index
                    ds.configuration_id = cfg
                paths["ANNUAL_" + cfg] = path
            for index, cfg in enumerate(("S_TAN", "L_TAN", "S_IPCC", "L_IPCC"), 1):
                output = functions.get_grid_cell(engine, GridCellRequest(lat=30, lon=70,
                    period_id="FY2024-25", configuration_id=cfg), paths)
                self.assertEqual(3 * index, output["values"][0]["value"])
                self.assertEqual(cfg, output["context"]["configuration_id"])
            wrong = dict(paths, ANNUAL_L_IPCC=paths["ANNUAL_S_TAN"])
            with self.assertRaises(errors.IdentityError):
                functions.get_grid_cell(engine, GridCellRequest(lat=30, lon=70,
                    period_id="FY2015-16", configuration_id="L_IPCC"), wrong)
            with self.assertRaises(errors.GrainUnavailable):
                functions.get_grid_cell(engine, GridCellRequest(lat=30, lon=70,
                    period_id="FY2015-16", configuration_id="L_TAN", month="201507"), paths)
        engine.con.close()


if __name__ == "__main__":
    unittest.main()
