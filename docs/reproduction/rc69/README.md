# Reproduction record for release 1.0.0rc69

Two reproductions of release 1.0.0rc69 were run in empty directories on 19 October 2026, on the
maintainer's machine (macOS, Python 3.11.10, the environment pinned in `requirements.lock`),
after the release record (commit `d93ddc7`). This folder publishes their results unchanged.
rc69 still carried the manuscripts; the logs therefore name their build phases, which rc70
removed.

## 1. Clean rebuild from the deposit's compiled inputs

`python3 scripts/clean_rebuild.py --work DIR --venv VENV`

The script copies the release's tracked inputs into an empty tree, installs nothing beyond the
pinned environment, and runs `python3 -m pkinv.build --group deposit --strict --quick`. It then
compares every product with the release using `tests/validation/compare_outputs.py`.

- **Level:** `compiled_inputs`. The engines were rebuilt from the verified source tables; the
  primary documents were NOT re-extracted (`source_extraction_repeated: false`).
- **Seeded phases:** the 15 phases that read primary documents or git history were not rebuilt;
  their verified products were seeded and checked against their release digests.
  `clean_rebuild_result.json` names each phase and what it reads.
- **Result:** build exit 0, comparison exit 0. Of the 470 compared files
  (`clean_rebuild_comparison.csv`):
  - 340 `rebuilt_identical`;
  - 118 `seeded`;
  - 11 `seeded_then_rewritten_identical`;
  - 1 `skipped_by_flag` (the manuscripts, which this run does not compile);
  - **0 differences**.

  The full build log is `clean_rebuild.log.txt`.

## 2. A reader's path: unpack the deposit and build it

1. `python3 scripts/unpack_deposit.py dist/pakemis-1.0.0rc69-release.zip DEST`. The four
   archives were built from commit `d93ddc7` (`RELEASE_SNAPSHOT.json`: working tree
   unmodified); the helper verified every checksum before restoring a file.
2. `python3 -m pkinv.activity.build` (`unpack_activity.log.txt`).
3. `python3 -m pkinv.build --group deposit --strict --quick --ledger logs/pakemis_run_ledger.json`
   (`unpack_build.log.txt`): exit 0, no `[FAIL]` or `[ERROR]` line.
4. `python3 tests/validation/compare_outputs.py` against the release (`unpack_compare.log.txt`).

**Result:** of the 400 compared files (`unpack_build_comparison.csv`):
- 289 `rebuilt_identical`;
- 110 `not_rebuilt`;
- 1 `skipped_by_flag`;
- **0 differences**.

The comparison exits 1 only because it counts `not_rebuilt` as a failure when no seeded receipt
names the file. The 110 are the held and source products a reader's build seeds, plus files the
strict build left unwritten because their inputs had not changed. All 110 were afterwards
compared byte for byte with the release and are identical (`unpack_not_rebuilt_check.csv`).

## 3. The archives' own checksums

Every file inside the four archives matches its archive's `SHA256SUMS`: data 879, documentation
308, ODbL companion 180, software 1,104 entries, 0 mismatches.

## What this does and does not establish

- **It does:** every numerical product of rc69 rebuilds byte for byte from the published
  compiled inputs, both in a copied tree and from the deposit a reader receives.
- **It does not:** re-extract any table from its primary document. The 15 seeded phases need
  documents the deposit lists by checksum and does not ship; `docs/deposit_rebuild_limits.md`
  lists them.

`test_run.json` is the rc69 canonical test record (4,112 executed, 0 failed, 20 skipped), byte
for byte as committed with that release.

The paths inside the logs and `clean_rebuild_result.json` (`/private/tmp/...`) are the temporary
directories the runs used on the maintainer's machine.
