"""Solid waste disposal sites - IPCC 4A (2006 GL Vol 5 Ch 3), First Order Decay.

THE COMPLEMENT OF OPEN BURNING, AND THAT IS THE POINT. open_burning.py takes the waste
that is never collected and burns a fraction of it. This module takes the waste that IS
collected and buries it. Together they exhaust what households generate:

    generated = collected + uncollected           (exactly, by construction)
    burned    = uncollected x B_frac              (open_burning.py)
    disposed  = collected                         (here)

The two categories therefore cannot double-count a tonne, and tests/test_waste.py asserts
the identity rather than trusting it. It is the same shape as the dung-cake transfer
between agriculture and residential and the rail/road diesel carve-out: a boundary that
closes arithmetically instead of by assertion in prose.

METHANE ARRIVES LATE, WHICH IS WHY THIS IS NOT A ONE-YEAR CALCULATION. Waste buried in
2010 is still emitting in 2023. IPCC's First Order Decay model tracks the stock of
decomposable carbon rather than the year's deposits (Vol 5 Ch 3 Eq 3.4-3.5):

    DDOCm_d(T)      = W(T) x DOC x DOCf x MCF          deposited, decomposable
    DDOCm_a(T)      = DDOCm_d(T) + DDOCm_a(T-1) x e^-k accumulated in the site
    DDOCm_decomp(T) = DDOCm_a(T-1) x (1 - e^-k)        decomposed this year
    CH4_generated   = DDOCm_decomp x F x 16/12
    CH4_emitted     = (CH4_generated - R) x (1 - OX)

R is zero: Pakistan has no operating landfill-gas recovery. OX is zero, which is IPCC's
default for unmanaged and uncategorised sites (Table 3.2) - oxidation credit requires a
managed cover this country's dumps do not have.

DOC IS DERIVED FROM THE COMPOSITION ALREADY IN THE REPOSITORY, NOT INVENTED. The open-
burning module carries total carbon (0.2195 t C/t wet) and fossil carbon (0.0757) per wet
tonne, both derived from the Pak-EPA 1996 composition against IPCC Vol 5 Ch 2 Table 2.4.
Degradable organic carbon is the difference: the biogenic carbon, 0.1438 t C/t wet. Plastics
and synthetic textiles are excluded because they are the fossil term, and street-sweeping
fines are excluded because that module already maps them to "other, inert". Deriving DOC
this way keeps the two categories on one composition; a separate DOC default would let the
same waste have two carbon contents.

THE SERIES IS BACK-PROJECTED BEFORE 2000, AND THAT IS DECLARED. The district panel starts
in 2000, but with k = 0.065 the half-life is about eleven years, so waste buried in the
1970s and 1980s still contributes in the reference year. Starting the model in 2000 with an
empty site would understate the answer. Population before 2000 is therefore back-projected
from the panel's own earliest compound growth rate, and the model is spun up from 1960.
That is a projection, not data: it is the reason the activity uncertainty carried here is
wider than open burning's, and the sensitivity in the runner shows what the alternative
no-spin-up assumption would give.

WHAT IS NOT HERE. Industrial and construction waste - IPCC would have them in the same
category, and Pakistan publishes no national quantity for either. Sludge from wastewater
treatment likewise. The category is municipal solid waste only, which is stated in
docs/completeness.md rather than left to be inferred from the number.
"""
import math

from pkinv.core.uncertainty import product

CATEGORY = "Solid waste disposal"
C_TO_CH4 = 16.0 / 12.0
SPINUP_FROM = 1960


def waste_generated(data, year=None):
    """Tonnes of wet municipal waste generated, all strata. The parent of both streams."""
    total_kg = 0.0
    for r in data.population_for(year):
        total_kg += (r["pop_urban"] * data.p("gen_rate_urban")
                     + r["pop_rural"] * data.p("gen_rate_rural")) * 365.0
    return total_kg / 1000.0


