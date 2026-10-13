# Where a power station's emissions are placed, and on whose authority

Stage 4 of the twenty-second review, item 7. This states the rule that decides the
district of every located power station, the record each station's answer comes from, and
what the 2026-10-07 correction moved. It names no release version: its identity is the
release record it accompanies.

Nothing here re-estimates anything. Every number below is a reallocation of mass the
engines had already fixed, and the national and provincial totals are asserted unchanged.

## Four records, and which question each one answers

| record | rows | answers |
|---|---|---|
| `data/sectors/power/activity/plant_locations.csv` | 157 | the station's **province** (and a town, not a district) |
| `plant_coordinates.csv`, `coal_plant_coordinates.csv`, `gas_plant_coordinates.csv` | 52 + 8 + 17 | the station's **coordinate** |
| `data/sectors/power/activity/grid_plant_district.csv` | 711 (107 stations × 10 fiscal years) | the station's **district**, as `district_printed` and a resolved `adm2_id` |
| `data/gis/PAK_ADM2.geojson`, rasterised at 0.05° | 126 units with a polygon | the **frame**: which polygon contains a point, and which province a polygon is in |

The third of these is the project's own 2024 compilation over NEPRA, OGRA, SNGPL, SSGC and
OCAC records. Until 2026-10-07 the spatial allocation did not read it: the districts had
been ingested, resolved against `data/adm2_canonical.csv` and verified, and then went
unused — the mistake CLAUDE.md's four-layer rule exists to prevent. It is used for
**geography only**, the scope its own banner declares. Its `fuel` column is a per-plant-year
capability label (`GAS+RFO+RLNG`, `Dual`) and not a quantity, and its emission columns are
held apart in `data/sectors/power/evidence/workbook_emissions_crosscheck.csv` — 755 rows of
SO₂, NOₓ, PM10, PM2.5 and CO on a Mid and a Max band — explicitly **to be compared and never
adopted**, because those factors are a "typical literature range consistent with US EPA
AP-42" and the bagasse SO₂ factor is an unsourced 0.0 by the workbook's own admission. This
inventory computes SO₂ from a sulfur balance on a dated evidence register
(`power_so2_admission.csv`, 31 stations × 9 fiscal years) instead.

## The placement rule

A station's mass is placed in this order, and the rule that placed it is published per
station in `outputs/pakemis_power_province_boundary_audit.csv` (`adm2_placement`).

1. **The province is a control; the district is not.** A station is pooled under the
   province of its curated record. The provincial share vector is the quantity the cube must
   reproduce exactly, so no district correction may move mass across a provincial line.
2. **The point's own ADM2 polygon**, where that polygon lies inside the pooled province.
   70 of 77 stations; plus Mangla and Attock Gen., whose polygons agree with their record.
3. **The curated district**, where the polygon containing the point does *not* lie in the
   pooled province, or no polygon contains the point at all — and only when the curated
   district's own polygon majority keeps the province. Five stations.
4. **The fallback surface at the point's own cell**, where no record names a district or the
   named district would cross a province. Zero stations today; the rule remains because a
   newly commissioned station can land there, and it must land somewhere declared.

Rule 3 is the 2026-10-07 addition, and it works for a reason worth stating. Rule 2 fails
near a border because a 0.05° cell is about 5.5 km across and the simplified ADM2 polygons
disagree with the records along a provincial line. A **named** district is adjudicated by the
majority of its own cells in the ADM1 control, which is robust where one cell is not:

| curated district | polygon | cells | raster-majority province | station's booked province |
|---|---|---|---|---|
| `balochistan_lasbela` | Lasbela | 703 | Balochistan | Balochistan |
| `sindh_kashmore` | Kashmore | 128 | Sindh | Sindh |
| `sindh_karachi_legacy` | Karachi | 124 | Sindh | Sindh |

So naming the district lands the mass in the right district *and* keeps the provincial
marginal — the trade rule 1 forbids never arises.

## The join that supplies a district, and what it refuses

Three rules, in order, in `grid_cube._curated_station_districts()`:

