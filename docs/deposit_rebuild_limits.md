# What a deposit can and cannot rebuild

Measured on 2026-10-09 from the unpacked rc62 deposit: `pakemis-1.0.0rc62-software.zip` plus the data deposit's `pakemis-support/inputs/` as `data/` and its three product folders copied into `outputs/`, no `sources/` tree, every registered phase run as its own process in registry order (`campaign/v3_readiness/all_phases_from_deposit.json`). **156 of 195 phases run; 39 fail**, for five reasons:

## Primary documents under sources/ (not shipped) (3)
- Power plant workbooks
- OGRA gas-class series
- F-gas leak-rate adjudication

## Acquisitions under data/raw (not shipped) (4)
- UNSD industrial-combustion control
- Lahore SO2 vs EDGAR gridmaps
- Provincial SO2 vs EDGAR gridmaps
- FAOSTAT nitrogen flows

## Gitignored GIS bundles (agriculture proxy and SPAM water-regime rasters) (8)
- Agriculture
- Agriculture districts
- Spatial brackets (ADM2)
- Gridded monthly cube
- Nine-year spatial products (ADM1 and ADM2)
- Air spatial (all sectors)
- Rice geography crosscheck
- Forest flux adjudication

## Build-tier intermediates the deposit excludes by rule (read by later phases) (18)
- National rollup
- Named national configurations
- National axis register
- Derivation chains
- District rice records validation
- District records validation (multi)
- Agriculture district panel (1990-2024)
- Agri reference-panel divergence
- Priority rankings
- Coverage matrix (year x category x gas x configuration)
- Benchmark: spatial allocation
- Joint uncertainty by resolution
- Completeness-mass ledger
- Structural trajectories
- Semantic release
- Industrial boundary ledger
- Product facts registry
- Product catalog

## Manuscript tree (needs the documentation deposit's sources) (5)
- Paper artefacts (stored queries)
- Manuscript figures
- Gridded figures
- Product coverage
- Claim matrix

## Artefact of the test harness (staleness sentinel after seeding outputs/) (1)
- Validation catalog + scorecard

## What this means

- Every sector engine except Agriculture runs from the deposit. Agriculture needs the SPAM water-regime rasters and the cropland proxy raster, which are gitignored GIS bundles the deposit does not carry; without them the national rollup, the named configurations, the axis register and the semantic release cannot be regenerated from the deposit, because they read Agriculture's outputs and the build-tier intermediates the deposit excludes by rule.
- The `deposit` build group (`python3 -m pkinv.build --group deposit`) skips the two phases whose only missing input is a primary document under `sources/` and takes their shipped products as given. It is necessary and not sufficient: `make full`-equivalence from the deposit also needs (a) the agriculture GIS bundle, (b) the build-tier intermediates that later phases read - `agriculture_water_regime_2024.csv`, `district_totals_2024.csv`, `transport_class_parameters_2024.csv`, `transport_class_fuel_weights_2024.csv`, `aviation_aircraft_ledger_fy2023_24.csv`, `aviation_model_resolution_fy2023_24.csv`, `ippu_hfc_species_bank.csv` - either shipped or regenerated, and (c) the four `data/raw` acquisitions the comparison phases read. The manuscript phases belong to the documentation deposit.
- A sector whose engine reads only compiled inputs rebuilds at runner level today (`python3 -m pkinv.activity.build`, then the runner; observed for waste: 72 rows, closes exactly).

Evidence: `campaign/v3_readiness/all_phases_from_deposit.json`, `deposit_failure_classes.json`, `phases_without_sources_test.json`, `phases_reading_sources.json`.
