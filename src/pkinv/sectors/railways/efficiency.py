"""Energy and emission intensity of Pakistani rail - the check EMEP says to run.

The EMEP railway chapter's verification guidance is to check fuel against distance,
passenger-km and tonne-km, historically and internationally. This module publishes those
quotients per fiscal year from the operator's own traffic statistics: litres and MJ per
train-km, per passenger-km and per tonne-km, and CO2 per passenger-km and tonne-km. The
FY2023-24 headline - 4.0 litres per train-kilometre - is the number that refutes the
official submissions' implied 46.

Passenger/freight attribution for the per-pkm and per-tkm figures uses the Tier 2 fuel
split, so those intensities inherit its declared shunting assumption; the per-train-km
figure does not (total fuel over total train-km, assumption-free). All quotients are
DIAGNOSTIC - nothing here feeds the inventory.

Usage:  python3 -m pkinv.sectors.railways.efficiency
Writes: outputs/railways_efficiency_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.railways import tier2, traction
from pkinv.sectors.railways.data import RailwaysData

_TRAFFIC = asset_path(DATA, "activity", "railways", "traffic.csv")


def traffic():
    out = {}
    for r in _activity_rows(_TRAFFIC, comments=False):
        out.setdefault(int(r["fiscal_year"]), {})[r["metric"]] = float(r["value"])
    return out


def rows(data):
    traf = traffic()
    out = []
    for year in sorted(traf):
        t = traf[year]
        try:
            litres_k = data.quantity("Gas/Diesel Oil", year)      # thousand litres
        except KeyError:
            continue
        tj = sum(traction.fuel_TJ(data, year).values())
        co2_t = tj * data.efv("railway_traction_co2", "Gas/Diesel Oil") / 1e3
        row = {"fiscal_year": year,
               "litres_per_train_km": None, "MJ_per_train_km": None,
               "MJ_per_passenger_km": None, "MJ_per_tonne_km": None,
               "gCO2_per_passenger_km": None, "gCO2_per_tonne_km": None}
        if t.get("total_train_km"):
            row["litres_per_train_km"] = litres_k / t["total_train_km"]
            row["MJ_per_train_km"] = tj * 1e6 / (t["total_train_km"] * 1e3)
        if t.get("passenger_km") or t.get("tonne_km"):
            split = tier2.split(data, year) if year in (2024, 2025) else None
            if split:
                pax_frac = split["line_haul_passenger"] / sum(split.values())
                frt_frac = split["line_haul_freight"] / sum(split.values())
                if t.get("passenger_km"):
                    row["MJ_per_passenger_km"] = (tj * pax_frac * 1e6
                                                  / (t["passenger_km"] * 1e3))
                    row["gCO2_per_passenger_km"] = (co2_t * pax_frac * 1e6
                                                    / (t["passenger_km"] * 1e3))
                if t.get("tonne_km"):
                    row["MJ_per_tonne_km"] = (tj * frt_frac * 1e6
                                              / (t["tonne_km"] * 1e3))
                    row["gCO2_per_tonne_km"] = (co2_t * frt_frac * 1e6
                                                / (t["tonne_km"] * 1e3))
        out.append(row)
    return out


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = RailwaysData()
    out = rows(data)
    with open(asset_path(OUTPUTS, "railways_efficiency_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        for r in out:
            w.writerow({k: (round(v, 4) if isinstance(v, float) else v)
                        for k, v in r.items()})
    print("Railway intensity (diagnostic):")
    for r in out:
        print("  FY%d: %s L/train-km, %s MJ/pkm, %s gCO2/tkm"
              % (r["fiscal_year"],
                 "%.2f" % r["litres_per_train_km"] if r["litres_per_train_km"] else "-",
                 "%.3f" % r["MJ_per_passenger_km"] if r["MJ_per_passenger_km"] else "-",
                 "%.1f" % r["gCO2_per_tonne_km"] if r["gCO2_per_tonne_km"] else "-"))


if __name__ == "__main__":
    main()
