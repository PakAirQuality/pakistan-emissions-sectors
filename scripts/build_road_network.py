"""The national road network from the held OSM snapshot: density raster + ADM2 road-km.

WHY. Road transport allocates on provincial fuel sales and holds no road geometry at
all - the fifth review's most obvious missing geospatial layer. The Geofabrik snapshot
is already on disk (sources/OSM/pakistan-20260809/, OpenStreetMap as of
2026-08-06T20:21:21Z, gitignored as a bulk re-downloadable cache), so this is an
extraction, not an acquisition. Two derivatives ship, both small enough to track:

  data/gis/roads/pak_road_density_267x340.npy   major-road length (km) per 0.05 degree
                                                cell, the established proxy-cache format
  outputs/pakemis_road_length_adm2.csv          road-km per canonical ADM2 unit x class

WHAT THIS IS NOT. A diagnostic and a next-stage input, never an allocation basis: no
row in data/stream_grid_proxy.csv or data/stream_geometry.csv points at these files,
and the 40.19 Mt road figure is set by fuel controls that geometry must never move.
Road length is not traffic - a class-weighted or ML traffic-propensity layer would
need held-out traffic observations this repository does not have, and the honest first
product is the geometry itself with its class breakdown.

METHOD. The four major functional classes (motorway, trunk, primary, secondary, plus
their _link ramps) are read from the snapshot with a pyogrio filter; each line is
segmentised to <=0.01 degree, per-segment geodesic lengths (WGS84) are attributed to
the 0.05 degree cell of the segment midpoint, and per-ADM2 totals follow the same
rasterised district labels the cube uses (cell -> district attribution, declared).
Residential/tertiary/unclassified roads are deliberately excluded: the national fuel
mass rides the trunk network, and the minor-road layer is dominated by mapping-effort
variance rather than road supply.

The rail precedent's one weakness - a dated but unhashed snapshot - is closed here:
ROAD_SOURCES.json carries the zip's sha256, and every build writes the same hash
into RAIL_SOURCES.json (same snapshot family).

Build-time geopandas/pyogrio/pyproj; nothing at runtime imports them. Deterministic;
--check re-derives and diffs (expensive: a 317 MB shapefile read).

Usage:  python3 scripts/build_road_network.py [--check]
Writes: data/gis/roads/pak_road_density_267x340.npy (+ .txt sidecar)
        data/gis/roads/ROAD_SOURCES.json
        outputs/pakemis_road_length_adm2.csv
"""
import csv
import hashlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

SNAPSHOT_DIR = asset_path(ROOT, "sources", "OSM", "pakistan-20260809")
ZIP_PATH = asset_path(SNAPSHOT_DIR, "pakistan-latest-free.shp.zip")
OUT_DIR = asset_path(ROOT, "data", "gis", "roads")
ADM2_CSV = asset_path(ROOT, "outputs", "pakemis_road_length_adm2.csv")

CLASSES = ("motorway", "trunk", "primary", "secondary")
FCLASSES = tuple(list(CLASSES) + ["%s_link" % c for c in CLASSES])

SOURCE_URL = "https://download.geofabrik.de/asia/pakistan-latest-free.shp.zip"
SNAPSHOT_TIMESTAMP = "2026-08-06T20:21:21Z"   # from the zip's README
DOWNLOAD_DATE = "2026-08-09"                  # per RAIL_SOURCES.json, same snapshot

