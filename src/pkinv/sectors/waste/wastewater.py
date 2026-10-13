"""Domestic wastewater - IPCC 4D1 (2006 GL Vol 5 Ch 6; nitrous oxide on the 2019 Refinement).

MARKED NE UNTIL THE ONE MISSING TABLE WAS FETCHED. Everything else was in hand - the
district population panel, IPCC's maximum methane-producing capacity, the regional BOD
default - and the category was left unestimated because the split of the population
between discharge pathways was unknown, and that split sets the methane correction factor
across a range from 0.0 to 0.8. Assuming it would have chosen the answer rather than
estimated it.

The WHO/UNICEF Joint Monitoring Programme publishes exactly that split for Pakistan, by
urban and rural, on a population denominator that leaves no ambiguity about what the
percentages are of - which was the specific defect in the secondhand figures circulating
in the literature. FY2023:

                      sewer   septic  latrine  unimproved  open defecation
    Urban              62.6     18.0      8.4        10.3              0.6
    Rural               8.8     34.8     29.9        12.2             14.4

That urban/rural contrast is the whole reason the category is worth stratifying: the
same person contributes about five times more methane on a city sewer than in a rural
latrine, and Pakistan's population is 62 percent rural.

THE PATHWAY THAT DECIDES THE ANSWER IS THE SEWER. IPCC gives flowing sewers 0.0 and
stagnant open warm sewers 0.5. Pakistani urban drainage is predominantly open, warm and
discharged untreated - under one percent of municipal wastewater is treated - so 0.5 is
the central value. The alternative reading, that sewered flow reaches a watercourse and
takes the 0.1 river-discharge factor, is published as a sensitivity rather than argued
away, because it moves the category by more than a factor of two.

Open defecation carries an explicit zero rather than being dropped: material left on open
ground decomposes aerobically, IPCC offers no anaerobic pathway for it, and writing the
assumption down is the difference between a decision and an oversight.

NITROUS OXIDE IS SMALL AND MUCH SOFTER THAN THE METHANE. It runs on protein supply rather
than BOD - FAOSTAT Food Balance Sheets, 73.39 g/capita/day - through IPCC's nitrogen chain.
Its effluent emission factor has a published range spanning a factor of 150, so the N2O
side is the least constrained number in this sector despite being a fraction of it.

THE NITROUS-OXIDE METHOD IS THE 2019 REFINEMENT'S SINCE rc67 (n2o_gg, nitrogen_pathways).
Through rc66 this module ran the 2006 equation: one nitrogen total for the whole
population, on protein supply, with the sewer's industrial factor applied to everyone,
all of it treated as effluent. The Refinement allocates the nitrogen to the SAME sanitation
pathways the methane side already uses, and changes five things at once, which is why it
is implemented as a method and not as a new factor:

  nitrogen in       protein CONSUMED (supply x 0.96), plus household products (x 1.1); the
                    industrial and commercial factor (1.25) on the sewered population only
  removal           a fraction of each pathway's nitrogen never reaches water: septic tank
                    0.15, latrine 0.12, secondary treatment 0.40, none where untreated
  plant emissions   the nitrogen entering a treatment plant emits there (0.016); with one
                    per cent of sewered flow treated this term is small and it is not zero
  effluent          what is left after removal, summed over EVERY pathway (Eq 6.8), at the
                    Tier 1 factor 0.005 - the same factor as 2006
  the factor's      0.0005-0.075, where the 2006 Guidelines printed 0.0005-0.25: the upper
  range             tail of this category, and of the national interval, is shorter

The whole population stays in the estimate. Three things the method needs are not measured
for Pakistan and are declared, each with a scenario: how much sewered flow is treated, where
the nitrogen leaving septic tanks and latrines ends up (water, as Eq 6.8 has it, or soil, as
the chapter's own Figure 6.1 draws it), and whether receiving waters are nutrient-impacted.
The 2006 method is retained whole as the alternative (parameter ww_n2o_method_2019 = 0).

WHAT IS NOT HERE. Industrial wastewater (4D2), which needs output and organic loading by
industry and is blocked with 1A2. Sludge, which IPCC would have in 4A if it were disposed
of and which Pakistan largely does not collect. And centralised treatment, which is
absent because there is almost none.
"""
from pkinv.core.uncertainty import product

CATEGORY = "Domestic wastewater"
N2O_N_TO_N2O = 44.0 / 28.0
SETTINGS = ("Urban", "Rural")
# pathway -> MCF parameter
PATHWAYS = (("sewer", "ww_mcf_sewer"), ("septic", "ww_mcf_septic"),
            ("latrine", "ww_mcf_latrine"), ("unimproved", "ww_mcf_latrine"),
            ("open", "ww_mcf_open"))


def population(data, year=None):
    """{setting: people} from the same district panel the other two categories use."""
    year = data.year if year is None else year
    urban = sum(r["pop_urban"] for r in data.population_for(year))
    rural = sum(r["pop_rural"] for r in data.population_for(year))
    return {"Urban": urban, "Rural": rural}


