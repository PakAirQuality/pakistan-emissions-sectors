"""Direct HTAPv3.2 Pakistan extraction and exact fiscal comparisons (NH3, and since rc68 all
seven core species at a process boundary in pakemis_air_htap_species_comparison.csv).

The original publisher ZIP is retained. Its country/sector monthly table is read
without a private account or spatial-subset service. Printed annual controls are
checked before any comparison. Post-2015 REAS levels in this mosaic use EDGAR
trends; agreement therefore does not constitute independent trend validation.
"""
import argparse
import collections
import csv
import hashlib
import io
import os
import zipfile

from pkinv.assets import asset_path
from pkinv.core import configurations as conf
from pkinv.core.io import read_rows
from pkinv.core.reporting_window import CORE_SUFFIX, CORE_FY_STARTS
from pkinv.paths import ROOT, OUTPUTS

RAW = asset_path(ROOT, "data/raw/htap/edgar_HTAPv32_NH3.zip")
ANNUAL = asset_path(OUTPUTS, "pakemis_htap_nh3_annual.csv")
MONTHLY = asset_path(OUTPUTS, "pakemis_htap_nh3_monthly.csv")
COMPARISON = asset_path(OUTPUTS, "pakemis_air_htap_comparison.csv")
PANEL = asset_path(OUTPUTS, "pakemis_air_annual_%s.csv" % CORE_SUFFIX)
SOURCE = "https://edgar.jrc.ec.europa.eu/dataset_htap_v32"
MEMBER = "edgar_HTAPv3_2_NH3.xlsx"
SHEET = "edgar_HTAPv3_2_NH3"
MONTHS = ("January", "February", "March", "April", "May", "June", "July",
          "August", "September", "October", "November", "December")
PROVENANCE = ("inventory_version", "provider", "country", "species", "sector", "source_file",
              "source_sha256", "source_sheet", "source_row", "source_url", "note")
ANNUAL_FIELDS = ("calendar_year", "annual_Mg", "sum_months_Mg", "control_residual_Mg") + PROVENANCE
MONTHLY_FIELDS = ("month", "emissions_Mg") + PROVENANCE
COMPARE_FIELDS = ("period_id", "configuration_id", "pollutant", "comparison_sector", "pakemis_Gg",
                  "htap_Gg", "ratio_pakemis_over_htap", "comparison_status", "time_basis", "provider",
                  "shared_input_note", "boundary_note", "source_sha256")


def extract(path=RAW, member=MEMBER, sheet_name=SHEET):
    import openpyxl
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError("HTAP archive CRC failed")
        workbook = openpyxl.load_workbook(io.BytesIO(archive.read(member)), read_only=True, data_only=True)
    sheet = workbook[sheet_name]
    rows = sheet.iter_rows(values_only=True)
    header = tuple(next(rows))
    expected = ("Data_provider", "Substance", "Year", "Country", "Sector") + MONTHS + ("Annual",)
    if header != expected:
        raise ValueError("HTAP source table header changed: %r" % (header,))
    annual, monthly, seen = [], [], set()
    for line, values in enumerate(rows, 2):
        provider, species, year, country, sector = values[:5]
        if country != "PAK":
            continue
        key = (year, country, sector, species)
        if key in seen:
            raise ValueError("duplicate HTAP country/sector/year record: %r" % (key,))
        seen.add(key)
        months = values[5:17]
        if any(v is None or float(v) < 0 for v in months) or values[17] is None:
            raise ValueError("missing or negative HTAP physical mass at source row %d" % line)
        total, printed = sum(months), float(values[17])
        residual = total - printed
        if abs(residual) > max(1e-7, 1e-10 * abs(printed)):
            raise ValueError("HTAP printed annual control disagrees with months at row %d: %g Mg" % (line, residual))
        provenance = dict(inventory_version="HTAPv3.2_publisher_release_2025-09", provider=provider,
                          country=country, species=species, sector=sector,
                          source_file="data/raw/htap/%s!%s" % (os.path.basename(path), member),
                          source_sha256=digest, source_sheet=sheet_name, source_row=line,
                          source_url=SOURCE,
                          note="Workbook _info says HTAPv3.1; publisher release, filename and data sheet identify v3.2. Original labels retained. REAS beyond2015 uses EDGAR trends.")
        annual.append(dict(provenance, calendar_year=int(year), annual_Mg=printed,
                           sum_months_Mg=total, control_residual_Mg=residual))
        monthly.extend(dict(provenance, month="%04d%02d" % (year, number), emissions_Mg=float(mass))
                       for number, mass in enumerate(months, 1))
    workbook.close()
    years = {r["calendar_year"] for r in annual}
    if years != set(range(2000, 2021)):
        raise ValueError("HTAP Pakistan calendar coverage is not 2000–2020: %r" % sorted(years))
    return annual, monthly


