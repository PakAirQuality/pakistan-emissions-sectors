# Development builds

`make dev` (also the default `make`) builds canonical activity inputs, scientific
products, and the semantic release. It reuses successful tasks whose inputs,
command, code, environment, and complete recorded outputs still match. Figures and
release manifests are separate from this everyday path.

```sh
make build-plan
make dev BUILD_ARGS='--explain --ledger logs/developer-build.json'
python3 -m pkinv.build --target 'Semantic release' --explain
make transport
make ingest
make release-check
```

## What each group builds

Every task in `pkinv.run_all.PHASES` declares one of four kinds in `run_all.CATEGORIES`:

- `science`: sources, engines, national, uncertainty, spatial.
- `validation`: comparisons, benchmarks and audits.
- `figures`: the inventory's figures (`outputs/figures/`) and the dashboard.
- `release`: inventories, manifests, deposit and provenance bookkeeping.

A task with no kind stops the registry from importing, so nothing joins a group by being
left off a list. Until rc68 `make dev` was "every task except eleven named ones", and the
figure stages added later ran in every development build.

| Group | Kinds | Make |
|---|---|---|
| `dev` | science, validation | `make dev` |
| `figures` | figures | `make figures` |
| `full` | all four | `make full`, `make release-check` |
| `deposit` | all but the 15 phases that read documents or history | public CI, the deposit reader |

`--target` accepts a task label, its module/script command, or an output path and
includes prerequisites. `--dry-run` explains the selected tasks without executing
producers or updating caches. A cold task with incomplete dependencies includes
the original preceding phases conservatively. Subsequent runs use file receipts
to narrow selection while preserving the original execution order.
`--sector transport` (also `make transport`) selects every registered transport
producer, including independent sibling tasks, before expanding prerequisites.
The legacy `run_all.py --changed` entry point forwards to the same scheduler with
the full task group; `--only` labels become dependency-closed targets. Its ledger
uses the developer schema and records reuse as `CACHED`. Combine neither
`--from` nor `--seeded` with that developer mode; strict/resume reproduction keeps
the original runner.

`make ingest` explicitly rebuilds official-reporting source extracts. Routine model
builds consume those extracts through the canonical CSV store. The ADM2 registry,
power admission register, kiln fleet observations, and power workbook inputs run
before the canonical snapshot because they produce some of its inputs.

`make release-check` and CI use full strict execution. They execute producers even
when the developer cache is current and retain the reproduction ledger. The
release-fixpoint command retains its existing release workflow.

## Cache integrity and concurrency

The task registry is `pkinv.run_all.PHASES`; Make and CI call it through
`pkinv.build`. Each developer subprocess records Python file reads, writes,
directory discovery, imported code, and exact canonical tables consumed. Catalog
metadata is fingerprinted per consumed table, so an unrelated table's updated
hash does not invalidate every sector. `data/catalog/canonical_consumers.csv` supplies
conservative additional per-sector canonical dependencies. Explicit source-tree
boundaries protect native readers that cannot be observed through Python hooks.
Other unaudited tasks retain broader source invalidation.
Generated-file names and types are also checked for unaudited tasks, covering
optional-file existence probes that Python's file-open audit cannot observe.
Adding or deleting a product can therefore rebuild more tasks than editing an
existing source; ordinary content edits keep their scoped dependencies. Receipts
from before this membership guard receive a one-time refresh.
A tree initially missing generated products can need a follow-up build to record
earlier tasks against the completed product membership.

Directory inputs and outputs include member names and content. Deleted or modified
outputs cause their producer to rerun. Failed executions remove the success record.
Cache files and timing ledgers live under ignored `logs/` and are written atomically.
If source/code identities or discovered input membership change while a producer
runs, the build stops and removes that task's success receipt. Rerunning then
calculates from the edited inputs instead of certifying old products against new
input hashes. Source changes found by a native-write snapshot are not treated as
producer-owned outputs.

The developer file-digest index uses device, inode, size, nanosecond modification
time, and nanosecond change time. It detects a same-size edit with restored mtime;
strict reproduction does not use this index. Delete `logs/build_cache.json` and
`logs/file_digests.json` to discard all developer cache state.

`--jobs` defaults to at most four workers. Only tasks with explicitly audited
complete inputs and exclusive output ownership may run together; observed IO alone
does not qualify a task for parallel execution. Unaudited producers stay serial.
A workspace lock prevents two builds from interleaving live output writes.

The validation catalog accepts an older product only when its producer was
successfully executed or its complete cache identity verified in the current
developer invocation, and the file still matches that verified content hash.
This proof is passed only to the catalog subprocess and then removed. Standalone
catalog checks and strict reproduction retain their existing age gate.
