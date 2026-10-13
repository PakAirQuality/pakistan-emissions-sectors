"""Four accounts of the national power-coal energy, per year, labelled by what each depends on.

WHY THIS EXISTS. The release publishes three readings of the public-power total - 57.82, 38.45
and 61.83 Mt CO2e - as a declared family, and an external reviewer said the preferred one is
unjustified. Justifying or changing it needs the candidates stated as ACTIVITY accounts rather
than as finished totals, because that is the grain at which they differ: each is a coal mass
times a calorific value, and the reviewer's question is which mass and which value.

THE ONE THAT MATTERS MOST, and it was not visible before. The alternative the release already
publishes rides the HEAT-RATE route: power/diagnostics.coal_energy_restatement calls
implied_cv.restated_coal_TJ, which sums mass times a calorific value derived as generation x a
printed heat rate / mass. Its energy therefore CONTAINS the generation it is later divided by,
so dividing electricity out of it returns the regulator's own printed efficiency and cannot
test it. That is C3 here, and it is marked circular_with_generation=yes. The rank-default route
- C1 - uses IPCC Vol.2 Ch.1 Table 1.2 values and no heat rate at all, so it is the only
candidate whose energy is independent of the generation it is judged against. It was not
published anywhere before this file.

WHAT THE FOUR ARE.
  C0  Table 3's published energy. Its mass is HDIP's power column and its conversion is a flat
      0.4474 TOE per tonne - 18.73 TJ/Gg - held constant for six consecutive years while the
      fleet went from imported bituminous to 92 per cent Thar lignite.
  C1  the stations' own metered coal at IPCC rank defaults. Non-circular. Nine years, with an
      interval wherever no edition prints a mass.
  C2  HDIP's national tonnage at the same rank composition. Isolates the MASS account from the
      conversion, because C1 and C2 differ only in whose tonnage they take.
  C3  the stations' coal at heat-rate-implied calorific values. Circular, five years only.

THE TEST THAT SEPARATES THEM, and it is a nine-year panel result rather than a
reference-year argument. Implied net efficiency is net generation x 3.6 / coal energy, and
nothing in C0, C1 or C2 touches a heat rate, so for those three it is a test and not a
restatement. Against the 28-47 band the audit resolved: C0 lands inside in TWO of nine years,
C1 in NINE of nine - and in the four years whose mass is reconstructed the WHOLE interval is
inside, so the result does not turn on where in that interval the reconstruction falls. C2 is
inside in six, which is the useful middle: swapping only the conversion repairs most of the
implausibility, and swapping the tonnage as well repairs the rest. The verdict is published
per row in efficiency_band_verdict rather than left to the reader's arithmetic, and an
interval that straddles an edge is labelled `straddles` so it cannot be read as a pass.

WHAT THIS FILE DOES NOT DO. It does not choose. C1/C0 crosses unity twice across the panel and
the ratio decomposes exactly into a mass term that stays inside 0.74-0.99 and a calorific term
that runs 0.63 to 1.38 - so the sign change is the conversion, which is a finding about the
mechanism and not a selection. Selecting a reference is a declared pin re-base.
"""
import argparse
import collections

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import DATA, OUTPUTS
from pkinv.sectors.power.reference_audit import BAND_LO, BAND_HI

OUT = asset_path(OUTPUTS, "pakemis_power_coal_configurations.csv")
RECON = asset_path(OUTPUTS, "pakemis_power_fuel_reconciliation.csv")
TOE_TJ = 41.868e-3
FLAT_TOE_PER_T = 0.4474            # Table 3's constant, six years to 0.016 per cent

FIELDS = ("period_id", "fiscal_start_year", "configuration_id", "configuration_label",
          "mass_kt", "mass_lo_kt", "mass_hi_kt", "mass_account", "mass_source",
          "cv_TJ_per_Gg", "cv_basis", "cv_source", "circular_with_generation",
          "coal_energy_TJ", "coal_energy_lo_TJ", "coal_energy_hi_TJ",
          "net_generation_GWh", "implied_net_efficiency_pct",
          "implied_net_efficiency_lo_pct", "implied_net_efficiency_hi_pct",
          "efficiency_band_verdict", "ratio_to_C0", "note")

