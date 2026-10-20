"""Run every coherent case of the gas reallocation and write outputs/pakemis_transition_gas_*.csv.

THE CASES. Baseline readings (A: FA1, FA2 admissible; FA3 exploratory) x power readings (PA1, PA2
admissible) x coherent pathways (B: R1-R3 with D1-D3, and D4 with no receiving station) x imported
urea routes (F1, F2). D5, the average fossil grid, runs beside them as a comparator. Each case is
computed at the full scope of the two plants' gas (s = 1) on one set of paired draws.

THE REPORTING RULES were fixed before any case was run (docs/gas_reallocation_application.md, s5):
  a cell's change is a REDUCTION if its 97.5th percentile is below zero and an INCREASE if its 2.5th
  is above zero; otherwise it SPANS zero. Over the admissible baselines and the evidence pathways:
  robust reduction / robust increase = every cell the same sign;
  conditional = every cell excludes zero but the sign differs, and the dimension that decides it is named;
  unresolved = at least one cell spans zero, or a not-estimated component could reverse the sign;
  trade-off = within one cell, one pollutant robustly falls while another robustly rises.
"Robust" means robust across the tested, justified cases and nothing wider.

Writes (all in outputs/): pakemis_transition_gas_sources.csv, _flows.csv, _baselines.csv,
_matrix.csv, _sectors.csv, _thresholds.csv, _conclusions.csv, _checks.csv.
"""
import argparse
import os

import numpy as np

from pkinv.core.io import write_table
from pkinv.core.shared_parameter_draws import SEED
from pkinv.core.units import TJ_PER_MMBTU
from pkinv.paths import OUTPUTS

from . import inputs, model

REPORTED_DRAWS = 10000
FA_ADMISSIBLE = ("FA1", "FA2")
FA_EXPLORATORY = ("FA3",)
PA_ADMISSIBLE = ("PA1", "PA2")
POLLUTANT_ROWS = model.POLLUTANTS + ("CO2e_AR5", "CO2e_AR6")
PREFIX = "pakemis_transition_gas_"


def _out(name):
    return os.path.join(OUTPUTS, PREFIX + name + ".csv")


def _na(v):
    return isinstance(v, str) and v == model.NA


def _feasible(x):
    """The feasible fraction, blank where no station group in the records limits it (D4)."""
    return "" if x == float("inf") else _fmt(x, 4)


def _stats(x):
    x = np.asarray(x, dtype=float)
    return {"mean": float(np.mean(x)), "p2_5": float(np.percentile(x, 2.5)),
            "p50": float(np.percentile(x, 50)), "p97_5": float(np.percentile(x, 97.5)),
            "p_reduction": float(np.mean(x < 0))}


def _fmt(v, digits=6):
    if v is None:
        return ""
    if isinstance(v, str):
        return v
    return ("%%.%dg" % digits) % v


def _sign(stats):
    if stats["p97_5"] < 0:
        return "-"
    if stats["p2_5"] > 0:
        return "+"
    if stats["p2_5"] == 0 and stats["p97_5"] == 0:
        return "0"
    return "~"


def _aggregate(base, tran, boundary, pollutant):
    """(delta array or None, base array, tran array, NE components as [(sector, direction)])."""
    delta = b_sum = t_sum = None
    missing = []
    for key, _label, sector_boundary, _status in model.SECTORS:
        if sector_boundary != boundary:
            continue
        if pollutant.startswith("CO2e"):
            ar = pollutant.split("_")[1]
            vb, vt = model.co2e(base[key], ar), model.co2e(tran[key], ar)
            if _na(vb) or _na(vt):
                continue
        else:
            if pollutant not in base[key] and pollutant not in tran[key]:
                continue                            # the process does not emit it (NA)
            vb, vt = base[key].get(pollutant), tran[key].get(pollutant)
        if vb is None or vt is None:
            missing.append((key, model.DIRECTION.get(key, 0)))
            continue
        d = vt - vb
        delta = d if delta is None else delta + d
        b_sum = vb if b_sum is None else b_sum + vb
        t_sum = vt if t_sum is None else t_sum + vt
    return delta, b_sum, t_sum, missing


def _coverage(missing, sign):
    """'complete', 'bound' (every NE part moves the same way as the estimate), or 'reversible'."""
    if not missing:
        return "complete"
    want = {"-": -1, "+": +1}.get(sign)
    if want is not None and all(direction == want for _k, direction in missing):
        return "bound"
    return "reversible"


def pathway_combinations():
    """(receiving, displaced, route, role) for every combination coherence.csv admits.

    R* and F* expand to every pathway of that family in pathways.csv; a 'no' row is never computed and a
    'comparator' row runs beside the evidence (on F1 only: the comparator has no external term)."""
    families = {}
    for pid, entry in inputs.pathways().items():
        families.setdefault(entry["family"], []).append(pid)
    out = []
    for row in inputs.table("coherence.csv"):
        if row["coherent"] not in ("yes", "comparator"):
            continue
        rs = sorted(families["receiving"]) if row["receiving"] == "R*" else [row["receiving"]]
        fs = sorted(families["fertilizer"]) if row["fertilizer"] == "F*" else [row["fertilizer"]]
        if row["coherent"] == "comparator":
            fs = fs[:1]
        role = "evidence" if row["coherent"] == "yes" else "comparator"
        out.extend((r, row["displaced"], f, role) for r in rs for f in fs)
    return out


def cases():
    out = []
    for fa in FA_ADMISSIBLE + FA_EXPLORATORY:
        for pa in PA_ADMISSIBLE:
            for r, d, f, role in pathway_combinations():
                if role == "evidence" and fa not in FA_ADMISSIBLE:
                    role = "exploratory"
                elif role == "comparator" and fa not in FA_ADMISSIBLE:
                    continue
                out.append(((fa, pa, r, d, f), role))
    return out


