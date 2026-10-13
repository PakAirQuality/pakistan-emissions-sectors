"""Can NEPRA's coal ENERGY and NEPRA's coal MASS describe the same fleet? They cannot.

WHY THIS EXISTS. The power grid-control family carries three readings of the same national
coal combustion - 57.820 Mt on the reference, 38.452 Mt on "coal at implied calorific
values", 61.834 Mt on the widened scope - and the release publishes them as co-equal
members of one family because nothing had adjudicated between them. Two of the three are a
disagreement between two tables of the SAME NEPRA State of Industry Report: Table 3, which
reports fuel consumed in tonnes of oil equivalent, and Table 21, which reports fuel
quantities and generation per station. This tests whether they can both be right.

THE TEST THAT DOES NOT DEPEND ON MASS. Divide each energy figure by the coal generation
NEPRA itself reports and read off the net thermal efficiency it implies. A coal station runs
at 33-42 per cent; above about 45 is no longer a coal plant and below about 30 is a fleet in
serious trouble. Table 3's energy implies 57.4 per cent in FY2020-21 and 18.9 per cent in
FY2023-24. No thermal fleet spans that range, and the swing is not a boundary difference:
a plant set that is too wide makes energy too HIGH in every year, and cannot also make it
too low. The plant-level route - Table 21 masses with each station's own metered heat rate -
implies 32.4 to 45.7 per cent across the same five years, which is a fleet.

WHICH RATIO MOVES, WHICH IS NOT THE SAME AS WHERE THE BREAK IS. Table 3 states that it takes
its figures
from the HDIP Pakistan Energy Yearbook, and HDIP's own power-sector coal MASS is held here
too - republished in the Pakistan Economic Survey's statistical supplement, Table 14.1(4).
Against that mass Table 3's TOE per tonne is 0.447 in FY2019-20 and 0.447 in FY2020-21,
identical to three figures, then 0.604, 0.511, 0.478. So Table 3's conversion is not what
doubles - it spreads 1.35x where the Table 21 ratio spreads 2.03x. What doubles is the ratio
of the two MASS ACCOUNTS: HDIP's national power-coal
series against NEPRA's own per-station quantities runs 0.88, 0.70, 1.05, 1.11, 1.21 - HDIP
30 per cent LOWER in FY2020-21 and 21 per cent HIGHER by FY2023-24, crossing unity between
them. A scope difference cannot cross unity; a consumption-versus-receipts difference could,
in either direction, and nothing held settles which.

ONE STATION ACCOUNTS FOR THE FY2021-22 CROSSING, THOUGH NOT FOR THE CROSSING ITSELF. Sahiwal
prints 1,443.97 kt against 6,881.4 GWh in FY2021-22 - 4.766 GWh per kilotonne, where its own
other four years run 2.716, 2.670, 2.438 and 2.689. At its own mean that generation needs
about 2,618 kt, so roughly 1,174 kt is missing from a NEPRA table and no diagnostic in this
repository had named it. Putting it back moves FY2021-22's HDIP-over-Table-21 ratio from
1.053 to 0.961, which is below unity: the series would read 0.88, 0.70, 0.96, 1.11, 1.21.
So the CROSSING SURVIVES - FY2022-23 and FY2023-24 are still above unity and a scope
difference still cannot produce that - but the year the crossing is attributed to is wrong,
and an argument built on FY2021-22 in particular rests on a station-level error rather than
on a national one.

WHAT THAT DOES NOT SHOW. The paragraph above is about variance, and an earlier version of it
concluded about location - that the break "is not in a conversion". Decomposing the level
discrepancy against the non-circular physical route puts 59 to 84 per cent of it in the
CONVERSION channel in every year (conversion_channel_share_pct). The two readings are
compatible: the conversion is both the steadier ratio and the larger share of the level
error, because the steadiness of a ratio says nothing about which factor carries a level
difference. The register of hypotheses this steered toward the mass accounts should be read
again with that corrected.

AND THE PHYSICAL TEST PICKS ONE. Take each mass account at the fleet's own rank composition
(IPCC default calorific values, no heat rates) and divide the electricity out of it. NEPRA's
per-station mass gives 34.4 to 38.7 per cent in every one of the five years - a fleet, in
the admissible band throughout. HDIP's national series gives 49.0 falling to 29.1, outside
at both ends. Table 3's published energy, which is HDIP's mass times its conversion, gives
57.5 falling to 18.9. Of the three accounts of the same coal, one is physically admissible
across the panel and two are not.

THE HEAT-RATE ROUTE CORROBORATES THE CALORIFIC VALUE AND NOT THE EFFICIENCY. Each station's
own metered heat rate
with its own tonnage gives a fleet calorific value falling 23.0 to 12.0 TJ/Gg as the Thar
fleet ramps; rank composition alone gives 21.5 to 13.0. Two routes, one using no rank
defaults and the other no heat rates, agreeing within 1-3 TJ/Gg and agreeing on direction.
Table 3's implied value RISES over the same years, 16.6 to 24.2, because its mass account
rises faster than the fleet's calorific value falls.

That agreement is on the CALORIFIC VALUE, where the two routes really are independent - one
uses rank defaults and no heat rates, the other heat rates and no rank defaults. It does not
extend to the efficiency. The heat-rate route's energy is its CV times mass, and that CV is
itself generation x heat rate / mass, so the product returns generation x heat rate and the
efficiency is NEPRA's printed heat rates rearranged: where the CV covers all the mass the
identity holds to 1.000 and 0.986. An earlier version of this section read the two routes as
independent corroboration of the fleet EFFICIENCY. Only the composition route is independent
of NEPRA's heat rates, and only it can place the fleet in a band.

WHAT THIS DOES NOT ESTABLISH. It does not show what Table 3's energy column is measuring,
and it does not license moving the reference: the reference rides Table 3 and changing that
is a pin re-base, not an audit. What it establishes is narrower and sufficient - the three
family members are NOT three equally supported readings of one quantity. Two of them rest
on a pairing of NEPRA tables that cannot hold in any year, and only one route stays
physically admissible across the whole panel.

Usage:  python3 -m pkinv.sectors.power.coal_energy_adjudication [--check]
        (run_power calls main() between the implied-CV diagnostic it reads
         and the hypotheses register that reads this)
Writes: outputs/pakemis_power_coal_energy_adjudication.csv
"""
import argparse
import collections
import csv
import io
import math
import os

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_table
from pkinv.paths import DATA, OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_power_coal_energy_adjudication.csv")

