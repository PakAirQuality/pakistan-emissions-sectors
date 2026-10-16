"""Diagnostic configurations of the livestock nitrogen chain.

Runs the same livestock population through alternative representations of where nitrogen is
lost, to separate a genuine physical disagreement from an artefact of misaligned system
boundaries. Nothing here writes to the shipped factor files: each run deep-copies the loaded
InventoryData and varies only the pre-field loss treatment, following the override pattern in
src/pkinv/inventory/mms_sensitivity.py.

  A  Legacy GHG        FracGASM (a POST-application fraction) applied at the pre-field
                       boundary, and then applied again to the survivor in soils.py.
                       Retained as a regression fixture: it must keep reproducing the
                       previously published total.
  A2 Fraction fixed    Correct per-system FracGasMS at the pre-field boundary, but with the
                       rest of Eq 10.34a still missing. Isolates the fraction substitution
                       from the completion of the loss equation.
  B  Stage-aligned     Full Eq 10.34a: FracGasMS + FracLeachMS + FracN2MS + EF3.
                       Complete IPCC structural alternative; the central reference is TAN.
  C  EMEP-linked       Pre-field volatilisation from the EMEP/EEA TAN chain (housing then
                       storage) instead of Table 10.22, other Eq 10.34a terms retained.
  D  Buffalo as Other  As B, but buffalo take the Other Cattle column of Table 10.22 instead
     Cattle            of Dairy Cow. Structural uncertainty on the single largest N pool.

Usage:  python3 -m pkinv.eval.n_ledger_runs
Writes: outputs/eval/n_ledger_runs.csv
"""

from pkinv.assets import asset_path
import copy
import csv
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture import enteric  , manure, rice, soils, residue_burning, liming_urea# noqa: E402
from pkinv.core import gwp  # noqa: E402
from pkinv.core.uncertainty import combine_sum  # noqa: E402

from pkinv.paths import ROOT

OUT_DIR = asset_path(ROOT, "outputs", "eval")
N2O_N_TO_N2O = 44.0 / 28.0
NH3_PER_N = 17.0 / 14.0
# 221.7 Mt was the agriculture total the edition BEFORE the boundary correction printed, and
# Run A reproduced it when this lane was written. The rc39 herd re-base (the census's exact
# enumeration) moved every run, so Run A on today's herd cannot reproduce a number printed
# on the old one: the figure is kept for the record and NOT asserted. rc42 (the twentieth
# review's M-1 class of stale eval products): the guard that matters is that Run B - the
# shipped configuration - equals the inventory's own published total, read from the tree.
LEGACY_TOTAL_MT_PRE_REBASE = 221.7
SHIPPED_TOL = 0.05           # Mt CO2e


def _emep_prefield_frac(data):
    """Fraction of managed manure N volatilised before the field on the EMEP TAN chain.

    Derived from the species- and system-resolved chain the air layer now runs, not from a single
    national solid-manure chain -- buffalo alone carry a different TAN fraction and storage factor,
    and Run C is only meaningful if it reflects the EMEP representation actually in use.
    """
    from pkinv.sectors.agriculture import air_pollutants as ap
    from pkinv.sectors.agriculture import manure as _manure
    _, npools = _manure.compute(data, method="tan")
    f = ap.livestock_nh3_flows(data, npools)
    return (f["housing"] + f["yard"] + f["storage"]) / npools["managed_N"]


def _rebuild(data, npools, gas_fn, loss_fn):
    """Recompute the manure N pools under an alternative pre-field loss treatment.

    gas_fn(row)  -> fraction of that species x system pool volatilised before the field
    loss_fn(row) -> total fraction lost before the field (volatilisation + anything else)
    Returns (npools2, mms_indirect_Gg, volat_uncert_pct).
    """
    out = dict(npools)
    # Legacy diagnostic substitutions explicitly use the IPCC field formulation.
    # Do not retain reference TAN field-loss metadata while replacing FON.
    out.pop("field_volat_NH3_N", None)
    out.pop("field_volat_NOx_N", None)
    volat = fon = 0.0
    terms = []
    for r in npools["by_system"]:
        n = r["excreted_N"]
        g, L = gas_fn(r), loss_fn(r)
        if not 0.0 <= L < 1.0:
            raise ValueError("FracLossMS %.3f outside [0,1) for %s/%s"
                             % (L, r["species"], r["system"]))
        volat += n * g
        fon += n * (1 - L)
        terms.append((n * g, data.efu("manure_fracgasms", r["class"] + "_" + r["system"])))
    out["volat_managed_N"] = volat
    out["FON_N"] = fon
    _, volat_u = combine_sum(terms)
    ef4 = data.efv("soils", "EF4_dry")
    return out, volat * ef4 * N2O_N_TO_N2O / 1e6, volat_u