def jmp_year(data, year=None):
    """The JMP calendar year that serves one fiscal-end year: the fiscal START year, as the
    2023 row has always served FY2023-24, clamped to the years the table holds."""
    held = sorted({y for y, _setting in data.sanitation})
    wanted = (data.year if year is None else year) - 1
    return min(max(wanted, held[0]), held[-1])


def _shares(data, setting, year=None):
    """Each year's own pathway shares (rc67). Through rc66 the table held 2023 alone and
    every year of the series carried it, "an explicit HOLD ... when the WHO/UNICEF annual
    series is transcribed, this becomes a year lookup". It is transcribed
    (scripts/ingest_jmp_sanitation.py), and methane and nitrous oxide read the same row."""
    return data.sanitation[(jmp_year(data, year), setting)]


def tow_kg(data, year=None, bod=None):
    """{(setting, pathway): kg BOD/yr} - total organics in wastewater, IPCC Eq 6.3.

    The industrial correction factor applies to the SEWERED fraction only: uncollected
    pathways receive no industrial load by definition.
    """
    rate = data.p("ww_bod_g_per_cap_day") if bod is None else bod
    out = {}
    pop = population(data, year)
    for setting in SETTINGS:
        shares = _shares(data, setting, year)
        for pathway, _mcf in PATHWAYS:
            people = pop[setting] * shares[pathway]
            load = people * rate / 1000.0 * 365.0          # g/day -> kg/yr
            if pathway == "sewer":
                load *= data.p("ww_industrial_factor")
            out[(setting, pathway)] = load
    return out


def ch4_gg(data, year=None, sewer_mcf=None, bod=None):
    """Gg CH4 from domestic wastewater, IPCC Eq 6.1/6.2."""
    tow = tow_kg(data, year, bod)
    total = 0.0
    for (setting, pathway), load in tow.items():
        mcf = dict(PATHWAYS)[pathway]
        value = (sewer_mcf if (pathway == "sewer" and sewer_mcf is not None)
                 else data.p(mcf))
        total += load * value
    return total * data.p("ww_bo") / 1e6                    # kg -> Gg


def _protein(data, year=None):
    """g protein SUPPLY per person per day for one year.

    Clamped-year lookup, not always-latest. protein.csv holds 2020-2023; the old
    max(data.protein) gave every year 2023's value, ignoring three observed years. The
    reference year 2024 still clamps to 2023, but 2020-2022 use their own observations.
    Outside the panel the nearest edge year is held, which the series declares."""
    wanted = year if year is not None else max(data.protein)
    return data.protein[min(max(wanted, min(data.protein)), max(data.protein))]


def n2o_gg_2006(data, year=None):
    """Gg N2O by the 2006 Guidelines' equation: one nitrogen total, all of it effluent.

    THE REFERENCE THROUGH rc66, THE ALTERNATIVE SINCE. IPCC 2006 Vol 5 Ch 6 Eq 6.8:
    N_EFFLUENT = P x Protein x F_NPR x F_NON-CON x F_IND-COM - N_SLUDGE, on protein supply,
    with the industrial factor on the whole population, and Eq 6.7 at the effluent factor.
    N_SLUDGE is an explicit parameter defaulting to zero, as the equation has it."""
    people = sum(population(data, year).values())
    n_total = (people * _protein(data, year) / 1000.0 * 365.0   # g/day -> kg protein/yr
               * data.p("ww_f_npr") * data.p("ww_f_non_con") * data.p("ww_f_ind_com"))
    n_effluent = max(n_total - data.p("ww_n_sludge_kg"), 0.0)
    return n_effluent * data.p("ww_ef_effluent") * N2O_N_TO_N2O / 1e6


# pathway -> (removal-fraction parameter, plant-factor parameter, centralised).
# None is the table's "no treatment": nothing removed, nothing emitted at a plant.
NITROGEN_PATHWAYS = (
    ("sewer, untreated", None, None, True),
    ("sewer, treated", "ww_nrem_secondary", "ww_ef_plant_aerobic", True),
    ("septic", "ww_nrem_septic", "ww_ef_septic", False),
    # Table 6.8A prints 0 for latrines ("N2O is not significant"): no plant term.
    ("latrine", "ww_nrem_latrine", None, False),
    ("unimproved", "ww_nrem_latrine", None, False),
    ("open", None, None, False),
)
_JMP_KEY = {"sewer, untreated": "sewer", "sewer, treated": "sewer"}


