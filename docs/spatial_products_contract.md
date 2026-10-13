# The spatial products contract

Every spatial artefact this release ships belongs to exactly one of three tiers, and
the tier states what a reader may rely on. The contract exists because the repository
carried two spatial families side by side with nothing saying which was authoritative:
the CI-built, conservation-tested cube products, and a hand-run per-sector GIS family
on three different district frames and four different build dates — and one member of
the hand-run family (`district_totals_2024.csv`) was silently a load-bearing *input*
to the canonical cube. That inversion is fixed (the writer is promoted to the build
definitions), and this document plus `tests/test_spatial_contract.py` keep the tiers
from drifting again.

## Tier 1 — canonical nested products

Built by `pkinv.report.grid_cube` in the cross-sector layer, on every `make national`,
in CI, and in `run_all.py`. The nesting identity **has two terms as of this release**:

    national == ADM1                                        (per gas, per month)
    ADM1     == ADM2 + unallocated_below_adm1
    ADM2     == module×ADM2 == grid

It used to read `national == province == ADM2 == module×ADM2 == grid`. The change is
that **24 industry streams — 9.01 Mt, 2.01 % of the national total, the whole of the
industry module — are no longer placed in cells.** They carry the geometry id
`S4:no-native-geometry`: their activity control is provincial and there is no
geography beneath it. Previously they were spread on the declared industrial proxy and
the cube shipped an `s4_co2e_share` raster layer saying how much of each cell rested on
no geometry at all. Flagging placed mass is not the same as not placing it — the number
still arrived in the cell, and the flag was a layer a reader had to know to open. The
layer is gone and the mass is published at the level its evidence supports.

**Nothing above ADM1 moved.** The national total was unchanged to the fifth decimal at that release and every one
of the 950 provincial marginals is unchanged; only cells and districts changed. That is
the property `tests/test_grid_cube.py` asserts against the previous release's committed
check file.

The identity is held by `tests/test_grid_cube.py` at declared tolerances (in-memory 1e-9
on weights; the ADM2 view within the 2 % outside-every-polygon slack, which applies to
the **allocated** portion only; the sector view a partition of the ADM2 view at 1e-5 Gg),
and — including the second term and the strict inequality — re-asserted from the
*shipped files* by `tests/test_spatial_contract.py`.

| file | axes |
|---|---|
| `outputs/pakemis_grid_0p05_monthly.nc` | gas × month × 0.05° grid + annual category group |
| `outputs/pakemis_adm2_monthly.csv` | shape × gas × month × **spatial view** |
| `outputs/pakemis_adm2_monthly_sector.csv` | module × shape × gas × month × spatial view |
| `outputs/pakemis_grid_provincial_check.csv` | stream × province marginals |
| `outputs/pakemis_grid_fallbacks.csv` | the declared substitutions (gated by `data/allowed_grid_fallbacks.csv`) |
| `outputs/pakemis_spatial_unallocated.csv` | stream × province × gas × month — the second term (gated by `scripts/release_fixpoint.py`, which refuses a cube shipped without it) |

### The spatial class is derived, not declared

S1–S4 was a literal on each sector engine, checked against nothing at the point it was
written. It is now computed from two measured facts and the declaration is kept only so
the build can fail where the two disagree (`pkinv.report.source_streams.build`).

Every stream in this inventory is controlled provincially, because that is the level the
activity statistics exist at. So the class is not about what binds the total — if it were,
every stream would be S3 and the axis would carry nothing. **It is about how mass is placed
below the province**, which is the only part an allocation invents.

| class | means |
|---|---|
| S1 | native source geometry consuming **observed per-object activity**, over members enough of which are located to carry it (≥ 95 %) |
| S2 | the geometry *is* opened below the province, but what spreads mass across it is not observed per-object activity — uniform, partial, or declared judgement |
| S3 | nothing of the geometry reaches below the province: a raster or an administrative share does the placing, **whether or not a facility register exists** |

The inputs: `within_province_placement` on `data/geometry_sets.csv` — one row per set, saying
what the cube's own weight distributes mass by, and held against the cube's actual dispatch by
`tests/test_spatial_decomposition.py` — and the geocoded fraction over the members that can
emit, from `data/facility_registry.csv`.

`geometry_available` is the orthogonal axis and answers a different question: does native
geometry exist at all. A stream can be S3 with a full facility register (the grid fleet) or S3
with none (the industry residual), and those are not the same statement.

