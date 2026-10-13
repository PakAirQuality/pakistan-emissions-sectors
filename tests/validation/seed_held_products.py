"""Seed the held products into an EMPTY outputs/ directory and record what was seeded.

Usage: python3 tests/validation/seed_held_products.py <package root> <reproduction tree>

Reads data/held_products.csv in the package, copies each listed file from the package into
the reproduction tree (creating outputs/ as needed), verifies the copied bytes against
sha256_at_release, and writes <tree>/logs/seeded_products.json - the list run_all's ledger
carries under "seeded" so compare_outputs can classify those products as `seeded` rather
than `rebuilt`. Exits non-zero if a held file is missing or its digest does not match the
registry: a seed that cannot be verified is not a seed.
"""

from pkinv.assets import asset_path
import csv
import hashlib
import json
import os
import shutil
import sys


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(root, tree):
    registry = asset_path(root, "data", "held_products.csv")
    with open(registry, encoding="utf-8") as handle:
        rows = list(csv.DictReader(line for line in handle if not line.startswith("#")))
    seeded, problems = [], []
    for r in rows:
        src = asset_path(root, r["path"])
        dst = os.path.join(tree, r["path"])
        if not os.path.exists(src):
            problems.append("%s: not in the package" % r["path"])
            continue
        digest = sha256(src)
        # `committed-copy`: the release manifest is seeded as committed and verified by the
        # release-integrity tests, never by a digest here (see the registry's banner).
        if r["sha256_at_release"] != "committed-copy" and digest != r["sha256_at_release"]:
            problems.append("%s: sha256 %s != registry %s" % (r["path"], digest[:12], r["sha256_at_release"][:12]))
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(src, dst)
        seeded.append({"path": r["path"], "sha256": digest, "producer": r["producer"],
                       "reason_held": r["reason_held"], "reproducible_in_package": r["reproducible_in_package"]})
    os.makedirs(os.path.join(tree, "logs"), exist_ok=True)
    with open(os.path.join(tree, "logs", "seeded_products.json"), "w", encoding="utf-8") as handle:
        json.dump(seeded, handle, indent=1, sort_keys=True)
        handle.write("\n")
    print("seeded %d held products into %s" % (len(seeded), os.path.relpath(os.path.join(tree, "outputs"), tree)))
    for p in problems:
        print("  PROBLEM " + p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])))
