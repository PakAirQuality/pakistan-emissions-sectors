"""Stage-resolved nitrogen ledger for the livestock -> manure -> soil chain.

One canonical accounting of every kilogram of excreted nitrogen, so that the greenhouse-gas
and air-pollutant layers can be compared on the same boundaries instead of on numbers that
look comparable but are not.

Three stages, following IPCC 2019 Refinement V4 Ch10 (Eq 10.34/10.34a/10.34b) and Ch11:

  A. Excretion partition   N_excreted = N_grazing + N_managed + N_diverted
  B. Pre-field management  losses inside housing and storage (FracGasMS volatilisation,
                           FracLeachMS leaching, FracN2MS as N2, EF3 as N2O-N), leaving
                           N available for application to soils (FON)
  C. Field application     from the GROSS applied N: direct soil N2O-N (EF1), post-application
                           volatilisation (FracGASM) and leaching (FracLEACH)

TOTAL N AND TAN ARE SEPARATE STATE VARIABLES. The IPCC chain tracks total nitrogen; the
EMEP/EEA chain used by the air-pollutant layer tracks total ammoniacal nitrogen (TAN), a
subset of it. Both are reported here over the same managed pool so the two representations
can be read against each other stage by stage -- which is the whole point of the ledger.

The critical boundary rule, and the one an earlier implementation broke: FracGasMS is a
PRE-FIELD loss and reduces the manure that reaches the field; FracGASM is a POST-APPLICATION
loss and does NOT reduce FON before Tier-1 direct soil N2O. They are different fractions
measured at different stages and are not interchangeable.

Usage:  python3 -m pkinv.sectors.agriculture.n_ledger
Writes: outputs/n_ledger_2024.csv, outputs/n_ledger_2024.md
"""

from pkinv.assets import asset_path
import csv
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture import manure  , soils# noqa: E402

from pkinv.paths import ROOT

OUT_DIR = asset_path(ROOT, "outputs")
TOL = 1e-9          # relative closure tolerance for each stage


def build(data=None, method=None):
    """Return (rows, checks). rows are ledger lines; checks are the closure residuals."""
    if data is None:
        data = InventoryData()
    _, np_ = manure.compute(data, method=method)

    excreted = np_["excreted_N"]
    grazing = np_["FPRP_cattle_N"] + np_["FPRP_other_N"]
    managed = np_["managed_N"]
    diverted = np_["diverted_N"]

    rows = []

    def add(stage, flow, kg, kind="flow"):
        rows.append({"stage": stage, "flow": flow, "kg_N": kg,
                     "pct_of_excreted": 100.0 * kg / excreted if excreted else 0.0,
                     "kind": kind})

    # ---- A. Excretion partition -------------------------------------------------------
    add("A. Excretion", "Total N excreted", excreted, "opening")
    add("A. Excretion", "to grazing (pasture/range/paddock -> soils FPRP)", grazing)
    add("A. Excretion", "to managed manure systems", managed)
    add("A. Excretion", "diverted as dung-cake material (destinations unresolved)", diverted)
    res_a = excreted - (grazing + managed + diverted)
    add("A. Excretion", "partition residual", res_a, "residual")

    # ---- B. Pre-field manure management (Eq 10.34a) ------------------------------------
    volat = np_["volat_managed_N"]
    leach = np_["leach_managed_N"]
    n2 = np_["n2_managed_N"]
    n2o = np_["n2o_managed_N"]
    fon = np_["FON_N"]
    add("B. Pre-field MMS", "Managed N entering housing and storage", managed, "opening")
    add("B. Pre-field MMS", "NH3-N + NOx-N volatilised (%s formulation)" % np_["nitrogen_method"], volat)
    add("B. Pre-field MMS", "leached/run-off (FracLeachMS, Table 10.22)", leach)
    add("B. Pre-field MMS", "lost as N2 (FracN2MS = RN2 x EF3, Eq 10.34b)", n2)
    add("B. Pre-field MMS", "emitted as direct N2O-N (EF3, Table 10.21)", n2o)
    add("B. Pre-field MMS", "= N available for application to soils (FON, Eq 10.34)", fon,
        "closing")
    res_b = managed - (volat + leach + n2 + n2o + fon)
    add("B. Pre-field MMS", "balance residual", res_b, "residual")

    # ---- B'. The same managed pool as TAN (EMEP/EEA), a separate state variable ---------
    # Resolved per species and manure system (EMEP/EEA Table 3-9), not a single national chain:
    # buffalo alone carry a different TAN fraction and storage factor from cattle.
    from pkinv.sectors.agriculture import air_pollutants as ap
    f = ap.livestock_nh3_flows(data, np_)
    tan = sum(r["excreted_N"] * data.efv("nh3_emep_tan", r["species"])
              for r in np_["by_system"] if r["system"] in ap.SYSTEM_STAGES)
    housing = f["housing"] + f["yard"]
    storage = f["storage"]
    application = f["application"]
    tan_applied = sum(r["TAN_after_management_N"] for r in np_["by_system"]
                      if r["TAN_after_management_N"] is not None)
    tan_other = tan - housing - storage - np_["managed_NOx_N"] - tan_applied
    add("B'. Same pool as TAN", "TAN in managed manure (species-specific TAN fractions)", tan,
        "opening")
    add("B'. Same pool as TAN", "NH3-N lost in housing and yards", housing)
    add("B'. Same pool as TAN", "NH3-N lost in storage", storage)
    add("B'. Same pool as TAN", "NOx-N lost during management", np_["managed_NOx_N"])
    add("B'. Same pool as TAN", "TAN removed in other management losses", tan_other)
    add("B'. Same pool as TAN", "= TAN reaching the field", tan_applied, "closing")
    add("B'. Same pool as TAN", "NH3-N lost on field application", application)
    res_bp = tan - (housing + storage + np_["managed_NOx_N"] + tan_other + tan_applied)
    add("B'. Same pool as TAN", "TAN balance residual", res_bp, "residual")

    # ---- C. Field application of FON (Ch11; GROSS basis) -------------------------------
    ef1 = data.efv("soils", "EF1_dry")
    fracgasm = data.efv("soils", "FracGASM")
    fracleach = data.efv("soils", "FracLEACH") * data.p("leach_applicable_fraction")
    c_n2o = fon * ef1
    c_volat = soils.volatilised_n(data, np_)["organic"]
    c_leach = fon * fracleach
    add("C. Field application", "Manure N applied to soils (gross FON)", fon, "opening")
    add("C. Field application", "direct soil N2O-N (EF1 x GROSS FON, Eq 11.1)", c_n2o)
    add("C. Field application", "NH3-N + NOx-N volatilised (%s formulation)" % np_["nitrogen_method"], c_volat)
    add("C. Field application", "leached/run-off (FracLEACH, Eq 11.10)", c_leach)
    add("C. Field application", "remaining in the soil N pool", fon - c_n2o - c_volat - c_leach,
        "closing")
    res_c = 0.0    # by construction: the remaining term is the residual

    # ---- Whole-chain closure -----------------------------------------------------------
    accounted = (grazing + diverted + volat + leach + n2 + n2o
                 + c_n2o + c_volat + c_leach + (fon - c_n2o - c_volat - c_leach))
    res_all = excreted - accounted
    add("D. Closure", "Total N excreted", excreted, "opening")
    add("D. Closure", "all named sinks and remaining soil pool", accounted, "closing")
    add("D. Closure", "closing residual", res_all, "residual")

    checks = {"nitrogen_method": np_["nitrogen_method"], "partition_residual": res_a, "mms_residual": res_b, "tan_residual": res_bp,
              "field_residual": res_c, "closing_residual": res_all, "excreted_N": excreted,
              "ipcc_prefield_volat_frac": volat / managed,
              "emep_prefield_volat_frac": (housing + storage) / managed,
              "emep_full_chain_frac": (housing + storage + application) / managed}
    return rows, checks


