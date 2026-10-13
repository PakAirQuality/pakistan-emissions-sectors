# Methods Note — National Inventory Engine (Tier 1 methods + Tier 2 country-specific data)

Companion to the engine in `src/pkinv/sectors/agriculture/`. Documents the equations, emission factors,
GWP set and uncertainty treatment. All numeric inputs live in `data/` — this note explains
how they are combined.

## Scope, year, basis
- **Categories:** enteric fermentation, manure management, rice cultivation, managed soils.
- **Year:** 2024 / FY2024-25.
- **Population basis:** PBS 7th Agricultural Census 2024 (Economic Survey kept as cross-check).
- **Tier:** Tier 1 (IPCC 2006 Guidelines Vol 4 + 2019 Refinement).

## Equations implemented

| Module | Category | IPCC equation | Formula (as coded) |
|---|---|---|---|
| `enteric.py` | Enteric CH₄ | Eq 10.19/10.20 | `Σ N · EF / 1e6` → Gg |
| `manure.py` | Manure CH₄ | Eq 10.22 | `Σ N · EF(temp-blend) / 1e6` |
| `manure.py` | Manure N₂O direct | Eq 10.25 | `Σ N·Nex·Σ(MS·EF3) · 44/28 / 1e6` |
| `manure.py` | Manure N₂O indirect | Eq 10.26 | `Nex_managed·FracGASM·EF4 · 44/28 / 1e6` |
| `rice.py` | Rice CH₄ | Eq 5.1-5.2 | `EFc·SFw·SFp·SFo·area·days·1e-6` |
| `soils.py` | Soils N₂O direct | Eq 11.1 | `(FSN+FON+FCR)·EF1 + FPRP·EF3PRP, ·44/28` |
| `soils.py` | Soils N₂O indirect | Eq 11.9/11.10 | volatilisation + leaching, `·44/28` |
| `soils.py` | Residue N (FCR) | Eq 11.6 (simplified) | `Σ_crop AGdry·fret·Nag + BGdry·Nbg` |

`44/28` converts N₂O-N to N₂O. Emissions are computed in Gg, then to CO₂e.

## Nitrogen accounting (avoids double counting)
Per livestock species the annual N excretion `Nex = Nrate·TAM·365/1000` (Eq 10.30) is split by
manure-management-system share (`data/mms_shares.csv`):
- **Pasture/range/paddock** → soils **FPRP** (gets EF3PRP), not counted in manure N₂O.
- **Burned for fuel** (dung cake) → excluded here; the N is removed and *received* by 1.A.4.b residential (`pkinv.sectors.residential`), which derives the burnt dry matter from this same flow.
- **Managed systems** → manure N₂O direct (EF3); the managed N then flows to soils as **FON**
  after subtracting storage volatilisation (`FracGASM`), which is itself counted as manure
  N₂O indirect. Field volatilisation and leaching of the applied FON are counted again in
  soils indirect — these are distinct fluxes at distinct stages, per IPCC.

## Emission factors & climate disaggregation
- All EFs in `data/emission_factors.csv` (2019 Refinement values for soils/rice where they
  differ; 2006 for livestock). Pakistan = "Indian Subcontinent" livestock region.
- **Manure CH₄** blends warm/cool temperature columns by `warm_zone_share`/`cool_zone_share`
  (default 70/30, Indus plain warm).
- **Soils EF1/EF4** blend dry/wet climate by `climate_dry_fraction`/`climate_wet_fraction`
  (default 90/10 — Pakistan is >60% arid). `FracGASF` is product-weighted at runtime
  over the NFDC Annex-7 mix (`fertiliser_mix.fracgasf()` = 0.1605; the IPCC urea
  default 0.15 in `emission_factors.csv` is the annexe-missing fallback only).
  `FracLEACH` scaled by `leach_applicable_fraction` (0.85) to reflect
  that the irrigated Indus belt triggers leaching even in a dry climate.

## GWP and CO₂e
`gwp.py`: AR5 GWP-100 primary (CH₄ 28, N₂O 265) to match UNFCCC ETF/CRT; AR6 (CH₄ 27, N₂O 273)
reported alongside. `Mt CO₂e = Gg gas · GWP / 1000`.

## Uncertainty (IPCC Approach 1)
`uncertainty.py`: products (AD × EF) combine percentage uncertainties in quadrature (Eq 3.1);
sums combine magnitude-weighted in quadrature (Eq 3.2). Inputs are the % ranges in
`emission_factors.csv` and the `ad_uncert_pct` columns in the activity files. A Monte-Carlo
(Approach 2) is implemented, both per sector and pooled across all seven (`pkinv.report.uncertainty_all`).