1. the exact name key;
2. the key of the name `plant_name_crosswalk.csv` canonicalises it to — this is how `HUBCO`
   reaches `Hub Power`, through a record already held rather than a new inference;
3. a **strict subset** of a coordinate-table key, of at least two tokens, and only when every
   workbook row matching it names one district.

Rule 3 exists for TPS Guddu: the workbook prints "TPS Guddu" and "TPS Guddu (GENCO-II)"
where the coordinate table prints "(Units 5-10)" and "(Units 14-16)", so no one-to-one match
exists — but both workbook rows say Kashmore, so the answer does not depend on which block is
which. An ambiguous subset is refused outright.

The two-token floor is the rule's safety rather than a tuning constant, and the evidence is
that every one-token match measured over the live tables was **wrong**: `Foundation Wind
Energy-I` and `-II` (the Sindh coast) would have taken Foundation Power Dharki's Ghotki,
`Liberty Power Tech.` would have taken Liberty Power's Ghotki, and `Sapphire Electric` would
have taken a district on the strength of the single word "Sapphire". A one-token subset
matches a company, not a station. With the floor the join is 38 exact, 5 subset-unanimous,
0 ambiguous.

## What the correction moved

Three states, one full cube build each, reference period, physical view, CO₂ Gg:

| | A = the committed baseline | B = curated province alone | C = province + district |
|---|---|---|---|
| Punjab | 54,441.504 | 57,066.477 | 54,441.504 |
| Sindh | 41,035.667 | 38,581.586 | 41,035.667 |
| Balochistan | 7,668.923 | 7,498.030 | 7,668.923 |
| Khyber Pakhtunkhwa | 14,552.049 | 14,552.049 | 14,552.049 |
| Other | 206.164 | 206.164 | 206.164 |
| national | 117,904.30627 | 117,904.30627 | 117,904.30627 |

**C against the baseline moves 36 of 126 district cells and 9,787 Gg of absolute mass,
with the national total bit-stable** (signed sum 8 × 10⁻⁸ Gg). The largest moves:

| ADM2 unit | before | after | delta |
|---|---|---|---|
| `sindh_kashmore` | 138.244 | 2,763.217 | +2,624.973 |
| `sindh_ghotki` | 4,304.404 | 1,679.431 | −2,624.973 |
| `punjab_dera_ghazi_khan` | 4,441.027 | 2,548.025 | −1,893.002 |
| `punjab_chiniot;punjab_jhang` | 4,561.391 | 5,421.110 | +859.720 |
| `punjab_kasur` | 3,982.091 | 4,518.049 | +535.958 |
| `balochistan_lasbela` | 3,516.970 | 3,672.247 | +155.277 |

TPS Guddu's mass had been sitting in Ghotki, the neighbouring Sindh district its fallback
surface reached, and now sits in Kashmore where the station is — a twentyfold change in one
district's power CO₂.

**The province fix alone would have shipped a 2.625 Mt ADM2 provincial error, and state B
is the proof.** Pooling TPS Guddu under Sindh (correct) while the frame still denied its
district sent its mass to the fallback surface at a cell whose polygon is Punjab; the nested
split then booked it in `punjab_rajanpur` while the ADM1 control said Sindh. The ADM2 product
and the ADM1 product would have disagreed by province, which is a state no published release
has been in. The two changes are one correction and ship together.

## The provincial totals do NOT move, and I reported otherwise before fixing my own defect

Between the first draft of this document and this one I claimed a declared provincial
re-base: four provinces moving 5.26-10.75 Mt per year. That was wrong, and the sequence is
worth recording because the guard was right at every step and I twice read it as an obstacle.

The provincial share vector is `data/province_shares.csv`, read through
`sectors/power/downscale.load_shares`. **It does not read the curated station record.** It is
the control the grid must reproduce. Pooling stations under their curated province, while the
raster still placed each point in its own cell, made the raster disagree with that control -
a Balochistan station adding to Sindh's raster sum while drawing on Balochistan's share. The
ADM1 product is derived from the raster, so it showed the disagreement, and I read a defect
of mine as a re-base.

