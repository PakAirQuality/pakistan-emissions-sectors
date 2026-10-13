"""Civil aviation - IPCC 1A3a (2006 GL Vol 2 Ch 3.6).

ACTIVITY. The CAA publishes aircraft movements, and an aircraft movement is one take-off
OR one landing. ICAO's own glossary: "For airport traffic purposes one arrival and one
departure is counted as two movements." So

    LTO cycles = movements / 2

Two independent routes reach that conclusion. The definition above, and load factors:
Karachi carries 150 domestic passengers per movement, which is 83% of a 180-seat A320 if
a movement is one-way but an implausible 42% if it is a whole cycle. This is the largest
factor-of-2 risk in the sector, so a test pins the load factor rather than the divisor.

The halving is right for domestic and international, but for different reasons, and the
distinction is worth stating because otherwise it looks like luck. A domestic Karachi to
Lahore flight produces two movements nationally (a departure and an arrival) and burns
exactly one complete LTO cycle inside Pakistan. An international Karachi to Dubai flight
produces only one movement here, corresponding to the departure half of a cycle; the
other half arrives on an inbound flight. Inbound and outbound balance, so N international
movements is still N/2 cycle-equivalents.

THE DOMESTIC/INTERNATIONAL SPLIT. IPCC Table 3.6.1: "The international/domestic split
should be determined on the basis of departure and landing locations for each flight
stage and not by the nationality of the airline." Only domestic (1A3a ii) enters the
national total. International (1A3a i) is a bunker memo item: IPCC section 3.6.1 says
emissions from international aviation "are to be excluded from national totals, and
reported separately as memo items". That is why compute() returns a tuple.

EMISSIONS. Domestic is estimated full-flight - LTO plus cruise - from the ICAO Carbon
Emissions Calculator's stage-length fuel tables, applied to a representative domestic
stage length and a year-varying fleet mix. The tempting shortcut of scaling LTO up by
IPCC's remark that ~10% of aviation fuel burns in the LTO cycle must NOT be used: that is
a global average dominated by long-haul, whereas Pakistan's domestic sectors run 18% to
40%, so it would inflate the estimate several-fold.

SPLIT SINCE rc47 WAVE 3 (the twenty-first review's finding, the rail-recode pattern:
same fuel, same factors, the national total conserved exactly). The full-flight estimate
ships as TWO streams: the LTO share (the fleet-weighted per-cycle fuel over the
full-flight fuel, ~16.5%% for the 2023 mix) placed at the airports whose movements
generate it, and the cruise remainder, which is NOT placed below the province - no
origin-destination matrix is held, and corridor weights built from endpoint movements
would be invented physics. Cruise is booked at the uplift provinces on the accounting
view (fuel is uplifted and sold at airports; the same convention road fuel rides) and
carries the aviation_cruise release-height class that sat waiting in the vocabulary
"until observed stages exist" - the stage split is that observation, from the ICAO
tables the estimate already rides.

International airport LTO emissions are reported separately from the full-flight bunker
estimate now supplied by the OCAC customer-to-flight-geography fuel bridge. Pakistan's
international network is too wide for one representative stage length to mean anything.

Non-commercial movements are kept as a separate labelled stream and are NOT part of
1A3a. IPCC puts military aviation in 1A5b, and the CAA's non-commercial column mixes
general aviation, training circuits and military movements at the joint-use fields
(Chaklala, Peshawar, Quetta, Faisalabad), and this inventory has not separated them. The
CAA source does not distinguish them; whether operator-level records would is untested.
"""
from pkinv.core.uncertainty import product

CATEGORY = "Domestic aviation"
FUEL_EF = "aviation_lto_fuel"
FF_EF = "aviation_fullflight"


def lto_cycles(data, year=None):
    """{'domestic': n, 'international': n, 'noncommercial': n} LTO-cycle equivalents."""
    per_lto = data.p("movements_per_lto")
    dom = intl = non = 0.0
    for r in data.movements_for(year):
        dom += r["com_dom_mv"]
        intl += r["com_intl_mv"]
        non += r["noncom_mv"]
    return {"domestic": dom / per_lto, "international": intl / per_lto,
            "noncommercial": non / per_lto}


def _fleet_fuel(data, segment, year, full_flight):
    """Fleet-weighted fuel in kg, per LTO cycle or per full flight."""
    mix = data.fleet_for(segment, year)
    stage = data.p("domestic_stage_length_nm")
    total = 0.0
    for aircraft, share in mix.items():
        if not full_flight:
            total += share * data.efv(FUEL_EF, aircraft)
            continue
        # ICAO Appendix C is tabulated at fixed stage lengths; interpolate between the
        # 500 and 750 nm columns, which bracket every Pakistani domestic sector.
        lo = data.efv(FF_EF, "%s_500" % aircraft)
        hi = data.efv(FF_EF, "%s_750" % aircraft)
        f = lo + (hi - lo) * (stage - 500.0) / 250.0
        total += share * f
    return total


