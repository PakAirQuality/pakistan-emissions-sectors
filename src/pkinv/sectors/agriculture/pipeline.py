"""The agriculture nitrogen bus, named.

manure.compute() is the only producer of the nitrogen pools and soils.compute() the only
greenhouse-gas consumer, so manure must run before soils. Eleven further call sites
(the air-pollutant layer, the nitrogen ledger, the structural-uncertainty runs) re-derive
the same pools by calling manure.compute() again and discarding its components. Routing
them all through one named function gives the bus a definition and makes it greppable.

This ordering and the pools themselves stay inside the sector. Core never learns what
FON_N is; a generic stage runner would buy nothing and would risk reordering the `+=`
accumulation that fixes the published row order of by_category.csv.
"""
from pkinv.sectors.agriculture import manure


def intermediates(data):
    """Shared physical intermediates: the manure components and the nitrogen pools.

    Deliberately NOT cached. timeseries._apply_year() mutates data.livestock / .crops /
    .fertilizer in place and drives one InventoryData across 35 years, so an
    identity-keyed cache would leak 1990 nitrogen into 2024 and silently rewrite every
    row of timeseries_1990_2024.csv.
    """
    components, npools = manure.compute(data)
    return {"manure_components": components, "npools": npools}


def nitrogen_pools(data):
    """Just the pools, for the consumers that do not want manure's components."""
    return intermediates(data)["npools"]
