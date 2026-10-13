# Worked annual example: landfill methane by first-order decay (FY2023-24)
This reproduces one year of `src/pkinv/sectors/waste/swds.py` exactly, so a reader can re-derive the time series. Every number below is printed by running the engine (`python3 docs/waste_fod_worked_example.py` is not a script; the values are copied from the engine call shown).
## Model, as implemented
Annual recurrence (IPCC 2006 Vol. 5 Ch. 3 Eqs 3.4-3.5 convention, single pool, deposit enters the decaying stock at the END of its year):
```
DDOCm_decomposed(T) = DDOCm_a(T-1) * (1 - exp(-k))
DDOCm_a(T)          = W(T) * DOC * DOCf * MCF + DDOCm_a(T-1) * exp(-k)
CH4_generated(T)    = DDOCm_decomposed(T) * F * 16/12
CH4_emitted(T)      = max(CH4_generated - R, 0) * (1 - OX)
```
Parameters (`data/sectors/waste/parameters/waste_params.csv`): k = 0.065 /yr; DOC = total C 0.2195 - fossil C 0.0757 = 0.1438 t C/t wet; DOCf = 0.50; MCF = 0.60; F = 0.50; R = 0.0 t; OX = 0.00. Combined deposit factor DOC*DOCf*MCF = 0.043140; exp(-k) = 0.937067.
Deposit series W(T): disposed waste from population x per-capita generation x collection, observed 2000..2023 (`population_district.csv`, census-interpolated); back-projected to 1960 by the first-decade growth rate (`disposal_series`, SPINUP_FROM = 1960). Composition is pre-collapsed into the three carbon scalars; no per-component table exists in the repository.
## The recurrence, selected years (tonnes)

| year | W(T) deposited | DDOCm_a at start of year | decomposed in year |
|---|---|---|---|
| 1960 | 3782387.3 | 0.0 | 0.0 |
| 1961 | 3865771.4 | 163172.2 | 10268.8 |
| 1970 | 4704003.7 | 1385623.7 | 87200.8 |
| 1980 | 5850181.1 | 2446603.7 | 153971.0 |
| 1990 | 7275636.1 | 3420369.6 | 215252.5 |
| 1999 | 8853244.6 | 4342255.2 | 273269.1 |
| 2000 | 9048417.4 | 4450915.1 | 280107.4 |
| 2001 | 9244797.2 | 4561156.4 | 287045.1 |
| 2010 | 11253154.6 | 5636215.9 | 354701.4 |
| 2020 | 14285416.5 | 7089326.6 | 446149.3 |
| 2021 | 14666113.9 | 7259450.1 | 456855.6 |
| 2022 | 15058399.8 | 7435290.7 | 467921.7 |
| 2023 | 15467237.3 | 7616988.3 | 479356.4 |

## FY2023-24 result

DDOCm decomposed in 2023 = **479356.4 t C**. CH4 generated = 479356.4 x 0.50 x 16/12 = **319570.9 t**. With R = 0 and OX = 0, CH4 emitted = **319.5709 Gg**.

Without the 1960 spin-up (site empty in 2000): decomposed = 416542.7 t C, i.e. 86.9% of the spun-up value; the pre-panel deposits supply the remainder.

The monthly engine (`monthly_state`) runs the same single pool with exact month lengths and a 6-month maturation delay; its annual sum is normalised to this annual value (`monthly_decomposition_shares`).
