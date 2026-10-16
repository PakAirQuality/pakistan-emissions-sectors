"""Every committed data product has a producer, a document, or a declared reason. This finds the ones that do not.

WHY. outputs/ has had this audit since rc20 (scripts/audit_outputs.py); data/ never did, and
the rc36 presence audit measured what that cost: of the committed data products, 91 were
hand-made, 14 of those came from a document that is not held, and two were read by nothing -
and nothing could enumerate the class. The build never touches this layer (run_all writes
data/periods.csv and data/months.csv and nothing else under data/), so the clean-room's
byte-identity proves nothing about whether an activity file still follows from the document
it was typed from. This audit does not prove that either. It says, for every product, WHICH
of the classes below is true, so that the re-derivation tests (producers), the transcription
checks (hand-made with a held document) and the gap registers (hand-made without one) can
each be held to their own list.

THE UNIVERSE is the data PRODUCTS on disk under data/ (rc41; git ls-files before, which a
tree without .git cannot answer): csv, npy, geojson, json, parquet.
Raw documents that happen to live under data/ (the PBS census workbooks, the NFDC PDFs, the
GHSL tiles, data/raw/ and data/cache/ wholesale) are data/raw_manifest.csv's business - they
are hashed there, and a raw document has no producer by definition.

CLASSES, one per product:
  producer               a script or module under scripts/ or src/ names it in a `Writes:`
                         or `Outputs:` docstring block (globs honoured) or beside a write
                         idiom; tests/test_data_rederivation.py is what proves it reproduces
  hand:held-source       no producer; data/source_documents.csv says archived - the
                         transcription-check register (data/transcription_checks.csv) covers it
  hand:derived           no producer; source_documents says derived (an alias table, a
                         judgement weight, a roll-up of other committed files)
  hand:no-source         no producer; source_documents says not-archived and names the gap
                         that data/not_retained_register.csv and data/data_gaps.csv explain
  hand:parameter         a root data/*.csv table with neither a producer nor a
                         source_documents row - a parameter choice or a register
  sidecar                a provenance record beside the asset it describes (*_SOURCES.json,
                         *.npy.txt, *.csv.txt): written by hand or by the fetch, read by people
  schema                 a JSON Schema under data/schemas/ (v1.0.0: the semantic contract's):
                         own work (a contract this project wrote; it derives from no publication), read by the tests
  unregistered           NONE of the above. tests/test_data_provenance_audit.py asserts none.

Separately, `orphan` marks a product whose name appears nowhere in src/, scripts/ or tests/
except its own producer - committed, maintained, and read by nothing. The test freezes that
set by name so a new orphan is a failure and a retired one is a deliberate edit.

Writes: outputs/pakemis_data_provenance.csv
"""
import collections
import csv
import fnmatch
import json
import os
import re

from pkinv.core import presentation
from pkinv.core.filenames import name_patterns
from pkinv.core.io import write_table
from pkinv.paths import OUTPUTS, ROOT
from pkinv.assets import catalog as asset_catalog, resolve, legacy_path

OUT = os.path.join(OUTPUTS, "pakemis_data_provenance.csv")
REGISTER = os.path.join(ROOT, "data", "source_documents.csv")

PRODUCT_SUFFIXES = (".csv", ".npy", ".geojson", ".json", ".parquet")
SIDECAR_SUFFIXES = ("_SOURCES.json", "_SOURCES.md", "PROXY_SOURCES.md", ".npy.txt", ".csv.txt")
# data/baselines/ holds PRESERVED COPIES of products, not products. Each is a byte copy of a
# shipped output taken at a named moment so that a later change can be measured against something
# rather than described - see the directory's own README and SHA256SUMS. They have no producer by
# construction: producing one would defeat its purpose, because a regenerated baseline is not the
# state that was preserved. The audit was right to flag them (a copy under data/ does look like an
# unregistered product) and the exclusion is declared here rather than by dropping the guard.
EXCLUDED_TREES = ("data/raw/", "data/cache/", "data/baselines/")
SEARCHED = ("src", "scripts")
READERS_ALSO = ("tests",)
# Files that NAME products without reading them - this module's own docstring, and the
# contract test that lists the orphans by name. audit_outputs learned this the hard way: a
# detector that names its examples immunises them (its docstring quoted the orphan that
# prompted it, and the search read that as a writer). The first run of this module with
# tests/ in scope reported 0 orphans for the same reason.
EXCLUDED_SOURCES = ("tests/test_data_provenance_audit.py",)