### The third axis: what a placement claims to be

The spatial class says how *finely* mass is placed and `geometry_available` says whether
geometry exists at all. Neither says whether the place is where the emission happens.

| view | means |
|---|---|
| `physical` | the allocation puts mass where it is emitted |
| `origin` | it puts mass where the generating activity originates; the release is elsewhere and its geography is not held — waste at the people rather than at the landfill, the drain or the burn site |
| `accounting` | it puts mass where the statistic is *booked* — road and industrial fuel at the province of sale, burnt wherever the vehicle or boiler is |

**88.91 Mt — 19.85 % of the inventory — is not physical**, and before this release every
product added the three together and returned one number. That was the last way a reader could
take a correct figure from this release and draw a wrong map with it.

So `pakemis_adm2_monthly.csv` carries `spatial_view` as a **real dimension** — shape × gas ×
month × view — and no row mixes views. Summing across them is a deliberate act. The sector
view carries it as a column, since it already keys on the module. The NetCDF labels each
`annual_by_category` layer with its view and names the mix in a global attribute rather than
shipping nine per-view rasters: the file is 6.0 MB against a hard 8 MB budget, and the ADM2
product already carries the axis properly.

**The cube is CF-1.8 (rc42).** Both NetCDF files declare `Conventions`, carry
`standard_name`/`axis`/`bounds` on the coordinate variables (`lat_bnds`, `lon_bnds`,
`time_bnds`), `cell_methods = "time: sum"` and `grid_mapping` on every data variable, and a
`crs` with the WGS 84 datum parameters and WKT. Only the cells outside every province are
missing (`_FillValue = -9999`); an in-country zero is a measurement and is stored as 0. Through
rc41 the fill value was 0, which masked 57 % of the in-country category cells as missing in
any CF-aware reader. The configuration-S file carries the three gas layers only, and its
`conservation` and `contents` attributes say exactly that instead of promising the annual
group the reference file carries.

Declared in `data/stream_geometry.csv`, not derived, and deliberately so — a view is a
property of what an activity statistic *means*, and no register here holds that. The guard is
a burden of proof instead: **a row that is not `physical` must name the release geography it
does not hold**, enforced by `tests/test_source_streams.py`. The national and per-module split
is published in `outputs/spatial_view_profile.csv`.

### The two declared absences

Both ADM2 views carry rows that carry no number, and both are deliberate: silence would
read as zero emissions. Since rc41 such a row leaves `emissions_Gg` EMPTY and names the
absence in its own `absence_reason` column (the nineteenth review: a status string in a
numeric column defeats every typed reader); the vocabulary is unchanged.

| literal | means |
|---|---|
| `unresolved-in-grid` | a canonical ADM2 unit with no drawable polygon (`shape_missing` / `no_geometry`) |
| `unallocated-below-adm1` | mass controlled at ADM1 with no geography beneath it; the numbers are in `pakemis_spatial_unallocated.csv` |

A downstream sum meets an empty cell it cannot mistake for a number, and a downstream
reader cannot miss the 2 %: the vocabulary is `grid_cube.DECLARED_ABSENCES`, and every
reader in the repository tests `absence_reason` against that set rather than comparing
`emissions_Gg` against a string of its own.

Frame: the canonical ADM2 registry (`data/adm2_canonical.csv`, 152 units) resolved to
the 126 geoBoundaries shapes, holes declared per row.

## Tier 2 — canonical inputs

Sector products the cube reads for its district factors. Each is built by a runner in
all three build definitions and reconciles exactly (1e-9) against its sector's
provincial allocation; names resolve through `pkinv.core.adm2`.

| file | frame | writer |
|---|---|---|
| `outputs/district_totals_2024.csv` | 114 four-province districts + residual (provincial activity scope) | `pkinv.sectors.agriculture.gis.district_downscale` — promoted to CI/run_all/Makefile in rc9; regenerates byte-identically from committed inputs |
| `outputs/residential_district_2024.csv` | 134 census-frame districts | `pkinv.sectors.residential.gis.district_downscale` (CI-built via `run_residential`) |
| `outputs/waste_district_2024.csv` | 134 census-frame districts (ORIGIN allocation) | `pkinv.sectors.waste.gis.district_downscale` (CI-built via `run_waste`) |

FOUR administrative frames coexist by design, and every one resolves into the
canonical registry (`data/adm2_canonical.csv`, 152 units; published join:
`outputs/pakemis_adm2_crosswalk.csv`):

