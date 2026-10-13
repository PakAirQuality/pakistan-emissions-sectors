"""Railway transport - IPCC 1A3c.

THE SIMPLEST SECTOR IN THE INVENTORY, AND DELIBERATELY SO. Pakistan Railways is a single
state operator that meters its own fuel and publishes the annual total in its Year Book
under the heading FUEL CONSUMPTION - the source's own word, and the word this module uses.
The 2020-21 narrative states that "these quantities comprise the entire fuel consumed on
the Railways, i.e. on locomotives, power houses, water pumps, workshops etc." There is no
fleet model, no split between operators, no allocation of a national fuel supply between
competing uses. The activity datum is one number a year, and the estimate is that number
times an IPCC factor. The Tier 1 assumption that fuel consumed in the year equals fuel
burnt in the year is stated rather than hidden; procurement and stock timing are why the
annual series is lumpy.

WHICH IPCC TABLE. Vol 2 Ch 3 gives rail its own default table, 3.4.1, and it is not the
road table. CO2 is identical at 74,100 kg/TJ, because CO2 depends only on the carbon in
the fuel. N2O is 28.6 against road diesel's 3.9 - SEVEN TIMES higher. Large slow-speed
locomotive engines run lean at high load, which is the N2O-forming regime. Using the road
factor would understate railway N2O by 86 percent and this sector's total by 8 percent
(0.363 against 0.394 Mt, published as a diagnostic row). This is the same trap the
residential sector documents against the power table and the power sector documents
against everything else; rail is its third instance.

NO CURRENT ELECTRIC TRACTION - SINCE ABOUT 2010, NOT THE 1970s. Recent Year Book editions
report Electric Energy as NIL, but the same historical table (2020-21 edition, p.154)
carries non-zero electric traction energy from the 1985-90 quinquennium (37.4 GWh/yr
average) declining through 2005-2010 (6.1 GWh/yr), going NIL only from the 2010-2015 row.
The Lahore-Khanewal electrification operated into the late 2000s; the network has been
diesel-only since roughly 2010. Scope: this module covers the Pakistan Railways mainline
system's direct combustion. Urban electric rail (the Lahore Orange Line) has zero direct
1A3c combustion; its electricity is accounted under power generation, and the boundary is
recorded in the completeness table.

THE RAIL/ROAD DIESEL BOUNDARY, CLOSED. Pakistan's national HSD supply figure covers road,
rail, agriculture and captive generation together, and the transport sector's control
total has been taking all of it as road while declaring in its own docstring that this
"biases the sector high" and naming rail first among the reasons. It no longer does:
transport now subtracts this sector's diesel from its control total, so the same tonne of
HSD cannot be burnt twice. The deduction is driven by this module rather than by a
hand-copied constant, so the two sectors cannot drift apart, and tests/test_railways.py
asserts the closure with == rather than a tolerance. Rail is about 1.3 percent of national
HSD, so this moves road transport by roughly a third of a megatonne - small, but it is a
real double-count and it was already written down as one.

THIS SECTOR DISAGREES WITH PAKISTAN'S OWN BUR-1 BY A FACTOR OF NINE IN THE MATCHED YEAR,
AND SAYS SO. The First Biennial Update Report puts railways at 4.06 Mt CO2e for FY2017-18.
That fiscal year is in this module's series (series year 2018, labelled by ending year):
156,396 thousand litres, 0.466 Mt CO2e by the identical method - a matched-year ratio of
8.7. The reference year FY2023-24 gives 0.394 Mt. The gap is not a year effect: FY2017-18
fuel is eighteen percent above FY2023-24, not a factor of ten.

The disagreement is resolvable on arithmetic rather than on judgement. 4.06 Mt of CO2
requires roughly 1,280 kt of diesel. Pakistan Railways reports consuming 112 kt in the
reference year (and 132 kt in the BUR's own year). Per unit of traffic, the metered
consumption works out at 4.0 litres per train-kilometre over the operator's own 33.1
million train-km, which is where a diesel locomotive belongs; BUR-1's implied fuel would
be 46 litres per train-kilometre, which no locomotive does. The lower figure is the one
the operator's fuel account, the traffic statistics and the carbon content of diesel all
support, so it is the one reported here.

Recorded rather than quietly matched, because a national inventory that silently disagrees
with its country's submission is worse than one that disagrees openly. tests/test_railways.py
pins both the fuel bound and the per-train-km intensity, so the claim is checked on every run.

KNOWN LIMITS, STATED RATHER THAN HIDDEN.

The series is unbroken, FY2014-FY2024. FY2018 and FY2019 were once absent (their own
editions are scans with no text layer) and were recovered from the 2020-21 edition's
historical run, which reproduces FY2016, FY2017 and FY2021 exactly against figures already
held from other editions. Recovered, not interpolated; a test pins the contiguity and both
values.

The furnace-oil basis is settled as tonnes. Editions changed the published unit label
without announcement - "Tonnes" through 2020-21, "Liters/thousand" from 2022-23 - and the
2023-24 edition resolves it against itself: the p.163 detail column is headed "Furnace Oil
(M. Tonnes)", the narrative states 79.907 M.T, and the summary's unit column is
demonstrably unreliable. The stream is under 0.001 Mt CO2e either way, and a test pins the
indifference. It is carried at all because IPCC Ch 3 s3.4.1.4 warns specifically against
omitting the non-diesel traction fuels.

Fuel used by railway workshops, stationary plant and track machines is inside the same
consumption figure THIS MODULE READS - the source narrative says so explicitly - and is
now MEASURED, not assumed: the Year Book's detail table splits locomotive from
other-than-locomotive consumption, and reconcile.py reads it. Non-traction diesel is 1,599
thousand litres, 1.21 percent of the total. It belongs outside 1A3c - by source, in
stationary or off-road categories, not as a single block in 1A4c ii - and leaving it here
biases this sector slightly high by that amount. Five Year Book editions are held in
sources/Railways/ with text dumps in railway_data/; the detail-vs-summary reconciliation
runs in reconcile.py and now closes in all ten years both tables cover - the one
disagreement it ever found (FY2023-24, a 4.52 percent gap on a typographically anomalous
cell) was restated by the 2024-25 edition to within one part in 132,588 of the summary
this module had reported throughout. See reconcile.py's docstring for the full story.
"""
from pkinv.core.uncertainty import product