def feasibility(rec, case, flows):
    """Most of the plants' gas the case can take before a station group runs out (fraction, <= 1 ok)."""
    _fa, _pa, r, d, _f = case
    service = float(np.median(flows["gwh_service"]))
    limits = []
    if d in ("D1", "D2", "D3"):
        limits.append(rec.gwh_capacity(d) / service)
    if r != "none":
        limits.append(rec.gwh_capacity(r) / service)
    return min(limits) if limits else float("inf")


def run_all(n=REPORTED_DRAWS, year=inputs.REFERENCE_YEAR):
    rec = model.Records(year)
    results = []
    for case, role in cases():
        base, tran, draws = model.run(rec, case, 1.0, n)
        results.append({"case": case, "role": role, "base": base, "tran": tran, "draws": draws,
                        "feasible_fraction": feasibility(rec, case, tran["flows"])})
    return rec, results


def matrix_rows(results, n):
    rows, cell_signs = [], {}
    label = "reported" if n >= REPORTED_DRAWS else "development_sample"
    for res in results:
        fa, pa, r, d, f = res["case"]
        pj = res["tran"]["flows"]["gas_moved_pj_hhv"]
        for boundary, pols in (("territorial", POLLUTANT_ROWS), ("external", ("CO2e_AR5",))):
            for pol in pols:
                if res["role"] == "comparator" and not pol.startswith("CO2e"):
                    continue
                delta, b, t, missing = _aggregate(res["base"], res["tran"], boundary, pol)
                row = {"reference_year": rec_year(res), "baseline_fertilizer": fa, "baseline_power": pa,
                       "receiving": r, "displaced": d, "fertilizer_route": f, "role": res["role"],
                       "boundary": boundary, "pollutant": pol,
                       "unit": "Gg CO2e" if pol.startswith("CO2e") else "Gg",
                       "not_estimated_components": ";".join(k for k, _d in missing),
                       "max_feasible_fraction": _feasible(res["feasible_fraction"]),
                       "n_draws": n, "sample_label": label}
                if delta is None:
                    row.update({"coverage": "NE", "sign": "NE"})
                    rows.append(row)
                    continue
                s = _stats(delta)
                per = _stats(delta / pj)
                sign = _sign(s)
                row.update({"baseline_mean": _fmt(float(np.mean(b))), "transition_mean": _fmt(float(np.mean(t))),
                            "delta_mean": _fmt(s["mean"]), "delta_p2_5": _fmt(s["p2_5"]),
                            "delta_p50": _fmt(s["p50"]), "delta_p97_5": _fmt(s["p97_5"]),
                            "delta_per_pj_mean": _fmt(per["mean"]), "delta_per_pj_p2_5": _fmt(per["p2_5"]),
                            "delta_per_pj_p97_5": _fmt(per["p97_5"]),
                            "p_reduction": _fmt(s["p_reduction"], 4), "sign": sign,
                            "coverage": _coverage(missing, sign)})
                rows.append(row)
                cell_signs[(res["case"], boundary, pol)] = (sign, row["coverage"], res["role"])
        # combined: territorial CO2e + external, formed only because both are CO2e AR5; labelled partial.
        dt, *_ = _aggregate(res["base"], res["tran"], "territorial", "CO2e_AR5")
        dx, *_ = _aggregate(res["base"], res["tran"], "external", "CO2e_AR5")
        row = {"reference_year": rec_year(res), "baseline_fertilizer": fa, "baseline_power": pa,
               "receiving": r, "displaced": d, "fertilizer_route": f, "role": res["role"],
               "boundary": "combined_partial", "pollutant": "CO2e_AR5", "unit": "Gg CO2e",
               "max_feasible_fraction": _feasible(res["feasible_fraction"]),
               "n_draws": n, "sample_label": label,
               "not_estimated_components": "exporter urea synthesis and finishing energy; urea shipping"}
        if dt is None or dx is None:
            row.update({"coverage": "NE", "sign": "NE"})
        else:
            s = _stats(dt + dx)
            per = _stats((dt + dx) / pj)
            sign = _sign(s)
            row.update({"delta_mean": _fmt(s["mean"]), "delta_p2_5": _fmt(s["p2_5"]), "delta_p50": _fmt(s["p50"]),
                        "delta_p97_5": _fmt(s["p97_5"]), "delta_per_pj_mean": _fmt(per["mean"]),
                        "delta_per_pj_p2_5": _fmt(per["p2_5"]), "delta_per_pj_p97_5": _fmt(per["p97_5"]),
                        "p_reduction": _fmt(s["p_reduction"], 4), "sign": sign, "coverage": "bound"})
            cell_signs[(res["case"], "combined_partial", "CO2e_AR5")] = (sign, "bound", res["role"])
        rows.append(row)
    return rows, cell_signs


def rec_year(res):
    return res.get("year", inputs.REFERENCE_YEAR)


MATRIX_FIELDS = ("reference_year", "baseline_fertilizer", "baseline_power", "receiving", "displaced",
                 "fertilizer_route", "role", "boundary", "pollutant", "unit", "baseline_mean",
                 "transition_mean", "delta_mean", "delta_p2_5", "delta_p50", "delta_p97_5",
                 "delta_per_pj_mean", "delta_per_pj_p2_5", "delta_per_pj_p97_5", "p_reduction", "sign",
                 "coverage", "not_estimated_components", "max_feasible_fraction", "n_draws", "sample_label")


DIMENSIONS = ("baseline_fertilizer", "baseline_power", "receiving", "displaced", "fertilizer_route")


