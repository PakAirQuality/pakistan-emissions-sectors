# Gas reallocation between urea production and grid power

An application of the inventory, not part of it. It asks what happens to Pakistan's
greenhouse-gas and air-pollutant emissions if a specified quantity of network gas is moved from two
urea plants to grid gas stations, while the same urea is still applied (it is imported instead), the
same merchant ammonia is still supplied, and the same electricity is still delivered (the new
gas-fired generation displaces an explicit alternative).

- Code: `src/pkinv/applications/gas_reallocation/`.
- Inputs: `data/shared/parameters/gas_reallocation/`.
- Products: `outputs/pakemis_transition_gas_*.csv` and two figures.
- Run with `make gas-pilot` (about 5 s; `GAS_ARGS="--draws 1000"` writes a labelled development
  sample).

The application was corrected on 21 October 2026 after an external audit of commit `2335b4d`. §11
lists each finding and what changed. Numbers below are from the corrected run.

**What it is not.**
- It is a counterfactual calculation on annual records. It is not evidence that a reallocation
  happened or caused any observed trend.
- It does not establish operational feasibility on any day. The records are annual, and pipeline
  capacity, the winter peak, outages, contracts and dispatch are not represented.
- It infers no concentration, secondary aerosol, exposure or health effect from an emission change.

## 1. What the audit of the repository found

Audited on 20 October 2026 on public `main` `25707ca`; corrected on 21 October.

**Reused from the inventory, every value read from its own row:**
- **Fertilizer gas, by plant** (NFDC Annual Fertilizer Review): FY2023-24 feed and fuel by plant,
  supplier and month (Annex-28); FY2024-25 plant totals (Table 40).
- **Urea production by manufacturer:** NFDC Table 1. This is production, not offtake.
- **The 2.B.1 method:** stoichiometric ammonia (0.567 t per t urea), the calibrated factor
  (1.815 t CO2 per t NH3) and urea recovery (44/60, `ammonia_reconciliation.UREA_CO2_RECOVERY`).
- **Station records:** the NEPRA SoIR 2024 station ledger (fuel and net generation) and printed heat
  rates, joined through `station_crosswalk.csv`; the GEM capacity tracker.
- **IPCC 2006 combustion factors and NCVs.**
- **The post-meter leak share** (`sectors/fugitives/post_meter.py`).
- **The furnace-oil sulfur regime** of the power SO2 register.
- **The 2.B.1 air factors.**
- **GWP, units, and the shared-draw sampler.**

**Records that disagree, and are kept apart rather than reconciled:**
- **The plants' 2.B.1 CO2:**
  - The plants' metered gas carbon (FA2) gives 704 Gg.
  - The inventory's calibrated factor (FA1) gives 276 Gg. That leaves 428 Gg of the metered gas's
    carbon unaccounted for.
  - Because the power side of every case moves that metered gas, FA1 cannot be crossed with it. It
    is reported as a diagnostic (`pakemis_transition_gas_baselines.csv`), not an admissible
    baseline.
  - Fatimafert's own energy index (28.70–28.93 MMBTU per t urea) supports the FA2 magnitude.
- **The station ledger against the printed heat rate:**
  - These are two records of the same stations.
  - At the RLNG combined-cycle stations, the ledger's MMBTU read as gross gives 58.6% net, against
    printed rates of 60.5–61.8%.
  - Read as net (the inventory's FY2019-24 convention), it gives 52.7%. That reading is reported
    only as a diagnostic.

**Settled and not reopened:**
- 2.B.1 has been estimated since rc52. "Not estimated" (FD1) is a diagnostic only.

**The post-meter feedstock rule.** The rc67 reference keeps fertilizer feedstock out of the leak
base. The inventory had described this as IPCC-directed. It is not.
- IPCC 2019 Eq 4.2.18 and Table 4.2.4k define the activity as gas consumed at industrial plants and
  power stations. Note c says nothing about combustion end uses.
- The exclusion is a modelling judgement. The application therefore crosses both bases:
  - LB1, the reference: feedstock outside;
  - LB2: feedstock inside, the inventory's named configuration `fugitives_including_feedstock`.
- Whether the national reference should change is a re-base decision deferred to the next mint.

**Not estimated in the inventory, and filled here as screening (each labelled `application
addition`):**
- fertilizer process-fuel air pollutants;
- urea prilling PM and NH3 (AP-42 Section 8.2);
- power-station NOx, PM2.5, CO and NMVOC. The inventory covers power SO2 from oil only.

**Not held:**
- dispatch, merit-order or curtailment records;
- a dated, basis-stated heating value of the delivered gas;
- fiscal-year ammonia sales and stocks;
- the prill-tower control status;
- the origin of imported urea.

## 2. Feasibility decision: the gas pilot, FY2023-24

**Why FY2023-24.** It is the only year with all four of these together:
- plant-wise feed and fuel gas;
- plant urea production;
- a printed station heat-rate table;
- an independent cross-check of the sector's gas (NFDC plant meters against OGRA utility returns,
  −0.54%).

