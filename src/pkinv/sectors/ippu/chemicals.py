"""Reusable IPCC calculation kernels for chemical-industry modules.

These functions do not decide that a Pakistani activity exists.  The activity ledger and
completeness gate make that decision; the kernels are executable now so plant data can be
loaded without changing accounting code later.
"""
from __future__ import annotations

from pkinv.core.uncertainty import product
from pkinv.sectors.ippu.material_flows import ammonia_carbon_balance


def activation_audit(evidence_rows, period_end_year, period_basis="calendar"):
    """Summarize plant evidence and enforce the national activation gate.

    A category becomes active only through an explicit ``model_ready_national`` record.
    Partial production, capacity or abatement evidence remains visible but cannot enter the
    registered inventory merely because a calculation kernel exists.
    """
    output = []
    specifications = {
        "2.B.1": ("Ammonia production", "complete plant NH3, feedstock and CO2 recovery"),
        "2.B.2": ("Nitric acid production",
                  "complete 100%-acid output, technology and annual abatement operation"),
    }
    for code, (category, missing) in specifications.items():
        category_rows = [row for row in evidence_rows
                         if code in row["ipcc_code"].split(";")]
        target = [row for row in category_rows
                  if int(row["period_end_year"]) == int(period_end_year)
                  and row["period_basis"] == period_basis]
        production = sum(float(row["production_t"].strip()) for row in target
                         if row.get("production_t", "").strip())
        # The activity CSV's column is evidence_status - schemas.validate_chemical_activity
        # guards that key, and this gate must read the same one. It read "status" from
        # Round 7 to Round 11, a key no activity row carries, so the gate could never open;
        # correct-by-accident while nothing was model-ready, and tested only for the
        # negative case, which is how it stayed invisible.
        activated = any(row.get("evidence_status") == "model_ready_national"
                        for row in target)
        output.append({
            "period_end_year": int(period_end_year), "period_basis": period_basis,
            "ipcc_code": code,
            "category": category, "target_year_evidence_rows": len(target),
            "all_year_evidence_rows": len(category_rows),
            "reported_target_year_production_t": production,
            "identified_target_year_facilities": len({row["facility_id"] for row in target}),
            "national_estimate_activated": activated,
            "gate_status": "E" if activated else "NE",
            "remaining_evidence": "" if activated else missing,
        })
    return output


TIER_REQUIREMENTS = {
    "2.B.1": (
        (1, "national ammonia production, or documented plant capacity times utilization, "
            "plus urea production for the recovery term"),
        (2, "complete plant NH3 output and CO2 recovery for every census plant"),
        (3, "actual plant fuel and feedstock inputs and their carbon content"),
    ),
    "2.B.2": (
        (1, "national 100%-acid output"),
        (2, "complete plant acid output and process technology"),
        (3, "plant-measured emission factor and annual abatement operation"),
    ),
}

NOT_ACTIVATED = "evidence ready at this tier; not activated; reconcile before activating"


def tier_readiness(evidence_rows, national_inputs, period_end_year,
                   period_basis="calendar"):
    """Per-tier evidence readiness for the chemical categories. Diagnostic only.

    The single-tier gate above demanded complete plant feedstock and recovery records
    before ANY estimate could exist, which conflated two different questions: whether a
    method's inputs are on hand, and whether its answer can be trusted. This table answers
    the first, per IPCC tier. It never answers the second: readiness at any tier does NOT
    activate a national estimate - activation still requires an explicit
    model_ready_national evidence row, and while the four independent activity pathways in
    the reconciliation disagree, no such row should be written.

    national_inputs carries the tier-1 inputs, which are national rather than plant
    quantities: national_nh3_production_t, capacity_based_nh3_t, urea_production_t,
    national_hno3_production_t.
    """
    def filled(row, column):
        return bool(str(row.get(column, "")).strip())

    output = []
    for code, tiers in TIER_REQUIREMENTS.items():
        category_rows = [row for row in evidence_rows
                         if code in row["ipcc_code"].split(";")]
        target = [row for row in category_rows
                  if int(row["period_end_year"]) == int(period_end_year)
                  and row["period_basis"] == period_basis]
        census = {row["facility_id"] for row in category_rows}
        with_production = {row["facility_id"] for row in target
                           if filled(row, "production_t")}
        with_recovery = {row["facility_id"] for row in target
                         if filled(row, "recovered_to_urea_t")}
        with_carbon = {row["facility_id"] for row in target
                       if filled(row, "feedstock_consumption_t")
                       and filled(row, "gross_process_co2_t")}
        for tier, requirement in tiers:
            if code == "2.B.1":
                if tier == 1:
                    activity = (bool(national_inputs.get("national_nh3_production_t"))
                                or bool(national_inputs.get("capacity_based_nh3_t")))
                    recovery = bool(national_inputs.get("urea_production_t"))
                    ready = activity and recovery
                    held = "; ".join(part for part, have in (
                        ("national NH3 production", bool(
                            national_inputs.get("national_nh3_production_t"))),
                        ("capacity-based NH3", bool(
                            national_inputs.get("capacity_based_nh3_t"))),
                        ("urea production", recovery)) if have)
                    missing = "" if ready else requirement
                elif tier == 2:
                    ready = bool(census) and census == with_production == with_recovery
                    held = ("%d of %d census plants with production, %d with recovery"
                            % (len(with_production), len(census), len(with_recovery)))
                    missing = "" if ready else requirement
                else:
                    ready = bool(census) and census == with_carbon
                    held = ("%d of %d census plants with feedstock and gross CO2"
                            % (len(with_carbon), len(census)))
                    missing = "" if ready else requirement
            else:
                if tier == 1:
                    ready = bool(national_inputs.get("national_hno3_production_t"))
                    held = "national 100%-acid output" if ready else ""
                    missing = "" if ready else requirement
                elif tier == 2:
                    ready = bool(census) and census == with_production
                    held = ("%d of %d census plants with acid output"
                            % (len(with_production), len(census)))
                    missing = "" if ready else requirement
                else:
                    # Abatement operation lives outside the activity schema entirely;
                    # this tier cannot be ready until that evidence has a column.
                    ready = False
                    held = "CDM monitoring proves historical abatement only"
                    missing = requirement
            output.append({
                "period_end_year": int(period_end_year), "period_basis": period_basis,
                "ipcc_code": code, "tier": tier, "requirement": requirement,
                "evidence_held": held, "evidence_missing": missing,
                "tier_ready": ready,
                "activation_status": NOT_ACTIVATED if ready else "not ready",
            })
    return output


