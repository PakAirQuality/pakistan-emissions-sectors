"""Export stable data assets and runtime bindings into an immutable release contract."""
import csv
import hashlib
import io
import os
import re
from pathlib import Path

from pkinv.assets import catalog
from pkinv.paths import ROOT

SCHEMA = "pakemis.asset_catalog/v1"
PUBLIC_LICENSES = {"own-work", "own-work-compilation", "public-licence"}
CLAIM_REGISTRIES = {
    "emission_factors": "data/emission_factors.csv", "parameters": "data/parameters.csv",
    "uncertainty_parameters": "outputs/national_uncertainty_parameters.csv",
    "source_documents": "data/source_documents.csv", "source_register": "outputs/pakemis_source_register.csv",
    "public_documents": "data/public_documents.csv", "temporal_profiles": "data/temporal_profiles.csv",
    "temporal_profile_weights": "outputs/pakemis_temporal_profiles.csv",
    "stream_grid_proxy": "data/stream_grid_proxy.csv", "stream_geometry": "data/stream_geometry.csv",
    "allowed_grid_fallbacks": "data/allowed_grid_fallbacks.csv", "geometry_sets": "data/geometry_sets.csv",
    "release_heights": "data/release_heights.csv", "grid_fallbacks": "outputs/pakemis_grid_fallbacks.csv",
    "validation_catalog": "outputs/pakemis_validation_catalog.csv",
    "validation_catalog_declared": "data/validation_catalog.csv",
    "validation_scorecard": "outputs/pakemis_validation_scorecard.csv",
    "validation_sector_scorecard": "outputs/pakemis_validation_sector_scorecard.csv",
    "benchmarks": "data/benchmarks.csv", "data_gaps": "data/data_gaps.csv",
    "source_streams": "outputs/pakemis_source_streams.csv",
}
RUNTIME = {
    "method_registry": "data/method_registry.csv",
    "geometry_adm1": "data/gis/PAK_ADM1.geojson",
    "geometry_adm2": "data/gis/PAK_ADM2.geojson",
    "boundary_sources": "data/gis/BOUNDARY_SOURCES.json",
    "geography_crosswalk": "data/adm2_canonical.csv",
}


def _list(value):
    return [part.strip() for part in (value or "").split(";") if part.strip()]


