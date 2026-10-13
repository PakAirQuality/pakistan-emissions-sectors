"""Road transport - IPCC 1A3b.

ANCHORED ON FUEL, NOT ON THE FLEET MODEL. The road total is the fuel sold to the road
customer class (OCAC Sectoral Sales, Road row) run through IPCC Vol 2 Ch 3 Table 3.2.1
factors. The vehicle fleet model then distributes that total between classes, fuels and
districts. Both IPCC and EMEP require a bottom-up road estimate to be reconciled against
fuel sales; anchoring on fuel does the reconciliation by construction rather than as an
afterthought, and it means the fleet model's known defects shift the DISTRIBUTION rather
than the magnitude.

Two consequences worth stating. The published emission factors are per kilometre, so they
determine relative activity, not the total. And a fleet error that would have been a
factor-of-four blunder in a pure bottom-up estimate becomes a misallocation between
districts here - still wrong, but bounded.

THE SPLIT IS ENERGY-WEIGHTED (August 2026). Each class's claim on a fuel is its
vehicle-kilometres times a declared per-kilometre energy intensity, normalised within
the fuel: s(c,f) = VKT(c,f) x MJ/km(c,f) / sum. Earlier editions normalised
vehicle-kilometres alone, which asserts that a motorcycle-kilometre burns as much
petrol as a car-kilometre and that a van-kilometre burns as much diesel as a
truck-kilometre. That was wrong in a knowable direction and the correction is large:
the two-wheeler petrol weight fell 0.8119 -> 0.6100 at the current anchoring, the off-road diesel partition
0.100 -> 0.078, and heavy goods vehicles plus buses overtook two-wheelers as the
largest share of on-road CO2.

The intensities are DECLARED ENGINEERING JUDGEMENT (data/transport_params.csv,
mjkm_lo_*/mjkm_hi_*), not Pakistani measurement - the same values the fleet-implied
fuel diagnostic uses, and the epistemic promotion is deliberate and bounded: because
the weights are normalised within each fuel, no choice of intensity can move a control
total or the sector magnitude. It moves COMPOSITION, and through the off-road
partition it moves which IPCC category carries a fixed quantity of diesel. Both are
priced by the class_intensity_low/high scenarios. What would retire the judgement is a
Pakistani on-road fuel-economy measurement, which remains unobtained.

THE CONTROLS ARE OCAC'S ROAD CUSTOMER-CLASS ROWS (August 2026 re-anchor; year-indexed
since the series round). The petrol and diesel controls are the Transport/Road rows of
OCAC's Sectoral Sales of Energy Products, read by inventory year from the transcribed
panel (FY2016-17 onward) with the sector's reference year FY2023-24 as the default. Road is a CUSTOMER CLASS, retail pump sales: bulk
Industry, Power, Government and Railways diesel never enters it, so those claimants
are excluded by construction rather than carved out. Two editions of this sector's
paper described these tables as not acquired while the repository held them (fetched
by the aviation sector for their jet-fuel columns) - the same not-absent-but-unread
failure the CNG stream exposed, at larger stakes.

RAIL IS A CROSS-CHECK NOW, NOT A DEDUCTION. Railways is its own OCAC customer-class
row, so no rail quantity is subtracted from the Road control.
The Year Book relay - pkinv.sectors.railways.traction.diesel_kt(), 112,037 t - is
retained as an INDEPENDENT cross-check on the boundary: two unrelated sources, a
metered purchase ledger and a member-supplied sales table, agree on the rail figure
to 5.2 percent. tests/test_railways.py asserts both the independence (they must NOT
be equal) and the tolerance.

HOUSEHOLD GENERATOR PETROL REMAINS THE ONE CARVE-OUT ON PETROL. Generator fuel is
bought at the same retail stations the Road row counts, so it is inside the control;
the residential sector derives the mass from HIES 2024-25 generator-fuel expenditure
(~56 kt) and it is subtracted here through the relayed-accessor idiom;
tests/test_residential.py asserts the equality.

WHAT REMAINS INSIDE, AND ITS BOUND. Retail-bought diesel for stationary agricultural
plant (tube wells, threshers) and for captive generation stays inside the Road row -
a customer class cannot see end uses - and biases 1A3b high. OCAC books ZERO bulk HSD
to Agriculture in all nine editions, so the agricultural claim is retail-channel only.
The nine-year Road share of national internal HSD (0.826-0.907) bounds the boundary,
and the fuel ledger carries both claimants as UNRESOLVED status rows. The superseded
PES-derived controls - whose stored values were the source figures times 16/9, not
the documented 12/9 - are retained as the legacy_pes_control structural scenario.

NRV IS NOT ROAD TRANSPORT. Tractors and off-road plant are IPCC 1A4c ii, not 1A3b. They
are computed and reported separately, and deliberately kept out of the sector total. The
class also absorbs the source data's "Other vehicles" residual bucket, which makes it a
soft category twice over - see data/activity/transport/vehicle_classes.csv.
"""
from pkinv.core.uncertainty import product
from pkinv.sectors.railways import traction as rail
from pkinv.sectors.railways.data import RailwaysData
from pkinv.sectors.transport import fleet