def classify(cell_signs, boundary, pollutant, select=None):
    """Classification of one (boundary, pollutant) over the admissible evidence cells (optionally a subset)."""
    cells = {case: v for (case, b, p), v in cell_signs.items()
             if b == boundary and p == pollutant and v[2] == "evidence" and (select is None or select(case))}
    if boundary == "territorial":     # the import route does not touch territorial emissions
        cells = {c: v for c, v in cells.items() if c[4] == "F1"}
    if not cells:
        return None
    signs = {c: v[0] for c, v in cells.items()}
    reversible = [c for c, v in cells.items() if v[1] == "reversible"]
    spans = [c for c, s in signs.items() if s in ("~", "NE")]
    n = len(cells)
    if spans or reversible:
        cls = "unresolved"
        why = []
        if spans:
            why.append("%d of %d cases span zero" % (len(spans), n))
        if reversible:
            why.append("%d of %d cases have a not-estimated component that could reverse the sign"
                       % (len(reversible), n))
        condition = "; ".join(why)
    elif set(signs.values()) == {"-"}:
        cls, condition = "robust reduction", "every admissible baseline and evidence pathway"
    elif set(signs.values()) == {"+"}:
        cls, condition = "robust increase", "every admissible baseline and evidence pathway"
    elif set(signs.values()) == {"0"}:
        cls, condition = "no change", "identical activity in both states"
    else:
        cls, condition = "conditional", _deciding_dimension(signs)
    bound = sum(1 for v in cells.values() if v[1] == "bound")
    return {"classification": cls, "condition": condition, "cases": n,
            "cases_reduction": sum(1 for s in signs.values() if s == "-"),
            "cases_increase": sum(1 for s in signs.values() if s == "+"),
            "cases_spanning": len(spans), "cases_bound_only": bound}


def _deciding_dimension(signs):
    """The dimension whose levels each carry one sign, named with the sign of each level."""
    for i, name in enumerate(DIMENSIONS):
        by_level = {}
        for case, sign in signs.items():
            by_level.setdefault(case[i], set()).add(sign)
        if all(len(v) == 1 for v in by_level.values()) and len(by_level) > 1:
            return "decided by %s: %s" % (name, ", ".join(
                "%s %s" % (lvl, "reduction" if s == {"-"} else "increase")
                for lvl, s in sorted(by_level.items())))
    return "the sign depends on more than one assumption at once"


def conclusion_rows(cell_signs):
    rows = []
    groups = [("all evidence pathways", None)] + [
        ("displaced %s" % d, (lambda d: lambda c: c[3] == d)(d)) for d in ("D1", "D2", "D3", "D4")]
    for boundary, pols in (("territorial", POLLUTANT_ROWS), ("external", ("CO2e_AR5",)),
                           ("combined_partial", ("CO2e_AR5",))):
        for pol in pols:
            for label, select in groups:
                c = classify(cell_signs, boundary, pol, select)
                if c is None:
                    continue
                rows.append(dict(c, boundary=boundary, pollutant=pol, scope=label))
    # trade-offs: within one territorial cell, a robust fall in one pollutant and a robust rise in another
    by_cell = {}
    for (case, b, p), (sign, cov, role) in cell_signs.items():
        if b == "territorial" and role == "evidence" and case[4] == "F1" and p in model.POLLUTANTS:
            by_cell.setdefault(case, {})[p] = sign if cov != "reversible" else "?"
    for d in ("D1", "D2", "D3", "D4"):
        cells = {c: v for c, v in by_cell.items() if c[3] == d}
        falls = set.intersection(*[{p for p, s in v.items() if s == "-"} for v in cells.values()])
        rises = set.intersection(*[{p for p, s in v.items() if s == "+"} for v in cells.values()])
        some = sum(1 for v in cells.values() if "-" in v.values() and "+" in v.values())
        rows.append({"boundary": "territorial", "pollutant": "air pollutants and GHGs", "scope": "displaced %s" % d,
                     "classification": "trade-off" if some else "no trade-off",
                     "condition": "falls in every case: %s; rises in every case: %s" % (
                         ", ".join(sorted(falls)) or "none", ", ".join(sorted(rises)) or "none"),
                     "cases": len(cells), "cases_reduction": "", "cases_increase": "",
                     "cases_spanning": "", "cases_bound_only": some})
    return rows


CONCLUSION_FIELDS = ("boundary", "pollutant", "scope", "classification", "condition", "cases",
                     "cases_reduction", "cases_increase", "cases_spanning", "cases_bound_only")


def sector_rows(results):
    rows = []
    for res in results:
        if res["role"] != "evidence" or res["case"][0] not in FA_ADMISSIBLE:
            continue
        fa, pa, r, d, f = res["case"]
        for key, label, boundary, status in model.SECTORS:
            if boundary == "territorial" and f != "F1":
                continue                      # territorial sectors do not depend on the import route
            for pol in POLLUTANT_ROWS if boundary == "territorial" else ("CO2e_AR5",):
                if pol.startswith("CO2e"):
                    vb = model.co2e(res["base"][key], pol.split("_")[1])
                    vt = model.co2e(res["tran"][key], pol.split("_")[1])
                    if _na(vb) or _na(vt):
                        continue
                else:
                    if pol not in res["base"][key] and pol not in res["tran"][key]:
                        continue
                    vb, vt = res["base"][key].get(pol), res["tran"][key].get(pol)
                row = {"baseline_fertilizer": fa, "baseline_power": pa, "receiving": r, "displaced": d,
                       "fertilizer_route": f if boundary == "external" else "", "sector": key,
                       "sector_label": label, "boundary": boundary, "inventory_status": status,
                       "pollutant": pol, "unit": "Gg CO2e" if pol.startswith("CO2e") else "Gg"}
                if vb is None or vt is None:
                    row["status"] = "NE"
                else:
                    s = _stats(vt - vb)
                    row.update({"delta_mean": _fmt(s["mean"]), "delta_p2_5": _fmt(s["p2_5"]),
                                "delta_p97_5": _fmt(s["p97_5"]), "status": "E"})
                rows.append(row)
    return rows


