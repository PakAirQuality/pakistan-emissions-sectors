# Source Inventory — Pakistan Agricultural GHG (Priority-4)

Verified June 2026. Access status: **Open** (free download), **Open (browser)** (viewable but
hotlink/automated fetch blocked), **Request** (form/fee/permission), **Flag** (no open data
product — proxy or benchmark only).

## Pakistani primary sources

| # | Source | Agency | Provides | Latest | Level | Access | URL |
|---|---|---|---|---|---|---|---|
| 1 | 7th Agricultural Census 2024 | PBS | Livestock by species (goats 95.8m, cattle 55.8m, buffalo 47.7m, sheep 44.5m, asses 4.8m, camels 1.5m); farms; cultivated/irrigated area; crop area shares; fodder; machinery | Released Aug 2025 | National + District | Open (PDF+Excel) | https://www.pbs.gov.pk/agriculture-census/ |
| 2 | Pakistan Economic Survey 2024-25, Ch.2 Agriculture | Ministry of Finance | Crop area/production/yield; livestock **estimates**; sector growth | Annual | National | Open (browser) | https://www.finance.gov.pk/survey/chapter_25/ |
| 3 | Agriculture Statistics of Pakistan | PBS (district via MNFSR) | Crop area/production/yield time series | Ongoing | National + Province (District via MNFSR) | Open | https://www.pbs.gov.pk/agriculture |
| 4 | Annual Fertilizer Review 2024-25 | NFDC / MNFSR | N/P/K offtake by product, crop-wise NPK, provincial splits | 2024-25 | National + Province | Open (PDF, http) | https://mnfsr.gov.pk/SiteImage/Misc/files/AFR2024-25.pdf · http://www.nfdc.gov.pk/stat.html |
| 5 | Crop Reporting Services (provincial) | Punjab/Sindh/KP Agriculture Depts | Crop-cutting area + production for ~12 major crops; feeds PBS national | Seasonal | Tehsil/District → Province | Open / Request | https://crs.agripunjab.gov.pk/ · https://crs.kp.gov.pk/ |
| 6 | SUPARCO crop monitoring / LULC | SUPARCO | Satellite crop masks, area forecasts (wheat/rice/cotton/sugarcane/maize), LULC atlases | Ongoing (new sats 2025-26) | National (grid) | **Flag** (request-based; no open portal) | https://suparco.gov.pk/ |
| 7 | Climate data | PMD — Climate Data Processing Centre | Rainfall/temperature (3-hourly → annual); climate normals | Ongoing | Station | **Request** (form + fee) | https://cdpc.pmd.gov.pk/ · https://portal.pmd.gov.pk/ |

**Key caveats**
- **Livestock counts:** the 2024 Census is the authoritative headcount. The Economic Survey's
  livestock figures are *modelled* from 1996/2006 inter-census growth rates — use them only as
  a cross-check, not as primary activity data.
- **No standalone livestock census** newer than 2006 exists; livestock now rides on the 2024
  Agricultural Census — for the national headcount **and** the spatial split: province shares
  (`province_shares.csv`) and EF-weighted district counts (`livestock_district_2024.csv`, 100/118
  districts; GLW-2020 proxy fallback for boundary-vintage gaps) both come from the 2024 census (was 2006).
- **Dairy/non-dairy cattle and manure-system shares** are not in the census. The MMS split is Tier-2/
  FAOSTAT-consistent (primary); FAO **GLEAM 3.0** (South Asia) is integrated as a *cross-check* only —
  its dry-lot-heavy split raises manure direct N₂O 2.6× (23→61 Gg, ~2× FAOSTAT), a GLEAM-MMS-vs-IPCC-EF₃
  taxonomy mismatch surfaced as a flagged uncertainty (`data/gleam_mms.csv`, `mms_sensitivity.py`), not
  adopted. GLEAM publishes no comparable in-milk fraction, so the FAOSTAT dairy share (0.295) is retained.

## Global / open backup sources