def nitrogen_pathways(data, year=None):
    """One row per setting and pathway: the 2019 Refinement's nitrogen account.

    Eq 6.10   TN_j = P_j x Protein x F_NPR x N_HH x F_NON-CON x F_IND-COM, with
              Protein = supply x F_PC (Eq 6.10a) and F_IND-COM 1.25 on sewers, 1 elsewhere
    Eq 6.9    N2O_plant = TN_j x EF_j x 44/28, on the nitrogen ENTERING the system
    Eq 6.8    N_effluent = TN_j x (1 - N_REM_j), the nitrogen left after removal
    Eq 6.7    N2O_effluent = N_effluent x EF_EFFLUENT x 44/28

    The sewered population is split by ww_treated_share into a treated part and an
    untreated part. ww_decentralised_to_water is the share of the nitrogen leaving
    decentralised systems that reaches an aquatic environment: 1 in the reference (Eq 6.8
    sums every pathway), 0 in the scenario that reads Figure 6.1's routing to soil.

    Pathway nitrogen sums to total nitrogen, and removed + effluent + diverted-to-soil
    sums to pathway nitrogen, on every row; tests assert both."""
    pop = population(data, year)
    protein_kg = (_protein(data, year) * data.p("ww_f_pc")) / 1000.0 * 365.0
    per_person = (protein_kg * data.p("ww_f_npr") * data.p("ww_n_hh")
                  * data.p("ww_f_non_con"))
    treated = data.p("ww_treated_share")
    to_water = data.p("ww_decentralised_to_water")
    ef_effluent = data.p("ww_ef_effluent")
    rows = []
    for setting in SETTINGS:
        shares = _shares(data, setting, year)
        for pathway, nrem_param, plant_param, centralised in NITROGEN_PATHWAYS:
            people = pop[setting] * shares[_JMP_KEY.get(pathway, pathway)]
            if pathway == "sewer, treated":
                people *= treated
            elif pathway == "sewer, untreated":
                people *= 1.0 - treated
            factor = data.p("ww_f_ind_com" if centralised
                            else "ww_f_ind_com_decentralised")
            tn = people * per_person * factor
            nrem = data.p(nrem_param) if nrem_param else 0.0
            ef_plant = data.p(plant_param) if plant_param else 0.0
            left = tn * (1.0 - nrem)
            effluent = left if centralised else left * to_water
            rows.append({
                "setting": setting, "pathway": pathway, "people": people,
                "nitrogen_kg": tn, "removed_kg": tn * nrem, "effluent_kg": effluent,
                "to_soil_kg": left - effluent,
                "n2o_plant_Gg": tn * ef_plant * N2O_N_TO_N2O / 1e6,
                "n2o_effluent_Gg": effluent * ef_effluent * N2O_N_TO_N2O / 1e6})
    return rows


def n2o_gg_2019(data, year=None):
    """Gg N2O by the 2019 Refinement: plant and effluent emissions over every pathway."""
    return sum(r["n2o_plant_Gg"] + r["n2o_effluent_Gg"]
               for r in nitrogen_pathways(data, year))


def n2o_method(data):
    """Which method this data object runs: the parameter ww_n2o_method_2019 is a switch."""
    return "ipcc2019" if data.p("ww_n2o_method_2019") >= 0.5 else "ipcc2006"


def n2o_gg(data, year=None, method=None):
    """Gg N2O from domestic wastewater nitrogen, by the method the data object selects
    (the 2019 Refinement since rc67) unless one is named."""
    method = method or n2o_method(data)
    if method == "ipcc2019":
        return n2o_gg_2019(data, year)
    if method == "ipcc2006":
        return n2o_gg_2006(data, year)
    raise ValueError("unknown wastewater N2O method %r" % (method,))


def activity_uncert(data):
    return product(5, data.pu("ww_bod_g_per_cap_day"), data.pu("ww_bo"))


def effluent_ef_uncert(data):
    """The effluent factor's declared width: the bounded-draw equivalent, in percent.

    Since rc11 the factor is drawn from a bounded split-triangular in log space over
    its published range (0.0005-0.075 since rc67, the 2019 Refinement's; 0.0005-0.25
    before, the 2006 Guidelines'; mode 0.005 in both) rather than a symmetric +/-100% -
    see waste/uncertainty.BOUNDED_DRAW. This helper converts that shape into the
    equivalent symmetric half-width - about 401%, log-variance matched - for the
    surfaces that can only carry one number: the component row, the Approach-1
    quadrature and the national parameter stream. This docstring said "about 1100%"
    for several releases against a function returning 400.8; the waste paper has
    always printed the right figure, so the error was confined to the one place a
    reader of the code would look. The asymmetric truth lives in the sector's parameter-rerun
    Monte Carlo percentiles, which is where the published interval now comes from.
    """
    from pkinv.sectors.waste import uncertainty as wu   # lazy: avoids import cycle
    return wu.equivalent_bounded_uncert_pct(data, "ww_ef_effluent")


def compute(data, year=None):
    """Return (components, memo). No memo: everything here is in the national total."""
    ad_u = activity_uncert(data)
    return [
        {"category": CATEGORY, "subitem": "Domestic wastewater CH4", "gas": "CH4",
         "emissions_Gg": ch4_gg(data, year),
         "uncert_pct": product(ad_u, data.pu("ww_mcf_sewer"))},
        {"category": CATEGORY, "subitem": "Domestic wastewater N2O", "gas": "N2O",
         "emissions_Gg": n2o_gg(data, year),
         # population 5, then every factor of the nitrogen chain that carries a declared
         # width. F_NON-CON was missing from this product through rc66 while the
         # parameter rerun drew it; the row and the draw now price the same chain.
         "uncert_pct": product(5, data.pu("ww_f_npr"), data.pu("ww_f_non_con"),
                               data.pu("ww_f_ind_com"), effluent_ef_uncert(data))},
    ], []
