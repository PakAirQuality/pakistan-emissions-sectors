# Pakistan Agricultural GHG - Gridded Surfaces (2024, provisional)

National emissions allocated to a 0.05-degree (~5 km) grid by dasymetric distribution of the Phase-3 provincial control totals, using **category-specific proxies**, reconciled exactly to province and national totals.

## Configuration
- Grid: 340x267 cells at 0.05 deg, EPSG:4326, bounds (60.85, 23.7, 77.85, 37.05)

## Proxies used per category

Allocation is per emission *stream*, not per category: a category whose subitems ride different nitrogen sources is gridded on several rasters and summed. Managed soils is the clear case -- most of its nitrogen is livestock-derived, so gridding it wholly on cropland would misplace the majority of it.

| Category | Proxies | Sources |
|---|---|---|
| Enteric fermentation | `glw_livestock` | GLW4-2020 emission-weighted livestock density (CTL+BFL+SHP+GTS) |
| Manure management | `glw_livestock` | GLW4-2020 emission-weighted livestock density (CTL+BFL+SHP+GTS) |
| Rice cultivation | `spam_rice` | manual: data/gis/manual/spam_rice.tif |
| Managed soils | `cropland`, `glw_livestock`, `manure_applied`, `spam_rice` | ESA WorldCover 2021 cropland fraction (34 tiles); GLW4-2020 emission-weighted livestock density (CTL+BFL+SHP+GTS); ESA WorldCover cropland x GLW4-2020 livestock density (per-cell intersection); manual: data/gis/manual/spam_rice.tif |
| Field burning of residues | `firms_fire` | NASA FIRMS VIIRS fire-occurrence density (166393 in-grid FY2023-24 detections of 1664876 fetched across the nine-year record, FRP-weighted) |
| Liming & urea (CO2) | `cropland` | ESA WorldCover 2021 cropland fraction (34 tiles) |

## Category totals (gridded == control)

| Category | Mt CO2e |
|---|---:|
| Enteric fermentation | 151.5 |
| Manure management | 21.2 |
| Rice cultivation | 16.5 |
| Managed soils | 28.5 |
| Field burning of residues | 0.7 |
| Liming & urea (CO2) | 4.8 |
| **Total** | **223.3** |

## Outputs
- Per-category + total GeoTIFFs (float32, Mt CO2e/cell), `hotspot_total.png`, `hotspot_by_category.png`, `grid_emissions_2024.csv`

## Data provenance & caveats
- **Enteric & manure** now use **GLW 4 (2020) emission-weighted livestock density** (FAO, open) - herds land on real locations (canal belt, rangeland, peri-urban), not just cropland.
- **Rice, soils, burning, urea** use ESA WorldCover 2021 cropland fraction. A user-supplied `data/gis/manual/spam_rice.tif` (MapSPAM) overrides rice automatically.
- **MapSPAM crop area and NASA FIRMS fire** are user-supplied drop-ins (see `docs/DATA_ACQUISITION.md`); absent -> cropland fallback.
- These are **allocated** surfaces, not measurements; category totals are exact control totals. GLW ref-year 2020 / WorldCover 2021 vs 2024 activity - stable but flagged.
