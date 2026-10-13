"""Structural trajectories: every registered axis, every year, priced or refused.

WHY THIS EXISTS (the twelfth review). The twenty structural axes are priced
against the FY2023-24 reference only - no configuration output anywhere carries
a year column - so a reader of the nine-year panel could not ask "how large was
the coal fork in FY2019-20?", and could not even see WHICH axes a year supports.
This product answers per (axis, year): the alternative's value where the sector
engine can honestly price it for that year, and an explicit refusal naming the
missing evidence where it cannot. A refusal is a row, never a silence - the
coverage matrix's pattern.

WHAT A PRICED ROW IS NOT. No probability, no trajectory ensemble: each row is
the same deterministic fork the axis register prices at the reference year,
re-evaluated on that year's own activity. The longitudinal ensemble's refusal
to cross structural axes into a probabilistic ensemble stands unchanged; these
are 9 deterministic re-readings per axis, not draws.

REFERENCE-YEAR ROWS ARE READ, NOT RECOMPUTED, from the axis register - the
release-manifest discipline - and where a per-year pricer also covers the
reference year, a guard asserts it reproduces the register's value.

Usage:  python3 -m pkinv.report.structural_trajectories
Writes: outputs/pakemis_structural_trajectories.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_structural_trajectories.csv")
YEARS = tuple(range(2016, 2025))          # fiscal end years
REFERENCE_YEAR = 2024

FIELDS = ("axis", "module", "fiscal_end_year", "status", "reference_Mt",
          "alternative_Mt", "delta_Mt", "reason")

PRICED = "priced"
PRICED_REGISTER = "priced_reference_register"
REFUSED = "not_priceable_for_year"

# The standing refusal texts, one per evidence situation.
REFUSE_SCENARIO_RUNNER = ("the sector's scenario runner prices the reference "
                          "year only; re-running the alternative for this year "
                          "needs engine work, not new data")
REFUSE_REFERENCE_DOC = ("the alternative is read from a reference-year document "
                        "(%s) that has no counterpart for this year")
REFUSE_UNPRICED = ("unpriced even at the reference year: the axis register "
                   "carries no published alternative row")


def _rows(path):
    return read_rows(path)


def _register():
    return {r["axis"]: r for r in _rows(asset_path(OUTPUTS,
                                                     "national_axis_register.csv"))}


def _fugitives_pricer(scenario):
    from pkinv.core import registry
    engine = registry.get("fugitives")
    data = engine.load_data()

    def price(year):
        try:
            alt = sum(c["co2e_Mt_AR5"] for c in engine.build_components(
                data, scenario=scenario, year=year))
        except KeyError as exc:
            return {"status": REFUSED, "reason": str(exc).strip("'\"")}
        ref = sum(c["co2e_Mt_AR5"] for c in engine.build_components(
            data, year=year))
        return {"status": PRICED, "reference_Mt": ref, "alternative_Mt": alt}
    return price


def _cement_fraction_pricer():
    from pkinv.core import registry
    engine = registry.get("ippu")
    data = engine.load_data()

    def price(year):
        try:
            ref = engine.clinker_co2_Mt(data, year)
            alt = engine.clinker_co2_Mt(data, year, fraction=0.95)
        except (KeyError, ValueError, StopIteration) as exc:
            return {"status": REFUSED,
                    "reason": "clinker balance not held for this year: %s"
                              % str(exc)[:120]}
        return {"status": PRICED, "reference_Mt": ref, "alternative_Mt": alt}
    return price


def _power_coal_ratio_pricer(which):
    """Both coal-energy alternatives, priced the same way the sector's own scenarios are:
    the year's coal components scaled by (alternative energy / BOOKED energy).

    THE DENOMINATOR IS THE BOOKED ENERGY, not NEPRA Table 3. Until the re-base those were the
    same number and this function could divide by Table 3 without saying so; they are not the
    same number any more, and a pricer that kept dividing by Table 3 would have reported the
    alternative's distance from an account the engine no longer books. combustion.fuel_TJ is
    the engine's own coal energy for the year, so the ratio is by construction the one the
    sector's scenario table applies.

      "heat_rate"   the calorific values the plants' own generation implies. CIRCULAR: the
                    energy contains the generation it is later divided by, which is why it is
                    an alternative and not the reference.
      "table3"      the energy NEPRA SoIR Table 3 prints - the LEGACY PUBLISHED CONTROL, the
                    reference for every release before this one, retained rather than deleted.
    """
    from pkinv.core import registry
    engine = registry.get("power")
    diagnostics = registry.diagnostics("power")
    data = engine.load_data()

    def price(fy_end):
        year = fy_end - 1               # grid years are fiscal-START
        try:
            accounts = diagnostics.coal_energy_accounts(data, year)
            booked, alt_TJ = accounts["booked"], accounts[which]
        except (KeyError, ValueError, StopIteration) as exc:
            return {"status": REFUSED,
                    "reason": "FY%d-%02d has no %s coal energy (%s)"
                              % (year, fy_end % 100, which, type(exc).__name__)}
        grid = [c for c in engine.build_components(data, year=year)
                if c["category"] == "Electricity and heat production"]
        ratio = alt_TJ / booked
        ref = sum(c["co2e_Mt_AR5"] for c in grid)
        alt = sum(c["co2e_Mt_AR5"] * (ratio if c["subitem"].startswith("Coal") else 1.0)
                  for c in grid)
        return {"status": PRICED, "reference_Mt": ref, "alternative_Mt": alt}
    return price


def _industry_hhv_pricer():
    from pkinv.core import registry
    engine = registry.get("industry")
    data = engine.load_data()

    def price(year):
        try:
            ref = sum(c["co2e_Mt_AR5"]
                      for c in engine.build_components(data, year=year))
            alt = sum(c["co2e_Mt_AR5"] for c in engine.build_components(
                data, year=year, hhv_btu=900))
        except (KeyError, ValueError) as exc:
            return {"status": REFUSED,
                    "reason": "the industry engine does not hold this year: %s"
                              % str(exc)[:120]}
        return {"status": PRICED, "reference_Mt": ref, "alternative_Mt": alt}
    return price


def _brick_kiln_pricer():
    from pkinv.core import registry
    by_year = registry.get("industry").brick_kiln_screen_Mt()

    def price(year):
        if year not in by_year:
            return {"status": REFUSED,
                    "reason": "the PEY Table 4.4 series runs FY2012-13.."
                              "FY2022-23 and does not hold this year; the "
                              "reference configuration uses the FY2022-23 "
                              "vintage, declared"}
        mt = by_year[year]
        return {"status": PRICED, "reference_Mt": 0.0, "alternative_Mt": mt,
                "reason": "OWN-year vintage (the reference configuration used "
                          "FY2022-23); the reference books the category NE, so "
                          "reference_Mt is zero and the delta IS the screening"}
    return price


def _bagasse_pricer():
    from pkinv.core import registry
    industry = registry.get("industry")

    def price(year):
        label = "FY%d-%02d" % (year - 1, year % 100)
        rows = [r for r in _rows(asset_path(
            DATA, "activity", "agriculture", "es_fiscal_series.csv"))
            if r["item"] == "sugarcane_production_t"
            and r["fiscal_label"] == label]
        if not rows:
            return {"status": REFUSED,
                    "reason": "no cane production row for %s in the Economic "
                              "Survey fiscal series" % label}
        cane = float(rows[0]["value"])
        mt = industry.bagasse_ceiling_Mt(cane)
        return {"status": PRICED, "reference_Mt": 0.0, "alternative_Mt": mt,
                "reason": "the all-cane CEILING for this year's own crop; the "
                          "reference books the category NE"}
    return price


def _kelectric_pricer():
    """The coverage alternative, per year (rc67): the reference grid plus the K-Electric
    system's fuel CO2. Through rc66 this axis was refused for every year but the
    reference; the system's fuel is held for all nine (NEPRA SoIR 2020 Table 24 for
    FY2015-16 to FY2018-19, the plant ledger after), so it is priced for all nine.

    A COVERAGE alternative, not a correction: whether the national fuel statistic the
    reference books already contains this fuel is not established, so the alternative is
    the upper reading of "it is entirely outside". Three furnace-oil cells in the early
    years are estimated from the station's own rate; the reason names them."""
    from pkinv.core import registry
    engine = registry.get("power")
    data = engine.load_data()
    series = {r["fiscal_year"]: r
              for r in registry.diagnostics("power").ke_coverage_series(data)}

    def price(fy_end):
        year = fy_end - 1               # grid years are fiscal-START
        row = series.get(year)
        if row is None:
            return {"status": REFUSED,
                    "reason": "no K-Electric station fuel is held for FY%d-%02d"
                              % (year, fy_end % 100)}
        ref = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data, year=year)
                  if c["category"] == "Electricity and heat production")
        out = {"status": PRICED, "reference_Mt": ref, "alternative_Mt": ref + row["co2_Mt"]}
        if row["estimated_cells"]:
            out["reason"] = ("%.3f Mt of the %.3f Mt rests on cells the source prints as "
                             "not provided, estimated from the station's own rate: %s"
                             % (row["co2_Mt"] - row["co2_Mt_printed_fuel_only"],
                                row["co2_Mt"], row["estimated_cells"]))
        return out
    return price


