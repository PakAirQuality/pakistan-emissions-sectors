<!-- This log describes the 1.0.0rc29 clean-room rebuild (the last one run). Its
     filename is version-free since rc36: the release it describes is stated here
     and in the JSON, not in the name. -->
# The rc29 clean-room rebuild log

**Verdict: PASS_WITH_NOTE** — the rebuild reproduced every committed data output byte-for-byte in an empty environment, offline - figures included; the only differences are the two declared artifact classes (the in-place national PDF, and the manifest's describes_commit block with zero substantive lines)

Run by `scripts/clean_room_full.sh`: a fresh `file://` clone of the release content commit, a fresh virtualenv from `requirements.lock`, an unroutable proxy exported so any network attempt fails loudly, the full offline build, the full test suite, the PDF build, and a byte comparison against the committed outputs. The machine-readable record is `docs/rebuild_log.json`, beside this page and outside the product tree it describes.

## Environment

- **git**: git version 2.49.0
- **git_lfs**: git-lfs/3.7.0
- **latexmk**: Latexmk, John Collins, 27 Dec. 2024. Version 4.86a
- **offline_proxy**: http(s)_proxy=http://127.0.0.1:9 exported for build and tests
- **os**: Darwin 24.6.0 (arm64)
- **python**: 3.11.10 (fresh venv from requirements.lock, 32 pins)

## Steps

| step | status | detail |
|---|---|---|
| clone | OK | file:// transport, 2f4a997f, 7355 tracked files |
| lfs_materialise | OK | 19 objects copied from the invoking repository (no remote holds them until the branch is pushed) |
| lfs_preflight | OK | no tracked file is an unsmudged LFS pointer |
| venv | OK | Python 3.11.10 + requirements.lock (32 pins) |
| offline_proof | OK | unroutable proxy exported; any network attempt in build or tests fails loudly |
| run_all | OK | every offline phase (the full product set; the one declared NETWORK phase is the only skip); log: /private/tmp/claude-501/-Users-rehanahmad-Desktop-emissions/500c4ae4-3141-4e4b-a076-4fd9fa3fe064/scratchpad/cleanroom/run_all.log |
| pdfs | OK | make papers succeeded; 16 PDFs built; combined sha256 0cd0f81bfc3b91b1ba55ab8c6b0fefe7715a97d5091870cb013408de9b570cbe (declared non-byte-stable: embedded CreationDate) |
| tests | OK | Ran 2192 tests in 325.081s, all green, inside the clone, offline |
| comparison | OK | every committed data output reproduced byte-for-byte, the shipped figures included; the only differences are the two declared artifact classes - the in-place national PDF the build rewrites, and the manifest describes_commit block (zero substantive lines) - the first filter missed the national PDF and the corrected exclusion mirrors release_fixpoint.py ARTIFACT_PATTERNS exactly |
| sabotage_check | OK | a deliberate one-line mutation of data/months.csv in the finished clone is detected by the comparison (and the first two runs were organic gate-bites: the LFS pointer preflight caught its own materialisation defect, and the clone suite caught a stale committed deposit manifest) |

## The reacquisition sweep (2026-08-23)

| dataset | outcome |
|---|---|
| OurAirports airports.csv (re-verification) | fetched |
| PIA privatisation investment teaser | fetched |
| Fatima Fertilizer annual report 2024 (PSX document 250354) | discovery_failed |
| CDM nitric-acid project pages (TUEV-SUED1155134039.49, RWTUV1322686352.38) | blocked |
| UNEP Ozone Secretariat Pakistan profile | fetched |
| UN Comtrade clinker (HS 2523, reporter 586) | fetched |
| World Bank WDI rail indicators | fetched |
| NASA POWER monthly T2M | fetched |
| FAOSTAT QCL normalized bulk | fetched |
| Zenodo brick-kiln record 14718244 Main.csv | fetched |
| HydroWASTE_v10.zip (figshare 31910714) | fetched |
| GEM cement tracker July 2026 xlsx | not_attempted |
| PIA fleet page | discovery_failed |
| PBS 7th Agricultural Census 2024 tables | discovery_failed |
| State Bank Statistical Supplement FY2023-24 | discovery_failed |

Full per-attempt detail, with URLs, lives in `data/acquisition_attempts.csv`; the per-source metadata contract is `data/not_retained_register.csv`.

## Unresolved failures, each typed

- **papers/pdf/*.pdf** — declared non-byte-stable: LaTeX embeds a CreationDate; the run records build success and hashes, and outputs/pakemis_paper_hashes.csv is the sidecar a holder verifies against
- **outputs/pakemis_grid_0p05_monthly.nc** — declared byte-churn: the NetCDF byte stream varies per code path while its content is deterministic (docs/spatial_products_contract.md); the conservation gates test content, not bytes
- **git-lfs objects (19, ~3 GB, 7 manifest-hashed source documents)** — no remote holds them until the branch is pushed (user-only action), so a stranger's clone cannot yet materialise them; this run copied them from the local object store and asserted no pointer survived
- **reacquisition:Fatima Fertilizer annual report 2024 (PSX document 250354)** — discovery_failed - rc29 sweep: the recorded direct URL now serves the PSX portal SPA shell, not the PDF - document IDs appear to have churned
- **reacquisition:CDM nitric-acid project pages (TUEV-SUED1155134039.49, RWTUV1322686352.38)** — blocked - rc29 sweep: both project pages answer with an Incapsula bot challenge (212 bytes) to unattended clients; the pages remain public to browsers
- **reacquisition:PIA fleet page** — discovery_failed - rc29 sweep: the server answers unattended clients with an empty body (0 bytes, twice, with and without TLS verification)
- **reacquisition:PBS 7th Agricultural Census 2024 tables** — discovery_failed - rc29 sweep: pbs.gov.pk root serves (398 KB) but the census content path returns an empty body unauthenticated; no stable document URL discovered
- **reacquisition:State Bank Statistical Supplement FY2023-24** — discovery_failed - rc29 sweep: the ecodata page serves a 5 KB shell; the supplement PDF path was not discoverable unauthenticated
