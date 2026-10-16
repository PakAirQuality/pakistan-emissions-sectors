# National Key Category Analysis (IPCC 2006 Vol 1 Ch 4, Approach 1)

Across all 10 registered sectors, 444.61 Mt CO2e (AR5). A **key category** is one with a significant influence on the national total; Approach 1 flags categories cumulatively to the **95%** threshold on absolute CO2e.

**Level assessment only.** A trend assessment needs a consistent series for every category between a common base and reference year. Four of the nine sectors report a single year, so a national trend assessment would be arithmetic without meaning. The agriculture-only trend assessment remains valid and is produced by `pkinv.sectors.agriculture.key_categories` in the companion research repository.

The totals span reference years 2022 to 2024, so this is a screen across vintages - see `outputs/national_all_sectors.csv`.

## Level assessment

| Category | Sector | Mt CO2e | Level % | Cumulative % | Key |
|---|---|---:|---:|---:|:--:|
| Enteric fermentation | agriculture | 151.66 | 34.1 | 34.1 | **KEY** |
| Road transportation | transport | 40.19 | 9.0 | 43.2 | **KEY** |
| Public electricity and heat production | power | 40.11 | 9.0 | 52.2 | **KEY** |
| Manufacturing industries and construction | industry + power | 28.13 | 6.3 | 58.5 | **KEY** |
| Domestic wastewater treatment and discharge | waste | 24.46 | 5.5 | 64.0 | **KEY** |
| Residential | residential | 24.22 | 5.4 | 69.4 | **KEY** |
| Fugitive emissions from oil and natural gas | fugitives | 23.50 | 5.3 | 74.7 | **KEY** |
| Cement production | ippu | 21.82 | 4.9 | 79.6 | **KEY** |
| Manure management | agriculture | 19.33 | 4.3 | 84.0 | **KEY** |
| Direct N2O emissions from managed soils | agriculture | 16.82 | 3.8 | 87.8 | **KEY** |
| Rice cultivation | agriculture | 16.55 | 3.7 | 91.5 | **KEY** |
| Indirect N2O emissions from managed soils | agriculture | 11.67 | 2.6 | 94.1 | **KEY** |
| Solid waste disposal | waste | 9.17 | 2.1 | 96.2 | **KEY** |
| Urea application | agriculture | 4.82 | 1.1 | 97.3 | - |
| Open burning of waste | waste | 3.83 | 0.9 | 98.1 | - |
| Ammonia production | ippu | 3.24 | 0.7 | 98.9 | - |
| Agriculture/forestry/fishing/fish farms | transport | 1.73 | 0.4 | 99.2 | - |
| Indirect N2O emissions from manure management | agriculture | 1.51 | 0.3 | 99.6 | - |
| Biomass burning in croplands | agriculture | 0.67 | 0.2 | 99.7 | - |
| Iron and steel production | ippu | 0.39 | 0.1 | 99.8 | - |
| Railways | railways | 0.39 | 0.1 | 99.9 | - |
| Civil aviation | aviation | 0.30 | 0.1 | 100.0 | - |
| Lubricant use | ippu | 0.08 | 0.0 | 100.0 | - |
| Railway stationary and off-road energy (unresolved split) | railways | 0.00 | 0.0 | 100.0 | - |

## Contribution to national variance

Where uncertainty reduction pays off, which is not the same ranking as size. Shares are (E x U)^2 normalised, the same Approach-1 quadrature that produces the national band in `outputs/national_all_sectors.csv`.

| Category | Sector | Variance share % | Cumulative % |
|---|---|---:|---:|
| Enteric fermentation | agriculture | 59.7 | 59.7 |
| Domestic wastewater treatment and discharge | waste | 12.3 | 72.0 |
| Public electricity and heat production | power | 6.0 | 78.0 |
| Rice cultivation | agriculture | 4.1 | 82.1 |
| Direct N2O emissions from managed soils | agriculture | 3.9 | 86.0 |
| Indirect N2O emissions from managed soils | agriculture | 3.4 | 89.5 |
| Fugitive emissions from oil and natural gas | fugitives | 3.1 | 92.6 |
| Solid waste disposal | waste | 2.2 | 94.8 |
| Manure management | agriculture | 1.8 | 96.6 |
| Residential | residential | 1.3 | 97.9 |
| Road transportation | transport | 0.9 | 98.8 |
| Manufacturing industries and construction | industry + power | 0.7 | 99.5 |
| Open burning of waste | waste | 0.2 | 99.7 |
| Cement production | ippu | 0.2 | 99.9 |
| Indirect N2O emissions from manure management | agriculture | 0.1 | 100.0 |
| Urea application | agriculture | 0.0 | 100.0 |
| Agriculture/forestry/fishing/fish farms | transport | 0.0 | 100.0 |
| Biomass burning in croplands | agriculture | 0.0 | 100.0 |
| Ammonia production | ippu | 0.0 | 100.0 |
| Civil aviation | aviation | 0.0 | 100.0 |
| Iron and steel production | ippu | 0.0 | 100.0 |
| Railways | railways | 0.0 | 100.0 |
| Lubricant use | ippu | 0.0 | 100.0 |
| Railway stationary and off-road energy (unresolved split) | railways | 0.0 | 100.0 |

## Key categories by level

- **Enteric fermentation** (agriculture, 34.1% of the national total)
- **Road transportation** (transport, 9.0% of the national total)
- **Public electricity and heat production** (power, 9.0% of the national total)
- **Manufacturing industries and construction** (industry + power, 6.3% of the national total)
- **Domestic wastewater treatment and discharge** (waste, 5.5% of the national total)
- **Residential** (residential, 5.4% of the national total)
- **Fugitive emissions from oil and natural gas** (fugitives, 5.3% of the national total)
- **Cement production** (ippu, 4.9% of the national total)
- **Manure management** (agriculture, 4.3% of the national total)
- **Direct N2O emissions from managed soils** (agriculture, 3.8% of the national total)
- **Rice cultivation** (agriculture, 3.7% of the national total)
- **Indirect N2O emissions from managed soils** (agriculture, 2.6% of the national total)
- **Solid waste disposal** (waste, 2.1% of the national total)
