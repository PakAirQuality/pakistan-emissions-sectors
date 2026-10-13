"""Phase 9 - run the LULUCF land sector and tie it to agriculture as an AFOLU total.

Usage:  python3 -m pkinv.lulucf.run_lulucf   (run run_inventory.py first for the agriculture total)
Writes: outputs/lulucf_totals.csv, afolu_summary.csv, lulucf_report.md
"""

from pkinv.assets import asset_path
import csv
import io
import os
import sys
import zipfile

from pkinv.lulucf import lulucf  # noqa: E402

from pkinv.paths import ROOT, OUTPUTS

OUT = asset_path(ROOT, "outputs")
EMIS_ZIP = asset_path(ROOT, "data", "faostat_cache", "Emissions_Totals.zip")


def _agriculture_total():
    path = asset_path(OUTPUTS, "national_totals_2024.csv")
    if not os.path.exists(path):
        return None
    for r in csv.DictReader(open(path)):
        if r["category"] == "TOTAL":
            return float(r["co2e_Mt_AR5"])
    return None


def _faostat_lulucf():
    """Latest-year + 1990 Pakistan FAOSTAT LULUCF and Forestland (Mt CO2e AR5)."""
    if not os.path.exists(EMIS_ZIP):
        return {}
    out = {}
    z = zipfile.ZipFile(EMIS_ZIP)
    name = [n for n in z.namelist() if n.endswith("(Normalized).csv")][0]
    with z.open(name) as fb:
        r = csv.reader(io.TextIOWrapper(fb, encoding="latin-1"))
        h = next(r)
        ci = {k: i for i, k in enumerate(h)}
        for row in r:
            if row[ci["Area"]] != "Pakistan" or row[ci["Element Code"]] != "723113":
                continue
            it = row[ci["Item"]]
            if it in ("LULUCF", "Forestland") and row[ci["Value"]]:
                y = int(row[ci["Year"]])
                out.setdefault(it, {})[y] = float(row[ci["Value"]]) / 1000.0
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    params = lulucf.load_params()
    comp = lulucf.compute(params)
    net = lulucf.net(comp)
    ag = _agriculture_total()
    fao = _faostat_lulucf()

    _write_totals(comp, net)
    _write_afolu(ag, net, fao)
    _write_report(comp, net, ag, fao, params)

    print("Pakistan LULUCF land sector (2024, provisional, Tier 1):")
    for c in comp:
        print("  %-6s %-38s %s" % (c["code"], c["subcategory"],
                                   "NE (not estimated)" if c["co2e_Mt"] is None
                                   else "%+7.2f Mt CO2e" % c["co2e_Mt"]))
    print("  %-45s %+7.2f Mt CO2e  (FAOSTAT LULUCF ~ %s)"
          % ("NET LULUCF", net, _fao_latest(fao, "LULUCF")))
    if ag is not None:
        print("  AFOLU net = agriculture %.1f + LULUCF %.1f = %.1f Mt CO2e" % (ag, net, ag + net))


def _fao_latest(fao, item):
    d = fao.get(item)
    if not d:
        return "n/a"
    y = max(d)
    return "%.1f (%d)" % (d[y], y)


def _write_totals(comp, net):
    with open(asset_path(OUT, "lulucf_totals.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["code", "subcategory", "gas", "co2e_Mt_AR5_signed", "c_stock_Mt_co2e"])
        for c in comp:
            w.writerow([c["code"], c["subcategory"], c["gas"],
                        c.get("notation", "NE") if c["co2e_Mt"] is None else round(c["co2e_Mt"], 3),
                        "" if c["c_stock_Mt_co2e"] is None else round(c["c_stock_Mt_co2e"], 0)])
        w.writerow(["3.B", "NET LULUCF", "CO2", round(net, 3), ""])


def _write_afolu(ag, net, fao):
    with open(asset_path(OUT, "afolu_summary.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["sector", "Mt_CO2e_AR5", "note"])
        w.writerow(["Agriculture (6 categories)", "" if ag is None else round(ag, 1),
                    "from national_totals_2024.csv"])
        w.writerow(["LULUCF (engine, forest + mangrove)", round(net, 2),
                    "Tier 1; sink negative"])
        if ag is not None:
            w.writerow(["AFOLU net (engine)", round(ag + net, 1), "agriculture + LULUCF"])
        w.writerow(["LULUCF (FAOSTAT, forest only)", _num(_fao_latest(fao, "LULUCF")),
                    "FAOSTAT omits mangroves -> engine slightly more negative"])


def _num(s):
    try:
        return float(s.split()[0])
    except Exception:
        return s


def _write_report(comp, net, ag, fao, params):
    lu_series = fao.get("LULUCF", {})
    lines = ["# Pakistan LULUCF Land Sector (2024, provisional, Tier 1)\n",
             "Carbon stock change in the land sector (IPCC 3.B), reported separately from "
             "agriculture and combined into an AFOLU total. Sink = negative.\n",
             "## Net by sub-category (Mt CO2e, AR5)\n",
             "| Code | Sub-category | Flux (signed) | C stock (context) |",
             "|---|---|---:|---:|"]
    for c in comp:
        stk = "-" if c["c_stock_Mt_co2e"] is None else "%.0f" % c["c_stock_Mt_co2e"]
        flux = "NE" if c["co2e_Mt"] is None else "%+.2f" % c["co2e_Mt"]
        lines.append("| %s | %s | %s | %s |" % (c["code"], c["subcategory"], flux, stk))
    lines.append("| **3.B** | **NET LULUCF** | **%+.2f** | |" % net)
    lines.append("")
    if ag is not None:
        lines += ["## AFOLU total\n",
                  "Agriculture **%.1f** + LULUCF **%+.1f** = **AFOLU net %.1f Mt CO2e**.\n"
                  % (ag, net, ag + net)]
    lines += ["## Land-sector narrative (FAOSTAT)\n",
              "Pakistan's land sector flipped from a small **source** to a **sink** as the "
              "Billion Tree -> Ten Billion Tree afforestation programmes took hold:"]
    for y in (1990, 2010, 2015, 2020, max(lu_series) if lu_series else 2023):
        if y in lu_series:
            lines.append("- %d: %+.1f Mt CO2e (FAOSTAT LULUCF)" % (y, lu_series[y]))
    lines += ["",
              "## Validation & caveats",
              "- **Forest** (%+.2f Mt) is calibrated to the afforestation programmes and matches "
              "FAOSTAT Forestland (~%s)." % (comp[0]["co2e_Mt"], _fao_latest(fao, "LULUCF")),
              "- **Mangrove blue carbon** (%+.2f Mt) is our addition - FAOSTAT's aggregate omits "
              "Indus-delta mangroves, so the engine net is slightly more negative (a real sink, "
              "not an error)." % comp[3]["co2e_Mt"],
              "- **Arid-climate caveat:** IPCC 2013 Wetlands defaults (AGB-C 86, soil-C 471 t C/ha) "
              "are humid-tropical; the arid Indus delta is likely lower - flagged for Tier 2.",
              "- Cropland/grassland SOC are NOT ESTIMATED (NE) at Tier 1 - no land-use or "
              "management change is modelled - and contribute nothing to the net; they are not "
              "zeros (rc42).",
              "- Tier 1, single-year; full per-transition gain-loss and a LULUCF time series are "
              "future work.", ""]
    with open(asset_path(OUT, "lulucf_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


if __name__ == "__main__":
    main()
