"""Industrial fuel combustion - IPCC 1A2, the metered gas and the liquid fuels.

THE GAP THIS PUTS A SECOND NUMBER INSIDE. 1A2 is the largest single hole in this inventory.
EDGAR puts Pakistani industrial combustion near 44 Mt; captive self-generation covered 5.6 of
it, and everything else - process heat, boilers, kilns, and every non-gas industrial fuel - was
absent. This category adds the metered gas that industry burns for heat rather than for
electricity.

THE LIQUID FUELS WERE IN THE REPOSITORY THE WHOLE TIME. For one edition this module read
natural gas and nothing else, and the gap register called industrial fuel "not acquired"
while OCAC's Total Industry customer-class row - 642,021 tonnes of FY2023-24 furnace oil,
400,400 of diesel, and four smaller products - sat in a committed CSV that the transport
sector had ingested for its own Road rows. Reading it adds 3.4 Mt and moves 1A2 coverage from
13 to 33 percent of the EDGAR benchmark. That is the fourth time this inventory has found a
category absent from its outputs and present in its own data, and the lesson is the same one
each time: look before declaring an absence.

IT IS STILL A FLOOR. Industrial COAL, petroleum coke and bagasse are not estimated - OCAC
covers petroleum products, so the solid fuels are outside the publication entirely and no
Pakistani source this inventory has read reports them by sector. Roughly 29 Mt of 1A2 remains
open. The completeness table says so, and the category note says so, because a reader who
takes this for "Pakistani industrial emissions" would still be short by two thirds.

CUSTOMER CLASS IS NOT END USE, here as in transport. An industrial customer's diesel may run
a standby generator, a kiln or a forklift; OCAC's class says who bought it, not what burned
it. All three are 1A2, which is why the boundary is safe at this category's level even though
it is soft within it.

WHY IT IS SEPARATE FROM CAPTIVE POWER, WHICH IS ALSO 1A2. OGRA's sector table reports Captive
Power and General Industry as different rows because they are different uses: one turns gas
into electricity for the factory, the other raises steam and fires kilns. Both are 1A2 and both
take Table 2.3. They are estimated separately because they are metered separately, and keeping
them apart is what makes it checkable that neither absorbs the other's gas - a test asserts the
two rows are distinct values.

WHAT IS DELIBERATELY EXCLUDED, AND IT IS THE LARGEST ROW IN THE TABLE. Fertiliser takes 756
MMCFD, more than twice General Industry and second only to power. The IPCC ammonia method
(2006 GL V3 Ch3) allocates a plant's TOTAL GAS REQUIREMENT - feedstock and process fuel
together - to 2B1, and removes that gas from Energy so the same molecules are never counted
twice; only separately metered auxiliary combustion outside the ammonia process boundary
would stay in 1A2. NFDC's plant-wise tables put the split at 83.5 percent feed and 16.5
percent fuel in FY2023-24 - the reference year itself, read off the plants' own monthly
meters in Annex-28 - and 83.2/16.8 in FY2024-25, so about a sixth of the row IS burned,
and the burned sixth belongs to 2B1 anyway because the method draws the boundary around
the process, not around the flame. For one edition the reference year's shares were
BORROWED from the year after it, the annex having gone unread; that borrowing is
withdrawn. Two institutions now measure the same fiscal year and land half a percent
apart: OGRA's 756 MMCFD against NFDC's 752, a regulator's utility table against an
industry body's plant meters. An earlier edition of this docstring called the row "not
combustion", which was wrong twice over: a sixth of it is, and that was never the reason
for the exclusion. The exclusion stands on the method: the
feedstock carbon leaves as urea, priced by the 2B1 ammonia ledger and at application in
3.H, and booking the row as 1A2 fuel would inflate this category by a factor of three and
a half while double-counting against the ammonia accounting.

THE CEMENT ROW IS HERE AND IS ESSENTIALLY NIL. 0.1 MMCFD, because Pakistani kilns burn coal and
petroleum coke. Carried because the cement paper names its kiln fuel as the sector's largest
unestimated component, and a reader following that thread should find the gas part measured at
approximately zero rather than missing.
"""
from pkinv.core.uncertainty import product
from pkinv.core.units import mmcfd_to_TJ

CATEGORY = "Industrial fuel combustion (1A2)"
ITEM = "Natural Gas"

# Printed names for the OCAC product codes, so a subitem reads as English rather than as a
# trade abbreviation.
LIQUID_LABELS = {"FO": "Industrial furnace oil", "HSD": "Industrial diesel",
                 "LDO": "Industrial light diesel oil", "KERO": "Industrial kerosene",
                 "MS": "Industrial gasoline", "HOBC": "Industrial HOBC"}


