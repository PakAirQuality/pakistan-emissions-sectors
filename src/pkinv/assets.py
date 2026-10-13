"""Stable data identities, independent of the sector folder layout.

The catalog owns locations. Historical paths remain logical aliases for released
source identities; they are never filesystem symlinks or duplicate data copies.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
import sys

from pkinv.paths import ROOT

LAYOUT_VERSION = "pkinv.data-layout/v1"
CATALOG = "data/catalog/assets.csv"
_CACHE = {}


def _index(root=ROOT):
    root = os.path.realpath(os.fspath(root))
    path = os.path.join(root, CATALOG)
    try:
        stat = os.stat(path)
        signature = (stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    except FileNotFoundError:
        return [], {}, {}, {}
    cached = _CACHE.get(root)
    if cached and cached[0] == signature:
        return cached[1:]
    with open(path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    forward, reverse = {}, {}
    for row in rows:
        target = row["path"]
        legacy = row["legacy_path"]
        for alias in (row["asset_id"], legacy, target):
            if alias in forward and forward[alias]["asset_id"] != row["asset_id"]:
                raise ValueError("Ambiguous asset alias: " + alias)
            forward[alias] = row
        reverse[target] = legacy
        canonical = row.get("canonical_path")
        if canonical:
            old_canonical = "data/canonical/" + legacy.removeprefix("data/")
            entry = dict(row, path=canonical)
            forward[canonical] = entry
            forward[old_canonical] = entry
            reverse[canonical] = old_canonical
    _CACHE[root] = (signature, rows, forward, reverse, _directories(rows))
    return _CACHE[root][1:]


def _directories(rows):
    """Legacy directories whose whole subtree relocated by one prefix substitution.

    A historical directory is only an alias when every registered file beneath it kept
    its relative position under a single destination. `data/gis/kilns` qualifies; the
    sectors under `data/activity` and `data/gis/manual` (whose `ghsl_built_1km` subtree
    went to `data/shared`) do not, and those stay unresolved rather than half right.
    """
    implied = {}
    for row in rows:
        legacy, target = row["legacy_path"].split("/"), row["path"].split("/")
        for depth in range(1, len(legacy)):
            suffix = legacy[depth:]
            if target[len(target) - len(suffix):] != suffix:
                continue
            implied.setdefault("/".join(legacy[:depth]), set()).add(
                "/".join(target[:len(target) - len(suffix)]))
    return {name: next(iter(seen)) for name, seen in implied.items() if len(seen) == 1}


def catalog(root=ROOT):
    sys.audit("pkinv.asset.catalog")
    return [dict(row) for row in _index(root)[0]]


def _relative(value, root):
    value = os.fspath(value)
    if os.path.isabs(value):
        relative = os.path.relpath(os.path.realpath(value), os.path.realpath(os.fspath(root)))
        if relative == ".." or relative.startswith("../"):
            return None
        return relative
    return os.path.normpath(value)


def resolve(value, *, root=ROOT):
    """Resolve an asset ID or legacy/current path; other paths pass through."""
    relative = _relative(value, root)
    if relative is None:
        return os.fspath(value)
    rows, forward, reverse, directories = _index(root)
    row = forward.get(relative)
    if row is None:
        # A vanished historical directory resolves too, so that joining a name onto it
        # does not build a path under a tree that no longer exists. A directory still
        # present on disk is a real one (raw documents stayed put) and is left alone.
        moved = directories.get(relative)
        if moved is None or os.path.isdir(os.path.join(os.fspath(root), relative)):
            return os.fspath(value)
        target = os.path.join(os.fspath(root), moved)
        sys.audit("pkinv.asset.resolve", relative + "/", target)
        return target
    target = os.path.join(os.fspath(root), row["path"])
    sys.audit("pkinv.asset.resolve", row["asset_id"], target)
    return target


def asset_path(*parts):
    """Join path parts and resolve registered files, including legacy aliases."""
    return resolve(os.path.join(*parts))


def legacy_path(value, *, root=ROOT):
    """Return the immutable repository-relative source identity for a location."""
    relative = _relative(value, root)
    if relative is None:
        return os.fspath(value)
    return _index(root)[2].get(relative, relative)


def members(prefix, *, root=ROOT):
    """Registered files beneath a historical or current directory, sorted by ID."""
    prefix = (_relative(prefix, root) or os.fspath(prefix)).rstrip("/") + "/"
    return sorted((row for row in catalog(root)
                   if row["legacy_path"].startswith(prefix) or row["path"].startswith(prefix)),
                  key=lambda row: row["asset_id"])


def clear_cache():
    _CACHE.clear()
