"""Seventy years of railway fuel, as context - quinquennial averages, not inventory.

WHAT THIS IS AND IS NOT. The Year Book's historical fuel table (2023-24 edition, p.163)
runs back to 1950, but at five-year-average resolution before 2015: 'back to 1950' is true
of the table's span and misleading about its resolution. This module publishes that history
as a labelled context product - steam-to-diesel transition, the 1971 boundary change, the
rise and death of the electric section, the end of furnace-oil traction - and it feeds
NOTHING: not the registry, not the national rollup, not the reported series. The inventory
is the annual FY2014-FY2024 series in fuel_consumption.csv.

THE EMISSIONS COLUMN IS INDICATIVE. Fuel quantities are the operator's; the conversion uses
the same rail factor rows as the inventory plus Table 3.4.1's sub-bituminous coal column
(HISTORY LAYER ONLY rows in the factor file - locomotive coal is Nil from 1980-85 onward,
so no inventory year touches them). The steam-era coal grade is unknown, today's diesel
density is applied to 1950s diesel, and each row is a five-year average across a network
whose boundary changed in 1971. The column shows the shape of seven decades; it is not a
time series to difference.

STRUCTURAL BREAKS are annotated row by row in the activity file itself, including the one
inter-edition discrepancy found in transcription (2005-10 locomotive furnace oil: 490 in
the 2023-24 edition against 121 in 2020-21, every other cell agreeing).

Usage:  python3 -m pkinv.sectors.railways.history
Writes: outputs/railways_fuel_history.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.railways.data import RailwaysData
from pkinv.activity.store import read_rows

_FILE = asset_path(DATA, "activity", "railways", "fuel_history_quinquennial.csv")

# (activity columns to sum, EF item, how the quantity becomes Gg of fuel)
_FUELS = (
    (("coal_locomotive_t", "coal_other_t"), "Sub-bituminous Coal", "tonnes"),
    (("fo_locomotive_t", "fo_other_t"), "Residual Fuel Oil", "tonnes"),
    (("hsd_locomotive_thousand_l", "hsd_other_thousand_l"), "Gas/Diesel Oil",
     "thousand litres"),
)


def _num(s):
    s = (s or "").strip()
    return 0.0 if s == "" else float(s)


def load(path=_FILE):
    return read_rows(path, comments=False)


def co2e_Mt(data, row):
    """Indicative AR5 CO2e for one period row, all three fuels, all three gases."""
    from pkinv.core.gwp import to_co2e
    total = 0.0
    for cols, item, unit in _FUELS:
        qty = sum(_num(row[c]) for c in cols)
        if unit == "thousand litres":
            gg = qty * 1000.0 * data.p("hsd_density_kg_per_l") / 1e6
        else:
            gg = qty / 1000.0
        tj = gg * data.efv("railway_ncv", item)
        for gas, cat in (("CO2", "railway_traction_co2"),
                         ("CH4", "railway_traction_ch4"),
                         ("N2O", "railway_traction_n2o")):
            ef_item = item if (item == "Sub-bituminous Coal" or gas == "CO2") \
                else "Gas/Diesel Oil"
            gg_gas = tj * data.efv(cat, ef_item) / 1e6
            total += to_co2e(gas, gg_gas, fossil=(gas == "CH4")) / 1000.0
    return total


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = RailwaysData()
    rows = load()
    out = asset_path(OUTPUTS, "railways_fuel_history.csv")
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["period", "coal_t", "furnace_oil_t", "diesel_thousand_l",
                    "electric_kwh_thousand", "co2e_Mt_AR5_indicative", "note"])
        for r in rows:
            w.writerow([
                r["period"],
                _num(r["coal_locomotive_t"]) + _num(r["coal_other_t"]),
                _num(r["fo_locomotive_t"]) + _num(r["fo_other_t"]),
                _num(r["hsd_locomotive_thousand_l"]) + _num(r["hsd_other_thousand_l"]),
                r["electric_kwh_thousand"],
                round(co2e_Mt(data, r), 4), r["note"]])
    print("railway fuel history, %d quinquennial rows -> %s" % (len(rows), out))
    for r in rows:
        print("  %-9s coal %9.0f t  FO %8.0f t  HSD %8.0f kL  ~%.2f Mt"
              % (r["period"], _num(r["coal_locomotive_t"]) + _num(r["coal_other_t"]),
                 _num(r["fo_locomotive_t"]) + _num(r["fo_other_t"]),
                 _num(r["hsd_locomotive_thousand_l"]) + _num(r["hsd_other_thousand_l"]),
                 co2e_Mt(data, r)))


if __name__ == "__main__":
    main()