SECTOR_FIELDS = ("baseline_fertilizer", "baseline_power", "receiving", "displaced", "fertilizer_route",
                 "sector", "sector_label", "boundary", "inventory_status", "pollutant", "unit",
                 "delta_mean", "delta_p2_5", "delta_p97_5", "status")


def threshold_rows(rec, results):
    """T1: the displaced-generation intensity at which the territorial CO2e change is zero.
    T2: the imported-urea intensity at which the territorial-plus-external change is zero."""
    rows = []
    seen = set()
    for res in results:
        fa, pa, r, d, f = res["case"]
        if res["role"] != "evidence" or f != "F1":
            continue
        base, tran = res["base"], res["tran"]
        service = tran["flows"]["gwh_service"]
        if d != "D4":
            rest = 0.0
            for key, _l, boundary, _s in model.SECTORS:
                if boundary == "territorial" and key != "1A1a_disp":
                    vb, vt = model.co2e(base[key]), model.co2e(tran[key])
                    if not (_na(vb) or _na(vt)):
                        rest = rest + (vt - vb)
            breakeven = rest / service                      # Gg CO2e per GWh = t per MWh
            disp = -(model.co2e(tran["1A1a_disp"]) - model.co2e(base["1A1a_disp"])) / service
            key = (fa, pa, r)
            if key not in seen:
                seen.add(key)
                s = _stats(breakeven)
                rows.append({"threshold": "T1 displaced-generation intensity for zero territorial CO2e change",
                             "baseline_fertilizer": fa, "baseline_power": pa, "receiving": r, "displaced": "",
                             "unit": "t CO2e (AR5) per MWh", "threshold_p50": _fmt(s["p50"]),
                             "threshold_p2_5": _fmt(s["p2_5"]), "threshold_p97_5": _fmt(s["p97_5"]),
                             "comparison": "D5 average fossil CPPA-G %.3f" % rec.grid_average,
                             "p_comparison_above_threshold": _fmt(float(np.mean(rec.grid_average > breakeven)), 4)})
            s = _stats(disp)
            rows.append({"threshold": "T1 intensity of the displaced pathway (combustion only)",
                         "baseline_fertilizer": fa, "baseline_power": pa, "receiving": r, "displaced": d,
                         "unit": "t CO2e (AR5) per MWh", "threshold_p50": _fmt(s["p50"]),
                         "threshold_p2_5": _fmt(s["p2_5"]), "threshold_p97_5": _fmt(s["p97_5"]),
                         "comparison": "the case's own T1 threshold",
                         "p_comparison_above_threshold": _fmt(float(np.mean(disp > breakeven)), 4)})
        dt, *_ = _aggregate(base, tran, "territorial", "CO2e_AR5")
        dfuel = model.co2e(tran["X_fuel"]) - model.co2e(base["X_fuel"])
        urea_moved = tran["flows"]["urea_imported_kt"]
        x_star = -(dt + dfuel) / urea_moved
        f1 = model.import_factor(res["draws"], "F1")
        f2 = model.import_factor(res["draws"], "F2")
        s = _stats(x_star)
        rows.append({"threshold": "T2 imported-urea intensity for zero territorial-plus-external CO2e change",
                     "baseline_fertilizer": fa, "baseline_power": pa, "receiving": r, "displaced": d,
                     "unit": "t CO2e (AR5) per t urea", "threshold_p50": _fmt(s["p50"]),
                     "threshold_p2_5": _fmt(s["p2_5"]), "threshold_p97_5": _fmt(s["p97_5"]),
                     "comparison": "F1 gas route p50 %.3f; F2 coal route (lower bound) p50 %.3f"
                                   % (np.median(f1), np.median(f2)),
                     "p_comparison_above_threshold": "F1 %.4f; F2 %.4f" % (np.mean(f1 > x_star),
                                                                          np.mean(f2 > x_star))})
    d = results[0]["draws"]
    for route, label in (("F1", "gas-reforming route"), ("F2", "coal-gasification route (feedstock only: a lower bound)")):
        s = _stats(model.import_factor(d, route))
        rows.append({"threshold": "T2 imported-urea intensity of route %s, %s" % (route, label),
                     "baseline_fertilizer": "", "baseline_power": "", "receiving": "", "displaced": "",
                     "unit": "t CO2e (AR5) per t urea", "threshold_p50": _fmt(s["p50"]),
                     "threshold_p2_5": _fmt(s["p2_5"]), "threshold_p97_5": _fmt(s["p97_5"]),
                     "comparison": "exporter 2.B.1 net of urea-bound CO2 plus feedstock upstream",
                     "p_comparison_above_threshold": ""})
    return rows


THRESHOLD_FIELDS = ("threshold", "baseline_fertilizer", "baseline_power", "receiving", "displaced", "unit",
                    "threshold_p50", "threshold_p2_5", "threshold_p97_5", "comparison",
                    "p_comparison_above_threshold")


