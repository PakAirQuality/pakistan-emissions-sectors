"""Process-specific monthly allocation of admitted air atoms, in native mass.

Administrative monthly observations supply allocation support, not measurements
of emitted pollutants. Incompatible processes receive an explicit days-weighted
fallback instead of inheriting an unrelated greenhouse-gas profile.
"""
import collections
import csv
import os

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows
from pkinv.core import configurations as conf, monthly
from pkinv.core.reporting_window import CORE_SUFFIX
from pkinv.paths import OUTPUTS
from pkinv.report.air_annual import ATOMS_OUT, atom_configuration

OUT = asset_path(OUTPUTS, "pakemis_air_monthly.csv")
SUPPORT = asset_path(OUTPUTS, "pakemis_air_temporal_support.csv")
FIELDS = ("period_id", "configuration_id", "sector_id", "source_class_id", "support_anchor_id",
          "process", "pollutant", "month", "emissions_Gg", "month_share", "temporal_evidence_class",
          "profile_id", "timing_target", "profile_source", "maturity", "coverage_scope")
SUPPORT_FIELDS = ("period_id", "configuration_id", "pollutant", "temporal_evidence_class", "emissions_Gg", "mass_share")


def _ghg_profiles():
    path = asset_path(OUTPUTS, "pakemis_monthly_%s.csv" % CORE_SUFFIX)
    result = collections.defaultdict(dict)
    for row in read_rows(path):
        if conf.canonical(row["configuration_id"]) != conf.REFERENCE:
            continue
        result[(row["period_id"], row["component_id"])][row["month"]] = row
    return result


def profile_for(atom, profiles):
    start = 2000 + int(atom["period_id"][-2:]) - 1
    fallback = monthly.days_weighted_profile(start)
    sector, process, source, sub = (atom[name] for name in ("sector_id", "process", "source_class_id", "subitem"))
    sub = sub.lower()
    flat = (sector == "waste" or
            (sector == "transport" and process != "exhaust") or
            (sector == "fugitives" and source == "fug_flaring") or
            (sector == "agriculture" and ("housing" in sub or "storage" in sub or
                                         "yard" in sub or "manure" in sub or "pasture" in sub)))
    if flat:
        target = ("evaporative releases; no supported monthly vapour-loss record" if process == "evaporative" else
                  "vehicle-kilometres; no observed monthly class activity" if sector == "transport" else
                  "field flare combustion; annual satellite volumes only" if source == "fug_flaring" else
                  "manure-stage release; management or application dates unobserved" if sector == "agriculture" else
                  "waste burning; annual population reconstruction, no monthly fire activity")
        return {m: (w, "TE4", "days_weighted", target, "declared allocation") for m, w in fallback.items()}
    if sector == "agriculture" and ("crop residues" in sub or "left in field" in sub):
        # Residue incorporation/decomposition and the associated gas releases
        # have no observed monthly record. A crop-calendar soil-N2O profile does
        # not measure NH3 or NOx release dates.
        return {m: (w, "TE4", "days_weighted", "residue decomposition release; emission timing unobserved",
                    "declared allocation") for m, w in fallback.items()}
    if sector == "agriculture" and "synthetic" in sub:
        from pkinv.sectors.agriculture.monthly import published_nitrogen_profile
        weights, method, basis = published_nitrogen_profile(start)
        result = {}
        for month, weight in weights.items():
            code = method[month] if isinstance(method, dict) else method
            # Offtake is supply timing, not observed application or volatilisation.
            evidence = "TE4" if code == "T4" else "TE3"
            result[month] = (weight, evidence, "fertiliser_offtake_proxy", "fertiliser application and volatilisation allocation", basis)
        return result
    if sector == "ippu" and source == "ippu_soda_ash_solvay":
        from pkinv.core import pbs_qim
        rows = [r for r in pbs_qim._panel() if r["item"] == "Soda ash" and int(r["fiscal_year_start"]) == start and r["row_kind"] == "quantity"]
        quantities = {r["month"]: float(r["quantity"]) for r in rows}
        if set(quantities) == set(fallback):
            return {m: (w, "TE2", "own_year_soda_ash_production", "process production", "PBS physical monthly output") for m, w in monthly.normalise(quantities).items()}
        return {m: (w, "TE4", "days_weighted", "soda ash production; monthly physical output unavailable", "declared allocation") for m, w in fallback.items()}
    own = profiles.get((atom["period_id"], atom["support_anchor_id"]))
    if own:
        if set(own) != set(fallback):
            raise ValueError("incomplete emitting-process profile for " + str((atom["period_id"], source)))
        if sector == "aviation" or source == "fug_petrol_distribution_refuelling":
            identity, target = (("aviation_customer_fuel_proxy", "domestic flight activity; resident-airline fuel-sales proxy")
                                if sector == "aviation" else
                                ("road_customer_petrol_proxy", "national petrol distribution/refuelling; road-customer sales proxy"))
            return {m: (float(r["share"]), "TE4" if r["temporal_evidence_class"] == "TE4" else "TE3",
                        r["profile_id"] if r["temporal_evidence_class"] == "TE4" else identity + ":" + r["profile_id"],
                        "annual process estimate; monthly activity unobserved" if r["temporal_evidence_class"] == "TE4" else target,
                        r["source_id"]) for m, r in own.items()}
        if sector == "power":
            # The admitted oil/diesel stations are a reviewed subset of the
            # national fuel fleet. An observed aggregate is a timing proxy for
            # that subset, not an observation of these stations' own months.
            return {m: (float(r["share"]), "TE4" if r["temporal_evidence_class"] == "TE4" else "TE3",
                        "parent_fuel_fleet_proxy:" + r["profile_id"],
                        "admitted station subset combustion; aggregate fuel-fleet timing proxy",
                        r["source_id"]) for m, r in own.items()}
        return {m: (float(r["share"]), r["temporal_evidence_class"], r["profile_id"],
                    r["timing_target"], r["source_id"]) for m, r in own.items()}
    return {m: (w, "TE4", "days_weighted", "annual source estimate; monthly allocation support absent", "declared allocation") for m, w in fallback.items()}


