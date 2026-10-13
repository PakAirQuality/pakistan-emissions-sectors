# Baseline: grid power by province immediately before the rc66 per-year split

WHAT THIS IS. Two extracts of release 1.0.0rc65 (commit 7efb9de0), cut with `git show`:

- `pakemis_adm1_by_year_power.csv`: the `power` rows of `outputs/pakemis_adm1_by_year.csv`,
  every stream, gas, province and fiscal year, as rc65 shipped them.
- `province_shares_power_rows.csv`: the `power_*`, `bagasse_grid` and `captive_gas` rows of
  `data/shared/lookups/province_shares.csv` as rc65 held them.

`SHA256SUMS` pins both.

WHY IT EXISTS. At rc66 the provincial split of grid power stopped being one reference-year
vector per fuel and became each year's own stations
(`src/pkinv/sectors/power/province_panel.py`). The national total of every fuel, gas and year is
unchanged; what each province is booked moves by up to 11.6 Mt CO2e in one province-year.
`outputs/pakemis_power_provincial_basis_by_year.csv` publishes that movement, and it has to be
measured against something that will still be here after the next release rebuilds
`outputs/`. A git ref would do in a checkout; a validation package is not a checkout.

WHAT RC65 APPLIED, so the "before" column is read correctly. Coal, gas and bagasse rode the
committed row in all nine years. Furnace oil and diesel rode own-year GENERATION shares for
FY2015-16 to FY2019-20 and the committed row after. Captive gas was already per year and does
not move at rc66; it is in the extract so the power module's rows are complete.

WHAT IT IS NOT. Not an input to any estimate. Nothing reads these files except the comparison
product and its test.
