"""Parametric Monte Carlo and discrete structural scenarios for aviation."""
import math
import random
from collections import defaultdict

from pkinv.core import montecarlo as mc_core
from pkinv.sectors.aviation import engine, fuel_bridge, lto, resolution

N_ITER = mc_core.N_ITER
SEED = mc_core.SEED


def factor_table(data):
    return [
        {"factor": "Aircraft movements", "value": 1.0, "unit": "multiplier",
         "uncert_pct_95": data.p("activity_uncert"), "uncertainty_type": "parametric",
         "distribution": "lognormal", "note": "Aggregate activity and fleet assignment"},
        {"factor": "Representative domestic stage length",
         "value": data.p("domestic_stage_length_nm"), "unit": "nautical miles",
         "uncert_pct_95": data.pu("domestic_stage_length_nm"),
         "uncertainty_type": "parametric", "distribution": "lognormal",
         "note": "One stage length represents the route network"},
        {"factor": "Jet-fuel carbon conversion", "value": data.p("co2_per_t_fuel"),
         "unit": "t CO2/t fuel", "uncert_pct_95": data.pu("co2_per_t_fuel"),
         "uncertainty_type": "parametric", "distribution": "lognormal",
         "note": "Shared by movement and fuel-control estimates"},
        {"factor": "Customer class to flight geography", "value": "three scenarios",
         "unit": "configuration", "uncert_pct_95": "",
         "uncertainty_type": "structural", "distribution": "discrete",
         "note": "Literal label, movement share, and OECD flight-fuel share"},
        {"factor": "Non-commercial classification", "value": "unresolved",
         "unit": "configuration", "uncert_pct_95": "",
         "uncertainty_type": "structural", "distribution": "not sampled",
         "note": "Government, military, training, and general aviation remain separate"},
    ]


def _lognormal(rng, mean, uncert_pct):
    sigma = mc_core.sigma_log(uncert_pct)
    return mean * math.exp(rng.gauss(0.0, 1.0) * sigma - sigma * sigma / 2.0)


def run(data, year=None, n_iter=N_ITER, seed=SEED):
    """Return one parametric interval per structural scenario plus movement model."""
    year = data.year if year is None else year
    movement_stats, _ = mc_core.run(engine.build_components(data, year),
                                    engine.CATEGORIES, n_iter=n_iter, seed=seed)
    result = [{"fiscal_year": year, "model": "aggregate_movement",
               "structural_scenario": "representative_stage",
               "mean_Mt": movement_stats["TOTAL"]["mean"],
               "P2.5_Mt": movement_stats["TOTAL"]["p025"],
               "P50_Mt": movement_stats["TOTAL"]["p50"],
               "P97.5_Mt": movement_stats["TOTAL"]["p975"],
               "parametric_inputs": "activity, stage length, emission factors"}]
    reconciled = {r["scenario"]: r for r in fuel_bridge.reconciliation(data, year)}
    for index, scenario in enumerate(fuel_bridge.SCENARIOS):
        central = reconciled[scenario]["domestic_co2_Gg"] / 1000.0
        rng = random.Random(seed + index + 1)
        samples = sorted(_lognormal(rng, central, data.pu("co2_per_t_fuel"))
                         for _ in range(n_iter))
        result.append({"fiscal_year": year, "model": "fuel_bridge",
                       "structural_scenario": scenario,
                       "mean_Mt": sum(samples) / len(samples),
                       "P2.5_Mt": mc_core.percentile(samples, 0.025),
                       "P50_Mt": mc_core.percentile(samples, 0.5),
                       "P97.5_Mt": mc_core.percentile(samples, 0.975),
                       "parametric_inputs": "fuel-carbon conversion only; mapping is structural"})
    return result


