# Quality Assurance / Quality Control and Recalculation Note

Companion to the inventory engine. Documents the QA/QC procedures actually enforced (IPCC 2006
Guidelines Vol 1 Ch 6), the verification against independent datasets, the recalculation history,
and how the Key Category Analysis directs future effort.

**Scope: the agriculture and AFOLU sector**, for FY2023-24 under the IPCC 2006 Guidelines with
the 2019 Refinement. This note predates the other nine sectors and is still written for one of
them; the figures below — the benchmark ratios, the uncertainty bands, the key categories, the
recalculation log — are agriculture-scoped and should not be read as national. It is kept
because agriculture is half the inventory and this is the only place its recalculation history
is written down.

**The national equivalents are generated, not written here**: `outputs/national_key_categories.csv`
for the key-category screen over all ten sectors, `outputs/national_uncertainty_montecarlo.csv`
and `outputs/pakemis_uncertainty_drivers.csv` for uncertainty, `outputs/completeness.csv` for
notation keys, and `docs/reproducibility.md` for what the build asserts about itself.

---

## 1. QC — general (Tier 1) checks

These are automated as unit tests (`tests/`, **3882 defined test functions across ten sectors**,
`python3 -m unittest discover tests`) and/or asserted on every pipeline run, so a regression fails
loudly rather than silently. The count is not decorative: it is checked against the suite itself,
because this line said 521 and seven sectors for several releases after both had stopped being
true.

**Defined is not executed.** That number counts the test functions in `tests/`. The number a
runner reports as `Ran` is lower and machine-dependent: a class that skips in `setUpClass` -- the
spatial NH3 benchmark grid is not staged in every checkout -- is recorded as skipped without
being counted as run. What the release run actually executed, passed, skipped and failed is
stamped in `outputs/pakemis_test_run.json` by the release fixpoint, so the two numbers can be
compared instead of confused.

| IPCC QC activity (Vol 1 Table 6.1) | How it is enforced here |
|---|---|
| Emission factors & parameters traceable to a source | Every value lives in `data/*.csv` with a `source` column; no magic numbers in code. `test_inventory` asserts each EF used is the CSV value. |
| Activity data transcription correct | `data/sectors/*/activity/*.csv` carry source + uncertainty columns; hand-calculated IPCC worked examples reproduced in `test_inventory` (e.g. buffalo enteric 47.7 M head x 55 kg = 2623.5 Gg CH4). |
| Units correct and consistent | Molecular conversions (N2O-N->N2O 44/28, C->CO2 44/12) applied once per module; GWP applied once in `gwp.py`; `test_inventory` checks GWP constants (AR5 CH4 28, N2O 265). |
| No double counting | Shared nitrogen budget across manure/soils: dung-cake N -> Energy (IE), pasture N -> soils FPRP, burned residue excluded from FCR. Documented in `docs/methods_note.md`; completeness keys in `docs/completeness.md`. |
| Internal consistency of methods | Indirect-volatilisation N2O uses the **same explicit dry EF4** in manure and soils (harmonised — see §4). |
| Totals reconcile across scales | National = Sum(provinces) = Sum(grid cells) asserted in `downscale.py`, `run_gis.py`, `test_downscale`, `test_gis` (to 1e-6 / 1e-3 Mt). |
| Completeness | Every AFOLU category x gas carries an IPCC notation key (E/NE/NO/IE/NA) in `docs/completeness.md`; `completeness.py` fails if any engine category is not marked estimated. |
| Time-series consistency | One method, activity-driven back-cast 1990-2024 (`timeseries.py`); the 2024 point equals the standalone run (`test_timeseries`). |
| Sign / range sanity | No negative agriculture emissions; national total in a plausible band; enteric is the largest category (`test_inventory`). |

## 2. QA — independent verification

Independent-of-the-compiler checks against datasets the engine does not use as inputs:

- **FAOSTAT Emissions Totals** (Pakistan, 2023) and **EDGAR 2024** — per-category and total, with a
  0.5-2.0x pass gate: `outputs/national_benchmark_comparison.csv`. Total 0.95x FAOSTAT, 0.83x EDGAR.
- **Year-by-year vs FAOSTAT** (1990-2023), same activity data so divergence isolates EF choices:
  `outputs/timeseries_validation.csv`. Enteric tracks at ~0.99x.
- **LULUCF forest** validated against FAOSTAT Forestland (`test_lulucf`, within 0.5-2.0x of -3.5 Mt).
- **Two uncertainty methods agree** — analytical Approach 1 (+/-19%) vs Monte-Carlo Approach 2
  (+/-16%), cross-checked per category in `outputs/uncertainty_montecarlo.csv` and `test_montecarlo`.

The one deliberate, documented divergence is managed soils vs FAOSTAT (0.49x): methodological, not
an error — the engine uses 2019 disaggregated dry EFs (EF1 0.005) vs FAOSTAT's 2006 aggregate
(0.010); an EF1 sensitivity pass brackets it (28 -> 40 Mt). See `docs/tier2_changelog.md`.

## 3. Uncertainty and key categories

- Approach 1 (analytical error propagation, `uncertainty.py`) on every component; Approach 2
  (lognormal Monte-Carlo, mean-preserving, `montecarlo.py`): 10,000 seeded iterations for
  sector-scoped runs, 100,000 for the published national run.
