"""Agricultural NOx pathway by pathway: the central partition against EMEP/EEA 2023 process factors.

WHY THIS EXISTS (rc69). The review called the nitrogen partition a major structural assumption:
the all-NH3 attribution diagnostic moves national NOx by about 150 Gg, 18 percent of the
reference total. The central inventory books NOx from agricultural nitrogen two ways:
- a fixed NO-N fraction of applied N for synthetic fertiliser and crop residues
  (soils.NOx_frac_of_applied, 0.007, Stehfest and Bouwman 2006);
- for manure management, applied manure and grazing excreta, 5 percent of each pathway's
  mixed volatilisation loss (soils.NH3_frac_of_volat = 0.95, so 0.05 is NOx-N).

Neither is the process-specific factor the EMEP/EEA Guidebook 2023 publishes for that pathway,
and the review asked for that justification with the alternative carried through national
totals and trends. This module reads both chapters (held in the restricted layers) and does
two things. First, it tabulates every pathway: the nitrogen it applies to, the central NOx and
the implied kg NO2 per kg N, and the EMEP/EEA 2023 factor with its table. Second, it computes
the national case in which the EMEP/EEA 2023 factors replace the central ones.

THE EMEP/EEA 2023 FACTORS, as printed:
  3.D Table 3-1 (Tier 1)   NO from N applied in fertiliser, manure and excreta:
                           0.04 kg NO2 per kg N (95 % interval 0.005-0.104), Skiba et al. 2021.
                           Applied to synthetic fertiliser N, applied manure N (FON) and N
                           deposited by grazing animals (FPRP).
  3.B Table 3-10 (Tier 2)  NO-N from storage: 0.01 kg NO-N per kg TAN for solid manure
                           (0.0001 for slurry), Misselbrook et al. 2015. Applied to the TAN that
                           enters the solid-storage and poultry-litter stages of this ledger. No
                           Pakistani system is a slurry store. The chapter gives no NO factor for
                           housing or yards.
  3.D                      no NO factor for crop-residue N; the central row is retained.

WHAT THE CASE IS AND IS NOT. It is a documented alternative factor set, not a bound and not
a probability. NO from applied and deposited N is computed on that N, as EMEP does, outside the
volatilisation pool, so the nitrogen ledger is not re-closed for it. The greenhouse-gas pools
(indirect N2O from IPCC FracGAS) are unchanged. NH3 is unchanged, because the central NH3
factors are already EMEP/IPCC NH3-N factors. Burning NOx is unchanged.

Usage:  python3 -m pkinv.report.nitrogen_no_pathways [--check]
Writes: outputs/pakemis_nitrogen_no_pathways.csv
"""
import argparse
import collections

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows
from pkinv.core import configurations as conf
from pkinv.core.io import write_or_check
from pkinv.paths import OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_nitrogen_no_pathways.csv")
CASE = "nitrogen_no_emep2023_process_factors"
NO2_PER_N = 46.0 / 14.0
EMEP_APPLIED = 0.04            # kg NO2 per kg N applied or deposited (3.D Table 3-1)
EMEP_STORAGE_SOLID = 0.01      # kg NO-N per kg TAN entering solid storage (3.B Table 3-10)
REFERENCE_3D = ("EMEP/EEA 2023 3.D Agricultural soils, Table 3-1: NO from N applied in "
                "fertiliser, manure and excreta, 0.04 kg NO2/kg N (0.005-0.104), Skiba et al. 2021; "
                "data/raw/emep/emep_eea_2023_3d_agricultural_soils.pdf")
REFERENCE_3B = ("EMEP/EEA 2023 3.B Manure management, Table 3-10: EF storage_solid NO 0.01 kg "
                "NO-N/kg TAN (slurry 0.0001), Misselbrook et al. 2015; "
                "data/raw/emep/emep_eea_2023_3b_manure_management.pdf")
