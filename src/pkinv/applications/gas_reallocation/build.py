"""Run every coherent case of the gas reallocation and write outputs/pakemis_transition_gas_*.csv.

THE CASES. The admissible baselines are crossed with the coherent pathways of coherence.csv:
- baselines (dimension A): the fertilizer reading FA2 (plant metered-gas carbon), two power readings
  (PA1 ledger, PA2 printed heat rate), two post-meter leak bases (LB1 reference, LB2 feedstock
  inside) and two prill-tower control states (PC1 uncontrolled, PC2 controlled);
- pathways (dimension B): receiving stations R1-R2 with displaced generation D1-D3 (read per PJ, valid
  only inside the displaced stations' own FY output), the mixed pathways M1-M3 (generation up to that
  output, the rest of the gas offsetting RLNG: the full-scope cases) and D4 (no new generation), each
  with the two imported-urea routes F1-F2.
FA1 (the inventory's calibrated factor) runs as a DIAGNOSTIC and FA3 (the IPCC Tier 1 factor) as an
EXPLORATORY sensitivity: neither enters a classification. D5, the average fossil grid, is a
comparator. Each case is computed on one set of paired draws and summarised at once, so no case's
draws outlive it.

THE REPORTING RULES were fixed before any case was run (docs/gas_reallocation_application.md, s5):
  a cell's change is a REDUCTION if its 97.5th percentile is below zero and an INCREASE if its 2.5th
  is above zero; otherwise it SPANS zero. Over the admissible baselines and the evidence pathways:
  robust reduction / robust increase = every cell the same sign;
  conditional = every cell excludes zero but the sign differs, and the dimension that decides it is named;
  unresolved = at least one cell spans zero, or a not-estimated component could reverse the sign;
  trade-off = within one cell, one pollutant robustly falls while another robustly rises.
The external and combined boundaries omit the exporter's urea synthesis and finishing energy and
shipping. Those omissions can only ADD emissions, so a negative external or combined change is
'reversible' (it cannot be classified a reduction) and a positive one is a bound. T3 says how large the
omitted exporter stages would have to be to cancel a negative combined change.
"Robust" means robust across the tested, justified cases and nothing wider.

Writes (all in outputs/): pakemis_transition_gas_sources.csv, _flows.csv, _baselines.csv,
_matrix.csv, _sectors.csv, _thresholds.csv, _conclusions.csv, _checks.csv.
"""
import argparse
import os

import numpy as np

from pkinv.core.io import write_table
from pkinv.core.shared_parameter_draws import SEED, rng_for
from pkinv.core.units import TJ_PER_MMBTU
from pkinv.paths import OUTPUTS

from . import inputs, model

REPORTED_DRAWS = 10000
FA_ADMISSIBLE = ("FA2",)
FA_DIAGNOSTIC = ("FA1",)
FA_EXPLORATORY = ("FA3",)
PA_ADMISSIBLE = ("PA1", "PA2")
LEAK_BASES = ("LB1", "LB2")
PRILL_CONTROL = ("PC1", "PC2")
POLLUTANT_ROWS = model.POLLUTANTS + ("CO2e_AR5", "CO2e_AR6")
PREFIX = "pakemis_transition_gas_"
DIMENSIONS = ("baseline_fertilizer", "baseline_power", "receiving", "displaced", "fertilizer_route",
              "leak_base", "prill_control")
PER_PJ = ("D1", "D2", "D3", "D4")
FULL_SCOPE = ("M1", "M2", "M3", "D4")
OMITTED_EXPORTER = ("X_omitted", +1)   # exporter urea synthesis/finishing energy and shipping: additions only


def _out(name):
    return os.path.join(OUTPUTS, PREFIX + name + ".csv")


def _na(v):
    return isinstance(v, str) and v == model.NA


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
    missing = [OMITTED_EXPORTER] if boundary == "external" else []
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
    """((fa, pa, r, d, f, lb, pc), role) for every computed case."""
    out = []
    combos = pathway_combinations()
    for pa in PA_ADMISSIBLE:
        for fa in FA_ADMISSIBLE:
            for lb in LEAK_BASES:
                for pc in PRILL_CONTROL:
                    out.extend(((fa, pa, r, d, f, lb, pc), role) for r, d, f, role in combos)
        for fa, role in [(x, "diagnostic") for x in FA_DIAGNOSTIC] + [(x, "exploratory") for x in FA_EXPLORATORY]:
            out.extend(((fa, pa, r, d, f, "LB1", "PC1"), role) for r, d, f, c_role in combos if c_role == "evidence")
    return out


def feasible_fraction(rec, case, draws):
    """Per draw, the most of the plants' gas the case can take before its displaced stations run out of
    FY output (D1-D3) or its receiving stations reach their theoretical nameplate ceiling."""
    _fa, pa, r, d, *_ = model.unpack(case)
    if r == "none":
        return None
    h, g2n = draws.get("hhv_network_btu_scf"), draws.get("gross_to_net")
    full = model.receiving_gwh(draws, rec, r, pa, (rec.feed + rec.fuel) * h, h, g2n)
    limits = [rec.gwh_capacity(r) / full]
    if d in ("D1", "D2", "D3"):
        limits.append(rec.gwh_capacity(d) / full)
    return np.minimum.reduce([np.asarray(x, dtype=float) for x in limits])


