"""Paper-A analyses: component reconciliation, bounds, and like-for-like ladders."""
from __future__ import annotations

from collections import defaultdict
import math

import numpy as np
from scipy.optimize import linprog

from pkinv.sectors.aviation import coverage, fuel_bridge, lto, resolution
from pkinv.sectors.aviation.reconstructed import PCAAReconstructedSource, _distance_km, _rows


FALLBACK_SEATS = {"AT72": 70.0}


def annual_component_comparison(data, years=(2022, 2023)):
    rows = []
    co2_factor = data.p("co2_per_t_fuel")
    for year in years:
        sales = data.fuel_sales_for(year)
        resident_fuel = sum(r["tonnes"] for r in sales if r["fuel_type"] == "JP-1" and
                            r["customer_category"] in fuel_bridge.LOCAL_CUSTOMERS)
        foreign_fuel = sum(r["tonnes"] for r in sales if r["fuel_type"] == "JP-1" and
                           r["customer_category"] == "Overseas/Foreign Aviation")
        government_fuel = sum(r["tonnes"] for r in sales if r["fuel_type"] == "JP-1" and
                              r["customer_category"].startswith("Government"))
        oecd_dom = fuel_bridge._oecd_value(data, year, "domestic")
        oecd_int = fuel_bridge._oecd_value(data, year, "international_bunker")
        oecd_res = (fuel_bridge._oecd_value(data, year, "resident_domestic_in") +
                    fuel_bridge._oecd_value(data, year, "resident_international_from"))
        oecd_foreign = oecd_dom + oecd_int - oecd_res
        components = (("resident", resident_fuel, oecd_res),
                      ("foreign", foreign_fuel, oecd_foreign),
                      ("combined", resident_fuel + foreign_fuel, oecd_dom + oecd_int))
        for component, fuel_t, benchmark in components:
            co2_t = fuel_t * co2_factor
            rows.append({"fiscal_year": year, "component": component,
                         "ocac_jp1_t": fuel_t, "ocac_co2_t": co2_t,
                         "oecd_co2_t": benchmark, "ratio": co2_t / benchmark,
                         "difference_co2_t": co2_t - benchmark,
                         "government_jp1_t_excluded": government_fuel,
                         "comparison_role": "gross-boundary external comparison"})
        resident_difference = rows[-3]["difference_co2_t"]
        foreign_difference = rows[-2]["difference_co2_t"]
        rows[-1]["offset_cancellation_fraction"] = (
            1.0 - abs(resident_difference + foreign_difference) /
            (abs(resident_difference) + abs(foreign_difference)))
    return rows


def _logit(value):
    value = min(1 - 1e-9, max(1e-9, value))
    return math.log(value / (1 - value))


def calibrate_shares(raw, weights, target):
    """Preserve odds ordering while matching one weighted aggregate share."""
    lo, hi = -30.0, 30.0
    for _ in range(200):
        shift = (lo + hi) / 2.0
        values = {key: 1.0 / (1.0 + math.exp(-(_logit(value) + shift)))
                  for key, value in raw.items()}
        aggregate = sum(weights[k] * values[k] for k in values) / sum(weights.values())
        if aggregate < target:
            lo = shift
        else:
            hi = shift
    return values, (lo + hi) / 2.0


def carrier_share_scenarios(data, modelled_stages, activity_dir=None):
    controls = _rows("airline_controls_2023_24.csv")
    groups = {"PIA": {"PIA"}, "Others": {"ABQ", "FJL", "SEP", "SIF"}}
    weights = {"PIA": next(r["tonnes"] for r in data.fuel_sales_for(2023)
                           if r["customer_category"] == "Domestic Avi-PIA" and r["fuel_type"] == "JP-1"),
               "Others": next(r["tonnes"] for r in data.fuel_sales_for(2023)
                              if r["customer_category"] == "Domestic Avi-Others" and r["fuel_type"] == "JP-1")}
    target = fuel_bridge.resident_domestic_share(data, 2023)
    common = {group: target for group in groups}
    movement = {}
    for group, airlines in groups.items():
        counts = defaultdict(float)
        for row in controls:
            if row["airline_icao"] in airlines:
                counts[row["traffic_scope"]] += float(row["departures"])
        movement[group] = counts["domestic"] / sum(counts.values())
    fuel = {}
    for group, airlines in groups.items():
        values = defaultdict(float)
        for stage in modelled_stages:
            if stage.operator in airlines and stage.total_fuel_kg > 0:
                values[stage.boundary] += stage.total_fuel_kg * stage.activity_count
        fuel[group] = values["domestic"] / sum(values.values()) if sum(values.values()) else movement[group]
    output = []
    for scenario, raw in (("common_resident_share", common),
                          ("carrier_movement_share", movement),
                          ("carrier_modelled_fuel_share", fuel)):
        calibrated, shift = (raw, 0.0) if scenario == "common_resident_share" else calibrate_shares(raw, weights, target)
        for group in groups:
            output.append({"fiscal_year": 2023, "scenario": scenario,
                           "customer_group": group, "ocac_weight_t": weights[group],
                           "raw_domestic_share": raw[group],
                           "calibrated_domestic_share": calibrated[group],
                           "aggregate_target_share": target, "logit_shift": shift,
                           "domestic_fuel_t": weights[group] * calibrated[group],
                           "international_fuel_t": weights[group] * (1 - calibrated[group]),
                           "calibration_source": "OECD resident domestic/(domestic+international-from)"})
    return output


