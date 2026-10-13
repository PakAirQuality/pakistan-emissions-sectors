"""Run the FY2023-24 flight-ledger inventory.

This command fails closed when permissioned records or required model fields are absent.
Use ``--coverage-only`` to audit an imported OpenSky sample before aircraft/performance
enrichment is complete.
"""

from pkinv.assets import asset_path
import argparse
import csv
import json
import os
from dataclasses import replace

from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.aviation import coverage, fuel_bridge, ledger, performance, products, resolution, uncertainty
from pkinv.sectors.aviation.data import AviationData
from pkinv.core.io import write_table


def _write_csv(path, rows):
    if not rows:
        return
    write_table(path, list(rows[0]), rows)


def _trajectory_points(path):
    if not path or not os.path.exists(path):
        return {}
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("trajectory Parquet requires the 'aviation' extra") from exc
    groups = {}
    for flight_id, frame in pd.read_parquet(path).groupby("flight_id"):
        groups[str(flight_id)] = []
        for row in frame.to_dict("records"):
            point = ledger.TrajectoryPoint(**row)
            if point.phase == "unclassified":
                point.phase = performance.phase(point.altitude_m, point.vertical_rate_ms,
                                                point.on_ground)
            groups[str(flight_id)].append(point)
    return groups


def _initial_mass(aircraft_type, data):
    try:
        from openap import prop
    except ImportError as exc:
        raise RuntimeError("OpenAP modelling requires the 'aviation' extra") from exc
    openap_type = data.openap_aircraft(aircraft_type) or aircraft_type
    return float(prop.aircraft(openap_type, use_synonym=True)["mtow"]) * data.p(
        "openap_default_mass_fraction_mtow")


def model_stages(stages, data, trajectory_path=None):
    points = _trajectory_points(trajectory_path)
    modelled = []
    for stage in stages:
        if stage.total_fuel_kg > 0:
            modelled.append(stage)
            continue
        if not stage.aircraft_type or not stage.great_circle_nm:
            modelled.append(stage)
            continue
        openap_type = data.openap_aircraft(stage.aircraft_type)
        if not openap_type:
            modelled.append(stage)
            continue
        original_type = stage.aircraft_type
        model_input = replace(stage, aircraft_type=openap_type)
        mass = _initial_mass(original_type, data)
        result = performance.model_stage(model_input, data, points.get(stage.flight_id), mass)
        result = replace(result, aircraft_type=original_type)
        result.imputation_method = (result.imputation_method + ";mass_%.2f_mtow" %
                                    data.p("openap_default_mass_fraction_mtow")).strip(";")
        modelled.append(result)
    return ledger.validate_records(modelled)


def run(ledger_path, coverage_only=False, trajectory_path=None):
    data = AviationData()
    stages = ledger.read(ledger_path)
    stages = [s for s in stages if s.fiscal_year == data.year]
    if not stages:
        raise ValueError("no FY%d stages in %s" % (data.year, ledger_path))
    controls = coverage.official_controls(data)
    pre = coverage.report(stages, controls)
    completed, residual = coverage.reconstruct(stages, controls, year=data.year)
    post = coverage.report(completed, controls)
    os.makedirs(OUTPUTS, exist_ok=True)
    _write_csv(asset_path(OUTPUTS, "aviation_coverage_airport_2023.csv"),
               [dict(row, coverage_stage="observed") for row in pre] +
               [dict(row, coverage_stage="completed") for row in post])
    _write_csv(asset_path(OUTPUTS, "aviation_flight_tiers_2023.csv"),
               coverage.tier_summary(completed))
    with open(asset_path(OUTPUTS, "aviation_coverage_residual_2023.json"), "w",
              encoding="utf-8") as handle:
        json.dump(residual, handle, indent=2, sort_keys=True)
        handle.write("\n")
    if coverage_only:
        return {"stages": len(completed), "residual_movements": sum(residual.values())}
    completed = model_stages(completed, data, trajectory_path)
    missing = [s.flight_id for s in completed if not s.aircraft_type or
               not s.great_circle_nm or not s.total_fuel_kg]
    if missing:
        raise ValueError("%d completed stages still need aircraft, distance, or OpenAP fuel; "
                         "first=%s" % (len(missing), missing[0]))
    recon = fuel_bridge.ledger_reconciliation(data, completed)
    _write_csv(asset_path(OUTPUTS, "aviation_fuel_reconciliation_flight_2023.csv"), recon)
    domestic_factor = next(r["reconciliation_factor"] for r in recon
                           if r["boundary"] == "domestic")
    ladder = resolution.compare(data, completed, domestic_factor)
    _write_csv(asset_path(OUTPUTS, "aviation_model_resolution_2023.csv"), ladder)
    _write_csv(asset_path(OUTPUTS, "aviation_uncertainty_flight_factors_2023.csv"),
               uncertainty.flight_factor_table(data))
    _write_csv(asset_path(OUTPUTS, "aviation_uncertainty_flight_scenarios_2023.csv"),
               uncertainty.run_flight_ledger(data, completed))
    _write_csv(asset_path(OUTPUTS, "aviation_monthly_flight_2023.csv"),
               products.monthly(completed, data.p("co2_per_t_fuel")))
    _write_csv(asset_path(OUTPUTS, "aviation_phase_emissions_2023.csv"),
               products.phase_totals(completed, data.p("co2_per_t_fuel")))
    _write_csv(asset_path(OUTPUTS, "aviation_airport_lto_flight_2023.csv"),
               products.airport_lto(completed, data.p("co2_per_t_fuel")))
    points_by_flight = _trajectory_points(trajectory_path)
    physical_fuel = None
    if points_by_flight:
        from pkinv.core.gis.grid import build_grid
        from pkinv.core.gis.render import write_geotiff
        grid = build_grid()
        physical = products.physical_grid(completed, points_by_flight, grid)
        physical_fuel = float(physical.sum())
        # Store kg fuel per cell; carbon conversion remains explicit in metadata/tables.
        write_geotiff(asset_path(OUTPUTS, "aviation_physical_fuel_2023.tif"), physical, grid)
        with open(asset_path(OUTPUTS, "aviation_routes_2023.geojson"), "w", encoding="utf-8") as handle:
            json.dump(products.route_geojson(completed, points_by_flight), handle,
                      separators=(",", ":"))
            handle.write("\n")
        _write_csv(asset_path(OUTPUTS, "aviation_altitude_bins_2023.csv"),
                   products.altitude_bins(completed, points_by_flight,
                                          data.p("co2_per_t_fuel")))
    _write_csv(asset_path(OUTPUTS, "aviation_accounting_views_2023.csv"),
               products.accounting_views(completed, data, physical_fuel))
    return {"stages": len(completed), "residual_movements": sum(residual.values()),
            "domestic_reconciliation_factor": domestic_factor}


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", default=asset_path(
        DATA, "private", "aviation", "flight_ledger_2023.parquet"))
    parser.add_argument("--coverage-only", action="store_true")
    parser.add_argument("--trajectories", default=asset_path(
        DATA, "private", "aviation", "trajectory_points_2023.parquet"))
    args = parser.parse_args(argv)
    result = run(args.ledger, args.coverage_only, args.trajectories)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
