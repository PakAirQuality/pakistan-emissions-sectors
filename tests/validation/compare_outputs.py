"""Compare a rebuilt outputs/ tree with the packaged one, bytewise first, numerically second.

Usage: python3 tests/validation/compare_outputs.py <package root> <rebuilt tree> <report csv>

(A fourth argument, the paper-build status of releases up to rc69, is accepted and ignored.)

Every product the release manifest hashes, every common-draw file and every parquet twin is
compared. A file whose bytes match is `identical`. A CSV whose bytes differ is compared cell
by cell: numeric cells at a relative tolerance of 1e-9 (absolute 1e-12 near zero), text cells
exactly; the maximum relative difference is reported. Two files differ BY CONSTRUCTION and are
reported as `expected_difference`: outputs/release_manifest.json, whose git block describes
the tree that ran it, and the NetCDF cube, whose HDF5 container carries a creation timestamp;
the cube's arrays are compared numerically when netCDF4 is importable. Anything else that
differs is a `difference` and fails the comparison.
"""

from pkinv.assets import asset_path
from pkinv.core.reporting_window import CORE_SUFFIX, RETIRED_GHG_PANEL_PRODUCTS
import csv
import hashlib
import json
import os
import sys

EXPECTED = {
    "outputs/release_manifest.json": "git block names the tree that produced it",
    "outputs/pakemis_grid_0p05_monthly.nc": "HDF5 creation timestamp; arrays compared numerically",
}
REL_TOL, ABS_TOL = 1e-9, 1e-12


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def numeric_csv_diff(a, b):
    import itertools
    import math
    worst = 0.0
    with open(a, encoding="utf-8") as fa, open(b, encoding="utf-8") as fb:
        for i, (xa, xb) in enumerate(itertools.zip_longest(csv.reader(fa), csv.reader(fb))):
            if xa is None or xb is None:
                return "row count differs at row %d" % i, float("inf")
            if len(xa) != len(xb):
                return "column count differs at row %d" % i, float("inf")
            for ca, cb in zip(xa, xb):
                if ca == cb:
                    continue
                try:
                    fa_, fb_ = float(ca), float(cb)
                except ValueError:
                    return "text cell differs at row %d: %r vs %r" % (i, ca[:40], cb[:40]), float("inf")
                if not (math.isfinite(fa_) and math.isfinite(fb_)):
                    return "nonfinite numeric cell differs at row %d" % i, float("inf")
                scale = max(abs(fa_), abs(fb_), ABS_TOL)
                worst = max(worst, abs(fa_ - fb_) / scale)
    return ("numeric within tolerance" if worst <= REL_TOL else "numeric difference"), worst


def cube_diff(a, b):
    try:
        import netCDF4  # noqa: F401
        import numpy as np
    except ImportError:
        return "netCDF4 not importable; arrays not compared", None
    from netCDF4 import Dataset

    # RECURSIVE, SYMMETRIC, AND IT READS STRINGS (rc45). This compared `da.variables` only -
    # the ROOT group - while the reference cube keeps its entire 42-layer category stack in
    # ds.createGroup("annual_by_category"). A rebuild that changed every category raster and
    # left the three gas layers alone reported "arrays within tolerance". It was also
    # one-directional (a variable present only in the rebuild was never noticed) and skipped
    # non-numeric variables, so a REORDER of the category labels - which is what aligns those
    # rasters to their names - was invisible twice over.
    def walk(ga, gb, prefix=""):
        """(message, worst) over one group and every group beneath it."""
        worst = 0.0
        def metadata(obj):
            return {key: str(obj.getncattr(key)) for key in obj.ncattrs()}
        if metadata(ga) != metadata(gb):
            return "group attributes differ: " + prefix, float("inf")
        if {k: (len(v), v.isunlimited()) for k, v in ga.dimensions.items()} != {
                k: (len(v), v.isunlimited()) for k, v in gb.dimensions.items()}:
            return "dimensions differ: " + prefix, float("inf")
        names_a, names_b = set(ga.variables), set(gb.variables)
        for name in sorted(names_a ^ names_b):
            side = "reference" if name in names_a else "rebuild"
            return "variable %s%s present only in the %s" % (prefix, name, side), float("inf")
        for name in sorted(names_a):
            va, vb = ga.variables[name], gb.variables[name]
            if va.dimensions != vb.dimensions or metadata(va) != metadata(vb):
                return "variable metadata differs: " + prefix + name, float("inf")
            xa, xb = ga.variables[name][:], gb.variables[name][:]
            kind = getattr(getattr(xa, "dtype", None), "kind", None)
            if not np.array_equal(np.ma.getmaskarray(xa), np.ma.getmaskarray(xb)):
                return "mask differs: " + prefix + name, float("inf")
            if kind in ("f", "i", "u"):
                xa, xb = np.asarray(xa, dtype=float), np.asarray(xb, dtype=float)
                if xa.shape != xb.shape:
                    return "shape of %s%s differs" % (prefix, name), float("inf")
                if not np.array_equal(np.isfinite(xa), np.isfinite(xb)):
                    return "finite values differ: " + prefix + name, float("inf")
                if not np.array_equal(np.isnan(xa), np.isnan(xb)):
                    return "NaN locations differ: " + prefix + name, float("inf")
                valid = np.isfinite(xa) & ~np.ma.getmaskarray(ga.variables[name][:])
                if not np.array_equal(xa[~np.isfinite(xa)], xb[~np.isfinite(xb)], equal_nan=True):
                    return "nonfinite values differ: " + prefix + name, float("inf")
                xa, xb = xa[valid], xb[valid]
                scale = np.maximum(np.maximum(np.abs(xa), np.abs(xb)), ABS_TOL)
                worst = max(worst, float(np.max(np.abs(xa - xb) / scale)) if xa.size else 0.0)
            else:
                # Labels and their ORDER. The category ordering is the only thing binding a
                # raster to its name; a silent permutation is a mislabelled product.
                if [str(v) for v in np.ravel(xa)] != [str(v) for v in np.ravel(xb)]:
                    return "labels of %s%s differ (order or content)" % (prefix, name), float("inf")
        groups_a, groups_b = set(ga.groups), set(gb.groups)
        for name in sorted(groups_a ^ groups_b):
            side = "reference" if name in groups_a else "rebuild"
            return "group %s%s present only in the %s" % (prefix, name, side), float("inf")
        for name in sorted(groups_a):
            message, sub = walk(ga.groups[name], gb.groups[name], prefix + name + "/")
            if sub == float("inf"):
                return message, sub
            worst = max(worst, sub)
        return None, worst

    with Dataset(a) as da, Dataset(b) as db:
        message, worst = walk(da, db)
        if message is not None:
            return message, worst
    return ("arrays within tolerance" if worst <= REL_TOL else "array difference"), worst


