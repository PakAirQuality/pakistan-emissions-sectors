# Data Acquisition — geospatial proxy datasets

How the best/most-recent gridded datasets are obtained for the emission maps. Some are fetched
automatically; two need a free browser download or key, which you drop into `data/sectors/agriculture/gis/manual/` (the sector data
layout's home for them; `data/gis/manual/` is the retired location and a file left there is
not read).

**Pakistan bounding box (W,S,E,N):** `60.5, 23.5, 77.5, 37.5`.

The pipeline logs which proxy each category used on every `run_gis.py` run, and falls back to the
ESA WorldCover cropland proxy for anything not supplied.

---

## 1. GLW 4 — livestock density  ·  ✅ automatic, no action needed

**Used for:** enteric fermentation + manure management (≈78% of emissions).
Gridded Livestock of the World 4, reference year **2020**, is open on FAO Google Cloud Storage
(CC-BY 4.0, no login). The pipeline reads it directly (windowed) and builds an **emission-weighted
livestock density** proxy (species density × per-head enteric EF).

Provenance (auto-fetched):
`https://storage.googleapis.com/fao-gismgr-glw4-2020-data/DATA/GLW4-2020/MAPSET/D-DA/GLW4-2020.D-DA.{CTL,BFL,SHP,GTS,CHK}.tif`
(cattle, buffalo, sheep, goats, chickens; 10 km, EPSG:4326, animals/km²).

---

## 2. MapSPAM 2020 — crop physical area (incl. rice)  ·  browser download, no login

**Used for:** a proper rice proxy (and a rice water-regime split later). Overrides the cropland
proxy for rice automatically when present.

Steps:
1. Open the Harvard Dataverse dataset: **DOI `10.7910/DVN/SWPENT`**
   (`https://doi.org/10.7910/DVN/SWPENT`) — SPAM 2020, reference year 2020. No login to download.
2. Download the **physical-area GeoTIFF** package and extract the rice file
   `spam2020_v1r0_global_A_RICE_A.tif` (all-technologies physical area, hectares/pixel).
   ACQUIRED (Wave 5, rc26): the held file is the newer **V2r2** release of the same
   product (`spam2020_V2r2_global_A_RICE_A.tif`, byte-hashed in
   `data/sectors/agriculture/gis/manual/RICE_SOURCES.json`), saved as `data/sectors/agriculture/gis/manual/spam_rice.tif`
   with the irrigated/rainfed variants (`RICE_I`/`RICE_R`) held beside it for the
   named water-regime split.
   *(Optional for water regime: `..._RICE_I.tif` irrigated and `..._RICE_R.tif` rainfed.)*
3. Save it as: **`data/sectors/agriculture/gis/manual/spam_rice.tif`**  (global is fine — the pipeline clips to Pakistan).
4. Re-run `python3 -m pkinv.sectors.agriculture.gis.run_gis`. The rice map will now use MapSPAM; the run log will show
   `Rice cultivation <- spam_rice`.

---

## 3. NASA FIRMS — VIIRS active fire (crop-residue burning)  ·  free key or CSV drop

**Used for:** a residue-burning occurrence proxy/map (field burning of residues).

Fastest path — give me a key and I fetch it:
1. Register a free **MAP_KEY** (email only, instant): `https://firms.modaps.eosdis.nasa.gov/api/map_key/`.
2. Paste the key here; I'll pull VIIRS fire for the Pakistan box over the burning seasons.

Or download it yourself:
- API: `https://firms.modaps.eosdis.nasa.gov/api/area/csv/MAP_KEY/VIIRS_SNPP_SP/60.5,23.5,77.5,37.5/10/2025-11-01`
  (`VIIRS_SNPP_SP` = science-quality archive, 2012→present; loop the date in 10-day steps to cover a
  season). Save the combined CSV as **`data/sectors/agriculture/gis/manual/firms_fire.csv`** (columns incl. lat, lon,
  acq_date, confidence, frp).
- Burned *area* (monthly, 500 m) alternative: MODIS **MCD64A1 v6.1** via a free NASA Earthdata Login
  (`https://urs.earthdata.nasa.gov`) through AppEEARS (clip to the box) or Google Earth Engine.

---

## 4. Rice mask / water regime  ·  optional refinement