def comparison(monthly, panel):
    external = collections.defaultdict(float)
    providers = collections.defaultdict(set)
    support = collections.defaultdict(set)
    digest = monthly[0]["source_sha256"]
    for row in monthly:
        month = str(row["month"])
        start = int(month[:4]) - (int(month[4:]) <= 6)
        sector = row["sector"]
        if "Agriculture_" in sector or "Agricultural_waste_burning" in sector:
            match = "agriculture"
        elif "Road_Transport" in sector:
            match = "transport"
        elif "Residential" in sector:
            match = "residential"
        elif "Waste" in sector:
            match = "waste"
        else:
            continue
        external[start, match] += float(row["emissions_Mg"]) / 1000
        providers[start, match].add(row["provider"])
        support[start, match, sector].add(month)
    internal = collections.defaultdict(float)
    for row in panel:
        if row["pollutant"] == "NH3":
            internal[int(row["fiscal_end_year"]) - 1, conf.canonical(row["configuration_id"]), row["sector_id"]] += float(row["emissions_Gg"])
    result = []
    for start in CORE_FY_STARTS:
        complete = 2000 <= start and start + 1 <= 2020
        for cfg in conf.AIR_ALL:
            for sector in ("agriculture", "transport", "residential", "waste"):
                estimate = internal.get((start, cfg, sector))
                if estimate is None:
                    raise ValueError("NH3 comparison lacks the advertised engine sector/year/configuration")
                if complete:
                    expected_count = 3 if sector == "agriculture" else 1
                    categories = [months for (fy, match, _source), months in support.items()
                                  if fy == start and match == sector]
                    if len(categories) != expected_count or any(len(months) != 12 for months in categories):
                        raise ValueError("incomplete HTAP monthly source coverage for FY%d %s" % (start, sector))
                other = external[start, sector] if complete else None
                compatible = sector in ("agriculture", "transport")
                boundary = ("agricultural livestock, crops and field burning summed on both sides; source allocation within agriculture differs" if sector == "agriculture" else
                            "road transport exhaust NH3; other ground transport excluded" if sector == "transport" else
                            "PakEmis gross household appliance emissions; HTAP residential release definition and commercial coverage may differ" if sector == "residential" else
                            "PakEmis open burning only; HTAP waste includes additional treatment sources")
                result.append(dict(period_id="FY%d-%02d" % (start, (start + 1) % 100), configuration_id=cfg,
                                   pollutant="NH3", comparison_sector=sector, pakemis_Gg=estimate,
                                   htap_Gg=other if other is not None else "",
                                   ratio_pakemis_over_htap=estimate / other if complete and compatible and other else "",
                                   comparison_status=("sector_comparison" if compatible else "boundary_difference_context_only") if complete else "no_complete_external_fiscal_period",
                                   time_basis="exact July–June sum of twelve published source months" if complete else "HTAP ends December2020; no partial or extrapolated fiscal counterpart",
                                   provider=";".join(sorted(providers[start, sector])) if complete else "",
                                   shared_input_note="REAS regional baseline; EDGAR agricultural burning/gapfills and post2015 trends; not independent trend validation",
                                   boundary_note=boundary, source_sha256=digest))
    return result