def period_product_register(evidence_rows):
    """Summarize evidence without ever combining fiscal and calendar periods."""
    groups = {}
    for row in evidence_rows:
        key = (int(row["period_end_year"]), row["period_basis"], row["product"])
        group = groups.setdefault(key, {"facilities": set(), "production_t": 0.0,
                                        "reported_rows": 0, "missing_rows": 0})
        group["facilities"].add(row["facility_id"])
        value = str(row.get("production_t") or "").strip()
        if value:
            group["production_t"] += float(value)
            group["reported_rows"] += 1
        else:
            group["missing_rows"] += 1
    return [{"period_end_year": year, "period_basis": basis, "product": product,
             "identified_facilities": len(values["facilities"]),
             "reported_production_rows": values["reported_rows"],
             "missing_activity_rows": values["missing_rows"],
             "reported_production_t": values["production_t"],
             "activation_status": "evidence only; not a national estimate"}
            for (year, basis, product), values in sorted(groups.items())]


def ammonia_component(production_kt, gross_ef_t_co2_per_t_nh3,
                      recovered_to_urea_kt=0.0, recovered_other_kt=0.0,
                      permanent_storage_kt=0.0, activity_uncert_pct=5.0,
                      ef_uncert_pct=10.0):
    gross = production_kt * gross_ef_t_co2_per_t_nh3
    ledger = ammonia_carbon_balance(gross, recovered_to_urea_kt,
                                    recovered_other_kt, permanent_storage_kt)
    return {
        "category": "Ammonia production", "subitem": "Ammonia process CO2",
        "gas": "CO2", "emissions_Gg": ledger["emitted_co2_kt"],
        "uncert_pct": product(activity_uncert_pct, ef_uncert_pct),
    }, ledger


def nitric_acid_component(production_kt_100pct_acid, ef_kg_n2o_per_t,
                          abated_share=0.0, destruction_efficiency=0.0,
                          abatement_utilisation=0.0, activity_uncert_pct=5.0,
                          ef_uncert_pct=30.0):
    fractions = (abated_share, destruction_efficiency, abatement_utilisation)
    if production_kt_100pct_acid < 0 or any(x < 0 or x > 1 for x in fractions):
        raise ValueError("invalid nitric-acid activity or abatement fraction")
    gross_n2o_kt = production_kt_100pct_acid * ef_kg_n2o_per_t / 1000.0
    destroyed = gross_n2o_kt * abated_share * destruction_efficiency * abatement_utilisation
    return {
        "category": "Nitric acid production", "subitem": "Nitric-acid process N2O",
        "gas": "N2O", "emissions_Gg": gross_n2o_kt - destroyed,
        "uncert_pct": product(activity_uncert_pct, ef_uncert_pct),
    }, {"gross_n2o_kt": gross_n2o_kt, "destroyed_n2o_kt": destroyed,
        "emitted_n2o_kt": gross_n2o_kt - destroyed}


def carbonate_component(category, subitem, activity_kt, ef_t_co2_per_t,
                        activity_uncert_pct=10.0, ef_uncert_pct=15.0):
    if activity_kt < 0 or ef_t_co2_per_t < 0:
        raise ValueError("carbonate activity and factor must be non-negative")
    return {"category": category, "subitem": subitem, "gas": "CO2",
            "emissions_Gg": activity_kt * ef_t_co2_per_t,
            "uncert_pct": product(activity_uncert_pct, ef_uncert_pct)}
