"""Species-aware F-gas components and equipment-bank accounting."""
from __future__ import annotations

from pkinv.sectors.ippu.material_flows import fgas_bank_step


def validate_inventory_rows(rows):
    """Validate future species/application rows before the bank kernel is activated.

    New-equipment and servicing charge remain separate flows.  The generic bank kernel uses
    ``supplied_charge_t`` only after an application-specific timing rule has documented how
    those flows enter the equipment bank.
    """
    required = {"year", "species", "application", "imports_t", "exports_t",
                "domestic_production_t", "destruction_t", "new_equipment_charge_t",
                "servicing_charge_t", "manufacturing_loss_fraction",
                "operating_loss_fraction", "retired_charge_t", "recovery_fraction",
                "destruction_fraction_of_recovered", "source_reference", "data_status"}
    allowed_status = {"observed", "reported", "modelled", "imputed", "missing"}
    seen = set()
    for index, row in enumerate(rows, 2):
        missing = required - set(row)
        if missing:
            raise ValueError("HFC inventory row %d lacks %s" % (index, sorted(missing)))
        key = (int(row["year"]), row["species"], row["application"])
        if key in seen:
            raise ValueError("duplicate HFC bank row %r" % (key,))
        seen.add(key)
        if row["data_status"] not in allowed_status:
            raise ValueError("HFC inventory row %d has invalid data status" % index)
        for field in ("imports_t", "exports_t", "domestic_production_t", "destruction_t",
                      "new_equipment_charge_t", "servicing_charge_t", "retired_charge_t"):
            if float(row[field]) < 0:
                raise ValueError("HFC inventory row %d has negative %s" % (index, field))
        for field in ("manufacturing_loss_fraction", "operating_loss_fraction",
                      "recovery_fraction", "destruction_fraction_of_recovered"):
            if not 0 <= float(row[field]) <= 1:
                raise ValueError("HFC inventory row %d has invalid %s" % (index, field))
    return rows


def component(category, application, species, emitted_t, uncert_pct):
    if emitted_t < 0:
        raise ValueError("F-gas emissions cannot be negative")
    return {"category": category, "subitem": "%s - %s" % (application, species),
            "gas": species, "emissions_Gg": emitted_t / 1000.0,
            "uncert_pct": uncert_pct}


def run_bank(species, application, annual_rows, initial_bank_t=0.0):
    """Run ordered annual bank rows and return ledgers plus emission components."""
    bank = initial_bank_t
    ledgers, components = [], []
    for row in sorted(annual_rows, key=lambda value: int(value["year"])):
        ledger = fgas_bank_step(
            bank, float(row["supplied_charge_t"]),
            float(row["manufacturing_loss_fraction"]),
            float(row["operating_loss_fraction"]), float(row["retired_charge_t"]),
            float(row["recovery_fraction"]),
            float(row.get("destruction_fraction_of_recovered", 0.0)))
        ledger.update({"year": int(row["year"]), "species": species,
                       "application": application})
        ledgers.append(ledger)
        components.append(component("Product uses as substitutes for ODS", application,
                                    species, ledger["total_emissions_t"],
                                    float(row.get("uncert_pct", 50.0))))
        bank = ledger["bank_end_t"]
    return ledgers, components
