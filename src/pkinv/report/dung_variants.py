"""National consequences of each destination for the unresolved dung residual.

The rc2 review's section 4: under the survey reading of household dung (configuration S,
THE REFERENCE since rc67), most of the diverted air-dry cake has no observed
destination, and until the residual is assigned somewhere the reference leaves a
declared mass, and the nitrogen in it, in no emitting account. Candidates differ in kind --
non-household combustion emits the same CH4/N2O as L, return to manure management raises
MMS N2O and the soils application, field application raises soils N2O directly -- so one
letter cannot carry the question. This module prices each destination declared in
data/scenario_variants.csv and publishes the national total it implies, with NO
probabilities: conservation says the mass exists; it does not say where it went.

Everything is engine reuse or arithmetic over published outputs. The agriculture variants
recompute manure.compute and soils.compute on IN-MEMORY COPIES of InventoryData -- the
shared instance is never mutated, and the reference recomputation is asserted against the
published agriculture rollup before any variant is trusted. Conservation is asserted at
write time: every variant's household + destination + unresolved masses must sum to the
diverted control from the dung-fate ledger.

Usage:  python3 -m pkinv.report.dung_variants
Writes: outputs/national_dung_variants.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core.gwp import GWP
from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

TOLERANCE_MT = 0.0002        # air-dry Mt, one part in ~300,000 of the account


def _rows(path):
    return read_rows(path)


def registry():
    return _rows(asset_path(DATA, "scenario_variants.csv"))


def _co2e(components, gwp="AR5"):
    return sum(c["emissions_Gg"] * GWP[gwp][c["gas"]] / 1000.0 for c in components
               if c["gas"] in GWP[gwp])


def _gas_gg(components, gas):
    return sum(c["emissions_Gg"] for c in components if c["gas"] == gas)


def _agriculture(year, reference_year):
    """Agriculture's data for one fiscal-end year: the reference library at the
    reference year, the fiscal back-cast before it."""
    from pkinv.sectors.agriculture.ef_library import InventoryData
    if year == reference_year:
        return InventoryData()
    from pkinv.sectors.agriculture import fiscal_activity
    return fiscal_activity.data_for_fiscal_year(year)


def price(year=None):
    """Every destination of the unresolved dung for ONE fiscal-end year, priced.

    Returns the masses, the nitrogen, and for each destination the trace gases and the
    change in national CO2e relative to the reference of that year. No totals: the
    caller joins them, because the reference-year file and the nine-year product carry
    different ones.

      diverted    what agriculture removes from manure management as fuel, from that
                  year's own herd (combustion.dung_air_dry_kg, basis ledger)
      household   what the survey series has households burning (the reference)
      unresolved  the difference; never negative (dung_ledger raises if it is)

    The combustion destination scales that year's ledger dung stream by the unresolved
    share. The two agriculture destinations RE-RUN manure and soils for that year on
    copies: the diversion is reduced to what the survey supports and the freed share is
    redistributed over each herd's other systems, so volatile solids and nitrogen move
    together and nothing is added as a scalar."""
    from pkinv.sectors.agriculture import manure, soils
    from pkinv.sectors.residential import combustion, engine, timeseries
    from pkinv.sectors.residential.data import ResidentialData

    res_data = ResidentialData()
    year = res_data.year if year is None else int(year)
    agri = _agriculture(year, res_data.year)

    diverted = combustion.dung_air_dry_kg(res_data, agri, basis="ledger") / 1e9
    household = timeseries.dung_survey_air_dry_kg(year) / 1e9
    unresolved = diverted - household
    if unresolved < -TOLERANCE_MT:
        raise ValueError("FY%d: households are observed burning more dung (%.3f Mt) "
                         "than agriculture diverts (%.3f Mt)" % (year, household, diverted))
    share = unresolved / diverted
    diverted_n = sum(combustion.diverted_n_by_species(agri).values())

    # Configuration L's dung stream for this year: the reference-year ledger rows scaled
    # by this year's diverted mass. Every combustion-type destination emits share x these.
    ledger_ref = combustion.dung_air_dry_kg(res_data, basis="ledger") / 1e9
    scale = diverted / ledger_ref
    dung = [c for c in engine.build_components(res_data, dung_basis="ledger")
            if c["subitem"].startswith("Dung")]
    dung_ch4 = _gas_gg(dung, "CH4") * scale
    dung_n2o = _gas_gg(dung, "N2O") * scale
    dung_memo = scale * sum(
        m["emissions_Gg"] for m in engine.memo_items(res_data, dung_basis="ledger")
        if "dung" in m["item"].lower() and m["gas"] == "CO2")

    manure_ref, npools_ref = manure.compute(agri)
    soils_ref = soils.compute(agri, npools_ref)
    ref_ag = _co2e(manure_ref) + _co2e(soils_ref)

    def ag_with_scaled_burned_fuel(factor):
        """Agriculture's manure+soils co2e with burned_fuel scaled by `factor` and the
        freed share redistributed over each herd's existing other systems."""
        copy = _agriculture(year, res_data.year)
        for species in ("cattle", "buffalo"):
            shares = copy.mms[species]
            freed = shares["burned_fuel"] * (1.0 - factor)
            shares["burned_fuel"] *= factor
            rest = sum(v for k, v in shares.items() if k != "burned_fuel")
            for k in [k for k in shares if k != "burned_fuel"]:
                shares[k] += freed * shares[k] / rest
        comps_m, npools = manure.compute(copy)
        comps_s = soils.compute(copy, npools)
        delta_ch4 = _gas_gg(comps_m + comps_s, "CH4") - _gas_gg(manure_ref + soils_ref,
                                                                "CH4")
        delta_n2o = _gas_gg(comps_m + comps_s, "N2O") - _gas_gg(manure_ref + soils_ref,
                                                                "N2O")
        return _co2e(comps_m) + _co2e(comps_s) - ref_ag, delta_ch4, delta_n2o

    def soils_with_extra_fon(extra_n_kg):
        """Soils with `extra_n_kg` more organic N applied, its field volatilisation included.

        The reference pools carry the organic field releases (field_volat_NH3_N / _NOx_N) that
        manure.compute derived for the reference N state, and soils.volatilised_n uses them
        whenever they are present. Adding N to FON alone therefore raised direct and leaching
        N2O but left volatilisation, and its indirect N2O, at the reference value (found by the
        external audit of 21 October 2026). The added N now volatilises at the reference's own
        organic field rate - released N over applied FON - under whichever method produced the
        pools; that treats the residual cake N like average applied manure N (no TAN lost while
        the cake dried), which the registry note states."""
        npools = dict(npools_ref)
        fon_ref = npools_ref["FON_N"]
        npools["FON_N"] = fon_ref + extra_n_kg
        for key in ("field_volat_NH3_N", "field_volat_NOx_N"):
            if key in npools_ref:
                pools = dict(npools_ref[key])
                rate = pools.get("organic", 0.0) / fon_ref if fon_ref else 0.0
                pools["organic"] = pools.get("organic", 0.0) + extra_n_kg * rate
                npools[key] = pools
        comps_s = soils.compute(agri, npools)
        return (_co2e(comps_s) - _co2e(soils_ref),
                _gas_gg(comps_s, "N2O") - _gas_gg(soils_ref, "N2O"))

    residual_n_kg = diverted_n * share
    ag_delta, ag_dch4, ag_dn2o = ag_with_scaled_burned_fuel(household / diverted)
    fon_delta, fon_dn2o = soils_with_extra_fon(residual_n_kg)
    burn_delta = (dung_ch4 * share * GWP["AR5"]["CH4"]
                  + dung_n2o * share * GWP["AR5"]["N2O"]) / 1000.0

    variants = {
        "S_household_only_unallocated": {
            "destination": "declared unresolved stock (no emissions pathway)",
            "destination_Mt": 0.0, "unresolved_Mt": unresolved,
            "ch4_Gg": 0.0, "n2o_Gg": 0.0, "biogenic_co2_memo_Gg": 0.0, "delta": 0.0},
        "S_residual_nonhousehold_combustion": {
            "destination": "non-household combustion (1.A.4.a-type), same fuel chain",
            "destination_Mt": unresolved, "unresolved_Mt": 0.0,
            "ch4_Gg": dung_ch4 * share, "n2o_Gg": dung_n2o * share,
            "biogenic_co2_memo_Gg": dung_memo * share, "delta": burn_delta},
        "S_residual_return_to_manure": {
            "destination": "manure management (MMS N2O + FON application to soils)",
            "destination_Mt": unresolved, "unresolved_Mt": 0.0,
            "ch4_Gg": ag_dch4, "n2o_Gg": ag_dn2o, "biogenic_co2_memo_Gg": 0.0,
            "delta": ag_delta},
        "S_residual_field_application": {
            "destination": "field application (direct + indirect soils N2O on the "
                           "residual nitrogen)",
            "destination_Mt": unresolved, "unresolved_Mt": 0.0,
            "ch4_Gg": 0.0, "n2o_Gg": fon_dn2o, "biogenic_co2_memo_Gg": 0.0,
            "delta": fon_delta},
        "S_revised_diversion_fraction": {
            "destination": "the diversion revised down: the residual never left the "
                           "herd's ordinary systems",
            "destination_Mt": unresolved, "unresolved_Mt": 0.0,
            "ch4_Gg": ag_dch4, "n2o_Gg": ag_dn2o, "biogenic_co2_memo_Gg": 0.0,
            "delta": ag_delta},
    }
    return {"year": year, "diverted_Mt": diverted, "household_Mt": household,
            "unresolved_Mt": unresolved, "share_unresolved": share,
            "diverted_N_kt": diverted_n / 1e6,
            "household_N_kt": diverted_n * (1.0 - share) / 1e6,
            "unresolved_N_kt": residual_n_kg / 1e6,
            "reference_ag_recomputed": ref_ag, "variants": variants}


