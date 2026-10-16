"""Write the README's numeric blocks from the engine outputs.

WHY. The README carried its own vintage of the inventory: a total of 454.48 Mt against a
current 455.14, a residential figure three megatonnes stale, a road-transport row that
still showed the pre-re-anchor split, completeness counts from a 63-row registry that now
has 81 rows - and a sector table whose rows summed to 448.80 against its own printed
total. Nothing checked any of it, because no test read the README at all.

Hand-updating those numbers would have fixed today's copy and left tomorrow's to drift the
same way. So the numeric blocks are generated between markers and CI diffs the result: the
prose around them stays hand-written, and the figures inside them cannot be wrong without
the build failing.

Usage:  python3 scripts/make_readme_tables.py [--check]
"""

from pkinv.assets import asset_path
import csv
import os
import sys
from pkinv.core.io import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS = asset_path(ROOT, "outputs")
README = asset_path(ROOT, "README.md")
PDF_README = asset_path(ROOT, "papers", "pdf", "README.md")

BEGIN = "<!-- BEGIN GENERATED: %s -->"
END = "<!-- END GENERATED: %s -->"

# IPCC codes for the README's sector table. The engine knows sector names and totals; the
# code column is presentational, so it lives here rather than being invented downstream.
IPCC = {
    "agriculture": "3.A-3.H", "power": "1A1a + 1A2", "transport": "1A3b + 1A4c/1A2",
    "waste": "4A, 4C2, 4D1", "residential": "1A4b", "fugitives": "1B2",
    "ippu": "2A1", "industry": "1A2", "railways": "1A3c + 1A2/1A4c",
    "aviation": "1A3a ii",
}
LABEL = {
    "agriculture": "Agriculture", "power": "Electricity + captive generation",
    "transport": "Road transport + mixed off-road", "waste": "Waste",
    "residential": "Residential fuel", "fugitives": "Oil & gas fugitives",
    "ippu": "Industrial processes", "industry": "Industrial combustion",
    "railways": "Railways", "aviation": "Domestic aviation",
}


def _rows(name):
    return read_rows(asset_path(OUTPUTS, name), comments=False)


def sector_table():
    rows = _rows("national_all_sectors.csv")
    alt = {r["sector"]: r for r in _rows("national_all_sectors_ledger.csv")}
    out = ["| Sector | IPCC | Year | Mt CO2e (AR5) | +/- % |",
           "|---|---|---|---:|---:|"]
    body = [r for r in rows if r["row_kind"] == "sector"]
    # The power row must never quote its magnitude bare: the configurations file
    # itself requires every quote of the grid figure to carry the structural
    # family beside it, and the ninth review caught this table violating that
    # rule. The three members are read from the file, never typed here.
    grid_family = {}
    for c in _rows("national_configurations.csv"):
        if c["family_id"] == "power_grid_control" and c["family_role"]:
            import re as _re
            m = _re.search(r"grid ([\d.]+)", c["family_role"])
            if m:
                grid_family[c["configuration_id"]] = m.group(1)
    family_note = ""
    if grid_family:
        family_note = (" (family power_grid_control: grid %s within the module "
                       "figure)" % " / ".join(sorted(grid_family.values(),
                                                     key=float)))
    for r in sorted(body, key=lambda r: -float(r["co2e_Mt_AR5"])):
        suffix = family_note if r["sector"] == "power" else ""
        out.append("| %s | %s | %s | %.2f | %.1f |"
                   % (LABEL.get(r["sector"], r["sector"]) + suffix,
                      IPCC.get(r["sector"], ""),
                      r["year"], float(r["co2e_Mt_AR5"]), float(r["uncert_pct_95"])))
    total = next(r for r in rows if r["row_kind"] == "national_total")
    # Not the literal "mixed" any more: the rollup says what the TOTAL row's period is, and
    # it is one period now. A hard-coded "mixed" beside a harmonised table is the same defect
    # the manuscript's year column had.
    # national_all_sectors.csv is the reference (survey dung, S) since rc67; the second
    # file is configuration L
    for label, row in (("S, the reference", total), ("L", alt["TOTAL"])):
        out.append("| **Total (configuration %s)** | | %s | **%.2f** | **%.1f** |"
                   % (label, row["year"], float(row["co2e_Mt_AR5"]),
                      float(row["uncert_pct_95"])))
    return "\n".join(out)


def headline():
    atoms = [r for r in _rows("pakemis_ghg_configuration_atoms.csv")
             if r["configuration_id"] == "S_TAN" and r["period_id"] == "FY2024-25"]
    total = sum(float(r["co2e_Mt_AR5"]) for r in atoms)
    air = [r for r in _rows("pakemis_air_annual_fy2015_16_fy2024_25.csv")
           if r["configuration_id"] == "S_TAN" and r["period_id"] == "FY2024-25"]
    mass = {p: sum(float(r["emissions_Gg"]) for r in air if r["pollutant"] == p)
            for p in ("PM2.5", "NOx", "NH3")}
    return ("A shared activity and material-flow inventory for Pakistan covering ten fiscal years, "
            "**July 2015–June 2025**. The latest covered-source estimates are **%.2f Mt CO2e "
            "(AR5)**, **%.1f Gg primary PM2.5**, **%.1f Gg NOx as NO2** and **%.1f Gg NH3**, "
            "under configuration S_TAN. Native CO2, CH4 and N2O are supplied separately from "
            "warming-potential aggregates. Other core air species are BC, SO2, CO and NMVOC. "
            "These totals exclude unestimated sources and LULUCF."
            % (total, mass["PM2.5"], mass["NOx"], mass["NH3"]))


