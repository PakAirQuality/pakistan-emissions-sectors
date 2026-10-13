"""Run the suite once and stamp what it actually did into outputs/pakemis_test_run.json.

WHY THIS EXISTS. Three shipped sites state how many tests this repository has, and the
number they state is the count of test FUNCTIONS defined under tests/ - checked against the
suite by the claims registry, so it cannot drift. It is not, however, the number a reader
sees when they run the suite. A class that skips in setUpClass is recorded as skipped
WITHOUT being counted as run, and whether it skips depends on what is staged in the
checkout: the spatial NH3 benchmark grid is not in every clone. So `Ran N` is smaller than
the published count and varies by machine, and a reader who compares the two has no way to
know which of the two numbers is wrong.

Both are true, and this file is where the second one is recorded: executed, passed, skipped,
failed, the names of anything that failed, on which Python and which platform.

RUN IT AFTER THE ARTIFACTS COMMIT, not inside the release fixpoint. Two release-integrity
tests compare the manifest and cover committed at HEAD against HEAD's content, and they
cannot pass until HEAD *is* the artifacts commit - so a record taken during the dance ships
a FAILED outcome that describes the dance rather than the release. Taken afterwards, it
describes the tree a reader will actually check out. Nothing is reopened by writing it late:
the manifest deliberately does not hash it.

NOT A HASHED PRODUCT. The suite tests the release manifest, so a manifest that hashed this
file would depend on a run that depends on the manifest. That is the same circle the paper
hashes fell into, one level down, and the resolution is the same: this is a product OF the
release dance, not an input to it, and release_manifest.PRODUCT_PATTERNS excludes it.

Usage:  python3 scripts/record_test_run.py [--quick]
Writes: outputs/pakemis_test_run.json
"""

from pkinv.assets import asset_path
import json
import os
import platform
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = asset_path(ROOT, "outputs", "pakemis_test_run.json")

RAN = re.compile(r"^Ran (\d+) tests in ([\d.]+)s", re.M)
OUTCOME = re.compile(r"^(OK|FAILED)(?:\s*\((.*)\))?\s*$", re.M)
FAILING = re.compile(r"^(?:FAIL|ERROR): (\S+) \((\S+?)\)", re.M)


def _counts(detail):
    """"failures=2, skipped=11" -> {"failures": 2, "skipped": 11}."""
    out = {}
    for part in (detail or "").split(","):
        if "=" in part:
            key, _, value = part.partition("=")
            out[key.strip()] = int(value.strip())
    return out


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    command = [sys.executable, "-m", "unittest", "discover", "tests"]
    print("-> %s" % " ".join(command))
    proc = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    # unittest writes its summary to stderr.
    text = proc.stderr + proc.stdout

    ran = RAN.search(text)
    outcome = OUTCOME.search(text)
    if not ran or not outcome:
        print("could not parse the suite summary; nothing written")
        print(text[-2000:])
        return 1

    total = int(ran.group(1))
    detail = _counts(outcome.group(2))
    failures = detail.get("failures", 0) + detail.get("errors", 0)
    record = {
        "schema": "pkinv.test_run/v1",
        "command": "python3 -m unittest discover tests",
        "executed": total,
        "passed": total - failures - detail.get("skipped", 0),
        "skipped": detail.get("skipped", 0),
        "failed": failures,
        "expected_failures": detail.get("expected failures", 0),
        "outcome": outcome.group(1),
        # NAMED, not just counted. A record that says "2 failed" and stops is a number a
        # reader can do nothing with; the names say whether the release shipped with a
        # broken sector or with two tests that cannot pass until the commit that follows
        # this run.
        "failing": sorted({"%s.%s" % (module, name)
                           for name, module in FAILING.findall(text)}),
        "seconds": float(ran.group(2)),
        "python": platform.python_version(),
        "platform": platform.platform(terse=True),
        # Said plainly on the artifact itself, because the two numbers WILL be compared.
        "note": ("`executed` counts what the runner ran on this machine and is lower than "
                 "the published count of defined test functions: classes that skip in "
                 "setUpClass are recorded as skipped without being counted as run, and "
                 "which ones skip depends on what is staged in the checkout."),
    }

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("wrote %s: %s, %d executed, %d passed, %d skipped, %d failed"
          % (os.path.relpath(OUT, ROOT), record["outcome"], record["executed"],
             record["passed"], record["skipped"], record["failed"]))
    for name in record["failing"]:
        print("   FAILING: %s" % name)
    # Non-zero on a failing suite, because by the time this runs the freeze is closed and
    # there is no structural reason for anything to fail. The record still gets written
    # first: a release that shipped with failures should say so on the artifact, not only
    # in a shell's exit status.
    return 0 if record["outcome"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