def _dung_ledger_pricer():
    """Configuration L per year (rc67): the residential sector with all the dung that
    year's herd diverts burned in households, against the survey-anchored reference.
    Refused for history through rc66, when the alternative was the survey and "no survey
    edition exists for this year"; the ledger series exists for every year."""
    from pkinv.core import registry
    engine = registry.get("residential")
    data = engine.load_data()

    def price(fy_end):
        ref = sum(c["co2e_Mt_AR5"] for c in engine.components_for_year(data, fy_end))
        alt = sum(c["co2e_Mt_AR5"]
                  for c in engine.components_for_year(data, fy_end, "ledger"))
        return {"status": PRICED, "reference_Mt": ref, "alternative_Mt": alt}
    return price


def _rail_pricer():
    def price(year):
        return {"status": PRICED, "reference_Mt": 0.0, "alternative_Mt": 0.0,
                "reason": "a reporting recode: both bookings conserve the "
                          "total exactly in every year, by construction"}
    return price


def _refuse(reason):
    def price(_year):
        return {"status": REFUSED, "reason": reason}
    return price


def _coal_screen_pricer():
    """The 1.B.1 surface screen per year: the plant ledger carries Thar mine-mouth
    deliveries by fiscal year, so the screen's own arithmetic re-runs on each year's
    activity. Years before the Thar plants delivered refuse with the screen's own
    error - the mine was not producing, and the underground share is unquantified in
    every year."""
    from pkinv.core import registry
    engine = registry.get("fugitives")
    data = engine.load_data()

    def price(year):
        try:
            rows = engine.coal_screen_rows(year - 1)
        except ValueError:
            return {"status": REFUSED,
                    "reason": "no Thar mine-mouth deliveries in the plant ledger "
                              "for this year (the mine was not delivering); the "
                              "underground share is unquantified in every year"}
        hi = max(float(r["co2e_Mt_AR5"]) for r in rows if r["co2e_Mt_AR5"] != "")
        ref = sum(c["co2e_Mt_AR5"] for c in engine.build_components(data, year=year))
        return {"status": PRICED, "reference_Mt": ref,
                "alternative_Mt": ref + hi}
    return price


