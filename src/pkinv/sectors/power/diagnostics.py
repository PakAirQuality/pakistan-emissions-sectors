"""Power's DIAGNOSTIC accessors - the closure channel, kept off the engine.

tests/test_plant_closure.py and tests/test_power_implied_cv.py assert that the
emissions path (engine.py) never imports plant_ledger or implied_cv: the
plant-side energy closure and the implied calorific value are evidence classes
that must not reach the estimate. The report layer still needs them by name
(the national gas ledger quotes the bridge; the structural trajectories price
the implied-CV restatement), so they live here and are reached through
registry.diagnostics("power"), never by importing this module from report/.
"""
from pkinv.sectors.power import combustion


def gas_bridge(data):
    """Plant-summed TJ vs the national TJ row and the implied HHV - the sector's
    own reconciliation, which the national gas ledger quotes in a note."""
    from pkinv.sectors.power import plant_ledger
    return plant_ledger.gas_closure(data)


def coal_energy_restatement(data, year):
    """(restated coal TJ at the implied CV, BOOKED coal TJ) for a fiscal-START year;
    raises where the plant ledger or heat-rate tables do not cover it.

    The second element was Table 3's coal energy until the coal re-base, when the two
    stopped being the same number. It is the BOOKED energy, which is what a caller
    computing a restatement ratio needs: the distance from what the engine books, not from
    an account it no longer books. coal_energy_accounts() below returns all three.
    """
    from pkinv.sectors.power import implied_cv
    return (implied_cv.restated_coal_TJ(data, year),
            combustion.fuel_TJ(data, year)["Coal"])


def coal_energy_accounts(data, year):
    """{booked, heat_rate, table3} coal TJ for a fiscal-START year.

    THE ROUTED ACCESSOR FOR THE COAL-ENERGY FAMILY. The report layer may not import a
    sector module (tests/test_sector_contract.py), and the structural-trajectory pricer
    needs all three accounts to price the two coal axes across the panel - so it asks
    here rather than reaching into power.combustion and power.implied_cv, which is what it
    did for about an hour until the contract test said otherwise.

    `heat_rate` raises for a year the plant ledger and heat-rate tables do not both cover;
    the caller catches and refuses that year. `booked` and `table3` exist for every year
    the fuel table covers.
    """
    out = {"booked": combustion.fuel_TJ(data, year)["Coal"],
           "table3": data.table3_coal_toe(year) * data.p("toe_to_tj")}
    from pkinv.sectors.power import implied_cv
    out["heat_rate"] = implied_cv.restated_coal_TJ(data, year)
    return out


def ke_coverage_series(data):
    """The K-Electric system's fuel CO2 for every fiscal START year held (2015-2023): the
    coverage alternative's own series, from ke_leg. Diagnostic: the emissions path
    (combustion.py, engine.py) never reads it."""
    from pkinv.sectors.power import ke_leg
    return ke_leg.coverage_series(data)