def _path(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("asset path escapes release: %s" % relative)
    return root / path


def _restricted_absent(root, relative):
    from pkinv.core import layers
    return layers.public_clone_without_layers(os.fspath(root)) and layers.is_restricted(relative)


def _prior_digested(root):
    """Storage paths whose committed record carries a digest: the restricted files a public
    clone cannot hold but the release recorded (the rasters, the boundary documents)."""
    return {a.get("storage_path") for a in _prior_assets(root).values() if a.get("sha256")}


def _prior_assets(root):
    import json
    path = Path(root) / "outputs" / "semantic" / "semantic_release.json"
    if not path.is_file():
        return {}
    release = json.loads(path.read_text(encoding="utf-8"))
    return {a["asset_id"]: a for a in release.get("asset_catalog", {}).get("assets", [])}


def _travels(storage):
    """Whether a reader's tree can hold this file: the deposit carries it, or it is not data.

    A digest recorded only because a file happened to be on the maintainer's disk is a fact
    about one checkout. rc68's clean rebuild lacked three undeposited internal assets (an
    OCHA boundary zip, the GCD-Rice raster, sources_freeze.txt) and its contract differed
    from the release on exactly those digests.
    """
    import fnmatch
    from pkinv.report import deposit_manifest
    if not storage.startswith("data/"):
        return True
    if deposit_manifest._excluded(storage):
        return False
    return any(fnmatch.fnmatch(storage, pattern)
               for _kind, patterns in deposit_manifest.DEPOSIT_PATTERNS for pattern in patterns)


def build(inputs, root=ROOT):
    """One asset inventory drives fetching, serving, library metadata, and internal readers."""
    root = Path(root)
    declarations = catalog(root)
    by_legacy = {row["legacy_path"]: row for row in declarations}
    tables = {table["source_path"]: table for table in inputs["tables"]}
    required = set(CLAIM_REGISTRIES.values()) | set(RUNTIME.values())
    # Derived registries stay in outputs/. They have stable bindings but are not
    # additional authoritative source tables in the sector asset inventory.
    for legacy in sorted(required - by_legacy.keys()):
        if not legacy.startswith("outputs/"):
            raise ValueError("required runtime asset is not registered: %s" % legacy)
        row = {"asset_id": "product." + Path(legacy).stem, "legacy_path": legacy,
               "path": legacy, "owner_sector": "shared", "purpose": "evidence",
               "kind": "derived", "publication": "compatibility", "license": "own-work",
               "title": Path(legacy).stem.replace("_", " "), "description": "Release evidence table."}
        declarations.append(row)
        by_legacy[legacy] = row
    assets, ids, filenames = [], set(), {}
    for row in declarations:
        asset_id, legacy = row["asset_id"], row["legacy_path"]
        if asset_id in ids:
            raise ValueError("duplicate asset ID: %s" % asset_id)
        ids.add(asset_id)
        table = tables.get(legacy)
        relative = table["path"] if table else row.get("canonical_path") or row["path"]
        path = _path(root, relative)
        publication = row.get("publication") or "internal"
        licence = row.get("license") or "not-established"
        downloadable = publication in {"library", "compatibility"} and licence in PUBLIC_LICENSES
        packaged = downloadable or legacy in required
        asset = {"asset_id": asset_id, "legacy_path": legacy, "path": relative,
                 "storage_path": row["path"], "owner_sector": row.get("owner_sector") or "shared",
                 "sectors": _list(row.get("applies_to_sectors")) or [row.get("owner_sector") or "shared"],
                 "purpose": row.get("purpose") or "evidence", "kind": row.get("kind") or "reference",
                 "title": row.get("title") or asset_id, "description": row.get("description") or "",
                 "publication": publication, "license": licence, "source_refs": _list(row.get("source_refs")),
                 "producer": row.get("producer") or "", "bundle_id": row.get("bundle_id") or "",
                 "downloadable": downloadable, "packaged": packaged,
                 "aliases": []}
        if not path.is_file() or not (packaged or _travels(row["path"])):
            if not path.is_file() and _restricted_absent(root, row["path"]) and \
                    (packaged or row["path"] in _prior_digested(root)):
                # rc69: a public clone without the restricted layers holds no third-party
                # document or raster (pkinv.core.layers), yet the release records them: a few
                # as packaged library assets (the COD-AB boundaries), the rasters with their
                # digests. Their record is the committed release's own,
                # exactly as the deposit seeds a document-reading phase's product; a release
                # is never built here (release_manifest.build() refuses the absent mode).
                prior = _prior_assets(root).get(asset_id)
                if prior is None:
                    raise ValueError("restricted asset %s is absent and the committed release "
                                     "has no record of it" % relative)
                assets.append(dict(prior))
                filenames[prior.get("filename", "")] = asset_id
                continue
            if packaged:
                raise ValueError("required release asset is absent: %s" % relative)
            assets.append(asset)
            continue
        payload = path.read_bytes()
        asset.update(sha256=hashlib.sha256(payload).hexdigest(), bytes=len(payload))
        if table:
            if asset["sha256"] != table["sha256"]:
                raise ValueError("canonical asset differs from its catalog: %s" % asset_id)
            asset.update(table_id=table["table_id"], columns=table["columns"],
                         row_count=table["row_count"], primary_key=["Record ID"],
                         canonical_path=relative)
            filename = "input_" + re.sub(r"[^a-zA-Z0-9_]", "_", table["table_id"]) + ".csv"
        else:
            filename = "asset_" + re.sub(r"[^a-zA-Z0-9_]", "_", asset_id) + path.suffix.lower()
            if path.suffix.lower() == ".csv":
                reader = csv.DictReader(line for line in io.StringIO(payload.decode("utf-8-sig"), newline="")
                                        if not line.startswith("#"))
                asset["columns"] = [{"field_id": name, "name": name} for name in reader.fieldnames or []]
                asset["row_count"] = sum(1 for _ in reader)
        if downloadable and legacy in required:
            asset["aliases"].append(filename)
            filename = os.path.basename(legacy)
        asset["filename"] = filename
        for public_name in [filename] + asset["aliases"] if downloadable else []:
            if public_name in filenames and filenames[public_name] != asset_id:
                raise ValueError("public asset filename collision: %s" % public_name)
            filenames[public_name] = asset_id
        assets.append(asset)
    bindings = {name: by_legacy[legacy]["asset_id"] for name, legacy in RUNTIME.items()}
    bindings["claim_registries"] = {name: by_legacy[legacy]["asset_id"]
                                     for name, legacy in CLAIM_REGISTRIES.items()}
    return {"schema": SCHEMA, "assets": sorted(assets, key=lambda asset: asset["asset_id"]),
            "bindings": bindings}
