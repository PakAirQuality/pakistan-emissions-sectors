# Entry points

Everything below runs from the package root with `PKINV_ROOT` set to it (both shipped
scripts do this). `code/` is a reading copy of `src/` and `scripts/`; the runnable tree is
the package root itself, because the engine, the tests and the manuscripts resolve every
path from one root (`src/pkinv/paths.py`).

| command | what it does | writes |
|---|---|---|
| `./validate.sh --quick` | integrity, canonical input bootstrap, schemas, keys, identity, arithmetic closure | `logs/`, `data/canonical/` |
| `./validate.sh --full` | canonical input bootstrap and the complete release suite (`python3 -m unittest discover tests`) plus the package's own tests | `logs/`, `data/canonical/` |
| `./validate.sh --documents DIR` | the documents gate (rc42): the tests that re-read the source documents the package registers and does not carry, over an overlay whose `sources/`, `data/raw/`, `data/cache/` are the mounted vault's, verified against `data/raw_manifest.csv` first; exit 3 = not executed (no vault) | `logs/`, `data/canonical/` |
| `PYTHONPATH=src python3 -m pkinv.activity.build` | reconstructs readable canonical inputs offline from the deposited source/schema recipe; run before a direct model command | `data/canonical/` |
| `./reproduce.sh [--papers] [--keep] [--sources DIR]` | rebuilds every canonical output in a temporary copy and compares; `--sources DIR` mounts the vault's document trees into the copy | `logs/` only |
| `python3 run_all.py` / `python3 -m pkinv.run_all` | the whole build, every phase an isolated subprocess; `--quick` skips the one network phase; `--strict` makes any non-zero phase stop the run; `--ledger logs/x.json` records per phase what was written (`--seeded` names pre-seeded held products) | `outputs/` (run it in a copy, as reproduce.sh does) |
| `sh scripts/empty_outputs_rebuild.sh` | the reproduction from an empty outputs/ directory, runnable from a checkout without building a package | `logs/` only |
| `make sectors` / `make <sector>` | one sector runner (`agriculture`, `power`, `transport`, `railways`, `aviation`, `fugitives`, `ippu`, `industry`, `residential`, `waste`) | `outputs/` |
| `make national` | the cross-sector layer: rollup, atomic table, monthly panel, cube, uncertainty, completeness, ledgers, registries, release manifest | `outputs/` |
| `make papers` | the national paper and supplement and the nine sector reports (`latexmk`; CI uses `tectonic`) | `papers/pdf/`, `paper_national/CURRENT/*.pdf` |
| `python3 -m unittest discover tests` | the release suite as the release ran it | nothing |
| `python3 -m unittest discover tests -p test_<module>.py` | one module | nothing |
| `python3 scripts/check_transcriptions.py` | re-extracts every hand-typed cell in `data/transcription_checks.csv` from its document (needs `pdftotext` and the documents, most of which are not shipped - see `data/restricted_sources/`) | nothing |
| `python3 -m pkinv.report.release_manifest` | regenerates `outputs/release_manifest.json`; its `git` block describes whatever tree it runs in | `outputs/release_manifest.json` |
| `python3 scripts/build_product_columns.py --check` | re-derives the typed column registry (`data/product_columns.csv`: type, nullability, enum and foreign-key constraint per product column) from the shipped products and reports drift | nothing |
| `python3 scripts/build_validation_package.py` | rebuilds THIS package from a release checkout (the code that made it ships in `scripts/`) | `dist/` in the checkout |

Where each published result is computed:

| layer | modules |
|---|---|
| sector engines | `src/pkinv/sectors/<sector>/run_<sector>.py` and siblings |
| national aggregation | `src/pkinv/report/national_rollup.py`, `atomic_annual.py`, `annual_product.py`, `national_series.py` |
| monthly allocation | `src/pkinv/report/monthly_all_years.py`, `monthly_layer.py`, `temporal_profiles.py`, `monthly_coverage.py` |
| spatial dispatch | `src/pkinv/core/gis/cube.py`, `src/pkinv/report/grid_cube.py`, `spatial_decomposition.py`, `spatial_exceptions.py`, `spatial_brackets*.py`, `src/pkinv/core/adm2.py` |
| uncertainty | `src/pkinv/core/montecarlo.py`, `core/parameters.py`, `core/uncertainty.py`, `report/uncertainty_all.py`, `report/joint_uncertainty.py`, `report/variance_attribution.py` |
| common ensembles | `src/pkinv/report/common_ensemble.py` (`outputs/mc_draws/`) |
| source ingestion | `src/pkinv/sectors/*/ingest*.py`, `scripts/*ingest*.py`, `scripts/check_transcriptions.py`; the consumed derivatives (`data/consumed_derivatives.csv`) by `scripts/ingest_climatetrace_power.py`, `ingest_fugitives_observations.py`, `ingest_aviation_study_inputs.py` (`--check` needs the documents) |
| manuscript generation | `scripts/make_*.py`, `scripts/sync_figures.py`, `scripts/repair_claims.py`, `scripts/repair_tables.py`, `tests/paper_numbers/` |
| cross-sector ledgers | `src/pkinv/report/gas_closure.py`, `category_ledger.py`, `sectors/agriculture/residue_ledger.py`, `sectors/agriculture/n_ledger.py`, `sectors/residential/combustion.py` (dung), `sectors/transport/fuel_ledger.py`, `sectors/waste/ledger.py`, `sectors/ippu/urea_bridge.py` |

No published number is computed by a notebook or a script outside this tree; the build
definition is asserted to agree across `Makefile`, `run_all.py` and CI by
`tests/test_build_definition.py`.
