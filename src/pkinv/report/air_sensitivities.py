"""Consequential air structural cases, kept separate from conditional percentiles.

Each case changes one documented source assumption. National covered-source
totals retain the other sources exactly; no scenario is a confidence interval,
probability-weighted mixture, complete national total or mathematical bound.
"""
import collections
import csv
import math

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows
from pkinv.core import configurations as conf, sulfur
from pkinv.paths import OUTPUTS
from pkinv.report.air_annual import ATOMS_OUT, CORE7
from pkinv.report.air_uncertainty import composed_atoms

OUT = asset_path(OUTPUTS, "pakemis_air_structural_sensitivities.csv")
COAL_CASES = asset_path(OUTPUTS, "pakemis_coal_allocation_cases.csv")
NITROGEN_OUT = asset_path(OUTPUTS, "pakemis_nitrogen_partition_sensitivity.csv")
GHG_ATOMS = asset_path(OUTPUTS, "pakemis_ghg_configuration_atoms.csv")
NITROGEN_CASE = "nitrogen_all_volatilised_n_as_nh3_diagnostic"
FIELDS = ("period_id", "configuration_id", "pollutant", "scenario_id", "affected_sector",
          "reference_sector_Gg", "case_sector_Gg", "reference_covered_Gg", "case_covered_Gg",
          "change_Gg", "case_kind", "coverage_scope", "evidence", "limitations")
NITROGEN_FIELDS = ("period_id", "configuration_id", "scenario_id", "affected_sector",
                  "metric", "unit", "reference_sector_quantity", "case_sector_quantity",
                  "reference_covered_quantity", "case_covered_quantity", "change_quantity",
                  "reference_NH3_fraction", "case_NH3_fraction", "case_kind", "coverage_scope",
                  "max_nitrogen_closure_residual_kgN", "evidence", "limitations")
NITROGEN_EVIDENCE = ("native conserved manure/soil nitrogen ledger replay; adopted NH3-N share "
                     "0.95 replaced by 1.0 only for mixed volatilisation pathways")
NITROGEN_LIMITATIONS = ("chemical-attribution diagnostic, not a measured alternative or plausible bound; "
                        "no probability; all activities and other factors held; separately factored applied-N "
                        "soil NOx and burning NOx retained; unestimated sources excluded")


def nitrogen_partition_replay(year, method, nh3_fraction=None):
    """Fresh deterministic N ledger, shared by the AP and native GHG case.

    A TAN loss factor represents NH3-N; changing its attribution also changes
    inferred total volatilisation and surviving manure N. Replaying the ledger
    is necessary: scaling the final NH3/NOx rows cannot conserve those pools.
    """
    from pkinv.sectors.agriculture import air_pollutants, fiscal_activity, manure, run_inventory
    data = fiscal_activity.data_for_fiscal_year(year)
    data.nitrogen_method = method
    key = ("soils", "NH3_frac_of_volat")
    if nh3_fraction is not None:
        data.ef[key] = dict(data.ef[key], value=nh3_fraction)
    fraction = data.efv(*key)
    _, pools = manure.compute(data, method=method)
    residuals = [pools["excreted_N"] - sum(pools[k] for k in
                 ("managed_N", "FPRP_cattle_N", "FPRP_other_N", "diverted_N")),
                 pools["managed_N"] - sum(pools[k] for k in
                 ("FON_N", "volat_managed_N", "leach_managed_N", "n2_managed_N", "n2o_managed_N"))]
    max_residual = max(abs(r) for r in residuals)
    if max_residual > max(1e-5, pools["excreted_N"] * 1e-12):
        raise ValueError("nitrogen attribution case does not close: %g kg N" % max_residual)
    air = collections.defaultdict(float)
    for row in air_pollutants.compute(data):
        air[row["pollutant"]] += row["emissions_kt"]  # kt = Gg, native pollutant mass
    ghg = collections.defaultdict(float)
    for row in run_inventory.build_components(data, nitrogen_method=method):
        ghg[row["gas"]] += row["emissions_Gg"]
        for ar in ("AR5", "AR6"):
            ghg["CO2e_" + ar] += row["co2e_Mt_" + ar]
    return dict(air=air, ghg=ghg, pools=pools, fraction=fraction,
                max_residual=max_residual)


