# This repository is the public copy of PakEmis 1.0.0rc67

It holds the code, the verified data tables, the released products, the manuscripts and the
tests of release candidate 1.0.0rc67, as one commit. It was made on 13 October 2026 from
commit `3db0d658294dae1e6c760844df167daf7938fd65` of the project's working repository, which
is private. `outputs/release_manifest.json` names the commits of that repository; they do not
exist here, because this copy carries no history.

## What is not here, and why

The working repository also keeps every document the inventory was built from. Those are
other people's publications and data, and this project cannot grant a licence for them, so
they are left out:

| Left out | What it is |
|---|---|
| `sources/`, `data/raw/` | 6,193 primary documents: government reports and scans, company reports, statistical yearbooks, IPCC chapters, comparator datasets. The household survey microdata (PBS, HIES) is among them; PBS forbids redistribution of the record-level files. |
| `data/cache/` | Downloaded aircraft-position archives used by one pilot study. |
| `data/nfdc/`, `data/gleam/`, `data/gmw/`, `data/pbs_census/`, `data/district_records/` | 22 further third-party documents kept under older paths. |
| Thirteen raster files under `data/sectors/agriculture/gis/manual/` and `data/shared/gis/` | SPAM 2020 rice area (three files), GCD-Rice 2023, WorldPop 2020 and eight GHSL built-up tiles. Obtain them from their publishers; the `*SOURCES*` notes kept beside them give the addresses and versions. |
| `campaign/`, `.claude/` | Working notes and tool settings. |

Every document left out is listed with its SHA-256 in `data/catalog/raw_manifest.csv` and
`data/catalog/document_retention.csv`, and `data/catalog/cited_documents.csv` says which data
table cites which document. A reader who obtains a document can check it is the one used.

What IS here from those documents is what the project derived from them: the transcribed and
verified tables under `data/sectors/` and `data/shared/`, each row with its source citation.

## What this means for rebuilding

The sector engines and the national build read the verified tables, not the documents, and
run from this copy. A small number of build phases, checks and tests read the documents or
the rasters directly and will fail or skip here; `docs/deposit_rebuild_limits.md` lists them.
The published test record (`outputs/pakemis_test_run.json`: 3,861 executed, 0 failed) was
taken on the full working tree, not on this copy. Continuous integration is switched off on
this repository for the same reason.

## Where else to look

- The release itself, its checksums and its citation: `README.md`, `CITATION.cff`,
  `outputs/SHA256SUMS`, `outputs/release_manifest.json`.
- What changed in this release: `CHANGELOG.md`, section 1.0.0rc67.
- An interactive explorer of the dataset is at https://emissions.hawanama.org. It is deployed
  separately and can serve an earlier release candidate than this one; check the release it
  names before comparing its totals with the ones in this repository.

Code is under the MIT licence (`LICENSE`); data and text under CC BY 4.0 (`LICENSE-data`).
