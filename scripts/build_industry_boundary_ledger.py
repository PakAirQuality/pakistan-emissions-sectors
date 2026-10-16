#!/usr/bin/env python3
"""THE INDUSTRIAL BOUNDARY LEDGER: one atomic table saying what "industrial
emissions" would contain under the full IPCC boundary -

    Industrial = 1.A.2 (fuel combustion, INCLUDING industry's own captive
                 generation, per the 1.A.2 definition) + 2.A-2.G (IPPU)

- and what of it the release actually prices. Every component appears exactly
once per state: PRICED rows carry the reference estimate per period and gas
(read from the semantic atom table, never re-derived); SCREENED rows carry the
release's own scenario brackets (read from the screening products' own values);
TYPED-ABSENT rows carry the reason and the named acquisition that would close
them; the one DIAGNOSTIC row carries the registered EDGAR 1.A.2 comparison difference (a signed
comparator difference since rc68, not a measure of absent emissions) -
a diagnostic, never a residual to be inserted.

THE LABEL RULE. Until every added category is back-calculated through
FY2015-16, the priced aggregate is "covered direct industrial sources", never
"the entire industrial sector": adding categories only in the reference year
would manufacture an apparent increase (the comparable-scope law).

THE ROADMAP (recorded 2026-09-10, priority order):
  1. close the 1.A.2 fuel balance against an HDIP energy-balance control total;
  2. price ammonia CO2 and nitric acid N2O (the reconciliation and monitoring
     products already exist);
  3. build the HFC equipment-bank model from Ozone Secretariat consumption;
  4. add lime, glass and soda ash;  5. iron/steel and lubricants (2.C, 2.D);
  6. industrial wastewater (4.D.2) as a cross-sector view, coded Waste.

Reads:  outputs/semantic/fact_annual.csv (the priced atoms)
        outputs/industry_solid_screenings_2024.csv
        outputs/industry_captive_screening_2024.csv
        outputs/ippu_chemicals_screening_2024.csv
        outputs/ippu_fgas_screening_2024.csv, ippu_fgas_bounded_bank_2024.csv
        outputs/national_benchmark_comparison.csv (the 1.A.2 diagnostic)
        outputs/pakemis_industry_edgar_divergence.csv (the nine-year EDGAR shape diagnostic)
Writes: outputs/pakemis_industry_boundary_ledger.csv
"""
import collections
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import OUTPUTS  # noqa: E402

OUT = asset_path(OUTPUTS, "pakemis_industry_boundary_ledger.csv")
REF = "S_TAN"

FIELDS = ("ipcc_code", "component", "detail", "gas", "period_id", "module_home",
          "boundary_status", "co2e_Mt", "bound_low_Mt", "bound_high_Mt",
          "comparison_difference_Mt", "comparison_basis",
          "source", "acquisition", "note")

HEADER = """\
# THE INDUSTRIAL BOUNDARY LEDGER - what "industrial emissions" contains under
#   Industrial = 1.A.2 (incl. captive generation) + 2.A-2.G
# and what of it this release prices. boundary_status is the row's one state:
#   priced             in the reference totals (co2e_Mt per period and gas);
#   screened_not_priced the release's own scenario bracket, OUTSIDE every total;
#   typed_absent       not estimated; the reason and the closing acquisition named;
#   diagnostic         the registered benchmark gap - a diagnostic, NEVER a residual.
# THE LABEL RULE: until every added category is back-calculated through FY2015-16,
# the priced aggregate is "covered direct industrial sources", never "the entire
# industrial sector". Empty numeric cells are typed absences, never zeros.
"""