def decomposition(data):
    """Expose the three multiplicative terms behind the aggregate historical result."""
    rows = []
    for year in sorted({r["year"] for r in data.movements}):
        cycles = lto.lto_cycles(data, year)
        fuel = lto.fuel_tonnes(data, year)
        rows.append({"fiscal_year": year, "flight_stages": cycles["domestic"],
                     "mean_stage_nm": data.p("domestic_stage_length_nm"),
                     "mean_fuel_kg_per_stage": (fuel["domestic"] * 1000.0 /
                                                cycles["domestic"] if cycles["domestic"] else 0),
                     "domestic_fuel_t": fuel["domestic"],
                     "domestic_co2_kt": fuel["domestic"] * data.p("co2_per_t_fuel") / 1000.0})
    return rows


def flight_factor_table(data):
    """Factors added by the flight-stage model; definitions remain invariants."""
    return [
        {"factor": "OpenAP initial mass/payload", "uncert_pct_95":
         data.pu("openap_default_mass_fraction_mtow"), "distribution": "lognormal",
         "correlation": "aircraft family", "uncertainty_type": "parametric"},
        {"factor": "Modelled-route detour", "uncert_pct_95":
         data.pu("openap_route_detour_factor"), "distribution": "lognormal",
         "correlation": "origin-destination", "uncertainty_type": "parametric"},
        {"factor": "Taxi time", "uncert_pct_95": max(
            data.pu("openap_default_taxi_out_s"), data.pu("openap_default_taxi_in_s")),
         "distribution": "lognormal", "correlation": "airport-month",
         "uncertainty_type": "parametric"},
        {"factor": "OpenSky/PCAA missing-flight reconstruction", "uncert_pct_95": "",
         "distribution": "discrete", "correlation": "airport-month",
         "uncertainty_type": "structural"},
        {"factor": "Aircraft assignment for unmatched registrations", "uncert_pct_95": "",
         "distribution": "discrete", "correlation": "route/operator",
         "uncertainty_type": "structural"},
    ]


