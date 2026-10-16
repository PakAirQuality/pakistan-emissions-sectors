"""Coal-source discrepancies and explicitly conditional industrial allocation cases.

Published supply and consumer allocations share inputs and are not independent
physical balance measurements. Replacing the published power allocation with
station consumption leaves a discrepancy which may include stock change,
coverage differences or unallocated use. It is never automatically kiln fuel.
Dated fleet/operating-season cases are separate from annual parameter uncertainty.
"""
import argparse
import collections
import os

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, write_or_check
from pkinv.paths import DATA, OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_coal_sector_reallocation.csv")
CASES_OUT = asset_path(OUTPUTS, "pakemis_coal_allocation_cases.csv")
CFG = asset_path(OUTPUTS, "pakemis_power_coal_configurations.csv")
ALLOC = asset_path(OUTPUTS, "pakemis_coal_allocation_identity.csv")

IND_NCV = 25.8          # TJ/Gg, industry_ncv "Other Bituminous Coal", the declared honest bucket
IND_CO2 = 94.6          # t CO2/TJ, other bituminous
UPLIFT = 1.00429        # CH4 and N2O beside the CO2

# FY2015-16 IS THE ONE YEAR THE IDENTITY DOES NOT CLOSE, by -203.8 kt, which the allocation
# identity already declares as its single unexplained exception. The two deltas therefore do
# NOT offset that year, and they offset by construction in the other eight. The gap is carried
# in identity_closes_kt rather than smoothed, because a reallocation that silently absorbed a
# known non-closure would be inventing 204 kt of coal.
FIELDS = ("period_id", "fiscal_start_year", "national_supply_kt", "station_power_kt",
          "hdip_power_kt", "power_delta_kt", "hdip_industrial_kt",
          "residual_industrial_kt", "industrial_delta_kt", "industrial_offset_Mt",
          "brick_booked_kt", "brick_fleet_low_kt", "brick_with_residual_kt",
          "brick_position_booked", "brick_position_with_residual", "identity_closes_kt",
          "note", "booked_industrial_kt", "station_power_low_kt", "station_power_high_kt",
          "industrial_delta_low_kt", "industrial_delta_high_kt", "unresolved_quantity_kind",
          # rc68: which dated fleet count, if any, was observed inside this fiscal period.
          "brick_fleet_case_basis",
          # rc68: K-Electric-system coal generation, printed without any station fuel.
          "ke_system_coal_generation_GWh", "ke_system_coal_fuel_status",
          # rc68: final-export decomposition of coal emissions into the supply balance and
          # the HDIP allocation seam, and both against the national change (AR5, Mt CO2e).
          "coal_central_Mt_AR5", "coal_power_Mt_AR5", "coal_industry_Mt_AR5",
          "coal_residential_Mt_AR5", "industry_coal_intensity_Mt_per_kt",
          "supply_balance_coal_Mt_AR5", "allocation_seam_Mt_AR5",
          "d_coal_central_vs_base_Mt", "d_supply_balance_vs_base_Mt", "d_allocation_seam_vs_base_Mt",
          "d_coal_central_yoy_Mt", "d_supply_balance_yoy_Mt", "d_allocation_seam_yoy_Mt",
          "national_S_TAN_Mt_AR5", "d_national_vs_base_S_TAN_Mt",
          "d_national_vs_base_L_TAN_Mt", "d_national_vs_base_S_IPCC_Mt",
          "d_national_vs_base_L_IPCC_Mt", "d_national_yoy_S_TAN_Mt",
          "seam_share_of_national_change_vs_base_S_TAN_pct",
          "seam_share_of_national_change_vs_base_L_TAN_pct",
          "seam_share_of_national_change_vs_base_S_IPCC_pct",
          "seam_share_of_national_change_vs_base_L_IPCC_pct",
          "seam_share_of_national_change_yoy_S_TAN_pct", "decomposition_basis")
