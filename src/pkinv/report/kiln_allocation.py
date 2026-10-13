"""The kiln allocation product: the screened coal on the mapped fleet, honestly (rc13).

WHAT THIS ALLOCATES. The brick-kiln screening estimate
(outputs/industry_brick_kiln_screening_2024.csv - outside every reference total,
FY2022-23 vintage) distributed over ADM2, using the 11,272 mapped kiln points where
the detection survey looked and a TESTED fallback where it did not. The coverage
mask's own sentence - "absence means unsurveyed, not zero kilns" - is structural
here, not decorative: 82 of 147 units are unsurveyed, and giving them zero would be
exactly the inference the mask forbids.

THE CONSTRUCTION, EVERY STEP DECLARED.
1. Punjab is FULLY surveyed (36/36 units) and holds the one fuel-split evidence
   beyond the national row: the kiln-census cross-section share 0.8668
   (kiln_screening.PUNJAB_BRICKKILN_SHARE). That share of the national coal rides
   the observed Punjab points, by kiln count per unit (shared geoBoundaries shapes
   split their kilns equally across members, so counts partition).
2. The 0.1332 remainder covers everywhere else - surveyed and unsurveyed alike.
   Surveyed non-Punjab units carry their OBSERVED counts; the 82 unsurveyed units
   carry PREDICTED counts from the benchmark's winning predictor
   (outputs/benchmark_kiln_allocation.csv - population, pooled rho ~0.76),
   calibrated as kilns-per-predictor on the surveyed non-Punjab frame. The
   remainder then distributes over observed + predicted counts together.
3. A per-kiln count weight still assumes equal fuel per kiln - stated, untested,
   and the reason this is an allocation of a SCREENING quantity, not a facility
   emissions register.

THE STATED FINDING. A naive transfer of Punjab's per-kiln coal intensity to the
1,781 observed non-Punjab kilns overshoots the remainder (the print shows the
ratio): the two frames are not exchangeable, which is why the remainder is
allocated as a share, never as intensity x count.

Usage:  python3 -m pkinv.report.kiln_allocation
Writes: outputs/pakemis_kiln_allocation_adm2.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import write_table

ASSETS = asset_path(DATA, "gis", "kilns", "pak_brick_kiln_assets.csv")
COVERAGE = asset_path(DATA, "gis", "kilns", "pak_brick_kiln_coverage.csv")


def kiln_counts():
    """{adm2_id: fractional kiln count}, shared shapes split equally so the
    national count partitions to exactly 11,272 (minus the 5 declared
    outside-boundary points, which have no ADM2 to carry)."""
    counts = {}
    for r in _activity_rows(ASSETS, comments=False):
        ids = [i for i in r["adm2_ids"].split(";") if i]
        if not ids or r["adm2_status"].startswith("unresolved"):
            continue
        for i in ids:
            counts[i] = counts.get(i, 0.0) + 1.0 / len(ids)
    return counts


def build():
    from pkinv.sectors.industry import kiln_screening
    from pkinv.eval import benchmark_kiln_allocation as bench
    ghg, air, meta = kiln_screening.screening()
    total_mt = sum(mt for _g, _gg, mt in ghg)
    pm_low = next(lo for p, lo, _hi in air if p == "PM2.5")
    pm_high = next(hi for p, _lo, hi in air if p == "PM2.5")
    coal_t = meta["coal_tonnes"]

    counts = kiln_counts()
    predictors, _unresolved = bench.proxy_by_adm2()
    predictor_name = bench.winner()

    cov = {}
    for r in _activity_rows(COVERAGE, comments=False):
        cov[r["adm2_id"]] = r

    punjab_share = kiln_screening.PUNJAB_BRICKKILN_SHARE
    punjab_units = {a: c for a, c in counts.items()
                    if cov.get(a, {}).get("province") == "Punjab"}
    punjab_total = sum(punjab_units.values())

    # non-Punjab: observed counts where surveyed, predicted where not
    surveyed_np, unsurveyed = {}, {}
    for adm2_id, row in cov.items():
        if row["province"] == "Punjab":
            continue
        if row["coverage"] == "observed_kilns":
            surveyed_np[adm2_id] = counts.get(adm2_id, 0.0)
        else:
            unsurveyed[adm2_id] = None
    # calibrate kilns-per-predictor on the surveyed non-Punjab frame
    cal_num = sum(surveyed_np.values())
    cal_den = sum(predictors.get(a, {}).get(predictor_name, 0.0)
                  for a in surveyed_np)
    ratio = cal_num / cal_den if cal_den else 0.0
    for adm2_id in unsurveyed:
        unsurveyed[adm2_id] = ratio * predictors.get(adm2_id, {}).get(
            predictor_name, 0.0)
    np_total = sum(surveyed_np.values()) + sum(unsurveyed.values())

    # the stated finding: naive Punjab-intensity transfer vs the remainder
    punjab_intensity = punjab_share * coal_t / punjab_total if punjab_total else 0.0
    naive_np_coal = punjab_intensity * sum(surveyed_np.values())
    remainder_coal = (1.0 - punjab_share) * coal_t

    rows = []
    for adm2_id in sorted(cov):
        province = cov[adm2_id]["province"]
        surveyed = cov[adm2_id]["coverage"] == "observed_kilns"
        if province == "Punjab":
            weight = (punjab_share * punjab_units.get(adm2_id, 0.0) / punjab_total
                      if punjab_total else 0.0)
            frame = "surveyed_points"
            count_obs = punjab_units.get(adm2_id, 0.0)
            count_pred = ""
        elif surveyed:
            weight = ((1.0 - punjab_share) * surveyed_np.get(adm2_id, 0.0)
                      / np_total if np_total else 0.0)
            frame = "surveyed_points"
            count_obs = surveyed_np.get(adm2_id, 0.0)
            count_pred = ""
        else:
            weight = ((1.0 - punjab_share) * unsurveyed[adm2_id] / np_total
                      if np_total else 0.0)
            frame = "unsurveyed_predicted"
            count_obs = ""
            count_pred = unsurveyed[adm2_id]
        note = ("the survey is IGP-scoped and publishes no coverage polygon; "
                "absence here means unsurveyed, not zero kilns - this unit's "
                "weight is PREDICTED (%s-calibrated on the surveyed non-Punjab "
                "frame), never inferred zero" % predictor_name
                if frame == "unsurveyed_predicted" else
                "observed detection counts; shared geoBoundaries shapes split "
                "equally across members; equal fuel per kiln is an assumption, "
                "stated")
        rows.append({
            "adm2_id": adm2_id, "province": province, "frame": frame,
            "kiln_count_observed": round(count_obs, 3) if count_obs != "" else "",
            "kiln_count_predicted": (round(count_pred, 2)
                                     if count_pred != "" else ""),
            "weight_national": round(weight, 8),
            "coal_t_fy2022_23": round(weight * coal_t, 1),
            "co2e_Mt_screening": round(weight * total_mt, 6),
            "pm25_kt_low": round(weight * pm_low, 4),
            "pm25_kt_high": round(weight * pm_high, 4),
            "predictor": predictor_name if frame == "unsurveyed_predicted" else "",
            "note": note})
    finding = {"naive_np_coal_t": naive_np_coal,
               "remainder_coal_t": remainder_coal,
               "overshoot_ratio": (naive_np_coal / remainder_coal
                                   if remainder_coal else 0.0)}
    return rows, finding


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows, finding = build()
    total_w = sum(r["weight_national"] for r in rows)
    if abs(total_w - 1.0) > 1e-6:
        raise SystemExit("kiln allocation weights do not partition: %r" % total_w)
    path = asset_path(OUTPUTS, "pakemis_kiln_allocation_adm2.csv")
    write_table(path, list(rows[0].keys()), rows)
    surveyed_w = sum(r["weight_national"] for r in rows
                     if r["frame"] == "surveyed_points")
    print("kiln allocation -> %s (%d units; weights partition exactly)"
          % (os.path.basename(path), len(rows)))
    print("  surveyed frame carries %.1f%% of the screened coal; the %d "
          "unsurveyed units carry %.1f%% on the benchmark-winning predictor"
          % (100 * surveyed_w,
             sum(1 for r in rows if r["frame"] == "unsurveyed_predicted"),
             100 * (1 - surveyed_w)))
    print("  STATED FINDING: naive Punjab-intensity transfer to observed "
          "non-Punjab kilns gives %.0f kt vs the %.0f kt remainder (x%.2f) - "
          "the frames are not exchangeable, so the remainder allocates as a "
          "share, never intensity x count"
          % (finding["naive_np_coal_t"] / 1e3, finding["remainder_coal_t"] / 1e3,
             finding["overshoot_ratio"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
