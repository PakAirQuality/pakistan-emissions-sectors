"""Generate reviewer guides and validate the registered sector data layout."""
from __future__ import annotations

import argparse
import collections
import csv
import os
from pathlib import Path

from pkinv.assets import catalog, resolve
from pkinv.paths import ROOT

PURPOSES = ("activity", "parameters", "lookups", "gis", "evidence", "metadata", "requests")
SECTORS = ("agriculture", "aviation", "fugitives", "industry", "ippu", "power", "railways",
           "residential", "transport", "waste", "lulucf")
EXPLANATIONS = {
    "activity": "Observed source quantities and verified extracts; generated compatibility views are identified separately.",
    "parameters": "Emission factors, scientific assumptions, scenarios and applicability rules.",
    "lookups": "Names, identifiers, classifications and mappings used to interpret the observations.",
    "gis": "Spatial inputs. Keep geometry, CRS, provenance and licensing companion files together.",
    "evidence": "Independent comparisons, diagnostics, source extracts and evidence supporting interpretation.",
    "metadata": "Coverage descriptions, source inventories and schema documentation.",
    "requests": "Outstanding data requests, letters and prospective templates. Templates are not observations.",
}


def _cell(text):
    return str(text or "").replace("|", "\\|").replace("\n", " ")


def _link(asset, folder, root):
    path = asset.get("canonical_path") or asset["path"]
    relative = os.path.relpath(Path(root) / path, folder).replace(os.sep, "/")
    return "[%s](<%s>)" % (_cell(asset["title"]), relative)


def guides(root=ROOT):
    root = Path(root)
    assets = catalog(root)
    documents = {}
    for sector in (*SECTORS, "shared"):
        folder = root / ("data/shared" if sector == "shared" else "data/sectors/" + sector)
        owned = [a for a in assets if a["owner_sector"] == sector and a["purpose"] != "catalog"]
        if not owned:
            continue
        title = "Shared data" if sector == "shared" else ("IPPU" if sector == "ippu" else "LULUCF" if sector == "lulucf" else sector.title())
        lines = ["# " + title + " data", "", "Start with the readable CSV links below. Each asset has one owner; shared inputs are linked rather than copied.", "",
                 "`canonical/` contains generated, Git-versioned runtime/download CSVs. Edit the maintained source listed in the catalog, then run `make dev`; do not edit canonical copies independently.", "",
                 "Source identities remain stable even where the old identity looks like a former file path. See the [asset catalog](<%s>) for physical locations, producers, consumers and source references." % os.path.relpath(root / "data/catalog/assets.csv", folder), ""]
        if sector == "lulucf":
            lines += ["LULUCF is exploratory and remains outside the inventory's national totals.", ""]
        for purpose in PURPOSES:
            members = [a for a in owned if a["purpose"] == purpose]
            if not members:
                continue
            lines += ["## " + purpose.title(), "", EXPLANATIONS[purpose], "",
                      "| Asset | Authoring | Representation |", "|---|---|---|"]
            for asset in sorted(members, key=lambda a: (a["title"], a["asset_id"])):
                authoring = "Maintained" if asset["maintained"] == "yes" else "Generated"
                if asset["publication"] == "compatibility":
                    authoring += " compatibility view"
                representation = "Readable canonical CSV" if asset["canonical_path"] else asset["kind"]
                lines.append("| %s | %s | %s |" % (_link(asset, folder, root), authoring, representation))
            lines.append("")
        shared = [a for a in assets if a["owner_sector"] == "shared" and sector in a.get("applies_to_sectors", "").split(";")]
        if shared and sector != "shared":
            lines += ["## Shared inputs", "", "| Asset | Purpose |", "|---|---|"]
            lines += ["| %s | %s |" % (_link(a, folder, root), a["purpose"]) for a in sorted(shared, key=lambda a: a["asset_id"])]
            lines.append("")
        documents[folder / "README.md"] = "\n".join(lines) + "\n"
    overview = ["# Data reviewer guide", "", "Browse by sector, then by purpose. The catalog separates observations, assumptions, spatial inputs, evidence, administrative metadata and requests.", "",
                "## Sectors", ""]
    for sector in SECTORS:
        if root / ("data/sectors/" + sector + "/README.md") in documents:
            overview.append("- [%s](sectors/%s/README.md)" % (sector.upper() if sector in ("ippu", "lulucf") else sector.title(), sector))
    overview += ["- [Shared data](shared/README.md)", "", "## Browse by purpose", "",
                 "[Cross-sector purpose index](catalog/by-purpose.md) · [Complete asset catalog](catalog/assets.csv) · [Migration map](catalog/migrations.csv)", "",
                 "## Reading and maintaining data", "",
                 "The sector guides link readable canonical CSVs first. Their source tables live in the corresponding sector purpose folders. Canonical CSVs are generated and versioned for review; their hashes and column definitions are recorded in the catalog. The model and downloads consume those same canonical values.", "",
                 "Files marked as compatibility views are generated selections from authoritative facts. Update the facts and regenerate the views; never maintain both independently.", "",
                 "Requests have separate registers, recipient-facing letters and prospective templates. Existing IDs and delivery/response states are preserved. Received material must pass source registration and verification before becoming activity data.", "",
                 "Raw documents, downloaded archives, caches, historical baselines and release outputs retain their existing locations. Source references link them into the sector catalog. Spatial assets retain all declared companion files and redistribution conditions.", "",
                 "Run `make data-index` after catalog edits and `make data-check` to verify assets, canonical CSVs and generated reviewer guides. `make dev` rebuilds changed calculations; `make release-check` runs strict reproduction.", ""]
    documents[root / "data/README.md"] = "\n".join(overview)
    purpose_lines = ["# Data by purpose", "", "Each link opens the owning sector's guide. Shared assets have one physical copy.", ""]
    for purpose in PURPOSES:
        purpose_lines += ["## " + purpose.title(), "", EXPLANATIONS[purpose], ""]
        for sector in (*SECTORS, "shared"):
            count = sum(a["owner_sector"] == sector and a["purpose"] == purpose for a in assets)
            if count:
                relative = "../shared/README.md" if sector == "shared" else "../sectors/" + sector + "/README.md"
                purpose_lines.append("- [%s](%s#%s): %d assets" % (sector, relative, purpose, count))
        purpose_lines.append("")
    documents[root / "data/catalog/by-purpose.md"] = "\n".join(purpose_lines)
    return documents


