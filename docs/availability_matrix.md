# Data Availability Matrix — Companion (Priority-4 Agricultural GHG Categories, Pakistan)

This document accompanies [`data/availability_matrix.csv`](../data/availability_matrix.csv).
It holds the full IPCC emission-factor tables, scaling factors, and 2006-vs-2019 comparisons
that are too large for a spreadsheet cell. The CSV carries the headline EF and the table
reference; the detail lives here.

**Methodological basis:** IPCC 2006 Guidelines for National GHG Inventories, Volume 4 (AFOLU),
updated by the 2019 Refinement. For livestock, Pakistan maps to the **"Indian Subcontinent"**
region; for soils and rice, Pakistan is predominantly **dry climate** (precipitation : PET < 1)
under the 2019 disaggregation, except irrigated/canal-command and high-rainfall northern tracts.

Source PDFs (public, ipcc-nggip.iges.or.jp):
`V4_10_Ch10_Livestock.pdf`, `V4_05_Ch5_Cropland.pdf`, `V4_11_Ch11_N2O&CO2.pdf`,
2019 Refinement `19R_V4_Ch11_Soils_N2O_CO2.pdf`.

---

## 1. Enteric fermentation — CH₄

**Method:** Tier 1, Eq 10.19 (per category: `Emissions = EF(T) × N(T) / 10⁶`, Gg CH₄/yr),
summed by Eq 10.20.

| Species | EF (kg CH₄/head/yr) | IPCC table | Notes |
|---|---|---|---|
| Dairy cattle | 58 | Table 10.11 (Indian Subcontinent) | "Asia" region = 68 for comparison |
| Other (non-dairy) cattle | 27 | Table 10.11 (Indian Subcontinent) | "Asia" = 47 |
| Buffalo | 55 | Table 10.10 | 300 kg liveweight basis |
| Sheep | 5 | Table 10.10 (developing) | |
| Goats | 5 | Table 10.10 (developing) | |
| Camels | 46 | Table 10.10 | Minor contributor |

**Uncertainty:** Tier 1 ±50% (Table 10.10 states ±30–50%; Section 10.3.4).
**Activity data:** annual animal population by species/category only.

---

## 2. Manure management — CH₄

**Method:** Tier 1, Eq 10.22 (`CH₄ = Σ EF(T) × N(T) / 10⁶`). EF varies with **mean annual
temperature** — pick the column.

| Species | EF range over ≤10 °C → ≥28 °C (kg CH₄/head/yr) | IPCC table |
|---|---|---|
| Dairy cattle | 5 → 6 | Table 10.14 (Indian Subcontinent) |
| Other cattle | 2 | Table 10.14 |
| Buffalo | 4 → 5 | Table 10.14 |
| Swine | 2 → 6 | Table 10.14 |
| Sheep | ~0.20 | Table 10.15 |
| Goats | ~0.22 | Table 10.15 |
| Poultry | ~0.02 | Table 10.16 |

**Uncertainty:** ±30% (Section 10.4.4).
**Activity data:** animal population + mean annual temperature. Tier 1 uses the regional
MMS-weighted default, so an explicit manure-management-system split is not strictly required.

---

## 3. Manure management — N₂O

### Direct N₂O — Eq 10.25
`N₂O_D(mm) = [Σ_S Σ_T (N(T) · Nex(T) · MS(T,S)) · EF3(S)] × 44/28`

**EF3 by manure management system** (Table 10.21, kg N₂O-N / kg N):

| System | EF3 | System | EF3 |
|---|---|---|---|
| Daily spread | 0 | Pit storage | 0.002 |
| Solid storage | 0.005 | Deep bedding (no mix) | 0.01 |
| Dry lot | 0.02 | Deep bedding (active mix) | 0.07 |
| Liquid/slurry (w/ crust) | 0.005 | Composting (in-vessel) | 0.006 |
| Anaerobic lagoon | ~0 | Composting (intensive windrow) | 0.1 |
| Poultry (with/without litter) | 0.001 | Composting (passive windrow) | 0.01 |

*Pasture/range/paddock is NOT here — it is handled in Chapter 11 as managed-soils FPRP.*

**N excretion (Nex) defaults, Asia region** (Table 10.19, kg N / 1000 kg animal mass / day):
dairy cattle 0.47 · other cattle 0.34 · swine 0.40 · poultry 0.82 · sheep 1.17 · goats 1.37 · buffalo 0.32.

**Uncertainty:** EF3 carries a *factor of 2*.

### Indirect N₂O — Eq 10.26–10.29
Volatilisation and leaching of manure N during management; uses EF4/EF5 as in managed soils.
Dry-climate values apply to most of Pakistan.

---

## 4. Rice cultivation — CH₄

**Method:** Eq 5.1 (`CH₄ = Σ EFijk · tijk · Aijk · 10⁻⁶`), Eq 5.2
(`EFi = EFc · SFw · SFp · SFo · SFs,r`), Eq 5.3 (SFo from amendment rate × CFOA).

