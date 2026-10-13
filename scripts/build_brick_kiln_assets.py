"""The brick-kiln asset table: the held detection snapshot as first-class geometry.

WHY. The Hamdani et al. (2025) snapshot has sat in data/ml/brick_kilns_pk.csv with five
columns, a blank id field, a six-token source province vocabulary, no district
assignment, no checksum and no machine-readable provenance - registered as a prospective
geometry set but unusable as an asset layer. This script builds the asset table the
fifth review specified: a stable per-kiln identifier, the source attributes verbatim
beside their engine-vocabulary mappings, an ADM2 assignment by point-in-polygon against
the canonical boundary file, and a declared coverage mask over the canonical ADM2 frame.

WHAT THE ID IS. kiln_<10 hex of sha1("lat,lon,type")> - derived from the kiln's own
content, not its row position, so re-sorting or appending to the source cannot silently
renumber every kiln (the registry's old kiln_%05d ids did exactly that). The source has
no duplicate coordinate pairs, so the id is unique by construction and asserted anyway.

THE COVERAGE MASK IS DECLARED, NOT INFERRED. The survey is IGP-scoped; no IGP polygon is
published with it. The mask is therefore the honest minimum: every canonical ADM2 unit
either holds >=1 detected kiln (observed_kilns, with the count) or is marked
not_covered_by_survey - and absence outside the covered units means UNSURVEYED, never
zero kilns. Shared geoBoundaries shapes attribute their count to every member unit,
flagged shared_shape_attribution.

STILL PROSPECTIVE. No estimated stream references these points
(tests/test_facility_registry.py::test_prospective_rows_touch_no_stream), and this table
changes no reported tonne. It is the geometry half of a future industrial-solids
category, shipped so the day that category is estimated it starts from assets, not from
a five-column CSV.

Build-time geopandas/shapely per the rail-network precedent; nothing at runtime imports
them. Deterministic; --check re-derives and diffs.

Usage:  python3 scripts/build_brick_kiln_assets.py [--check]
Writes: data/gis/kilns/pak_brick_kiln_assets.csv
        data/gis/kilns/pak_brick_kiln_coverage.csv
        data/gis/kilns/BRICK_KILN_SOURCES.json
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
from pkinv.core.io import read_rows

SOURCE = asset_path(ROOT, "data", "ml", "brick_kilns_pk.csv")
ADM2_GEOJSON = asset_path(ROOT, "data", "gis", "PAK_ADM2.geojson")
OUT_DIR = asset_path(ROOT, "data", "gis", "kilns")

ASSET_FIELDS = ("kiln_id", "latitude", "longitude", "kiln_type", "source_province",
                "province", "shape_id", "adm2_ids", "adm2_status", "status",
                "dataset", "dataset_doi", "licence")
COVERAGE_FIELDS = ("adm2_id", "province", "coverage", "observed_kilns", "note")

# The dataset's six province tokens against the engine's five-value vocabulary
# (core/geography.PROVINCES): AJK and ICT are the engine's "Other".
PROVINCE_MAP = {
    "Punjab": "Punjab",
    "Sindh": "Sindh",
    "Khyber-Pakhtunkhwa": "Khyber Pakhtunkhwa",
    "Balochistan": "Balochistan",
    "Azad Kashmir": "Other",
    "Islamabad": "Other",
}

DATASET = "Hamdani et al. 2025, Brick Kiln Dataset for Pakistan's IGP Region Using AI"
DOI = "10.1038/s41597-025-05148-9"
ZENODO = "14038648"
LICENCE = "CC-BY-4.0"
# THE VERSION PIN (rc11). "Zenodo record 14038648" names a version whose Main.csv
# carries 11,277 rows, and the 11,272-row held snapshot matched no stated version -
# a versionless citation of a versioned dataset. The 2026-08 audit fetched every
# version's Main.csv and compared (lat, lon, type) key sets: version 14718244
# (2024-11-04) matches the held snapshot EXACTLY, zero differences either way; the
# 14038648 file's five extra rows are four coordinate-duplicate keys plus one kiln
# the held set lacks; the latest version (17897579, 2025-12-11) DROPS 687 kilns to
# a filtered subset. The pin is therefore 14718244, and the held snapshot is that
# version's kiln set reduced to five columns with content-hash ids.
ZENODO_VERSION = "14718244"
ZENODO_VERSION_DOI = "10.5281/zenodo.14718244"
ZENODO_VERSION_FILE = "Brick_Kilns_IGP_PK-Main.csv"
ZENODO_VERSION_FILE_MD5 = "e96975b1749e1f453d8a4f898ebe88bc"


def _read_source():
    return read_rows(SOURCE, comments=False)


def kiln_id(lat, lon, kiln_type):
    digest = hashlib.sha1(("%s,%s,%s" % (lat, lon, kiln_type)).encode()).hexdigest()
    return "kiln_%s" % digest[:10]


def _pip_index():
    """shape_id per kiln by point-in-polygon, one STRtree pass (build-time shapely)."""
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree
    with open(ADM2_GEOJSON, encoding="utf-8") as handle:
        features = json.load(handle)["features"]
    geoms, shape_ids = [], []
    for feature in features:
        geoms.append(shape(feature["geometry"]))
        shape_ids.append(feature["properties"]["shapeID"])
    tree = STRtree(geoms)
    def lookup(lat, lon):
        point = Point(float(lon), float(lat))
        for idx in tree.query(point):
            if geoms[idx].contains(point) or geoms[idx].touches(point):
                return shape_ids[idx]
        return None
    return lookup


def build():
    source = _read_source()
    lookup = _pip_index()
    shape_members = adm2_core.shape_to_adm2()
    canonical = adm2_core.load_canonical()

    assets = []
    per_shape = {}
    for r in source:
        sid = lookup(r["lat"], r["lon"])
        if sid is None:
            shape_id, members, status = "", "", "unresolved-outside-simplified-boundary"
        else:
            members = shape_members.get(sid, [])
            shape_id = sid
            status = "one_to_one" if len(members) == 1 else "shared_shape"
            per_shape[sid] = per_shape.get(sid, 0) + 1
        assets.append({
            "kiln_id": kiln_id(r["lat"], r["lon"], r["type"]),
            "latitude": r["lat"], "longitude": r["lon"], "kiln_type": r["type"],
            "source_province": r["province"],
            "province": PROVINCE_MAP[r["province"]],
            "shape_id": shape_id, "adm2_ids": ";".join(members),
            "adm2_status": status, "status": "prospective",
            "dataset": DATASET, "dataset_doi": DOI, "licence": LICENCE})
    assets.sort(key=lambda a: a["kiln_id"])

    covered = {}
    for sid, count in per_shape.items():
        members = shape_members.get(sid, [])
        for member in members:
            note = "" if len(members) == 1 else \
                "shared_shape_attribution: the geoBoundaries shape spans %s" \
                % ";".join(members)
            covered[member] = (covered.get(member, (0, note))[0] + count, note)
    coverage = []
    for adm2_id, row in sorted(canonical.items()):
        # Active census districts plus the territory units: kilns are detected in AJK
        # and ICT, and a mask that dropped those units would silently orphan 87 points.
        if row["status"] not in ("active", "territory"):
            continue
        if adm2_id in covered:
            count, note = covered[adm2_id]
            coverage.append({"adm2_id": adm2_id, "province": row["province_id"],
                             "coverage": "observed_kilns",
                             "observed_kilns": count, "note": note})
        else:
            coverage.append({"adm2_id": adm2_id, "province": row["province_id"],
                             "coverage": "not_covered_by_survey", "observed_kilns": "",
                             "note": "the survey is IGP-scoped and publishes no "
                                     "coverage polygon; absence here means "
                                     "unsurveyed, not zero kilns"})

    with open(SOURCE, "rb") as handle:
        sha = hashlib.sha256(handle.read()).hexdigest()
    provenance = {
        "dataset": DATASET,
        "article_doi": DOI,
        "data_record": "Zenodo record %s" % ZENODO,
        "version_record": "Zenodo version %s" % ZENODO_VERSION,
        "version_doi": ZENODO_VERSION_DOI,
        "version_file": ZENODO_VERSION_FILE,
        "version_file_md5": ZENODO_VERSION_FILE_MD5,
        "licence": LICENCE,
        "held_snapshot": "data/ml/brick_kilns_pk.csv",
        "held_snapshot_sha256": sha,
        "held_rows": len(source),
        "note": "the held snapshot's 11,272 kiln locations match Zenodo version "
                "14718244's Main.csv EXACTLY under (lat, lon, type) keys - the "
                "version pin above, established by fetching every published "
                "version. The concept record's 14038648 file carries 11,277 rows: "
                "four coordinate-duplicate keys and one kiln the held set lacks, "
                "which is the previously unversioned 11,272-vs-11,277 discrepancy. "
                "The id column in the snapshot is blank throughout; kiln_id here is "
                "a content hash of (lat, lon, type), stable under re-sorting.",
        "outside_boundary_points": sum(1 for a in assets
                                       if a["adm2_status"]
                                       == "unresolved-outside-simplified-boundary"),
    }
    return assets, coverage, provenance


def _render(rows, fields):
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return out.getvalue()


def main(check=False):
    assets, coverage, provenance = build()
    ids = [a["kiln_id"] for a in assets]
    assert len(ids) == len(set(ids)), "content-hash kiln ids collide"
    assert len(assets) == provenance["held_rows"]
    texts = {
        "pak_brick_kiln_assets.csv": _render(assets, ASSET_FIELDS),
        "pak_brick_kiln_coverage.csv": _render(coverage, COVERAGE_FIELDS),
        "BRICK_KILN_SOURCES.json": json.dumps(provenance, indent=2,
                                              sort_keys=True) + "\n",
    }
    if check:
        for name, text in texts.items():
            path = asset_path(OUT_DIR, name)
            if not os.path.exists(path) or open(path, encoding="utf-8").read() != text:
                print("%s is stale; run python3 scripts/build_brick_kiln_assets.py"
                      % name)
                return 1
        print("brick-kiln assets are current.")
        return 0
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, text in texts.items():
        open(asset_path(OUT_DIR, name), "w", encoding="utf-8").write(text)
    observed = [c for c in coverage if c["coverage"] == "observed_kilns"]
    print("wrote %d kiln assets (%d outside the simplified boundary), coverage over "
          "%d canonical units (%d observed)"
          % (len(assets), provenance["outside_boundary_points"], len(coverage),
             len(observed)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(check="--check" in sys.argv))
