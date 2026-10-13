"""The fleet-implied fuel diagnostic - the bottom-up demand the paper refuses to use.

THE MISSING DEMONSTRATION. The paper's central thesis is that the fleet model should
distribute fuel, not size it. CNG already shows why (cng_gap.py: metered gas implies
0.87 MJ/km against any plausible rate). This module performs the same comparison for
all three fuels: the bottom-up demand a conventional inventory would compute,

    F_f = sum_c  vkt(c, f) x MJ/km(c, f),

against the observed controls (OCAC Road rows; OGRA metered gas). The per-class
energy-intensity bands are DECLARED ENGINEERING JUDGEMENT in transport_params.csv
(mjkm_lo_*/mjkm_hi_*), the same epistemic class as cng_gap's 1.2-6.0 MJ/km band -
generic ranges, not Pakistani measurements - so the output is a diagnostic that
flags disagreement and NEVER adjusts anything, the cng_gap precedent.

ONE DEFINITION OF MJ/km, SHARED WITH THE ALLOCATOR. Since August 2026 the same bands
also weight the class split (road._shares via data.mjkm), so this diagnostic is no
longer independent of the composition it is quoted beside: both read one accessor, and
that is the point - the numbers cannot diverge. What the diagnostic still tests
independently is the MAGNITUDE, because the class split is normalised and therefore
cannot reproduce a fuel total at all. That is the comparison below.

Writes: outputs/transport_fleet_fuel_diagnostic_2022.csv - per fuel: fleet-implied
TJ at the band low/mid/high, the control TJ, implied/control ratios, the
calibration multiplier a bottom-up build would need, and a verdict.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.sectors.transport import cng, road
from pkinv.sectors.transport.data import TransportData
from pkinv.core.io import write_table

FUELS = ("Petrol", "Diesel", "CNG")


def implied_TJ(data, year=None):
    """{fuel: (lo_TJ, mid_TJ, hi_TJ)} - bottom-up demand at the declared bands."""
    vkt, _cells, _capped = road.effective_vkt(data, year)
    out = {}
    for fuel in FUELS:
        lo = mid = hi = 0.0
        for (cls, f), km in vkt.items():
            if f != fuel:
                continue
            lo += km * data.mjkm(cls, f, "lo") / 1e6
            hi += km * data.mjkm(cls, f, "hi") / 1e6
            mid += km * data.mjkm(cls, f, "mid") / 1e6
        out[fuel] = (lo, mid, hi)
    return out


def controls_TJ(data, year=None):
    tj = road.fuel_TJ(data, year)
    return {"Petrol": tj["Petrol"], "Diesel": tj["Diesel"],
            "CNG": cng.gas_TJ(data, year)}


def diagnostic(data=None, year=None):
    """One row per fuel. Flags, never adjusts."""
    data = TransportData() if data is None else data
    implied = implied_TJ(data, year)
    controls = controls_TJ(data, year)
    rows = []
    for fuel in FUELS:
        lo, mid, hi = implied[fuel]
        control = controls[fuel]
        ratio_mid = mid / control
        if hi < control:
            verdict = "FLEET-MODEL-LOW"       # even the high band undershoots
        elif lo > control:
            verdict = "FLEET-MODEL-HIGH"      # even the low band overshoots
        else:
            verdict = "CONTROL-INSIDE-BAND"
        rows.append({
            "fuel": fuel,
            "implied_TJ_lo": round(lo, 0), "implied_TJ_mid": round(mid, 0),
            "implied_TJ_hi": round(hi, 0),
            "control_TJ": round(control, 0),
            "ratio_mid_over_control": round(ratio_mid, 3),
            "calibration_multiplier": round(1.0 / ratio_mid, 3),
            "verdict": verdict,
            "note": "declared engineering bands, not Pakistani measurements; the "
                    "diagnostic never adjusts the inventory - it demonstrates why "
                    "the fleet distributes rather than sizes",
        })
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = TransportData()
    rows = diagnostic(data)
    path = asset_path(OUTPUTS,
                        "transport_fleet_fuel_diagnostic_%d.csv" % data.year)
    write_table(path, list(rows[0].keys()), rows)
    print("Fleet-implied vs observed fuel (TJ):")
    for r in rows:
        print("  %-7s implied [%s, %s, %s] vs control %s  ratio %.2f  x%.2f  %s"
              % (r["fuel"], r["implied_TJ_lo"], r["implied_TJ_mid"],
                 r["implied_TJ_hi"], r["control_TJ"],
                 r["ratio_mid_over_control"], r["calibration_multiplier"],
                 r["verdict"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