STORAGE_STAGES = {("solid_storage", "storage"), ("poultry_litter", "storage")}
FIELDS = ("period_id", "configuration_id", "pathway", "central_subitems", "nitrogen_basis",
          "nitrogen_basis_kg", "central_NOx_Gg", "central_kg_NO2_per_kg", "emep_factor",
          "emep_factor_unit", "emep_case_NOx_Gg", "change_Gg", "emep_reference", "note")
# (pathway, central subitems, basis, emep factor kind)
PATHWAYS = (
    ("manure_management", ("NOx - manure management",), "TAN entering solid storage and litter", "storage"),
    ("grazing_excreta", ("NOx - pasture_cattle", "NOx - pasture_other"), "N deposited by grazing animals (FPRP)", "applied"),
    ("synthetic_fertiliser", ("Soil NOx - synthetic fertiliser",), "synthetic fertiliser N (offtake)", "applied"),
    ("applied_manure", ("Soil NOx - organic manure",), "manure N applied to soils (FON)", "applied"),
    ("crop_residues", ("Soil NOx - crop residues",), "crop residue N", "retained"),
)


def _year(period_id):
    return 2000 + int(period_id[-2:])


def _basis(year, method, replays):
    """{pathway: kg N or kg TAN} from the central ledger replay of this year and method."""
    from pkinv.report.air_sensitivities import nitrogen_partition_replay
    from pkinv.sectors.agriculture import fiscal_activity
    if (year, method) not in replays:
        replays[year, method] = nitrogen_partition_replay(year, method)
    pools = replays[year, method]["pools"]
    if (year, "tan") not in replays:
        replays[year, "tan"] = nitrogen_partition_replay(year, "tan")
    tan_pools = replays[year, "tan"]["pools"]
    storage = 0.0
    for system in tan_pools["by_system"]:
        for stage in system.get("stage_detail", ()):
            if (system["system"], stage["stage"]) in STORAGE_STAGES:
                storage += stage["input_TAN_N"]
    data = fiscal_activity.data_for_fiscal_year(year)
    return {"manure_management": storage,
            "grazing_excreta": pools["FPRP_cattle_N"] + pools["FPRP_other_N"],
            "synthetic_fertiliser": data.fertilizer["nitrogen_N_offtake"]["value_t"] * 1000.0,
            "applied_manure": pools["FON_N"],
            "crop_residues": None}


def _emep_Gg(kind, basis_kg):
    if kind == "storage":
        return basis_kg * EMEP_STORAGE_SOLID * NO2_PER_N / 1e6
    if kind == "applied":
        return basis_kg * EMEP_APPLIED / 1e6
    raise ValueError(kind)


def build(atoms=None):
    """(pathway rows, {(period, configuration): NOx change in Gg})."""
    from pkinv.report.air_annual import ATOMS_OUT
    atoms = read_rows(ATOMS_OUT) if atoms is None else atoms
    central = collections.defaultdict(float)
    keys = set()
    for a in atoms:
        if a["sector_id"] != "agriculture" or a["pollutant"] != "NOx":
            continue
        keys.add((a["period_id"], a["configuration_id"]))
        central[(a["period_id"], a["configuration_id"], a["subitem"])] += float(a["emissions_Gg"])
    replays, rows, change = {}, [], {}
    for period, cfg in sorted(keys):
        year, method = _year(period), conf.nitrogen_method(cfg)
        basis = _basis(year, method, replays)
        total = 0.0
        for pathway, subitems, label, kind in PATHWAYS:
            present = sum(central.get((period, cfg, s), 0.0) for s in subitems)
            if kind == "retained":
                case, factor, unit, ref = present, "", "", "EMEP/EEA 2023 3.D gives no NO factor for crop-residue N; the central row is retained"
                implied, basis_kg = "", ""
            else:
                basis_kg = basis[pathway]
                case = _emep_Gg(kind, basis_kg)
                factor = EMEP_STORAGE_SOLID * NO2_PER_N if kind == "storage" else EMEP_APPLIED
                unit = ("kg NO2 per kg TAN (0.01 kg NO-N)" if kind == "storage"
                        else "kg NO2 per kg N")
                ref = REFERENCE_3B if kind == "storage" else REFERENCE_3D
                implied = round(present * 1e6 / basis_kg, 6) if basis_kg else ""
            total += case - present
            rows.append({"period_id": period, "configuration_id": cfg, "pathway": pathway,
                         "central_subitems": "; ".join(subitems), "nitrogen_basis": label,
                         "nitrogen_basis_kg": round(basis_kg, 1) if basis_kg != "" else "",
                         "central_NOx_Gg": round(present, 6),
                         "central_kg_NO2_per_kg": implied,
                         "emep_factor": round(factor, 6) if factor != "" else "",
                         "emep_factor_unit": unit, "emep_case_NOx_Gg": round(case, 6),
                         "change_Gg": round(case - present, 6), "emep_reference": ref,
                         "note": "configuration nitrogen method %s" % method})
        change[(period, cfg)] = total
    return rows, change


