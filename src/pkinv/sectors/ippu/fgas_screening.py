"""The F-gas screening lane (rc20): a priced scope extension, outside every total.

WHAT CHANGED AND WHAT DID NOT. 2.F stays NE in the reference inventory - that does
not change until species-, application- and bank-resolved evidence supports an IPCC
emissions calculation (the field-by-field contract a real dataset must meet is
data/activity/ippu/hfc_inventory_import_contract.csv, and the bank engine that will
consume it is fgases.py). What changed is that the absence is now PRICED: UNEP's
country data publishes Pakistan's aggregate Annex-F consumption (Article 7:
production + imports - exports, bulk substances), and a consumption observation
bounds the scope question the way the kiln-coal screening bounds its category.

THE LABEL IS THE METHOD. The screening value is a POTENTIAL-CONSUMPTION-EQUIVALENT:
the calendar-2024 reported consumption, taken as if all supplied gas were emitted.
IPCC calls this the potential approach and says it is inappropriate for formal
annual reporting - gas entering equipment banks leaks over years, so potential
overstates early-life years and ignores the bank the past has already built. It is
used here ONLY as a screening bound on an absent category, never as an emissions
estimate, and the configuration that carries it lives outside every reference total.

FOUR EVIDENCE LANES, NEVER BLENDED. The screening output publishes each lane as
its own typed row, because they measure different quantities and genuinely
disagree:

  official_bulk_consumption      UNEP Article-7 aggregate, calendar 2024:
                                 9.815 Mt CO2e of SUPPLY, not emissions.
  official_emissions_comparator  Pakistan's own 2022 CRT filing, category 2.F:
                                 0.00294 Mt CO2e - the filing books the category
                                 as almost entirely NE/NO with a small HFC-23
                                 entry, three orders of magnitude below the
                                 consumption lane. The gap IS the finding: the
                                 official record neither models the bank nor
                                 claims the supply.
  external_emissions_benchmark   EDGAR's 11.54 Mt CO2e for 2024 F-gases - an
                                 external model, kept as the completeness
                                 benchmark it always was.
  customs_trade_screening        UN Comtrade's HS-2022 HFC lines (2903.41-49
                                 bulk; 3827 mixtures), reporter Pakistan,
                                 partner World (rc30): net-mass SUPPLY through
                                 customs, the species/mixture screening the
                                 eighteenth review asked for. Mass, not CO2e -
                                 converting would need the species split inside
                                 3827 mixtures, which is exactly what the NOU
                                 request is for.

Averaging any two of these would manufacture a number no evidence supports.

CALENDAR VS FISCAL, DECLARED. The reference period FY2023-24 spans calendar 2023
H2 and 2024 H1; calendar 2023 is publicly unreported (a `missing` row in the
controls file), so the screening anchors on calendar 2024 - the nearest reported
observation - and says so rather than interpolating.

Usage:  python3 -m pkinv.sectors.ippu.fgas_screening
Writes: outputs/ippu_fgas_screening_2024.csv
"""
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import write_table
from pkinv.assets import asset_path

CONTROLS = asset_path(DATA, "activity", "ippu", "hfc_consumption_controls.csv")
TRADE = asset_path(DATA, "activity", "ippu", "hfc_trade_screening.csv")
CRT_SUMMARY = asset_path(OUTPUTS, "ippu_unfccc_crt_summary_2022.csv")
OUT = asset_path(OUTPUTS, "ippu_fgas_screening_2024.csv")

SCREENING_YEAR = 2024          # nearest reported calendar year to FY2023-24
BENCHMARK_MT = 11.54           # EDGAR 2025 booklet, 2F; pinned to data/benchmarks.csv


def _consumption_mt(year=SCREENING_YEAR):
    for r in _activity_rows(CONTROLS, comments=True):
        if int(r["calendar_year"]) == year:
            if r["status"] != "reported":
                raise SystemExit(
                    "fgas screening: calendar %d is %s, not reported - the "
                    "screening year must be a reported observation" %
                    (year, r["status"]))
            if r["is_emissions"] != "false":
                raise SystemExit("fgas screening: the control row claims to be "
                                 "emissions; the lane typing is broken")
            return float(r["value_t_co2e"]) / 1e6
    raise SystemExit("fgas screening: no calendar-%d row in %s" % (year, CONTROLS))


def _crt_2f_mt():
    # the CRT extraction is in kilotonnes CO2e; the 2.F row's total is HFC-only
    for r in _activity_rows(CRT_SUMMARY, comments=False):
        if r["category"].startswith("2.F.  Product uses"):
            return float(r["total_co2e_kt"]) / 1e3
    raise SystemExit("fgas screening: the 2022 CRT summary carries no 2.F row")


def _trade_net_import_kt(year=SCREENING_YEAR):
    """Net bulk+mixture HFC imports through customs, kilotonnes of substance."""
    rows_ = [r for r in _activity_rows(TRADE, comments=False)
             if int(r["calendar_year"]) == year]
    if not rows_:
        raise SystemExit("fgas screening: no calendar-%d rows in %s" % (year, TRADE))
    imports = sum(float(r["net_kg"]) for r in rows_ if r["flow"] == "import")
    exports = sum(float(r["net_kg"]) for r in rows_ if r["flow"] == "export")
    return (imports - exports) / 1e6


