# Gas reallocation between urea production and grid power

An application of the inventory, not part of it. It asks what happens to Pakistan's
greenhouse-gas and air-pollutant emissions if a specified quantity of network gas is moved from two
urea plants to grid gas stations, while the same urea is still applied (it is imported instead) and
the same electricity is still delivered (the new gas-fired generation displaces an explicit
alternative). Code: `src/pkinv/applications/gas_reallocation/`. Inputs:
`data/shared/parameters/gas_reallocation/`. Products: `outputs/pakemis_transition_gas_*.csv` and two
figures. Run with `make gas-pilot` (about 5 s; `GAS_ARGS="--draws 1000"` writes a labelled
development sample).

**What it is not.** It is a counterfactual calculation on annual records. It is not evidence that a
reallocation happened or caused any observed trend. It does not establish that the reallocation is
operationally feasible on any day: the records are annual, and pipeline capacity, the winter peak
and dispatch are not represented. It infers no concentration, secondary aerosol, exposure or
health effect from an emission change.

## 1. What the audit found

The audit was carried out on 20 October 2026, on public `main` at `25707ca`; the work is on branch
`gas-reallocation-pilot`. The inventory covers FY2015-16..FY2024-25, with FY2023-24 as its reference
year, and holds FY2025-26 as provisional only (`src/pkinv/core/reporting_window.py`).

### Reused from the inventory

The application reads every inventory value from its own file, so it carries no copied numbers.

- **Fertilizer gas, by plant.** The NFDC Annual Fertilizer Review prints plant × supplier × month
  feed and fuel gas for FY2023-24 (Annex-28) and plant × supplier totals for FY2024-25 (Table 40):
  `data/shared/activity/nfdc/`.
- **Urea production by manufacturer.** NFDC Table 1. This is production, not offtake.
- **2.B.1 method.** `src/pkinv/sectors/ippu/ammonia.py`:
  - stoichiometric ammonia (0.567 t NH3 per t urea);
  - the calibrated factor of 1.815 t CO2 per t NH3;
  - urea recovery of 44/60 (`ammonia_reconciliation.UREA_CO2_RECOVERY`).
- **Station records.**
  - Fuel and net generation for each station, from the NEPRA SoIR 2024 ledger (`plant_fuel_ledger.csv`).
  - Printed heat rates (`plant_heat_rates.csv`) and the GEM capacity tracker.
- **Factors and conventions.**
  - IPCC 2006 combustion factors and the inventory's NCVs (`emission_factors.csv`).
  - The post-meter leak share and its base (`sectors/fugitives/post_meter.py`).
  - The furnace-oil sulfur regime of the power SO2 register.
  - The 2.B.1 air factors (`air_emission_factors.csv`).
  - GWP (`core/gwp.py`), units (`core/units.py`) and the shared-draw sampler
    (`core/shared_parameter_draws.py`).

### Records that disagree, and are kept apart rather than reconciled

**Fertilizer CO2 for the two plants.**

| Reading | 2.B.1 CO2, FY2023-24 | Implied gas carbon |
|---|---|---|
| Inventory's calibrated factor (FA1) | 266 Gg | 32 GJ(NCV) per t NH3 |
| Plants' metered gas carbon (FA2) | 706 Gg | 48 GJ(NCV) per t NH3 |

- The repository already carried this conflict as an open difference
  (`outputs/pakemis_gas_flow_crosswalk.csv`).
- Fatimafert's own energy index (28.70–28.93 MMBTU per t urea, company annual reports) supports the
  FA2 magnitude for that plant.
- Neither reading is an error, so both are admissible.

**Station efficiency.** The receiving stations' printed heat rate and their printed fuel and
generation are two records of the same stations.

- **RLNG combined cycle:** they agree within 5% when the ledger MMBTU is read as gross (58.1% vs
  60.5–61.8%). Read as net, which is the inventory's FY2019-24 convention, the ledger gives 52.3%.
- **Guddu:** the ledger gives 27% against a printed 36%. Its fuel is printed in MMCF, so the
  difference may lie in the gas's heating value; the holdings cannot say.

