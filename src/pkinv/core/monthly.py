"""The monthly layer: annual components resolved in time, closing exactly.

THE CONTRACT. For a stream s in year y,

    E(s, y, m) = E(s, y) . p(s, y, m),    with  sum_m p(s, y, m) = 1

so the twelve months reproduce the annual inventory exactly, and moving emissions between
months can never create or destroy any. The annual component remains the control; this
layer only decides *when* within the year. That direction matters - it is why a bad
seasonal profile is a presentational error rather than an inventory error, and why the
national total is unaffected by every profile in this file.

WHY MONTHS ARE NOT A COMPONENT KEY. The obvious alternative is to have sectors emit twelve
rows per stream. It was rejected: (category, subitem) is a primary key that ten-plus
modules match on by exact string or substring, twelve-ing every sector's row count would
push the annual total from a control to a derived quantity, and every closure test in the
suite is written against the annual shape. A separate layer expresses the same equation
without touching any of that.

RESOLUTION IS NOT OBSERVATION. A monthly figure produced by spreading an annual total over
a degree-day curve is not a measurement, and a dataset that presents it beside a metered
monthly series without saying which is which invites exactly the misreading that finer
resolution encourages. Every row therefore carries a temporal_method from core.evidence:

    T1  observed monthly activity for this source and year
    T2  reconstructed from cumulative or related monthly administrative records
    T3  process-based seasonal profile (degree days, crop calendar, fire counts)
    T4  flat or weakly-informed profile

T4 is a legitimate answer. Some sources really are aseasonal, and a declared flat profile
is better than a fabricated shape. What is not legitimate is an undeclared one.
"""
import calendar
import csv

from pkinv.core import evidence

TOL = 1e-9          # relative; the profile is a pure redistribution, so closure is exact


def months_for(fiscal_year_start):
    """The twelve YYYYMM keys of a July-June fiscal year, in order.

    fiscal_year_start is the calendar year the fiscal year opens in: 2023 -> FY2023-24,
    202307 through 202406.
    """
    return (["%d%02d" % (fiscal_year_start, m) for m in range(7, 13)]
            + ["%d%02d" % (fiscal_year_start + 1, m) for m in range(1, 7)])


def normalise(weights):
    """{month: weight} -> {month: share summing to 1}.

    Raises on an all-zero or negative-summing profile rather than returning a uniform
    fallback: a profile that carries no information should say so by being declared T4,
    not by being silently invented here.
    """
    total = sum(weights.values())
    if total <= 0:
        raise ValueError("profile weights sum to %r; declare a flat T4 profile explicitly "
                         "rather than relying on a fallback" % total)
    return {m: w / total for m, w in weights.items()}


def flat_profile(fiscal_year_start):
    """An equal-twelfths profile: every month gets 1/12 regardless of how long it is.

    Keep this only for a quantity that really is per-month rather than per-day - a monthly
    charge, a per-month enumeration. For a continuous emission use days_weighted_profile:
    equal twelfths quietly claim February emits as much as July, which is wrong by 10.7
    percent between the shortest month and the longest.
    """
    months = months_for(fiscal_year_start)
    return {m: 1.0 / len(months) for m in months}


def days_weighted_profile(fiscal_year_start):
    """Each month's share is its length. The right default for a continuous source.

    A source with no seasonal evidence is not thereby a source that emits in equal monthly
    lumps: enteric fermentation, gas distribution leakage and landfill decay all run at some
    rate per day, so a year's emissions divide by TIME, and time is not distributed in equal
    twelfths. February is 28 or 29 days against July's 31 - a 10.7 percent difference on
    every stream that declares no seasonality, which is most of this inventory by mass.

    This is still TE4. Declaring no seasonality is a claim about the source; using the
    calendar correctly is not evidence about it. What days-weighting removes is an error,
    not an unknown.
    """
    months = months_for(fiscal_year_start)
    days = {m: calendar.monthrange(int(m[:4]), int(m[4:]))[1] for m in months}
    total = sum(days.values())
    return {m: d / total for m, d in days.items()}