RES = 0.05
SEGMENT_DEG = 0.01


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build():
    import geopandas as gpd
    import numpy as np
    import shapely
    from pyproj import Geod

    from pkinv.core.gis.grid import build_grid

    grid = build_grid()
    minx, miny, maxx, maxy = grid.bounds
    geod = Geod(ellps="WGS84")

    where = "fclass IN (%s)" % ", ".join("'%s'" % f for f in FCLASSES)
    gdf = gpd.read_file("zip://%s!gis_osm_roads_free_1.shp" % ZIP_PATH, where=where)

    rasters = {c: np.zeros((grid.height, grid.width), dtype=np.float64)
               for c in CLASSES}
    class_km = {c: 0.0 for c in CLASSES}
    class_km_extracted = {c: 0.0 for c in CLASSES}
    for base in CLASSES:
        members = gdf[gdf["fclass"].isin((base, base + "_link"))]
        if members.empty:
            continue
        segmented = shapely.segmentize(members.geometry.values, SEGMENT_DEG)
        coords, line_index = shapely.get_coordinates(segmented, return_index=True)
        same_line = line_index[1:] == line_index[:-1]
        lon1, lat1 = coords[:-1, 0][same_line], coords[:-1, 1][same_line]
        lon2, lat2 = coords[1:, 0][same_line], coords[1:, 1][same_line]
        _az12, _az21, metres = geod.inv(lon1, lat1, lon2, lat2)
        km = metres / 1000.0
        mid_lon = (lon1 + lon2) / 2.0
        mid_lat = (lat1 + lat2) / 2.0
        col = np.floor((mid_lon - minx) / RES).astype(np.int64)
        row = np.floor((maxy - mid_lat) / RES).astype(np.int64)
        inside = (col >= 0) & (col < grid.width) & (row >= 0) & (row < grid.height)
        np.add.at(rasters[base], (row[inside], col[inside]), km[inside])
        # class_km is ON-GRID km - what the shipped products contain. The sliver of
        # extracted ways whose segment midpoints fall outside the national bbox
        # (border roads running past the frame) is recorded separately.
        class_km[base] = float(km[inside].sum())
        class_km_extracted[base] = float(km.sum())

    total = np.zeros((grid.height, grid.width), dtype=np.float64)
    for c in CLASSES:
        total += rasters[c]

    adm2_rows = []
    from pkinv.core import adm2 as adm2_core
    canonical = adm2_core.load_canonical()
    name_by_idx = list(grid.districts)
    unit_by_name = {}
    for adm2_id, row in canonical.items():
        unit_by_name.setdefault(row["shape_name"], []).append(adm2_id)
    ids = grid.district_id
    valid = ids >= 0
    for c in CLASSES:
        sums = np.bincount(ids[valid].ravel().astype(np.int64),
                           weights=rasters[c][valid].ravel(),
                           minlength=len(name_by_idx))
        outside = float(rasters[c][~valid].sum())
        for idx, name in enumerate(name_by_idx):
            members = unit_by_name.get(name, [])
            adm2_rows.append({
                "adm2_id": ";".join(sorted(members)) if members else name,
                "province": grid.district_province[idx],
                "fclass": c,
                "road_km": round(float(sums[idx]), 3)})
        adm2_rows.append({"adm2_id": "outside_every_polygon",
                          "province": "", "fclass": c,
                          "road_km": round(outside, 3)})
    adm2_rows.sort(key=lambda r: (r["adm2_id"], r["fclass"]))

    # --- the link table (rc9), ROUTABLE since rc13 -------------------------------------
    import shapely
    coords_all, idx_all = shapely.get_coordinates(
        shapely.segmentize(gdf.geometry.values, SEGMENT_DEG), return_index=True)
    same = idx_all[1:] == idx_all[:-1]
    _a1, _a2, m = geod.inv(coords_all[:-1, 0][same], coords_all[:-1, 1][same],
                           coords_all[1:, 0][same], coords_all[1:, 1][same])
    import numpy as _np
    seg_owner = idx_all[1:][same]
    per_way = _np.bincount(seg_owner, weights=m / 1000.0, minlength=len(gdf))

    # GRAPH (rc13): endpoint nodes bucketed at 3 decimal places (~100 m, the rail
    # builder's healing rule for OSM's un-merged joints), connected components by
    # union-find over the node pairs. The component flag is what a router needs
    # first: 'main' edges reach each other, 'disconnected' edges do not.
    endpoints = []
    raw_coords, raw_idx = shapely.get_coordinates(gdf.geometry.values,
                                                  return_index=True)
    first_of = _np.searchsorted(raw_idx, _np.arange(len(gdf)), side="left")
    last_of = _np.searchsorted(raw_idx, _np.arange(len(gdf)), side="right") - 1

    def _node(lon, lat):
        return "%.3f_%.3f" % (round(lon, 3), round(lat, 3))

    node_ids = {}
    parent = []

    def _find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def _union(a, b):
        ra, rb = _find(a), _find(b)
        if ra != rb:
            parent[rb] = ra

    from_nodes, to_nodes = [], []
    for i in range(len(gdf)):
        fn = _node(raw_coords[first_of[i], 0], raw_coords[first_of[i], 1])
        tn = _node(raw_coords[last_of[i], 0], raw_coords[last_of[i], 1])
        for n in (fn, tn):
            if n not in node_ids:
                node_ids[n] = len(parent)
                parent.append(len(parent))
        _union(node_ids[fn], node_ids[tn])
        from_nodes.append(fn)
        to_nodes.append(tn)
    comp_size = {}
    for i in range(len(gdf)):
        root = _find(node_ids[from_nodes[i]])
        comp_size[root] = comp_size.get(root, 0) + 1
    main_root = max(comp_size, key=comp_size.get)

    # URBAN CONTEXT (rc13): built-up fraction sampled at the way's representative
    # point; the threshold is declared, not fitted. LENGTH-MAJORITY district (rc13):
    # the district carrying the most of the way's segment-midpoint km, replacing the
    # representative-point single-cell assignment - a long inter-district way now
    # lands where most of it lies.
    builtup = np.load(asset_path(ROOT, "data", "gis",
                                   "proxy_builtup_267x340.npy")).astype(np.float64)
    URBAN_BUILTUP_THRESHOLD = 0.10

    seg_mid_lon = (coords_all[:-1, 0][same] + coords_all[1:, 0][same]) / 2.0
    seg_mid_lat = (coords_all[:-1, 1][same] + coords_all[1:, 1][same]) / 2.0
    seg_col = _np.floor((seg_mid_lon - minx) / RES).astype(_np.int64)
    seg_row = _np.floor((maxy - seg_mid_lat) / RES).astype(_np.int64)
    seg_in = ((seg_col >= 0) & (seg_col < grid.width)
              & (seg_row >= 0) & (seg_row < grid.height))
    seg_district = _np.full(len(seg_owner), -1, dtype=_np.int64)
    seg_district[seg_in] = grid.district_id[seg_row[seg_in], seg_col[seg_in]]
    # per (way, district) km via a composite key bincount
    n_dist = len(grid.districts)
    key = seg_owner * (n_dist + 2) + (seg_district + 1)
    km_by_key = {}
    for k, kmv in zip(key.tolist(), (m / 1000.0).tolist()):
        km_by_key[k] = km_by_key.get(k, 0.0) + kmv
    majority_district = {}
    for k, kmv in km_by_key.items():
        way = k // (n_dist + 2)
        dist = k % (n_dist + 2) - 1
        cur = majority_district.get(way)
        if cur is None or kmv > cur[1]:
            majority_district[way] = (dist, kmv)

    # fuel-station context (rc13): stations per 0.05-degree cell from the snapshot's
    # own traffic layers - the one traffic-adjacent evidence held offline.
    station_cells = np.zeros((grid.height, grid.width), dtype=np.float64)
    for layer, geom_kind in (("gis_osm_traffic_free_1", "point"),
                             ("gis_osm_traffic_a_free_1", "poly")):
        tdf = gpd.read_file("zip://%s!%s.shp" % (ZIP_PATH, layer),
                            where="fclass = 'fuel'")
        pts = (tdf.geometry if geom_kind == "point"
               else tdf.geometry.representative_point())
        for pt in pts:
            c = int((pt.x - minx) / RES)
            rw = int((maxy - pt.y) / RES)
            if 0 <= rw < grid.height and 0 <= c < grid.width:
                station_cells[rw, c] += 1.0

    name_by_idx = list(grid.districts)
    reps = gdf.geometry.representative_point()
    link_rows = []
    for i, (_, r) in enumerate(gdf.iterrows()):
        lon, lat = reps.iloc[i].x, reps.iloc[i].y
        col = int((lon - minx) / RES)
        row_i = int((maxy - lat) / RES)
        in_grid = 0 <= row_i < grid.height and 0 <= col < grid.width
        urban = bool(in_grid and builtup[row_i, col] >= URBAN_BUILTUP_THRESHOLD)
        stations_here = float(station_cells[row_i, col]) if in_grid else 0.0
        maj = majority_district.get(i, (-1, 0.0))[0]
        link_rows.append({
            "osm_id": r["osm_id"], "fclass": r["fclass"],
            "name": r["name"] or "", "ref": r["ref"] or "",
            "oneway": {"B": "two_way", "F": "oneway", "T": "oneway_reversed"}.get(
                r["oneway"], r["oneway"]),
            "maxspeed": int(r["maxspeed"] or 0),
            "bridge": r["bridge"], "tunnel": r["tunnel"],
            "layer": int(r["layer"] or 0),
            "length_km": round(float(per_way[i]), 3),
            "district": name_by_idx[maj] if maj >= 0 else "",
            "from_node": from_nodes[i], "to_node": to_nodes[i],
            "component": ("main" if _find(node_ids[from_nodes[i]]) == main_root
                          else "disconnected"),
            "urban": "urban" if urban else "non_urban",
            "fuel_stations_cell": int(stations_here),
        })

    # --- calibrated traffic-propensity weights (rc13) ----------------------------------
    # DECLARED CONSTANTS, not fitted: no Pakistani traffic record exists to fit
    # against (benchmark task spatial_road_transport, pending_record). Class weights
    # are relative traffic per km in the spirit of functional-class AADT ratios;
    # urban and fuel-station factors price where demand concentrates. The product is
    # a PRICED ALTERNATIVE beside the builtup reference, never the reference itself.
    CLASS_WEIGHT = {"motorway": 3.0, "motorway_link": 3.0,
                    "trunk": 2.0, "trunk_link": 2.0,
                    "primary": 1.5, "primary_link": 1.5,
                    "secondary": 1.0, "secondary_link": 1.0}
    URBAN_FACTOR = 1.5
    STATION_K = 0.25          # weight multiplier per fuel station in the link's cell,
    STATION_CAP = 4           # capped - a 10-station cell is a city block, not 10x traffic

    for r in link_rows:
        w = (r["length_km"] * CLASS_WEIGHT[r["fclass"]]
             * (URBAN_FACTOR if r["urban"] == "urban" else 1.0)
             * (1.0 + STATION_K * min(r["fuel_stations_cell"], STATION_CAP)))
        r["weight_calibrated"] = round(w, 4)

    weight_rows = []
    by_district = {}
    for r in link_rows:
        d = r["district"]
        if not d:
            continue
        cur = by_district.setdefault(d, {"uniform_length": 0.0,
                                         "class_weighted": 0.0,
                                         "calibrated": 0.0})
        cur["uniform_length"] += r["length_km"]
        cur["class_weighted"] += r["length_km"] * CLASS_WEIGHT[r["fclass"]]
        cur["calibrated"] += r["weight_calibrated"]
    totals_w = {k: sum(v[k] for v in by_district.values())
                for k in ("uniform_length", "class_weighted", "calibrated")}
    prov_of = {name: grid.district_province[idx]
               for idx, name in enumerate(name_by_idx)}
    for d in sorted(by_district):
        v = by_district[d]
        weight_rows.append({
            "district": d, "province": prov_of.get(d, ""),
            "share_uniform_length": round(v["uniform_length"]
                                          / totals_w["uniform_length"], 6),
            "share_class_weighted": round(v["class_weighted"]
                                          / totals_w["class_weighted"], 6),
            "share_calibrated": round(v["calibrated"]
                                      / totals_w["calibrated"], 6),
            # WHAT THIS PRODUCT IS, stated after rc47 Wave 5 and not before it. These
            # are candidate district shares derived from the road GRAPH, and they are a
            # priced alternative. The note used to say "the allocation reference remains
            # builtup", which stopped being true when stream_grid_proxy.csv promoted the
            # road RASTER to the within-province basis for petrol and diesel: built-up
            # became the comparator, not the reference. Two different road products are
            # involved and only the raster allocates - saying otherwise invited the
            # reader to think the graph was in the reference allocation, or that the
            # reference was still built-up.
            "note": "candidate national shares from the road GRAPH; PRICED ALTERNATIVE "
                    "only. The within-province reference is the road RASTER "
                    "(stream_grid_proxy.csv transport/road_density, rc47 Wave 5); "
                    "built-up is the priced comparator. Provincial fuel marginals are "
                    "conserved by the bracket machinery whatever the within-province "
                    "shape says, so nothing here moves an ADM1 total"})

    oneway_km = {c: 0.0 for c in CLASSES}
    for r in link_rows:
        base = r["fclass"].replace("_link", "")
        if r["oneway"] in ("oneway", "oneway_reversed"):
            oneway_km[base] = oneway_km.get(base, 0.0) + r["length_km"]

    provenance = {
        "graph": {
            "nodes": len(node_ids),
            "components": len(comp_size),
            "main_component_links": int(comp_size[main_root]),
            "disconnected_links": int(len(link_rows) - comp_size[main_root]),
            "node_bucketing": "endpoints rounded to 3 decimal places (~100 m), "
                              "the rail builder's healing rule",
            "urban_links": sum(1 for r in link_rows if r["urban"] == "urban"),
            "urban_builtup_threshold": URBAN_BUILTUP_THRESHOLD,
        },
        "calibration": {
            "class_weight": {k: v for k, v in CLASS_WEIGHT.items()
                             if not k.endswith("_link")},
            "urban_factor": URBAN_FACTOR,
            "station_k": STATION_K, "station_cap": STATION_CAP,
            "fuel_stations_gridded": int(station_cells.sum()),
            "status": "DECLARED constants, unfitted: benchmark task "
                      "spatial_road_transport is pending_record - no Pakistani "
                      "traffic record exists to calibrate or score against",
        },
        "dual_carriageway_oneway_km": {c: round(v, 1)
                                       for c, v in oneway_km.items()},
        "dual_carriageway_statement": "OSM maps each carriageway of a dual "
                                      "carriageway as its own way; the oneway-km "
                                      "per class above bounds the way-km inflation "
                                      "(DECLARED, not de-duplicated - the rail "
                                      "corridor-normalisation precedent)",
        "source_url": SOURCE_URL,
        "snapshot_timestamp": SNAPSHOT_TIMESTAMP,
        "download_date": DOWNLOAD_DATE,
        "snapshot_zip_sha256": _sha256(ZIP_PATH),
        "layer": "gis_osm_roads_free_1",
        "licence": "ODbL",
        "fclass_filter": list(FCLASSES),
        "segment_deg": SEGMENT_DEG,
        "cell_attribution": "segment midpoint, 0.05 degree grid, rasterised ADM2 labels",
        "link_count": len(link_rows),
        "maxspeed_coverage_pct": round(100.0 * sum(1 for r in link_rows
                                                   if r["maxspeed"] > 0)
                                       / len(link_rows), 1),
        "no_lanes_statement": "the Geofabrik free schema carries no lanes, surface "
                              "or access columns; the link table cannot state "
                              "capacity under any framing",
        "class_km": {c: round(v, 1) for c, v in class_km.items()},
        "total_km": round(sum(class_km.values()), 1),
        "extracted_km_off_grid": round(sum(class_km_extracted.values())
                                       - sum(class_km.values()), 1),
        # ⚠ THIS NOTE WAS FALSE FROM rc47 UNTIL rc64. It said "a PRICED ALTERNATIVE,
        # never the allocation reference: no stream registry row points at these files",
        # and rc47 Wave 5 had promoted the raster to the declared basis - the shipped
        # ROAD_SOURCES.json was updated to say so and this generator was not. The
        # consequence was worse than a stale comment: --check reported the sidecar
        # "stale" and told the reader to re-run the builder, which would have
        # overwritten a correct provenance claim with a false one. Corrected against
        # data/shared/gis/stream_grid_proxy.csv, which carries
        # `transport / Road transport -> road_density` with the rc47 rationale.
        "note": 'rc47 Wave 5: PROMOTED - the road-density raster is the declared within-province basis for road-transport petrol and diesel (stream_grid_proxy.csv points at it); builtup remains the priced comparator and the ADM2 bracket keeps the decision reversible, the road-transport magnitude is set by fuel controls, and since rc13 the calibrated weight surface ships as a spatial-bracket alternate beside the builtup reference. Road length is not traffic - the calibration constants are declared, not fitted, and the benchmark task that would score them is pending_record. OSM maps each carriageway of a dual carriageway as its own way; the per-class oneway-km bound above declares the inflation.',
    }
    return total, adm2_rows, provenance, link_rows, weight_rows, gdf


