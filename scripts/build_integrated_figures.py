"""Publication figures and LaTeX facts from the integrated released products.

No engine is called. Each plotted number is retained beside its figure, and
partial FY2026 sources are never plotted as a common national trend endpoint.
"""
from __future__ import annotations

import argparse
import collections
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from pkinv.core import configurations as conf
from pkinv.core.io import read_rows, write_table
from pkinv.report import manuscript_style as S

import numpy as np

OUT = ROOT / "outputs"
FIGURES = ROOT / "paper_national/figures"
DATA = FIGURES / "integrated_inputs"
PREVIEWS = DATA / "previews"
FACTS = ROOT / "paper_national/versions/v3/generated/integrated_facts.tex"
CFG = conf.REFERENCE
REFERENCE = "FY2023-24"
LATEST = "FY2024-25"
CORE7 = ("PM2.5", "BC", "NOx", "SO2", "CO", "NMVOC", "NH3")
LABEL = {"CO2": "CO₂", "CH4": "CH₄", "N2O": "N₂O", "PM2.5": "PM₂.₅",
         "BC": "BC", "NOx": "NOₓ", "SO2": "SO₂", "CO": "CO", "NMVOC": "NMVOC", "NH3": "NH₃"}
SECTOR = {"agriculture": "#117733", "industry": "#AA4499", "ippu": "#CC6677",
          "power": "#332288", "residential": "#DDCC77", "transport": "#88CCEE",
          "waste": "#999933", "fugitives": "#882255", "aviation": "#44AA99", "railways": "#777777"}
SCRIPT = "scripts/build_integrated_figures.py"


def rows(name, optional=False):
    path = OUT / name
    if optional and not path.exists():
        return []
    return read_rows(path)


def reference(row):
    return conf.canonical(row.get("configuration_id", row.get("cfg", CFG))) == CFG


def products():
    ghg = [r for r in rows("pakemis_atomic_annual.csv") if reference(r) and r["gas"] in ("CO2", "CH4", "N2O")]
    air = [r for r in rows("pakemis_air_annual_fy2015_16_fy2024_25.csv") if reference(r) and r["pollutant"] in CORE7]
    if not all(any(r["period_id"] == period for r in ghg) and any(r["period_id"] == period for r in air)
               for period in (REFERENCE, LATEST)):
        raise ValueError("Both GHG and air products must contain reference and latest common-core years")
    if any(r["emission_native_mass"] == "" for r in ghg):
        raise ValueError("Native gas mass is missing; CO2e cannot substitute for native mass")
    if {r["native_unit"] for r in ghg} != {"Gg"}:
        raise ValueError("The figure conversion requires GHG native mass in Gg")
    expected_periods = {"FY%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2025)}
    for panel, field, species in ((ghg, "gas", ("CO2", "CH4", "N2O")),
                                   (air, "pollutant", CORE7)):
        if {r["period_id"] for r in panel} != expected_periods:
            raise ValueError("Figure products must share exactly the ten core fiscal years")
        for period in expected_periods:
            if {r[field] for r in panel if r["period_id"] == period} != set(species):
                raise ValueError("Missing species cannot become a zero plotted estimate")
        unknown = {r["sector_id"] for r in panel} - set(SECTOR)
        if unknown:
            raise ValueError("Unmapped calculation module in figure: " + str(unknown))
    return ghg, air


def national(ghg, air):
    values = collections.defaultdict(float)
    for row in ghg:
        values[(row["period_id"], row["gas"])] += float(row["emission_native_mass"])
        values[(row["period_id"], "AR5")] += float(row["co2e_Mt_AR5"])
        values[(row["period_id"], "AR6")] += float(row["co2e_Mt_AR6"])
    for row in air:
        values[(row["period_id"], row["pollutant"])] += float(row["emissions_Gg"])
    return values


def plotted(name, values):
    import pkinv
    values = [dict(row, configuration=CFG, release_id=pkinv.__version__) for row in values]
    write_table(DATA / (name + ".csv"), list(values[0]), values)


def save(fig, name, title):
    S.save(fig, name, str(FIGURES), str(PREVIEWS), SCRIPT, title, CFG)


def plain_log_ticks(ax, values):
    from matplotlib.ticker import FixedLocator, FuncFormatter, NullLocator
    ax.xaxis.set_major_locator(FixedLocator(values))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda value, position: format(value, "g")))
    ax.xaxis.set_minor_locator(NullLocator())


def fy_label(period_id):
    """FY2015–16: the fiscal label used throughout the article."""
    return "FY" + S.fiscal(period_id)


def mass_label(value):
    """Three significant figures, digits grouped with a thin space, never e-notation."""
    rounded = float(format(value, ".3g"))
    if rounded >= 1000:
        return format(int(round(rounded)), ",").replace(",", "\u2009")
    return format(rounded, "g")


