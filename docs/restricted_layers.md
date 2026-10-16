# What this repository does not hold, and how the full build reads it

After release 1.0.0rc68 the inventory is developed in this public repository. It holds the
code, the verified data tables, the released products, the manuscripts and the tests.

Releases through 1.0.0rc68 were made in a private working repository. Commits 383f939
(rc67) and 3cef2f3 (rc68) here are whole-tree copies of those releases. The commits their
manifests name are in the private history, not this one.

## What is not here, and why

The inventory was built from some 6,300 primary documents. They are other people's
publications and data, and this project cannot grant a licence for them. They stay in a
private checkout, the **restricted layers**. `src/pkinv/core/layers.py` lists them, and
`.gitignore` ignores each name:

| Not here | What it is |
|---|---|
| `sources/`, `data/raw/` | Primary documents: government reports and scans, company reports, statistical yearbooks, IPCC chapters, comparator datasets. They include the household survey microdata (PBS, HIES), whose record-level files PBS does not allow to be redistributed. |
| `data/cache/` | Downloaded aircraft-position archives used by one pilot study. |
| `data/nfdc/`, `data/gleam/`, `data/gmw/`, `data/pbs_census/`, `data/district_records/` | More third-party documents, kept under older paths. |
| Thirteen rasters under `data/sectors/agriculture/gis/manual/` and `data/shared/gis/` | SPAM 2020 rice area (three files), GCD-Rice 2023, WorldPop 2020 and eight GHSL built-up tiles. Get them from their publishers; the `*SOURCES*` notes kept beside them give the addresses and versions. |
| Any `.sav`, `.dta`, `.por` or `.zsav` file | Survey microdata, wherever a future layout puts it. |
| `campaign/`, `research_campaign/`, `.claude/`, `CLAUDE.md` | Working notes and tool settings. |

This project's own products that exceed GitHub's 100 MB file limit are built here and
ignored. They are `outputs/pakemis_ghg_configuration_adm2_monthly.csv`,
`outputs/semantic/fact_adm1_month.csv` and `outputs/semantic/fact_adm2_month.csv`. They
ship in the archive deposit, and their checksums are in `outputs/SHA256SUMS`.

## How a missing document can still be checked

- `data/catalog/raw_manifest.csv` and `data/catalog/document_retention.csv` list every
  document with its SHA-256.
- `data/catalog/cited_documents.csv` says which data table cites which document.

A reader who obtains a document can check that it is the one used. What this repository
does hold from those documents is what the project derived from them: the transcribed and
verified tables under `data/sectors/` and `data/shared/`, each row citing its source.

## Licences

- Code: MIT (`LICENSE`).
- Project-created data and text: CC BY 4.0 (`LICENSE-data`).
- Files with Open Database License obligations: listed in `NOTICE-ODbL.md`. These are
  derived from OpenStreetMap or other ODbL databases, or are earlier releases and spatial
  products whose lineage was not cleared file by file. They are under the ODbL
  (`LICENSE-ODbL`), and the deposit packages them in its separate ODbL companion.

## Building with and without the restricted layers

`python3 -m pkinv.core.layers` decides the mode; `make layers` prints it.

- **Without them** (a fresh clone, and the public CI):
  - The engines read the verified tables, not the documents, so they run here.
  - The tests that need a document or the private history skip with the reason
    `restricted layers absent:`. That set is pinned in
    `data/catalog/restricted_gated_tests.txt`, and a run that skips anything else fails.
  - Build with `python3 -m pkinv.build --group deposit`. It reuses the published products of
    the fifteen phases that read documents or release history, which
    `docs/deposit_rebuild_limits.md` lists. It also reuses the products of every other
    phase that declares a restricted read (the ADM2 2022 frame reads the COD-AB
    boundaries) and of the whole `release` category: the deposit manifest, source register,
    release manifest, artifact inventory and facts registry describe the release with its
    documents, so built here they would describe a smaller tree. Those are checked where
    the layers are mounted (`make release-check`, `.github/workflows/reproduce.yml`). Any
    other group refuses to start rather than silently drop those phases.
- **With them** (the maintainer's full build):
  - Run `python3 scripts/overlay.py link /path/to/private/checkout` once. It records the
    path in the ignored file `.pkinv-overlay` and links each restricted name.
  - `python3 scripts/overlay.py check` confirms that every link resolves and no document is
    an unfetched Git LFS pointer.
  - Questions about the documents' git state (tracked, LFS, history) go to the repository
    that owns them.
  - The release manifest records both commits: `git` for this repository and
    `git.restricted_layers` for the private checkout.
  - A release requires zero `restricted layers absent:` skips.

Before every push, `python3 scripts/check_public_tree.py` fails on:
- a tracked restricted path;
- a file over the size limit;
- a restricted name that is not ignored;
- an out-of-date `NOTICE-ODbL.md`.

## Where else to look

- The release, its checksums and its citation: `README.md`, `CITATION.cff`,
  `outputs/SHA256SUMS`, `outputs/release_manifest.json`.
- What changed in each release: `CHANGELOG.md`.
- The interactive explorer, https://emissions.hawanama.org, a website of the Pakistan Air
  Quality Initiative (https://pakairquality.com). It is deployed separately and can serve an
  earlier release than this one.