- **MapSPAM `RICE_I` / `RICE_R`** (from #2) already give an irrigated-vs-rainfed split — the direct
  water-regime proxy for rice CH₄ scaling factors.
- **GloRice v1.0** (Nature Sci Data 2025) — a gridded paddy-rice time series 1961–2021, no login;
  find the repository DOI in the paper's Data Availability section.
- A 10 m rice mask (Sentinel-1/2 phenology) needs a free **Google Earth Engine** account — a
  processing route, not a download. ESA WorldCereal 2021 does **not** include rice.

---

## Drop-in summary

| File you provide | Path | Enables |
|---|---|---|
| MapSPAM rice GeoTIFF | `data/sectors/agriculture/gis/manual/spam_rice.tif` | rice proxy (replaces cropland for rice) |
| FIRMS VIIRS CSV | `data/sectors/agriculture/gis/manual/firms_fire.csv` | residue-burning occurrence proxy/map |

Anything absent falls back to the ESA WorldCover cropland proxy. GLW livestock is always automatic.
Re-run `python3 -m pkinv.sectors.agriculture.gis.run_gis` (or `run_all.py`) after adding files.

---

## Outstanding: jet fuel for the aviation reconciliation (1A3a)

**The gap.** Both IPCC 2006 Vol 2 Ch 3.6 and the EMEP/EEA Guidebook require a bottom-up
aviation estimate to be reconciled against fuel sales — EMEP §3.4.2: "the total estimated
fuel use for domestic aviation must be compared with sales statistics… If the estimated
fuel use deviates from the direct observations, the main parameters used for estimating
the fuel must be adjusted in proportion." The aviation sector currently has no such
check, which is the first thing a reviewer will look for. It is a data-acquisition task,
not a coding one, and should be closed before submission rather than before the next
sector.

**Where the series lives, in order of usefulness:**

| Source | What it gives | Access |
|---|---|---|
| **HDIP Pakistan Energy Yearbook** | Product-wise JP-1 by year *and* by sector; back editions cover FY2006 on. The authoritative series. | Paid / on request: `eyb@hdip.gov.pk`, form at hdip.gov.pk/pakistan-energy-yearbook |
| **OCAC** | The source feeding both HDIP and the Economic Survey — one layer closer to the data | Members-only portal; responds to direct data requests |
| **Pakistan Economic Survey, energy chapter** | JP-1 in 000 MT, *recent editions only*. FY2024-25 Fig 14.4 gives JP-1 511.1 and **JP-8 91.4 separately**. Table 14.7 gives OCAC sectoral consumption incl. an "Overseas" line. | **Free**, verified working: finance.gov.pk/survey/chapter_25/14_Energy.pdf — needs a browser user-agent, returns 403 to bare curl |
| **EIA international** | Jet fuel consumption, thousand bbl/day, 1980–2024 (2023 = 16.62, peak 20.44 in 2019) | Free; modelled/reported rather than national statistics, so a cross-check not a substitute |

**Two things worth knowing before using it.**

The Economic Survey separates **JP-8 (military) from JP-1 (civil)**. That is directly
useful beyond the reconciliation: the CAA digest's "non-commercial" movement column mixes
general aviation, training circuits and military movements at the joint-use airfields with
no way to separate them, and IPCC reports military aviation under 1A5b rather than 1A3a.
A JP-1/JP-8 split is the only route we have found to that boundary.

The published JP-1 figure is **total fuel uplifted in Pakistan**, covering domestic and
international together. It cannot be compared directly against the domestic-only estimate
in `outputs/aviation_totals_*.csv` without first apportioning it. The "Overseas" line in
Economic Survey Table 14.7 may be the lever, but what it includes is unconfirmed.

Older editions do **not** carry the product breakdown — the FY2020-21 chapter has sectoral
totals only — so the free route yields recent anchor years, not a 2006–2023 series. Even
two or three anchor years would be enough to compute and publish the reconciliation ratio.

---

## Residential fuel combustion (1A4b) — what is open

The sector is built and reports 28.2 Mt CO2e for FY2023-24. The firewood item below is
resolved; the others remain open in descending order of how much a fix would change the
answer.

### 1. Firewood — RESOLVED (August 2026): HIES microdata is the primary quantity

This entry used to claim there was no Pakistani national firewood quantity anywhere in the
public record we had searched. There was: PBS posted the full HIES 2024-25 **microdata**
(and the 2018-19 round) as free SPSS downloads, and the consumption module records
physical firewood kilograms per household across four acquisition routes. The
design-weighted national total is 23.1 Mt air-dry wood (2024-25), reproduced within 6% by
the independent 2018-19 sample and within 7% by FAOSTAT's moisture-matched equivalent.
The survey is now the sector's primary firewood activity at 35% uncertainty; FAOSTAT is
demoted to the structural scenario `firewood_faostat`. See `scripts/ingest_hies.py`,
`pkinv.sectors.residential.hies` and `outputs/residential_hies_comparison_2024.csv`.

Still worth acquiring on this stream:

| Source | What it would add | Access |
|---|---|---|
| **HDIP Pakistan Energy Yearbook** | A supply-side biomass line to test the survey against | Paid / on request: `eyb@hdip.gov.pk` |
| **Census 2023 district cooking-fuel tables** | Prevalence geography for the district downscale | Free, PBS |

### 2. LPG sectoral split — published only as a bar chart

OGRA's *State of the Regulated Petroleum Industry* gives sector-wise LPG consumption in
**Figure 5.2 with no corresponding table**, so the 0.35 domestic share in
`data/residential_params.csv` is read off the chart and carries 25% uncertainty. OGRA's
"Commercial" bar also includes small catering and shop use that some inventories treat as
residential, so the household share is more likely above 0.35 than below it. Region-wise
LPG (Figure 5.1) has the same problem and is why LPG falls back to population geography.

**Ask OGRA for the underlying table.** It plainly exists — they plotted it.

### 3. Gas heating value — the same gross-versus-net trap as the power sector

`gas_mmcf_to_TJ` converts at 1,000 Btu/scf gross × 0.90, the IPCC net factor. Pakistani
gas is metered and billed gross; every IPCC Table 2.5 factor is net; getting it backwards
inflates residential gas CO2 — the sector's largest stream — by about 10%. The assumed
1,000 Btu/scf is the pipeline sales-gas specification, not a measured national average.

**SNGPL and SSGCL both publish annual average heating values in their annual reports**,
and OGRA's tariff determinations state the BTU basis explicitly. Either would replace the
assumption with a measurement. This is the same unresolved risk `data/power_params.csv`
records for `toe_to_tj`, and one document may well close both.

### Not blocking, but worth recording

Household **coal and charcoal** are marked NE. OGRA's sector-wise coal table reports a nil
household figure for FY2023-24, which is what justifies the key, but brick-kiln and
domestic coal are hard to separate in Pakistani statistics and the nil is not convincing.

**Captive diesel generator sets** in homes are absent from every source. Pakistan's own
BUR-1 flags this in the same words: "this source is scattered and a systematic collection
could not be carried out … the fuel consumption in these private generator sets could be
substantial."

---

## Shipping (1A3d) — why it is not built, and the trap to avoid

Shipping was the last sector believed to be unblocked. It is not. **There is no marine
fuel figure for Pakistan at any tier**, and the line that looks like one is not one.

### The trap: OGRA's "Overseas/Export" line is cargo, not bunkers

An earlier note in this document flagged the "Overseas" line of Economic Survey Table 14.7
as a possible lever for the aviation bunker split, with its contents "unconfirmed". They
are now partly confirmed, and for shipping the answer is negative.

The Economic Survey text states that the overseas sector "includes bunker sales **and
other exports**". OGRA's Table 2.1 gives the product split for FY2023-24: furnace oil
1.01 Mt, aviation fuels 0.28 Mt, HSD ~0.00. The furnace-oil component is **exported cargo,
not fuel bunkered at Pakistani ports**:

- Pakistan exported **1.11 Mt of furnace oil in calendar 2024** (LSEG, reported Nov 2025) —
  the same quantity as the entire OGRA "Overseas/Export" FO line.
- The cause is domestic, not maritime. Furnace oil for power generation collapsed from
  1,668 kt (FY2023) to 607 kt (FY2024) to 116 kt (Jul–Mar FY2025) as generation shifted to
  RLNG, Thar coal and renewables. Refineries exported the surplus to stay viable. The
  cargoes went to Southeast Asia and the Middle East.
- Modern bunkering at Karachi launched in 2026 through Vitol, targeting 500–600 kt/yr
  across Karachi, Port Qasim and the anchorages — a plan for the future, not a record of
  the past. This used to read "Pakistan had **no formal bunkering market** during any
  inventory year", and that sentence was doing work it cannot do: a market's absence is not
  the absence of fuel delivered to a vessel, and Pakistan's own first Biennial Transparency
  Report books **0.0393 Mt CO₂ — 0.040 Mt CO₂e — of international marine bunkers for
  2020–21** (`sources/UNFCCC/btr1_2024.txt` line 843). So the memo item is small, not
  empty, and the national submission is the only anchor for it that exists.

Building 1A3d on that line would report roughly **3 Mt CO₂ of emissions that did not occur
in Pakistan**, from fuel that IPCC would not attribute to Pakistan in any case. The rows
are in `docs/completeness.md` under 1.A.3.d so the reasoning is visible where a compiler
would look for it.

The aviation half of the same line points the other way and is worth pursuing: Pakistan
**imports** JP-1 rather than exporting it, so the 0.28 Mt of aviation fuel in "Overseas" is
much more likely to be genuine international bunkers. That is a live lead for the jet-fuel
reconciliation in the section above.

### What the workbook has, and what 1A3d would need

`Shipping/Sea Port data.xlsx` in the data repository holds port calls, gross registered
tonnage (Karachi, two years only), cargo tonnage and container throughput. It contains no
fuel of any kind, no time-in-mode, no vessel power, and no domestic/international split.
The two ports do not overlap in any single year with comparable metrics, and the Karachi
2022 rows are on a different unit basis and appear to be a partial year.

| Source | What it would give | Access |
|---|---|---|
| **HDIP Pakistan Energy Yearbook** | Product-wise by sector; the only plausible home for a national marine bunker series | Paid / on request: `eyb@hdip.gov.pk` |
| **OCAC** | The sectoral petroleum data feeding OGRA and the Economic Survey — a marine category would have to originate here | Members-only; responds to direct requests |
| **IEA / UN Energy Balances** | "International marine bunkers" for Pakistan — the memo control total and the benchmark | Free (UN), subscription (IEA) |
| **KPT Year Book / PQA** | Vessel calls and GRT back-series, for a Tier 3 port inventory | Free: kpt.gov.pk/Downloads, pqa.gov.pk |

A Tier 3 vessel-activity estimate is the fallback if no fuel figure ever appears, but it
needs a GRT series for both ports and time-in-mode assumptions that no Pakistani source
publishes. That is a different and much larger piece of work than the other sectors, and
it would produce a number with no fuel figure to reconcile against — the opposite of how
every sector here is built.

---

## Domestic wastewater (4D) — not estimated, and the gap is one table

Solid waste disposal (4A) is built. Wastewater is not, and it is worth being precise about
why, because almost everything it needs is already here.

**In hand:** the 134-district population panel (`data/sectors/waste/activity/population_district.csv`),
IPCC's maximum methane-producing capacity Bo = 0.6 kg CH₄/kg BOD (Vol 5 Ch 6 Table 6.2),
the regional BOD default of 40 g/person/day for "Asia, Middle East, Latin America"
(Table 6.4 — note India is listed separately at 34, which is arguably the closer analogue
and is the obvious sensitivity), and the protein-consumption route to N₂O via FAOSTAT.

**Correction to an earlier version of this note:** it said the protein data was "already
cached in `data/faostat_cache/`". It is not. That cache holds Emissions_Totals, Forestry,
QCL and RFN; per-capita protein supply is in the **Food Balance Sheets** domain, which has
never been fetched. It is a one-command addition using the bulk-zip pattern already in
`scripts/ingest_residential.py`, but today the N₂O half of 4D has no input at all.

**Missing: the split of the population between discharge pathways.** IPCC Table 6.3 sets
the methane correction factor by pathway, and the spread is not a detail:

| Pathway | MCF |
|---|---|
| Flowing sewer (open or closed) | 0.0 |
| Sea, river and lake discharge | 0.1 |
| Latrine (dry climate, low water table) | 0.1 |
| Anaerobic shallow lagoon | 0.2 |
| Septic system | 0.5 |
| Stagnant sewer (open and warm) | 0.5 |
| Anaerobic deep lagoon / reactor | 0.8 |

Pakistani urban drainage is largely open, warm and stagnant, which points at 0.5; rural
sanitation is latrines and septic tanks, which points at 0.1–0.5. Assuming the mix would
choose the answer rather than estimate it — a factor of five sits between the plausible
end-points — so the category is marked **NE** instead.

**What would close it:** the PBS *Pakistan Social and Living Standards Measurement* (PSLM)
household survey tabulates sanitation type — flush to sewer, flush to septic, flush to open
drain, pit latrine, none — by province and by urban/rural. That single table, on a stated
denominator, is the whole requirement. WHO/UNICEF JMP publishes a coarser version of the
same thing and would serve as a cross-check. Secondhand figures circulate (PBS 2021: 83%
flush toilets, of which 27% sewerage, 21% septic, 17% pit latrine, 18% open drain) but it is
not clear from the citing sources whether those percentages are of households or of the 83%,
and that ambiguity is exactly the kind that silently doubles a national estimate.

This is the same acquisition family as the residential firewood and LPG gaps: PSLM would
close household fuel use and household sanitation in one request.

---

## Air-pollutant layers — what is covered and what is not

The co-emission layers report mass (kt) and never enter the greenhouse-gas totals.
Agriculture, waste, aviation, road transport, residential biomass and power have one.
Railways has one too since the August 2026 rounds (outputs/railways_air_pollutants_2024.csv, EMEP/EEA ch 1.A.3.c).

**What the residential layer shows, and why it was worth building.** Household solid fuel is
a minor greenhouse-gas sector — 7% of the national total — and the dominant particulate
source:

| Source | PM₂.₅ | Black carbon |
|---|---:|---:|
| Residential biomass (dung + firewood) | **461 kt** | **31 kt** |
| Road transport, on-road | 23 kt | — |

That ratio is the reason the two layers were built first, and it matches the published
picture for Pakistan and South Asia generally.

**Railways is the one remaining sector without a layer, and the historical blocker was the
EEA's own delivery.** The locomotive factors live in EMEP/EEA Guidebook chapter 1.A.3.c
Railways, which Andreae's field-measurement compilation does not cover (it is a
biomass-burning compilation, and a locomotive is not a fire) and AP-42 Chapter 3.3 does not
substitute for (large stationary diesels, not locomotives). The EEA long served its
guidebook chapters behind a landing page that returned HTML rather than the PDF — that
retrieval failure is what blocked both the power and railway layers. Both layers have
since been built: the railway chapter was acquired
(`sources/EMEP/emep_eea_2023_1a3c_railways.pdf`) and `air-railways` is CLOSED in
`data/data_gaps.csv` - this section is retained as the record of the retrieval
failure and its resolution, not as an open item.

