"""What moves coal emissions from one fiscal year to the next: activity, allocation or print.

WHY THIS EXISTS (rc69). The rc68 manuscript attributes 69 percent of the latest one-year GHG
change to the coal allocation seam, and national SO2 rises from 213.6 to 368.9 Gg in the
same year. The GHG split (pakemis_coal_sector_reallocation.csv) separates the supply balance
from the seam because one industrial coal intensity applies to every consumer, so moving
coal between brick kilns and cement cannot change CO2. For air pollutants it can. Brick-kiln
pollutants are computed from booked brick coal mass, while cement-kiln pollutants are computed
from clinker and do not follow booked cement coal. A print that moves coal from the cement
column to the brick column therefore raises SO2, PM and BC with no physical change anywhere.
The review asked for that decomposition. This module gives it, per species and year, and
the terms are additive identities on the final exports, not a model.

THE IDENTITY. For species X and fiscal year t, booked industrial coal is I = B + C (brick
kilns, cement and other industry). R is the supply-balance industrial quantity (supply minus
metered station burn minus household; pakemis_coal_sector_reallocation.csv) and U = I - R
the allocation seam. Industrial coal emissions are E = e_B B + e_C C, with e the implied
factor read off the final atoms. For GHG, e_B = e_C = the one industrial intensity. For air,
e_C = 0, because the cement atoms carry clinker. Let a superscript * denote the same year
under the series print: the Statistical Supplement 2024-25, which the booking policy follows
except in FY2015-16 and FY2024-25. Then

  dE = [ (E1 - E1*) - (E0 - E0*) ]                   source vintage
     + dR m0*                                         supply balance (physical)
     + dU* m0*                                        allocation seam
     + I1* (s1* - s0*) (e_B0 - e_C0)                  consumer split within the print
     + I1* [ s1* (e_B1 - e_B0) + (1 - s1*) (e_C1 - e_C0) ]   factor change

with s = B/I and m = s e_B + (1 - s) e_C. Power-station and household coal are added as
their own terms. Every term is exact, and closure_residual is what rounding leaves.

WHAT IT DOES NOT SAY. The seam is an accounting allocation (HDIP's power column against
metered station burn), not a measured activity, and the split is a published consumer
allocation, not an observed kiln fuel record. Neither term is a probability.
Configuration S_TAN.

Usage:  python3 -m pkinv.sectors.industry.coal_change_decomposition [--check]
Writes: outputs/pakemis_coal_change_decomposition.csv
"""
import argparse
import collections

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import DATA, OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_coal_change_decomposition.csv")
REALLOCATION = asset_path(OUTPUTS, "pakemis_coal_sector_reallocation.csv")
AIR_ATOMS = asset_path(OUTPUTS, "pakemis_air_atomic_annual.csv")
VINTAGES = asset_path(DATA, "activity", "industry", "coal_by_sector_vintages.csv")
CONFIGURATION = "S_TAN"
SERIES_PRINT = "sup25"          # Statistical Supplement 2024-25, Table 14.1 sec.4
BRICK_FUEL = "Brick-kiln coal"
GHG = "CO2e_AR5"

FIELDS = ("period_id", "previous_period_id", "species", "unit",
          "coal_emissions_previous", "coal_emissions", "d_coal_emissions",
          "d_source_vintage", "d_supply_balance", "d_allocation_seam",
          "d_consumer_split", "d_factor", "d_power_station_coal", "d_household_coal",
          "closure_residual", "allocation_effect", "national_change",
          "national_change_without_allocation", "allocation_share_of_national_change_pct",
          "brick_booked_kt", "other_booked_kt", "brick_series_print_kt",
          "other_series_print_kt", "supply_balance_industrial_kt", "seam_series_print_kt",
          "factor_brick", "factor_other", "factor_unit", "basis")
BASIS = ("additive identity on the final exports, configuration S_TAN; series print = "
         "Statistical Supplement 2024-25; cement-and-other coal carries no air factor "
         "(cement air pollutants follow clinker); the seam and the split are published "
         "allocations, not measured activity")