TOE_TJ = 41.868e-3          # 1 tonne of oil equivalent = 41.868 GJ = 0.041868 TJ
GWH_TJ = 3.6

# IPCC 2006 Vol.2 Ch.1 Table 1.2 net calorific values, TJ/Gg. Lucky Electric's origin is
# blank in the ledger; its own implied CV is 11.4-12.1, which is lignite, and the coal-blend
# table already carries it as the declared residual - so it is weighted as lignite here and
# the row says so.
NCV_BY_RANK = {"Thar lignite": 11.9, "unknown": 11.9, "imported": 25.8}
LIGNITE_RANKS = ("Thar lignite", "unknown")

# What a coal station can physically do. Not a tuning knob: the lower bound is a poor
# subcritical unit and the upper is an ultra-supercritical one, and the point of the test is
# that one of the two routes leaves the band in both directions.
COAL_EFF_LO, COAL_EFF_HI = 30.0, 45.0

FIELDS = ("period_id", "fiscal_start_year", "table3_coal_toe", "table21_mass_kt",
          "hdip_mass_kt", "hdip_over_table21", "table3_toe_per_hdip_tonne",
          "hdip_mass_implied_efficiency_pct", "table21_mass_implied_efficiency_pct",
          "coal_generation_GWh", "lignite_share_of_mass_pct", "table3_toe_per_tonne",
          "table3_energy_TJ", "table3_implied_ncv_TJ_per_Gg", "table3_implied_efficiency_pct",
          "plant_energy_TJ", "plant_implied_ncv_TJ_per_Gg", "plant_implied_efficiency_pct",
          "fleet_cv_mass_coverage_pct", "conversion_channel_share_pct",
          "composition_only_ncv_TJ_per_Gg", "table3_over_plant", "verdict")