**Baseline EFc = 1.30 kg CH₄/ha/day** (range 0.80–2.20; Table 5.11) — continuously flooded,
no organic amendment, pre-season non-flooded < 180 days.

**SFw — water regime during cultivation** (Table 5.12, disaggregated):

| Regime | SFw | Range |
|---|---|---|
| Continuously flooded | 1.00 | 0.79–1.26 |
| Intermittent — single aeration | 0.60 | 0.46–0.80 |
| Intermittent — multiple aeration | 0.52 | 0.41–0.66 |
| Regular rainfed | 0.28 | 0.21–0.37 |
| Drought-prone | 0.25 | 0.18–0.36 |
| Deep water | 0.31 | — |
| Upland | 0 | — |

**SFp — pre-season water status** (Table 5.13): non-flooded < 180 d → 1.0; non-flooded > 180 d
→ 0.68; flooded > 30 d before → 1.90.

**SFo — organic amendment**, via CFOA (Table 5.14): straw < 30 d before 1.0 · straw > 30 d 0.29
· compost 0.05 · farmyard manure 0.14 · green manure 0.50.

**Activity data:** harvested rice area by water regime (cultivation + pre-season) and amendment,
plus cultivation-period length *t* (days). The water-regime area split is the largest data gap.

---

## 5. Managed soils — direct N₂O (Eq 11.1)

| Factor | 2006 default | 2019 Refinement (relevant to Pakistan) |
|---|---|---|
| EF1 (all synthetic + organic N) | 0.01 (0.003–0.03) | aggregated 0.010; synthetic-N **wet** 0.016; **all N dry-climate 0.005** |
| EF1FR (flooded rice) | 0.003 (0.000–0.006) | aggregated 0.004; continuous flood 0.003, drained 0.005 |
| EF3PRP cattle/poultry/pigs | 0.02 | 0.004 aggregated (wet 0.006 / dry 0.002) |
| EF3PRP sheep & other | 0.01 | 0.003 |

Units: kg N₂O-N / kg N. **For most of Pakistan's rainfed/dryland soils use the dry-climate
EF1 = 0.005**; irrigated canal-command and northern high-rainfall areas may qualify as wet.

**Activity data / N-input streams:** synthetic fertiliser N (FSN), organic N (FON), crop-residue
N (FCR), N mineralised from SOC loss (FSOM), and pasture/range/paddock N (FPRP).

---

## 6. Managed soils — indirect N₂O (Eq 11.9 volatilisation, Eq 11.10 leaching)

| Factor | 2006 default | 2019 Refinement |
|---|---|---|
| EF4 (volatilisation/redeposition) | 0.010 (0.002–0.05) | aggregated 0.010; **dry 0.005**, wet 0.014 |
| EF5 (leaching/runoff) | 0.0075 (0.0005–0.025) | **0.011** (0.000–0.020) |
| FracGASF (synthetic-N volatilised) | 0.10 (0.03–0.3) | 0.11; **urea 0.15**, ammonium-based 0.08, nitrate 0.01 |
| FracGASM (organic + grazing) | 0.20 | 0.21 |
| FracLEACH-(H) | 0.30 (0.1–0.8) | 0.24 (0.01–0.73); **≈0 in dry regions** unless rain+irrigation exceed soil WHC |

- Eq 11.9: `N₂O(ATD)-N = [(FSN·FracGASF) + ((FON+FPRP)·FracGASM)] · EF4`
- Eq 11.10: `N₂O(L)-N = (FSN+FON+FPRP+FCR+FSOM) · FracLEACH-(H) · EF5`

**Pakistan note:** urea dominates the N mix, and the engine now product-weights the
EMEP/EEA high-pH factors over the NFDC Annex-7 mix: FracGASF runs at 0.1605 (NH₃-N
term; 0.1675 with the NOₓ term of Eq 11.9), superseding the IPCC urea default 0.15
this note used to recommend (`fertiliser_mix.fracgasf()`).
FracLEACH defaults to ~0 for dry regions, *but non-drip (canal/flood) irrigation triggers
FracLEACH-(H)* — so the irrigated Indus belt should not be treated as zero-leaching.

---

## Cross-cutting decisions for the matrix

- **2006 vs 2019:** both are recorded. The 2019 Refinement is current best practice and
  materially changes EF5 (↑ 0.011), FracLEACH (↓ 0.24), and disaggregates EF1/EF4 by climate.
- **Climate split:** classify each province/zone as wet or dry by precipitation : PET so the
  right EF1/EF4/FracLEACH is applied — a Tier 1.5 step that meaningfully changes soil N₂O.
- **Largest gaps** (drive Phase-2 priorities): rice water-regime areas, manure-management-system
  shares by province, dairy/non-dairy cattle split, and crop-residue removed/burned fractions.
