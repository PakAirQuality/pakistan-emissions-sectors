"""Process-matched tabular products derived from the flight ledger."""
from collections import defaultdict
from datetime import datetime, timezone

from pkinv.sectors.aviation.performance import PHASE_FIELDS


def monthly(stages, co2_per_t_fuel):
    totals = defaultdict(lambda: {"flight_stages": 0, "fuel_t": 0.0})
    for stage in stages:
        month = (datetime.fromtimestamp(stage.first_seen, timezone.utc).strftime("%Y-%m")
                 if stage.first_seen else "FY%d-%02d" %
                 (stage.fiscal_year, (stage.fiscal_year + 1) % 100))
        key = (month, stage.boundary, stage.source_tier)
        totals[key]["flight_stages"] += stage.activity_count
        totals[key]["fuel_t"] += stage.total_fuel_kg * stage.activity_count / 1000.0
    return [{"period": key[0], "boundary": key[1], "source_tier": key[2],
             "flight_stages": value["flight_stages"], "fuel_t": value["fuel_t"],
             "co2_kt": value["fuel_t"] * co2_per_t_fuel / 1000.0}
            for key, value in sorted(totals.items())]


def phase_totals(stages, co2_per_t_fuel):
    totals = defaultdict(float)
    for stage in stages:
        for phase_name, field in PHASE_FIELDS.items():
            totals[(stage.boundary, phase_name)] += (getattr(stage, field) *
                                                      stage.activity_count / 1000.0)
    return [{"boundary": key[0], "phase": key[1], "fuel_t": fuel,
             "co2_kt": fuel * co2_per_t_fuel / 1000.0}
            for key, fuel in sorted(totals.items())]


def airport_lto(stages, co2_per_t_fuel):
    """Allocate physical main-engine LTO fuel to its actual endpoint airport."""
    totals = defaultdict(float)
    for stage in stages:
        # Taxi is split until separate taxi-in/out integration is available.
        weight = stage.activity_count
        totals[(stage.origin_icao, stage.boundary, "taxi")] += stage.taxi_fuel_kg * weight / 2000.0
        totals[(stage.destination_icao, stage.boundary, "taxi")] += stage.taxi_fuel_kg * weight / 2000.0
        totals[(stage.origin_icao, stage.boundary, "takeoff")] += stage.takeoff_fuel_kg * weight / 1000.0
        totals[(stage.destination_icao, stage.boundary, "landing")] += stage.landing_fuel_kg * weight / 1000.0
    return [{"airport_icao": key[0], "boundary": key[1], "phase": key[2],
             "fuel_t": fuel, "co2_kt": fuel * co2_per_t_fuel / 1000.0,
             "taxi_split_assumption": "50/50 taxi-in/out" if key[2] == "taxi" else ""}
            for key, fuel in sorted(totals.items()) if key[0]]


def accounting_views(stages, data, physical_fuel_kg=None):
    """Four definitions that must never be collapsed into one aviation total."""
    values = {
        "UNFCCC domestic aviation": sum(s.total_fuel_kg * s.activity_count for s in stages if s.boundary == "domestic"),
        "International aviation bunkers": sum(s.total_fuel_kg * s.activity_count for s in stages if s.boundary == "international"),
        "Resident-carrier worldwide departures": sum(
            s.total_fuel_kg * s.activity_count for s in stages
            if data.operator_by_icao.get((s.operator or s.callsign[:3]).upper(), {}).get("residence")
            == "Pakistan"),
    }
    if physical_fuel_kg is not None:
        values["Physical emissions over Pakistan"] = physical_fuel_kg
    return [{"accounting_view": name, "fuel_t": kg / 1000.0,
             "co2_kt": kg / 1000.0 * data.p("co2_per_t_fuel") / 1000.0,
             "note": "Trajectory segments physically inside the national grid"
                     if name == "Physical emissions over Pakistan" else ""}
            for name, kg in values.items()]


def physical_grid(stages, points_by_flight, grid):
    """Allocate observed trajectory phase fuel to 0.05-degree cells inside Pakistan."""
    import numpy as np
    arr = np.zeros((grid.height, grid.width), dtype=float)
    minx, _, _, maxy = grid.bounds
    res_x = (grid.bounds[2] - grid.bounds[0]) / grid.width
    res_y = (grid.bounds[3] - grid.bounds[1]) / grid.height
    for stage in stages:
        points = sorted(points_by_flight.get(stage.flight_id, []), key=lambda p: p.timestamp)
        durations, pieces = defaultdict(float), []
        for left, right in zip(points, points[1:]):
            dt = right.timestamp - left.timestamp
            if dt <= 0 or dt > 1800 or left.latitude is None or left.longitude is None:
                continue
            durations[left.phase] += dt
            pieces.append((left, dt))
        phase_fuel = {name: getattr(stage, field) for name, field in PHASE_FIELDS.items()}
        for point, dt in pieces:
            if not durations[point.phase]:
                continue
            row = int((maxy - point.latitude) / res_y)
            col = int((point.longitude - minx) / res_x)
            if 0 <= row < grid.height and 0 <= col < grid.width and grid.province_id[row, col] >= 0:
                arr[row, col] += phase_fuel.get(point.phase, 0.0) * dt / durations[point.phase]
    return arr


def route_geojson(stages, points_by_flight):
    features = []
    for stage in stages:
        points = sorted(points_by_flight.get(stage.flight_id, []), key=lambda p: p.timestamp)
        coords = [[p.longitude, p.latitude, p.altitude_m or 0.0] for p in points
                  if p.longitude is not None and p.latitude is not None]
        if len(coords) < 2:
            continue
        features.append({"type": "Feature", "geometry": {"type": "LineString", "coordinates": coords},
                         "properties": {"flight_id": stage.flight_id, "boundary": stage.boundary,
                                        "data_tier": stage.data_tier,
                                        "fuel_kg": stage.total_fuel_kg}})
    return {"type": "FeatureCollection", "features": features}


def altitude_bins(stages, points_by_flight, co2_per_t_fuel, bin_ft=5000):
    """Allocate phase fuel across observed points by phase duration and altitude band."""
    totals = defaultdict(float)
    for stage in stages:
        points = sorted(points_by_flight.get(stage.flight_id, []), key=lambda p: p.timestamp)
        durations = defaultdict(float)
        pieces = []
        for left, right in zip(points, points[1:]):
            dt = right.timestamp - left.timestamp
            if dt <= 0 or dt > 1800:
                continue
            phase_name = left.phase
            altitude_ft = max(0.0, (left.altitude_m or 0.0) * 3.280839895)
            band = int(altitude_ft // bin_ft) * bin_ft
            durations[phase_name] += dt
            pieces.append((phase_name, band, dt))
        phase_fuel = {name: getattr(stage, field) for name, field in PHASE_FIELDS.items()}
        for phase_name, band, dt in pieces:
            if durations[phase_name]:
                totals[(stage.boundary, band)] += phase_fuel.get(phase_name, 0.0) * dt / durations[phase_name]
    return [{"boundary": key[0], "altitude_bin_min_ft": key[1],
             "altitude_bin_max_ft": key[1] + bin_ft, "fuel_t": kg / 1000.0,
             "co2_kt": kg / 1000.0 * co2_per_t_fuel / 1000.0}
            for key, kg in sorted(totals.items())]