CATEGORY = "Road transport"
OFF_ROAD = "NRV"
FUELS = ("Petrol", "Diesel", "CNG")
# Punjab workbook fuel label -> IPCC emission-factor item
IPCC_FUEL = {"Petrol": "Motor Gasoline", "Diesel": "Gas/Diesel Oil", "CNG": "Natural Gas"}


def suv_share(data, year):
    """The 4W1/4W2 split ramp, linear between the two reconstructed anchors.

    Declared rather than inherited: this ramp exists in neither the workbook nor the
    manuscript. It lived in a classify_vehicles.py that is not in the repository, and was
    reconstructed from the classified counts.
    """
    a, b = data.p("suv_share_start"), data.p("suv_share_end")
    lo, hi = 2003, 2023
    y = min(max(year, lo), hi)
    return a + (b - a) * (y - lo) / (hi - lo)


def effective_vkt(data, year=None):
    """{(ei_class, fuel): vehicle-km/yr} plus the fleet-cap diagnostic.

    Returns (vkt_by_class_fuel, n_cells, n_capped). Public so the air-pollutant layer
    uses the identical activity rather than recomputing it.

    THE FLEET YEAR IS NOT THE CONTROL YEAR, and defaulting it to the control year was a
    trap. The registration panel's last year is always partial - provinces file at different
    times - so FY2023-24 asked for 2024 and got 271 district-class cells against 2023's 741,
    with no exception. The class split then rode a third of the fleet and the fleet-implied
    fuel diagnostic collapsed by an order of magnitude, which looked like a finding about the
    fleet model rather than a missing-data artefact.

    Composition is a SHAPE, so it borrows the nearest complete year exactly as the provincial
    allocation does, and data.fleet_year() raises rather than silently thinning the fleet.
    """
    # EVERY requested year goes through the completeness rule, not only the default.
    # An explicit year used to bypass it and ride whatever partial panel that year had.
    year = data.fleet_year(year)
    out, capped, cells = {}, 0, 0
    for province, district, cls in data.cells(year):
        series = data.stock_series(province, district, cls)
        if year not in series:
            continue
        beta = data.p("weibull_beta_%s" % cls)
        life = data.p("weibull_life_%s" % cls)
        active, was_capped = fleet.active_fleet(series, beta, life, year)
        cells += 1
        capped += 1 if was_capped else 0
        km = active * data.vkt_for(cls, year)
        for f, share in data.split_for(cls, year).items():
            if share:
                out[(cls, f)] = out.get((cls, f), 0.0) + km * share
    return out, cells, capped


def rail_diesel_kt(rail_data=None):
    """The railways module's own diesel figure, kt/yr - the Year Book side of the
    rail cross-check. No longer deducted from the Road control (Railways is its own
    OCAC row); still relayed rather than copied, so the check cannot drift."""
    return rail.diesel_kt(RailwaysData() if rail_data is None else rail_data)


CROSSCHECK_HISTORICAL_YEAR = 2022      # FY2021-22, this sector's superseded reference period


def rail_crosscheck(data, rail_data=None):
    """The independent rail-diesel figures and their relative gaps.

    Year Book metered purchases against OCAC Railways customer-class sales - unrelated
    reporting chains, which is what makes agreement evidence rather than bookkeeping.

    HARMONISATION MADE THE PRIMARY PAIR THE NATURAL ONE. While this sector reported
    FY2021-22 and railways reported FY2023-24, the two sides of the check were two years
    apart, and matching them meant reaching back for the Year Book's own historical row -
    a deliberate contrivance, documented as such. Both sectors now report FY2023-24, so the
    railway module's OWN control-year quantity and the OCAC row for this sector's OWN
    reference period describe the same twelve months, and they agree to about 3.8 percent.

    The FY2021-22 Year Book row is retained as a cross-year bracket, which is the direction
    it should always have run: the year-matched pair is the check, and the mismatched one
    shows what a two-year offset costs.
    """
    rd = RailwaysData() if rail_data is None else rail_data
    yb = rail_diesel_kt(rd)
    yb_historical = rail.diesel_kt(rd, year=CROSSCHECK_HISTORICAL_YEAR)
    ocac_kt = data.ocac_t("Railways", "HSD") / 1000.0
    return {"yb_kt": yb, "ocac_kt": ocac_kt,
            "rel_diff_matched": abs(yb - ocac_kt) / ocac_kt,
            "yb_historical_kt": yb_historical,
            "rel_diff": abs(yb_historical - ocac_kt) / ocac_kt}


