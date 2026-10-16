"""Incremental developer builds from the same PHASES registry as strict reproduction.

Examples: python -m pkinv.build; python -m pkinv.build --target 'Semantic release'
          python -m pkinv.build --dry-run --explain; python -m pkinv.build --full --strict

Unaudited producers retain the original serial ordering and conservative source/upstream
dependencies. Observed IO improves receipts and missing-output checks without pretending
that a Python trace proves the behavior of native libraries or external programs.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fnmatch
import csv
import json
import hashlib
import os
import shlex
import subprocess
import sys
import tempfile
import time

from pkinv import run_all as registry
from pkinv.core import layers
from pkinv.build_support import (FileDigests, dump_atomic, file_identity, input_snapshot,
                                directory_identity, asset_bindings, physical_paths)


FINALIZATION = frozenset({
    "Paper artefacts (stored queries)", "Manuscript figures", "Dashboard",
    "Artifact inventory", "Product coverage", "Deposit manifest", "Product facts registry",
    "Claim matrix", "Release manifest", "Availability fragments", "Sync paper figures",
})
CI_EXCLUDED = frozenset({"Manuscript figures", "Dashboard", "Sync paper figures"})

# Native readers can bypass Python's file-open audit event. These explicit source
# boundaries supplement the exact canonical rows and Python reads in each receipt.
# Shared geospatial/raw caches are intentionally conservative until separately audited.
SECTOR_SOURCE_TREES = {
    "agriculture": ("Agriculture", "Provincial Statistics", "IPCC", "EMEP"),
    "waste": ("HydroWASTE", "Provincial Statistics", "IPCC", "EMEP"),
    "transport": ("Transport", "Punjab Transport", "OGRA", "Railways", "Aviation", "EMEP", "IPCC"),
    "power": ("Power Plants", "NEPRA HSE", "ClimateTRACE", "AP42", "OGRA", "Aviation", "IPCC", "UNFCCC"),
    "residential": ("HIES", "OGRA", "Aviation", "IPCC", "EMEP", "UNFCCC"),
    "industry": ("Industries", "AGP", "GEM", "OGRA", "IPCC", "EMEP"),
    "ippu": ("IPPU", "Industries", "GEM", "Aviation", "IPCC", "UNFCCC"),
    "fugitives": ("Fugitives", "OGRA", "AGP", "Aviation", "IPCC", "UNFCCC"),
    "railways": ("Railways", "Aviation", "ELK", "EMEP", "IPCC", "UNFCCC"),
    "aviation": ("Aviation", "IPCC", "EMEP", "UNFCCC"),
}


# The deposit reproduces from compiled source tables. These explicitly named
# phases need retained primary documents not shipped in the compact package;
# their verified compiled products are seeded and recorded separately.
DEPOSIT_SOURCE_PHASES = {
    "Power plant workbooks": "retained NEPRA primary spreadsheets",
    "OGRA gas-class series": "retained OGRA primary report",
    "Fiscal extension source tables": "retained official PDFs, XLSX and monthly source records",
    "Residential own-year degree-days": "retained NASA POWER monthly responses",
    "HTAP air comparison": "retained HTAP source workbook archive",
    "Power air-control evidence": "retained plant licence application PDFs",
    "UNSD industrial-combustion control": "retained UNSD energy-balance PDF",
    "UNSD coal supply control": "retained UNSD energy-balance PDF",
    "Forest flux adjudication": "retained FAOSTAT land-use forests bulk archive",
    "F-gas leak-rate adjudication": "retained UNFCCC CRT tables",
    "Lahore SO2 vs EDGAR gridmaps": "retained EDGAR v8.1 air-pollutant gridmap archives",
    "Provincial SO2 vs EDGAR gridmaps": "retained EDGAR v8.1 air-pollutant gridmap archives",
    "FAOSTAT nitrogen flows": "retained FAOSTAT bulk emissions archives",
    # rc68: these two read every published release's manifest out of git history, which a
    # deposit does not carry; in a fresh tree each earlier vintage came out "absent".
    "Published release vintages": "published release manifests read from git history",
    "Release axis fingerprints": "published release products read from git history",
}
DEPOSIT_EXCLUDED = tuple(DEPOSIT_SOURCE_PHASES)


def phases_for_group(group, phases=None):
    phases = registry.PHASES if phases is None else phases
    if group == "deposit":
        return [p for p in phases if p.label not in DEPOSIT_EXCLUDED]
    if group == "dev":
        return [p for p in phases if p.label not in FINALIZATION and not p.network]
    if group == "ci":
        return [p for p in phases if p.label not in CI_EXCLUDED]
    if group == "full":
        return list(phases)
    if group == "sectors":
        boundary = next(i for i, phase in enumerate(phases) if phase.label == "Completeness table")
        return list(phases[:boundary])
    if group == "ingest":
        return registry._with_asset_paths([
            registry.Phase("Official reporting extracts", "scripts/ingest_official_reporting.py",
                           True, writes=("data/extracted/unfccc/",), reads=("sources/",))])
    raise ValueError("unknown build group: " + group)


def _covers(declaration, path):
    return (path == declaration.rstrip("/") or
            declaration.endswith("/") and path.startswith(declaration))


def outputs_for(phase, cache):
    return set(phase.writes) | set(cache.get("phases", {}).get(phase.label, {}).get("writes", {}))


def dependencies(phases, cache):
    """Audit-backed edges, with a serial prefix for every unaudited producer.

    The prefix is deliberately conservative. A learned trace is not promoted into an
    audit, and an unknown writer is never assumed independent just to obtain parallelism.
    """
    result, owners, descendants, directory_owners = {}, {}, {}, []
    positions = {phase.label: index for index, phase in enumerate(phases)}
    for phase in phases:
        if phase.prints_only:
            continue
        for output in outputs_for(phase, cache):
            path = output.rstrip("/")
            owners.setdefault(path, set()).add(phase.label)
            if output.endswith("/"):
                directory_owners.append((output, phase.label))
            parent = os.path.dirname(path)
            while parent:
                descendants.setdefault(parent, set()).add(phase.label)
                parent = os.path.dirname(parent)

    def producers(read):
        if read.startswith("glob:"):
            return {owner for path, names in owners.items() if fnmatch.fnmatch(path, read[5:])
                    for owner in names}
        path = read.rstrip("/")
        found = set(owners.get(path, ()))
        found.update(owner for prefix, owner in directory_owners if read.startswith(prefix))
        if read.endswith("/"):
            found.update(descendants.get(path, ()))
        return found

    for index, phase in enumerate(phases):
        earlier = phases[:index]
        observed = cache.get("phases", {}).get(phase.label, {})
        reads = list(phase.reads or ()) + observed.get("observed_reads", [])
        directories = observed.get("directory_reads", [])
        explicit_prior = {p.split(":", 1)[1] for p in phase.reads or ()
                          if p.startswith(("prior:", "held:"))}
        # A cached artifact is not evidence that its writer ran before its reader.
        # Fail on concrete forward edges instead of silently accepting last run's data.
        deps = set()
        for read in reads:
            if read.startswith(("held:", "prior:", "glob:")) or read in explicit_prior:
                continue
            found = producers(read)
            found.discard(phase.label)
            for label in found:
                if positions[label] > index:
                    raise ValueError("%s reads %s before producer %s; fix task ordering" %
                                     (phase.label, read, label))
                deps.add(label)
        if not phase.audited and not observed.get("observation_complete"):
            result[phase.label] = {p.label for p in earlier}
            continue
        for read in reads:
            if read.startswith("glob:"):
                deps.update(label for label in producers(read) if positions[label] < index)
        for directory in directories:
            deps.update(label for label in descendants.get(directory.rstrip("/"), ())
                        if positions[label] < index)
        result[phase.label] = deps
    return result


def select(phases, targets, cache):
    graph = dependencies(phases, cache)
    if not targets:
        return list(phases), graph
    selected = set()
    for target in targets:
        matches = [p for p in phases if target in (p.label, p.target) or
                   any(_covers(w, target) for w in p.writes)]
        if not matches:
            raise ValueError("no task, label or product matches %r" % target)
        selected.update(p.label for p in matches)
    pending = list(selected)
    while pending:
        for label in graph[pending.pop()] - selected:
            selected.add(label)
            pending.append(label)
    return [p for p in phases if p.label in selected], graph


def sector_targets(phases, sectors):
    """Select every registered task owned by a sector, including independent peers."""
    prefixes = tuple("pkinv.sectors.%s." % name for name in sectors)
    return [phase.label for phase in phases if phase.target.startswith(prefixes)]


def _files(root, folder):
    base = os.path.join(root, folder)
    for directory, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in ("__pycache__", ".cache", ".git"))
        for name in sorted(names):
            yield os.path.relpath(os.path.join(directory, name), root)


def conservative_inputs(phase, phases, cache, inventory=None):
    """Held source boundaries supplement observed reads for an unaudited task.

    Data files owned by producers are taken at their graph position, never hashed as
    timeless sources. This keeps a late-generated registry out of an earlier task's
    source digest and prevents caches from depending on their own outputs.
    """
    if phase.audited:
        return []
    # A no-op invocation observes one file universe. Reuse directory enumeration
    # between tasks, then discard it whenever a producer may have changed it.
    inventory = {} if inventory is None else inventory
    def files(folder):
        key = ("files", folder)
        if key not in inventory:
            inventory[key] = tuple(_files(registry.ROOT, folder))
        return inventory[key]
    entry = cache.get("phases", {}).get(phase.label, {})
    parts = phase.target.split(".")
    if len(parts) > 3 and parts[:2] == ["pkinv", "sectors"]:
        sector = parts[2]
        folders = ["sources/" + name for name in SECTOR_SOURCE_TREES.get(sector, ())]
        folders += ["data/gis", "data/raw", "data/cache", "data/ml"]
        # Canonical CSV consumers are observed directly, including their source
        # hashes and column metadata. These native boundaries do not include other
        # sectors' staging/canonical CSVs or unrelated earlier products.
        result = {path for folder in folders for path in files(folder)}
        # Native inputs retain their complete registered bundles after a legacy
        # directory is split across sector/purpose folders.
        for asset in asset_bindings(registry.ROOT):
            if any(asset["legacy_path"].startswith(folder.rstrip("/") + "/")
                   for folder in folders):
                result.add(asset["path"])
        consumers = os.path.join(registry.ROOT, physical_paths("data/canonical_consumers.csv", registry.ROOT)[0])
        tables_path = os.path.join(registry.ROOT, physical_paths("data/canonical_tables.csv", registry.ROOT)[0])
        tables = {}
        if os.path.exists(tables_path):
            with open(tables_path, encoding="utf-8", newline="") as handle:
                tables = {row["table_id"]: row for row in csv.DictReader(handle)}
        observed = set(entry.get("canonical_tables", ()))
        if os.path.exists(consumers):
            with open(consumers, encoding="utf-8", newline="") as handle:
                for row in csv.DictReader(handle):
                    if row["sector"] == sector:
                        # Canonical access is fail-closed and emits IDs for reads
                        # and availability probes. Ancillary request/evidence
                        # tables omitted by the numerical task must not invalidate
                        # it solely because they share a sector directory.
                        if entry.get("observation_complete") and row["table_id"] not in observed:
                            continue
                        table = tables.get(row["table_id"])
                        result.update(physical_paths(row["source_path"], registry.ROOT))
                        if table:
                            result.add(table["path"])
        return sorted(result)
    generated = set()
    for p in phases:
        generated.update(outputs_for(p, cache))
    generated_files = {w.rstrip("/") for w in generated if not w.endswith("/")}
    generated_dirs = tuple(w for w in generated if w.endswith("/"))
    managed = set()
    if entry.get("observation_complete"):
        # Managed CSVs are read through the canonical boundary or captured by an
        # explicit Python open receipt. They are not opaque native dependencies.
        # Keep native files and undeclared data conservative; do not make every
        # national numerical report depend on every request packet in the tree.
        for asset in asset_bindings(registry.ROOT):
            if asset.get("canonical_path"):
                managed.update((asset["path"], asset["canonical_path"]))
            elif asset.get("purpose") in ("metadata", "requests", "catalog"):
                managed.add(asset["path"])
        managed.update(physical_paths("data/canonical_tables.csv", registry.ROOT))
        managed.update(physical_paths("data/canonical_columns.csv", registry.ROOT))
        managed.update(physical_paths("data/canonical/catalog.json", registry.ROOT))
        managed.update(physical_paths("data/download_catalog.json", registry.ROOT))
        managed.add("data/catalog/assets.csv")
    result = set()
    for folder in ("data", "sources"):
        for path in files(folder):
            if path not in generated_files and not path.startswith(generated_dirs) and path not in managed:
                result.add(path)
    # Scheduler barriers do not themselves create data dependencies. Actual
    # upstream products are declared or recorded by the IO receipt.
    own = outputs_for(phase, cache)
    return sorted(path for path in result if not any(_covers(w, path) for w in own))


def output_membership(phase, phases, cache, inventory=None, extra_owned=()):
    """Guard optional generated-file probes that Python open auditing cannot see.

    Membership is deliberately broader than content dependencies: adding or
    deleting a product can invalidate unrelated unaudited consumers once.
    """
    if phase.audited:
        return []
    inventory = {} if inventory is None else inventory
    if "generated_membership" not in inventory:
        # The discovery universe must not grow as secondary-write receipts arrive:
        # that would invalidate earlier tasks merely because a later task rewrote
        # an already-existing documentation file. Published products are covered by
        # outputs/ in full; other build destinations follow the shared registry.
        generated = {path for producer in phases for path in producer.writes}
        roots = {"outputs/"} | {path for path in generated if path.endswith("/")}
        paths = {path for path in generated if not path.endswith("/")}
        for rel in roots:
            for folder, dirs, names in os.walk(os.path.join(registry.ROOT, rel)):
                dirs[:] = [name for name in dirs if name != "__pycache__"]
                paths.update(os.path.relpath(os.path.join(folder, name), registry.ROOT)
                             for name in dirs + names)
        members = []
        for path in sorted(paths):
            absolute = os.path.join(registry.ROOT, path)
            if os.path.islink(absolute):
                members.append((path, "link", os.readlink(absolute)))
            elif os.path.isdir(absolute):
                members.append((path, "directory"))
            elif os.path.isfile(absolute):
                members.append((path, "file"))
        inventory["generated_membership"] = members
    own = outputs_for(phase, cache) | set(extra_owned)
    return [member for member in inventory["generated_membership"]
            if not any(_covers(path, member[0]) for path in own)]


def _conservative_identity(paths, membership=()):
    digest = hashlib.sha256()
    # Versioning forces a safe one-time refresh of receipts created before the
    # optional generated-file membership guard existed.
    digest.update(b"source-and-output-membership/v1")
    digest.update(json.dumps(membership, separators=(",", ":")).encode("utf-8"))
    for path in paths:
        digest.update(path.encode("utf-8"))
        digest.update(registry._sha(os.path.join(registry.ROOT, path)).encode("ascii"))
    return digest.hexdigest()


def reason(phase, cache):
    entry = cache.get("phases", {}).get(phase.label)
    if not entry or not entry.get("fingerprint"):
        return "no successful cached execution"
    if registry.is_current(phase, cache):
        return "inputs, command, environment and outputs unchanged"
    for path, digest in entry.get("writes", {}).items():
        if registry._sha(os.path.join(registry.ROOT, path)) != digest or digest == "MISSING":
            return "output missing or changed: " + path
    return "input, directory membership, command or environment changed"


def dry_run(phases, cache, *, registry_phases=None, full=False, strict=False, explain=False):
    """Use the same source membership and identities as execution, without writes."""
    original_sha = registry._sha
    digests, memo, inventory = FileDigests(registry.ROOT), {}, {}
    def digest(path):
        if path not in memo:
            memo[path] = digests.digest(path, original_sha)
        return memo[path]
    registry._sha = digest
    try:
        for phase in phases:
            entry = cache.get("phases", {}).get(phase.label)
            if entry and entry.get("observation_complete"):
                paths = conservative_inputs(phase, registry_phases or phases, cache, inventory)
                entry["conservative_reads"] = []
                entry["conservative_identity"] = _conservative_identity(
                    paths, output_membership(phase, registry_phases or phases, cache, inventory))
            state = "RUN" if full or strict else ("CACHED" if registry.is_current(phase, cache) else "RUN")
            if phase.prints_only:
                state = "VERIFY"
            print("%-6s %s%s" % (state, phase.label,
                  ": " + reason(phase, cache) + ("; conservative serial dependencies" if not phase.audited else "")
                  if explain else ""))
        print("%d tasks selected; dry run does not execute producers or update cache" % len(phases))
    finally:
        registry._sha = original_sha


def run_phase(phase, verified_outputs=None):
    """One isolated subprocess. Receipts are unique, including under parallel execution."""
    with tempfile.TemporaryDirectory(prefix="pakemis-task-") as scratch:
        receipt_path = os.path.join(scratch, "io.json")
        target = shlex.split(phase.target)
        command = [sys.executable, "-X", "importtime", "-m", "pkinv.build_trace",
                   "--root", registry.ROOT, "--receipt", receipt_path]
        if target[0].endswith(".py"):
            command += ["--script", os.path.join(registry.ROOT, target[0])]
        else:
            command += [target[0]]
        command += target[1:]
        environment = os.environ.copy()
        environment.pop("PKINV_BUILD_VERIFIED_OUTPUTS", None)
        if phase.target == "pkinv.report.validation_catalog" and verified_outputs is not None:
            proof_path = os.path.join(scratch, "verified.json")
            dump_atomic(proof_path, {"schema": "pkinv.verified_outputs/v1",
                                    "root": os.path.realpath(registry.ROOT),
                                    "outputs": verified_outputs})
            environment["PKINV_BUILD_VERIFIED_OUTPUTS"] = proof_path
        start = time.monotonic()
        proc = subprocess.run(command, cwd=registry.ROOT, capture_output=True, text=True,
                              env=environment)
        elapsed = time.monotonic() - start
        receipt = {"complete": False, "reads": [], "writes": [], "directories": []}
        if os.path.exists(receipt_path):
            with open(receipt_path, encoding="utf-8") as handle:
                receipt = json.load(handle)
        closure = registry._closure_from(proc.stderr, phase.target, registry._module_files())
        return proc.returncode, elapsed, proc.stdout, registry._strip_importtime(proc.stderr), closure, receipt


def _ownership_problems(phases, cache):
    problems = []
    for index, phase in enumerate(phases):
        if phase.prints_only:
            continue
        own = outputs_for(phase, cache)
        for other in phases[:index]:
            if other.prints_only:
                continue
            for left in own:
                for right in outputs_for(other, cache):
                    if _covers(left, right) or _covers(right, left):
                        problems.append((phase.label, other.label, left))
    return problems


def _ready_batch(pending, done, graph, jobs, cache):
    ready = [p for p in pending if graph[p.label] <= done]
    if not ready:
        raise ValueError("dependency cycle or missing task in selected build")
    # Retain original order for every unaudited task, independently of dependency
    # selection. Learned edges may prune a target's scope but never license races.
    first = pending[0]
    if first not in ready:
        raise ValueError("a selected task depends on a later producer")
    if not first.audited or first.prints_only:
        return [first]
    batch = []
    for phase in ready:
        if not phase.audited or phase.prints_only:
            break
        if not _ownership_problems(batch + [phase], cache):
            batch.append(phase)
        if len(batch) >= jobs:
            break
    return batch


def changed_during_task(phase, before, conservative, closure, receipt, cache, phases,
                        membership_before=()):
    """Never associate old products with inputs edited during their calculation."""
    owned = set(phase.writes)
    # Previous observations establish secondary product ownership, but never let
    # inferred writes to source data hide a source edit. A first-run native output
    # that is also an input must be explicitly declared by its producer.
    owned.update(path for path in outputs_for(phase, cache) if path.startswith("outputs/"))
    inputs = (set(conservative) | set(conservative_inputs(phase, phases, cache)) |
              set(receipt.get("reads", ())) | set(receipt.get("read_before_write", ())))
    for declaration in phase.reads or ():
        path = declaration.split(":", 1)[1] if declaration.startswith(("prior:", "held:")) else declaration
        if path.startswith("glob:"):
            inputs.update(p for p in before["files"] if fnmatch.fnmatch(p, path[5:]))
            inputs.update(p for p in registry._glob_universe() if fnmatch.fnmatch(p, path[5:]))
        elif path.endswith("/") or os.path.isdir(os.path.join(registry.ROOT, path)):
            prefix = path.rstrip("/") + "/"
            inputs.update(p for p in before["files"] if p.startswith(prefix))
            inputs.update(_files(registry.ROOT, path))
        else:
            inputs.add(path)
    inputs = {path for path in inputs if not any(_covers(output, path) for output in owned)}
    inputs.update(closure or ())
    changed = {path for path in inputs
               if before["files"].get(path) != file_identity(os.path.join(registry.ROOT, path))}
    def discovered(directory, members):
        if members is None:
            return None
        return [(name, kind) for name, kind in members
                if not any(_covers(output, os.path.normpath(os.path.join(directory, name))) or
                           output.startswith(os.path.normpath(os.path.join(directory, name)) + "/")
                           for output in owned)]
    for directory in receipt.get("directories", ()):
        old = discovered(directory, before["directories"].get(directory))
        new = discovered(directory, directory_identity(os.path.join(registry.ROOT, directory)))
        if old != new:
            changed.add(directory + "/ (membership)")
    # Compare the optional-product universe too: exists()/stat() probes are not
    # Python open events. Only actual Python writes may excuse new secondary
    # products here; a snapshot diff could instead be a concurrent user edit.
    actual_writes = set(receipt.get("writes", ())) | owned
    def product_members(members):
        return [member for member in members
                if not any(_covers(path, member[0]) or path.startswith(member[0] + "/")
                           for path in actual_writes)]
    membership_after = output_membership(phase, phases, cache)
    if product_members(membership_before) != product_members(membership_after):
        changed.add("generated products/ (membership)")
    return sorted(changed)


def execute(phases, graph, cache, *, full=False, strict=False, jobs=1, explain=False,
            ledger_path=None, registry_phases=None):
    root_phases = registry_phases or phases
    pending, done, records = list(phases), set(), []
    verified_outputs = {}
    started = time.monotonic()
    os.makedirs(os.path.join(registry.ROOT, "logs"), exist_ok=True)
    # Cache hashes within a single scheduling decision, never across producer writes.
    # Each no-op build still reads the content of every input at least once.
    original_sha = registry._sha
    file_digests = FileDigests(registry.ROOT)
    digest_cache = {}
    inventory = {}
    def digest(path):
        if path not in digest_cache:
            digest_cache[path] = file_digests.digest(path, original_sha)
        return digest_cache[path]
    registry._sha = digest

    def finish(code):
        ledger = {"schema": "pkinv.developer_build/v1", "exit_code": code,
                  "full": full, "strict": strict, "seconds": round(time.monotonic() - started, 3),
                  "phases": records,
                  "executed": sum(r["status"] == "OK" for r in records),
                  "cached": sum(r["status"] == "CACHED" for r in records)}
        if ledger_path:
            dump_atomic(ledger_path, ledger)
        print("Build: %d executed, %d cached, %.2fs" %
              (ledger["executed"], ledger["cached"], ledger["seconds"]))
        return code

    try:
        while pending:
            batch = _ready_batch(pending, done, graph, jobs, cache)
            running = []
            for phase in batch:
                entry = cache.get("phases", {}).get(phase.label)
                conservative = conservative_inputs(phase, root_phases, cache, inventory)
                # The current membership is part of the fingerprint, including newly
                # introduced source files. Do not reuse an old enumerated universe.
                if entry and entry.get("observation_complete"):
                    entry["conservative_reads"] = []
                    entry["conservative_identity"] = _conservative_identity(
                        conservative, output_membership(phase, root_phases, cache, inventory))
                current = not full and registry.is_current(phase, cache)
                why = reason(phase, cache) if explain else ""
                if phase.prints_only:
                    missing = [w for w in phase.writes if not os.path.exists(os.path.join(registry.ROOT, w))]
                    if missing:
                        records.append({"label": phase.label, "status": "FAIL", "missing": missing})
                        return finish(1)
                    # These outputs belong to the sector runner. Some historical
                    # prints_only commands actually rewrite them; do not invoke twice.
                    records.append({"label": phase.label, "status": "VERIFIED", "seconds": 0})
                elif current:
                    verified_outputs.update(entry.get("writes", {}))
                    print("CACHED %s%s" % (phase.label, ": " + why if why else ""))
                    records.append({"label": phase.label, "status": "CACHED", "seconds": 0})
                else:
                    print("RUN    %s%s" % (phase.label, ": " + why if why else ""), flush=True)
                    running.append((phase, conservative,
                                    output_membership(phase, root_phases, cache, inventory)))
                    continue
                pending.remove(phase)
                done.add(phase.label)
            if not running:
                continue
            # Snapshot ownership is reliable only in the serial lane. Audited
            # parallel tasks must already declare their complete outputs.
            before = registry._snapshot() if len(running) == 1 else {}
            source_before = input_snapshot(registry.ROOT)
            with ThreadPoolExecutor(max_workers=min(jobs, len(running))) as pool:
                results = list(pool.map(lambda phase: run_phase(phase, verified_outputs),
                                        [p for p, _, _ in running]))
            after = registry._snapshot() if len(running) == 1 else {}
            digest_cache.clear()
            inventory.clear()
            for (phase, conservative, membership_before), result in zip(running, results):
                code, seconds, stdout, stderr, closure, receipt = result
                unstable = changed_during_task(phase, source_before, conservative, closure, receipt,
                                               cache, root_phases, membership_before)
                if len(running) == 1:
                    receipt["writes"] = sorted(set(receipt.get("writes", [])) |
                                                set(registry._written(before, after)))
                missing = [w for w in phase.writes if not os.path.exists(os.path.join(registry.ROOT, w))]
                success = code == 0 and receipt.get("complete") and not missing and not unstable
                records.append({"label": phase.label, "target": phase.target,
                                "status": "OK" if success else "FAIL", "exit_code": code,
                                "seconds": round(seconds, 3), "writes": receipt.get("writes", []),
                                "missing": missing, "inputs_changed_during_task": unstable,
                                "stderr_tail": stderr.splitlines()[-10:]})
                if not success:
                    cache.setdefault("phases", {}).pop(phase.label, None)
                    registry.save_cache(cache)
                    print(stdout[-2000:])
                    print(stderr[-4000:], file=sys.stderr)
                    if missing:
                        print("Missing declared outputs: " + ", ".join(missing), file=sys.stderr)
                    if unstable:
                        print("Inputs changed while %s was running; rerun the build: %s" %
                              (phase.label, ", ".join(unstable)), file=sys.stderr)
                    return finish(1)
                if not full:
                    # Install the successful observation before choosing the next
                    # invocation's native supplement. Cold tasks start with broader
                    # CSV scopes; saving that bootstrap scope would force a needless
                    # second execution when the first warm run narrows it.
                    registry.record_current(phase, cache, closure, receipt)
                    learned = conservative_inputs(phase, root_phases, cache, inventory)
                    cache["phases"][phase.label]["conservative_identity"] = _conservative_identity(
                        learned, output_membership(phase, root_phases, cache, inventory))
                    cache["phases"][phase.label]["fingerprint"] = registry._fingerprint(phase, cache)
                    registry.save_cache(cache)
                for path in set(phase.writes) | set(receipt.get("writes", ())):
                    verified_outputs[path] = registry._sha(os.path.join(registry.ROOT, path))
                done.add(phase.label)
                pending.remove(phase)
        return finish(0)
    finally:
        registry._sha = original_sha
        file_digests.save()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--group", choices=("dev", "ci", "full", "ingest", "sectors", "deposit"), default="dev")
    parser.add_argument("--target", action="append", help="task label, command or product; includes prerequisites")
    parser.add_argument("--sector", action="append", choices=sorted(SECTOR_SOURCE_TREES),
                        help="all registered tasks for this sector, with prerequisites")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--explain", action="store_true")
    parser.add_argument("--full", action="store_true", help="bypass cache reuse")
    parser.add_argument("--strict", action="store_true", help="full strict reproduction via the canonical runner")
    parser.add_argument("--quick", action="store_true", help="exclude network tasks")
    parser.add_argument("--jobs", "-j", type=int, default=min(4, os.cpu_count() or 1),
                        help="parallel workers for explicitly audited tasks; others stay serial")
    parser.add_argument("--ledger", default=None)
    parser.add_argument("--seeded", default=None, help="verified seeded-product receipt for strict reproduction")
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if args.strict and (args.target or args.sector):
        parser.error("--strict cannot be combined with a partial --target or --sector")
    cache = registry.load_cache()
    group = "full" if args.strict and args.group == "dev" else args.group
    phases = phases_for_group(group)
    if args.quick:
        phases = [p for p in phases if not p.network]
    try:
        targets = list(args.target or ()) + sector_targets(phases, args.sector or ())
        selected, graph = select(phases, targets, cache)
    except ValueError as exc:
        parser.error(str(exc))
    if layers.mode(registry.ROOT) == "absent":
        # rc69: a public clone without the restricted layers. The phases that read primary
        # documents or the release history cannot run, and dropping them quietly would
        # publish their stale products as if rebuilt. The deposit group seeds them instead.
        needs = [p.label for p in selected if p.label in DEPOSIT_SOURCE_PHASES]
        if needs:
            parser.error("the restricted layers are not mounted here, and these tasks read "
                         "them: %s. Use --group deposit, or mount them with "
                         "python3 scripts/overlay.py link PATH" % "; ".join(needs))
    if args.dry_run:
        dry_run(selected, cache, registry_phases=registry.PHASES, full=args.full,
                strict=args.strict, explain=args.explain)
        return 0
    # A lock prevents two independent builds from interleaving live-tree writes and
    # publishing mutually inconsistent cache receipts. It is outside tracked state.
    import fcntl
    lock_path = os.path.join(registry.ROOT, "logs", "build.lock")
    os.makedirs(os.path.dirname(lock_path), exist_ok=True)
    with open(lock_path, "a", encoding="utf-8") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error("another build is writing this workspace")
        if args.strict:
            original = registry.PHASES
            try:
                registry.PHASES = selected
                legacy = ["--strict"]
                if args.quick:
                    legacy.append("--quick")
                if args.ledger:
                    legacy += ["--ledger", args.ledger]
                if args.seeded:
                    legacy += ["--seeded", args.seeded]
                return registry.main(legacy)
            finally:
                registry.PHASES = original
        return execute(selected, graph, cache, full=args.full, jobs=args.jobs,
                       explain=args.explain, ledger_path=args.ledger,
                       registry_phases=registry.PHASES)


if __name__ == "__main__":
    raise SystemExit(main())
