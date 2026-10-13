"""Off-road mobile machinery - IPCC 1A4c ii.

Tractors, agricultural plant and construction machinery. It lives in the transport package
because it is computed from the transport sector's fleet model and the same national diesel
control total, but it is NOT road transport: IPCC reports it under 1A4c, Other Sectors, and
the category name says so because a reader scanning a category list should not have to
know.

WHY THIS WAS A MEMO FOR SO LONG, AND WHY IT NO LONGER IS. road.compute() has been carrying
this stream as a CO2-only memo item outside every total, with a note explaining that 1A4c
is not 1A3b. That was the right call while the stream had no category to live in - a memo
cannot be summed into the national total by accident. Now it has one. The memo is gone,
because reporting the same diesel in both places would be the double-count the memo
convention exists to prevent, and tests/test_transport.py asserts the memo is empty.

THE ACTIVITY IS THE ON-ROAD SPLIT'S OWN WEIGHT. road._shares() normalises energy-weighted
vehicle-kilometre shares over ALL classes including this one, deliberately - renormalising
after dropping off-road would hand the on-road classes 100 percent of the diesel while this
category separately claimed its share, counting the same tonne twice. off_road_TJ() reads
its share straight out of that normalisation rather than recomputing one, so the partition
conserves the diesel control structurally. Since the split became energy-weighted the share
is 0.078 rather than the 0.100 that distance alone implied: off-road machinery burns more
fuel per kilometre than the on-road diesel fleet average, so weighting by energy moves
diesel back to the road category.

TABLE 3.3.1, NOT THE ROAD TABLE. IPCC gives off-road machinery its own defaults and N2O is
28.6 kg/TJ against road diesel's 3.9 - seven times higher, and identical to the rail value,
because all three come from EEA 2005 and off-road engines generally carry no catalyst. On
the road factor this category would report about 8 percent less. Third instance of the same
trap in this inventory after power/residential and road/rail, and pinned the same way.

THIS IS THE CORRECTION ROAD.PY ASKED FOR. That module's docstring records that agricultural
and captive-generation diesel remain inside the road control total with no figure to remove
them by obtained here, biasing road transport high. Booking off-road as its own category is
that removal for the agricultural half: the diesel now leaves 1A3b and arrives in 1A4c
instead of being counted as road and separately noted as a memo.

KNOWN FLAW, INHERITED AND STATED. The class is the source workbook's residual bucket as
well as its tractor class - vehicle_classes.csv maps the catch-all "Other vehicles" into it
wholesale, and the whole class is then modelled as 100 percent diesel. So the magnitude is
a genuine carve-out of the fuel control total, but what exactly is inside it is soft, and
the cropland proxy that allocates it is right for the tractors and wrong for the remainder.
"""
from pkinv.core.uncertainty import product
from pkinv.sectors.transport import road

# The name declares the mixture: the class is reported under 1A4c ii but the source
# workbook's residual bucket puts construction and industrial machinery - IPCC 1A2
# gvii - inside it, and no equipment-stock data here supports splitting the two. The
# offroad_reallocated_1a2 scenario prices the recode; the completeness table carries
# the 1A2 side as a declared IE row.
CATEGORY = "Mixed off-road (1A4c/1A2)"
ITEM = "Gas/Diesel Oil"


def compute(data, year=None, control_category="transport_fuel_supply",
            deduct_rail=False, intensity_basis="mid"):
    """Return (components, memo). No memo: this category is reported, not excluded."""
    tj = road.off_road_TJ(data, year, control_category=control_category,
                          deduct_rail=deduct_rail, intensity_basis=intensity_basis)
    ad_u = road.activity_uncert(data)
    components = []
    for gas, cat in (("CO2", "offroad_machinery_co2"),
                     ("CH4", "offroad_machinery_ch4"),
                     ("N2O", "offroad_machinery_n2o")):
        row = {"category": CATEGORY, "subitem": "Off-road machinery diesel %s" % gas,
               "gas": gas, "emissions_Gg": tj * data.efv(cat, ITEM) / 1e6,
               "uncert_pct": product(ad_u, data.efu(cat, ITEM))}
        if gas == "CH4":
            # Diesel is fossil, so CH4 takes AR5 30 not 28 - as in road, rail and power.
            row["fossil"] = True
        components.append(row)
    return components, []
