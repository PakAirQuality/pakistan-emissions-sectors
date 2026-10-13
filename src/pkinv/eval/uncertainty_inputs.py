"""Document the uncertainty model inputs so the Monte-Carlo is reproducible.

The Monte-Carlo (src/pkinv/inventory/montecarlo.py) draws each category total from a lognormal parameterised
by that category's combined uncertainty, treated as a 95% relative half-width (divide by 1.96 for the
1-sigma lognormal shape) and sampled independently. This script writes the derived per-category
distribution parameters so a reader can reproduce the sampling exactly; the per-factor uncertainties that
feed the combined values are the +/-% column of the emission-factor table (data/emission_factors.csv).

Usage:  python3 -m pkinv.eval.uncertainty_inputs
Writes: outputs/eval/uncertainty_derived.csv
"""

from pkinv.assets import asset_path
import csv
import math
import os

from pkinv.paths import ROOT, OUTPUTS
from pkinv.core.io import write_table

NAT = asset_path(OUTPUTS, "national_totals_2024.csv")
OUT = asset_path(ROOT, "outputs", "eval", "uncertainty_derived.csv")
Z95 = 1.959964      # 95% half-width -> 1 sigma (matches montecarlo.Z95)


def derive():
    rows = []
    for r in csv.DictReader(open(NAT, newline="", encoding="utf-8")):
        pt = float(r["co2e_Mt_AR5"])
        u = float(r["uncert_pct"])
        rel_sd = (u / 100.0) / Z95
        sigma = math.sqrt(math.log(1.0 + rel_sd * rel_sd))  # core.montecarlo convention
        # mean-preserving lognormal: draw = pt * exp(N(0,sigma) - sigma^2/2); median = pt*exp(-sigma^2/2)
        median = pt * math.exp(-sigma * sigma / 2.0)
        mu = math.log(pt) - sigma * sigma / 2.0         # lognormal location parameter
        rows.append({"category": r["category"], "point_Mt": round(pt, 2),
                     "combined_uncert_pct_95": round(u, 1), "lognormal_mu": round(mu, 3),
                     "lognormal_sigma": round(sigma, 4), "implied_median_Mt": round(median, 2),
                     "distribution": "lognormal", "correlation": "independent"})
    return rows


def main():
    rows = derive()
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    write_table(OUT, ["category", "point_Mt", "combined_uncert_pct_95",
                                          "lognormal_mu", "lognormal_sigma", "implied_median_Mt",
                                          "distribution", "correlation"], rows)
    print("Uncertainty model inputs -> outputs/eval/uncertainty_derived.csv")
    for r in rows:
        print("  %-28s pt %6.1f  +/-%4.1f%% (95%%)  mu %6.3f  sigma %.3f"
              % (r["category"], r["point_Mt"], r["combined_uncert_pct_95"],
                 r["lognormal_mu"], r["lognormal_sigma"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