def targets(root, seeded=()):
    """Every product the reproduction must account for.

    rc42 (the twentieth review's fifth gate): the release manifest lists 74 products, the
    validation manifest 104 (every row of data/product_schemas.csv that exists), and the
    rc41 report compared only the first set - 27 manifest products, all rebuilt by OK
    phases, had no row at all. The targets are now the UNION of the release-manifest
    products, the schema registry's products, the parquet twins, the draw files and every
    path the reproduction seeded: a seeded file is a compared file."""
    with open(os.path.join(root, "outputs", "release_manifest.json"), encoding="utf-8") as handle:
        manifest = json.load(handle)
    paths = [p["path"] for p in manifest["products"]]
    schemas = asset_path(root, "data", "product_schemas.csv")
    if os.path.exists(schemas):
        with open(schemas, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(line for line in handle if not line.startswith("#")):
                rel = row["relative_path"]
                if os.path.exists(asset_path(root, rel)):
                    paths.append(rel)
    paths += [rel for rel in seeded if os.path.exists(asset_path(root, rel))]
    for extra in ("outputs/pakemis_atomic_annual.parquet",
                  "outputs/pakemis_monthly_" + CORE_SUFFIX + ".parquet",
                  "outputs/pakemis_annual_" + CORE_SUFFIX + ".parquet"):
        if os.path.exists(asset_path(root, extra)):
            paths.append(extra)
    draws = os.path.join(root, "outputs", "mc_draws")
    if os.path.isdir(draws):
        paths += sorted("outputs/mc_draws/" + n for n in os.listdir(draws)
                        if not n.startswith("."))
    return sorted(set(paths) - RETIRED_GHG_PANEL_PRODUCTS)


def load_ledger(tree):
    """({written path: (phase label, status)}, {seeded path}) from the rebuild's run ledger.

    rc41: the ledger is what ties a product to a phase that ran. Without it (an older tree),
    the fallback is the summary-table regex, and every product is `not_rebuilt` unless its
    phase printed OK - strictly less generous than the rc40 report, never more."""
    writers, seeded = {}, set()
    path = os.path.join(tree, "logs", "pakemis_run_ledger.json")
    if not os.path.exists(path):
        return None, seeded
    with open(path, encoding="utf-8") as h:
        ledger = json.load(h)
    for entry in ledger.get("seeded", []):
        seeded.add(entry["path"])
    for phase in ledger.get("phases", []):
        for rel in phase.get("written", []):
            writers[rel] = (phase["label"], phase["status"])      # last writer wins
    return writers, seeded


# rc42: the release manifest describes the release CHECKOUT - the commit it was cut at, the
# 3.8 GB document vault's digests, the data files present - and a reproduction inside a
# package regenerates it from a tree with no .git, no vault and a SOURCE_MANIFEST.csv of its
# own. Those blocks differ by construction; every other block (the products and their
# digests above all) must agree byte for byte.
RELEASE_CHECKOUT_BLOCKS = ("git", "source_documents", "sources")


def _release_manifest_masked_equal(a, b):
    import json
    try:
        with open(a, encoding="utf-8") as fa, open(b, encoding="utf-8") as fb:
            ja, jb = json.load(fa), json.load(fb)
    except (OSError, ValueError):
        return False
    for block in RELEASE_CHECKOUT_BLOCKS:
        ja.pop(block, None)
        jb.pop(block, None)
    return ja == jb


def load_rewritable(tree):
    """{seeded path: reproducible_in_package} from the ledger's seeded list."""
    path = os.path.join(tree, "logs", "pakemis_run_ledger.json")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as handle:
        ledger = json.load(handle)
    return {entry["path"]: entry.get("reproducible_in_package", "")
            for entry in ledger.get("seeded", [])}


def main(root, tree, report, _ignored=None):
    rows, failed = [], 0
    writers, seeded = load_ledger(tree)
    rewritable = load_rewritable(tree)
    if writers is None:
        print("WARNING: no run ledger in the rebuilt tree; products cannot be tied to a phase "
              "and every one is reported not_rebuilt unless bytes prove otherwise is impossible")
        writers = {}
    for rel in targets(root, seeded):
        a, b = asset_path(root, rel), os.path.join(tree, rel)
        row = {"path": rel, "status": "", "detail": "", "max_rel_diff": "", "writer_phase": "", "phase_status": ""}
        phase, status = writers.get(rel, ("", ""))
        row.update(writer_phase=phase, phase_status=status)
        rebuilt = status == "OK"
        if rel in seeded and rebuilt:
            # rc42: a seeded product a phase then rewrote. Only the two declared classes may
            # be both (the prior-release manifest read then rewritten; the network phase's
            # cached products under a full run); anything else seeded that a phase touched is
            # a registry error. Either way the bytes must still match the packaged ones.
            allowed = rewritable.get(rel) in ("rewritten", "network")
            same = os.path.exists(b) and sha256(a) == sha256(b)
            masked = (not same and allowed and rel.endswith("release_manifest.json")
                      and os.path.exists(b) and _release_manifest_masked_equal(a, b))
            if allowed and same:
                row.update(status="seeded_then_rewritten_identical",
                           detail="seeded from the registry, then rewritten by phase %r to the same bytes" % phase)
            elif masked:
                row.update(status="seeded_then_rewritten_identical",
                           detail="seeded from the registry, then rewritten by phase %r to the same bytes "
                                  "outside the blocks that describe the release checkout (%s), which a "
                                  "package cannot carry: no .git, no source vault, and a source manifest "
                                  "of its own" % (phase, ", ".join(RELEASE_CHECKOUT_BLOCKS)))
            elif allowed:
                row.update(status="difference", detail="seeded, then rewritten by phase %r to different bytes" % phase)
                failed += 1
            else:
                row.update(status="difference", detail="a phase rewrote a product the registry holds as %r"
                           % (rewritable.get(rel) or "no"))
                failed += 1
        elif rel in seeded and not rebuilt:
            row.update(status="seeded", detail="held product (data/held_products.csv), seeded into the empty "
                                                "outputs/ and verified against its release digest; not rebuilt")
            if not os.path.exists(b) or sha256(a) != sha256(b):
                row.update(status="difference", detail="seeded product differs from the packaged bytes")
                failed += 1
        elif not os.path.exists(b):
            row.update(status="missing_in_rebuild", detail="no phase wrote this file in the rebuild")
            failed += 1
        elif not rebuilt:
            row.update(status="not_rebuilt", detail="present in the rebuilt tree but no phase logged OK and wrote it "
                                                     "in this run (%s)" % (("phase %r ended %s" % (phase, status)) if phase else "no writer in the ledger"))
            failed += 1
        elif sha256(a) == sha256(b):
            row.update(status="rebuilt_identical", detail="bytewise")
        elif rel.endswith(".nc"):
            detail, worst = cube_diff(a, b)
            row.update(status="rebuilt_identical_numerically" if worst is not None and worst <= REL_TOL
                       else "difference", detail=detail,
                       max_rel_diff="" if worst is None else "%.3e" % worst)
            failed += row["status"] == "difference"
        elif rel in EXPECTED:
            equal = _release_manifest_masked_equal(a, b)
            row.update(status="rebuilt_expected_difference" if equal else "difference", detail=EXPECTED[rel])
            failed += not equal
        elif rel.endswith(".csv"):
            detail, worst = numeric_csv_diff(a, b)
            row.update(status="rebuilt_identical_numerically" if worst <= REL_TOL else "difference",
                       detail=detail, max_rel_diff="%.3e" % worst if worst != float("inf") else "inf")
            failed += row["status"] == "difference"
        else:
            row.update(status="difference", detail="bytes differ (binary; no numeric comparison)")
            failed += 1
        rows.append(row)
    with open(report, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=("path", "status", "detail", "max_rel_diff",
                                                    "writer_phase", "phase_status"))
        writer.writeheader()
        writer.writerows(rows)
    tally = {}
    for r in rows:
        tally[r["status"]] = tally.get(r["status"], 0) + 1
    print("compared %d files: %s" % (len(rows), ", ".join("%s=%d" % kv for kv in sorted(tally.items()))))
    for r in rows:
        if r["status"] in ("difference", "missing_in_rebuild", "not_rebuilt"):
            print("  %s %s: %s" % (r["status"].upper(), r["path"], r["detail"]))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:5]))