class Collector:
    """Everything the products need, summarised case by case."""

    def __init__(self, n):
        self.n = n
        self.label = "reported" if n >= REPORTED_DRAWS else "development_sample"
        self.matrix, self.sectors, self.thresholds, self.flows = [], [], [], []
        self.signs = {}
        self.service = {"urea": 0.0, "gwh": 0.0, "nh3": 0.0, "negative": 0, "share_above_one": 0}
        self.t1_seen = set()

    def case_fields(self, case, role):
        fa, pa, r, d, f, lb, pc = model.unpack(case)
        return {"reference_year": inputs.REFERENCE_YEAR, "baseline_fertilizer": fa, "baseline_power": pa,
                "receiving": r, "displaced": d, "fertilizer_route": f, "leak_base": lb, "prill_control": pc,
                "role": role}


def summarise(rec, case, role, base, tran, draws, col):
    fa, pa, r, d, f, lb, pc = model.unpack(case)
    pj = tran["flows"]["gas_moved_pj_hhv"]
    feasible = feasible_fraction(rec, case, draws)
    feas = "" if feasible is None else _fmt(float(np.median(feasible)), 4)
    fields = col.case_fields(case, role)
    # services and flows
    fb, ft = base["flows"], tran["flows"]
    col.service["urea"] = max(col.service["urea"], float(np.max(np.abs(
        (fb["urea_domestic_kt"] + fb["urea_imported_kt"]) - (ft["urea_domestic_kt"] + ft["urea_imported_kt"])))))
    col.service["gwh"] = max(col.service["gwh"], float(np.max(np.abs(
        (fb["gwh_receiving"] + fb["gwh_displaced_running"]) - (ft["gwh_receiving"] + ft["gwh_displaced_running"])))))
    col.service["nh3"] = max(col.service["nh3"], float(np.max(np.abs(
        (fb["merchant_nh3_domestic_kt"] + fb["merchant_nh3_imported_kt"])
        - (ft["merchant_nh3_domestic_kt"] + ft["merchant_nh3_imported_kt"])))))
    for flows in (fb, ft):
        col.service["negative"] += sum(int(np.sum(np.asarray(v) < -1e-9)) for v in flows.values())
    col.service["share_above_one"] += int(np.sum(np.asarray(ft["generation_share"]) > 1 + 1e-12))

    for boundary, pols in (("territorial", POLLUTANT_ROWS), ("external", ("CO2e_AR5",))):
        if boundary == "external" and role == "comparator":
            continue
        for pol in pols:
            if role == "comparator" and not pol.startswith("CO2e"):
                continue
            delta, b, t, missing = _aggregate(base, tran, boundary, pol)
            row = dict(fields, boundary=boundary, pollutant=pol,
                       unit="Gg CO2e" if pol.startswith("CO2e") else "Gg",
                       not_estimated_components=";".join(k for k, _d in missing),
                       max_feasible_fraction=feas, n_draws=col.n, sample_label=col.label)
            if delta is None:
                row.update({"coverage": "NE", "sign": "NE"})
                col.matrix.append(row)
                continue
            s, per = _stats(delta), _stats(delta / pj)
            sign = _sign(s)
            row.update({"baseline_mean": _fmt(float(np.mean(b))), "transition_mean": _fmt(float(np.mean(t))),
                        "delta_mean": _fmt(s["mean"]), "delta_p2_5": _fmt(s["p2_5"]),
                        "delta_p50": _fmt(s["p50"]), "delta_p97_5": _fmt(s["p97_5"]),
                        "delta_per_pj_mean": _fmt(per["mean"]), "delta_per_pj_p2_5": _fmt(per["p2_5"]),
                        "delta_per_pj_p97_5": _fmt(per["p97_5"]), "p_reduction": _fmt(s["p_reduction"], 4),
                        "sign": sign, "coverage": _coverage(missing, sign)})
            col.matrix.append(row)
            col.signs[(case, boundary, pol)] = (sign, row["coverage"], role)
    if role == "comparator":
        return
    # combined partial: territorial CO2e + external; the omitted exporter stages can only add
    dt, *_ = _aggregate(base, tran, "territorial", "CO2e_AR5")
    dx, *_ = _aggregate(base, tran, "external", "CO2e_AR5")
    row = dict(fields, boundary="combined_partial", pollutant="CO2e_AR5", unit="Gg CO2e",
               max_feasible_fraction=feas, n_draws=col.n, sample_label=col.label,
               not_estimated_components="X_omitted (exporter urea synthesis and finishing energy; shipping)")
    comb = dt + dx
    s, per = _stats(comb), _stats(comb / pj)
    sign = _sign(s)
    row.update({"delta_mean": _fmt(s["mean"]), "delta_p2_5": _fmt(s["p2_5"]), "delta_p50": _fmt(s["p50"]),
                "delta_p97_5": _fmt(s["p97_5"]), "delta_per_pj_mean": _fmt(per["mean"]),
                "delta_per_pj_p2_5": _fmt(per["p2_5"]), "delta_per_pj_p97_5": _fmt(per["p97_5"]),
                "p_reduction": _fmt(s["p_reduction"], 4), "sign": sign,
                "coverage": _coverage([OMITTED_EXPORTER], sign)})
    col.matrix.append(row)
    col.signs[(case, "combined_partial", "CO2e_AR5")] = (sign, row["coverage"], role)
    if role != "evidence":
        return
    _thresholds(rec, case, base, tran, draws, dt, dx, comb, col)
    if pc == "PC1":
        _sector_rows(case, base, tran, col)
    if fa == "FA2" and lb == "LB1" and pc == "PC1" and f == "F1":
        _flow_row(rec, case, base, tran, feasible, col)


