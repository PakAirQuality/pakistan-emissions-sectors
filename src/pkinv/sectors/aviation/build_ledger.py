"""Normalize private OpenSky extracts into the canonical FY2023-24 ledger."""

from pkinv.assets import asset_path
import os
import math

from pkinv.paths import DATA
from pkinv.sectors.aviation import ledger, opensky


def _distance_nm(points):
    total = 0.0
    for left, right in zip(points, points[1:]):
        lat1, lat2 = math.radians(left["lat"]), math.radians(right["lat"])
        dlat = lat2 - lat1
        dlon = math.radians(right["lon"] - left["lon"])
        a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
        total += 3440.065 * 2 * math.asin(min(1.0, math.sqrt(a)))
    return total


def _metadata(input_dir, pd):
    for name in ("aircraft_metadata.parquet", "aircraft_metadata.csv"):
        path = asset_path(input_dir, name)
        if os.path.exists(path):
            frame = pd.read_parquet(path) if path.endswith(".parquet") else pd.read_csv(path)
            return {str(row["icao24"]).strip().lower(): row for row in frame.to_dict("records")}
    return {}


def build(input_dir=opensky.PRIVATE_DIR, output_path=None):
    try:
        import pandas as pd
    except ImportError as exc:
        raise RuntimeError("ledger construction requires the 'aviation' extra") from exc
    flights_path = asset_path(input_dir, "flights.parquet")
    states_path = asset_path(input_dir, "state_vectors.parquet")
    if not os.path.exists(flights_path):
        raise FileNotFoundError("missing permissioned OpenSky extract: %s" % flights_path)
    flights = pd.read_parquet(flights_path)
    states = pd.read_parquet(states_path) if os.path.exists(states_path) else None
    states_by_aircraft = {}
    if states is not None and len(states):
        # A flight is trajectory-observed only after at least two state vectors fall in
        # its aircraft/time window; exact point matching is performed by the model runner.
        states["icao24"] = states["icao24"].astype(str).str.lower()
        states_by_aircraft = {key: group.sort_values("time")
                              for key, group in states.groupby("icao24")}
    metadata = _metadata(input_dir, pd)
    records, trajectory_rows = [], []
    for row in flights.to_dict("records"):
        record = ledger.from_mapping(row, source="OpenSky flights_data4")
        meta = metadata.get(record.icao24, {})
        record.registration = str(meta.get("registration") or "").strip().upper()
        record.aircraft_type = str(meta.get("typecode") or meta.get("aircraft_type") or "").strip().upper()
        aircraft_states = states_by_aircraft.get(record.icao24)
        matched = []
        if aircraft_states is not None:
            matched = aircraft_states[(aircraft_states["time"] >= record.first_seen) &
                                      (aircraft_states["time"] <= record.last_seen)].to_dict("records")
        if len(matched) >= 2:
            record.source_tier = record.data_tier = "A"
            record.trajectory_quality = "observed"
            record.trajectory_available = True
            record.trajectory_distance_nm = _distance_nm(matched)
            record.great_circle_nm = _distance_nm([matched[0], matched[-1]])
            for point in matched:
                trajectory_rows.append({"flight_id": record.flight_id, "timestamp": int(point["time"]),
                                        "latitude": point.get("lat"), "longitude": point.get("lon"),
                                        "altitude_m": point.get("baroaltitude"),
                                        "velocity_ms": point.get("velocity"),
                                        "vertical_rate_ms": point.get("vertrate"),
                                        "on_ground": bool(point.get("onground", False)),
                                        "phase": "unclassified", "source": "OpenSky state_vectors_data4",
                                        "quality_flag": "observed"})
        records.append(record.validate())
    ledger.validate_records(records)
    output_path = output_path or asset_path(DATA, "private", "aviation",
                                               "flight_ledger_2023.parquet")
    ledger.write(records, output_path)
    if trajectory_rows:
        trajectory_path = asset_path(os.path.dirname(output_path), "trajectory_points_2023.parquet")
        pd.DataFrame(trajectory_rows).to_parquet(trajectory_path, index=False)
    ledger.write_manifest(output_path + ".manifest.json", records, opensky.query_manifest())
    return records, output_path


def main():
    records, path = build()
    print("canonical flight ledger: %d records -> %s" % (len(records), path))


if __name__ == "__main__":
    main()