## Validation
`national_benchmark_comparison.csv` compares the engine, per category and in total, to real
**FAOSTAT Emissions Totals** (Pakistan, area 165, 2023, AR5 — from the bulk `Emissions_Totals`
CSV) and the **EDGAR_2024_GHG** agriculture sector (Pakistan, 2023, AR5 — from the EDGAR
booklet). Pass = ratio 0.5–2.0. Results: engine total 222 Mt = 0.95× FAOSTAT (233) and
0.83× EDGAR (267); enteric/manure/rice all within band; managed soils is the one notable
divergence (engine 30 vs FAOSTAT 58 Mt) because the dry-climate EF3PRP (0.002) makes
pasture-deposited manure N₂O much smaller than FAOSTAT's — a real, documented methodological
choice, not an error. Benchmark values live in `data/benchmarks.csv`.

## Provincial downscaling (Phase 3, `downscale.py`)
National category emissions are allocated to Punjab/Sindh/KP/Balochistan (+ "Other") by a
category-appropriate proxy from `data/province_shares.csv`:

| Component | Proxy | Source |
|---|---|---|
| Enteric & manure CH₄ (per species) | province livestock shares by species | PBS Livestock Census 2006 |
| Manure N₂O, organic-manure & pasture soils N₂O | livestock totals / small-ruminant shares | PBS 2006 (pop-weighted) |
| Rice CH₄ | rice harvested-area shares | MNFSR district-wise 2022-23 |
| Synthetic-fertiliser & indirect soils N₂O | fertiliser offtake shares | NFDC 2024-25 |
| Crop-residue soils N₂O | residue-mass-weighted crop shares | MNFSR 2022-23 |

Because every proxy's shares sum to 1, provincial totals reconcile **exactly** to the national
control totals (enforced by an assertion and a `test_downscale` check). Livestock relies on the
2006 census because no public 2024 province livestock table exists — the main provisional flag.
Result: Punjab 126 (56%), Sindh 53 (24%), KP 26 (12%), Balochistan 18 (8%) Mt CO₂e.

## Gridded emission surfaces (Phase 4, `src/pkinv/core/gis/`)
The provincial control totals are allocated to a **0.05° (~5 km) national grid** by dasymetric
distribution: within each province, each category total is spread across cells ∝ a proxy, then
normalised so the province's cell-sum equals its control total. National, per-province and
per-category reconciliation are therefore **exact by construction** (asserted in `run_gis.py`
and `test_gis.py`).

- **Grid & boundaries:** `grid.py` rasterises geoBoundaries ADM1 polygons to a `province_id`
  array (GB/AJK/ICT → "Other"); 340×267 cells over the Pakistan bbox.
