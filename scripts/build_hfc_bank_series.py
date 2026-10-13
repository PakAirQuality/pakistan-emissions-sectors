"""HFC emissions from the HOUSEHOLD EQUIPMENT BANK, FY2015-16..FY2023-24 - a band per year, and the
first stock-based cross-check of the consumption-based F-gas lanes.

WHY A STOCK MODEL. Annex F consumption (Ozone Secretariat) is the SUPPLY entering the bank, not the
emission; the shipped F-gas lanes (`scope_plus_fgas_screening` 9.82 Mt bulk, `scope_plus_fgas_bounded_bank`
4.42, `scope_plus_fgas_species_bank` 5.85) all start from that supply. IPCC Vol 3 Ch 7 Tier 2 starts
from the equipment instead: emissions = stock x charge x refrigerant GWP x operating loss rate. This
release holds the stock indicator for the first time - design-weighted household ownership from HIES
2018-19 and 2024-25 (data/activity/ippu/hies_appliance_ownership.csv: refrigerators 17.2 -> 23.8 M,
air conditioners 3.29 -> 5.70 M, cars 2.05 -> 3.03 M) - so the household bank can be priced as a band.

WHAT IS INSIDE, WHAT IS NOT. Three household applications: domestic refrigeration (refrigerators +
deep freezers), residential air conditioning, mobile air conditioning (cars). Commercial and
industrial refrigeration, chillers, transport refrigeration, foams, aerosols and solvents carry NO
stock indicator here and are typed absent - which is exactly why this band is a FLOOR on the
equipment bank and the comparison with the supply lanes is the finding, not a reconciliation.

EVERY PARAMETER IS A RANGE FROM IPCC TABLE 7.9 (data/raw/ipcc/ipcc2006_V3_7_Ch7_ODS_Substitutes.pdf)
OR A NAMED ASSUMPTION: charge (kg/unit), operating emission factor x (percent of charge per year;
the developing-country end of each range applies). Refrigerant identity per application is NOT
surveyed: the HFC share of the stock is a declared band (refrigerators: R-134a giving way to R-600a,
0.5..1.0; residential AC: R-22 (an HCFC, outside Annex F) still dominant, HFC blends R-410A/R-32
0.2..0.6; mobile AC: R-134a, 1.0). GWP (AR5): R-134a 1300; R-410A 1924 / R-32 677 as the AC band.
Ownership between the two surveys is interpolated linearly; before FY2018-19 it is EXTRAPOLATED and
flagged (HIES 2015-16 asks no ownership question). Household totals are the surveys' own weighted
frames (33.34 M FY2018-19, 40.12 M FY2024-25), interpolated the same way.

Reads:  data/activity/ippu/hies_appliance_ownership.csv
Writes: outputs/pakemis_hfc_bank_series.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, OUTPUTS  # noqa: E402

OWNERSHIP = asset_path(DATA, "activity", "ippu", "hies_appliance_ownership.csv")
OUT = asset_path(OUTPUTS, "pakemis_hfc_bank_series.csv")
YEARS = list(range(2016, 2025))               # fiscal end years FY2015-16..FY2023-24
SURVEY_YEARS = {"HIES 2018-19": 2019, "HIES 2024-25": 2025}

# application -> (appliances, charge kg low/high, operating x % low/high, HFC share low/high, GWP low/high, IPCC row)
APPLICATIONS = {
    "domestic refrigeration": (("refrigerator", "deep_freezer"), 0.05, 0.5, 0.1, 0.5, 0.5, 1.0, 1300.0, 1300.0,
                               "Table 7.9 Domestic Refrigeration: M 0.05..0.5 kg, x 0.1..0.5 %/yr; R-134a (GWP 1300) giving way to R-600a - HFC share 0.5..1.0 assumed"),
    "residential air conditioning": (("air_conditioner",), 0.5, 2.0, 1.0, 10.0, 0.2, 0.6, 677.0, 1924.0,
                                     "Table 7.9 Residential and Commercial A/C: M 0.5..100 kg (household splits 0.5..2 taken), x 1..10 %/yr; R-22 (HCFC) dominant, HFC blends R-32 (677)..R-410A (1924) share 0.2..0.6 assumed"),
    "mobile air conditioning": (("motor_car",), 0.5, 1.5, 10.0, 20.0, 1.0, 1.0, 1300.0, 1300.0,
                                "Table 7.9 Mobile A/C: M 0.5..1.5 kg, x 10..20 %/yr; R-134a (GWP 1300)"),
}
FIELDS = ("fiscal_year", "application", "appliances", "stock_units", "stock_basis", "households",
          "charge_kg_low", "charge_kg_high", "hfc_share_low", "hfc_share_high", "gwp_low", "gwp_high",
          "bank_mt_co2e_low", "bank_mt_co2e_high", "loss_pct_low", "loss_pct_high",
          "emissions_mt_co2e_low", "emissions_mt_co2e_high", "ipcc_basis", "status", "note")
HEADER = """\
# HFC EMISSIONS FROM THE HOUSEHOLD EQUIPMENT BANK, FY2015-16..FY2023-24 - a BAND per year and application (IPCC Vol 3
# Ch 7 Tier 2 shape: stock x charge x HFC share x GWP x operating loss), from the first stock indicator held (HIES
# 2018-19 and 2024-25 design-weighted ownership). Household applications only: commercial/industrial refrigeration,
# chillers, foams, aerosols and solvents carry no stock indicator and are typed absent, so the total is a FLOOR on the
# equipment bank. Ownership before FY2018-19 is EXTRAPOLATED (flagged). Every parameter is an IPCC range or a named
# assumption; no central. Outside every total. scripts/build_hfc_bank_series.py
"""


def _rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def observations():
    """{(survey_year, appliance): (units_owned, households_total)} at national level."""
    obs = {}
    for r in _rows(OWNERSHIP):
        if r["region"] or r["survey"] not in SURVEY_YEARS or not r["weighted_units_owned"]:
            continue
        obs[(SURVEY_YEARS[r["survey"]], r["appliance"])] = (float(r["weighted_units_owned"]), float(r["weighted_households_total"]))
    return obs


def interpolate(y, y0, v0, y1, v1):
    return v0 + (v1 - v0) * (y - y0) / float(y1 - y0)


def build():
    obs = observations()
    y0, y1 = 2019, 2025
    out = []
    for y in YEARS:
        fy = "%d-%02d" % (y - 1, y % 100)
        hh = interpolate(y, y0, obs[(y0, "refrigerator")][1], y1, obs[(y1, "refrigerator")][1])
        basis = "interpolated between HIES 2018-19 and 2024-25" if y0 <= y <= y1 else "EXTRAPOLATED before HIES 2018-19 (no ownership question in HIES 2015-16)"
        for app, (apps, m_lo, m_hi, x_lo, x_hi, s_lo, s_hi, g_lo, g_hi, basis_txt) in APPLICATIONS.items():
            stock = 0.0
            for a in apps:
                stock += max(0.0, interpolate(y, y0, obs[(y0, a)][0], y1, obs[(y1, a)][0]))
            bank_lo = stock * m_lo * s_lo * g_lo / 1e9          # units x kg -> kg refrigerant -> t (/1e3) x GWP -> t CO2e -> Mt (/1e6)
            bank_hi = stock * m_hi * s_hi * g_hi / 1e9
            out.append({
                "fiscal_year": fy, "application": app, "appliances": "+".join(apps),
                "stock_units": "%.0f" % stock, "stock_basis": basis, "households": "%.0f" % hh,
                "charge_kg_low": m_lo, "charge_kg_high": m_hi, "hfc_share_low": s_lo, "hfc_share_high": s_hi,
                "gwp_low": "%.0f" % g_lo, "gwp_high": "%.0f" % g_hi,
                "bank_mt_co2e_low": "%.4f" % bank_lo, "bank_mt_co2e_high": "%.4f" % bank_hi,
                "loss_pct_low": x_lo, "loss_pct_high": x_hi,
                "emissions_mt_co2e_low": "%.5f" % (bank_lo * x_lo / 100.0),
                "emissions_mt_co2e_high": "%.5f" % (bank_hi * x_hi / 100.0),
                "ipcc_basis": basis_txt,
                "status": "band series (screening; outside every total); household applications only",
                "note": "operating losses only; manufacturing/initial charge, servicing and end-of-life losses are not priced here",
            })
        # the floor total
        lo = sum(float(r["emissions_mt_co2e_low"]) for r in out if r["fiscal_year"] == fy and r["application"] != "household bank total (floor)")
        hi = sum(float(r["emissions_mt_co2e_high"]) for r in out if r["fiscal_year"] == fy and r["application"] != "household bank total (floor)")
        out.append({"fiscal_year": fy, "application": "household bank total (floor)", "appliances": "",
                    "stock_units": "", "stock_basis": basis, "households": "%.0f" % hh,
                    "charge_kg_low": "", "charge_kg_high": "", "hfc_share_low": "", "hfc_share_high": "", "gwp_low": "", "gwp_high": "",
                    "bank_mt_co2e_low": "%.4f" % sum(float(r["bank_mt_co2e_low"]) for r in out if r["fiscal_year"] == fy and r["bank_mt_co2e_low"]),
                    "bank_mt_co2e_high": "%.4f" % sum(float(r["bank_mt_co2e_high"]) for r in out if r["fiscal_year"] == fy and r["bank_mt_co2e_high"]),
                    "loss_pct_low": "", "loss_pct_high": "",
                    "emissions_mt_co2e_low": "%.5f" % lo, "emissions_mt_co2e_high": "%.5f" % hi,
                    "ipcc_basis": "sum of the three household applications",
                    "status": "FLOOR on the equipment bank: commercial/industrial refrigeration, chillers, foams, aerosols, solvents typed absent",
                    "note": ("compare the supply lanes: Annex F consumption 7.4-9.8 Mt CO2e/yr (2019-2024) and the consumption-based banks "
                             "4.42 / 5.85 Mt - the household equipment bank cannot absorb that supply; the difference is commercial "
                             "and industrial banks, servicing losses and stockpiling, none of which is surveyed")})
    return out


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("HFC household bank series -> %s (%d rows)" % (os.path.relpath(OUT), len(rows)))
    for r in rows:
        if r["application"].startswith("household bank total"):
            print("  %s households %s M  bank %s..%s Mt  emissions %s..%s Mt CO2e  (%s)" % (
                r["fiscal_year"], "%.2f" % (float(r["households"]) / 1e6), r["bank_mt_co2e_low"], r["bank_mt_co2e_high"],
                r["emissions_mt_co2e_low"], r["emissions_mt_co2e_high"], r["stock_basis"][:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