def full_factor_table(data, route_bounds=None):
    """Complete, manuscript-ready uncertainty register.

    Percent ranges are approximate 95% input ranges.  Discrete choices are kept
    unsampled so a confidence interval cannot conceal a boundary or coverage choice.
    """
    bounds = {r["scenario"]: r for r in (route_bounds or [])}
    central_nm = bounds.get("central_ipf", {}).get(
        "mean_stage_nm", data.p("domestic_stage_length_nm"))
    route_range = ""
    route_uncert = ""
    if "minimum" in bounds and "maximum" in bounds:
        route_range = "%.1f--%.1f" % (bounds["minimum"]["mean_stage_nm"],
                                      bounds["maximum"]["mean_stage_nm"])
        route_uncert = max(abs(bounds["minimum"]["mean_stage_nm"] / central_nm - 1),
                           abs(bounds["maximum"]["mean_stage_nm"] / central_nm - 1)) * 100
    return [
        {"variable": "Official domestic commercial movements", "central_value": 40600,
         "range_95": "reported control (conditional)", "uncert_pct_95": "",
         "distribution": "not sampled", "source": "PCAA airport controls FY2023-24",
         "applicable_model": "M0--M2", "correlation_group": "fiscal-year activity",
         "uncertainty_class": "parametric"},
        {"variable": "Aggregate activity/fleet representation", "central_value": 1.0,
         "range_95": "+/- %.1f%%" % data.p("activity_uncert"),
         "uncert_pct_95": data.p("activity_uncert"), "distribution": "lognormal",
         "source": data.ps("activity_uncert"), "applicable_model": "M0",
         "correlation_group": "fiscal-year aggregate model", "uncertainty_class": "parametric"},
        {"variable": "Constrained route-matrix mean distance", "central_value": central_nm,
         "range_95": route_range, "uncert_pct_95": route_uncert,
         "distribution": "bounded structural envelope", "source": "PCAA airport/airline margins and documented route graph",
         "applicable_model": "M1--M2", "correlation_group": "route matrix",
         "uncertainty_class": "structural"},
        {"variable": "Aggregate representative stage length", "central_value": data.p("domestic_stage_length_nm"),
         "range_95": "+/- %.1f%%" % data.pu("domestic_stage_length_nm"),
         "uncert_pct_95": data.pu("domestic_stage_length_nm"), "distribution": "lognormal",
         "source": data.ps("domestic_stage_length_nm"), "applicable_model": "M0",
         "correlation_group": "all domestic stages", "uncertainty_class": "parametric"},
        {"variable": "Airline-aircraft family assignment", "central_value": "documented family shares",
         "range_95": "documented aircraft-family support", "uncert_pct_95": "",
         "distribution": "categorical draw by operator and unordered route", "source": "FY2023-24 fleet histories and route suitability",
         "applicable_model": "M2", "correlation_group": "operator-route",
         "uncertainty_class": "parametric"},
        {"variable": "PCAA-constrained passenger/cargo/mail payload", "central_value": "operator embarked load per departure",
         "range_95": "min(62.5%, observed); observed; max(87.5%, observed)", "uncert_pct_95": "",
         "distribution": "triangular interpolation over modelled payload cases",
         "source": "PCAA airline passengers, loaded cargo and loaded mail", "applicable_model": "M2",
         "correlation_group": "operator-route", "uncertainty_class": "parametric"},
        {"variable": "Synthetic-route detour multiplier", "central_value": data.p("openap_route_detour_factor"),
         "range_95": "+/- %.1f%%" % data.pu("openap_route_detour_factor"),
         "uncert_pct_95": data.pu("openap_route_detour_factor"), "distribution": "lognormal",
         "source": data.ps("openap_route_detour_factor"), "applicable_model": "M2",
         "correlation_group": "origin-destination", "uncertainty_class": "parametric"},
        {"variable": "Taxi-in/out time", "central_value": "%g/%g s" % (
            data.p("openap_default_taxi_in_s"), data.p("openap_default_taxi_out_s")),
         "range_95": "+/- %.1f%%" % max(data.pu("openap_default_taxi_in_s"),
                                          data.pu("openap_default_taxi_out_s")),
         "uncert_pct_95": max(data.pu("openap_default_taxi_in_s"),
                                data.pu("openap_default_taxi_out_s")), "distribution": "lognormal",
         "source": data.ps("openap_default_taxi_out_s"), "applicable_model": "M2/airport LTO",
         "correlation_group": "airport-month", "uncertainty_class": "parametric"},
        {"variable": "Unsupported-aircraft fuel imputation", "central_value": "ICAO stage factor",
         "range_95": "OpenAP/ICAO assignment scenarios", "uncert_pct_95": "",
         "distribution": "discrete", "source": "ICAO Carbon Emissions Calculator stage factors",
         "applicable_model": "coverage completion", "correlation_group": "aircraft family",
         "uncertainty_class": "structural"},
        {"variable": "Jet-fuel carbon conversion", "central_value": data.p("co2_per_t_fuel"),
         "range_95": "+/- %.1f%%" % data.pu("co2_per_t_fuel"),
         "uncert_pct_95": data.pu("co2_per_t_fuel"), "distribution": "lognormal",
         "source": data.ps("co2_per_t_fuel"), "applicable_model": "all CO2 products",
         "correlation_group": "all jet fuel", "uncertainty_class": "parametric"},
        {"variable": "CH4 emission factor", "central_value": data.p("ch4_kg_per_tj"),
         "range_95": "+/- %.1f%%" % data.pu("ch4_kg_per_tj"),
         "uncert_pct_95": data.pu("ch4_kg_per_tj"), "distribution": "lognormal",
         "source": data.ps("ch4_kg_per_tj"), "applicable_model": "GHG supplement",
         "correlation_group": "all jet fuel", "uncertainty_class": "parametric"},
        {"variable": "N2O emission factor", "central_value": data.p("n2o_kg_per_tj"),
         "range_95": "+/- %.1f%%" % data.pu("n2o_kg_per_tj"),
         "uncert_pct_95": data.pu("n2o_kg_per_tj"), "distribution": "lognormal",
         "source": data.ps("n2o_kg_per_tj"), "applicable_model": "GHG supplement",
         "correlation_group": "all jet fuel", "uncertainty_class": "parametric"},
        {"variable": "Customer class to flight geography", "central_value": "OECD-calibrated resident share",
         "range_95": "literal, movement, common-share, carrier-specific", "uncert_pct_95": "",
         "distribution": "discrete", "source": "OCAC ledger; PCAA/OECD bridge",
         "applicable_model": "fuel bridge", "correlation_group": "source row",
         "uncertainty_class": "structural"},
        {"variable": "Incomplete international flight-stage coverage", "central_value": "27.9% departures reconstructed",
         "range_95": "partial model versus aggregate residual", "uncert_pct_95": "",
         "distribution": "discrete", "source": "PCAA airline controls and reconstruction coverage",
         "applicable_model": "M2 carrier fuel share", "correlation_group": "operator-route",
         "uncertainty_class": "structural"},
        {"variable": "ERA5 duration adjustment", "central_value": "still-air primary interval",
         "range_95": "bootstrap of six-route audit", "uncert_pct_95": "",
         "distribution": "empirical bootstrap", "source": "ERA5 representative-route audit",
         "applicable_model": "M2 weather-augmented interval", "correlation_group": "all native non-taxi fuel",
         "uncertainty_class": "parametric"},
    ]


