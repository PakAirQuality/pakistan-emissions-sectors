"""Cement production (IPCC 2.A.1): process CO2 from calcination.

PROCESS EMISSIONS ONLY.  Fuel used to heat cement kilns belongs to Energy 1.A.2 (1A2)
and is excluded here.

THE REFERENCE ACTIVITY IS THE PRODUCER CENSUS (rc30, the eighteenth review's
re-base): all sixteen FY2023-24 producers now report actual clinker production -
Fecto's 651,048 t closed the census via the FY2025 annual report's comparative
table - so calcination activity is OBSERVED at the company grain and needs neither
a clinker fraction nor a trade correction. The Tier-1 model this replaces
(PBS QIM cement x a default clinker fraction, corrected for HS 252310 trade) is
retained in full as the named structural diagnostics ``qim_trade`` produces, with
the census-vs-model residuals published in the tier comparison; it is what IPCC
Equation 2.1 prescribes when production is NOT observed, which is no longer this
inventory's situation.
"""
from __future__ import annotations

import math

from pkinv.core.uncertainty import product
from pkinv.sectors.ippu import trade_evidence
from pkinv.sectors.ippu.data import REFERENCE_CEMENT_SOURCE
from pkinv.sectors.ippu.material_flows import check_cement_balance

CATEGORY = "Cement production"
PRODUCT = "Cement"


def clinker_kt(data, year=None, fraction=None, activity_source=REFERENCE_CEMENT_SOURCE):
    """Clinker contained in cement, before imports and exports are reconciled."""
    resolved_fraction = data.p("clinker_fraction") if fraction is None else float(fraction)
    return data.cement_activity_kt(activity_source, year) * resolved_fraction


def clinker_balance(data, year=None, activity_source=REFERENCE_CEMENT_SOURCE,
                    fraction=None, include_trade=True, stock_change_kt=0.0):
    """Solve IPCC's clinker balance for domestic clinker production.

    ``stock_change_kt`` is positive for a stock increase.  Public stock data have
    not been found, so the reference configuration reports zero transparently.
    """
    end_year = data.year if year is None else int(year)
    resolved_fraction = data.p("clinker_fraction") if fraction is None else float(fraction)
    if not 0 <= resolved_fraction <= 1:
        raise ValueError("clinker fraction must lie between zero and one")
    cement_kt = data.cement_activity_kt(activity_source, end_year)
    # The gate, not the accessor, decides whether this year HAS a trade term. It raises
    # rather than returning zero, because every arithmetic path downstream would consume a
    # zero happily and the quantity is unknown rather than small. What include_trade=False
    # produces is a screening calculation, never a valid configuration - see
    # trade_evidence.py and uncertainty.method_benchmarks.
    if include_trade:
        verdict = trade_evidence.require(end_year)
        imports_kt, exports_kt = verdict["import_kt"], verdict["export_kt"]
    else:
        verdict = None
        imports_kt = exports_kt = 0.0
    content_kt = cement_kt * resolved_fraction
    production_kt = content_kt - imports_kt + exports_kt + float(stock_change_kt)
    if production_kt < 0:
        raise ValueError("clinker balance implies negative production")
    balance = {
        "period_end_year": end_year, "period_basis": "fiscal",
        "cement_activity_kt": cement_kt, "cement_source": activity_source,
        "clinker_fraction": resolved_fraction,
        "clinker_in_cement_kt": content_kt,
        "clinker_imports_kt": imports_kt, "clinker_exports_kt": exports_kt,
        "stock_change_kt": float(stock_change_kt),
        "clinker_production_kt": production_kt,
        "trade_included": bool(include_trade),
        "trade_source": data.clinker_trade_source() if include_trade else "not included",
        # What the trade term IS, and what the configuration therefore counts as. A balance
        # that omits trade is retained for method benchmarking and screening; it is not a
        # member of the valid structural range, the reference configuration, the common-scope
        # trend or any national total.
        "trade_status": verdict["status"] if verdict else trade_evidence.ABSENT,
        "configuration_status": "valid" if include_trade else "screening_only",
        "stock_source": "no public FY2023-24 stock control; zero reference assumption",
    }
    check_cement_balance(balance)
    return balance


def _balance_uncertainty_pct(balance, activity_uncert_pct, fraction_uncert_pct,
                             trade_uncert_pct=10.0, stock_uncert_kt=0.0):
    content_abs = balance["clinker_in_cement_kt"] * product(
        activity_uncert_pct, fraction_uncert_pct) / 100.0
    export_abs = balance["clinker_exports_kt"] * trade_uncert_pct / 100.0
    import_abs = balance["clinker_imports_kt"] * trade_uncert_pct / 100.0
    absolute = math.sqrt(content_abs ** 2 + export_abs ** 2 + import_abs ** 2 +
                         stock_uncert_kt ** 2)
    return absolute / balance["clinker_production_kt"] * 100.0


def census_production(data, year=None):
    """The reference activity record: audited census clinker production, no model.

    Shaped like a balance for the writers that consume one, with the model's
    fields explicitly marked not-applicable rather than zero - a zero clinker
    fraction would read as a datum.
    """
    end_year = data.year if year is None else int(year)
    production_kt = data.census_clinker_kt(end_year)
    return {
        "period_end_year": end_year, "period_basis": "fiscal",
        "activity_basis": "producer_census",
        "cement_activity_kt": "", "cement_source": "16-company producer census",
        "clinker_fraction": "", "clinker_in_cement_kt": "",
        "clinker_imports_kt": "", "clinker_exports_kt": "",
        "stock_change_kt": "",
        "clinker_production_kt": production_kt,
        "trade_included": "not applicable: production observed directly",
        "trade_source": "not applicable",
        "trade_status": "not applicable",
        "configuration_status": "reference",
        "stock_source": "not applicable: no balance is solved",
    }