### Settled corrections, not reopened

- 2.B.1 has been estimated since rc52. "Not estimated" (FD1) is a diagnostic only.
- Fertilizer feedstock is outside the post-meter leak base (rc67). The post-meter factor is defined
  on gas burned in combustion equipment, and feedstock is reformed. The earlier membership, with
  feedstock inside, is "retained and not defended" in `outputs/national_configurations.csv`; here it
  appears only as a diagnostic.

### Not estimated in the inventory, and filled here as screening

Each is labelled `application addition` wherever it appears.

- Fertilizer process-fuel air pollutants. The air register points at an industry gas class that
  holds no fertilizer gas.
- Urea prilling PM and NH3 (AP-42 Section 8.2, acquired for this work).
- Power-station NOx, PM2.5, CO and NMVOC. The inventory covers power SO2 from oil only.

### Not held at all

- No dispatch, merit-order or curtailment record (`scripts/holdings.py merit NPCC curtail`).
- The heating value of the gas actually delivered in FY2023-24. NFDC Fertilizer Statistics Table 6.2
  prints one undated value per gas (Sui 925, Mari 723 Btu/cft), which is held and used as a check.
- Captive output at the fertilizer plants.
- The origin of imported urea.

## 2. Feasibility decision: the gas pilot, FY2023-24

**Why FY2023-24.** It is the only year with all of the following together:

- plant-wise feed and fuel gas;
- plant urea production;
- a printed station heat-rate table;
- an independent cross-check of fertilizer gas (NFDC plant meters against OGRA utility returns,
  −0.54%).

FY2024-25 has plant gas and production but no heat-rate table, so it is used as a replication year
for the plant intensities.

**Why this scope.** The plants in scope are the two whose gas reaches them through the SNGPL network
or as RLNG and that make only urea: **Agritech** and **Fatimafert**.

- FY2023-24: 27,099 MMCF in total, 22,249 of it feed and 4,850 fuel; 899 kt urea; about
  27.0 PJ (HHV).
- Mari dedicated-line plants are excluded, because field gas on a dedicated line cannot reach a grid
  station through the network. So is the SSGCL-supplied FFC site, which makes DAP and urea from one
  supply. The reasons are recorded in `scope_plants.csv`.

**Measured, bounded and unidentified.**

- **Measured:** plant gas, plant urea, station fuel and generation, printed heat rates.
- **Bounded:**
  - the heating value: 900–1,000 Btu/scf, mode 939.5 from Fatimafert's records; NFDC Table 6.2
    prints 925 for Sui gas, 1.5% lower;
  - the import routes, from IPCC Tables 3.1 and 3.30;
  - fuel sulfur;
  - FGD removal;
  - upstream intensities;
  - air factors.
- **Unidentified:** which generation a new gas-fired GWh displaces. It is replaced by explicit
  pathways and a threshold (T1), never by a default.

**Why not the dung alternative.** It was not chosen: the repository holds no stove efficiency, the
household dung quantity differs about five-fold between the ledger and the survey
(`docs/dung_destination.md`), the burned-fuel manure share is a working pointer, and biogas is NE.

## 3. Physical accounting