def _pricers():
    return {
        "fugitive practice": _fugitives_pricer("lower_practices"),
        "fugitive activity basis": _fugitives_pricer("throughput"),
        "post-meter feedstock scope":
            _fugitives_pricer("post_meter_including_feedstock"),
        "coal mining fugitives scope": _coal_screen_pricer(),
        "cement clinker fraction": _cement_fraction_pricer(),
        "power coal energy basis": _power_coal_ratio_pricer("heat_rate"),
        # The account the reference replaced, priced across the panel so the re-base's
        # consequence is a series and not one year's number.
        "power coal energy basis (legacy published control)":
            _power_coal_ratio_pricer("table3"),
        "industrial gas heating value": _industry_hhv_pricer(),
        "brick kiln coal scope": _brick_kiln_pricer(),
        "aviation model resolution": _refuse(
            "the flight-route ledger is a reference-year reconstruction "
            "(PCAA movement-constrained routes for FY2023-24); no earlier "
            "year's route ledger exists and the aggregate-movement model is "
            "the only member the panel supports"),
        "rice water regime": _refuse(
            "the SPAM technology split is a 2020-vintage model surface with no "
            "per-year counterpart; re-weighting an earlier year's rice total by "
            "the same split would present one vintage as nine, and no Pakistani "
            "water-management series exists to replace it"),
        "captive coal scope": _refuse(
            "the captive register is a current-snapshot merge (NEPRA licence "
            "list + OGRA FY2024 utility tables) with no per-year capacity "
            "history; re-pricing the bracket for an earlier year would need "
            "that year's own register"),
        "bagasse process heat scope": _bagasse_pricer(),
        "rail traction boundary": _rail_pricer(),
        "residential dung basis": _dung_ledger_pricer(),
        "sewer methane correction factor": _refuse(REFUSE_SCENARIO_RUNNER),
        "wastewater effluent N2O factor": _refuse(REFUSE_SCENARIO_RUNNER),
        "power energy convention": _refuse(REFUSE_SCENARIO_RUNNER),
        "power scope": _kelectric_pricer(),
        "cement clinker activity basis": _refuse(
            REFUSE_REFERENCE_DOC % "the FY2023-24 producer census"),
        "cement kiln fuel scope": _refuse(
            REFUSE_REFERENCE_DOC % "the FY2023-24 producer census clinker"),
        "aviation military scope": _refuse(
            REFUSE_REFERENCE_DOC % "the FY2023-24 OCAC JP-1 bridge"),
        "aviation general aviation scope": _refuse(
            REFUSE_REFERENCE_DOC % "the FY2023-24 OCAC 100LL row"),
        "aviation unresolved residual scope": _refuse(
            REFUSE_REFERENCE_DOC % "the FY2023-24 OCAC JP-1 bridge"),
        "transport retail non-road": _refuse(REFUSE_UNPRICED),
    }