ATOMS = asset_path(OUTPUTS, "pakemis_ghg_configuration_atoms.csv")
FLEET = asset_path(OUTPUTS, "pakemis_brick_kiln_fleet_by_year.csv")
GENERATION = asset_path(DATA, "activity", "power", "generation_by_fuel.csv")
CONFIGURATIONS = ("S_TAN", "L_TAN", "S_IPCC", "L_IPCC")
PUNJAB_KILN_SHARE = 0.8668   # declared national scale-out, shared with allocation_cases
DECOMPOSITION_BASIS = (
    "identity on the final atoms: industry coal = f x booked HDIP brick+cement, f its own "
    "Mt/kt; supply balance = power station coal + residential coal + f x (supply - station "
    "burn - HDIP household); seam = industry coal - f x that balance = -f x unresolved kt. "
    "Supply is HDIP production+imports with no published stock change or exports; the seam "
    "is an accounting allocation (HDIP's power column versus metered station burn), not a "
    "measured physical activity. Base year FY2015-16; no probability.")


def _coal_atoms():
    """Coal CO2e by period and sector from the final atoms, plus national totals."""
    coal = collections.defaultdict(float)
    national = collections.defaultdict(float)
    for r in read_rows(ATOMS):
        mass = float(r["co2e_Mt_AR5"] or 0)
        national[(r["configuration_id"], r["period_id"])] += mass
        if r["configuration_id"] != "S_TAN":
            continue
        sub, sector = r["subitem"], r["sector_id"]
        if sector == "power" and sub.startswith("Coal "):
            coal[(r["period_id"], "power")] += mass
        elif sector == "industry" and (sub.startswith("Brick-kiln coal")
                                       or sub.startswith("Cement-sector coal")):
            coal[(r["period_id"], "industry")] += mass
        elif sector == "residential" and sub.startswith("Coal "):
            coal[(r["period_id"], "residential")] += mass
    return coal, national


def _own_period_fleet():
    """{period_id: (national low kt, reading, date)} only where a count was made in the period.

    A fleet counted once is a dated observation, not an annual series: it is compared with
    the booked column only inside the fiscal period that contains its observation date.
    The Punjab fleet is scaled to national by the declared kiln-count share, the same
    scale-out the dated allocation cases state.
    """
    own = {}
    if not os.path.exists(FLEET):
        return own
    lows = collections.defaultdict(float)
    meta = {}
    for row in read_rows(FLEET, comments=True):
        if not row["year_basis"].startswith("the observation's OWN period"):
            continue
        key = (row["period_id"], row["reading"])
        lows[key] += float(row["coal_kt_low"])
        meta[key] = row["observation_date"]
    for (period, reading), low in lows.items():
        national = low / PUNJAB_KILN_SHARE
        if period not in own or national < own[period][0]:
            own[period] = (national, reading, meta[(period, reading)])
    return own


def _ke_coal_generation():
    out = {}
    for r in read_rows(GENERATION):
        if r["fuel"] == "Coal" and r["system"] == "K-Electric":
            out[int(r["fiscal_year"])] = float(r["gwh_net"])
    return out
CASE_FIELDS = ("period_id", "case_id", "case_kind", "geographic_scope", "observation_date",
               "brick_kt", "cement_other_kt", "station_power_kt", "unresolved_quantity_kt",
               "probability", "interpretation")

BANNER = """# Coal-source discrepancies; unresolved quantities are not automatically emitted.
# Published consumer allocations are not independent national physical balances.
# Dated fleet cases carry no probability, confidence interval or annual physical floor.
"""


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _period(y):
    return "FY%d-%02d" % (y, (y + 1) % 100)


