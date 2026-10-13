# The monthly lane: three products, one state machine

*Written for rc10 as the DESIGN the sixth review specified. Only the first product
and the seed of the second exist; the spec is committed so the lane grows into an
architecture instead of accreting.*

## The three products

| Product | Exists | Cadence | Contract |
|---|---|---|---|
| **Annual Final** | yes — the whole inventory | yearly, at each release | every number traces to a closed fiscal year's editions; fails loudly on any missing input |
| **Monthly Provisional** | seed only — `outputs/pakemis_monthly_controls.csv` | monthly, when new OCAC/aviation editions land | each stream-month carries its edition stamp, measurement basis, lifecycle status and `as_of`; values may be revised by later editions and the register says when |
| **Nowcast Beta** | no | monthly+ | model-extrapolated beyond the last edition; promoted only by beating the frozen benchmark baselines (`data/benchmark_tasks.csv`) |

The registered temporal benchmark is the lane's promotion rule: a nowcast that
cannot beat flat and last-year-shape on the frozen origins
(`outputs/benchmark_temporal_hindcast.csv`) has no claim to the third column.

## The record schema (seeded in the controls register)

One row per (stream, month): `stream, sector_row, products, month, tonnes, t_class,
measurement, status, as_of, source_file, source_sha256, revision_note`.

The provisional lane extends it with `ingested_at` (when this repository read the
edition) and `supersedes` (the sha256 of the edition a corrected row replaces) —
both already implicit in aviation's published vocabulary, whose `revision_note`
values ("direct monthly report", "July-only", "corrected November/April",
"final revised annual") are the observed state transitions the machine encodes.

## The state machine

```
provisional --(later edition revises the month)--> corrected --(FY closes)--> final
     \--------------------(FY closes without revision)---------------------/
superseded: any row replaced by a corrected one keeps its stamps and gains
            status=superseded; the register keeps both rows' hashes
```

Every fiscal year the panel currently holds is closed, so every seed row is
`final`. The machine activates with the first FY2025-26 edition.

## Stale-not-zero (answering `core/monthly.py`'s fail-loudly rule)

`core/monthly.normalise()` refuses an all-zero profile rather than inventing a
uniform one, and that is correct **for the Annual Final lane**: an annual product
built from a closed year has no excuse for a missing month, so absence is a defect
and must raise.

A provisional lane faces a different failure: the next edition is *late*, not
wrong. Raising would take the whole product down every month-end; substituting
zero would publish a real-looking collapse in fuel sales. So the provisional
contract is **stale-not-zero**: carry the last valid value forward, flag the row
`stale` with the `as_of` of the edition it actually came from, and NEVER let a
stale month enter a share normalisation silently — a consumer sees the flag or
sees a raise, no third state. The two rules are one principle at two cadences:
absence must be visible. The annual lane makes it visible by refusing to run;
the provisional lane makes it visible by labelling the substitution, because a
lane whose job is timeliness cannot express absence by stopping.

## What activates the lane

The first OCAC edition after the FY2024-25 close (expected via the same
wp-content endpoints the 48-month panel was fetched from). Ingest appends panel
rows with the new edition's hash; the controls register gains its first
`provisional` rows; the reconciliation test (`tests/test_monthly_controls.py`)
extends from closed-year identity to provisional-vs-revision tracking.
