"""The national inventory in twelve months - every module, every stream, every gas.

WHAT THIS ADDS. Nothing to the total. E(s,m) = E(s).p(s,m) with sum_m p = 1, so the twelve
months reproduce the annual national figure exactly and every profile in the inventory could
be wrong without moving it by a gramme. What the layer adds is a dimension: *when*, with the
evidence for the timing declared separately from the evidence for the quantity, because they
are not the same evidence and an inventory that reports one resolution for both invites the
reader to trust the weaker of them.

WHY IT IS ASSEMBLED HERE AND NOT SUMMED FROM FILES. Each module writes its own layer, and a
national product built by concatenating those CSVs would close against whatever was last
written rather than against what the engine computes today. This calls every registered
module's layer and then closes it against registry.build_all() - the same annual components
the national rollup, the uncertainty run and the category ledger are built from. A module
whose layer had drifted from its engine would fail here, not publish.

THE CLASS DISTRIBUTION IS THE POINT. 8a reported the evidence and spatial axes over the
national total; this reports the third. The honest headline is that most of the inventory is
flat: agriculture's livestock categories are a census stock with no month at all, and the
streams with a genuinely observed monthly basis are the petroleum ones, because OCAC is the
only Pakistani statistical series in this inventory that publishes monthly.

AND THE ANNUAL DECLARATION IS NOW CHECKABLE. Every component carries a temporal_method from
8a, which until there was a layer was a claim about evidence nobody had used. Reconciling the
two moved 34 of 184 rows, in both directions: aviation's T1 became T2 because FY2023-24's OCAC
editions are cumulative and only July is read directly; road CNG, power's bagasse, field
burning and 16 Mt of livestock-origin soil nitrogen fell to T4 because the shapes their
declarations implied were never assembled; residential charcoal rose to T3 with the rest of
its sector. tests/test_monthly_layer.py asserts they agree from here on.

Usage:  python3 -m pkinv.report.monthly_all
Writes: outputs/national_monthly_2024.csv, outputs/temporal_profile.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import monthly as core_monthly
from pkinv.core import registry
from pkinv.paths import OUTPUTS

FY_START = 2023
OUT = asset_path(OUTPUTS, "national_monthly_2024.csv")
PROFILE_OUT = asset_path(OUTPUTS, "temporal_profile.csv")

FIELDS = ("sector",) + core_monthly.FIELDS


def build():
    """(month rows tagged with their sector, annual components) across every module."""
    rows, components = [], []
    for sector in registry.all_sectors():
        annual, month_rows = registry.monthly_layer(sector.NAME).rows()
        for r in month_rows:
            rows.append(dict(r, sector=sector.NAME))
        components.extend(dict(c, _sector=sector.NAME) for c in annual)
    return rows, components


def check(rows):
    """Close the layer against the engine, component by component. Raises.

    The control is registry.build_all(), not the components each layer happened to hand back:
    a layer that quietly built its own variant of the sector - a different vintage, a
    different scenario, combustion only - would close against itself and disagree with the
    published inventory, which is the failure mode this whole file exists to make impossible.
    """
    annual, _categories, _sector_of = registry.build_all()
    core_monthly.check_closure(rows, annual)
    return annual


def by_class(rows):
    """{T-class: national CO2e Mt} - the temporal analogue of evidence.summarise."""
    out = {}
    for r in rows:
        out[r["temporal_method"]] = out.get(r["temporal_method"], 0.0) + r["co2e_Mt_AR5"]
    return dict(sorted(out.items()))


def sector_classes(rows):
    """{sector: {T-class: Mt}}, so a reader can see which module carries which class."""
    out = {}
    for r in rows:
        out.setdefault(r["sector"], {})
        out[r["sector"]][r["temporal_method"]] = (
            out[r["sector"]].get(r["temporal_method"], 0.0) + r["co2e_Mt_AR5"])
    return {s: dict(sorted(v.items())) for s, v in sorted(out.items())}


def write(rows, path=OUT):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(FIELDS)
        for r in sorted(rows, key=lambda x: (x["sector"], x["category"], x["subitem"],
                                             x["gas"], x["month"])):
            w.writerow([r["sector"], r["category"], r["subitem"], r["gas"], r["month"],
                        round(r["share"], 8), round(r["emissions_Gg"], 8),
                        round(r["co2e_Mt_AR5"], 10), round(r["co2e_Mt_AR6"], 10),
                        r["temporal_method"], r["basis"]])
    return path


def write_profile(rows, path=PROFILE_OUT):
    """The class distribution, nationally and per module, as a generated table."""
    national = by_class(rows)
    grand = sum(national.values())
    per_sector = sector_classes(rows)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scope", "temporal_method", "co2e_Mt_AR5", "share_of_scope_pct"])
        for cls, mt in national.items():
            w.writerow(["NATIONAL", cls, round(mt, 4), round(100 * mt / grand, 2)])
        for sector, classes in per_sector.items():
            total = sum(classes.values())
            for cls, mt in classes.items():
                w.writerow([sector, cls, round(mt, 4), round(100 * mt / total, 2)])
    return path


def main():
    rows, _annual_from_layers = build()
    check(rows)
    write(rows)
    write_profile(rows)

    totals = core_monthly.month_totals(rows)
    grand = sum(totals.values())
    national = by_class(rows)
    peak, trough = max(totals, key=totals.get), min(totals, key=totals.get)

    print("national monthly layer -> %s" % OUT)
    print("  %d rows, %d modules, closes to the annual inventory exactly (%.2f Mt)"
          % (len(rows), len(registry.SECTOR_MODULES), grand))
    print("  peak %s %.2f Mt, trough %s %.2f Mt (flat would be %.2f); ratio %.2f"
          % (peak, totals[peak], trough, totals[trough], grand / 12.0,
             totals[peak] / totals[trough]))
    print("  temporal evidence: "
          + ", ".join("%s %.1f%%" % (c, 100 * mt / grand) for c, mt in national.items()))
    for sector, classes in sector_classes(rows).items():
        total = sum(classes.values())
        print("    %-12s %s" % (sector, ", ".join("%s %.0f%%" % (c, 100 * mt / total)
                                                  for c, mt in classes.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