def _run(data, label, gas_fn, loss_fn):
    """Build the full national inventory under one pre-field configuration."""
    base = []
    base += enteric.compute(data)
    base += rice.compute(data)
    base += residue_burning.compute(data)
    base += liming_urea.compute(data)

    mcomp, npools = manure.compute(data, method="ipcc")
    npools2, indirect_gg, volat_u = _rebuild(data, npools, gas_fn, loss_fn)
    mcomp = copy.deepcopy(mcomp)
    for c in mcomp:
        if c["subitem"] == "Indirect N2O (volatilisation)":
            c["emissions_Gg"] = indirect_gg
    scomp = soils.compute(data, npools2)

    comps = base + mcomp + scomp
    for c in comps:
        c["co2e_Mt_AR5"] = gwp.to_co2e(c["gas"], c["emissions_Gg"], "AR5") / 1000.0

    def gg(cat, sub):
        return sum(c["emissions_Gg"] for c in comps
                   if c["category"] == cat and c["subitem"] == sub)

    # NH3-N implied by THIS nitrogen chain (pre-field + post-application + grazing),
    # so the GHG representation can be read against the air layer's EMEP estimate.
    fracgasm = data.efv("soils", "FracGASM")
    f_nh3 = data.efv("soils", "NH3_frac_of_volat")
    prp = npools2["FPRP_cattle_N"] + npools2["FPRP_other_N"]
    nh3_n = (npools2["volat_managed_N"] + npools2["FON_N"] * fracgasm + prp * fracgasm)
    managed = npools2["managed_N"]

    return {
        "run": label,
        "livestock_NH3_kt_implied": nh3_n * f_nh3 * NH3_PER_N / 1e6,
        "MMS_direct_N2O_Gg": gg("Manure management", "Direct N2O"),
        "MMS_indirect_N2O_Gg": gg("Manure management", "Indirect N2O (volatilisation)"),
        "manure_N_applied_Mt_N": npools2["FON_N"] / 1e9,
        "soil_direct_N2O_manure_Gg": gg("Managed soils", "Direct N2O - organic manure"),
        "soil_indirect_volat_N2O_Gg": sum(c["emissions_Gg"] for c in scomp if c["subitem"].startswith("Indirect N2O - volatilisation")),
        "soil_indirect_leach_N2O_Gg": sum(c["emissions_Gg"] for c in scomp if c["subitem"].startswith("Indirect N2O - leaching/runoff")),
        "managed_soils_Mt": sum(c["co2e_Mt_AR5"] for c in comps
                                if c["category"] == "Managed soils"),
        "national_total_Mt": sum(c["co2e_Mt_AR5"] for c in comps),
        "prefield_volat_pct_of_managed": 100.0 * npools2["volat_managed_N"] / managed,
        "closing_N_residual_kg": (npools2["excreted_N"]
                                  - (prp + managed + npools2["diverted_N"])),
    }


def all_runs(data=None):
    if data is None:
        data = InventoryData()
    legacy = data.efv("soils", "FracGASM")
    emep = _emep_prefield_frac(data)

    def other_cattle_class(r):
        return "other_cattle" if r["species"] == "buffalo" else r["class"]

    runs = [
        _run(data, "A. Legacy GHG (FracGASM at pre-field, applied twice)",
             lambda r: legacy, lambda r: legacy),
        _run(data, "A2. Correct fraction only (FracGasMS, Eq 10.34a incomplete)",
             lambda r: r["FracGasMS"], lambda r: r["FracGasMS"]),
        _run(data, "B. Complete IPCC alternative, full Eq 10.34a",
             lambda r: r["FracGasMS"], lambda r: r["FracLossMS"]),
        _run(data, "C. EMEP-linked pre-field volatilisation",
             lambda r: emep,
             lambda r: emep + r["FracLeachMS"] + r["FracN2MS"] + r["EF3"]),
        _run(data, "D. Buffalo as Other Cattle (structural alternative)",
             lambda r: data.efv("manure_fracgasms",
                                other_cattle_class(r) + "_" + r["system"]),
             lambda r: (data.efv("manure_fracgasms",
                                 other_cattle_class(r) + "_" + r["system"])
                        + r["FracLeachMS"] + r["FracN2MS"] + r["EF3"])),
    ]
    # The reference is a complete engine rerun, not a national-average fraction
    # substituted into an otherwise different nitrogen formulation.
    comps, pools = manure.rerun_nitrogen(data, method="tan")
    extra = enteric.compute(data) + rice.compute(data) + residue_burning.compute(data) + liming_urea.compute(data)
    all_components = comps + extra
    def gg(category, prefix):
        return sum(c["emissions_Gg"] for c in comps if c["category"] == category and c["subitem"].startswith(prefix))
    runs.append({
        "run": "R. Coherent species-specific TAN reference [SHIPPED]",
        "livestock_NH3_kt_implied": (pools["managed_NH3_N"] + sum(pools["field_volat_NH3_N"].values())) * NH3_PER_N / 1e6,
        "MMS_direct_N2O_Gg": gg("Manure management", "Direct N2O"),
        "MMS_indirect_N2O_Gg": gg("Manure management", "Indirect N2O (volatilisation)"),
        "manure_N_applied_Mt_N": pools["FON_N"] / 1e9,
        "soil_direct_N2O_manure_Gg": gg("Managed soils", "Direct N2O - organic manure"),
        "soil_indirect_volat_N2O_Gg": gg("Managed soils", "Indirect N2O - volatilisation"),
        "soil_indirect_leach_N2O_Gg": gg("Managed soils", "Indirect N2O - leaching/runoff"),
        "managed_soils_Mt": sum(gwp.to_co2e(c["gas"], c["emissions_Gg"], "AR5") / 1000 for c in comps if c["category"] == "Managed soils"),
        "national_total_Mt": sum(gwp.to_co2e(c["gas"], c["emissions_Gg"], "AR5") / 1000 for c in all_components),
        "prefield_volat_pct_of_managed": 100 * pools["volat_managed_N"] / pools["managed_N"],
        "closing_N_residual_kg": pools["excreted_N"] - pools["FPRP_cattle_N"] - pools["FPRP_other_N"] - pools["managed_N"] - pools["diverted_N"],
    })
    return runs