def build(atoms=None, profiles=None):
    atoms = read_rows(ATOMS_OUT) if atoms is None else atoms
    profiles = _ghg_profiles() if profiles is None else profiles
    records = []
    shares = collections.defaultdict(float)
    totals = collections.defaultdict(float)
    for cfg in conf.AIR_ALL:
        for atom in atoms:
            if atom["core7"] != "yes" or conf.canonical(atom["configuration_id"]) != atom_configuration(cfg, atom["sector_id"]):
                continue
            plan = profile_for(atom, profiles)
            if abs(sum(p[0] for p in plan.values()) - 1) > 1e-10:
                raise ValueError("air monthly shares do not close for " + atom["source_class_id"])
            annual = float(atom["emissions_Gg"])
            for month, (weight, evidence, identity, target, source) in sorted(plan.items()):
                mass = annual * weight
                records.append(dict(period_id=atom["period_id"], configuration_id=cfg,
                                    sector_id=atom["sector_id"], source_class_id=atom["source_class_id"],
                                    support_anchor_id=atom["support_anchor_id"], process=atom["process"], pollutant=atom["pollutant"],
                                    month=month, emissions_Gg=mass, month_share=weight,
                                    temporal_evidence_class=evidence, profile_id=identity, timing_target=target,
                                    profile_source=source, maturity=atom["maturity"], coverage_scope="covered_sources_only"))
                key = (atom["period_id"], cfg, atom["pollutant"])
                shares[key + (evidence,)] += mass
                totals[key] += mass
    support = [dict(period_id=k[0], configuration_id=k[1], pollutant=k[2], temporal_evidence_class=k[3],
                    emissions_Gg=value, mass_share=value / totals[k[:3]] if totals[k[:3]] else 0)
               for k, value in sorted(shares.items())]
    return records, support


def main():
    for path, fields, records in zip((OUT, SUPPORT), (FIELDS, SUPPORT_FIELDS), build()):
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(records)
    print("air monthly product: process profiles; native Gg; screening excluded")


if __name__ == "__main__":
    main()