def flow_rows(rec, results):
    rows = []
    for plant in sorted(rec.gas):
        g, u = rec.gas[plant], rec.urea[plant]
        rows.append({"item": "plant", "name": plant, "feed_mmcf": _fmt(g["feed"]), "fuel_mmcf": _fmt(g["fuel"]),
                     "urea_kt": _fmt(u), "nh3_kt": _fmt(u * rec.params["nh3_per_urea"]["value"]),
                     "mmcf_per_kt_urea": _fmt((g["feed"] + g["fuel"]) / u, 5),
                     "note": "suppliers " + ", ".join("%s %.0f" % kv for kv in sorted(g["suppliers"].items())),
                     "source": g["source"] + "; NFDC Table 1"})
    seen = set()
    for res in results:
        fa, pa, r, d, f = res["case"]
        if res["role"] == "exploratory" or fa != "FA1" or f != "F1" or (pa, r, d) in seen:
            continue
        seen.add((pa, r, d))
        fl, fb = res["tran"]["flows"], res["base"]["flows"]
        service = _stats(fl["gwh_service"])
        dom_b, dom_t = float(np.median(fb["urea_domestic_kt"])), float(np.median(fl["urea_domestic_kt"]))
        imp_b, imp_t = float(np.median(fb["urea_imported_kt"])), float(np.median(fl["urea_imported_kt"]))
        rows.append({"item": "case", "name": "%s %s %s" % (pa, r, d),
                     "gas_moved_mmcf": _fmt(float(np.median(fl["gas_moved_mmcf"]))),
                     "gas_moved_pj_hhv_p50": _fmt(float(np.median(fl["gas_moved_pj_hhv"]))),
                     "gwh_service_p50": _fmt(service["p50"]), "gwh_service_p2_5": _fmt(service["p2_5"]),
                     "gwh_service_p97_5": _fmt(service["p97_5"]),
                     "urea_service_baseline_kt": _fmt(dom_b + imp_b), "urea_service_transition_kt": _fmt(dom_t + imp_t),
                     "gwh_service_baseline": _fmt(float(np.median(fb["gwh_receiving"] + fb["gwh_displaced_running"]))),
                     "gwh_service_transition": _fmt(float(np.median(fl["gwh_receiving"] + fl["gwh_displaced_running"]))),
                     "displaced_capacity_gwh": _fmt(rec.gwh_capacity(d)) if d in ("D1", "D2", "D3") else "",
                     "receiving_headroom_gwh": _fmt(rec.gwh_capacity(r)) if r != "none" else "",
                     "max_feasible_fraction": _feasible(res["feasible_fraction"]),
                     "feasible_at_full_scope": "yes" if res["feasible_fraction"] >= 1 else "no",
                     "note": ("D4 adds no generation; the LNG import falls by the moved gas" if d == "D4" else
                              "capacity = the displaced stations' own FY generation; headroom = nameplate "
                              "hours minus FY generation, availability not modelled"),
                     "source": "NEPRA SoIR 2024 station ledger and heat rates; GEM gas/oil tracker"})
    return rows


FLOW_FIELDS = ("item", "name", "feed_mmcf", "fuel_mmcf", "urea_kt", "nh3_kt", "mmcf_per_kt_urea",
               "gas_moved_mmcf", "gas_moved_pj_hhv_p50", "gwh_service_p50", "gwh_service_p2_5",
               "gwh_service_p97_5", "urea_service_baseline_kt", "urea_service_transition_kt",
               "gwh_service_baseline", "gwh_service_transition", "displaced_capacity_gwh",
               "receiving_headroom_gwh", "max_feasible_fraction", "feasible_at_full_scope", "note", "source")


def baseline_rows(rec, n):
    """Dimension A side by side: the plants' 2.B.1 CO2 under each fertilizer reading and the GWh per PJ
    of each power reading at each receiving pathway."""
    rows = []
    for fa in ("FA1", "FA2", "FA3", "FD1"):
        d = model.Draws(rec.params, rec.factors, n)
        st = model.state(d, rec, (fa, "PA1", "R1", "D1", "F1"), 1.0, 0.0)
        co2 = st["2B1"]["CO2"]
        entry = [r for r in inputs.table("baselines.csv") if r["baseline_id"] == fa][0]
        row = {"baseline_id": fa, "axis": "fertilizer_2B1", "classification": entry["classification"],
               "quantity": "2.B.1 CO2 of the two plants at FY levels", "unit": "Gg CO2"}
        if co2 is None:
            row.update({"status": "NE", "note": entry["definition"]})
        else:
            s = _stats(co2)
            gas_c = (co2 + rec.urea_kt * model.UREA_CO2) / d.get("ef_co2_gas") * 1e6     # TJ of gas carbon
            nh3 = rec.urea_kt * d.get("nh3_per_urea")
            row.update({"p50": _fmt(s["p50"]), "p2_5": _fmt(s["p2_5"]), "p97_5": _fmt(s["p97_5"]),
                        "implied_gj_ncv_per_t_nh3_p50": _fmt(float(np.median(gas_c * 1e3 / (nh3 * 1e3))), 4),
                        "status": "E", "note": entry["definition"]})
        rows.append(row)
    for r in ("R1", "R2", "R3"):
        for pa in ("PA1", "PA2", "PD1"):
            d = model.Draws(rec.params, rec.factors, n)
            h, g2n = d.get("hhv_network_btu_scf"), d.get("gross_to_net")
            mmcf = rec.feed + rec.fuel
            if pa == "PD1":
                if r == "R3":
                    continue                     # MMCFT stations carry no MMBTU to misread
                gwh = model.receiving_gwh(d, rec, r, "PA1", mmcf * h * g2n, mmcf, h, g2n)
            else:
                gwh = model.receiving_gwh(d, rec, r, pa, mmcf * h, mmcf, h, g2n)
            pj = mmcf * h * TJ_PER_MMBTU / 1e3
            s = _stats(gwh / pj)
            eff = _stats(gwh * 3.6 / (pj * 1e3 * g2n))
            entry = [x for x in inputs.table("baselines.csv") if x["baseline_id"] == pa][0]
            rows.append({"baseline_id": pa, "axis": "power_conversion:%s" % r,
                         "classification": entry["classification"],
                         "quantity": "GWh per PJ (HHV) of the plants' gas at %s" % r, "unit": "GWh per PJ",
                         "p50": _fmt(s["p50"]), "p2_5": _fmt(s["p2_5"]), "p97_5": _fmt(s["p97_5"]),
                         "implied_net_efficiency_p50": _fmt(eff["p50"], 4), "status": "E",
                         "note": entry["definition"]})
    return rows