# Producers the docstring/write-idiom search cannot see, with the reason.
PRODUCER_OVERRIDES = {
    "data/activity/power/generation_monthly.csv":
        "scripts/ingest_pbs_generation.py + scripts/ingest_sir_generation.py (two lanes, "
        "each preserving the other's rows; run in that order)",
    "data/activity/power/generation_monthly_coverage.csv":
        "scripts/ingest_pbs_generation.py + scripts/ingest_sir_generation.py",
    "data/activity/waste/population_district.csv":
        "scripts/ingest_waste_population.py then scripts/project_waste_population.py "
        "(appends the projected year in place)",
    # written inside an `if fuel_out:` guard through the module constant OUT_FUEL, so the
    # filename never appears near a write idiom and the scan called this file hand-made
    "data/activity/power/fuel_consumed.csv": "scripts/ingest_power.py",
    # core/gis/proxies.py names its caches "proxy_%s_%dx%d.npy" at run time; the population
    # surface comes from the held WorldPop tif, builtup/cropland/GLW from ESA WorldCover and
    # GLW read over the network, manure_applied from agriculture/gis/derive_manure_proxy.py
    "data/gis/proxy_population_267x340.npy": "src/pkinv/core/gis/proxies.py (get_proxy)",
    "data/gis/proxy_builtup_267x340.npy": "src/pkinv/core/gis/proxies.py (get_proxy; network)",
    "data/gis/proxy_cropland_267x340.npy": "src/pkinv/core/gis/proxies.py (get_proxy; network)",
    "data/gis/proxy_glw_livestock_267x340.npy":
        "src/pkinv/core/gis/proxies.py (get_proxy; network)",
    "data/gis/proxy_manure_applied_267x340.npy":
        "src/pkinv/sectors/agriculture/gis/derive_manure_proxy.py via proxies.get_proxy",
    # rc41: the rice crosscheck instrument, aggregated from the held GCD-Rice 2023 raster
    # (data/gis/manual/gcd_rice_2023.tif) by proxies.build_gcd_rice_proxy on a cache miss
    "data/gis/proxy_gcd_rice_267x340.npy":
        "src/pkinv/core/gis/proxies.py (get_proxy; reads data/gis/manual/gcd_rice_2023.tif)",
    # rc69: the SPAM rasters' grid caches, named by proxies.manual_cache_path at run time
    "data/sectors/agriculture/gis/proxy_manual_spam_rice_267x340.npy":
        "scripts/build_manual_proxy_caches.py (resamples the held SPAM raster)",
    "data/sectors/agriculture/gis/proxy_manual_spam2020_V2r2_global_A_RICE_I_267x340.npy":
        "scripts/build_manual_proxy_caches.py (resamples the held SPAM raster)",
    "data/sectors/agriculture/gis/proxy_manual_spam2020_V2r2_global_A_RICE_R_267x340.npy":
        "scripts/build_manual_proxy_caches.py (resamples the held SPAM raster)",
}

