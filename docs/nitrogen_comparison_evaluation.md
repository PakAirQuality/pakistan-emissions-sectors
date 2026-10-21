# Managed-soils comparison: what is established and what remains unresolved

The current PakEmis engine gives **28.493727 Mt CO2e AR5**, compared with **58.499700 Mt** in the retained FAOSTAT four-item snapshot. Replacing selected direct factors, while keeping the current PakEmis nitrogen inputs and all other terms fixed, gives **55.071751 Mt**. This bridges **88.576%** of the initial numerical difference on this particular substitution path. It demonstrates substantial method sensitivity. It does not establish that these factors caused 88.576% of the difference between the complete inventories, or that either inventory is more accurate.

## Reproducible calculation

Run:

```sh
PYTHONPATH=src python -m pkinv.sectors.agriculture.faostat_nitrogen_flows
PYTHONPATH=src python -m pkinv.sectors.agriculture.faostat_nitrogen_flows --check
PYTHONPATH=src python -m unittest discover -s tests -p test_faostat_nitrogen_flows.py
```

`manure.compute()` supplies the current nitrogen pools. `soils.compute()` calculates all managed-soils subitems, using the same GWP conversion as the inventory. The comparison no longer consumes `outputs/eval/sensitivity.csv` or the rounded activity-factor ledger. The reference and substitution cases therefore share one internally consistent baseline. No inventory factor or activity is recalibrated to FAOSTAT.

| Conditional case | PakEmis, Mt CO2e AR5 | Change from reference | Fraction of initial difference bridged |
|---|---:|---:|---:|
| Current engine | 28.493727 | 0 | 0% |
| Upland EF1 substitution | 40.788901 | 12.295174 | 40.976% |
| Pasture EF3PRP substitution | 42.776577 | 14.282850 | 47.600% |
| Both substitutions | 55.071751 | 26.578024 | 88.576% |
| Retained FAOSTAT comparator | 58.499700 | — | — |

The combined case leaves **3.427949 Mt**. Its constituents have not been identified. Differences in activity, nitrogen partition, indirect factors, detailed coverage and period may offset one another, so this residual is not a bound on any one source of disagreement.

The percentage is `(combined − reference) / (FAOSTAT − reference)`. The two substitutions affect disjoint direct-emission subitems and their effects add exactly at fixed nitrogen pools. This is an accounting identity within PakEmis, not an independently estimated causal decomposition of the cross-inventory gap.

## Factors and limits of the substitution

The target values are read from the existing factor registry, rather than hard-coded baseline multipliers:

| Factor | Current | Substitution target | Terms changed |
|---|---:|---:|---|
| EF1 | 0.005 | 0.010 | Upland synthetic N, applied manure N, returned crop-residue N |
| EF3PRP, cattle-type | 0.002 | 0.020 | Cattle-type pasture deposition |
| EF3PRP, sheep/goat/other | 0.003 | 0.010 | Other pasture deposition |