def coverage():
    comp = _rows("completeness.csv")
    counts = {key: sum(r["notation_key"] == key for r in comp)
              for key in ("E", "NE", "IE", "NO", "NA")}
    return ("The GHG completeness register contains %d category–gas records: %d estimated, "
            "%d not estimated, %d included elsewhere, %d not occurring and %d not applicable. "
            "The separate air coverage matrix reports source/process × species × year. "
            "Missing estimates are notation statuses, not zero. Differences from EDGAR or "
            "another inventory are matched-boundary comparisons; their residuals are not "
            "automatically estimates of missing PakEmis emissions."
            % (len(comp), counts["E"], counts["NE"], counts["IE"], counts["NO"], counts["NA"]))


# The sector-paper index in papers/pdf/README.md. The ARGUMENT column is editorial and stays
# hand-written here; the sector, code and magnitude columns are read from the release, because
# that is what went stale. It carried agriculture at 221.22 and waste at 36.96 - two rounds
# behind - alongside a residential PM figure from before the configuration split and a
# railways line still advertising a diesel carve-out that has been retired.
PAPER_ARGUMENT = {
    "agriculture": "One nitrogen ledger serving two inventories, with mass-conserving "
                   "allocation to a 0.05\u00b0 grid and 114 districts plus a declared residual unit",
    "power": "Physical station fuel and rank-specific calorific values, with public/captive "
             "and K-Electric boundaries and control assumptions kept explicit",
    "transport": "Product-specific fuel balances with exhaust, evaporation and wear; "
                 "transferred fleet factors tested separately from the carbon balance",
    "waste": "Disposal history, wastewater and open burning with shared activity "
             "and separate method and treatment alternatives",
    "residential": "Survey-based household fuel and an explicit diverted-dung alternative; "
                   "gross appliance emissions, with no assumed outdoor escape fraction",
    # Filled by _fugitives_argument() at render time - the shares went stale
    # twice as literals (5.4/3.4 against the paper's 5.5/3.2).
    "fugitives": None,
    "ippu": "Physical cement, ammonia, steel and lubricant accounts; process carbon "
            "separated from fuel, and admitted air-process boundaries recorded explicitly",
    "railways": "Operator diesel and traction accounts checked against traffic; "
                "national fuel, network allocation and unplaced mass kept distinct",
    "aviation": "Domestic airport movements and modelled stage fuel, with landing/take-off, "
                "cruise and international-bunker boundaries stated separately",
}

PAPER_LABEL = {"transport": "Road + off-road", "power": "Electricity",
               "ippu": "Industrial processes", "aviation": "Domestic aviation"}


def paper_table():
    """One row per sector manuscript, ordered as the papers are built."""
    rows = {r["sector"]: r for r in _rows("national_all_sectors.csv")}
    from pkinv import release as _release
    out = ["| TN | PDF | Sector | IPCC | Mt CO\u2082e | The argument |", "|---|---|---|---|---:|---|"]
    for sector, argument in PAPER_ARGUMENT.items():
        if argument is None:
            argument = _fugitives_argument()
        row = rows.get(sector)
        if row is None:
            raise SystemExit("no %s row in national_all_sectors.csv: the sector-paper index "
                             "would print a magnitude with nothing behind it" % sector)
        out.append("| %s | `%s_paper.pdf` | %s | %s | %.2f | %s |"
                   % (_release.TECHNICAL_NOTES[sector], sector, PAPER_LABEL.get(sector, LABEL[sector]),
                      IPCC[sector].replace("+", "+"), float(row["co2e_Mt_AR5"]), argument))
    return "\n".join(out)


def _fugitives_argument():
    """The fugitives index line, with both shares read from the engine."""
    rows = {r["sector"]: r for r in _rows("national_all_sectors.csv")}
    share = float(rows["fugitives"]["share_pct"])
    var = next(float(r["variance_share_pct_independent_approx"])
               for r in _rows("national_key_categories.csv")
               if r["category"] == "Fugitive emissions from oil and natural gas")
    # COUNTED, not remembered: the thirteenth review caught this string still
    # saying 168 after the excluding-feedstock leg grew the factorial to 224.
    configurations = len(_rows("fugitives_structural_factorial_2024.csv"))
    return ("The published envelope spans 9.60-24.69 Mt across %d structural "
            "configurations; %.1f%% of emissions and %.1f%% of national "
            "Approach-1 variance" % (configurations, share, var))


