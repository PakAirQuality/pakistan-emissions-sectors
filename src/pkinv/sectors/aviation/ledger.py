"""Canonical records for the flight-stage aviation inventory.

Source adapters stop here.  OpenSky, a future PCAA operational export, and a public
schedule all become the same :class:`FlightStage`; no accounting rule is allowed to
depend on a provider-specific column.  Permissioned inputs can therefore be replaced
without changing the emissions engine.
"""
from pkinv.activity.store import read_rows as _activity_rows
from dataclasses import asdict, dataclass, fields
from datetime import datetime, timezone
import csv
import hashlib
import json
import os
from pkinv.core.io import write_table

PAKISTAN_PREFIX = "OP"
SOURCE_TIERS = ("A", "B", "C", "D")
DATA_TIERS = SOURCE_TIERS  # backwards-compatible public name
LEGACY_TIERS = {"observed_trajectory": "A",
                "observed_stage_modelled_trajectory": "B",
                "reconstructed_missing_stage": "C",
                "aggregate_residual": "D"}
BOUNDARIES = ("domestic", "international", "unresolved")
GRANULARITIES = ("flight_stage", "annual_route", "aggregate_residual")


def _clean(value):
    return (value or "").strip()


def boundary(origin, destination):
    """Classify by flight geography, never carrier nationality."""
    origin, destination = _clean(origin).upper(), _clean(destination).upper()
    if not origin or not destination:
        return "unresolved"
    n_pk = int(origin.startswith(PAKISTAN_PREFIX)) + int(destination.startswith(PAKISTAN_PREFIX))
    return "domestic" if n_pk == 2 else "international" if n_pk == 1 else "unresolved"


def stable_flight_id(source, icao24, callsign, first_seen, last_seen, origin, destination):
    payload = "|".join(str(x or "").strip().upper() for x in
                       (source, icao24, callsign, first_seen, last_seen, origin, destination))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


@dataclass
class FlightStage:
    flight_id: str
    fiscal_year: int
    first_seen: int = 0
    last_seen: int = 0
    origin_icao: str = ""
    destination_icao: str = ""
    boundary: str = "unresolved"
    date: str = ""
    period_start: str = ""
    period_end: str = ""
    departure_time: str = ""
    arrival_time: str = ""
    record_granularity: str = "flight_stage"
    activity_count: float = 1.0
    source_tier: str = "B"
    operator: str = ""
    operator_residence: str = ""
    callsign: str = ""
    icao24: str = ""
    registration: str = ""
    aircraft_type: str = ""
    engine: str = ""
    engine_type: str = ""
    commercial_class: str = ""
    passengers: float | None = None
    cargo_kg: float | None = None
    mail_kg: float | None = None
    great_circle_nm: float | None = None
    trajectory_distance_nm: float | None = None
    trajectory_quality: str = "missing"
    trajectory_available: bool = False
    data_tier: str = ""
    source: str = ""
    source_reference: str = ""
    imputation_method: str = "none"
    taxi_fuel_kg: float = 0.0
    takeoff_fuel_kg: float = 0.0
    climb_fuel_kg: float = 0.0
    cruise_fuel_kg: float = 0.0
    descent_fuel_kg: float = 0.0
    landing_fuel_kg: float = 0.0
    total_fuel_kg: float = 0.0

    def validate(self):
        if self.source_tier in LEGACY_TIERS:
            self.source_tier = LEGACY_TIERS[self.source_tier]
        if self.data_tier in LEGACY_TIERS:
            self.data_tier = LEGACY_TIERS[self.data_tier]
        if self.data_tier and self.source_tier == "B":
            self.source_tier = self.data_tier
        self.data_tier = self.source_tier
        if not self.flight_id:
            raise ValueError("flight_id is required")
        if self.fiscal_year < 2000:
            raise ValueError("invalid fiscal year %r" % self.fiscal_year)
        if self.activity_count <= 0:
            raise ValueError("flight %s has non-positive activity_count" % self.flight_id)
        if self.record_granularity not in GRANULARITIES:
            raise ValueError("invalid record granularity %r" % self.record_granularity)
        if self.source_tier in ("A", "B") and self.record_granularity != "flight_stage":
            raise ValueError("observed source tiers require flight_stage granularity")
        if self.source_tier == "C" and self.record_granularity != "annual_route":
            raise ValueError("Tier C requires annual_route granularity")
        if self.source_tier == "D" and self.record_granularity != "aggregate_residual":
            raise ValueError("Tier D requires aggregate_residual granularity")
        if self.last_seen and self.first_seen and self.last_seen <= self.first_seen:
            raise ValueError("flight %s has non-positive duration" % self.flight_id)
        if self.boundary not in BOUNDARIES:
            raise ValueError("invalid boundary %r" % self.boundary)
        expected = boundary(self.origin_icao, self.destination_icao)
        if expected != "unresolved" and self.boundary != expected:
            raise ValueError("flight %s boundary is %s, endpoints imply %s"
                             % (self.flight_id, self.boundary, expected))
        if expected == "unresolved" and self.source_tier != "D" and self.boundary != "unresolved":
            raise ValueError("only Tier D may carry a known boundary without endpoints")
        if self.source_tier not in SOURCE_TIERS:
            raise ValueError("invalid source tier %r" % self.source_tier)
        phase_sum = sum((self.taxi_fuel_kg, self.takeoff_fuel_kg, self.climb_fuel_kg,
                         self.cruise_fuel_kg, self.descent_fuel_kg, self.landing_fuel_kg))
        if self.total_fuel_kg and abs(phase_sum - self.total_fuel_kg) > max(0.01, self.total_fuel_kg * 1e-6):
            raise ValueError("flight %s phase fuel does not close" % self.flight_id)
        if any(value < 0 for value in (self.taxi_fuel_kg, self.takeoff_fuel_kg,
                                       self.climb_fuel_kg, self.cruise_fuel_kg,
                                       self.descent_fuel_kg, self.landing_fuel_kg,
                                       self.total_fuel_kg)):
            raise ValueError("flight %s has negative fuel" % self.flight_id)
        return self