# --- rc68: all seven core species at a process boundary ---------------------------------
#
# The NH3 comparison above stays exactly as published. This extends the same rule to the six
# other core species, held from the same keyless JRC open-data release, and draws the boundary
# at the emitting PROCESS rather than the reporting sector: road exhaust (with evaporative
# NMVOC) against HTAP road transport, tyre and brake wear against HTAP brake and tyre wear,
# residue burning against agricultural waste burning, livestock and soils against HTAP's two
# agricultural sectors, domestic aviation against HTAP's three domestic-aviation phases. A
# ratio is published only where both sides describe the same process; every other row keeps
# both masses and says why there is no ratio. Nothing here is read back into the inventory.
SPECIES = ("BC", "CO", "NH3", "NMVOC", "NOx", "PM2.5", "SO2")
SPECIES_COMPARISON = asset_path(OUTPUTS, "pakemis_air_htap_species_comparison.csv")
ATOMS = asset_path(OUTPUTS, "pakemis_air_atomic_annual.csv")
SPECIES_FIELDS = ("period_id", "configuration_id", "pollutant", "comparison_group", "pakemis_Gg",
                  "htap_Gg", "ratio_pakemis_over_htap", "comparison_status", "htap_sectors",
                  "htap_providers", "pakemis_scope", "boundary_note", "decomposition",
                  "pakemis_activity", "pakemis_activity_unit", "pakemis_implied_factor",
                  "htap_equivalent_factor_at_pakemis_activity", "factor_unit", "time_basis",
                  "shared_input_note", "units", "source_sha256")
UNITS = ("Gg of native pollutant mass on both sides; NOx as NO2; NH3 as NH3; SO2 as SO2; "
         "HTAP Mg divided by 1000")
SHARED = ("REAS regional baseline for Asia with post-2015 levels extended by EDGAR trends; EDGAR "
          "for aviation, wear, solvents and agriculture; both draw on international fuel and "
          "agricultural statistics that overlap PakEmis inputs; not independent confirmation")


def _htap_path(species):
    return asset_path(ROOT, "data/raw/htap/edgar_HTAPv32_%s.zip" % species)


def _member(species):
    return "edgar_HTAPv3_2_%s.xlsx" % species, "edgar_HTAPv3_2_%s" % species


def species_monthly(species):
    member, sheet = _member(species)
    _annual, monthly = extract(_htap_path(species), member, sheet)
    return monthly


# (group, htap sector suffixes, matched?, pakemis selector, scope, boundary note, activity unit)
GROUPS = (
    ("road_exhaust", ("5.1_Road_Transport",), True,
     lambda a: a["sector_id"] == "transport" and a["process"] in ("exhaust", "evaporative"),
     "transport atoms, processes exhaust + evaporative (EMEP Tier 1, hot and cold operation inside the factor)",
     "on-road exhaust and evaporation both sides; off-road machinery excluded from PakEmis and in HTAP 5.4; "
     "tyre/brake and road-surface wear excluded here; whether the REAS road sector carries evaporative NMVOC "
     "is not documented per country, so NMVOC carries that caveat", "kt_fuel"),
    ("road_tyre_brake_wear", ("5.2_Brake_and_Tyre_wear",), True,
     lambda a: a["sector_id"] == "transport" and a["process"] == "tyre_brake_wear",
     "transport atoms, process tyre_brake_wear",
     "abrasion particulate both sides; PakEmis road-surface wear is a separate process with no HTAP "
     "counterpart and is excluded; resuspended road dust is in neither", ""),
    ("agricultural_residue_burning", ("8.1_Agricultural_waste_burning",), True,
     lambda a: a["sector_id"] == "agriculture" and a["category"] == "Field burning of residues",
     "agriculture atoms, Field burning of residues",
     "open burning of crop residues in the field both sides", "t_dry_residue"),
    ("agriculture_livestock_and_soils", ("8.2_Agriculture_livestock", "8.3_Agriculture_crops"), True,
     lambda a: a["sector_id"] == "agriculture" and a["category"] in ("Manure management", "Managed soils"),
     "agriculture atoms, Manure management + Managed soils",
     "livestock housing, storage, grazing and manure/fertiliser/residue application both sides; "
     "allocation between HTAP's livestock and crop sectors differs from PakEmis categories", ""),
    ("domestic_aviation", ("2.1.1_Domestic_Aviation_LTO", "2.1.2_Domestic_Aviation_CDS",
                           "2.1.3_Domestic_Aviation_CRS"), True,
     lambda a: a["sector_id"] == "aviation",
     "aviation atoms (domestic LTO and cruise)",
     "domestic flights both sides; PakEmis HC is not NMVOC and is not compared", ""),
    ("residential", ("6_Residential",), False,
     lambda a: a["sector_id"] == "residential",
     "residential atoms (household fuels, gross appliance emissions)",
     "PakEmis gross household appliance emissions with no outdoor-escape fraction; HTAP/REAS residential "
     "also carries commercial and other small combustion; no ratio", ""),
    ("waste", ("7_Waste",), False,
     lambda a: a["sector_id"] == "waste",
     "waste atoms (open burning of municipal waste)",
     "PakEmis open burning only; HTAP waste is treatment and incineration and carries little or no open "
     "burning; no ratio", ""),
    ("industry_and_process", ("4.1_Industry",), False,
     lambda a: a["sector_id"] in ("industry", "ippu"),
     "industry + ippu atoms (fuel combustion incl. captive gas, cement kiln, brick kilns, 2.B/2.C process)",
     "HTAP/REAS industry fuel, biomass and process boundary is not published per Pakistani source class; "
     "PakEmis types industrial biomass (bagasse) absent; captive generation may sit in HTAP energy; no ratio", ""),
    ("fugitives", ("4.2_Fugitive",), False,
     lambda a: a["sector_id"] == "fugitives",
     "fugitives atoms (oil and gas segments, refining, flaring, petrol distribution)",
     "HTAP fugitive sector also carries coal mining and other fugitive sources; no ratio", ""),
    ("public_power", ("3_Energy",), False,
     lambda a: a["sector_id"] == "power",
     "power atoms (admitted oil/diesel SO2 only)",
     "COVERAGE difference: coal, gas and bagasse stack emissions are screening scenarios outside the PakEmis "
     "covered panel; HTAP energy also carries refineries and other energy industries; the gap is not evidence "
     "of low plant emissions; no ratio", ""),
    ("rail_and_other_ground", ("5.4_Other_ground_transport",), False,
     lambda a: a["sector_id"] == "railways",
     "railways atoms",
     "HTAP other ground transport also carries off-road and pipeline transport; no ratio", ""),
)


