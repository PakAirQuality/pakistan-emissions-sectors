"""Lubricant use (IPCC 2.D.1), Tier 1 - a reference component since rc52.

IPCC 2006 Vol 3 Ch 5 Eq 5.2:  CO2 = LC x ODU x 44/12, with LC the carbon in the lubricants used
(tonnes x NCV 40.2 TJ/Gg x 20.0 t C/TJ, Vol 2 Tables 1.2-1.3) and ODU the fraction oxidised in use:
0.2 for lubricating oil, 0.05 for grease (Table 5.2). The activity is OCAC's sectoral sales of
non-energy products - the LUBES and GREASES grand totals per fiscal year, all sectors, M. Tons
(data/activity/industry/ocac_non_energy_sectoral.csv): sales are the 2.D activity basis (first use
of the product), and the ODU fraction is what separates the share burned in engines from the share
recovered or disposed. FY2015-16 is the 2016-17 edition's previous-year column (status carried).

WHY IT ENTERS NOW. Nine years of the publisher's own national sales, every row closing on its
printed total; the IPCC default method; a small mass (0.05-0.10 Mt). Two-stroke engine use, which
Table 5.2 excludes from the ODU default, is not separated in the sales table - a small upward bias
named here rather than corrected.
"""
from __future__ import annotations

from pkinv.core.uncertainty import product

CATEGORY = "Lubricant use"
SUBITEM_OIL = "Lubricating oil oxidised in use"
SUBITEM_GREASE = "Grease oxidised in use"
ACTIVITY_UNCERT_PCT = 10.0


def fiscal_label(year):
    return "%d-%02d" % (year - 1, year % 100)


def sales_t(data, fiscal_year, product_name):
    """The grand-total tonnes of LUBES or GREASES for a fiscal year: the year's own edition where
    held ('GRAND TOTAL (A+B) VOLUME'), else the next edition's previous-year grand total."""
    own, previous = None, None
    for r in data.ocac_non_energy_rows:
        if r["fiscal_year"] != fiscal_year or r["section"] != "GRAND TOTAL" or r["product"] != product_name or not r["quantity"]:
            continue
        if "(A+B)" in r["sector_row"]:
            own = float(r["quantity"])
        else:
            previous = float(r["quantity"])
    if own is not None:
        return own
    if previous is not None:
        return previous
    raise ValueError("OCAC non-energy sales are not held for %s %s" % (fiscal_year, product_name))


def _co2_Gg(data, tonnes, odu_param):
    tj = tonnes / 1000.0 * data.p("lubricant_ncv_tj_per_gg")
    carbon_t = tj * data.p("lubricant_carbon_t_per_tj")
    return carbon_t * data.p(odu_param) * 44.0 / 12.0 / 1000.0


def compute(data, year=None):
    year = data.year if year is None else int(year)
    fy = fiscal_label(year)
    oil_t, grease_t = sales_t(data, fy, "LUBES"), sales_t(data, fy, "GREASES")
    components = [
        {"category": CATEGORY, "subitem": SUBITEM_OIL, "gas": "CO2",
         "emissions_Gg": _co2_Gg(data, oil_t, "lubricant_odu_oil"),
         "uncert_pct": product(ACTIVITY_UNCERT_PCT, data.pu("lubricant_odu_oil"))},
        {"category": CATEGORY, "subitem": SUBITEM_GREASE, "gas": "CO2",
         "emissions_Gg": _co2_Gg(data, grease_t, "lubricant_odu_grease"),
         "uncert_pct": product(ACTIVITY_UNCERT_PCT, data.pu("lubricant_odu_grease"))},
    ]
    memo = {"fiscal_year": fy, "lubricating_oil_t": oil_t, "grease_t": grease_t,
            "configuration_status": "reference_tier1_odu"}
    return components, [memo]