def _num(text):
    return float(text) if text not in ("", None) else 0.0


def _series_print():
    """{(period_id, 'brick'|'other'): kt} from the Statistical Supplement 2024-25 print."""
    out = {}
    for row in read_rows(VINTAGES):
        if not row["estimate_id"].startswith(SERIES_PRINT + ":") or \
                row["period_coverage"] != "full_year":
            continue
        kind = {"brick_kilns": "brick", "cement_other": "other"}.get(row["sector_mapped"])
        if kind:
            start = row["reference_fiscal_year"][:4]
            period = "FY%s-%s" % (start, row["reference_fiscal_year"][-2:])
            out[(period, kind)] = float(row["value"])
    return out


def _reallocation():
    return {r["period_id"]: r for r in read_rows(REALLOCATION)}


def _air():
    """{(period, species): (brick Gg, power coal Gg, household coal Gg)} and national totals."""
    brick = collections.defaultdict(float)
    power = collections.defaultdict(float)
    household = collections.defaultdict(float)
    national = collections.defaultdict(float)
    for r in read_rows(AIR_ATOMS):
        if r["configuration_id"] != CONFIGURATION or r["core7"] != "yes":
            continue
        key = (r["period_id"], r["pollutant"])
        mass = _num(r["emissions_Gg"])
        national[key] += mass
        fuel = r["fuel_or_material"] or ""
        if fuel == BRICK_FUEL:
            brick[key] += mass
        elif r["sector_id"] == "power" and fuel.lower().startswith("coal"):
            power[key] += mass
        elif r["sector_id"] == "residential" and r["subitem"].startswith("Coal "):
            household[key] += mass
    species = sorted({k[1] for k in brick})
    return brick, power, household, national, species


def _round(value, places=6):
    return round(value, places)