def _rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def priced_rows():
    """The three priced components, per period and gas, read from the atom table.

    The captive row is selected on the REPORTING axis (sector_id power, reporting_sector
    industry - data/stream_reporting_sector.csv), not on a code match; module_home stays
    power, the module that computes it."""
    atoms = _rows(asset_path(OUTPUTS, "semantic", "fact_annual.csv"))
    agg = collections.defaultdict(float)
    for r in atoms:
        if r["configuration_id"] != REF:
            continue
        key = None
        if r["sector_id"] == "industry" and r["reporting_sector"] == "industry":
            key = ("1.A.2", "Industrial fuel combustion", "industry")
        elif r["sector_id"] == "power" and r["reporting_sector"] == "industry":
            key = ("1.A.2", "Captive gas self-generation", "power")
        elif r["reporting_sector"] == "ippu":
            key = (r["ipcc_code"], r["category"], "ippu")
        if key:
            agg[key + (r["gas"], r["period_id"])] += float(r["co2e_Mt_AR5"])
    out = []
    for (ipcc, comp, module, gas, period), mt in sorted(agg.items()):
        out.append({
            "ipcc_code": ipcc, "component": comp, "detail": "",
            "gas": gas, "period_id": period, "module_home": module,
            "boundary_status": "priced", "co2e_Mt": "%.6f" % mt,
            "bound_low_Mt": "", "bound_high_Mt": "",
            "comparison_difference_Mt": "", "comparison_basis": "",
            "source": "outputs/semantic/fact_annual.csv (%s)" % REF,
            "acquisition": "",
            "note": ("the 1.A.2 definition includes industry's own generation, so this row "
                     "belongs to the industrial aggregate although the power module computes it"
                     if comp == "Captive gas self-generation" else ""),
        })
    return out


def row(ipcc, comp, detail, status, low="", high="", source="", acquisition="", note="", module="", gas="", comparison_basis=""):
    if status == "diagnostic" and comparison_basis not in ("engine_minus_comparator", "comparator_minus_engine"):
        raise ValueError("diagnostic comparison direction is required for " + comp)
    return {"ipcc_code": ipcc, "component": comp, "detail": detail, "gas": gas,
            "period_id": "", "module_home": module, "boundary_status": status,
            "co2e_Mt": "", "bound_low_Mt": "" if status == "diagnostic" else low,
            "bound_high_Mt": "" if status == "diagnostic" else high,
            "comparison_difference_Mt": high if status == "diagnostic" else "",
            "comparison_basis": comparison_basis,
            "source": source, "acquisition": acquisition, "note": note}