# Readers that build the name at run time, so the search cannot see them.
READER_OVERRIDES = {
    "data/benchmark_splits/spatial_rice_mnfsr.csv": "src/pkinv/eval/benchmark_spatial.py (task id)",
    "data/benchmark_splits/spatial_rice_punjabcrs.csv": "src/pkinv/eval/benchmark_spatial.py (task id)",
    "data/benchmark_splits/spatial_wheat_mnfsr.csv": "src/pkinv/eval/benchmark_spatial.py (task id)",
    "data/benchmark_splits/spatial_road_transport.csv":
        "src/pkinv/eval/benchmark_spatial.py (task id; pending_record)",
    "data/gis/proxy_manure_applied_267x340.npy": "src/pkinv/core/gis/proxies.py (get_proxy by name)",
    "data/sectors/agriculture/gis/proxy_manual_spam_rice_267x340.npy":
        "src/pkinv/core/gis/proxies.py (build_manual_proxy, when the raster is not mounted)",
    "data/sectors/agriculture/gis/proxy_manual_spam2020_V2r2_global_A_RICE_I_267x340.npy":
        "src/pkinv/core/gis/proxies.py (build_manual_proxy, when the raster is not mounted)",
    "data/sectors/agriculture/gis/proxy_manual_spam2020_V2r2_global_A_RICE_R_267x340.npy":
        "src/pkinv/core/gis/proxies.py (build_manual_proxy, when the raster is not mounted)",
}

WRITE_IDIOM = re.compile(r"write_table\(|write_dicts\(|\.to_csv\(|csv\.writer\(|"
                         r"csv\.DictWriter\(|open\([^)]*[\"']w[\"']|np\.save\(|savez|"
                         r"json\.dump\(|to_file\(")
# a Writes:/Outputs: docstring line and its indented continuation lines
WRITES_LINE = re.compile(r"(?:Writes?|Outputs?):\s*([^\n]+(?:\n[ \t]+[^\n]+)*)")
FIELDS = ("data_file", "tree", "class", "producer", "archival_state", "gap_id",
          "readers", "orphan", "note")


def universe():
    """Every data product on DISK under data/ (outside the excluded trees).

    rc41: this was `git ls-files data`, which a tree without .git - the validation
    package, the empty-outputs rebuild's copy - cannot answer (the strict rebuild stopped
    here), and which hid an untracked new file from the audit until it was staged. The
    disk is the universe the deposit manifest already enumerates; in the repository the
    two differ by exactly the gitignored exact-area partition the cube consumes
    (data/gis/adm2_intersections_267x340.csv and its sidecar, held since the sector
    layout at data/shared/gis/ and excluded by that path in .gitignore), which the
    deposit ships and this audit now sees.
    """
    files = []
    copies = presentation.layer()
    # rc69: the restricted layers are symlinks into the private checkout
    # (pkinv.core.layers), and os.walk does not enter a linked folder unless told to. The
    # excluded trees are pruned before descent, so following links walks the same files
    # the monorepo walked.
    for folder, dirs, names in os.walk(os.path.join(ROOT, "data"), followlinks=True):
        here = os.path.relpath(folder, ROOT).replace(os.sep, "/")
        dirs[:] = [d for d in dirs if not (here + "/" + d + "/").startswith(EXCLUDED_TREES)]
        for name in names:
            rel = os.path.relpath(os.path.join(folder, name), ROOT).replace(os.sep, "/")
            if rel.startswith(EXCLUDED_TREES) or rel in copies:
                continue
            if rel.endswith(SIDECAR_SUFFIXES) or rel.endswith(PRODUCT_SUFFIXES):
                files.append(rel)
    return sorted(files)


def _sources(trees):
    """{relative path: text} for every .py under the trees, this module excluded."""
    text = {}
    for tree in trees:
        for folder, _dirs, names in os.walk(os.path.join(ROOT, tree)):
            if "__pycache__" in folder or "egg-info" in folder:
                continue
            for name in names:
                full = os.path.join(folder, name)
                rel = os.path.relpath(full, ROOT).replace(os.sep, "/")
                if (not name.endswith(".py") or full == os.path.abspath(__file__)
                        or rel in EXCLUDED_SOURCES):
                    continue
                with open(full, encoding="utf-8", errors="replace") as f:
                    text[rel] = f.read()
    return text


def register():
    with open(resolve(REGISTER, root=ROOT), encoding="utf-8") as f:
        rows = list(csv.DictReader(l for l in f if not l.startswith("#")))
    return {os.path.relpath(resolve(os.path.join(ROOT, r["data_file"]), root=ROOT), ROOT): r
            for r in rows}