EVIDENCE = ("EMEP/EEA 2023 process factors replace the central partition pathway by pathway: "
            "3.D Table 3-1 0.04 kg NO2/kg N on fertiliser, applied manure and grazing N; 3.B "
            "Table 3-10 0.01 kg NO-N/kg TAN on solid storage; crop residue and burning NOx kept")
LIMITATIONS = ("documented alternative factor set, not a bound or probability; NO from applied "
               "N is computed outside the volatilisation pool, so the nitrogen ledger is not "
               "re-closed for it; GHG pools, NH3 and burning unchanged; the 3.D factor's 95 % "
               "interval is 0.005-0.104 kg NO2/kg N")


def structural_rows(change, atoms=None):
    """Rows in the structural-sensitivity table's own shape, one per species."""
    from pkinv.report.air_annual import ATOMS_OUT, CORE7
    from pkinv.report.air_uncertainty import composed_atoms
    atoms = list(composed_atoms(read_rows(ATOMS_OUT) if atoms is None else atoms))
    total, sector = collections.defaultdict(float), collections.defaultdict(float)
    for a in atoms:
        key = (a["period_id"], a["configuration_id"], a["pollutant"])
        total[key] += float(a["emissions_Gg"])
        if a["sector_id"] == "agriculture":
            sector[key] += float(a["emissions_Gg"])
    out = []
    for (period, cfg), delta in sorted(change.items()):
        for pol in CORE7:
            d = delta if pol == "NOx" else 0.0
            key = (period, cfg, pol)
            out.append({"period_id": period, "configuration_id": cfg, "pollutant": pol,
                        "scenario_id": CASE, "affected_sector": "agriculture",
                        "reference_sector_Gg": sector[key], "case_sector_Gg": sector[key] + d,
                        "reference_covered_Gg": total[key], "case_covered_Gg": total[key] + d,
                        "change_Gg": d, "case_kind": "alternative_factor_set_no_probability",
                        "coverage_scope": "covered_sources_only", "evidence": EVIDENCE,
                        "limitations": LIMITATIONS})
    return out


BANNER = [
    "AGRICULTURAL NOx BY PATHWAY: the central partition against the EMEP/EEA 2023 process",
    "factors (rc69).",
    "- Central: 0.007 kg NO-N per kg N applied for fertiliser and residues; 5 percent of the",
    "  mixed volatilisation loss for manure management, applied manure and grazing.",
    "- EMEP/EEA 2023, applied pathway by pathway: 3.D Table 3-1 for fertiliser, manure and",
    "  excreta; 3.B Table 3-10 for solid storage.",
    "The case changes NOx only, and is carried into national totals as",
    "nitrogen_no_emep2023_process_factors in pakemis_air_structural_sensitivities.csv.",
    "Producer: pkinv.report.nitrogen_no_pathways.",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rows, _change = build()
    return write_or_check(OUT, FIELDS, rows, check=args.check, banner=BANNER)


if __name__ == "__main__":
    raise SystemExit(main())
