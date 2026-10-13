"""Captive self-generation - IPCC 1A2.

Industrial plants that generate their own electricity from metered natural gas. This is the
first category in the inventory to put a number inside the roughly 44 Mt industrial-combustion
hole, and it does so on measured activity rather than a proxy: OGRA publishes the gas
delivered to captive power annually, and a 1,105-plant register built from the SNGPL and SSGC
captive fleets, the NEPRA licence list and the OGRA totals reconciles against it to within
0.01 MMCFD.

WHY THIS IS NOT 1A1a, AND WHY IT LIVES IN THE POWER MODULE ANYWAY. A captive plant exists to
serve its own factory, not to sell power, so IPCC reports it under 1A2 Manufacturing
Industries and Construction rather than 1A1a Main Activity Electricity. It sits in this module
for the same reason off-road machinery sits in the transport module: it shares that module's
subject matter and its plant register, while carrying its own IPCC code and its own factor
table. The national rollup sees a category, not a module, so nothing downstream conflates them.

THE FACTOR TABLE IS 2.3, AND FOR NATURAL GAS IT AGREES WITH 2.2. Elsewhere this inventory
documents four cases where taking the wrong one of Chapter 2's parallel tables leaves CO2
exactly right and moves the trace gases by an order of magnitude. This is not a fifth. For
natural gas, Table 2.3 and Table 2.2 carry the same CO2, CH4 and N2O; only Table 2.5's
residential CH4 of 5 differs from the industrial and utility value of 1. That is the boundary
of the finding rather than a counterexample to it: the trap bites where combustion conditions
genuinely differ, and an industrial gas engine burns closely enough to a utility boiler that
IPCC gives them the same numbers. The factors are still cited to 2.3, because the citation is
what an auditor checks and being right by luck is not being right.

VOLUME, NOT MASS, WHICH IS WHERE THE UNCERTAINTY IS. OGRA reports MMCFD - a volume - while
IPCC factors are per terajoule on a NET calorific basis. The conversion needs a heating value,
and nothing read here pins it: pipeline gas runs roughly 900 to 1,000 Btu/scf depending on
field and RLNG share. At 1,000 the category is 5.55 Mt and at 900 it is 4.99, so that single
assumption spans more than half a megatonne. Both are reported, as the cement sector reports
both clinker ratios, rather than one being chosen quietly. Everything else in the chain is
metered gas or an IPCC default.

WHAT THIS IS NOT. It is captive GAS only. Captive plants burning furnace oil, diesel, coal or
bagasse are in the register but have no metered fuel series, and the rest of 1A2 - industrial
process heat, boilers, kilns - is not here at all (and since rc46 Wave 2 the industry
module estimates brick and cement COAL as reference streams). This category remains a floor on its own 1A2 slice, not an
estimate of it, and the completeness table says so.
"""
from pkinv.core.uncertainty import product
from pkinv.core.units import mmcfd_to_TJ

CATEGORY = "Captive gas self-generation (1A2)"
ITEM = "Natural Gas"


def gas_TJ(data, hhv_btu=None, year=None):
    """Net terajoules of captive gas in the reported year.

    hhv_btu overrides the gross heating value for the sensitivity pass; None uses the
    reported 1,000 Btu/scf.
    """
    mmcfd = data.captive_total_mmcfd(year)
    hhv = data.p("captive_hhv_btu_per_scf") if hhv_btu is None else hhv_btu
    return mmcfd_to_TJ(mmcfd, hhv, data.p("captive_gross_to_net"))


def compute(data, hhv_btu=None, year=None):
    """year is the CAPTIVE panel's own key, which is fiscal-END (OGRA convention: 2024 =
    FY2023-24), while the grid stream this sector leads with is fiscal-START. The engine
    does the +1 conversion so no caller has to know two conventions live in one module;
    passing a grid-convention year straight through would shift captive history by a year,
    silently, in a direction nothing bounds. Default None keeps the pinned reference
    (power_params.captive_year), so the published FY2023-24 build is untouched.
    """
    """Return (components, memo). No memo: this category is reported, not excluded."""
    tj = gas_TJ(data, hhv_btu, year)
    # Activity uncertainty is the metered supply combined with the heating-value assumption,
    # because the conversion to energy is as much a part of the activity figure as the volume.
    ad_u = product(data.p("captive_activity_uncert"),
                   data.pu("captive_hhv_btu_per_scf"),
                   data.pu("captive_gross_to_net"))
    # THE GAS BOUNDARY DECISION (rc19): captive gas is inside the post-meter
    # leak base, so its combustion books NET of the leaked share - all three
    # gases; the share's one home is fugitives.post_meter. gas_TJ stays the
    # delivered meter for every non-emissions consumer.
    from pkinv.sectors.fugitives import post_meter
    net = post_meter.combusted_fraction()
    out = []
    for gas, cat in (("CO2", "captive_combustion_co2"),
                     ("CH4", "captive_combustion_ch4"),
                     ("N2O", "captive_combustion_n2o")):
        row = {"category": CATEGORY, "subitem": "Captive natural gas %s" % gas, "gas": gas,
               "emissions_Gg": tj * net * data.efv(cat, ITEM) / 1e6,
               "uncert_pct": product(ad_u, data.efu(cat, ITEM)),
               # Wave 6: marks this row as netted by the post-meter leak share so
               # the national MC can hold the physical-atmosphere identity PER
               # DRAW (uncertainty_all.gas_coupling_scalers)
               "net_of_leak": True}
        if gas == "CH4":
            # Natural gas is fossil, so CH4 takes AR5 30 rather than the biogenic 28, as in
            # power, road, rail and residential.
            row["fossil"] = True
        out.append(row)
    return out, []
