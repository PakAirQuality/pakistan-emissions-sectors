"""Run the suite in parallel, one process per test MODULE.

WHY THIS EXISTS. The suite is 2,975 tests in 232 modules and takes about 616 seconds in one
process on a ten-core machine. Nothing about it is inherently serial except a short, nameable
list, so the everyday edit-and-check loop was paying ten minutes for work that fits in two.

WHAT IT IS NOT. It does not replace `python3 -m unittest discover -s tests` from the repo
root. That invocation stays canonical: scripts/record_test_run.py shells it and stamps the
result into outputs/pakemis_test_run.json, which is the published count, and
tests/test_parallel_runner.py holds this script to discovering exactly the same modules and
the same test ids. This is an accelerator for iteration, and a second opinion about order
dependence - a suite that only ever runs in one fixed order hides the state it leaks.

THE UNIT IS THE MODULE, NOT THE TEST. Five modules carry state across their own tests in
module globals (test_data_rederivation's SKIPPED is written by 26 tests and asserted by a
27th; also _POOLED, _PREBUILT, EXPECTED_ABSENT, _DECOMPOSITION), and ten monkeypatch
production module globals with finally-restores that are correct sequentially and not under
concurrency in one process. Keeping each module whole in one process preserves all of it.
Splitting by test would break them silently, which is the worst way to be fast.

Usage:
  python3 scripts/run_tests.py                 # the exclusive lane, then the rest
  python3 scripts/run_tests.py -j 4            # four workers
  python3 scripts/run_tests.py -k spatial      # only modules whose name contains "spatial"
  python3 scripts/run_tests.py --serial        # every module, one at a time, same reporting
  python3 scripts/run_tests.py --list          # the partition, and why each exclusive entry is
"""

from pkinv.assets import asset_path
import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TESTS = asset_path(ROOT, "tests")
TIMINGS = asset_path(ROOT, "logs", "test_timings.json")
# rc69: the tests a public clone WITHOUT the restricted layers skips, one test id per line.
# A skip with the layers prefix that is not listed here fails the run, and so does a listed
# test that no longer skips: the set is exact, so a guard cannot drift into skipping unseen.
GATED = asset_path(ROOT, "data", "catalog", "restricted_gated_tests.txt")
LAYERS_ABSENT = "restricted layers absent:"

# THE EXCLUSIVE LANE, with the reason beside each entry. A module belongs here only because
# running it BESIDE another module would be wrong - never because it is slow, and never
# because it looked risky. Each of these three writes a FIXED filename into the live
# repository tree, which any concurrent module that enumerates outputs/ or reads data/ would
# see; they run alone, one at a time, before the parallel lane opens.
#
# WHAT IS NOT HERE, AND WHY - because the first draft of this list was wrong in the cautious
# direction and cost about 150 seconds of the wall time it was written to save:
#
#   the git readers (test_holdings_discipline, test_raw_data, test_dev_snapshot,
#   test_grid_cube's three `git show HEAD:` calls, test_release_integrity) do
#   not need exclusivity. git readers do not take index.lock, and comparing the working tree
#   against HEAD is not a claim about what other processes are doing. They were quarantined
#   for "serialises on the object store", which is a performance guess, not a correctness
#   requirement - and an expensive one, since test_dev_snapshot zips the checkout twice.
#
#   test_data_rederivation spawns 26 subprocesses, and its 27th test asserts the SKIPPED dict
#   the other 26 wrote. That is INTRA-module state, and sharding by module preserves it by
#   construction. Its subprocesses run the producers with --check, which reads. At 91 seconds
#   it is the third-longest module in the suite and belongs in the parallel window.
#
# The same argument covers the ten modules that monkeypatch production module globals and the
# five that carry state in module globals: every one of those hazards is intra-module, and the
# unit of sharding is the module. That is the whole reason the unit is the module.
EXCLUSIVE = {
    # DO NOT SPELL THE PLANTED FILENAME HERE. scripts/audit_outputs.py greps every .py under
    # src/ and scripts/ for text naming an output, and treats a match as evidence that
    # something writes the file. A first draft of this reason quoted the name in full and the
    # self-test - which plants a name chosen to appear NOWHERE - stopped being able to fail.
    # That module's own docstring warns about it: a detector that names its examples
    # immunises them. It excludes itself; it cannot exclude this file.
    "test_outputs_audit":
        "plants a deliberately unregistered CSV in outputs/, runs the outputs audit over it "
        "to prove the orphan detector is not vacuous, and removes it; any concurrent module "
        "that enumerates outputs/ would see the planted file and report it as an orphan",
    "test_transcription_checks":
        "plants outputs/zz_transcription_selftest.csv on every _run(), and several test "
        "methods call _run() - two workers would collide on the fixed name",
    "test_pbs_qim":
        "re-runs scripts/ingest_pbs_qim.py, which REWRITES the committed panel under data/, "
        "then byte-compares it; every reader of that table would race the rewrite",
}


