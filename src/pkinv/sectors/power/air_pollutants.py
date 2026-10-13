"""Air-pollutant co-emissions from electricity generation - UNCONTROLLED, and that word carries
the whole caveat.

Mass only. Air pollutants are never converted to CO2e and never enter a greenhouse-gas total,
as in the residential, transport, waste and aviation layers.

ON THE FUEL, NOT ON GENERATION. Every factor here is applied to the same terajoules that the
greenhouse-gas layer burns, because the two inventories describing the same combustion should
describe the same activity. That is what makes the cross-sector comparison in the national
manuscript - household biomass against road transport against this sector - a statement about
how fuels burn rather than an artefact of three different activity bases.

WHY THIS SECTOR WAS NOT ESTIMATED BEFORE, AND WHAT ACTUALLY CHANGED. The completeness table
recorded this category as blocked on emission factors. Re-deriving from AP-42 showed that was
the wrong diagnosis. AP-42 does not publish a coal SO2 factor: Table 1.1-3 publishes 38S,
where S is the sulfur weight percent of the coal burned. Table 1.3-1 publishes 157S for No. 6
oil. Table 1.1-4 publishes PM as 10A, a function of ash. The factors were never missing - the
FUEL ANALYSIS was, and NEPRA publishes none. So the blocker was fuel quality all along, and
naming it that way is most of this module's value.

THREE THINGS THIS IS A BOUND ON, NOT AN ESTIMATE OF.

First, sulfur. Published Thar lignite sulfur spans 0.26 to 2.90 percent, a factor of eleven,
and the imported bituminous burned at Sahiwal, Port Qasim and Hub is a different coal that SIR
Table 3 does not separate. The central value is the geometric mean of the published range and
the uncertainty is read off the range, which is exactly how sectors/fugitives/leakage.py
handles IPCC's published factor ranges; range_uncert_pct is imported from there rather than
reimplemented, so the two sectors cannot drift apart on the convention.

Second, and larger: THESE ARE UNCONTROLLED FACTORS. AP-42's uncontrolled rows describe what
leaves the furnace, not what leaves the stack. Pakistan's supercritical coal units were built
with electrostatic precipitators, and the newer ones with flue-gas desulphurisation, which
remove most of the particulate and much of the sulfur. No national dataset records which
control is fitted where or how it performs, so applying a removal efficiency would mean
inventing one. The uncontrolled figure is therefore reported as what it is - an UNCONTROLLED
SCREENING SCENARIO of what the fleet emits with no control devices credited - and the
estimate of what it does emit is left NE. It is NOT a mathematical maximum: AP-42 defaults
are typical uncontrolled rates, not worst cases, so a plant could exceed a row of this
scenario even uncontrolled. A number labelled as a screening scenario is useful; the same
number labelled as an estimate (or as a bound it is not) would not be.

Third, combustor type for gas - RESOLVED BY THE LEDGER, WITH A RESIDUAL. AP-42 Chapter 1.4 is
an EXTERNAL COMBUSTION chapter - boilers - while much of Pakistan's gas fleet is
combined-cycle, which is Chapter 3.1, and turbine NOx differs from boiler NOx (3.2E-01 versus
280/1,020 = 2.7E-01 lb/MMBtu, both uncontrolled, both rated A). SIR Table 3 reports fuel
without plant type, but the plant ledger carries heat rates, and a plant at or below 9,000
kJ/kWh net can only be a combined cycle. plant_ledger.gas_technology_split classifies the
grid gas energy that way - turbine, boiler, or unresolved - and the grid gas NOx factor here
is the energy-weighted blend, with the unresolved share KEPT ON THE BOILER FACTOR and
published as the residual rather than assigned. Only NOx is split: the CO factors are
numerically indistinguishable across the two chapters (84/1,020 = 8.2E-02 versus 8.2E-02
lb/MMBtu), and sulfur passes through to SO2 regardless of how the gas is burned. Captive gas
stays on the boiler chapter: those units are engines and small turbines that Chapter 3.2
would describe, but no dataset splits the captive fleet, so its NOx keeps the weakest-row
caveat that the grid row has now shed.

PM2.5 FROM THE SIZE DISTRIBUTION, NOT A LOOKUP. AP-42 Table 1.1-4 gives filterable PM and
PM-10 for coal but no PM2.5. Table 1.1-6 publishes the cumulative particle-size distribution
for dry-bottom pulverised-coal boilers, uncontrolled: 6 percent of filterable mass is at or
below 2.5 microns, a cumulative factor of 0.6A lb/ton, which the table rates C - below the
A of the mass factor it scales, as a derived number should be. The same table puts 23
percent at or below 10 microns, 2.3A, exactly the PM-10 factor Table 1.1-4 already carries,
which is the internal consistency check on the transcription. Gas PM2.5 equals gas PM
because AP-42's note says all gas particulate is under a micron. Oil PM (all sizes) remains
out: this module has never carried an oil particulate factor, and oil is under two percent
of the sector's fuel. Reporting the gas figure alone would have put about 1 kt against
residential biomass at 461 and read as power being negligible for fine particulate, which
uncontrolled coal is not - the coal row is what makes the number honest.

THE COAL FAMILY IS SPLIT BY RANK SINCE rc10, because AP-42 is. Section 1.1 is BITUMINOUS
and subbituminous coal; 79 percent of this fleet's coal energy is Thar LIGNITE
(coal_lignite_share, generation-weighted from the plant fuel ledger), which AP-42 covers in
its own Section 1.7 with different factors on every axis: SOx 30S against 38S, and the
sulfur-retention physics differ (the 1.7-1 footnote scales the factor 22S-34S with ash
sodium, unknown here, so the table's own 30S default is carried); PM 6.5A against 10A; and
the size distribution is lignite's own Table 1.7-7 (35 percent of filterable at or below 10
microns, 10 percent at 2.5) rather than 1.1-6's 23/6. Firing configuration is carried as a
DECLARED ASSUMPTION: pulverized dry-bottom TANGENTIAL (SCC 1-01-003-02), the configuration
whose NOx factor 1.7-1 rates A and whose PM matches Table 1.7-7's own basis - no Pakistani
document read here states the Thar boilers' firing arrangement. Lignite CO is ND for
tangential in 1.7-1 and is therefore ABSENT, not zero-filled - the same rule that kept the
placeholder bagasse factors out. The 3 unknown-origin ledger plants ride the bituminous side
via the share's own construction (0.79 is the midpoint of Lucky-as-imported/Lucky-as-Thar).
Per-TJ conversion uses each rank's own IPCC NCV (plant_ledger.NCV_LIGNITE 11.9 against 25.8)
- the point the GHG layer already makes: rank factors differ modestly per TJ and enormously
per tonne. The Thar sulfur and ash ranges apply to the LIGNITE rows by construction; the
bituminous rows keep the same ranges as a DECLARED PROXY because no imported-coal
consignment analysis is held (power-fuel-analysis in the gap register) - typically imported
bituminous is lower-sulfur, so if anything the bituminous side of the bound is generous.

BAGASSE IS ESTIMATED SINCE rc10, from AP-42 Section 1.8 (bagasse-fired boilers, sugar
mills) on the same fuel energy the greenhouse-gas layer burns (bagasse.fuel_TJ). The
section publishes uncontrolled filterable PM (15.6 lb/ton wet bagasse, rated C) and NOx
(1.2, C) and NO SOx or CO factor - bagasse sulfur is characteristically negligible and the
section says so in prose rather than printing a factor - so this stream carries exactly two
pollutant rows and the absence of the others is the section's, not an oversight. Conversion
uses the section's own stated heating value (7.0 MMBtu per wet ton), so the factor stays on
the basis it was measured on. The old placeholder story: the source workbook for this
sector's plant register carries four bagasse factors it flags itself as unsourced
placeholders, all zero - a zero that means "not looked up" is worse than an absence, so
those never entered and the category was NE until the section itself was fetched
(sources/AP42/AP42_1.8_bagasse.pdf).
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.uncertainty import product
from pkinv.core.units import TJ_PER_MMBTU
from pkinv.sectors.fugitives.leakage import range_uncert_pct
from pkinv.sectors.power import bagasse, captive, combustion, plant_ledger
from pkinv.core import period
from pkinv.sectors.power import engine
from pkinv.paths import DATA

def _sfx(year):
    """The output filename's period suffix - "fy2023_24", not a bare year (rc15:
    this sector keys on the fiscal-START year, so _2023 named the same twelve
    months as the _2024 files beside it)."""
    return period.file_suffix(year, engine.YEAR_CONVENTION)



CATEGORY = combustion.CATEGORY

# ---------------------------------------------------------------------------
# AP-42 factors, per unit of FUEL, transcribed with their table and rating.
#   coal: lb per short ton, AP-42 Table 1.1-3 (SO2/NOx/CO) and 1.1-4 (PM), PC-fired dry
#         bottom wall-fired, uncontrolled. "S" and "A" mark sulfur- and ash-scaled factors.
#   oil:  lb per 10^3 US gallons, AP-42 Table 1.3-1, No. 6 oil, normal firing, >100 MMBtu/hr.
#   gas:  lb per 10^6 standard cubic feet, AP-42 Table 1.4-1 (NOx/CO) and 1.4-2 (the rest).
# ---------------------------------------------------------------------------
BITUMINOUS_LB_PER_TON = {    # value, scaled-by, AP-42 table, rating (Section 1.1)
    "SO2":   (38.0, "sulfur", "1.1-3", "A"),
    # 22, NOT the 21.7 shipped through rc49: the held 9/98 chapter's wall-fired
    # pre-NSPS row prints 22 and no held vintage prints 21.7 - a transcription
    # defect fixed against sources/AP42/AP42_1.1_bituminous_coal.pdf (p. 1.1-16)
    "NOx":   (22.0, None,     "1.1-3", "A"),
    "CO":    (0.5,  None,     "1.1-3", "A"),
    "PM":    (10.0, "ash",    "1.1-4", "A"),
    "PM10":  (2.3,  "ash",    "1.1-4", "E"),
    "PM2.5": (0.6,  "ash",    "1.1-6", "C"),  # 6% of filterable at/below 2.5 um, cumulative
}
# Section 1.7, pulverized dry-bottom TANGENTIAL (SCC 1-01-003-02) - a declared assumption,
# see the module docstring. CO is ND for this configuration and is absent, not zero.
# 30S is Table 1.7-1's own default for unknown ash-sodium (22S high-Na, 34S low-Na).
# PM10/PM2.5 are Table 1.7-7's cumulative distribution on ITS OWN tangential basis:
# 2.3A at 10 um and 0.66A at 2.5 um of the 6.5A filterable mass (35% and 10%).
LIGNITE_LB_PER_TON = {
    "SO2":   (30.0, "sulfur", "1.7-1", "C"),
    "NOx":   (7.1,  None,     "1.7-1", "A"),
    "PM":    (6.5,  "ash",    "1.7-4", "E"),
    "PM10":  (2.3,  "ash",    "1.7-7", "E"),
    "PM2.5": (0.66, "ash",    "1.7-7", "E"),
}
# Section 1.8, bagasse-fired boilers: lb per ton of WET as-fired bagasse (~50% moisture),
# uncontrolled. The section publishes no SOx or CO factor (bagasse sulfur negligible, in
# prose), so exactly these two rows exist. Converted on the section's own 7.0 MMBtu/ton.
BAGASSE_LB_PER_WET_TON = {
    "PM":    (15.6, None, "1.8-1", "C"),
    "NOx":   (1.2,  None, "1.8-1", "C"),
}
_BAGASSE_MMBTU_PER_TON = 7.0
OIL_LB_PER_KGAL = {
    "SO2":   (157.0, "sulfur", "1.3-1", "A"),
    "NOx":   (47.0,  None,     "1.3-1", "A"),
    "CO":    (5.0,   None,     "1.3-1", "A"),
}
GAS_LB_PER_MMSCF = {
    "SO2":   (0.6,   None, "1.4-2", "A"),
    "NOx":   (280.0, None, "1.4-1", "A"),   # large wall-fired boiler, uncontrolled pre-NSPS
    "CO":    (84.0,  None, "1.4-1", "B"),
    "PM":    (7.6,   None, "1.4-2", "D"),   # total; AP-42 note c says all of it is <1 micron
    "PM10":  (7.6,   None, "1.4-2", "D"),
    "PM2.5": (7.6,   None, "1.4-2", "D"),   # = PM, by the same note c
    "VOC":   (5.5,   None, "1.4-2", "C"),
}
# AP-42 Table 3.1-1, natural-gas-fired stationary turbine, uncontrolled, lb/MMBtu. Applied
# to the ledger-classified turbine share of grid gas; see gas_technology_split for why the
# unresolved share stays on the 1.4-1 boiler factor above.
GAS_TURBINE_NOX_LB_PER_MMBTU = (0.32, "3.1-1", "A")

# ---------------------------------------------------------------------------
# THE CONTROLLED-CASE SCENARIO END (air absence-screening round). The pair
# uncontrolled/controlled_case are the two ends the fleet lies between GIVEN the
# control fleet is unknown; NEITHER is an estimate, and the NEPRA acquisition
# (gap air-power-controlled) is what would replace the pair with one. Every value
# below is a HELD-table row, never an invented removal rate:
#   coal NOx: Table 1.1-3's "Pre-NSPS with low-NOx burner" wall-fired row (11, A);
#   lignite NOx: Table 1.7-3's Subpart Da tangential overfire-air row (6.0, C) -
#     the post-1978 analog for a 2019+ fleet;
#   coal PM/PM10/PM2.5: Table 1.1-6's ESP columns (0.08A/0.054A/0.024A, D - the
#     table's own 99.2% estimated ESP efficiency);
#   lignite PM: Table 1.7-5's LARGEST high-efficiency controlled row (Subpart D
#     baghouse 0.08A, C) as the declared proxy for the fleet's ESPs - 1.7-5 prints
#     no PC-ESP row, and taking the largest published row keeps the credit modest;
#   lignite PM2.5: 1.1-6's ESP fine fraction (0.024/0.08 = 30%) applied to that
#     0.08A - a declared cross-chapter proxy, rated E here for that reason;
#   SO2 (both ranks): the chapters publish no controlled SO2 factor ROW; Tables
#     1.1-1/1.7-2 publish the wet lime/limestone scrubber efficiency RANGE 80-95+%,
#     carried as the RESIDUAL fraction [0.05, 0.20], geometric-mean centre, the
#     same range convention every fuel-quality span here uses;
#   CO: carried unchanged - combustion NOx controls do not credit CO (1.7-3's
#     wall-fired row shows the trade running the other way);
#   gas: the turbine share takes 3.1-1's water-steam injection row (0.13, A); the
#     boiler and unresolved shares KEEP the uncontrolled 1.4-1 factor because the
#     1.4 chapter is not held and no controlled boiler row can be cited - which
#     keeps the controlled end conservative;
#   oil, bagasse, captive gas: unchanged, declared (no held controlled rows; oil
#     is under two percent of the fuel and bagasse controls are undocumented).
BITUMINOUS_CONTROLLED_LB_PER_TON = {
    "NOx":   (11.0,  None,  "1.1-3", "A"),   # pre-NSPS wall-fired with LNB
    "CO":    (0.5,   None,  "1.1-3", "A"),   # unchanged; no controlled CO row
    "PM":    (0.08,  "ash", "1.1-6", "D"),   # ESP column, TOTAL
    "PM10":  (0.054, "ash", "1.1-6", "D"),
    "PM2.5": (0.024, "ash", "1.1-6", "D"),
}
LIGNITE_CONTROLLED_LB_PER_TON = {
    "NOx":   (6.0,   None,  "1.7-3", "C"),   # Subpart Da tangential, overfire air
    "PM":    (0.08,  "ash", "1.7-5", "C"),   # Subpart D baghouse, largest hi-eff row
    "PM2.5": (0.024, "ash", "1.7-5/1.1-6", "E"),  # 30% ESP fine fraction, proxy
}
# SO2 under wet lime/limestone FGD: the RESIDUAL fraction range the chapters print
# (efficiency 80-95+% in 1.1-1 and 1.7-2; the "+" is not priced - capping at 95
# keeps the credit inside what the table states).
FGD_RESIDUAL_RANGE = (0.05, 0.20)
GAS_TURBINE_NOX_CONTROLLED_LB_PER_MMBTU = (0.13, "3.1-1", "A")  # water-steam injection
CONTROLLED_BASIS = (
    "COAL-CONTROL SCENARIO, OIL REMOVAL UNCHANGED - every unit credited with the "
    "named held-table control (LNB/OFA for NOx, ESP-class collection for PM, wet "
    "lime/limestone FGD residual 0.05-0.20 for SO2, water-steam injection for the "
    "turbine share); the other end of the pair the fleet lies between, not an "
    "estimate and not a minimum - gas boilers, oil, bagasse and captive keep "
    "uncontrolled factors because no held chapter prices their controls. "
    "ITS NAME WAS WRONG UNTIL rc60. It was called the `controlled_case`, and for "
    "SO2 that reads as 'the fleet with its controls credited' when what it "
    "actually credits is COAL FGD and nothing else: oil takes the same factor at "
    "both ends of the pair, so for an oil-fired station the two ends coincide. "
    "That coincidence was once offered as a reason to admit oil, which it is not - "
    "it is a property of this scenario, not of the plants. AP-42 Section 1.3 "
    "records scrubbing on oil-fired boilers at 90 to 95 percent SO2 removal, so "
    "'no held chapter prices their controls' was itself untrue for oil; what is "
    "true is that no record of these stations' equipment is held. The scenario id "
    "is unchanged so the released series stays comparable; the name it goes by is "
    "now the one that describes it.")

# Unit conversions. Exact where the definition is exact.
_KG_PER_LB = 0.45359237
_TONNE_PER_SHORT_TON = 0.90718474
_TJ_PER_MMBTU = TJ_PER_MMBTU      # shared; see pkinv.core.units for why it is not restated
# AP-42 Table 1.4 factors are stated at an average 1,020 Btu/scf and the tables say to divide
# by 1,020 to reach lb/MMBtu. Using that constant keeps the factor on the basis it was
# measured on; the sector's own heating value belongs to the activity, not to the factor.
_AP42_GAS_BTU_PER_SCF = 1020.0
# IPCC 2006 Vol 2 Ch 1 Table 1.2 net calorific values, TJ/Gg. The coal ranks come from
# plant_ledger so the air layer and the blend arithmetic cannot drift apart.
_NCV = {"Coal": plant_ledger.NCV_BITUMINOUS, "Lignite": plant_ledger.NCV_LIGNITE,
        "Residual Fuel Oil": 40.4}
# Residual fuel oil density, kg per US gallon at 15 C (about 0.99 kg/L).
_KG_PER_GAL_RFO = 3.75


def _quality(data, fuel, prop):
    """(central, uncert_pct) for a fuel-quality range, geometric mean as the centre."""
    lo, hi = data.fuel_quality(fuel, prop)
    if lo == hi:
        return lo, 0.0
    return (lo * hi) ** 0.5, range_uncert_pct(lo, hi)


def _coal_kg_per_TJ(value, scaled_by, data, rank="Coal", quality_fuel="Coal"):
    """lb per short ton -> kg per TJ, scaling by sulfur or ash where AP-42 says to.

    rank picks the NCV (lignite tonnes carry half the energy of bituminous tonnes, so
    the same lb/ton means a very different kg/TJ); quality_fuel picks the sulfur/ash
    rows in data/power_fuel_quality.csv.
    """
    mult, mult_u = 1.0, 0.0
    if scaled_by:
        mult, mult_u = _quality(data, quality_fuel, scaled_by + "_pct")
    kg_per_tonne = value * mult * _KG_PER_LB / _TONNE_PER_SHORT_TON
    return kg_per_tonne / _NCV[rank] * 1000.0, mult_u


def _oil_kg_per_TJ(value, scaled_by, data):
    mult, mult_u = 1.0, 0.0
    if scaled_by:
        mult, mult_u = _quality(data, "Residual Fuel Oil", scaled_by + "_pct")
    kg_per_kgal = value * mult * _KG_PER_LB
    tj_per_kgal = 1000.0 * _KG_PER_GAL_RFO / 1e6 * _NCV["Residual Fuel Oil"]
    return kg_per_kgal / tj_per_kgal, mult_u


def _gas_kg_per_TJ(value):
    return value / _AP42_GAS_BTU_PER_SCF * _KG_PER_LB / _TJ_PER_MMBTU, 0.0


# --- the admitted remainder -------------------------------------------------------------
# rc60. Oil and diesel SO2 is estimated per station on a reviewed register
# (data/activity/power/power_so2_admission.csv), so this screening no longer brackets the
# whole fleet for those two cells - it brackets what is left of it.
#
# IT IS APPLIED HERE, INSIDE compute(), AND NOT IN THE CONSUMER. It was written in the panel
# first, and that would have shipped TWO POWER GEOGRAPHIES: the nine-year panel would have
# carried the narrowed number while outputs/power_air_pollutants_fy2023_24.csv - which
# air_spatial_sectors.py reads to place power on the map - carried the un-narrowed one. Every
# consumer of this function now gets the same answer, which is the only way the map and the
# table can agree.
ADMITTED_SO2_FUELS = {"Furnace Oil": "RFO", "Diesel Oil": "HSD"}
ADMISSION_REGISTER = asset_path(DATA, "activity", "power", "power_so2_admission.csv")
_ADMITTED_NCV = {"RFO": 40.4, "HSD": 43.0}
_admitted_cache = None


def _admitted_cppa_kt():
    """{(fiscal START year, fuel): kt} of admitted CPPA-side fuel. K-Electric is excluded.

    The screening runs on the national fuel table, which the boundary audit behind
    data/power_params.csv activity_uncert_fo establishes covers the CPPA side only. Taking
    K-Electric's admitted mass out of it would open a hole rather than close one: those
    stations were never inside this universe.
    """
    global _admitted_cache
    if _admitted_cache is None:
        _admitted_cache = {}
        for row in _activity_rows(ADMISSION_REGISTER, comments=True):
            if (row["disposition"] != "provisional_estimate"
                    or row["system"] == "K-Electric"):
                continue
            key = (int(row["fiscal_start_year"]), row["fuel"])
            _admitted_cache[key] = (_admitted_cache.get(key, 0.0)
                                    + float(row["fuel_mass_kt"]))
    return _admitted_cache


def admitted_remainder_fraction(data, year, screening_fuel):
    """(fraction of this fuel still unestimated, why) - (1.0, "") where none is admitted.

    EXACT, NOT APPROXIMATE. The screening's SO2 is linear in fuel mass, so applying the
    unadmitted fraction gives the same sulfur, the same retention and the same scenario on the
    fuel that is left - which is the remainder itself rather than a model of it.
    """
    fuel = ADMITTED_SO2_FUELS[screening_fuel]
    admitted = _admitted_cppa_kt().get((year, fuel), 0.0)
    if admitted <= 0:
        return 1.0, ""
    toe = data.fuel_for(year).get(screening_fuel, 0.0)
    national_kt = toe * data.p("toe_to_tj") / _ADMITTED_NCV[fuel]
    if national_kt <= 0:
        return 1.0, ""
    return max(0.0, 1.0 - admitted / national_kt), (
        "REMAINDER ONLY: %.1f of %.1f kt of CPPA-side %s is estimated at plant grain "
        "(data/activity/power/power_so2_admission.csv); this row screens the %.1f kt left"
        % (admitted, national_kt, screening_fuel, max(0.0, national_kt - admitted)))


def compute(data, year=None, scenario="uncontrolled", include_captive=False):
    """Air-pollutant emissions, kilotonnes, by fuel and pollutant, for ONE end of the
    screening pair: "uncontrolled" (the historical default - AP-42 defaults with no
    control devices credited) or "controlled_case" (every unit credited with the
    named held-table control; see CONTROLLED_BASIS). Neither is an estimate."""
    if scenario not in ("uncontrolled", "controlled_case"):
        raise ValueError("scenario must be uncontrolled or controlled_case, not %r"
                         % scenario)
    controlled = scenario == "controlled_case"
    # SO2 under FGD: the residual fraction range, geometric-mean centre - the same
    # range convention the fuel-quality spans use (range_uncert_pct)
    lo, hi = FGD_RESIDUAL_RANGE
    fgd_residual = (lo * hi) ** 0.5
    fgd_u = range_uncert_pct(lo, hi)
    tj = combustion.fuel_TJ(data, year)
    act_u = data.p("activity_uncert")
    rows = []

    def emit(stream, fuel_label, pollutant, kg_per_tj, factor_u, table, rating, energy,
             detail="", extra_u=None):
        rows.append({
            "category": stream, "fuel": fuel_label, "fuel_detail": detail,
            "pollutant": pollutant,
            "emissions_kt": energy * kg_per_tj / 1e6,
            "uncert_pct": product(act_u, factor_u, extra_u),
            "ap42_table": table, "ap42_rating": rating})

    for fuel, energy in sorted(tj.items()):
        if fuel == "Coal":
            # split by rank: 79% of the coal energy is Thar lignite on Section 1.7
            # factors, the rest imported bituminous (plus the ledger's unresolved
            # residual, by the share's own construction) on Section 1.1
            # year-aware: the FY2023-24 parameter at the reference, the ledger mid from
            # FY2019-20, zero before the Thar fleet existed - the same three-regime rule
            # the GHG layer burns (applying 0.79 lignite to FY2015-16 would be the very
            # defect the module docstring warns about, pointed backwards)
            share = combustion.coal_lignite_share(data, year)
            share_u = data.pu("coal_lignite_share")
            lignite_set = LIGNITE_CONTROLLED_LB_PER_TON if controlled else LIGNITE_LB_PER_TON
            bituminous_set = (BITUMINOUS_CONTROLLED_LB_PER_TON if controlled
                              else BITUMINOUS_LB_PER_TON)
            for detail, portion, table_set, rank, qfuel in (
                    ("Thar lignite (share %.2f, SCC 1-01-003-02 assumed)" % share,
                     share, lignite_set, "Lignite", "Lignite"),
                    ("imported bituminous incl. unresolved residual (share %.2f; "
                     "Thar quality ranges as declared proxy)" % (1.0 - share),
                     1.0 - share, bituminous_set, "Coal", "Coal")):
                for pol, (v, scaled, tbl, rate) in sorted(table_set.items()):
                    k, u = _coal_kg_per_TJ(v, scaled, data, rank, qfuel)
                    emit(CATEGORY, fuel, pol, k, u, tbl, rate, energy * portion,
                         detail=detail, extra_u=share_u)
                if controlled:
                    # SO2 keeps its rank's uncontrolled factor times the FGD
                    # residual: the chapters publish the efficiency RANGE, not a
                    # controlled factor row (1.1-1 / 1.7-2, wet lime/limestone)
                    base = LIGNITE_LB_PER_TON if rank == "Lignite" else BITUMINOUS_LB_PER_TON
                    v, scaled, tbl, rate = base["SO2"]
                    k, u = _coal_kg_per_TJ(v, scaled, data, rank, qfuel)
                    emit(CATEGORY, fuel, "SO2", k * fgd_residual,
                         product(u, fgd_u), tbl + "/1.1-1 FGD residual", rate + "C",
                         energy * portion, detail=detail, extra_u=share_u)
        elif fuel in ("Furnace Oil", "Diesel Oil"):
            for pol, (v, scaled, tbl, rate) in sorted(OIL_LB_PER_KGAL.items()):
                k, u = _oil_kg_per_TJ(v, scaled, data)
                emit(CATEGORY, fuel, pol, k, u, tbl, rate, energy)
        elif fuel == "Gas":
            split = plant_ledger.gas_technology_split(data, year)
            for pol, (v, _s, tbl, rate) in sorted(GAS_LB_PER_MMSCF.items()):
                k, u = _gas_kg_per_TJ(v)
                if pol == "NOx" and split["turbine_share"]:
                    tv, ttbl, trate = (GAS_TURBINE_NOX_CONTROLLED_LB_PER_MMBTU
                                       if controlled else GAS_TURBINE_NOX_LB_PER_MMBTU)
                    k_turbine = tv * _KG_PER_LB / _TJ_PER_MMBTU
                    k = (split["turbine_share"] * k_turbine
                         + (1.0 - split["turbine_share"]) * k)
                    tbl, rate = tbl + "/" + ttbl, rate if rate == trate else rate + trate
                emit(CATEGORY, fuel, pol, k, u, tbl, rate, energy)

    # Grid bagasse cogeneration: Section 1.8 on the same fuel energy the GHG layer
    # burns. Two rows only - the section publishes no SOx or CO factor.
    bag_tj = bagasse.fuel_TJ(data, year=year)
    if bag_tj:
        bag_u = product(data.p("activity_uncert"),
                        data.pu("bagasse_heat_rate_kj_per_kwh"))
        for pol, (v, _s, tbl, rate) in sorted(BAGASSE_LB_PER_WET_TON.items()):
            k = v / _BAGASSE_MMBTU_PER_TON * _KG_PER_LB / _TJ_PER_MMBTU
            rows.append({"category": CATEGORY, "fuel": "Bagasse",
                         "fuel_detail": "wet as-fired basis, Section 1.8's own "
                                        "7.0 MMBtu/ton",
                         "pollutant": pol, "emissions_kt": bag_tj * k / 1e6,
                         "uncert_pct": bag_u, "ap42_table": tbl,
                         "ap42_rating": rate})

    # Captive self-generation burns gas and takes the same gas factors.
    # rc58: NOT by default. IPCC 2006 reports autoproducer generation under 1.A.2
    # (data/stream_reporting_sector.csv), and the industrial air layer
    # (pkinv.sectors.industry.air_pollutants, classes captive_gas_engine/turbine) now
    # prices captive gas on engine and turbine factors and carries it INTO the covered
    # panel under industry. Emitting it here too would count the same terajoules twice -
    # once beside the panel, once inside it - so the grid screening is grid-only and
    # include_captive=True exists for the transcription-equality test alone.
    if not include_captive:
        return _narrow_admitted(data, year, rows)
    # the captive panel is fiscal-END keyed while the grid year is fiscal-START; the
    # engine does this +1 at its own seam and the air layer must do the same, or captive
    # history shifts by a year silently (None keeps the pinned reference)
    cap_tj = captive.gas_TJ(data, year=None if year is None else year + 1)
    cap_u = product(data.p("captive_activity_uncert"), data.pu("captive_hhv_btu_per_scf"))
    for pol, (v, _s, tbl, rate) in sorted(GAS_LB_PER_MMSCF.items()):
        k, _u = _gas_kg_per_TJ(v)
        rows.append({"category": captive.CATEGORY, "fuel": "Natural Gas",
                     "fuel_detail": "", "pollutant": pol,
                     "emissions_kt": cap_tj * k / 1e6, "uncert_pct": cap_u,
                     "ap42_table": tbl, "ap42_rating": rate})
    return rows


def _narrow_admitted(data, year, rows):
    """Scale the oil and diesel SO2 rows to the fuel the admission register did not take.

    The include_captive=True path deliberately does NOT come through here: it exists only for
    the transcription-equality test, which compares against a figure computed before any of
    this, and narrowing it would make that test compare two different questions.
    """
    year = data.year if year is None else year
    for r in rows:
        if r["pollutant"] != "SO2" or r["fuel"] not in ADMITTED_SO2_FUELS:
            continue
        fraction, why = admitted_remainder_fraction(data, year, r["fuel"])
        if why:
            r["emissions_kt"] *= fraction
            r["basis"] = why
    return rows


def main():
    import csv
    import os

    from pkinv.paths import OUTPUTS
    from pkinv.sectors.power.data import PowerData

    data = PowerData()
    rows = compute(data)
    path = asset_path(OUTPUTS, "power_air_pollutants_%s.csv" % _sfx(data.year))
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "fuel", "fuel_detail", "pollutant", "emissions_kt",
                    "uncert_pct", "ap42_table", "ap42_rating", "basis"])
        for r in rows:
            w.writerow([r["category"], r["fuel"], r.get("fuel_detail", ""),
                        r["pollutant"], round(r["emissions_kt"], 3),
                        round(r["uncert_pct"], 1), r["ap42_table"], r["ap42_rating"],
                        "UNCONTROLLED SCREENING SCENARIO - what AP-42 default factors give on the fleet's own fuel with no control devices credited; not an estimate of stack emissions and not a mathematical maximum"])

    totals = {}
    for r in rows:
        totals[r["pollutant"]] = totals.get(r["pollutant"], 0.0) + r["emissions_kt"]
    print("Power air pollutants (uncontrolled screening scenario, GRID ONLY since rc58, FY%d)" % data.year)
    for p, v in sorted(totals.items(), key=lambda kv: -kv[1]):
        print("  %-8s %9.1f kt" % (p, v))
    print("  These are AP-42 uncontrolled factors: what leaves the furnace, not the stack.")
    print("  Pakistan's coal units carry precipitators and the newer ones desulphurisation,")
    print("  and no national dataset records which or how well, so the controlled figure is NE.")


if __name__ == "__main__":
    main()