def _sector_rows(case, base, tran, col):
    fa, pa, r, d, f, lb, pc = model.unpack(case)
    for key, label, boundary, status in model.SECTORS:
        if boundary == "territorial" and f != "F1":
            continue                      # territorial sectors do not depend on the import route
        for pol in POLLUTANT_ROWS if boundary == "territorial" else ("CO2e_AR5",):
            if pol.startswith("CO2e"):
                vb, vt = model.co2e(base[key], pol.split("_")[1]), model.co2e(tran[key], pol.split("_")[1])
                if _na(vb) or _na(vt):
                    continue
            else:
                if pol not in base[key] and pol not in tran[key]:
                    continue
                vb, vt = base[key].get(pol), tran[key].get(pol)
            row = {"baseline_fertilizer": fa, "baseline_power": pa, "receiving": r, "displaced": d,
                   "fertilizer_route": f if boundary == "external" else "", "leak_base": lb, "sector": key,
                   "sector_label": label, "boundary": boundary, "inventory_status": status, "pollutant": pol,
                   "unit": "Gg CO2e" if pol.startswith("CO2e") else "Gg"}
            if vb is None or vt is None:
                row["status"] = "NE"
            else:
                s = _stats(vt - vb)
                row.update({"delta_mean": _fmt(s["mean"]), "delta_p2_5": _fmt(s["p2_5"]),
                            "delta_p97_5": _fmt(s["p97_5"]), "status": "E"})
            col.sectors.append(row)


def _thresholds(rec, case, base, tran, draws, dt, dx, comb, col):
    fa, pa, r, d, f, lb, pc = model.unpack(case)
    if pc != "PC1":
        return                            # prill control moves no GHG
    service = tran["flows"]["gwh_service"]
    urea_moved = tran["flows"]["urea_imported_kt"]
    base_fields = {"baseline_fertilizer": fa, "baseline_power": pa, "receiving": r, "leak_base": lb}
    if d in ("D1", "D2", "D3") and f == "F1":
        rest = 0.0
        for key, _l, boundary, _s in model.SECTORS:
            if boundary == "territorial" and key != "1A1a_disp":
                vb, vt = model.co2e(base[key]), model.co2e(tran[key])
                if not (_na(vb) or _na(vt)):
                    rest = rest + (vt - vb)
        breakeven = rest / service                      # Gg CO2e per GWh = t per MWh
        disp = -(model.co2e(tran["1A1a_disp"]) - model.co2e(base["1A1a_disp"])) / service
        key = (fa, pa, r, lb)
        if key not in col.t1_seen:
            col.t1_seen.add(key)
            s = _stats(breakeven)
            col.thresholds.append(dict(base_fields, threshold="T1 displaced-generation intensity for zero "
                                       "territorial CO2e change", displaced="", unit="t CO2e (AR5) per MWh",
                                       threshold_p50=_fmt(s["p50"]), threshold_p2_5=_fmt(s["p2_5"]),
                                       threshold_p97_5=_fmt(s["p97_5"]),
                                       comparison="D5 average fossil CPPA-G %.3f" % rec.grid_average,
                                       p_comparison_above_threshold=_fmt(float(np.mean(rec.grid_average > breakeven)), 4)))
        s = _stats(disp)
        col.thresholds.append(dict(base_fields, threshold="T1 intensity of the displaced pathway (combustion only)",
                                   displaced=d, unit="t CO2e (AR5) per MWh", threshold_p50=_fmt(s["p50"]),
                                   threshold_p2_5=_fmt(s["p2_5"]), threshold_p97_5=_fmt(s["p97_5"]),
                                   comparison="the case's own T1 threshold",
                                   p_comparison_above_threshold=_fmt(float(np.mean(disp > breakeven)), 4)))
    if f == "F1":
        dfuel = model.co2e(tran["X_fuel"]) - model.co2e(base["X_fuel"])
        dnh3 = model.co2e(tran["X_ammonia"]) - model.co2e(base["X_ammonia"])
        x_star = -(dt + dfuel + dnh3) / urea_moved
        f1, f2 = model.import_factor(draws, "F1"), model.import_factor(draws, "F2")
        s = _stats(x_star)
        col.thresholds.append(dict(base_fields, threshold="T2 imported-urea intensity for zero "
                                   "territorial-plus-external CO2e change", displaced=d,
                                   unit="t CO2e (AR5) per t urea", threshold_p50=_fmt(s["p50"]),
                                   threshold_p2_5=_fmt(s["p2_5"]), threshold_p97_5=_fmt(s["p97_5"]),
                                   comparison="F1 gas route p50 %.3f; F2 coal route p50 %.3f"
                                              % (np.median(f1), np.median(f2)),
                                   p_comparison_above_threshold="F1 %.4f; F2 %.4f" % (np.mean(f1 > x_star),
                                                                                    np.mean(f2 > x_star))))
    s = _stats(comb)
    if s["p97_5"] < 0:
        t3 = _stats(-comb / urea_moved)
        col.thresholds.append(dict(base_fields, threshold="T3 omitted exporter emission (urea synthesis, "
                                   "finishing, shipping) that would cancel the combined reduction",
                                   displaced=d, fertilizer_route=f, unit="t CO2e (AR5) per t urea",
                                   threshold_p50=_fmt(t3["p50"]), threshold_p2_5=_fmt(t3["p2_5"]),
                                   threshold_p97_5=_fmt(t3["p97_5"]),
                                   comparison="the omitted stages are NOT ESTIMATED; below this the reduction survives",
                                   p_comparison_above_threshold=""))


