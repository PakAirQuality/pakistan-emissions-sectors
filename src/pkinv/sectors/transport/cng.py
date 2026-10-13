"""Compressed natural gas in road transport - IPCC 1A3b.

THE GAP THIS CLOSES, AND HOW IT WAS MISDESCRIBED. Pakistan ran one of the world's largest CNG
vehicle fleets, and this sector had no CNG in it at all, because the sector anchors on the
national PETROLEUM supply and CNG sits in the gas statistics. The paper called that "a
data-availability problem rather than a methodological one".

It was neither. OGRA's State of the Regulated Petroleum Industry reports gas consumption by
sector, and this inventory already read that document for the residential control total, the
LPG total, the kerosene total and the captive-power series. The CNG figure was one row of a
table four other numbers already came from. Nobody had fetched it.

THE ACTIVITY DATUM IS METERED AND CROSS-CHECKED. The FY2023-24 edition reports CNG twice, in
two tables built for different purposes: Table 3.31 splits sector gas by utility (SNGPL 59 +
SSGCL 3 = 62 MMCFD) and Table 6.1 gives the CNG sector's own thirteen-year series (62 MMCFD for
the same year). They agree. That is the only independent check the source offers on itself and
it is worth more than the precision of either figure.

WHY THIS DOES NOT DOUBLE-COUNT ANYTHING. Table 3.31 partitions national gas supply across
residential, commercial, industry, fertiliser, captive power, cement, power and transport. This
inventory takes the residential row into 1A4b, the captive row into 1A2, and now the transport
row into 1A3b. Three different rows of one partition, and the petroleum control total that
drives the rest of road transport is a different fuel entirely. Nothing here can be counted
twice, and a test asserts the three sectors read three distinct rows.

THE HEATING VALUE IS THE ASSUMPTION, AS IT IS FOR CAPTIVE GAS. OGRA reports a volume; IPCC
factors are per terajoule net. Pakistani pipeline gas runs roughly 900 to 1,000 Btu/scf
depending on field and RLNG share, and nothing read here pins it. The category is reported at
1,000 with the 900 case published beside it, exactly as the captive category does - and the
two sectors are pinned to the same value by test, because the same gas assumed two different
ways in one inventory is worse than an unpinned assumption.

WHAT IT IS NOT. It is not a fleet estimate. The vehicle-kilometre share of CNG travel is
reported separately by cng_gap.py and is NOT used here, because the sector's whole argument is
that its magnitude comes from metered fuel rather than from the fleet model. The two now sit
side by side: metered gas gives the emissions, and the fleet model says which vehicles burnt
it - which is the same division of labour road transport uses for petrol and diesel.

THE SERIES IS THE RESULT WORTH LOOKING AT. CNG gas fell from 325 MMCFD in FY2011-12 to 62 in
FY2023-24, an eighty-one percent collapse, as gas shortages closed stations and the federal
government's 2008 ban on new licences held. This category is shrinking faster than any other in
the inventory.
"""
from pkinv.core.uncertainty import product
from pkinv.core.units import mmcfd_to_TJ

CATEGORY = "Road transport"          # 1A3b, the same category as petrol and diesel
ITEM = "Natural Gas"
SUBITEM = "CNG %s"


def gas_TJ(data, year=None, hhv_btu=None):
    """Net terajoules of CNG in the year.

    hhv_btu overrides the gross heating value for the published sensitivity; None uses the
    nominal 1,000 Btu/scf the utilities bill at.
    """
    mmcfd = data.cng_mmcfd(year)
    hhv = data.p("cng_hhv_btu_per_scf") if hhv_btu is None else hhv_btu
    return mmcfd_to_TJ(mmcfd, hhv, data.p("cng_gross_to_net"))


def compute(data, year=None, hhv_btu=None):
    """Return components for the CNG stream. No memo: this is reported, not excluded."""
    tj = gas_TJ(data, year, hhv_btu)
    # The conversion to energy is as much a part of the activity figure as the volume, so the
    # heating value and the gross-to-net ratio join the metered uncertainty rather than being
    # treated as factor uncertainty.
    ad_u = product(data.p("cng_activity_uncert"),
                   data.pu("cng_hhv_btu_per_scf"),
                   data.pu("cng_gross_to_net"))
    out = []
    for gas, cat in (("CO2", "transport_fuel_co2"),
                     ("CH4", "transport_fuel_ch4"),
                     ("N2O", "transport_fuel_n2o")):
        row = {"category": CATEGORY, "subitem": SUBITEM % gas, "gas": gas,
               "emissions_Gg": tj * data.efv(cat, ITEM) / 1e6,
               "uncert_pct": product(ad_u, data.efu(cat, ITEM))}
        if gas == "CH4":
            # Fossil, so AR5 30 rather than the biogenic 28 - as in petrol, diesel, rail,
            # power and captive gas. CNG's methane factor is 92 kg/TJ against diesel's 3.9,
            # because unburnt methane slip dominates a gas engine's exhaust, so this row
            # matters more here than in any other combustion category.
            row["fossil"] = True
        out.append(row)
    return out
