# The power coal energy basis: what the evidence says, and what each account costs

Stage 2 of the response to the twenty-second review (item 2). This file is the written
report the review asked for: the reconciliation, the candidate accounts, the test that
separates them, and the numerical consequence of each. It does not itself select a
reference series — selecting one is a declared pin re-base and is recorded with the pins.

> **Status at rc67 (13 October 2026).** The first three sections describe the account as it
> stood when the question was asked. The re-base recorded below has since been performed:
> `outputs/national_all_sectors.csv` books public-power coal on the stations' own tonnage
> (grid 40.04 Mt), and Table 3 (57.82 Mt) is the previously published account. Since rc67
> the alternatives are presented by kind (fuel property, coverage, previously published
> account) and never as one range; the coal bound is worded as a required stock drawdown,
> not as infeasibility.

## The question

`outputs/national_all_sectors.csv` books public-power coal on NEPRA's State of Industry
Report Table 3, which publishes a fuel energy in tonnes of oil equivalent. An external
reviewer asked why that control is preferred over the plant-based alternative the release
already publishes beside it (38.45 Mt CO2e against 57.82), and observed that the stated
reason — agreement with an external total — cannot select between two accounts that share
inputs.

## What was already established (Stage 0, `outputs/pakemis_power_reference_audit.csv`)

* **Table 3's energy is a conversion, not a measurement.** Its implied TOE per tonne is
  0.4474 — 18.73 TJ/Gg — held constant across FY2015-16..FY2020-21 to 0.016 per cent while
  the fleet went from imported bituminous to 92 per cent Thar lignite, and then breaks
  *upward* (25.27, 21.40, 20.02 TJ/Gg) exactly as the fleet's physical calorific value
  falls 20.34 to 13.01. A measured energy cannot move the wrong way against its own fuel.
* **The supply bound survives all six rescue bases** — matched period, stock change, coal
  rank, moisture, calorific value and fleet coverage. Rescuing Table 3 in FY2023-24 needs a
  stock drawdown of 42 per cent of a year's national coal supply, or a lignite share of
  41.6 per cent where NEPRA prints 92.0 per station.
* **The published alternative is circular.** Its calorific values are derived as generation
  x a printed heat rate / mass, so its energy *contains* the generation it is later divided
  by. Dividing electricity back out of it returns the regulator's own printed efficiency to
  within 0.1 percentage point in all five years it covers. It is a plausibility screen, not
  independent corroboration.
* **The efficiency band is 28-47 per cent**, the wider of the two envelopes in circulation,
  because for a refutation the wider band is the harder test.

## The reconciliation (`outputs/pakemis_power_fuel_reconciliation.csv`)

Fifty rows, nine fiscal years. Each carries coal mass, rank with its origin evidence, the
calorific value and its basis, net and gross energy in separate columns, net generation with
a declared basis, the public/captive split, the K-Electric treatment, and a page-level
pointer with the printed column heading. Evidence grades: 29 rows `printed`, 8
`printed-other-edition`, 4 `reconstructed` and 9 `comparison`. It closes on CPPA-G
generation in all nine years.

The four reconstructed lanes are the only places no edition prints a mass, and each carries
an interval with its reason rather than a point:

| year | lane | interval (kt) | basis |
|---|---|---|---|
| FY2016-17 | Sahiwal + Port Qasim, commissioning | 321.02-409.94 | the 2.13-2.72 GWh/kt band the same units show once metered |
| FY2017-18 | Sahiwal + Port Qasim | 4332.03-5531.98 | as above |
| FY2018-19 | pre-COD commissioning, mixed rank | 197.88-498.37 | rank unknown; the band spans bituminous to lignite |
| FY2021-22 | pre-COD commissioning, mixed rank | 28.51-71.81 | as above |

A back-years ingest (`data/sectors/power/activity/coal_plant_fuel_back_years.csv`, 19 rows
from SoIR 2018/2020/2023) supplies the plant-years the committed FY2019-20..FY2023-24 ledger
does not reach. Ten of its twelve overlapping cells reproduce the committed ledger exactly;
the two that differ are a declared revision.

## The four accounts (`outputs/pakemis_power_coal_configurations.csv`)

Each is a coal MASS times a CALORIFIC VALUE, which is the grain at which the candidates
actually differ.

