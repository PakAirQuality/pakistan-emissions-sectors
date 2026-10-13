"""Verify every line of SHA256SUMS with the standard library, and report what it does not cover.

Usage: python3 tests/validation/check_sha256sums.py <package root>

Exit 0 when every listed file hashes to its recorded digest. Files under logs/ are reported
separately and never fail the check: validate.sh and reproduce.sh rewrite them on every run,
so the digests recorded at packaging time describe the packager's run, not the reviewer's.
Files present in the tree but absent from SHA256SUMS (other than SHA256SUMS itself and
logs/) are listed as UNLISTED and fail the check - a package must not carry bytes it does not
vouch for.
"""

from pkinv.assets import asset_path
import hashlib
import os
import sys


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


# rc42: the log files the packager itself writes AFTER SHA256SUMS exists (its own tail,
# the self-check's log, the records gate's log). They are excluded from SHA256SUMS at
# packaging and tolerated as unlisted here; every other logs/ entry must verify under
# --strict, which is what a plain `sha256sum -c SHA256SUMS` demands.
PACKAGER_TAIL_LOGS = ("logs/build_tail.log", "logs/sha256_check_at_packaging.log", "logs/records_gate.log",
                      "logs/command_timings.csv", "logs/exit_codes.txt")


def main(root, strict=False):
    sums = os.path.join(root, "SHA256SUMS")
    if not os.path.exists(sums):
        print("SHA256SUMS is absent from %s: nothing to verify against (a package is hashed "
              "after its validations run; a tree without the file is not a finished package)" % root)
        return 2
    listed = {}
    with open(sums, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            digest, _, rel = line.partition("  ")
            listed[rel] = digest
    mismatched, missing, logs_changed = [], [], []
    for rel, digest in sorted(listed.items()):
        path = asset_path(root, rel)
        tolerated = rel.startswith("logs/") and not strict
        if not os.path.exists(path):
            # a reviewer may mount logs/ elsewhere (a read-only package with a writable
            # logs volume); the packaging run's logs are then absent, not corrupted
            (logs_changed if tolerated else missing).append(rel)
            continue
        actual = sha256(path)
        if actual != digest:
            (logs_changed if tolerated else mismatched).append(rel)
    present = set()
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in names:
            rel = os.path.relpath(os.path.join(folder, name), root)
            if rel == "SHA256SUMS" or name.endswith((".pyc", ".DS_Store")):
                continue
            if rel in PACKAGER_TAIL_LOGS or (rel.startswith("logs/") and not strict):
                continue
            present.add(rel)
    unlisted = sorted(present - set(listed))
    print("SHA256SUMS: %d entries, %d verified, %d mismatched, %d missing, %d unlisted, "
          "%d log files rewritten since packaging"
          % (len(listed), len(listed) - len(mismatched) - len(missing) - len(logs_changed),
             len(mismatched), len(missing), len(unlisted), len(logs_changed)))
    for rel in mismatched:
        print("  MISMATCH  %s" % rel)
    for rel in missing:
        print("  MISSING   %s" % rel)
    for rel in unlisted:
        print("  UNLISTED  %s" % rel)
    for rel in logs_changed:
        print("  (logs)    %s rewritten by a later run; not a failure" % rel)
    return 1 if (mismatched or missing or unlisted) else 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(main(os.path.abspath(args[0] if args else "."), strict="--strict" in sys.argv))