- **Key Category Analysis** (`key_categories.py`, IPCC Approach 1, `outputs/key_categories.csv`):
  the key categories by level and/or trend are **enteric fermentation, managed soils, manure
  management, rice cultivation**. These carry >95% of the inventory and its trend, and coincide with
  the widest Monte-Carlo bands (rice, soils) — so they are the priority targets for Tier-2/3 emission
  factors and better activity data.

## 4. Recalculation log

Recalculations follow IPCC time-series-consistency guidance: whenever a method or factor changes,
the **entire 1990-2024 series is regenerated** with the new basis, so no discontinuity is introduced.

| Date / phase | Change | Effect on national total |
|---|---|---|
| Phase 5 (Tier 1 -> Tier 2) | Country-specific dairy share (0.295), animal weights (TAM), MMS shares, rice period, residue-return fractions, 2019 dry soil EFs (EF1 0.005, EF1FR 0.004 for rice N). | 223.1 -> 217.0 Mt (per `tier2_changelog.md`); subsequent activity-data updates -> 222 Mt. |
| Finalisation | **EF4 harmonisation**: manure indirect-volatilisation N2O switched from a dry/wet climate-blended EF4 (0.0059) to the **explicit dry EF4 (0.005)**, matching the managed-soils treatment (Pakistan predominantly arid). Removes an internal method inconsistency. | Manure 21.24 -> 20.97 Mt; national 221.99 -> **221.71 Mt** (rounds to 222); AFOLU 218.0 -> 217.7 (rounds to 218). Headlines unchanged. |
| Finalisation | Documentation consistency: precise tier framing ("Tier 1 methods with Tier 2 country-specific data/parameters"), stale-figure corrections, CRT manure AD relabelled "head incl. poultry". | None (no emissions change). |

The now-unused `climate_dry_fraction` / `climate_wet_fraction` parameters and `EF4_wet` factor are
retained in `data/` for the documented sensitivity context but are no longer referenced by the engine.

## 5. Reproducibility

**Every printed number is a registered claim.** `tests/paper_numbers/doc_claims.py` holds
one entry per number a manuscript prints - a regex anchoring it in its section and a getter
that recomputes it from the engine's outputs - and the suite fails when the two disagree by
more than an absolute tolerance plus half an ulp at the printed precision. When a re-base
moves the engine, `python3 scripts/repair_claims.py` rewrites every disagreeing printed
value to the getter's value at the printed decimals (never the other way round: the
manuscripts follow the engine, not the assertions); its bare prose twins are then named by
`tests/paper_numbers/test_quantity_coverage.py`.

**The data layer has its own audit (rc37).** The build never reads raw documents - the
scripts under `scripts/ingest_*`, `fetch_*` and `build_*` do, into the committed CSVs under
`data/` - so byte-identical regeneration of `outputs/` says nothing about whether an activity
file still follows from the document it was typed from. Four instruments hold that layer:
`python3 scripts/audit_data.py` (`pkinv.report.data_provenance`, a build phase) classes every
git-tracked data product as produced by a named script, hand-made with its document held,
derived, hand-made with no held source and the gap that says so, a root parameter table, or a
provenance sidecar, and `tests/test_data_provenance_audit.py` asserts nothing is unregistered
and freezes by name the products nothing reads; `tests/test_data_rederivation.py` re-runs every
producer that ships a `--check` and fails on a byte that differs; `data/transcription_checks.csv`
records hand-typed cells re-read from their documents (by `pdftotext`, OCR, or a person) and
`python3 scripts/check_transcriptions.py` re-extracts the automatable rows under the same
half-ulp rule the claims use; and `outputs/pakemis_validation_sector_scorecard.csv` projects the
validation catalog onto (module x property), so "is this sector validated?" is a row rather
than a search. A re-derivation or transcription that disagrees is a finding for a person -
nothing rewrites a committed data file.


- Core inventory runs on the **Python standard library alone** (`python3 run_all.py --quick`); the
  gridding/charts use the optional stack in `requirements.txt`.
- Single source of truth: all numbers in `data/*.csv`; each sector declares its own category list
  through `core.registry`, and that declaration propagates to the provincial, gridded,
  time-series, key-category, monthly and completeness outputs.
- Deterministic: Monte-Carlo is seeded (SEED=42); `run_all.py` sequences every phase and writes a
  self-contained `outputs/dashboard.html`.
- Version-controlled; CI smoke test runs the suite.

## 6. Extraction provenance and its uncertainty (rc20)

Every raw acquisition in `data/catalog/manifests/source_manifest.csv` carries an
`extraction_method` from a closed vocabulary: `text_native`, `ocr_identity_gated`,
`manual_transcription_gated`, `spreadsheet`, `chart_read`.

**The pricing rule.** Identity-gated reads are exact by construction: the read is
accepted only when the table's own arithmetic closes over it (row sums, block
sums, cross-document controls — `scripts/ocr_ogra_2020_21.py` and
`sectors/transport/ocac_image_edition.py` are the two implementations), and a
read that fails any identity is rejected, never adjusted. A gated cell therefore
carries the same downstream uncertainty as a text-native cell, and no separate
extraction term is added — adding one would price an error mode the gate has
already excluded. Extraction uncertainty is priced **only** where no closing
identity gates the read; the one such case in the inventory is the FY2021 captive
chart read, priced inside `captive_activity_uncert` (12%, with the chart read
named in the parameter note).
