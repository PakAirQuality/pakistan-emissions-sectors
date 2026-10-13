# The data record, prepared and NOT YET DEPOSITED

This page is the metadata for the **data DOI** — the second of the three identifiers
the release plan mints (software / data / documentation). Nothing here has been
submitted anywhere: it exists so that the deposit, when the user makes it, is a
copy-paste rather than a reconstruction, and so the licence split is decided before
the form asks for one licence.

## What the record deposits

The **product tree**, not the repository: the files
`outputs/pakemis_deposit_manifest.csv` enumerates with `derived_file_in_deposit=yes`,
which is the deposit the licensing round already scoped — products and own-work
registers, never third-party source documents (their absence is per-row explained in
`outputs/pakemis_source_register.csv`).

## Metadata

| field | value |
|---|---|
| upload_type | dataset |
| title | PakEmis: a reproducible national GHG inventory for Pakistan — data products |
| creators | as in `CITATION.cff` |
| version | the release being deposited (the manifest's `version`) |
| licence | **CC-BY-4.0, with the ODbL carve-outs below** — Zenodo's single-licence field takes CC-BY-4.0 and the description must state the carve-outs |
| related identifiers | isSupplementTo → the software DOI; isDocumentedBy → the documentation DOI |

## The licence statement the description must carry

Code is MIT (not in this record). Data and text are CC-BY-4.0 **except** the
OpenStreetMap-derived databases, which remain ODbL 1.0 (© OpenStreetMap
contributors; attribution + share-alike, which CC-BY cannot waive):

- `data/sectors/waste/gis/pak_landfill_assets.csv`
- `data/sectors/waste/gis/pak_landfill_coverage.csv`
- `data/sectors/railways/gis/pak_rail_network.geojson`
- `data/sectors/railways/gis/yards.csv`
- `data/sectors/transport/gis/pak_road_density_267x340.npy`
- `data/shared/gis/osm_building_fraction_267x340.npy`
- `data/sectors/ippu/lookups/facility_geocoding_overrides.csv`
- the `odbl-1.0` rows of `data/facility_registry.csv` and
  `outputs/pakemis_facility_registry.csv`

This list is the manifest's `licences.odbl_carveouts` block, and
`tests/test_deposit_licensing.py` asserts the two stay identical — update the
manifest, and this page follows it, never the other way around.

## Integrity

`outputs/release_manifest.json` carries a SHA-256 per product;
`outputs/SHA256SUMS` is the flat file a downloader runs `shasum -a 256 -c` against.
Both ship inside the record, so the deposit verifies itself.

## Not deposited, and why

Third-party source documents (rows of `pakemis_source_register.csv` with
`document_in_deposit=no`, each with `document_not_deposited_because`); the raw
acquisition tree `data/raw/**` (hashed in `data/catalog/manifests/source_manifest.csv`;
publisher terms are per-file); anything the deposit manifest does not enumerate.
