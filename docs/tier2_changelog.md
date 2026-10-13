# Tier 1 → Tier 2 Changelog (Phase 5)

Each Tier 1 default replaced with a researched, sourced Pakistan-specific value, and its effect.
National total for the four core categories moved **223.1 → 217.0 Mt CO₂e**; every input is now
sourced rather than assumed. With field-burning and liming/urea CO₂ added (Phase 8) and the EF4
harmonisation (see `docs/qa_qc.md`), the current **six-category** national total is **222 Mt CO₂e**.

## Livestock

| Parameter | Tier 1 | Tier 2 | Source | Effect |
|---|---|---|---|---|
| Dairy cattle share | 0.40 (assumed) | **0.295** | FAOSTAT QCL 2024: Milk Animals 16.975M / Cattle stocks 57.541M | Enteric ↓ (fewer cattle at EF 58) |
| Buffalo TAM | 295 kg | **380 kg** | Category herd-avg (Nili-Ravi adult ♀ ~450; LRRD/OK State) | Buffalo Nex ↑ ~30% → manure & soils N ↑ |
| Camel TAM | 217 kg | **480 kg** | Khan et al. 2025 (adult ~620-660; herd-avg lower) | Minor (camels 1.5M head) |
| Other-cattle TAM | 130 kg | **225 kg** | Pakistan mixed/draught zebu | Nex ↑ |
| Dairy-cattle TAM | 275 kg | **400 kg** | Sahiwal/crossbred adult cow | Nex ↑ |
| Sheep / goat TAM | 28 / 30 | **35 / 32** | Pakistan population-average adult | Small Nex ↑ |
| MMS shares | IPCC/literature defaults | sourced (dung-cake 28%, pasture 20-30%) | MDPI 2021 / AAQR 2024 | Refines manure N₂O & FON/FPRP split |
| Enteric EFs | dairy 58 / other 27 / buffalo 55 | **kept** (cross-checked) | Pakistan EF ~40.7 (Tariq 2025) ≈ current effective 39 | none — validated |

Enteric: **156.6 → 151.5 Mt** · Manure: **19.9 → 21.2 Mt**.

## Managed soils

| Parameter | Tier 1 | Tier 2 | Source | Effect |
|---|---|---|---|---|
| EF1 (cropland) | 0.0061 (90/10 dry/wet blend) | **0.005 (explicit dry)** | IPCC 2019 Ch11; PMC9293294 (dry EF1 derived from irrigated dry fields) | Direct N₂O ↓ slightly; now best-supported, not assumed |
| EF1FR (rice N) | — (rice N got cropland EF1) | **0.004** on 16% of synthetic N | IPCC 2019 flooded-rice | Small ↓ |
| EF4 (volatilisation) | 0.0059 (blend) | **0.005 (dry)** | IPCC 2019 dry | Indirect volatilisation ↓ slightly |
| FracLEACH applicable | 0.85 | **0.80** (= irrigated fraction) | FAO AQUASTAT / Econ Survey | Leaching retained on irrigated land despite dry climate |
| Residue frac_returned | 0.30–0.60 | **0.20–0.30** | IGC Pakistan residue mgmt (straw removed as fodder/fuel; rice burned) | Residue N₂O ↓ |

Managed soils: **30.0 → 28.4 Mt** (competing effects: higher manure-N raises FON/FPRP; lower
residue return and rice-N split lower it).

## Rice

| Parameter | Tier 1 | Tier 2 | Source |
|---|---|---|---|
| Cultivation period | 130 d | **125 d** (area-weighted) | PARC (Punjab basmati ~130, Sindh IRRI ~110) |
| Water regime SFw | 1.0 (continuous) | **1.0 kept** | AWD negligible commercially (Agronomy 2021) |

Rice: **16.6 → 15.9 Mt**.

## The managed-soils vs FAOSTAT divergence — explained, not "fixed"

The engine's soils (~28 Mt) stays well below FAOSTAT's (~58 Mt). This is **methodological, not an
error**: FAOSTAT uses 2006 *aggregate* defaults (EF1 0.01, EF3PRP 0.02); the engine uses the
2019 *disaggregated dry* values (EF1 0.005, EF3PRP 0.002), which are the empirically best-supported
for irrigated arid cropland — the 2019 dry EF1 was itself derived largely from irrigated dry-climate
fields (Global Change Biology 2022, PMC9293294). Using the wet EF1 (0.016) is explicitly unsupported.

A **sensitivity pass** runs the inventory at EF1 = 0.005 (Tier 2 default) and 0.010
(Pakistan-official / FAOSTAT-comparable): soils **28.4 → 40.4 Mt**, six-category national
**222 → 234 Mt** (vs FAOSTAT 233.3). Reported in `inventory_report.md` and `outputs/by_category.csv`.

## Net result
- National total (four core categories): **223.1 → 217.0 Mt CO₂e**. Full six-category total: **222 Mt**
  (EF1 sensitivity 222–234).
- vs FAOSTAT 233.3: 0.95× (default) to 1.00× (EF1=0.010); vs EDGAR 267: 0.83×.
- Provincial & gridded outputs regenerated from the Tier 2 totals (reconciliation intact).