def screened_rows():
    out = []
    solids = {(r["name"], r["bound"]): r for r in _rows(asset_path(OUTPUTS, "industry_solid_screenings_2024.csv"))}
    kiln_lo, kiln_hi = solids[("Cement kiln fuel", "low")], solids[("Cement kiln fuel", "high")]
    out.append(row("1.A.2", "Cement kiln fuel", "clinker heat, coal/petcoke", "screened_not_priced",
                   kiln_lo["quantity"], kiln_hi["quantity"],
                   "outputs/industry_solid_screenings_2024.csv "
                   "(cement gas ~nil confirmed by outputs/ogra_gas_class_series.csv cement class)",
                   "a Pakistani kiln heat audit, or the HDIP energy balance's cement coal",
                   "central %s; a REPLACEMENT comparator for the reference's own cement-sector "
                   "coal, priced NET as cement_kiln_fuel_in_scope (+2.80 Mt) - not an addition "
                   "to the 1.A.2 gap" %
                   solids[("Cement kiln fuel", "central")]["quantity"], gas="CO2"))
    bag = solids[("Process bagasse CH4+N2O", "ceiling")]
    out.append(row("1.A.2", "Industrial bagasse CH4+N2O", "process heat, whole-crop ceiling",
                   "screened_not_priced", "", bag["quantity"],
                   "outputs/industry_solid_screenings_2024.csv",
                   "PSMA mill crush share", "CEILING - biogenic CO2 outside every total", gas="CH4+N2O"))
    captive = {r["fuel_class"]: r for r in _rows(asset_path(OUTPUTS, "industry_captive_screening_2024.csv"))}
    out.append(row("1.A.2", "Captive coal fleet", "%s MW, %s plants" % (captive["coal"]["capacity_MW"], captive["coal"]["plants"]),
                   "screened_not_priced", captive["coal"]["bracket_low_Mt"], captive["coal"]["bracket_high_Mt"],
                   "outputs/industry_captive_screening_2024.csv",
                   "NEPRA captive licences with fuel logs", "", gas="CO2"))
    out.append(row("1.A.2", "Captive biomass CH4+N2O", "non-bagasse biomass",
                   "screened_not_priced", captive["biomass"]["bracket_low_Mt"], captive["biomass"]["bracket_high_Mt"],
                   "outputs/industry_captive_screening_2024.csv", "", "biogenic CO2 outside every total", gas="CH4+N2O"))
    chem = {r["stream"]: r for r in _rows(asset_path(OUTPUTS, "ippu_chemicals_screening_2024.csv")) if r["stream"]}
    # 2.B.1 ammonia: PRICED since rc52 (Tier 1 calibrated, nine years) - it is a priced row above, not a screening
    nit = chem["Nitric acid (Fatima Sadiqabad)"]
    out.append(row("2.B.2", "Nitric acid N2O", "one plant, prior-vintage production", "screened_not_priced",
                   nit["bracket_low_Mt"], nit["bracket_high_Mt"],
                   "outputs/ippu_chemicals_screening_2024.csv + ippu_nitric_acid_monitoring.csv",
                   "actual abatement operation records (the CDM monitoring ended) - roadmap step 2",
                   "abated-case point exists in the screening file", gas="N2O"))
    # 2.C.1 iron and steel: PRICED since rc52 (Tier 1 EAF on QIM billets, nine years)
    out.append(row("2.B.7", "Soda ash", "Solvay process (LCI Khewra, Olympia)", "typed_absent",
                   acquisition="coke tonnage burned in the Solvay lime kilns (LCI reports) - a 1.A.2 term, not 2.B.7",
                   note="NA in IPPU by IPCC 2006 Vol 3 s3.8.3.1: Solvay emissions are allocated to the Energy sector (coke), no IPPU "
                        "method is provided; the earlier natural-process ceiling (0.0974 t/t) was the wrong method for a Solvay country - "
                        "nine-year activity in pakemis_industrial_screening_series.csv", gas="CO2"))
    bank = _rows(asset_path(OUTPUTS, "ippu_fgas_bounded_bank_2024.csv"))
    last = max(bank, key=lambda r: int(r["year"]))
    out.append(row("2.F", "F-gas bounded bank", "HFC bank model, %s" % last["year"], "screened_not_priced",
                   "", "%.5f" % float(last["total_emissions_t"]),
                   "outputs/ippu_fgas_bounded_bank_2024.csv + ippu_fgas_screening_2024.csv",
                   "Ozone Secretariat consumption into an equipment-bank model (consumption is supply, "
                   "not emission) - roadmap step 3",
                   "the scope_plus_fgas_bounded_bank screening configuration's own year", gas="HFCs"))
    return out


def absent_rows():
    chem_reasons = {r["stream"]: r["note"] for r in _rows(asset_path(OUTPUTS, "ippu_chemicals_screening_2024.csv")) if r["stream"]}
    captive = {r["fuel_class"]: r for r in _rows(asset_path(OUTPUTS, "industry_captive_screening_2024.csv"))}
    return [
        row("2.A.2", "Lime", "", "typed_absent",
            source="outputs/ippu_chemicals_screening_2024.csv (refused_no_activity)",
            acquisition="a national lime-production series (PBS minerals statistics, producer reports) - roadmap step 4",
            note=chem_reasons.get("Lime", "")),
        row("2.A.3", "Glass", "", "typed_absent",
            source="outputs/ippu_chemicals_screening_2024.csv (refused_activity_not_mass)",
            acquisition="glass output by MASS (PBS QIM publishes area) - roadmap step 4",
            note=chem_reasons.get("Glass", "")),
        row("1.A.2", "Captive furnace-oil and diesel", "%s MW" % captive["furnace_oil+diesel"]["capacity_MW"], "typed_absent",
            source="outputs/industry_captive_screening_2024.csv (excluded_possible_IE)",
            acquisition="OGRA/OCAC customer-class splits that separate captive purchases from Total Industry",
            note="excluded for double-count risk: the fleet buys from the market OCAC's Total Industry row already covers"),
        row("1.A.2", "Steel works process gas", "blast-furnace and coke-oven gas", "typed_absent",
            source="outputs/industry_captive_screening_2024.csv (refused_needs_works_balance)",
            acquisition="the works' own carbon balance - roadmap step 5"),
        # 2.D.1 lubricant use: PRICED since rc52 (Tier 1 ODU on OCAC non-energy sales, nine years)
        row("2.D.2", "Paraffin wax and other non-energy products", "2.D.2/2.D.3", "typed_absent",
            acquisition="OCAC non-energy sales carry MTT, solvent, process oil and asphalt (held, ingested); IPCC ODU factors for these products and the two-stroke lubricant share",
            note="lubricants (2.D.1) are priced since rc52; the remaining non-energy products are held as sales but not yet priced"),
        row("2.G", "SF6 and other product uses", "electrical equipment and other applications", "typed_absent",
            acquisition="Customs/UN Comtrade equipment and gas imports; utility equipment stock"),
        row("4.D.2", "Industrial wastewater CH4 and N2O", "by industry type", "typed_absent", module="waste",
            acquisition="PBS production by industry, provincial EPD effluent and COD records - roadmap step 6",
            note="belongs to the Waste module (4.D.2); appears in an ECONOMIC-SECTOR VIEW of industry only, never re-coded"),
    ]