def one_at_a_time_sensitivity(data, stages, completed_fuel_t, route_bounds=None):
    """One-at-a-time screening around the completed domestic flight-stage estimate."""
    native = [s for s in stages if s.boundary == "domestic" and s.total_fuel_kg > 0]
    native_fuel = sum(s.total_fuel_kg * s.activity_count for s in native) / 1000.0
    taxi_fuel = sum(s.taxi_fuel_kg * s.activity_count for s in native) / 1000.0
    non_taxi = native_fuel - taxi_fuel
    imputed = max(0.0, completed_fuel_t - native_fuel)
    central_co2 = completed_fuel_t * data.p("co2_per_t_fuel")
    bounds = {r["scenario"]: r for r in (route_bounds or [])}
    central_nm = bounds.get("central_ipf", {}).get("mean_stage_nm", 1.0)
    route_low = bounds.get("minimum", {}).get("mean_stage_nm", central_nm) / central_nm
    route_high = bounds.get("maximum", {}).get("mean_stage_nm", central_nm) / central_nm
    specifications = [
        ("Route-matrix distance envelope", route_low, route_high, non_taxi,
         "native non-taxi fuel"),
        ("Synthetic-route detour", 1 - data.pu("openap_route_detour_factor") / 100,
         1 + data.pu("openap_route_detour_factor") / 100, non_taxi,
         "native non-taxi fuel"),
        ("Taxi time", 1 - data.pu("openap_default_taxi_out_s") / 100,
         1 + data.pu("openap_default_taxi_out_s") / 100, taxi_fuel,
         "native taxi fuel"),
        ("Unsupported-aircraft/residual imputation", 0.5, 1.5, imputed,
         "coverage-completion fuel"),
    ]
    output = []
    for variable, low_multiplier, high_multiplier, affected_fuel, scope in specifications:
        base_unaffected = completed_fuel_t - affected_fuel
        low = (base_unaffected + affected_fuel * low_multiplier) * data.p("co2_per_t_fuel")
        high = (base_unaffected + affected_fuel * high_multiplier) * data.p("co2_per_t_fuel")
        output.append({"variable": variable, "central_co2_t": central_co2,
                       "low_co2_t": low, "high_co2_t": high,
                       "max_absolute_change_pct": max(abs(low / central_co2 - 1),
                                                       abs(high / central_co2 - 1)) * 100,
                       "affected_fuel_t": affected_fuel, "scope": scope,
                       "method": "one-at-a-time screening; not a Sobol index"})
    carbon_pct = data.pu("co2_per_t_fuel")
    output.append({"variable": "Jet-fuel carbon conversion", "central_co2_t": central_co2,
                   "low_co2_t": central_co2 * (1 - carbon_pct / 100),
                   "high_co2_t": central_co2 * (1 + carbon_pct / 100),
                   "max_absolute_change_pct": carbon_pct,
                   "affected_fuel_t": completed_fuel_t, "scope": "all completed fuel",
                   "method": "one-at-a-time screening; not a Sobol index"})
    return sorted(output, key=lambda r: r["max_absolute_change_pct"], reverse=True)