def nitrogen_partition_rows(atoms=None, ghg_atoms=None):
    """Return separately typed air and GHG diagnostics for all supported cases.

    Reference replays must match actual exported central records. Only the
    agriculture delta changes the covered national total; other sources and
    the configuration's household dung choice are retained exactly.
    """
    atoms = list(composed_atoms(read_rows(ATOMS_OUT) if atoms is None else atoms))
    air_total, air_sector = collections.defaultdict(float), collections.defaultdict(float)
    ghg_total, ghg_sector = collections.defaultdict(float), collections.defaultdict(float)
    for row in atoms:
        key = tuple(row[k] for k in ("period_id", "configuration_id", "pollutant"))
        air_total[key] += float(row["emissions_Gg"])
        if row["sector_id"] == "agriculture":
            air_sector[key] += float(row["emissions_Gg"])
    for row in read_rows(GHG_ATOMS) if ghg_atoms is None else ghg_atoms:
        if not row["gas"] or row["emission_native_mass"] == "":
            continue
        if row["native_unit"] != "Gg":
            raise ValueError("native GHG diagnostic requires Gg records")
        for metric, value in ((row["gas"], float(row["emission_native_mass"])),
                              ("CO2e_AR5", float(row["co2e_Mt_AR5"])),
                              ("CO2e_AR6", float(row["co2e_Mt_AR6"]))):
            key = row["period_id"], row["configuration_id"], metric
            ghg_total[key] += value
            if row["sector_id"] == "agriculture":
                ghg_sector[key] += value
    replays = {}
    air_rows, ghg_rows = [], []
    for pid, cfg in sorted({key[:2] for key in air_total}):
        year, method = 2000 + int(pid[-2:]), conf.nitrogen_method(cfg)
        if (year, method) not in replays:
            replays[year, method] = (nitrogen_partition_replay(year, method),
                                     nitrogen_partition_replay(year, method, 1.0))
        reference, case = replays[year, method]
        if reference["fraction"] != 0.95:
            raise ValueError("diagnostic reference NH3 share changed; review case definition")
        common = dict(period_id=pid, configuration_id=cfg, scenario_id=NITROGEN_CASE,
                      affected_sector="agriculture", case_kind="diagnostic_structural_case_no_probability",
                      coverage_scope="covered_sources_only", evidence=NITROGEN_EVIDENCE,
                      limitations=NITROGEN_LIMITATIONS)
        for pol in CORE7:
            key = pid, cfg, pol
            exported, replayed = air_sector[key], reference["air"][pol]
            if not math.isclose(exported, replayed, rel_tol=1e-9, abs_tol=1e-4):
                raise ValueError("air nitrogen reference differs from export %r: %g vs %g" % (key, replayed, exported))
            delta = case["air"][pol] - replayed
            air_rows.append(dict(common, pollutant=pol, reference_sector_Gg=exported,
                                 case_sector_Gg=exported + delta, reference_covered_Gg=air_total[key],
                                 case_covered_Gg=air_total[key] + delta, change_Gg=delta))
        for metric in ("CO2", "CH4", "N2O", "CO2e_AR5", "CO2e_AR6"):
            key = pid, cfg, metric
            if key not in ghg_total:
                raise ValueError("missing GHG covered reference %r" % (key,))
            exported, replayed = ghg_sector[key], reference["ghg"][metric]
            if not math.isclose(exported, replayed, rel_tol=1e-9, abs_tol=1e-4):
                raise ValueError("GHG nitrogen reference differs from export %r: %g vs %g" % (key, replayed, exported))
            delta = case["ghg"][metric] - replayed
            ghg_rows.append(dict(common, metric=metric,
                                 unit="Mt_CO2e" if metric.startswith("CO2e") else "Gg",
                                 reference_sector_quantity=exported, case_sector_quantity=exported + delta,
                                 reference_covered_quantity=ghg_total[key],
                                 case_covered_quantity=ghg_total[key] + delta, change_quantity=delta,
                                 reference_NH3_fraction=reference["fraction"], case_NH3_fraction=case["fraction"],
                                 max_nitrogen_closure_residual_kgN=max(reference["max_residual"], case["max_residual"])))
    return air_rows, ghg_rows


