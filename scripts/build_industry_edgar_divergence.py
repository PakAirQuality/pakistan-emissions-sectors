"""The engine's industrial series against EDGAR's, every fiscal year - a DIAGNOSTIC of shape.

Two comparisons per fiscal year, both at EDGAR's fiscal blend (half of each adjacent calendar
column, the transport lane's convention):
  * 1.A.2: the engine's industry module + the captive generation the power module computes
    (both IPCC 1.A.2) against EDGAR 'Industrial Combustion';
  * the covered industrial aggregate: the above + cement 2.A.1 against EDGAR 'Industrial
    Combustion' + 'Processes' WITHOUT the F-gases (the engine prices no F-gas; EDGAR's Processes
    also hold ammonia, nitric acid, lime, glass, steel and non-energy products the engine
    screens or lacks - so the second comparison brackets the engine LOW by construction).
What the table shows (rc50 atoms): from FY2015-16 through FY2021-22 the two 1.A.2 series differ
by -4.6..+6.6 Mt with ALTERNATING sign (the engine's FY2020-21 peak sits 6.6 Mt above EDGAR's);
in FY2022-23 and FY2023-24 the engine falls 17.9 and 17.5 Mt BELOW EDGAR - the two years in
which HDIP's power allocation sits ABOVE NEPRA's metered burn (pakemis_coal_balance.csv, H2).
The break is confined to the seam, not spread over the series. EDGAR is IEA-balance-derived and HDIP-fed upstream, and its 2023-2024 columns are
preliminary: this is evidence about WHERE the compilations part, never an independent
verification and never a residual to insert (the boundary ledger's rule).

Reads:  outputs/semantic/fact_annual.csv, data/activity/industry/edgar_pak_industry_series.csv
Writes: outputs/pakemis_industry_edgar_divergence.csv
"""
import csv
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, OUTPUTS  # noqa: E402

FACTS = asset_path(OUTPUTS, "semantic", "fact_annual.csv")
SERIES = asset_path(DATA, "activity", "industry", "edgar_pak_industry_series.csv")
OUT = asset_path(OUTPUTS, "pakemis_industry_edgar_divergence.csv")
REF = "REF_2023_24"
FIELDS = ("period_id", "engine_industry_module_mt", "engine_captive_1a2_mt", "engine_1a2_mt",
          "engine_cement_2a1_mt", "engine_covered_industrial_mt",
          "edgar_basis", "edgar_industrial_combustion_mt", "edgar_processes_excl_fgas_mt",
          "edgar_fgas_mt", "edgar_industrial_total_mt",
          "divergence_1a2_mt", "divergence_1a2_pct", "divergence_covered_excl_fgas_mt", "reading")
HEADER = """\
# THE ENGINE'S INDUSTRIAL SERIES AGAINST EDGAR'S, EVERY FISCAL YEAR - a diagnostic of SHAPE, never a
# residual. divergence = engine - EDGAR at EDGAR's fiscal blend (0.5 x CY(Y-1) + 0.5 x CY(Y) for FYY-1/Y).
# 1.A.2 = industry module + captive generation (power module, IPCC 1.A.2). covered = 1.A.2 + cement 2.A.1.
# EDGAR 'Processes' is ALL of IPPU; its F-gases are kept apart and the covered comparison excludes them,
# so that comparison brackets the engine LOW by construction (ammonia, nitric, lime, glass, steel,
# non-energy products are screened or absent here). EDGAR is IEA-balance-derived and HDIP-fed upstream;
# 2023-2024 preliminary. scripts/build_industry_edgar_divergence.py
"""


def _rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def engine_terms():
    terms = defaultdict(lambda: defaultdict(float))
    for r in _rows(FACTS):
        if r["configuration_id"] != REF or r["geography_id"] != "PK":
            continue
        v = float(r["co2e_Mt_AR5"])
        p = r["period_id"]
        if r["sector_id"] == "industry":
            terms[p]["industry"] += v
        elif r["sector_id"] == "power" and r["ipcc_code"] == "1.A.2":
            terms[p]["captive"] += v
        elif r["sector_id"] == "ippu" and r["ipcc_code"].startswith("2.A.1"):
            terms[p]["cement"] += v
    return terms


def edgar_terms():
    by = {}
    for r in _rows(SERIES):
        by[(r["sector"], int(r["year"]))] = r
    return by


def blend(by, sector, end_year, col):
    a, b = by[(sector, end_year - 1)], by[(sector, end_year)]
    return 0.5 * float(a[col] or 0) + 0.5 * float(b[col] or 0)


def reading(d):
    if abs(d) <= 2.0:
        return "within 2 Mt of EDGAR"
    return "engine %s EDGAR by %.1f Mt" % ("below" if d < 0 else "above", abs(d))


def build():
    eng, ed = engine_terms(), edgar_terms()
    out = []
    for p in sorted(eng):
        y = int(p[2:6]) + 1                      # FY2015-16 -> 2016
        t = eng[p]
        e_1a2 = t["industry"] + t["captive"]
        e_cov = e_1a2 + t["cement"]
        ic = blend(ed, "Industrial Combustion", y, "total_Mt_co2e_AR5")
        pr_total = blend(ed, "Processes", y, "total_Mt_co2e_AR5")
        fgas = blend(ed, "Processes", y, "fgas_co2e_Mt")
        pr_ex = pr_total - fgas
        d1 = e_1a2 - ic
        out.append({
            "period_id": p,
            "engine_industry_module_mt": "%.3f" % t["industry"], "engine_captive_1a2_mt": "%.3f" % t["captive"],
            "engine_1a2_mt": "%.3f" % e_1a2, "engine_cement_2a1_mt": "%.3f" % t["cement"],
            "engine_covered_industrial_mt": "%.3f" % e_cov,
            "edgar_basis": "0.5 x CY%d + 0.5 x CY%d" % (y - 1, y),
            "edgar_industrial_combustion_mt": "%.3f" % ic, "edgar_processes_excl_fgas_mt": "%.3f" % pr_ex,
            "edgar_fgas_mt": "%.3f" % fgas, "edgar_industrial_total_mt": "%.3f" % (ic + pr_total),
            "divergence_1a2_mt": "%.3f" % d1, "divergence_1a2_pct": "%.1f" % (100.0 * d1 / ic),
            "divergence_covered_excl_fgas_mt": "%.3f" % (e_cov - ic - pr_ex),
            "reading": reading(d1),
        })
    return out


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
    print("industry vs EDGAR divergence -> %s (%d periods)" % (os.path.relpath(OUT), len(rows)))
    for r in rows:
        print("  %s engine 1.A.2 %7s  EDGAR IC %7s  d %7s  %s" % (r["period_id"], r["engine_1a2_mt"],
              r["edgar_industrial_combustion_mt"], r["divergence_1a2_mt"], r["reading"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