def _flight_groups(stages, include_reconstructed=True):
    groups = defaultdict(lambda: [0.0, 0.0])  # non-taxi kg, taxi kg
    for stage in stages:
        if not include_reconstructed and stage.source_tier in ("C", "D"):
            continue
        key = (stage.aircraft_type or "unknown", stage.origin_icao, stage.destination_icao,
               stage.operator or "unknown", stage.source_tier)
        groups[key][0] += ((stage.total_fuel_kg - stage.taxi_fuel_kg) *
                           stage.activity_count)
        groups[key][1] += stage.taxi_fuel_kg * stage.activity_count
    return groups


def run_flight_ledger(data, stages, n_iter=N_ITER, seed=SEED):
    """Monte Carlo within separate complete-ledger and observed-only structures.

    Shared multipliers are drawn once per aircraft family and route in each iteration,
    retaining the correlations lost by applying one uncertainty percentage per flight.
    """
    rows = []
    for scenario_index, (scenario, include_reconstructed) in enumerate(
            (("completed_ledger", True), ("observed_only", False))):
        groups = _flight_groups(stages, include_reconstructed)
        rng = random.Random(seed + 100 + scenario_index)
        samples = []
        for _ in range(n_iter):
            carbon = _lognormal(rng, data.p("co2_per_t_fuel"), data.pu("co2_per_t_fuel"))
            by_aircraft = {key[0]: _lognormal(rng, 1.0,
                           data.pu("openap_default_mass_fraction_mtow")) for key in groups}
            by_route = {(key[1], key[2]): _lognormal(rng, 1.0,
                        data.pu("openap_route_detour_factor")) for key in groups}
            taxi = _lognormal(rng, 1.0, max(data.pu("openap_default_taxi_out_s"),
                                             data.pu("openap_default_taxi_in_s")))
            fuel_kg = sum(non_taxi * by_aircraft[key[0]] * by_route[(key[1], key[2])] +
                          taxi_kg * taxi for key, (non_taxi, taxi_kg) in groups.items())
            samples.append(fuel_kg / 1e9 * carbon)  # kg fuel -> Mt CO2
        samples.sort()
        rows.append({"fiscal_year": data.year, "model": "flight_ledger",
                     "structural_scenario": scenario, "mean_Mt": sum(samples) / len(samples),
                     "P2.5_Mt": mc_core.percentile(samples, 0.025),
                     "P50_Mt": mc_core.percentile(samples, 0.5),
                     "P97.5_Mt": mc_core.percentile(samples, 0.975),
                     "parametric_inputs": "carbon, aircraft-mass, route-detour, taxi"})
    return rows


def _triangular_quantile(q, low, mode, high):
    """Inverse triangular CDF, including one-sided observed-load cases."""
    if high <= low:
        return low
    mode = min(high, max(low, mode))
    split = (mode - low) / (high - low)
    if q < split and split > 0:
        return low + math.sqrt(q * (high - low) * (mode - low))
    if split >= 1:
        return high
    return high - math.sqrt((1 - q) * (high - low) * (high - mode))


def _linear(points, x, field):
    points = sorted(points, key=lambda row: float(row["passenger_load_fraction"]))
    if x <= float(points[0]["passenger_load_fraction"]):
        return float(points[0][field])
    if x >= float(points[-1]["passenger_load_fraction"]):
        return float(points[-1][field])
    for left, right in zip(points, points[1:]):
        lo, hi = (float(left["passenger_load_fraction"]),
                  float(right["passenger_load_fraction"]))
        if lo <= x <= hi:
            if hi == lo:
                return float(right[field])
            weight = (x - lo) / (hi - lo)
            return float(left[field]) * (1 - weight) + float(right[field]) * weight
    raise AssertionError("payload interpolation fell outside lookup")