def generator_petrol_kt(res_data=None):
    """Petrol to deduct for household generators, kt/yr - the second carve-out on this
    control after railway diesel. Generator fuel is bought at the same stations the road
    control counts, but burns in stationary household engines and books to 1A4b; the
    residential sector derives the mass (HIES 2024-25 generator expenditure over the
    administered petrol price) and this function only relays it, so the two sectors
    cannot disagree. tests/test_residential.py asserts the equality."""
    from pkinv.sectors.residential import combustion as residential_combustion
    return residential_combustion.generator_petrol_kt(res_data)


def road_control_kt(data, param, year=None):
    """The road control quantity, kt, read from the OCAC panel by year.

    THE STATIC FACTOR ROWS AND THIS FUNCTION ARE ONE NUMBER, AND A TEST HOLDS THEM TO IT.
    tr_fuel_petrol_kt and tr_fuel_diesel_kt in data/emission_factors.csv are the OCAC
    FY2023-24 cells to the digit (MS 7,104,484 + HOBC 104,926 = 7,209,410 t = 7209.410 kt;
    HSD 5,551,442 t likewise), and tests/test_national_series.py asserts the equality as
    FLOAT ==, not a tolerance. The rows stay because they carry the declared 10 percent
    activity uncertainty (activity_uncert reads efu) and the provenance note; this function
    is the quantity path, so the magnitude can move with the year while the uncertainty
    declaration stays put. Until this function existed the magnitude was pinned to the
    reference year no matter what year a caller asked for - the year argument was accepted
    and ignored, which the sector contract called out as a declared limitation for three
    releases.
    """
    year = 2024 if year is None else year
    if param == "Motor Gasoline":
        return (data.ocac_t("Road", "MS", year) + data.ocac_t("Road", "HOBC", year)) / 1000.0
    return data.ocac_t("Road", "HSD", year) / 1000.0


def fuel_TJ(data, year=None, rail_data=None, res_data=None,
            control_category="transport_fuel_supply", deduct_rail=False):
    """{fuel: TJ} of the road control totals, split petrol/diesel.

    The controls are OCAC's Road customer-class rows, which exclude rail by
    construction, so only the household-generator petrol carve-out applies. The
    control_category and deduct_rail kwargs exist for the structural scenarios,
    which rebuild the superseded national-supply-minus-rail arrangement.

    The reference control reads the OCAC panel through road_control_kt(year); the
    structural-scenario categories (_legacy, _pes12) keep their factor-row path, because
    each of those IS a declared alternative static control rather than a year series.
    The generator-petrol deduction is the HIES-derived value in every year - a declared
    held-constant, surfaced in the national series' held_constant column.
    """
    deduction = {"Motor Gasoline": generator_petrol_kt(res_data),
                 "Gas/Diesel Oil":
                     rail_diesel_kt(rail_data) if deduct_rail else 0.0}
    out = {}
    for fuel, param in (("Petrol", "Motor Gasoline"), ("Diesel", "Gas/Diesel Oil")):
        if control_category == "transport_fuel_supply":
            kt = road_control_kt(data, param, year) - deduction[param]
        else:
            kt = data.efv(control_category, param) - deduction[param]
        ncv = data.efv("transport_ncv", param)
        out[fuel] = kt * 1000.0 * ncv / 1000.0        # kt -> Gg -> TJ
    return out


