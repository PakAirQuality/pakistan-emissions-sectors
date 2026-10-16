"""Current release quantities for maintained agriculture, power and household notes."""
import collections
import os

from pkinv.assets import asset_path
from pkinv.core import configurations as conf
from pkinv.core.io import read_rows, write_table
from pkinv.paths import ROOT, OUTPUTS
from pkinv.report.air_annual import ROLLUP_OUT

OUT = asset_path(OUTPUTS, "pakemis_sector_note_facts.csv")
SECTORS = ("agriculture", "power", "residential")
PERIODS = (("FY2023-24", "Ref"), ("FY2024-25", "Latest"))
SPECIES = (("PM2.5", "PMfine", r"PM$_{2.5}$"), ("BC", "BC", "BC"),
           ("NOx", "NOx", r"NO$_x$"), ("SO2", "SOtwo", r"SO$_2$"),
           ("CO", "CO", "CO"), ("NMVOC", "NMVOC", "NMVOC"), ("NH3", "NHthree", r"NH$_3$"))


def main():
    gas, categories, air, records = collections.defaultdict(float), collections.defaultdict(float), collections.defaultdict(float), []
    for r in read_rows(asset_path(OUTPUTS, "pakemis_atomic_annual.csv")):
        if r["configuration_id"] == conf.REFERENCE and r["sector_id"] in SECTORS:
            gas[r["period_id"], r["sector_id"]] += float(r["co2e_Mt_AR5"])
            categories[r["period_id"], r["sector_id"], r["category"]] += float(r["co2e_Mt_AR5"])
    for r in read_rows(ROLLUP_OUT):
        if r["configuration_id"] == conf.REFERENCE and r["sector_id"] in SECTORS:
            air[r["period_id"], r["sector_id"], r["pollutant"]] += float(r["emissions_Gg"])
    for sector in SECTORS:
        commands, table = ["% Generated from the current ten-fiscal-year reference release; do not hand edit."], []
        for period, tag in PERIODS:
            quantity = gas[period, sector]
            if quantity <= 0:
                raise ValueError("missing source GHG reference for " + sector + period)
            commands.append(r"\newcommand{\Sector%sGHG}{%.4g}" % (tag, quantity))
            records.append(dict(sector=sector, period_id=period, configuration_id=conf.REFERENCE,
                                species="CO2e_AR5", quantity=quantity, unit="Mt_CO2e", coverage="supported_source_scope"))
            for pol, macro, label in SPECIES:
                key = period, sector, pol
                if key in air:
                    value = air[key]
                    commands.append(r"\newcommand{\Sector%s%s}{%.4g}" % (tag, macro, value))
                    records.append(dict(sector=sector, period_id=period, configuration_id=conf.REFERENCE,
                                        species=pol, quantity=value, unit="Gg", coverage="covered_sources_only"))
        for pol, _macro, label in SPECIES:
            row = [label] + ["%.4g" % air[p, sector, pol] if (p, sector, pol) in air else "NE"
                             for p, _tag in PERIODS]
            table.append(" & ".join(row) + r" \\")
        directory = os.path.join(ROOT, "papers", sector, "generated")
        os.makedirs(directory, exist_ok=True)
        with open(os.path.join(directory, "integrated_air_facts.tex"), "w") as handle:
            handle.write("\n".join(commands) + "\n")
        with open(os.path.join(directory, "integrated_air_table.tex"), "w") as handle:
            handle.write("% Native Gg; missing species are NE, not zero.\n"
                         + r"\begin{tabular}{@{}lrr@{}}\toprule" + "\n"
                         + r"Species (Gg) & FY2023--24 & FY2024--25\\\midrule" + "\n"
                         + "\n".join(table) + "\n" + r"\bottomrule\end{tabular}" + "\n")
        ghg_table = []
        for category in sorted({key[2] for key in categories if key[1] == sector}):
            row = [category.replace("&", r"\&").replace("_", r"\_")]
            for period, _tag in PERIODS:
                quantity = categories[period, sector, category]
                row.append("%.4g" % quantity)
                records.append(dict(sector=sector, period_id=period, configuration_id=conf.REFERENCE,
                                    species="category:" + category, quantity=quantity, unit="Mt_CO2e_AR5",
                                    coverage="supported_source_scope"))
            ghg_table.append(" & ".join(row) + r" \\")
        with open(os.path.join(directory, "integrated_ghg_table.tex"), "w") as handle:
            handle.write("% Source category AR5 Mt; configuration reference.\n"
                         + r"\begin{tabular}{@{}p{.46\linewidth}rr@{}}\toprule" + "\n"
                         + r"Source category (Mt CO$_2$-equivalent) & FY2023--24 & FY2024--25\\\midrule" + "\n"
                         + "\n".join(ghg_table) + "\n" + r"\bottomrule\end{tabular}" + "\n")
    write_table(OUT, ("sector", "period_id", "configuration_id", "species", "quantity", "unit", "coverage"), records)
    print("maintained sector note facts: %d source-backed quantities" % len(records))


if __name__ == "__main__":
    main()