| id | mass | calorific value | circular? | years |
|---|---|---|---|---|
| `C0_table3` | HDIP's power column | Table 3's flat 18.73 TJ/Gg | no | 9 |
| `C1_stations_rank_default` | the stations' own metered coal | IPCC Vol.2 Ch.1 Table 1.2 rank defaults | **no** | 9 |
| `C2_hdip_rank_default` | HDIP's power column | the same rank defaults | no | 9 |
| `C3_stations_heat_rate` | the stations' own metered coal | generation x printed heat rate / mass | **yes** | 5 |

C1 and C2 differ only in whose tonnage they take, which is what separates the mass question
from the conversion question. The ratio C1/C0 decomposes exactly into (station mass / HDIP
mass) × (fleet rank calorific value / 18.73).

**Both terms move, and an earlier draft of this file said otherwise.** It claimed the mass
term "stays inside 0.74–0.99" while only the calorific term crossed one. That was written
against the five years whose mass is printed and it is wrong even for those: across the panel
the mass term runs **0.569 to 1.423** and the calorific term **0.635 to 1.377**, and both cross
unity. The correct statement is about which one is larger, measured in log space so the two are
comparable: **the calorific term is the larger of the two in seven of nine years**, and in the
three years carrying the biggest moves — FY2021-22 to FY2023-24 — it is two to three times the
mass term. The two years where the mass account dominates are FY2016-17, where the stations
report 445–534 kt against HDIP's 859.6, and FY2020-21, where they report 13,111 kt against
9,215.

So the conversion is the main driver but not the only one, and the mass accounts genuinely
disagree in some years. Neither fact rescues C0: the band test above rests on C1's own mass and
calorific value together, not on either term separately.

## The test that separates them

Implied net efficiency = net generation x 3.6 / coal energy, against the 28-47 per cent band.
Nothing in C0, C1 or C2 touches a heat rate, so this is a test and not a restatement.

| fiscal year | C0 | C1 |
|---|---|---|
| FY2015-16 | 13.9 | 29.4 |
| FY2016-17 | 22.3 | 29.8-36.8 |
| FY2017-18 | 51.1 | 29.7-37.9 |
| FY2018-19 | 53.1 | 37.5-38.4 |
| FY2019-20 | 45.1 | 34.7 |
| FY2020-21 | 57.5 | 34.4 |
| FY2021-22 | 29.6 | 38.7 |
| FY2022-23 | 22.8 | 34.9 |
| FY2023-24 | 18.9 | 35.2 |

**C0 is inside the band in 2 of 9 years. C1 is inside in 9 of 9 — and in the four
reconstructed years the WHOLE interval is inside, so the result does not depend on where in
the band the reconstruction lands.** C2 is inside in 6, which is the useful middle: swapping
only the conversion repairs most of the implausibility and swapping the tonnage as well
repairs the rest. The two commissioning years that Stage 0 marked uninterpretable for the
mass-free test are interpretable here, because this test uses the station account's own mass
rather than Table 3's.

The verdict is a published column — `efficiency_band_verdict`, with
`implied_net_efficiency_lo_pct` / `_hi_pct` beside it — not arithmetic a reader has to redo.
An interval that straddles an edge is labelled `straddles` and is not counted as a pass; none
currently does. `tests/test_power_coal_configurations.py` derives every verdict from its own
row and pins the two counts, so the prose above cannot drift from the product.

## The industrial consequence (`outputs/pakemis_coal_sector_reallocation.csv`)

HDIP's coal consumption *is* its coal supply: the allocation identity closes to a kilotonne
in thirteen of fourteen years, so the sectoral split redistributes a fixed total. Moving the
power column therefore moves the industrial residual by the same tonnage in the opposite
direction, and the national effect is a difference of two numbers rather than one.

The residual is **not booked**. A diagnostic gap is never inserted as a residual, and which
non-power consumer took the coal is unresolved: the evidence shows only that the coal was
supplied and that the stations did not burn it. The reallocation ships beside the total, with
its own cross-check — the brick-kiln fleet bound, a kiln census that shares no input with
NEPRA's per-station metering. As booked, brick sits below that fleet's own low bound in three
of the nine years; adding the residual brings all nine inside. That is a consistency argument
in the reconciled treatment's favour, not a proof: six years were already inside and the
bound (3,095-9,005 kt) is wider than the quantity in dispute.

FY2015-16 is the one year the identity does not close, by -204 kt. It is carried in
`identity_closes_kt` rather than smoothed.

