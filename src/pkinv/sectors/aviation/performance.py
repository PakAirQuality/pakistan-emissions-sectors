"""OpenAP flight- and phase-specific fuel modelling.

OpenAP is imported lazily so the aggregate national inventory keeps its zero-dependency
contract.  All public functions also accept a fuel-flow object, which makes physical
accounting tests independent of a particular OpenAP release.
"""
from collections import defaultdict
from dataclasses import replace
import math

from pkinv.sectors.aviation.ledger import TrajectoryPoint

M_TO_FT = 3.280839895
MS_TO_KT = 1.943844492
MS_TO_FPM = 196.850394
NM_TO_KM = 1.852
PHASE_FIELDS = {"taxi": "taxi_fuel_kg", "takeoff": "takeoff_fuel_kg",
                "climb": "climb_fuel_kg", "cruise": "cruise_fuel_kg",
                "descent": "descent_fuel_kg", "landing": "landing_fuel_kg"}


def phase(altitude_m, vertical_rate_ms, on_ground=False):
    if on_ground:
        return "taxi"
    altitude_m = altitude_m or 0.0
    vertical_rate_ms = vertical_rate_ms or 0.0
    if altitude_m < 305 and vertical_rate_ms > 1.5:
        return "takeoff"
    if vertical_rate_ms > 1.5:
        return "climb"
    if vertical_rate_ms < -1.5 and altitude_m > 305:
        return "descent"
    if altitude_m < 305:
        return "landing"
    return "cruise"


def _openap_fuel_flow(aircraft, engine=""):
    try:
        from openap import FuelFlow
    except ImportError as exc:
        raise RuntimeError("flight performance requires the 'aviation' extra (OpenAP)") from exc
    return FuelFlow(aircraft, eng=engine or None)


def _flow(model, p, mass_kg):
    ph = p.phase or phase(p.altitude_m, p.vertical_rate_ms, p.on_ground)
    tas = max(20.0, (p.velocity_ms or 0.0) * MS_TO_KT)
    alt = max(0.0, (p.altitude_m or 0.0) * M_TO_FT)
    if ph == "takeoff":
        return float(model.takeoff(tas=tas, alt=alt))
    # The clean-configuration model is the reproducible fallback for taxi/landing;
    # those phases remain structurally separated and receive airport-time scenarios.
    return float(model.enroute(mass=mass_kg, tas=tas, alt=alt,
                               vs=(p.vertical_rate_ms or 0.0) * MS_TO_FPM))


def _openap_range_argument(generator, cruise_distance_m, dt):
    """Adapt to the OpenAP ``range_cr`` documentation/implementation mismatch.

    OpenAP 2.4 documents kilometres but its deterministic cruise generator compares
    ``range_cr`` directly with a cumulative distance in metres.  A small runtime probe
    keeps this adapter safe if that upstream behaviour is corrected later.
    """
    probe = generator.cruise(dt=max(60, dt), range_cr=1000, random=False)
    implementation_uses_metres = len(probe) <= 5
    return (cruise_distance_m if implementation_uses_metres
            else cruise_distance_m / 1000.0)


def _synthetic_frame(generator, distance_km, dt):
    """Generate a complete profile whose horizontal range matches the route target."""
    target_m = float(distance_km) * 1000.0
    range_scale = _openap_range_argument(generator, 1.0, dt)
    range_arg = lambda metres: metres * range_scale
    cruise_probe = generator.cruise(dt=dt, range_cr=range_arg(0), random=False)
    default_altitude_ft = float(cruise_probe["alt_cr"].iloc[0])

    def no_cruise(altitude_ft):
        return generator.complete(dt=dt, range_cr=range_arg(0),
                                  alt_cr=altitude_ft, random=False)

    altitude_ft = default_altitude_ft
    base = no_cruise(altitude_ft)
    # Short routes cannot sustain the default cruise level without the climb and
    # descent alone exceeding route length.  Find the highest feasible altitude.
    if float(base["s"].iloc[-1]) > target_m:
        low, high = 5000.0, default_altitude_ft
        low_frame = no_cruise(low)
        if float(low_frame["s"].iloc[-1]) > target_m:
            raise ValueError("route %.1f km is too short for OpenAP complete profile" %
                             distance_km)
        for _ in range(12):
            middle = (low + high) / 2.0
            middle_frame = no_cruise(middle)
            if float(middle_frame["s"].iloc[-1]) <= target_m:
                low, low_frame = middle, middle_frame
            else:
                high = middle
        altitude_ft, base = low, low_frame

    noncruise_m = float(base["s"].iloc[-1])
    cruise_m = max(0.0, target_m - noncruise_m)
    frame = generator.complete(dt=dt, range_cr=range_arg(cruise_m),
                               alt_cr=altitude_ft, random=False)
    modelled_m = float(frame["s"].iloc[-1])
    # Discretisation may undershoot by one time step, but a gross mismatch is a
    # hard failure: it was precisely this condition that made the old M2 route-
    # invariant.
    tolerance_m = max(5000.0, target_m * 0.03)
    if abs(modelled_m - target_m) > tolerance_m:
        raise ValueError("OpenAP profile range %.1f km does not match target %.1f km" %
                         (modelled_m / 1000.0, distance_km))
    frame.attrs.update({"target_distance_km": distance_km,
                        "modelled_distance_km": modelled_m / 1000.0,
                        "cruise_altitude_ft": altitude_ft})
    return frame


