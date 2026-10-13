"""Sentinel-5P against the fleet: the one validation channel outside every reporting chain.

Every other comparator this sector carries - the CRT, EDGAR, Climate TRACE, the report's
own heat rates - ultimately rests on statistics someone reported. TROPOMI measures NO2
and SO2 columns from orbit, daily; NO2's hours-scale lifetime keeps its signal near the
source, and the fleet's largest plants are visible in it. The extraction
(scripts/extract_tropomi_power.py, from the daily 0.1-degree archive on the user's SSD)
computed a same-day annulus-background enhancement per source per day; this module turns
those into fiscal-year statements and tests four hypotheses THAT WERE STATED BEFORE THE
FULL RUN, each keyed to something the ledger already claims:

  H1 HUB DECLINE. The ledger retires the Hub site's fuel (Hubco RFO 977 kt -> 0; China
     Power Hub coal 2,253 -> 132 kt). The satellite must see the site fade:
     FY2023 enhancement below 0.65 x FY2020.
  H2 THAR RAMP. The mine-mouth cluster went one plant to four, 3.6 to 13.2 Mt of coal.
     FY2023 enhancement above 1.5 x FY2020 - and SO2, the lignite sulfur signature,
     should rise harder than NO2.
  H3 SAHIWAL FY2021 ARBITRATION - the cross-module payoff. The implied-CV channel
     flagged Sahiwal's FY2021 ledger mass as a suspect cell (1,444 kt against 6,881 GWh,
     implied CV 44 TJ/Gg). Generation says FY2021 was 0.94 x FY2020; the suspect mass
     says 0.53. If the satellite tracks the plant rather than the misprinted cell, its
     enhancement ratio sits near the generation ratio.
  H4 NULL CONTROL. Uch burns steady field gas; its FY enhancements should be flat
     (CV below 0.3). Guddu was drafted as a second null and the data rejected the
     premise: its fuel actually swings by a third across the window (the 747 MW block's
     degradation years), and its enhancement follows (within-source rho +0.8) - which is
     covariation evidence, not a failed control, and it is reported as such.

SEASON-BALANCED AGGREGATION. Daily enhancements are noisy (std about the median) and
cloud gaps are seasonal, so fiscal years aggregate in two stages: daily -> monthly mean
(at least 5 valid days), monthly -> FY mean (at least 8 months, at least 2 in each
half-year). The July-June convention matches the sector; the rule automatically excludes
FY2019-20, which the archive covers only from January 2020.

WHAT THIS CAN AND CANNOT SAY. No wind rotation: the annulus background is smeared into
by the plume itself, biasing enhancements LOW - conservative for the detection claims.
The Port Qasim complex sits inside Karachi's plume and the Hub annulus touches it, so
those two sources support only within-source time contrasts, never cross-source levels.
Columns are GEE daily L3 composites without averaging-kernel handling; complexes closer
than the 0.1-degree grid separates are one source each, attribution mixed by
construction. The ledger ends at FY2023-24, so satellite FY2024-25 rows are
observations, not verdicts. DIAGNOSTIC ONLY: combustion.py and engine.py never import
this module, and nothing here feeds the estimate.
"""

from pkinv.assets import asset_path
import csv
import os
from collections import defaultdict

from pkinv.paths import DATA
from pkinv.sectors.power import plant_ledger
from pkinv.activity.store import read_rows

CSV = asset_path(DATA, "activity", "power", "tropomi_no2_plants.csv")

MIN_DAYS_PER_MONTH = 5
MIN_MONTHS_PER_FY = 8
MIN_MONTHS_PER_HALF = 2
MIN_SRC_CELLS, MIN_BKG_CELLS = 4, 60

# Satellite source -> the ledger plants whose fuel/generation it integrates over.
LEDGER_PLANTS = {
    "sahiwal": ["Huaneng Shandong Ruyi (Sahiwal Imported Coal)"],
    "thar_cluster": ["Engro Powergen Thar", "Thar Coal Block-I", "Thar Energy",
                     "ThalNova"],
    "hub_complex": ["Hub", "China Power Hub"],
    "port_qasim_complex": ["Port Qasim Electric Power", "Lucky Electric",
                           "Bin Qasim TPS-I", "Bin Qasim TPS-II",
                           "(000 liters) (Average) & Bin Qasim TPS-III"],
    "uch": ["Uch", "Uch-II"],
    "guddu": ["(Rs. Million) TPS Guddu (Units 5-10) (GENCO-II)",
              "TPS Guddu (Units 14-16) (GENCO-II)"],
    "balloki": ["NPPMCL (Balloki)"],
    "bhikki": ["QATPL (Bhikki)"],
    "hbs": ["NPPMCL (HBS)"],
}


def _rows(path=CSV):
    return read_rows(path, comments=False)


def _fy_of(day):
    """'YYYY-MM-DD' -> fiscal year (July-June, labelled by start year)."""
    y, m = int(day[:4]), int(day[5:7])
    return y if m >= 7 else y - 1


