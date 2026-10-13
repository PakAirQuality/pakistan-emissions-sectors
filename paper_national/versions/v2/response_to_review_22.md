# Response to the reviewer

Working draft. Each item names the product and the test that answers it, so a claim here can
be checked against the repository rather than taken. Items still in progress are marked as
such; nothing below is stated as finished before it is.

> **Status of the two items that move numbers.** The classification migration (item 6) is
> complete and shipped. The power coal-energy re-base (item 2) has its evidence complete and
> its consequence priced through the engine; the reference series has not yet been moved, and
> this letter will carry the moved pins and the per-year causes when it is.

---

## General remark: "improvements elsewhere have not been incorporated into these files"

This was correct and it was the most useful sentence in the review. Of the eight shipped
evidence products most relevant to the manuscript — the forest-flux adjudication, the F-gas
leak-rate adjudication, the BTR comparison, the release axis fingerprints, the citation-pointer
audit, the minerals-panel screening, the power coal-energy adjudication and the coverage matrix
— **none was cited in either version of the paper.** Four lanes of evidence existed in the
repository and reached no reader. The revision's first job is therefore integration, not new
analysis, and the items below say in each case whether the answer is new work or an existing
product finally brought into the manuscript.

---

## Item 6 — classification scheme (resolved)

**Conceded as stated.** Sector 3 carried UNFCCC CRT codes while sectors 1, 2 and 4 carried
IPCC 2006, and no test asserted a scheme.

**What was done.** IPCC 2006 is now canonical, with a versioned CRT crosswalk published as
`outputs/pakemis_category_crosswalk.csv` (29 rules; 12 resolve components). Target codes were
read from IPCC 2006 Vol.1 Ch.8 Table 8.2 — *not* from the project's own BTR crosswalk, whose
numbering is shifted (it books urea at 3.C.2, which Table 8.2 uses for liming) and which
conflated indirect manure N₂O with indirect soils N₂O, one of the distinctions the review asked
to separate.

**Mapped at component grain, as asked.** Manure management splits: CH₄ and direct N₂O to
**3.A.2**, indirect (volatilisation) N₂O to **3.C.6** — which leaves the livestock block
entirely. Managed soils splits: 6 direct components to **3.C.4**, 9 indirect (both
volatilisation and leaching/runoff) to **3.C.5**. Enteric 3.A.1, rice 3.C.7, residue burning
3.C.1.b, urea 3.C.3.

**Nothing was invented.** CRT 3.I and 3.J have no IPCC 2006 counterpart that could be asserted
without guessing an allocation; they are carried with their notation status under a
`(crt-only)` sentinel, and the guard asserts an `unmapped` row names no code.

**Identifiers are unmoved.** `component_id`, `source_stream_id` and `estimate_status` encode no
code, so no shipped identifier changed. The migration keys on `component_id` throughout,
because the move is **not injective on code text**: 3.A, 3.B, 3.C and 3.D all exist on both
sides with different meanings, and Waste is 4 in IPCC 2006 and 5 in the CRT.

**Conservation, before and after.** 28 of 29 invariants are bit-identical, including every
native-gas and CO₂e aggregate by period × gas × configuration × geography, the 202-component
set and both national pins. The single intended change is `national_category_gas.csv` going
50 → 52 rows as the splits become their own categories, with its aggregate *by gas* unchanged.
The split pairs sum to the external audit's single-category values to six decimals:

```
3.A.2 19.330010 + 3.C.6  1.898470 = 21.228480  vs the audit's 3.B 21.228487
3.C.4 16.434470 + 3.C.5 12.091480 = 28.525950  vs the audit's 3.D 28.525954
```

**Three silent failures the migration exposed**, each a default hiding a miss: the source-stream
product shipped 24 rows containing the literal string `"unresolved"`; a cross-sector ledger read
3.C.4 as NE because a dict comprehension was last-write-wins over a code that now has two rows;
and a related-work section printed a completeness total no claim reached.

**All sectors audited, not only the ones that moved.** Sectors 1 and 2 (50 live codes) agree
code for code between the two schemes and therefore carry no crosswalk rule — that absence is
the audit's finding, not an omission, and it is why the hybrid survived two reviews. Sector 4
renumbers wholesale to CRT 5.

**Guard.** `tests/test_category_crosswalk.py` (10 tests) asserts both directions and sweeps the
code columns. The sweep is not redundant: the conservation check aggregates at a grain *no code
appears in*, so it passed while the entire monthly lane still carried retired codes. Report:
`docs/classification_scheme.md`.

---

## Item 2 — the preferred power reference (re-based; legacy pins retained as a published control)

**The framing in the review is generous to the published control, and the evidence does not
support treating this as a tie.**

*What drifts is the calorific basis, not the generation.* NEPRA Table 3's implied conversion is
**0.4474 TOE per tonne — 18.73 TJ/Gg — held constant across FY2015-16..FY2020-21 to 0.016 per
cent** while the fleet went from imported bituminous to 92 per cent Thar lignite, and then
breaks *upward* (25.27, 21.40, 20.02) exactly as the fleet's physical calorific value falls
20.34 → 13.01. A measured energy cannot move the wrong way against its own fuel.