def discover_modules():
    """The module names `unittest discover -s tests` would import.

    A filesystem walk rather than a call to unittest's own discovery, because discovery
    IMPORTS every module it finds and this runs in the parent process, where the
    module-level side effects of 233 test modules have no business happening. It is the
    same rule discover applies - the `test*.py` pattern, recursing only into packages -
    and tests/test_parallel_runner.py holds the walk to discovery's actual answer, test id
    by test id, so the two cannot drift apart unnoticed.
    """
    found = []

    def walk(folder, prefix):
        for name in sorted(os.listdir(folder)):
            path = asset_path(folder, name)
            if name.startswith("test") and name.endswith(".py"):
                found.append(prefix + name[:-3])
            elif os.path.isdir(path) and os.path.exists(asset_path(path, "__init__.py")):
                walk(path, prefix + name + ".")

    walk(TESTS, "")
    return found


def _env():
    env = dict(os.environ)
    path = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = TESTS + (os.pathsep + path if path else "")
    return env


WORKER = r"""
import json, sys, time, unittest, io
module = sys.argv[1]
t0 = time.time()
buf = io.StringIO()
out = {"module": module, "ran": 0, "failures": [], "errors": [], "skipped": [],
       "expected_failures": 0, "unexpected_successes": []}
try:
    suite = unittest.defaultTestLoader.loadTestsFromName(module)
    if unittest.defaultTestLoader.errors:
        out["errors"].append([module, "\n".join(unittest.defaultTestLoader.errors)])
    result = unittest.TextTestRunner(stream=buf, verbosity=0).run(suite)
    out["ran"] = result.testsRun
    out["failures"] += [[str(t), tb] for t, tb in result.failures]
    out["errors"] += [[str(t), tb] for t, tb in result.errors]
    out["skipped"] = [[str(t), r] for t, r in result.skipped]
    out["expected_failures"] = len(result.expectedFailures)
    out["unexpected_successes"] = [str(t) for t in result.unexpectedSuccesses]
except BaseException as exc:
    import traceback
    out["errors"].append([module + " (collection)", traceback.format_exc()])
out["seconds"] = round(time.time() - t0, 2)
out["output"] = buf.getvalue()[-4000:]
sys.stdout.write("\n@@RESULT@@" + json.dumps(out))
"""


def run_module(module):
    proc = subprocess.run([sys.executable, "-c", WORKER, module],
                          cwd=ROOT, env=_env(), capture_output=True, text=True)
    marker = "@@RESULT@@"
    if marker in proc.stdout:
        payload = json.loads(proc.stdout.rsplit(marker, 1)[1])
        payload["stray_stdout"] = proc.stdout.rsplit(marker, 1)[0].strip()[-2000:]
        return payload
    # the worker died before it could report: a segfault, an os._exit, a hard import crash
    return {"module": module, "ran": 0, "failures": [], "skipped": [], "seconds": 0.0,
            "expected_failures": 0, "unexpected_successes": [], "output": "",
            "errors": [[module + " (worker died)",
                        "exit %d\nstdout:\n%s\nstderr:\n%s"
                        % (proc.returncode, proc.stdout[-2000:], proc.stderr[-2000:])]]}


