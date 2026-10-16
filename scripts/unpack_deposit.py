#!/usr/bin/env python3
"""Verify and assemble the local release collection into an empty reproduction tree."""
import argparse
import hashlib
import io
from pathlib import Path, PurePosixPath
import zipfile


def verify(archive, sums_prefix=""):
    names = archive.namelist()
    # The archive's own list is the shallowest one. rc68 archives also carry nested lists (the
    # campaign reproduction folder, the preserved baselines), and taking the first in name
    # order checked a baseline's list against the archive root and refused the release.
    candidates = [name for name in names if name.endswith("/SHA256SUMS") or name == "SHA256SUMS"]
    if not candidates:
        raise ValueError("archive has no SHA256SUMS")
    sums = min(candidates, key=lambda name: (name.count("/"), name))
    prefix = sums.rsplit("/", 1)[0] + "/" if "/" in sums else ""
    listed = set()
    for line in archive.read(sums).decode().splitlines():
        digest, name = line.split("  ", 1)
        target = name if name in names else prefix + name
        if target not in names or hashlib.sha256(archive.read(target)).hexdigest() != digest:
            raise ValueError("checksum does not reproduce: " + target)
        listed.add(target)
    actual = {name for name in names if not name.endswith("/") and name != sums}
    if listed != actual:
        raise ValueError("checksum inventory differs from archive entries")
    return actual


def destination(name, kind):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError("unsafe archive path: " + name)
    if kind == "software":
        return PurePosixPath(*path.parts[1:])
    if kind == "documentation" or len(path.parts) == 1:
        return path
    folder, rest = path.parts[0], path.parts[1:]
    if folder == "docs":                 # the ODbL companion carries its rebuild note at top level
        return path
    if folder not in ("pakemis-core", "pakemis-support", "pakemis-audit"):
        raise ValueError("unexpected data package path: " + name)
    if rest[0] == "inputs":
        return PurePosixPath("data", *rest[1:])
    if rest[0] == "reproduction":
        return PurePosixPath("outputs", *rest[1:])
    if rest[0] == "provenance":
        return PurePosixPath("outputs", *rest[1:])
    if rest[0] == "docs":
        return PurePosixPath("docs", *rest[1:])
    if rest[0] == "review-evidence":
        if len(rest) < 3 or rest[1] != "campaign":
            raise ValueError("unexpected review-evidence path: " + name)
        return PurePosixPath(*rest[1:])
    return PurePosixPath("outputs", *rest)


def unpack(source, output):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("reproduction destination must be empty")
    output.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(source) as release:
        sums_name = next(name for name in release.namelist() if name.endswith("-deposits.SHA256SUMS"))
        checks = dict((name, digest) for digest, name in
                      (line.split("  ", 1) for line in release.read(sums_name).decode().splitlines()))
        if set(checks) != set(release.namelist()) - {sums_name}:
            raise ValueError("release collection checksum inventory differs")
        for name in sorted(checks):
            data = release.read(name)
            if hashlib.sha256(data).hexdigest() != checks[name]:
                raise ValueError("collection checksum failed: " + name)
            kind = ("software" if name.endswith("-software.zip") else
                    "documentation" if name.endswith("-documentation.zip") else "data")
            with zipfile.ZipFile(io.BytesIO(data)) as archive:
                for entry in sorted(verify(archive)):
                    target = output / destination(entry, kind)
                    body = archive.read(entry)
                    if target.exists() and target.read_bytes() != body:
                        raise ValueError("conflicting package bytes: " + str(target))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(body)
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("collection")
    parser.add_argument("destination")
    args = parser.parse_args()
    print(unpack(args.collection, args.destination))
