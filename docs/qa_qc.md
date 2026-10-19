# Integrated inventory QA/QC

This note describes the rc68 non-LULUCF greenhouse-gas and air-pollutant release.
Its common core is July 2015–June 2025; reference-year analyses and provisional
FY2025–26 sources retain distinct labels. Historical agricultural recalculations
remain in the preserved release evidence.

## Source and calculation checks

- PBS mineral controls compare the final exported province/month records with
  independently read source cells, national months and compatible annual totals.
  Grouped labels and duplicate-sheet regressions are tested. Missing provinces
  are not zero-filled, and twelve months alone do not establish national coverage.
- Station coal consumption, rank NCV and heat-weighted factors are reconciled with
  independent fuel and generation evidence. Receipts, stocks and heat-rate cases
  remain distinct. Unresolved non-power coal is not assigned silently to kilns.
- Nitrogen, residue and dung accounts conserve shared material. Activity/fate
  uncertainty regenerates the relevant pathways from a common state. The same
  leaked gas quantity is excluded from GHG and air combustion activity.
- Species retain native chemical conventions, factor units, controls and coverage.
  BC/OC and nested particulate fractions are checked at matched source boundaries;
  the query interface refuses sums across incompatible species.

## Product checks

For each supported configuration and fiscal year, monthly masses close to annual
estimates and placed plus unallocated mass closes to the compatible national or
administrative estimate. Tests retain masks, commissioning/closure periods,
fixed/substituted geography and evidence classes. Tolerances follow recorded
precision and aggregation; missing observations and scientifically material
discrepancies are not rounded away.

The four S/L × TAN/IPCC configurations are tested separately. Conditional
parameter percentiles, structural cases, unestimated sources and allocation
uncertainty are different products. Paired draws generate trend intervals.
Scenario extrema are not 95% bounds. Driver diagnostics are pollutant-specific;
correlations are not additive variance contributions.

Public query results are checked against the actual annual, spatial and
uncertainty records. Period/configuration mismatches and unsupported grains
receive typed refusals. Partial FY2026 activity cannot return a common-scope
national total. Product schema checks enforce units, keys, missingness and
vocabularies on the exported records.

## Evaluation and publication checks

Magnitude, historical change, timing and location comparisons use matched
species, units, periods and source boundaries. Shared activity statistics and
factors limit independence. Agreement with FAOSTAT does not choose a soil factor;
a difference from EDGAR is not automatically an estimate of a missing source.
Satellite concentrations or columns are not treated as direct local emission
measurements. No exposure or health ranking follows from emission totals alone.

Current figures include their plotted data and independent source-value checks.
The main article, longer report and affected sector notes are compiled and
visually inspected. Quantitative claims resolve to release products, with
historical examples explicitly separated from current estimates.

## Verification evidence

Run `PYTHONPATH=src:tests python3 -m unittest discover -s tests` from the repository
root. The executed count, skips, failures, environment and command belong in the
actual test receipt (`outputs/pakemis_test_run.json`), not a fixed count in this
note. A successful phase does not replace the final source/product checks.

The strict integration ledger and clean-rebuild result identify exactly what was
regenerated and compared. Primary-document re-extraction and regeneration from
compiled tables are separate levels. The retained-source checksum audit verifies
custody; it does not by itself validate a transcription or emission factor.
See [reproduction instructions](reproducibility.md), the repair register and the
current verification evidence for results and remaining limitations.
