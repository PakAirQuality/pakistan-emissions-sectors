"""Build the versioned railway network from the Geofabrik OSM extract.

WHAT THIS PRODUCES. data/gis/rail/pak_rail_network.geojson - the slim, versioned, corridor-
tagged network the spatial model burns - from the (gitignored) Geofabrik shapefile bundle
under sources/OSM/. The derived file is committed because reconciliation tests depend on
its exact geometry, the same policy as the ADM boundary files; the 360 MB source archive is
re-fetchable and stays out of git, with RAIL_SOURCES.json recording URL, date and the ODbL
attribution beside the derived file.

HOW CORRIDORS ARE ASSIGNED. OSM's Pakistani railway ways carry almost no name tags, so
corridors cannot be read off the data. Instead data/gis/rail/corridors.csv lists waypoint
coordinates (well-known junctions and cities) per corridor; each consecutive pair is
connected by shortest path over the network graph (plain Dijkstra - no new dependency),
and traversed segments take the corridor's tag. Main-component segments no path claims
become branch_other; segments outside the main component are kept but flagged
disconnected (isolated yard trackage and fragments - they receive no line-haul weight).

fclass=rail only: the subway class (Lahore's Orange Line among it) is electric urban rail
with zero direct 1A3c combustion, outside the operator and outside this network.

Usage:  python3 scripts/build_rail_network.py
Writes: data/gis/rail/pak_rail_network.geojson, data/gis/rail/RAIL_SOURCES.json
"""

from pkinv.assets import asset_path
import csv
import glob
import heapq
import json
import math
import os
from collections import defaultdict
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = asset_path(ROOT, "data", "gis", "rail")
CORRIDORS = asset_path(OUT_DIR, "corridors.csv")
SNAP_MAX_DEG = 0.20          # a waypoint must land within ~20 km of the network
SIMPLIFY_DEG = 0.0005        # ~50 m: shrinks the GeoJSON without moving any cell


def _km(x0, y0, x1, y1):
    lat = math.radians((y0 + y1) / 2.0)
    return math.hypot((x1 - x0) * 111.320 * math.cos(lat), (y1 - y0) * 110.574)


def _node(pt):
    # ~100 m buckets: OSM ways that should join frequently stop short by tens of metres,
    # and un-merged joints turn into hundred-kilometre Dijkstra detours. Merging nodes at
    # this scale closes the gaps; parallel tracks merging at a bucket is harmless here.
    return (round(pt[0], 3), round(pt[1], 3))


def _line_km(coords):
    return sum(_km(x0, y0, x1, y1)
               for (x0, y0), (x1, y1) in zip(coords[:-1], coords[1:]))


def load_segments():
    import geopandas as gpd
    src = sorted(glob.glob(asset_path(ROOT, "sources", "OSM", "pakistan-*",
                                        "gis_osm_railways_free_1.shp")))[-1]
    g = gpd.read_file(src)
    g = g[g.fclass == "rail"]
    segs = []
    for _i, row in g.iterrows():
        geom = row.geometry
        parts = geom.geoms if geom.geom_type == "MultiLineString" else [geom]
        for part in parts:
            coords = list(part.coords)
            if len(coords) >= 2:
                segs.append({"osm_id": str(row.osm_id), "coords": coords,
                             "km": _line_km(coords)})
    return src, segs


def build_graph(segs):
    adj = defaultdict(list)
    for i, s in enumerate(segs):
        u, v = _node(s["coords"][0]), _node(s["coords"][-1])
        adj[u].append((v, s["km"], i))
        adj[v].append((u, s["km"], i))
    return adj


def main_component(adj):
    best, seen_all = set(), set()
    for start in adj:
        if start in seen_all:
            continue
        comp, stack = set(), [start]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            stack.extend(v for v, _k, _i in adj[n] if v not in comp)
        seen_all |= comp
        if len(comp) > len(best):
            best = comp
    return best


def snap(adj, comp, lon, lat):
    node, dist = None, float("inf")
    for n in comp:
        d = math.hypot(n[0] - lon, n[1] - lat)
        if d < dist:
            node, dist = n, d
    return (node, dist) if dist <= SNAP_MAX_DEG else (None, dist)


