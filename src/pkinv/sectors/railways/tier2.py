"""Tier 2 service split - a diagnostic decomposition that rescales exactly to the control.

WHAT THIS IS. EMEP's Tier 2 applies service-specific factors to fuel apportioned among
line-haul locomotives, shunting locomotives and railcars, and its chapter says the component
estimates 'should be scaled to the national fuel statistic so the total energy balance is
retained' - which is this inventory's own reconciliation rule, stated by the method itself.
The split here is exactly that: the operator's metered total is the only magnitude, and the
services carry only its decomposition.

WHAT THE DECOMPOSITION RESTS ON, HONESTLY. Railcars are NO - workings are Nil in every
recent year (service_statistics.csv cites the comparative statement). Passenger and freight
line-haul train-km are published. Shunting activity is published in NO form, so its fuel
share is a DECLARED ASSUMPTION - 5 percent, derived in railways_params.csv from EMEP's own
duty rates under an assumed shunter fleet share, wide uncertainty, gap-registered
(rail-service-split). The reported inventory is Tier 1 and does not depend on any of this;
the split feeds the Tier 2 air diagnostic and the yard layer of the spatial model.

WHAT THE DIAGNOSTIC SHOWS. Tier 2 line-haul NOx is 63 kg/t against Tier 1's fleet-average
52.4, so a fleet that is nearly all line-haul - Pakistan's - implies Tier 1 may understate
NOx by roughly a fifth; PM runs the other way. That sensitivity to duty cycle is the reason
the comparison is published, and the reason neither layer is silently swapped for the other.

Usage:  python3 -m pkinv.sectors.railways.tier2
Writes: outputs/railways_tier2_split_2024.csv, railways_tier2_air_diagnostic_2024.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.railways import air_pollutants, traction
from pkinv.sectors.railways.data import RailwaysData
from pkinv.activity.store import read_rows

_SERVICES = asset_path(DATA, "activity", "railways", "service_statistics.csv")

# Diagnostic pollutants: the ones Tables 3-2/3-3 tabulate with central values.
T2_POLLUTANTS = ("NOx", "CO", "NMVOC", "NH3", "TSP", "PM10", "PM2.5")
T2_CATEGORY = {"line_haul": "railway_air_t2_linehaul",
               "shunting": "railway_air_t2_shunting"}


def service_stats(year, path=_SERVICES):
    return {r["service"]: r for r in read_rows(path, comments=False) if r["fiscal_year"] == str(year) and (r["value"] or "").strip() != ""}


def split(data, year=None):
    """{service: kt of diesel}, summing to traction.diesel_kt EXACTLY.

    Shunting takes the declared share; the line-haul remainder divides by published
    train-km. The equality assertion is in-function because a split that does not
    reconcile is not a decomposition, it is a second estimate.
    """
    year = data.year if year is None else year
    control = traction.diesel_kt(data, year)
    stats = service_stats(year)
    tkm_p = float(stats["line_haul_passenger"]["value"])
    tkm_f = float(stats["line_haul_freight"]["value"])
    shunt = control * data.p("shunting_fuel_share")
    line_haul = control - shunt
    out = {"line_haul_passenger": line_haul * tkm_p / (tkm_p + tkm_f),
           "line_haul_freight": line_haul * tkm_f / (tkm_p + tkm_f),
           "shunting": shunt}
    assert abs(sum(out.values()) - control) < 1e-12 * max(control, 1.0)
    return out


def reconciliation(data, year=None):
    s = split(data, year)
    return {"control_kt": traction.diesel_kt(data, year),
            "split_total_kt": sum(s.values()),
            "shunting_share": data.p("shunting_fuel_share")}


def air_diagnostic(data, year=None):
    """[{pollutant, tier1_kt, tier2_kt, ratio_t2_over_t1}] on the same fuel mass.

    Tier 2 applies the line-haul factors to line-haul fuel and the shunting factors to
    shunting fuel; railcars are NO. Diesel only - the furnace-oil stream is 0.04 percent
    of fuel mass and both tiers treat it identically, so it cancels from the ratio.
    """
    s = split(data, year)
    tonnes = {k: v * 1000.0 for k, v in s.items()}
    lh_t = tonnes["line_haul_passenger"] + tonnes["line_haul_freight"]
    sh_t = tonnes["shunting"]
    diesel_t = lh_t + sh_t
    out = []
    for pol in T2_POLLUTANTS:
        t1 = diesel_t * data.efv("railway_air", pol) / 1e6
        t2 = (lh_t * data.efv(T2_CATEGORY["line_haul"], pol)
              + sh_t * data.efv(T2_CATEGORY["shunting"], pol)) / 1e6
        out.append({"pollutant": pol, "tier1_kt": t1, "tier2_kt": t2,
                    "ratio_t2_over_t1": t2 / t1 if t1 else None})
    return out


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = RailwaysData()
    s = split(data)
    control = traction.diesel_kt(data)
    with open(asset_path(OUTPUTS, "railways_tier2_split_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["service", "fuel_kt", "share_pct", "basis"])
        for k, v in s.items():
            basis = ("declared 5 percent assumption; see rail-service-split"
                     if k == "shunting" else "published train-km split of the remainder")
            w.writerow([k, round(v, 4), round(100 * v / control, 2), basis])
        w.writerow(["railcar", 0.0, 0.0, "NO - workings Nil in the inventory years"])
        w.writerow(["CONTROL (traction.diesel_kt)", round(control, 4), 100.0,
                    "the split reconciles to this exactly; asserted in-function"])

    diag = air_diagnostic(data)
    with open(asset_path(OUTPUTS, "railways_tier2_air_diagnostic_%d.csv" % data.year),
              "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["pollutant", "tier1_kt", "tier2_kt",
                                          "ratio_t2_over_t1"])
        w.writeheader()
        for r in diag:
            w.writerow({k: (round(v, 6) if isinstance(v, float) else v)
                        for k, v in r.items()})

    print("Tier 2 split (kt diesel, control %.2f):" % control)
    for k, v in s.items():
        print("  %-20s %8.3f  (%.1f%%)" % (k, v, 100 * v / control))
    print("Tier 1 vs Tier 2 air diagnostic:")
    for r in diag:
        print("  %-6s T1 %8.4f  T2 %8.4f kt  (x%.2f)"
              % (r["pollutant"], r["tier1_kt"], r["tier2_kt"], r["ratio_t2_over_t1"]))


if __name__ == "__main__":
    main()