| # | Source | Provides | Ref year | Resolution / level | Access | URL |
|---|---|---|---|---|---|---|
| 8 | FAOSTAT | QCL (production/headcounts); Emissions domains (enteric, manure, rice, synthetic fertilizers); RFN (fertilizer by nutrient, updated Jul 2025) | to ~2023 | National | Open (API + bulk CSV) | https://www.fao.org/faostat/en/#data · https://bulks-faostat.fao.org/ |
| 9 | Gridded Livestock of the World (GLW4) | Cattle/buffalo/sheep/goats/poultry distribution | 2024 release, ref 2020 | ~10 km (5 arc-min) GeoTIFF | Open | https://www.fao.org/livestock-systems/global-distributions/en/ · https://dataverse.harvard.edu/dataverse/glw |
| 10 | GLEAM 3.0 | Livestock population, products, emissions, intensities by species × production system | ref 2015 | National | Open (dashboard) | https://www.fao.org/gleam/dashboard/en/ |
| 11 | EDGAR (EDGAR_2024_GHG) | Agriculture-sector national totals + gridmaps (enteric, manure, ag soils, residue burning, indirect N₂O) | to ~2021 | National (xlsx) + 0.1°×0.1° NetCDF | Open | https://edgar.jrc.ec.europa.eu/dataset_ghg2024 |
| 12 | ESA WorldCover | 10 m land cover incl. cropland class | 2020/2021 v200 | 10 m | Open (CC-BY-4.0) | https://esa-worldcover.org/en/data-access |
| 13 | SoilGrids | Soil properties (SOC, texture) | current | 250 m | Open | https://soilgrids.org/ |
| 14 | WorldClim 2.1 | Temperature, precipitation, climate normals | current | 30 arc-sec | Open | https://www.worldclim.org/ |
| 15 | Sentinel-2 / Landsat | Surface reflectance for crop & water-regime mapping | ongoing | 10 m / 30 m | Open | https://dataspace.copernicus.eu/ · USGS/GEE |
| 16 | TROPOMI / Sentinel-5P | NO₂+SO₂ power-plant cross-check **implemented** (pkinv.sectors.power.tropomi_crosscheck, from the daily 0.1° archive on the project SSD — GEE L3 composites, 2020–2026): Thar ramp, Hub decline, the Sahiwal FY2021 arbitration, rank agreement. The CH₄ (XCH₄) fugitives-hotspot cross-check from the same archive remains future work; not activity data in either use | 2020–present | 0.1° (grid) | Open (GEE) | https://sentinels.copernicus.eu/web/sentinel/missions/sentinel-5p |
| 17 | Climate TRACE (v7) | **Independent benchmark** — Pakistan agriculture emissions by subsector (enteric, manure, rice, fertiliser, fires, ag-soils); observation-driven, AR6 GWP. A 3rd validation axis beside FAOSTAT/EDGAR | 2023–2024 | National (+ asset) | Open (API) | https://api.climatetrace.org · https://climatetrace.org/data |
| 18 | Cui et al. 2021 (Nature Food) | **Empirical N₂O EF adjudicator** — 1,507 field observations → crop-specific direct-N₂O EFs. PAK crop-weighted EF ≈ 0.0055, anchoring the arid EF1=0.005 over FAOSTAT's flat 0.010 (managed soils) | 2021 (field DB) | Gridded 5-arcmin + obs | Open (figshare) | https://doi.org/10.1038/s43016-021-00384-9 · https://doi.org/10.6084/m9.figshare.14844069 |

**Flags to confirm at download**
- **GLW4 DOI:** the Harvard Dataverse collection is still labelled "2015"; cite the FAO 2024 /
  ref-2020 grids specifically and confirm the exact DOI when downloading.
- **SUPARCO / PMD** are not open-data products — treat SUPARCO as a crop/water-regime proxy and
  validation layer, and budget for a PMD data request for station climate.

## How sources map to the Priority-4 categories

