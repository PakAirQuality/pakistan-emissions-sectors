"""Industrial combustion, resolved into the twelve months of FY2023-24.

TWO PROFILES, TWO EVIDENCE CLASSES, AND THE DIFFERENCE IS THE POINT.

The LIQUID fuels are reconstructed from OCAC's own monthly editions of the same table the
annual quantities come from. July 2023 was published as a direct monthly edition (T1); the
eleven editions after it print PAKISTAN-wide cumulative year-to-date totals only, so each
month is recovered by DIFFERENCING consecutive cumulative columns (T2). This is not a
model. Every monthly value is an arithmetic identity on two published numbers, and the June
cumulative column is the annual figure itself - which is why the twelve months close to the
annual control exactly rather than approximately.

The GAS streams ride a PRODUCTION PROXY since rc20, and the grade says what that means.
OGRA publishes the sector-wise gas table annually and nothing monthly, so no monthly
industrial gas quantity is observed. What IS observed monthly is PRODUCTION: the PBS QIM
panel (all nine fiscal editions parsed, each row closed against its own printed annual
total) carries two gas-intensive industry series - steel billets/ingots and glass sheets -
and cement's own production months. The General Industry gas stream takes the unweighted
mean of the two industry shapes; the Cement gas stream takes cement's own shape. Both are
T3, not T2, on the reviewer's own distinction: production is a proxy for fuel, and QIM
measures output, never fuel burned. The unweighted mean is a declared choice, not a
weighting claim - no gas-consumption weights are held. Years the QIM panel does not
reach stay flat T4; monthly gas SALES by sector remain the named acquisition
(OGRA/SNGPL/SSGC request), which would move these rows to T2.

Usage:  python3 -m pkinv.sectors.industry.monthly
Writes: outputs/industry_monthly_2024.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.industry import combustion
from pkinv.sectors.industry.data import IndustryData
from pkinv.activity.store import read_rows

PANEL = asset_path(DATA, "activity", "transport", "ocac_sectoral_provincial.csv")
FY_START = 2023          # FY2023-24: 2023-07 .. 2024-06
SECTOR_ROW = "Total Industry"
NATIONAL = "PAKISTAN"


def _panel_rows():
    return [r for r in read_rows(PANEL, comments=False) if r["sector_row"] == SECTOR_ROW and r["area"] == NATIONAL]


def monthly_tonnes(product, fy_start=FY_START):
    """{month: tonnes} for one OCAC product code, and {month: T-class}.

    The first month of the fiscal year is taken from its direct monthly edition where one
    exists; every later month is the difference of consecutive cumulative columns. A
    cumulative series that ever goes backwards would mean the editions disagree with each
    other, so a negative difference RAISES rather than being clipped to zero.
    """
    months = ["%s-%02d" % (fy_start, m) for m in range(7, 13)] + \
             ["%s-%02d" % (fy_start + 1, m) for m in range(1, 7)]
    direct, cumulative = {}, {}
    for r in _panel_rows():
        if r["month"] not in months or r["product"] != product:
            continue
        (direct if r["report_kind"] == "monthly" else cumulative)[r["month"]] = \
            float(r["tonnes"])

    out, method, running = {}, {}, 0.0
    for i, m in enumerate(months):
        if m in cumulative:
            value, cls = cumulative[m] - running, "T2"
            running = cumulative[m]
        elif m in direct:
            value, cls = direct[m], "T1"
            running += value
        else:
            raise KeyError("OCAC has no %s edition covering %s for %s"
                           % (SECTOR_ROW, m, product))
        if i == 0:
            # The first month of a fiscal year is never a difference: its cumulative
            # column IS the month. Published figure, no reconstruction.
            cls = "T1"
        if value < 0:
            raise ValueError(
                "OCAC cumulative %s goes backwards at %s (%.0f t): the editions "
                "disagree and the month cannot be recovered by differencing"
                % (product, m, value))
        out[m], method[m] = value, cls
    return out, method


def _key(month):
    """OCAC's YYYY-MM -> the inventory's YYYYMM."""
    return month.replace("-", "")


def profiles(data=None, fy_start=FY_START):
    """({product: {YYYYMM: share}}, {product: {YYYYMM: T-class}}).

    Liquid products carry their reconstructed shape; the gas streams are not in here -
    they take the flat profile in rows(), which is where their T4 is declared.
    """
    data = data or IndustryData()
    shares, methods = {}, {}
    for code in data.liquid_products():
        try:
            tonnes, method = monthly_tonnes(code, fy_start)
        except KeyError:
            # The panel opens partway through this inventory's window. A product it does not
            # reach is simply absent from the result and takes the flat profile in rows(),
            # rather than raising past every other stream this layer can still serve.
            continue
        shares[code] = core_monthly.normalise({_key(m): v for m, v in tonnes.items()})
        methods[code] = {_key(m): c for m, c in method.items()}
    return shares, methods


def _code_of(component):
    """OCAC product code behind a component, or None for the gas streams."""
    for code, label in combustion.LIQUID_LABELS.items():
        if component["subitem"].startswith(label + " "):
            return code
    return None


def _gas_proxies(fy_start=FY_START):
    """(general-industry proxy profile, cement proxy profile), or (None, None).

    Both from the QIM panel; each item's own-year months only (the panel contract:
    no shape is ever borrowed across years)."""
    from pkinv.core import pbs_qim
    items = ("billets_ingots", "glass_plates_sheets")
    if not all(pbs_qim.covers(item, fy_start) for item in items):
        general = None
    else:
        profs = [pbs_qim.profile(item, fy_start) for item in items]
        keys = sorted(profs[0])
        general = core_monthly.normalise(
            {k: sum(p[k] for p in profs) / len(profs) for k in keys})
    cement = (core_monthly.normalise(pbs_qim.profile("cement", fy_start))
              if pbs_qim.covers("cement", fy_start) else None)
    return general, cement


def rows(data=None, components=None, fy_start=FY_START):
    """(annual components, month rows) - core.registry's monthly-layer contract."""
    data = data or IndustryData()
    if components is None:
        # BOTH component families, the same set the engine builds. rc46 Wave 2's solid
        # streams were invisible here for one build - this default recomputed combustion
        # alone, and 13.6 Mt would have been absent from the 108-month panel while present
        # in the annual atom, which the closure identity refuses.
        from pkinv.sectors.industry import solid_fuels
        components, _memo = combustion.compute(data)
        solid, _solid_memo = solid_fuels.compute(data)
        components = components + solid
    from pkinv.core.components import enrich_co2e
    enrich_co2e(components)

    shares, methods = profiles(data, fy_start)
    # Days-weighted, not equal twelfths: these streams declare no seasonality, which
    # is a claim about the SOURCE and not a licence to mis-divide the calendar.
    flat = core_monthly.days_weighted_profile(fy_start)
    gas_proxy, cement_proxy = _gas_proxies(fy_start)

    def _served(c):
        code = _code_of(c)
        return code if code in shares else None

    def _gas_profile(c):
        """The production-proxy shape for a gas stream, or None."""
        if c["subitem"].startswith("Cement gas"):
            return cement_proxy
        # rc46 Wave 2: cement-sector COAL rides the same QIM cement-production proxy as
        # cement gas, for the same reason and at the same T3 - output is what QIM observes,
        # not fuel. Brick coal deliberately does NOT take a proxy: the kiln firing season is
        # real (winter-skewed) and unmodelled, and borrowing cement's shape for it would be
        # the borrowed-seasonality defect the QIM round measured at half-overstated.
        if c["subitem"].startswith("Cement-sector coal"):
            return cement_proxy
        if c["subitem"].startswith("General Industry gas"):
            return gas_proxy
        return None

    def profile_for(c):
        code = _served(c)
        if code:
            return shares[code]
        gp = _gas_profile(c)
        return gp if gp is not None else flat

    def method_for(c, month):
        code = _served(c)
        if code:
            return methods[code][month]
        return "T3" if _gas_profile(c) is not None else "T4"

    def basis_for(c):
        if _served(c):
            return ("OCAC monthly editions, %s customer class: direct where published, "
                    "otherwise cumulative differencing" % SECTOR_ROW)
        if _code_of(c):
            return ("flat: the OCAC panel does not reach this fiscal year for this product, "
                    "and one year's sales shape is not carried to another")
        if _gas_profile(c) is not None:
            if c["subitem"].startswith(("Cement gas", "Cement-sector coal")):
                return ("PBS QIM cement production months as a production PROXY for this "
                        "stream's fuel (T3: output, not fuel, is what QIM observes)")
            return ("unweighted mean of the PBS QIM billets/ingots and glass-sheet "
                    "production shapes as a production PROXY for utility gas (T3: "
                    "output, not fuel; no gas-consumption weights are held, so the "
                    "mean is a declared choice rather than a weighting claim)")
        if c["subitem"].startswith("Brick-kiln coal"):
            return ("DECLARED FLAT, AND KNOWN WRONG IN SHAPE: brick kilns fire seasonally "
                    "(winter-skewed, monsoon-suppressed) and no monthly kiln statistic is "
                    "held; days-weighted twelfths by assertion, with the season named in "
                    "the deferral list rather than borrowed from another industry's shape")
        return ("DECLARED FLAT: no monthly industrial gas statistic was obtained here and "
                "the QIM panel does not reach this fiscal year; equal twelfths by "
                "assertion, not by observation")

    out = []
    for c in components:
        out.extend(core_monthly.apply_profile([c], None, fy_start, method_for,
                                              profile_for=profile_for, basis=basis_for(c)))
    core_monthly.check_closure(out, components)
    return components, out


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    data = IndustryData()
    components, out = rows(data)

    path = asset_path(OUTPUTS, "industry_monthly_%d.csv" % data.year)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["category", "subitem", "gas", "month", "share",
                                          "emissions_Gg", "co2e_Mt_AR5", "co2e_Mt_AR6",
                                          "temporal_method", "basis"])
        w.writeheader()
        for r in out:
            w.writerow({**r, "share": round(r["share"], 6),
                        "emissions_Gg": round(r["emissions_Gg"], 4),
                        "co2e_Mt_AR5": round(r["co2e_Mt_AR5"], 6),
                        "co2e_Mt_AR6": round(r["co2e_Mt_AR6"], 6)})

    totals = core_monthly.month_totals(out)
    liquid = core_monthly.month_totals([r for r in out if _code_of(r)])
    hi, lo = max(totals, key=totals.get), min(totals, key=totals.get)
    lhi, llo = max(liquid, key=liquid.get), min(liquid, key=liquid.get)
    classes = {}
    for r in out:
        classes[r["temporal_method"]] = classes.get(r["temporal_method"], 0.0) \
            + r["co2e_Mt_AR5"]
    grand = sum(classes.values())
    print("Industry monthly (FY%d-%02d): %d rows, annual closure exact -> %s"
          % (FY_START, (FY_START + 1) % 100, len(out), path))
    print("  sector    peak %s %.4f Mt, trough %s %.4f Mt (ratio %.2f)"
          % (hi, totals[hi], lo, totals[lo], totals[hi] / totals[lo]))
    print("  liquids   peak %s %.4f Mt, trough %s %.4f Mt (ratio %.2f)"
          % (lhi, liquid[lhi], llo, liquid[llo], liquid[lhi] / liquid[llo]))
    print("  by class  " + ", ".join("%s %.0f%%" % (k, 100 * v / grand)
                                     for k, v in sorted(classes.items())))


if __name__ == "__main__":
    main()