BASELINE_FIELDS = ("baseline_id", "axis", "classification", "quantity", "unit", "p50", "p2_5", "p97_5",
                   "implied_gj_ncv_per_t_nh3_p50", "implied_net_efficiency_p50", "status", "note")


def check_rows(rec, results, n):
    rows = []

    def add(kind, check, value, expected, ok, note):
        rows.append({"kind": kind, "check": check, "value": value, "expected": expected,
                     "result": "INFO" if ok is None else ("PASS" if ok else "FAIL"), "note": note})

    worst_urea = worst_gwh = 0.0
    negative = 0
    for res in results:
        fb, ft = res["base"]["flows"], res["tran"]["flows"]
        worst_urea = max(worst_urea, float(np.max(np.abs(
            (fb["urea_domestic_kt"] + fb["urea_imported_kt"]) - (ft["urea_domestic_kt"] + ft["urea_imported_kt"])))))
        worst_gwh = max(worst_gwh, float(np.max(np.abs(
            (fb["gwh_receiving"] + fb["gwh_displaced_running"]) - (ft["gwh_receiving"] + ft["gwh_displaced_running"])))))
        for fl in (fb, ft):
            negative += sum(int(np.sum(np.asarray(v) < -1e-9)) for v in fl.values())
    add("internal", "urea service held: baseline minus transition urea applied, worst case", _fmt(worst_urea),
        "0 kt", worst_urea < 1e-9, "domestic plus imported urea is the same in both states")
    add("internal", "electricity service held: baseline minus transition GWh, worst case", _fmt(worst_gwh),
        "0 GWh", worst_gwh < 1e-6, "receiving plus still-running displaced generation is the same in both states")
    add("internal", "non-negative flows in every state", negative, "0", negative == 0, "")
    zero = model.run(rec, ("FA2", "PA1", "R1", "D1", "F1"), 0.0, 500)
    worst = 0.0
    for key, *_ in model.SECTORS:
        for pol, vb in zero[0][key].items():
            vt = zero[1][key].get(pol)
            if vb is not None and vt is not None:
                worst = max(worst, float(np.max(np.abs(np.asarray(vt) - np.asarray(vb)))))
    add("internal", "zero intervention gives zero change", _fmt(worst), "0", worst == 0.0, "s_case = 0")
    case = ("FA2", "PA1", "R1", "D1", "F1")
    paired = model.run(rec, case, 1.0, 4000)
    unpaired = model.run(rec, case, 1.0, 4000, paired=False)
    width = {}
    for name, (b, t, _d) in (("paired", paired), ("unpaired", unpaired)):
        dl, *_ = _aggregate(b, t, "territorial", "CO2e_AR5")
        width[name] = float(np.percentile(dl, 97.5) - np.percentile(dl, 2.5))
    add("internal", "paired draws narrow the interval of the change (95%% width, %s)" % " ".join(case),
        "paired %.1f, unpaired %.1f Gg CO2e" % (width["paired"], width["unpaired"]), "paired < unpaired",
        width["paired"] < width["unpaired"], "independent draws per state would double-count shared uncertainty")
    d = model.Draws(rec.params, rec.factors, 500)
    st = model.state(d, rec, ("FA2", "PA1", "R1", "D1", "F1"), 1.0, 0.0)
    h, g2n, ls = d.get("hhv_network_btu_scf"), d.get("gross_to_net"), rec.leak_share
    carbon_in = ((rec.feed + rec.fuel * (1 - ls)) * h * TJ_PER_MMBTU * g2n * d.get("ef_co2_gas") / 1e6)
    gap = float(np.max(np.abs(carbon_in - (st["2B1"]["CO2"] + rec.urea_kt * model.UREA_CO2))))
    add("internal", "carbon balance FA2: gas carbon in = CO2 out + urea-bound CO2", _fmt(gap), "0 Gg CO2",
        gap < 1e-9, "post-meter leaked gas leaves as CH4 and is booked in 1.B.2.b, not as CO2")
    add("internal", "3.C urea application unchanged (same urea, same fields)", "0", "0", True,
        "the application's state carries one urea total; 3.C.3 CO2, soil N2O and NH3 cannot move")
    # independent checks
    agree = [r for r in inputs.nfdc_ogra_agreement() if r["record"] == "difference"]
    add("independent", "NFDC plant meters vs OGRA utility returns, fertilizer gas FY2023-24",
        agree[0]["agreement_pct"] + "%", "within a few percent", abs(float(agree[0]["agreement_pct"])) < 3,
        "validates the sector's gas volume; says nothing about the plant split or the energy content")
    p = rec.params
    stoich = p["fatimafert_urea_cy2024"]["value"] * p["nh3_per_urea"]["value"]
    gapp = (p["fatimafert_ammonia_cy2024"]["value"] - stoich) / stoich * 100
    add("independent", "Fatimafert ammonia: company-reported vs urea x 0.567 (calendar 2024)",
        "%.0f vs %.0f t (%+.1f%%)" % (p["fatimafert_ammonia_cy2024"]["value"], stoich, gapp), "close",
        abs(gapp) < 10, "the company also SOLD 4,313 t of ammonia in 2024 (1.4 points); the stoichiometric "
                        "reconstruction holds for this plant")
    if inputs.REPLICATION_YEAR in inputs.YEARS:
        g25, u25 = inputs.plant_gas(inputs.REPLICATION_YEAR), inputs.plant_urea(inputs.REPLICATION_YEAR)
        for plant in sorted(rec.gas):
            a = (rec.gas[plant]["feed"] + rec.gas[plant]["fuel"]) / rec.urea[plant]
            b = (g25[plant]["feed"] + g25[plant]["fuel"]) / u25[plant]
            add("independent", "%s gas per tonne of urea, FY2024-25 (Table 40) vs FY2023-24 (Annex-28)" % plant,
                "%.2f vs %.2f MMCF/kt (%+.1f%%)" % (b, a, (b - a) / a * 100), "stable", abs(b - a) / a < 0.05,
                "a different year's meters: the plant intensity the reallocation scales with is not a one-year artefact")
    # documentary bound and diagnostics
    mode = model.hhv_mode(rec.params)
    lo, hi = p["hhv_network_btu_scf"]["low"], p["hhv_network_btu_scf"]["high"]
    add("documentary", "heating value implied by Fatimafert's energy index", "%.1f Btu/scf" % mode,
        "within %g-%g" % (lo, hi), lo <= mode <= hi, "NOT a validation: it sets the mode of the range it is checked against")
    sui = p["nfdc_gcv_sui_btu_cft"]["value"]
    add("independent", "heating value: NFDC Table 6.2 Sui gas vs the value Fatimafert's own records imply",
        "%.0f vs %.1f Btu/scf (%+.1f%%)" % (sui, mode, (sui - mode) / mode * 100), "close",
        abs(sui - mode) / mode < 0.05,
        "a printed constant against a company energy index divided by NFDC plant meters: no input is shared")
    norm = p["nfdc_urea_gas_norm_mmbtu_t"]["value"]
    for plant in sorted(rec.gas):
        per_t = (rec.gas[plant]["feed"] + rec.gas[plant]["fuel"]) / rec.urea[plant] * sui / 1e3
        add("diagnostic", "%s metered gas per tonne of urea at the Sui heating value vs the NFDC norm" % plant,
            "%.1f vs %.0f MMBTU/t" % (per_t, norm), "", None, "the norm (24 feed + 6 fuel) is a planning figure")
    mari = p["nfdc_gcv_mari_btu_cft"]["value"]
    add("diagnostic", "Mari dedicated-line gas heating value (out-of-scope plants)", "%.0f Btu/cft" % mari, "", None,
        "below the 900-1,000 the inventory's gas-carbon memo applies to the whole fertilizer class "
        "(outputs/pakemis_gas_flow_crosswalk.csv), which therefore overstates the Mari plants' gas carbon")
    for r in ("R1", "R2"):
        recs = rec.stations[r]
        led = sum(l["gwh"] for s in recs for l in s["legs"] if l["unit"] == "MMBTU")
        mmbtu = sum(l["quantity"] for s in recs for l in s["legs"] if l["unit"] == "MMBTU")
        g2n = p["gross_to_net"]["value"]
        eff_gross_read = led * 3.6e3 / (mmbtu * 1.05505585262 * g2n)
        eff_net_read = led * 3.6e3 / (mmbtu * 1.05505585262)
        printed = [e for s in recs for e in s["eff_net"]]
        add("diagnostic", "%s: ledger efficiency with MMBTU read as gross (PA1) / as net (PD1) vs printed SoIR" % r,
            "%.3f / %.3f vs %.3f-%.3f" % (eff_gross_read, eff_net_read, min(printed), max(printed)),
            "the gross reading nearer the printed heat rates", None,
            "evidence on how the station MMBTU should be read; the inventory reads it as net for FY2019-24")
    leak = [r for r in results if r["case"][:4] == ("FA1", "PA1", "R1", "D1")][0]
    term = _stats(model.co2e(leak["tran"]["1B2b"]) - model.co2e(leak["base"]["1B2b"]))
    add("diagnostic", "1.B.2.b term of R1-D1 under the reference leak base (feedstock outside, rc67)",
        _fmt(term["p50"]) + " Gg CO2e", "", None,
        "feedstock is reformed, not burned, so it is outside the post-meter base (IPCC 2019 Table 4.2.4k defines "
        "the factor on gas consumed in combustion); moved to a power station it enters the base. Under the "
        "membership used through rc66 (feedstock inside, retained and NOT defended) this term would be zero")
    fd1 = [r for r in results if r["case"][0] == "FA1" and r["role"] == "evidence"][0]
    omit = _stats(model.co2e(fd1["tran"]["2B1"]) - model.co2e(fd1["base"]["2B1"]))
    add("diagnostic", "what a 2.B.1-not-estimated account (FD1, superseded rc52) would omit", _fmt(omit["p50"]) + " Gg CO2e",
        "", None, "the fertilizer-side change under FA1 that FD1 would set to NE")
    add("internal", "draws", n, ">= %d for reported results" % REPORTED_DRAWS, True if n >= REPORTED_DRAWS else None,
        "deterministic: seed %d; a smaller run is labelled development_sample in every product" % SEED)
    return rows