- **Category-specific proxies** (`proxies.py`), each read as remote COG windows via `/vsicurl`:
  - **Enteric fermentation & manure** → **GLW 4 (2020) emission-weighted livestock density** (FAO
    GCS, open): species density × per-head enteric EF, so herds land on real locations (canal belt,
    rangeland, peri-urban).
  - **Rice** → **MapSPAM 2020 rice physical area** (`data/sectors/agriculture/gis/manual/spam_rice.tif`),
    HELD and hash-pinned since rc26 with its cropland-fallback class deleted from the
    allow-list (a checkout without it refuses the build); the own-year GCD-Rice 2023
    classification ships beside it as a crosscheck and a priced ADM2 bracket.
  - **Field burning of residues** → **NASA FIRMS VIIRS fire-occurrence** (FRP-weighted, 166,393 in-grid
    FY2023–24 detections of 1,664,876 fetched across the nine-year record; the surface consumes only the reporting period's own dates): concentrates on the Punjab rice–wheat
    belt where straw is actually burned (`fetch_firms.py`, key via `FIRMS_MAP_KEY` env, never committed).
  - **Managed soils, liming/urea** → ESA WorldCover 2021 cropland fraction.
  All proxies fall back to cropland if a file is absent. See `docs/DATA_ACQUISITION.md`.
- **Control totals:** reused from Phase 3 via `downscale_bridge.provincial_matrix()` — the grid
  sums to the same ~222 Mt the provincial report publishes.
- **Outputs:** per-category + total GeoTIFFs (float32, Mt CO₂e/cell, EPSG:4326), log-scale
  hotspot PNGs, per-cell CSV, and `gis_report.md`. Emissions concentrate along the Indus belt.

**Status:** every category uses a category-appropriate proxy from real data — GLW 4
livestock, FIRMS VIIRS fire, MapSPAM rice (held since rc26) and WorldCover cropland.
The held maps are genuinely distinct (fire vs cropland total-variation distance 0.67;
rice vs cropland 0.51). The water-regime split from MapSPAM `_I`/`_R` is consumed by
the rice_water_regime_weighted configuration; a 10 m EO rice mask remains an optional
refinement. These are *allocated*
surfaces, not measurements; category totals are exact control totals, and national/provincial totals
are unchanged by the gridding.

## Tier 2 country-specific factors (Phase 5)
The inventory is now Tier 2 for the inputs where Pakistan-specific data exists (full detail and
sources in `docs/tier2_changelog.md`):
- **Dairy share 0.295** from FAOSTAT QCL 2024 (Milk Animals ÷ Stocks), replacing the 0.40 assumption.
- **Animal weights (TAM)** as Pakistan category herd-averages (buffalo 380, camel 480, cattle
  dairy 400 / other 225, sheep 35, goats 32 kg) → corrected N-excretion.
- **Manure-system shares** sourced (dung-cake-burned ~28% routed to Energy; pasture/storage split).
- **Managed-soils EF1 = 0.005 (dry)** kept as the best-supported value for irrigated arid cropland
  (the 2019 dry EF1 was derived largely from irrigated dry fields, PMC9293294); rice N split to
  **EF1FR 0.004**; leaching retained on the ~80% irrigated area despite the dry classification.
- **Rice cultivation period 125 d** (area-weighted Punjab/Sindh); **residue return lowered**
  (straw removed as fodder/fuel, Punjab rice straw burned).
- **EF1 sensitivity pass** (0.005 vs 0.010) brackets the managed-soils estimate (28→40 Mt) and
  explains the FAOSTAT divergence as methodological (2019 disaggregated dry vs 2006 aggregate).

Result for the four core categories: national **223 → 217 Mt CO₂e**. With field-burning and
liming/urea CO₂ added (Phase 8) and the EF4 harmonisation (see `docs/qa_qc.md`), the current
six-category national total is **222 Mt CO₂e** (EF1 sensitivity **222–234 Mt**); provincial and
gridded outputs regenerate from the Tier 2 totals with reconciliation intact.

## Time series 1990–2024 + CRT tables (Phase 6, `timeseries.py`)
The Tier 2 method is driven over 1990–2024 with **FAOSTAT historical activity data** (QCL
livestock stocks + crop area/production; RFN nitrogen fertiliser), built by `fetch_history.py`
into `data/sectors/agriculture/activity/historical/`. The engine reads activity solely from `InventoryData`'s
`.livestock/.crops/.fertilizer` dicts, so the driver mutates those per year and calls
`build_components` with **constant Tier 2 EFs** (activity-driven back-casting). The 2024 point is
the census-based Tier 2 anchor.

- **Trajectory:** 83 Mt (1990) → 222 Mt (2024), CAGR ~2.9 %/yr — driven by livestock-herd growth
  (cattle 14→55 M, buffalo 7→45 M) and rising fertiliser/rice area.
- **CRT-style table** (`crt_AFOLU_table.csv`): UNFCCC AFOLU codes 3.A Enteric, 3.B Manure, 3.C
  Rice, 3.D Agricultural Soils — activity data, implied EF, CH₄/N₂O (kt), CO₂e (kt) for 1990 +
  latest + 2024.
- **Validation** (`timeseries_validation.csv`): engine vs FAOSTAT's own emission series, year by
  year. Same activity data, so divergence isolates the Tier 2 EF choices: enteric tracks at
  **0.99×**, manure ~1.4×, rice ~1.2×; managed soils ~0.5× (the documented 2019-dry vs
  2006-aggregate difference). FAOSTAT multi-source rows are de-duplicated per (year, item) before
  bucketing (a summed-duplicate artifact was caught and fixed during the build).

## Field burning of residues (Phase 8a, `residue_burning.py`)
A 5th category — IPCC 2006 Vol 4 Ch 2 Eq 2.27: `emission(Gg) = mass_burnt(t) · Cf · Gef / 1e6`,
where `mass_burnt = crop production × above-ground residue ratio × fraction burned`, `Cf` = 0.85
(combustion factor), and `Gef` = 2.7 (CH₄) / 0.07 (N₂O) g per kg dry matter. Burned fractions
(`data/burning_params.csv`) are Pakistan-specific: rice 0.30 (Punjab basmati→wheat belt burns
heavily; Sindh removes straw as fodder), wheat/maize 0.05, cotton/sugarcane 0.10. Result ≈ **0.6
Mt CO₂e** — small for GHG (it matters more for air quality), validated against FAOSTAT "Burning -
Crop residues" (0.76 Mt, 0.81×). No double counting: the burned residue is already excluded from
the managed-soils residue-N return (`frac_returned` reflects removal + burning). The category
flows through provincial, gridded and time-series outputs automatically — the category list is
centralised in `run_inventory.CATEGORIES` and imported everywhere.

## Liming & urea CO₂ (Phase 8b, `liming_urea.py`)
A 6th category completing the IPCC **agriculture** sector — CO₂ from carbon-containing soil
amendments (introduces CO₂ as a third gas; GWP = 1):
- **Urea application (IPCC Eq 11.13):** CO₂-C = M_urea × 0.20; CO₂ = C × 44/12. Urea mass is
  **derived from the nitrogen series** — `M_urea = N_total × 0.80 / 0.46` — which reproduces the
  actual NFDC 2024 urea offtake (5.89 Mt) exactly, so the same formula drives every historical
  year of the time series. Pakistan's heavy urea use makes this **≈ 4.3 Mt CO₂** — a real
  category, not negligible.
- **Liming (IPCC Eq 11.12):** CO₂-C = limestone × 0.12 + dolomite × 0.13. Set **≈ 0** because
  Pakistani cropland soils are alkaline/calcareous (liming is for acidic soils); parameter-driven
  so it can be updated if data emerges.
- **No FAOSTAT benchmark:** urea/liming CO₂ are not in FAOSTAT's GT emission series, so the
  time-series validation reports "no-faostat" for this category rather than fabricating a ratio.
- CRT rows **3.G** (liming) and **3.H** (urea). Including this category brings the national
  agriculture total to **~222 Mt**.

## LULUCF land sector (Phase 9, `src/pkinv/lulucf/`)
A **separate sector** from agriculture (reported apart in the BTR; dominated by sinks → signed
values). Tier 1, single-year, CO₂:
- **Forest land (3.B.1):** net afforestation sink ≈ `−(afforested_growing_area × seq_rate × 44/12)`
  ≈ **−3.5 Mt**, calibrated to the Billion Tree (350k ha) + Ten Billion Tree (~290k ha) programmes
  and consistent with FAOSTAT's Forestland. Gross deforestation ≈ 0 (FAO net). FAOSTAT's series
  **flipped from source (+2.4 Mt, 1990) to sink (−3.5 Mt, 2023)** as afforestation took hold.
- **Wetlands — mangrove blue carbon (3.B.4):** ≈ **−0.5 Mt** (Indus-delta restored area ×
  Delta Blue Carbon ~6.5 t CO₂/ha/yr). **FAOSTAT's aggregate omits mangroves**, so the engine net
  is slightly more negative — a real sink, not an error. Mangrove C **stock** ≈ 286 Mt CO₂e (area ×
  IPCC 2013 Wetlands AGB-C 86 + soil-C 471 t C/ha); **arid-climate caveat** — humid defaults likely
  overstate the arid Indus delta (flagged for Tier 2).
- **Cropland/grassland SOC (3.B.2/3):** 0 at Tier 1 (matches FAOSTAT).
- **Net LULUCF ≈ −4 Mt → AFOLU net = agriculture (222) + LULUCF (−4) ≈ 218 Mt CO₂e.** The agriculture
  pipeline is untouched (LULUCF is a parallel track); validation reads the cached FAOSTAT LULUCF series.

## Monte-Carlo uncertainty (Phase 10, `montecarlo.py`)
IPCC **Approach 2** alongside the analytical Approach 1. Each deterministic component is drawn
**lognormally** (IPCC-recommended for emissions — non-negative, right-skewed) from its documented
combined `uncert_pct`, then aggregated to category and national totals. The published national
run uses **100,000 seeded iterations**, because the paper draws a conclusion from a difference
between two runs that is the same size as the Monte Carlo standard error at the sector default
of **10,000** (stdlib `random`; zero new core deps).
- **Mean-preserving** parameterisation (`draw = value·exp(N(0,σ) − σ²/2)`) so the deterministic
  value is the distribution **mean** (IPCC best estimate), avoiding the upward drift that summing
  median-centred lognormals would introduce.
- σ from the 95% half-width: `σ = sqrt(ln(1 + ((uncert_pct/100)/1.96)²))`.
- **Result (agriculture):** P50 ≈ 221 Mt, **90% CI ≈ [190, 261] Mt CO₂e, ±16%** — consistent with
  Approach 1's ±19% (the CSV carries both per category as a cross-check; histogram in
  `uncertainty_distribution.png`).
- Components treated as independent (documented simplification). **Scope = agriculture** (positive,
  lognormal-valid); the signed LULUCF sinks keep their Approach-1 band. Input-level sampling with
  correlations and sensitivity-ranking are future work.

## Known simplifications
- Rice is modelled continuously-flooded (SFw = 1); the intermittent/rainfed water-regime scaling
  factors exist in `emission_factors.csv` but are not applied to the base estimate.
- Residue-N uses default residue:product ratios on production tonnage (no per-ha yield split).
- FSOM (mineralised N from SOC change) = 0 until land-use-change data exists.
- Dung-cake-burned N is removed here and is received by the residential energy sector; the transfer is closed at both ends and asserted with `==`.

(The rice-N split to the rice-specific EF1FR is now applied in `soils.py`, so it is no longer a
simplification. See `docs/completeness.md` for the full notation-key coverage.)
