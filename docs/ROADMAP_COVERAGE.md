# Roadmap Coverage — Desk-Based Roadmap vs. the Built System

This maps the *Desk-Based Roadmap for an Agricultural GHG Inventory and Geospatial Emission Maps
for Pakistan* against what actually exists in this repository. Legend: ✅ Done · 🟡 Partial · ⬜ Not yet.
Each row cites where the evidence lives. No new computation — an audit of coverage.

## Bottom line

The built system already realises the substantial majority of the roadmap's **desk-based Phases
0–3**. The open items are precisely the ones the roadmap itself defers to later/fieldwork, or that
need access-gated satellite/livestock datasets — plus a data-vintage refresh to the newer 2025-26
Economic Survey. Nothing in the roadmap's core method (top-down control + bottom-up allocation +
mass-balance reconciliation, the IPCC formulas, Monte-Carlo) is missing.

## Scorecard

| Area | Status | One-line |
|---|---|---|
| A. Feasibility premise & sequencing | ✅ | Built exactly as prescribed: desk backbone → spatialise → defer fieldwork |
| B. Phased workplan (0–3) | ✅ mostly | Phases 1–2 complete; Phase 0 minus institutional governance; Phase 3 minus field-validation plan |
| C. Data-availability matrix | ✅ | All 5 categories sourced and implemented |
| D. IPCC methods & formulas | ✅ | Every category equation implemented as specified |
| E. Spatialisation & reconciliation | ✅ | Reconciliation exact; category-specific proxies now real (GLW livestock, FIRMS fire, WorldCover cropland; MapSPAM rice HELD since rc26, fallback class deleted) |
| F. Uncertainty & validation | 🟡 | Monte-Carlo + benchmark validation done; variance ranking now done at national scope (`key_categories_all.py`); beta/Dirichlet and field plan not |
| G. Reproducible workflow | 🟡 | Python + git + CI + repo structure done; Docker/GEE not used (by design) |
| H. Outputs / visual products | 🟡 | Most maps/tables/dashboard done; monthly burn map and some per-category maps not |
| I. Risks & governance | ✅ | Mitigations in place |

## A. Feasibility premise & sequencing — ✅

| Roadmap element | Status | Evidence |
|---|---|---|
| Desk-based first-pass feasible without new fieldwork | ✅ | Entire repo built from official stats + open data |
| Priority-four first (enteric, manure, soils, rice) | ✅ | `src/pkinv/sectors/agriculture/{enteric,manure,soils,rice}.py` |
| Residue burning as first extension | ✅ | `src/pkinv/sectors/agriculture/residue_burning.py` (added after the four) |
| Fieldwork deferred to Tier 2/3 | ✅ | Documented as future work in `docs/methods_note.md` |

## B. Phased workplan — ✅ mostly

| Phase | Roadmap intent | Status | Evidence / gap |
|---|---|---|---|
| 0 | Methods, source register, data dictionary, reproducible repo | 🟡 | `docs/methods_note.md`, `docs/sources.md`, CSV data dictionary, git ✅; formal institutional governance/MoUs ⬜ (not a code artefact) |
| 1 | National Tier 1/2 + back-cast time series | ✅ | `src/pkinv/sectors/agriculture/`, `timeseries.py` (1990–2024) |
| 2 | Provincial + gridded, reconciled | ✅ | `downscale.py`, `src/pkinv/core/gis/` (0.05° rasters) |
| 3 | Uncertainty, dashboard, versioned pipeline, field-validation plan | 🟡 | `montecarlo.py`, `dashboard.py`, `run_all.py` ✅; **field-validation protocol/budget ⬜** |

## C. Data-availability matrix — ✅

| Roadmap element | Status | Evidence |
|---|---|---|
| Matrix of sources / proxies / resolution / method per category | ✅ | `data/availability_matrix.csv`, `docs/availability_matrix.md`, `docs/sources.md` |
| All five categories covered | ✅ | Six categories implemented (the five + liming/urea CO₂) |

## D. IPCC methods & formulas — ✅