CATEGORY = "Railways"
# THE rc11 RE-BASE: the reference itself now books the measured non-traction fuel at its
# own category instead of declaring it IE inside 1.A.3.c. The Year Book's detail table
# splits locomotive from other-than-locomotive consumption per fuel (reconcile.py), so
# 1.A.3.c holds locomotive traction (0.38939 Mt) and this category holds the 0.00498 Mt
# of workshops, power houses, pumps and track machinery - fuels and factors identical,
# so the module total is conserved to the last digit and only the reporting code moves.
# The IPCC destination is 1.A.2 / 1.A.4.c BY USE, and the source publishes no per-use
# split, which is why the category name says unresolved rather than picking one. The
# seventh review asked for exactly this booking twice; the previous declared-IE reference
# survives as the rail_ie_summary configuration.
NON_TRACTION_CATEGORY = "Railway non-traction energy (1A2/1A4c unresolved)"
# (stream label, IPCC emission-factor item, density parameter, activity-uncertainty suffix)
FUELS = (("Diesel", "Gas/Diesel Oil", "hsd_density_kg_per_l", "diesel"),
         ("Furnace oil", "Residual Fuel Oil", "rfo_density_kg_per_l", "rfo"))


def locomotive_fraction(data, stream, year=None):
    """The locomotive share of one fuel stream, from the Year Book detail table.

    Years the detail table does not cover (the series' pre-2016 tail) return 1.0:
    with no measured split the whole account stays at 1.A.3.c, which is the
    pre-detail booking and is declared on the series rather than back-projected.
    """
    from pkinv.sectors.railways import reconcile
    if stream == "Diesel":
        share = reconcile.non_traction_share(data, year)
        return 1.0 if share is None else 1.0 - share
    d = reconcile.detail_for(year if year is not None else data.year,
                             fuel="Residual Fuel Oil")
    if d is None:
        return 1.0
    total = (d["locomotive"] or 0.0) + (d["other_than_locomotive"] or 0.0)
    return (d["locomotive"] or 0.0) / total if total else 1.0