*The supply bound survives every rescue the review asks for.* Matched period, stock change, coal
rank, moisture, calorific value and fleet coverage are each tested separately in
`outputs/pakemis_power_reference_audit.csv` (35 rows), which publishes a verdict **and a rescue
requirement** per basis. Rescuing Table 3 in FY2023-24 needs a stock drawdown of 42 per cent of
a year's national coal supply, or a lignite share of 41.6 per cent where NEPRA prints 92.0 per
station.

*The reviewer's independence question was right, and the answer is uncomfortable.* The
alternative the release already publishes (38.45 Mt) rides a **circular** route: its calorific
values are derived as generation × a printed heat rate / mass, so its energy contains the
generation it is later divided by, and its implied efficiency reproduces the regulator's own
print to within 0.1 percentage point in all five years. It is a plausibility screen, not
independent corroboration. The manuscript's earlier claim that "the physical test picks one" is
withdrawn.

*A non-circular account now exists and is priced through the engine.*
`outputs/pakemis_power_coal_configurations.csv` publishes four accounts, each a coal mass times
a calorific value — C0 Table 3; **C1 the stations' own metered coal at IPCC rank defaults, no
heat rate anywhere in it**; C2 HDIP's tonnage at the same rank composition; C3 the circular
heat-rate route. C1 and C2 differ only in whose tonnage they take, which separates the mass
question from the conversion question. The ratio C1/C0 decomposes exactly into (station mass /
HDIP mass) × (fleet rank calorific value / 18.73), and **both terms cross unity**: the mass
term runs 0.569–1.423 and the calorific term 0.635–1.377. Measured in log space so the two are
comparable, the calorific term is the larger in **seven of nine years**, and two to three times
the mass term in the three years carrying the biggest moves. The two years where the mass
account dominates are real disagreements between the records — FY2016-17, where the stations
report 445–534 kt against HDIP's 859.6, and FY2020-21, where they report 13,111 against 9,215.
An earlier draft of this response said the mass term stayed inside 0.74–0.99; it does not, and
the correction is recorded here rather than made quietly.

*The test that separates them, over the whole panel.* Implied net efficiency against the
28–47 per cent band (the wider of the two envelopes in circulation, because for a refutation the
wider band is the harder test):

| fiscal year | C0 | C1 |
|---|---|---|
| FY2015-16 | 13.9 | 29.4 |
| FY2016-17 | 22.3 | 29.8–36.8 |
| FY2017-18 | 51.1 | 29.7–37.9 |
| FY2018-19 | 53.1 | 37.5–38.4 |
| FY2019-20 | 45.1 | 34.7 |
| FY2020-21 | 57.5 | 34.4 |
| FY2021-22 | 29.6 | 38.7 |
| FY2022-23 | 22.8 | 34.9 |
| FY2023-24 | 18.9 | 35.2 |

**C0 is inside the band in 2 of 9 years; C1 in 9 of 9**, and in the four years whose mass is
reconstructed the *whole interval* is inside, so the result does not depend on where in the
interval the reconstruction lands. C2 — HDIP's tonnage at the same rank composition — is
inside in 6, which locates the damage: the conversion accounts for most of the implausibility
and the tonnage for the rest. The verdict ships as a column, and a test derives each one from
its own row and pins both counts, so this paragraph cannot drift from the product.

*Reconstruction, with its coverage and uncertainty stated.*
`outputs/pakemis_power_fuel_reconciliation.csv` (50 rows, nine years) carries coal mass, rank
with origin evidence, calorific values, net and gross energy in separate columns, generation
with a declared basis, the public/captive split, the K-Electric treatment and page-level
pointers with printed column headings. Evidence grades: 29 printed, 8 printed-other-edition,
4 reconstructed, 9 comparison. The four reconstructed lanes are the only plant-years no edition
prints, and each carries an interval with its reason rather than a point. **No constant
correction is applied, and none would be defensible: the required correction changes sign.**

*Power and industry move together.* HDIP's coal consumption *is* its coal supply — the
allocation identity closes to a kilotonne in thirteen of fourteen years — so the sectoral split
redistributes a fixed total and the national effect is a difference of two numbers.
`outputs/pakemis_coal_sector_reallocation.csv` publishes both deltas per year. The industrial
residual is **not booked**: which non-power consumer took the coal is unresolved, and a
diagnostic gap is never inserted as a residual. It ships beside the total with an independent
cross-check — the brick-kiln fleet bound, a kiln census sharing no input with NEPRA's
per-station metering. As booked, brick sits below that fleet's own floor in three of nine years;
with the residual all nine are inside. That is a consistency argument, not a proof: six years
were already inside and the bound is wider than the quantity in dispute.

