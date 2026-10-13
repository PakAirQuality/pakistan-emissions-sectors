# T-BIO-1 and T-BIO-2 — dung balance, and the effluent N2O factor

Read-and-tabulate only; pins unmoved. Detail: `dung_balance.csv`, `wastewater_n2o.csv`.

## T-BIO-1 — the dung balance

Both numbers reproduce exactly: 58.74144 and 11.96739 Mt air-dry cake, residual
46.77405 Mt (79.63%). The L chain closes per species (N 1.26018 Mt → VS 38.76935 → TS
51.69247 → air-dry); the configurations' energy difference, 542,579 TJ, equals 46.774
Mt × 11.6 TJ/Gg; L − S = 5.1328 Mt CO2e is exactly the gap between the two pins.

**The two sides are not measuring the same quantity.** L is all excreted nitrogen
leaving manure management for fuel use, by any burner anywhere; S is formed cake
entering a sampled dwelling. Commercial tandoors, eateries and on-farm burning sit
inside L's definition and outside S's frame. Three further mismatches run the *wrong*
way: L covers only cattle and buffalo while S is species-agnostic; the implied cake
nitrogen is 3.25% of VS, high in the published range; and no preparation, collection
or spoilage loss exists anywhere in the chain. Closing any of the three raises L. The
moisture conversion (0.12) is symmetric across both sides — no basis error. Ash (0.25)
binds only L; over its declared 15–35% span L moves 51.8–67.8 Mt, so it cannot produce
a factor of 4.9.

Against S: HIES 2024-25 is one fiscal year after the reference period (about −8%); and
the two-round corroboration the module claims for firewood does **not** extend to dung
— 6.504 Mt in 2018-19 against 11.967, all of that growth per-user intensity while
prevalence fell. Design SE 6.61%, top-5% of households 44.7%.

The falsifiable statement concerns the *assignment*, not the mass: L as a household
quantity needs either 72.6% of households burning cake at the observed 5.55 kg/day, or
the observed 14.79% burning 27.2 kg/day. **What would settle it is a national
prevalence measurement of dung-cake cooking fuel plus a commercial-sector fuel
survey**; Census 2023's cooking-fuel distribution is the first instrument and
`holdings.py "cooking fuel"` reports nothing held. No residual was distributed and none
should be: the engine already prices four destinations beside the S total (3.41–5.13 Mt
CO2e) and adopts none. Defect: `combustion.py:147` and `dung_ledger.py:4` say 58.69 Mt
where the engine computes 58.74144.

## T-BIO-2 — the effluent N2O factor

`waste:ww_ef_effluent`, 0.005 kg N2O-N per kg N, IPCC 2006 Table 6.11. Units and gas
identity are clean (44/28 applied separately; 11.44732 Gg N2O booked before AR5 265).
Denominator: the protein-derived nitrogen of the whole population, 1,456,932 t N —
*generated* nitrogen, with **no discharge-pathway split** and no N_SLUDGE term, where
the CH4 side splits five pathways. Faithful to 2006 Tier 1; the pathway scope is a
flagged **hypothesis** (a strict aquatic-discharge denominator is roughly 29% of the
population, about −3.4× on the N2O row), unverifiable here and in no gap row.

I reproduced the engine's RNG streams **bit-exactly** against the persisted draw file
(max abs diff 0.0). The sampled shape is a bounded split-triangular in log space over
[0.0005, 0.25], mode = median = 0.005, mean 0.016080, seed 4421, singleton correlation
group, hard-truncated. **0.25 has probability exactly zero** — it is the supremum,
realised max 0.24601 — but its *emission level* (national 618.282 Mt) is reached with
probability **0.127%**, about 1 draw in 790; 12 such draws sit in the persisted 10,000
prefix, whose maximum is 677.3 Mt, and the ensemble's own P99.9 is 623.6, above the
endpoint. The endpoint is a stress test the ensemble already samples, not an additional
structural allowance, and "it exceeds P97.5" would have been the wrong conclusion.
Freezing the factor moves national P97.5 from 550.0 to 529.0 and P99.9 from 623.6 to
572.8: it owns 26% of the upper half-width and 93% of the endpoint's probability mass.

The national ensemble **does** call the same engine: waste is injected by draw index
and the published percentiles reproduce the draw file exactly. The **Sobol/priority
sensitivity does not** — `variance_attribution.py` re-expresses every parameter as a
mean-preserving lognormal, with no injection. Log-variance is matched exactly; the
level is not (median 0.002196 against 0.005), so Var(ef) is 7.3× larger natively and
the published index 0.0487 understates the ensemble's own S_T = 0.275 by 5.6×. The
largest single driver of the national upper tail therefore ranks 7th and falls outside
the published top-5 parametric ranking, while `priority_rankings.py` excludes it from
the structural ranking on a comment asserting it "leads the PARAMETRIC ranking". It
does not. For the two injected modules these indices are not a verified decomposition
of the ensemble.