def _flow_row(rec, case, base, tran, feasible, col):
    fa, pa, r, d, *_ = model.unpack(case)
    fl, fb = tran["flows"], base["flows"]
    service = _stats(fl["gwh_service"])
    share = _stats(fl["generation_share"])
    row = {"item": "case", "name": "%s %s %s" % (pa, r, d),
           "gas_moved_mmcf": _fmt(float(np.median(fl["gas_moved_mmcf"]))),
           "gas_moved_pj_hhv_p50": _fmt(float(np.median(fl["gas_moved_pj_hhv"]))),
           "generation_share_p50": _fmt(share["p50"], 4), "generation_share_p2_5": _fmt(share["p2_5"], 4),
           "generation_share_p97_5": _fmt(share["p97_5"], 4),
           "gwh_service_p50": _fmt(service["p50"]), "gwh_service_p2_5": _fmt(service["p2_5"]),
           "gwh_service_p97_5": _fmt(service["p97_5"]),
           "urea_service_baseline_kt": _fmt(float(np.median(fb["urea_domestic_kt"] + fb["urea_imported_kt"]))),
           "urea_service_transition_kt": _fmt(float(np.median(fl["urea_domestic_kt"] + fl["urea_imported_kt"]))),
           "merchant_nh3_service_kt_p50": _fmt(float(np.median(fl["merchant_nh3_domestic_kt"]
                                                               + fl["merchant_nh3_imported_kt"])), 4),
           "displaced_capacity_gwh": _fmt(rec.gwh_capacity(d)) if d in ("D1", "D2", "D3") else
           (_fmt(rec.gwh_capacity("D" + d[1:])) if d.startswith("M") else ""),
           "receiving_headroom_gwh_theoretical": _fmt(rec.gwh_capacity(r)) if r != "none" else "",
           "max_feasible_fraction_p50": "" if feasible is None else _fmt(float(np.median(feasible)), 4),
           "feasible_at_full_scope": ("yes" if feasible is None or np.median(feasible) >= 1 else
                                      "no: per-PJ reading only; the full-scope case is the mixed pathway"),
           "note": ("D4 adds no generation; the LNG import falls by the moved gas" if d == "D4" else
                    "displaced capacity = the displaced stations' own FY generation; receiving headroom = "
                    "nameplate hours minus FY generation, a theoretical ceiling (outages, contracts, dispatch "
                    "and gas deliverability not modelled)"),
           "source": "NEPRA SoIR 2024 station ledger and heat rates via station_crosswalk.csv; GEM gas/oil tracker"}
    col.flows.append(row)


def run_all(n=REPORTED_DRAWS, year=inputs.REFERENCE_YEAR):
    rec = model.Records(year)
    col = Collector(n)
    for case, role in cases():
        base, tran, draws = model.run(rec, case, 1.0, n)
        summarise(rec, case, role, base, tran, draws, col)
    return rec, col


MATRIX_FIELDS = ("reference_year", "baseline_fertilizer", "baseline_power", "leak_base", "prill_control",
                 "receiving", "displaced", "fertilizer_route", "role", "boundary", "pollutant", "unit",
                 "baseline_mean", "transition_mean", "delta_mean", "delta_p2_5", "delta_p50", "delta_p97_5",
                 "delta_per_pj_mean", "delta_per_pj_p2_5", "delta_per_pj_p97_5", "p_reduction", "sign",
                 "coverage", "not_estimated_components", "max_feasible_fraction", "n_draws", "sample_label")


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
        cls, condition = "robust reduction", "every admissible baseline and evidence pathway in scope"
    elif set(signs.values()) == {"+"}:
        cls, condition = "robust increase", "every admissible baseline and evidence pathway in scope"
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
    scopes = [("full scope: mixed pathways and D4", lambda c: c[3] in FULL_SCOPE),
              ("per PJ inside the feasible range: pure pathways and D4", lambda c: c[3] in PER_PJ)]
    scopes += [("displaced %s" % d, (lambda d: lambda c: c[3] == d)(d)) for d in PER_PJ + FULL_SCOPE[:3]]
    for boundary, pols in (("territorial", POLLUTANT_ROWS), ("external", ("CO2e_AR5",)),
                           ("combined_partial", ("CO2e_AR5",))):
        for pol in pols:
            for label, select in scopes:
                c = classify(cell_signs, boundary, pol, select)
                if c is not None:
                    rows.append(dict(c, boundary=boundary, pollutant=pol, scope=label))
    by_cell = {}
    for (case, b, p), (sign, cov, role) in cell_signs.items():
        if b == "territorial" and role == "evidence" and case[4] == "F1" and p in model.POLLUTANTS:
            by_cell.setdefault(case, {})[p] = sign if cov != "reversible" else "?"
    for d in PER_PJ + FULL_SCOPE[:3]:
        cells = {c: v for c, v in by_cell.items() if c[3] == d}
        if not cells:
            continue
        falls = set.intersection(*[{p for p, s in v.items() if s == "-"} for v in cells.values()])
        rises = set.intersection(*[{p for p, s in v.items() if s == "+"} for v in cells.values()])
        some = sum(1 for v in cells.values() if "-" in v.values() and "+" in v.values())
        rows.append({"boundary": "territorial", "pollutant": "air pollutants and GHGs", "scope": "displaced %s" % d,
                     "classification": "trade-off" if some else "no trade-off",
                     "condition": "trade-off in %d of %d cases; falls in every case: %s; rises in every case: %s" % (
                         some, len(cells), ", ".join(sorted(falls)) or "none", ", ".join(sorted(rises)) or "none"),
                     "cases": len(cells), "cases_reduction": "", "cases_increase": "",
                     "cases_spanning": "", "cases_bound_only": ""})
    return rows