def payload_capacity_audits(assigned_stages, lookup_rows, airport_controls=None,
                            airline_controls=None):
    """Reconcile PCAA passenger/payload controls with assigned aircraft capacity.

    Passenger, cargo and mail controls are operator averages, not route observations.
    The audit therefore applies each operator's published per-departure load to its
    reconstructed stages and makes incomplete assignment visible.
    """
    airport_controls = airport_controls or _rows("airport_controls_2023_24.csv")
    airline_controls = airline_controls or _rows("airline_controls_2023_24.csv")
    official = {(r["airline_icao"], r["traffic_scope"]): r for r in airline_controls
                if r["traffic_scope"] in ("domestic", "international")}
    central = {(r["boundary"], r["origin_icao"], r["destination_icao"],
                r["airline_icao"], r["aircraft_type"]): r for r in lookup_rows
               if r["payload_scenario"] == "central"}

    def seats(stage):
        row = central.get((stage.boundary, stage.origin_icao, stage.destination_icao,
                           stage.operator, stage.aircraft_type))
        if row and row.get("available_seats") not in (None, ""):
            return float(row["available_seats"]), "OpenAP aircraft properties"
        if stage.aircraft_type in FALLBACK_SEATS:
            return FALLBACK_SEATS[stage.aircraft_type], "documented family fallback"
        return 0.0, "unresolved"

    assigned = defaultdict(float)
    seat_departures = defaultdict(float)
    seat_sources = defaultdict(set)
    airport_passengers = defaultdict(float)
    airport_capacity = defaultdict(float)
    for stage in assigned_stages:
        if stage.boundary not in ("domestic", "international") or not stage.operator:
            continue
        key = (stage.operator, stage.boundary)
        control = official.get(key)
        if not control:
            continue
        n = float(stage.activity_count)
        capacity, source = seats(stage)
        assigned[key] += n
        seat_departures[key] += n * capacity
        seat_sources[key].add(source)
        if stage.boundary == "domestic":
            departures = float(control["departures"])
            pax_per_departure = (float(control["passengers_embarked"]) / departures
                                 if departures else 0.0)
            for airport in (stage.origin_icao, stage.destination_icao):
                airport_passengers[airport] += n * pax_per_departure
                airport_capacity[airport] += n * capacity

    airline_rows = []
    for key in sorted(assigned):
        control = official[key]
        departures = float(control["departures"])
        assigned_departures = assigned[key]
        weighted_seats = (seat_departures[key] / assigned_departures
                          if assigned_departures else 0.0)
        pax_per_departure = (float(control["passengers_embarked"]) / departures
                             if departures else 0.0)
        load = pax_per_departure / weighted_seats if weighted_seats else 0.0
        airline_rows.append({
            "airline_icao": key[0], "boundary": key[1],
            "official_departures": departures,
            "assigned_departures": assigned_departures,
            "unmatched_departures": departures - assigned_departures,
            "passengers_embarked": float(control["passengers_embarked"]),
            "passengers_per_departure": pax_per_departure,
            "weighted_seats_per_departure": weighted_seats,
            "implied_passenger_load_factor": load,
            "cargo_loaded_t": float(control["cargo_loaded_t"]),
            "cargo_kg_per_departure": (float(control["cargo_loaded_t"]) * 1000 / departures
                                        if departures else 0.0),
            "mail_loaded_t": float(control["mail_loaded_t"]),
            "mail_kg_per_departure": (float(control["mail_loaded_t"]) * 1000 / departures
                                       if departures else 0.0),
            "capacity_status": "WARN_ABOVE_CAPACITY" if load > 1 else "PASS",
            "seat_capacity_source": "; ".join(sorted(seat_sources[key])),
            "payload_scope": "PCAA airline average; not route-observed",
        })

    airport_rows = []
    for control in airport_controls:
        airport = control["airport_icao"]
        reported = float(control["domestic_passengers"])
        modelled = airport_passengers[airport]
        capacity = airport_capacity[airport]
        airport_rows.append({
            "airport_icao": airport,
            "reported_domestic_passengers": reported,
            "reconstructed_named_airline_passengers": modelled,
            "reconstructed_named_airline_seat_capacity": capacity,
            "passenger_control_ratio": modelled / reported if reported else "",
            "implied_capacity_load_factor": modelled / capacity if capacity else "",
            "unallocated_passenger_difference": reported - modelled,
            "interpretation": "airline-average loads applied to Tier C routes",
        })

    departure_rows = []
    resident = {"PIA", "ABQ", "FJL", "SEP", "SIF"}
    for boundary, movement_field in (("domestic", "domestic_commercial_movements"),
                                     ("international", "international_commercial_movements")):
        selected = [r for r in airline_controls if r["traffic_scope"] == boundary]
        airport_equivalent = sum(float(r[movement_field]) for r in airport_controls) / 2.0
        published_departures = sum(float(r["departures"]) for r in selected)
        published_arrivals = sum(float(r["arrivals"]) for r in selected)
        resident_departures = sum(float(r["departures"]) for r in selected
                                  if r["airline_icao"] in resident)
        departure_rows.append({
            "boundary": boundary,
            "airport_movements": airport_equivalent * 2,
            "airport_movements_divided_by_two": airport_equivalent,
            "published_airline_departures": published_departures,
            "published_airline_arrivals": published_arrivals,
            "airline_departures_minus_half_movements": published_departures - airport_equivalent,
            "departures_minus_arrivals": published_departures - published_arrivals,
            "resident_carrier_departures": resident_departures,
            "comparison_scope": "all published airlines; resident subset reported separately",
        })
    return airline_rows, airport_rows, departure_rows


