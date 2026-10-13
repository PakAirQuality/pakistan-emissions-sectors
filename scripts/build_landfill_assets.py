"""The landfill asset table: OSM's 56 disposal-site polygons as prospective geometry.

WHY, AND WHY SO CAREFULLY. The waste sector allocates on ORIGIN (population) because
no release geometry is held; the sixth review asked for waste release assets. The held
OSM snapshot carries exactly 56 landuse=landfill polygons for the whole country - 13
named, median area 0.3 hectares - which is a SEED, not a surface: 56 polygons over a
sector spread across 134 districts cannot carry an SWDS allocation, and pretending
otherwise would put Pakistan's landfill methane wherever OSM mappers have been. The
four large named metro sites (Lakho Der and Mehmood Booti in Lahore, LFS Gondpass and
GTS Imtiaz around Karachi, plus Losar in Rawalpindi) are real, well-known disposal
sites and give the table its anchor value; everything else ships with a quality flag
that says what it is.

QUALITY FLAGS, the honest partition:
  named_site        the polygon carries a name - a mapped, identifiable facility
  unnamed_fragment  no name; most are sub-hectare mapping scraps
  suspect_remote    the one >2 km2 unnamed polygon on the Iran border, flagged rather
                    than dropped - deleting suspect data is how suspicion disappears

STILL PROSPECTIVE. status=prospective throughout; no stream references
facilities:landfills_prospective (the discipline test covers every prospective set
since rc9), and no tonne moves. Build-time geopandas/shapely per the kiln precedent;
deterministic; --check re-derives and diffs.

THE COVERAGE MASK (rc10, gate 4). Every asset class must say where it was looked
for, not just where it was found. OSM is nominally countrywide, so the honest
classes differ from the kilns' survey-scoped mask: a unit either has
observed_sites or is not_mapped_in_osm - and unmapped means NOBODY DREW A POLYGON
THERE, never that no disposal happens there. The mask makes the seed's sparseness
enumerable: most canonical units have no mapped site, which is exactly why the
waste allocation stays an origin allocation.

Usage:  python3 scripts/build_landfill_assets.py [--check]
Writes: data/gis/landfills/pak_landfill_assets.csv
        data/gis/landfills/pak_landfill_coverage.csv
        data/gis/landfills/LANDFILL_SOURCES.json
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

from pkinv.core import adm2 as adm2_core                   # noqa: E402

ZIP_PATH = asset_path(ROOT, "sources", "OSM", "pakistan-20260809",
                        "pakistan-latest-free.shp.zip")
ADM2_GEOJSON = asset_path(ROOT, "data", "gis", "PAK_ADM2.geojson")
OUT_DIR = asset_path(ROOT, "data", "gis", "landfills")

FIELDS = ("landfill_id", "name", "latitude", "longitude", "area_m2", "quality",
          "shape_id", "adm2_ids", "adm2_status", "status", "osm_id", "dataset",
          "licence")

SNAPSHOT_TIMESTAMP = "2026-08-06T20:21:21Z"
SUSPECT_AREA_M2 = 1.5e6      # >1.5 km2 AND unnamed -> suspect_remote


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def build():
    import geopandas as gpd

    gdf = gpd.read_file("zip://%s!gis_osm_landuse_a_free_1.shp" % ZIP_PATH,
                        where="fclass = 'landfill'")
    areas = gdf.geometry.to_crs("EPSG:32642").area

    from shapely.geometry import shape as shp
    from shapely.strtree import STRtree
    with open(ADM2_GEOJSON, encoding="utf-8") as handle:
        features = json.load(handle)["features"]
    geoms = [shp(f["geometry"]) for f in features]
    shape_ids = [f["properties"]["shapeID"] for f in features]
    tree = STRtree(geoms)
    shape_members = adm2_core.shape_to_adm2()

    rows = []
    for (_, r), area in zip(gdf.iterrows(), areas):
        centroid = r.geometry.centroid
        lat, lon = round(centroid.y, 5), round(centroid.x, 5)
        name = (r["name"] or "").strip()
        if name:
            quality = "named_site"
        elif area > SUSPECT_AREA_M2:
            quality = "suspect_remote"
        else:
            quality = "unnamed_fragment"
        sid = None
        for idx in tree.query(centroid):
            if geoms[idx].contains(centroid) or geoms[idx].touches(centroid):
                sid = shape_ids[idx]
                break
        if sid is None:
            shape_id, members, status = "", "", "unresolved-outside-simplified-boundary"
        else:
            members = shape_members.get(sid, [])
            shape_id = sid
            status = "one_to_one" if len(members) == 1 else "shared_shape"
        digest = hashlib.sha1(("%s,%s" % (lat, lon)).encode()).hexdigest()
        rows.append({
            "landfill_id": "landfill_%s" % digest[:10],
            "name": name, "latitude": lat, "longitude": lon,
            "area_m2": round(float(area), 1), "quality": quality,
            "shape_id": shape_id, "adm2_ids": ";".join(members),
            "adm2_status": status, "status": "prospective",
            "osm_id": r["osm_id"],
            "dataset": "OpenStreetMap landuse=landfill, Geofabrik snapshot %s"
                       % SNAPSHOT_TIMESTAMP,
            "licence": "ODbL"})
    rows.sort(key=lambda a: a["landfill_id"])

    provenance = {
        "source": "gis_osm_landuse_a_free_1 (fclass=landfill), Geofabrik Pakistan "
                  "shapefile extract",
        "snapshot_timestamp": SNAPSHOT_TIMESTAMP,
        "snapshot_zip_sha256": _sha256(ZIP_PATH),
        "licence": "ODbL",
        "polygons": len(rows),
        "named": sum(1 for r in rows if r["quality"] == "named_site"),
        "unnamed_fragments": sum(1 for r in rows
                                 if r["quality"] == "unnamed_fragment"),
        "suspect_remote": sum(1 for r in rows if r["quality"] == "suspect_remote"),
        "note": "a SEED, never an allocation surface: 56 polygons over a sector that "
                "spreads across 134 districts, coverage tracking OSM mapping effort. "
                "The named metro sites (Lakho Der, Mehmood Booti, LFS Gondpass, GTS "
                "Imtiaz, Losar) are the anchor value; the waste sector's allocation "
                "remains an origin allocation and says so.",
    }

    # the coverage mask over the canonical ADM2 frame, kiln-mask pattern: active
    # census districts plus the territory units (a mask that dropped AJK/ICT/GB
    # units would silently orphan any site mapped there)
    covered = {}
    for r in rows:
        members = [m for m in r["adm2_ids"].split(";") if m]
        for member in members:
            note = "" if len(members) == 1 else \
                "shared_shape_attribution: the geoBoundaries shape spans %s" \
                % ";".join(members)
            covered[member] = (covered.get(member, (0, note))[0] + 1, note)
    canonical = adm2_core.load_canonical()
    coverage = []
    for adm2_id, row in sorted(canonical.items()):
        if row["status"] not in ("active", "territory"):
            continue
        if adm2_id in covered:
            count, note = covered[adm2_id]
            coverage.append({"adm2_id": adm2_id, "province": row["province_id"],
                             "coverage": "observed_sites",
                             "observed_sites": count, "note": note})
        else:
            coverage.append({"adm2_id": adm2_id, "province": row["province_id"],
                             "coverage": "not_mapped_in_osm",
                             "observed_sites": "",
                             "note": "no landuse=landfill polygon in the OSM "
                                     "snapshot; unmapped means nobody drew one, "
                                     "not that no disposal happens here"})
    return rows, coverage, provenance


def _render(rows, fields=None):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(fields or FIELDS),
                            lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


COVERAGE_FIELDS = ("adm2_id", "province", "coverage", "observed_sites", "note")


def main(check=False):
    rows, coverage, provenance = build()
    ids = [r["landfill_id"] for r in rows]
    assert len(ids) == len(set(ids)), "landfill ids collide"
    texts = {
        "pak_landfill_assets.csv": _render(rows),
        "pak_landfill_coverage.csv": _render(coverage, COVERAGE_FIELDS),
        "LANDFILL_SOURCES.json": json.dumps(provenance, indent=2,
                                            sort_keys=True) + "\n",
    }
    if check:
        for name, text in texts.items():
            path = asset_path(OUT_DIR, name)
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
                print("%s is stale; run python3 scripts/build_landfill_assets.py"
                      % name)
                return 1
        print("landfill assets are current.")
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, text in texts.items():
        open(asset_path(OUT_DIR, name), "w", encoding="utf-8").write(text)
    observed = sum(1 for c in coverage if c["coverage"] == "observed_sites")
    print("wrote %d landfill assets (%d named, %d fragments, %d suspect) + "
          "coverage mask (%d of %d units with a mapped site)"
          % (len(rows), provenance["named"], provenance["unnamed_fragments"],
             provenance["suspect_remote"], observed, len(coverage)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