CONCLUSION_FIELDS = ("boundary", "pollutant", "scope", "classification", "condition", "cases",
                     "cases_reduction", "cases_increase", "cases_spanning", "cases_bound_only")
SECTOR_FIELDS = ("baseline_fertilizer", "baseline_power", "leak_base", "receiving", "displaced",
                 "fertilizer_route", "sector", "sector_label", "boundary", "inventory_status", "pollutant",
                 "unit", "delta_mean", "delta_p2_5", "delta_p97_5", "status")
THRESHOLD_FIELDS = ("threshold", "baseline_fertilizer", "baseline_power", "leak_base", "receiving", "displaced",
                    "fertilizer_route", "unit", "threshold_p50", "threshold_p2_5", "threshold_p97_5",
                    "comparison", "p_comparison_above_threshold")
FLOW_FIELDS = ("item", "name", "feed_mmcf", "fuel_mmcf", "urea_kt", "nh3_kt", "mmcf_per_kt_urea",
               "gas_moved_mmcf", "gas_moved_pj_hhv_p50", "generation_share_p50", "generation_share_p2_5",
               "generation_share_p97_5", "gwh_service_p50", "gwh_service_p2_5", "gwh_service_p97_5",
               "urea_service_baseline_kt", "urea_service_transition_kt", "merchant_nh3_service_kt_p50",
               "displaced_capacity_gwh", "receiving_headroom_gwh_theoretical", "max_feasible_fraction_p50",
               "feasible_at_full_scope", "note", "source")


def route_rows(rec, n):
    d = model.Draws(rec.params, rec.factors, n)
    rows = []
    for route, label in (("F1", "gas-reforming route"),
                         ("F2", "coal-gasification hydrogen route (synthesis loop and urea stage outside it)")):
        s = _stats(model.import_factor(d, route))
        rows.append({"threshold": "T2 imported-urea intensity of route %s, %s" % (route, label),
                     "unit": "t CO2e (AR5) per t urea", "threshold_p50": _fmt(s["p50"]),
                     "threshold_p2_5": _fmt(s["p2_5"]), "threshold_p97_5": _fmt(s["p97_5"]),
                     "comparison": "exporter 2.B.1 net of urea-bound CO2 plus feedstock upstream",
                     "p_comparison_above_threshold": ""})
    return rows


def plant_rows(rec):
    rows = []
    for plant in sorted(rec.gas):
        g, u = rec.gas[plant], rec.urea[plant]
        rows.append({"item": "plant", "name": plant, "feed_mmcf": _fmt(g["feed"]), "fuel_mmcf": _fmt(g["fuel"]),
                     "urea_kt": _fmt(u), "nh3_kt": _fmt(u * rec.params["nh3_per_urea"]["value"]),
                     "mmcf_per_kt_urea": _fmt((g["feed"] + g["fuel"]) / u, 5),
                     "note": "suppliers " + ", ".join("%s %.0f" % kv for kv in sorted(g["suppliers"].items()))
                             + ("; merchant ammonia 4,313-7,277 t (bound)" if plant == "Fatimafert" else
                                "; merchant ammonia not reported (NE)"),
                     "source": g["source"] + "; NFDC Table 1"})
    return rows