def fuel_tonnes(data, year=None):
    """{stream: tonnes of jet fuel}. Domestic is full-flight; the others are LTO only."""
    cyc = lto_cycles(data, year)
    y = data.year if year is None else year
    return {
        "domestic": cyc["domestic"] * _fleet_fuel(data, "commercial", y, True) / 1000.0,
        "international": cyc["international"] * _fleet_fuel(data, "international", y, False) / 1000.0,
        "noncommercial": cyc["noncommercial"] * _fleet_fuel(data, "noncommercial", y, False) / 1000.0,
    }


def _gases(data, fuel_t):
    """(CO2 Gg, CH4 Gg, N2O Gg) from a tonnage of jet fuel."""
    tj = fuel_t * data.p("jet_kerosene_ncv") / 1000.0        # t -> Gg -> TJ
    co2 = fuel_t * data.p("co2_per_t_fuel") / 1000.0          # t CO2 -> Gg
    ch4 = tj * data.p("ch4_kg_per_tj") / 1e6                  # kg -> Gg
    n2o = tj * data.p("n2o_kg_per_tj") / 1e6
    return co2, ch4, n2o


def activity_uncert(data):
    return product(data.p("activity_uncert"), data.pu("domestic_stage_length_nm"))


def compute(data, year=None):
    """Return (components, memo).

    components: 1A3a ii domestic aviation, the only part that counts nationally.
    memo:       1A3a i international bunkers, plus the non-commercial stream, both
                reported and both deliberately outside the national total.
    """
    fuel = fuel_tonnes(data, year)
    ad_u = activity_uncert(data)
    co2_u = product(ad_u, data.pu("co2_per_t_fuel"))

    y = data.year if year is None else year
    # The stage split: per-cycle fuel over full-flight fuel, both from the same ICAO
    # tables and the same year's fleet mix, so LTO + cruise == the old domestic stream
    # EXACTLY by construction (cruise is the residual of the same tonnage).
    lto_fuel = min(fuel["domestic"],
                   lto_cycles(data, year)["domestic"]
                   * _fleet_fuel(data, "commercial", y, False) / 1000.0)
    cruise_fuel = fuel["domestic"] - lto_fuel
    ch4_u = product(ad_u, data.pu("ch4_kg_per_tj"))
    n2o_u = product(ad_u, data.pu("n2o_kg_per_tj"))
    components = []
    for stage, tonnes in (("LTO", lto_fuel), ("cruise", cruise_fuel)):
        co2, ch4, n2o = _gases(data, tonnes)
        components += [
            {"category": CATEGORY, "subitem": "Domestic aviation %s CO2" % stage,
             "gas": "CO2", "emissions_Gg": co2, "uncert_pct": co2_u},
            {"category": CATEGORY, "subitem": "Domestic aviation %s CH4" % stage,
             "gas": "CH4",
             # Jet kerosene is a fossil fuel, so this CH4 carries the fossil GWP: AR5 30
             # rather than 28, AR6 29.8 rather than 27. The inverse of the waste sector,
             # where the flag stays off, and pinned by a test in both places.
             "fossil": True,
             "emissions_Gg": ch4, "uncert_pct": ch4_u},
            {"category": CATEGORY, "subitem": "Domestic aviation %s N2O" % stage,
             "gas": "N2O", "emissions_Gg": n2o, "uncert_pct": n2o_u},
        ]

    memo = []
    ico2, ich4, in2o = _gases(data, fuel["international"])
    memo.append({
        "item": "International aviation LTO emissions at Pakistani airports",
        "gas": "CO2", "emissions_Gg": ico2, "fuel_t": fuel["international"],
        "note": "IPCC 2006 GL Vol 2 Ch 3 s3.6.1: emissions from international aviation "
                "are excluded from national totals and reported separately as memo items. "
                "Covers only landing and take-off at Pakistani airports. It is distinct "
                "from the full-flight bunker memo estimated by the fuel bridge."})
    nco2, nch4, nn2o = _gases(data, fuel["noncommercial"])
    memo.append({
        "item": "Non-commercial movements, LTO portion",
        "gas": "CO2", "emissions_Gg": nco2, "fuel_t": fuel["noncommercial"],
        "note": "Reported separately rather than inside 1A3a: the CAA's non-commercial "
                "column mixes general aviation, training circuits and military movements "
                "at joint-use airfields, and IPCC reports military aviation under 1A5b."})
    return components, memo
