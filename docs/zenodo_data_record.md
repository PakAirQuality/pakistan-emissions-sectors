# The data record, prepared and NOT YET DEPOSITED

This page drafts metadata for a future **primary data record**. Nothing has been
submitted or assigned a DOI. The [ESSD submission guidance](https://www.earth-system-science-data.net/submission.html)
requires the dataset to be accessible at the selected repository for review, while
its [FAQ](https://www.earth-system-science-data.net/about/faqs.html) allows the DOI
to remain pending until acceptance.
The ODbL companion is a separate package and cannot be presented as CC BY data.

## What the record deposits

The primary package comprises the rows of `outputs/pakemis_deposit_manifest.csv`
whose `package_group` is `primary`. It contains the independently sourced core
products, own-work registers and reproduction assets, never third-party source
documents. Rows marked `odbl-companion` are excluded from this record and can be
distributed only with their own ODbL notices and attribution.

## Metadata

| field | value |
|---|---|
| upload_type | dataset |
| title | PakEmis 1.0.0rc68: greenhouse gas and air pollutant emissions in Pakistan, July 2015–June 2025 — data products |
| creators | as in `CITATION.cff` |
| version | the release being deposited (the manifest's `version`) |
| licence | CC BY 4.0 for the project-owned primary data, with per-file upstream terms recorded in the manifest; ODbL material is excluded |
| related identifiers | add software/documentation identifiers only when those records actually exist |

## Excluded ODbL companion

Code is MIT. The following OpenStreetMap-derived databases remain ODbL 1.0
(© OpenStreetMap contributors, with attribution and share-alike obligations)
and belong to the separate companion, not the CC BY primary record:

- `data/sectors/waste/gis/pak_landfill_assets.csv`
- `data/sectors/waste/gis/pak_landfill_coverage.csv`
- `data/sectors/railways/gis/pak_rail_network.geojson`
- `data/sectors/railways/gis/yards.csv`
- `data/sectors/transport/gis/pak_road_density_267x340.npy`
- `data/shared/gis/osm_building_fraction_267x340.npy`
- `data/sectors/ippu/lookups/facility_geocoding_overrides.csv`
- the `odbl-1.0` rows of `data/facility_registry.csv` and
  `outputs/pakemis_facility_registry.csv`

The manifest's `package_group` and row-level terms, rather than a blanket label,
govern the actual archive selection. ESSD's current FAQ does not accept ODbL as
the licence for its reviewed dataset. The primary data must be reviewable on
its own; if the companion is discussed as a separately published dataset, its
repository, licence and citation require an explicit editorial decision.

## Integrity

`outputs/release_manifest.json` carries a SHA-256 per product;
`outputs/SHA256SUMS` is the flat file a downloader runs `shasum -a 256 -c` against.
Both ship inside the record, so the deposit verifies itself.

## Not deposited, and why

Third-party source documents (rows of `pakemis_source_register.csv` with
`document_in_deposit=no`, each with `document_not_deposited_because`); the raw
acquisition tree `data/raw/**` (hashed in `data/catalog/manifests/source_manifest.csv`;
publisher terms are per-file); anything the deposit manifest does not enumerate.