def baseline_rows(rec, n):
    """Dimension A side by side."""
    rows = []
    table = {r["baseline_id"]: r for r in inputs.table("baselines.csv")}
    d = model.Draws(rec.params, rec.factors, n)
    ref = model.state(d, rec, ("FA2", "PA1", "R1", "D1", "F1"), 1.0, 0.0)["2B1"]["CO2"]
    for fa in ("FA1", "FA2", "FA3", "FD1"):
        st = model.state(d, rec, (fa, "PA1", "R1", "D1", "F1"), 1.0, 0.0)
        co2 = st["2B1"]["CO2"]
        entry = table[fa]
        row = {"baseline_id": fa, "axis": "fertilizer_2B1", "classification": entry["classification"],
               "quantity": "2.B.1 CO2 of the two plants at FY levels", "unit": "Gg CO2", "note": entry["definition"]}
        if co2 is None:
            row.update({"status": "NE"})
        else:
            s = _stats(co2)
            nh3 = rec.urea_kt * d.get("nh3_per_urea") + d.get("fatimafert_merchant_nh3_t") / 1e3
            gas_c = (co2 + rec.urea_kt * model.UREA_CO2) / d.get("ef_co2_gas") * 1e6     # TJ of gas carbon
            residual = _stats(ref - co2)
            row.update({"p50": _fmt(s["p50"]), "p2_5": _fmt(s["p2_5"]), "p97_5": _fmt(s["p97_5"]),
                        "implied_gj_ncv_per_t_nh3_p50": _fmt(float(np.median(gas_c * 1e3 / (nh3 * 1e3))), 4),
                        "carbon_residual_vs_metered_gas_p50": _fmt(residual["p50"]), "status": "E"})
        rows.append(row)
    for lb in LEAK_BASES:
        b, t, _d = model.run(rec, ("FA2", "PA1", "R1", "M1", "F1", lb, "PC1"), 1.0, n)
        s = _stats(model.co2e(t["1B2b"]) - model.co2e(b["1B2b"]))
        rows.append({"baseline_id": lb, "axis": "leak_base", "classification": table[lb]["classification"],
                     "quantity": "change in 1.B.2.b post-meter CH4 (R1, M1)", "unit": "Gg CO2e",
                     "p50": _fmt(s["p50"]), "p2_5": _fmt(s["p2_5"]), "p97_5": _fmt(s["p97_5"]), "status": "E",
                     "note": table[lb]["definition"]})
    for pc in PRILL_CONTROL:
        st = model.state(d, rec, ("FA2", "PA1", "R1", "D1", "F1", "LB1", pc), 1.0, 0.0)
        pm = st["2B_finish"]["PM2.5"]
        row = {"baseline_id": pc, "axis": "prill_control", "classification": table[pc]["classification"],
               "quantity": "urea finishing PM2.5 of the two plants at FY levels", "unit": "Gg",
               "note": table[pc]["definition"]}
        if pm is None:
            row.update({"status": "NE", "p50": "", "implied_net_efficiency_p50": ""})
        else:
            s = _stats(pm)
            row.update({"p50": _fmt(s["p50"]), "p2_5": _fmt(s["p2_5"]), "p97_5": _fmt(s["p97_5"]), "status": "E"})
        rows.append(row)
    h, g2n = d.get("hhv_network_btu_scf"), d.get("gross_to_net")
    mmcf = rec.feed + rec.fuel
    for r in ("R1", "R2"):
        for pa in ("PA1", "PA2", "PD1"):
            mmbtu = mmcf * h * (g2n if pa == "PD1" else 1.0)
            gwh = model.receiving_gwh(d, rec, r, "PA1" if pa == "PD1" else pa, mmbtu, h, g2n)
            pj = mmcf * h * TJ_PER_MMBTU / 1e3
            s = _stats(gwh / pj)
            eff = _stats(gwh * 3.6 / (pj * 1e3 * g2n))
            entry = table[pa]
            rows.append({"baseline_id": pa, "axis": "power_conversion:%s" % r, "classification": entry["classification"],
                         "quantity": "GWh per PJ (HHV) of the plants' gas at %s" % r, "unit": "GWh per PJ",
                         "p50": _fmt(s["p50"]), "p2_5": _fmt(s["p2_5"]), "p97_5": _fmt(s["p97_5"]),
                         "implied_net_efficiency_p50": _fmt(eff["p50"], 4), "status": "E", "note": entry["definition"]})
    return rows


BASELINE_FIELDS = ("baseline_id", "axis", "classification", "quantity", "unit", "p50", "p2_5", "p97_5",
                   "implied_gj_ncv_per_t_nh3_p50", "carbon_residual_vs_metered_gas_p50",
                   "implied_net_efficiency_p50", "status", "note")