*A defect found on the way, and conceded.* The allocation-identity builder read the
consumer table with no `revision_status` filter where its own supply reader had one, so it
published a superseded print (brick kilns 1,564 instead of 1,129 kt). Emissions were unaffected
— the engine selects vintages through a booking policy — but the manuscript carried the
superseded figures and is corrected. The declared exception that masked it stated a reason that
*inverted* the source note it cited.

### The re-base, performed

**The reference now books the station account.** Public-power coal energy comes from
`data/activity/power/coal_energy_booking.csv`, one row per fiscal year, declaring which of
the four published accounts the engine books with the superseded Table 3 figure and the ratio
beside it. `fuel_consumed.csv` is untouched and still a faithful Table 3 transcription — which
is exactly what lets the refuted control ship beside the reference rather than disappear. The
engine **raises** on a year the booking table does not cover rather than falling back to
Table 3: a silent fallback would make the reference depend on which years someone had got
round to booking, and the failure would look like data.

**The pins moved, for the first time since the agriculture correction:**

| | previous | re-based |
|---|---|---|
| configuration L | 469.63822 | **451.85782** |
| configuration S | 464.50543 | **446.72502** |
| grid 1.A.1.a | 57.82049 | **40.04008** |

Both configurations move by the same −17.78041, because the coal account is
residential-configuration-independent. **The old pins are not lost**: the retained legacy
control reproduces 469.63823 in `national_configurations.csv`
(`power_table3_legacy_control`), which is the published total to the fifth decimal and the
cross-check that the re-base changed the account and nothing else.

**The nine-year series, with the per-year cause.** `outputs/pakemis_power_coal_rebase_ledger.csv`
gives each year the two coal energies, the mass and calorific terms whose product *is* their
ratio (asserted, not asserted-in-prose), which of the two is larger, and the national
consequence taken from the legacy axis in the structural trajectories so a reader can
reproduce it from shipped products:

| fiscal year | published | re-based | move | ratio | dominant term |
|---|---|---|---|---|---|
| FY2015-16 | 401.09 | 400.898 | −0.19 | 0.473 | calorific |
| FY2016-17 | 427.074 | 426.581 | −0.49 | 0.677 | **mass** |
| FY2017-18 | 450.742 | 454.944 | +4.20 | 1.532 | calorific |
| FY2018-19 | 446.846 | 451.048 | +4.20 | 1.400 | calorific |
| FY2019-20 | 446.733 | 452.628 | +5.89 | 1.301 | calorific |
| FY2020-21 | 479.511 | 490.583 | +11.07 | 1.669 | **mass** |
| FY2021-22 | 497.774 | 490.488 | −7.29 | 0.766 | calorific |
| FY2022-23 | 456.621 | 445.236 | −11.38 | 0.652 | calorific |
| FY2023-24 | 469.638 | **451.858** | −17.78 | 0.538 | calorific |

**Three trend consequences, all of them weaker than the previous version's claims, and all
stated rather than absorbed:**

1. **The peak moves.** It was FY2021-22 at 497.77; it is FY2020-21 at 490.58, with FY2021-22
   at 490.49 — 0.095 Mt below. The position is not robust and the manuscript says so instead
   of asserting a year.
2. **The nine-year increase falls from 68.55 Mt (17.1%) to 50.96 Mt (12.7%)**, and the
   reference year falls 17.78 Mt while FY2015-16 falls 0.19, so almost the whole move lands
   on the decadal difference.
3. **The trend no longer resolves under all three dependence settings.** Reference
   (parameter-typed) 12.75–93.01 Mt and time-correlated 39.96–64.04 Mt both exclude zero;
   **time-independent is −12.48 to +117.11 and does not.** The previous edition said no end of
   the bracket left the decadal change spanning zero — true of the larger change, false of
   this one under the same intervals. Corrected on the record.

**The monthly evidence position gets slightly worse, not better.** TE4 (flat or weakly
constrained) rises from 52.13% to 54.18%, because public-power coal is one of the few streams
with reconstructed monthly activity and booking a smaller coal energy shrinks it.

**The selection rule is rewritten, and the argument it replaced is withdrawn.** The old rule
took the regulator's statistic *because* Pakistan's CRT filing agreed with it on solid fuels
to 2 per cent, held to be standing counter-evidence. That agreement is not evidence: the
filing is compiled from the same HDIP series, and `data/validation_catalog.csv` has carried
that row at independence class `none` throughout — the prose contradicted the register beside
it. Both ratios now ship: **Table 3 / CRT = 1.021, booked / CRT = 0.665.**

**Independent confirmation from a diagnostic that was not built for this.** `heat_rate.stability()`
now takes a basis argument and runs the same check on both accounts over the *same*
generation. Table 3's coal: 19.3–58.4%, spread **3.03**, verdict UNSTABLE, above the ceiling
for any coal plant ever built. The booked account: 34.6–39.3%, spread **1.14**, verdict
stable. Nothing on the generation side changed. The test asserts both halves, because either
alone could pass for the wrong reason.