FIELDS = ["run", "livestock_NH3_kt_implied", "MMS_direct_N2O_Gg", "MMS_indirect_N2O_Gg",
          "manure_N_applied_Mt_N", "soil_direct_N2O_manure_Gg", "soil_indirect_volat_N2O_Gg",
          "soil_indirect_leach_N2O_Gg", "managed_soils_Mt", "national_total_Mt",
          "prefield_volat_pct_of_managed", "closing_N_residual_kg"]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    runs = all_runs()

    with open(asset_path(OUT_DIR, "n_ledger_runs.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in runs:
            w.writerow({k: (r[k] if k == "run" else round(r[k], 6)) for k in FIELDS})

    print("Diagnostic configurations of the livestock nitrogen chain (2024):")
    print()
    hdr = ("%-52s %9s %9s %9s %9s %9s %9s" %
           ("run", "NH3 kt", "MMSind", "FON MtN", "soilDir", "soils Mt", "TOTAL Mt"))
    print("  " + hdr)
    print("  " + "-" * len(hdr))
    for r in runs:
        print("  %-52s %9.1f %9.3f %9.3f %9.3f %9.2f %9.2f"
              % (r["run"][:52], r["livestock_NH3_kt_implied"], r["MMS_indirect_N2O_Gg"],
                 r["manure_N_applied_Mt_N"], r["soil_direct_N2O_manure_Gg"],
                 r["managed_soils_Mt"], r["national_total_Mt"]))
    print()
    for r in runs:
        assert abs(r["closing_N_residual_kg"]) < 1.0, r["run"]
    print("  Excretion partition closes in every run (|residual| < 1 kg N).")

    a = runs[0]["national_total_Mt"]
    a2 = runs[1]["national_total_Mt"]
    b = runs[2]["national_total_Mt"]
    print()
    print("  Attribution of the A -> B change (Mt CO2e):")
    print("    A  legacy                                        %8.2f" % a)
    print("    +  substitute FracGASM -> per-system FracGasMS   %+8.2f" % (a2 - a))
    print("    +  complete Eq 10.34a (leaching, N2, N2O-N)      %+8.2f" % (b - a2))
    print("    =  B complete IPCC alternative                   %8.2f" % b)

    shipped = _shipped_total_mt()
    reference = runs[-1]["national_total_Mt"]
    if abs(reference - shipped) > SHIPPED_TOL:
        raise SystemExit("Run R no longer reproduces the shipped agriculture total %.2f (got %.2f)"
                         % (shipped, reference))
    print()
    print("  Run R reproduces the shipped agriculture total %.2f Mt (national_totals_2024.csv),"
          % shipped)
    print("  so the A -> B attribution above is a decomposition of the inventory's own number;")
    print("  Run A on today's herd is %.2f Mt (the pre-re-base edition printed %.1f)."
          % (a, LEGACY_TOTAL_MT_PRE_REBASE))
    return 0


def _shipped_total_mt():
    import csv
    path = asset_path(ROOT, "outputs", "national_totals_2024.csv")
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(line for line in handle if not line.startswith("#")):
            if row["category"] == "TOTAL":
                return float(row["co2e_Mt_AR5"])
    raise SystemExit("no TOTAL row in %s" % path)


if __name__ == "__main__":
    raise SystemExit(main())