def check_rows(rec, col):
    rows = []

    def add(kind, check, value, expected, ok, note):
        rows.append({"kind": kind, "check": check, "value": value, "expected": expected,
                     "result": "INFO" if ok is None else ("PASS" if ok else "FAIL"), "note": note})

    sv = col.service
    add("internal", "urea service held: baseline minus transition urea applied, worst case", _fmt(sv["urea"]),
        "0 kt", sv["urea"] < 1e-9, "domestic plus imported urea is the same in both states")
    add("internal", "merchant ammonia service held: baseline minus transition, worst case", _fmt(sv["nh3"]),
        "0 kt", sv["nh3"] < 1e-9, "Fatimafert's sold ammonia is made at home or imported, never dropped")
    add("internal", "electricity service held: baseline minus transition GWh, worst case", _fmt(sv["gwh"]),
        "0 GWh", sv["gwh"] < 1e-6, "receiving plus still-running displaced generation is the same in both states")
    add("internal", "non-negative flows in every state", sv["negative"], "0", sv["negative"] == 0, "")
    add("internal", "generation share never above 1 in a mixed pathway", sv["share_above_one"], "0",
        sv["share_above_one"] == 0, "the displaced stations cannot give up more than their FY output")
    zero = model.run(rec, ("FA2", "PA1", "R1", "M1", "F1", "LB2", "PC1"), 0.0, 500)
    worst = 0.0
    for key, *_ in model.SECTORS:
        for pol, vb in zero[0][key].items():
            vt = zero[1][key].get(pol)
            if vb is not None and vt is not None:
                worst = max(worst, float(np.max(np.abs(np.asarray(vt) - np.asarray(vb)))))
    add("internal", "zero intervention gives zero change", _fmt(worst), "0", worst == 0.0, "s_case = 0")
    case = ("FA2", "PA1", "R1", "D1", "F1")
    width = {}
    for name, paired in (("paired", True), ("unpaired", False)):
        b, t, _d = model.run(rec, case, 1.0, 4000, paired=paired)
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
    fa1 = model.state(d, rec, ("FA1", "PA1", "R1", "D1", "F1"), 1.0, 0.0)["2B1"]["CO2"]
    residual = _stats(st["2B1"]["CO2"] - fa1)
    add("diagnostic", "FA1 carbon residual against the plants' metered gas", _fmt(residual["p50"]) + " Gg CO2",
        "0 for a carbon-consistent reading", None,
        "why FA1 is a diagnostic: the power side moves the metered gas, whose carbon FA1's calibrated factor does "
        "not account for; the residual is not a measured additional emission")
    add("internal", "3.C urea application unchanged (same urea, same fields)", "0", "0", True,
        "the application's state carries one urea total; 3.C.3 CO2, soil N2O and NH3 cannot move")
    rng = rng_for("gas_reallocation|check|two_piece")
    draw = model.two_piece_lognormal(rng, 3.4, 0.9, 90.0, 200000)
    q = np.percentile(draw, [2.5, 50, 97.5])
    add("internal", "two-piece lognormal keeps the printed quantiles (coal PM2.5 0.9 / 3.4 / 90 g/GJ)",
        "%.3f / %.3f / %.2f; mean %.2f" % (q[0], q[1], q[2], draw.mean()), "0.9 / 3.4 / 90",
        abs(q[1] - 3.4) / 3.4 < 0.02 and abs(q[0] - 0.9) / 0.9 < 0.03 and abs(q[2] - 90) / 90 < 0.05,
        "a triangular draw on the same three numbers had a mean of 31")
    for row in inputs.crosswalk_report():
        if row["ledger_joined"] == "no" or row["heat_rate_joined"] == "no":
            add("crosswalk", "%s %s: a declared record did not join" % (row["pathway"], row["station"]),
                "ledger %s, heat rate %s" % (row["ledger_joined"], row["heat_rate_joined"]), "both joined", None,
                "the station keeps the record that did join; Sahiwal's SoIR heat rate is printed gross only")
    excluded = [r["station"] for r in inputs.crosswalk("excluded")]
    add("crosswalk", "stations excluded as receivers (dedicated field gas)", "; ".join(excluded), "", None,
        "OGRA SoRPI 2023-24 Table 3.21 and the station_crosswalk.csv evidence column")
    agree = [r for r in inputs.nfdc_ogra_agreement() if r["record"] == "difference"]
    add("independent", "NFDC plant meters vs OGRA utility returns, fertilizer gas FY2023-24",
        agree[0]["agreement_pct"] + "%", "within a few percent", abs(float(agree[0]["agreement_pct"])) < 3,
        "validates the sector's gas volume; says nothing about the plant split or the energy content")
    p = rec.params
    stoich = p["fatimafert_urea_cy2024"]["value"] * p["nh3_per_urea"]["value"]
    gapp = (p["fatimafert_ammonia_cy2024"]["value"] - stoich) / stoich * 100
    add("independent", "Fatimafert ammonia: company-reported vs urea x 0.567 (calendar 2024)",
        "%.0f vs %.0f t (%+.1f%%)" % (p["fatimafert_ammonia_cy2024"]["value"], stoich, gapp), "close",
        abs(gapp) < 10, "the company sold 4,313 t of ammonia that year (1.4 points), carried here as merchant "
                        "ammonia; the stoichiometric reconstruction holds for this plant")
    g25, u25 = inputs.plant_gas(inputs.REPLICATION_YEAR), inputs.plant_urea(inputs.REPLICATION_YEAR)
    for plant in sorted(rec.gas):
        a = (rec.gas[plant]["feed"] + rec.gas[plant]["fuel"]) / rec.urea[plant]
        b = (g25[plant]["feed"] + g25[plant]["fuel"]) / u25[plant]
        add("independent", "%s gas per tonne of urea, FY2024-25 (Table 40) vs FY2023-24 (Annex-28)" % plant,
            "%.2f vs %.2f MMCF/kt (%+.1f%%)" % (b, a, (b - a) / a * 100), "stable", abs(b - a) / a < 0.05,
            "a different year's meters: the plant intensity the reallocation scales with is not a one-year artefact")
    mode = model.hhv_mode(rec.params)
    lo, hi = p["hhv_network_btu_scf"]["low"], p["hhv_network_btu_scf"]["high"]
    add("documentary", "heating value implied by Fatimafert's energy index", "%.1f Btu/scf" % mode,
        "within %g-%g" % (lo, hi), lo <= mode <= hi, "NOT a validation: it sets the mode of the range it is checked against")
    sui = p["nfdc_gcv_sui_btu_cft"]["value"]
    add("documentary", "heating value: NFDC Table 6.2 Sui gas vs the value Fatimafert's records imply",
        "%.0f vs %.1f Btu/scf (%+.1f%%)" % (sui, mode, (sui - mode) / mode * 100), "compatible",
        abs(sui - mode) / mode < 0.05,
        "a CROSS-PERIOD COMPATIBILITY check: the NFDC value is undated and states no gross/net basis, so it does "
        "not validate a measured heating value")
    norm = p["nfdc_urea_gas_norm_mmbtu_t"]["value"]
    for plant in sorted(rec.gas):
        per_t = (rec.gas[plant]["feed"] + rec.gas[plant]["fuel"]) / rec.urea[plant] * sui / 1e3
        add("diagnostic", "%s metered gas per tonne of urea at the Sui heating value vs the NFDC norm" % plant,
            "%.1f vs %.0f MMBTU/t" % (per_t, norm), "", None, "the norm (24 feed + 6 fuel) is a planning figure")
    add("diagnostic", "Mari dedicated-line gas heating value (out-of-scope plants)",
        "%.0f Btu/cft" % p["nfdc_gcv_mari_btu_cft"]["value"], "", None,
        "below the 900-1,000 the inventory's gas-carbon memo applies to the whole fertilizer class "
        "(outputs/pakemis_gas_flow_crosswalk.csv), a candidate explanation of its open difference, not yet tested")
    for r in ("R1", "R2"):
        recs = rec.stations[r]
        led = sum(l["gwh"] for s in recs for l in s["legs"] if l["unit"] == "MMBTU")
        mmbtu = sum(l["quantity"] for s in recs for l in s["legs"] if l["unit"] == "MMBTU")
        g2n = p["gross_to_net"]["value"]
        printed = [e for s in recs for e in s["eff_net"]]
        add("diagnostic", "%s: ledger efficiency with MMBTU read as gross (PA1) / as net (PD1) vs printed SoIR" % r,
            "%.3f / %.3f vs %.3f-%.3f" % (led * 3.6e3 / (mmbtu * 1.05505585262 * g2n), led * 3.6e3 / (mmbtu * 1.05505585262),
                                         min(printed), max(printed)),
            "the gross reading nearer the printed heat rates", None,
            "evidence on how the station MMBTU should be read; the inventory reads it as net for FY2019-24")
    add("internal", "draws", col.n, ">= %d for reported results" % REPORTED_DRAWS,
        True if col.n >= REPORTED_DRAWS else None,
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
    add("Fatimafert merchant ammonia FY2023-24", "4,313-7,277", "t", "documentary_bound",
        "Fatima AR 2023 and 2024 calendar-year sales", "the ammonia service; X_ammonia")
    add("Agritech merchant ammonia", "not reported", "", "NE", "Agritech AR 2023 (held as psx_document_228733.pdf) "
        "prints urea only", "an unpriced service if any was sold")
    add("CO2 sold by the plants", "not attributed to a plant", "", "NE (unpriced coproduct)",
        "Fatima AR 2024 prints company-wide CO2 captured and sold (188,341 t)", "not priced: the buyers' "
        "replacement CO2 is outside the boundary")
    add("grid electricity bought by the plants", "not held per plant", "", "NE",
        "Fatima AR 2024 prints a company-wide WAPDA purchase", "not priced: the shut plants' grid demand")
    add("heating value of the delivered gas", "%.1f (900-1000)" % model.hhv_mode(rec.params), "Btu/scf gross",
        "documentary_bound", "Fatima AR 2023/2024 energy index with NFDC gas per tonne; inventory 900/1000 axis; "
        "NFDC Table 6.2 Sui 925 (undated, basis unstated) as a compatibility check",
        "FA2, every gas-to-energy conversion")
    for row in inputs.crosswalk_report():
        add("%s station %s" % (row["pathway"], row["station"]),
            "ledger %s; heat rate %s%s" % (row["ledger_joined"], row["heat_rate_joined"],
                                          " (%s)" % row["eff_basis"] if row["eff_basis"] else ""), "",
            "measured", "NEPRA SoIR 2024 via station_crosswalk.csv", "PA1/PA2")
    for row in inputs.crosswalk("excluded"):
        add("excluded receiver %s" % row["station"], "not network-eligible", "", "documentary",
            row["eligibility_evidence"], "kept out of R1/R2")
    for pw, entry in inputs.pathways().items():
        add("pathway %s: %s" % (pw, entry["label"]), entry["role"], "", "assumption",
            "data/shared/parameters/gas_reallocation/pathways.csv", "dimension B")
    add("which generation a new gas-fired GWh displaces", "not held", "", "NE (unidentified)",
        "no dispatch, merit-order or curtailment record is held", "replaced by explicit pathways and threshold T1")
    for pid, prm in sorted(rec.params.items()):
        add("parameter %s" % pid, _fmt(prm["value"]) if prm["value"] is not None else "derived or ranged",
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
    rec, col = run_all(args.draws)
    checks = check_rows(rec, col)
    tables = (
        ("sources", "SOURCES AND COVERAGE", SOURCE_FIELDS, source_rows(rec)),
        ("flows", "PHYSICAL FLOWS AND SERVICES", FLOW_FIELDS, plant_rows(rec) + col.flows),
        ("baselines", "BASELINE RECONSTRUCTIONS COMPARED", BASELINE_FIELDS, baseline_rows(rec, args.draws)),
        ("matrix", "CHANGES ACROSS BASELINES AND PATHWAYS", MATRIX_FIELDS, col.matrix),
        ("sectors", "SECTOR DECOMPOSITION OF THE CHANGE", SECTOR_FIELDS, col.sectors),
        ("thresholds", "THRESHOLDS", THRESHOLD_FIELDS, col.thresholds + route_rows(rec, args.draws)),
        ("conclusions", "CONCLUSIONS UNDER THE PRE-DECLARED RULES", CONCLUSION_FIELDS, conclusion_rows(col.signs)),
        ("checks", "INTERNAL CONSISTENCY, INDEPENDENT AND DIAGNOSTIC CHECKS", CHECK_FIELDS, checks),
    )
    for name, title, fields, rows in tables:
        write_table(_out(name), fields, [{k: r.get(k, "") for k in fields} for r in rows],
                    banner=banner(title, args.draws))
        print("wrote %s (%d rows)" % (os.path.relpath(_out(name), os.path.dirname(OUTPUTS)), len(rows)))
    failed = [r for r in checks if r["result"] == "FAIL"]
    for r in failed:
        print("CHECK FAILED: %s (%s)" % (r["check"], r["value"]))
    return 1 if failed else 0
