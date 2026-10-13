# Data reviewer guide

Browse by sector, then by purpose. The catalog separates observations, assumptions, spatial inputs, evidence, administrative metadata and requests.

## Sectors

- [Agriculture](sectors/agriculture/README.md)
- [Aviation](sectors/aviation/README.md)
- [Fugitives](sectors/fugitives/README.md)
- [Industry](sectors/industry/README.md)
- [IPPU](sectors/ippu/README.md)
- [Power](sectors/power/README.md)
- [Railways](sectors/railways/README.md)
- [Residential](sectors/residential/README.md)
- [Transport](sectors/transport/README.md)
- [Waste](sectors/waste/README.md)
- [LULUCF](sectors/lulucf/README.md)
- [Shared data](shared/README.md)

## Browse by purpose

[Cross-sector purpose index](catalog/by-purpose.md) · [Complete asset catalog](catalog/assets.csv) · [Migration map](catalog/migrations.csv)

## Reading and maintaining data

The sector guides link readable canonical CSVs first. Their source tables live in the corresponding sector purpose folders. Canonical CSVs are generated and versioned for review; their hashes and column definitions are recorded in the catalog. The model and downloads consume those same canonical values.

Files marked as compatibility views are generated selections from authoritative facts. Update the facts and regenerate the views; never maintain both independently.

Requests have separate registers, recipient-facing letters and prospective templates. Existing IDs and delivery/response states are preserved. Received material must pass source registration and verification before becoming activity data.

Raw documents, downloaded archives, caches, historical baselines and release outputs retain their existing locations. Source references link them into the sector catalog. Spatial assets retain all declared companion files and redistribution conditions.

Run `make data-index` after catalog edits and `make data-check` to verify assets, canonical CSVs and generated reviewer guides. `make dev` rebuilds changed calculations; `make release-check` runs strict reproduction.