def census_implied_fraction(data):
    """The clinker-in-cement fraction the reference year's census itself implies,
    (census clinker - exports + imports) / cement, DERIVED from held data at every call.

    rc50: the IPCC blended-cement default 0.75 the back-years rode had no Pakistani evidence
    behind it; the audited 16-company census fixes FY2023-24 and, through the clinker
    balance, implies ~0.965 - GEM's per-plant substitution (30 of 32 at 0-5 percent)
    corroborates and IPCC's all-portland 0.95 brackets it. The registry carries the value
    as `clinker_fraction_census_implied` for the record; this derivation is authoritative
    and tests/test_cement_rebase.py holds the two together.
    """
    ref = data.year
    census_kt = data.census_clinker_kt(ref)
    cement_kt = data.cement_activity_kt(data.cement_activity_source(ref), ref)
    verdict = trade_evidence.require(ref)
    return (census_kt - verdict["export_kt"] + verdict["import_kt"]) / cement_kt


# The census total is a sum of sixteen audited annual-report figures. 5 percent is
# the same conservative activity band the QIM model carried - company reports are
# audited but the census's own movement fields (stocks, transfers) are unavailable,
# so the band prices boundary slack, not digit noise.
CENSUS_ACTIVITY_UNCERT_PCT = 5.0


def compute(data, year=None, clinker_override=None,
            activity_source=REFERENCE_CEMENT_SOURCE, include_trade=True,
            stock_change_kt=0.0):
    """Return the census-based 2.A.1 component, with the model balance as memo.

    The memo carries BOTH records: the census reference (first) and the
    trade-corrected Tier-1 model at the reference fraction (second, a named
    diagnostic) - the writers publish the pair and the tier comparison prices
    their residual.
    """
    if clinker_override not in (None, "portland"):
        raise ValueError("clinker_override must be None or 'portland', not %r" %
                         (clinker_override,))
    fraction_param = ("clinker_fraction_portland" if clinker_override == "portland"
                      else "clinker_fraction")
    fraction = data.p(fraction_param)
    model_balance = clinker_balance(data, year, activity_source, fraction,
                                    include_trade, stock_change_kt)
    ef = data.efv("ippu_cement", "Clinker")
    try:
        census = census_production(data, year)
    except ValueError:
        # rc50: the census is held for the reference period only. Earlier fiscal years ride
        # the clinker balance at the CENSUS-IMPLIED fraction (census_implied_fraction), not
        # the IPCC blended default 0.75 - the 0.75 series manufactured a +9,027 kt method
        # break into the census year; at f* the FY2022-23 -> FY2023-24 step is +109 kt. The
        # 0.75 balance is kept as the named DIAGNOSTIC memo so the tier comparison still
        # prices what the change was. A declared series basis, one quantity for all eight
        # years (typed `persists`), never a silent extrapolation.
        f_star = census_implied_fraction(data)
        anchored = clinker_balance(data, year, activity_source, f_star,
                                   include_trade, stock_change_kt)
        anchored["configuration_status"] = "reference_model_census_anchored"
        model_balance["configuration_status"] = "diagnostic_model_ipcc_blended_default"
        activity_uncert = 5.0
        balance_uncert = _balance_uncertainty_pct(
            anchored, activity_uncert, data.pu("clinker_fraction_census_implied"))
        component = {
            "category": CATEGORY, "subitem": "Clinker calcination CO2", "gas": "CO2",
            "emissions_Gg": anchored["clinker_production_kt"] * ef,
            "uncert_pct": product(balance_uncert, data.efu("ippu_cement", "Clinker")),
        }
        return [component], [anchored, model_balance]
    model_balance["configuration_status"] = "diagnostic_model"
    component = {
        "category": CATEGORY, "subitem": "Clinker calcination CO2", "gas": "CO2",
        "emissions_Gg": census["clinker_production_kt"] * ef,
        "uncert_pct": product(CENSUS_ACTIVITY_UNCERT_PCT,
                              data.efu("ippu_cement", "Clinker")),
    }
    return [component], [census, model_balance]


def calendar_reconstruction(data, year, fraction=0.75, stock_change_kt=0.0):
    """Reconstruct a calendar-year Tier-1 cement estimate on matched QIM/trade data."""
    cement_kt = data.calendar_cement_activity_kt(year)
    imports_kt = data.annual_clinker_trade_kt("import", year)
    exports_kt = data.annual_clinker_trade_kt("export", year)
    content_kt = cement_kt * float(fraction)
    clinker_kt_value = content_kt - imports_kt + exports_kt + float(stock_change_kt)
    return {
        "calendar_year": int(year), "cement_activity_kt": cement_kt,
        "cement_source": "PBS QIM monthly physical output",
        "clinker_fraction": float(fraction), "clinker_imports_kt": imports_kt,
        "clinker_exports_kt": exports_kt, "stock_change_kt": float(stock_change_kt),
        "inferred_clinker_production_kt": clinker_kt_value,
        "co2_mt": clinker_kt_value * data.efv("ippu_cement", "Clinker") / 1000.0,
        "trade_source": data.annual_clinker_trade_source(year),
        "status": "matched-calendar public-data reconstruction",
    }