| frame | units | used by | vintage |
|---|---|---|---|
| agricultural activity scope | 114 + residual | agriculture district products | ag census 2024 naming |
| census full frame | 134 | residential + waste district products | PBS Census 2023 |
| railway network districts | 66 | railways corridor allocation | boundary file 2019 |
| drawable boundary shapes | 126 | every choropleth + the grid cube | geoBoundaries gbOpen 2019 |

The registry itself is multi-vintage by construction (`effective_date`: census_2023
134, boundary_2019 11, pre-subdivision 3, ag_census_2024 3), which is what lets four
observed vocabularies resolve to stable ids. What does NOT yet exist — declared
future work, not an omission — is a frame-to-frame MASS mapping (how the 114
agricultural units aggregate or split into the 134 census units); products reconcile
through provincial marginals and the name crosswalk today.

## Tier 3 — research products

Hand-run, outside `make all`/CI, on their own frames and build vintages. Real,
citable, and NOT authoritative where they overlap a canonical product; no canonical
writer may read them (tested). `scripts/audit_outputs.py` KNOWN_TREES carries the
same designation.

| family | contents | frame / vintage |
|---|---|---|
| `outputs/gis/*.tif`, `*.png`, `grid_emissions_2024.csv`, `gis_report.md` | agriculture category rasters, residential co2e/pm25/bc, air-pollutant rasters, hotspot maps | agriculture 115-frame / Aug 2026 vintages |
| `outputs/gis/railways_*` + `outputs/railways_gis_{cells,district,provincial}_2024.csv` | rail network surfaces | 66-district rail corridor frame |
| `outputs/districts/*_by_district.csv`, `district_totals_by_year.csv`, `*.png` | nowcast-era district panels and figures | mixed |
| `outputs/residential_gis_provincial_2024.csv`, `outputs/air_pollutants_district_2024.csv` | sector research summaries | sector frames |

The air-pollutant rasters have no canonical counterpart because the cube carries
CO2/CH4/N2O only; a pollutant axis is a future feature, not a regeneration.

## Diagnostics (not allocation)

Road geometry (`data/sectors/transport/gis/`, `outputs/pakemis_road_length_adm2.csv`, the link
table) and the OSM building-fraction raster are diagnostics under the discipline
tests: no stream registry row may point at them.

## The district frame across the nine-year products (added with the nine-year spatial pass)

`pakemis_adm1_by_year.csv`, `pakemis_adm2_by_year.csv` and `pakemis_adm2_monthly_by_year.csv`
publish **every period on one fixed frame**: the canonical 152-unit set of
`data/adm2_canonical.csv` on `geoBoundaries-gbOpen-PAK-ADM2-2019`, with the 2023 census names.

**The v1.1 migration, declared (rc47 Wave 6).** The 2019 rasterisation draws only 126 of
the 152 units — fourteen collision groups share polygons, Larkana has none at all (its
territory is absorbed by its 2019 neighbours, so no additive patch exists), and 21.4% of
district mass sits on shared shapes. The OCHA COD-AB 2022 vintage
(`data/shared/gis/cod_ab/`, CC BY-IGO, 160 units) resolves twelve of the fourteen groups plus
Larkana and Tor Ghar; `outputs/pakemis_adm2_frame_2022.csv` is the complete, per-unit-typed
crosswalk. Swapping the rasterisation re-keys every `shape_id`, golden and grid cell at
once, so it is **v1.1's one declared migration** — prepared here, tested here, and
deliberately not performed inside a release candidate. Until then this contract's fixed
frame stands unchanged.

Eleven of those units carry `geometry_relation=carved_from` — they were created out of larger
districts, several of them during the inventory window — and three are `legacy_aggregate` units
with status `superseded` (Chitral, Kohistan and Karachi before their subdivisions), retained
because live historical panels report them.

**What an earlier year's district row therefore means.** It is the mass that would fall inside
*today's* boundary, not a figure any administration reported for that year. A district created
in the middle of the window has a row in all nine periods. This is the only choice under which
the nine years can be compared with one another at all, and it is a choice rather than a fact
about Pakistan, so it is stated here, in `06_results.tex`, and asserted in
`tests/test_spatial_by_year.py` rather than left to a reader who might reasonably assume
contemporaneous administrative geography.

