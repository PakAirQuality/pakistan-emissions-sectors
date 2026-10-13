"""One-time, digest-checked sector layout migration; no raw documents are moved.

Run without arguments to prepare logs/data_layout_plan.csv. --apply records the
move map and moves only its declared files. Scientific source IDs remain aliases.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

FIELDS = ("asset_id", "legacy_path", "path", "canonical_path", "owner_sector", "purpose",
          "kind", "producer", "publication", "license", "bundle_id", "title", "description",
          "source_refs", "applies_to_sectors", "maintained")
SECTORS = {"agriculture", "aviation", "fugitives", "industry", "ippu", "power", "railways",
           "residential", "transport", "waste", "lulucf"}
AGRICULTURE = {"burning_params", "cui2021_pak_ef", "fertilizer_calendar", "gleam_mms", "mms_shares",
               "nfdc_offtake", "nowcast_params", "parameters", "residue_params", "rice_calendar",
               "rice_temperature_climatology"}
CATALOG_STEMS = {"acquisition_attempts", "artifact_roles", "canonical_columns", "canonical_consumers",
                 "canonical_tables", "download_catalog", "raw_manifest", "source_documents",
                 "public_documents", "source_keys", "source_search_log", "sources_freeze",
                 "cross_tree_duplicates_baseline", "consumed_derivatives", "not_retained_register",
                 "held_products", "product_columns", "product_schemas", "compatibility_view_formats"}
METADATA_STEMS = {"source_manifest", "hfc_inventory_import_contract", "master_data_gap_matrix",
                  "evidence_maturity", "cdm_access_manifest"}
NONCANONICAL = METADATA_STEMS | {"data_request_packets"}
FACTS = {"fugitives/anchor_activity", "residential/fuel_supply_observations",
         "residential/fuel_supply_annotations", "ippu/company_production",
         "ippu/company_production_evidence", "ippu/company_roster"}
VIEWS = {"aviation/fuel_controls_2023_24", "fugitives/anchor_activity_2021_23",
         "fugitives/anchor_activity_2023_24", "residential/fuel_supply",
         "residential/fuel_supply_history", "ippu/company_clinker_2023_24",
         "ippu/company_clinker_series", "ippu/cement_producer_census_2023_24"}


def rows(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def write(path, records, fields):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(records)


def classify(relative, table=None):
    p = Path(relative)
    stem, parts = p.stem, p.parts
    owner, purpose, suffix = "shared", "metadata", p.name
    if relative.startswith("data/activity/"):
        lane = parts[2]
        if lane in SECTORS:
            owner, suffix = lane, "/".join(parts[3:])
        elif lane == "wastewater":
            owner, suffix = "waste", "wastewater/" + "/".join(parts[3:])
        elif lane == "historical":
            owner, suffix = "agriculture", "historical/" + p.name
        elif lane == "monthly":
            suffix = "monthly/" + p.name
        else:
            owner = "agriculture"
        purpose = "activity"
        if "/requests/" in relative:
            purpose, suffix = "requests", "templates/" + p.name
        elif stem == "data_request_packets":
            purpose, suffix = "requests", "register.csv"
        elif stem in METADATA_STEMS:
            purpose = "metadata"
        elif any(word in stem for word in ("alias", "crosswalk", "overrides", "vehicle_classes", "operator_groups")):
            purpose = "lookups"
        elif any(word in stem for word in ("evidence", "benchmark", "diagnostic", "crosscheck", "discrepanc", "audit", "reconciliation", "completeness")):
            purpose = "evidence"
    elif relative.startswith("data/extracted/unfccc/"):
        owner = stem.split("_")[0]
        purpose, suffix = "evidence", "unfccc/" + p.name
    elif relative.startswith("data/gis/"):
        purpose, suffix = "gis", "/".join(parts[2:])
        if parts[2] in ("rail", "roads", "kilns", "landfills"):
            owner = {"rail": "railways", "roads": "transport", "kilns": "industry", "landfills": "waste"}[parts[2]]
            suffix = "/".join(parts[3:])
        elif any(word in p.name.lower() for word in ("rice", "cropland", "livestock", "manure", "firms")):
            owner = "agriculture"
    elif relative.startswith("data/nfdc/"):
        purpose, suffix = "activity", "nfdc/" + p.name
    elif relative.startswith("data/pbs_census/"):
        purpose, suffix = "activity", "pbs_census/" + p.name
    elif relative.startswith("data/manifests/"):
        purpose, suffix = "catalog", "manifests/" + p.name
    elif relative.startswith(("data/district_records/", "data/gleam/", "data/gmw/")):
        owner = "lulucf" if parts[1] == "gmw" else "agriculture"
        purpose, suffix = "evidence", parts[1] + "/" + p.name
    elif relative.startswith(("data/validation/", "data/benchmark_splits/", "data/ml/")):
        purpose, suffix = "evidence", "/".join(parts[1:])
    elif relative.startswith("data/schemas/"):
        purpose, suffix = "catalog", "schemas/" + p.name
    elif len(parts) == 2:
        if stem in CATALOG_STEMS or stem.startswith(("activity_", "verification_")):
            purpose = "catalog"
        elif stem in AGRICULTURE:
            owner, purpose = "agriculture", "parameters"
        elif any(stem.startswith(s + "_") for s in SECTORS):
            owner = next(s for s in sorted(SECTORS) if stem.startswith(s + "_"))
            purpose = "parameters"
        elif stem in ("monthly_data_requests", "data_gaps"):
            purpose = "requests"
        elif any(word in stem for word in ("benchmark", "validation", "transcription", "claim")):
            purpose = "evidence"
        elif any(word in stem for word in ("adm2", "geometry", "grid", "spatial", "release_heights")):
            purpose = "gis"
        elif stem in ("periods", "months", "province_shares", "facility_registry", "physical_sources", "stream_reporting_sector"):
            purpose = "lookups"
        elif any(word in stem for word in ("factor", "parameter", "scenario", "policy", "scope", "uncertainty", "temporal", "method")):
            purpose = "parameters"
    if purpose == "catalog":
        destination = "data/catalog/" + suffix
    else:
        base = "data/shared" if owner == "shared" else "data/sectors/" + owner
        destination = base + "/" + purpose + "/" + suffix
    return owner, purpose, destination


def prepare():
    tables = rows(ROOT / "data/canonical_tables.csv")
    if not tables:
        raise SystemExit("Migration already applied; validate with make data-check.")
    by_source = {t["source_path"]: t for t in tables}
    licenses = {r["path"]: r for r in rows(ROOT / "outputs/pakemis_deposit_manifest.csv")}
    provenance = {r["data_file"]: r for r in rows(ROOT / "outputs/pakemis_data_provenance.csv")}
    documents = {r["data_file"]: r for r in rows(ROOT / "data/source_documents.csv")}
    consumers = {}
    for r in rows(ROOT / "data/canonical_consumers.csv"):
        consumers.setdefault(r["source_path"], set()).add(r["sector"])
    candidates = []
    for path in (ROOT / "data").rglob("*"):
        rel = path.relative_to(ROOT).as_posix()
        if not path.is_file() or any(part in {"raw", "cache", "baselines", "canonical", "sectors", "shared", "catalog"} for part in path.relative_to(ROOT / "data").parts[:-1]):
            continue
        if path.name.startswith("."):
            continue
        if rel.startswith("data/gis/") or path.suffix.lower() in {".csv", ".json", ".md"} or path.name == "sources_freeze.txt":
            candidates.append(rel)
    candidates.append("data/canonical/catalog.json")
    assets, move_map = [], []
    destinations = set()
    for relative in sorted(candidates):
        table = by_source.get(relative)
        owner, purpose, destination = classify(relative, table)
        if relative == "data/canonical/catalog.json":
            owner, purpose, destination = "shared", "catalog", "data/catalog/canonical.json"
        if destination in destinations:
            raise ValueError("Destination collision: " + destination)
        destinations.add(destination)
        path = ROOT / relative
        eligible = table is not None and purpose not in {"requests", "metadata", "catalog"}
        base = "data/shared" if owner == "shared" else "data/sectors/" + owner
        canonical = (base + "/canonical/" + destination[len(base) + 1:]) if eligible else ""
        licensing = licenses.get(relative, {})
        license_value = licensing.get("outbound_licence", "not-established")
        fact_name = relative.removeprefix("data/activity/").removesuffix(".csv")
        if fact_name in FACTS:
            license_value = "own-work-compilation"
        if purpose == "catalog":
            license_value = "own-work"
        if relative.startswith("data/extracted/unfccc/"):
            license_value = "own-work-compilation"
        kind = "template" if "/requests/" in relative else "table" if path.suffix == ".csv" else "gis" if purpose == "gis" else "document"
        public = "library" if purpose != "catalog" and license_value in {"own-work", "own-work-compilation", "public-licence"} else "internal"
        if fact_name in VIEWS:
            public = "compatibility"
        identifier = table["table_id"] if table else "asset." + re.sub(r"[^a-zA-Z0-9_.]", "_", relative.removeprefix("data/").replace("/", "."))
        applies = consumers.get(relative, set()) | ({owner} if owner != "shared" else set())
        title = table["title"] if table else path.stem.replace("_", " ").capitalize()
        producer = "pkinv.activity.compatibility_views" if fact_name in VIEWS else provenance.get(relative, {}).get("producer", "")
        document = documents.get(relative, {})
        refs = ";".join(x for x in (document.get("archived_path"), document.get("source_url")) if x)
        description = {"activity": "Verified observations and source quantities", "parameters": "Scientific factors and assumptions",
                       "lookups": "Identifiers, aliases and classification mappings", "gis": "Spatial inputs with companion provenance",
                       "evidence": "Supporting evidence, comparisons or diagnostics", "requests": "Data-request workflow or submission material",
                       "metadata": "Source, coverage or schema documentation", "catalog": "Data contract and repository catalog"}[purpose]
        assets.append(dict(zip(FIELDS, [identifier, relative, destination, canonical, owner, purpose, kind,
            producer, public, license_value,
            (owner + ".gis." + str(Path(destination).parent).replace("/", ".")) if purpose == "gis" else "",
            title, description, refs, ";".join(sorted(applies)), "no" if producer else "yes"])))
        move_map.append({"asset_id": identifier, "old_path": relative, "new_path": destination,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bundle_id": assets[-1]["bundle_id"]})
        if eligible and (ROOT / table["path"]).exists():
            move_map.append({"asset_id": identifier, "old_path": table["path"], "new_path": canonical,
                             "sha256": hashlib.sha256((ROOT / table["path"]).read_bytes()).hexdigest(), "bundle_id": ""})
    return assets, move_map, tables


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    assets, moves, tables = prepare()
    fields = ("asset_id", "old_path", "new_path", "sha256", "bundle_id")
    write(ROOT / "logs/data_layout_plan.csv", moves, fields)
    write(ROOT / "logs/data_assets_plan.csv", assets, FIELDS)
    print("%d assets; %d file moves" % (len(assets), len(moves)))
    if not args.apply:
        return
    # Validate the entire move map before changing any file.
    for row in moves:
        if (ROOT / row["new_path"]).exists():
            raise ValueError("Destination already exists: " + row["new_path"])
        if hashlib.sha256((ROOT / row["old_path"]).read_bytes()).hexdigest() != row["sha256"]:
            raise ValueError("Source changed: " + row["old_path"])
    for row in moves:
        target = ROOT / row["new_path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        (ROOT / row["old_path"]).rename(target)
    write(ROOT / "data/catalog/assets.csv", assets, FIELDS)
    write(ROOT / "data/catalog/migrations.csv", moves, fields)
    by_source = {a["legacy_path"]: a for a in assets}
    selected = []
    for table in tables:
        asset = by_source[table["source_path"]]
        if asset["canonical_path"]:
            selected.append(dict(table, path=asset["canonical_path"], storage_path=asset["path"]))
    write(ROOT / "data/catalog/canonical_tables.csv", selected, list(tables[0]) + ["storage_path"])
    selected_ids = {r["table_id"] for r in selected}
    for name in ("canonical_columns.csv", "canonical_consumers.csv"):
        records = rows(ROOT / "data/catalog" / name)
        write(ROOT / "data/catalog" / name, [r for r in records if r["table_id"] in selected_ids], list(records[0]))
    # Only obsolete generated copies are removed, after verifying their old bytes.
    for table in tables:
        path = ROOT / table["path"]
        if path.exists() and table["table_id"] not in selected_ids:
            path.unlink()
    for folder in sorted((ROOT / "data").rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if folder.is_dir() and not any(folder.iterdir()) and not any(x in folder.parts for x in ("raw", "cache", "baselines")):
            folder.rmdir()


if __name__ == "__main__":
    main()
