"""Gas reallocation between urea production and grid power, with both services held fixed.

THE QUESTION. What happens to Pakistan's greenhouse-gas and air-pollutant emissions if a specified
quantity of network gas is moved from two urea plants to grid gas stations, while the same urea is
still applied to the same fields (it is imported instead) and the same electricity is still
delivered (the new gas-fired generation displaces an explicit alternative)?

WHY IT BELONGS NEXT TO THE INVENTORY. The answer depends on records the inventory already holds and
on where they disagree: the fertilizer plants' metered gas against the national calibrated ammonia
factor, the regulator's printed station heat rates against the same stations' printed fuel and
generation. The application crosses those baseline readings (dimension A) with explicit replacement
pathways (dimension B) and propagates parameter uncertainty within each case (dimension C) on
PAIRED draws: baseline and transition share every draw, so the change is computed draw by draw.

WHAT IT IS NOT. It is a counterfactual calculation. It is not evidence that a reallocation
happened, that one caused any observed trend, or that it is operationally feasible on any day: the
records are annual. It infers no concentration, exposure or health effect.

Layout: inputs.py reads the records and the application's tables
(data/shared/parameters/gas_reallocation/); model.py computes one case; build.py runs every case
and writes outputs/pakemis_transition_gas_*.csv; figures.py draws the two threshold figures from
those CSVs. docs/gas_reallocation_application.md is the method and the result.

Usage:  PYTHONPATH=src python3 -m pkinv.applications.gas_reallocation [--draws N] [--year FY]
"""
