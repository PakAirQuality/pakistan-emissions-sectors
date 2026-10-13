"""OpenAP synthetic route/aircraft lookup generation for the provisional anchor."""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
from dataclasses import asdict, replace
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.aviation import ledger, performance
from pkinv.sectors.aviation.data import AviationData
from pkinv.core.io import write_table

LOADS = {"low": 0.625, "central": None, "high": 0.875}
FALLBACK_SEATS = {"AT72": 70.0}


def _airline_loads(stages):
    path = asset_path(DATA, "activity", "aviation", "airline_controls_2023_24.csv")
    rows = list(_activity_rows(path, comments=False))
    loads = {(row["airline_icao"], row["traffic_scope"]): {
                "passengers": float(row["passengers_total"]),
                "passengers_embarked": float(row["passengers_embarked"]),
                "movements": float(row["movements"]),
                "cargo_loaded_t": float(row["cargo_loaded_t"]),
                "mail_loaded_t": float(row["mail_loaded_t"]),
                "departures": float(row["departures"])}
            for row in rows if row["traffic_scope"] in ("domestic", "international")}
    from openap import prop
    available = set(prop.available_aircraft(use_synonym=False))
    totals = {}
    for stage in stages:
        key = (stage.operator, stage.boundary)
        if key not in loads or not stage.aircraft_type:
            continue
        aircraft = stage.aircraft_type.lower()
        if aircraft in available:
            seats = float(prop.aircraft(aircraft)["pax"]["max"])
        else:
            seats = FALLBACK_SEATS.get(stage.aircraft_type, 0.0)
        count = float(stage.activity_count)
        stage_total, seat_total = totals.get(key, (0.0, 0.0))
        totals[key] = stage_total + count, seat_total + count * seats
    for key, load_info in loads.items():
        assigned, seat_departures = totals.get(key, (0.0, 0.0))
        weighted_seats = seat_departures / assigned if assigned else 0.0
        pax_per_departure = (load_info["passengers_embarked"] / load_info["departures"]
                             if load_info["departures"] else 0.0)
        load_info["assigned_weighted_seats"] = weighted_seats
        load_info["observed_load_fraction"] = (pax_per_departure / weighted_seats
                                               if weighted_seats else 0.0)
    return loads


def _models(aircraft):
    from openap import Emission, FuelFlow, prop
    if aircraft.lower() not in prop.available_aircraft(use_synonym=False):
        raise ValueError("aircraft %s is not natively supported by OpenAP" % aircraft)
    properties = prop.aircraft(aircraft)
    engine_name = properties["engine"]["default"]
    engine = prop.engine(engine_name)
    return (properties, engine,
            FuelFlow(aircraft, eng=engine_name), Emission(aircraft, eng=engine_name))


def _integrate_pollutants(points, fuel_flow, emission, initial_mass):
    totals = {"nox_kg": 0.0, "co_kg": 0.0, "hc_kg": 0.0}
    mass = initial_mass
    for left, right in zip(points, points[1:]):
        dt = right.timestamp - left.timestamp
        if dt <= 0 or dt > 1800:
            continue
        ff = max(0.0, performance._flow(fuel_flow, left, mass))
        tas = max(20.0, (left.velocity_ms or 0.0) * performance.MS_TO_KT)
        alt = max(0.0, (left.altitude_m or 0.0) * performance.M_TO_FT)
        totals["nox_kg"] += float(emission.nox(ff, tas, alt)) * dt / 1000.0
        totals["co_kg"] += float(emission.co(ff, tas, alt)) * dt / 1000.0
        totals["hc_kg"] += float(emission.hc(ff, tas, alt)) * dt / 1000.0
        mass -= ff * dt
    return totals


