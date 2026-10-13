"""Non-exhaust particulate matter from wheel, rail and brake wear - EXPLORATORY.

WHAT THIS IS. Railway wear PM is locally relevant near stations, yards and the urban
corridors the track runs through - plausibly more policy-relevant there than further
refinement of national railway CO2 - and no Pakistani measurement exists. This layer
carries the TNO fuel-based factors (Dutch national inventory update, anchored on an
Austrian tonne-km measurement): wear scales with traction work, traction work with fuel,
so the factors apply to the same metered control as everything else in this sector.

WHAT THIS IS NOT. It is not part of the EMEP exhaust inventory and is never summed with
it: the exhaust CSV is untouched by this module, the output is labelled EXPLORATORY on
every row, and a test asserts both. Mass discipline extends to wear: PM2.5 is a declared
fraction of wear PM10, wear PM10 a fraction of wear TSP, and none of it touches BC.

THE SOURCE'S OWN DEFECT, RECORDED. The TNO report's PM2.5 summary bullet (130 mg/kg)
contradicts its own stated size fractions (25 percent of the sub-10-micron half); the
factor rows adopt the fraction-consistent reading and quote the discrepancy verbatim,
with the bullet's reading covered inside the declared uncertainty.

Usage:  python3 -m pkinv.sectors.railways.wear_pm
Writes: outputs/railways_wear_pm_2024.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.sectors.railways import traction
from pkinv.sectors.railways.data import RailwaysData

LABEL = "EXPLORATORY - wear PM, not exhaust; never added to the EMEP layer"


def compute(data, year=None):
    """[{pollutant, emissions_kt, uncert_pct, source, label}] - diesel stream only.

    The furnace-oil stream is stationary power-house fuel for the most part and under
    0.05 percent of fuel mass; wear factors describe traction work, so it is excluded
    rather than decorated with false precision.
    """
    litres_k = data.quantity("Gas/Diesel Oil", year)              # thousand litres
    kg = litres_k * 1000.0 * data.p("hsd_density_kg_per_l")
    pm10_kt = litres_k * 1000.0 * data.efv("railway_wear", "PM10") / 1e6 / 1e6
    tsp_kt = kg * data.efv("railway_wear", "TSP") / 1e6 / 1e6
    frac = data.efv("railway_wear_frac", "PM2.5_of_PM10")
    rows = [
        {"pollutant": "TSP", "emissions_kt": tsp_kt,
         "uncert_pct": data.efu("railway_wear", "TSP"),
         "source": data.efs("railway_wear", "TSP"), "label": LABEL},
        {"pollutant": "PM10", "emissions_kt": pm10_kt,
         "uncert_pct": data.efu("railway_wear", "PM10"),
         "source": data.efs("railway_wear", "PM10"), "label": LABEL},
        {"pollutant": "PM2.5", "emissions_kt": pm10_kt * frac,
         "uncert_pct": data.efu("railway_wear_frac", "PM2.5_of_PM10"),
         "source": data.efs("railway_wear_frac", "PM2.5_of_PM10"), "label": LABEL},
    ]
    assert rows[2]["emissions_kt"] < rows[1]["emissions_kt"] < rows[0]["emissions_kt"]
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = RailwaysData()
    rows = compute(data)
    path = asset_path(OUTPUTS, "railways_wear_pm_%d.csv" % data.year)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["pollutant", "emissions_kt", "uncert_pct",
                                          "source", "label"])
        w.writeheader()
        for r in rows:
            w.writerow({**r, "emissions_kt": round(r["emissions_kt"], 6),
                        "uncert_pct": round(r["uncert_pct"], 1)})
    print("Railway wear PM (EXPLORATORY, kt): "
          + ", ".join("%s %.4f" % (r["pollutant"], r["emissions_kt"]) for r in rows))
    print("  vs exhaust PM10 0.161 kt: wear adds ~%d%% ALONGSIDE, never summed"
          % round(100 * rows[1]["emissions_kt"] / 0.1614))


if __name__ == "__main__":
    main()