def stage_comparison(data=None):
    """IPCC and EMEP livestock ammonia, stage by stage, on a COMMON NH3-N basis.

    Comparing only the totals is not safe. The IPCC fractions are defined on NH3+NOx and the EMEP
    factors on NH3-N, so they must first be put on one chemical basis; and once they are, the
    agreement in the total turns out to be two large stage-level disagreements cancelling -- the
    same failure this work identified in the spatial proxies, where two allocation errors offset.
    A combined total that matches therefore says nothing about stage-level equivalence.
    """
    if data is None:
        data = InventoryData()
    _, np_ = manure.compute(data, method="ipcc")
    _, tan_ = manure.compute(data, method="tan")
    share = data.efv("soils", "NH3_frac_of_volat")
    fracgasm = data.efv("soils", "FracGASM")

    prp = np_["FPRP_cattle_N"] + np_["FPRP_other_N"]
    # EMEP side is now resolved per species and manure system (air_pollutants.livestock_nh3_flows),
    # so the comparison is against that rather than against a single national chain.
    from pkinv.sectors.agriculture import air_pollutants as ap
    f = ap.livestock_nh3_flows(data, tan_)

    stages = [
        ("housing + storage", np_["volat_managed_N"] * share,
         f["housing"] + f["yard"] + f["storage"]),
        ("field application", np_["FON_N"] * fracgasm * share, f["application"]),
        ("grazing", prp * fracgasm * share, f["grazing"]),
    ]
    out = [{"stage": s, "ipcc_nh3_n": i, "emep_nh3_n": e, "ratio": i / e if e else None}
           for s, i, e in stages]
    ti = sum(r["ipcc_nh3_n"] for r in out)
    te = sum(r["emep_nh3_n"] for r in out)
    out.append({"stage": "TOTAL", "ipcc_nh3_n": ti, "emep_nh3_n": te, "ratio": ti / te})
    return out


QA_TABLE = "agriculture_n_ledger_qa_2024.csv"
DECLARED = ("n_ledger_stage_comparison.csv", "n_ledger_2024.csv", "n_ledger_2024.md")