def fuel_TJ(data, year=None):
    """{stream: TJ}. Litres -> tonnes -> Gg -> TJ, or tonnes -> Gg -> TJ directly.

    The furnace-oil rows before FY2022 are published in tonnes and the rows from FY2022 in
    thousand litres; the unit travels with each row in the activity file rather than being
    assumed from the year, so a future correction to either basis is a data edit.
    """
    out = {}
    for stream, item, density_param, _u in FUELS:
        try:
            qty = data.quantity(item, year)
        except KeyError:
            if item == "Gas/Diesel Oil":
                raise  # a year without diesel is not a year; furnace oil may be absent
            continue  # the stream is <0.001 Mt in every held year; a test pins the bound
        unit = data.unit(item, year)
        if unit == "thousand litres":
            gg = qty * 1000.0 * data.p(density_param) / 1e6      # k litres -> l -> kg -> Gg
        elif unit == "tonnes":
            gg = qty / 1000.0                                     # t -> Gg
        else:
            raise ValueError("unhandled activity unit %r for %s" % (unit, item))
        out[stream] = gg * data.efv("railway_ncv", item)
    return out


def diesel_kt(data, year=None):
    """Railway diesel in kt/yr.

    Public because the road-transport sector subtracts it from the national HSD control
    total. Exposing the quantity rather than the emissions keeps the deduction on the
    fuel side, which is where transport's anchoring argument lives.
    """
    return (data.quantity("Gas/Diesel Oil", year) * 1000.0
            * data.p("hsd_density_kg_per_l") / 1e6)


def compute(data, year=None):
    """Return (components, memo). Rail has no memo stream; the tuple keeps the shape.

    Each fuel stream splits by the Year Book detail table's locomotive share: the
    traction part stays 1.A.3.c, the measured remainder books at the non-traction
    category. Factors are IDENTICAL on both sides - the source publishes no per-use
    split that would justify different ones, and identical factors are what makes the
    re-base a pure reporting recode: the module total is conserved exactly.
    """
    tj = fuel_TJ(data, year)
    components = []
    for stream, item, _d, unc in FUELS:
        ad_u = data.p("activity_uncert_" + unc)
        loco = locomotive_fraction(data, stream, year)
        # CH4 and N2O come from the rail table for both fuels: Table 3.4.1 tabulates only
        # diesel and coal, and s3.4.1.4 directs that other traction fuels be treated with
        # the same emission properties.
        for gas, cat, ef_item in (("CO2", "railway_traction_co2", item),
                                  ("CH4", "railway_traction_ch4", "Gas/Diesel Oil"),
                                  ("N2O", "railway_traction_n2o", "Gas/Diesel Oil")):
            gg = tj[stream] * data.efv(cat, ef_item) / 1e6
            u = product(ad_u, data.efu(cat, ef_item))
            for category, sub_label, portion in (
                    (CATEGORY, "%s %s" % (stream, gas), loco),
                    (NON_TRACTION_CATEGORY,
                     "Non-traction %s %s" % (stream.lower(), gas), 1.0 - loco)):
                if portion <= 0.0:
                    continue
                row = {"category": category, "subitem": sub_label, "gas": gas,
                       "emissions_Gg": gg * portion, "uncert_pct": u}
                if gas == "CH4":
                    # Diesel and furnace oil are fossil, so CH4 takes AR5 30 not 28 - as
                    # in road transport, power and aviation, and the opposite of waste.
                    row["fossil"] = True
                components.append(row)
    return components, []