def annual_replication(data, years=(2022, 2023)):
    source = PCAAReconstructedSource()
    airports = {r["airport_icao"]: r for r in _rows("airports.csv")}
    rows = []
    for year in years:
        if year == 2023:
            routes, _residual = source.route_ledger()
            assumption = "FY2023-24 documented route graph"
        else:
            controls = {r["icao"]: float(r["com_dom_mv"]) for r in data.movements_for(year)}
            routes, _residual = coverage.reconstruct([], controls, source.route_weights(), year)
            for stage in routes:
                a, b = airports.get(stage.origin_icao), airports.get(stage.destination_icao)
                if a and b and a["latitude_deg"] and b["latitude_deg"]:
                    stage.great_circle_nm = _distance_km(a, b) / 1.852
            assumption = "FY2023-24 documented graph held constant; FY2022-23 PCAA margins"
        ladder = resolution.compare(data, routes, year=year)
        route_row = next(r for r in ladder if r["model"] == "route_resolved")
        movement_fuel = lto.fuel_tonnes(data, year)["domestic"]
        bridge = {r["scenario"]: r for r in fuel_bridge.reconciliation(data, year)}
        summary = fuel_bridge.benchmark_summary(data, year)
        base = {"fiscal_year": year, "commercial_ocac_jp1_t": summary["commercial_jp1_t"],
                "government_jp1_t": sum(r["tonnes"] for r in data.fuel_sales_for(year)
                                        if r["fuel_type"] == "JP-1" and
                                        r["customer_category"].startswith("Government")),
                "movement_model_fuel_t": movement_fuel,
                "route_resolved_fuel_t": route_row["fuel_t"],
                "route_coverage_share": route_row["coverage_share"],
                "route_network_assumption": assumption,
                "oecd_domestic_co2_t": summary["oecd_domestic_co2_t"],
                "oecd_international_co2_t": summary["oecd_international_co2_t"],
                "combined_boundary_ratio": summary["fuel_over_oecd_total"]}
        for scenario, item in bridge.items():
            base[scenario + "_domestic_fuel_t"] = item["domestic_fuel_t"]
        rows.append(base)
    return rows


