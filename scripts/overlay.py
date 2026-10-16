#!/usr/bin/env python3
"""Mount, check or unmount the restricted layers in a public clone.

The documents this inventory was built from stay in the private checkout (see
src/pkinv/core/layers.py for which paths and why). A public clone reads them through
symlinks of the same names, so every reader keeps its path. The public .gitignore lists
each name, so a link is never committed.

  python3 scripts/overlay.py link [PATH]   record PATH (or $PKINV_OVERLAY) in .pkinv-overlay
                                           and create the links
  python3 scripts/overlay.py check         every link resolves; no restricted file is a Git
                                           LFS pointer whose bytes were never fetched
  python3 scripts/overlay.py unlink        remove the links (never a real file)

A link is only ever created where nothing exists, and only a link is ever removed.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core import layers  # noqa: E402

LFS_HEADER = b"version https://git-lfs.github.com/spec/"


def _links():
    overlay = layers.overlay_root()
    if overlay is None or overlay == ROOT:
        raise SystemExit("no overlay is configured here (set %s or write %s)"
                         % (layers.ENVIRONMENT, layers.CONFIG))
    return overlay, layers.mounts()


def link(argv):
    if argv:
        with open(os.path.join(ROOT, layers.CONFIG), "w", encoding="utf-8") as handle:
            handle.write("# the private checkout that holds the restricted layers\n%s\n"
                         % os.path.abspath(os.path.expanduser(argv[0])))
    overlay, names = _links()
    made, kept, problems = 0, 0, []
    for name in names:
        source, target = os.path.join(overlay, name), os.path.join(ROOT, name)
        if not os.path.lexists(source):
            continue
        if os.path.islink(target):
            if os.path.realpath(target) == os.path.realpath(source):
                kept += 1
            else:
                problems.append("%s links elsewhere (%s)" % (name, os.readlink(target)))
            continue
        if os.path.lexists(target):
            problems.append("%s exists here as a real file or folder; not replaced" % name)
            continue
        os.makedirs(os.path.dirname(target), exist_ok=True)
        os.symlink(source, target)
        made += 1
    print("overlay %s: %d links made, %d already in place" % (overlay, made, kept))
    if problems:
        raise SystemExit("\n".join(problems))
    return check([])


def check(_argv):
    overlay, names = _links()
    problems, pointers, files = [], [], 0
    for name in names:
        source, target = os.path.join(overlay, name), os.path.join(ROOT, name)
        if not os.path.lexists(source):
            continue
        if not os.path.islink(target) or os.path.realpath(target) != os.path.realpath(source):
            problems.append("%s is not linked to the overlay" % name)
            continue
        walk = os.walk(target) if os.path.isdir(target) else [
            (os.path.dirname(target), [], [os.path.basename(target)])]
        for folder, _dirs, members in walk:
            for member in members:
                path = os.path.join(folder, member)
                files += 1
                if os.path.getsize(path) < 1024:
                    with open(path, "rb") as handle:
                        if handle.read(len(LFS_HEADER)) == LFS_HEADER:
                            pointers.append(os.path.relpath(path, ROOT))
    if pointers:
        problems.append("%d restricted files are Git LFS pointers whose bytes were never "
                        "fetched (run git lfs pull in %s): %s"
                        % (len(pointers), overlay, ", ".join(pointers[:5])))
    print("overlay %s: %d files under %d mounts, mode %s"
          % (overlay, files, len(names), layers.mode()))
    if problems:
        raise SystemExit("\n".join(problems))
    return 0


def unlink(_argv):
    removed = 0
    for name in layers.mounts():
        target = os.path.join(ROOT, name)
        if os.path.islink(target):
            os.unlink(target)
            removed += 1
    print("%d links removed" % removed)
    return 0


if __name__ == "__main__":
    commands = {"link": link, "check": check, "unlink": unlink}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        raise SystemExit(__doc__)
    sys.exit(commands[sys.argv[1]](sys.argv[2:]))