def build():
    from pkinv.sectors.industry import solid_fuels
    cfg = {int(r["fiscal_start_year"]): r for r in read_rows(CFG, comments=True)
           if r["configuration_id"] == "C1_stations_rank_default"}
    supply, consumers, bounds, booked = {}, {}, {}, {}
    for r in read_rows(asset_path(DATA, "activity", "industry", "coal_supply.csv"),
                       comments=True):
        if r.get("period_coverage") != "full_year" or r.get("revision_status") not in ("final", "provisional"):
            continue
        y = int(r["fiscal_year"].split("-")[0])
        imp, pro = _num(r["coal_imports_kt"]), _num(r["coal_production_kt_petroleum_division"])
        if imp is not None and pro is not None:
            supply[y] = imp + pro
    for r in read_rows(asset_path(DATA, "activity", "industry", "coal_by_consumer.csv"),
                       comments=True):
        if r["coal_kt"] and r["revision_status"] in ("final", "provisional"):
            consumers.setdefault(int(r["fiscal_year"].split("-")[0]), {})[r["consumer"]] = \
                float(r["coal_kt"])
    # A dated fleet count is compared only inside the fiscal period of its observation
    # (rc68). Through rc67 the lowest Punjab-only floor of a fleet counted once (2020-11,
    # 2023-07) was set against the NATIONAL booked column in every year from FY2015-16,
    # which treated one count as an annual series and mixed geographic scopes.
    own_fleet = _own_period_fleet()
    for period, (low, _reading, _date) in own_fleet.items():
        bounds[int(period[2:6])] = low
    ke_coal = _ke_coal_generation()
    coal, national = _coal_atoms()

    rows = []
    for y in sorted(set(cfg) & set(supply) & set(consumers)):
        c = cfg[y]
        lo, high = _num(c["mass_lo_kt"]), _num(c["mass_hi_kt"])
        stn = _num(c["mass_kt"])
        if stn is None and lo is not None and high is not None:
            stn = (lo + high) / 2
        hp = consumers[y].get("power")
        hi = consumers[y].get("brick_kilns", 0.0) + consumers[y].get("cement", 0.0)
        fiscal = "%d-%02d" % (y, (y + 1) % 100)
        booked_ind = sum(solid_fuels.coal_kt(fiscal, item) for item in ("brick_kilns", "cement"))
        house = consumers[y].get("household", 0.0)
        if stn is None or hp is None:
            continue
        resid = supply[y] - stn - house
        d_ind = resid - booked_ind
        offset = d_ind * IND_NCV * IND_CO2 * UPLIFT / 1e6
        bk, floor = solid_fuels.coal_kt(fiscal, "brick_kilns"), bounds.get(y)
        bk_resid = (bk + d_ind) if (bk is not None and d_ind > 0) else bk
        def place(v):
            if v is None:
                return ""
            if floor is None:
                return "not compared: no fleet count observed in this fiscal period"
            return "below conditional fleet case" if v < floor else "within conditional fleet range"
        period = _period(y)
        fleet = own_fleet.get(period)
        fleet_basis = ("national scale-out (/%.4f) of the %s Punjab fleet counted %s, short-season "
                       "low; observed in this period" % (PUNJAB_KILN_SHARE, fleet[1], fleet[2])
                       if fleet else "no dated fleet count in this period; a count is never "
                       "carried to another year")
        power_mt = coal.get((period, "power"))
        ind_mt = coal.get((period, "industry"))
        res_mt = coal.get((period, "residential"), 0.0)
        decomposition = {}
        if power_mt is not None and ind_mt is not None and booked_ind:
            f = ind_mt / booked_ind
            balance_kt = supply[y] - stn - house
            decomposition = {
                "coal_central_Mt_AR5": power_mt + ind_mt + res_mt, "coal_power_Mt_AR5": power_mt,
                "coal_industry_Mt_AR5": ind_mt, "coal_residential_Mt_AR5": res_mt,
                "industry_coal_intensity_Mt_per_kt": f,
                "supply_balance_coal_Mt_AR5": power_mt + res_mt + f * balance_kt,
                "allocation_seam_Mt_AR5": ind_mt - f * balance_kt}
        for config in CONFIGURATIONS:
            if (config, period) in national:
                decomposition["_national_" + config] = national[(config, period)]
        rows.append({
            "period_id": _period(y), "fiscal_start_year": y,
            "national_supply_kt": "%.0f" % supply[y],
            "station_power_kt": "%.0f" % stn, "hdip_power_kt": "%.0f" % hp,
            "power_delta_kt": "%+.0f" % (stn - hp),
            "hdip_industrial_kt": "%.0f" % hi,
            "residual_industrial_kt": "%.0f" % resid,
            "industrial_delta_kt": "%+.0f" % d_ind,
            "industrial_offset_Mt": "%+.2f" % offset,
            "brick_booked_kt": "" if bk is None else "%.0f" % bk,
            "brick_fleet_low_kt": "" if floor is None else "%.0f" % floor,
            "brick_with_residual_kt": "" if bk_resid is None else "%.0f" % bk_resid,
            "brick_position_booked": place(bk),
            "brick_position_with_residual": place(bk_resid),
            # supply less everything HDIP books. Zero in eight years by construction; -204 kt
            # in FY2015-16, the allocation identity's one declared exception.
            "identity_closes_kt": "%+.0f" % (supply[y] - hp - booked_ind - house),
            "booked_industrial_kt": "%.6f" % booked_ind,
            "station_power_low_kt": "%.6f" % lo if lo is not None else "",
            "station_power_high_kt": "%.6f" % high if high is not None else "",
            "industrial_delta_low_kt": "%.6f" % (supply[y] - high - house - booked_ind) if high is not None else "",
            "industrial_delta_high_kt": "%.6f" % (supply[y] - lo - house - booked_ind) if lo is not None else "",
            "unresolved_quantity_kind": "stock_change_or_source_boundary_or_unallocated_consumer; no probability",
            "brick_fleet_case_basis": fleet_basis,
            "ke_system_coal_generation_GWh": ("%.2f" % ke_coal[y]) if y in ke_coal else "",
            "ke_system_coal_fuel_status": (
                "no K-Electric-system coal generation printed" if not ke_coal.get(y) else
                "not_printed: NEPRA prints K-Electric-system coal generation (IPPs/CPPs in the KE "
                "system) without station fuel in any held edition; outside the station coal "
                "account and not estimated; may sit inside HDIP cement/others (captive) or in "
                "the unresolved quantity - typed, never zero") if y in ke_coal else
                "generation not held for this year",
            "_decomposition": decomposition,
            "note": ("the industrial lane moves %+.0f kt, worth %+.2f Mt CO2e at industry_ncv "
                     "%.1f TJ/Gg - against the power lane's %+.0f kt. Which non-power consumer "
                     "took the coal is NOT resolved; attributing all of it to brick is an upper "
                     "reading used to test direction%s"
                     % (d_ind, offset, IND_NCV, stn - hp,
                        ". NOTE: HDIP's own supply and consumption do not close this year, by "
                        "%+.0f kt - the allocation identity's single declared exception - so "
                        "the two deltas do not offset here and the difference is that gap"
                        % (supply[y] - hp - booked_ind - house)
                        if abs(supply[y] - hp - booked_ind - house) > 2.0 else ""))})
    return _decompose(rows)