def build():
    realloc = _reallocation()
    series = _series_print()
    brick_air, power_air, household_air, national_air, species = _air()
    periods = [p for p in sorted(realloc)]
    rows = []
    for previous, period in zip(periods, periods[1:]):
        r0, r1 = realloc[previous], realloc[period]
        b0, b1 = _num(r0["brick_booked_kt"]), _num(r1["brick_booked_kt"])
        i0, i1 = _num(r0["booked_industrial_kt"]), _num(r1["booked_industrial_kt"])
        c0, c1 = i0 - b0, i1 - b1
        rr0, rr1 = _num(r0["residual_industrial_kt"]), _num(r1["residual_industrial_kt"])
        bs0, bs1 = series[(previous, "brick")], series[(period, "brick")]
        cs0, cs1 = series[(previous, "other")], series[(period, "other")]
        for name in [GHG] + species:
            if name == GHG:
                f0 = _num(r0["industry_coal_intensity_Mt_per_kt"])
                f1 = _num(r1["industry_coal_intensity_Mt_per_kt"])
                eb0, ec0, eb1, ec1 = f0, f0, f1, f1
                p0, p1 = _num(r0["coal_power_Mt_AR5"]), _num(r1["coal_power_Mt_AR5"])
                h0, h1 = _num(r0["coal_residential_Mt_AR5"]), _num(r1["coal_residential_Mt_AR5"])
                e0 = _num(r0["coal_industry_Mt_AR5"])
                e1 = _num(r1["coal_industry_Mt_AR5"])
                national = (_num(r1["national_S_TAN_Mt_AR5"])
                            - _num(r0["national_S_TAN_Mt_AR5"]))
                unit, factor_unit = "Mt CO2e (AR5)", "Mt CO2e per kt coal"
            else:
                eb0 = brick_air[(previous, name)] / b0 if b0 else 0.0
                eb1 = brick_air[(period, name)] / b1 if b1 else 0.0
                ec0 = ec1 = 0.0
                p0, p1 = power_air[(previous, name)], power_air[(period, name)]
                h0, h1 = household_air[(previous, name)], household_air[(period, name)]
                e0, e1 = brick_air[(previous, name)], brick_air[(period, name)]
                national = national_air[(period, name)] - national_air[(previous, name)]
                unit, factor_unit = "Gg", "Gg per kt brick-kiln coal"
            booked0 = eb0 * b0 + ec0 * c0
            booked1 = eb1 * b1 + ec1 * c1
            star0 = eb0 * bs0 + ec0 * cs0
            star1 = eb1 * bs1 + ec1 * cs1
            is0, is1 = bs0 + cs0, bs1 + cs1
            s0, s1 = bs0 / is0, bs1 / is1
            m0 = s0 * eb0 + (1 - s0) * ec0
            u0, u1 = is0 - rr0, is1 - rr1
            vintage = (booked1 - star1) - (booked0 - star0)
            physical = (rr1 - rr0) * m0
            seam = (u1 - u0) * m0
            split = is1 * (s1 - s0) * (eb0 - ec0)
            factor = is1 * (s1 * (eb1 - eb0) + (1 - s1) * (ec1 - ec0))
            d_power, d_house = p1 - p0, h1 - h0
            total0, total1 = e0 + p0 + h0, e1 + p1 + h1
            change = total1 - total0
            residual = change - (vintage + physical + seam + split + factor + d_power + d_house)
            allocation = vintage + seam + split
            rows.append({
                "period_id": period, "previous_period_id": previous, "species": name,
                "unit": unit,
                "coal_emissions_previous": _round(total0), "coal_emissions": _round(total1),
                "d_coal_emissions": _round(change), "d_source_vintage": _round(vintage),
                "d_supply_balance": _round(physical), "d_allocation_seam": _round(seam),
                "d_consumer_split": _round(split), "d_factor": _round(factor),
                "d_power_station_coal": _round(d_power), "d_household_coal": _round(d_house),
                "closure_residual": _round(residual, 9), "allocation_effect": _round(allocation),
                "national_change": _round(national),
                "national_change_without_allocation": _round(national - allocation),
                # a share is printed only where the national change is at least as large as
                # the allocation effect and of the same sign; otherwise the ratio of a small
                # net change is not a share of anything
                "allocation_share_of_national_change_pct":
                    _round(100.0 * allocation / national, 2)
                    if national and allocation / national >= 0 and abs(national) >= abs(allocation)
                    else "",
                "brick_booked_kt": _round(b1, 3), "other_booked_kt": _round(c1, 3),
                "brick_series_print_kt": _round(bs1, 3), "other_series_print_kt": _round(cs1, 3),
                "supply_balance_industrial_kt": _round(rr1, 3),
                "seam_series_print_kt": _round(u1, 3),
                "factor_brick": _round(eb1, 9), "factor_other": _round(ec1, 9),
                "factor_unit": factor_unit, "basis": BASIS,
            })
    return rows


BANNER = [
    "COAL EMISSIONS, YEAR ON YEAR: physical supply balance, allocation seam, consumer split,",
    "source vintage and factor change, per species (rc69). The terms are additive identities on",
    "the final exports (configuration S_TAN): d_coal_emissions = d_source_vintage +",
    "d_supply_balance + d_allocation_seam + d_consumer_split + d_factor + d_power_station_coal",
    "+ d_household_coal, with closure_residual the rounding remainder. allocation_effect is",
    "vintage + seam + split; national_change_without_allocation is what the national total",
    "would have done had none of the three moved.",
    "- The seam is HDIP's power allocation against metered station burn.",
    "- The split is the published brick versus cement-and-other column.",
    "- The vintage is the booked print against the Statistical Supplement 2024-25 print.",
    "None of the three is measured activity.",
    "Cement-and-other coal carries no air factor, because cement air pollutants follow clinker.",
    "Producer: pkinv.sectors.industry.coal_change_decomposition.",
]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    rows = build()
    return write_or_check(OUT, FIELDS, rows, check=args.check, banner=BANNER)


if __name__ == "__main__":
    raise SystemExit(main())
