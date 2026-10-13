"""ADSB.lol daily-history adapter and Pakistan coverage pilot.

The raw trace database is ODbL.  Raw archives and extracted trace records stay below
``data/cache``; only aggregate diagnostics and canonical stage records are emitted.
"""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
from collections import Counter, defaultdict
from datetime import datetime, timezone
import gzip
import io
import json
import math
import os
import tarfile

from pkinv.paths import DATA
from pkinv.sectors.aviation import ledger
from pkinv.activity.store import read_rows

CACHE = asset_path(DATA, "cache", "aviation", "adsblol")
PILOT_DATES = ("2023-08-15", "2023-11-15", "2024-02-15", "2024-05-15")
# Deliberately labelled a *candidate* region: the rectangle also intersects
# Afghanistan, China, India and Iran and therefore cannot establish that a
# trace physically crossed Pakistan.  Airport-linked legs are the publishable
# pilot unit until a versioned national boundary is added.
PAKISTAN_CANDIDATE_BBOX = (23.0, 37.5, 60.0, 78.5)
LICENSE = "Open Database License 1.0 (ODbL)"
SOURCE_URL = "https://github.com/adsblol/globe_history_2023"


def _distance_km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 6371.0088 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _airports():
    import csv
    path = asset_path(DATA, "activity", "aviation", "airports.csv")
    return [{**row, "lat": float(row["latitude_deg"]), "lon": float(row["longitude_deg"]), "elevation": float(row.get("elevation_ft") or 0)} for row in read_rows(path, comments=False) if row["latitude_deg"] and row["longitude_deg"]]


def _operators():
    import csv
    path = asset_path(DATA, "activity", "aviation", "operator_groups.csv")
    return {row["icao_operator"]: row for row in read_rows(path, comments=False)}


def _decode_member(member, handle):
    payload = handle.read()
    if member.name.endswith(".gz") or payload[:2] == b"\x1f\x8b":
        payload = gzip.decompress(payload)
    return json.loads(payload)


def _point(entry, base):
    if len(entry) < 3 or entry[1] is None or entry[2] is None:
        return None
    altitude = entry[3] if len(entry) > 3 else None
    altitude_ft = 0.0 if altitude == "ground" else (float(altitude) if altitude is not None else None)
    details = entry[8] if len(entry) > 8 and isinstance(entry[8], dict) else {}
    return {
        "timestamp": float(base) + float(entry[0]),
        "latitude": float(entry[1]), "longitude": float(entry[2]),
        "altitude_ft": altitude_ft,
        "ground_speed_kt": float(entry[4]) if len(entry) > 4 and entry[4] is not None else None,
        "track_deg": float(entry[5]) if len(entry) > 5 and entry[5] is not None else None,
        "flags": int(entry[6] or 0) if len(entry) > 6 else 0,
        "vertical_rate_fpm": float(entry[7]) if len(entry) > 7 and entry[7] is not None else None,
        "callsign": str(details.get("flight") or "").strip().upper(),
        "position_source": entry[9] if len(entry) > 9 else details.get("type", ""),
    }


def _legs(trace):
    points = [point for point in (_point(entry, trace["timestamp"])
                                  for entry in trace.get("trace", [])) if point]
    output, current = [], []
    for point in points:
        new_leg = bool(point["flags"] & 2)
        large_gap = bool(current and point["timestamp"] - current[-1]["timestamp"] > 3600)
        if current and (new_leg or large_gap):
            output.append(current)
            current = []
        current.append(point)
    if current:
        output.append(current)
    return output


def _inside_candidate_region(point, bbox=PAKISTAN_CANDIDATE_BBOX):
    south, north, west, east = bbox
    return south <= point["latitude"] <= north and west <= point["longitude"] <= east


def _airport_proximity(points, airports, max_distance_km=35.0,
                       max_height_above_airport_ft=6000.0):
    """Return ordered visits and the nearest candidate point to a Pakistani airport.

    The altitude test is relative to airport elevation so that northern
    airports such as Gilgit and Skardu are not excluded by a sea-level cutoff.
    A 35 km radius is intentionally permissive for a coverage pilot; a visit is
    an endpoint candidate, not proof of a landing or take-off.
    """
    visits, minimum_distance = [], math.inf
    for point in points:
        distance, airport = min(((_distance_km(point["latitude"], point["longitude"],
                                               row["lat"], row["lon"]), row)
                                 for row in airports), key=lambda pair: pair[0])
        minimum_distance = min(minimum_distance, distance)
        altitude = point["altitude_ft"]
        low_enough = (altitude is None or
                      altitude <= airport["elevation"] + max_height_above_airport_ft)
        if distance <= max_distance_km and low_enough:
            code = airport["airport_icao"]
            if not visits or visits[-1] != code:
                visits.append(code)
    return visits, minimum_distance