def _decompose(rows):
    """Change in central coal emissions = supply-balance change + allocation-seam change.

    Exact on the final atoms. The seam share of the national change is the part of the
    national movement that comes from booking HDIP's industrial allocation rather than
    supply minus metered station burn; it is an accounting quantity, not physics.
    """
    def fmt(v, spec="%.6f"):
        return "" if v is None else spec % v
    base, previous = None, None
    for row in rows:
        d = row.pop("_decomposition")
        complete = "coal_central_Mt_AR5" in d
        for key in ("coal_central_Mt_AR5", "coal_power_Mt_AR5", "coal_industry_Mt_AR5",
                    "coal_residential_Mt_AR5", "supply_balance_coal_Mt_AR5", "allocation_seam_Mt_AR5"):
            row[key] = fmt(d.get(key))
        row["industry_coal_intensity_Mt_per_kt"] = fmt(d.get("industry_coal_intensity_Mt_per_kt"), "%.9f")
        row["national_S_TAN_Mt_AR5"] = fmt(d.get("_national_S_TAN"), "%.5f")
        row["decomposition_basis"] = DECOMPOSITION_BASIS if complete else "final atoms do not carry this period"
        if complete and base is None:
            base = d
        for prefix, ref in (("vs_base", base), ("yoy", previous)):
            ok = complete and ref is not None and "coal_central_Mt_AR5" in ref
            for name, key in (("coal_central", "coal_central_Mt_AR5"),
                              ("supply_balance", "supply_balance_coal_Mt_AR5"),
                              ("allocation_seam", "allocation_seam_Mt_AR5")):
                row["d_%s_%s_Mt" % (name, prefix)] = fmt(d[key] - ref[key]) if ok else ""
        seam_base = (d["allocation_seam_Mt_AR5"] - base["allocation_seam_Mt_AR5"]) if complete and base else None
        for cfg in CONFIGURATIONS:
            k = "_national_" + cfg
            change = (d[k] - base[k]) if complete and base and k in d and k in base else None
            row["d_national_vs_base_%s_Mt" % cfg] = fmt(change)
            row["seam_share_of_national_change_vs_base_%s_pct" % cfg] = (
                fmt(100 * seam_base / change, "%.3f") if change and d is not base else "")
        yoy_nat = (d["_national_S_TAN"] - previous["_national_S_TAN"]) if (
            complete and previous and "_national_S_TAN" in previous and "_national_S_TAN" in d) else None
        row["d_national_yoy_S_TAN_Mt"] = fmt(yoy_nat)
        seam_yoy = (d["allocation_seam_Mt_AR5"] - previous["allocation_seam_Mt_AR5"]) if (
            complete and previous and "allocation_seam_Mt_AR5" in previous) else None
        row["seam_share_of_national_change_yoy_S_TAN_pct"] = (
            fmt(100 * seam_yoy / yoy_nat, "%.3f") if yoy_nat and seam_yoy is not None else "")
        previous = d if complete else None
    return rows