**What the re-base does NOT claim.** The industrial residual is still not booked — which
non-power consumer took the coal is unresolved, and it ships beside the total. The largest
*unresolved* structural axis is now the sewer methane correction factor at 9.07 Mt, not the
coal basis; the coal fork was decided on evidence rather than carried, and the refuted account
is excluded from the priority ranking of open choices because it is not an open choice.

Reports: `docs/power_coal_energy_basis.md`,
`outputs/pakemis_power_coal_rebase_ledger.csv`, `scripts/check_pins.py` (the declaration).

---

---

## Item 3 — the gas boundary and the leak deduction (resolved, with one gap named)

**The premise does not hold for three of the four streams, and the reason is a measurement
point.** The leak booked at 1.B.2 is *post-meter*: downstream of the utility sales meter,
upstream of the burner. Each combustion module starts from gas *delivered and sold*, measured
at that same meter, so the leaked molecules are inside the original quantity by construction
and removing them is a correction rather than a second deduction. This is checkable rather
than assertable: `outputs/national_gas_closure.csv` gives every stream a `metering_basis` from
a closed vocabulary, and the six streams in the post-meter leak base are exactly the six whose
basis reads `delivered-sold; also metered-downstream-of-loss for the leak factor`. The three
that are not in the base are marked so. `gas_TJ` stays gross; the leak is booked once. The
closure identity aborts the build rather than reporting a discrepancy, and nine tests cover it
including a positive control that breaks the identity on purpose.

**Estimated leakage is not unaccounted-for gas**, and the two are never equated: 23.83 per
cent of UFG would have to be physical loss for them to agree, and no Pakistani measurement
establishes that share.

**Conceded, and priced rather than resolved:** 756 MMCFD of fertilizer feedstock gas sits
inside the post-meter leak base and outside every combustion module. The leak factor's own
lineage row defines its activity as gas consumed for *combustion end uses*, so applying it to
feedstock has no behavioural basis — and no measurement supports either treatment. It ships as
a named configuration worth **−1.43 Mt**, the largest single unpriced number the gas ledger
had surfaced.

**The one genuine gap, now named — and larger than I first estimated.** Power grid gas
(1060.13 MMCFD, 1.A.1.a) is `reconciled_different_meter`: its activity is NEPRA Table 3 TOE, a
consumed-reported basis, not OGRA delivered sales, so the measurement *point* is not
established against the customer meter. An earlier draft of this response put the quantity at
stake at about 0.11 Mt. Derived rather than estimated, the regulator's two publications differ
by **26,672 TJ on this stream, 8.5 per cent — up to 1.48 Mt CO₂e** at the gas combustion
factor. That makes it the *largest* unestablished quantity in the gas account, bigger than the
1.43 Mt feedstock inconsistency it had been compared against as "small beside" it. The band is
0 to 1.48 Mt because an unknown share is the heating value the plant sum assumes (implied
736 Btu/scf) rather than a quantity; the decomposition is the open question and settling it
needs the two publications' series for the same twelve months, which nothing held prints
together. The gap now has its own row in `outputs/national_gas_closure.csv`
(`not_established_declared`) where the account previously had none. Report:
`docs/gas_boundary.md`.

---

## Item 4 — the dung residual (resolved; nothing distributed)

**The two sides do not measure the same quantity, and that is the finding.** L is all excreted
nitrogen leaving manure management for fuel use, by any burner anywhere; S is formed cake
entering a sampled dwelling, by questionnaire construction. Commercial tandoors, eateries and
on-farm burning are inside L and outside S by definition. Three further scope differences run
the *wrong* way — L covers three livestock species where the survey records "dung cake" with
no species, L has an age dimension the survey has none of, and L carries no
fuel-preparation-loss term at all — so closing any of them *raises* L.

**No parameter movement closes it.** The ash fraction is the only free parameter binding the L
chain, and across its declared 15–35 per cent span L moves 51.83 to 67.78 Mt. The gap is
46.77 Mt.

**The falsifiable statement is about the assignment, not the mass.** L is coherent as a
household quantity only if 72.6 per cent of households burn cake at the observed intensity, or
the observed 14.8 per cent burn 27.2 kg per household per day against the observed 5.55.
Neither is observed.

**Nothing is distributed.** `outputs/national_dung_variants.csv` prices four destinations
beside the S total and adopts none; under S the residual is a typed zero on an unallocated
row, not an assertion that the mass vanished. What would settle it is a national dung-cake
prevalence measurement plus a commercial-fuel survey; the repository holds neither, and a
holdings search for census cooking-fuel tabulations returns nothing.

**Conceded:** two engine docstrings state 58.69 Mt where the engine computes 58.74144 — a
pre-re-base value that survived the agriculture correction. Corrected. Report:
`docs/dung_destination.md`.

---

## Item 8 — the validation register (existed; now stated)