def waste_disposed(data, year=None):
    """Tonnes of wet waste collected and taken to a disposal site.

    The complement of open_burning.waste_burnt's uncollected stream, using the same
    generation rates and the same collection coverage, so the two cannot disagree about
    how much waste exists.
    """
    total_kg = 0.0
    for r in data.population_for(year):
        total_kg += (r["pop_urban"] * data.p("gen_rate_urban")
                     * (1.0 - data.p("uncollected_urban"))
                     + r["pop_rural"] * data.p("gen_rate_rural")
                     * (1.0 - data.p("uncollected_rural"))) * 365.0
    return total_kg / 1000.0


def panel_years(data):
    return sorted({r["year"] for r in data.population})


def disposal_series(data, year=None):
    """{year: tonnes disposed} from SPINUP_FROM to `year`, back-projected before the panel.

    The back-projection uses the compound growth rate of the panel's own first decade,
    applied backwards. It is a projection and is labelled as one everywhere it surfaces.
    """
    year = data.year if year is None else year
    years = panel_years(data)
    first, last = years[0], years[-1]

    observed = {y: waste_disposed(data, y) for y in years if y <= year}
    if not observed:
        return {}

    # min(year, last): asking for a year below the panel's tenth used to KeyError on
    # observed[first + span] - the growth window reached past the filtered dict. It only
    # bites below 2010, outside the published series span, but a spin-up helper that
    # crashes on the years it exists to reconstruct is wrong on its own terms.
    span = min(10, min(year, last) - first)
    growth = (observed[first + span] / observed[first]) ** (1.0 / span) if span else 1.0
    series = dict(observed)
    for y in range(first - 1, SPINUP_FROM - 1, -1):
        series[y] = series[y + 1] / growth
    return series


def ddocm_accumulated(data, year=None, spinup=True):
    """Run the FOD forward and return (DDOCm decomposed in `year`, series used).

    spinup=False starts the site empty in the panel's first year, which is what an
    inventory that ignored the deposit history would get. It exists for the sensitivity.
    """
    year = data.year if year is None else year
    series = disposal_series(data, year)
    if not spinup:
        series = {y: v for y, v in series.items() if y >= panel_years(data)[0]}
    if not series:
        return 0.0, {}

    k = data.p("swds_k")
    doc = data.p("total_c_per_wet_t") - data.p("fossil_c_per_wet_t")
    factor = doc * data.p("swds_docf") * data.p("swds_mcf")
    decay = math.exp(-k)

    accumulated, decomposed = 0.0, 0.0
    for y in sorted(series):
        decomposed = accumulated * (1.0 - decay)
        accumulated = series[y] * factor + accumulated * decay
    return decomposed, series


def monthly_state(data, through_fy_start):
    """{YYYYMM: emission} from ONE continuous monthly FOD recursion, 1960 onward.

    The Wave-3 state engine, replacing a per-year replay that had three defects the
    survey named: each fiscal year recomputed its stock independently (no continuity
    across June 30), the within-year deposit used the LAST year of the whole series
    (2024's tonnage injected into 2015's stock), and a declared half-year seam stood
    between the calendar-keyed annual recursion and the fiscal months.

    Now: a single pool decays month by month from SPINUP_FROM, S_m = S_{m-1}
    e^(-k days_m/365.25) + W_m, with W_m the deposit of the month's OWN calendar
    year spread by days (days-weighted by declaration - no monthly tonnage is
    observed), calendar month lengths and leap years exact, and the reaction delay
    a declared parameter (swds_delay_months): a deposit joins the DECAYING stock
    that many months after it lands, the IPCC convention the ANNUAL model omits.
    The delay is a SHAPE refinement only - the annual control is preserved exactly
    by per-year normalisation downstream, and the annual model's delay-absence is
    the separate, priced methodology candidate the registries record.

    Single pool, deliberately: the annual model carries one k, and expressing
    per-cohort or per-waste-stream half-lives here would make the shape disagree
    with the total it distributes. The day cohorts become expressible only when
    the annual model does.
    """
    import calendar as _calendar
    series = disposal_series(data, data.year)
    k = data.p("swds_k")
    doc = data.p("total_c_per_wet_t") - data.p("fossil_c_per_wet_t")
    factor = doc * data.p("swds_docf") * data.p("swds_mcf")
    delay = int(data.p("swds_delay_months"))

    emissions = {}
    stock = 0.0
    maturing = []                       # deposits waiting out the reaction delay
    for year in range(SPINUP_FROM, through_fy_start + 2):
        annual = series.get(year, 0.0) * factor
        year_days = 366 if _calendar.isleap(year) else 365
        for month in range(1, 13):
            days = _calendar.monthrange(year, month)[1]
            decay = math.exp(-k * days / 365.25)
            emissions["%d%02d" % (year, month)] = stock * (1.0 - decay)
            maturing.append(annual * days / year_days)
            stock = stock * decay
            if len(maturing) > delay:
                stock += maturing.pop(0)
    return emissions