- **Functional unit.** Change per PJ of reallocated gas (HHV, i.e. MMBTU on the gross basis gas is
  billed on), valid for 0 to 27.0 PJ (the plants' FY2023-24 gas). It is linear inside that range.
- **Services held fixed.**
  - Urea: domestic plus imported urea is the same in both states.
  - Electricity: receiving-station GWh plus the displaced stations' remaining GWh is the same in
    both states.
  - Both hold to zero in every case (`pakemis_transition_gas_checks.csv`).
- **Fertilizer side.**
  - Feed and fuel gas are kept separate.
  - Process-fuel CO2 sits inside 2.B.1 under every reading and is never booked twice.
  - The CO2 bound into urea (44/60) is released on Pakistani fields under 3.C.3. That does not
    change, because the same urea is applied, so it appears in no change term.
  - Soil N2O and NH3 are unchanged for the same reason.
- **Receiving stations (R).**
  - R1: the RLNG combined-cycle stations (Balloki, Bhikki, Haveli Bahadur Shah, Trimmu/Punjab
    Thermal).
  - R2: older gas combined-cycle stations.
  - R3: GENCO Guddu.
- **Displaced generation (D).**
  - D1: furnace-oil engines.
  - D2: furnace-oil steam.
  - D3: imported coal.
  - D4: no new generation. The gas the plants no longer use substitutes for imported RLNG at stations
    already running, so station combustion cancels and the LNG chain abroad shrinks.
  - D5: the average fossil CPPA-G grid, 0.688 t CO2e per MWh, shown as a comparator only. An average
    is not what a new gas-fired GWh displaces.
- **Imported urea (F).**
  - F1: gas reforming at IPCC 2006 Table 3.1, 0.52 t CO2e per t urea (0.39–0.65).
  - F2: coal gasification from IPCC 2019 Table 3.30 hydrogen factors, feedstock only, so a LOWER
    bound: 1.66 t CO2e per t urea (1.27–2.07).
  - Both are net of urea-bound CO2 and include feedstock upstream from DESNZ 2024 well-to-tank
    factors, used as a proxy.
- **Operating limits** (`pakemis_transition_gas_flows.csv`). These are annual energy ceilings only.
  The gas makes 3.9 TWh at R1. The displaced stations' own FY2023-24 output caps how much of it each
  pathway can absorb:

  | Pathway | Share of the plants' gas it can absorb |
  |---|---|
  | D1 oil engines | 40% |
  | D2 oil steam | 16% |
  | D3 imported coal | 85% |

  Results are therefore stated per PJ, with each case's feasible fraction beside them.
- **Boundaries.** Territorial (IPCC categories, domestic) and external (exporter production; upstream
  of displaced or imported fuels) are reported separately.
  - External covers GHGs only.
  - `combined_partial` adds the two and is labelled partial: exporter urea-synthesis energy and
    shipping are not estimated.
- **Not estimated:** short-term feasibility; the shut plants' own grid import; urea shipping;
  domestic refinery emissions if the displaced oil is domestically refined (it is treated as
  imported); concentrations and exposure.

## 4. Uncertainty, kept in three dimensions

**A. Baselines** (`baselines.csv`). None is weighted or averaged.

| Reading | Status |
|---|---|
| FA1, FA2 (fertilizer) | admissible |
| FA3, the IPCC Tier 1 factor | exploratory |
| FD1 | diagnostic |
| PA1 (ledger), PA2 (printed heat rate) | admissible |
| PD1 (ledger MMBTU read as net) | diagnostic |

**B. Pathways.** `coherence.csv` lists the coherent combinations: R1–R3 × D1–D3, and D4 with no
receiving station, each × F1–F2. A receiving station paired with D4 would count the same gas twice
and is excluded.

**C. Parameters.**

- Conditional distributions are given in `parameter_ranges.csv` and `air_factors.csv`. They are not
  probabilities over A or B.
- 10,000 draws, seed 20261014. Baseline and transition share every draw.
- The 95% width of the CO2e change in FA2, PA1, R1, D1 is 328 Gg paired against 454 Gg if the two
  states were drawn independently (4,000 draws). The checks table records both.

## 5. Reporting rules (fixed in code before any case was run)

- **Cell signs.** A cell is a reduction if its 97.5th percentile is below zero, an increase if its
  2.5th percentile is above zero, and otherwise spans zero.
- **Classifications.** Over the admissible baselines and the evidence pathways:
  - **robust reduction / robust increase:** every cell has the same sign;
  - **conditional:** every cell excludes zero but the sign differs, and the dimension that decides it
    is named;
  - **unresolved:** a cell spans zero, or a not-estimated component could reverse the sign;
  - **trade-off:** within one cell, one pollutant robustly falls while another robustly rises.
- **"Robust"** means robust across the tested, justified cases and nothing wider.

## 6. Results (FY2023-24, per PJ of reallocated gas, mean and 95% conditional interval)

**Territorial CO2e** (AR5; AR6 classifies the same way):

- **Range.** It falls in 39 of 40 admissible cases, from −10.7 Gg (FA1, D4) to −113.7 Gg (FA2, PA2,
  R1, D3).
- **The one exception.** FA1, PA1, R3, D1 is unresolved at +3.9 (−1.8 to +9.9): Guddu at its ledger
  efficiency displacing oil engines.

  | Case | Change per PJ |
  |---|---|
  | R1 → oil engines (D1), FA1 | −43.6 (−49.2 to −38.0) |
  | R1 → oil engines (D1), FA2 | −59.8 (−64.7 to −55.0) |
  | R1 → imported coal (D3), FA1 | −90.2 (−98.9 to −81.8) |
  | RLNG imports fall (D4), FA1 | −10.7 (−13.3 to −8.4) |
  | RLNG imports fall (D4), FA2 | −27.0 (−29.2 to −24.8) |

- **The two fertilizer readings move every case by about 16 Gg per PJ.** That is the whole of the D4
  result, so there the record conflict changes the answer by a factor of 2.5.

**T1 threshold.** Territorial CO2e falls whenever the displaced generation is more intense than the
breakeven value. Fertilizer reading and power reading change the breakeven far less than the
receiving station does:

| Receiving stations | Breakeven intensity |
|---|---|
| R1 | 0.18–0.31 t CO2e/MWh |
| R2 | 0.23–0.37 t CO2e/MWh |
| R3 | 0.31–0.66 t CO2e/MWh |

The displaced pathways are 0.61 (D1), 0.84–0.85 (D2) and 0.93 (D3) t/MWh.

**Territorial plus external (T2).**

- **D4:** the combined change falls with gas-reforming imports (F1). With coal-gasification imports
  (F2), even at F2's lower bound, it rises under FA1 and spans zero under FA2:

  | Case | F1 | F2 |
  |---|---|---|
  | FA1 | −11.5 | +26.5 |
  | FA2 | −27.7 | +10.3 (−4.0 to +24.8, spans zero) |

- **R1 cases:** the combined change stays a reduction unless imported urea exceeds 1.9–4.2 t CO2e per
  t urea.
- **R3 cases:** the thresholds fall to 0.16–2.1 t CO2e per t urea, inside the range of the two routes.
- **What decides it.** The origin of imported urea (not held) decides the combined sign for D4 and
  the low-efficiency receiving station.

**Air pollutants** (territorial; screening factors; NOx as NO2):

- **NOx: robust reduction** in every case, from −0.03 Gg (D4: the plants' process fuel only) to
  −1.05 Gg per PJ (R1, D1).
- **SO2: robust reduction**, −1.40 Gg per PJ for D1 and −1.56 for D3. Its coverage is a bound:
  2.B.1 process SO2 is NE and moves the same way.
- **PM2.5: robust reduction** (bound).
- **CH4: conditional**, decided by whether gas reaches a receiving station.
  - It rises in every R case, by about 0.14 Gg per PJ. The feedstock gas enters the post-meter leak
    base once it is burned in a power station; the term rests on the factor's definition (IPCC 2019
    Table 4.2.4k).
  - It falls under D4.
- **N2O, CO and NMVOC: unresolved** in some cells, because their intervals span zero.
- **BC and NH3: unresolved.** EMEP prints no gas-turbine BC or NH3 factor, and that NE component
  could reverse the sign.
  - NH3 under D4 is a robust reduction: urea finishing NH3 alone, −0.32 Gg per PJ.
- **Trade-offs:** every case with a receiving station trades a robust fall in NOx, SO2 and PM2.5 (and
  CO2, in D2–D3) against a robust rise in CH4. D4 has no trade-off.

`pakemis_transition_gas_conclusions.csv` holds every classification. `pakemis_transition_gas_sectors.csv`
decomposes every cell by process.

## 7. Checks

**Internal consistency** (these are not validation):

- services held;
- non-negative flows;
- zero intervention gives zero change;
- the carbon balance of FA2 closes;
- 3.C is unchanged;
- paired draws are narrower than unpaired ones.

**Independent checks:**

- NFDC against OGRA: −0.54%. It confirms the sector volume only.
- Fatimafert's company-reported ammonia, 311,242 t, against 0.567 × its reported urea: +3.9%. The
  company sold 4,313 t of ammonia that year.
- FY2024-25 plant gas per tonne against FY2023-24, from a different year's meters: +0.2% (Agritech)
  and −1.7% (Fatimafert).

- The heating value: NFDC Table 6.2 prints 925 Btu/cft for Sui gas against the 939.5 that
  Fatimafert's energy index and NFDC plant meters imply (−1.5%). The two share no input.

**Documentary.** The Fatimafert heating value (939.5 Btu/scf) is a bound, not a validation, because
it sets the mode of the range it is checked against; the NFDC value above is the independent check.

**A finding for the inventory.** NFDC Table 6.2 prints Mari dedicated-line gas at 723 Btu/cft. The
inventory's fertilizer gas-carbon memo (`outputs/pakemis_gas_flow_crosswalk.csv`) converts the whole
class at 900–1,000, so it overstates the Mari plants' gas carbon. That is a candidate explanation of
its open difference, not yet tested.

No independent observation of the change itself exists. Agreement with another inventory built on
the same activity would not be one.

## 8. What would settle the open parts, smallest first

- **A dispatch or curtailment record for gas-shortage days** (NPCC daily reports). It would turn D1–D4
  from assumptions into observed displacement. T1 says how far the answer can move without it.
- **The origin of imported urea** (customs records by origin; UN Comtrade HS 310210). It decides the
  combined sign for D4 and R3.
- **A dated heating value of SNGPL and RLNG gas for FY2023-24** (OGRA determinations). NFDC's
  undated 925 is already within 1.5% of the plant-derived value. It would narrow FA2 and every
  conversion.
- **Gas-turbine BC and NH3 factors**, which would resolve BC and NH3.
- **The prill-tower control status** of the two plants.

## 9. Temporal coverage and extension

The application is computed for FY2023-24 only. Plant-wise feed and fuel gas exists for FY2023-24
and FY2024-25 only (Annex-28 and Table 40); earlier NFDC reviews in the holdings print the class
total, not plants.

- **Before FY2023-24:** extension would require carrying FY2023-24 plant shares backwards, which the
  inventory's own rule forbids presenting as observed.
- **FY2024-25:** a second computed year is justified once that year's heat-rate table is ingested.
  The plant intensities already replicate within 2%.
- **FY2025-26:** stays provisional, as in the inventory.

## 10. Files

**Inputs** (`data/shared/parameters/gas_reallocation/`): `scope_plants.csv`, `baselines.csv`,
`pathways.csv`, `coherence.csv`, `parameter_ranges.csv`, `air_factors.csv`.

**Acquired documents.** `scripts/fetch_gas_reallocation_evidence.py` fetched these, kept through
`pkinv.core.retention` before reading:

- UK DESNZ 2024 conversion factors and methodology;
- the IPCC 2019 Refinement Vol 3 Ch 3;
- the EMEP/EEA 2023 1.A.1 chapter;
- AP-42 Section 8.2.

**Products** (outputs/):

- `pakemis_transition_gas_sources.csv`: sources and coverage;
- `pakemis_transition_gas_flows.csv`: physical flows and services;
- `pakemis_transition_gas_baselines.csv`: the baseline reconstructions compared;
- `pakemis_transition_gas_matrix.csv`: every case × boundary × pollutant;
- `pakemis_transition_gas_sectors.csv`: the sector decomposition;
- `pakemis_transition_gas_thresholds.csv`: T1 and T2;
- `pakemis_transition_gas_conclusions.csv`: the classifications;
- `pakemis_transition_gas_checks.csv`: internal, independent and diagnostic checks.

**Figures** (`outputs/figures/`): `pakemis_transition_gas_t1_displaced_intensity.png`,
`pakemis_transition_gas_t2_import_route.png`.

**Tests:** `tests/test_gas_reallocation.py`.