The register the review asks for exists with every field listed, and the manuscript did not
name it. It holds **102 entries**, each carrying the property tested (magnitude 50, timing 20,
geography 32), module, grain, comparator and version, period and boundary on each side, the
inputs the two sides share, an independence class, a calibration/validation/corroboration/
declared-absence classification, the output holding its result, and — for all 102 — an explicit
interpretation limit.

The independence classes are the point: **only 11 entries compare against an independent
compilation.** 45 are partial, 20 share a large part of their inputs, 2 share an upstream
statistic outright, and 4 are internal identities labelled as such. Seven entries are
*calibrations* and are separated, because an input fitted to a comparator cannot then be
validated by it. Eleven are **declared absences** — checks the inventory would want and cannot
make — carried in the register rather than omitted, so the gaps are counted beside the checks.
The supplement now states all of this and points at the register.

---

## Item 9 — uncertainty inspectability and the Sobol question (answered)

**The Sobol analysis runs on a surrogate, and the supplement now says so in those words.** The
engines are evaluated once for the component list; the sampled model is then a closed-form
mean-preserving multiplicative lognormal over those components. Nothing is re-run. For the two
modules whose ensembles are *injected* rather than re-expressed — waste and fugitives — the
indices are therefore **not a decomposition of the reported ensemble**.

**The size of that gap is measurable, and it is largest where it matters.** The wastewater
effluent factor is sampled in the waste engine as a bounded split-triangular distribution in
log space, which is *median*-preserving (median 0.005, mean 0.01608). The surrogate matches its
log-variance exactly but is *mean*-preserving (mean 0.005, median 0.002196). Its variance is
7.6 × 10⁻⁴ as sampled against 1.05 × 10⁻⁴ in the surrogate — a factor of 7.3 — and its
total-effect index is **0.0487 as published against 0.275 on the ensemble's own draws, a
factor of 5.6**. At 0.275 it would stand at or above the top-ranked parameter in the published
table, whose module is not injected and whose index is therefore directly comparable. The
consequence — that the largest single driver of the national upper tail appears in neither
published priority ranking — is now stated rather than left to be inferred.

**Conceded and repaired:** the structural ranking excluded that axis and justified the
exclusion in a code comment asserting it "leads the PARAMETRIC ranking". It does not and is
not in it — it is seventh in the surrogate table and therefore outside the published top five.
The exclusion rests on its first half alone (an endpoint declared *not* equally probable with
the reference should not be ranked beside co-equal readings), which is sufficient; the false
half is removed and the honest pointer put in its place.

**Also stated plainly:** only total-effect indices ship. First-order indices and the derived
interaction were withdrawn as typed absences because ΣSᵢ reached 1.322 against an exact bound
of 1, making the derived interaction negative on 142 of 151 rows. Carrying the measurement over
a sixteen-fold range of sample size shows ΣSᵢ swinging 0.427 → 1.322 → 1.159 while ΣS_Ti holds
between 1.021 and 1.030, which locates the failure in the estimator, not the model. What is
withdrawn is an estimate, not a finding.

---

## Item 7 — spatial products (methods written; station re-base performed; figure in progress)

The spatial methods the review asks for were committed registers the supplement never named.
It now names them: five committed 0.05° proxy rasters with source, vintage, licence and
SHA-256 (WorldPop constrained 2020; ESA WorldCover v200 built-up and cropland 2021; FAO GLW4
2020; a derived manure surface), two manual acquisitions (MapSPAM 2020 V2r2 rice, VIIRS fire
detections), and a **declared two-to-three-year vintage offset** — every surface predates the
reference period, so a spatial proxy here is a versioned snapshot and never a measurement of
the reporting period.

Four registers make the allocation inspectable: a per-stream proxy table, a geometry table, a
geometry-set table, and a per-stream-year weight registry of 1818 rows and 27 columns carrying
geometry and surface vintages *separately*, the substituted-surface share, the period a
borrowed pattern came from, and a pattern hash that makes "borrowed" checkable rather than
labelled. The time-basis vocabulary is four narrow classes: annual observed activity (795
stream-years), static structural (615), reference-shape backcast (306) and substituted surface
(46). Being the reference year does not make a 2021 snapshot an observation of FY2023-24, and
an earlier vocabulary that implied otherwise labelled 196 stream-years and 632.9 Mt in a way
that invited exactly that reading. Substitutions are fail-closed: a fallback class absent from
a committed allow-list refuses the release fixpoint.

### The station re-base, performed

The review was right that the spatial placement of power stations needed correcting, and the
correction is larger than the audit it came from. `docs/power_station_geography.md` is the
full report; the four things that matter here:

**1. The province of a station is now taken from its curated record, not from the raster
cell.** `coal_plant_coordinates.csv` carried a column called `Province` that
`scripts/ingest_coal_plant_coordinates.py` had filled *from the grid*, so China Power Hub
sat in Sindh while Hub Power, 1.11 km away in the same 0.05° cell, sat in Balochistan from
its own record — two stations on one site in two provinces, invisible to any check that
compares a table against the raster. The column is renamed `raster_province`, and
`core/geography.py::curated_province()` raises on a province name in no vocabulary rather
than letting a caller fall back to the raster.

