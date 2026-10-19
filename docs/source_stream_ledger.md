# The source-stream ledger

`outputs/pakemis_source_streams.csv` — 190 rows, 36 fields, one row per emitting stream.

This is the first object in the release meant to be read *instead of* a prose description. Everything
else the inventory publishes is an aggregate of something: a module total, an IPCC category, a
province, a month. The ledger is the thing those are aggregates **of**, and it exists to answer
one question without a join:

> what was emitted, by which process and gas, in which year and month, at which physical
> location, under which scenario, from which source document, and with which parametric,
> structural, temporal and spatial limitations?

Written by `src/pkinv/report/source_streams.py`, in the cross-sector layer of `run_all.py`,
`make national` and CI.

## It recomputes nothing

Every quantity is read from an output that already exists. The ledger equals the national rollup
exactly — in total, and module by module — and `tests/test_source_streams.py` asserts it. This is
the same discipline as `release_manifest.py`: a second arithmetic path is a second vintage waiting
to disagree with the first.

It is **derived, not emitted**. The component row stays the atom — a closed set of fifteen keys,
which is what makes the sector contract checkable — and the ledger is assembled by joining the
registries that already exist: the IPCC category ledger, the completeness matrix, the scenario
registry, the parameter registry and scope map, the source-document register, and the monthly
layer.

## What it says that nothing said before

**Release height.** A new categorical axis (`core.evidence.RELEASE_HEIGHT`), declared per category
in `data/release_heights.csv`. Classes only — no invented stack heights. The national picture:

| class | share |
|---|---|
| surface | 58.7% |
| high_stack | 16.8% |
| traffic_surface | 9.1% |
| low_stack | 8.8% |
| household_low | 6.6% |
| airport_LTO | 0.1% |

**Spatial class, finally published.** S1–S4 has been required on every component row since the
schema freeze and validated on every build, and appeared in no output file. `outputs/spatial_profile.csv`
is now the exact analogue of `outputs/temporal_profile.csv` — and publishing it forced the
classes honest (see the corrections below).

