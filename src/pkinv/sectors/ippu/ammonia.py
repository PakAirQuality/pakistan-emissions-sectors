"""Ammonia production (IPCC 2.B.1), Tier 1 calibrated - a reference component since rc52.

THE METHOD (the user's, 2026-09-10):  E_2.B.1 = A_NH3 x EF_gross - CO2_recovered_to_urea.
  A_NH3   the ammonia embodied in NFDC's domestic fertilizer production by nitrogen stoichiometry
          (every ammoniacal product x its NH3 content, data/emission_factors.csv ammonia_embodied) -
          the PRIMARY activity pathway; NFDC's nitrogen x 17/14 validates it independently and the
          two plant censuses disaggregate it (ammonia_reconciliation.py keeps all four pathways).
  EF      1.815 t CO2/t NH3, CALIBRATED so the 2020-21 NFDC year reproduces Pakistan's own BTR filing
          (3.02 Mt); the IPCC modern (1.694) and conventional total-energy (2.104) factors are the
          METHOD envelope beside it, never a confidence interval.
  recovery  urea produced x 44/60 (IPCC Eq 3.10): the CO2 that leaves the plant inside the urea
          re-emerges at application under agriculture's 3.H, so booking it here would count it twice.

WHY IT ENTERS NOW (decision-rule row 2). The activity is a full FY2015-16..FY2024-25 series from
NFDC's own production statistics, every year closing on its printed total and identical across
editions (data/nfdc/nfdc_production_by_product_series.csv); the factor is calibrated to the official
inventory; and since rc67 the post-meter leak factor no longer rides the feedstock gas (the
fugitives reference withholds it; outputs/pakemis_gas_flow_crosswalk.csv). An earlier edition of this
docstring said the feedstock double-claim was "already priced (the gas ledger's -0.288 Mt deduction)".
That figure is the combustion netting of four burned streams and holds no fertiliser term. What
the gate still lacks - plant-level output and recovered CO2 for every plant - is a Tier 2 refinement
of a Tier 1 estimate, not a reason to keep 3 Mt a year outside every total.

THE BOUNDARY. The whole fertiliser gas class, feedstock and process fuel together, is outside every
combustion total: the factor here is on the plant's total gas requirement, so it prices the fuel
with the feed, and OGRA's fertiliser class is not in the industry module's general-industry row.
An earlier edition said the fuel gas was "inside 1.A.2"; it is not, and booking it there would count
it twice. Nothing here double counts combustion.
"""
from __future__ import annotations

from pkinv.core.uncertainty import product

CATEGORY = "Ammonia production"
SUBITEM = "Ammonia process CO2 net of urea recovery"
PRODUCTS = ("Urea", "CAN", "NP", "DAP", "NPK", "SSP", "SOP")
ACTIVITY_UNCERT_PCT = 5.0        # NFDC production statistics: published administrative totals


def fiscal_label(year):
    """2024 -> '2023-24' (the fiscal year ending in `year`)."""
    return "%d-%02d" % (year - 1, year % 100)


def production_kt(data, fiscal_year, product_name):
    """NFDC production of one product in one fiscal year, kt; the first edition printing the year
    wins (editions agree to the tonne where both print a year). Raises when the year is not held."""
    for r in data.fertilizer_production_series_rows:
        if r["fiscal_year"] == fiscal_year and r["product"] == product_name and r["production_000t"]:
            return float(r["production_000t"])
    if any(r["fiscal_year"] == fiscal_year for r in data.fertilizer_production_series_rows):
        return 0.0                                   # the year is printed, the product is not made
    raise ValueError("NFDC production is not held for %s" % fiscal_year)


def nh3_kt(data, fiscal_year):
    return sum(production_kt(data, fiscal_year, p) * data.efv("ammonia_embodied", p) for p in PRODUCTS)


def compute(data, year=None):
    """Return ([component], [memo]) for the fiscal year ending in `year` (default: the reference)."""
    year = data.year if year is None else int(year)
    fy = fiscal_label(year)
    nh3 = nh3_kt(data, fy)
    ef = data.p("ammonia_ef_calibrated")
    urea = production_kt(data, fy, "Urea")
    recovered = urea * data.p("urea_co2_recovery_factor")
    gross = nh3 * ef
    net = gross - recovered
    if net <= 0:
        raise ValueError("ammonia process CO2 net of urea recovery is not positive for %s" % fy)
    component = {
        "category": CATEGORY, "subitem": SUBITEM, "gas": "CO2",
        "emissions_Gg": net,
        "uncert_pct": product(ACTIVITY_UNCERT_PCT, data.pu("ammonia_ef_calibrated")),
    }
    memo = {
        "fiscal_year": fy, "nh3_kt": nh3, "urea_kt": urea, "ef_t_co2_per_t_nh3": ef,
        "gross_Gg": gross, "recovered_to_urea_Gg": recovered, "net_Gg": net,
        "envelope_low_Gg": nh3 * data.p("ammonia_ef_modern") - recovered,
        "envelope_high_Gg": nh3 * data.p("ammonia_ef_total_energy") - recovered,
        "activity_basis": "NFDC production by product x NH3 stoichiometry",
        "configuration_status": "reference_tier1_calibrated",
    }
    return [component], [memo]