CHECK_FIELDS = ("kind", "check", "value", "expected", "result", "note")


def source_rows(rec):
    rows = []

    def add(quantity, value, unit, status, source, used):
        rows.append({"quantity": quantity, "value": value, "unit": unit, "evidence_status": status,
                     "source": source, "used_in": used})

    for plant in sorted(rec.gas):
        g = rec.gas[plant]
        add("%s feed gas %s" % (plant, rec.year), _fmt(g["feed"]), "MMCF", "measured", g["source"], "all cases")
        add("%s fuel gas %s" % (plant, rec.year), _fmt(g["fuel"]), "MMCF", "measured", g["source"], "all cases")
        add("%s urea production %s" % (plant, rec.year), _fmt(rec.urea[plant]), "kt", "measured",
            "NFDC AFR 2024-25 Table 1 (production by manufacturer; production, not offtake)", "all cases")
        add("%s ammonia %s" % (plant, rec.year), _fmt(rec.urea[plant] * rec.params["nh3_per_urea"]["value"]),
            "kt", "reconstructed", "urea x 0.567 (stoichiometry); Fatimafert checked against its annual report",
            "FA1, FA3, 2.B.1 process air")
    add("heating value of the delivered gas", "%.1f (900-1000)" % model.hhv_mode(rec.params), "Btu/scf gross",
        "documentary_bound", "Fatima AR 2023/2024 energy index with NFDC gas per tonne; inventory 900/1000 axis",
        "FA2, every gas-to-energy conversion")
    for pw in ("R1", "R2", "R3", "D1", "D2", "D3"):
        st = rec.stations[pw]
        add("%s stations: printed fuel and net generation" % pw,
            "%d stations, %.0f GWh" % (len(st), sum(l["gwh"] for s in st for l in s["legs"])), "GWh", "measured",
            "NEPRA SoIR 2024 Tables 18/21 (plant_fuel_ledger.csv)", "PA1")
        add("%s stations: printed net heat rate" % pw, "%d values" % sum(len(s["eff_net"]) for s in st), "",
            "measured (several are contract values)", "NEPRA SoIR 2024 Tables 20/23 (plant_heat_rates.csv)", "PA2")
    for pw, entry in inputs.pathways().items():
        add("pathway %s: %s" % (pw, entry["label"]), entry["role"], "", "assumption",
            "data/shared/parameters/gas_reallocation/pathways.csv", "dimension B")
    add("which generation a new gas-fired GWh displaces", "not held", "", "NE (unidentified)",
        "no dispatch, merit-order or curtailment record is held", "replaced by explicit pathways D1-D4 and threshold T1")
    for pid, prm in sorted(rec.params.items()):
        add("parameter %s" % pid, _fmt(prm["value"]) if prm["value"] is not None else "derived",
            prm["unit"], prm["evidence_status"], prm["inventory_ref"] or prm["source"], prm["note"][:120])
    for fset, pols in sorted(rec.factors.items()):
        for pol, entry in sorted(pols.items()):
            status = "NE" if entry is None else ("screening" if "value" in entry else "sulfur balance")
            add("air factor %s %s" % (fset, pol), _fmt(entry["value"]) if entry and "value" in entry else "",
                entry["unit"] if entry and "unit" in entry else "", status,
                entry["source"] if entry else "no factor printed", "air pollutants")
    add("fertilizer process-fuel air pollutants in the inventory", "not estimated", "", "NE in the inventory",
        "data/shared/metadata/air_source_classes.csv points at an industry gas class that holds no fertilizer gas",
        "filled here by the application with EMEP 1.A.2 Table 3-3")
    add("urea prilling PM and NH3 in the inventory", "not estimated", "", "NE in the inventory",
        "AP-42 8.2 was not held; acquired 2026-10-20", "filled here by the application (screening)")
    return rows