BANNER = """\
# CAN NEPRA'S COAL ENERGY AND NEPRA'S COAL MASS DESCRIBE THE SAME FLEET?
#
# One row per fiscal year of the plant fuel ledger. `table3_*` is NEPRA State of Industry
# Report Table 3 (fuel consumed, tonnes of oil equivalent); `plant_*` is Table 21 (per-station
# quantities and generation) with each station's own metered heat rate; `composition_only_*`
# uses the Table 21 mass split by rank and IPCC default calorific values, and no heat rate
# at all.
#
# THREE ACCOUNTS OF THE SAME COAL. `table3_*` is the published energy; `hdip_mass_kt` is the
# national power-coal consumption Table 3 says it derives from (Pakistan Economic Survey
# statistical supplement, Table 14.1(4), the HDIP series); `table21_mass_kt` is NEPRA's own
# per-station quantities. `table3_toe_per_hdip_tonne` spreads 1.35x across the panel
# where `table3_toe_per_tonne` spreads 2.03x, so the conversion is the steadier of the two
# ratios. It does NOT follow that the disagreement is in the mass accounts, and an earlier
# version of this banner drew exactly that conclusion: stability across years is a statement
# about VARIANCE, and which account carries the level discrepancy is a different question.
# Decomposed, it is mostly the conversion - `conversion_channel_share_pct` puts 59 to 84 per
# cent of the log discrepancy against the non-circular physical route in the conversion
# channel in every one of the five years. Both facts are published because both are true;
# only the inference between them was wrong.
#
# The three `*_implied_efficiency_pct` columns take each account at the fleet's rank
# composition and divide the electricity out of it, against a 30-45 per cent band for a coal
# fleet. Only the per-station account stays inside that band in every year.
#
# THE BAND'S EDGES ARE CONSEQUENTIAL, which an earlier version of this note denied. It is a
# plausibility screen from general thermal practice, not a Pakistani measurement, and three
# cells change side between 30-45 and a wider 28-47: Table 3 at 45.1 in FY2019-20 and 29.6
# in FY2021-22, and the HDIP account at 29.1 in FY2023-24. Two of those are quoted in a
# verdict string, so two verdicts are band-dependent and a reader who prefers 28-47 should
# read them as inside.
#
# WHAT SURVIVES EITHER BAND is the conclusion this file is for: the per-station account is
# inside BOTH bands in all five years, and Table 3 is outside both in three of the five. The
# asymmetry between the accounts does not depend on where the edges are put; only the
# marginal verdicts do.
#
# `plant_implied_efficiency_pct` IS NOT INDEPENDENT EVIDENCE, and the column exists to be
# read with that said. The fleet calorific value it uses is itself generation x heat rate /
# mass, so multiplying it back by mass returns generation x heat rate and the efficiency it
# implies is NEPRA's own printed heat rates re-expressed. Measured: where the fleet CV covers
# all the mass, plant_energy_TJ reproduces the sum of generation x printed heat rate to a
# ratio of 1.000 and 0.986 (FY2022-23, FY2023-24). It cannot test whether NEPRA's fleet
# efficiency is plausible, because it is inside any band NEPRA's own heat rates are inside.
# What IS independent is the calorific value: composition_only_ncv_TJ_per_Gg uses rank
# defaults and no heat rate, and the two agree within 1-3 TJ/Gg on level and direction. The
# CV corroboration is real; the efficiency corroboration is circular.
#
# `fleet_cv_mass_coverage_pct` makes the identity exact and two of the years worse than
# circular. The fleet CV is mass-weighted over the non-outlier stations with a printed heat
# rate - sum(generation x heat rate) / that mass, reproducing the printed CV to the digit in
# all five years - and is then multiplied by TOTAL mass. So plant_energy_TJ is identically
# sum(generation x printed heat rate) divided by this coverage, which is the precise sense in
# which the route contains NEPRA's heat rates.
#
# Coverage runs 69, 72, 88, 100, 99 per cent. In FY2019-20 and FY2020-21 the only lignite
# station has no printed heat rate, so the CV is imported-only (23.03 and 22.87 TJ/Gg,
# identical to this file's own "imported only" rows) and is applied to lignite tonnes whose
# implied CV in the years that print one is about 11. Those two years' energy is inflated by
# 1/coverage and their efficiency biased DOWN by the same factor.
#
# This adjudicates; it does not re-base. The reference series rides Table 3, and moving it
# is a declared pin re-base rather than an audit finding.
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return 0.0


def build():
    ledger = read_rows(asset_path(DATA, "activity", "power", "plant_fuel_ledger.csv"))
    consumed = {r["fiscal_year"]: _num(r["toe"])
                for r in read_rows(asset_path(DATA, "activity", "power",
                                              "fuel_consumed.csv"))
                if "oal" in r["fuel"]}
    # Table 3 names the HDIP Pakistan Energy Yearbook as its source, and HDIP's own
    # power-sector coal mass is held - republished in the Economic Survey supplement. It is
    # the account Table 3's TOE is computed from, so it belongs beside the other two.
    hdip = {r["fiscal_year"]: _num(r["coal_kt"])
            for r in read_rows(asset_path(DATA, "activity", "industry",
                                          "coal_by_consumer.csv"))
            if r["consumer"] == "power" and r["coal_kt"]}
    implied = read_rows(asset_path(OUTPUTS, "power_implied_coal_cv_fy2023_24.csv"))
    fleet_cv = {r["fiscal_year"]: _num(r["implied_cv_TJ_per_Gg"])
                for r in implied if r["plant"].startswith("FLEET")}

    rows = []
    for year in sorted({r["fiscal_year"] for r in ledger if "oal" in r["fuel"]}):
        coal = [r for r in ledger if r["fiscal_year"] == year and "oal" in r["fuel"]]
        mass = sum(_num(r["quantity"]) for r in coal)
        gen = sum(_num(r["net_generation_GWh"]) for r in coal)
        toe = consumed.get(year, 0.0)
        if not (mass and gen and toe):
            continue
        by_rank = collections.defaultdict(float)
        for r in coal:
            by_rank[r["fuel_origin"]] += _num(r["quantity"])
        lignite = sum(v for k, v in by_rank.items() if k in LIGNITE_RANKS)
        comp = sum(v * NCV_BY_RANK.get(k, 25.8) for k, v in by_rank.items()) / mass

        t3_tj = toe * TOE_TJ
        t3_ncv = t3_tj / mass
        t3_eff = 100.0 * gen * GWH_TJ / t3_tj
        p_ncv = fleet_cv.get(year, 0.0)
        p_tj = p_ncv * mass
        p_eff = 100.0 * gen * GWH_TJ / p_tj if p_tj else 0.0
        # HOW MUCH OF THE MASS THE FLEET CV ACTUALLY COVERS. The CV is weighted over the
        # stations with a printed heat rate and then multiplied by TOTAL mass, so where this
        # is below 100 the plant route's energy is inflated by 1/coverage and its efficiency
        # depressed by the same factor. Published rather than noted, because a note does not
        # travel with the number.
        # The weight base is the FLEET row's own mass, not "the stations with a heat rate":
        # the CV excludes outliers from its weights, so in FY2021-22 and FY2023-24 those two
        # sets differ. Taking the wrong one put this at 100 per cent for a year whose CV was
        # weighted over 88, which a guard caught.
        covered = next((_num(r["mass_kt"]) for r in implied
                        if r["fiscal_year"] == year and r["plant"].startswith("FLEET")), 0.0)
        coverage = 100.0 * covered / mass if mass else 0.0

        period = "FY%s-%s" % (year, str(int(year) + 1)[-2:])
        hm = hdip.get(period.replace("FY", ""))
        gen_tj = gen * GWH_TJ
        eff_hdip = 100.0 * gen_tj / (hm * comp) if hm else None
        eff_t21 = 100.0 * gen_tj / (mass * comp)

        bad = []
        if not (COAL_EFF_LO <= t3_eff <= COAL_EFF_HI):
            bad.append("Table 3 implies %.1f%% fleet efficiency, outside %g-%g"
                       % (t3_eff, COAL_EFF_LO, COAL_EFF_HI))
        if p_eff and not (COAL_EFF_LO <= p_eff <= COAL_EFF_HI):
            bad.append("the plant route implies %.1f%%, outside %g-%g"
                       % (p_eff, COAL_EFF_LO, COAL_EFF_HI))
        if eff_t21 and not (COAL_EFF_LO <= eff_t21 <= COAL_EFF_HI):
            bad.append("NEPRA's per-station mass implies %.1f%%, outside %g-%g"
                       % (eff_t21, COAL_EFF_LO, COAL_EFF_HI))
        if eff_hdip and not (COAL_EFF_LO <= eff_hdip <= COAL_EFF_HI):
            bad.append("HDIP's national mass implies %.1f%%, outside %g-%g"
                       % (eff_hdip, COAL_EFF_LO, COAL_EFF_HI))
        verdict = ("; ".join(bad) if bad
                   else "every account inside the admissible efficiency band")

        # WHICH CHANNEL CARRIES THE LEVEL DISCREPANCY. Table 3's energy against the
        # non-circular physical route (rank composition x Table 21 mass) decomposes in logs
        # into a conversion channel, log(ncv3/ncv_composition), and a mass channel,
        # log(hdip/table21). The share reported is the conversion channel's share of the two
        # absolute log terms. This exists because the banner used to infer the location of
        # the discrepancy from which RATIO was steadier across years, which is a different
        # question and gave the opposite answer.
        conv_share = ""
        if t3_ncv and comp and hm and mass:
            conv = abs(math.log(t3_ncv / comp))
            mass_ch = abs(math.log(hm / mass))
            if conv + mass_ch:
                conv_share = "%.0f" % (100.0 * conv / (conv + mass_ch))

        rows.append({
            "period_id": period,
            "fiscal_start_year": year,
            "table3_coal_toe": "%.0f" % toe,
            "table21_mass_kt": "%.2f" % mass,
            "hdip_mass_kt": "%.2f" % hm if hm else "",
            "hdip_over_table21": "%.2f" % (hm / mass) if hm else "",
            "table3_toe_per_hdip_tonne": "%.3f" % (toe / (hm * 1000.0)) if hm else "",
            "hdip_mass_implied_efficiency_pct": "%.1f" % eff_hdip if eff_hdip else "",
            "table21_mass_implied_efficiency_pct": "%.1f" % eff_t21,
            "coal_generation_GWh": "%.2f" % gen,
            "lignite_share_of_mass_pct": "%.1f" % (100.0 * lignite / mass),
            "table3_toe_per_tonne": "%.3f" % (toe / (mass * 1000.0)),
            "table3_energy_TJ": "%.0f" % t3_tj,
            "table3_implied_ncv_TJ_per_Gg": "%.2f" % t3_ncv,
            "table3_implied_efficiency_pct": "%.1f" % t3_eff,
            "plant_energy_TJ": "%.0f" % p_tj if p_tj else "",
            "plant_implied_ncv_TJ_per_Gg": "%.2f" % p_ncv if p_ncv else "",
            "plant_implied_efficiency_pct": "%.1f" % p_eff if p_eff else "",
            "fleet_cv_mass_coverage_pct": "%.0f" % coverage if coverage else "",
            "conversion_channel_share_pct": conv_share,
            "composition_only_ncv_TJ_per_Gg": "%.2f" % comp,
            "table3_over_plant": "%.2f" % (t3_ncv / p_ncv) if p_ncv else "",
            "verdict": verdict,
        })
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped file matches a fresh build; write nothing")
    args = ap.parse_args(argv)
    rows = build()
    if args.check:
        if not os.path.exists(OUT):
            raise SystemExit("%s does not exist" % OUT)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        if io.open(OUT, encoding="utf-8").read() != BANNER + buf.getvalue():
            raise SystemExit("%s differs from a fresh build" % OUT)
        print("%s: current" % OUT)
        return
    write_table(OUT, FIELDS, rows, banner=BANNER.splitlines())
    print("Power coal energy adjudication -> %s (%d periods)" % (OUT, len(rows)))
    print("  period      HDIP kt   T21 kt  HDIP/T21  T3/HDIP t   "
          "eff%: T3 / HDIP / T21")
    for r in rows:
        print("  %-10s %8s %8s    %5s     %5s       %5s / %5s / %5s"
              % (r["period_id"], r["hdip_mass_kt"] or "-", r["table21_mass_kt"],
                 r["hdip_over_table21"] or "-", r["table3_toe_per_hdip_tonne"] or "-",
                 r["table3_implied_efficiency_pct"],
                 r["hdip_mass_implied_efficiency_pct"] or "-",
                 r["table21_mass_implied_efficiency_pct"]))


if __name__ == "__main__":
    main()
