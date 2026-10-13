"""Execute one producer and report Python file IO to its parent.

This is observation, not a sandbox: native libraries and external commands can do IO
outside Python's audit hooks. The scheduler therefore retains conservative dependencies
and serial barriers unless the task's declarations have separately been audited.
"""
import argparse
import json
import os
import runpy
import sys


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    parser.add_argument("--receipt", required=True)
    parser.add_argument("--script", action="store_true")
    parser.add_argument("target")
    parser.add_argument("arguments", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    root = os.path.realpath(args.root)
    reads, writes, directories, commands = set(), set(), set(), []
    canonical = set()
    assets = set()
    whole_asset_catalog = False
    active = True

    def relative(value):
        if not isinstance(value, (str, bytes, os.PathLike)):
            return None
        path = os.path.realpath(os.fsdecode(value))
        if path == root:
            return "."
        if not path.startswith(root + os.sep):
            return None
        rel = os.path.relpath(path, root)
        if "__pycache__" in rel.split(os.sep) or rel.endswith((".pyc", ".pyo")):
            return None
        return rel

    def audit(event, values):
        nonlocal whole_asset_catalog
        if not active:
            return
        if event == "open":
            path = relative(values[0])
            if path is None:
                return
            mode, flags = values[1], values[2]
            writing = (any(c in (mode or "") for c in "wax+") or
                       bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC)))
            if writing:
                writes.add(path)
            elif path not in writes:
                reads.add(path)
        elif event in ("os.listdir", "os.scandir"):
            path = relative(values[0])
            if path is not None:
                directories.add(path)
        elif event in ("os.rename", "os.remove"):
            path = relative(values[1] if event == "os.rename" else values[0])
            if path is not None:
                writes.add(path)
        elif event == "subprocess.Popen":
            command = values[1]
            commands.append(command if isinstance(command, str) else [str(x) for x in command])
            if isinstance(command, (list, tuple)):
                for word in command:
                    path = relative(word)
                    if path and os.path.isfile(os.path.join(root, path)):
                        reads.add(path)
        elif event == "pkinv.canonical.read":
            canonical.add(str(values[0]))
        elif event == "pkinv.asset.resolve":
            assets.add(str(values[0]))
        elif event == "pkinv.asset.catalog":
            whole_asset_catalog = True

    sys.addaudithook(audit)
    sys.argv = [args.target] + args.arguments
    complete = False
    try:
        if args.script:
            sys.path.insert(0, os.path.dirname(os.path.abspath(args.target)))
            runpy.run_path(args.target, run_name="__main__")
        else:
            runpy.run_module(args.target, run_name="__main__", alter_sys=True)
        complete = True
    except SystemExit as exc:
        complete = exc.code in (None, 0)
        if not complete:
            raise
    finally:
        active = False
        # Read-after-write products are internal to the task; its output identity
        # already protects them. Directory names record discovery, not member bytes.
        receipt = {"complete": complete, "reads": sorted(reads - writes),
                   "read_before_write": sorted(reads & writes),
                   "writes": sorted(p for p in writes if os.path.exists(os.path.join(root, p))),
                   "directories": sorted(directories), "external_commands": commands,
                   "canonical_tables": sorted(canonical), "assets": sorted(assets),
                   "whole_asset_catalog": whole_asset_catalog}
        with open(args.receipt, "w", encoding="utf-8") as handle:
            json.dump(receipt, handle)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