## The axis, priced through the engine

`power coal calorific basis (non-circular)` is a registered structural axis
(`data/shared/parameters/scenarios.csv`), priced by the same machinery as every other:

* reference year: grid coal 57.82049 -> **40.04007** Mt CO2e; national
  **451.85780** Mt under configuration `power_stations_rank_default`.
* the circular member beside it (`power_plant_physical_coal`) gives 38.45184 / 450.26957.
  The two routes land **1.6 Mt apart**, which is the useful result: the circularity is a
  method defect that happens not to move this year's answer much, so the refutation of
  Table 3 does not rest on it.
* across the panel (`outputs/pakemis_structural_trajectories.csv`) the delta is
  -0.19, -0.49, +4.20, +4.20, +5.90, +11.08, -7.28, -11.38, -17.78 Mt. **It changes sign
  twice.** No constant correction is admissible, and any cross-period trend statement has to
  be restated year by year rather than shifted.

## The re-base, performed

**The account.** `data/activity/power/coal_energy_booking.csv` declares which account the
engine books, one row per fiscal year, with the superseded Table 3 figure and the ratio beside
it. `fuel_consumed.csv` is untouched and still a faithful Table 3 transcription, which is what
lets C0 ship as a retained control rather than disappear. The engine RAISES on a year the
booking table does not cover rather than falling back to Table 3 — a silent fallback would
make the reference depend on which years had been booked, and the failure would look like
data. That raise is what surfaced the two pre-panel years (FY2013-14, FY2014-15) the sector's
own diagnostics enumerate; they are booked on the same account, from the one coal station
running.

**The pins.** L 469.63822 → **451.85782**, S 464.50543 → **446.72502**, both by the same
−17.78041 because the coal account is residential-configuration-independent. The declaration
and its reason are in `scripts/check_pins.py`. The previous pins are reproduced to the fifth
decimal by the retained control (`power_table3_legacy_control`, 469.63823) — the cross-check
that the re-base changed the account and nothing else.

**The reconstructed years book the midpoint**, with `booked_lo_toe`/`booked_hi_toe` carrying
the interval as activity uncertainty. The other five carry lo = hi, because every plant-year
in them is printed.

**The industrial residual is still not booked.** It ships beside the total in
`outputs/pakemis_coal_sector_reallocation.csv`, because which non-power consumer took the coal
is unresolved and a diagnostic gap is never inserted as a residual.

**The per-year consequence and its cause** are published in
`outputs/pakemis_power_coal_rebase_ledger.csv`: the two coal energies, the mass and calorific
terms whose product is each year's ratio (asserted, not asserted-in-prose), which term is
larger, and the national move taken from the legacy axis in the structural trajectories.

## What the re-base cost, stated as losses

Three claims got weaker and all three are corrected rather than absorbed.

1. **The peak moved** from FY2021-22 (497.77) to FY2020-21 (490.58), with FY2021-22 at 490.49
   — 0.095 Mt below. The position is not robust and the manuscript says that instead of
   naming a year.
2. **The nine-year increase fell** from 68.55 Mt (17.1%) to 50.96 Mt (12.7%), because the
   reference year moves 17.78 Mt and FY2015-16 only 0.19.
3. **The trend no longer resolves under every dependence setting.** Reference 12.75–93.01 and
   time-correlated 39.96–64.04 exclude zero; **time-independent, −12.48 to +117.11, does
   not.** The previous edition said no end of the bracket left the decadal change spanning
   zero: true of the larger change, false of this one under the same intervals.

And one that got worse for an honest reason: **TE4, the flat or weakly constrained share of
reference-year emissions, rose from 52.13% to 54.18%**, because public-power coal is one of
the few streams with reconstructed monthly activity and booking less of it shrinks the
observed share.

## Independent confirmation, from a diagnostic not built for this

`heat_rate.stability()` takes a basis argument, so the same check runs on both accounts over
the same printed generation. Table 3's coal implies **19.3–58.4%**, a spread of **3.03**,
verdict UNSTABLE, above the ceiling for any coal plant ever built. The booked account implies
**34.6–39.3%**, spread **1.14**, verdict stable. Nothing on the generation side changed. The
guard asserts both halves, because either alone could pass for the wrong reason: if the
refutation stopped reproducing the booked half would still be stable, and if the booking
silently reverted the Table 3 half would still be unstable.
