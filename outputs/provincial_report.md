# Pakistan Agricultural GHG - Provincial Downscaling (2024, provisional)

National Tier 1 emissions allocated to provinces by category-appropriate proxies (`data/province_shares.csv`). Provincial totals reconcile exactly to the national control totals.

## Provincial totals (Mt CO2e, AR5)

| Province | Enteric fermentation | Manure management | Rice cultivation | Managed soils | Field burning of residues | Urea application | TOTAL | Share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Punjab | 79.9 | 10.3 | 12.2 | 17.1 | 0.5 | 3.3 | 123.3 | 55% |
| Sindh | 35.8 | 4.7 | 3.4 | 6.4 | 0.1 | 1.1 | 51.4 | 23% |
| Khyber Pakhtunkhwa | 24.3 | 3.7 | 0.3 | 2.5 | 0.0 | 0.2 | 31.0 | 14% |
| Balochistan | 11.4 | 2.5 | 0.7 | 2.6 | 0.0 | 0.1 | 17.3 | 8% |
| Other | 0.3 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.4 | 0% |
| **NATIONAL** | 151.7 | 21.2 | 16.5 | 28.5 | 0.7 | 4.8 | **223.5** | 100% |

## Allocation proxies

- Enteric & manure CH4 -> province livestock shares by species (**PBS 7th Agricultural Census 2024**).
- Rice CH4 -> rice harvested-area shares (MNFSR district-wise 2022-23).
- Soils synthetic-N N2O -> fertiliser offtake shares (NFDC 2024-25).
- Soils manure/pasture N2O -> livestock shares; residue N2O -> residue-mass-weighted crop shares.

Livestock province shares are now on the **2024 census** (was 2006; e.g. KP's livestock share rose 0.153->0.195). District downscaling uses real 2024 census district counts (EF-weighted) where available, GLW-2020 proxy for unmatched districts.