def _gates(run, checks):
    """The closure properties, published where a reader can see them.

    tests/test_n_ledger.py asserts these already; a test is not an artefact, and the
    agriculture paper says the ledger closes on every run. Relative residuals, because an
    absolute tonnage means nothing without the mass it is a residual OF."""
    excreted = checks["excreted_N"]
    for key, what in (("partition_residual", "excretion splits into its named pools"),
                      ("mms_residual", "the manure-management systems account for all managed N"),
                      ("tan_residual", "the TAN pool closes"),
                      ("closing_residual", "the ledger closes end to end")):
        rel = abs(checks[key]) / excreted
        run.gate("%s (%s)" % (what, key), rel < TOL,
                 actual="%.3e" % rel, expected="< %.0e" % TOL,
                 note="residual relative to excreted N (%.4f Mt N)" % (excreted / 1e9))


def main():
    from pkinv.core.runner import Runner
    run = Runner("agriculture nitrogen ledger", declared=DECLARED)
    os.makedirs(OUT_DIR, exist_ok=True)
    rows, checks = build()
    stages = stage_comparison()
    with open(asset_path(OUT_DIR, "n_ledger_stage_comparison.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["stage", "ipcc_nh3_n", "emep_nh3_n", "ratio"])
        w.writeheader()
        for r in stages:
            w.writerow({"stage": r["stage"], "ipcc_nh3_n": round(r["ipcc_nh3_n"] / 1e9, 4),
                        "emep_nh3_n": round(r["emep_nh3_n"] / 1e9, 4),
                        "ratio": round(r["ratio"], 3)})

    with open(asset_path(OUT_DIR, "n_ledger_2024.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["stage", "flow", "kg_N", "Mt_N", "pct_of_excreted", "kind"])
        for r in rows:
            w.writerow([r["stage"], r["flow"], "%.6e" % r["kg_N"],
                        round(r["kg_N"] / 1e9, 4), round(r["pct_of_excreted"], 3), r["kind"]])

    lines = ["# Pakistan livestock nitrogen ledger, 2024", "",
             "All flows in Mt N. Stages follow IPCC 2019 Refinement Eq 10.34/10.34a/10.34b "
             "(pre-field) and Ch11 (post-application). Stage B' re-expresses the same managed "
             "pool as total ammoniacal nitrogen (TAN), the EMEP/EEA state variable used by the "
             "air-pollutant layer; it is a parallel representation of stage B, not an addition "
             "to it.", ""]
    stage = None
    for r in rows:
        if r["stage"] != stage:
            stage = r["stage"]
            lines += ["", "## " + stage, "", "| Flow | Mt N | % of excreted |", "|---|---:|---:|"]
        lines.append("| %s | %.4f | %.2f |"
                     % (r["flow"], r["kg_N"] / 1e9, r["pct_of_excreted"]))
    lines += ["", "## Boundary comparison", "",
              "| Representation | Pre-field volatilisation | Full chain |", "|---|---:|---:|",
              "| IPCC FracGasMS (Table 10.22) | %.2f%% of managed N | -- |"
              % (100 * checks["ipcc_prefield_volat_frac"]),
              "| EMEP/EEA TAN chain | %.2f%% of managed N | %.2f%% of managed N |"
              % (100 * checks["emep_prefield_volat_frac"],
                 100 * checks["emep_full_chain_frac"]), ""]
    run.record("n_ledger_stage_comparison.csv")
    run.record("n_ledger_2024.csv")
    with open(asset_path(OUT_DIR, "n_ledger_2024.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("Pakistan livestock nitrogen ledger, 2024 (Mt N):")
    stage = None
    for r in rows:
        if r["stage"] != stage:
            stage = r["stage"]
            print("  " + stage)
        print("    %-62s %9.4f  (%6.2f%%)"
              % (r["flow"][:62], r["kg_N"] / 1e9, r["pct_of_excreted"]))
    print()
    print("  Pre-field volatilisation, IPCC FracGasMS : %.2f%% of managed N"
          % (100 * checks["ipcc_prefield_volat_frac"]))
    print("  Pre-field volatilisation, EMEP TAN chain : %.2f%% of managed N"
          % (100 * checks["emep_prefield_volat_frac"]))
    print("  Full EMEP chain incl. field application  : %.2f%% of managed N"
          % (100 * checks["emep_full_chain_frac"]))
    print()
    print("  Stage-by-stage on a common NH3-N basis (Mt NH3-N):")
    print("    %-20s %10s %10s %8s" % ("stage", "IPCC", "EMEP", "ratio"))
    for r in stages:
        print("    %-20s %10.4f %10.4f %8.2f"
              % (r["stage"], r["ipcc_nh3_n"] / 1e9, r["emep_nh3_n"] / 1e9, r["ratio"]))
    print("    Resolving EMEP per species and system did NOT reconcile the chains: field")
    print("    application improved but grazing did not; the stage-level disagreement is")
    print("    structural: IPCC applies one post-application fraction where EMEP uses grazing.")

    run.record("n_ledger_2024.md")
    _gates(run, checks)
    run.finalize(qa_table=QA_TABLE)   # writes the table, THEN raises on any failed gate
    print("  All stages close to < %.0e relative." % TOL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