def is_producer(rel, patterns, text):
    """A `Writes:` block naming the path (globs honoured), or a mention beside a write idiom."""
    for m in WRITES_LINE.finditer(text):
        for token in re.split(r"[\s;,]+", m.group(1)):
            token = token.strip("()`'\"")
            if not token or "/" not in token and "." not in token:
                continue
            if fnmatch.fnmatch(rel, token) or fnmatch.fnmatch(os.path.basename(rel), token):
                return True
    for pattern in patterns:
        for m in re.finditer(pattern, text):
            window = text[max(0, m.start() - 400): m.end() + 400]
            if WRITE_IDIOM.search(window):
                return True
    return False


def classify(rel, producer, reg):
    """The class of one product from its producer string and its register row (or None)."""
    tree = legacy_path(rel, root=ROOT).rsplit("/", 1)[0]
    if rel.endswith(SIDECAR_SUFFIXES):
        return "sidecar"
    if tree == "data/schemas" and rel.endswith(".schema.json"):
        return "schema"
    if producer:
        return "producer"
    if reg is None:
        return "hand:parameter" if tree in ("data", "data/catalog") else "unregistered"
    if reg["archival_state"] == "archived":
        return "hand:held-source"
    if reg["archival_state"] == "derived":
        return "hand:derived"
    return "hand:no-source"


def declared_input_provenance():
    """Producer and reader edges declared by the canonical and extraction contracts.

    These tables are addressed through catalogs, so finding a basename beside a
    write() call cannot discover their producer. Follow the declarations rather
    than classing generated inputs as hand-authored parameters or orphan files.
    """
    from pathlib import Path
    from pkinv.activity.build import declarations
    from pkinv.activity.store import CATALOG_PATH
    from pkinv.core.io import read_rows

    declared = {}
    for table in declarations(ROOT):
        declared[table["path"]] = {
            "producer": "src/pkinv/activity/build.py",
            "readers": ("src/pkinv/activity/store.py", "src/pkinv/semantic/build.py"),
            "note": "Lossless canonical input from %s; declared field mapping in data/canonical_columns.csv"
                    % table["source_path"],
        }
    declared[os.path.relpath(resolve(os.path.join(ROOT, CATALOG_PATH), root=ROOT), ROOT)] = {
        "producer": "src/pkinv/activity/build.py",
        "readers": ("src/pkinv/activity/store.py", "src/pkinv/semantic/build.py"),
        "note": "Canonical input schemas, source digests, row counts and CSV digests.",
    }
    raw = {row["path"]: row["sha256"]
           for row in read_rows(resolve(os.path.join(ROOT, "data", "raw_manifest.csv"), root=ROOT))}
    from pkinv.report.deposit_manifest import extract_receipts, storage_path
    for relative in extract_receipts():
        path = Path(ROOT) / relative
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if manifest.get("schema") != "pkinv.source_extract/v1":
            raise ValueError("Unrecognised source extract receipt: %s" % path)
        if raw.get(manifest["source"]) != manifest["source_sha256"]:
            raise ValueError("Source extract receipt disagrees with raw_manifest.csv: %s" % path)
        entry = {
            "producer": "scripts/ingest_official_reporting.py",
            "readers": ("src/pkinv/core/source_extracts.py", "src/pkinv/activity/build.py"),
            "note": "Verified extract of %s; source SHA256 %s; typed receipt %s"
                    % (manifest["source"], manifest["source_sha256"], path.name),
        }
        declared[path.relative_to(ROOT).as_posix()] = entry

        def collect(node):
            if node["kind"] == "tuple":
                for child in node["items"]:
                    collect(child)
            else:
                name = node["path"]
                if Path(name).name != name:
                    raise ValueError("Source extract receipt escapes its directory")
                logical = os.path.join(os.path.dirname(legacy_path(relative, root=ROOT)), name)
                declared[storage_path(logical)] = entry

        collect(manifest["result"])
    assets = asset_catalog(root=ROOT)
    known_sources = {row[key] for row in assets for key in ("asset_id", "legacy_path", "path")}
    registered_sources = register()
    for asset in assets:
        if asset["path"] in declared:
            continue
        if asset.get("producer"):
            declared[asset["path"]] = {
                "producer": asset["producer"],
                "readers": ("src/pkinv/activity/build.py",) if asset.get("canonical_path") else None,
                "note": "Producer and storage binding declared in data/catalog/assets.csv.",
            }
        elif asset.get("purpose") == "catalog":
            declared[asset["path"]] = {
                "producer": "", "readers": ("src/pkinv/assets.py",),
                "note": "Maintained catalog or schema registry.",
            }
        elif (asset["path"] not in registered_sources and asset.get("maintained") == "yes"
              and asset.get("source_refs")):
            references = asset["source_refs"].split(";")
            unknown = set(references) - known_sources
            if unknown:
                raise ValueError("Unknown asset provenance references for %s: %s" %
                                 (asset["asset_id"], sorted(unknown)))
            declared[asset["path"]] = {
                "producer": "", "class": "hand:derived",
                "readers": ("src/pkinv/activity/store.py", "src/pkinv/assets.py"),
                "note": "Maintained consolidation of registered source identities: " + asset["source_refs"],
            }
    return declared


