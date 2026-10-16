"""Shared build identities. No producer runs when this module is imported."""
import dataclasses
import functools
import hashlib
import importlib.metadata
import json
import os
import platform
import sys


def asset_bindings(root):
    """Declared physical inputs, without treating an old filename as storage."""
    if not os.path.isfile(os.path.join(root, "data/catalog/assets.csv")):
        return []                       # small isolated build fixtures have no catalog
    from pkinv.assets import _index
    # Registry construction also happens in scientific children importing
    # run_all for writer ownership. It uses location bindings, not the complete
    # presentation catalog; do not mark every metadata label as a model input.
    return _index(root)[0]


def physical_paths(declaration, root):
    """Expand a legacy file/directory/glob into its registered physical members.

    Sector organization can split one old directory across several purposes. Never
    resolve such a directory to one arbitrary destination or follow alias symlinks.
    """
    import fnmatch
    prefix = ""
    if declaration.startswith(("held:", "prior:", "glob:")):
        prefix, declaration = declaration.split(":", 1)
        prefix += ":"
    bindings = asset_bindings(root)
    if not bindings or not declaration.startswith("data/"):
        return (prefix + declaration,)
    if declaration.endswith("/") or prefix == "glob:":
        matches = []
        for asset in bindings:
            legacy = asset["legacy_path"]
            if (fnmatch.fnmatch(legacy, declaration) if prefix == "glob:" else
                    legacy.startswith(declaration)):
                matches.append(asset["path"])
        if matches:
            # A physical wildcard would reintroduce undeclared files. Membership of
            # the explicit catalog is part of task identity instead.
            qualifier = "" if prefix == "glob:" else prefix
            return tuple(qualifier + path for path in sorted(set(matches)))
    from pkinv.assets import resolve
    absolute = resolve(os.path.join(root, declaration), root=root)
    path = os.path.relpath(absolute, root)
    if declaration.endswith("/"):
        path += "/"
    return (prefix + path,)


def phase_identity(phase):
    return dataclasses.asdict(phase)


@functools.lru_cache(maxsize=1)
def _packages():
    return sorted((d.metadata.get("Name", ""), d.version)
                  for d in importlib.metadata.distributions())


def environment_identity(root):
    locks = {}
    for name in ("requirements.lock", "pyproject.toml"):
        path = os.path.join(root, name)
        if os.path.isfile(path):
            with open(path, "rb") as handle:
                locks[name] = hashlib.sha256(handle.read()).hexdigest()
    return {"python": sys.version, "executable": sys.executable,
            "data_layout": "pkinv.data-layout/v1",
            "platform": platform.platform(), "packages": _packages(), "locks": locks,
            "variables": {key: os.environ.get(key) for key in
                          ("PYTHONHASHSEED", "PYTHONPATH", "TZ", "LC_ALL", "LANG",
                           "OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")}}


def task_id(phase):
    """Stable callable identity, retaining argument distinctions such as MC draws."""
    return phase.target


def dump_atomic(path, value):
    import tempfile
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=os.path.dirname(os.path.abspath(path)),
                                     prefix=".build-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def file_identity(path):
    """Metadata identity for detecting edits while a producer is running."""
    try:
        stat = os.stat(path)
        return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
    except OSError:
        return None


SNAPSHOT_IGNORED = {".git", ".venv", "venv", "node_modules", "__pycache__", "logs",
                    ".pytest_cache", ".mypy_cache", ".ruff_cache"}


def directory_identity(path):
    try:
        with os.scandir(path) as entries:
            return sorted((entry.name, "link:" + os.readlink(entry.path) if entry.is_symlink()
                           else "directory" if entry.is_dir() else "file")
                          for entry in entries if entry.name not in SNAPSHOT_IGNORED)
    except OSError:
        return None


def input_snapshot(root):
    """Snapshot potential cold-task inputs before its actual reads are known."""
    result, directories = {}, {}

    def walk(top):
        for folder, dirs, names in os.walk(top):
            dirs[:] = [name for name in dirs if name not in SNAPSHOT_IGNORED]
            directories[os.path.relpath(folder, root)] = directory_identity(folder)
            for name in names:
                path = os.path.join(folder, name)
                result[os.path.relpath(path, root)] = file_identity(path)

    walk(root)
    # rc69: the restricted layers are mounted as symlinks (pkinv.core.layers) and os.walk does
    # not enter a linked folder, so their files were absent here and every one of them read
    # as "changed while the task ran". A mounted folder is walked through its link.
    from pkinv.core import layers
    for name in layers.mounts(root=os.fspath(root)) if layers.mode(os.fspath(root)) == "overlay" else ():
        top = os.path.join(root, name)
        if os.path.islink(top) and os.path.isdir(top):
            walk(top)
    return {"files": result, "directories": directories}


class FileDigests:
    """Developer-only digest index, invalidated by inode/size/mtime/ctime identity.

    Full strict reproduction never consults this index. Including ctime detects a
    same-size edit even when a tool deliberately restores the old mtime.
    Directory membership is always walked; directory mtimes cannot validate children.
    """
    def __init__(self, root):
        self.path = os.path.join(root, "logs", "file_digests.json")
        try:
            with open(self.path, encoding="utf-8") as handle:
                record = json.load(handle)
            self.entries = (record.get("files", {}) if
                            os.path.realpath(record.get("root", "")) == os.path.realpath(root)
                            else {})
        except (OSError, ValueError):
            self.entries = {}
        self.root = root

    def digest(self, path, fallback):
        try:
            stat = os.stat(path)
        except OSError:
            return "MISSING"
        if not os.path.isfile(path):
            return fallback(path)
        identity = [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
        cached = self.entries.get(path)
        if cached and cached[0] == identity:
            return cached[1]
        value = fallback(path)
        self.entries[path] = [identity, value]
        return value

    def save(self):
        dump_atomic(self.path, {"schema": "pkinv.file_digests/v1", "root": self.root,
                                "files": self.entries})