def model_combination(stage, airline, payload_scenario, data, load_info, points=None):
    properties, engine, fuel_flow, emission = _models(stage.aircraft_type)
    seats = float(properties["pax"]["max"])
    # A modelled stage represents a departure.  International uplift is modelled only
    # outbound from Pakistan, so embarked passengers/departure is the matched load.
    central_pax = (load_info["passengers_embarked"] / load_info["departures"]
                   if load_info["departures"] else 0.0)
    observed_load = load_info["observed_load_fraction"]
    central_load = min(1.0, observed_load)
    if payload_scenario == "central":
        load = central_load
    elif payload_scenario == "low":
        load = min(LOADS["low"], central_load)
    else:
        load = max(LOADS["high"], central_load)
    passengers = seats * load
    cargo_kg = (load_info["cargo_loaded_t"] * 1000.0 / load_info["departures"]
                if load_info["departures"] else 0.0)
    mail_kg = (load_info["mail_loaded_t"] * 1000.0 / load_info["departures"]
               if load_info["departures"] else 0.0)
    payload_kg = passengers * 100.0 + cargo_kg + mail_kg
    reserve_kg = float(properties["mtow"]) * 0.05
    mass = min(float(properties["mtow"]), float(properties["oew"]) + payload_kg + reserve_kg + 5000)
    points = points or performance.synthetic_points(stage, data)
    model_input = replace(stage, source_tier="B", data_tier="B",
                          record_granularity="flight_stage", activity_count=1.0)
    result = None
    for _ in range(8):
        result = performance.integrate(model_input, points, mass, fuel_flow=fuel_flow)
        target = min(float(properties["mtow"]), float(properties["oew"]) + payload_kg +
                     reserve_kg + result.total_fuel_kg)
        if abs(target - mass) < 1.0:
            break
        mass = target
    taxi_seconds = data.p("openap_default_taxi_out_s") + data.p("openap_default_taxi_in_s")
    taxi_ff = float(engine["ff_idl"]) * int(properties["engine"]["number"])
    taxi_fuel = taxi_ff * taxi_seconds
    result = replace(result, taxi_fuel_kg=taxi_fuel,
                     total_fuel_kg=result.total_fuel_kg + taxi_fuel,
                     source_tier="C", record_granularity="annual_route",
                     trajectory_quality="modelled", trajectory_available=False).validate()
    pollutants = _integrate_pollutants(points, fuel_flow, emission, mass)
    for key, ei in (("nox_kg", "ei_nox_idl"), ("co_kg", "ei_co_idl"),
                    ("hc_kg", "ei_hc_idl")):
        pollutants[key] += taxi_fuel * float(engine[ei]) / 1000.0
    duration = points[-1].timestamp - points[0].timestamp + taxi_seconds
    return {
        "boundary": stage.boundary,
        "origin_icao": stage.origin_icao, "destination_icao": stage.destination_icao,
        "airline_icao": airline, "aircraft_type": stage.aircraft_type,
        "payload_scenario": payload_scenario, "passenger_load_fraction": load,
        "observed_passengers_per_departure": central_pax,
        "observed_passenger_load_fraction": observed_load,
        "available_seats": seats,
        "capacity_warning": "OBSERVED_PAX_EXCEED_SEATS" if observed_load > 1 else "",
        "payload_source": "PCAA airline embarked passengers, loaded cargo and loaded mail per departure",
        "passengers_per_stage": passengers, "cargo_kg_per_stage": cargo_kg,
        "mail_kg_per_stage": mail_kg, "payload_kg_per_stage": payload_kg,
        "distance_km": stage.great_circle_nm * 1.852,
        "route_multiplier": data.p("openap_route_detour_factor"),
        "flight_time_min": duration / 60.0, "initial_mass_kg": mass,
        "reserve_fuel_mass_kg": reserve_kg,
        "taxi_fuel_kg": result.taxi_fuel_kg,
        "takeoff_fuel_kg": result.takeoff_fuel_kg,
        "climb_fuel_kg": result.climb_fuel_kg,
        "cruise_fuel_kg": result.cruise_fuel_kg,
        "descent_fuel_kg": result.descent_fuel_kg,
        "approach_landing_fuel_kg": result.landing_fuel_kg,
        "total_fuel_kg": result.total_fuel_kg,
        "co2_kg": result.total_fuel_kg * data.p("co2_per_t_fuel"),
        **pollutants,
        "trajectory_source": "OpenAP synthetic profile",
        "inventory_status": "provisional",
    }


def generate(stages, output_path=None):
    data, loads = AviationData(), _airline_loads(stages)
    combinations = {}
    for stage in stages:
        if not stage.aircraft_type or not stage.great_circle_nm or not stage.operator:
            continue
        combinations[(stage.boundary, stage.origin_icao, stage.destination_icao,
                      stage.operator, stage.aircraft_type)] = stage
    rows = []
    for (boundary, _, _, airline, _), stage in sorted(combinations.items()):
        try:
            points = performance.synthetic_points(stage, data)
        except ValueError:
            continue
        for scenario in LOADS:
            try:
                rows.append(model_combination(stage, airline, scenario, data,
                                              loads[(airline, boundary)], points=points))
            except ValueError:
                # Aircraft supported by the fuel model may still lack an OpenAP
                # kinematic profile.  The caller detects the absent lookup and keeps
                # that activity unfuelled, so it remains visible in coverage/residuals.
                continue
    output_path = output_path or asset_path(OUTPUTS, "aviation_openap_lookup_fy2023_24.csv")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    if rows:
        write_table(output_path, list(rows[0]), rows, lineterminator="\n")
    return rows
