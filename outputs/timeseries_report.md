# Pakistan Agricultural GHG - Time Series 1990-2024 (Tier 2, provisional)

Tier 2 method (constant Phase-5 EFs) driven over FAOSTAT historical activity data (livestock stocks, crop area/production, N fertiliser). The 2024 point is the census-based Tier 2 anchor; earlier years are FAOSTAT-activity-driven.

## Trajectory

- **1990:** 83 Mt CO2e -> **2024:** 223 Mt CO2e  (CAGR **3.0%/yr**, x2.7 over 34 yr)

| Category | 1990 (Mt) | 2024 (Mt) | growth |
|---|---:|---:|---:|
| Enteric fermentation | 54.5 | 151.7 | x2.8 |
| Manure management | 6.6 | 20.8 | x3.2 |
| Rice cultivation | 9.6 | 16.5 | x1.7 |
| Managed soils | 10.1 | 28.5 | x2.8 |
| Field burning of residues | 0.3 | 0.7 | x2.6 |
| Urea application | 1.9 | 4.8 | x2.6 |
| **TOTAL** | **82.9** | **223.0** | **x2.7** |

## Validation vs FAOSTAT (latest common year)

| Category | Engine (Mt) | FAOSTAT (Mt) | ratio |
|---|---:|---:|---:|
| Enteric fermentation | 143.2 | 145.1 | 0.99 |
| Manure management | 19.8 | 14.6 | 1.36 |
| Rice cultivation | 16.5 | 14.3 | 1.16 |
| Managed soils | 27.2 | 58.5 | 0.46 |
| Field burning of residues | 0.7 | 0.8 | 0.92 |
| Urea application | 4.9 | 0.0 | 0.00 |

## Caveats
- Activity data is FAOSTAT (consistent series); the 2024 census-based snapshot (217 Mt) differs slightly from the FAOSTAT-driven point.
- Method held constant (Tier 2 EFs, dairy share 0.295) - this is an activity-driven trajectory, not a re-derivation of EFs per year.
- Managed soils tracks below FAOSTAT (2019 disaggregated dry vs 2006 aggregate, see tier2_changelog.md); enteric/manure/rice track closely.