def route_activity_scenarios(source=None, assigned_stages=None):
    """Return feasible operator-route matrices for central, minimum and maximum distance."""
    source = source or PCAAReconstructedSource()
    routes, _ = source.route_ledger()
    if assigned_stages is None:
        assigned_stages, _ = source.aircraft_ledger(routes)
    _airport_controls, airline_controls = source.controls()
    supported, _priors = source._supported("domestic")
    named = {r["airline_icao"]: float(r["departures"]) for r in airline_controls
             if r["traffic_scope"] == "domestic" and r["airline_icao"] in supported}
    route_pairs = {(s.origin_icao, s.destination_icao): s for s in routes}
    target_out = defaultdict(float)
    target_in = defaultdict(float)
    for stage in routes:
        target_out[stage.origin_icao] += stage.activity_count
        target_in[stage.destination_icao] += stage.activity_count
    unknown = sum(s.activity_count for s in routes) - sum(named.values())
    operators = sorted(named) + ["UNKNOWN"]
    cells = []
    for operator in operators:
        allowed = set(route_pairs) if operator == "UNKNOWN" else supported[operator]
        cells.extend((operator, pair) for pair in sorted(allowed) if pair in route_pairs)
    constraints, targets = [], []
    for operator in operators:
        constraints.append([1.0 if op == operator else 0.0 for op, _p in cells])
        targets.append(unknown if operator == "UNKNOWN" else named[operator])
    for airport, target in sorted(target_out.items()):
        constraints.append([1.0 if pair[0] == airport else 0.0 for _op, pair in cells])
        targets.append(target)
    for airport, target in sorted(target_in.items()):
        constraints.append([1.0 if pair[1] == airport else 0.0 for _op, pair in cells])
        targets.append(target)
    distances = np.array([route_pairs[pair].great_circle_nm for _op, pair in cells])
    results = []

    central_named = defaultdict(float)
    for stage in assigned_stages:
        if stage.boundary == "domestic" and stage.operator:
            central_named[(stage.operator, stage.origin_icao, stage.destination_icao)] += float(
                stage.activity_count)
    for pair, route in sorted(route_pairs.items()):
        allocated = 0.0
        for operator in sorted(named):
            count = central_named[(operator, pair[0], pair[1])]
            if count > 1e-9:
                results.append({"route_graph": "central_ipf", "operator": operator,
                                "origin_icao": pair[0], "destination_icao": pair[1],
                                "stage_count": count, "distance_nm": route.great_circle_nm})
                allocated += count
        residual = max(0.0, float(route.activity_count) - allocated)
        if residual > 1e-9:
            results.append({"route_graph": "central_ipf", "operator": "UNKNOWN",
                            "origin_icao": pair[0], "destination_icao": pair[1],
                            "stage_count": residual, "distance_nm": route.great_circle_nm})

    for scenario, objective in (("minimum", distances), ("maximum", -distances)):
        solved = linprog(objective, A_eq=np.asarray(constraints), b_eq=np.asarray(targets),
                         bounds=(0, None), method="highs")
        if not solved.success:
            raise RuntimeError("route distance %s LP failed: %s" % (scenario, solved.message))
        for (operator, pair), count in zip(cells, solved.x):
            if count > 1e-9:
                results.append({"route_graph": scenario, "operator": operator,
                                "origin_icao": pair[0], "destination_icao": pair[1],
                                "stage_count": float(count),
                                "distance_nm": route_pairs[pair].great_circle_nm})
    return results


def route_distance_bounds(source=None, assigned_stages=None):
    scenarios = route_activity_scenarios(source, assigned_stages)
    output = []
    for scenario in ("minimum", "central_ipf", "maximum"):
        selected = [row for row in scenarios if row["route_graph"] == scenario]
        stages = sum(row["stage_count"] for row in selected)
        distance = sum(row["stage_count"] * row["distance_nm"] for row in selected)
        output.append({"scenario": scenario, "supported_stages": stages,
                       "total_stage_nm": distance, "mean_stage_nm": distance / stages})
    return output