`pakemis_grid_provincial_check.csv` reported it exactly: 18 `exact_by_construction` rows
breaching 2e-6 in paired, opposite amounts, 0.0083 Mt of coal between Sindh and Balochistan
and 0.0767 Mt of furnace oil between Punjab and Other. **My first response was to pass
`--adm1-may-move` to `measure_spatial_rebase.py`, which made a failing guard pass while the
guard was correctly reporting that the control was broken.** The flag exists for a re-base
whose declared purpose is to move provinces; using it to silence a leak is exactly the misuse
the script's own docstring warns about.

The repair is in `_place_inside_province`: a point whose cell lies outside the province it was
pooled under puts its mass in the curated district's cells **intersected with** the province
mask - the same cell set the ADM2 vector uses, which is what keeps the two views from
disagreeing - and in the nearest cell of the pooled province where no district resolves. The
intersection is not decoration: a district's polygon majority can be the pooled province
while some of its cells are not, and a cell outside the province is the thing being avoided.

Afterwards the provincial check is **exact**: 0 of 920 `exact_by_construction` rows breach
2e-6, and the worst diff over all of them is 0.000000000. The declared-divergence set is
unchanged at 45 rows and still only aviation and railways - power did not join it, because
the mass was placed correctly rather than excused.

So the station-district correction sits BELOW the provincial marginal, which is where a
district correction belongs. Measured against the pre-session baseline with the fix in place,
`measure_spatial_rebase.py 1c9acaf9 "rc63 curated station district" --modules power` passes
**without** `--adm1-may-move` - ADM1 does not move - and records districts only:

| period | ADM2 units moved | gross Mt | net Mt |
|---|---|---|---|
| FY2015-16 | 36 | 2.767170 | -2e-9 |
| FY2016-17 | 36 | 2.394872 | -6e-9 |
| FY2017-18 | 39 | 17.613166 | -1.4e-8 |
| FY2018-19 | 109 | 11.594305 | -1.8e-8 |
| FY2019-20 | 109 | 18.527446 | +2.4e-8 |
| FY2020-21 | 103 | 20.205473 | +1.9e-8 |
| FY2021-22 | 106 | 14.408987 | +5.1e-8 |
| FY2022-23 | 106 | 13.846617 | +6e-9 |
| FY2023-24 | 106 | 9.799279 | +9e-9 |

A pure reallocation inside each province in every period. The reference-year district table
above stands; what is withdrawn is the provincial claim beside it.

Whether the provincial CONTROL should itself be re-based onto the curated record is a
separate question this change does not answer. It would need `province_shares.csv` re-derived
from station records with its own evidence, and it would move published provincial totals.
Nothing here does that.

## rc66: the provincial split follows each year's stations

Everything above concerns where a station is placed INSIDE a province. This section is about
the split BETWEEN provinces, which the sections above describe as a fixed control: "the
provincial share vector is `data/province_shares.csv` ... it does not read the curated station
record." Through rc65 that was the whole truth, and it was the defect. One row per fuel,
measured on FY2023-24, was applied to all nine fiscal years for coal and gas (furnace oil and
diesel took own-year generation for FY2015-16 to FY2019-20; captive gas took its own year).

From rc66 `downscale.load_shares(period)` asks `sectors/power/province_panel.py` for each
year's own split:

| fuel | basis | record |
|---|---|---|
| coal | station tonnage x the rank-default calorific value, the national booking's own basis | `coal_plant_fuel_back_years.csv`, the plant fuel ledger, `coal_energy_booking.csv` |
| gas and RLNG, furnace oil, diesel | station fuel quantity | the plant fuel ledger from FY2019-20; `plant_fuel_quantity_back_years.csv` (NEPRA SoIR 2020 Tables 16 and 19) before |
| bagasse | station generation | `bagasse_generation.csv` |

The committed rows are now the reference year of that series and nothing more: the engine
reads them for FY2023-24 and for callers with no period, and `tests/test_province_panel.py`
holds the panel to reproducing them.

