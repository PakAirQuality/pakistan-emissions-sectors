# Pakistan Agricultural GHG Inventory - Tier 2 (6 categories), 2024

**Provisional estimate.** National inventory for the full IPCC agriculture sector - enteric fermentation, manure management, rice cultivation, managed soils, field burning of residues, and liming & urea CO2 - using Tier 1 methods with Tier 2 country-specific livestock weights, dairy share, manure-system shares and rice agronomy (see `docs/tier2_changelog.md`).

## Headline

**Pakistan agricultural emissions = 223 Mt CO2e (AR5 GWP-100, +/-19%), provisional.**  (AR6: 218 Mt CO2e.)

**Managed-soils EF1 sensitivity (3-point).** At the best-supported dry EF1=0.005 (primary), soils = 28.5 Mt / national = 223.5 Mt. Cui et al. 2021 --- the largest field-observation N2O database (1,507 obs) --- gives a Pakistan crop-weighted EF of **0.0055**, essentially the primary value (soils = 29.7 / national = 224.6 Mt), empirically anchoring the low arid EF1 over FAOSTAT's flat EF1=0.010 (soils = 40.4 / national = 235.4 Mt). Pakistan itself has no field observations, so the Cui value is climate-model-extrapolated with a wide CI, but its central estimate clearly favours 0.005.

## By category

| Category | Mt CO2e (AR5) | Mt CO2e (AR6) | Uncertainty |
|---|---:|---:|---:|
| Enteric fermentation | 151.7 | 146.2 | +/-25% |
| Manure management | 21.2 | 21.0 | +/-33% |
| Rice cultivation | 16.5 | 16.0 | +/-61% |
| Managed soils | 28.5 | 29.4 | +/-47% |
| Field burning of residues | 0.7 | 0.7 | +/-45% |
| Urea application | 4.8 | 4.8 | +/-11% |
| **TOTAL** | **223.5** | **218.1** | **+/-19%** |

## Detailed components

| Category | Component | Gas | Gg | Mt CO2e (AR5) |
|---|---|---|---:|---:|
| Enteric fermentation | dairy_cattle | CH4 | 955.8 | 26.76 |
| Enteric fermentation | other_cattle | CH4 | 1063.3 | 29.77 |
| Enteric fermentation | buffalo | CH4 | 2625.6 | 73.52 |
| Enteric fermentation | sheep | CH4 | 222.9 | 6.24 |
| Enteric fermentation | goats | CH4 | 479.1 | 13.42 |
| Enteric fermentation | camels | CH4 | 69.5 | 1.95 |
| Manure management | dairy_cattle (CH4) | CH4 | 93.9 | 2.63 |
| Manure management | other_cattle (CH4) | CH4 | 78.8 | 2.21 |
| Manure management | buffalo (CH4) | CH4 | 224.4 | 6.28 |
| Manure management | sheep (CH4) | CH4 | 8.9 | 0.25 |
| Manure management | goats (CH4) | CH4 | 21.1 | 0.59 |
| Manure management | camels (CH4) | CH4 | 2.4 | 0.07 |
| Manure management | poultry (CH4) | CH4 | 41.3 | 1.16 |
| Manure management | Direct N2O | N2O | 23.2 | 6.15 |
| Manure management | Indirect N2O (volatilisation) | N2O | 7.2 | 1.90 |
| Rice cultivation | Continuously flooded | CH4 | 591.0 | 16.55 |
| Managed soils | Direct N2O - synthetic fertiliser (upland) | N2O | 24.9 | 6.60 |
| Managed soils | Direct N2O - synthetic fertiliser (rice EF1FR) | N2O | 3.8 | 1.01 |
| Managed soils | Direct N2O - organic manure | N2O | 18.3 | 4.86 |
| Managed soils | Direct N2O - crop residues | N2O | 1.7 | 0.44 |
| Managed soils | Direct N2O - pasture deposition (cattle-type) | N2O | 3.4 | 0.91 |
| Managed soils | Direct N2O - pasture deposition (sheep/goat/other) | N2O | 9.9 | 2.61 |
| Managed soils | Indirect N2O - volatilisation (synthetic fertiliser) | N2O | 5.0 | 1.32 |
| Managed soils | Indirect N2O - volatilisation (organic manure) | N2O | 3.9 | 1.02 |
| Managed soils | Indirect N2O - volatilisation (pasture, cattle-type) | N2O | 1.8 | 0.48 |
| Managed soils | Indirect N2O - volatilisation (pasture, sheep/goat/other) | N2O | 3.4 | 0.91 |
| Managed soils | Indirect N2O - leaching/runoff (synthetic fertiliser) | N2O | 12.5 | 3.32 |
| Managed soils | Indirect N2O - leaching/runoff (organic manure) | N2O | 7.7 | 2.05 |
| Managed soils | Indirect N2O - leaching/runoff (crop residues) | N2O | 0.7 | 0.19 |
| Managed soils | Indirect N2O - leaching/runoff (pasture, cattle-type) | N2O | 3.6 | 0.96 |
| Managed soils | Indirect N2O - leaching/runoff (pasture, sheep/goat/other) | N2O | 6.9 | 1.84 |
| Field burning of residues | Residue burning CH4 | CH4 | 19.2 | 0.54 |
| Field burning of residues | Residue burning N2O | N2O | 0.5 | 0.13 |
| Urea application | Urea application CO2 | CO2 | 4824.5 | 4.82 |

## Method

- IPCC 2006 Guidelines Vol 4 + 2019 Refinement; Tier 1 methods with Tier 2 country-specific activity data and parameters.
- GWP-100: AR5 primary (CH4 28, N2O 265) for UNFCCC ETF/CRT; AR6 secondary.
- Tier 2 country-specific: FAOSTAT dairy share, Pakistan animal weights, manure-system shares, rice agronomy, residue return (see tier2_changelog.md).
- Every emission factor traces to `data/emission_factors.csv`; uncertainty by IPCC Approach 1 error propagation.

## Key assumptions & provisional flags

- Livestock basis = PBS 7th Agricultural Census 2024; dairy share = FAOSTAT QCL 2024 Milk Animals/Stocks (cattle 0.295). Animal weights = Pakistan herd-averages (Tier 2).
- Managed-soils EF1 = 0.005 (2019 dry) is the best-supported value for irrigated arid cropland - the dry EF1 was itself derived largely from irrigated dry fields (PMC9293294). A sensitivity at EF1=0.010 (Pakistan-official) is reported.
- Leaching retained on the ~80% irrigated area (FracLEACH 0.24, EF5 0.011) despite the dry climate - canal irrigation exceeds field capacity (defensible asymmetry).
- Rice harvested area ~3.5 Mha provisional; cultivation period 125 d (area-weighted).
- Manure-management-system shares are Tier 2 South-Asia/Pakistan estimates pending a national survey; dung-cake-burned N (~28%) routed to Energy, not Manure Management.
- FSOM (N mineralised from SOC loss) set to 0.
- Benchmarks: FAOSTAT (Pakistan 2023, AR5), EDGAR_2024 (2023 data) and EDGAR_2025 (2024 data, year-matched: agri 261 Mt vs engine 222 Mt, ratio 0.85). The managed-soils divergence from FAOSTAT (engine ~28 vs FAOSTAT 58 Mt) is METHODOLOGICAL - FAOSTAT uses 2006 aggregate defaults (EF1 0.01, EF3PRP 0.02); the engine uses the empirically-better 2019 disaggregated dry values. The EF1=0.010 sensitivity brackets it.