**The class is now DERIVED, and it moved again — further, and in both directions.** It was a
hand-assigned literal on each sector engine, checked against nothing where it was written. It
is now read from what the allocation does: `within_province_placement` on
`data/geometry_sets.csv` (what the cube's weight distributes mass by inside each geometry, one
row per set, held against the cube's own dispatch by test) plus the geocoded fraction over the
members that can emit. `pakemis_source_streams.csv` publishes `spatial_class` and
`spatial_class_measured` side by side and **the build fails where they disagree**.

**98.6% of national emissions are allocated by administrative statistic (S3), 1.3% by facility
or network proxy (S2), and 0.07% by native geometry consuming per-object activity (S1 —
domestic aviation, the only earned claim).** Five sets of streams moved:

| streams | was | is | why |
|---|---|---|---|
| grid power, 57.8 Mt | S2 | **S3** | 30 of 78 emitting stations are located and not one gramme rides on them; the cube spreads provincial generation on built-up |
| captive power, 5.5 Mt | S3 | **S2** | the one allocation that opens its register below the province — 1,068 of 1,105 geocoded, 864 with a gas allocation |
| railways traction, 0.39 Mt | S1 | **S2** | the track is native geometry; the corridor service tiers that distribute along it are declared judgement |
| aviation, 0.30 Mt | S2 | **S1** | 36 of 37 airports located, weighted by PCAA movements per airport |
| LNG terminals, 0.13 Mt | S2 | **S3** | neither terminal is located, so the "facility proxy" never reaches the allocation |

Nothing about any allocation changed — the national total held to the fifth decimal at that release, every cell and district byte-identical.
Only the letters were wrong, which is the argument for deriving them.

**Temporal profiles have identities.** `data/temporal_profiles.csv` names all 32 profiles the
monthly layer applies, with each one's source and the period that source covers. They were built
inline in each sector's `monthly.py` and identified only by a free-text basis string.

## What it says that is uncomfortable, and is meant to be

A field that cannot be resolved carries an explicit value, never a blank. A ledger whose gaps are
empty strings reads as complete; one whose gaps say `unresolved` can be counted.

| gap | streams |
|---|---|
| `licence_status` undetermined | 188 of 190 |
| `factor_identity_ids` unresolved | 89 of 190 |
| `geometry_id` explicit S4 residual | 24 of 190 (industry) |

- **Every stream now names its geometry or its absence** (Stage 5). `geometry_id` resolves to
  one of nine registered geometry sets (`data/geometry_sets.csv`) or to the explicit
  `S4:no-native-geometry` residual — "unresolved" stopped being a legal value in that column.
  Behind the sets stand `data/facility_registry.csv` (**12,620 facilities**: 1,068 geocoded
  captive plants with confidence grades, 157 grid plants declared `coordinate_unresolved`,
  airports, rail yards, the IPPU census, two LNG terminals, and 11,272 prospective brick
  kilns touching no total) and the canonical ADM2 package (`data/adm2_canonical.csv`, 152
  units; `data/adm2_crosswalk.csv`, 305 spellings across four district systems).
- **Almost nothing has a determined licence.** `licence_status` on the source register is
  filled only where the source's own identity settles it; the rest is `undetermined` rather
  than guessed. (The reasoning lives here rather than as a comment header in the CSV: that
  file predates the `#`-header convention and three of its readers open it raw.)
- **`module_structural_axes` is module-scoped, and named so.** `data/scenarios.csv` registers
  an axis against a module rather than against a stream.
- **`process` is `not-applicable` everywhere.** The engine has no process concept distinct
  from the sub-item.

## Corrections this product forced

**IPPU no longer claims native geometry.** It declared `S1` for three releases on the strength of
a facility registry with 34 rows and **zero** populated latitudes, while its allocation actually
rode `ippu_cement_prod` in `data/province_shares.csv` — a provincial share whose own note reads
*"PROVISIONAL GEOGRAPHY … must not be interpreted as measured FY2023-24 provincial production"*.
It is `S3` until the coordinates land.

**The reviewer's Stage 2 is met.** *"One row may depend simultaneously on several differently
shared parameters; 100% of conditional variance is attached to named parameters or named residual
objects."* Round 8 gave the first half — 172 of 190 rows carry more than one distinct named parameter —
and Round 9's per-module residual split gave the second.
`outputs/national_variance_attribution.csv` has 85 rows, 10 named residual objects and **no
anonymous variance**.

*Status at rc67.* That product was a decomposition of a surrogate of the inventory and has
been withdrawn (CHANGELOG, 1.0.0rc67). What drives the national spread is now read from the
released draws in `outputs/pakemis_uncertainty_drivers.csv`. The paragraph above records the
stage as it was met.

## Corrections Stage 5 forced

**Power's grid never had coordinates, and its engine said it did.** The declaration comment
read *"S1 throughout: the plant register carries coordinates, so emissions sit on the
facilities that produce them"* — while `plant_locations.csv` has columns
plant/town/province/station_type and nothing else. The same prose-asserts-what-the-data-denies
defect the IPPU round corrected, one module over. Grid streams (and bagasse, and the two
LNG-terminal streams whose "geometry" is a station count of two) went to S2 at the time.

**And S2 was wrong too — the same defect, one step milder, surviving two more releases.** A
facility proxy has to reach the allocation to be one. Thirty of the grid fleet's seventy-eight
emitting stations now carry a corroborated coordinate and the cube opens none of them: the
streams are placed by provincial generation share on the built-up raster. `geometry_sets.csv`
said so in its own note the whole time — *"the surface stays built-up until coverage supports
points"* — while the class beside it said facility proxy. **They are S3 as of the derived
class**, and return to S2 when an allocation actually consumes the points.

**The boundary file has no Larkana.** Found while building the canonical table: geoBoundaries
gbOpen PAK ADM2 carries no Larkana polygon — while Qambar Shahdadkot, carved *out of* Larkana
in 2004, is present. A distributor defect, meaning every district product ever built on this
file silently rasterised Larkana's territory as "outside any district". The canonical table
declares it (`geometry_relation = shape_missing`) and `tests/test_adm2.py` pins the
declaration.

## The cube

`outputs/pakemis_grid_0p05_monthly.nc` places all of this on the national grid: every
stream's `geometry_id` becomes a weight surface (points, network, district panels, or
declared proxy), every month from the temporal layer, native gas mass, conservation tested
end to end (`tests/test_grid_cube.py`).

## Known vintage skew in the spatial products

Since rc9 the tiers are DECLARED: `docs/spatial_products_contract.md` names the
canonical nested products (the cube family), the canonical inputs (the three district
panels, all in the build definitions — agriculture's was promoted in rc9 after the
cube was found silently depending on a hand-run artefact), and the research tier
(`outputs/gis/`, `outputs/districts/*_by_district.csv`, `railways_gis_*`), which keeps
its own frames and build dates and which no canonical writer may read (tested). The
frame divergence — 114+1 for agriculture, 134 for residential and waste, 66 for
railways, against the 126-feature geoBoundaries file — is the deliberate two-frame
design plus the rail corridor scope, reconciled in the claims registry. The spatial class
is therefore published on the ledger and on the provincial profile, and **not** carried into those
stale artefacts, where it would assert a freshness they do not have.