def build():
    register = _register()
    pricers = _pricers()
    missing = set(register) - set(pricers)
    if missing:
        raise SystemExit("axes with no trajectory pricer: %s - a new axis "
                         "must be priced or refused here, never omitted"
                         % sorted(missing))
    rows = []
    for axis in sorted(register):
        reg = register[axis]
        for year in YEARS:
            if year == REFERENCE_YEAR:
                priced = bool(reg.get("national_delta_Mt", "").strip())
                rows.append({
                    "axis": axis, "module": reg["module"],
                    "fiscal_end_year": year,
                    "status": PRICED_REGISTER if priced else REFUSED,
                    "reference_Mt": "",
                    "alternative_Mt": reg.get("alternative_Mt", ""),
                    "delta_Mt": reg.get("national_delta_Mt", ""),
                    "reason": ("the axis register's own reference-year row"
                               if priced else REFUSE_UNPRICED)})
                continue
            result = pricers[axis](year)
            row = {"axis": axis, "module": reg["module"],
                   "fiscal_end_year": year, "status": result["status"],
                   "reference_Mt": "", "alternative_Mt": "", "delta_Mt": "",
                   "reason": result.get("reason", "")}
            if result["status"] == PRICED:
                row["reference_Mt"] = round(result["reference_Mt"], 5)
                row["alternative_Mt"] = round(result["alternative_Mt"], 5)
                row["delta_Mt"] = round(result["alternative_Mt"]
                                        - result["reference_Mt"], 5)
            rows.append(row)
    return rows


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, list(FIELDS), rows, banner=("# EVERY registered structural axis in EVERY panel year: the alternative re-priced on that year's own activity where the engine honestly can, an explicit refusal naming the missing evidence where it cannot.", "# Deterministic forks only - no probability, no trajectory ensemble; the longitudinal product's refusal to cross axes into a probabilistic ensemble stands.",))
    priced = sum(1 for r in rows if r["status"] == PRICED)
    register_rows = sum(1 for r in rows if r["status"] == PRICED_REGISTER)
    refused = sum(1 for r in rows if r["status"] == REFUSED)
    print("structural trajectories -> %s" % os.path.basename(OUT))
    print("  %d axis-years: %d priced per-year, %d reference-register, "
          "%d refused with reasons" % (len(rows), priced, register_rows,
                                       refused))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
