#!/usr/bin/env python3
"""A read-only development snapshot of the tree for a collaborator (v1.0.0 program).

    python3 scripts/build_dev_snapshot.py [--out DIR] [--with-surfaces] [--with-activity]

NOT a validation package: no gate runs to build it, nothing is verified, and README_DEV.md
says so. It is the repository laid out the way the collaborator asked for it -
outputs/, registries/, schemas/, data/geometry/, src/, tests/ and the release metadata -
deterministic (fixed entry times, sorted entries, one top-level folder), with a plain
SHA256SUMS. Source documents (sources/, data/raw/, data/cache/) never enter it; the source
register inside says how to obtain each. The registries/ block is the validation package's
own (build_validation_package.layout), so the two artefacts name things the same way.
"""
import io
import os
import shutil
import sys
import time
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from pkinv.assets import asset_path

import pkinv  # noqa: E402
import build_validation_package as bvp  # noqa: E402
from pkinv.core.io import read_rows  # noqa: E402

NAME = "pakemis_%s_dev_snapshot" % pkinv.__version__

# (destination prefix inside the snapshot, source prefix in the repository, predicate on the
# repository-relative path). Order matters only for the reader; every source is tracked.
MAP = [
    ("outputs/", "outputs/", None),
    ("src/", "src/", None),
    ("tests/", "tests/", None),
    ("data/geometry/tables/", "data/", lambda rel: os.path.basename(rel) in (
        "adm2_canonical.csv", "adm2_crosswalk.csv", "geometry_sets.csv", "stream_geometry.csv",
        "facility_registry.csv", "adm2_alias.csv", "province_shares.csv")),
]
GEOMETRY_SRC = "data/gis/"
SURFACES = "data/gis/manual/"
RELEASE_FILES = ("outputs/release_manifest.json", "outputs/pakemis_test_run.json", "outputs/SHA256SUMS",
                 "outputs/pakemis_deposit_manifest.csv",
                 "outputs/pakemis_source_register.csv", "CITATION.cff", ".zenodo.json", "CHANGELOG.md",
                 "LICENSE", "LICENSE-data", "pyproject.toml", "requirements.lock")
SCHEMA_FILES = ("data/product_schemas.csv", "data/product_columns.csv",
                "data/schemas/semantic_release.schema.json",
                "validation_package/VALIDATION_MANIFEST.schema.json")
EXCLUDED_TOPS = ("sources", "dist", ".git", "logs", "capsule", "PakEmis_108_month_data_bundle")


def _copy(src, dst):
    """Copy one file, or RECREATE an in-tree relative symlink rather than following it.

    The blanket refusal below was right about what it feared - a link out of the tree, or
    a dangling one, would snapshot something the snapshot does not describe - and wrong
    about one case it could not have known: a relative link to a sibling inside the tree is
    structure a reader needs, not a file. Following it would duplicate the target under a
    second name; refusing it stopped the snapshot entirely. So a relative link that stays inside the tree is recreated as a
    link, and everything else still refuses.
    """
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.islink(src):
        target = os.readlink(src)
        inside = (not os.path.isabs(target)
                  and not os.path.normpath(
                      os.path.join(os.path.dirname(src), target)
                  ).startswith(".." + os.sep))
        if not inside:
            raise SystemExit("refusing to snapshot a symlink that leaves the tree or is "
                             "absolute: %s -> %s" % (src, target))
        if os.path.lexists(dst):
            os.remove(dst)
        os.symlink(target, dst)
        return
    shutil.copy2(src, dst)


def stage(out_dir, with_surfaces=False, with_activity=False):
    top = asset_path(out_dir, NAME)
    if os.path.exists(top):
        shutil.rmtree(top)
    os.makedirs(top)
    tracked = bvp.tracked_files()
    copied = []
    for rel in tracked:
        if rel.split("/")[0] in EXCLUDED_TOPS or rel.startswith(("data/raw/", "data/cache/")):
            continue
        for dst_prefix, src_prefix, predicate in MAP:
            if rel.startswith(src_prefix) and (predicate is None or predicate(rel)):
                dst = asset_path(top, dst_prefix + rel[len(src_prefix):])
                _copy(asset_path(ROOT, rel), dst)
                copied.append(rel)
                break
        else:
            if rel.startswith(GEOMETRY_SRC) and (with_surfaces or not rel.startswith(SURFACES)):
                _copy(asset_path(ROOT, rel), asset_path(top, "data/geometry/", rel[len(GEOMETRY_SRC):]))
                copied.append(rel)
            elif with_activity and rel.startswith("data/") and rel.endswith(".csv"):
                _copy(asset_path(ROOT, rel), asset_path(top, "data/activity_inputs/", rel[len("data/"):]))
                copied.append(rel)
    # the validation package's registries block, verbatim
    for dst, kind, src in bvp.layout(ROOT):        # only layout()'s registries/ block is used
        if not dst.startswith("registries/"):
            continue
        target = asset_path(top, dst)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        if kind == "copy":
            _copy(asset_path(ROOT, src), target)
        elif kind == "view":
            rows = src(ROOT, target)
            if rows is not None and not os.path.exists(target):
                raise SystemExit("view %s wrote nothing" % dst)
    for rel in SCHEMA_FILES:
        if os.path.exists(asset_path(ROOT, rel)):
            _copy(asset_path(ROOT, rel), asset_path(top, "schemas", os.path.basename(rel)))
    for rel in RELEASE_FILES:
        if os.path.exists(asset_path(ROOT, rel)):
            _copy(asset_path(ROOT, rel), asset_path(top, "release", os.path.basename(rel)))
    _write_licences(top)
    _write_readme(top, len(copied), with_surfaces, with_activity)
    bvp.write_sha256sums(top, skip=("SHA256SUMS",))
    return top