**2. The district now comes from a record this repository already held and did not read.**
`data/sectors/power/activity/grid_plant_district.csv` places **107 thermal stations across
ten fiscal years** with a `district_printed` and an `adm2_id` resolved against
`data/adm2_canonical.csv`. Coordinates resolve 76 station names; this record names a district
for 107, and the spatial allocation never consulted it. It is used for geography only, the
scope its own banner declares — its emission columns are held apart in
`data/sectors/power/evidence/workbook_emissions_crosscheck.csv` (755 rows) explicitly to be
compared and never adopted, because those factors are a literature range and the bagasse SO₂
factor is an unsourced zero by the compilation's own admission.

**3. The exposure was the largest in the grid fleet and nothing measured it.** Five of the
seven boundary stations had their district *refused* — the provincial marginal is a control
and the district is not, so a point whose ADM2 polygon left its pooled province dropped to a
proxy surface. Those five carry up to **43.9% of a profile-period's spatial pool** (furnace
oil, FY2015-16) and 13–24% in most profile-years. The counter that recorded the refusal was
incremented and read by nothing, so this could not have been seen from any output; it is now
published per station in `outputs/pakemis_power_province_boundary_audit.csv`
(`adm2_placement`), and no station is left on a fallback surface.

A named district survives the control that defeated the point. A 0.05° cell is 5.5 km across
and the simplified polygons disagree with the records along a provincial line; a district is
adjudicated by the majority of its own cells in the ADM1 control — Lasbela 703 cells
Balochistan, Kashmore 128 Sindh, Karachi 124 Sindh — so naming it lands the mass in the right
district *and* keeps the province.

**4. What moved: districts, and not provinces.** Across the nine years the correction moves
36 to 109 ADM2 units per period, 2.77 to 20.21 Mt gross, with a net of order 10 to the minus
8 Mt in every period - a pure reallocation inside each province. In the reference year
`sindh_kashmore` goes 138.244 to 2,763.217 Gg as TPS Guddu lands in its own district, taken
from `sindh_ghotki` (4,304.404 to 1,679.431); `punjab_dera_ghazi_khan` 4,441.027 to
2,548.025; `balochistan_lasbela` 3,516.970 to 3,672.247. No provincial total and no national
total moves. `scripts/measure_spatial_rebase.py` publishes this and asserts those invariants,
and it is run **without** `--adm1-may-move`.

**A defect of ours, and the way we first mishandled the guard that caught it.** An
intermediate version of this change pooled each station under its curated province while the
grid raster still placed every point in its own cell. The provincial share vector
(`data/province_shares.csv`) does not read the curated record - it is the control the grid
must reproduce - so the raster began to disagree with it: a Balochistan station added to
Sindh's raster sum while drawing on Balochistan's share.
`outputs/pakemis_grid_provincial_check.csv` reported it precisely, as 18
`exact_by_construction` rows breaching 2e-6 in paired, opposite amounts (0.0083 Mt of coal
between Sindh and Balochistan; 0.0767 Mt of furnace oil between Punjab and Other), and for a
time we described the resulting ADM1 movement as a declared provincial re-base and passed
`--adm1-may-move` to publish it. That flag exists for a re-base whose purpose is to move
provinces; we used it on a leak, which made a correct guard quiet.

The repair places a point whose cell lies outside its pooled province into the curated
district's cells intersected with the province mask - the same cell set the ADM2 view uses -
falling back to the nearest cell of that province. The provincial check is then exact: 0 of
920 rows breach 2e-6 and the worst difference across all of them is 0.000000000. The
declared-divergence set is unchanged at 45 rows, still aviation and railways only; power did
not join it, because the mass is placed correctly rather than excused. Whether the provincial
control should itself be re-based onto station records is a separate question with its own
evidence requirement, and this change does not answer it.

**On Climate TRACE, since the station geography invites the question.** Climate TRACE
supplies no quantity to this inventory. Its MWh and CO₂e never enter a total: the ingested
table is read only by a diagnostic module that the engine never imports. It is used for a
published comparison and to *corroborate* a GEM coordinate, where a disagreement beyond 5 km
aborts the ingest. One caveat we should have printed and had not: 29 of the 52 rows in
`plant_coordinates.csv` are themselves Climate TRACE derived, so for those stations the
agreement check is self-agreement and carries no evidence —
`data/shared/evidence/validation_catalog.csv` says so and the manuscript did not.

*Still to come in this item:* the gridded GHG figure with its missing N₂O panel.

---

## Item 1 — a fixed, hash-locked review version (defects found and fixed; two author items open)

The review asked for a version a reader can verify byte for byte. Auditing that produced
three defects, and all three were in the machinery that was supposed to prevent exactly this.