def _aircraft_shares(rows, operator, boundary="domestic"):
    selected = [row for row in rows if row["airline_icao"] == operator and
                row["origin_icao"] in ("*", boundary) and
                row["destination_icao"] in ("*", boundary)]
    total = sum(float(row["share"]) for row in selected)
    return [(row["aircraft_type"], float(row["share"]) / total) for row in selected] if total else []


def _categorical(rng, choices):
    q, cumulative = rng.random(), 0.0
    for value, probability in choices:
        cumulative += probability
        if q <= cumulative:
            return value
    return choices[-1][0]


def _sample_sd(values):
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / (len(values) - 1))


def _summary(samples):
    ordered = sorted(samples)
    mean = sum(ordered) / len(ordered)
    return {"mean_Mt": mean, "P2.5_Mt": mc_core.percentile(ordered, 0.025),
            "P50_Mt": mc_core.percentile(ordered, 0.5),
            "P97.5_Mt": mc_core.percentile(ordered, 0.975),
            "sd_Mt": _sample_sd(ordered)}


def _completed_m2_configuration(data, route_rows, endpoint_count, lookup_rows,
                                share_rows, completion_method, weather_effects,
                                n_iter, seed, freeze=frozenset()):
    """Draw one route-graph/completion configuration with declared correlations."""
    by_key = defaultdict(list)
    for row in lookup_rows:
        if row["boundary"] == "domestic":
            key = (row["airline_icao"], row["origin_icao"],
                   row["destination_icao"], row["aircraft_type"])
            by_key[key].append(row)
    central_by_route = defaultdict(list)
    for key, rows in by_key.items():
        central = next((row for row in rows if row["payload_scenario"] == "central"), None)
        if central:
            central_by_route[(key[1], key[2])].append(float(central["total_fuel_kg"]))

    aggregate_per_stage = (lto.fuel_tonnes(data, 2023)["domestic"] * 1000.0 /
                           lto.lto_cycles(data, 2023)["domestic"])
    fleet = data.fleet_for("commercial", 2023)
    taxi_out_fraction = (data.p("openap_default_taxi_out_s") /
                         (data.p("openap_default_taxi_out_s") +
                          data.p("openap_default_taxi_in_s")))
    taxi_in_fraction = 1 - taxi_out_fraction
    weather_values = [1 + float(value) / 100.0 for value in weather_effects] or [1.0]
    rng = random.Random(seed)
    output = {"primary_co2": [], "primary_co2e": [],
              "weather_co2": [], "weather_co2e": []}

    for _ in range(n_iter):
        aircraft_draw, payload_draw, detour_draw, taxi_draw = {}, {}, {}, {}
        carbon = (data.p("co2_per_t_fuel") if "carbon" in freeze else
                  _lognormal(rng, data.p("co2_per_t_fuel"), data.pu("co2_per_t_fuel")))
        ncv = _lognormal(rng, data.p("jet_kerosene_ncv"), data.pu("jet_kerosene_ncv"))
        ch4_ef = _lognormal(rng, data.p("ch4_kg_per_tj"), data.pu("ch4_kg_per_tj"))
        n2o_ef = _lognormal(rng, data.p("n2o_kg_per_tj"), data.pu("n2o_kg_per_tj"))
        native_non_taxi, native_taxi, completion_fuel = 0.0, 0.0, 0.0

        for route in route_rows:
            operator = route["operator"]
            origin, destination = route["origin_icao"], route["destination_icao"]
            count, distance = float(route["stage_count"]), float(route["distance_nm"])
            unordered = tuple(sorted((origin, destination)))
            if operator == "UNKNOWN":
                if completion_method == "all_m0":
                    per_stage = aggregate_per_stage
                elif completion_method == "openap_analogue" and central_by_route[(origin, destination)]:
                    per_stage = (sum(central_by_route[(origin, destination)]) /
                                 len(central_by_route[(origin, destination)]))
                else:
                    per_stage = sum(share * resolution._factor(data, ac, distance)
                                    for ac, share in fleet.items())
                completion_fuel += per_stage * count
                continue

            shared_key = (operator, unordered)
            choices = _aircraft_shares(share_rows, operator)
            if not choices:
                completion_fuel += aggregate_per_stage * count
                continue
            if shared_key not in aircraft_draw:
                aircraft_draw[shared_key] = (max(choices, key=lambda item: item[1])[0]
                                             if "aircraft" in freeze else
                                             _categorical(rng, choices))
            aircraft = aircraft_draw[shared_key]
            lookup = by_key.get((operator, origin, destination, aircraft), [])
            if not lookup:
                if completion_method == "all_m0":
                    per_stage = aggregate_per_stage
                elif completion_method == "openap_analogue":
                    analogues = [rows for (op, a, b, _ac), rows in by_key.items()
                                 if op == operator and a == origin and b == destination]
                    central_values = [float(next(row for row in rows
                                      if row["payload_scenario"] == "central")["total_fuel_kg"])
                                      for rows in analogues]
                    per_stage = (sum(central_values) / len(central_values)
                                 if central_values else aggregate_per_stage)
                else:
                    per_stage = resolution._factor(data, data.inventory_aircraft(aircraft), distance)
                completion_fuel += per_stage * count
                continue

            loads = [float(row["passenger_load_fraction"]) for row in lookup]
            central = next(row for row in lookup if row["payload_scenario"] == "central")
            if shared_key not in payload_draw:
                payload_draw[shared_key] = (float(central["passenger_load_fraction"])
                                            if "payload" in freeze else
                                            _triangular_quantile(rng.random(), min(loads),
                                                float(central["passenger_load_fraction"]), max(loads)))
            load = payload_draw[shared_key]
            total = _linear(lookup, load, "total_fuel_kg")
            taxi = _linear(lookup, load, "taxi_fuel_kg")
            if unordered not in detour_draw:
                detour_draw[unordered] = (1.0 if "detour" in freeze else
                    _lognormal(rng, 1.0, data.pu("openap_route_detour_factor")))
            for airport in (origin, destination):
                if airport not in taxi_draw:
                    taxi_draw[airport] = (1.0 if "taxi" in freeze else
                        _lognormal(rng, 1.0, max(data.pu("openap_default_taxi_out_s"),
                                                 data.pu("openap_default_taxi_in_s"))))
            adjusted_non_taxi = (total - taxi) * detour_draw[unordered]
            adjusted_taxi = taxi * (taxi_out_fraction * taxi_draw[origin] +
                                    taxi_in_fraction * taxi_draw[destination])
            native_non_taxi += adjusted_non_taxi * count
            native_taxi += adjusted_taxi * count

        completion_fuel += endpoint_count * aggregate_per_stage
        primary_fuel_t = (native_non_taxi + native_taxi + completion_fuel) / 1000.0
        weather = 1.0 if "weather" in freeze else weather_values[rng.randrange(len(weather_values))]
        weather_fuel_t = (native_non_taxi * weather + native_taxi + completion_fuel) / 1000.0
        for label, fuel_t in (("primary", primary_fuel_t), ("weather", weather_fuel_t)):
            co2_t = fuel_t * carbon
            energy_tj = fuel_t * ncv / 1000.0
            co2e_t = co2_t + energy_tj * ch4_ef / 1000.0 * 30.0 + energy_tj * n2o_ef / 1000.0 * 265.0
            output[label + "_co2"].append(co2_t / 1e6)
            output[label + "_co2e"].append(co2e_t / 1e6)
    return output


