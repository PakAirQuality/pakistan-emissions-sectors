"""Structural uncertainty in NH3 and manure N2O from the manure-management split.

The Monte-Carlo interval on ammonia is PARAMETRIC: it varies the emission factors and activity data
while holding the manure-management configuration fixed. But this work's own diagnosis is that the
management split -- how excreted nitrogen divides between grazing, confined systems and dung fuel --
is the dominant uncertainty, is not measured for Pakistan, and is disputed between external sources
by more than a factor of four at the per-head level.

A +/-25% parametric band therefore cannot be read as the uncertainty on the national NH3 total. This
module supplies the missing dimension: the same engine under alternative, individually defensible
management configurations, reported alongside the central estimate rather than described in prose.

Configurations
  current            the shipped FAOSTAT-consistent split (data/mms_shares.csv)
  benchmark-like     high grazing, low confinement -- the configuration implied by the South Asian
                     benchmark's back-calculated per-head factor
  GLEAM 3.0          FAO's South Asia split (data/gleam_mms.csv): no buffalo grazing at all
  evidence-weighted  the mean of the three, as a deliberately agnostic middle case

Usage:  python3 -m pkinv.eval.mms_structural_uncertainty
Writes: outputs/eval/mms_structural_uncertainty.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import copy
import csv
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData  # noqa: E402
from pkinv.sectors.agriculture.run_inventory import build_components  # noqa: E402
from pkinv.sectors.agriculture import air_pollutants as ap  # noqa: E402
from pkinv.sectors.agriculture import manure  # noqa: E402

from pkinv.paths import ROOT

OUT = asset_path(ROOT, "outputs", "eval")
GLEAM = asset_path(ROOT, "data", "gleam_mms.csv")
MANAGED = manure.MANAGED_SYSTEMS


def _gleam():
    mms = {}
    for r in _activity_rows(GLEAM, comments=False):
        mms.setdefault(r["species"], {})[r["system"]] = float(r["share"])
    return mms


def _high_grazing(base):
    """Shift confined manure to pasture, holding the dung-fuel diversion fixed.

    The benchmark's implied per-head buffalo factor is only reachable if buffalo manure is largely
    grazing-deposited (6% loss) rather than passing through housing, storage and application (49.5%).
    This configuration expresses that reading: two thirds of the confined share moves to pasture.
    """
    out = {}
    for sp, shares in base.items():
        s = dict(shares)
        managed = sum(s.get(k, 0.0) for k in MANAGED)
        if managed <= 0:
            out[sp] = s
            continue
        moved = managed * (2.0 / 3.0)
        for k in MANAGED:
            if k in s:
                s[k] *= (1.0 / 3.0)
        s["pasture_range_paddock"] = s.get("pasture_range_paddock", 0.0) + moved
        out[sp] = s
    return out


def _mean_of(configs, species):
    """Share-wise mean across configurations, renormalised per species."""
    out = {}
    for sp in species:
        systems = set()
        for c in configs:
            systems |= set(c.get(sp, {}))
        s = {k: sum(c.get(sp, {}).get(k, 0.0) for c in configs) / len(configs) for k in systems}
        tot = sum(s.values())
        out[sp] = {k: v / tot for k, v in s.items()} if tot else s
    return out


def _run(label, mms):
    data = InventoryData()
    data.mms = copy.deepcopy(mms)
    comps = build_components(data)
    air = ap.compute(data)

    def gg(sub):
        return sum(c["emissions_Gg"] for c in comps if c["subitem"] == sub)

    nh3 = sum(r["emissions_kt"] for r in air if r["pollutant"] == "NH3")
    livestock_nh3 = sum(r["emissions_kt"] for r in air if r["pollutant"] == "NH3"
                        and not r["subitem"].startswith(
                            ("NH3 - synthetic fertiliser",
                             "NH3 - crop residues left in field",
                             "Residue burning NH3")))
    _, npools = manure.compute(data)
    return {
        "configuration": label,
        "grazing_share_of_excreted": (npools["FPRP_cattle_N"] + npools["FPRP_other_N"])
        / npools["excreted_N"],
        "NH3_total_kt": nh3,
        "NH3_livestock_kt": livestock_nh3,
        "manure_N2O_Gg": gg("Direct N2O") + gg("Indirect N2O (volatilisation)"),
        "managed_soils_Mt": sum(c["co2e_Mt_AR5"] for c in comps
                                if c["category"] == "Managed soils"),
        # rice and manure category totals so the sensitivity table can source this scenario from the
        # full rerun rather than re-slicing one category (which the coupled ledger makes invalid)
        "rice_Mt": sum(c["co2e_Mt_AR5"] for c in comps if c["category"] == "Rice cultivation"),
        "manure_Mt": sum(c["co2e_Mt_AR5"] for c in comps
                         if c["category"] == "Manure management"),
        "national_total_Mt": sum(c["co2e_Mt_AR5"] for c in comps),
    }


def scenarios():
    base = InventoryData().mms
    gleam = _gleam()
    high = _high_grazing(base)
    species = set(base) | set(gleam)
    mid = _mean_of([base, gleam, high], species)
    return [_run("current (FAOSTAT-consistent)", base),
            _run("benchmark-like (high grazing)", high),
            _run("GLEAM 3.0 South Asia", gleam),
            _run("evidence-weighted mean", mid)]


FIELDS = ["configuration", "grazing_share_of_excreted", "NH3_total_kt", "NH3_livestock_kt",
          "manure_N2O_Gg", "managed_soils_Mt", "national_total_Mt"]


def main():
    os.makedirs(OUT, exist_ok=True)
    rows = scenarios()
    with open(asset_path(OUT, "mms_structural_uncertainty.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: (r[k] if k == "configuration" else round(r[k], 4)) for k in FIELDS})

    print("Structural uncertainty from the manure-management split:")
    print("  %-32s %8s %10s %10s %9s %9s"
          % ("configuration", "grazing", "NH3 kt", "livestock", "soils Mt", "TOTAL"))
    for r in rows:
        print("  %-32s %8.2f %10.1f %10.1f %9.2f %9.2f"
              % (r["configuration"], r["grazing_share_of_excreted"], r["NH3_total_kt"],
                 r["NH3_livestock_kt"], r["managed_soils_Mt"], r["national_total_Mt"]))
    lo = min(r["NH3_total_kt"] for r in rows)
    hi = max(r["NH3_total_kt"] for r in rows)
    print()
    print("  NH3 spans %.0f-%.0f kt across defensible configurations (%.2fx), against a parametric"
          % (lo, hi, hi / lo))
    print("  95%% interval of about +/-25%% at fixed configuration. The structural term is the larger")
    print("  of the two and is not represented in the Monte-Carlo band.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