| Category | Primary activity data | PK source | Global backup |
|---|---|---|---|
| Enteric fermentation (CH₄) | Headcounts by species | PBS Census 2024 (#1) | FAOSTAT QCL (#8), GLW4 (#9) |
| Manure management (CH₄/N₂O) | Headcounts + temperature + MMS shares | PBS Census (#1) + PMD (#7) | FAOSTAT (#8), GLEAM (#10) |
| Rice cultivation (CH₄) | Rice area by water regime | PBS Ag Stats (#3) + provincial CRS (#5) | FAOSTAT (#8); SUPARCO/Sentinel-2 proxy (#6, #15) |
| Managed soils (N₂O) | Synthetic + organic N, crop areas; **direct-N₂O EF1 anchored by Cui 2021 (#18)** | NFDC (#4) + PBS Census (#1) | FAOSTAT RFN (#8) |

## Energy-sector sources (added with residential fuel combustion, 1A4b)

| # | Source | Agency | Provides | Latest | Level | Access | URL |
|---|---|---|---|---|---|---|---|
| E1 | State of the Regulated Petroleum Industry | OGRA | Sector-wise gas consumption by utility (Table 3.31); cumulative domestic gas **connections** by province (Table 3.26); sectoral petroleum products incl. kerosene (Table 2.1, source OCAC); LPG supply (Table 5.1) | FY2023-24 | National + Province | Open (PDF) | https://www.ogra.org.pk/petroleum-industry-reports |
| E2 | Pakistan Economic Survey, energy chapter | Ministry of Finance | Sector-wise gas (Table 14.9) and petroleum (Table 14.7); product-wise POL (Fig 14.4) | Annual | National | Open (browser) | https://www.finance.gov.pk/survey/chapter_25/14_Energy.pdf |
| E3 | FAOSTAT Forestry Production and Trade | FAO | Wood-fuel removals, m3 | 1961-2024 | National | Open (bulk zip) | https://bulks-faostat.fao.org/production/ |
| E4 | Pakistan's First Biennial Update Report (BUR-1) | Ministry of Climate Change / UNFCCC | Pakistan's own 1A4 breakdown for FY2017-18: residential 19.0, agriculture 11.3, commercial 3.8 Mt CO2e; states the biomass memo convention | 2022 (FY2017-18) | National | Open (PDF) | https://unfccc.int/documents/ |

**Key caveats**

- **OGRA over the Economic Survey for gas.** Both publish sector-wise gas, but the Survey's
  table is July–March only, and domestic gas demand peaks in winter — a nine-month figure
  is not a full year scaled down, it is the wrong shape. OGRA Table 3.31 is a full fiscal
  year for the whole country and is what the sector uses.
- **Connections, not people, for gas geography.** OGRA Table 3.26 gives metered domestic
  consumers by province. Balochistan has 5.5% of Pakistan's population and 2.8% of its gas
  connections; a population proxy would have got that stream badly wrong.
- **BUR-1 is a benchmark, not an input.** Nothing is taken from it. It supplies the
  order-of-magnitude check in `tests/test_residential.py` and confirms that this inventory
  and Pakistan's official submission use the same biomass memo convention.

## Railways (added with IPCC 1A3c)

| # | Source | Agency | Provides | Latest | Level | Access | URL |
|---|---|---|---|---|---|---|---|
| R1 | Pakistan Railways Year Book | Ministry of Railways | Principal Statistics: fuel consumption (HSD in thousand litres, furnace oil), train-kilometres, traffic, locomotives; divisional freight loading | FY2023-24 | National (divisional for freight) | Open (PDF) | https://www.pakrail.gov.pk/yearbook.aspx |
| R2 | PSO High Speed Diesel Material Safety Data Sheet | Pakistan State Oil | HSD specific gravity 0.83-0.86 at 16 C — the litres-to-mass conversion | — | National | Open (PDF) | https://psopk.com/files/product_and_services/aviation_marine_and_exports/pdf/hsd.pdf |

**Key caveats**

- **The series has holes, and they are left as holes.** The FY2017-18, FY2018-19,
  FY2019-20, FY2021-22 and FY2024-25 editions are scanned images with no text layer, so
  FY2018 and FY2019 are absent from the time series. Interpolating them would invent
  activity data for a sector whose whole claim is that it reports metered purchases.
- **Furnace oil changed reporting basis mid-series** — "Tonnes" through the FY2020-21
  edition, "Liters/thousand" from FY2022-23, with no announcement. The stream is under
  0.001 Mt CO₂e on either reading and a test pins that it cannot matter, but the published
  label is preserved per row in the activity file.
- **The Year Book's own unit column is misaligned** in the FY2023-24 edition: Persons
  Employed is labelled "Tonne" and Cost of Employees "No.". Read the table from the page,
  not from a text extraction.
- **This inventory reports railways an order of magnitude below Pakistan's BUR-1** (0.39 vs
  4.06 Mt CO₂e). The operator's metered fuel gives 4.0 litres per train-kilometre; BUR-1's
  implied fuel would need 46. See `src/pkinv/sectors/railways/traction.py`.

## Fugitive oil and gas (added with IPCC 1B2)

| # | Source | Agency | Provides | Latest | Level | Access | URL |
|---|---|---|---|---|---|---|---|
| F1 | Pakistan Statistical Year Book | PBS | Table 7.2 mineral production incl. crude oil (000 bbl) and natural gas (MMCFT), FY2010-11 onward; Table 7.3 the same **by province** | 2020 edition (FY2019-20) | National + Province | Open (PDF), inside `Provincial Statistics/National-*.zip` in the data repository | https://www.pbs.gov.pk/ |

**Key caveats**

- **These archives had never been opened.** The data repository has carried ~1.4 GB of
  provincial and national statistical yearbooks since it was created, and its own README
  guessed they were "the most likely source for the industrial-fuel tables". Table 7.2 is
  sourced to the Directorate General of Petroleum Concessions, Petroleum Division.
- **The only measured provincial split in this inventory.** Every other sector allocates a
  national total by a proxy. Table 7.3 reports production province by province, and
  fugitive emissions occur where production does. Oil and gas need separate rows: Sindh has
  64% of the gas, Khyber Pakhtunkhwa 48% of the oil.
- **The two tables round differently.** 7.2 gives crude oil in thousands of barrels
  (28,091), 7.3 in whole barrels (28,090,543). The 457-barrel gap is rounding and is pinned
  by a test so it cannot later be mistaken for a real divergence.
- **Vintage.** FY2019-20 is the newest the 2020 edition carries, against 2022–2024 for the
  rest of the inventory. A free Economic Survey or OGRA fetch would bring it current.
- **The factors, not the activity, are the problem here** — see `DATA_ACQUISITION.md`.

## Industrial processes (added with IPCC 2A1)

| # | Source | Agency | Provides | Latest | Level | Access | URL |
|---|---|---|---|---|---|---|---|
| I1 | Punjab Statistical Pocket Book | Punjab Bureau of Statistics | Table 16.3 Production of Major Manufactured Items: cement, fertilisers, soda ash, caustic soda, sugar, paper — Pakistan **and** Punjab | 2025 (FY2023-24) | National + Punjab only | Open (PDF), inside `Provincial Statistics/Punjab-*.zip` | http://bos.punjab.gov.pk/ |

**Key caveats**

- **A provincial pocket book carrying national figures** is why this table matters: it
  publishes Pakistan totals alongside Punjab's, so it supplies the control total and one
  measured provincial anchor at once.
- **The activity is cement; the emission is at clinker.** No Pakistani source publishes
  clinker production, so the ratio is assumed and it dominates: 18.72 Mt at IPCC's 0.75
  blended default against 23.72 Mt at its 0.95 all-portland default. Both are published.
  APCMA (`apcma.com`) publishes dispatches and would also give a time series; PBS's Quantum
  Index of Manufacturing carries the LSM series in tonnes.
- **Only Punjab is measured**, so the other three provinces are split by limestone
  production from the Statistical Year Book — physically motivated, since a cement plant is
  built at its quarry, but still a proxy. It puts 35% of national cement in Khyber
  Pakhtunkhwa.
- **Process CO₂ only.** The fuel these kilns burn is 1A2 and is not in this inventory.

## Domestic wastewater (added with IPCC 4D1)

| # | Source | Agency | Provides | Latest | Level | Access | URL |
|---|---|---|---|---|---|---|---|
| W1 | JMP household country file | WHO/UNICEF Joint Monitoring Programme | Population shares by sanitation pathway — sewer, septic, latrine, unimproved, open defecation — national **and urban/rural** | 2023 | National + urban/rural | Open (XLSX) | https://washdata.org/data/country/PAK/household/download |
| W2 | FAOSTAT Food Balance Sheets | FAO | Per-capita protein supply (g/capita/day), the N₂O driver | 2023 | National | Open (bulk zip) | https://bulks-faostat.fao.org/production/ |

**Key caveats**

- **JMP settled the ambiguity that kept this category unestimated.** Secondhand PBS figures
  circulate as "83% flush toilets, of which 27% sewerage…" without saying what the
  percentages are *of*. JMP publishes on a population denominator, and the urban and rural
  rows each sum to 100%.
- **The urban/rural contrast is the point.** Sewer coverage is 62.6% urban against 8.8%
  rural, and sewered flow carries a five-times-higher methane correction factor than a
  rural latrine — so a national average would misstate a country that is 62% rural.
- **The sewer MCF is the judgement that decides the category**, and it is unresolved rather
  than settled: 24.28 Mt at IPCC's stagnant-open-warm-sewer 0.5, 15.45 Mt at the
  river-discharge 0.1. Pakistani drains are open, warm and untreated, which argues for 0.5;
  EDGAR's waste total sits closer to 0.1. Both are published.

## Power-plant workbooks (2026)

Two Excel workbooks under `sources/Power Plants/`, added after the sector was first built and
consolidating material the earlier sources did not carry.

| Sheet | What it provides | Used for |
|---|---|---|
| `OGRA_captive_gas` | Metered captive-power gas FY2016–24, MMCFD, with the SNGPL/SSGCL split, a verified/provisional status flag and per-year notes | **The activity datum for 1A2 captive generation.** FY2021 is provisional (read by OCR from a chart label in an image-scan edition) and FY2023's SSGCL figure was restated upward in the following edition — both flagged in `data/sectors/power/activity/captive_gas.csv` rather than smoothed |
| `CPP_master` | 1,105 deduplicated captive plants: SNGPL fleet (480), SSGC geocoded list (557), NEPRA licensees (83), with metered gas, capacity, industry and coordinates | **The measured provincial split for captive generation.** Sums to 288.01 MMCFD against OGRA's independently published 288 — the check that the register and the national total describe the same fleet |
| `Grid_power_plants` | Grid thermal and non-thermal plants, annual generation 2015–24 by province and district | **The `power_generation` provincial proxy**, replacing a capacity database that this repo had already flagged as its weakest element and correctly predicted would overstate Khyber Pakhtunkhwa |
| `Emission_factors`, `Emissions_timeseries`, `*_emissions_calc` | Air-pollutant factors in kg/MWh and computed emissions 2015–24 | **Not used.** The factors are generation-based and 77 of 96 trace to "typical literature range … retained from original workbook" rather than a table; four are flagged unsourced placeholders. The air layer is re-derived from AP-42 on a fuel basis instead — see `sectors/power/air_pollutants.py`. Its CO₂ rows are also unused, being kg/MWh via an assumed heat rate, which is the assumption the fuel-based GHG layer exists to avoid |

Interesting convergence worth recording: the workbook's grid SO₂ for 2024 (253.2 kt) and this
inventory's AP-42-derived uncontrolled figure (254.4 kt) agree within 0.5% despite different
factors, a different activity basis and a different year. That is a coincidence of assumptions
rather than corroboration, but it is the kind of coincidence worth noticing.