def dijkstra_edges(adj, src, dst):
    """Set of segment indices on the shortest path src -> dst, or None."""
    dist, prev = {src: 0.0}, {}
    heap = [(0.0, src)]
    while heap:
        d, n = heapq.heappop(heap)
        if n == dst:
            break
        if d > dist.get(n, float("inf")):
            continue
        for v, km, idx in adj[n]:
            nd = d + km
            if nd < dist.get(v, float("inf")):
                dist[v], prev[v] = nd, (n, idx)
                heapq.heappush(heap, (nd, v))
    if dst not in prev and dst != src:
        return None
    edges, n = set(), dst
    while n != src:
        n, idx = prev[n]
        edges.add(idx)
    return edges


def main():
    src, segs = load_segments()
    adj = build_graph(segs)
    comp = main_component(adj)
    print("segments %d, graph nodes %d, main component %d nodes"
          % (len(segs), len(adj), len(comp)))

    corridor_of = {}
    with open(CORRIDORS, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    by_corridor = defaultdict(list)
    for r in rows:
        by_corridor[r["corridor"]].append(r)
    for corridor, pts in by_corridor.items():
        pts = sorted(pts, key=lambda r: int(r["seq"]))
        nodes = []
        for p in pts:
            node, d = snap(adj, comp, float(p["lon"]), float(p["lat"]))
            if node is None:
                raise SystemExit("waypoint %s (%s) is %.2f deg off the network"
                                 % (p["waypoint"], corridor, d))
            nodes.append(node)
        claimed = 0
        for (a, b), (pa, pb) in zip(zip(nodes[:-1], nodes[1:]),
                                    zip(pts[:-1], pts[1:])):
            edges = dijkstra_edges(adj, a, b)
            if edges is None:
                raise SystemExit("no path %s between %s" % (corridor, (a, b)))
            leg_km = sum(segs[i]["km"] for i in edges)
            print("    leg %-18s -> %-18s %6.0f km  (%d segs)"
                  % (pa["waypoint"], pb["waypoint"], leg_km, len(edges)))
            for i in edges:
                corridor_of.setdefault(i, corridor)
            claimed += len(edges)
        print("  %-14s %4d segments, %6.0f km"
              % (corridor, claimed,
                 sum(segs[i]["km"] for i, c in corridor_of.items()
                     if c == corridor)))

    try:
        from shapely.geometry import LineString
        simplify = lambda cs: list(LineString(cs).simplify(SIMPLIFY_DEG).coords)
    except ImportError:
        simplify = lambda cs: cs

    features, km_active, km_disconnected = [], 0.0, 0.0
    for i, s in enumerate(segs):
        in_main = _node(s["coords"][0]) in comp
        corridor = corridor_of.get(i, "branch_other" if in_main else "")
        status = "active" if in_main else "disconnected"
        if in_main:
            km_active += s["km"]
        else:
            km_disconnected += s["km"]
        features.append({
            "type": "Feature",
            "properties": {"edge_id": i, "osm_id": s["osm_id"],
                           "corridor": corridor, "status": status,
                           "km": round(s["km"], 4)},
            "geometry": {"type": "LineString",
                         "coordinates": [[round(x, 5), round(y, 5)]
                                         for x, y in simplify(s["coords"])]}})

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(asset_path(OUT_DIR, "pak_rail_network.geojson"), "w",
              encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)

    meta = {
        "source": "Geofabrik pakistan-latest-free.shp.zip, layer gis_osm_railways_free_1",
        "source_url": "https://download.geofabrik.de/asia/pakistan-latest-free.shp.zip",
        "download_date": str(date.today()),
        "licence": "OpenStreetMap contributors, Open Database License (ODbL) 1.0; "
                   "this derived file inherits ODbL share-alike",
        "filter": "fclass == 'rail' (subway/urban electric excluded)",
        "segments": len(segs),
        "km_active_incl_parallel_tracks": round(km_active),
        "km_disconnected_fragments": round(km_disconnected),
        "year_book_route_km": 7791,
        "audit_note": "OSM line-km exceed route-km because double-track sections and "
                      "yard trackage map as parallel ways; the corridor normalisation "
                      "makes parallels share their corridor's weight.",
    }
    with open(asset_path(OUT_DIR, "RAIL_SOURCES.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    print("active %d km (Year Book route-km 7,791), disconnected fragments %d km"
          % (km_active, km_disconnected))


if __name__ == "__main__":
    main()