@dataclass
class TrajectoryPoint:
    flight_id: str
    timestamp: int
    latitude: float
    longitude: float
    altitude_m: float | None = None
    velocity_ms: float | None = None
    vertical_rate_ms: float | None = None
    on_ground: bool = False
    phase: str = "unclassified"
    source: str = ""
    quality_flag: str = "observed"


def fiscal_year(timestamp):
    dt = datetime.fromtimestamp(int(timestamp), timezone.utc)
    return dt.year if dt.month >= 7 else dt.year - 1


def from_mapping(row, source="generic_import"):
    """Normalize a canonical CSV/Parquet mapping into a validated stage."""
    origin = _clean(row.get("origin_icao") or row.get("estDepartureAirport")).upper()
    destination = _clean(row.get("destination_icao") or row.get("estArrivalAirport")).upper()
    first = int(float(row.get("first_seen") or row.get("firstSeen") or 0))
    last = int(float(row.get("last_seen") or row.get("lastSeen") or 0))
    icao24 = _clean(row.get("icao24")).lower()
    callsign = _clean(row.get("callsign")).upper()
    src = _clean(row.get("source")) or source
    fid = _clean(row.get("flight_id")) or stable_flight_id(
        src, icao24, callsign, first, last, origin, destination)
    names = {f.name for f in fields(FlightStage)}
    payload = {k: row[k] for k in names if k in row and row[k] not in (None, "")}
    inferred_year = fiscal_year(first) if first else int(row.get("fiscal_year") or 0)
    payload.update(flight_id=fid, fiscal_year=int(row.get("fiscal_year") or inferred_year),
                   first_seen=first, last_seen=last, origin_icao=origin,
                   destination_icao=destination,
                   boundary=_clean(row.get("boundary")) or boundary(origin, destination),
                   callsign=callsign, icao24=icao24, source=src)
    for name in ("activity_count", "passengers", "cargo_kg", "mail_kg", "great_circle_nm", "trajectory_distance_nm",
                 "taxi_fuel_kg", "takeoff_fuel_kg", "climb_fuel_kg", "cruise_fuel_kg",
                 "descent_fuel_kg", "landing_fuel_kg", "total_fuel_kg"):
        if name in payload and payload[name] not in (None, ""):
            payload[name] = float(payload[name])
    return FlightStage(**payload).validate()


def validate_records(records):
    seen = set()
    for record in records:
        record.validate()
        if record.flight_id in seen:
            raise ValueError("duplicate flight_id %s" % record.flight_id)
        seen.add(record.flight_id)
    return records


def read(path):
    if path.endswith(".parquet"):
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("Parquet flight ledgers require the 'aviation' extra") from exc
        rows = pd.read_parquet(path).where(lambda x: x.notna(), None).to_dict("records")
    else:
        rows = list(_activity_rows(path, comments=False))
    return validate_records([from_mapping(row) for row in rows])


def write(records, path):
    validate_records(records)
    rows = [asdict(record) for record in records]
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if path.endswith(".parquet"):
        try:
            import pandas as pd
        except ImportError as exc:
            raise RuntimeError("Parquet flight ledgers require the 'aviation' extra") from exc
        pd.DataFrame(rows).to_parquet(path, index=False)
    else:
        write_table(path, [f.name for f in fields(FlightStage)], rows, lineterminator="\n")


def manifest(records, source_metadata):
    counts = {tier: {"records": 0, "activity_count": 0.0} for tier in SOURCE_TIERS}
    for record in records:
        counts[record.source_tier]["records"] += 1
        counts[record.source_tier]["activity_count"] += record.activity_count
    return {"schema": "pkinv.aviation.flight_stage/v2", "records": len(records),
            "tiers": counts, "source": source_metadata}


def write_manifest(path, records, source_metadata):
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest(records, source_metadata), handle, indent=2, sort_keys=True)
        handle.write("\n")
