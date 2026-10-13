"""Open burning of municipal solid waste - IPCC 4C2 (2006 GL Vol 5 Ch 5).

Activity, IPCC Equation 5.7, applied per district and per urban/rural stratum:

    MSW_B = P x MSW_P x P_frac x B_frac x 365

  P       district population in the stratum
  MSW_P   per-capita generation (Pak-EPA 1996: urban 0.453, rural 0.283 kg/cap/day)
  P_frac  share of waste never collected (What a Waste 2.0: urban 0.30, rural 0.70)
  B_frac  share of uncollected waste openly burned (IPCC Box 5.1 expert judgement, 0.60)

This deliberately replaces the source workbook's `((0.35*0.5*Rural)+(0.55*0.2*Urban))*365`,
whose four constants had no label, unit or citation anywhere. Re-anchoring on Eq 5.7 with
Pakistani inputs lowers 2023 burned mass from 13.0 to about 9 Mt/yr. That drop is the
honest consequence of sourcing the numbers, not a correction of an arithmetic error.

Carbon dioxide, IPCC Equation 5.2:

    CO2 = MSW_B x SUM_j(WF_j x dm_j x CF_j x FCF_j) x OF x 44/12

Only the FOSSIL fraction enters the national total. IPCC Vol 5 Ch 5 section 5.1 is explicit:
CO2 from the biomass content of waste (food, paper, wood) is biogenic and "should not be
included in national total emission estimates", while CO2 from plastics, synthetic
textiles and rubber is. Biogenic CO2 is computed here too, but only as a memo item, and
is never returned as a component. That is why this module returns a tuple - the memo
would otherwise have to ride the component contract, where it would be summed into the
national total, which is exactly what the convention forbids.

CH4 and N2O are counted in full regardless of carbon origin. Note the two IPCC factors use
different weight bases by design: CH4 per WET tonne, N2O per DRY tonne.
"""
from pkinv.core.uncertainty import product

CATEGORY = "Open burning of waste"
C_TO_CO2 = 44.0 / 12.0
EF = "waste_burning"


def waste_burnt(data, year=None):
    """Tonnes of wet municipal waste openly burned, summed over districts and strata.

    Public because the air-pollutant layer must use the identical mass rather than
    recomputing it - the same reason residue_burning.mass_burnt is public.
    """
    gen_u = data.p("gen_rate_urban")
    gen_r = data.p("gen_rate_rural")
    unc_u = data.p("uncollected_urban")
    unc_r = data.p("uncollected_rural")
    bfrac = data.p("burned_fraction")

    total_kg = 0.0
    for r in data.population_for(year):
        total_kg += (r["pop_urban"] * gen_u * unc_u + r["pop_rural"] * gen_r * unc_r) * bfrac * 365.0
    return total_kg / 1000.0          # kg -> tonnes wet


def activity_uncert(data):
    """Approach-1 uncertainty on burned mass.

    Population is well measured (a census panel), so the term is small; the generation
    rates, uncollected shares and the burned fraction are not, and B_frac dominates.
    """
    return product(5,                                   # population, census-interpolated
                   data.pu("gen_rate_urban"),
                   data.pu("uncollected_urban"),
                   data.pu("burned_fraction"))


def co2_streams(data, year=None):
    """(fossil CO2 Gg, biogenic CO2 Gg) from IPCC 2006 Vol 5 Ch 5 Eq 5.1.

    5.1, not 5.2: 5.2 sums over waste COMPONENTS with their own dm/CF/FCF, and this path
    does not - it applies one combined coefficient to the whole burned mass, which is the
    5.1 form under that equation's stated allowance to "combine them into one component"
    when the fossil carbon fraction is known directly. fossil_c_per_wet_t already carries
    dm x CF x FCF, so there is deliberately no dry-matter term here; dry_matter belongs to
    the N2O path below and to the air factors, whose IPCC factors are per dry tonne.
    """
    mb = waste_burnt(data, year)
    of = data.p("oxidation_factor")
    fossil_c = data.p("fossil_c_per_wet_t")
    total_c = data.p("total_c_per_wet_t")
    fossil = mb * fossil_c * of * C_TO_CO2 / 1000.0        # t -> Gg
    total = mb * total_c * of * C_TO_CO2 / 1000.0
    return fossil, total - fossil


def compute(data, year=None):
    """Return (components, memo).

    components: the three streams that count toward the national total.
    memo:       biogenic CO2, reported but deliberately NOT a component.
    """
    mb = waste_burnt(data, year)
    ad_u = activity_uncert(data)
    dm = data.p("dry_matter")

    fossil_co2, biogenic_co2 = co2_streams(data, year)
    ch4_gg = mb * data.efv(EF, "CH4") / 1e6                # g/kg wet x t -> Gg
    n2o_gg = mb * dm * data.efv(EF, "N2O") / 1e6           # N2O factor is per DRY tonne

    components = [
        {"category": CATEGORY, "subitem": "Open waste burning CO2 (fossil)", "gas": "CO2",
         "emissions_Gg": fossil_co2,
         "uncert_pct": product(ad_u, data.pu("fossil_c_per_wet_t"), data.pu("oxidation_factor"))},
        {"category": CATEGORY, "subitem": "Open waste burning CH4", "gas": "CH4",
         "emissions_Gg": ch4_gg,
         # Landfill and dump fires are fossil-fuel-free, but the CH4 comes from combustion
         # of a stream that is roughly a third fossil carbon. IPCC still treats waste CH4 as
         # non-fossil for GWP purposes, so the flag stays off.
         "uncert_pct": product(ad_u, data.efu(EF, "CH4"))},
        {"category": CATEGORY, "subitem": "Open waste burning N2O", "gas": "N2O",
         "emissions_Gg": n2o_gg,
         "uncert_pct": product(ad_u, data.pu("dry_matter"), data.efu(EF, "N2O"))},
    ]
    memo = [
        {"item": "Biogenic CO2 (memo, excluded from the national total)",
         "gas": "CO2", "emissions_Gg": biogenic_co2,
         "note": "IPCC 2006 GL Vol 5 Ch 5 s5.1: CO2 from the biomass content of waste is "
                 "not included in national totals."},
    ]
    return components, memo
