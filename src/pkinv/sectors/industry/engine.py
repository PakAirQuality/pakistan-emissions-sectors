"""Industrial fuel combustion as a registered sector (IPCC 1A2).

Gas, liquids and - since rc46 Wave 2 - the two solid-fuel streams (brick-kiln and
cement-sector coal) from the HDIP coal-by-consumer series, activated through the
industrial_solid_fuels_1a2 gate. The old self-description "a floor on 1A2, not an estimate
of it" is retired with the activation: the sector now estimates every 1A2 fuel family the
national statistics publish, and what remains outside is named (petcoke on its trade lane,
captive coal inside the power module's captive category and the brick residual - see
solid_fuels.py's docstring for the exhaustive-supply argument). Captive self-generation is also 1A2 and is estimated in the power
module, where it shares that module's plant register - the same arrangement off-road machinery
has in transport. The national rollup sees categories, not modules, so the two 1A2 categories
sum correctly without either module knowing about the other.
"""
from pkinv.core import period
from pkinv.core.components import enrich_co2e
from pkinv.sectors.industry import combustion, downscale, solid_fuels
from pkinv.sectors.industry.data import IndustryData, YEAR

NAME = "industry"
CATEGORIES = (combustion.CATEGORY,)
GASES = ("CO2", "CH4", "N2O")
HAS_SINKS = False
YEAR = YEAR

# The reference PERIOD, not just a year. See core.period: this sector's YEAR is the calendar
# year its reporting period CLOSES in, a convention that was implicit until it collided
# with the opposite one in a neighbouring sector.
YEAR_CONVENTION = 'fiscal-end'
PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

MC_DISTRIBUTION = "lognormal"

load_data = IndustryData
proxy_for = downscale.proxy_for
load_shares = downscale.load_shares


def build_components(data, year=None, hhv_btu=None):
    components, _memo = combustion.compute(data, year, hhv_btu)
    solid, _solid_memo = solid_fuels.compute(data, year)
    components = components + solid
    # combustion.py sets the three evidence axes per stream, which are genuinely different
    # between the metered gas rows and the OCAC liquid rows. It does not set the period kind,
    # because every row here is a flow accumulated over the period and there was nothing to
    # distinguish - which stopped being a reason to omit it when the key became required.
    for row in components:
        row.setdefault("activity_period_kind", "span")
    return enrich_co2e(components)


def memo_items(data, year=None):
    """None. Nothing here is excluded from the national total."""
    return []


# --- Declared accessors (rc34). The report layer reaches these BY NAME through
# the registry instead of importing sector internals; each wraps one module of
# this sector and nothing here recomputes anything.


def gas_activity(data):
    """Live MMCFD throughput per gas-consuming stream, for the national gas ledger."""
    return {"General industry": data.mmcfd("General Industry", YEAR),
            "Cement": data.mmcfd("Cement", YEAR)}


def brick_kiln_screen_Mt():
    """{fiscal_end_year: Mt CO2e} of the PEY Table 4.4 brick-kiln coal screening,
    priced on each year's OWN coal - the arithmetic the structural-trajectory
    report used to do itself from four scraped constants."""
    from pkinv.core.gwp import GWP
    from pkinv.sectors.industry import kiln_screening
    _latest, rows = kiln_screening.latest_row()
    out = {}
    for r in rows:
        tj = float(r["coal_tonnes"]) / 1000.0 * kiln_screening.COAL_NCV_TJ_GG
        out[int(r["fiscal_year"])] = (
            tj * kiln_screening.COAL_CO2_KG_TJ / 1e9
            + tj * kiln_screening.COAL_CH4_KG_TJ / 1e9 * GWP["AR5"]["CH4_fossil"]
            + tj * kiln_screening.COAL_N2O_KG_TJ / 1e9 * GWP["AR5"]["N2O"])
    return out


def bagasse_ceiling_Mt(cane_t):
    """The all-cane bagasse CEILING (CH4 + N2O, Mt CO2e) for a cane crop in tonnes."""
    from pkinv.core.gwp import GWP
    from pkinv.sectors.industry import solid_screenings
    bagasse_gg = cane_t * solid_screenings.BAGASSE_T_PER_T_CANE / 1000.0
    tj = bagasse_gg * solid_screenings.BAGASSE_NCV_TJ_GG
    return (tj * solid_screenings.BAGASSE_CH4_KG_TJ / 1e9 * GWP["AR5"]["CH4"]
            + tj * solid_screenings.BAGASSE_N2O_KG_TJ / 1e9 * GWP["AR5"]["N2O"])
