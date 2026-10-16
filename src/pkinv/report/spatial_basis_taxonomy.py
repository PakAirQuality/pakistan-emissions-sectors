"""Mass-weighted spatial evidence classes and their limits.

The semantic fact joins each stream-year mass to its actual placement evidence.
This producer publishes class definitions and national/reporting-sector shares,
including explicit modelled demographics, calendar proxies, and backward/forward
reference-pattern reuse. Evidence shares are not uncertainty probabilities.
"""
import csv
import io
import os

from pkinv.core.io import write_table
from pkinv.paths import OUTPUTS

SRC = os.path.join(OUTPUTS, "semantic", "fact_spatial_basis_year.csv")
OUT_CLASSES = os.path.join(OUTPUTS, "pakemis_spatial_basis_classes.csv")
OUT_SHARES = os.path.join(OUTPUTS, "pakemis_spatial_basis_shares.csv")
OUT_SECTOR = os.path.join(OUTPUTS, "pakemis_spatial_basis_shares_by_sector.csv")

# The closed vocabulary, in the order the shares are printed. `plain_name` is what a
# figure legend or a sentence may call the class; `what_it_supports` is the claim a reader
# may make from a cell in that class and `what_it_does_not` the one they may not.
CLASSES = (
    ("annual_observed_activity", "that year's observed activity",
     "the district pattern is built from activity records of the same fiscal year "
     "(a plant-fuel ledger, a generation panel, a district crop or livestock table)",
     "where a district's mass sits in that year, and how it moved between years",
     "nothing beyond the records' own resolution: a station pool that does not cover all "
     "of the year's fuel leaves the remainder on a fallback raster, priced per period in "
     "pakemis_grid_fallbacks_by_year.csv"),
    ("calendar_activity_proxy", "a calendar-year activity proxy",
     "dated calendar-year activity is used as a proxy for a July–June spatial pattern; "
     "the actual calendar period is recorded separately from the fiscal target",
     "placement conditional on the named calendar-year proxy",
     "observed complete fiscal-year activity or emission geography"),
    ("modelled_population_proxy", "a census-based demographic proxy",
     "fiscal-mean district population is interpolated or projected from census anchors; "
     "household panels retain the named HIES survey's fuel strata; population source "
     "years and survey reuse are recorded separately",
     "a conditional allocation using the stated demographic model and fixed raster",
     "observed annual district activity or observed changes in household fuel geography"),
    ("static_structural", "a timeless structural surface",
     "a surface that does not change with time (built-up area, road network, population "
     "grid, soil or land-cover class) spreads the year's national or provincial mass; the "
     "same surface serves every period, the reference year included",
     "where mass of this kind is likely to be, given the year's total",
     "any change in the district pattern between years: the pattern cannot move because "
     "the surface does not; year-on-year differences at district grain are the totals' "
     "differences and nothing else"),
    ("reference_shape_backcast", "the reference year's pattern, rescaled",
     "the FY2023-24 district shape of the stream rescaled to the year's mass",
     "a district share that is the reference year's",
     "a pattern of the year's own: a district's share is the reference year's, so a "
     "change between this year and the reference year is a change in totals only"),
    ("reference_shape_forward", "a reference district pattern reused later",
     "a later fiscal period lacks its own usable district panel, so the cube retains "
     "the declared reference district category pattern",
     "an allocation conditional on retaining that reference geography",
     "observed later-year district activity or measured local changes after the reference"),
    ("substituted_surface", "a declared stand-in surface",
     "the stream's own geography is unavailable for the year and a declared substitute "
     "(usually built-up area) carries it; the substitution is named per stream",
     "a placement to the resolution of the substitute, declared as such",
     "a placement on the stream's own objects; nothing located here should be read as a "
     "facility or a field"),
    ("unallocated", "retained at province level",
     "mass with a provincial total and no district geography at all (domestic aviation, "
     "the closure identity's remainder)",
     "the provincial total",
     "any district statement; the mass is absent from every district table by design"),
)
CLASS_IDS = tuple(c[0] for c in CLASSES)

CLASS_FIELDS = ("spatial_time_basis", "plain_name", "definition", "what_it_supports",
                "what_it_does_not_support")
SHARE_FIELDS = ("configuration_id", "period_id", "spatial_time_basis", "plain_name", "co2e_Mt_AR5",
                "share_of_period", "n_streams", "period_total_Mt")
SECTOR_FIELDS = ("configuration_id", "period_id", "reporting_sector", "spatial_time_basis", "plain_name",
                 "co2e_Mt_AR5", "share_of_sector_period", "n_streams",
                 "sector_period_total_Mt")


