# Defects and documentation errors found (NOT fixed — task is read-and-tabulate)

## D-E2-01 — the shipped adjudication's own conclusion is not supported by its panel
`src/pkinv/sectors/power/coal_energy_adjudication.py`, docstring and CSV banner:

> "`table3_toe_per_hdip_tonne` shows the conversion is stable where `table3_toe_per_tonne` is
> not, which locates the disagreement in the MASS ACCOUNTS rather than in a conversion."
> "So Table 3's conversion is not what doubles."

The series is **0.4474, 0.4474, 0.6036, 0.5111, 0.4781 TOE/t** — flat for two years, then +35%
and back. A log decomposition of Table 3's energy against the non-circular physical route
(`implied_efficiency_decomposition.csv`) puts **53 / 31 / 81 / 77 / 69 per cent** of the error
in the conversion channel, not the mass channel, and the conversion channel is the only one
with an identified mechanism (the rank shift it fails to track). The claim as written is
wrong, and it is the sentence that steered the hypothesis register toward the mass accounts.
Severity: high — it is a published conclusion in a shipped product's banner.

## D-E2-02 — the plant route is circular with the envelope it is tested against
Same module. `plant_energy_TJ = plant_implied_ncv × mass`, where `plant_implied_ncv` comes from
`power_implied_coal_cv_fy2023_24.csv`, which computes it as `generation × heat_rate / mass`.
So the route's energy is identically `Σ generation × heat rate`, and its "implied efficiency"
is the harmonic mean of NEPRA's **printed** plant efficiencies. It is inside 30–45% by
construction and **cannot** test whether NEPRA's fleet efficiency is plausible. The module's
"THE HEAT-RATE ROUTE AGREES WITH THE COMPOSITION ROUTE" paragraph treats the two as
independent corroboration; only the composition route is independent.
Severity: high — it is the reasoning that selects the preferred route.

## D-E2-03 — the fleet calorific value is weighted over a subset and applied to all mass
`power_implied_coal_cv_fy2023_24.csv` FLEET rows carry a mass-weighted CV computed only over
stations that HAVE a printed heat rate, and `coal_energy_adjudication.build()` multiplies it
by **total** Table 21 mass. In FY2019-20 and FY2020-21 the only lignite station (Engro
Powergen Thar, 3,776.90 and 3,612.93 kt) has no printed heat rate, so the FLEET CV is
**imported-only** (23.03 and 22.87 TJ/Gg, identical to the file's own "imported only" summary
rows) and is then applied to lignite tonnes. The note "the fleet CV covers 69% of it" records
the coverage but the arithmetic ignores it. Repairing it moves the plant route's
`plant_implied_efficiency_pct` from **32.4 → 38.1** (FY2019-20) and **33.1 → 38.1**
(FY2020-21), and tightens the route's span from 13.3 to 6.2 points (see route R5).
Severity: medium — two published values are biased, in a diagnostic, not a pin.

## D-E2-04 — the envelope in the code is 30–45, the envelope in the campaign is 28–47
`COAL_EFF_LO, COAL_EFF_HI = 30.0, 45.0`, and the banner says "A coal fleet runs at 30-45 per
cent", while T-ENERGY-1 and `diagnostics_reproduced.csv` test 28–47 (sub 33–37, super 37–42,
ultra-super 42–47). Under 28–47 the shipped `verdict` strings for FY2019-20 ("45.1%, outside
30-45") and FY2021-22 ("the plant route implies 45.7%, outside 30-45") are wrong: both are
inside. The two bands should not both be in circulation.
Severity: medium — the published verdict column.

## D-E2-05 — NEPRA print errors carried forward without a flag on every affected row
From `sources/Power Plants/NEPRA State of Industry Report 2024.pdf` Table 23 (pp.161–163):
- **Huaneng Shandong Ruyi (Sahiwal)**: gross heat rate a fixed **8,749.08 Btu/kWh at exactly
  39.00%** in FY2019-20…FY2022-23 (a contract/reference value, not a measurement), net export
  heat rate `n.p.` in every year, yet net-export **efficiency** printed as 42.94% (FY2021-22)
  and 40.69% (FY2022-23) — **above** the gross efficiency, which is impossible.
- **Port Qasim FY2021-22**: printed gross efficiency 41.34% is not 3,412.14 / 8,703.02 =
  39.21%; one of the two printed cells is mis-keyed. The other four years reconcile.
- **Thar Coal Block-I**: net HR below gross in both years. The repo flags this one already.
`plant_heat_rates.csv` carries a `note` on Thar Block-I only. The Sahiwal and Port Qasim rows
are unflagged, and `power_implied_coal_cv_fy2023_24.csv` marks Sahiwal FY2021-22 `outlier`
without saying the mass, not the heat rate, is the suspect quantity.

## D-E2-06 — a probable NEPRA mass error that no repo diagnostic names
**Sahiwal FY2021-22: 1,443.97 kt of coal for 6,881.38 GWh = 4.766 GWh/kt**, against the same
station's 2.716 / 2.670 / 2.438 / 2.689 in the other four years. At its own four-year mean
the generation needs ~2,610 kt, so roughly **1,170 kt is missing from the printed mass**. That
single plant-year accounts for most of the FY2021-22 crossing of the two mass accounts
(HDIP/Table 21 goes 0.70 → 1.05) and for the plant route's 45.7% excursion. The repo attributes
the crossing to a consumption-versus-receipts difference; one plant-year explains much of it.

## D-E2-07 — a plant-coverage hole
GEM lists **Lakhra power station, 3 × 50 MW lignite, status "operating"**
(`data/sectors/power/activity/gem_coal_pak.csv`). It appears in neither Table 18/20 (GENCO
fuel and heat rate, which print gas/RLNG/RFO/HSD only) nor Table 21 (IPPs), so it is absent
from the plant lane. Bounded well under 0.5 Mt/yr against a 12–16 Mt fleet. Separately, GEM
lists **378 MW of captive coal** (DG Khan Cement, Maple Leaf, Hub Cement, Sitara Chemical,
Fauji Fertilizer, Muzaffargarh sugar) which belongs to industry and sits inside HDIP's Cement
column — relevant to the industrial-coal residual, not to power.

## D-E2-08 — minor, provenance only
`outputs/power_activity_factor_ledger.csv` prints the power coal CH4 as **0.384262 Gg** beside
activity 384,262 TJ and factors "10.0 / 300.0 kg CH4/TJ"; the printed number is 384,262 TJ ×
**1** kg/TJ. N2O (0.576393 Gg at 1.5 kg/TJ) and CO2 (38,293.988 Gg at an effective 99.656
kg/TJ, a lignite-weighted blend of the repo's own 94,600 / 101,000) both reconcile. The row
disclaims identity ("no identity is claimed"), so this is a ledger-legibility issue rather
than a proven engine defect, but the coal CH4 lane cannot be audited from the ledger.