For power specifically there is a second, Pakistan-shaped gap: SO₂ from oil- and coal-fired
generation is driven by the sulphur content of the fuel, and NEPRA publishes fuel quantities
but not fuel sulphur. Furnace-oil and Thar-lignite sulphur specifications would close it.

**Residential fossil fuels are also uncovered** for the same guidebook reason — piped gas,
LPG and kerosene emit NOx and a little particulate, and none of it is in the residential
layer. The omission biases NOx low and barely touches PM₂.₅ or BC, which is what that layer
exists to quantify.

---

## Fugitive oil and gas (1B2) — built, and unusually uncertain

The sector reports **3.81 Mt CO₂e central against a published range of 0.76–35.36 Mt**. That
span is not a defect of this implementation; it is what IPCC Tier 1 can say about fugitive
emissions in a developing country, and it is worth being explicit about why.

Every factor in IPCC Vol 2 Ch 4 Table 4.2.5 is a **range**, and the ranges are wide because
IPCC is declining to guess how leaky a given country's infrastructure is. Gas-production
fugitive CH₄ spans a factor of 63; onshore oil fugitives span a factor of **forty thousand**.
This inventory therefore takes the geometric mean of each range as its central value and
derives the uncertainty from the range itself rather than assuming one — and publishes both
bounds, because a reader who leans on the central value without seeing the span will be
misled.

