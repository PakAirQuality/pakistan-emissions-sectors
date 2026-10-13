"""Document digests that survive a tree without the documents (rc41).

WHY. Sector runners record the sha256 of every source document they stand on in their
run manifests, hashing the file live. That is the right record on the release machine
and an impossible one in the validation package, which registers the 3.8 GB of
third-party documents instead of shipping them: the first strict empty-outputs
reproduction (rc41 Wave 1) stopped at every runner that opened a document only to hash
it. This module is the one answer:

  * a document that IS held is hashed live, and the live digest must equal the one
    data/raw_manifest.csv registers for it - a mismatch is a finding (the document or
    the register changed and nobody re-ran), never silently the newer of the two;
  * a document that is NOT held is carried forward from data/raw_manifest.csv, and the
    runner says so on its log; the run manifest it writes is byte-identical to the
    release's, because the digest is the same fact either way;
  * a document neither held nor registered raises - nothing is invented.

The CONSUMED DERIVATIVES (data/consumed_derivatives.csv) are the other half of the
same rule: the tables under data/activity that an ingest script extracts from a
document the package does not ship, with exactly the columns the engine reads. The
engine reads the table; scripts/ingest_*.py --check proves the table against the
document wherever the document is held (tests/test_data_rederivation.py).
"""
from __future__ import annotations

from pkinv.assets import asset_path, catalog, legacy_path

import fnmatch
import glob
import hashlib
import os
import re
from functools import lru_cache

from pkinv.paths import ROOT
from pkinv.activity.store import read_rows

RAW_MANIFEST = asset_path(ROOT, "data", "raw_manifest.csv")
DERIVATIVES = asset_path(ROOT, "data", "consumed_derivatives.csv")

_registered = None
_derivatives = None


def sha256(path):
    """Hash a held document once per unchanged file version within this process."""
    path = os.path.abspath(path)
    stat = os.stat(path)
    signature = (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    return _cached_sha256(path, signature)


@lru_cache(maxsize=256)
def _cached_sha256(path, signature):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    stat = os.stat(path)
    if signature != (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns):
        raise ValueError("%s changed while its document digest was being computed" % path)
    return digest.hexdigest()


def registered():
    """{repo-relative path: sha256} from data/raw_manifest.csv (loaded once)."""
    global _registered
    if _registered is None:
        _registered = {row["path"]: row["sha256"] for row in read_rows(RAW_MANIFEST)}
    return _registered


def derivatives():
    """{derivative path: register row} from data/consumed_derivatives.csv."""
    global _derivatives
    if _derivatives is None:
        _derivatives = {row["derivative"]: row for row in read_rows(DERIVATIVES)}
    return _derivatives


def relative(path):
    # Provenance registers predate the sector tree and deliberately keep their stable
    # logical source identities. Resolve moved files back to those identities before
    # looking them up, while preserving unregistered path strings as-is.
    return legacy_path(path, root=ROOT) if os.path.isabs(path) else path


def digest(path, quiet=False):
    """The sha256 of a source document, live when held, registered when not."""
    rel = relative(path)
    absolute = asset_path(ROOT, rel)
    known = registered().get(rel)
    if os.path.exists(absolute):
        live = sha256(absolute)
        if known is not None and known != live:
            raise ValueError(
                "%s: the held document's sha256 %s… differs from the %s… that "
                "data/raw_manifest.csv registers - the document or the register changed; "
                "rebuild the register (scripts/build_raw_manifest.py) before building on it"
                % (rel, live[:12], known[:12]))
        return live
    if known is None:
        raise FileNotFoundError(
            "%s: not held in this tree and not registered in data/raw_manifest.csv; "
            "nothing to carry forward" % rel)
    if not quiet:
        print("   document not held in this tree, digest carried from data/raw_manifest.csv: %s"
              % rel)
    return known


def require(path, purpose="a build phase reads it"):
    """Refuse, by name, a document the tree must hold to build. The message says where
    the document comes from: the validation package ships the ones data/public_documents.csv
    lists (on the publisher's recorded terms) and registers every other one."""
    absolute = asset_path(ROOT, path) if not os.path.isabs(path) else asset_path(path)
    if os.path.exists(absolute):
        return absolute
    rel = relative(path)
    public = asset_path(ROOT, "data", "public_documents.csv")
    listed = os.path.exists(public) and any(row["path"] == rel for row in read_rows(public))
    raise FileNotFoundError(
        "%s is not held in this tree and %s. %s" % (
            rel, purpose,
            "It is listed in data/public_documents.csv, so a complete validation package "
            "ships it under sources/ - restore it from the package or the URL that row names."
            if listed else
            "It is registered in data/raw_manifest.csv and not redistributed; obtain it from "
            "the publisher named in data/source_documents.csv."))


def digests(patterns, skip=()):
    """[{path, sha256}] for every document matching the repo-relative glob patterns,
    pattern by pattern and sorted within each (the order the runners always wrote):
    the union of what is on disk, what the asset catalog registers under the pattern,
    and what data/raw_manifest.csv registers - so a tree without the documents writes
    the same list.

    THE CATALOG BRANCH IS LOAD-BEARING. asset_path() resolves a registered FILE; a glob
    pattern is not one, so `data/activity/transport/*.csv` passed straight through to a
    directory the sector layout had emptied and matched nothing. The transport run
    manifest silently dropped fourteen of its eighty-nine hashed sources - the whole
    activity layer behind the sector's numbers - and the file still looked well formed.
    Matching the pattern against each asset's stable legacy identity, the way
    core.manifest.sha256_sources already does, is what keeps a relocation invisible here.
    """
    out, seen = [], set()
    assets = catalog(ROOT)
    for pattern in patterns:
        paths = set()
        for hit in glob.glob(asset_path(ROOT, pattern), recursive=True):
            if os.path.isfile(hit):
                paths.add(relative(hit))
        expression = re.escape(pattern).replace(r"\*\*/", "(?:.*/)?").replace(r"\*\*", ".*")
        expression = expression.replace(r"\*", "[^/]*").replace(r"\?", "[^/]")
        for asset in assets:
            identity = asset["legacy_path"]
            if re.fullmatch(expression, identity) and os.path.isfile(
                    os.path.join(ROOT, asset["path"])):
                paths.add(identity)
        for rel in registered():
            if fnmatch.fnmatch(rel, pattern):
                paths.add(rel)
        for rel in sorted(paths):
            if rel in skip or rel in seen:
                continue
            seen.add(rel)
            out.append({"path": rel, "sha256": digest(rel)})
    return out


def read_extract(path, types=None):
    """Rows of a consumed-derivative table with the declared columns re-typed (csv
    holds text; the engine's downstream arithmetic expects the numbers the extractor
    produced). An empty cell stays the empty string."""
    from pkinv.activity.store import read_rows as read_activity_rows
    types = types or {}
    rows = []
    for row in read_activity_rows(path):
        for column, convert in types.items():
            if row.get(column, "") != "":
                row[column] = convert(row[column])
        rows.append(row)
    return rows


def source_digest(derivative_path):
    """The registered sha256 of the document a consumed derivative was extracted from."""
    row = derivatives().get(relative(derivative_path))
    if row is None:
        raise KeyError("%s is not registered in data/consumed_derivatives.csv"
                       % relative(derivative_path))
    return row["source_sha256"]


def source_document(derivative_path):
    return derivatives()[relative(derivative_path)]["source_document"]
