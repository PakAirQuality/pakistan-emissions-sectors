"""Roll the step results of one validate.sh run into logs/quick_summary.json or logs/full_summary.json.

Usage: python3 tests/validation/summarise_logs.py <package root> --quick|--full

Reads logs/command_timings.csv (one row per step) and, for a quick run, the per-module
unittest tails inside logs/quick_validation.log. Writes a JSON record with every step, its exit
code and its duration, and a cross-reference against KNOWN_EXCEPTIONS.json: a failing step
whose test names are all declared there is `failed_declared`; one that is not is
`failed_undeclared`, which is the finding to report.
"""
import csv
import json
import os
import re
import sys

RAN = re.compile(r"Ran (\d+) tests? in ([0-9.]+)s")
FAILING = re.compile(r"^(FAIL|ERROR): (\S+) \(([^)]+)\)", re.M)
# rc42: a test that needs a document the package registers and does not carry skips with
# this reason (tests/_support.require_documents); the documents gate re-runs them over a vault
DOCUMENT_SKIP = re.compile(r"^(\S+) \(([^)]+)\)(?: \S+)? \.\.\. skipped '?document vault not mounted: ([^']*)'?$", re.M)


def main(root, mode):
    timings = os.path.join(root, "logs", "command_timings.csv")
    with open(timings, encoding="utf-8") as handle:
        steps = [r for r in csv.DictReader(handle) if r["mode"] == mode]
    # keep the LAST record of each step name for this mode
    latest = {}
    for r in steps:
        latest[r["step"]] = r
    declared = set()
    known = os.path.join(root, "KNOWN_EXCEPTIONS.json")
    if os.path.exists(known):
        with open(known, encoding="utf-8") as handle:
            for exc in json.load(handle).get("exceptions", []):
                for name in exc.get("tests", []):
                    declared.add(name)
    log_name = "quick_validation.log" if mode == "--quick" else "full_validation.log"
    with open(os.path.join(root, "logs", log_name), encoding="utf-8", errors="replace") as handle:
        log = handle.read()
    failing = sorted({"%s.%s" % (m.group(3), m.group(2)) for m in FAILING.finditer(log)})
    undeclared = [t for t in failing if t not in declared]
    for_documents = sorted({"%s.%s: %s" % (m.group(2), m.group(1), m.group(3)) for m in DOCUMENT_SKIP.finditer(log)})
    record = {
        "schema": "pakemis.validation_run/v1",
        "mode": mode,
        "steps": [{"step": k, "exit_code": int(v["exit_code"]), "seconds": int(v["seconds"]),
                   "command": v["command"]} for k, v in latest.items()],
        "steps_failed": [k for k, v in latest.items() if int(v["exit_code"]) != 0],
        "tests_failing": failing,
        "tests_failing_declared_in_known_exceptions": [t for t in failing if t in declared],
        "tests_failing_undeclared": undeclared,
        "tests_skipped_for_documents": for_documents,
        "tests_ran": sum(int(m.group(1)) for m in RAN.finditer(log)),
    }
    out = os.path.join(root, "logs", "%s_summary.json" % mode.strip("-"))
    with open(out, "w", encoding="utf-8") as handle:
        json.dump(record, handle, indent=2, sort_keys=True)
        handle.write("\n")
    print("summary -> logs/%s: %d steps, %d failed, %d tests ran, %d failing (%d undeclared), "
          "%d skipped for the document vault"
          % (os.path.basename(out), len(latest), len(record["steps_failed"]),
             record["tests_ran"], len(failing), len(undeclared), len(for_documents)))
    return 1 if undeclared else 0


if __name__ == "__main__":
    sys.exit(main(os.path.abspath(sys.argv[1]), sys.argv[2]))