def _timings():
    try:
        with open(TIMINGS, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {}


def _save_timings(results):
    known = _timings()
    known.update({r["module"]: r["seconds"] for r in results if r["seconds"]})
    os.makedirs(os.path.dirname(TIMINGS), exist_ok=True)
    with open(TIMINGS, "w", encoding="utf-8") as handle:
        json.dump(known, handle, indent=1, sort_keys=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("-j", "--jobs", type=int, default=os.cpu_count() or 4)
    ap.add_argument("-k", "--filter", default=None, help="substring of the module name")
    ap.add_argument("--serial", action="store_true", help="one module at a time")
    ap.add_argument("--list", action="store_true", help="print the partition and exit")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    modules = discover_modules()
    if args.filter:
        modules = [m for m in modules if args.filter in m]
    exclusive = [m for m in modules if m in EXCLUSIVE]
    parallel = [] if args.serial else [m for m in modules if m not in EXCLUSIVE]
    if args.serial:
        exclusive = modules

    if args.list:
        print("%d modules: %d parallel, %d exclusive\n"
              % (len(modules), len(parallel), len(exclusive)))
        for m in sorted(exclusive):
            print("  EXCLUSIVE  %-34s %s" % (m, EXCLUSIVE.get(m, "--serial was passed")))
        stale = sorted(set(EXCLUSIVE) - set(discover_modules()))
        if stale:
            print("\n  STALE exclusive entries naming no module: %s" % ", ".join(stale))
        return 0

    # longest first, from the previous run's timings: the tail of a parallel lane is set by
    # its slowest member, so a 50-second module started last costs 50 seconds of idle cores
    known = _timings()
    parallel.sort(key=lambda m: -known.get(m, 1.0))

    started = time.time()
    results = []
    # the exclusive lane first, and alone: it is three short modules, and putting it last
    # would add its whole duration to a wall time the parallel lane has already paid for
    if exclusive:
        print("-> %d modules alone (see EXCLUSIVE in scripts/run_tests.py for why)"
              % len(exclusive))
        for m in exclusive:
            r = run_module(m)
            results.append(r)
            _report(r)
    if parallel:
        print("-> %d modules on %d workers" % (len(parallel), args.jobs))
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            for r in pool.map(run_module, parallel):
                results.append(r)
                _report(r)

    _save_timings(results)
    gated = None if args.filter else restricted_skip_problems(results)
    return _summary(results, time.time() - started, gated)


def gated_tests():
    try:
        with open(GATED, encoding="utf-8") as handle:
            return {l.strip() for l in handle if l.strip() and not l.startswith("#")}
    except FileNotFoundError:
        return set()


def restricted_skip_problems(results, mode=None):
    """[(test, why)] for skips with the layers prefix that the mode does not allow.

    With the layers present (monorepo, overlay) there may be none at all. Without them the
    skipped set must equal data/catalog/restricted_gated_tests.txt exactly."""
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from pkinv.core import layers
    mode = mode or layers.mode(ROOT)
    skipped = {name for r in results for name, why in r["skipped"]
               if why.startswith(LAYERS_ABSENT)}
    if mode in ("monorepo", "overlay"):
        return [(name, "skipped for absent restricted layers while they are mounted")
                for name in sorted(skipped)]
    if mode != "absent":
        return []
    pinned = gated_tests()
    return ([(name, "skipped for absent restricted layers and not pinned in %s"
              % os.path.relpath(GATED, ROOT)) for name in sorted(skipped - pinned)]
            + [(name, "pinned as restricted-gated and did not skip")
               for name in sorted(pinned - skipped)])


def _report(r):
    bad = len(r["failures"]) + len(r["errors"])
    print("   %-6s %-46s %6.1fs  %4d tests%s"
          % ("BAD" if bad else "ok", r["module"], r["seconds"], r["ran"],
             "  %d failed or errored" % bad if bad else ""))


# THE TWO MARKERS ARE A CONTRACT, not formatting. scripts/gate_chain.sh counts them, and its
# head-baseline exclusion list may only ever apply to FAILURES: a test that cannot run at all
# is never "expected to fail before a content commit". An ERROR that got printed as [FAIL]
# would become excludable, and the gate would pass a suite that had not run. Renaming either
# marker without the gate silently makes every count zero, which reads as green - so
# tests/test_parallel_runner.py asserts the gate greps for exactly what this prints.
FAIL_MARKER = "[FAIL]"
ERROR_MARKER = "[ERROR]"


def _summary(results, wall, gated=None):
    ran = sum(r["ran"] for r in results)
    skipped = sum(len(r["skipped"]) for r in results)
    failures = [(r["module"], n, tb) for r in results for n, tb in r["failures"]]
    errors = [(r["module"], n, tb) for r in results for n, tb in r["errors"]]
    unexpected = [(r["module"], n) for r in results for n in r["unexpected_successes"]]
    print("\n%d modules, %d tests run, %d skipped, %d failed, %d errored, %.1fs wall"
          % (len(results), ran, skipped, len(failures), len(errors), wall))
    slow = sorted(results, key=lambda r: -r["seconds"])[:8]
    print("slowest: " + ", ".join("%s %.0fs" % (r["module"], r["seconds"]) for r in slow))
    for marker, rows in ((FAIL_MARKER, failures), (ERROR_MARKER, errors)):
        for module, name, tb in rows:
            print("\n%s %s :: %s\n%s" % (marker, module, name, tb.strip()[-1500:]))
    for module, name in unexpected:
        print("\n%s %s :: %s unexpectedly succeeded" % (FAIL_MARKER, module, name))
    restricted = sum(1 for r in results for _n, why in r["skipped"]
                     if why.startswith(LAYERS_ABSENT))
    release_time = sum(1 for r in results for _n, why in r["skipped"]
                       if why.startswith("release-time check:"))
    large = sum(1 for r in results for _n, why in r["skipped"]
                if why.startswith("large product not built:"))
    print("restricted-layer skips: %d; release-time skips: %d; large products not built: %d"
          % (restricted, release_time, large))
    for name, why in gated or ():
        print("\n%s restricted layers :: %s %s" % (FAIL_MARKER, name, why))
    return 1 if failures or errors or unexpected or gated else 0


if __name__ == "__main__":
    sys.exit(main())
