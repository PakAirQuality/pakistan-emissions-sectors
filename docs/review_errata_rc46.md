# Review errata — the twentieth review (rc45 → rc46)

The reviewer's rc46 program was audited premise-by-premise before planning. Most premises
held; the ones below did not, and are recorded so the next reader does not re-fix what is
already fixed or chase a number that is not a stream. Each erratum names where the truth
lives in the tree.

## E1 — "Equal weight per 0.05° cell is not equal weight per square kilometre" (already fixed)

The review prescribed computing intersections in an equal-area CRS to fix the latitude-area
problem. The defect was real and was fixed at rc44/rc45, before this review arrived:

- Polygon intersections are computed in **ESRI:54034** (World Cylindrical Equal Area) in
  `scripts/build_adm2_intersections.py`; the shipped product is
  `data/gis/adm2_intersections_267x340.csv`.
- Line lengths are metric everywhere: `src/pkinv/core/gis/lines.py` accumulates km with a
  per-segment cos-latitude correction, and `scripts/build_road_network.py` uses the full
  WGS84 geodesic (`pyproj.Geod.inv`).
- `uniform` has meant uniform **per km²** since rc44: `src/pkinv/core/gis/proxies.py`
  `as_measure()` applies `cell_area_km2` per the declared semantics in
  `data/grid_proxy_semantics.csv`, and an unregistered proxy name **raises** rather than
  silently spreading per square degree.

No further change is made for this item in rc46.

## E2 — "the 29.42 Mt industrial solid-fuel residual" is a bound, not a block

The figure is an EDGAR-minus-engine **benchmark residual** (`data/scope_registry.csv`,
`outputs/industry_fuel_ledger_2024.csv`). It has never been inside any published total, and
it is already decomposed into priced NE claimants (cement kiln fuel, brick coal, captive
coal, bagasse) plus a 7.0 Mt typed refusal for industrial coal/petcoke. The rc46 work is
activating claimants through the written activation gate and closing the refusal with the
coal-by-consumer series — not replacing an estimate, because there was no estimate.

## E3 — the plant-month panel already exists

"Build the plant-month panel from PBS and NEPRA" was done before this review:
`data/activity/power/generation_monthly.csv` carries 534 plants × nine fiscal years
(PBS FY2015-16..FY2020-21, NEPRA SIR FY2021-22..FY2023-24). The live constraint is fuel
labelling coverage (`generation_monthly_coverage.csv`), not panel existence. Likewise
plant-specific coal calorific values (`outputs/power_implied_coal_cv_fy2023_24.csv`) —
the review's "do not use one national coal NCV" was already the tree's position.

## E4 — the reviewer's coal table is the HDIP series, and its numbers verify

"Finance Division Statistical Supplement 2024-25, Table 14.1" is the HDIP coal-by-consumer
series (the same family the repo knew as PEY Table 4.4). The document was acquired at rc46
Wave 0 and transcribed (`data/activity/industry/coal_by_consumer.csv`); all nine years of
the review's quoted power/brick/cement values reproduce exactly, and the review's caution
about the FY2023-24 brick figure was vindicated — it was revised 1,564 → 1,129 kt between
editions, and both vintages are retained.
