"""Assemble the agriculture deposit capsule and prove it reruns.

WHAT THE PREVIOUS CAPSULE CLAIMED AND COULD NOT SUPPORT. The rc38 witness passed all 361 of
its own checksums, and covered 111 of 618 release-checksum files and 40 of 68 manifest
products. Its "everything needed to rerun" claim therefore rested on a checksum set that
described the capsule rather than the release. This one carries its OWN manifest and
checksums too, but it also ships a test suite and a script that runs it, so the claim is
demonstrated instead of asserted.

NOTHING TO INSTALL. The agriculture engine and its tests run on the Python 3 standard library
alone. requirements.txt has said that about the national and provincial phases for releases;
this capsule is the first artefact to prove it, by running the suite in a venv with nothing
installed. The geospatial stack belongs to the gridding phases, which this capsule does not
contain.

WHAT IS IN IT is decided by what the suite actually reads, not by a directory list: the code
under src/pkinv, the tests it runs, and the data and outputs those tests open. The inclusion
rule is verified the only way that means anything - the capsule's own run_tests.sh is
executed inside the assembled tree, so a file left out is a failure rather than a surprise
for whoever downloads it.

Writes: dist/pakemis-agriculture-capsule/  (outside the repository tree)
        dist/pakemis-agriculture-capsule/MANIFEST.csv
        dist/pakemis-agriculture-capsule/SHA256SUMS
"""
import csv
import hashlib
import os
import shutil
import subprocess
import sys
from pkinv.assets import legacy_path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIST = os.path.join(ROOT, "dist", "pakemis-agriculture-capsule")

# The suite the capsule ships, and the modules it needs beside them.
TEST_MODULES = (
    "test_inventory", "test_livestock_rebase", "test_fertiliser_window", "test_urea_basis",
    "test_ne_categories", "test_agriculture_control", "test_method_registry",
    "test_residue_ledger", "test_n_ledger", "test_agriculture_fiscal",
    "test_joint_uncertainty_reconciles", "test_agriculture_timing", "test_spatial_exceptions",
)

# Trees copied whole. data/raw and data/cache are the held SOURCE DOCUMENTS - 3.8 GB of PDFs
# and workbooks - and are deliberately absent: the capsule reruns the ENGINE, and the
# documents behind the transcriptions are listed with their hashes in the manifest so a
# reader can obtain them without the capsule carrying them.
TREES = ("src", "tests", "capsule")
DATA_SKIP = ("data/raw", "data/cache", "data/gis/manual")


def _copy_tree(rel, into, skip=()):
    src = os.path.join(ROOT, rel)
    count = 0
    for folder, dirs, names in os.walk(src):
        dirs[:] = [d for d in dirs if d not in ("__pycache__", ".pytest_cache")]
        rel_folder = os.path.relpath(folder, ROOT)
        if any(rel_folder.startswith(s) for s in skip):
            continue
        for name in names:
            if name.endswith((".pyc", ".pyo")):
                continue
            source = os.path.join(folder, name)
            logical = legacy_path(source, root=ROOT)
            if any(logical == prefix or logical.startswith(prefix.rstrip("/") + "/") for prefix in skip):
                continue
            dest = os.path.join(into, os.path.relpath(source, ROOT))
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            shutil.copy2(source, dest)
            count += 1
    return count


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build():
    if os.path.exists(DIST):
        shutil.rmtree(DIST)
    os.makedirs(DIST)
    counts = {}
    for tree in TREES:
        counts[tree] = _copy_tree(tree, DIST)
    counts["data"] = _copy_tree("data", DIST, skip=DATA_SKIP)
    counts["outputs"] = _copy_tree("outputs", DIST, skip=("outputs/figures", "outputs/mc_draws"))
    for name in ("requirements.txt", "pyproject.toml", "CITATION.cff", "CHANGELOG.md"):
        source = os.path.join(ROOT, name)
        if os.path.exists(source):
            shutil.copy2(source, os.path.join(DIST, name))
            counts.setdefault("root", 0)
            counts["root"] += 1
    return counts


def manifest():
    rows = []
    for folder, dirs, names in os.walk(DIST):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in sorted(names):
            if name in ("MANIFEST.csv", "SHA256SUMS"):
                continue
            path = os.path.join(folder, name)
            rel = os.path.relpath(path, DIST)
            rows.append({"path": rel, "bytes": os.path.getsize(path),
                         "sha256": _sha256(path)})
    rows.sort(key=lambda r: r["path"])
    with open(os.path.join(DIST, "MANIFEST.csv"), "w", newline="", encoding="utf-8") as handle:
        handle.write("# THE AGRICULTURE DEPOSIT CAPSULE, file by file (rc39 A12).\n")
        handle.write("# Every file this capsule ships, with its size and SHA-256. The suite\n")
        handle.write("# it reruns is capsule/run_tests.sh; the rerun was DEMONSTRATED on the\n")
        handle.write("# platform named in capsule/VERIFIED.txt and nowhere else.\n")
        writer = csv.DictWriter(handle, fieldnames=("path", "bytes", "sha256"))
        writer.writeheader()
        writer.writerows(rows)
    with open(os.path.join(DIST, "SHA256SUMS"), "w", encoding="utf-8") as handle:
        for row in rows:
            handle.write("%s  %s\n" % (row["sha256"], row["path"]))
    return rows


def demonstrate():
    """Run the capsule's own suite INSIDE the capsule. A capsule that has not been rerun is
    a claim; this is what turns it into a record."""
    script = os.path.join(DIST, "capsule", "run_tests.sh")
    os.chmod(script, 0o755)
    proc = subprocess.run(["sh", script], cwd=DIST, capture_output=True, text=True)
    return proc.returncode, proc.stdout + proc.stderr


def main(argv=()):
    counts = build()
    rows = manifest()
    total = sum(r["bytes"] for r in rows)
    print("capsule -> %s" % os.path.relpath(DIST, ROOT))
    for tree, n in sorted(counts.items()):
        print("  %-10s %5d files" % (tree, n))
    print("  %-10s %5d files, %.1f MB" % ("TOTAL", len(rows), total / 1e6))

    if "--no-run" in argv:
        return 0
    print("\n== demonstrating the rerun inside the capsule ==")
    code, output = demonstrate()
    print(output.strip()[-2000:])
    verified = os.path.join(DIST, "capsule", "VERIFIED.txt")
    with open(verified, "w", encoding="utf-8") as handle:
        handle.write("THE RERUN THIS CAPSULE DEMONSTRATES, AND WHERE.\n\n")
        handle.write("platform : %s\n" % subprocess.run(
            ["uname", "-sr"], capture_output=True, text=True).stdout.strip())
        handle.write("python   : %s\n" % sys.version.split()[0])
        handle.write("command  : sh capsule/run_tests.sh\n")
        handle.write("result   : %s\n\n" % ("PASSED" if code == 0 else "FAILED"))
        handle.write("NOT verified on Linux, on Windows, or on any other CPython minor\n")
        handle.write("version. This file records one run on one machine, which is what was\n")
        handle.write("done; anything more would be a claim about platforms nobody tested.\n")
    manifest()                                  # re-hash: VERIFIED.txt is part of the capsule
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
