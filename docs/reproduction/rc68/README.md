# Reproduction record for release 1.0.0rc68

Two reproductions of release 1.0.0rc68 were run in empty directories on 16 October 2026,
on the maintainer's machine (macOS, Python 3.11.10, the environment pinned in
`requirements.lock`). This folder publishes their results unchanged: until rc69 they existed
only on that machine. Nothing here was re-run for publication.

## 1. Clean rebuild from the deposit's compiled inputs

`python3 scripts/clean_rebuild.py --work DIR --venv VENV`

The script copies the release's tracked inputs into an empty tree, installs nothing beyond
the pinned environment, and runs `python3 -m pkinv.build --group deposit --strict --quick`.
It then compares every product with the release using `tests/validation/compare_outputs.py`.

- **Commit:** content commit `541fe357`. The three commits after it, up to the release
  record `e09958ba`, changed only release bookkeeping: `outputs/SHA256SUMS`, the deposit
  manifest, the citation deposit audit, the paper hashes, the product facts registry, the
  test record, the release manifest, the cover and the compiled PDFs. No numerical product
  changed after `541fe357`; `git diff --stat 541fe357 6d8e8669 -- outputs` lists exactly
  those seven bookkeeping files.
- **Level:** `compiled_inputs`. The engines were rebuilt from the verified source tables.
  The primary documents were NOT re-extracted (`source_extraction_repeated: false`).
- **Seeded phases:** the 15 phases that read primary documents or git history were not
  rebuilt (13 primary-source phases and 2 release-history phases). Their verified products
  were seeded and checked against their release digests. `clean_rebuild_result.json` names
  each phase and what it reads.
- **Result:** build exit 0, comparison exit 0. Of the 465 compared files
  (`clean_rebuild_comparison.csv`):
  - 339 `rebuilt_identical`;
  - 118 `seeded`;
  - 7 `seeded_then_rewritten_identical`;
  - 1 `skipped_by_flag` (the manuscripts, which this run does not compile);
  - **0 differences**.

  The full build log is `clean_rebuild.log.txt`.

## 2. A reader's path: unpack the deposit and build it

1. `python3 scripts/unpack_deposit.py COLLECTION DEST`, on the four deposit archives built
   from commit `6d8e8669` (`RELEASE_SNAPSHOT.json`: `git_head` 6d8e8669, working tree
   unmodified). The helper verified the checksums and restored 2,414 files.
2. `python3 -m pkinv.activity.build` (`unpack_activity.log.txt`).
3. `python3 -m pkinv.build --group deposit --strict --quick` (`unpack_build.log.txt`).
4. `python3 tests/validation/compare_outputs.py` against the release (`unpack_compare.log.txt`).

**Result:** build exit 0. Of the 395 compared files (`unpack_build_comparison.csv`):
- 284 `rebuilt_identical`;
- 110 `not_rebuilt`;
- 1 `skipped_by_flag`;
- **0 differences**.

The comparison exits 1 only because it counts `not_rebuilt` as a failure when no seeded
receipt names the file. The 110 are the 50 held and source products a reader's build seeds,
plus 60 files the strict build left unwritten because its inputs had not changed. All 110
were afterwards compared byte for byte with the release commit and are identical
(`unpack_not_rebuilt_check.csv`).

## What this does and does not establish

- **It does:** every numerical product of rc68 rebuilds byte for byte from the published
  compiled inputs, both in a copied tree and from the deposit a reader receives.
- **It does not:** re-extract any table from its primary document. The 15 seeded phases need
  documents the deposit lists by checksum and does not ship; `docs/deposit_rebuild_limits.md`
  lists them. It also does not compile the manuscripts.
- These runs found sixteen packaging and bookkeeping defects in rc68 before it was minted,
  none of which moved a number; `CHANGELOG.md` (1.0.0rc68, "What the clean rebuild found")
  lists them.

`test_run.json` is the rc68 canonical test record (4,057 executed, 0 failed), byte for byte as
committed with that release (public commit 3cef2f3). It was added in rc69, when the measured-
validation table stopped reading the live record, which each release overwrites.

The paths inside the logs and `clean_rebuild_result.json` (`/private/tmp/...`) are the
temporary directories the runs used on the maintainer's machine.