| Category | Roadmap formula | Status | Module |
|---|---|---|---|
| Enteric CH₄ | ΣN·EF | ✅ | `enteric.py` (Eq 10.19) |
| Manure CH₄ | ΣN·VS·AWMS·EF | ✅ | `manure.py` (Eq 10.22, temperature-blended) |
| Manure N₂O direct + indirect | Eq 10.25 + vol/leach | ✅ | `manure.py` |
| Soils N₂O direct | (FSN+FON+FCR+FSOM)·EF1 + FPRP·EF3PRP + rice EF1FR | ✅ | `soils.py` (Eq 11.1; 2019 dry + rice EF1FR split) |
| Soils N₂O indirect | volatilisation + leaching | ✅ | `soils.py` (Eq 11.9/11.10) |
| Rice CH₄ | EFc·SFw·SFp·SFo·t·A | ✅ | `rice.py` (Eq 5.1–5.2) |
| Residue burning | Activity·load·fracburned·CF·EF | ✅ | `residue_burning.py` (Eq 2.27) |

The roadmap's dry-climate/rice disaggregation (EF1 0.005, EF1FR 0.004) is exactly what the soils
module uses — see `docs/tier2_changelog.md`.

## E. Spatialisation & reconciliation — 🟡

| Roadmap element | Status | Evidence / gap |
|---|---|---|
| Top-down control + bottom-up allocation + rescale to total | ✅ | `src/pkinv/core/gis/allocate.py`; exact reconciliation asserted + tested (`test_gis.py`) |
| Dasymetric livestock, **species-specific GLW masks** | ✅ | **GLW 4 (2020) emission-weighted livestock density** now drives enteric + manure (`proxies.build_glw_livestock_proxy`); FAO GCS is open. Enteric map is genuinely distinct from cropland (TV-distance ~0.30) |
| **Crop-specific N downscaling** (crop area × N intensity) | 🟡 | Province fertiliser share + cropland proxy; MapSPAM crop rasters available (`data/sectors/agriculture/gis/manual/`); per-cell N intensity ⬜ |
| **Rice mask** + water-regime classes | ✅ | MapSPAM 2020 rice area (`spam_rice.tif`) HELD since rc26 (fallback class deleted fail-closed); GCD-Rice 2023 crosscheck + priced ADM2 bracket beside it. `RICE_I`/`RICE_R` consumed at Wave 6: the water-regime axis is priced (`rice_water_regime_weighted`, SFw 0.594). A 10 m EO rice mask (GEE) remains an optional refinement |
| **Residue-burning MODIS/VIIRS** fire detection + crop windows | ✅ | **NASA FIRMS VIIRS** fire-occurrence now drives the burning map + `fire_occurrence.png` (`fetch_firms.py`, 1,664,876 detections over nine years of FAO-derived per-crop windows; the FY2023-24 surface consumes only its own 166,393 in-grid detections); emissions still IPCC Eq 2.27 |

## F. Uncertainty & validation — 🟡

