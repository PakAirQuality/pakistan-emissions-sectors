# Missing sources lane — findings

`coverage_matrix.csv` (84 rows), `fgas.csv` (19 inputs),
`fgas_stock_screen.csv`, `fgas_benchmark_consistency.csv`, `defects_found.md`,
two builder scripts. Nothing outside this directory was written; no pin moved.

## T-MISS-1 — the coverage matrix

Built from `outputs/completeness.csv` by `build_coverage_matrix.py`, which fails
if a non-E row has no judgement, so it cannot go stale silently. 56 rows come
from the executable inventory; 28 more are IPPU categories the ippu gap matrix
carries as NE that **have no row at all in the national completeness
table** — 2.A.3, 2.A.4, 2.B.3–2.B.10, 2.C.2–2.C.7, 2.D.2, 2.D.3, 2.E,
2.F.2–2.F.6, 2.G.1–2.G.4, 2.H: the silent-absence class the 1.A.4.a audit and
the Wave-4 2.B.2 insertion closed, still open for 28 cells.

`campaign_status` (what grade of treatment is supportable today) is kept apart
from the notation key, which answers a different question: 10 SUPPORTED, 14
CONDITIONAL, 17 SCREENING, 43 UNESTIMATED/BLOCKED. **No completeness percentage
is computed** — the denominator is what is unknown.

Findings:

1. **BTR1 prints numbers for categories PakEmis omits** (2021): 4.D.2 industrial
   wastewater **2.22 Mt**, 2.H **1.35 Mt**, 2.A.2 lime **1.33 Mt**, 1.B.1 solid
   fuels **0.73 Mt**, 2.A.4 **0.27 Mt**, 4.C.1 **0.11 Mt**, marine bunkers
   **0.040 Mt**. Scope screens, not values to adopt: the same table books 4.C.2
   open burning at 0.20 Mt against PakEmis's 3.83 Mt, so it disagrees rather than
   calibrates.
2. **A contradiction**: PakEmis records no formal bunkering market before 2026;
   the BTR books 0.040 Mt of marine bunkers for 2021. One is wrong.
3. **Cheapest open fronts**, public and unblocked: 1.B.2 gas T&D (SNGPL/SSGC
   publish throughput — but UFG includes theft and meter error and must never be
   GWP-weighted), LULUCF harvested wood products (FAOSTAT roundwood + PBS trade;
   only a half-life choice missing), 2.D.2 paraffin wax (the OCAC table already
   read for 2.D.1), 2.G.1 SF6 (Tier 1 runs on nameplate charge).
4. **Overlap is already realised.** The brick and captive screenings were retired
   at rc47 for double counting against the activated HDIP series; commercial gas
   is counted as post-meter leakage, never as combustion; stationary farm diesel
   sits in the road total at road factors. The positive control is the dung-cake
   transfer, which closes both ways under an equality test.

## T-MISS-2 — F-gases

**Verified in the latest reporting, not assumed.** Pakistan's 2022 CRT
(`PAK_CRT_2024.zip`, Table2(II).B-Hs2) books all of 2.F as **one species**:
HFC-23, 0.236955 t, from a declared stock of 23.695 t at a 1 % product-life
factor, entered at 2.F.1.a *commercial refrigeration*, other subcategories IE —
0.00294 Mt CO2e. BTR1 2024 prints 2.F, 2.C, 2.E, 2.G all = 0. HFC-23 is a cascade
component and an HCFC-22 by-product, not a commercial refrigerant: the species
assignment looks misfiled.

**A bank/emissions method is required and most of it exists**: a mass-conserving
kernel, a 143-stratum species × application bank (5.854 Mt CO2e AR5, 2024), the
Article-7 supply series, IPCC Vol 3 Ch 7, and a household stock band. Four of
five activation criteria are met; the unmet one is **pre-charged equipment
imports** (REQ-NOU-01, drafted not sent) — gas inside imported appliances never
enters bulk Article-7 reporting.

**A stock-side cross-check, and a correction.** I first called my
`fgas_stock_screen.csv` the first use of the HIES stock indicator. **Wrong**:
`scripts/build_hfc_bank_series.py` already ships a household band on the same
indicator and Table 7.9 basis (FY2023-24 floor 0.191–2.423 Mt CO2e); I grepped
only `src/pkinv/sectors/ippu/` and missed a `scripts/` phase. Mine is a second,
independently parameterised run and lands inside that band (0.119–2.520, central
0.654), which is corroboration, not a new number. What *is* new is the axis: the
shipped band compares emissions, mine compares the two banks in **tonnes of
refrigerant, per application**, separating a stock-coverage gap from a leak-rate
gap.

The decisive result is per application. For **refrigeration** the two independent
banks agree to within **1.3×** while emissions differ **107×**: bank size agreed,
so only the leak rate can explain it. The bank prices that stratum at 8 %/yr;
Table 7.9 gives domestic refrigeration 0.1–0.5 %/yr. A domestic/commercial split
nobody holds decides ~1.2 Mt. For stationary and mobile AC the bank and emissions
ratios match (3.7×/9.0×, 2.9×/5.1×) — stock coverage and species share, not
parameters.

**EDGAR's 11.54 Mt is not usable as a value.** It implies 60,000–109,000 t of
refrigerant in service (3.0–5.4× the supply bank, 7.7–13.9× the household stock);
its cumulative 1990–2024 emissions are 2.6× the whole Article-7-era supply; its
last five increments agree to within 3 %, with a non-zero *declining* 1990–95
segment — the shape of an extrapolation. Scope screening only; confirming it
needs EDGAR's own F-gas documentation, which I did not read.

SF6 (2.G.1, AR5 GWP 23,500) and PFCs from 2.C.3 / 2.E sit inside EDGAR's
"Processes" total and outside the HFC bank, so EDGAR-minus-bank cannot be read as
HFCs without ruling them out. HCFC-22's share of the installed AC base is
publicly reported under Pakistan's HPMP and could halve this category.

**Second error, logged:** I keyworded `holdings.py` wrongly and re-downloaded
IPCC Vol 3 Ch 7, already held at
`data/raw/ipcc/ipcc2006_V3_7_Ch7_ODS_Substitutes.pdf` (identical sha256). The
copy was deleted, so nothing was retained and there is no acquisition to log.
Both of my errors were the same mistake: searching one layer and concluding from
its silence.
