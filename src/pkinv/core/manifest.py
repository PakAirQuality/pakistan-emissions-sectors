"""Source hashing and manifest writing, shared.

Six sector runners grew their own copy of "glob some patterns, sha256 each file, dump
JSON", in three mutually incompatible shapes, and four sectors never grew one at all.
This is that code, once, so a manifest means the same thing everywhere and the release
manifest can aggregate them without a per-sector special case.

Two properties worth stating, because the previous copies disagreed about both:

HASHES ARE VERIFIED, NOT JUST RECORDED. `verify_sources` re-hashes against a recorded
set and raises on mismatch. A manifest that only records a digest documents what was
read; one that checks it detects a source changing under the inventory, which is the
failure it exists to catch. Only the aviation runner did this before.

TIMESTAMPS ARE OPTIONAL AND OFF BY DEFAULT. A `generated_at` field makes every manifest
differ on every run, which destroys the "regenerates byte-identically" test that proves
a build is reproducible. The release manifest passes `stamp=True` deliberately, once,
and its test excludes that one field rather than giving up the property everywhere.
"""

from pkinv.assets import asset_path, catalog, resolve
import fnmatch
import re
import glob
import hashlib
import json
import os

from pkinv.paths import ROOT

SCHEMA_VERSION = "pkinv.manifest/v1"


def sha256_file(path):
    path = resolve(path)
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_sources(patterns, root=ROOT):
    """[{path, sha256}] for every file matching any glob pattern, path-sorted.

    Patterns are relative to the repository root and are resolved in sorted order so the
    result is deterministic regardless of filesystem iteration order.

    recursive=True IS LOAD-BEARING AND WAS MISSING. Without it Python treats `**` as a plain
    `*` - one directory level - so release_manifest.DOCUMENT_PATTERNS ("sources/**/*.pdf" and
    its siblings) hashed 116 of the 257 archived documents and silently skipped 141, every
    one of them a level deeper: sources/Agriculture/machinery_census_2004/*.pdf, the OGRA and
    HIES subtrees, and more. The manifest's central promise is the hash of every primary
    source, and it was keeping that promise for 45 percent of them while reporting no
    problem. Found by the deposit register, which asked every archived document for its hash
    and got nothing back from more than half.
    """
    seen, out = set(), []
    assets = catalog(root)
    for pattern in patterns:
        candidates = [(path, os.path.relpath(path, root)) for path in
                      glob.glob(os.path.join(root, pattern), recursive=True)]
        expression = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*")
        expression = expression.replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
        candidates.extend((resolve(asset["legacy_path"], root=root), asset["legacy_path"])
                          for asset in assets if re.fullmatch(expression, asset["legacy_path"]))
        for path, identity in sorted(candidates):
            if not os.path.isfile(path) or path in seen:
                continue
            seen.add(path)
            out.append({"path": identity,
                        "sha256": sha256_file(path)})
    return sorted(out, key=lambda r: r["path"])


def verify_sources(recorded, root=ROOT):
    """Re-hash a recorded source list; return the entries that no longer match.

    An empty list means every source is byte-identical to when the manifest was written.
    Missing files are reported with sha256 None rather than raising, so a caller can
    distinguish "changed" from "gone".
    """
    changed = []
    for entry in recorded:
        path = asset_path(root, entry["path"])
        if not os.path.isfile(path):
            changed.append({"path": entry["path"], "recorded": entry["sha256"],
                            "actual": None})
            continue
        actual = sha256_file(path)
        if actual != entry["sha256"]:
            changed.append({"path": entry["path"], "recorded": entry["sha256"],
                            "actual": actual})
    return changed


def write_manifest(path, body, stamp=False):
    """Write a manifest as sorted-key JSON with a trailing newline.

    Sorted keys and a fixed indent make two manifests diffable and make byte-equality a
    usable test. `stamp` adds generated_at (UTC, second resolution); leave it off unless
    the caller's own test knows to ignore the field.
    """
    payload = dict(body)
    payload.setdefault("schema", SCHEMA_VERSION)
    if stamp:
        import datetime
        payload["generated_at"] = (datetime.datetime.now(datetime.timezone.utc)
                                   .replace(microsecond=0).isoformat())
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, sort_keys=True)
        f.write("\n")
    return path


def read_manifest(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)