def allocation_cases(rows=None):
    """Priceable structural cases without turning a dated fleet into a series.

    The national scale-out of the Punjab fleet assumes equal coal use per kiln
    outside Punjab. It is stated in every case, not promoted to an observation.
    The unresolved quantity is retained, including negative discrepancies.
    """
    rows = rows if rows is not None else build()
    out = []
    for row in rows:
        brick = float(row["brick_booked_kt"])
        cement = float(row["booked_industrial_kt"]) - brick
        out.append(dict(period_id=row["period_id"], case_id="booked_reference", case_kind="reference",
                        geographic_scope="national", observation_date="", brick_kt=brick,
                        cement_other_kt=cement, station_power_kt=row["station_power_kt"],
                        unresolved_quantity_kt=float(row["industrial_delta_kt"]), probability="",
                        interpretation="declared source vintage; supply-minus-use discrepancy includes stocks and source-boundary differences, not known kiln consumption"))
    references = {row["period_id"]: row for row in out}
    # The detailed reference year remains FY2023-24 even when annual core extends.
    from pkinv.core.reporting_window import REFERENCE_PERIOD
    reference = references.get(REFERENCE_PERIOD)
    if reference is None:
        return out
    fleet = collections.defaultdict(lambda: [0.0, 0.0, set()])
    for row in read_rows(asset_path(OUTPUTS, "pakemis_brick_kiln_fleet_by_year.csv"), comments=True):
        if row["period_id"] != REFERENCE_PERIOD:
            continue
        values = fleet[row["reading"]]
        values[0] += float(row["coal_kt_low"])
        values[1] += float(row["coal_kt_high"])
        values[2].add(row["observation_date"])
    for reading, (low, high, dates) in sorted(fleet.items()):
        for endpoint, punjab_mass in (("short_season", low), ("long_season", high)):
            national_mass = punjab_mass / 0.8668
            change = national_mass - float(reference["brick_kt"])
            out.append(dict(reference, case_id="fleet_%s_%s" % (reading, endpoint),
                            case_kind="structural_case", observation_date=";".join(sorted(dates)),
                            brick_kt=national_mass,
                            unresolved_quantity_kt=float(reference["unresolved_quantity_kt"]) - change,
                            interpretation="dated Punjab fleet and declared firing-season/fuel-rate assumptions; national scale-out divides by Punjab kiln-count share 0.8668, assuming equal per-kiln fuel outside Punjab; no annual operating census, no probability or confidence bound; cement and power held"))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped file matches a fresh build; write nothing")
    args = ap.parse_args(argv)
    rows = build()
    status = write_or_check(OUT, FIELDS, rows, check=args.check, banner=(
        "# Coal-source/accounting alternatives relative to the inventory's declared booked vintage.",
        "# Station reconstruction midpoints and conditional bounds are separate; no probabilities assigned.",
        "# Supply less measured burn is unresolved stock/coverage/allocation, never automatically kiln fuel.",
        "# A dated counted-fleet scenario is not an observed annual physical floor."))
    case_status = write_or_check(CASES_OUT, CASE_FIELDS, allocation_cases(rows), check=args.check,
                                banner=("# Dated conditional coal allocation cases; no scenario probabilities.",))
    if args.check:
        return status or case_status
    print("Coal sector reallocation -> %s (%d years)" % (OUT, len(rows)))
    print("  %-10s %11s %11s %12s %24s %22s" % ("period", "power kt", "industry kt",
                                                "offset Mt", "brick booked", "with residual"))
    below = 0
    for r in rows:
        below += r["brick_position_booked"] == "below conditional fleet case"
        print("  %-10s %11s %11s %12s %24s %22s"
              % (r["period_id"], r["power_delta_kt"], r["industrial_delta_kt"],
                 r["industrial_offset_Mt"], r["brick_position_booked"],
                 r["brick_position_with_residual"]))
    print("  booked values below the dated conditional fleet case: %d of %d; this is not an annual physical floor" % (below, len(rows)))


if __name__ == "__main__":
    raise SystemExit(main())
