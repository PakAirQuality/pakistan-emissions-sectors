"""The versioned railway network, loaded and audited.

The network is a derived, committed artefact (data/gis/rail/pak_rail_network.geojson,
built by scripts/build_rail_network.py from the gitignored Geofabrik archive) because the
spatial reconciliation tests depend on its exact geometry - the ADM-boundary policy. The
audit's headline: 7,574 active line-km against the Year Book's 7,791 route-kilometres,
97 percent, with double-track parallel ways netting against branches OSM lacks.
"""

from pkinv.assets import asset_path
import csv
import json
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows

NETWORK = asset_path(DATA, "gis", "rail", "pak_rail_network.geojson")
YARDS = asset_path(DATA, "gis", "rail", "yards.csv")
WEIGHTS = asset_path(DATA, "activity", "railways", "corridor_weights.csv")


def load_network(path=NETWORK):
    """[{coords, corridor, status, km, edge_id}] - every feature of the committed file."""
    with open(path, encoding="utf-8") as f:
        fc = json.load(f)
    out = []
    for feat in fc["features"]:
        p = feat["properties"]
        out.append({"coords": feat["geometry"]["coordinates"],
                    "corridor": p["corridor"], "status": p["status"],
                    "km": p["km"], "edge_id": p["edge_id"]})
    return out


def load_weights(path=WEIGHTS):
    return {r["corridor"]: {"passenger": float(r["passenger_tier"]), "freight": float(r["freight_tier"]), "basis": r["basis"]} for r in read_rows(path, comments=False)}


def load_yards(path=YARDS):
    return [(float(r["lon"]), float(r["lat"]), float(r["wagons_loaded"])) for r in read_rows(path, comments=False)]


def audit(data, segments=None):
    """Corridor-by-corridor km and the route-km comparison the network must survive."""
    segments = segments or load_network()
    by_corridor = {}
    active = disconnected = 0.0
    for s in segments:
        if s["status"] == "active":
            active += s["km"]
            by_corridor[s["corridor"]] = by_corridor.get(s["corridor"], 0.0) + s["km"]
        else:
            disconnected += s["km"]
    return {"active_km": active, "disconnected_km": disconnected,
            "route_km_yearbook": data.p("route_km"),
            "ratio_osm_over_yearbook": active / data.p("route_km"),
            "by_corridor": by_corridor}
