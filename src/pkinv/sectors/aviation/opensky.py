"""OpenSky Trino extraction into private, non-redistributable Parquet files.

The module intentionally contains no credentials and never writes below tracked
``data/activity``.  It publishes exact SQL separately so a run remains auditable even
when the permissioned rows cannot be redistributed.
"""

from pkinv.assets import asset_path
from datetime import datetime, timezone
import hashlib
import json
import os

from pkinv.paths import DATA

START = datetime(2023, 7, 1, tzinfo=timezone.utc)
END = datetime(2024, 7, 1, tzinfo=timezone.utc)
PRIVATE_DIR = asset_path(DATA, "private", "aviation", "opensky", "FY2023")


class OpenSkySource:
    """Permissioned source adapter implementing the canonical import boundary."""
    name = "OpenSkySource"

    def __init__(self, input_dir=PRIVATE_DIR):
        self.input_dir = input_dir

    def load(self):
        from pkinv.sectors.aviation import build_ledger
        records, _ = build_ledger.build(self.input_dir)
        return records


def flight_sql(start=START, end=END):
    return """SELECT icao24, callsign, firstseen, lastseen,
       estdepartureairport, estarrivalairport
FROM flights_data4
WHERE firstseen >= %d
  AND firstseen < %d
  AND (estdepartureairport LIKE 'OP%%' OR estarrivalairport LIKE 'OP%%')
""" % (int(start.timestamp()), int(end.timestamp()))


def state_sql(start=START, end=END):
    return """WITH selected_flights AS (
  SELECT icao24, firstseen, lastseen
  FROM flights_data4
  WHERE firstseen >= %d AND firstseen < %d
    AND (estdepartureairport LIKE 'OP%%' OR estarrivalairport LIKE 'OP%%')
)
SELECT s.time, s.icao24, s.callsign, s.lat, s.lon, s.baroaltitude,
       s.velocity, s.vertrate, s.onground
FROM state_vectors_data4 s
JOIN selected_flights f ON s.icao24 = f.icao24
  AND s.time >= f.firstseen AND s.time <= f.lastseen
WHERE s.time >= %d
  AND s.time < %d
  AND s.hour >= %d
  AND s.hour < %d
""" % (int(start.timestamp()), int(end.timestamp()), int(start.timestamp()), int(end.timestamp()),
         int(start.timestamp()), int(end.timestamp()))


def query_manifest():
    queries = {"flights": flight_sql(), "state_vectors": state_sql()}
    return {"schema": "OpenSky Trino data4", "period_start": START.isoformat(),
            "period_end_exclusive": END.isoformat(),
            "queries": {name: {"sql": sql, "sha256": hashlib.sha256(sql.encode()).hexdigest()}
                        for name, sql in queries.items()}}


def _credentials():
    required = ("OPENSKY_TRINO_USER", "OPENSKY_TRINO_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError("OpenSky Trino extraction requires %s" % ", ".join(missing))
    return os.environ[required[0]], os.environ[required[1]]


def extract(output_dir=PRIVATE_DIR):
    """Execute auditable queries when research credentials are present."""
    try:
        import pandas as pd
        import trino
        from trino.auth import BasicAuthentication
    except ImportError as exc:
        raise RuntimeError("OpenSky extraction requires the 'aviation' extra") from exc
    user, password = _credentials()
    host = os.environ.get("OPENSKY_TRINO_HOST", "trino.opensky-network.org")
    port = int(os.environ.get("OPENSKY_TRINO_PORT", "443"))
    catalog = os.environ.get("OPENSKY_TRINO_CATALOG", "minio")
    schema = os.environ.get("OPENSKY_TRINO_SCHEMA", "osky")
    os.makedirs(output_dir, exist_ok=True)
    connection = trino.dbapi.connect(host=host, port=port, user=user, catalog=catalog,
                                     schema=schema, http_scheme="https",
                                     auth=BasicAuthentication(user, password))
    outputs = {}
    for name, sql in (("flights", flight_sql()), ("state_vectors", state_sql())):
        frame = pd.read_sql_query(sql, connection)
        path = asset_path(output_dir, name + ".parquet")
        frame.to_parquet(path, index=False)
        outputs[name] = {"path": path, "rows": len(frame)}
    manifest = query_manifest()
    manifest.update(extracted_at=datetime.now(timezone.utc).isoformat(), outputs=outputs,
                    host=host, catalog=catalog, schema=schema)
    with open(asset_path(output_dir, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")
    return outputs
