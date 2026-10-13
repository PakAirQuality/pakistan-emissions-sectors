"""Verify a mounted source vault against data/raw_manifest.csv before the documents gate runs.

Usage: python3 tests/validation/verify_vault.py <overlay root>

rc42 (the twentieth review's gate 14). The package registers every third-party document
with its SHA-256 and does not carry the bytes; ./validate.sh --documents DIR builds an
overlay of the package in which sources/, data/raw/ and data/cache/ are the vault's, and
this script checks, file by file, that what is mounted is what the release registered:
every vault file under a registered path must hash to its registered digest (a wrong
edition fails, loudly, before any test reads it), and the script reports how many
registered documents the vault supplies. Exit 0 iff no mounted file mismatches.
"""

from pkinv.assets import asset_path
import hashlib
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))

TREES = ("sources", "data/raw", "data/cache")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(root):
    os.environ.setdefault("PKINV_ROOT", root)
    from pkinv.core import documents
    registered = documents.registered()
    mounted = present = mismatched = unregistered = 0
    problems = []
    for tree in TREES:
        top = asset_path(root, tree)
        if not os.path.isdir(top):
            continue
        mounted += 1
        for folder, _dirs, names in os.walk(top):
            for name in names:
                if name.startswith("."):
                    continue
                rel = os.path.relpath(os.path.join(folder, name), root).replace(os.sep, "/")
                want = registered.get(rel)
                if want is None:
                    unregistered += 1
                    continue
                present += 1
                if sha256(os.path.join(folder, name)) != want:
                    mismatched += 1
                    problems.append(rel)
    supplied = present
    total = sum(1 for rel in registered if rel.startswith(tuple(t + "/" for t in TREES)))
    print("vault: %d of %d registered documents present (%d trees mounted, %d unregistered files ignored), "
          "%d mismatched" % (supplied, total, mounted, unregistered, mismatched))
    for rel in problems[:50]:
        print("  MISMATCH %s" % rel)
    return 1 if mismatched else 0


if __name__ == "__main__":
    sys.exit(main(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")))