def _shares(data, vkt, basis="mid"):
    """Within-fuel weights that split each fuel control total between classes.

        w(c,f) = VKT(c,f) x MJ/km(c,f);   s(c,f) = w(c,f) / sum_c w(c,f)

    ENERGY, NOT DISTANCE. Until August 2026 this normalised vehicle-kilometres
    alone, which asserts that a motorcycle-kilometre and a car-kilometre consume the
    same petrol and that a van-kilometre and a truck-kilometre consume the same
    diesel. Both are false in a knowable direction, and the effect was large: the
    two-wheeler petrol weight fell from 0.8119 to 0.6100 once the intensities were
    applied, and heavy diesel overtook two-wheelers as the largest class.

    The intensities are declared engineering judgement (data.mjkm), not Pakistani
    measurement. That is why they are confined to this function: because each fuel's
    weights are normalised to one, NO choice of intensity can move a control total or
    the sector magnitude. It moves composition, and through the off-road partition it
    moves which IPCC category carries a fixed quantity of diesel. The
    class_intensity_low/high scenarios price that.

    Normalised over ALL classes including off-road, deliberately. Renormalising after
    dropping off-road would give the on-road classes 100% of the diesel while off-road
    separately claimed its share - the same tonne of fuel counted twice.
    """
    out = {}
    for fuel in FUELS:
        weighted = {k: v * data.mjkm(k[0], fuel, basis)
                    for k, v in vkt.items() if k[1] == fuel}
        tot = sum(weighted.values())
        for k, v in weighted.items():
            out[k] = v / tot if tot else 0.0
    return out


def activity_uncert(data):
    return product(data.p("activity_uncert"), data.efu("transport_fuel_supply", "Motor Gasoline"))


def off_road_TJ(data, year=None, control_category="transport_fuel_supply",
                deduct_rail=False, intensity_basis="mid"):
    """Diesel energy burnt by off-road machinery, TJ/yr.

    Public because offroad.py is the module that reports it - IPCC puts this stream in
    1A4c, not 1A3b, so it is a separate category built from the same fuel control total.

    THE SHARE IS READ FROM _shares(), NOT RECOMPUTED. It used to be its own ratio of
    raw vehicle-kilometres, which agreed with the on-road split only because both were
    built the same way. Once the on-road split became energy-weighted that coincidence
    broke: on-road classes would have taken 1 - 0.078 of the diesel while off-road
    still claimed 0.100, and the sector would have silently gained half a megatonne of
    double-counted fuel. Reading the same normalised weight makes conservation of the
    diesel control structural rather than a property two functions happen to share.
    """
    vkt, _cells, _capped = effective_vkt(data, year)
    share = _shares(data, vkt, intensity_basis).get((OFF_ROAD, "Diesel"), 0.0)
    if not share:
        return 0.0
    tj = fuel_TJ(data, year, control_category=control_category,
                 deduct_rail=deduct_rail)
    return tj["Diesel"] * share


def compute(data, year=None, control_category="transport_fuel_supply",
            deduct_rail=False, intensity_basis="mid"):
    """Return (components, memo).

    components: 1A3b on-road, the national total.
    memo:       empty. Off-road machinery used to ride here as a CO2-only memo item; it is
                now a reported category of its own (offroad.py), and leaving the memo in
                place would report the same diesel twice.
    """
    vkt, _cells, _capped = effective_vkt(data, year)
    tj = fuel_TJ(data, year, control_category=control_category,
                 deduct_rail=deduct_rail)
    shares = _shares(data, vkt, intensity_basis)
    ad_u = activity_uncert(data)
    components = []

    for fuel in ("Petrol", "Diesel"):
        item = IPCC_FUEL[fuel]
        co2_ef = data.efv("transport_fuel_co2", item)
        ch4_ef = data.efv("transport_fuel_ch4", item)
        n2o_ef = data.efv("transport_fuel_n2o", item)
        # Split the fuel control total across classes by their share of vehicle-km.
        for cls in fleet.CLASSES:
            if cls == OFF_ROAD:
                continue
            share = shares.get((cls, fuel), 0.0)
            if share <= 0:
                continue
            t = tj[fuel] * share
            components.append({
                "category": CATEGORY, "subitem": "%s %s CO2" % (cls, fuel), "gas": "CO2",
                "emissions_Gg": t * co2_ef / 1e6,
                "uncert_pct": product(ad_u, data.efu("transport_fuel_co2", item))})
            components.append({
                "category": CATEGORY, "subitem": "%s %s CH4" % (cls, fuel), "gas": "CH4",
                # Petrol and diesel are fossil, so CH4 takes AR5 30 not 28 - as in power
                # and aviation, and the opposite of waste.
                "fossil": True, "emissions_Gg": t * ch4_ef / 1e6,
                "uncert_pct": product(ad_u, data.efu("transport_fuel_ch4", item))})
            components.append({
                "category": CATEGORY, "subitem": "%s %s N2O" % (cls, fuel), "gas": "N2O",
                "emissions_Gg": t * n2o_ef / 1e6,
                "uncert_pct": product(ad_u, data.efu("transport_fuel_n2o", item))})

    return components, []