def build():
    """The reference year's variants with the national total each implies."""
    priced = price()
    diverted, household = priced["diverted_Mt"], priced["household_Mt"]
    reference_total = _published_total("national_all_sectors.csv")
    ledger_total = _published_total("national_all_sectors_ledger.csv")

    out = []
    for reg in registry():
        vid = reg["variant_id"]
        v = priced["variants"][vid]
        out.append({
            "variant_id": vid, "parent_axis": reg["parent_axis"],
            "description": reg["description"],
            "diverted_Mt": round(diverted, 4),
            "household_Mt": round(household, 4),
            "destination_Mt": round(v["destination_Mt"], 4),
            "unresolved_Mt": round(v["unresolved_Mt"], 4),
            "destination": v["destination"],
            "ch4_Gg": round(v["ch4_Gg"], 4), "n2o_Gg": round(v["n2o_Gg"], 4),
            "biogenic_co2_memo_Gg": round(v["biogenic_co2_memo_Gg"], 2),
            "delta_vs_S_Mt_co2e_AR5": round(v["delta"], 4),
            "national_total_Mt_co2e_AR5": round(reference_total + v["delta"], 5),
            "machinery": reg["machinery"], "note": reg["note"]})

    # CONSERVATION, the reviewer's gate, asserted over the published rows: every
    # variant's masses partition the diverted control exactly.
    for r in out:
        if abs(r["household_Mt"] + r["destination_Mt"] + r["unresolved_Mt"]
               - r["diverted_Mt"]) > TOLERANCE_MT:
            raise ValueError("%s does not conserve the diverted mass" % r["variant_id"])

    # The base variant is the published reference total to the last digit, or the
    # variants file is claiming a second national number.
    base = next(r for r in out if r["variant_id"] == "S_household_only_unallocated")
    if abs(base["national_total_Mt_co2e_AR5"] - round(reference_total, 5)) > 1e-9:
        raise ValueError("the base variant does not equal the published reference total")
    # Burning the whole residual outside households is configuration L by another
    # name, so it must land on the published L total. If it does not, the two products
    # disagree about what the diverted dung is worth.
    burned = next(r for r in out
                  if r["variant_id"] == "S_residual_nonhousehold_combustion")
    if abs(burned["national_total_Mt_co2e_AR5"] - ledger_total) > 2e-5:
        raise ValueError("burning the residual gives %.5f, configuration L %.5f"
                         % (burned["national_total_Mt_co2e_AR5"], ledger_total))

    diag = {"ledger_total": ledger_total, "survey_total": reference_total,
            "reference_ag_recomputed": priced["reference_ag_recomputed"]}
    return out, diag


def _published_total(name):
    for r in _rows(asset_path(OUTPUTS, name)):
        if r["row_kind"] == "national_total":
            return float(r["co2e_Mt_AR5"])
    raise KeyError(name)


FIELDS = ("variant_id", "parent_axis", "description", "diverted_Mt", "household_Mt",
          "destination_Mt", "unresolved_Mt", "destination", "ch4_Gg", "n2o_Gg",
          "biogenic_co2_memo_Gg", "delta_vs_S_Mt_co2e_AR5", "national_total_Mt_co2e_AR5",
          "machinery", "note")


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows, diag = build()
    path = asset_path(OUTPUTS, "national_dung_variants.csv")
    write_table(path, FIELDS, rows, lineterminator="\n")
    print("dung destination variants -> %s" % path)
    print("  reference (S) total %.5f; L total %.5f"
          % (diag["survey_total"], diag["ledger_total"]))
    for r in rows:
        print("  %-38s delta %+8.4f -> %10.5f Mt" %
              (r["variant_id"], r["delta_vs_S_Mt_co2e_AR5"],
               r["national_total_Mt_co2e_AR5"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