| Roadmap element | Status | Evidence / gap |
|---|---|---|
| Deterministic totals + transparent assumptions | ✅ | `national_totals_2024.csv` + flagged report |
| Monte-Carlo ≥10k draws, lognormal, medians + P5–P95 | ✅ | `montecarlo.py` (10,000 per sector, 100,000 national, lognormal, mean-preserving) → `national_uncertainty_montecarlo.csv`, `national_uncertainty.png` |
| **Beta/Dirichlet draws** | ⬜ | Lognormal-only |
| **Variance-contribution ranking** | ✅ | `pkinv.report.key_categories_all` ranks every category by (E x U)^2 share of the national variance, alongside the IPCC level assessment → `national_key_categories.csv`. The two orderings differ sharply: enteric fermentation is 42% of emissions and 69% of the variance, road transport 16% and 3% |
| Benchmark validation vs FAOSTAT/EDGAR (+ year-by-year) | ✅ | `national_benchmark_comparison.csv`, `timeseries_validation.csv` — **exceeds** the roadmap (it doesn't specify this) |
| **Field-validation plan** (sentinel districts, chambers, costs) | ⬜ | Not built (post-desk fieldwork) |

## G. Reproducible workflow & repository — 🟡

| Roadmap element | Status | Evidence / gap |
|---|---|---|
| Python/R for ETL, calc, uncertainty | ✅ | Pure-stdlib core `src/pkinv/sectors/agriculture/` |
| Version control + CI | ✅ | git (commit `317b3aa`), `.github/workflows/ci.yml` |
| Repo: raw archive / processed / params / scripts / docs | ✅ | `data/` (bulk cache gitignored) · `outputs/` · `data/*.csv` params · `src/` · `docs/` |
| Inventory and maps from the *same* codebase/params | ✅ | Grid reuses `provincial_matrix` / `build_components` (single source of truth) |
| **Docker** container | ⬜ | Not provided (zero-dependency core makes it largely unnecessary) |
| **Google Earth Engine** | ⬜ | Not used — `rasterio` remote-COG reads of ESA WorldCover instead (a deliberate, documented divergence) |

## H. Outputs / visual products — 🟡

| Roadmap product | Status | Evidence / gap |
|---|---|---|
| National category bar chart / table | ✅ | `national_totals_2024.csv`, dashboard |
| Province contributions | ✅ | `provincial_totals_2024.csv` |
| Livestock CH₄ hotspot map (1 km) | 🟡 | National + by-category rasters (`outputs/gis/`); a livestock-specific dasymetric surface ⬜ |
| Rice CH₄ intensity map (Punjab/Sindh) | 🟡 | `rice_ch4_2024.tif` exists (cropland-allocated); dedicated rice-mask intensity ⬜ |
| Managed-soils N₂O map by crop-season | 🟡 | `managed_soils_2024.tif` exists; crop-season split ⬜ |
| Residue-burning occurrence map **by month** | ⬜ | Emissions computed; no monthly satellite burn map |
| Reconciliation figure (cells = national total) | 🟡 | Enforced + tested; no standalone figure (shown as control row in tables) |
| Time series + CRT tables | ✅ | `trend_chart.png`, `crt_AFOLU_table.csv` (3.A–3.H) |
| Dashboard | ✅ | `outputs/dashboard.html` |

## I. Risks & governance — ✅

| Roadmap risk | Mitigation in place | Evidence |
|---|---|---|
| Livestock totals ahead of production parameters | Tier labels + explicit uncertainty bands | `tier2_changelog.md`, uncertainty outputs |
| Proxy misuse in maps | Reconcile every raster to control total; weights stored separately from emissions | `src/pkinv/core/gis/allocate.py`, `proxies.py` |
| Fragmented data ownership | Documented source hierarchy (PBS/ES, NFDC, PMD, SUPARCO, FAO/ESA/NASA) | `docs/sources.md` |

## Notable deltas

1. **Activity-data vintage.** The roadmap cites the **2025-26 Economic Survey** (cattle 61.96M,
   buffalo 49.1M, sheep 33.5M, goats 91.8M; N offtake 3,795 kt). The inventory currently uses the
   **PBS 2024 census + NFDC 2024-25** (cattle 55.8M, buffalo 47.7M, sheep 44.5M, goats 95.8M; N
   3,387 kt). The newer figures imply roughly **+10% cattle/buffalo and +12% nitrogen**, which would
   raise the national total (enteric and soils especially). This is a **one-file change**
   (`data/sectors/agriculture/activity/livestock_2024.csv`, `fertilizer_2024.csv`) plus a re-run — offered as a
   follow-up, not done here. Note the census and Survey differ by design (the census enumerates;
   the Survey projects), so choosing the basis is a documented decision, not a correction.
2. **Category-specific spatial proxies** — now **implemented with real data**: GLW 4 livestock
   (FAO GCS), MapSPAM 2020 rice, and NASA FIRMS VIIRS fire, each driving its category's map, with
   WorldCover cropland for soils/urea. Only a 10 m EO rice mask + rice water-regime remain optional.
3. **Field validation & Tier 3** — measurement campaigns, country-specific factors. The roadmap
   itself places these after the desk build; not started (needs real-world data).

## What would close the remaining gaps

- **Data refresh** to the 2025-26 Survey (quick, high-value).
- **GLW/MapSPAM proxies + rice mask + MODIS/VIIRS burn mapping** once those datasets are reachable
  — turns the 🟡 spatial rows green.
- ~~**Sensitivity/variance ranking** on the Monte-Carlo~~ — done, and at national rather than
  agriculture scope: `pkinv.report.key_categories_all` (variance shares) and
  `pkinv.report.uncertainty_all` (Approach-2 national band, plus a bounding case with the
  shared IPCC fuel-carbon factors correlated).
- **Field-validation protocol + budget** document (the roadmap's Phase-3 planning artefact).
- **District (ADM2) allocation** once public district livestock/crop tables are used as control totals.