def fy_enhancements(species="no2", path=CSV):
    """{(source, fy): {"enh": mean, "n_days": int, "n_months": int}} - season-balanced."""
    monthly = defaultdict(list)
    for r in _rows(path):
        e = r["%s_enhancement" % species]
        if e == "":
            continue
        if (int(r["%s_src_cells" % species]) < MIN_SRC_CELLS
                or int(r["%s_bkg_cells" % species]) < MIN_BKG_CELLS):
            continue
        monthly[(r["source"], r["date"][:7])].append(float(e))
    month_means = {k: (sum(v) / len(v), len(v)) for k, v in monthly.items()
                   if len(v) >= MIN_DAYS_PER_MONTH}
    per_fy = defaultdict(list)
    for (source, ym), (mean, ndays) in month_means.items():
        m = int(ym[5:7])
        fy = _fy_of(ym + "-15")
        half = 0 if m >= 7 else 1
        per_fy[(source, fy)].append((mean, ndays, half))
    out = {}
    for key, months in per_fy.items():
        halves = {h for _m, _n, h in months}
        if len(months) < MIN_MONTHS_PER_FY:
            continue
        if (sum(1 for _m, _n, h in months if h == 0) < MIN_MONTHS_PER_HALF
                or sum(1 for _m, _n, h in months if h == 1) < MIN_MONTHS_PER_HALF):
            continue
        out[key] = {"enh": sum(m for m, _n, _h in months) / len(months),
                    "n_days": sum(n for _m, n, _h in months),
                    "n_months": len(months)}
    return out


def ledger_generation(source, fy):
    """Summed net generation (GWh) of the source's ledger plants for the fiscal year."""
    plants = LEDGER_PLANTS[source]
    total, found = 0.0, False
    for r in plant_ledger.rows(fy):
        if r["plant"] in plants:
            total += float(r["net_generation_GWh"])
            found = True
    return total if found else None


def table(species="no2"):
    """One row per source-FY: enhancement, coverage, ledger generation."""
    fy = fy_enhancements(species)
    out = []
    for (source, year), v in sorted(fy.items()):
        out.append({"source": source, "fiscal_year": year,
                    "%s_enh" % species: v["enh"], "n_days": v["n_days"],
                    "n_months": v["n_months"],
                    "ledger_net_GWh": ledger_generation(source, year)})
    return out


def _enh(fy_map, source, year):
    v = fy_map.get((source, year))
    return v["enh"] if v else None


def verdicts():
    """The four pre-stated hypotheses, as numbers plus booleans."""
    no2 = fy_enhancements("no2")
    so2 = fy_enhancements("so2")
    out = {}

    hub23, hub20 = _enh(no2, "hub_complex", 2023), _enh(no2, "hub_complex", 2020)
    out["h1_hub_ratio_fy2023_over_fy2020"] = hub23 / hub20 if hub23 and hub20 else None
    out["h1_hub_decline_confirmed"] = bool(hub23 and hub20 and hub23 < 0.65 * hub20)

    th23, th20 = _enh(no2, "thar_cluster", 2023), _enh(no2, "thar_cluster", 2020)
    out["h2_thar_no2_ratio"] = th23 / th20 if th23 and th20 else None
    ts23, ts20 = _enh(so2, "thar_cluster", 2023), _enh(so2, "thar_cluster", 2020)
    out["h2_thar_so2_ratio"] = ts23 / ts20 if ts23 and ts20 else None
    out["h2_thar_ramp_confirmed"] = bool(th23 and th20 and th23 > 1.5 * th20)

    s21, s20 = _enh(no2, "sahiwal", 2021), _enh(no2, "sahiwal", 2020)
    out["h3_sahiwal_enh_ratio_fy2021_over_fy2020"] = s21 / s20 if s21 and s20 else None
    out["h3_generation_ratio"] = 6881.38 / 7342.70   # ledger GWh, FY2021/FY2020
    out["h3_suspect_mass_ratio"] = 1443.97 / 2750.14
    out["h3_satellite_sides_with_generation"] = bool(
        s21 and s20 and abs(s21 / s20 - out["h3_generation_ratio"])
        < abs(s21 / s20 - out["h3_suspect_mass_ratio"]))

    for src in ("uch", "guddu"):
        vals = [v["enh"] for (s, _y), v in no2.items() if s == src]
        if len(vals) >= 3:
            mean = sum(vals) / len(vals)
            var = sum((x - mean) ** 2 for x in vals) / len(vals)
            out["h4_%s_cv" % src] = (var ** 0.5) / mean if mean else None
        else:
            out["h4_%s_cv" % src] = None
    # Uch is the null control. Guddu's variability is real fuel variability (see the
    # module docstring); its verdict lives in the per-source Spearman instead.
    out["h4_uch_flat_confirmed"] = bool(
        out["h4_uch_cv"] is not None and out["h4_uch_cv"] < 0.3)
    return out


def spearman():
    """Rank agreement between FY NO2 enhancement and ledger generation, three ways."""
    from scipy.stats import spearmanr
    rows = [r for r in table("no2") if r["ledger_net_GWh"]]
    pooled = spearmanr([r["no2_enh"] for r in rows],
                       [r["ledger_net_GWh"] for r in rows])
    per_source = {}
    for src in sorted({r["source"] for r in rows}):
        sub = [r for r in rows if r["source"] == src]
        if len(sub) >= 4:
            rho = spearmanr([r["no2_enh"] for r in sub],
                            [r["ledger_net_GWh"] for r in sub])
            per_source[src] = {"rho": rho.statistic, "p": rho.pvalue, "n": len(sub)}
    # Within-source ranks pooled: removes between-source level differences.
    ranked_e, ranked_g = [], []
    for src in sorted({r["source"] for r in rows}):
        sub = [r for r in rows if r["source"] == src]
        if len(sub) < 3:
            continue
        es = sorted(r["no2_enh"] for r in sub)
        gs = sorted(r["ledger_net_GWh"] for r in sub)
        for r in sub:
            ranked_e.append(es.index(r["no2_enh"]))
            ranked_g.append(gs.index(r["ledger_net_GWh"]))
    within = spearmanr(ranked_e, ranked_g)
    return {"pooled_rho": pooled.statistic, "pooled_p": pooled.pvalue,
            "pooled_n": len(rows),
            "within_rho": within.statistic, "within_p": within.pvalue,
            "per_source": per_source}
