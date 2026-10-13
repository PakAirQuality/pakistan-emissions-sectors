"""Conserved industrial-material ledgers used by several IPPU categories."""
from __future__ import annotations


def cement_rows(balance):
    """Return the physical clinker bridge represented by ``balance``.

    Production + imports - exports - stock increase must equal the clinker ground into
    cement.  The calculation solves that identity for domestic clinker production.
    """
    return [
        {"material": "clinker", "flow": "clinker in cement", "amount_kt":
         balance["clinker_in_cement_kt"], "sign_in_production_balance": 1,
         "source_reference": balance["cement_source"]},
        {"material": "clinker", "flow": "imports for consumption", "amount_kt":
         balance["clinker_imports_kt"], "sign_in_production_balance": -1,
         "source_reference": balance["trade_source"]},
        {"material": "clinker", "flow": "exports", "amount_kt":
         balance["clinker_exports_kt"], "sign_in_production_balance": 1,
         "source_reference": balance["trade_source"]},
        {"material": "clinker", "flow": "stock increase", "amount_kt":
         balance["stock_change_kt"], "sign_in_production_balance": 1,
         "source_reference": balance["stock_source"]},
        {"material": "clinker", "flow": "inferred domestic production", "amount_kt":
         balance["clinker_production_kt"], "sign_in_production_balance": 0,
         "source_reference": "IPCC Equation 2.1/worksheet balance"},
    ]


def check_cement_balance(balance, tolerance=1e-9):
    available = (balance["clinker_production_kt"] + balance["clinker_imports_kt"] -
                 balance["clinker_exports_kt"] - balance["stock_change_kt"])
    residual = available - balance["clinker_in_cement_kt"]
    if abs(residual) > tolerance:
        raise AssertionError("cement clinker balance does not close: %r kt" % residual)
    return residual


def company_clinker_balance(row):
    """Audit one producer's clinker flow without imputing unreported fields.

    The balance is only evaluated when all stock and movement terms are reported.
    Production-only records remain valuable Tier-2 activity evidence but are marked
    incomplete rather than forced to close.
    """
    fields = ("opening_clinker_stock_t", "clinker_production_t",
              "clinker_purchases_t", "clinker_imports_t", "clinker_ground_t",
              "domestic_clinker_sales_t", "clinker_exports_t",
              "closing_clinker_stock_t")
    missing = [field for field in fields if row.get(field) is None]
    result = {"company": row["company"], "balance_complete": not missing,
              "missing_fields": "; ".join(missing)}
    if missing:
        result.update({"clinker_available_t": "", "clinker_outflows_t": "",
                       "closure_residual_t": ""})
        return result
    available = (row["opening_clinker_stock_t"] + row["clinker_production_t"] +
                 row["clinker_purchases_t"] + row["clinker_imports_t"])
    outflows = (row["clinker_ground_t"] + row["domestic_clinker_sales_t"] +
                row["clinker_exports_t"] + row["closing_clinker_stock_t"])
    result.update({"clinker_available_t": available, "clinker_outflows_t": outflows,
                   "closure_residual_t": available - outflows})
    return result


def ammonia_carbon_balance(gross_process_co2_kt, recovered_to_urea_kt=0.0,
                           recovered_other_kt=0.0, permanent_storage_kt=0.0):
    """Conserve process CO2 between atmosphere and named recovery destinations."""
    recovered = recovered_to_urea_kt + recovered_other_kt + permanent_storage_kt
    if min(gross_process_co2_kt, recovered_to_urea_kt, recovered_other_kt,
           permanent_storage_kt) < 0:
        raise ValueError("ammonia carbon flows cannot be negative")
    if recovered > gross_process_co2_kt + 1e-12:
        raise ValueError("recovered ammonia-process CO2 exceeds generation")
    emitted = gross_process_co2_kt - recovered
    return {
        "gross_process_co2_kt": gross_process_co2_kt,
        "recovered_to_urea_kt": recovered_to_urea_kt,
        "recovered_other_kt": recovered_other_kt,
        "permanent_storage_kt": permanent_storage_kt,
        "emitted_co2_kt": emitted,
        "closure_residual_kt": gross_process_co2_kt - recovered - emitted,
    }


def fgas_bank_step(bank_start_t, supplied_charge_t, manufacturing_loss_fraction,
                   operating_loss_fraction, retired_charge_t, recovery_fraction,
                   destruction_fraction_of_recovered=0.0):
    """One mass-conserving year of an equipment bank.

    Recovered gas that is not destroyed leaves this bank as a named reusable stream; it is
    not silently treated as either an emission or new charge.
    """
    values = (bank_start_t, supplied_charge_t, retired_charge_t)
    fractions = (manufacturing_loss_fraction, operating_loss_fraction, recovery_fraction,
                 destruction_fraction_of_recovered)
    if min(values) < 0 or any(f < 0 or f > 1 for f in fractions):
        raise ValueError("invalid F-gas bank input")
    manufacturing_emissions = supplied_charge_t * manufacturing_loss_fraction
    installed = supplied_charge_t - manufacturing_emissions
    pre_operation = bank_start_t + installed
    operating_emissions = pre_operation * operating_loss_fraction
    available_for_retirement = pre_operation - operating_emissions
    if retired_charge_t > available_for_retirement + 1e-12:
        raise ValueError("retired charge exceeds the operating bank")
    recovered = retired_charge_t * recovery_fraction
    destruction = recovered * destruction_fraction_of_recovered
    recovered_for_reuse = recovered - destruction
    retirement_emissions = retired_charge_t - recovered
    bank_end = available_for_retirement - retired_charge_t
    emissions = manufacturing_emissions + operating_emissions + retirement_emissions
    residual = (bank_start_t + supplied_charge_t - bank_end - emissions - destruction -
                recovered_for_reuse)
    if abs(residual) > 1e-9:
        raise AssertionError("F-gas bank does not close")
    return {
        "bank_start_t": bank_start_t, "supplied_charge_t": supplied_charge_t,
        "installed_charge_t": installed,
        "manufacturing_emissions_t": manufacturing_emissions,
        "operating_emissions_t": operating_emissions,
        "retired_charge_t": retired_charge_t,
        "retirement_emissions_t": retirement_emissions,
        "recovered_t": recovered, "destroyed_t": destruction,
        "recovered_for_reuse_t": recovered_for_reuse, "bank_end_t": bank_end,
        "total_emissions_t": emissions, "closure_residual_t": residual,
    }
