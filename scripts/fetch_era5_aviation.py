#!/usr/bin/env python3
"""Fetch a small, versioned ARCO-ERA5 sample for the FY2023-24 route audit."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path

import cdsapi
import numpy as np
import xarray as xr

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "sources" / "Aviation" / "ERA5_route_weather_FY2023_24.nc"
DATASET = "reanalysis-era5-pressure-levels"
ROUTES = {
    "OPKC-OPLA": ((24.9065, 67.1608), (31.5216, 74.4036)),
    "OPKC-OPIS": ((24.9065, 67.1608), (33.5490, 72.8257)),
    "OPLA-OPIS": ((31.5216, 74.4036), (33.5490, 72.8257)),
    "OPKC-OPQT": ((24.9065, 67.1608), (30.2514, 66.9378)),
    "OPIS-OPGT": ((33.5490, 72.8257), (35.9188, 74.3336)),
    "OPIS-OPSD": ((33.5490, 72.8257), (35.3355, 75.5360)),
}


def fetch():
    route_names, lats, lons, fractions = [], [], [], []
    for route, ((lat1, lon1), (lat2, lon2)) in ROUTES.items():
        for fraction in np.linspace(0, 1, 21):
            route_names.append(route)
            lats.append(lat1 + fraction * (lat2 - lat1))
            lons.append(lon1 + fraction * (lon2 - lon1))
            fractions.append(fraction)
    times = [np.datetime64(datetime(year, month, 15, hour))
             for year, month in [(2023, m) for m in range(7, 13)] +
                                [(2024, m) for m in range(1, 7)]
             for hour in (12,)]
    raw = (ROOT / "data" / "cache" / "aviation" / "era5" /
           "FY2023_24_pressure_levels_12utc.nc")
    raw.parent.mkdir(parents=True, exist_ok=True)
    request = {
        "product_type": ["reanalysis"],
        "variable": ["temperature", "u_component_of_wind", "v_component_of_wind"],
        "pressure_level": ["250", "500", "850"],
        "year": ["2023", "2024"], "month": ["%02d" % month for month in range(1, 13)],
        "day": ["15"], "time": ["12:00"],
        "area": [38, 60, 23, 79], "data_format": "netcdf",
        "download_format": "unarchived",
    }
    # cdsapi creates the target before the object-store transfer begins.  A
    # timed-out request can therefore leave an empty file that must not be
    # mistaken for a valid cache hit on the next run.
    if not raw.exists() or raw.stat().st_size < 1024:
        cdsapi.Client().retrieve(DATASET, request, str(raw))
    dataset = xr.open_dataset(raw)
    rename = {old: new for old, new in
              (("u", "u_component_of_wind"), ("v", "v_component_of_wind"),
               ("t", "temperature"), ("valid_time", "time"),
               ("pressure_level", "level")) if old in dataset.variables or old in dataset.dims}
    dataset = dataset.rename(rename)
    selected = dataset[["u_component_of_wind", "v_component_of_wind", "temperature"]].sel(
        time=xr.DataArray(times, dims="sample_time"), level=[850, 500, 250]).interp(
        latitude=xr.DataArray(lats, dims="route_point"),
        longitude=xr.DataArray(lons, dims="route_point")).load()
    if "level" in selected.dims:
        selected = selected.rename({"level": "pressure_level"})
    selected = selected.assign_coords(
        route=("route_point", route_names),
        route_fraction=("route_point", fractions),
        requested_latitude=("route_point", lats),
        requested_longitude=("route_point", lons))
    selected.attrs.update({
        "source": "Copernicus Climate Change Service ERA5",
        "source_dataset": DATASET,
        "selection": "15th day of each FY2023-24 month at 12 UTC; bilinear 0.25 degree interpolation",
        "purpose": "weather sensitivity audit; not observed flight-specific weather",
        "cds_request": json.dumps(request, sort_keys=True),
    })
    DEST.parent.mkdir(parents=True, exist_ok=True)
    selected.to_netcdf(DEST)
    print(json.dumps({"path": str(DEST), "times": len(times), "route_points": len(lats),
                      "levels": [850, 500, 250]}, sort_keys=True))


if __name__ == "__main__":
    fetch()
