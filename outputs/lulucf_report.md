# Pakistan LULUCF Land Sector (2024, provisional, Tier 1)

Carbon stock change in the land sector (IPCC 3.B), reported separately from agriculture and combined into an AFOLU total. Sink = negative.

## Net by sub-category (Mt CO2e, AR5)

| Code | Sub-category | Flux (signed) | C stock (context) |
|---|---|---:|---:|
| 3.B.1 | Forest land | -3.52 | 818 |
| 3.B.2 | Cropland (SOC) | NE | - |
| 3.B.3 | Grassland (SOC) | NE | - |
| 3.B.4 | Wetlands - mangrove blue carbon | -0.49 | 286 |
| **3.B** | **NET LULUCF** | **-4.01** | |

## AFOLU total

Agriculture **223.5** + LULUCF **-4.0** = **AFOLU net 219.4 Mt CO2e**.

## Land-sector narrative (FAOSTAT)

Pakistan's land sector flipped from a small **source** to a **sink** as the Billion Tree -> Ten Billion Tree afforestation programmes took hold:

## Validation & caveats
- **Forest** (-3.52 Mt) is calibrated to the afforestation programmes and matches FAOSTAT Forestland (~n/a).
- **Mangrove blue carbon** (-0.49 Mt) is our addition - FAOSTAT's aggregate omits Indus-delta mangroves, so the engine net is slightly more negative (a real sink, not an error).
- **Arid-climate caveat:** IPCC 2013 Wetlands defaults (AGB-C 86, soil-C 471 t C/ha) are humid-tropical; the arid Indus delta is likely lower - flagged for Tier 2.
- Cropland/grassland SOC are NOT ESTIMATED (NE) at Tier 1 - no land-use or management change is modelled - and contribute nothing to the net; they are not zeros (rc42).
- Tier 1, single-year; full per-transition gain-loss and a LULUCF time series are future work.