# THE BOUNDED BANK MODEL (rc30, the eighteenth review's free configuration). One
# CO2e-weighted stratum run through the mass-conserving bank kernel: supply is
# the UNEP consumption series itself, so nothing about species or applications is
# invented - what IS assumed is declared line by line below, every value an IPCC
# default or a UNEP-recorded fact, and the loss-rate spread brackets the answer.
#
#   start year / bank      2019, empty - consumption before 2019 is unreported;
#                          an empty start UNDERSTATES the bank, so the model is
#                          a lower-leaning bound by construction
#   2021-2023 supply       UNEP reports the years as missing; linear
#                          interpolation 2020->2024, labelled modelled
#   manufacturing loss     0.5% of new charge (IPCC 2006 V3 Ch7 assembly low)
#   operating loss         central 10%/yr of the operating bank, bracketed
#                          5-15% (IPCC 2006 V3 Ch7.5 refrigeration/AC defaults
#                          span 2-25% by application; the mid-range is used
#                          because the application split is exactly what is not
#                          held)
#   retirement             none inside the window: a bank started in 2019 with
#                          ~15-year equipment lifetimes retires nothing by 2024
#   recovery               0% - UNEP records no HFC licensing system in
#                          Pakistan, and no recovery infrastructure is documented
BANK_START_YEAR = 2019
BANK_LOSS_CENTRAL, BANK_LOSS_LOW, BANK_LOSS_HIGH = 0.10, 0.05, 0.15
BANK_MANUFACTURING_LOSS = 0.005


def _supply_series_mt():
    """UNEP consumption by calendar year, Mt CO2e, with declared interpolation."""
    reported = {}
    for r in _activity_rows(CONTROLS, comments=True):
        if r["status"] == "reported":
            reported[int(r["calendar_year"])] = float(r["value_t_co2e"]) / 1e6
    series = []
    for year in range(BANK_START_YEAR, SCREENING_YEAR + 1):
        if year in reported:
            series.append((year, reported[year], "reported"))
        else:
            before = max(y for y in reported if y < year)
            after = min(y for y in reported if y > year)
            frac = (year - before) / (after - before)
            series.append((year, reported[before] +
                           (reported[after] - reported[before]) * frac, "modelled"))
    return series


def bounded_bank(loss_fraction=BANK_LOSS_CENTRAL):
    """Run the one-stratum bank; returns (per-year ledgers, screening-year Mt)."""
    from pkinv.sectors.ippu.material_flows import fgas_bank_step
    bank, ledgers = 0.0, []
    for year, supply_mt, status in _supply_series_mt():
        step = fgas_bank_step(bank, supply_mt, BANK_MANUFACTURING_LOSS,
                              loss_fraction, 0.0, 0.0)
        step.update({"year": year, "supply_status": status,
                     "operating_loss_fraction": loss_fraction})
        ledgers.append(step)
        bank = step["bank_end_t"]
    return ledgers, ledgers[-1]["total_emissions_t"]


def _species_bank_latest():
    """The species-resolved bank's latest-year emissions, Mt CO2e AR5 (rc46 Wave 4)."""
    from pkinv.sectors.ippu import hfc_bank
    rows = hfc_bank.build()
    latest = max(int(r["year"]) for r in rows)
    return round(sum(float(r["emissions_Mt_co2e_AR5"]) for r in rows
                     if int(r["year"]) == latest), 5)