def common_support_ladder(data, route_stages, assigned_stages, endpoint_residual):
    supported = [s for s in assigned_stages if s.boundary == "domestic" and s.total_fuel_kg > 0]
    unsupported = [s for s in assigned_stages if s.boundary == "domestic" and s.total_fuel_kg <= 0]
    fleet = data.fleet_for("commercial", 2023)
    aggregate_per_stage = lto.fuel_tonnes(data, 2023)["domestic"] * 1000 / lto.lto_cycles(data, 2023)["domestic"]
    common_count = sum(s.activity_count for s in supported)
    common_aggregate = aggregate_per_stage * common_count / 1000
    common_route = sum(sum(share * resolution._factor(data, ac, s.great_circle_nm)
                           for ac, share in fleet.items()) * s.activity_count
                       for s in supported) / 1000
    common_openap = sum(s.total_fuel_kg * s.activity_count for s in supported) / 1000
    common = [{"experiment": "common_support", "step": name,
               "stage_count": common_count, "stage_coverage": common_count / 20300,
               "fuel_t": value, "fuel_coverage": 1.0,
               "activity_definition": "identical native-OpenAP-supported strata"}
              for name, value in (("aggregate_factor", common_aggregate),
                                  ("route_distance", common_route),
                                  ("route_aircraft_openap", common_openap))]
    unsupported_fuel = 0.0
    for stage in unsupported:
        aircraft = data.inventory_aircraft(stage.aircraft_type)
        unsupported_fuel += resolution._factor(data, aircraft, stage.great_circle_nm) * stage.activity_count / 1000
    assigned_by_route = defaultdict(float)
    for stage in assigned_stages:
        if stage.boundary == "domestic":
            assigned_by_route[(stage.origin_icao, stage.destination_icao)] += stage.activity_count
    route_residual_fuel = 0.0
    route_residual_count = 0.0
    for stage in route_stages:
        residual = max(0.0, stage.activity_count - assigned_by_route[(stage.origin_icao, stage.destination_icao)])
        route_residual_count += residual
        route_residual_fuel += sum(share * resolution._factor(data, ac, stage.great_circle_nm)
                                   for ac, share in fleet.items()) * residual / 1000
    endpoint_count = sum(s.activity_count for s in endpoint_residual) / 2.0
    endpoint_fuel = endpoint_count * aggregate_per_stage / 1000
    components = (("native_openap", common_count, common_openap),
                  ("unsupported_aircraft_icao_imputation", sum(s.activity_count for s in unsupported), unsupported_fuel),
                  ("supported_route_operator_residual", route_residual_count, route_residual_fuel),
                  ("endpoint_residual_aggregate_imputation", endpoint_count, endpoint_fuel))
    completed = sum(fuel for _name, _count, fuel in components)
    completion = [{"experiment": "coverage_completion", "step": name,
                   "stage_count": count, "stage_coverage": count / 20300,
                   "fuel_t": fuel, "fuel_coverage": fuel / completed,
                   "activity_definition": "mutually exclusive completion component"}
                  for name, count, fuel in components]
    completion.append({"experiment": "coverage_completion", "step": "completed_total",
                       "stage_count": sum(c for _n, c, _f in components),
                       "stage_coverage": sum(c for _n, c, _f in components) / 20300,
                       "fuel_t": completed, "fuel_coverage": 1.0,
                       "activity_definition": "sum of completion components"})
    return common + completion


def independence_matrix():
    return [
        {"comparison": "Movement model vs OECD domestic", "purpose": "external territory comparison",
         "shared_inputs": "possible ICAO performance conventions", "independence": "partial", "calibration": "no"},
        {"comparison": "Fuel bridge vs OECD domestic", "purpose": "partition consistency",
         "shared_inputs": "OECD resident share directly used", "independence": "none", "calibration": "yes"},
        {"comparison": "OCAC total vs OECD combined", "purpose": "gross-boundary closure",
         "shared_inputs": "carbon conversion only", "independence": "large", "calibration": "no"},
        {"comparison": "Pakistan CRT vs OECD", "purpose": "official-boundary diagnostic",
         "shared_inputs": "inventory year only", "independence": "large", "calibration": "no"},
        {"comparison": "PCAA airports vs Climate TRACE", "purpose": "spatial corroboration",
         "shared_inputs": "possible surveillance and performance inputs", "independence": "partial", "calibration": "no"},
        {"comparison": "ADSB.lol vs PCAA daily rate", "purpose": "observed-data coverage pilot",
         "shared_inputs": "airport coordinates only", "independence": "large but incomplete", "calibration": "no"},
        {"comparison": "ERA5 duration vs OpenAP still air", "purpose": "weather sensitivity",
         "shared_inputs": "same OpenAP fuel and synthetic route", "independence": "not validation", "calibration": "no"},
        {"comparison": "PCAA movements vs passenger load", "purpose": "movement divisor check",
         "shared_inputs": "PCAA reporting system", "independence": "limited targeted", "calibration": "no"},
    ]