def apply_profile(components, profile, fiscal_year_start, temporal_method,
                  profile_for=None, basis=""):
    """Resolve annual components into month rows.

    profile      {month: share} used for every component, or None to use profile_for.
    profile_for  callable(component) -> {month: share}, when streams differ in shape.
    Exactly one of the two is used; profile_for wins if given.

    temporal_method  a T-class string, or callable(component, month) -> T-class. The
    callable form exists because a real profile is often not one class throughout: a
    fiscal year covered by one direct monthly edition and eleven cumulative ones is T1 in
    July and T2 for the rest, and flattening that to the weaker class everywhere would
    discard the only observed month.

    basis  a string, or callable(component) -> string. Per-component because one module's
    streams often rest on different evidence: industry's liquids come from OCAC and its
    gas is flat, and a shared basis line would describe neither.

    Returns rows carrying the component's identity plus month, share and the emission
    columns scaled by the share. The annual row is left untouched.
    """
    pick = temporal_method if callable(temporal_method) else (lambda _c, _m: temporal_method)
    say = basis if callable(basis) else (lambda _c: basis)
    months = months_for(fiscal_year_start)
    out = []
    for c in components:
        shares = profile_for(c) if profile_for else profile
        missing = set(months) - set(shares)
        if missing:
            raise ValueError("profile for %s/%s is missing months: %s"
                             % (c["category"], c["subitem"], sorted(missing)))
        for m in months:
            share = shares[m]
            method = pick(c, m)
            if method not in evidence.TEMPORAL:
                raise ValueError("unknown temporal_method %r (expected one of %s)"
                                 % (method, sorted(evidence.TEMPORAL)))
            row = {"category": c["category"], "subitem": c["subitem"], "gas": c["gas"],
                   "month": m, "share": share,
                   "emissions_Gg": c["emissions_Gg"] * share,
                   "co2e_Mt_AR5": c["co2e_Mt_AR5"] * share,
                   "co2e_Mt_AR6": c["co2e_Mt_AR6"] * share,
                   "temporal_method": method, "basis": say(c)}
            out.append(row)
    return out


def check_totals(rows, controls, key, col, tol=TOL, what="monthly layer"):
    """Assert the month rows sum to their annual controls, per key.

    RAISES, like core.downscale.check_reconciliation, rather than returning a status. A
    monthly product that does not close is not a weaker product, it is a different
    inventory wearing the same name, and the run should stop.

    key      callable(row) -> hashable, applied to both rows and controls
    controls {key: annual total} or an iterable of control rows to be keyed and summed
    col      the column summed on the month rows
    """
    if not isinstance(controls, dict):
        acc = {}
        for c in controls:
            acc[key(c)] = acc.get(key(c), 0.0) + c[col]
        controls = acc
    monthly = {}
    for r in rows:
        monthly[key(r)] = monthly.get(key(r), 0.0) + r[col]

    problems = []
    for k, want in controls.items():
        got = monthly.get(k)
        if got is None:
            problems.append("%s: no monthly rows" % (k,))
            continue
        if abs(got - want) > max(tol * abs(want), tol):
            problems.append("%s: months sum to %.12f, control is %.12f" % (k, got, want))
    for k in set(monthly) - set(controls):
        problems.append("%s: monthly rows with no annual control" % (k,))
    if problems:
        raise AssertionError("%s does not close:\n  %s" % (what, "\n  ".join(problems)))
    return True


def _component_key(r):
    return (r["category"], r["subitem"], r["gas"])


def check_closure(rows, components, tol=TOL):
    """Assert the twelve months reproduce every annual component exactly."""
    return check_totals(rows, components, _component_key, "co2e_Mt_AR5", tol)


FIELDS = ("category", "subitem", "gas", "month", "share", "emissions_Gg",
          "co2e_Mt_AR5", "co2e_Mt_AR6", "temporal_method", "basis")


def write_layer(path, rows, components):
    """Check the layer closes, then write it. In that order, and it matters.

    Every module's layer ends the same way - assert, then write - and a module that wrote
    first would leave a published CSV describing an inventory the check had already rejected.
    check_closure raises, so this cannot return a partial product.
    """
    check_closure(rows, components)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for r in sorted(rows, key=lambda x: (x["category"], x["subitem"], x["gas"],
                                             x["month"])):
            w.writerow([r["category"], r["subitem"], r["gas"], r["month"],
                        round(r["share"], 8), round(r["emissions_Gg"], 8),
                        round(r["co2e_Mt_AR5"], 10), round(r["co2e_Mt_AR6"], 10),
                        r["temporal_method"], r["basis"]])
    return rows


def modal_class(rows):
    """{component key: the T-class covering most of the year}, by share.

    A stream is often not one class throughout - OCAC gives one directly published month and
    eleven differenced ones, NFDC gives nine observed months and three borrowed - and the
    annual component carries a single temporal_method. This is the rule that relates the two:
    the class that governs most of the year is the one the annual row declares, and the layer
    keeps the month-by-month detail that summary drops.
    """
    weight = {}
    for r in rows:
        k = _component_key(r)
        weight.setdefault(k, {})
        weight[k][r["temporal_method"]] = (weight[k].get(r["temporal_method"], 0.0)
                                           + r["share"])
    return {k: max(w, key=w.get) for k, w in weight.items()}


def month_totals(rows, col="co2e_Mt_AR5"):
    """{month: total} - the seasonal curve a reader actually wants to see."""
    out = {}
    for r in rows:
        out[r["month"]] = out.get(r["month"], 0.0) + r[col]
    return dict(sorted(out.items()))