**1. None of v2's PDFs was hashed anywhere in the release record.** The fixpoint's paper-hash
sidecar is driven by `PAPER_GLOBS`, which named the *main* version's two filenames literally
— `paper_national.pdf` and `supplement.pdf`. v2's files are `paper.pdf`, `submission.pdf` and
`technical_supplement.pdf`, so the version actually going to the journal appeared in
`outputs/pakemis_paper_hashes.csv` zero times. The review named the technical supplement;
measured, it was all three files. The globs now take every version directory, so a v3 needs
no edit — a literal filename is how an artefact stays unhashed while the manifest's own
description implies otherwise, which this project had already paid for once in the air lane.

**2. The quantity sweep did not cover v2 at all, and a re-based number had already gone
stale behind that gap.** `COVERED_DOCUMENTS` lists eleven documents and `national-v2` was not
among them, so roughly 244 printed quantities checked against nothing. Inside that gap sat a
real error: the paper printed three public-power readings — 38.45, 40.04 and 44.05 Mt — against
three national totals, 450.3, **469.64** and 455.9. The middle pair is wrong. 40.04 Mt is the
re-based reference, whose total is 451.86 and is printed correctly two sentences earlier in
the same paragraph; 469.64 is the legacy Table-3 control, whose power figure is 57.82. The
re-base moved the power account and the sentence kept the old total beside the new reading.
The sentence now carries four readings against their own totals and says which one is
retained-and-not-preferred. v2's in-place coverage has gone from 211 of 244 quantities to 228,
and the eighteen that remain are listed rather than left implicit: the legacy pin, the
sewer-connected-population alternative, one spatial time-basis mass, the surrogate's sample
size, and seven sample-size-sweep diagnostics that no product yet publishes.

**3. Two shipped labels were 17.78 Mt stale, beside the correct value in their own rows.**
`outputs/national_configurations.csv` carries a `family_role` for each configuration, and two
of them had the pre-re-base grid figure typed into the prose: the reference read "grid 57.82
Mt" where it is now 40.04, and the K-Electric member "grid 61.83" where it is 44.05 — each off
by exactly the re-base. Both rows carried the right number in `alternative_value_Mt` at the
same time. No test could see it, because it is prose inside a data file. The figures are now
formatted from the row that holds them, so the class is removed and not just the two
instances.

**What is now in place.** The release dance is unchanged and still enforced: content commit,
fixpoint, a check that the manifest's `describes_commit` equals that commit with a clean tree,
artefacts commit, then the recorded test run. The hash-locked archive is built by
`scripts/build_deposit_zip.py` and `build_verification_bundle.py` on the rc47–rc49 precedent,
and now includes every version's PDFs.

**Two things in the availability statements are the author's and remain open**, and we would
rather leave them visibly unfilled than fill them with something that is not yet true: the
**dataset DOI** (reserved, not minted — the release script waits on it) and the
**repository-native review link**. The release-specific commit and the reproduction
instructions will be filled from the fixpoint record at submission, and the ODbL-derived
tables that cannot ship inside a primary CC-BY data record are a third decision we have
recorded rather than taken.

---

## Item 5 — the agriculture and wastewater specifications (documented, not re-modelled)

Each of the three things the review asks to see specified was executable in code and absent
from the prose. None of them changes a number; all three are now stated.

**The livestock census bridge.** Enteric fermentation and manure management ride a stock in
every year, enumerated in the census year and projected between censuses. The reference herd
is the 2024 census; the historical years take a **calendar-year** driver, because no fiscal
enumeration of livestock exists. The phase shift that implies is priced rather than waved
through: FAOSTAT's stock for calendar year $Y$ is a point on a smooth inter-census
projection, the fiscal year ending in $Y$ is centred half a year earlier, and re-driving both
categories on the midpoint of $Y-1$ and $Y$ measures what the mapping leaves behind. The
interpolation is faithful *here* and would not be everywhere: the interpolated series is a
deterministic geometric projection off two censuses rather than an observation with a shape
of its own, and a linear midpoint on a geometric series understates by under a tenth of a
per cent at these growth rates.

**The solid-waste specification.** One continuous monthly first-order-decay recursion from
1960, with deposits before the panel back-projected on the panel's own earliest compound
growth rate, and a no-spin-up scenario that prices the assumption rather than asserting it is
small. Generation rates, collection, composition and sanitation shares are held fixed across
the series, so the historical trend represents demographic change and accumulated deposits
and **not** observed change in waste-management practice. That restriction is a property of
the evidence, and the series should not be read as a management-practice trend.

**The effluent denominator, stated as the hypothesis it is.** The two wastewater gases do not
share a denominator. The methane side splits the population across five sanitation pathways
with a correction factor for each, and open defecation carries an explicit zero rather than
being dropped, because material left on open ground decomposes aerobically and the Guidelines
offer no anaerobic pathway for it. The nitrous-oxide side applies the effluent factor to
nitrogen generated by the **whole** population, with no pathway split and no sludge-nitrogen
term, following the 2006 Tier 1 equation as written — sludge is largely not collected in
Pakistan, so there is no stream to deduct. What that makes the N2O denominator is a
hypothesis about where effluent nitrogen reaches a nitrifying environment, not an
observation, and the supplement now says so and prices the strict aquatic-discharge reading
beside it rather than adopting it.

