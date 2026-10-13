"""Domestic navigation (1.A.3.d): the screening estimate the OCAC row permits.

THE AUDIT THIS CLOSES (the second review's 8.5). The activity has been in this repository
since the OCAC transcription landed -- a Domestic Bunkers HSD row in every held edition --
while the category sat NE with a hard-coded "about 0.022 Mt" note in the fuel ledger. That
note was FY2021-22 arithmetic (6.936 kt) attached to a live quantity that reads 3.054 kt
in the FY2023-24 reference year: a stale prose constant on a moving number, the exact
defect class the paper-number guards exist for, sitting in a code comment where they
cannot see it. The two things the register said were missing -- a marine factor choice and
a domestic/foreign boundary review -- are made here, and the result is published as a
SCREENING ESTIMATE with a notation-key consequence, not a new term in the frozen total.

THE FACTOR CHOICE. IPCC 2006 Vol 2 Ch 3 Table 3.5.2 gives water-borne diesel CO2 74,100
kg/TJ (identical to every other diesel use: carbon is carbon) and Table 3.5.3 gives CH4 7
and N2O 2 kg/TJ for ocean-going ships. The factors live HERE, not in
data/emission_factors.csv: a registry row would join the shared fuel-carbon dependency
groups and the parameter count the paper states, for a category outside every total.

THE BOUNDARY REVIEW. OCAC's row is labelled Domestic Bunkers within the TRANSPORT section
and rolls up into Total Transport beside Road and Railways, so the label itself asserts
the domestic side of the 1.A.3.d split. International bunkering is a separate register row
(marine-bunkers) with its own warning about the OGRA Overseas/Export line, and Pakistan
had no formal international bunkering market in the covered years. The residual boundary
risk -- fishing vessels fueling at retail pumps inside the Road row -- is declared, not
resolved.

THE SERIES IS THE FINDING. Nine held editions run 0.032 to 8.342 kt with no trend; the
screening estimate is therefore quoted per edition, with the reference-year value the
headline and the spread the caveat. This is why it stays a screen: an activity this
volatile needs the port-side series the gap register names before it can carry an E.

Usage: written by run_transport on every run; also
       python3 -m pkinv.sectors.transport.navigation_screen
Writes: outputs/transport_navigation_screen_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import write_table

PANEL = asset_path(DATA, "activity", "transport", "ocac_sectoral_annual.csv")

# IPCC 2006 Vol 2 Ch 3, water-borne navigation, diesel. Screening-only: never read by any
# engine build, never in the parameter registry (see the module docstring for why).
MARINE_CO2_KG_TJ = 74100.0     # Table 3.5.2, gas/diesel oil
MARINE_CH4_KG_TJ = 7.0         # Table 3.5.3, ocean-going ships
MARINE_N2O_KG_TJ = 2.0         # Table 3.5.3
DIESEL_NCV_TJ_GG = 43.0        # Table 1.2, same value the whole diesel chain uses

GWP_AR5 = {"CH4": 28.0, "N2O": 265.0}


def rows():
    """One screening row per held OCAC edition, tonnes HSD -> Mt CO2e (AR5)."""
    out = []
    panel = list(_activity_rows(PANEL, comments=False))
    for r in panel:
        if r["sector_row"] != "Domestic Bunkers" or r["product"] != "HSD":
            continue
        tonnes = float(r["tonnes"])
        tj = tonnes / 1e6 * DIESEL_NCV_TJ_GG * 1000.0     # t -> Gg -> TJ
        co2_t = tj * MARINE_CO2_KG_TJ / 1000.0
        ch4_t = tj * MARINE_CH4_KG_TJ / 1000.0
        n2o_t = tj * MARINE_N2O_KG_TJ / 1000.0
        co2e_mt = (co2_t + ch4_t * GWP_AR5["CH4"] + n2o_t * GWP_AR5["N2O"]) / 1e6
        out.append({
            "fy_label": r["fy_label"], "inventory_year": r["inventory_year"],
            "hsd_t": tonnes, "energy_TJ": round(tj, 3),
            "co2_t": round(co2_t, 2), "ch4_t": round(ch4_t, 4),
            "n2o_t": round(n2o_t, 4), "co2e_Mt_AR5": round(co2e_mt, 5),
            "status": "screening - outside every total",
            "basis": "OCAC Domestic Bunkers HSD x IPCC Table 1.2 NCV x Tables "
                     "3.5.2/3.5.3 water-borne factors",
        })
    if not out:
        raise ValueError("no Domestic Bunkers HSD rows found in the OCAC panel; the "
                         "screen has nothing to screen and the register row is stale")
    out.sort(key=lambda r: r["fy_label"])
    return out


def reference_row(year=2024):
    for r in rows():
        if int(r["inventory_year"]) == year:
            return r
    raise KeyError(year)


FIELDS = ("fy_label", "inventory_year", "hsd_t", "energy_TJ", "co2_t", "ch4_t", "n2o_t",
          "co2e_Mt_AR5", "status", "basis")


def write(year=2024):
    out = rows()
    path = asset_path(OUTPUTS, "transport_navigation_screen_%d.csv" % year)
    write_table(path, FIELDS, out, lineterminator="\n")
    return path, out


def main():
    path, out = write()
    ref = reference_row()
    print("domestic navigation screen -> %s" % path)
    print("  FY2023-24: %.0f t HSD -> %.5f Mt CO2e (AR5), screening only"
          % (ref["hsd_t"], ref["co2e_Mt_AR5"]))
    values = [r["co2e_Mt_AR5"] for r in out]
    print("  %d editions span %.5f-%.5f Mt; the volatility is the finding"
          % (len(out), min(values), max(values)))


if __name__ == "__main__":
    main()
