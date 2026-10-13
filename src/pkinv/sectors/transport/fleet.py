"""Weibull survival model: registered stock -> active fleet.

Pakistani provincial registration tables report CUMULATIVE STOCK — "NUMBER OF MOTOR
VEHICLES STOOD REGISTERED UPTO 30.06.2023". A scrapped vehicle stays in the total unless
formally deregistered, so the raw counts badly overstate what is actually on the road,
and increasingly so for short-lived classes like motorcycles.

The model, from the Punjab Transport manuscript s3.7.3. Its shape parameters exist ONLY
in that PDF: the workbook is pasted values and its methodology note gives median service
lives but not beta.

    cohort      d(y0,c) = max(0, N(y0,c) - N(y0-1,c))        eq (6)
    survival    S(t)    = exp(-(t/lambda)^beta),  lambda = L / (ln 2)^(1/beta)   eq (7)
    active      F(y,c)  = SUM over y0<=y of  d(y0,c) * S(y-y0)                   eq (8)

ONE DELIBERATE DEPARTURE FROM THE SOURCE. Equation (6) discards negative increments, so
the summed survived cohorts can exceed the stock actually reported. In the Punjab
workbook this is not a rounding artefact: at district-and-class level the 2023 mean ratio
of active fleet to reported stock is 4.43, taxis average 23.6, and the maximum is 402 —
i.e. the model claims four hundred times more active taxis than were ever registered
there. That happens wherever a reported series falls (a deregistration, a boundary
change, or Sindh's documented flip between "ON ROAD" and "REGD:" reporting bases): the
drop is discarded on the way down but the earlier cohorts keep surviving.

We cap the active fleet at reported stock and count how often the cap binds, rather than
inheriting the defect. Because this sector is anchored on a fuel control total the error
would be distributional rather than a level error, but an uncapped 402x would still wreck
the allocation between districts.
"""
import math

CLASSES = ("2W", "3W", "4W1", "4W2", "4WT", "LDV", "BUS", "HDV", "NRV")


def lambda_for(beta, half_life):
    """Weibull scale from the shape and the median life, so that S(L) = 0.5 exactly."""
    return half_life / (math.log(2.0) ** (1.0 / beta))


def survival(age, beta, half_life):
    """S(t) = exp(-(t/lambda)^beta). S(0) = 1, S(half_life) = 0.5."""
    if age <= 0:
        return 1.0
    return math.exp(-((age / lambda_for(beta, half_life)) ** beta))


def cohorts(stock_by_year):
    """{year: new registrations} from a cumulative series, eq (6).

    The first year is treated as one entering cohort of the whole stock, which is the
    source's convention and means the base year is unsurvived.
    """
    years = sorted(stock_by_year)
    out = {}
    for i, y in enumerate(years):
        if i == 0:
            out[y] = stock_by_year[y]
        else:
            out[y] = max(0.0, stock_by_year[y] - stock_by_year[years[i - 1]])
    return out


def active_fleet(stock_by_year, beta, half_life, year, cap=True):
    """Active vehicles in `year`, eq (8). Returns (fleet, capped) — `capped` records
    whether the cap bound, so the caller can report how often the defect would have
    fired."""
    coh = cohorts(stock_by_year)
    total = sum(n * survival(year - y0, beta, half_life)
                for y0, n in coh.items() if y0 <= year)
    reported = stock_by_year.get(year)
    if cap and reported is not None and total > reported:
        return reported, True
    return total, False
