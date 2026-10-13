"""The NEPRA/K-Electric reconciliation ladder as ONE published table (rc30).

The eighteenth review asked for the public reconciliation to be finished as an
explicit ladder - physical plant fuel, K-Electric's leg, the national Table-3
account and the plant-implied coal energy, per year, side by side - rather than
as ratios scattered across three outputs. Every number here is READ from an
output the power runner already ships (the boundary audit, the KE leg, the
implied-CV table); nothing is recomputed, so this table cannot become a second
vintage of the arithmetic it summarises.

The national energy per fuel is recovered from the audit's own two ratios
(without-KE and with-KE coverage of the same national row):
    national_TJ = KE_TJ / (with_ratio - without_ratio)
which uses no calorific constant of its own - the point, because the TOE
conversion IS the open question (gap rows coal-toe-ncv and ke-boundary; the
HDIP metadata remains the closing acquisition and letter REQ-HDIP-01 is
drafted). The three configurations stay as named and none is silently
privileged; the reviewer's proposed post-HDIP names map
    hdip_toe_reported  -> inventory_reference (57.82)
    plant_physical_ncv -> power_plant_physical_coal (38.45)
    hdip_toe_plus_ke   -> power_with_kelectric (61.83)

Usage:  python3 scripts/make_power_toe_reconciliation.py
Writes: outputs/power_toe_reconciliation.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.core.io import read_rows

AUDIT = asset_path(OUTPUTS, "power_boundary_audit_fy2023_24.csv")
KE = asset_path(OUTPUTS, "power_ke_leg_fy2023_24.csv")
CV = asset_path(OUTPUTS, "power_implied_coal_cv_fy2023_24.csv")
OUT = asset_path(OUTPUTS, "power_toe_reconciliation.csv")


def _rows(path):
    return read_rows(path, comments=False)


def build():
    audit = {r["fiscal_year"]: r for r in _rows(AUDIT)}
    ke = {r["fiscal_year"]: r for r in _rows(KE)}
    cv = _rows(CV)
    out = []
    for year in sorted(audit):
        a, k = audit[year], ke.get(year, {})
        for fuel, prefix, ke_col in (("gas (incl. RLNG)", "gas", "KE_gas_TJ"),
                                     ("furnace oil", "rfo", "KE_rfo_TJ")):
            without = float(a["%s_without_KE" % prefix])
            with_ke = float(a["%s_with_KE" % prefix])
            ke_tj = float(a[ke_col])
            national = ke_tj / (with_ke - without) if with_ke > without else ""
            cppa = national * without if national else ""
            out.append({
                "fiscal_year": year, "fuel": fuel,
                "rung_national_table3_TJ": round(national) if national else "",
                "rung_cppa_plant_TJ": round(cppa) if cppa else "",
                "rung_ke_plant_TJ": round(ke_tj),
                "coverage_without_ke": without, "coverage_with_ke": with_ke,
                "basis": "national energy recovered from the audit's own ratio pair "
                         "(no calorific constant of this table's own); plant rungs "
                         "from the NEPRA plant ledger; KE rung from the KE leg",
            })
        year_cv = [r for r in cv if r["fiscal_year"] == year
                   and r["implied_cv_TJ_per_Gg"] and r["mass_kt"]]
        if year_cv:
            implied = sum(float(r["mass_kt"]) * float(r["implied_cv_TJ_per_Gg"])
                          for r in year_cv)
            out.append({
                "fiscal_year": year, "fuel": "coal (plant-implied energy)",
                "rung_national_table3_TJ": "",
                "rung_cppa_plant_TJ": round(implied),
                "rung_ke_plant_TJ": 0,
                "coverage_without_ke": "", "coverage_with_ke": "",
                "basis": "sum of ledger mass x heat-rate-implied CV over %d plants; "
                         "the Table-3 comparison is the open coal-toe-ncv question "
                         "(x~2 at FY2023-24) and is NOT settled here - see the "
                         "power_grid_control configuration family and REQ-HDIP-01"
                         % len(year_cv),
            })
    return out


def main():
    rows = build()
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        f.write("# The NEPRA/K-Electric reconciliation ladder, assembled from shipped "
                "outputs only (rc30).\n"
                "# The three power configurations remain co-published and unprivileged; "
                "the HDIP metadata is the closing acquisition.\n")
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print("power TOE reconciliation -> %s (%d rungs over %d years)"
          % (OUT, len(rows), len({r['fiscal_year'] for r in rows})))


if __name__ == "__main__":
    import sys as _sys
    if "--check" in _sys.argv[1:]:
        # re-derive into a temporary directory and compare; nothing in the tree is written
        from pkinv.core.checkmode import compare_only
        _sys.exit(compare_only(globals(), ("OUT",), main))
    main()