def gas_TJ(data, stream, year=None, hhv_btu=None):
    """Net terajoules for one stream in the year."""
    hhv = data.p("industry_hhv_btu_per_scf") if hhv_btu is None else hhv_btu
    return mmcfd_to_TJ(data.mmcfd(stream, year), hhv, data.p("industry_gross_to_net"))


def total_TJ(data, year=None, hhv_btu=None):
    return sum(gas_TJ(data, s, year, hhv_btu) for s in data.streams(year))


def liquid_TJ(data, product_code, year=None):
    """Net terajoules of one industrial liquid fuel.

    OCAC reports the Total Industry customer class in tonnes by product; the IPCC net
    calorific values turn that into the energy the factors are defined on.
    """
    _factor_item, ncv_item = data.LIQUID_ITEMS[product_code]
    tonnes = data.liquid_tonnes(product_code, year)
    return tonnes / 1000.0 * data.efv("industry_ncv", ncv_item)


def compute(data, year=None, hhv_btu=None):
    """Return (components, memo). No memo: reported, not excluded.

    Two activity bases, kept apart because they are metered apart: OGRA's sector-wise gas
    table for the gas streams, and OCAC's Total Industry customer-class rows for the
    liquid fuels. Both are national statistics for the same fiscal year.
    """
    ad_u = product(data.p("industry_activity_uncert"),
                   data.pu("industry_hhv_btu_per_scf"),
                   data.pu("industry_gross_to_net"))
    # THE GAS BOUNDARY DECISION (rc19): the OGRA gas streams are inside the
    # post-meter leak base, so their combustion books NET of the leaked share -
    # all three gases; liquids below are untouched. One home for the share:
    # fugitives.post_meter. gas_TJ stays the delivered meter everywhere else.
    from pkinv.sectors.fugitives import post_meter
    net = post_meter.combusted_fraction()
    out = []
    for stream in data.streams(year):
        tj = gas_TJ(data, stream, year, hhv_btu)
        for gas, cat in (("CO2", "industry_combustion_co2"),
                         ("CH4", "industry_combustion_ch4"),
                         ("N2O", "industry_combustion_n2o")):
            row = {"category": CATEGORY, "subitem": "%s gas %s" % (stream, gas), "gas": gas,
                   "emissions_Gg": tj * net * data.efv(cat, ITEM) / 1e6,
                   "uncert_pct": product(ad_u, data.efu(cat, ITEM)),
                   # Wave 6: per-draw gas identity (see uncertainty_all)
                   "net_of_leak": True,
                   "activity_year": year if year is not None else data.year,
                   # A published national statistic for this source and period, not
                   # independently verified. T3 since rc20: the monthly layer rides
                   # PBS QIM production as a declared proxy for this gas (output, not
                   # fuel - the layer's basis says which series).
                   #
                   # S3 since rc47 Wave 4, and the letter's history matters: it said S3
                   # before rc46 while NOTHING placed it below the province (a claimed
                   # allocation that did not exist), then honestly NA. Now the placement
                   # EXISTS - provincial shares spread on built-up within each province,
                   # an administrative basis the cube actually executes - so S3 is earned
                   # the ordinary way rather than asserted.
                   "evidence_class": "E2", "temporal_method": "T3",
                   "spatial_method": "S3", "source_id": "ogra_sorpi_sector_gas"}
            if gas == "CH4":
                # Natural gas is fossil: AR5 30, not the biogenic 28.
                row["fossil"] = True
            out.append(row)

    # --- industrial liquid fuels, from OCAC's Total Industry customer class -------------
    liquid_ad_u = data.p("industry_liquid_activity_uncert")
    for code in data.liquid_products(year):
        factor_item, _ncv_item = data.LIQUID_ITEMS[code]
        tj = liquid_TJ(data, code, year)
        for gas, cat, item in (("CO2", "industry_combustion_co2", factor_item),
                               ("CH4", "industry_combustion_ch4", "Liquid Fuels"),
                               ("N2O", "industry_combustion_n2o", "Liquid Fuels")):
            row = {"category": CATEGORY,
                   "subitem": "%s %s" % (LIQUID_LABELS[code], gas), "gas": gas,
                   "emissions_Gg": tj * data.efv(cat, item) / 1e6,
                   "uncert_pct": product(liquid_ad_u, data.efu(cat, item)),
                   "activity_year": year if year is not None else data.year,
                   # OCAC's customer-class rows are a published national statistic (E2).
                   # The same publication issues monthly editions, so a monthly profile is
                   # reconstructible by differencing (T2) - see industry/monthly.py. The
                   # area pages give a provincial split, an administrative basis (S3).
                   "evidence_class": "E2", "temporal_method": "T2",
                   # S3 since rc47 Wave 4, same story as the gas stream above: the
                   # built-up placement now exists, so the letter is earned.
                   "spatial_method": "S3", "source_id": "ocac_sectoral_total_industry"}
            if gas == "CH4":
                row["fossil"] = True
            out.append(row)
    return out, []