**Why it is not simply fixed.** The creation dates are real and knowable, but they are not in
this tree. The frame's `effective_date` column holds *source labels* — `census_2023`,
`boundary_2019`, `pre_subdivision`, `ag_census_2024`, `n/a` — and not dates, so no filter can
be written against it. Supplying the dates from memory is the kind of unsourced precision this
inventory refuses everywhere else, so the gap is carried as the declared absence **abs-adm2-frame-vintage**
in `data/validation_catalog.csv` and stays visible until it is closed. It is deliberately not
in `data/monthly_data_requests.csv`: that registry is keyed to the monthly decomposition's
components, and a district-frame gap is not one of them.

**What is NOT published, and why.** Nine gridded cubes. At 0.05° that is roughly 52 MB of
NetCDF whose within-province pattern is, for about two thirds of stream-years, the reference
year's — precision the evidence does not have, in the format most likely to be read as though
it did. The gridded product remains the reference year; the months below the nation ship at
ADM2 for all nine periods, and a historical cube can be regenerated from the code in under a
minute, which is the same argument that kept the per-stream surfaces out of the tree.

## Spatial brackets across the nine years

`outputs/pakemis_spatial_brackets.csv` prices, per allocation, the spread between the placement
this inventory uses and an admissible second reading of it — road diesel on vehicle
registrations rather than fuel sales, and so on. It carries 83 rows and no period axis, and
`data/product_schemas.csv` declares its coverage as FY2023-24.

That is not an oversight in a nine-year release, and the reason is the one that also kept nine
gridded cubes out of the tree. A bracket measures the distance between two readings of the
**same** placement. For 1,102 of the 1,672 live stream-years the placement *is* the reference
year's, rescaled to that year's own control — so those years' brackets are the reference year's
brackets by construction, and publishing them per year would ship nine copies of one spread.

The join that makes this readable is already published: `spatial_time_basis` in
`pakemis_spatial_weights_by_year.csv` names every stream-year that is a
`reference_shape_backcast`, and each of those inherits the reference year's bracket exactly.
The 299 stream-years whose geography is their own are where a genuinely different bracket could
exist; pricing them would need the alternative proxies to be available per year, and they are
not — the registration and area statistics that supply the alternatives are themselves
single-vintage or province-ragged. That is a data gap rather than a modelling choice, and it is
the same gap the weight registry records on the primary side.

What a reader must therefore **not** infer is that an earlier year's placement is better
constrained than the reference year's because no per-year bracket is published for it. It is
constrained identically where the pattern is inherited, and less well where it is not.

## The provenance vocabulary (rc44)

`pakemis_spatial_weights_by_year.csv` types every stream-period by one question: **does the
evidence behind this surface have a time axis the engine reads for this period?**

| value | meaning |
| --- | --- |
| `annual_observed_activity` | the evidence has a time axis and the engine read it for this period |
| `static_structural` | a timeless surface — a raster snapshot or a declared judgement with no time axis at all, in any period including the reference year |
| `reference_shape_backcast` | the reference year's pattern, rescaled to this year's own control |
| `substituted_surface` | the declared surface had no evidence and a substitute placed the majority of the mass |
| `unallocated` | never placed below ADM1, in any year |
| `not_present` | the stream carries no mass in this period |

**What changed, and why it was not a rename.** Until rc44 the first two were three values —
`direct_activity`, `administrative_activity` and `dynamic_proxy` — which were a pure function of
`within_province_placement`, a column already in the same row, and so carried no information the
row did not already hold. One of them was worse than redundant: `dynamic_proxy` was applied to
streams placed on an ESA WorldCover 2021 built-up raster, and a reader counting "measured for
its own year" counted all 196 of them. Re-deriving moved 299 of 1,701 rows and corrected a
published figure downwards — 299 stream-years measured for their own year became **159**, with
**140** now saying plainly that they ride a timeless surface. No mass moved.

**Two values the review proposed are reserved, not shipped.**
`interpolated_between_anchors` and `nearest_vintage` describe evidence this build does not yet
produce. Declaring them in the enum would make `test_the_basis_vocabulary_is_closed` pass
vacuously — a value no code path can emit cannot catch a value that should have been retired,
which is that guard's only job. They will be declared by whatever first emits them.

**One honest imprecision, to be revisited.** A non-reference year whose surface is timeless is
labelled `reference_shape_backcast` rather than `static_structural`, because although the
within-province raster is timeless the provincial share it rides is still the reference year's.
That is true today and stops being true when the provincial shares are period-keyed; the label
is deliberately the more pessimistic of the two until then.
