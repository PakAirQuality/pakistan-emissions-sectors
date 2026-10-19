# Pass 2 baseline — the frozen rc21 scorecard

**This file is a SNAPSHOT, deliberately not regenerated.** It records the state of the
science at the Pass-2 baseline so every later scorecard has a fixed comparator. The
baseline is release `1.0.0rc21`, fixpoint triple `5f150b2` (content) → `3d5dfe9`
(artifacts) → `2d012f7` (record), suite 2121 executed / 0 failed. The tag for this
commit is created by the maintainer, not by the build.

Prompted by the sixteenth review (August 2026), whose Pass-2 program this baseline
opens: evidence acquisition → annual scope decisions → monthly reconstruction →
spatial allocation → joint uncertainty → science freeze → journal conversion.
Restructuring the published description is deferred until the science freeze.

## The four measurable Pass-2 outcomes

1. Complete or explicitly bound the material annual-scope gaps (countable floor
   ≈ 47 Mt CO₂e: industrial combustion 1A2 ≈ 29 Mt, F-gas benchmark 11.54 Mt,
   non-cement IPPU, industrial wastewater).
2. Reduce genuinely time-variable-but-unobserved monthly mass from 22.71% to ≤ ~15%
   (≈ 34 Mt must move to observed, defensible proxy, or genuinely continuous/
   stock-driven — the target is eliminating avoidable flat allocation, never
   "zero TE4").
3. Replace proxy placement for major facilities with activity-resolved native
   locations or an explicit unallocated layer.
4. Propagate common uncertainty draws through every supported annual × monthly ×
   spatial × structural configuration.

## Baseline numbers (rc21, from the shipped outputs)

Annual: reference FY2023-24 total 447.71688 Mt CO₂e AR5 (L), 442.59021 (S);
nine-year panel FY2015-16..FY2023-24 complete at 90 sector-years, all E,
372.39 → 447.72 Mt; national interval ±13.18% (−10.4/+16.0 about the median).

Temporal, reference year (share of national mass): T1 0.94 / T2 27.19 / T3 18.44 /
**T4 53.42**. Nine-year monthly product (3733.266 Mt over 108 months): observed
(decomposition sense, incl. TE3-timed) 33.84%; **variable-but-unobserved 22.71%**
(the Pass-2 metric); flatness-appropriate 43.4%; strict TE1+TE2 16.72%, TE4 64.14%.
(rc21 figures, frozen with the rest of this file. The live TE4 share is the coverage
summary's; since rc42 `outputs/pakemis_flatness_crosswalk.csv` is joined at the same
month-row grain and its grain_difference row reads zero.)

Spatial, reference year: S1 0.07% / S2 1.33% / **S3 96.59%** / unallocated-at-ADM1
2.01% (closure is raster + unallocated, `pakemis_spatial_unallocated.csv`).

Completeness: 88 category-gas combinations — E 41 · NE 36 · IE 7 · NO 4.

Power (the rc21 headline): sector T4 96.96% → 8.79%; grid coal TE2 and gas TE3 for
FY2022-23/FY2023-24 via the SIR listing lane; FY2021-22 gas refused at 94.0% bound.

## The eight non-negotiable rules

1. This baseline is frozen; Pass-2 work branches from it (`pakemis-pass2-2026-08`).
2. Monthly and spatial transformations preserve their annual controls exactly.
3. Every new annual category begins OUTSIDE the reference total.
4. Raw source objects are immutable and content-hashed.
5. Revised sources supersede earlier versions (supersedes_document_id); nothing is
   deleted.
6. Missing values are typed; they are never silently changed to zero.
7. Unallocated mass is publishable and preferable to forced allocation.
8. Structural alternatives remain separate configurations and are never averaged.

Status vocabulary for scope work: `NE`, `screening`, `configuration`, `reference`,
`not_applicable`, `unsupported`, `not_implemented`. Named configurations:
`reference_v1`, `reference_plus_1A2_screening`, `reference_plus_fgas_screening`,
`expanded_public_data_scope`.

## The validation ladder every work package climbs

L0 raw file hashed with URL/publisher/revision · L1 parser reproduces printed source
totals · L2 independent annual controls reconciled before normalization · L3
overlapping sources compared, discrepancies published · L4 exact annual/monthly/
spatial/accounting closure · L5 perturbation and positive-control tests · L6
external comparisons diagnostic only, never silent calibration.