Units are kg N2O-N per kg N. The targets agree with [IPCC 2006 Volume 4, Chapter 11, Table 11.1](https://www.ipcc-nggip.iges.or.jp/public/2006gl/pdf/4_Volume4/V4_11_Ch11_N2O%26CO2.pdf). That table also has a flooded-rice factor of 0.003. The current engine instead retains **EF1FR = 0.004** in every case here; this alone precludes describing the exercise as a complete 2006 factor replacement.

The [2019 Refinement, Chapter 11, Table 11.1](https://www.ipcc-nggip.iges.or.jp/public/2019rf/pdf/4_Volume4/19R_V4_Ch11_Soils_N2O_CO2.pdf) distinguishes wet/dry EF1 and cattle-type EF3PRP, but gives sheep/other animals a single EF3PRP value without a climate split. Its rice aggregate factor is 0.004. Therefore the combined change should not be described wholly as climate disaggregation. All indirect volatilisation and leaching terms, rice allocation, excretion rates and manure routing remain at their current PakEmis settings. No conclusion about their suitability follows from this comparison.

[FAO's livestock-emissions metadata](https://data.fao.org/catalog/dataset/b5f6204f-441f-4696-9fe5-902b52cde61d) describes a Tier 1 method following the 2006 Guidelines. [Tubiello et al. (2013), Table 1](https://www.fao.org/climatechange/36143-0fa4483057747f41c08183b702ec5954e.pdf) documents the FAOSTAT method's factor families. These establish a reason to examine the selected factor changes; they do not reconstruct the retained 2023 national estimates or establish their exact nitrogen pools.

## Activity evidence and scope

PakEmis uses 3,775,000 t synthetic fertiliser N in FY2023-24; the retained FAOSTAT activity panel reports 3,808,775 t in CY2023. The difference is −0.887%. This is a limited consistency observation, subject to the fiscal/calendar mismatch and potentially shared national statistics.

Animal heads are reported separately by species. An all-animal total is no longer used: poultry dominates a head-count sum, while species have very different excretion rates. The stock comparator is CY2024, not the CY2023 stock input behind the emissions comparator. PakEmis metadata also distinguishes census enumeration from the poultry projection. Neither close heads nor close synthetic N proves agreement in total excreted N, applied-manure N, pasture N or residue N.

The generated table exposes five PakEmis nitrogen inputs, with blank FAOSTAT counterpart values where no matching pool-N data are held. Its four broad emissions groups are:

| Pool | PakEmis | Retained FAOSTAT |
|---|---:|---:|
| Synthetic fertiliser | 12.247742 | 21.015600 |
| Manure applied to soils | 8.898363 | 6.864500 |
| Manure on pasture | 6.713682 | 27.291200 |
| Crop residues | 0.633939 | 3.328400 |

All values are Mt CO2e AR5. Broad source labels permit this diagnostic grouping but do not prove identical crop/animal coverage, nitrogen partition, omitted terms or reporting periods. Higher PakEmis applied-manure emissions cannot, on their own, establish that more nitrogen is field-applied: direct and indirect methods both contribute to the totals. No pool-specific cause is assigned from the sign of the difference alone.

## Comparator provenance and arithmetic repair

`data/sectors/agriculture/evidence/faostat_soils_comparator_snapshot.csv` transcribes the four **FAOSTAT** pool values already published in `outputs/pakemis_faostat_nitrogen_flows.csv` at commit `41b56365df9195d6a028a66630d0395b0d7c5de1`. Each input row records that chain and its four-decimal-place Mt precision. It is a retained comparator, not a new primary extraction or independent check of the earlier transcription. The original raw archive is absent from the public repository. The public build always uses this fixed snapshot and does not change its answer according to private-file availability.

The four printed values sum to **58.4997**, rather than the **58.4996** described in older prose. Four independently rounded four-decimal-place values permit at most ±0.0002 Mt rounding error in their sum. The 0.0001 difference is compatible with rounding, but exact original precision cannot be recovered or asserted from this snapshot.

At the audited commit, the old comparison mixed a current ledger sum of **28.49372651** (rounded subitems: **28.4937**) with the **28.53** baseline in the stale sensitivity table. The current national category output was **28.494**. Its EF1-only scenario also retained **40.43**, although the current EF1-linked direct components sum to **12.295174** and therefore yield **40.788901** after substitution. Reading all cases directly from the engine resolves these inconsistent baselines. The independently owned legacy sensitivity product was regenerated from current tracked category outputs and agrees with the fresh engine within its two-decimal-place publication precision; it is no longer an input here.

Tests verify closure, units, disjoint factor effects, unchanged rice/indirect terms, live activity/factor dependence, input immutability, comparator-year/metric checks and exact public rebuilds. They do not require a preferred agreement ratio or a minimum share explained.

## Next evidence needed

To turn the conditional comparison into a stronger attribution, acquire and retain versioned FAOSTAT primary extracts for nitrogen excretion, manure applied and left on pasture, crop-residue inputs, species coverage and the exact 2023 factor/method implementation. Then harmonise the fiscal/calendar and coverage differences explicitly and compare activity-only and method-only substitutions. Shared upstream statistics and choices previously informed by FAOSTAT must remain labelled as dependent evidence. Independent physical observations would be a separate evaluation, not a conclusion from agreement between model estimates.