def _airport_visits(points, airports, max_distance_km=35.0,
                    max_height_above_airport_ft=6000.0):
    return _airport_proximity(points, airports, max_distance_km,
                              max_height_above_airport_ft)[0]


def _trajectory_nm(points):
    return sum(_distance_km(a["latitude"], a["longitude"], b["latitude"], b["longitude"])
               for a, b in zip(points, points[1:])) / 1.852


def _stage(trace, points, archive_name, airports, operators, visits=None):
    visits = _airport_visits(points, airports) if visits is None else visits
    origin = visits[0] if visits else ""
    destination = visits[-1] if len(visits) > 1 else ""
    callsigns = Counter(point["callsign"] for point in points if point["callsign"])
    callsign = callsigns.most_common(1)[0][0] if callsigns else ""
    operator_code = callsign[:3] if len(callsign) >= 3 else ""
    operator = operators.get(operator_code, {})
    first, last = int(points[0]["timestamp"]), int(points[-1]["timestamp"])
    fid = ledger.stable_flight_id("ADSB.lol", trace.get("icao", ""), callsign,
                                  first, last, origin, destination)
    record = ledger.FlightStage(
        flight_id=fid, fiscal_year=ledger.fiscal_year(first), first_seen=first,
        last_seen=last, origin_icao=origin, destination_icao=destination,
        boundary=ledger.boundary(origin, destination),
        date=datetime.fromtimestamp(first, timezone.utc).date().isoformat(),
        departure_time=datetime.fromtimestamp(first, timezone.utc).isoformat(),
        arrival_time=datetime.fromtimestamp(last, timezone.utc).isoformat(),
        record_granularity="flight_stage", source_tier="A", operator=operator_code,
        operator_residence=operator.get("residence", ""), callsign=callsign,
        icao24=str(trace.get("icao") or "").lower(),
        registration=str(trace.get("r") or ""), aircraft_type=str(trace.get("t") or ""),
        great_circle_nm=None, trajectory_distance_nm=_trajectory_nm(points),
        trajectory_quality="observed_partial_or_complete", trajectory_available=True,
        source="ADSB.lol globe history", source_reference=archive_name,
        imputation_method="endpoint_nearest_airport_low_altitude")
    return record.validate()


def scan_archive(path, airports=None, candidate_bbox=PAKISTAN_CANDIDATE_BBOX,
                 control_name="pakistan"):
    """Stream one daily tar without extracting the derivative trace database."""
    airports, operators = airports or _airports(), _operators()
    stages, stats = [], Counter()
    route_counts, airport_counts, aircraft_counts = Counter(), Counter(), Counter()
    minimum_airport_distance = math.inf
    with tarfile.open(path, mode="r|*") as archive:
        for member in archive:
            if not member.isfile() or ".json" not in member.name:
                continue
            stats["trace_members"] += 1
            handle = archive.extractfile(member)
            if handle is None:
                continue
            try:
                trace = _decode_member(member, handle)
            except (OSError, ValueError, json.JSONDecodeError):
                stats["parse_failures"] += 1
                continue
            candidate_region = False
            airport_linked = False
            for points in _legs(trace):
                if len(points) < 2:
                    continue
                in_candidate_region = any(_inside_candidate_region(point, candidate_bbox)
                                          for point in points)
                if in_candidate_region:
                    candidate_region = True
                    stats["regional_candidate_legs"] += 1
                else:
                    continue
                visits, proximity = _airport_proximity(points, airports)
                minimum_airport_distance = min(minimum_airport_distance, proximity)
                if not visits:
                    if in_candidate_region:
                        stats["regional_candidate_legs_without_airport_link"] += 1
                    continue
                airport_linked = True
                stats["target_airport_linked_legs"] += 1
                if control_name == "pakistan":
                    stats["pakistan_airport_linked_legs"] += 1
                record = _stage(trace, points, os.path.basename(path), airports, operators,
                                visits=visits)
                stages.append(record)
                if record.callsign:
                    stats["callsign_identified"] += 1
                if record.aircraft_type:
                    stats["aircraft_type_identified"] += 1
                    aircraft_counts[record.aircraft_type] += 1
                if record.origin_icao:
                    airport_counts[record.origin_icao] += 1
                if record.destination_icao:
                    airport_counts[record.destination_icao] += 1
                if record.origin_icao and record.destination_icao:
                    stats["both_endpoints_identified"] += 1
                    route_counts[(record.origin_icao, record.destination_icao)] += 1
                    stats[record.boundary + "_stages"] += 1
            if candidate_region:
                stats["regional_candidate_aircraft_traces"] += 1
            if airport_linked:
                stats["target_airport_linked_aircraft_traces"] += 1
                if control_name == "pakistan":
                    stats["pakistan_airport_linked_aircraft_traces"] += 1
    stats["canonical_stages"] = len(stages)
    diagnostics = {**stats, "control_name": control_name,
                   "archive": os.path.basename(path), "source_license": LICENSE,
                   "minimum_candidate_point_to_pakistan_airport_km":
                   (minimum_airport_distance if math.isfinite(minimum_airport_distance) else ""),
                   "top_routes": [{"route": "%s-%s" % pair, "stages": count}
                                  for pair, count in route_counts.most_common(20)],
                   "airport_endpoint_counts": dict(sorted(airport_counts.items())),
                   "aircraft_type_counts": dict(sorted(aircraft_counts.items()))}
    return stages, diagnostics