What moved, per fuel, year and province, is `outputs/pakemis_power_provincial_basis_by_year.csv`
(the largest row is coal in Sindh in FY2020-21, -11.63 Mt CO2e), and the rig's record is in
`outputs/pakemis_spatial_rebase_rc44.csv` under "rc66 grid power provincial split by year".
That run passed `--adm1-may-move` for the purpose the flag exists for: a re-base whose
declared intent is to move provincial marginals. The national sum over provinces is asserted
at every grain and is zero net in all nine periods.

Three things this did not change, each deliberately:

- **K-Electric stays outside the split**, as `plant_ledger.in_boundary` has it. Whether the
  national fuel control includes K-Electric is the boundary's question.
- **Two fuel-years keep the reference vector**: diesel in FY2018-19 and FY2019-20, where the
  station record covers under half of the national diesel control. Both are wholly Punjab on
  either reading.
- **Suspect inputs are used as booked**: Sahiwal's FY2021-22 tonnage and Guddu's gas volume at
  an assumed heating value. A split may not correct a national account.

## Guards

- `tests/test_power_province_boundary.py` holds the misplaced set at the known seven, and
  since this change also holds the *outcome*: every boundary station resolves to a declared
  placement rule, no station is left on the fallback surface, and a rescue whose curated
  district would cross a province fails the suite. A **positive control** removes the curated
  districts and requires the five to strand again, so a record that quietly stopped being
  read cannot pass.
- `tests/test_power_province_boundary.py::TestTheCuratedDistrictJoin` asserts the two-token
  floor by name, the crosswalk route for `HUBCO`, and that a poisoned workbook row making
  TPS Guddu ambiguous yields **no** district rather than a chosen one.
- `scripts/measure_spatial_rebase.py` publishes the re-base to
  `outputs/pakemis_spatial_rebase_rc44.csv` and **asserts** the provincial and national
  invariants, exiting 1 rather than reporting a breach. It is run without
  `--adm1-may-move`, because nothing provincial moves and that flag would switch off the
  guard that proves it.
- `PointProjection` now counts crossings, curated rescues and the share each class carries,
  and `grid_plant_province_sources()` publishes them. Before this change `crossings` was
  incremented and read by nothing, so the single most exposed placement in the grid fleet —
  the five boundary stations carry up to 43.9% of a profile-period's spatial pool, RFO in
  FY2015-16 — could not have been checked from any output.

## What is still placed by a proxy, and how much

Coordinates resolve 76 station names; the curated record names a district for 107 stations,
115 name keys after the crosswalk. The gap matters most in the early panel years, where the
pool comes from the generation panel rather than the plant-fuel ledger:

- **Unlocated stations** carry 0–14.9% of a profile-period's pool (worst: HSD in FY2018-19
  at 14.9%, FY2020-21 at 11.7%; gas 1.3–5.0% in all nine years). The curated record places
  all but ≤2.0 percentage points of it.
- **Fuel-unlabelled panel mass** is the larger gap and a different one: 24.4–31.4% of the
  early years' panel GWh carries no fuel label, of which 59–65% is on a real grid station,
  and the curated record supplies a single-fuel label for only 20–34% of it. That is a
  labelling gap rather than a geography gap and is not closed here.

## Climate TRACE, for the record

Climate TRACE supplies no quantity to this inventory. Its activity (MWh) and emissions
(CO₂e) never enter a total: `climatetrace_power_assets_pak.csv` is read only by
`pkinv.sectors.power.benchmarks_plants`, which is imported only by the report driver and
never by the engine. It is used as a diagnostic
(`outputs/power_climatetrace_plants_fy2023_24.csv`) and as **corroboration** of a GEM
coordinate, where a disagreement beyond 5 km aborts the ingest.
`sources/Power Plants/README.md` records why it is not a target: its Pakistani coal assets
imply 2,431 g CO₂/kWh against a ceiling near 1,100, so "Climate TRACE is a divergence to
explain, not a number to hit."

One caveat belongs in the open, and `validation_catalog.csv` already carries it: 29 of the
52 rows in `plant_coordinates.csv` are themselves Climate TRACE derived, so for those
stations the agreement check is self-agreement and carries no evidence.
