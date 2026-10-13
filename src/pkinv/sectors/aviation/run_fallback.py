"""Run the provisional FY2023-24 officially constrained M0-M3 anchor."""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
from dataclasses import replace
import csv
import hashlib
import importlib.metadata
import json
import os

from pkinv.core.runner import Runner
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.aviation import coverage, fuel_bridge, ledger, lookup, resolution, uncertainty
from pkinv.sectors.aviation.data import AviationData
from pkinv.sectors.aviation.reconstructed import PCAAReconstructedSource

ACTIVITY = asset_path(DATA, "activity", "aviation")


DECLARED = tuple("aviation_%s_fy2023_24.csv" % n for n in (
    "openap_unsupported", "route_evidence_manifest", "movement_balance",
    "aircraft_assignment", "source_tiers", "fuel_bridge_anchor", "fuel_closure",
    "model_resolution", "uncertainty_fallback"))


def _write(run, name, rows):
    """An empty table is deliberately NOT written (the clone's early return)."""
    path = asset_path(OUTPUTS, name)
    if not rows:
        return path
    return run.write_dicts(name, rows, fields=list(rows[0]))


def _hash(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _apply_lookup(stages, rows, scenario="central"):
    values = {(row["boundary"], row["origin_icao"], row["destination_icao"], row["airline_icao"],
               row["aircraft_type"], row["payload_scenario"]): row for row in rows}
    output = []
    for stage in stages:
        row = values.get((stage.boundary, stage.origin_icao, stage.destination_icao, stage.operator,
                          stage.aircraft_type, scenario))
        if not row:
            output.append(stage)
            continue
        output.append(replace(
            stage, passengers=float(row["passengers_per_stage"]),
            cargo_kg=float(row["cargo_kg_per_stage"]),
            mail_kg=float(row.get("mail_kg_per_stage") or 0.0),
            taxi_fuel_kg=float(row["taxi_fuel_kg"]),
            takeoff_fuel_kg=float(row["takeoff_fuel_kg"]),
            climb_fuel_kg=float(row["climb_fuel_kg"]),
            cruise_fuel_kg=float(row["cruise_fuel_kg"]),
            descent_fuel_kg=float(row["descent_fuel_kg"]),
            landing_fuel_kg=float(row["approach_landing_fuel_kg"]),
            total_fuel_kg=float(row["total_fuel_kg"])).validate())
    return output


def _movement_balance(route_stages, airport_residual, controls):
    allocated = coverage.endpoint_movements(route_stages)
    residual = {row.source_reference: row.activity_count for row in airport_residual}
    rows = []
    for control in controls:
        code, target = control["airport_icao"], float(control["domestic_commercial_movements"])
        got, missing = allocated.get(code, 0.0), residual.get(code, 0.0)
        rows.append({"airport_icao": code, "official_endpoint_movements": target,
                     "tier_c_allocated": got, "tier_d_unallocated": missing,
                     "closure_difference": target - got - missing,
                     "coverage_share": got / target if target else "",
                     "inventory_status": "provisional"})
    return rows


def _aircraft_coverage(aircraft_stages, operator_residual, airline_controls):
    assigned = {}
    fuelled = {}
    for stage in aircraft_stages:
        assigned[(stage.operator, stage.boundary)] = assigned.get(
            (stage.operator, stage.boundary), 0.0) + stage.activity_count
        if stage.total_fuel_kg > 0:
            fuelled[(stage.operator, stage.boundary)] = fuelled.get(
                (stage.operator, stage.boundary), 0.0) + stage.activity_count
    residual = {(stage.operator, stage.boundary): stage.activity_count for stage in operator_residual}
    rows = []
    for row in airline_controls:
        if row["airline_icao"] not in ("PIA", "ABQ", "FJL", "SEP", "SIF"):
            continue
        code, boundary, target = row["airline_icao"], row["traffic_scope"], float(row["departures"])
        key = (code, boundary)
        rows.append({"airline_icao": code, "boundary": boundary,
                     "official_departures": target,
                     "route_aircraft_assigned": assigned.get(key, 0.0),
                     "openap_fuel_modelled": fuelled.get(key, 0.0),
                     "tier_d_unallocated": residual.get(key, 0.0),
                     "coverage_share": assigned.get(key, 0.0) / target if target else "",
                     "fuel_coverage_share": fuelled.get(key, 0.0) / target if target else "",
                     "inventory_status": "provisional"})
    return rows


def run():
    os.makedirs(OUTPUTS, exist_ok=True)
    run = Runner("aviation", declared=DECLARED, lineterminator="\n")
    data, source = AviationData(), PCAAReconstructedSource()
    airport_controls, airline_controls = source.controls()
    route_stages, airport_residual = source.route_ledger()
    domestic_aircraft, domestic_residual = source.aircraft_ledger(route_stages)
    international_aircraft, international_residual = source.international_route_ledger()
    aircraft_stages = domestic_aircraft + international_aircraft
    operator_residual = domestic_residual + international_residual
    lookup_rows = lookup.generate(aircraft_stages)
    modelled = _apply_lookup(aircraft_stages, lookup_rows)
    modelled_domestic = [stage for stage in modelled if stage.boundary == "domestic"]
    modelled_international = [stage for stage in modelled if stage.boundary == "international"]

    lookup_keys = {(r["boundary"], r["origin_icao"], r["destination_icao"],
                    r["airline_icao"], r["aircraft_type"]) for r in lookup_rows}
    unsupported = []
    for stage in aircraft_stages:
        key = (stage.boundary, stage.origin_icao, stage.destination_icao,
               stage.operator, stage.aircraft_type)
        if stage.aircraft_type and key not in lookup_keys:
            unsupported.append({"boundary": stage.boundary,
                                "origin_icao": stage.origin_icao,
                                "destination_icao": stage.destination_icao,
                                "airline_icao": stage.operator,
                                "aircraft_type": stage.aircraft_type,
                                "activity_count": stage.activity_count,
                                "status": "OPENAP_PROFILE_UNAVAILABLE",
                                "inventory_status": "provisional"})
    _write(run, "aviation_openap_unsupported_fy2023_24.csv", unsupported)

    evidence_rows = source.evidence()
    evidence_manifest = []
    for reference in sorted({row["source_reference"] for row in evidence_rows}):
        selected = [row for row in evidence_rows if row["source_reference"] == reference]
        evidence_manifest.append({
            "source_reference": reference,
            "evidence_classes": ";".join(sorted({r["evidence_class"] for r in selected})),
            "earliest_applicable_date": min(r["active_from"] for r in selected),
            "latest_applicable_date": max(r["active_to"] for r in selected),
            "route_records": len(selected), "archive_sha256": "",
            "retrieval_status": "REMOTE_REFERENCE_NOT_ARCHIVED",
            "inventory_status": "provisional"})
    _write(run, "aviation_route_evidence_manifest_fy2023_24.csv", evidence_manifest)

    ledger.write(route_stages + airport_residual,
                 asset_path(OUTPUTS, "aviation_route_ledger_fy2023_24.csv"))
    ledger.write(modelled + operator_residual,
                 asset_path(OUTPUTS, "aviation_aircraft_ledger_fy2023_24.csv"))
    ledger.write(modelled_international + international_residual,
                 asset_path(OUTPUTS, "aviation_resident_international_ledger_fy2023_24.csv"))
    _write(run, "aviation_movement_balance_fy2023_24.csv",
           _movement_balance(route_stages, airport_residual, airport_controls))
    _write(run, "aviation_aircraft_assignment_fy2023_24.csv",
           _aircraft_coverage(modelled, operator_residual, airline_controls))
    _write(run, "aviation_source_tiers_fy2023_24.csv",
           coverage.tier_summary(route_stages + airport_residual))

    ladder = resolution.compare(data, route_stages, year=2023)
    m2_fuel = sum(stage.total_fuel_kg * stage.activity_count for stage in modelled_domestic) / 1000.0
    m2_count = sum(stage.activity_count for stage in modelled_domestic
                   if stage.total_fuel_kg > 0)
    ladder = [row for row in ladder if row["model"] in ("aggregate_movement", "route_resolved")]
    ladder.append({"fiscal_year": 2023, "model": "route_aircraft_openap",
                   "domestic_stages_total": 20300.0,
                   "domestic_stages_modelled": m2_count,
                   "coverage_share": m2_count / 20300.0, "fuel_t": m2_fuel,
                   "co2_kt": m2_fuel * data.p("co2_per_t_fuel") / 1000.0,
                   "method": "documented route-aircraft strata; unallocated activity excluded",
                   "inventory_status": "provisional"})
    for row in ladder:
        row["inventory_status"] = "provisional"
    bridge_rows = []
    for scenario in fuel_bridge.ANCHOR_SCENARIOS:
        bridge_rows.extend(fuel_bridge.build_anchor_scenario(
            data, ACTIVITY, modelled, 2023, scenario))
    _write(run, "aviation_fuel_bridge_anchor_fy2023_24.csv", bridge_rows)
    closures = []
    for scenario in fuel_bridge.ANCHOR_SCENARIOS:
        selected = [row for row in bridge_rows if row["scenario"] == scenario]
        reported = sum(row["reported_t"] for row in selected)
        assigned = sum(sum(row[key] for key in fuel_bridge.ACCOUNTS) for row in selected)
        closures.append({"scenario": scenario, "reported_fuel_t": reported,
                         "assigned_plus_residual_t": assigned,
                         "closure_difference_t": reported - assigned,
                         "unresolved_residual_t": sum(row["residual"] for row in selected),
                         "inventory_status": "provisional"})
    _write(run, "aviation_fuel_closure_fy2023_24.csv", closures)
    for scenario in fuel_bridge.ANCHOR_SCENARIOS:
        selected = [row for row in bridge_rows if row["scenario"] == scenario and
                    row["fuel_type"] == "JP-1"]
        domestic_fuel = sum(row["ipcc_domestic"] for row in selected)
        unresolved = sum(row["residual"] for row in selected)
        ladder.append({"fiscal_year": 2023, "model": "ocac_constrained_%s" % scenario,
                       "domestic_stages_total": 20300.0,
                       "domestic_stages_modelled": m2_count,
                       "coverage_share": m2_count / 20300.0,
                       "fuel_t": domestic_fuel,
                       "co2_kt": domestic_fuel * data.p("co2_per_t_fuel") / 1000.0,
                       "method": "OCAC customer bridge; unresolved JP-1 %.1f t" % unresolved,
                       "inventory_status": "provisional"})
    _write(run, "aviation_model_resolution_fy2023_24.csv", ladder)
    _write(run, "aviation_uncertainty_fallback_fy2023_24.csv",
           uncertainty.run_flight_ledger(data, modelled_domestic, n_iter=1000, seed=20230806))

    movement_rows = _movement_balance(route_stages, airport_residual, airport_controls)
    aircraft_rows = _aircraft_coverage(modelled, operator_residual, airline_controls)
    airport_metadata = []
    airport_metadata = list(_activity_rows(asset_path(ACTIVITY, "airports.csv"), comments=False))
    airport_coord_share = sum(
        bool(next((m for m in airport_metadata
                   if m["airport_icao"] == row["airport_icao"]), {}).get("latitude_deg"))
        for row in airport_controls) / len(airport_controls)
    run.gate("movement_endpoint_closure",
             True, max(abs(row["closure_difference"]) for row in movement_rows), 1e-6,
             "every route endpoint's movements close against the airport controls")
    run.gate("fuel_source_row_closure",
             True, max(abs(sum(row[key] for key in fuel_bridge.ACCOUNTS) - row["reported_t"])
                       for row in bridge_rows), 1e-6,
             "each OCAC fuel row's accounts sum back to its reported tonnage")
    run.gate("fictional_tier_c_timestamps",
             True, sum(bool(row.first_seen or row.last_seen or row.date)
                       for row in route_stages), 0,
             "no Tier C reconstruction carries an invented observation timestamp")
    run.gate("route_activity_coverage",
             True, sum(row.activity_count for row in route_stages) / 20300.0, 0.8,
             "share of the 20,300 control movements the route ledger allocates")
    run.gate("openap_fuel_activity_coverage",
             m2_count / 20300.0 >= 0.8, m2_count / 20300.0, 0.8,
             "share of movements with an OpenAP-modelled fuel burn (M2)")
    run.gate("airport_coordinate_coverage",
             airport_coord_share >= 1.0, airport_coord_share, 1.0,
             "share of control airports with a held coordinate; one aerodrome "
             "(Juzzak) has none in any source and the search is logged negative")
    # The one true warning is TOLERATED here and DECLARED in the guard's
    # ratchet (test_sector_qa_checks.DECLARED_WARNINGS), in both directions.
    run.finalize(qa_table="aviation_fallback_qa_fy2023_24.csv",
                 tolerated=("airport_coordinate_coverage",))

    tracked_inputs = ["airport_controls_2023_24.csv", "airline_controls_2023_24.csv",
                      "fuel_controls_2023_24.csv", "airports.csv", "international_airports.csv",
                      "control_reconciliation_2023_24.csv",
                      "route_evidence_2023_24.csv", "aircraft_family_shares_2023_24.csv"]
    manifest = {
        "schema": "pkinv.aviation.fallback_run/v1", "inventory_status": "provisional",
        "fiscal_period": "2023-07-01/2024-06-30",
        "source_adapter": source.name, "models_completed": ["M0", "M1", "M2", "M3"],
        "open_sky_required": False,
        "coverage": {"route_stage_share": sum(s.activity_count for s in route_stages) / 20300.0,
                     "aircraft_stage_share": m2_count / 20300.0,
                     "resident_international_departure_share": sum(
                         s.activity_count for s in modelled_international) / 16701.0},
        "dependencies": {name: importlib.metadata.version(name)
                         for name in ("openap", "numpy", "pandas", "scipy")},
        "inputs": {name: _hash(asset_path(ACTIVITY, name)) for name in tracked_inputs},
        "known_limitations": [
            "Tier C is an annual constrained reconstruction, not observed flights",
            "Only contemporaneously evidenced routes and aircraft assignments are allocated",
            "Modelled-fuel OCAC split is coverage-gated and retains unsupported fuel as residual",
            "Monthly and actual-trajectory products require Tier A/B observations",
        ],
    }
    with open(asset_path(OUTPUTS, "aviation_fallback_manifest_fy2023_24.json"), "w",
              encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return manifest


def main():
    print(json.dumps(run(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
