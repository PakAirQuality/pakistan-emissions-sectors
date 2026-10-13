# Where the dung goes, and what the two readings actually measure

Stage 3 of the response to the twenty-second review (item 4). The review treated the gap
between the agricultural diversion and the household survey as a mass-balance problem. It is
not: the two sides do not measure the same quantity, and no plausible movement of the chain's
parameters closes a factor of 4.9. This file states what each side measures, what the residual
is, what would settle it, and why nothing is distributed.

> **Status at rc67 (13 October 2026).** This is the Stage 3 report as written, when
> configuration L was the reference and the pins were 469.64 and 464.51. Since rc67 the
> survey reading is the reference in every year, on the two-round interpolation (10.93 Mt in
> FY2023-24, not the 11.97 Mt below), and the dung with no household destination is an
> unresolved row beside the total, priced per year in
> `outputs/pakemis_dung_fate_by_year.csv`. The argument below is unchanged; the numbers are
> those of the release it was written for.

## The two numbers, and both reproduce

| | configuration L | configuration S |
|---|---|---|
| air-dry dung cake | **58.74144 Mt** | **11.96739 Mt** |
| residential total | 29.467 Mt CO₂e | 24.334 Mt CO₂e |

The residual is 46.77405 Mt — **79.63 per cent** of the L quantity. The difference in
residential emissions, 5.1328 Mt CO₂e, is exactly the gap between the two national pins
(469.63822 − 464.50543 = 5.13279), so the configurations table is arithmetically consistent
with the mass ledger. The energy side closes too: 542,579 TJ of difference against
46.774 Mt × 11.6 TJ/Gg = 542,578 TJ, one part in 500,000.

## The central mismatch is a boundary, not an error

**L** is all excreted nitrogen leaving manure management for fuel use — by any burner,
anywhere. Its chain is N 1.26018 Mt → VS 38.76935 → TS 51.69247 → air-dry 58.74144, under a
0.25 ash fraction and 0.12 moisture.

**S** is formed cake entering a sampled dwelling, by questionnaire construction: purchased,
own-produced, in-kind or gifted. Commercial tandoors, eateries and on-farm burning are inside
L and outside S by definition.

Three further scope differences run the **wrong** way — L covers only dairy cattle, other
cattle and buffalo, while the survey records "dung cake" with no species; L has an age
dimension the survey has none of; and L carries no fuel-preparation or handling loss term at
all. Closing any of them raises L.

## No parameter movement closes the gap

The ash fraction is the only free parameter that binds the L chain, and over its declared
15–35 per cent span L moves **51.83 to 67.78 Mt**. The gap is 46.77 Mt. A factor of 4.9 cannot
come out of this chain.

## What configuration L implies about households, which is the falsifiable statement

L is coherent *as a household quantity* only if either the user base or the intensity is about
4.9× what the survey observes: **72.6 per cent of Pakistani households burning cake at the
observed intensity** (29.0 of 39.9 million), or the observed **14.8 per cent burning
27.2 kg per household per day** against the observed 5.55. Neither is observed. The
falsifiable claim is therefore about the *assignment*, not about the mass.

## Nothing is distributed, and four destinations are priced beside the total

`outputs/national_dung_variants.csv` prices four alternative destinations for the residual and
**adopts none**: non-household combustion (+5.1328 Mt CO₂e, which reproduces L exactly under a
1.A.4.b → 1.A.4.a reclassification), return to manure management (+4.3882), field burning, and
a fourth unresolved end. Under S the residual is priced at zero in the headline — `ch4_Gg` and
`n2o_Gg` are both 0 on the unallocated row — which is a typed absence, not an assertion that
the mass vanished.

## What would settle it

A national dung-cake **prevalence** measurement plus a commercial-fuel survey. The two
instruments answer the two halves of the falsifiable statement above. Census 2023 cooking-fuel
tabulations are the obvious first instrument and the repository holds none: a holdings search
on the bare terms returns nothing. Survey-round movement is itself large — HIES 2018-19 gives
6.504 Mt against HIES 2024-25's 11.967, +84 per cent — and the survey total is concentrated,
with the top 1 per cent of reporting households holding 17.9 per cent of it, so the S side is
not a settled quantity either.

## One correction

Two engine docstrings state the L quantity as 58.69 Mt where the engine computes 58.74144 — a
pre-census-re-base value that survived the rc39 agriculture correction. It is 0.09 per cent and
has no numeric consequence, but it is a published-adjacent number disagreeing with its own
product. It is recorded here so that the correction is a change someone can check, rather than
a quiet edit.