def release():
    """The README's release identity, from the manifest - STABLE fields only.

    The commit hash and manifest digest are deliberately absent: README.md is
    content, not a fixpoint artifact, so embedding the volatile git block here
    would make the release fixpoint unreachable. Those two live in the release
    cover and the manifest itself."""
    import json
    with open(asset_path(OUTPUTS, "release_manifest.json"), encoding="utf-8") as f:
        m = json.load(f)
    totals = m["national_totals"]
    comp = m["completeness"]["by_notation_key"]
    n_config = sum(1 for r in _rows("national_configurations.csv"))
    n_axes = sum(1 for r in _rows("national_axis_register.csv"))
    return ("**Release** `%s` | reporting period **%s** (%s to %s) | "
            "reference FY2023–24: **%.2f Mt CO2e** (AR5, S_TAN) / **%.2f Mt** (L_TAN) | "
            "%d structural axes, %d named configurations | completeness "
            "%d E / %d NE / %d IE / %d NO | code %s; %s. ODbL-derived components are packaged separately. "
            "Commit and manifest digest: `paper_common/release_cover.tex` and "
            "`outputs/release_manifest.json`."
            % (m["version"], m["reporting_period"]["label"],
               m["reporting_period"]["start"], m["reporting_period"]["end"],
               totals[m["baseline_configuration"]["code"]]["co2e_Mt_AR5"],
               totals["L"]["co2e_Mt_AR5"],
               n_axes, n_config,
               comp.get("E", 0), comp.get("NE", 0), comp.get("IE", 0),
               comp.get("NO", 0),
               m["licences"]["code"], m["licences"]["data_and_text"]))


def movers():
    """The 'what would move it most' fugitives sentence, shares from the engine
    (they went stale twice as hand prose)."""
    rows = {r["sector"]: r for r in _rows("national_all_sectors.csv")}
    share = float(rows["fugitives"]["share_pct"])
    var = next(float(r["variance_share_pct_independent_approx"])
               for r in _rows("national_key_categories.csv")
               if r["category"] == "Fugitive emissions from oil and natural gas")
    return ("1. **Resolve gas-system practice and facility activity.** The 2019 segment "
            "inventory makes\n   fugitives %.1f%% of national emissions and %.1f%% of "
            "national Approach-1 variance. Pipeline\n   length and utility throughput "
            "are now included; material, pressure, LDAR, compressor,\n   "
            "processing-plant and well records are the binding evidence."
            % (share, var)).replace("\\n", "\n")


def products():
    """The four product families and their canonical entry points, from the catalogue.

    THE README WAS A SECTOR-PAPER INDEX. A reader arriving at the repository could find the
    nine sector reports and not the four product families the release is actually for, and the
    reviewer said so. This is the landing section, and it is generated from
    outputs/pakemis_product_catalog.csv so a product cannot ship without appearing here.
    """
    import sys
    sys.path.insert(0, asset_path(ROOT, "src"))
    from pkinv.report import product_catalog

    rows = [r for r in product_catalog.catalog() if r["release_tier"] == "core"]
    out = ["| Family | Product | Entry point | Status |", "|---|---|---|---|"]
    for family in product_catalog.FAMILY_ORDER:
        for row in [r for r in rows if r["product_family"] == family]:
            out.append("| %s | `%s` | `outputs/%s` | %s |" % (
                product_catalog.FAMILY_LABEL[family], row["product_id"],
                row["primary_artifact"], row["status"]))
    return "\n".join(out)


BLOCKS = {"headline": headline, "sectors": sector_table, "coverage": coverage,
          "release": release, "movers": movers, "products": products}
PDF_BLOCKS = {"papers": paper_table}


def render(text, blocks=None):
    """Replace the content of every generated block, leaving the prose untouched."""
    for name, fn in (blocks or BLOCKS).items():
        begin, end = BEGIN % name, END % name
        if begin not in text or end not in text:
            raise SystemExit("README is missing the %r generated block markers" % name)
        head = text[:text.index(begin) + len(begin)]
        tail = text[text.index(end):]
        text = head + "\n" + fn() + "\n" + tail
    return text


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    stale, written = [], []
    for path, blocks in ((README, BLOCKS), (PDF_README, PDF_BLOCKS)):
        with open(path, encoding="utf-8") as f:
            current = f.read()
        updated = render(current, blocks)
        if "--check" in argv:
            if current != updated:
                stale.append(os.path.relpath(path, ROOT))
            continue
        if current != updated:
            with open(path, "w", encoding="utf-8") as f:
                f.write(updated)
        written.append("%s (%s)" % (os.path.relpath(path, ROOT), ", ".join(sorted(blocks))))
    if "--check" in argv:
        if stale:
            print("generated blocks are stale in %s; run "
                  "python3 scripts/make_readme_tables.py" % ", ".join(stale))
            return 1
        print("generated blocks are current.")
        return 0
    print("generated blocks written: %s" % "; ".join(written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