def _pakemis_mass(atoms, start, cfg, pollutant, select):
    from pkinv.report.air_annual import atom_configuration
    pid = "FY%d-%02d" % (start, (start + 1) % 100)
    mass, activity = 0.0, {}
    found = False
    for a in atoms:
        if a["period_id"] != pid or a["pollutant"] != pollutant or not select(a):
            continue
        if a["configuration_id"] != atom_configuration(cfg, a["sector_id"]):
            continue
        found = True
        mass += float(a["emissions_Gg"])
        activity[(a["source_class_id"], a["process"], a["activity_unit"])] = a["activity_value"]
    return (mass if found else None), activity


def species_comparison(monthly_by_species, atoms):
    rows = []
    for species in SPECIES:
        monthly = monthly_by_species[species]
        digest = monthly[0]["source_sha256"]
        external = collections.defaultdict(float)
        months = collections.defaultdict(set)
        providers = collections.defaultdict(set)
        for row in monthly:
            month = str(row["month"])
            start = int(month[:4]) - (int(month[4:]) <= 6)
            external[start, row["sector"]] += float(row["emissions_Mg"]) / 1000
            months[start, row["sector"]].add(month)
            providers[start, row["sector"]].add(row["provider"])
        sectors = {row["sector"] for row in monthly}
        for start in CORE_FY_STARTS:
            complete = 2000 <= start and start + 1 <= 2020
            for cfg in conf.AIR_ALL:
                for group, suffixes, matched, select, scope, boundary, unit in GROUPS:
                    named = sorted(s for s in sectors if any(s.endswith(x) for x in suffixes))
                    absent = [x for x in suffixes if not any(s.endswith(x) for s in sectors)]
                    estimate, activity = _pakemis_mass(atoms, start, cfg, species, select)
                    other = None
                    if complete and named:
                        for sector in named:
                            if len(months[start, sector]) != 12:
                                raise ValueError("incomplete HTAP monthly source coverage for FY%d %s %s"
                                                 % (start, species, sector))
                        other = sum(external[start, sector] for sector in named)
                    if not complete:
                        status = "no_complete_external_fiscal_period"
                    elif not named:
                        # HTAP publishes no row for this species and sector: an absence, not a zero
                        status = ("coverage_difference_comparator_absent" if estimate is not None
                                  else "neither_side_estimates")
                    elif not matched:
                        status = "boundary_difference_context_only"
                    elif estimate is None and other:
                        status = "coverage_difference_pakemis_not_estimated"
                    elif estimate is not None and not other:
                        status = "coverage_difference_comparator_zero_or_absent"
                    elif estimate is None:
                        status = "neither_side_estimates"
                    else:
                        status = "process_comparison"
                    ratio = estimate / other if status == "process_comparison" else None
                    act_value, implied, equivalent, factor_unit = "", "", "", ""
                    if status == "process_comparison" and unit:
                        totals = collections.defaultdict(float)
                        for (_cls, _process, aunit), value in activity.items():
                            if aunit == unit and value not in ("", None):
                                totals[aunit] += float(value)
                        if totals.get(unit):
                            act_value = totals[unit]
                            # Gg per kt fuel x 1e3 is g/kg; Gg per t dry residue x 1e6 is g/kg
                            per = 1e3 if unit == "kt_fuel" else 1e6
                            implied = estimate / act_value * per
                            equivalent = other / act_value * per
                            factor_unit = "g pollutant per kg %s" % ("fuel" if unit == "kt_fuel" else "dry residue burned")
                    if status == "process_comparison":
                        decomposition = ("activity x factor product, not separable: HTAP publishes no Pakistan activity "
                                         "beside these masses; the equivalent factor is what HTAP's mass would imply on "
                                         "PakEmis's own activity, so it folds any activity difference into the factor")
                    elif status == "boundary_difference_context_only":
                        decomposition = "coverage/boundary: see boundary_note; no factor or activity attribution is attempted"
                    elif status.startswith("coverage_difference") or status == "neither_side_estimates":
                        decomposition = "coverage: one side has no estimate for this species and process"
                    else:
                        decomposition = ""
                    rows.append(dict(
                        period_id="FY%d-%02d" % (start, (start + 1) % 100), configuration_id=cfg,
                        pollutant=species, comparison_group=group,
                        pakemis_Gg="" if estimate is None else estimate,
                        htap_Gg="" if other is None else other,
                        ratio_pakemis_over_htap="" if ratio is None else ratio,
                        comparison_status=status, htap_sectors=";".join(named),
                        htap_providers=";".join(sorted(set().union(*(providers[start, s] for s in named))))
                        if complete else "",
                        pakemis_scope=scope,
                        boundary_note=boundary + ("; HTAP publishes no %s row for %s" % (species, ", ".join(absent))
                                                  if absent else ""),
                        decomposition=decomposition,
                        pakemis_activity=act_value, pakemis_activity_unit=unit if act_value != "" else "",
                        pakemis_implied_factor=implied, htap_equivalent_factor_at_pakemis_activity=equivalent,
                        factor_unit=factor_unit,
                        time_basis=("exact July-June sum of twelve published source months" if complete else
                                    "HTAP ends December 2020; no partial or extrapolated fiscal counterpart"),
                        shared_input_note=SHARED, units=UNITS, source_sha256=digest))
    return rows


def write(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extract-only", action="store_true")
    args = parser.parse_args()
    annual, monthly = extract()
    matches = None if args.extract_only else comparison(monthly, read_rows(PANEL))
    write(ANNUAL, ANNUAL_FIELDS, annual)
    write(MONTHLY, MONTHLY_FIELDS, monthly)
    if matches is not None:
        write(COMPARISON, COMPARE_FIELDS, matches)
        by_species = {"NH3": monthly}
        for species in SPECIES:
            if species != "NH3":
                by_species[species] = species_monthly(species)
        species_rows = species_comparison(by_species, read_rows(ATOMS))
        write(SPECIES_COMPARISON, SPECIES_FIELDS, species_rows)
        print("HTAP species comparison: %d rows, %d process ratios"
              % (len(species_rows), sum(1 for r in species_rows if r["ratio_pakemis_over_htap"] != "")))
    print("HTAP original-source controls: %d annual and %d monthly PAK records; maximum residual %.9g Mg" %
          (len(annual), len(monthly), max(abs(r["control_residual_Mg"]) for r in annual)))


if __name__ == "__main__":
    main()