def _render_csv(rows):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=("adm2_id", "province", "fclass",
                                             "road_km"), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def _render_rows(rows):
    """The text a DictWriter would emit for these rows, keyed on the first row's fields.

    Shared by the check and the write path so a product cannot be written by one and
    compared by the other - the divergence that left three road products unverified from
    rc47 to rc64.
    """
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(check=False):
    import numpy as np
    total, adm2_rows, provenance, link_rows, weight_rows, gdf = build()
    npy = total.astype(np.float32)
    sidecar = ("OSM major-road length km per 0.05 deg cell (motorway/trunk/primary/"
               "secondary + links), Geofabrik snapshot %s; see ROAD_SOURCES.json\n"
               % SNAPSHOT_TIMESTAMP)
    csv_text = _render_csv(adm2_rows)
    json_text = json.dumps(provenance, indent=2, sort_keys=True) + "\n"
    # ONE TEXT PER PRODUCT, BUILT ABOVE THE BRANCH. Until rc64 the links, weights and
    # parquet writes lived below the `if check: ... return` and were therefore never
    # compared, while all three named this command as their verification in
    # data/catalog/held_products.csv. That is the general defect: a check covers what its
    # producer writes BEFORE the early return, and adding a product below it extends the
    # write path without extending the check. Rendering here makes the two branches share
    # the text, so they cannot diverge again.
    links_text = _render_rows(link_rows)
    weights_text = _render_rows(weight_rows)

    if check:
        stale = []
        existing = np.load(asset_path(OUT_DIR, "pak_road_density_267x340.npy"))
        if not np.allclose(existing, npy, rtol=0, atol=1e-4):
            stale.append("pak_road_density_267x340.npy")
        if open(ADM2_CSV, encoding="utf-8").read() != csv_text:
            stale.append("pakemis_road_length_adm2.csv")
        held = json.load(open(asset_path(OUT_DIR, "ROAD_SOURCES.json"),
                              encoding="utf-8"))
        if held != provenance:
            # NAME THE FIELD. "stale: ROAD_SOURCES.json" sent a reader to a twenty-key
            # provenance dict with no indication of which key moved, and the answer matters:
            # a changed count means the graph moved and the products with it, while a changed
            # timestamp means only the sidecar did. The raster and the CSV are compared
            # above, so if they pass and this fails, the difference is metadata by
            # elimination - but a reader should not have to reason that out.
            differing = sorted(k for k in set(held) | set(provenance)
                               if held.get(k) != provenance.get(k))
            stale.append("ROAD_SOURCES.json (%s)" % ", ".join(differing))
        links_path = asset_path(ROOT, "outputs", "pakemis_road_links.csv")
        if open(links_path, encoding="utf-8").read() != links_text:
            stale.append("pakemis_road_links.csv")
        weights_path = asset_path(ROOT, "outputs", "pakemis_road_weights_adm2.csv")
        if open(weights_path, encoding="utf-8").read() != weights_text:
            stale.append("pakemis_road_weights_adm2.csv")
        # THE PARQUET IS A CONTENT CHECK, NOT A BYTE ONE. gpd.to_parquet embeds the writer's
        # library versions and its own metadata, so re-serialising and diffing bytes would
        # fail on a pyarrow upgrade and say nothing about the roads. What is checkable is
        # that the held file carries the same links as the CSV beside it, one geometry each.
        parquet_path = asset_path(ROOT, "outputs", "pakemis_road_links.parquet")
        try:
            import geopandas as gpd
            held_frame = gpd.read_parquet(parquet_path)
            if (len(held_frame) != len(link_rows)
                    or [c for c in held_frame.columns if c != "geometry"]
                    != list(link_rows[0])
                    or int(held_frame.geometry.notna().sum()) != len(link_rows)):
                stale.append("pakemis_road_links.parquet (rows/columns/geometry against "
                             "the link table)")
        except ImportError:
            print("note: geopandas absent, pakemis_road_links.parquet not compared")
        if stale:
            print("stale: %s; run python3 scripts/build_road_network.py"
                  % ", ".join(stale))
            return 1
        # THE COVERAGE CONTRACT (rc64). A check must NAME every product it compared, and
        # tests/test_held_product_freshness.py holds the held registry to those names: a
        # product registered against this command whose path is not printed here fails.
        # That is what makes adding a write below the early return impossible to miss.
        for covered in ("data/gis/pak_road_density_267x340.npy",
                        "data/gis/ROAD_SOURCES.json",
                        "outputs/pakemis_road_length_adm2.csv",
                        "outputs/pakemis_road_links.csv",
                        "outputs/pakemis_road_weights_adm2.csv",
                        "outputs/pakemis_road_links.parquet"):
            print("checked: %s" % covered)
        print("road products are current.")
        return 0

    os.makedirs(OUT_DIR, exist_ok=True)
    np.save(asset_path(OUT_DIR, "pak_road_density_267x340.npy"), npy)
    open(asset_path(OUT_DIR, "pak_road_density_267x340.npy.txt"), "w",
         encoding="utf-8").write(sidecar)
    open(asset_path(OUT_DIR, "ROAD_SOURCES.json"), "w",
         encoding="utf-8").write(json_text)
    open(ADM2_CSV, "w", encoding="utf-8").write(csv_text)

    links_path = asset_path(ROOT, "outputs", "pakemis_road_links.csv")
    open(links_path, "w", newline="", encoding="utf-8").write(links_text)

    weights_path = asset_path(ROOT, "outputs", "pakemis_road_weights_adm2.csv")
    open(weights_path, "w", newline="", encoding="utf-8").write(weights_text)
    print("weights: %d districts -> pakemis_road_weights_adm2.csv "
          "(uniform_length / class_weighted / calibrated candidates)"
          % len(weight_rows))

    # GeoParquet with simplified geometry - the review's asked-for delivery format.
    import shapely
    import geopandas as gpd
    import pandas as pd
    frame = gpd.GeoDataFrame(pd.DataFrame(link_rows),
                             geometry=shapely.simplify(gdf.geometry.values, 0.0005),
                             crs="EPSG:4326")
    parquet_path = asset_path(ROOT, "outputs", "pakemis_road_links.parquet")
    frame.to_parquet(parquet_path)
    print("links: %d rows -> CSV + GeoParquet (%.1f MB)"
          % (len(link_rows), os.path.getsize(parquet_path) / 1e6))

    # Close the rail precedent's missing-hash gap: same snapshot family, same digest.
    rail_sources = asset_path(ROOT, "data", "gis", "rail", "RAIL_SOURCES.json")
    rail = json.load(open(rail_sources, encoding="utf-8"))
    rail["snapshot_zip_sha256"] = provenance["snapshot_zip_sha256"]
    rail["snapshot_timestamp"] = SNAPSHOT_TIMESTAMP
    open(rail_sources, "w", encoding="utf-8").write(
        json.dumps(rail, indent=2, sort_keys=True) + "\n")

    print("wrote road products: %.0f km major roads (%s)"
          % (provenance["total_km"],
             ", ".join("%s %.0f" % (c, provenance["class_km"][c]) for c in CLASSES)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