def diagnostic_row():
    bench = _rows(asset_path(OUTPUTS, "national_benchmark_comparison.csv"))
    r = next(b for b in bench if b["engine_category"] == "1A2 (all estimated)")
    gap = float(r["benchmark_Mt_co2e"]) - float(r["engine_Mt_co2e"])
    return [row("1.A.2", "EDGAR 1.A.2 comparison difference", "benchmark %s vs engine %s Mt" % (r["benchmark_Mt_co2e"], r["engine_Mt_co2e"]),
                "diagnostic", "", "%.2f" % gap,
                "outputs/national_benchmark_comparison.csv (comparison_role=diagnostic)",
                "public coal supply/use controls, station consumption and OGRA's sector-wise gas "
                "classes distinguish feedstock, captive and general industry; remaining source "
                "differences require matched periods and activity/factor/coverage reconciliation",
                "Signed comparator minus estimated-source difference, not absent emissions, a floor "
                "or an upper bound. Fiscal/calendar periods, fuel allocations, factors and source "
                "coverage differ; never insert the difference as residual activity.",
                comparison_basis="comparator_minus_engine"),
            _unsd_diagnostic()]


def _engine_1a2_by_period(native_co2=False):
    """The engine's 1.A.2 per period: the industry module plus the captive generation the
    power module computes (both IPCC 1.A.2), from the priced atoms."""
    out = collections.defaultdict(float)
    for r in _rows(asset_path(OUTPUTS, "semantic", "fact_annual.csv")):
        if r["configuration_id"] != REF or r["geography_id"] != "PK":
            continue
        if native_co2 and r["gas"] != "CO2":
            continue
        if r["sector_id"] == "industry" or (r["sector_id"] == "power" and r["ipcc_code"] == "1.A.2"):
            if native_co2 and r["native_unit"] != "Gg":
                raise ValueError("industrial native CO2 comparison requires Gg atoms")
            out[r["period_id"]] += (float(r["native_mass"]) / 1000 if native_co2
                                    else float(r["co2e_Mt_AR5"]))
    return out


def _unsd_series_diagnostics():
    """One diagnostic row PER PERIOD from the UNSD control at the fiscal blend (half of each
    adjacent calendar column): the second benchmark's SHAPE beside EDGAR's. UNSD manufacturing
    excludes captive generation and includes cement kiln coal, so it brackets the engine high
    by construction; the sign and size of the gap per year is the diagnostic, never a residual."""
    rows = _rows(asset_path(OUTPUTS, "unsd_industry_combustion_control.csv"))
    totals = {int(r["year"]): float(r["co2_Mt"]) for r in rows if r["fuel"] == "FOSSIL_COMBUSTION_TOTAL"}
    engine = _engine_1a2_by_period(native_co2=True)
    out = []
    for period in sorted(engine):
        y = int(period[2:6]) + 1
        if (y - 1) not in totals or y not in totals:
            continue
        blend = 0.5 * totals[y - 1] + 0.5 * totals[y]
        d = row("1.A.2", "UNSD 1.A.2 series benchmark",
                "native CO2: engine %.3f vs UNSD manufacturing %.3f Mt at 0.5 x CY%d + 0.5 x CY%d" % (engine[period], blend, y - 1, y),
                "diagnostic", "", "%.3f" % (engine[period] - blend),
                "outputs/unsd_industry_combustion_control.csv",
                "the HDIP energy balance as the 1.A.2 control total - roadmap step 1",
                "UNSD manufacturing excludes captive generation, while fuel and source boundaries differ; "
                "shared national energy statistics limit independence. Engine minus UNSD is a signed "
                "diagnostic, not missing emissions or a bound.", gas="CO2", comparison_basis="engine_minus_comparator")
        d["period_id"] = period
        out.append(d)
    return out