BANNER = """\
# FOUR ACCOUNTS OF THE NATIONAL POWER-COAL ENERGY, PER YEAR, FY2015-16..FY2023-24.
#
# Each is a coal MASS times a CALORIFIC VALUE. They are published side by side because that is
# the grain at which the published readings of the public-power total differ, and because the
# review asked which of the differences arise from conversion, from coverage, and from
# conflicting activity records.
#
# READ circular_with_generation FIRST. C3 takes calorific values derived from printed heat
# rates, so its energy contains the generation it is later divided by: dividing electricity out
# of it returns the regulator's own efficiency and cannot test it. The release's existing
# 38.45 Mt alternative rides exactly this route. C1 uses IPCC rank defaults and no heat rate,
# so it is the only candidate independent of the generation it is judged against.
#
# C1 AND C2 DIFFER ONLY IN WHOSE TONNAGE THEY TAKE, which is what makes the pair useful: the
# mass question and the conversion question can be separated. C1/C0 decomposes exactly into
# (station mass / HDIP mass) x (real rank CV / 18.73). Across the panel the mass term stays
# inside 0.74-0.99 while the calorific term runs 0.63 to 1.38 and CROSSES ONE. The sign change
# is the conversion.
#
# THE BAND VERDICT IS THE POINT OF THE PANEL. implied_net_efficiency_pct (or its lo/hi pair
# where the mass is an interval) against 28-47 per cent: C0 is inside in two of nine years, C1
# in nine of nine with the whole interval inside in every reconstructed year, C2 in six. A
# straddling interval is labelled `straddles` and is NOT a pass.
#
# INTERVALS are real, not decoration. Four plant-years carry no printed mass in any edition, so
# C1 and C2 carry mass_lo/mass_hi and energy_lo/energy_hi in those years and NO point.
#
# NOTHING HERE IS A TOTAL AND NOTHING HERE SELECTS. Selecting a reference series is a declared
# pin re-base, and the national consequence of each account belongs with that re-base rather
# than in an activity file.
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _period(y):
    return "FY%d-%02d" % (y, (y + 1) % 100)


def build():
    # THE SHIPPED SCHEMA, not the one this module was written against. The reconciliation
    # was rewritten to plant_coverage_class / quantity_class / ncv_TJ_per_Gg and its two
    # consumers were not: the test errored in setUpClass and ran none of its cases, and this
    # module raised KeyError('row_kind') at the first full build after the change. Both were
    # invisible until something ran them - which is the whole argument for a schema check
    # that names the producer's own FIELDS.
    # BOTH LANES. The enumerated stations carry metered masses; the reconstructed lane
    # carries the commissioning generation with an interval on its coal. Reading only the
    # first made the fleet's generation - the denominator of every efficiency below - the
    # generation of the stations that happen to be printed, which put FY2016-17 at 2.8 per
    # cent efficient instead of 22.3.
    recon = [r for r in read_rows(RECON, comments=True)
             if r["plant_coverage_class"] in ("enumerated station", "reconstructed lane")]
    t3 = {int(r["fiscal_year"]): _num(r["toe"])
          for r in read_rows(asset_path(DATA, "activity", "power", "fuel_consumed.csv"))
          if "oal" in r["fuel"]}
    hdip = {int(r["fiscal_year"].split("-")[0]): _num(r["coal_kt"])
            for r in read_rows(asset_path(DATA, "activity", "industry",
                                          "coal_by_consumer.csv"), comments=True)
            if r["consumer"] == "power" and r["coal_kt"] and r["revision_status"] == "final"}
    # the heat-rate route, where it exists at all
    hr_cv = {}
    for r in read_rows(asset_path(OUTPUTS, "power_implied_coal_cv_fy2023_24.csv")):
        if r["plant"].startswith("FLEET"):
            hr_cv[int(r["fiscal_year"])] = _num(r["implied_cv_TJ_per_Gg"])

    def _start(row):
        """"FY2023-24" -> 2023. The schema dropped fiscal_start_year; period_id carries it."""
        return int(row["period_id"][2:6])

    years = sorted({_start(r) for r in recon if _start(r) >= 2015})
    rows = []
    for y in years:
        plants = [r for r in recon if _start(r) == y]
        gwh = sum(_num(r["net_generation_GWh"]) or 0.0 for r in plants)
        mlo = mhi = elo = ehi = 0.0
        for r in plants:
            ncv = _num(r["ncv_TJ_per_Gg"])
            m = _num(r["mass_kt"])
            if m is None:
                # A reconstructed row states no point mass, by design. Its INTERVAL enters
                # the two bounds - which is what the bounds are for - and a row with neither
                # a mass nor an interval enters neither, rather than being read as a zero.
                lo_m, hi_m = _num(r["mass_lo_kt"]), _num(r["mass_hi_kt"])
            else:
                lo_m = hi_m = m
            if ncv is None or lo_m is None or hi_m is None:
                continue
            mlo += lo_m; mhi += hi_m; elo += lo_m * ncv; ehi += hi_m * ncv
        blend = (ehi / mhi) if mhi else 0.0          # the fleet's own rank composition
        c0_tj = t3[y] * TOE_TJ if y in t3 else None

        def emit(cid, label, mass, lo, hi, account, msrc, cv, cvbasis, cvsrc, circ,
                 tj, tjlo, tjhi, note):
            eff = (100.0 * gwh * 3.6 / tj) if (tj and gwh) else None
            # A BIGGER ENERGY IS A SMALLER EFFICIENCY, so the energy's LOW bound gives the
            # efficiency's HIGH one. Without this the four reconstructed years carried no
            # efficiency at all and the panel test could only be stated for five of nine -
            # which is exactly the half that needed no reconstruction, so the test looked
            # weaker than the evidence is.
            efflo = (100.0 * gwh * 3.6 / tjhi) if (tjhi and gwh and tj is None) else None
            effhi = (100.0 * gwh * 3.6 / tjlo) if (tjlo and gwh and tj is None) else None
            lo_e, hi_e = (eff, eff) if eff is not None else (efflo, effhi)
            if lo_e is None or hi_e is None:
                verdict = ""
            elif BAND_LO <= lo_e and hi_e <= BAND_HI:
                verdict = "inside %g-%g" % (BAND_LO, BAND_HI)
            elif hi_e < BAND_LO or lo_e > BAND_HI:
                verdict = "OUTSIDE %g-%g" % (BAND_LO, BAND_HI)
            else:
                # An interval that straddles an edge decides nothing, and saying so is the
                # point: it must not be read as a pass.
                verdict = "straddles %g-%g" % (BAND_LO, BAND_HI)
            ratio = (tj / c0_tj) if (tj and c0_tj) else None
            rlo = (tjlo / c0_tj) if (tjlo and c0_tj) else None
            rhi = (tjhi / c0_tj) if (tjhi and c0_tj) else None
            rows.append({
                "period_id": _period(y), "fiscal_start_year": y, "configuration_id": cid,
                "configuration_label": label,
                "mass_kt": "" if mass is None else "%.2f" % mass,
                "mass_lo_kt": "" if lo is None else "%.2f" % lo,
                "mass_hi_kt": "" if hi is None else "%.2f" % hi,
                "mass_account": account, "mass_source": msrc,
                "cv_TJ_per_Gg": "" if cv is None else "%.2f" % cv,
                "cv_basis": cvbasis, "cv_source": cvsrc,
                "circular_with_generation": circ,
                "coal_energy_TJ": "" if tj is None else "%.0f" % tj,
                "coal_energy_lo_TJ": "" if tjlo is None else "%.0f" % tjlo,
                "coal_energy_hi_TJ": "" if tjhi is None else "%.0f" % tjhi,
                "net_generation_GWh": "%.2f" % gwh,
                "implied_net_efficiency_pct": "" if eff is None else "%.1f" % eff,
                "implied_net_efficiency_lo_pct": "" if efflo is None else "%.1f" % efflo,
                "implied_net_efficiency_hi_pct": "" if effhi is None else "%.1f" % effhi,
                "efficiency_band_verdict": verdict,
                "ratio_to_C0": ("1.000" if cid == "C0_table3"
                                else "" if ratio is None and rlo is None
                                else "%.3f" % ratio if ratio is not None
                                else "%.3f-%.3f" % (rlo, rhi)),
                "note": note})

        emit("C0_table3", "as published: NEPRA SoIR Table 3 coal energy",
             hdip.get(y), None, None, "HDIP apparent consumption from supply",
             "Finance Division Statistical Supplement Table 14.1(4), Power column",
             (c0_tj / hdip[y]) if (c0_tj and hdip.get(y)) else None,
             "implied by the published energy over HDIP's tonnage",
             "NEPRA SoIR Table 3 'Fuel consumed' (TOE)", "no",
             c0_tj, None, None,
             "the flat %.4f TOE per tonne (%.2f TJ/Gg) held for six consecutive years to "
             "0.016 per cent while the fleet's rank composition changed completely"
             % (FLAT_TOE_PER_T, FLAT_TOE_PER_T * 41.868))
        emit("C1_stations_rank_default",
             "THE NON-CIRCULAR ROUTE: the stations' own metered coal at IPCC rank defaults",
             None if mlo != mhi else mhi, mlo, mhi,
             "coal used, as the stations report it",
             "outputs/pakemis_power_fuel_reconciliation.csv (NEPRA SoIR 2018/2023/2024)",
             blend, "mass-weighted IPCC rank defaults; NO heat rate",
             "IPCC 2006 Vol.2 Ch.1 Table 1.2 (other bituminous 25.8, lignite 11.9 TJ/Gg)",
             "no", None if elo != ehi else ehi, elo, ehi,
             "independent of the generation it is judged against, which no other candidate is")
        emit("C2_hdip_rank_default",
             "HDIP's national tonnage at the same rank composition",
             hdip.get(y), None, None, "HDIP apparent consumption from supply",
             "Finance Division Statistical Supplement Table 14.1(4), Power column",
             blend, "mass-weighted IPCC rank defaults; NO heat rate",
             "IPCC 2006 Vol.2 Ch.1 Table 1.2", "no",
             (hdip[y] * blend) if (hdip.get(y) and blend) else None, None, None,
             "differs from C1 ONLY in whose tonnage it takes, which is what isolates the mass "
             "question from the conversion question")
        if y in hr_cv and hr_cv[y]:
            emit("C3_stations_heat_rate",
                 "the stations' coal at heat-rate-implied calorific values",
                 mhi, None, None, "coal used, as the stations report it",
                 "outputs/pakemis_power_fuel_reconciliation.csv",
                 hr_cv[y], "fleet-weighted, derived as generation x printed heat rate / mass",
                 "NEPRA SoIR Table 23 heat rates", "yes", mhi * hr_cv[y], None, None,
                 "CIRCULAR: the energy contains the generation it is later divided by, so its "
                 "implied efficiency restates the regulator's own print. This is the route the "
                 "release's existing 38.45 Mt alternative rides")
    return rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped file matches a fresh build; write nothing")
    args = ap.parse_args(argv)
    rows = build()
    status = write_or_check(OUT, FIELDS, rows, check=args.check, banner=BANNER.splitlines())
    if args.check:
        return status
    print("Power coal configurations -> %s (%d rows)" % (OUT, len(rows)))
    by = collections.Counter(r["configuration_id"] for r in rows)
    for cid, n in sorted(by.items()):
        print("  %-28s %d year(s)" % (cid, n))
    print("  %-10s %10s %10s %10s" % ("period", "C0 TJ", "C1 TJ", "C1/C0"))
    for r in rows:
        if r["configuration_id"] == "C1_stations_rank_default":
            c0 = next(x for x in rows if x["period_id"] == r["period_id"]
                      and x["configuration_id"] == "C0_table3")
            print("  %-10s %10s %10s %10s" % (r["period_id"], c0["coal_energy_TJ"],
                                              r["coal_energy_TJ"] or
                                              "%s-%s" % (r["coal_energy_lo_TJ"],
                                                         r["coal_energy_hi_TJ"]),
                                              r["ratio_to_C0"]))


if __name__ == "__main__":
    raise SystemExit(main())
