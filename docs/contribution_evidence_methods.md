# National conclusions and their evidence limits

The two `pakemis_contribution_*` tables consolidate existing public products into
ten claims. They do not estimate new emissions, fit an inventory to a comparator,
or count agreement as independent validation. The national and gas-application
engines remain the sources of their respective estimates.

Run from the repository root:

```bash
PYTHONPATH=src python3 -m pkinv.report.contribution_evidence
PYTHONPATH=src python3 -m pkinv.report.contribution_evidence --check
PYTHONPATH=src:tests python3 -m unittest test_contribution_evidence -v
```

The operation reads eleven small-to-moderate CSV products/registers and writes two
CSV tables. It does not require a GIS stack or a complete inventory rebuild.
`--root PATH` allows the same calculation on another complete source snapshot.
All required inputs must exist; absent inputs fail instead of silently narrowing
the set of comparisons.

## Claim table

`outputs/pakemis_contribution_claims.csv` provides questions, numerical results,
the comparison set, and the limits on admission and interpretation. Every row
identifies exact source products and their SHA-256 hashes. `source_selection`
describes the selected rows or aggregation; single-cell selections use the
repository's existing claim-pointer grammar. Aggregated selections are explanatory
and are not all executable pointer expressions.

The numerical columns are deliberately accompanied by `metric_definition` and
`unit`:

- The GHG decade row reports the reference deterministic change and the outer
  endpoints of eight separate paired parameter intervals (four configurations
  under two dependence assumptions). That outer range is **not** a pooled 95%
  confidence interval and does not include all structural uncertainty.
- Air trend ranges are deterministic endpoint changes across the four published
  configurations. Sector-leader ranges are shares of each case's largest covered
  sector; the identity of that sector can change. A tie is retained as a tie.
  The `(sector_id, category)` coverage must match across every compared
  configuration at the starting, ending and reference year. A dropped category
  fails the calculation instead of being interpreted as an emissions reduction.
- Structural coverage counts priced and refused axis/year questions. A priced
  axis is not necessarily an admissible alternative; legacy controls, diagnostics
  and coverage changes must not be combined as interchangeable possibilities.
- The coal seam row is an accounting decomposition of the latest annual change.
  Its signed ratio can be negative or exceed 100%. A zero national denominator
  yields an explicit undefined result. No consuming sector is assigned to the
  unresolved coal quantity by this calculation.
- Gas rows retain only evidence cases and full-scope mixed pathways plus LNG
  substitution in FY2023-24. Their complete case set is reconstructed from the
  public baseline, pathway and coherence registers; the admitted fertilizer
  baseline must be FA2. A missing case, incorrect year or diagnostic baseline
  fails even if the matrix and conclusion product agree with each other.
  A changed baseline admission register requires review of this bounded claim's
  scope. The territorial boundary retains one import route because the
  import route does not change domestic emissions. Shared inputs and repeated
  parameter axes mean case counts are not independent observations. Missing
  components that could reverse a negative estimate force an unresolved result.
  Counts and classification must agree with the existing gas conclusion product.

The four national configurations include a diagnostic allocation of all modelled
diverted dung to households. They are not four independent observed national
accounts. TAN/IPCC is a method choice. Invariance across the four configurations
therefore establishes a bounded conditional result, not robustness to all
reasonable evidence choices.

`supporting_catalogue_ids` link to relevant existing evaluation records. The
accompanying interpretation explicitly states whether the link is only a
contextual comparison. The synthesis does not promote those comparisons into
independent tests of the listed claims. The catalogue's `large` independence label
also does not, by itself, demonstrate an independent emissions measurement.

## Evidence summary

`outputs/pakemis_contribution_evidence_summary.csv` reuses the existing seven
validation groups, counts structural-axis statuses, and records each input
snapshot. Counts describe catalogue entries or registered questions; they are
neither emission-weighted validation coverage nor a probability that the
inventory is correct. The summary does not replace the more detailed catalogue.

## What remains empirical

The next evidence is attached to each claim. Shared historical reconstructions,
household end uses and technology factors, control histories, stock changes,
unestimated sources, exporter stages and actual power dispatch remain distinct
questions. Improving one does not automatically validate the other dimensions.
The published results concern covered emissions; they do not establish ambient
concentrations, exposure reductions or health impacts.