def integrate(stage, points, initial_mass_kg, fuel_flow=None):
    """Integrate kg/s over trajectory intervals and return a closed stage record."""
    points = sorted(points, key=lambda p: p.timestamp)
    if len(points) < 2:
        raise ValueError("flight %s needs at least two trajectory points" % stage.flight_id)
    model = fuel_flow or _openap_fuel_flow(stage.aircraft_type, stage.engine)
    by_phase, mass = defaultdict(float), float(initial_mass_kg)
    for left, right in zip(points, points[1:]):
        dt = right.timestamp - left.timestamp
        if dt <= 0 or dt > 1800:
            continue
        ph = left.phase if left.phase != "unclassified" else phase(
            left.altitude_m, left.vertical_rate_ms, left.on_ground)
        kg = max(0.0, _flow(model, replace(left, phase=ph), mass) * dt)
        by_phase[ph] += kg
        mass = max(1.0, mass - kg)
    values = {field: by_phase[name] for name, field in PHASE_FIELDS.items()}
    total = sum(values.values())
    return replace(stage, **values, total_fuel_kg=total,
                   trajectory_quality="observed",
                   trajectory_available=True, source_tier="A").validate()


def synthetic_points(stage, data):
    """Generate a deterministic OpenAP trajectory for a stage without state vectors."""
    if not stage.aircraft_type:
        raise ValueError("flight %s has no aircraft type" % stage.flight_id)
    if not stage.great_circle_nm:
        raise ValueError("flight %s has no route distance" % stage.flight_id)
    try:
        from openap import FlightGenerator
    except ImportError as exc:
        raise RuntimeError("trajectory generation requires the 'aviation' extra (OpenAP)") from exc
    dt = int(data.p("openap_profile_step_s"))
    distance_km = stage.great_circle_nm * NM_TO_KM * data.p("openap_route_detour_factor")
    frame = _synthetic_frame(FlightGenerator(stage.aircraft_type, random_seed=42),
                             distance_km, dt)
    base = stage.first_seen
    return [TrajectoryPoint(stage.flight_id, base + int(row.t), 0.0, 0.0,
                            altitude_m=float(row.altitude) / M_TO_FT,
                            velocity_ms=float(row.groundspeed) / MS_TO_KT,
                            vertical_rate_ms=float(row.vertical_rate) / MS_TO_FPM,
                            phase=phase(float(row.altitude) / M_TO_FT,
                                        float(row.vertical_rate) / MS_TO_FPM),
                            source="OpenAP modelled profile", quality_flag="modelled")
            for row in frame.itertuples()]


def model_stage(stage, data, points=None, initial_mass_kg=None, fuel_flow=None):
    if initial_mass_kg is None:
        raise ValueError("initial mass is required and must retain its assumption source")
    trajectory = points if points and len(points) >= 2 else synthetic_points(stage, data)
    result = integrate(stage, trajectory, initial_mass_kg, fuel_flow=fuel_flow)
    if not points or len(points) < 2:
        result = replace(result, trajectory_quality="modelled",
                         trajectory_available=False,
                         source_tier=("C" if stage.source_tier == "C" else "B"))
    return result.validate()