EDGAR puts Pakistani fuel exploitation at 17.54 Mt CO₂e, **4.6× the central estimate and
comfortably inside the range**. The two are not in conflict. Tier 1 cannot distinguish them.

### What would actually narrow it — measurement, not better defaults

| Source | What it gives | Access |
|---|---|---|
| **VIIRS Nightfire / World Bank GGFR** | Satellite-measured flared gas volumes for Pakistan, annually, in bcm — the only *measured* flaring figure that exists | Free: `eogdata.mines.edu/products/vnf/` |
| **OGRA, State of the Regulated Petroleum Industry** | The unaccounted-for-gas line, which drives transmission and distribution — the largest omission inside 1B2 | Free PDF, already source E1 here and already used for three other numbers |
| **Climate TRACE `fossil-fuel-operations`** | Observation-driven oil-and-gas production, refining and transport for Pakistan | Free API; the held pulls live under `sources/` (aviation, waste and power each read their own extract) |
| **Pakistan Economic Survey energy chapter** | Brings production to the current fiscal year, closing the FY2019-20 vintage gap | Free; verified working (browser user-agent) |

The OGRA fetch is the best value: it closes the distribution term here, the LPG bar-chart
gap in residential, and the gas heating-value question in one document.

### What is not estimated inside 1B2

Refining, well drilling, testing and servicing (Tier 1 wants throughput and well counts;
the Year Book carries production only), and gas transmission and distribution. All are NE
rows in `docs/completeness.md` rather than silent omissions.