SOURCE_FIELDS = ("quantity", "value", "unit", "evidence_status", "source", "used_in")


def banner(name, n):
    return ("PAKEMIS GAS-REALLOCATION APPLICATION - %s." % name,
            "A counterfactual calculation on the FY2023-24 records: NOT evidence that a reallocation happened "
            "or caused any trend, and not a statement of operational feasibility on any day.",
            "Every change is transition minus baseline on paired draws; negative = reduction. Gg; CO2e on AR5 "
            "GWP100 (AR6 beside). NOx as NO2. NE = not estimated, never zero.",
            "%d draws, seed %d (%s). Method: docs/gas_reallocation_application.md. Code: "
            "src/pkinv/applications/gas_reallocation/." % (n, SEED, "reported" if n >= REPORTED_DRAWS
                                                          else "DEVELOPMENT SAMPLE - not for reporting"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--draws", type=int, default=REPORTED_DRAWS)
    args = parser.parse_args(argv)
    rec, results = run_all(args.draws)
    matrix, signs = matrix_rows(results, args.draws)
    tables = (
        ("sources", "SOURCES AND COVERAGE", SOURCE_FIELDS, source_rows(rec)),
        ("flows", "PHYSICAL FLOWS AND SERVICES", FLOW_FIELDS, flow_rows(rec, results)),
        ("baselines", "BASELINE RECONSTRUCTIONS COMPARED", BASELINE_FIELDS, baseline_rows(rec, args.draws)),
        ("matrix", "CHANGES ACROSS BASELINES AND PATHWAYS", MATRIX_FIELDS, matrix),
        ("sectors", "SECTOR DECOMPOSITION OF THE CHANGE", SECTOR_FIELDS, sector_rows(results)),
        ("thresholds", "THRESHOLDS", THRESHOLD_FIELDS, threshold_rows(rec, results)),
        ("conclusions", "CONCLUSIONS UNDER THE PRE-DECLARED RULES", CONCLUSION_FIELDS, conclusion_rows(signs)),
        ("checks", "INTERNAL CONSISTENCY, INDEPENDENT AND DIAGNOSTIC CHECKS", CHECK_FIELDS,
         check_rows(rec, results, args.draws)),
    )
    for name, title, fields, rows in tables:
        write_table(_out(name), fields, [{k: r.get(k, "") for k in fields} for r in rows],
                    banner=banner(title, args.draws))
        print("wrote %s (%d rows)" % (os.path.relpath(_out(name), os.path.dirname(OUTPUTS)), len(rows)))
    failed = [r for r in tables[-1][3] if r["result"] == "FAIL"]
    for r in failed:
        print("CHECK FAILED: %s (%s)" % (r["check"], r["value"]))
    return 1 if failed else 0