def monthly_decomposition_shares(data, fy_start=None):
    """{YYYYMM: share} for one fiscal year, cut from the continuous state engine.

    The recursion runs once from 1960; a fiscal year's twelve months are read out
    of it, so the stock flows across June 30 by construction and FY(t+1)'s July
    opens on exactly the stock FY(t)'s June closed with. The shares normalise to
    one, so the layer's closure to the annual row is unchanged by construction
    (FOD_shaped_allocation: the engine decides WHEN within the year, never how
    much).
    """
    fy_start = data.year - 1 if fy_start is None else fy_start
    emissions = monthly_state(data, fy_start)
    months = (["%d%02d" % (fy_start, m) for m in range(7, 13)]
              + ["%d%02d" % (fy_start + 1, m) for m in range(1, 7)])
    year = {m: emissions[m] for m in months}
    total = sum(year.values())
    return {key: v / total for key, v in year.items()}


def monthly_spread_pct(data, fy_start=None):
    """Max-to-min spread of the monthly FOD shares, in percent of a flat month -
    the number the temporal decomposition quotes as the finding."""
    shares = monthly_decomposition_shares(data, fy_start)
    return 100.0 * (max(shares.values()) - min(shares.values())) * 12.0


def ch4_emitted(data, year=None, spinup=True):
    """Gg CH4 released from disposal sites in `year`."""
    decomposed, _series = ddocm_accumulated(data, year, spinup)
    generated = decomposed * data.p("swds_f") * C_TO_CH4
    recovered = data.p("swds_recovery_t")
    return max(generated - recovered, 0.0) * (1.0 - data.p("swds_oxidation")) / 1000.0


def activity_uncert(data):
    """Wider than open burning's: the deposit history is partly back-projected, and MCF
    stands in for a site-type census Pakistan has never published."""
    # swds_backprojection is itself an uncertainty term, so its VALUE is the percentage -
    # the same convention residential uses for its activity_uncert_* rows.
    return product(5,                                  # population, census-interpolated
                   data.pu("gen_rate_urban"),
                   data.pu("uncollected_urban"),
                   data.p("swds_backprojection"))


def compute(data, year=None):
    """Return (components, memo). Disposal has no memo stream: the CO2 released as landfill
    gas is biogenic and, unlike open burning, IPCC does not ask for it as a memo item -
    that carbon is already tracked as a stock change in the AFOLU sector."""
    ad_u = activity_uncert(data)
    components = [{
        "category": CATEGORY, "subitem": "Managed and unmanaged disposal sites CH4",
        "gas": "CH4", "emissions_Gg": ch4_emitted(data, year),
        "uncert_pct": product(ad_u, data.pu("swds_k"), data.pu("swds_mcf"),
                              data.pu("swds_docf")),
    }]
    return components, []