def run_completed_m2(data, route_scenarios, endpoint_count, lookup_rows, share_rows,
                     weather_effects, n_iter=20000, seed=20230806):
    """Full completed-M2 intervals plus a distinct structural envelope.

    Route graphs and completion algorithms are configurations, never random draws.
    The legacy aggregate ±60% representation term is deliberately absent.
    """
    intervals = []
    configurations = (("current", "current_icao_route_m1_endpoint_m0"),
                      ("openap_analogue", "route_matched_openap_analogue"),
                      ("all_m0", "all_missing_stages_m0"))
    grouped = defaultdict(list)
    for row in route_scenarios:
        grouped[row["route_graph"]].append(row)
    for graph_index, graph in enumerate(("minimum", "central_ipf", "maximum")):
        for method_index, (method, label) in enumerate(configurations):
            samples = _completed_m2_configuration(
                data, grouped[graph], endpoint_count, lookup_rows, share_rows,
                method, weather_effects, n_iter, seed + graph_index * 100 + method_index)
            for interval_type, sample_key in (("primary", "primary"),
                                               ("weather_augmented", "weather")):
                for metric in ("co2", "co2e"):
                    stats = _summary(samples[sample_key + "_" + metric])
                    first = _summary(samples[sample_key + "_" + metric][:n_iter // 2])
                    second = _summary(samples[sample_key + "_" + metric][n_iter // 2:])
                    intervals.append({
                        "fiscal_year": 2023, "model": "completed_M2",
                        "route_graph": graph, "completion_method": label,
                        "interval_type": interval_type, "metric": metric.upper(),
                        **stats, "iterations": n_iter, "seed": seed + graph_index * 100 + method_index,
                        "stage_count": sum(float(row["stage_count"]) for row in grouped[graph]) + endpoint_count,
                        "half_sample_p50_difference_pct": (abs(first["P50_Mt"] - second["P50_Mt"]) /
                                                            stats["P50_Mt"] * 100),
                        "parametric_inputs": "aircraft assignment; PCAA payload; detour; airport taxi; fuel factors" +
                        ("; sampled ERA5 duration effect" if interval_type == "weather_augmented" else ""),
                    })

    envelope = []
    for interval_type in ("primary", "weather_augmented"):
        for metric in ("CO2", "CO2E"):
            selected = [row for row in intervals if row["interval_type"] == interval_type and
                        row["metric"] == metric]
            low = min(selected, key=lambda row: row["P2.5_Mt"])
            high = max(selected, key=lambda row: row["P97.5_Mt"])
            envelope.append({
                "fiscal_year": 2023, "model": "completed_M2",
                "interval_type": interval_type, "metric": metric,
                "structural_low_Mt": low["P2.5_Mt"],
                "structural_high_Mt": high["P97.5_Mt"],
                "low_configuration": low["route_graph"] + "/" + low["completion_method"],
                "high_configuration": high["route_graph"] + "/" + high["completion_method"],
                "interpretation": "scenario envelope across route graph and completion method; not a confidence interval",
            })

    central_rows = grouped["central_ipf"]
    base = _completed_m2_configuration(data, central_rows, endpoint_count, lookup_rows,
                                       share_rows, "current", weather_effects,
                                       min(5000, n_iter), seed + 900)
    base_variance = _sample_sd(base["primary_co2"]) ** 2
    contributions = []
    for index, group in enumerate(("aircraft", "payload", "detour", "taxi", "carbon")):
        frozen = _completed_m2_configuration(data, central_rows, endpoint_count, lookup_rows,
                                             share_rows, "current", weather_effects,
                                             min(5000, n_iter), seed + 901 + index,
                                             freeze=frozenset({group}))
        variance = _sample_sd(frozen["primary_co2"]) ** 2
        contributions.append({
            "uncertainty_group": group, "full_variance_Mt2": base_variance,
            "variance_with_group_frozen_Mt2": variance,
            "variance_reduction_pct": max(0.0, (1 - variance / base_variance) * 100) if base_variance else 0.0,
            "method": "drop-one variance reduction screen; contributions are not additive",
            "iterations": min(5000, n_iter),
        })
    return intervals, envelope, sorted(contributions,
                                       key=lambda row: row["variance_reduction_pct"], reverse=True)