def audit():
    files = universe()
    producers_text = _sources(SEARCHED)
    readers_text = dict(producers_text)
    readers_text.update(_sources(READERS_ALSO))
    reg_by_file = register()
    declared = declared_input_provenance()
    rows = []
    for rel in files:
        logical = legacy_path(rel, root=ROOT)
        name = os.path.basename(rel)
        patterns = list(name_patterns(name))
        explicit = declared.get(rel)
        if explicit:
            producer = explicit["producer"]
        elif logical in PRODUCER_OVERRIDES:
            producer = PRODUCER_OVERRIDES[logical]
        else:
            producer = ";".join(sorted(p for p, t in producers_text.items()
                                       if is_producer(logical, patterns, t)))
        readers = (list(explicit["readers"]) if explicit and explicit.get("readers") is not None else
                   sorted(p for p, t in readers_text.items()
                          if p not in producer and any(re.search(q, t) for q in patterns)))
        if logical in READER_OVERRIDES:
            readers.append(READER_OVERRIDES[logical])
        reg = reg_by_file.get(rel)
        rows.append({
            "data_file": rel, "tree": rel.rsplit("/", 1)[0],
            "class": (explicit or {}).get("class") or classify(rel, producer, reg), "producer": producer,
            "archival_state": reg["archival_state"] if reg else "",
            "gap_id": reg["gap_id"] if reg else "",
            "readers": len(readers),
            "orphan": "no" if readers else "yes",
            "note": explicit["note"] if explicit else (reg["note"][:120] if reg else ""),
        })
    return rows


def main(argv=()):
    rows = audit()
    write_table(OUT, FIELDS, rows, banner=(
        "THE DATA PROVENANCE AUDIT (rc37): every git-tracked data product under data/",
        "classed as producer / hand:held-source / hand:derived / hand:no-source /",
        "hand:parameter / sidecar / unregistered, with its reader count. See",
        "pkinv.report.data_provenance for the classes and tests/test_data_provenance_audit.py",
        "for what is asserted.",
    ))
    counts = collections.Counter(r["class"] for r in rows)
    print("data provenance audit -> %s" % os.path.relpath(OUT, ROOT))
    print("  %d products" % len(rows))
    for cls, n in sorted(counts.items()):
        print("  %-18s %4d" % (cls, n))
    orphans = [r["data_file"] for r in rows if r["orphan"] == "yes" and r["class"] != "sidecar"]
    unreg = [r["data_file"] for r in rows if r["class"] == "unregistered"]
    print("  %d read by nothing (sidecars excluded)" % len(orphans))
    if "--verbose" in argv:
        for p in orphans:
            print("      %s" % p)
    if unreg:
        print("  %d UNREGISTERED - no producer, without a source_documents row:" % len(unreg))
        for p in unreg:
            print("      %s" % p)
    return 1 if unreg else 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main(sys.argv[1:]))
