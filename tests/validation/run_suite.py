"""Run the release suite exactly as the release ran it and record the result as data.

Usage: python3 tests/validation/run_suite.py <package root>

Runs `python3 -m unittest discover tests -v` with the package as the repository root, streams
the output to stdout (validate.sh tees it into logs/full_validation.log) and writes
logs/test_summary.json: executed, passed, failed, errors, skipped, the name of every failing
test and every skipped test with its reason. The exit code is the suite's own.
"""
import json
import os
import re
import subprocess
import sys
import time

RAN = re.compile(r"^Ran (\d+) tests? in ([0-9.]+)s", re.M)
OUTCOME = re.compile(r"^(OK|FAILED)(?: \((.*)\))?$", re.M)
FAILING = re.compile(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", re.M)
SKIPPED = re.compile(r"^(\S+) \(([^)]+)\)(?: \S+)? \.\.\. skipped '?(.*?)'?$", re.M)


def main(root):
    env = dict(os.environ)
    env["PKINV_ROOT"] = root
    env["PYTHONPATH"] = os.pathsep.join(p for p in (
        os.path.join(root, "src"), os.path.join(root, "tests"),
        os.path.join(root, "tests", "paper_numbers"), env.get("PYTHONPATH", "")) if p)
    start = time.time()
    proc = subprocess.run([sys.executable, "-m", "unittest", "discover", "tests", "-v"],
                          cwd=root, env=env, capture_output=True, text=True)
    text = proc.stdout + proc.stderr
    sys.stdout.write(text)
    ran = RAN.search(text)
    outcome = OUTCOME.findall(text)
    counts = {}
    if outcome:
        for part in (outcome[-1][1] or "").split(","):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=")
                counts[k.strip()] = int(v)
    executed = int(ran.group(1)) if ran else 0
    # Python 3.11 prints "FAIL: test_x (module.Class.test_x)"; 3.10 prints "(module.Class)"
    failing = sorted({m.group(3) if m.group(3).endswith("." + m.group(2)) else "%s.%s" % (m.group(3), m.group(2))
                      for m in FAILING.finditer(text)})
    skipped = sorted({"%s.%s: %s" % (m.group(2), m.group(1), m.group(3))
                      for m in SKIPPED.finditer(text)})
    summary = {
        "schema": "pakemis.validation_test_run/v1",
        "command": "python3 -m unittest discover tests -v",
        "executed": executed,
        "failures": counts.get("failures", 0),
        "errors": counts.get("errors", 0),
        "skipped": counts.get("skipped", 0),
        "expected_failures": counts.get("expected failures", 0),
        "passed": executed - counts.get("failures", 0) - counts.get("errors", 0)
                  - counts.get("skipped", 0),
        "outcome": outcome[-1][0] if outcome else "NO SUMMARY LINE",
        "exit_code": proc.returncode,
        "failing": failing,
        "skipped_tests": skipped,
        "seconds": round(time.time() - start, 1),
        "python": sys.version.split()[0],
        "platform": "%s %s" % (os.uname().sysname, os.uname().release),
    }
    os.makedirs(os.path.join(root, "logs"), exist_ok=True)
    with open(os.path.join(root, "logs", "test_summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("\nsummary -> logs/test_summary.json: %s, %d executed, %d failing, %d skipped"
          % (summary["outcome"], executed, len(failing), summary["skipped"]))
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")))