def synthetic_positive_control():
    """Exercise leg splitting, the altitude-aware gate and canonical Tier-A output."""
    trace = {"timestamp": 1692100000, "icao": "760001", "r": "AP-TST", "t": "A320",
             "trace": [
                 [0, 24.9065, 67.1608, "ground", 0, 0, 0, 0, {"flight": "PIA301"}],
                 [120, 25.10, 67.30, 2500, 180, 30, 0, 1500, {"flight": "PIA301"}],
                 [3300, 31.40, 74.20, 3000, 180, 30, 0, -1500, {"flight": "PIA301"}],
                 [3600, 31.5216, 74.4036, "ground", 0, 0, 0, 0, {"flight": "PIA301"}],
             ]}
    points = _legs(trace)[0]
    airports = _airports()
    visits = _airport_visits(points, airports)
    stage = _stage(trace, points, "synthetic-positive-control", airports, _operators(), visits)
    return stage, {"control": "synthetic_OPKC_OPLA", "canonical_stages": 1,
                   "origin_icao": stage.origin_icao,
                   "destination_icao": stage.destination_icao,
                   "boundary": stage.boundary,
                   "trajectory_distance_nm": stage.trajectory_distance_nm,
                   "status": "PASS" if (stage.origin_icao, stage.destination_icao) ==
                   ("OPKC", "OPLA") else "FAIL"}


def archive_positive_control(path):
    """Run the identical archive parser around well-covered Dubai International."""
    import csv
    metadata = asset_path(DATA, "activity", "aviation", "international_airports.csv")
    row = next(row for row in _activity_rows(metadata, comments=False) if row["airport_icao"] == "OMDB")
    airports = [{**row, "lat": float(row["latitude_deg"]),
                 "lon": float(row["longitude_deg"]),
                 "elevation": float(row.get("elevation_ft") or 0)}]
    stages, diagnostics = scan_archive(path, airports=airports,
                                       candidate_bbox=(24.0, 26.0, 54.0, 56.5),
                                       control_name="OMDB_archive_positive")
    diagnostics["status"] = ("PASS" if diagnostics.get("target_airport_linked_legs", 0) > 0
                              else "FAIL")
    diagnostics["interpretation"] = "parser/gate positive control; not Pakistan coverage"
    return stages, diagnostics


class ADSBLOLSource:
    """Public observed-trajectory source implementing the canonical stage boundary."""
    name = "ADSBLOLSource"

    def __init__(self, cache_dir=CACHE, dates=PILOT_DATES):
        self.cache_dir, self.dates = cache_dir, tuple(dates)

    def archives(self):
        return [asset_path(self.cache_dir, date + ".tar") for date in self.dates]

    def load(self):
        stages = []
        for path in self.archives():
            day, _diagnostics = scan_archive(path)
            stages.extend(day)
        return ledger.validate_records(stages)

    def pilot(self, parallel=False):
        stages, days = [], []
        archives = self.archives()
        if parallel and len(archives) > 1:
            from concurrent.futures import ProcessPoolExecutor
            with ProcessPoolExecutor(max_workers=min(4, len(archives))) as pool:
                scanned = list(pool.map(scan_archive, archives))
        else:
            scanned = [scan_archive(path) for path in archives]
        for day_stages, diagnostics in scanned:
            stages.extend(day_stages)
            days.append(diagnostics)
        totals = Counter()
        for day in days:
            for key, value in day.items():
                if isinstance(value, int):
                    totals[key] += value
        summary = {
            "pilot_dates": list(self.dates), "archives_processed": len(days),
            "source": "ADSB.lol globe history", "source_license": LICENSE,
            "raw_redistribution": "not included; review ODbL derivative-database obligations",
            **totals,
            "callsign_coverage": totals["callsign_identified"] / max(1, totals["canonical_stages"]),
            "aircraft_type_coverage": totals["aircraft_type_identified"] / max(1, totals["canonical_stages"]),
            "endpoint_pair_coverage": totals["both_endpoints_identified"] / max(1, totals["canonical_stages"]),
            "minimum_candidate_point_to_pakistan_airport_km": min(
                (float(day["minimum_candidate_point_to_pakistan_airport_km"])
                 for day in days if day["minimum_candidate_point_to_pakistan_airport_km"] != ""),
                default=""),
        }
        return stages, days, summary