def rows():
    consumption = _consumption_mt()
    crt = _crt_2f_mt()
    trade_kt = _trade_net_import_kt()
    _ledgers, bank_central = bounded_bank()
    _l, bank_low = bounded_bank(BANK_LOSS_LOW)
    _h, bank_high = bounded_bank(BANK_LOSS_HIGH)
    shared = {"reference_period": "FY2023-24"}
    return [
        dict(shared, configuration="reference", adjustment_Mt_co2e=0.0,
             lane="", value_Mt_co2e="", value_is_emissions="",
             note="2.F stays NE in the reference inventory: no species-, "
                  "application- or bank-resolved evidence is held, and an "
                  "aggregate consumption figure is not an emissions estimate"),
        dict(shared, configuration="scope_plus_fgas_screening",
             adjustment_Mt_co2e=round(consumption, 5),
             lane="official_bulk_consumption",
             value_Mt_co2e=round(consumption, 5), value_is_emissions="false",
             note="POTENTIAL-CONSUMPTION-EQUIVALENT, screening grade: the "
                  "calendar-2024 UNEP Article-7 aggregate taken as if all "
                  "supplied gas were emitted - a scope bound, deliberately "
                  "outside every reference total, labelled by its method. The "
                  "calendar/fiscal mismatch (FY2023-24 vs calendar 2024; 2023 "
                  "unreported) is declared, not interpolated"),
        dict(shared, configuration="(comparator, never selected)",
             adjustment_Mt_co2e="",
             lane="official_emissions_comparator",
             value_Mt_co2e=round(crt, 5), value_is_emissions="true",
             note="Pakistan's own 2022 CRT filing, category 2.F: booked almost "
                  "entirely NE/NO with a small HFC-23 entry - three orders of "
                  "magnitude below the consumption lane, which is the whole gap "
                  "a bank model would have to explain"),
        dict(shared, configuration="(benchmark, never selected)",
             adjustment_Mt_co2e="",
             lane="external_emissions_benchmark",
             value_Mt_co2e=BENCHMARK_MT, value_is_emissions="true",
             note="EDGAR 2025 booklet F-gases for 2024, the completeness "
                  "benchmark; an external model, not a Pakistani record"),
        dict(shared, configuration="scope_plus_fgas_bounded_bank",
             adjustment_Mt_co2e=round(bank_central, 5),
             lane="bounded_bank_model",
             value_Mt_co2e=round(bank_central, 5), value_is_emissions="modelled",
             note="THE BOUNDED BANK MODEL (rc30): one CO2e-weighted stratum, "
                  "supply = the UNEP consumption series (2021-23 interpolated, "
                  "labelled), empty 2019 start (a lower-leaning bound), 0.5%% "
                  "assembly loss, 10%%/yr operating loss bracketed [%.2f, %.2f] "
                  "Mt by the 5-15%% IPCC range, no retirement inside the window, "
                  "zero recovery per UNEP's no-licensing-system record. A "
                  "screening configuration outside every reference total - "
                  "between the CRT's near-zero and the potential-consumption "
                  "ceiling, which is exactly where a bank answer must sit"
                  % (bank_low, bank_high)),
        # rc46 Wave 4: the SPECIES-RESOLVED bank supersedes the one-stratum reading as the
        # configuration lane's best bank answer; the bounded bank above stays as the
        # comparator it now is (its bracket [2.3, 6.2] contains the species answer for
        # 2023, which is the mutual corroboration two different constructions owe each
        # other). Computed by pkinv.sectors.ippu.hfc_bank over the populated import
        # contract; 2.F still enters no total - the gate's charged-equipment criterion
        # remains unmet and says so on the scope registry row.
        dict(shared, configuration="scope_plus_fgas_species_bank",
             adjustment_Mt_co2e=_species_bank_latest(),
             lane="species_resolved_bank",
             value_Mt_co2e=_species_bank_latest(), value_is_emissions="modelled",
             note="THE SPECIES-RESOLVED BANK (rc46 Wave 4): per (species, application) "
                  "strata from the UNDP RAC import table (2012-19), Comtrade HS-2022 "
                  "(2022-24) and a typed geometric bridge for 2020-21, run through the "
                  "fgases.py kernel with IPCC application loss defaults and blend GWPs "
                  "priced at component shares. Supersedes the one-stratum bounded bank "
                  "as the lane's answer; per-stratum detail in "
                  "outputs/ippu_hfc_species_bank.csv"),
        dict(shared, configuration="(trade screening, never selected)",
             adjustment_Mt_co2e="",
             lane="customs_trade_screening",
             value_Mt_co2e="", value_is_emissions="false",
             note="UN Comtrade calendar-%d net HFC imports: %.3f kt of substance "
                  "(HS 2903.41-49 bulk plus 3827 mixtures, partner World) - the "
                  "same order as the UNEP consumption lane at plausible mixture "
                  "GWPs, corroborating supply without resolving species; in mass "
                  "units deliberately, because converting mixtures to CO2e would "
                  "invent the species split the NOU request exists to obtain"
                  % (SCREENING_YEAR, trade_kt)),
    ]


def main():
    out = rows()
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, ["configuration", "reference_period",
                                          "adjustment_Mt_co2e", "lane",
                                          "value_Mt_co2e", "value_is_emissions",
                                          "note"], out, banner=('# Four typed evidence lanes for an absent category, never blended; the', '# screening configuration prices the consumption lane as a scope bound', "# OUTSIDE every reference total. See fgas_screening.py's docstring.",))
    ledgers, _central = bounded_bank()
    write_table(asset_path(OUTPUTS, "ippu_fgas_bounded_bank_2024.csv"), list(ledgers[0].keys()), ledgers, banner=('# The one-stratum CO2e-weighted bank model behind the scope_plus_fgas_bounded_bank screening configuration; every assumption is declared in fgas_screening.py. Units are Mt CO2e of charge, not chemical tonnes.',))
    screening = next(r for r in out
                     if r["configuration"] == "scope_plus_fgas_screening")
    print("fgas screening -> %s (potential-consumption-equivalent %.3f Mt CO2e; "
          "CRT 2022 comparator %.3f; EDGAR benchmark %.2f)"
          % (os.path.relpath(OUT), screening["adjustment_Mt_co2e"],
             _crt_2f_mt(), BENCHMARK_MT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