FY2024-25 replicates the plant intensities.

**Why these two plants.** They are the only plants whose gas reaches them through the SNGPL network or
as RLNG and that make only urea and ammonia: **Agritech** and **Fatimafert**.
- FY2023-24: 27,099 MMCF in total, of which 22,249 is feed and 4,850 fuel.
- Products: 899 kt urea, plus Fatimafert's merchant ammonia (bounded at 4,313–7,277 t).
- About 27.0 PJ (HHV).

Mari dedicated-line plants are excluded (`scope_plants.csv`).

**Receiving stations: only those that take network gas.** A station is a receiver if it burned RLNG
in FY2023-24, according to the SoIR ledger.
- **R1:** Balloki, Haveli Bahadur Shah, Bhikki and Punjab Thermal (Trimmu), 4,993 MW.
- **R2:** Orient, Saif, Sapphire, Halmore, Rousch, Fauji Kabirwala and Nandipur, 2,087 MW.
- **Excluded:** Uch, Uch-II, Foundation, Guddu, Engro Qadirpur and Liberty Daharki. They burn
  dedicated field gas (OGRA SoRPI 2023-24 Table 3.21 and Table 3.8).

**What is measured, bounded and unidentified.**
- **Measured:** plant gas and urea; station fuel and generation; printed heat rates.
- **Bounded:** the heating value (900–1,000 Btu/scf, mode 939.5 from Fatimafert's records), the import
  routes, merchant ammonia, fuel sulfur, FGD removal, upstream intensities and the air factors.
- **Unidentified:** which generation a new gas-fired GWh displaces. Explicit pathways and the T1
  threshold stand in for it.

## 3. Physical accounting

**Functional unit.** The change per PJ of reallocated gas (HHV), from 0 to 27.0 PJ.

**Services held fixed.** Each holds to zero in every case (`pakemis_transition_gas_checks.csv`):
- urea: domestic plus imported is the same in both states;
- Fatimafert's merchant ammonia: domestic plus imported is the same in both states;
- electricity: receiving-station GWh plus the displaced stations' remaining GWh is the same in both
  states.

**Pathways.**
- **Receiving: R1 and R2** (§2).
- **Displaced generation (pure pathways, read per PJ):**
  - D1: furnace-oil engines, including Liberty Power Tech;
  - D2: furnace-oil steam;
  - D3: imported coal.
- **Operating limits.** These pure readings are valid only while the displaced stations can give up
  the GWh. Their own FY2023-24 output caps them:

  | Pathway | Cap, as a share of the plants' gas at R1 |
  |---|---|
  | D1 oil engines | 46% |
  | D2 oil steam | 16% |
  | D3 imported coal | 84% |

  The limit comes from the DISPLACED stations' observed output. It is not evidence about what the
  receiving stations can absorb: their headroom is nameplate hours minus generation, a theoretical
  ceiling.
- **Mixed pathways (M1–M3), the full-scope cases.** Generation displaces Dk up to the Dk stations' FY
  output. The rest of the gas offsets RLNG imports. The share is computed per draw.
- **D4:** no new generation. The gas the plants no longer use substitutes for imported RLNG, so
  station combustion cancels and the LNG chain abroad shrinks.
- **D5:** the average fossil CPPA-G grid, 0.688 t CO2e per MWh. A comparator only.

**Imported urea and ammonia (F).**
- **F1, gas reforming:** IPCC 2006 Table 3.1; 0.52 t CO2e per t urea (0.39–0.65).
- **F2, coal gasification:** the IPCC 2019 Table 3.30 hydrogen factor, whose feedstock requirement
  covers raw material and fuel; 1.66 (1.27–2.07).
- Both are net of urea-bound CO2. Feedstock upstream comes from DESNZ 2024 well-to-tank factors,
  used as UK proxies.
- Neither includes the exporter's ammonia synthesis loop, urea stage or shipping.

**Fertilizer side.**
- Feedstock and process fuel are separate.
- Process-fuel CO2 is inside 2.B.1 under every reading.
- Urea-bound CO2 is released on Pakistani fields under 3.C.3, which does not change.

**Boundaries.**
- **Territorial:** IPCC categories, domestic.
- **External:** GHGs only.
- **`combined_partial`:** the two together. The omitted exporter stages can only ADD emissions. So a
  negative external or combined change is `reversible`: it cannot be called a reduction. Threshold T3
  states how large the omitted stages would have to be.

**Not estimated:**
- short-term feasibility;
- the plants' own grid purchases;
- Agritech merchant ammonia (not reported);
- the company's CO2 sales;
- domestic refinery emissions of displaced oil (treated as imported);
- concentrations and exposure.

## 4. Uncertainty, kept in three dimensions

**A. Baselines** (`baselines.csv`). None is weighted or averaged.

| Axis | Admissible | Diagnostic or exploratory |
|---|---|---|
| Fertilizer reading | FA2 | FA1 (diagnostic), FA3 (exploratory), FD1 (diagnostic) |
| Power reading | PA1, PA2 | PD1 (diagnostic) |
| Leak base | LB1, LB2 | — |
| Prill control | PC1 uncontrolled, PC2 controlled | — |

Under PC2 the finishing PM2.5 is NE, because AP-42 prints a size distribution only for uncontrolled
emissions.

**B. Pathways.** `coherence.csv`: R1–R2 × D1–D3 and M1–M3, and D4 with no receiving station, each ×
F1–F2.

**C. Parameters.**
- 10,000 paired draws, seed 20261014.
- Air factors are drawn as a two-piece lognormal that keeps the printed median and 95% bounds.
  Triangular draws on the same numbers put the mean of coal PM2.5 at 31 against a printed 3.4.
- Paired draws: a 95% width of 332 Gg, against 460 if drawn independently.

## 5. Reporting rules (fixed in code before any case was run)

- **Cell sign:** a reduction if p97.5 < 0, an increase if p2.5 > 0, and otherwise it spans zero.
- **Classification over the admissible baselines and the evidence pathways:**
  - *robust reduction / robust increase:* every cell has the same sign;
  - *conditional:* every cell excludes zero, the signs differ, and the deciding dimension is named;
  - *unresolved:* a cell spans zero, or a not-estimated component could reverse the sign;
  - *trade-off:* one pollutant robustly falls while another robustly rises in the same cell.
- **Scopes:** results are classified separately at **full scope** (M1–M3 and D4) and **per PJ inside
  the feasible range** (D1–D3 and D4).
- **"Robust"** means robust across the tested, justified cases and nothing wider.

## 6. Results (FY2023-24, per PJ of reallocated gas)

**Territorial CO2e: a robust reduction in all 56 admissible cases, in both scopes.**
- Full scope: −27 to −101 Gg per PJ. Per PJ inside the feasible range: −27 to −118.
- The breakeven displaced intensity (T1) is far below every displaced pathway:

  | Receiving stations | Breakeven intensity |
  |---|---|
  | R1 | 0.16–0.19 t CO2e/MWh |
  | R2 | 0.20–0.25 t CO2e/MWh |
  | Displaced pathways (D1–D3) | 0.61, 0.85, 0.93 t CO2e/MWh |

- Representative cases (PA1, LB1):

  | Case | Change per PJ |
  |---|---|
  | R1, M1 | −42.2 (−44.7 to −39.8) |
  | R1, M3 | −94.8 (−102.2 to −88.0) |
  | D4 | −27.0 (−29.2 to −24.8) |

- **The record conflict.** FA1 would put D4 at about a third of FA2's value. The inventory's own
  calibrated factor and the plants' metered gas disagree by 428 Gg of carbon, which is why FA1 is a
  diagnostic.

**Methane: unresolved, decided by the accounting boundary.**
- Under LB1 it rises wherever gas reaches a power station: +0.05 Gg per PJ for R1-M1, +0.14 for
  R1-D1.
- Under LB2 it falls or spans zero.
- The audit's point stands: the methane penalty rests on a leak-base judgement, not on IPCC.

**Air pollutants (screening factors; NOx as NO2):**
- **NOx, SO2 and PM2.5: robust reductions** in every tested case.
  - Full scope: NOx −0.03 to −0.51 Gg per PJ; SO2 down to −0.87; PM2.5 −0.05 to −0.07.
  - The SO2 and PM2.5 coverage is a bound: the not-estimated parts move the same way.
- **BC and NH3: unresolved,** because EMEP prints no gas-turbine factor. Under D4 both are robust
  reductions (NH3 −0.32 Gg per PJ, from urea finishing).
- **CO, NMVOC and N2O:** unresolved in some cells.

**Territorial plus external (T2, T3): unresolved everywhere,** because the external footprint is
incomplete.
- The cases stay negative unless imported urea exceeds:

  | Case | Imported urea above (t CO2e per t urea) |
  |---|---|
  | D4 | 1.34 |
  | R1-M1 | 1.82 |
  | R1-M3 | 3.52 |

  F1 is 0.52 and F2 is 1.66.
- T3: in the cases whose partial combined change is negative, the omitted exporter stages would have
  to exceed 0.73–3.74 t CO2e per t urea to cancel it.
- The origin of imported urea (not held) and the exporter's urea stage decide the combined sign.

**Trade-offs.** Under LB1, every case with a receiving station trades robust falls in NOx, SO2 and
PM2.5 against a methane rise. D4 has no trade-off.

The full matrix is in `pakemis_transition_gas_matrix.csv` and the classifications in
`pakemis_transition_gas_conclusions.csv`.

## 7. Checks

**Internal consistency** (not validation):
- the three services held;
- non-negative flows;
- generation share ≤ 1;
- zero intervention gives zero change;
- the FA2 carbon balance closes;
- 3.C unchanged;
- paired draws narrower than unpaired;
- the two-piece lognormal keeps the printed quantiles;
- every crosswalk record joins (Sahiwal's heat rate is printed gross only and is listed).

**Independent checks:**
- NFDC against OGRA: −0.54%. This covers the sector volume only.
- Fatimafert's company-reported ammonia against stoichiometry: +3.9%. The merchant sales explain
  1.4 points.
- FY2024-25 against FY2023-24 plant gas per tonne: +0.2% and −1.7%.

**Documentary:**
- The Fatimafert-implied heating value (939.5 Btu/scf) is the range's mode, so it is not a
  validation.
- NFDC Table 6.2 prints Sui gas at 925 Btu/cft, with no year and no gross/net basis. That makes it a
  cross-period compatibility check, not validation of a measured heating value.

**A finding for the inventory.** NFDC Table 6.2 prints Mari gas at 723 Btu/cft, below the 900–1,000
the fertilizer gas-carbon memo (`outputs/pakemis_gas_flow_crosswalk.csv`) applies to the whole class.
It is a candidate explanation of that memo's open difference, not yet tested.

## 8. What would settle the open parts, smallest first

- **Dispatch or curtailment records for gas-shortage days.** They would turn D1–D4 and M1–M3 into
  observed displacement. T1 bounds how far the answer can move without them.
- **The origin of imported urea, and the exporter's urea and shipping footprint.** They decide the
  combined sign (T2, T3).
- **A gas-turbine BC and NH3 factor,** which would resolve BC and NH3.
- **A dated, basis-stated heating value of SNGPL and RLNG gas** (OGRA determinations).
- **Fiscal-year ammonia sales and stocks** for both plants, and **the prill-tower control
  configuration.**
- **A post-meter leak-base decision** for the national reference (LB1 or LB2) at the next mint.

## 9. Temporal coverage and extension

The application is computed for FY2023-24 only. Plant-wise feed and fuel gas exists for FY2023-24
and FY2024-25 only.
- **Before FY2023-24:** extension would require carrying plant shares backwards.
- **FY2024-25:** a second computed year needs that year's heat-rate table, which is not ingested. Its
  ledger also relabels several stations, which the crosswalk would have to absorb. The plant
  intensities already replicate within 2%.

## 10. Files

**Inputs** (`data/shared/parameters/gas_reallocation/`): `scope_plants.csv`, `station_crosswalk.csv`,
`baselines.csv`, `pathways.csv`, `coherence.csv`, `parameter_ranges.csv`, `air_factors.csv`.

**Acquired documents.** Fetched by `scripts/fetch_gas_reallocation_evidence.py` and kept through
`pkinv.core.retention`: DESNZ 2024 conversion factors and methodology, the IPCC 2019 Refinement Vol 3
Ch 3, the EMEP/EEA 2023 1.A.1 chapter, AP-42 Section 8.2.

**Products** (outputs/):
- `pakemis_transition_gas_sources.csv`: sources, coverage, crosswalk joins, unpriced services;
- `pakemis_transition_gas_flows.csv`: physical flows, services and generation shares;
- `pakemis_transition_gas_baselines.csv`: the baseline readings compared, with the FA1 carbon residual;
- `pakemis_transition_gas_matrix.csv`: every case × boundary × pollutant;
- `pakemis_transition_gas_sectors.csv`: the sector decomposition;
- `pakemis_transition_gas_thresholds.csv`: T1, T2 and T3;
- `pakemis_transition_gas_conclusions.csv`: the classifications by scope;
- `pakemis_transition_gas_checks.csv`: internal, independent, documentary, diagnostic and crosswalk
  checks.

**Figures:** `outputs/figures/pakemis_transition_gas_t1_displaced_intensity.png`,
`pakemis_transition_gas_t2_import_route.png`.

**Tests:** `tests/test_gas_reallocation.py`.

## 11. External audit, 21 October 2026: findings and what changed

| Finding | Verified? | Change |
|---|---|---|
| Station joins: HBS lost its ledger record, Punjab Thermal its heat rate, Liberty Power Tech its row; HSD heat rates priced R2 | Yes | `station_crosswalk.csv`; heat rates filtered by fuel; an unmatched-row report; tests |
| Uch (and Foundation, Guddu) cannot receive network gas | Yes (OGRA Table 3.21) | R2 rebuilt from RLNG-burning stations; R3 retired; exclusions cited |
| FA1 leaves about 439 Gg of the metered carbon unaccounted for | Yes (428 Gg with merchant ammonia included) | FA1 diagnostic; FA2 the admissible reading |
| The methane penalty rests on the feedstock exclusion, which IPCC does not direct | Yes | LB1 and LB2 both admissible; inventory rationale corrected (CHANGELOG) |
| The combined footprint was called a bound for either sign | Yes | Sign-aware coverage; T3 |
| Merchant ammonia was not replaced | Yes (Fatimafert 4,313–7,277 t) | A bound and an imported-ammonia replacement; Agritech NE |
| The 16–40% limit concerns the displaced stations, not the receivers | Yes | Mixed pathways M1–M3 with a per-draw generation share; pure pathways are per-PJ readings only |
| The IPCC FRF includes raw material and fuel | Yes | The F2 text corrected; F2 no longer called a lower bound |
| NFDC 925/723 states no basis; 939.5 is not a measured HHV; DESNZ gas is a UK proxy | Yes | Relabelled |
| Triangular EMEP draws distort skewed ranges; AP-42's 79% applies to uncontrolled emissions only | Yes | Two-piece lognormal; prill control as an explicit state (PC2: PM2.5 NE) |

**The reviewer's evidence requests, answered from the holdings:**
- **Ammonia:** calendar-year figures only (Fatima AR 2023/2024). The Agritech AR 2023 prints no
  ammonia; RETRIEVALS mislabels it 2024.
- **Gas quality and connectivity:** OGRA Table 3.21 is held. No delivered composition is held.
- **Prilling and controls:** no prill or control configuration is held.
- **HIES:** item 045404, one-month recall ×12, household weights, household scope only.
- **Manure fuel shares:** the burned-fuel shares are unsourced.
- **Cement:** no clinker stock data is held; Comtrade HS 252310 is.