def _write_licences(top):
    import json
    with open(asset_path(ROOT, "outputs", "release_manifest.json"), encoding="utf-8") as handle:
        licences = json.load(handle)["licences"]
    lines = ["# Licences of the geometry and proxy files in this snapshot", "",
             "Code: %s. Data, figures and text: %s." % (licences["code"], licences["data_and_text"]), "",
             "The following are DERIVATIVE DATABASES under ODbL 1.0 (OpenStreetMap contributors) and keep",
             "share-alike; a rendered map is a produced work needing attribution only:", ""]
    lines += ["- %s" % c for c in licences["odbl_carveouts"]]
    lines += ["", licences["odbl_note"], "", "See release/LICENSE-data for the full statement."]
    os.makedirs(asset_path(top, "data", "geometry"), exist_ok=True)
    with open(asset_path(top, "data", "geometry", "LICENSES.md"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def _write_readme(top, n_copied, with_surfaces, with_activity):
    commit = bvp.git("rev-parse", "HEAD").strip()
    dirty = bool(bvp.git("status", "--porcelain").strip())
    text = """# PakEmis %(version)s - development snapshot

Development snapshot of the PakEmis repository at commit %(commit)s (tree %(state)s), built by
scripts/build_dev_snapshot.py. **This is not a validation package**: no gate ran to build it and
nothing in it was verified by its construction; the reviewer-facing artefact with its own gates
is `pakemis_%(version)s_full_validation.zip`. It is the tree laid out for a collaborator:

- `outputs/` - every tracked output, including the semantic release (`outputs/semantic/`)
- `registries/` - the validation package's registries block (periods, months, sectors,
  components, configurations, methods, parameters, ...)
- `schemas/` - the product schema and column registries and the two JSON Schemas
- `data/geometry/` - the boundary files and proxy grids the allocation reads (surfaces under
  `manual/` %(surfaces)s), the ADM2 tables under `tables/`, and `LICENSES.md` naming the ODbL files
- `src/`, `tests/` - the engine and its suite
- `release/` - the release manifest, the recorded test run, SHA256SUMS,
  the deposit manifest and the source register, CITATION.cff, .zenodo.json, CHANGELOG, licences

Source documents (`sources/`, `data/raw/`, `data/cache/`) are not included; `release/
pakemis_source_register.csv` names every one with its SHA-256 and how to obtain it.
%(activity)s
%(n)d tracked files copied. `SHA256SUMS` covers every file here (`sha256sum -c SHA256SUMS`).
""" % {"version": pkinv.__version__, "commit": commit[:12], "state": "dirty" if dirty else "clean",
       "surfaces": "included" if with_surfaces else "NOT included; --with-surfaces adds 212 MB",
       "activity": ("The activity inputs under `data/` are included under `data/activity_inputs/`.\n"
                    if with_activity else "The activity inputs under `data/` are not included (`--with-activity` adds them).\n"),
       "n": n_copied}
    with open(asset_path(top, "README_DEV.md"), "w", encoding="utf-8") as handle:
        handle.write(text)


def zip_deterministic(top, zip_path):
    """One top-level folder, sorted entries, a fixed timestamp: the same tree gives the same bytes."""
    stamp = (2026, 1, 1, 0, 0, 0)
    parent = os.path.dirname(top)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for folder, dirs, names in os.walk(top):
            dirs.sort()
            for name in sorted(names):
                path = asset_path(folder, name)
                arc = os.path.relpath(path, parent)
                info = zipfile.ZipInfo(arc, date_time=stamp)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o644 << 16
                with open(path, "rb") as handle:
                    z.writestr(info, handle.read())
    return zip_path


def main(argv):
    out_dir = asset_path(ROOT, "dist")
    if "--out" in argv:
        out_dir = os.path.abspath(argv[argv.index("--out") + 1])
    os.makedirs(out_dir, exist_ok=True)
    top = stage(out_dir, "--with-surfaces" in argv, "--with-activity" in argv)
    zip_path = asset_path(out_dir, NAME + ".zip")
    zip_deterministic(top, zip_path)
    digest = bvp.sha256(zip_path)
    with open(asset_path(out_dir, NAME + ".SHA256SUMS"), "w", encoding="utf-8") as handle:
        handle.write("%s  %s\n" % (digest, NAME + ".zip"))
    print("%s  %s  (%.1f MB)" % (digest, zip_path, os.path.getsize(zip_path) / 1e6))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