def road_ratio(atom, endpoint, factors, bridge, sulfur_cases):
    """Replay a factor endpoint while retaining the same class/fuel activity."""
    _, cls, fuel, process = atom["source_class_id"].split(":", 3)
    pol = atom["pollutant"]
    if pol == "SO2":
        central, low, high = sulfur_cases[fuel]
        return (low if endpoint == "low" else high) / central
    cat, efuel, _proxy = bridge[(cls, fuel)]
    key_pol = "PM2.5" if pol == "BC" else pol
    key = (process, cat, efuel if process == "exhaust" else "Petrol" if process == "evaporative" else "", key_pol)
    if key not in factors:
        raise ValueError("no road factor for admitted atom %r" % (key,))
    central, low, high = factors[key]
    alternative = low if endpoint == "low" else high
    return 1.0 if alternative is None or central == 0 else alternative / central


def build(atoms=None):
    from pkinv.sectors.transport import air_pollutants as road
    from pkinv.sectors.industry import air_pollutants as industry
    from pkinv.report.air_records import _agriculture, _data
    atoms = list(composed_atoms(read_rows(ATOMS_OUT) if atoms is None else atoms))
    classes = {c["source_class_id"]: c for c in industry.classes()}
    factors, bridge = road.factors(), road.class_map()
    waste_fraction = _data("waste").p("burned_fraction")
    coal_cases = collections.defaultdict(list)
    booked_coal = {}
    for row in read_rows(COAL_CASES):
        if row["case_kind"] == "reference":
            booked_coal[row["period_id"]] = float(row["brick_kt"])
        elif row["case_kind"] == "structural_case" and row["geographic_scope"] == "national":
            coal_cases[row["period_id"]].append(row)
    totals, sectors, cases = collections.defaultdict(float), collections.defaultdict(float), collections.defaultdict(float)
    evidence = {}
    for atom in atoms:
        pid, cfg, pol, sector = (atom[k] for k in ("period_id", "configuration_id", "pollutant", "sector_id"))
        year = 2000 + int(pid[-2:])
        mass = float(atom["emissions_Gg"])
        totals[pid, cfg, pol] += mass
        sectors[pid, cfg, pol, sector] += mass
        changes = {}
        if sector == "transport":
            for end in ("low", "high"):
                case = "road_transferred_factor_" + end
                changes[case] = mass * road_ratio(atom, end, factors, bridge, road.sulfur_ppm(year))
                evidence[case] = ("EMEP/EEA Tier1 published technology endpoints and declared sulfur cases",
                                  "simultaneous endpoints are sensitivities, not fleet observations or probabilistic limits; CNG/LPG and petrol-bus proxies retained")
        if sector == "industry":
            cls = classes[atom["source_class_id"]]
            for allocation in coal_cases[pid]:
                case = "coal_allocation:" + allocation["case_id"]
                ratio = (float(allocation["brick_kt"]) / booked_coal[pid]
                         if cls["activity_function"] == "industry.coal_kt:brick_kilns" else 1.0)
                changes[case] = mass * ratio
                evidence[case] = (allocation["interpretation"] + "; observation date=" + allocation["observation_date"],
                                  "dated fleet operating case, not annual observation; unresolved coal=%s kt, including negative residuals exposing inconsistency; kiln-type/fuel factors and sulfur held" % allocation["unresolved_quantity_kt"])
            for end in ("low", "high"):
                case = "industrial_fuel_sulfur_" + end
                ratio = 1.0
                if pol == "SO2" and cls["sulfur_evidence_id"]:
                    row = sulfur.evidence(cls["sulfur_evidence_id"], year, cls["source_class_id"])
                    ratio = float(row["s_pct_lo" if end == "low" else "s_pct_hi"]) / float(row["s_pct_central"])
                changes[case] = mass * ratio
                evidence[case] = ("dated fuel-sulfur evidence register; measured batches or fuel specification cases",
                                  "three kiln batches do not represent a national sample; raw-material sulfur unresolved; controls and coal account held")
        if sector == "waste":
            for fraction in (.3, .9):
                case = "waste_burned_fraction_%.1f" % fraction
                changes[case] = mass * fraction / waste_fraction
                evidence[case] = ("IPCC2006 expert-judgement central0.60; declared +/-50% transfer sensitivity",
                                  "burning locations, annual management observations and probabilities unavailable; remaining activity/factors fixed")
        if sector == "agriculture":
            case = "fertiliser_urea_regional_factor"
            ratio = 1.0
            if pol == "NH3" and atom["source_class_id"] == "agriculture:fertiliser:Urea":
                data = _agriculture(year)
                ratio = data.efv("fert_nh3_alt", "Urea_Bhatia") / data.efv("fert_nh3_highpH", "Urea")
            changes[case] = mass * ratio
            evidence[case] = ("held regional Bhatia urea NH3-N factor versus EMEP high-pH urea factor",
                              "factor transfer sensitivity; fertiliser offtake is not measured application or volatilisation")
        for case, value in changes.items():
            cases[pid, cfg, pol, sector, case] += value
    result = []
    for (pid, cfg, pol, sector, case), value in sorted(cases.items()):
        reference = sectors[pid, cfg, pol, sector]
        total = totals[pid, cfg, pol]
        source, limitations = evidence[case]
        result.append(dict(period_id=pid, configuration_id=cfg, pollutant=pol,
                           scenario_id=case, affected_sector=sector, reference_sector_Gg=reference,
                           case_sector_Gg=value, reference_covered_Gg=total,
                           case_covered_Gg=total + value - reference, change_Gg=value - reference,
                           case_kind="structural_case_no_probability", coverage_scope="covered_sources_only",
                           evidence=source, limitations=limitations))
    for (pid, cfg, pol), total in sorted(totals.items()):
        if conf.dung_basis(cfg) != "survey":
            continue
        alternative = conf.IPCC_LEDGER if conf.nitrogen_method(cfg) == "ipcc" else conf.LEDGER
        target = totals[pid, alternative, pol]
        central = sectors[pid, cfg, pol, "residential"]
        result.append(dict(period_id=pid, configuration_id=cfg, pollutant=pol,
                           scenario_id="all_diverted_dung_household_combustion", affected_sector="residential",
                           reference_sector_Gg=central, case_sector_Gg=sectors[pid, alternative, pol, "residential"],
                           reference_covered_Gg=total, case_covered_Gg=target, change_Gg=target - total,
                           case_kind="structural_case_no_probability", coverage_scope="covered_sources_only",
                           evidence="shared residential S/L activity configurations",
                           limitations="diverted dung destination unresolved; L assumes all diverted mass is burned in households; gross appliance emissions, outdoor escape not estimated"))
    return result


def main():
    rows = build()
    air_cases, ghg_cases = nitrogen_partition_rows()
    rows.extend(air_cases)
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    with open(NITROGEN_OUT, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, NITROGEN_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(ghg_cases)
    print("air structural sensitivities: %d rows; no scenario probabilities or confidence limits" % len(rows))
    print("nitrogen chemical-attribution diagnostic: %d native-GHG/GWP rows" % len(ghg_cases))


if __name__ == "__main__":
    main()