def native_log_label(value, position):
    exponent = int(round(np.log10(value)))
    return "10" + str(exponent).translate(str.maketrans("0123456789-", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻"))


def facts(ghg, air):
    import pkinv
    values = national(ghg, air)
    macro_species = {"CO2": "COtwo", "CH4": "CHfour", "N2O": "NtwoO", "AR5": "ARfive", "AR6": "ARsix",
                     "PM2.5": "PMfine", "BC": "BC", "NOx": "NOx", "SO2": "SOtwo", "CO": "CO", "NMVOC": "NMVOC", "NH3": "NHthree"}
    output = ["% Generated from released native gas and pollutant products; do not hand edit.",
              r"\newcommand{\PakEmisRelease}{%s}" % pkinv.__version__,
              r"\newcommand{\CoreEndYear}{2025}"]
    table = []
    for period, tag in ((REFERENCE, "Ref"), (LATEST, "Latest"), ("FY2015-16", "First")):
        for species in ("CO2", "CH4", "N2O", "AR5", "AR6") + CORE7:
            amount = values[(period, species)]
            # Gg and kt are numerically identical. CO2 alone is displayed in Mt.
            display = amount / 1000 if species == "CO2" else amount
            unit = "Mt" if species in ("CO2", "AR5", "AR6") else "Gg"
            command = "Pak" + tag + macro_species[species]
            output.append(r"\newcommand{\%s}{%s}" % (command, format(display, ".4g")))
            table.append({"macro": command, "period": period, "species": species, "value": display, "unit": unit})
    for species in ("AR5",) + CORE7:
        first, last = values[("FY2015-16", species)], values[(LATEST, species)]
        change = 100 * (last / first - 1)
        command = "PakChange" + macro_species[species]
        output.append(r"\newcommand{\%s}{%.1f}" % (command, change))
        table.append({"macro": command, "period": "FY2015-16 to " + LATEST, "species": species, "value": change, "unit": "%"})
    intervals = rows("pakemis_air_conditional_uncertainty.csv", optional=True)
    for period, tag in ((REFERENCE, "Ref"), (LATEST, "Latest")):
        for row in intervals:
            if row["period_id"] != period or not reference(row) or row["sector_id"] != "national_covered" or row["dependence_case"] != "persistent_parameters":
                continue
            for suffix, key in (("Low", "P2_5_Gg"), ("Median", "P50_Gg"), ("High", "P97_5_Gg")):
                command = "Pak" + tag + macro_species[row["pollutant"]] + suffix
                output.append(r"\newcommand{\%s}{%s}" % (command, format(float(row[key]), ".4g")))
                table.append({"macro": command, "period": period, "species": row["pollutant"], "value": row[key], "unit": "Gg"})
    levels = rows("pakemis_ghg_conditional_uncertainty.csv", optional=True)
    for period, tag in ((REFERENCE, "Ref"), (LATEST, "Latest")):
        match = [r for r in levels if r["period_id"] == period and reference(r)
                 and r["species_or_metric"] == "CO2e_AR5" and r["sector_id"] == "national_covered"
                 and r["dependence_case"] == "persistent_parameters"]
        for row in match:
            for suffix, key in (("Low", "P2_5_quantity"), ("Median", "P50_quantity"), ("High", "P97_5_quantity")):
                command = "Pak" + tag + "ARfive" + suffix
                output.append(r"\newcommand{\%s}{%s}" % (command, format(float(row[key]), ".4g")))
                table.append({"macro": command, "period": period, "species": "AR5", "value": row[key], "unit": "MtCO2e"})
    cases = rows("pakemis_air_structural_sensitivities.csv", optional=True)
    for row in cases:
        if not reference(row):
            continue
        scenario = row["scenario_id"]
        if row["period_id"] == REFERENCE and scenario == "all_diverted_dung_household_combustion" and row["pollutant"] in ("PM2.5", "BC"):
            command = "PakDungCase" + macro_species[row["pollutant"]]
            output.append(r"\newcommand{\%s}{%s}" % (command, format(float(row["case_covered_Gg"]), ".4g")))
            table.append({"macro": command, "period": REFERENCE, "species": row["pollutant"], "value": row["case_covered_Gg"], "unit": "Gg"})
        if (scenario == "nitrogen_all_volatilised_n_as_nh3_diagnostic" and
                row["period_id"] in (REFERENCE, LATEST) and row["pollutant"] in ("NOx", "NH3")):
            tag = "Ref" if row["period_id"] == REFERENCE else "Latest"
            command = "Pak" + tag + "NPartition" + macro_species[row["pollutant"]] + "ChangeGg"
            output.append(r"\newcommand{\%s}{%s}" % (command, format(float(row["change_Gg"]), ".4g")))
            table.append({"macro": command, "period": row["period_id"], "species": row["pollutant"], "value": row["change_Gg"], "unit": "Gg"})
    for row in rows("pakemis_nitrogen_partition_sensitivity.csv", optional=True):
        if not reference(row) or row["period_id"] not in (REFERENCE, LATEST) or row["metric"] not in ("CO2e_AR5", "CO2e_AR6"):
            continue
        tag = "Ref" if row["period_id"] == REFERENCE else "Latest"
        metric = "GHGChange" if row["metric"] == "CO2e_AR5" else "ARsixChange"
        command = "Pak" + tag + "NPartition" + metric
        output.append(r"\newcommand{\%s}{%s}" % (command, format(float(row["change_quantity"]), ".4g")))
        table.append({"macro": command, "period": row["period_id"], "species": row["metric"], "value": row["change_quantity"], "unit": row["unit"]})
    # rc69: the latest-year coal change split into source vintage, supply balance, allocation
    # seam and consumer split (pakemis_coal_change_decomposition.csv), for the trend text
    for row in rows("pakemis_coal_change_decomposition.csv", optional=True):
        if row["period_id"] != LATEST or row["species"] not in ("SO2", "PM2.5"):
            continue
        for suffix, key in (("ChangeGg", "d_coal_emissions"), ("VintageGg", "d_source_vintage"),
                            ("SupplyGg", "d_supply_balance"), ("SeamGg", "d_allocation_seam"),
                            ("SplitGg", "d_consumer_split"), ("AllocationGg", "allocation_effect"),
                            ("WithoutAllocationGg", "national_change_without_allocation")):
            command = "PakLatestCoal" + macro_species[row["species"]] + suffix
            output.append(r"\newcommand{\%s}{%s}" % (command, format(float(row[key]), ".3g")))
            table.append({"macro": command, "period": LATEST, "species": row["species"],
                          "value": row[key], "unit": "Gg"})
    aliases = {"GHGReferenceTotal": "PakRefARfive", "GHGLatestTotal": "PakLatestARfive",
               "GHGReferenceLow": "PakRefARfiveLow", "GHGReferenceHigh": "PakRefARfiveHigh",
               "GHGLatestLow": "PakLatestARfiveLow", "GHGLatestHigh": "PakLatestARfiveHigh"}
    for suffix in ("NOxChangeGg", "NHthreeChangeGg", "GHGChange", "ARsixChange"):
        aliases["PakNPartition" + suffix] = "PakRefNPartition" + suffix
    for period_tag, tag in (("Reference", "Ref"), ("Latest", "Latest")):
        for pol, short in (("PM2.5", "PM"), ("BC", "BC"), ("NOx", "NOx"), ("SO2", "SOtwo"),
                           ("CO", "CO"), ("NMVOC", "NMVOC"), ("NH3", "NHthree")):
            aliases["Air" + period_tag + short] = "Pak" + tag + macro_species[pol]
    available = {r["macro"] for r in table}
    for name, target in aliases.items():
        if target in available:
            output.append(r"\newcommand{\%s}{\%s}" % (name, target))
    FACTS.parent.mkdir(parents=True, exist_ok=True)
    FACTS.write_text("\n".join(output) + "\n")
    plotted("integrated_facts", table)


COVERAGE_TABLE = ROOT / "paper_national/versions/v3/generated/tab_integrated_coverage.tex"
MODULE_LABEL = {"power": "Public power", "industry": "Industrial combustion", "ippu": "Industrial processes",
                "transport": "Road and off-road transport", "railways": "Railways", "aviation": "Domestic aviation",
                "residential": "Households", "agriculture": "Agriculture", "waste": "Waste",
                "fugitives": "Oil and gas fugitives"}


def coverage_table(ghg):
    """Module x species coverage in the reference year, read from the released products.

    GHG cells are E where the module carries a non-zero native estimate for that gas.
    Air cells copy the state of pakemis_air_coverage_matrix.csv; an absence whose only
    estimate is a screening case is printed S. No number is printed, so nothing here can
    drift from a product without the product itself changing.
    """
    matrix = [r for r in rows("pakemis_air_coverage_matrix.csv") if r["period_id"] == REFERENCE]
    air_state = {}
    for r in matrix:
        state = r["state"]
        # A species the screening set does not price is plainly not estimated.
        if state != "E" and "screening" in r["state_basis"] and "not in the" not in r["note"]:
            state = "S"
        air_state[(r["sector_id"], r["pollutant"])] = state
    gas_state = collections.defaultdict(float)
    for r in ghg:
        if r["period_id"] == REFERENCE:
            gas_state[(r["sector_id"], r["gas"])] += abs(float(r["emission_native_mass"]))
    gases = ("CO2", "CH4", "N2O")
    head = " & ".join(["Module"] + [LABEL[g].replace("₂", "$_2$").replace("₄", "$_4$")
                                       for g in gases]
                      + [{"PM2.5": "PM$_{2.5}$", "NOx": "NO$_x$", "SO2": "SO$_2$",
                          "NH3": "NH$_3$"}.get(p, p) for p in CORE7])
    lines = ["%% GENERATED by scripts/build_integrated_figures.py from pakemis_atomic_annual.csv",
             "%% and pakemis_air_coverage_matrix.csv (%s, %s). Do not edit." % (REFERENCE, CFG),
             r"\begin{table*}[t]",
             r"\caption{Coverage by calculation module and species in FY2023--24. E: estimated; "
             r"S: unestimated in the central product, with separate screening cases; NE: not estimated; "
             r"--: not applicable or no source of the species in the module. Power SO$_2$ covers oil and diesel only. "
             r"The release gives the same matrix for every year with the reason for each absence.}",
             r"\label{tab:species_coverage}",
             r"\small",
             r"\begin{tabular*}{\textwidth}{@{\extracolsep{\fill}}l" + "c" * (len(gases) + len(CORE7)) + "@{}}",
             r"\tophline",
             head + r" \\",
             r"\middlehline"]
    for sector in SECTOR:
        cells = ["E" if gas_state.get((sector, g), 0) > 0 else "--" for g in gases]
        cells += [air_state.get((sector, p), "--") for p in CORE7]
        lines.append(" & ".join([MODULE_LABEL[sector]] + cells) + r" \\")
    lines += [r"\bottomhline", r"\end{tabular*}", r"\end{table*}"]
    COVERAGE_TABLE.write_text("\n".join(lines) + "\n")


def composition(ghg, air):
    plt = S.use()
    species = ("CO2", "CH4", "N2O") + CORE7
    mass = collections.defaultdict(float)
    for row in ghg:
        if row["period_id"] == REFERENCE:
            mass[(row["gas"], row["sector_id"])] += float(row["emission_native_mass"])
    for row in air:
        if row["period_id"] == REFERENCE:
            mass[(row["pollutant"], row["sector_id"])] += float(row["emissions_Gg"])
    admitted = set(mass)
    totals = {pol: sum(v for (p, _), v in mass.items() if p == pol) for pol in species}
    fig = S.figure(S.FULL_WIDTH, 4.5)
    left = fig.add_axes([.10, .21, .53, .70])
    right = fig.add_axes([.70, .21, .27, .70])
    y = np.arange(len(species))
    offset = np.zeros(len(species))
    records = []
    for sector, colour in SECTOR.items():
        quantities = np.array([mass[(pol, sector)] for pol in species])
        shares = quantities / np.array([totals[p] for p in species]) * 100
        left.barh(y, shares, left=offset, color=colour, height=.7,
                  label="IPPU" if sector == "ippu" else sector.capitalize(), linewidth=0)
        offset += shares
        for pol, amount, share in zip(species, quantities, shares):
            records.append({"period": REFERENCE, "species": pol, "module": sector,
                            "native_Gg": amount if (pol, sector) in admitted else "",
                            "share_pct": share if (pol, sector) in admitted else "",
                            "total_Gg": totals[pol],
                            "coverage_status": "admitted_estimate" if (pol, sector) in admitted else "no_admitted_estimate"})
    left.set_yticks(y, [LABEL[p] for p in species])
    left.invert_yaxis()
    left.set_xlim(0, 100)
    left.set_xticks([0, 25, 50, 75, 100])
    left.set_xlabel("Contribution to each species (%)")
    S.panel(left, "a", "Shares by source module")
    right.barh(y, [totals[p] for p in species], color=S.ACCENT, height=.65)
    right.set_xscale("log")
    right.set_yticks(y, [])
    right.invert_yaxis()
    right.set_xlabel("Native mass (Gg; log scale)")
    S.panel(right, "b", "Covered mass")
    for index, pol in enumerate(species):
        right.text(totals[pol] * 1.07, index, mass_label(totals[pol]), va="center", fontsize=S.SIZE_FLOOR)
    right.set_xlim(min(totals.values()) * .5, max(totals.values()) * 15)
    plain_log_ticks(right, (100, 1000, 10000, 100000))
    from matplotlib.ticker import FuncFormatter
    right.xaxis.set_major_formatter(FuncFormatter(native_log_label))
    S.quiet(left, grid="x")
    S.quiet(right)
    handles, names = left.get_legend_handles_labels()
    fig.legend(handles, names, loc="lower center", bbox_to_anchor=(.52, .01), ncol=5,
               columnspacing=1.1, handletextpad=.4)
    plotted("f09_integrated_composition", records)
    save(fig, "f09_integrated_composition", "GHG and air-pollutant composition and native masses")


def trends(ghg, air):
    plt = S.use()
    values = national(ghg, air)
    periods = sorted({p for p, _ in values})
    variables = ("AR5", "PM2.5", "NOx", "SO2", "NH3", "BC")
    air_intervals = rows("pakemis_air_conditional_uncertainty.csv")
    ghg_intervals = rows("pakemis_ghg_conditional_uncertainty.csv")
    fig = S.figure(S.FULL_WIDTH, 4.7)
    axes = fig.subplots(2, 3)
    fig.subplots_adjust(left=.10, right=.98, bottom=.16, top=.93, wspace=.42, hspace=.55)
    records = []
    for ax, pol, letter in zip(axes.ravel(), variables, "abcdef"):
        x = np.arange(len(periods))
        y = np.array([values[(p, pol)] for p in periods])
        indexed = {}
        if pol == "AR5":
            indexed = {r["period_id"]: (float(r["P2_5_quantity"]), float(r["P97_5_quantity"]))
                       for r in ghg_intervals if reference(r) and r["species_or_metric"] == "CO2e_AR5"
                       and r["sector_id"] == "national_covered" and r["dependence_case"] == "persistent_parameters"}
        else:
            indexed = {r["period_id"]: (float(r["P2_5_Gg"]), float(r["P97_5_Gg"]))
                       for r in air_intervals if reference(r) and r["sector_id"] == "national_covered"
                       and r["dependence_case"] == "persistent_parameters" and r["pollutant"] == pol}
        if set(periods) - set(indexed):
            raise ValueError("Missing conditional interval for %s" % pol)
        low, high = np.array([indexed[p] for p in periods]).T
        ax.fill_between(x, low, high, color=S.FILL, edgecolor="none", label="Conditional 95% interval")
        ax.plot(x, y, color=S.ACCENT, marker="D", markersize=3, label="Deterministic estimate")
        ax.set_xticks([0, 4, len(periods) - 1], [fy_label(periods[i]) for i in [0, 4, len(periods) - 1]], rotation=25, ha="right")
        ax.set_ylabel("Mt CO₂e (AR5)" if pol == "AR5" else "Native mass (Gg)")
        S.panel(ax, letter, "GHG aggregate" if pol == "AR5" else LABEL[pol])
        S.quiet(ax, grid="y")
        ax.set_ylim(bottom=0)
        for period, estimate, a, b in zip(periods, y, low, high):
            records.append({"period": period, "species": pol, "deterministic": estimate,
                            "P2_5": a, "P97_5": b, "unit": "MtCO2e_AR5" if pol == "AR5" else "Gg",
                            "configuration": CFG, "interval_kind": "conditional_parameter_percentiles"})
    handles, names = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, names, loc="lower center", bbox_to_anchor=(.5, .005), ncol=2)
    plotted("f10_integrated_trends", records)
    save(fig, "f10_integrated_trends", "Common-scope fiscal trends and conditional parameter intervals")


def maps(ghg, air):
    import netCDF4
    from matplotlib.colors import LogNorm
    from matplotlib.ticker import FuncFormatter
    plt = S.use()
    ghg_path = OUT / "pakemis_grid_0p05_annual_ref_fy2015_16_fy2024_25.nc"
    air_path = OUT / "pakemis_air_grid_0p05_annual_s_tan_fy2015_16_fy2024_25.nc"
    fig = S.figure(S.FULL_WIDTH, 5.55)
    axes = fig.subplots(2, 3)
    fig.subplots_adjust(left=.07, right=.98, bottom=.08, top=.94, wspace=.40, hspace=.42)
    records = []
    summaries = []
    national_tonnes = collections.defaultdict(float)
    for row in ghg:
        if row["period_id"] == REFERENCE:
            national_tonnes[row["gas"]] += float(row["emission_native_mass"]) * 1000
    for row in air:
        if row["period_id"] == REFERENCE:
            national_tonnes[row["pollutant"]] += float(row["emissions_Gg"]) * 1000
    with netCDF4.Dataset(ghg_path) as ghg, netCDF4.Dataset(air_path) as air:
        for index, (ax, pol, variable) in enumerate(zip(axes.ravel(),
                ("CO2", "CH4", "N2O", "PM2.5", "NOx", "NH3"),
                ("co2_emissions", "ch4_emissions", "n2o_emissions", "pm25_emissions", "nox_emissions", "nh3_emissions"))):
            ds = ghg if index < 3 else air
            periods = list(ds.variables["period_id"][:])
            t = periods.index(REFERENCE)
            fraction = np.asarray(ds.variables["pakistan_fraction"][:])
            lon, lat = np.asarray(ds.variables["lon"][:]), np.asarray(ds.variables["lat"][:])
            view_mass = {"physical": "", "origin": "", "accounting": ""}
            if index < 3:
                views = list(ds.variables["spatial_view"][:])
                layers = np.ma.asarray(ds.variables[variable][t, :, :, :], dtype="float64") * 1000
                # The views are disjoint emitting-source partitions, not complete
                # alternatives. Sum for the all-placed map and retain each account.
                values = np.ma.sum(layers, axis=0)
                view_mass = {view: float(np.ma.masked_where(fraction <= 0, layers[i]).sum())
                             for i, view in enumerate(views)}
            else:
                values = np.ma.asarray(ds.variables[variable][t, :, :], dtype="float64") * 1000
            # Everything on the grid, before the display mask: the remainder of the
            # national total is the unallocated account.
            gridded = float(np.ma.sum(values))
            values = np.ma.masked_where((fraction <= 0) | (values <= 0), values)
            valid = values.compressed()
            if not len(valid):
                raise ValueError("Map contains no placed positive mass for " + pol)
            low = max(np.percentile(valid, 1), np.max(valid) / 1e7)
            high = np.max(valid)
            cmap = "cividis_r" if index < 3 else "magma_r"
            artist = ax.pcolormesh(lon, lat, values, cmap=cmap, norm=LogNorm(low, high),
                                   rasterized=True, shading="nearest")
            colourbar = fig.colorbar(artist, ax=ax, orientation="horizontal", fraction=.045, pad=.10, aspect=22,
                                    extend="min", format=FuncFormatter(native_log_label))
            colourbar.minorticks_off()
            colourbar.set_label("t cell⁻¹ yr⁻¹", fontsize=S.SIZE_FLOOR, labelpad=1)
            colourbar.ax.tick_params(labelsize=S.SIZE_FLOOR)
            ax.set_xlim(60.5, 77.5)
            ax.set_ylim(23.3, 37.4)
            ax.set_aspect(1 / np.cos(np.deg2rad(30)))
            ax.set_xticks([62, 69, 76], ["62°E", "69°E", "76°E"])
            ax.set_yticks([25, 30, 35], ["25°N", "30°N", "35°N"])
            S.panel(ax, "abcdef"[index], LABEL[pol])
            S.quiet(ax, keep=())
            unallocated = max(0.0, 100 * (1 - gridded / national_tonnes[pol]))
            ax.text(1.0, 1.0, ("unallocated %.2g%%" % unallocated) if unallocated >= 0.01 else "unallocated <0.01%",
                    transform=ax.transAxes, ha="right", va="bottom", fontsize=S.SIZE_FLOOR, color=S.MUTED)
            summaries.append({"period": REFERENCE, "species": pol, "placed_tonnes": float(valid.sum()),
                              "national_tonnes": national_tonnes[pol], "unallocated_pct_of_national": unallocated,
                              "physical_tonnes": view_mass["physical"], "origin_tonnes": view_mass["origin"],
                              "accounting_tonnes": view_mass["accounting"],
                              "colour_min_t_cell": low, "colour_max_t_cell": high,
                              "source": str(Path(ds.filepath()).relative_to(ROOT)), "interpretation": "Allocated annual mass; independent logarithmic scale; not flux density"})
            yy, xx = np.where(~np.ma.getmaskarray(values))
            for y, x in zip(yy, xx):
                records.append({"period": REFERENCE, "species": pol, "lat": lat[y], "lon": lon[x],
                                "tonnes_per_cell": float(values[y, x])})
    plotted("f11_integrated_maps", records)
    plotted("f11_integrated_map_scales", summaries)
    save(fig, "f11_integrated_maps", "Allocated native GHG and pollutant masses on independent scales")


SENSITIVITY_FAMILIES = (
    # (label, scenario-id prefixes, sector whose colour it takes, marker). The colour is the
    # module the case perturbs, as in Fig. 9; the marker separates cases within a module.
    ("All diverted dung burned in households (L)", ("all_diverted_dung_household_combustion",), "residential", "o"),
    ("Dated kiln-fleet coal cases (4)", ("coal_allocation:",), "industry", "o"),
    ("Industrial fuel sulfur, low and high", ("industrial_fuel_sulfur_",), "industry", "s"),
    ("Transferred road factors, low and high", ("road_transferred_factor_",), "transport", "o"),
    ("Waste burned fraction 0.3 and 0.9", ("waste_burned_fraction_",), "waste", "o"),
    ("Regional fertiliser NH₃ factor", ("fertiliser_urea_regional_factor",), "agriculture", "s"),
    ("Nitrogen attribution diagnostic (all NH₃)", ("nitrogen_all_volatilised_n_as_nh3_diagnostic",), "agriculture", "^"),
)


def sensitivity():
    plt = S.use()
    intervals = [r for r in rows("pakemis_air_conditional_uncertainty.csv")
                 if reference(r) and r["period_id"] == REFERENCE and r["sector_id"] == "national_covered"
                 and r["dependence_case"] == "persistent_parameters"]
    cases = [r for r in rows("pakemis_air_structural_sensitivities.csv")
             if reference(r) and r["period_id"] == REFERENCE]
    variables = ("PM2.5", "BC", "NOx", "SO2", "NH3")
    fig = S.figure(S.FULL_WIDTH, 3.9)
    axes = fig.subplots(1, 2)
    fig.subplots_adjust(left=.08, right=.98, bottom=.31, top=.91, wspace=.18)
    records = []
    for y, pol in enumerate(variables):
        row = next(r for r in intervals if r["pollutant"] == pol)
        centre = float(row["deterministic_Gg"])
        lo, hi = float(row["P2_5_Gg"]) / centre, float(row["P97_5_Gg"]) / centre
        S.interval(axes[0], lo, hi, y)
        S.deterministic(axes[0], 1, y)
        records.append({"species": pol, "kind": "conditional_parameter_interval", "case": "persistent_parameters",
                        "ratio": 1, "low_ratio": lo, "high_ratio": hi})
    seen = {r["scenario_id"] for r in cases}
    for _label, keys, _sector, _marker in SENSITIVITY_FAMILIES:
        if not any(s == k or s.startswith(k) for s in seen for k in keys):
            raise ValueError("Missing structural sensitivity family %s" % (keys,))
    n = len(SENSITIVITY_FAMILIES)
    step = .78 / (n - 1)
    for i, (label, keys, sector, marker) in enumerate(SENSITIVITY_FAMILIES):
        colour = SECTOR[sector]
        family = [r for r in cases if any(r["scenario_id"] == k or r["scenario_id"].startswith(k) for k in keys)
                  and r["pollutant"] in variables]
        for pol in variables:
            ratios = []
            for row in (r for r in family if r["pollutant"] == pol):
                ratio = float(row["case_covered_Gg"]) / float(row["reference_covered_Gg"])
                kind = ("attribution_diagnostic_no_probability" if row["scenario_id"].endswith("_diagnostic")
                        else "structural_case_no_probability")
                records.append({"species": pol, "kind": kind, "case": row["scenario_id"],
                                "ratio": ratio, "low_ratio": "", "high_ratio": ""})
                # A case that leaves this pollutant unchanged is recorded but not drawn.
                if abs(ratio - 1) > 5e-4:
                    ratios.append(ratio)
            if not ratios:
                continue
            y = variables.index(pol) - .39 + i * step
            if len(ratios) > 1:
                axes[1].plot([min(ratios), max(ratios)], [y, y], color=colour, lw=1.0, zorder=3)
            for ratio in ratios:
                axes[1].plot([ratio], [y], marker=marker, markersize=4.2, markerfacecolor=S.PAPER,
                             markeredgecolor=colour, markeredgewidth=1.3, linestyle="none", zorder=5)
        axes[1].plot([], [], marker=marker, markerfacecolor="white", markeredgecolor=colour,
                     markeredgewidth=1.3, color=colour, lw=1.0, label=label)
    for ax in axes:
        ax.axvline(1, color=S.RULE, lw=.7)
        ax.set_yticks(range(len(variables)), [LABEL[p] for p in variables])
        ax.set_ylim(len(variables) - .45, -.55)
        ax.set_xscale("log")
        ax.set_xlim(.45, 5)
        plain_log_ticks(ax, (.5, 1, 2, 4))
        ax.set_xlabel("Ratio to reference estimate (log scale)")
        S.quiet(ax, grid="x")
    axes[1].set_yticklabels([])
    S.panel(axes[0], "a", "Conditional 95% parameter intervals")
    S.panel(axes[1], "b", "Structural cases (no probability)")
    handles, names = axes[1].get_legend_handles_labels()
    fig.legend(handles, names, loc="lower center", bbox_to_anchor=(.53, .0), ncol=2,
               fontsize=S.SIZE_FLOOR, columnspacing=1.4, handletextpad=.5)
    plotted("f12_air_sensitivity", records)
    save(fig, "f12_air_sensitivity", "Air-pollutant parameter intervals and separate structural cases")


def evaluation():
    plt = S.use()
    industry = rows("pakemis_industry_air_edgar_comparison.csv")
    # The comparison publication itself supplies a fiscal blend of the two
    # corresponding calendar years. Keep the fossil+biomass boundary explicit.
    comparable = [r for r in industry if r["species"] in CORE7 and r["engine_industry_kt"]
                  and r["edgar_1a2_fossil_kt"] and r["edgar_1a2_fossil_bio_kt"]
                  and r["edgar_1a2_fossil_plus_2a1_kt"]]
    comparison_period = max(r["period_id"] for r in comparable)
    chosen = sorted((r for r in comparable if r["period_id"] == comparison_period),
                    key=lambda r: CORE7.index(r["species"]))
    if not chosen:
        raise ValueError("No complete matched EDGAR fiscal comparison")
    # HTAP v3.2 on matched process boundaries, every species the product compares,
    # FY2015-16 to FY2019-20 (exact July-June sums of published months).
    htap_rows = [("road_exhaust", p) for p in ("NOx", "CO", "NMVOC", "SO2", "PM2.5", "BC", "NH3")]
    htap_rows += [("agriculture_livestock_and_soils", "NH3"), ("agriculture_livestock_and_soils", "NOx"),
                  ("agricultural_residue_burning", "PM2.5"), ("agricultural_residue_burning", "CO")]
    group_label = {"road_exhaust": "Road exhaust", "agriculture_livestock_and_soils": "Livestock and soils",
                   "agricultural_residue_burning": "Residue burning"}
    group_sector = {"road_exhaust": "transport", "agriculture_livestock_and_soils": "agriculture",
                    "agricultural_residue_burning": "agriculture"}
    htap = [r for r in rows("pakemis_air_htap_species_comparison.csv") if reference(r)
            and r["comparison_status"] == "process_comparison"
            and (r["comparison_group"], r["pollutant"]) in htap_rows and r["ratio_pakemis_over_htap"]]
    for key in htap_rows:
        if len([r for r in htap if (r["comparison_group"], r["pollutant"]) == key]) != 5:
            raise ValueError("Expected five matched HTAP fiscal years for %s" % (key,))
    fig = S.figure(S.FULL_WIDTH, 4.2)
    ax = fig.add_axes([.09, .28, .33, .62])
    right = fig.add_axes([.66, .28, .32, .62])
    records = []
    labels = []
    for index, row in enumerate(chosen):
        pak = float(row["engine_industry_kt"])
        fossil = float(row["edgar_1a2_fossil_plus_2a1_kt"])
        cement_process = fossil - float(row["edgar_1a2_fossil_kt"])
        all_fuel = float(row["edgar_1a2_fossil_bio_kt"]) + cement_process
        if not all_fuel or not fossil:
            continue
        ax.plot([pak / fossil, pak / all_fuel], [index, index], color=S.RULE, lw=2)
        ax.plot(pak / fossil, index, "o", color=S.NEUTRAL)
        ax.plot(pak / all_fuel, index, "s", color=S.ACCENT)
        labels.append((index, LABEL[row["species"]]))
        for basis, external in (("EDGAR fossil 1.A.2 + cement process 2.A.1", fossil),
                                ("EDGAR fossil+biomass 1.A.2 + cement process 2.A.1", all_fuel)):
            records.append({"period": comparison_period, "species": row["species"], "sector": "industry",
                            "pakemis_Gg": pak, "comparator_Gg": external, "comparator": basis,
                            "ratio_pakemis_over_comparator": pak / external,
                            "time_basis": row["edgar_basis"], "scope": "Industrial combustion plus integrated cement process; other IPPU separate"})
    ax.axvline(1, color=S.RULE, lw=.8)
    ax.set_xscale("log")
    plain_log_ticks(ax, (.1, 1, 10))
    ax.set_yticks([i for i, _ in labels], [s for _, s in labels])
    ax.invert_yaxis()
    ax.set_xlabel("PakEmis / EDGAR (log scale)")
    ax.plot([], [], "o", color=S.NEUTRAL, label="Fossil fuels + cement process")
    ax.plot([], [], "s", color=S.ACCENT, label="Fossil + biomass + cement process")
    ax.legend(loc="upper center", bbox_to_anchor=(.5, -.29), ncol=1, fontsize=S.SIZE_FLOOR)
    S.panel(ax, "a", "Industry, " + fy_label(comparison_period))
    S.quiet(ax, grid="x")
    marker = {"FY2015-16": "o", "FY2016-17": "o", "FY2017-18": "o", "FY2018-19": "o", "FY2019-20": "o"}
    for y, key in enumerate(htap_rows):
        own = sorted((r for r in htap if (r["comparison_group"], r["pollutant"]) == key), key=lambda r: r["period_id"])
        ratios = [float(r["ratio_pakemis_over_htap"]) for r in own]
        colour = SECTOR[group_sector[key[0]]]
        right.plot([min(ratios), max(ratios)], [y, y], color=colour, lw=1.6, alpha=.55, solid_capstyle="butt")
        right.plot(ratios, [y] * len(ratios), "o", markersize=3.2, color=colour,
                   markeredgecolor=S.MUTED, markeredgewidth=.4)
        for row in own:
            records.append({"period": row["period_id"], "species": row["pollutant"], "sector": row["comparison_group"],
                            "pakemis_Gg": row["pakemis_Gg"], "comparator_Gg": row["htap_Gg"],
                            "comparator": "HTAPv3.2", "ratio_pakemis_over_comparator": row["ratio_pakemis_over_htap"],
                            "time_basis": row["time_basis"], "scope": row["boundary_note"]})
    right.axvline(1, color=S.RULE, lw=.8)
    right.set_xscale("log")
    right.set_xlim(.1, 8)
    plain_log_ticks(right, (.1, .3, 1, 3))
    right.set_yticks(range(len(htap_rows)),
                     ["%s %s" % (group_label[g], LABEL[p]) for g, p in htap_rows], fontsize=S.SIZE_FLOOR)
    right.invert_yaxis()
    right.set_xlabel("PakEmis / HTAP (log scale)")
    right.plot([], [], color=SECTOR["transport"], lw=1.6, label="Road transport")
    right.plot([], [], color=SECTOR["agriculture"], lw=1.6, label="Agriculture")
    right.legend(loc="upper center", bbox_to_anchor=(.5, -.20), ncol=2, fontsize=S.SIZE_FLOOR)
    S.panel(right, "b", "HTAP v3.2 by process")
    S.quiet(right, grid="x")
    plotted("f13_air_evaluation", records)
    save(fig, "f13_air_evaluation", "Matched air-pollutant comparisons with EDGAR and HTAP")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts-only", action="store_true")
    parser.add_argument("--skip-maps", action="store_true")
    args = parser.parse_args(argv)
    DATA.mkdir(parents=True, exist_ok=True)
    ghg, air = products()
    facts(ghg, air)
    coverage_table(ghg)
    if args.facts_only:
        return 0
    composition(ghg, air)
    trends(ghg, air)
    sensitivity()
    evaluation()
    if not args.skip_maps:
        maps(ghg, air)
    print("Integrated figures and facts generated from %s common-core products" % CFG)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
