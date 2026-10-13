# Pakistan's official land account: what exists (Level A)

A **transcription and comparison** of official accounts — not a new land estimate, and
nothing here is independently validated.

## What exists

One national land estimate, published three times. BTR1 (2024), CRT v2.83 and the TNC
(2025) all carry the **same** FY2020-21 numbers: land sector **34.82 Mt CO2e** (forest 28.64,
cropland 5.67, wetlands 0.48, grassland 0.03). BUR1 (2022) carries a different estimate for
FY2017-18: **31.52 Mt CO2e**. Two inventory years, nine years of PakEmis to cover; no series.

Forest land is reported as a **net source of +28.44 Mt CO2** — a sink nowhere except four
forest strata and one banana plantation.

Four structural facts, verifiable in the CRT workbook:

- **The "LUC" in LULUCF is not estimated.** Table 4.1 (land transition matrix) is blank and
  every `4.X.2 land converted to` row is empty: land-remaining-land only, as BUR1 states.
- **Only living biomass is estimated.** Dead wood, litter and mineral- and organic-soil SOC
  are blank in every land class. Blank is *not estimated*, not zero, and the CRT has no
  notation to distinguish them. FAOSTAT does support a genuine zero for organic soils.
- **Settlements (4.E), Other land (4.F) and HWP (4.G) are wholly absent**, though BUR1
  reports them as 2.1% and 12.2% of national area.
- **Grassland CO2 is zero by stated assumption** (release from grass cutting "offset by
  growth in the subsequent year") over 53,041 kha, the largest area in the account.

Three defects to flag before joining to these numbers:

1. **Year label.** Every LULUCF and Agriculture CRT sheet reads `Year: 2021-22`; the BTR and
   TNC narrate the identical figures as FY2020-21.
2. **The published gross split is wrong.** BTR1 and TNC state forest "gross CO2 emissions
   43.55 Mt, removals 15.11 Mt". Those are sums of net-positive and net-negative *strata*.
   The CRT's own carbon-stock gains and losses give **gross removals 26.08 and gross
   emissions 54.52 Mt CO2**. Both net to 28.44. BUR1 reported a real gross split (32.68 /
   57.54), so the regression is new.
3. **Reported areas are impossible.** 4.A+4.B+4.C+4.D = 182,676 kha, 2.37x Pakistan's land
   area; cropland alone is 124,368 kha. The CRT also files gains/losses in the implied-factor
   (t C/ha) column block and labels 1,065 kha "peat extraction".

Land biomass-burning non-CO2 sits in the **Agriculture** CRT (3.E, 3.F) while the BTR folds
it into the land block, so a PakEmis land layer adopting the BTR's cropland 5.67 Mt will
**double count** crop-residue burning.

## Definitions, and why sensors cannot settle them

National definition (FREL s.1.4.1): minimum **0.5 ha**, crown cover **>10%**, trees with
**potential to reach 2 m**, *plus* irrigated plantations and anything notified as forest in
law. FAO FRA uses **5 m**, so it moves Pakistan's scrub forest to other wooded land (FRA 2025
comment 1). FRA Forest 2020 = 3,088.53 kha against the CRT's 4,079.63 kha — a purely
definitional 32% gap; CRT forest matches FRA Forest + OWL (4,113.66 kha) to 0.8%.

No sensor threshold reproduces this definition. Hansen/GLAD tree cover is a canopy fraction
with no height, minimum-area rule or land-use concept (a 30 m pixel is 0.09 ha, so 0.5 ha is
5-6 pixels); ESA WorldCover's tree class assumes >=3 m. The "notified in law" clause is
administrative, unobservable in principle. **Report any raster comparison against the FRA
5 m series, never against the CRT area.**

## What each source cannot support

- **FREL (946,653 t CO2e/yr)** is one activity (deforestation), two pools (AGB+BGB), one gas
  (CO2), calendar **2004-2012**, no sink term, no forest-remaining-forest term. Not a current
  whole-country net flux; never difference it against 28.44 Mt. Its activity data was later
  revised — FRA 2025 says the 2004-2012 Balochistan forest area was overestimated.
- **FRA 2025** reports areas only, no fluxes.
- **FAOSTAT** reports forest land as a **net sink of -4.11 Mt CO2 (2016-2020) / -3.50 Mt
  (2021-2025)** — opposite in sign to Pakistan's own account, a 32 Mt gap. Calendar-year,
  linearly interpolated between FRA five-yearly points (flag `I`), constant within each
  interval, and `Forestland = Carbon stock change - Net Forest conversion` exactly in all 36
  years, making pre-2016 values a cancellation of two large sources.

## Recommended first reproducible component

**Forest-land net CO2 and its corrected gross decomposition.** Inputs: three cells from CRT
`Table4.A` — G10 = 7113.0834552, H10 = 14868.348452164, I10 = -7755.264996964 (kt C) — and
44/12. This reproduces the reported 28,435.972 kt CO2 to 0.000 kt and publishes gross removals
26,081.0 and gross emissions 54,517.3 kt CO2, correcting the 43.55/15.11 claim. No new data,
no modelling. Second: cropland residue burning from `Table3.F` (areas 4039.61/2299.31/165.25/630.15 kha; 4/5.5/10/6.5 t dm/ha;
combustion factor 1.0; EF 2.7 kg CH4 and 0.07 kg N2O per t dm; AR5 GWP 28/265) reproduces
3,253.17 kt CO2e exactly — but book it once.

*No retrieved document contained directives addressed to a reader-agent.*
