"""Reader-facing catalogue owned by the release, alongside its canonical input tables."""
import json
import os
import re

from pkinv.assets import asset_path
from pkinv.paths import ROOT


def input_product_name(table_id):
    return "input_" + re.sub(r"[^a-zA-Z0-9_]", "_", table_id)


def build(tables, sources):
    with open(sources.path("data/download_catalog.json"), encoding="utf-8") as handle:
        catalog = json.load(handle)
    with open(sources.path("data/canonical/catalog.json"), encoding="utf-8") as handle:
        inputs = json.load(handle)
    names = set(tables)
    with open(os.path.join(ROOT, "outputs", "release_manifest.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    names.update(os.path.basename(p["path"]).rsplit(".", 1)[0] for p in manifest["products"])
    names.update(os.path.basename(p).rsplit(".", 1)[0] for p in sources.products.values())
    names.update(os.path.basename(p).rsplit(".", 1)[0] for p in sources.used.values())
    seen = set()
    for collection in catalog["collections"]:
        for item in collection["downloads"]:
            if item["id"] in seen:
                raise ValueError("duplicate download id: %s" % item["id"])
            seen.add(item["id"])
            for filename in item["files"]:
                name = filename.rsplit(".", 1)[0]
                if name not in names and not os.path.isfile(asset_path(ROOT, "data", filename)):
                    raise ValueError("download %s names an unknown product: %s" % (item["id"], filename))
    input_names = set()
    for table in inputs["tables"]:
        name = input_product_name(table["table_id"])
        if name in input_names or name in names:
            raise ValueError("canonical input product name collision: %s" % name)
        input_names.add(name)
        sources.path(table["path"])
        if sources.digests([table["path"]])[0]["sha256"] != table["sha256"]:
            raise ValueError("canonical input differs from its catalogue: %s" % table["path"])
    return catalog, inputs
