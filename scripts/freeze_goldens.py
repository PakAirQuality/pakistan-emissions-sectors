#!/usr/bin/env python3
"""Freeze the golden receipts: run every golden against the built semantic release and write
its receipt into `expect_receipt`. Run once when a golden is added and again, deliberately, when
a release changes what a query returns - a diff in tests/semantic/golden/ is then the record.

    python3 scripts/freeze_goldens.py [--check]
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from pkinv.assets import asset_path

from semantic._golden import GOLDEN_DIR, check, load_goldens, open_engine, run  # noqa: E402


def main(argv):
    check_only = "--check" in argv
    engine = open_engine()
    changed = 0
    for name, golden in load_goldens():
        if golden.get("expect_error"):
            continue
        env = run(engine, golden)
        problems = [p for p in check(golden, env) if not p.startswith("receipt")]
        if problems:
            print("%s: NOT frozen - %s" % (name, "; ".join(problems)))
            return 1
        if golden.get("expect_receipt") != env["receipt"]:
            changed += 1
            print("%s: receipt %s -> %s" % (name, golden.get("expect_receipt") or "(none)", env["receipt"]))
            if not check_only:
                golden["expect_receipt"] = env["receipt"]
                with open(asset_path(GOLDEN_DIR, name), "w", encoding="utf-8") as handle:
                    json.dump(golden, handle, indent=1, sort_keys=True)
                    handle.write("\n")
    print("%d receipt(s) %s" % (changed, "would change" if check_only else "frozen"))
    return 1 if (check_only and changed) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
