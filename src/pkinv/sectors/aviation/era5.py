"""ERA5 wind/temperature sensitivity for representative OpenAP route strata."""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
import csv
import math
import os

import numpy as np

from pkinv.paths import OUTPUTS, ROOT
from pkinv.sectors.aviation import lto, resolution
from pkinv.sectors.aviation.data import AviationData

SOURCE = asset_path(ROOT, "sources", "Aviation", "ERA5_route_weather_FY2023_24.nc")
LOOKUP = asset_path(OUTPUTS, "aviation_openap_lookup_fy2023_24.csv")
ROUTES = {"OPKC-OPLA", "OPKC-OPIS", "OPLA-OPIS", "OPKC-OPQT", "OPIS-OPGT", "OPIS-OPSD"}


def _bearing(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.atan2(y, x)


# rc41: the consumed derivative of the ERA5 route-weather NetCDF (see
# monthly.OCAC_EXTRACT); the extractor below needs xarray and the document, the
# reader needs neither.
EXTRACT_CSV = asset_path(ROOT, "data", "activity", "aviation", "era5_route_weather_extract.csv")
EXTRACT_FIELDS = ("route", "pressure_level_hpa", "samples", "mean_tailwind_ms",
                  "p05_tailwind_ms", "p95_tailwind_ms", "mean_temperature_k",
                  "p05_temperature_k", "p95_temperature_k", "sampling_note")


def route_weather(extract_csv=None):
    from pkinv.core.documents import read_extract

    return read_extract(extract_csv or EXTRACT_CSV,
                        {"pressure_level_hpa": int, "samples": int,
                         **{f: float for f in EXTRACT_FIELDS[3:9]}})


def extract_route_weather(path=None, pressure_level=250):
    import xarray as xr

    dataset = xr.open_dataset(path or SOURCE)
    output = []
    for route in sorted(set(str(value) for value in dataset.route.values)):
        selected = dataset.where(dataset.route == route, drop=True).sel(pressure_level=pressure_level)
        lat1, lat2 = float(selected.requested_latitude.values[0]), float(selected.requested_latitude.values[-1])
        lon1, lon2 = float(selected.requested_longitude.values[0]), float(selected.requested_longitude.values[-1])
        bearing = _bearing(lat1, lon1, lat2, lon2)
        tailwind = selected.u_component_of_wind * math.sin(bearing) + selected.v_component_of_wind * math.cos(bearing)
        temperature = selected.temperature
        output.append({
            "route": route, "pressure_level_hpa": pressure_level,
            "samples": int(tailwind.size),
            "mean_tailwind_ms": float(tailwind.mean()),
            "p05_tailwind_ms": float(tailwind.quantile(0.05)),
            "p95_tailwind_ms": float(tailwind.quantile(0.95)),
            "mean_temperature_k": float(temperature.mean()),
            "p05_temperature_k": float(temperature.quantile(0.05)),
            "p95_temperature_k": float(temperature.quantile(0.95)),
            "sampling_note": dataset.attrs["selection"],
        })
    dataset.close()
    return output


def performance_audit(weather_rows, lookup_path=None):
    lookup = list(_activity_rows(lookup_path or LOOKUP, comments=False))
    weather = {row["route"]: row for row in weather_rows}
    data = AviationData()
    movement_fuel_per_stage = (lto.fuel_tonnes(data, 2023)["domestic"] * 1000 /
                               lto.lto_cycles(data, 2023)["domestic"])
    output = []
    for row in lookup:
        route = row["origin_icao"] + "-" + row["destination_icao"]
        if route not in ROUTES or route not in weather:
            continue
        taxi_minutes = (data.p("openap_default_taxi_out_s") +
                        data.p("openap_default_taxi_in_s")) / 60.0
        air_minutes = max(1.0, float(row["flight_time_min"]) - taxi_minutes)
        distance_km = float(row["distance_km"]) * float(row["route_multiplier"])
        still_ground_speed_kmh = distance_km / (air_minutes / 60.0)
        tailwind_kmh = float(weather[route]["mean_tailwind_ms"]) * 3.6
        adjusted_speed = max(100.0, still_ground_speed_kmh + tailwind_kmh)
        adjusted_air_minutes = distance_km / adjusted_speed * 60.0
        duration_ratio = adjusted_air_minutes / air_minutes
        taxi_fuel = float(row["taxi_fuel_kg"])
        still_fuel = float(row["total_fuel_kg"])
        weather_fuel = taxi_fuel + (still_fuel - taxi_fuel) * duration_ratio
        route_factor = resolution._factor(data, data.inventory_aircraft(row["aircraft_type"]),
                                          float(row["distance_km"]) / 1.852)
        output.append({
            "route": route, "aircraft_type": row["aircraft_type"],
            "payload_scenario": row["payload_scenario"],
            "initial_mass_kg": float(row["initial_mass_kg"]),
            "distance_km": float(row["distance_km"]),
            "openap_stillair_block_min": float(row["flight_time_min"]),
            "era5_mean_tailwind_ms": weather[route]["mean_tailwind_ms"],
            "era5_mean_temperature_k": weather[route]["mean_temperature_k"],
            "duration_scaled_block_min": adjusted_air_minutes + taxi_minutes,
            "openap_stillair_fuel_kg": still_fuel,
            "era5_duration_scaled_fuel_kg": weather_fuel,
            "weather_fuel_change_pct": (weather_fuel / still_fuel - 1) * 100,
            "m0_national_mean_fuel_per_stage_kg": movement_fuel_per_stage,
            "route_inventory_factor_kg": route_factor,
            "method_status": "weather sensitivity; OpenAP aerodynamics not rerun",
        })
    return output


def diagnostics(audit_rows):
    central = [row for row in audit_rows if row["payload_scenario"] == "central"]
    changes = np.asarray([float(row["weather_fuel_change_pct"]) for row in central])
    openap = np.asarray([float(row["openap_stillair_fuel_kg"]) for row in central])
    m0 = np.asarray([float(row["m0_national_mean_fuel_per_stage_kg"]) for row in central])
    route = np.asarray([float(row["route_inventory_factor_kg"]) for row in central])
    return [{
        "representative_route_aircraft_combinations": len(central),
        "mean_weather_fuel_change_pct": float(changes.mean()),
        "min_weather_fuel_change_pct": float(changes.min()),
        "max_weather_fuel_change_pct": float(changes.max()),
        "mean_openap_over_m0_ratio": float(np.mean(openap / m0)),
        "mean_openap_over_route_factor_ratio": float(np.mean(openap / route)),
        "interpretation": "weather sensitivity is comparable to the corrected common-support M1-to-M2 gap but is not flight-specific validation",
    }]