def validate(root=ROOT):
    root = Path(root)
    assets = catalog(root)
    errors, identifiers, physical = [], set(), set()
    for asset in assets:
        if asset["asset_id"] in identifiers:
            errors.append("duplicate asset ID: " + asset["asset_id"])
        identifiers.add(asset["asset_id"])
        for path in (asset["path"], asset.get("canonical_path", "")):
            if not path:
                continue
            if Path(path).is_absolute() or ".." in Path(path).parts:
                errors.append("unsafe asset path: " + path)
            if path in physical:
                errors.append("duplicate physical asset: " + path)
            physical.add(path)
            if not (root / path).is_file():
                errors.append("missing asset: " + path)
        if asset["purpose"] == "requests" and asset["canonical_path"]:
            errors.append("request material must not be a canonical model input: " + asset["asset_id"])
    for base in (root / "data/sectors", root / "data/shared"):
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() in (".csv", ".json", ".geojson", ".tif", ".npy") and path.relative_to(root).as_posix() not in physical:
                errors.append("unregistered managed asset: " + path.relative_to(root).as_posix())
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args(argv)
    errors = validate(args.root)
    if errors:
        print("\n".join(errors))
        return 1
    differences = []
    for path, text in guides(args.root).items():
        if path.exists() and path.read_text(encoding="utf-8") == text:
            continue
        differences.append(str(path.relative_to(args.root)))
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    if args.check and differences:
        print("Stale reviewer indexes: " + ", ".join(differences))
        return 1
    print("Data catalog: %d assets; %d reviewer indexes %s" %
          (len(catalog(args.root)), len(differences), "differ" if args.check else "updated"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
