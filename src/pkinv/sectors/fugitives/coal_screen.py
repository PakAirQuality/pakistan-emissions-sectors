"""Coal-mining fugitives (1.B.1): the Tier-1 screen the held activity permits.

THE AUDIT THIS CLOSES (the second review's 8.7). The gap register said a Tier-1 estimate
"needs coal PRODUCTION, which ... has not been compiled here" with access marked paid --
and the dominant share of Pakistani coal production has been in this repository the whole
time: NEPRA Table 21 plant-level fuel deliveries (data/activity/power/plant_fuel_ledger.csv)
carry the four Thar mine-mouth plants' lignite in tonnes, and a mine-mouth delivery IS the
mine's dispatched output. The same "it was here all along" pattern the OCAC bunkers row and
the industrial-liquids rows recorded. What is genuinely absent is narrower than the
register claimed: national production OUTSIDE Thar -- the underground mines of Balochistan,
KP and Punjab -- and any Pakistani mine-gas measurement.

THE SCREEN, and its declared scope. IPCC 2006 Vol 2 Ch 4 Tier 1 for SURFACE mining
(Table 4.1.5): 0.3--2.0 m3 CH4 per tonne, plus 0--0.2 m3/t post-mining, at 0.67 kg/m3.
Applied to the FY2023-24 Thar mine-mouth deliveries this brackets the surface share at
roughly 0.07--0.55 Mt CO2e (AR5). Thar lignite is shallow and young, which argues the low
end. THE BOUND IS PARTIAL BY CONSTRUCTION and every row says so: underground mining runs
10--25 m3/t -- thirty times the surface low -- so even a small underground tonnage could
dominate the category, and no underground production figure is held. A screen that printed
its surface arithmetic as the category's upper bound would be the familiar defect of a
check claiming more than it tests; the unquantified row is published beside the numbers.

Usage: written by run_fugitives on every run; also
       python3 -m pkinv.sectors.fugitives.coal_screen
Writes: outputs/fugitives_coal_screen_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import write_table

PLANT_LEDGER = asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv")
FISCAL_YEAR = 2023            # the power ledger's FY2023-24 label

# IPCC 2006 Vol 2 Ch 4, Tier 1, surface mining. Screening-only constants, deliberately
# not in any factor registry (the category is outside every total).
SURFACE_MINING_M3_T = (0.3, 2.0)       # Table 4.1.5
SURFACE_POST_MINING_M3_T = (0.0, 0.2)  # Table 4.1.5
UNDERGROUND_M3_T = (10.0, 25.0)        # Table 4.1.4, quoted for scale only - no activity
CH4_KG_M3 = 0.67
GWP_AR5_CH4 = 28.0


def thar_mass_kt(fiscal_year=FISCAL_YEAR):
    """Mine-mouth Thar lignite deliveries, kt, plus the unknown-origin tonnage beside
    them (published so the exclusion is visible, never silently dropped)."""
    thar, unknown = 0.0, 0.0
    for r in _activity_rows(PLANT_LEDGER, comments=False):
        if int(r["fiscal_year"]) != fiscal_year or r["fuel"].lower() != "coal":
            continue
        if r["fuel_origin"] == "Thar lignite":
            thar += float(r["quantity"])
        elif r["fuel_origin"] == "unknown":
            unknown += float(r["quantity"])
    if thar <= 0:
        raise ValueError("no Thar lignite rows in the plant ledger for FY%d; the coal "
                         "screen has lost its activity basis" % fiscal_year)
    return thar, unknown


def rows(fiscal_year=FISCAL_YEAR):
    thar_kt, unknown_kt = thar_mass_kt(fiscal_year)
    tonnes = thar_kt * 1000.0

    def bound(m3_per_t):
        ch4_t = tonnes * m3_per_t * CH4_KG_M3 / 1000.0
        return ch4_t, ch4_t * GWP_AR5_CH4 / 1e6

    lo_ch4, lo_mt = bound(SURFACE_MINING_M3_T[0] + SURFACE_POST_MINING_M3_T[0])
    hi_ch4, hi_mt = bound(SURFACE_MINING_M3_T[1] + SURFACE_POST_MINING_M3_T[1])
    return [
        {"scope": "Thar surface (mine-mouth deliveries)", "bound": "low",
         "activity_kt": round(thar_kt, 2),
         "ef_m3_per_t": SURFACE_MINING_M3_T[0] + SURFACE_POST_MINING_M3_T[0],
         "ch4_t": round(lo_ch4, 1), "co2e_Mt_AR5": round(lo_mt, 4),
         "status": "screening - outside every total",
         "note": "IPCC Table 4.1.5 surface low + post-mining low; shallow young lignite "
                 "argues this end of the band"},
        {"scope": "Thar surface (mine-mouth deliveries)", "bound": "high",
         "activity_kt": round(thar_kt, 2),
         "ef_m3_per_t": SURFACE_MINING_M3_T[1] + SURFACE_POST_MINING_M3_T[1],
         "ch4_t": round(hi_ch4, 1), "co2e_Mt_AR5": round(hi_mt, 4),
         "status": "screening - outside every total",
         "note": "IPCC Table 4.1.5 surface high + post-mining high"},
        {"scope": "unknown-origin plant coal", "bound": "excluded",
         "activity_kt": round(unknown_kt, 2), "ef_m3_per_t": "",
         "ch4_t": "", "co2e_Mt_AR5": "",
         "status": "excluded from the bound",
         "note": "plant coal of undeclared origin (Lucky Electric); if domestic surface "
                 "it raises the Thar band by about a tenth, if imported it belongs to "
                 "another country's 1.B.1"},
        {"scope": "underground mining (Balochistan, KP, Punjab)", "bound": "unquantified",
         "activity_kt": "", "ef_m3_per_t": "%s-%s" % UNDERGROUND_M3_T,
         "ch4_t": "", "co2e_Mt_AR5": "",
         "status": "unquantified - no production figure held",
         "note": "Table 4.1.4 underground factors run thirty times the surface low, so "
                 "even a small underground tonnage could dominate the category; the "
                 "band above is a PARTIAL bound and must not be read as the category's "
                 "ceiling. The named acquisition (fugitive-solid-fuels) is national "
                 "production by mine type"},
    ]


FIELDS = ("scope", "bound", "activity_kt", "ef_m3_per_t", "ch4_t", "co2e_Mt_AR5",
          "status", "note")


def surface_band_mt(fiscal_year=FISCAL_YEAR):
    """(low, high) Mt CO2e of the Thar surface bound - what the materiality screen fills
    its column with, labelled partial."""
    out = rows(fiscal_year)
    return out[0]["co2e_Mt_AR5"], out[1]["co2e_Mt_AR5"]


def write(year=2024):
    out = rows()
    path = asset_path(OUTPUTS, "fugitives_coal_screen_%d.csv" % year)
    write_table(path, FIELDS, out, lineterminator="\n")
    return path, out


def main():
    path, out = write()
    lo, hi = surface_band_mt()
    print("coal-mining screen -> %s" % path)
    print("  Thar surface bound: %.4f-%.4f Mt CO2e (AR5) on %.1f kt mine-mouth "
          "deliveries; underground unquantified" % (lo, hi, out[0]["activity_kt"]))


if __name__ == "__main__":
    main()
