# The product catalog: design, specified and not yet built

This is a specification, not a description. Nothing here ships yet. It exists so the next pass
implements a decided design rather than re-deriving one, and so the rulings behind it are not
re-argued.

## Why the current `role` field is not enough

`data/artifact_roles.csv` assigns one `role` per file, and that single field conflates four
independent dimensions:

| the field says | but it is really about |
|---|---|
| `canonical` | release importance |
| `sector_headline` | scientific content |
| `diagnostic` | intended use |
| `intermediate` | build lifecycle |

These are not mutually exclusive. A facility registry is *supporting* **and** *spatial*. A
diagnostic can still be publicly released. Forcing one word to carry four meanings is why the
tier had to be derived from the role rather than declared beside it.

**And a physical file is not a logical product.** `pakemis_annual_fy2015_16_fy2023_24.csv` and
its `.parquet` twin are one product in two representations. Three such pairs exist today.
Counting citation coverage over file extensions is what makes a number like "12 uncited"
harder to interpret than it should be.

## The schema

Two generated registers replace the one:

**`product_catalog.csv`** — one row per logical scientific product:

| field | example |
|---|---|
| `product_id` | `annual.atomic`, `spatial.facilities` |
| `product_family` | `annual` / `monthly` / `spatial` / `uncertainty` / `cross-cutting` |
| `release_tier` | `core` / `supporting` / `audit` / `build` |
| `artifact_kind` | `estimate` / `registry` / `diagnostic` / `schema` / `intermediate` |
| `ship` | true/false |
| `documentation_anchor` | `main:6.5`, `supp:S2`, `README:products` |
| `license_id` | `CC-BY-4.0`, `ODbL`, `restricted` |
| `generated_by` | module or command |

**`artifact_manifest.csv`** — one row per physical file: `product_id`, `representation`
(CSV / Parquet / NetCDF / GeoParquet), `bytes`, `sha256`.

Citation coverage is measured against the catalog, never against files. `role` is retained,
derived, until every reader has moved.

## The four families and their core products

```
annual.atomic              annual.national_rollup     annual.adm1
annual.coverage            annual.unallocated_controls annual.structural_bridges

monthly.atomic_108         monthly.temporal_profiles  monthly.evidence_register
monthly.unallocated        monthly.closure_summary

spatial.reference_cube     spatial.native_geometries  spatial.adm_crosswalk
spatial.unallocated        spatial.decomposition      spatial.facility_registry
spatial.evidence_masks

uncertainty.draws          uncertainty.quantiles      uncertainty.parameter_registry
uncertainty.dependency_registry
scenarios.structural_registry  scenarios.completeness_states
```

## Two rulings to apply, not re-derive

**The deletion test decides the tier.** *If this file disappeared, could a user still
interpret, reproduce and validate a declared PakEmis product?* No → `core` or `supporting`.
Yes, but it carries useful QA → `audit`. Regenerable with no independent user value →
`build`.

**No catch-all outside `build/`.** The present `*` → `intermediate` rule is precisely how a
new final product gets silently buried, and it must not survive this migration. Public output
directories fail on an unregistered file; only `build/` may have a catch-all. The current rule
is a scaffold with an expiry date, and this paragraph is the expiry date.

## Packaging

Assembled from explicit allowlists, never by copying `outputs/`:

```
pakemis-core/     the four families, schemas, data dictionary, catalog, licences, provenance
pakemis-support/  sector headline tables, crosswalks, supporting registries, technical docs
pakemis-audit/    diagnostics, sensitivity comparisons, closure reports, source-search logs
build/            regenerable intermediates, temporary joins, caches -- normally not deposited
```

If an intermediate is necessary *because its source is unavailable or hard to reconstruct*, it
is a derived source artifact and belongs in `support/`, not `build/`.

The integrated release retains registered compiled dependencies in
`pakemis-support/reproduction/` for offline recalculation. They remain distinct
from advertised core records. ODbL-derived inputs, legacy spatial descendants and
preserved baselines are packaged in a separate ODbL companion with upstream
licences and attribution. The manifest's `package_group` determines which archive
contains a file; removing an input alone cannot clear a derived product.

## Manifests, and why there must be two

```
scientific build -> catalog + classification -> allowlists
   -> artifact manifest (sha256 of every shipped file)
   -> data release manifest
```

The split is not tidiness. A document cannot contain the hash of a manifest that changes when
that document's hash is added to it, so anything typeset from the release is hashed after it,
outside the manifest (rc70: such documents are no longer built in this repository).

## Documentation rule

**Do not require canonical filenames in prose.** Require each core *logical product* to have
one `documentation_anchor`: a heading in the release README or a document under docs/
(`tests/test_product_catalog_anchors.py` resolves every one). The detailed product table is
generated from the catalog.

Then *core-but-undocumented* becomes a zero-tolerance release gate without inventing a dozen
artificial paragraphs — which is the trap the present ratchet is holding the door against.

## Exit criteria

1. Every discovered physical file has exactly one `product_id`.
2. Every logical product has at least one artifact.
3. Every public artifact is hashed.
4. Every core product belongs to exactly one family.
5. Every core product has a schema, a licence and a documentation anchor.
6. Every referenced artifact exists.
7. No build/intermediate artifact enters `pakemis-core`.
8. No unregistered artifact enters any release archive.
9. CSV / Parquet / NetCDF representations count as one logical product.
10. Product counts reconcile exactly with artifact counts.
11. The artifact manifest is generated only after all scientific outputs exist.
12. The documentation manifest is generated only after the PDFs exist.
13. A clean rebuild reproduces every core-product hash.

Gates 1, 10 and the reconciliation identities are already live in
`tests/test_artifact_inventory.py`; the rest arrive with the catalog.

**The end state is not "all 406 files cited."** It is: every shipped artifact registered and
hashed, every core logical product discoverable and documented, and everything else clearly
supporting, audit-only, or excluded from the release.