---

## Item 10 — coverage, and forestry as a deliberate exclusion

**The silent-absence class the review was right to suspect is closed, and I can now say so
from a measurement rather than from memory.** The campaign that preceded this revision found
28 IPPU categories carried as not-estimated by the sector's own gap matrix with **no row at
all** in the national completeness table — absences that no reader could count because
nothing recorded them. Re-measured today, `outputs/completeness.csv` holds **138 rows**
(54 E, 71 NE, 8 IE, 4 NO, 1 NA) against the 108 the campaign saw, and **all 33** sector-2
categories it named now carry a row, 32 of them as NE. Four appeared to be missing on a first
pass and are not: the campaign's gas vocabulary writes `F-gases` and `multiple` where the
inventory writes `HFC/PFC` and `CO2/CH4/N2O`, so a join on (code, gas) reported absences that
a join on the code alone does not. The coverage product itself ships as
`outputs/pakemis_coverage_matrix.csv`, 2,656 rows over period x category x gas, and
deliberately computes **no completeness percentage**, because the denominator is the thing
that is unknown.

**Forestry is excluded on purpose, and the reason is verifiable in the primary document.** We
extracted Pakistan's own CRT submission (`@CRT_2.83_LULUCF.xlsx`, held in this repository)
rather than quoting a secondary account of it:

- **The reported areas cannot all be land.** Table 4.A through 4.D give total areas of
  4,079.631, 124,367.646, 53,041 and 1,188 kha. They sum to **182,676.277 kha against a
  national land area near 77,088 kha — a factor of 2.37.** Cropland alone, at 124,368 kha,
  is **1.61 times the entire country**.
- **Land-use change is not estimated at all.** Every `4.X.2 Land converted to ...` row in
  Table 4 is blank: forest, cropland, grassland, wetlands, settlements, other land. So is
  4.C grassland, 4.E settlements, 4.F other land, 4.G harvested wood products and 4.H other.
  Three of the eight land categories carry a value.
- **The two available accounts disagree on the sign**, which
  `outputs/pakemis_forest_flux_adjudication.csv` publishes: Pakistan books forest land as a
  **source** of 28,435.972 kt CO2 in FY2020-21 while FAOSTAT books a **sink** of 4.107 Mt in
  CY2020 — a matched-year gap of **32.55 Mt**, about seven per cent of the national total.
  The CRT's own gross pair (7,113.083 kt C gained, 14,868.348 kt C lost, a loss/gain ratio of
  2.09) reproduces its net to 28.436 Mt, so the sign is internal to the submission and not a
  transcription artefact.
- **FAOSTAT's side is interpolated where it matters.** Its Pakistani forest area rises by
  exactly +20.786 kha in each of 2020-2023 — constant to three decimals, which is
  interpolation and not observation — and its net forest conversion is exactly 0.000 kha from
  2020 against 26.104 kha in 2015.
- **The area definitions are not the same quantity.** Pakistan's national definition takes a
  0.5 ha minimum, over 10 per cent crown cover and trees with the potential to reach 2 m,
  plus irrigated plantations and anything notified as forest in law. FAO's FRA uses 5 m,
  which moves Pakistani scrub forest to other wooded land. FRA 2020 gives 3,088.53 kha
  against the CRT's 4,079.63 kha, and that gap is definitional before any flux is computed.
- **Adopting the submission's cropland figure would double count.** Land biomass burning's
  non-CO2 sits in the Agriculture CRT while the BTR narrative folds it into the land block,
  so a land layer that took the BTR's cropland value would count crop-residue burning twice —
  a category this revision moves to `3.C.1`.

So the exclusion is a decision with a stated basis, not an omission: a land module cannot be
added to a reported boundary on an account whose areas exceed the country by a factor of two,
whose land-use change is unreported, and whose sign is contradicted by the only independent
compilation available. The exploratory layer stays outside every total, publishes its own
−3.52 Mt CO2 forest-land estimate beside the two it disagrees with, and moves no pin. The
review's own advice — stabilise the declared core and develop the land module separately — is
the course taken.

---

## The three decisions that are not mine

These are recorded rather than answered, because answering them would mean asserting
something that is not yet true:

1. **The dataset DOI.** Reserved and not minted;  waits on it, and
   the availability statement says so rather than carrying a placeholder that looks like an
   identifier.
2. **The ESSD generative-AI route.** This revision was produced with substantial
   machine assistance and the editorial office should decide how that is declared; we have
   not chosen a form of words on the journal's behalf.
3. **The ODbL carve-out.** Seven derived tables inherit a share-alike obligation that cannot
   travel inside a primary CC-BY data record. Each is identified in the deposit manifest with
   its licence; the choice between excluding them, replacing their inputs, or splitting the
   record is an author decision with consequences for what the paper can cite.