def _rows():
    with io.open(SRC, encoding="utf-8") as handle:
        return list(csv.DictReader(line for line in handle if not line.startswith("#")))


def build():
    rows = _rows()
    unknown = sorted({r["spatial_time_basis"] for r in rows} - set(CLASS_IDS))
    if unknown:
        raise SystemExit("fact_spatial_basis_year carries classes outside the declared "
                         "vocabulary: %s - extend CLASSES before publishing shares"
                         % unknown)
    names = {c[0]: c[1] for c in CLASSES}
    names = {c[0]: c[1] for c in CLASSES}
    configurations = sorted({r["configuration_id"] for r in rows})
    sectors = sorted({r["reporting_sector"] for r in rows})
    nat, sec = {}, {}
    for r in rows:
        mt, n = float(r["co2e_Mt_AR5"]), int(r["n_streams"])
        k = (r["configuration_id"], r["period_id"], r["spatial_time_basis"])
        nat[k] = (nat.get(k, (0.0, 0))[0] + mt, nat.get(k, (0.0, 0))[1] + n)
        k2 = (r["configuration_id"], r["period_id"], r["reporting_sector"], r["spatial_time_basis"])
        sec[k2] = (sec.get(k2, (0.0, 0))[0] + mt, sec.get(k2, (0.0, 0))[1] + n)
    share_rows, sector_rows = [], []
    for cfg in configurations:
        periods = sorted({r["period_id"] for r in rows if r["configuration_id"] == cfg})
        for p in periods:
            total = sum(nat.get((cfg, p, c), (0.0, 0))[0] for c in CLASS_IDS)
            for c in CLASS_IDS:
                mt, n = nat.get((cfg, p, c), (0.0, 0))
                share_rows.append({"configuration_id": cfg, "period_id": p,
                    "spatial_time_basis": c, "plain_name": names[c], "co2e_Mt_AR5": "%.6f" % mt,
                    "share_of_period": "%.6f" % (mt / total if total else 0.0),
                    "n_streams": n, "period_total_Mt": "%.6f" % total})
            for sector in sectors:
                st = sum(sec.get((cfg, p, sector, c), (0.0, 0))[0] for c in CLASS_IDS)
                if st == 0 and not any((cfg, p, sector, c) in sec for c in CLASS_IDS):
                    continue
                for c in CLASS_IDS:
                    mt, n = sec.get((cfg, p, sector, c), (0.0, 0))
                    sector_rows.append({"configuration_id": cfg, "period_id": p,
                        "reporting_sector": sector, "spatial_time_basis": c,
                        "plain_name": names[c], "co2e_Mt_AR5": "%.6f" % mt,
                        "share_of_sector_period": "%.6f" % (mt / st if st else 0.0),
                        "n_streams": n, "sector_period_total_Mt": "%.6f" % st})
    class_rows = [dict(zip(CLASS_FIELDS, c)) for c in CLASSES]
    return class_rows, share_rows, sector_rows


def main():
    class_rows, share_rows, sector_rows = build()
    write_table(OUT_CLASSES, CLASS_FIELDS, class_rows, banner=(
        "# The spatial evidence vocabulary (spatial_time_basis), defined in plain words.",
        "# pkinv.report.spatial_basis_taxonomy; the registry is pakemis_spatial_weights_by_year.csv.",))
    write_table(OUT_SHARES, SHARE_FIELDS, share_rows, banner=(
        "# Mass-weighted share of each period's emissions by spatial evidence class, national.",
        "# From outputs/semantic/fact_spatial_basis_year.csv; every period x class cell printed, zero included.",))
    write_table(OUT_SECTOR, SECTOR_FIELDS, sector_rows, banner=(
        "# Mass-weighted share of each period's emissions by spatial evidence class, per IPCC reporting sector.",
        "# From outputs/semantic/fact_spatial_basis_year.csv; every period x sector x class cell printed, zero included.",))
    ref = {r["spatial_time_basis"]: r for r in share_rows if r["period_id"] == "FY2023-24" and r["configuration_id"] == "S_TAN"}
    print("spatial_basis_taxonomy: %d periods per configuration; FY2023-24 S_TAN %s"
          % (len({r["period_id"] for r in share_rows}),
             ", ".join("%s %.1f%%" % (c, 100 * float(ref[c]["share_of_period"])) for c in CLASS_IDS)))


if __name__ == "__main__":
    main()