def _unsd_diagnostic():
    """The second, independent 1.A.2 benchmark: UNSD's manufacturing combustion at the
    release's own IPCC factors, with a distinct fuel/source/calendar boundary."""
    rows = _rows(asset_path(OUTPUTS, "unsd_industry_combustion_control.csv"))
    totals = {r["year"]: float(r["co2_Mt"]) for r in rows if r["fuel"] == "FOSSIL_COMBUSTION_TOTAL"}
    latest = max(totals)
    engine = _engine_1a2_by_period(native_co2=True)["FY2023-24"]
    return row("1.A.2", "UNSD 1.A.2 combustion benchmark",
               "native CO2: UNSD manufacturing %g Mt (CY%s) vs engine %.2f Mt" % (totals[latest], latest, engine),
               "diagnostic", "", "%.2f" % (totals[latest] - engine),
               "outputs/unsd_industry_combustion_control.csv",
               "already held - UNSD energy balances (the public HDIP stand-in), the release's "
               "own IPCC 2006 CO2 factors applied - roadmap step 1",
               "UNSD manufacturing excludes captive generation and shares national energy statistics "
               "with other comparators. Comparator minus engine is a scope-approximate signed "
               "difference, not a missing-emissions floor or upper bound.",
               gas="CO2", comparison_basis="comparator_minus_engine")


def _edgar_series_diagnostics():
    """One diagnostic row PER PERIOD from the nine-year divergence product: where the engine's
    1.A.2 (industry + captive) and EDGAR's Industrial Combustion part at the fiscal blend. The
    reference-year coverage row above stays; this lane carries the SHAPE. Never a residual."""
    out = []
    for r in _rows(asset_path(OUTPUTS, "pakemis_industry_edgar_divergence.csv")):
        d = row("1.A.2", "EDGAR 1.A.2 series divergence",
                "engine %s vs EDGAR %s Mt at %s" % (r["engine_1a2_mt"], r["edgar_industrial_combustion_mt"], r["edgar_basis"]),
                "diagnostic", "", r["divergence_1a2_mt"],
                "outputs/pakemis_industry_edgar_divergence.csv",
                "reconcile public coal production/imports, documented station consumption and "
                "industrial allocations before attributing a comparator difference to missing sources",
                "a DIAGNOSTIC of shape (engine minus EDGAR at the fiscal blend), never an EDGAR residual to "
                "insert; EDGAR is IEA-balance-derived and HDIP-fed upstream, 2023-2024 preliminary; %s" % r["reading"],
                comparison_basis="engine_minus_comparator")
        d["period_id"] = r["period_id"]
        out.append(d)
    return out


def main():
    priced = priced_rows()
    rows = priced + screened_rows() + absent_rows() + diagnostic_row() + _edgar_series_diagnostics() + _unsd_series_diagnostics()
    with open(OUT, "w", newline="", encoding="utf-8") as handle:
        handle.write(HEADER)
        writer = csv.DictWriter(handle, fieldnames=list(FIELDS), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    ref_total = sum(float(r["co2e_Mt"]) for r in priced if r["period_id"] == "FY2023-24")
    periods = {r["period_id"] for r in priced}
    print("industry boundary ledger -> %s (%d rows; covered direct industrial sources "
          "FY2023-24 = %.2f Mt over %d periods)" % (os.path.relpath(OUT), len(rows), ref_total, len(periods)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
