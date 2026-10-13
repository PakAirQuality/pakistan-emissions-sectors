# The uncertainty contract

The question this document answers is *"what is the uncertainty on the figure I am looking
at"*, and the answer depends on which figure that is. There is no single number, and the one
that is easiest to find — the national annual interval, −10.4 %/+16.0 % — is the **narrowest**
statement this release makes. Borrowing it for a district in June would understate the bound
by roughly a third.

## Five kinds, kept apart

| kind | what it is | where it is measured |
|---|---|---|
| **parametric** | probabilistic. A 100,000-draw Monte Carlo over the activity data, conversions and emission factors, correlated within and across sectors — and, since rc18, joinable across products through the common draw ensemble (`outputs/mc_draws/pakemis_ensemble_*.parquet`, draw_id 0–9999, a bit-identical prefix of the published run) | `outputs/national_uncertainty_montecarlo.csv`, `outputs/pakemis_ensemble_summary.csv` |
| **profile (timing)** | two sub-kinds, split by `timing_basis`. A **measured hindcast dispersion** is probabilistic-adjacent and is *drawn* in the ensemble's monthly layer (weights renormalised inside every draw); a **structural variant** (power's constant fuel mix) is a disagreement between readings, carries no probability, and stays a conditional configuration | `benchmark_temporal_hindcast.csv`, `pakemis_power_profile_variant.csv` |
| **placement** | structural. How far a *sub-national* figure moves under a defensible alternative proxy; the ensemble carries each priced alternative as a conditional block over the same draw_ids | `pakemis_spatial_brackets.csv`, `pakemis_spatial_brackets_adm2.csv`, `pakemis_ensemble_spatial_conditionals.csv` |
| **structure** | discrete named configurations of the evidence — the 22 registered axes and their families. No probability, by schema-tested contract | `national_configurations.csv`, `national_axis_register.csv` |
| **completeness** | a BOUND on what is absent, beside the interval and never inside it: comparator-bounded absent mass per category (`completeness_bound_Mt` in the joint table), the screenings that interpret the 1A2 residual, and the national composed bound (1A2 residual + F-gases = the "outside the inventory" statement) | `pakemis_joint_uncertainty.csv`, `national_priority_rankings.csv` (coverage), `pakemis_coverage_matrix.csv` (the `screened` state) |

**They are not added into one σ.** A bracket is a disagreement between two readings of the
same evidence and carries no probability — `06_results.tex` has said so since rc13. Summing it
into a standard deviation would manufacture a distribution nobody measured. So
`outputs/pakemis_joint_uncertainty.csv` publishes the three separately with their epistemic
class on each row, and offers one combined number as an **envelope**: the probabilistic
interval widened by the structural half-widths. A bound, not a distribution, and the column
`envelope_kind` says exactly that.

## A bracket only bites on the figure it can move

Re-allocating a category across districts does not change its national total. Re-profiling it
across months does not change its annual one. So the table is keyed `(category, resolution)`:

| resolution | parametric | timing | placement |
|---|---|---|---|
| `annual_national` | ✓ | — | — |
| `monthly_national` | ✓ | ✓ | — |
| `annual_adm2` | ✓ | — | ✓ |
| `monthly_adm2` | ✓ | ✓ | ✓ |

Nationally, that reads:

| resolution | bound |
|---|---|
| `annual_national` | −10.38 % / +15.99 % |
| `monthly_national` | −12.61 % / +18.22 % |
| `annual_adm2` | −14.16 % / +19.77 % |
| `monthly_adm2` | −16.40 % / +22.01 % |

**These four are a lattice, not a chain.** `monthly_national` and `annual_adm2` are
incomparable: one adds a timing bracket and the other a placement one. Railways is the case
that proves it — timing priced at 3.5 % on a measured hindcast error, placement unpriced —
so its monthly national bound is legitimately wider than its annual district bound.

## The correlation rule, and it is directional

**Within** a category the parametric error is perfectly correlated: one emission factor moves
every district and every month of that category together. Intervals therefore add **linearly**
across districts and months, never in quadrature.

**Across** categories, do not add at all. The Monte Carlo measures the actual dependence and
publishes it at `aggregation_level=national`. Getting this backwards is not a theoretical
risk — the first cut of `joint_uncertainty.py` added the twenty category intervals linearly
and inflated the national bound to −22.0 %/+45.3 %. That is not a conservative reading of the
evidence; it is a different and wrong one, asserting that every sector's factors move together
when the correlation model explicitly denies it.

Both halves are proved by worked example in `tests/test_joint_uncertainty.py`, each with a
positive control, because a rule stated in a column is a rule nobody checks.

## No per-cell interval, on purpose

The ADM2 views and the cube carry **no** uncertainty column. A scaled copy of one of twenty
intervals repeated down 13,600 rows would read as twenty thousand independent errors and
invite exactly the quadrature that the rule above forbids. Both files carry a header comment
naming this table instead, and the NetCDF carries the same as a global attribute.

## What the envelope does not contain

Timing is priced for **3 of 20** categories, placement for **4 of 20**. Every row names its
unpriced components in `unpriced_components`, because an envelope that silently omitted them
would be narrower than the truth while reading as though it were wider.

Filling those cells with a weak alternative would make the bound look rigorous and be worse.
They close when a defensible second reading exists — the monthly requests in
`data/monthly_data_requests.csv` are what would close the timing ones.

**Unpriced is not the same as unexamined**, and `data/stream_spatial_alternatives.csv` records
which it is. Agriculture is the case that made the distinction necessary: it is 223 Mt, half
the inventory, and `outputs/eval/proxy_attribution.csv` prices three proxy changes at up to
2.3 Mt each, which reads like a ready-made bracket. It is not one. All three are **corrections
already applied**, and the readings they replaced are known worse rather than co-defensible —
applied manure rode `livestock_total`, which ignores that manure goes to fields. A bracket
between the current reading and a superseded one would make the bound look rigorous while
resting on a proxy nobody defends. The register carries that reasoning so the next reader does
not have to rediscover it, or act on it.

## Validation is a separate register and stays that way

`outputs/pakemis_validation_catalog.csv` records what has been compared against what, per module and
per property (magnitude, timing, geography), with an independence class on every row. An
uncertainty interval is not a validation: a wide bound that contains the truth and a narrow
one that does not are indistinguishable from inside the model. Every `(module, property)`
cell resolves to either a comparison or a **declared absence** with a reason, enforced by
`tests/test_joint_uncertainty.py` — the coverage-matrix discipline applied to validation, so
a new sector cannot arrive with no independent check and go unnoticed.
