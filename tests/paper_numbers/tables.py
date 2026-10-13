"""The table expectations: NATIONAL_TABLES and TABLES with their row builders.

Split from tests/test_paper_numbers.py in rc35; the shim of that name
re-exports the data and helpers. Test modules import only from the four data
modules (_common, doc_claims, tables, quantity_policy), never from each other.
"""
import collections
import csv
import io
import filecmp
import glob
import json
import math
import os
import re
import sys
import unittest

from pkinv import paths
from pkinv.core.io import read_rows
from paper_numbers._common import (
    OUT,
    _cell,
    _data_rows,
    _doc_path,
    _first_where,
    _rows,
    _sector,
    _sector_row,
    _sum_prefix,
    _sum_where,
    _transport_year,
    _waste_year)
from paper_numbers.doc_claims import (
    _agri_districttop_rows,
    _air_kt,
    _bench,
    _ef,
    _keycat,
    _mc,
    _notation,
    _power_keycat_rows,
    _wpar)


def _bench_ratio_withheld(source, category, year=None):
    """Whether the register forbids a ratio for this row, so the table prints a dash."""
    for r in _rows("national_benchmark_comparison.csv"):
        if (r["source"] == source and r["engine_category"] == category
                and (year is None or r["year"] == str(year))):
            return r["ratio_engine_over_benchmark"] == ""
    raise KeyError((source, category, year))


def _constrained_round(cells, total, dp=2):
    """Largest-remainder rounding: `cells` at `dp` decimals, summing EXACTLY to
    round(total, dp).

    Independent rounding printed 157.31 + 248.58 + 42.12 = 448.01 beside a bolded 448.00
    in a paper whose central claim is exact closure. Each cell was within half an ulp of
    the engine -- the per-cell comparator was satisfied -- and the row was not. So the
    displayed row is now a deterministic function of the unrounded values: floor every
    cell at dp, then distribute the shortfall to the largest remainders, ties broken by
    column order. The shortfall is never negative because the hidden (dashed,
    sub-threshold) mass is non-negative; a cell moves by at most one trailing digit.
    """
    scale = 10 ** dp
    target = int(round(round(total, dp) * scale))
    floors = [int(math.floor(c * scale + 1e-9)) for c in cells]
    remainders = [c * scale - f for c, f in zip(cells, floors)]
    shortfall = target - sum(floors)
    assert 0 <= shortfall <= len(cells) + 1, (cells, total, shortfall)
    out = list(floors)
    for i in sorted(range(len(cells)), key=lambda i: (-remainders[i], i))[:shortfall]:
        out[i] += 1
    return [v / scale for v in out]


def _aviation_two_year_rows():
    """tab:two-year: one row per carrier component, FY2022-23 and FY2023-24 side by
    side, from the component comparison the engine publishes."""
    rows = []
    for component in ("resident", "foreign", "combined"):
        cells = []
        for year in ("2022", "2023"):
            r = next(x for x in _rows("aviation_annual_component_comparison.csv")
                     if x["fiscal_year"] == year and x["component"] == component)
            cells += [float(r["ocac_jp1_t"]) / 1000.0, float(r["ocac_co2_t"]) / 1000.0,
                      float(r["oecd_co2_t"]) / 1000.0, float(r["ratio"])]
        rows.append(cells)
    return rows


def _aviation_bridge_rows():
    """tab:source-bridge under the OECD-calibrated resident share, dashes dropped; the
    two 100LL source rows print as one line and the totals close over the columns."""
    rows = {(r["customer_category"], r["fuel_type"]): r
            for r in _rows("aviation_bridge_source_rows_all_scenarios.csv")
            if r["fiscal_year"] == "2023"
            and r["scenario"] == "carrier_common_resident_share"}

    def take(cat, fuel, cols):
        r = rows[(cat, fuel)]
        return [float(r[c]) for c in cols]

    ll = [rows[k] for k in rows if k[1] == "100LL"]
    ll_total = sum(float(r["reported_t"]) for r in ll)
    ga_total = sum(float(r["general_aviation"]) for r in ll)
    out = [
        take("Domestic Avi-PIA", "JP-1",
             ("reported_t", "ipcc_domestic", "international_bunker")),
        take("Domestic Avi-Others", "JP-1",
             ("reported_t", "ipcc_domestic", "international_bunker")),
        take("Overseas/Foreign Aviation", "JP-1",
             ("reported_t", "international_bunker")),
        take("Government Aviation", "JP-1", ("reported_t", "military_1a5b")),
        take("Government Other", "JP-1", ("reported_t", "residual")),
        take("Government Other", "JP-8", ("reported_t", "military_1a5b")),
        [ll_total, ga_total],
    ]
    all_rows = list(rows.values())
    out.append([sum(float(r["reported_t"]) for r in all_rows),
                sum(float(r["ipcc_domestic"]) for r in all_rows),
                sum(float(r["international_bunker"]) for r in all_rows),
                sum(float(r["military_1a5b"]) for r in all_rows),
                sum(float(r["general_aviation"]) for r in all_rows),
                sum(float(r["residual"]) for r in all_rows)])
    return out


def _aviation_estimate_rows():
    """tab:bridge-results: each estimator's fuel and CO2 from the output that owns it."""
    def model(name):
        r = next(x for x in _rows("aviation_model_resolution_fy2023_24.csv")
                 if x["fiscal_year"] == "2023" and x["model"] == name)
        return [float(r["fuel_t"]), float(r["co2_kt"])]

    def bridge(name):
        r = next(x for x in _rows("aviation_reconciliation_fy2023_24.csv")
                 if x["fiscal_year"] == "2023" and x["scenario"] == name)
        return [float(r["domestic_fuel_t"]), float(r["domestic_co2_Gg"])]

    m2_fuel = float(next(x for x in _rows("aviation_common_support_ladder.csv")
                         if x["experiment"] == "coverage_completion"
                         and x["step"] == "completed_total")["fuel_t"])
    m2_co2 = float(next(x for x in _rows("aviation_uncertainty_sensitivity.csv")
                        if x["variable"] == "Jet-fuel carbon conversion")
                   ["central_co2_t"]) / 1000.0
    oecd = float(next(x for x in _rows("aviation_two_year_replication.csv")
                      if x["fiscal_year"] == "2023")["oecd_domestic_co2_t"]) / 1000.0
    return [model("aggregate_movement"), model("route_resolved"),
            bridge("flight_fuel_weighted"), bridge("movement_count"),
            model("ocac_constrained_literal_customer"),
            [m2_fuel, m2_co2], [oecd]]


def _fugitives_segment_rows():
    """tab:segments from the per-segment native-gas aggregate, in the printed (CO2e
    descending) order, with the N2O column in tonnes and the closing total row."""
    rows = sorted(_rows("fugitives_segment_native_gases_2024.csv"),
                  key=lambda r: -float(r["co2e_Mt_AR5"]))
    out = [[float(r["ch4_Gg"]), float(r["co2_Gg"]), float(r["n2o_Gg"]) * 1000.0,
            float(r["co2e_Mt_AR5"]), float(r["share_pct"])] for r in rows]
    out.append([sum(float(r["ch4_Gg"]) for r in rows),
                sum(float(r["co2_Gg"]) for r in rows),
                sum(float(r["n2o_Gg"]) for r in rows) * 1000.0,
                sum(float(r["co2e_Mt_AR5"]) for r in rows),
                sum(float(r["share_pct"]) for r in rows)])
    return out


def _category_gas_rows(labelled=False):
    """Rows of tab:categorygas: the three gases and the total per IPCC code, largest first,
    with cells below the table's own 0.005 Mt threshold omitted because the table dashes
    them. The TOTAL row's four bolded figures close the list. `labelled` pairs each row
    with the IPCC code it prints first ("Total" for the last), for the label-aware registry.

    Gas cells come back CONSTRAINED-ROUNDED to two decimals (see _constrained_round), so
    the generic half-ulp comparator becomes exact for them: a plainly-rounded 157.31
    against the constrained 157.30 is off by a full ulp and fails. Row totals stay
    unrounded; the printed total is plain rounding, which the comparator already checks.
    """
    rows = _rows("national_category_gas.csv")
    agg = {}
    for r in rows:
        d = agg.setdefault(r["ipcc_code"], {"CO2": 0.0, "CH4": 0.0, "N2O": 0.0, "tot": 0.0})
        d[r["gas"]] += float(r["co2e_Mt_AR5"])
        d["tot"] += float(r["co2e_Mt_AR5"])
    out = []
    for code, d in sorted(agg.items(), key=lambda kv: -kv[1]["tot"]):
        cells = [d[g] for g in ("CO2", "CH4", "N2O") if d[g] >= 0.005]
        row = _constrained_round(cells, d["tot"]) + [d["tot"]]
        out.append((code, row) if labelled else row)
    tot_cells = [sum(d[g] for d in agg.values()) for g in ("CO2", "CH4", "N2O")]
    grand = sum(d["tot"] for d in agg.values())
    row = _constrained_round(tot_cells, grand) + [grand]
    out.append(("Total", row) if labelled else row)
    return out


def _waste_sensitivity_rows():
    """tab:sensitivity (waste): [category reading, implied sector total] per printed case
    (lifted from the ordinal registry's inline lambda so the labelled one can carry it)."""
    def cat(name):
        return _cell("waste_totals_%d.csv" % _waste_year(), "category", name, "co2e_Mt_AR5")
    tot, ww, dis = cat("TOTAL"), cat("Domestic wastewater"), cat("Solid waste disposal")
    river = cat("Sensitivity: wastewater on the river-discharge MCF (category total)")
    bod = cat("Sensitivity: wastewater on India's BOD rate (category total)")
    nospin = cat("Sensitivity: disposal without spin-up")
    return [[ww, tot], [river, tot - ww + river], [bod, tot - ww + bod], [dis, tot],
            [nospin, tot - dis + nospin]]


def _cell_value(cell):
    """A tabular cell reduced to its printed number, or None for a text cell.

    Strips the formatting LaTeX puts around a number - \\num, \\SI, \\textbf, gas macros,
    thin-space thousand separators - and accepts only cells that are then purely numeric,
    so labels like '2015--16' and 'Total (1A3c)' fall out as text rather than mis-parsing.
    """
    c = cell.strip()
    # A footnote marker on a value - the review-flag daggers in tab:benchmarks - is
    # annotation, not arithmetic. Stripped explicitly rather than by dropping every '^',
    # so a genuine exponent would still fall out as text instead of silently losing its
    # caret and being read as a different number.
    c = re.sub(r"\$\^\{?\\d?dagger\}?\$", "", c)
    for _ in range(3):  # macros can nest one level (\textbf{\num{x}})
        c = re.sub(r"\\(num|SI|textbf|emph)\{([^{}]*)\}(\{[^{}]*\})?", r"\2", c)
    c = re.sub(r"\\[A-Za-z]+\{?\}?", "", c)
    c = c.replace("\\,", "").replace("$", "").replace("{", "").replace("}", "").strip()
    # rc42 (M-7): a signed reallocation cell prints its plus sign ($+2.08$); it is a number
    return c.replace(",", "") if re.fullmatch(r"[-+]?\d[\d,]*(\.\d+)?", c) else None


def _expand_generated_inputs(block, path):
    """A table block that inputs a generated body (\\input{sections/gen_*}) is read with
    that body spliced in, so the label, self-sum and coverage readers see the cells the
    paper prints (v1.0.0 Wave 4: the stored-query tables live in their own files)."""
    def splice(m):
        target = os.path.join(os.path.dirname(path), os.path.basename(m.group(1)))
        target = target if target.endswith(".tex") else target + ".tex"
        if not os.path.exists(target):
            return m.group(0)
        body = open(target, encoding="utf-8").read()
        return re.sub(r"(?<!\\)%.*", "", body)
    return re.sub(r"\\input\{(sections/gen_[^}]*)\}", splice, block)


def _tex_table(doc, section, label):
    """The numeric cells of the table labelled `label`, as printed strings, row by row.

    Rows with no numeric cell (headers, rules) are dropped. Returns None when no table in
    the section carries the label - which the caller treats as a failure, not a skip.
    """
    path = _doc_path(doc, section)
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"(?<!\\)%.*", "", text)          # a LaTeX comment is not a cell (rc42)
    for m in re.finditer(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", text, re.S):
        block = m.group(0)
        if "\\label{%s}" % label not in block:
            continue
        block = _expand_generated_inputs(block, path)
        body = re.search(r"\\begin\{tabular\}\{(?:[^{}]|\{[^{}]*\})*\}(.*?)\\end\{tabular\}",
                         block, re.S)          # a nested-brace column spec (rc42)
        if not body:
            return None
        rows = []
        for chunk in body.group(1).split("\\\\"):
            chunk = re.sub(r"\\(top|mid|bottom)rule", "", chunk).strip()
            if not chunk:
                continue
            cells = [_cell_value(c) for c in chunk.split("&")]
            numeric = [c for c in cells if c is not None]
            if numeric:
                rows.append(numeric)
        return rows
    return None


# ---- label + value (rc41, M-1/M-2/M-8) -------------------------------------------------
# The numeric comparator above drops every text cell, so a table whose LABELS were swapped
# against its numbers passed for a release: tab:keycat printed "Manure management ... 21.82"
# and "Cement production ... 21.23" - the engine's cement 21.816 and manure 21.228 in each
# other's rows, in the CSV's own order, so the ordinal zip was satisfied and the name<->code
# check (which reads the two text cells together) was satisfied too. A label is a claim, and
# the value beside it is a claim ABOUT that label; the registry below carries both.
_GAS_MACROS = (("\\NHthree{}", "NH3"), ("\\NOx{}", "NOx"), ("\\NtwoO{}", "N2O"),
               ("\\CHfour{}", "CH4"), ("\\COtwo{}", "CO2"), ("\\COe{}", "CO2e"),
               ("\\SOtwo{}", "SO2"), ("\\PM{}", "PM2.5"), ("\\PMten{}", "PM10"))


def _label_text(cell):
    """A tabular text cell reduced to comparable prose: formatting macros unwrapped, gas
    macros spelled out, footnote markers and math decoration dropped, whitespace collapsed."""
    c = cell.strip()
    c = re.sub(r"\$\^\{?(?:\\d?dagger|\\ddagger|[a-z])\}?\$", "", c)
    for macro, name in _GAS_MACROS:
        c = c.replace(macro, name)
    c = re.sub(r"\\textsubscript\{([^{}]*)\}", r"\1", c)
    for _ in range(3):
        c = re.sub(r"\\(textbf|emph|texttt|textit|mathrm)\{([^{}]*)\}", r"\2", c)
    c = c.replace("\\quad", " ").replace("\\&", "&").replace("~", " ").replace("\\,", " ")
    c = re.sub(r"\\[A-Za-z]+\{?\}?", "", c)
    c = c.replace("$", "").replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", c).strip()


def _tex_table_labelled(doc, section, label):
    """Every data row of the table labelled `label` as (text cells, numeric cells).

    Rows with no numeric cell are dropped, as in _tex_table; the text cells are reduced by
    _label_text. None when the table is not found (a failure for the caller, not a skip)."""
    path = _doc_path(doc, section)
    if not os.path.exists(path):
        return None
    text = open(path, encoding="utf-8").read()
    text = re.sub(r"(?<!\\)%.*", "", text)          # a LaTeX comment is not a cell (rc42)
    for m in re.finditer(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", text, re.S):
        block = m.group(0)
        if "\\label{%s}" % label not in block:
            continue
        block = _expand_generated_inputs(block, path)
        body = re.search(r"\\begin\{tabular\}\{(?:[^{}]|\{[^{}]*\})*\}(.*?)\\end\{tabular\}",
                         block, re.S)          # a nested-brace column spec (rc42)
        if not body:
            return None
        rows = []
        for chunk in body.group(1).split("\\\\"):
            chunk = re.sub(r"\\(top|mid|bottom)rule", "", chunk).strip()
            if not chunk:
                continue
            raw = chunk.split("&")
            values = [_cell_value(c) for c in raw]
            numeric = [v for v in values if v is not None]
            if numeric:
                rows.append(([_label_text(c) for c, v in zip(raw, values) if v is None],
                             numeric))
        return rows
    return None


def _match_labelled(printed, expected, label):
    """Problems joining `expected` [(row label, values)] to `printed` [(texts, numbers)] by
    label. A label matches a printed row whose FIRST text cell starts with it; every printed
    row must be claimed, and the values beside a matched label must agree at the printed
    precision.

    rc42 (M-7): a label may be a TUPLE, matched positionally over the row's text cells - the
    way to name a continuation row whose first cell is blank (("", "N2O")) or a table keyed
    on two columns (tab:ledger, tab:params, tab:benchmarks). Expected rows are joined in
    order and a label claims the first UNCLAIMED row it matches, so two ("", "N2O") rows
    resolve deterministically; the uniqueness the old one-hit rule enforced is kept by the
    every-row-claimed check below."""
    problems = []
    if len(printed) != len(expected):
        problems.append("%s: %d data rows printed, %d in the output"
                        % (label, len(printed), len(expected)))
    claimed = set()
    for name, want in expected:
        parts = name if isinstance(name, tuple) else (name,)
        hits = [i for i, (texts, _num) in enumerate(printed)
                if i not in claimed and len(texts) >= len(parts)
                and all(texts[j].startswith(p) for j, p in enumerate(parts))]
        if not hits:
            problems.append("%s: label %r matches no unclaimed printed row" % (label, name))
            continue
        i = hits[0]
        claimed.add(i)
        got = printed[i][1]
        if len(got) != len(want):
            problems.append("%s %r: %d numeric cells printed, %d in the output"
                            % (label, name, len(got), len(want)))
            continue
        for w, g in zip(want, got):
            dp = len(g.split(".")[1]) if "." in g else 0
            if abs(float(g) - w) > 0.5 * 10 ** (-dp) + 1e-9:
                problems.append("%s %r: printed %s, output %.6g" % (label, name, g, w))
    for i, (texts, _num) in enumerate(printed):
        if i not in claimed:
            problems.append("%s: printed row %r claimed by no label" % (label, texts[:1]))
    return problems


# The key-category table prints short names for six of the engine's declared IPCC names.
KEYCAT_PRINTED = {
    "Public electricity and heat production": "Public electricity and heat",
    "Domestic wastewater treatment and discharge": "Domestic wastewater",
    "Fugitive emissions from oil and natural gas": "Fugitive emissions, oil and gas",
    "Manufacturing industries and construction": "Manufacturing and construction",
    "Field burning of agricultural residues": "Field burning of residues",
    "Agriculture/forestry/fishing/fish farms": "Agriculture/forestry/fishing",
    "Railway stationary and off-road energy (unresolved split)":
        "Railway stationary/off-road",
}
# tab:sectors prints each module under a display name; the engine's sector ids are the key.
SECTORS_PRINTED = {
    "agriculture": "Agriculture", "power": "Power module", "transport": "Transport module",
    "waste": "Waste", "residential": "Residential fuel",
    "fugitives": "Oil and gas fugitives", "ippu": "Cement (IPPU)",
    "industry": "Industrial fuel (1A2)", "railways": "Railways",
    "aviation": "Domestic aviation", "TOTAL": "Total",
}
AGRI_PRINTED = {"Field burning of residues": "Field burning", "TOTAL": "Total"}


def _agri_labelled(rows_fn, order, total_label="Total"):
    """Pair a per-category row builder (in `order`) with the printed category labels."""
    rows = rows_fn()
    labels = [total_label if k == "TOTAL" else AGRI_PRINTED.get(k, k) for k in order]
    assert len(rows) == len(labels), (len(rows), len(labels))
    return list(zip(labels, rows))


def _power_fuel_rows():
    """tab:fuel: the four grid fuels in printed order plus the closing total row."""
    by = {r["fuel"]: r for r in _rows("power_fuel_fy2023_24.csv")}
    order = ("Coal", "Gas", "Furnace Oil", "Diesel Oil")
    rows = [[float(by[f]["TJ"]), float(by[f]["share_pct"])] for f in order]
    rows.append([sum(r[0] for r in rows), sum(r[1] for r in rows)])
    return rows


def _power_captive_rows():
    """tab:captive: the OGRA captive-gas series FY2016-24, year and MMCFD."""
    return [[float(r["fiscal_year"]), float(r["total_mmcfd"])]
            for r in _data_rows(os.path.join("activity", "power", "captive_gas.csv"))
            if r["total_mmcfd"] and 2016 <= int(r["fiscal_year"]) <= 2024]


def _power_scenarios_rows():
    """tab:scenarios in its printed order, [deterministic, P2.5, P97.5] per case."""
    by = {r["structural_scenario"]: r
          for r in _rows("power_uncertainty_scenarios_fy2023_24.csv")}
    order = ("reference", "coal_all_bituminous", "coal_all_lignite",
             "coal_at_implied_cv", "coal_at_table3_legacy", "toe_gross_basis",
             "grid_plus_ke_ledger_fuel", "captive_hhv_900")
    return [[float(by[s]["deterministic_Mt"]), float(by[s]["P2.5_Mt"]),
             float(by[s]["P97.5_Mt"])] for s in order]


def _power_sensitivity_rows():
    """tab:sensitivity: one deterministic cell per printed row."""
    keys = ("Sensitivity: all coal bituminous", "Electricity and heat production",
            "Sensitivity: all coal lignite",
            "Sensitivity: coal at ledger mass x implied CV",
            # The account the coal re-base replaced, kept in the table so the blend span
            # and the account change are not read as one quantity.
            "Sensitivity: Table 3 published coal energy (legacy control)",
            "Sensitivity: captive gas at 900 Btu/scf",
            "Captive gas self-generation (1A2)")
    return [[_cell("power_totals_fy2023_24.csv", "category", k, "co2e_Mt_AR5")]
            for k in keys]


def _power_results_rows():
    """tab:results: [Mt, +/-%] for the two categories and the sector total."""
    out = []
    for cat in ("Electricity and heat production",
                "Captive gas self-generation (1A2)", "TOTAL"):
        r = next(x for x in _rows("power_uncertainty_fy2023_24.csv")
                 if x["category"] == cat)
        out.append([float(r["co2e_Mt_AR5"]), float(r["approach1_pct_grouped"])])
    return out


def _power_air_rows():
    """tab:air: uncontrolled kt per pollutant, grid only (captive is priced in the industry
    air layer since rc58), printed order."""
    order = ("PM", "SO2", "NOx", "PM10", "PM2.5", "CO", "VOC")
    return [[_sum_where("power_air_pollutants_fy2023_24.csv", "emissions_kt",
                        pollutant=p)] for p in order]


def _power_heatrate_rows():
    """tab:heatrate: only the spread cell survives the numeric-cell extractor; the
    SIrange efficiency endpoints are covered by DOC_CLAIMS."""
    by = {r["fuel"]: r for r in _rows("power_heat_rate_stability_fy2023_24.csv")}
    return [[float(by[f]["spread"])]
            for f in ("Gas", "Furnace Oil", "Coal", "Diesel Oil")]


def _residential_air_pair_rows():
    """tab:air (residential): [residential kt, road kt] per pollutant. Since the road
    layer's EMEP Tier 1 refactor BC exists on the road side too (f-BC of exhaust
    PM2.5); OC still prints a dash there and reduces to one numeric cell."""
    res, road = {}, {}
    for r in _rows("residential_air_pollutants_2024.csv"):
        res[r["pollutant"]] = res.get(r["pollutant"], 0.0) + float(r["emissions_kt"])
    for r in _rows("transport_air_pollutants_2024.csv"):
        road[r["pollutant"]] = road.get(r["pollutant"], 0.0) + float(r["emissions_kt"])
    rows = []
    for p in ("CO", "NMVOC", "PM2.5", "NOx", "OC", "NH3", "SO2", "BC"):
        cells = [res[p]]
        if p in road and p != "OC":
            cells.append(road[p])
        rows.append(cells)
    return rows


def _agri_sensitivity_rows():
    """04b tab:sensitivity: [rice, soils, total] per scenario, COMPUTED - not read from
    outputs/eval/sensitivity.csv. rc42 (the twentieth review's M-1): the eval lane is
    hand-run (make eval) and the shipped CSV was an rc40 artefact (223.26 main case); a
    table gate that reads the stale file it should be checking is self-referential."""
    from pkinv.eval import sensitivity_table
    rows, _total = sensitivity_table.scenarios()
    return [[float(r["rice"]), float(r["soils"]), float(r["total"])] for r in rows]


def _agri_fertmix_rows():
    """04c product table: engine mix, contents, shares, EMEP factors and the total."""
    from pkinv.sectors.agriculture import fertiliser_mix as fm
    from pkinv.sectors.agriculture.ef_library import InventoryData
    d = InventoryData()
    weighted, detail, total_n = fm.weighted_fracgasf(d)
    by = {x["product"]: x for x in detail}
    # rc39 A2: the national nitrogen comes from Annex-5's Jul-Jun window directly. It used to
    # be summed out of Annex-7's PROVINCIAL table, which meant the printed table carried an
    # April-March composition under a fiscal-year heading.
    nat, _ = fm.national_product_nitrogen(d)
    def row(*prods):
        tn = sum(nat.get(p, 0.0) for p in prods)
        share = sum(by[p]["share_of_N"] for p in prods if p in by)
        ef = by[prods[0]]["EF_NH3N_per_N"]
        return [tn, d.efv("fert_n_content", prods[0]), share, ef, share * ef]
    rows = [row("Urea"), row("DAP"), row("CAN"), row("NP", "MAP"), row("AS"),
            row("NPKs")]
    rows.append([total_n, 1.0, weighted])
    return rows


def _agri_crt_rows():
    """tab:crt: 1990 and 2024 CO2e (Mt AR5) per category/gas from the CRT table."""
    rows = list(_rows("crt_AFOLU_table.csv"))
    def yr(y, code):
        return next(x for x in rows if x["year"] == y and x["code"] == code)
    out = [[1990.0, 2024.0]]
    a90, a24 = yr("1990", "3.A"), yr("2024", "3.A")
    out.append([float(a90["CO2e_kt_AR5"]) / 1000.0,
                float(a24["CO2e_kt_AR5"]) / 1000.0])
    b90, b24 = yr("1990", "3.B"), yr("2024", "3.B")
    out.append([float(b90["CH4_kt"]) * 0.028, float(b24["CH4_kt"]) * 0.028])
    out.append([float(b90["N2O_kt"]) * 0.265, float(b24["N2O_kt"]) * 0.265])
    for code in ("3.C", "3.D", "3.F", "3.H"):
        out.append([float(yr("1990", code)["CO2e_kt_AR5"]) / 1000.0,
                    float(yr("2024", code)["CO2e_kt_AR5"]) / 1000.0])
    out.append([float(yr("1990", "3")["CO2e_kt_AR5"]) / 1000.0,
                float(yr("2024", "3")["CO2e_kt_AR5"]) / 1000.0])
    return out


def _agri_unc_rows():
    """tab:unc: point, band and lognormal parameters per category."""
    by = {r["category"]: r for r in _rows(os.path.join("eval",
                                                       "uncertainty_derived.csv"))}
    order = ("Enteric fermentation", "Manure management", "Managed soils",
             "Rice cultivation", "Field burning of residues",
             "Urea application", "TOTAL")
    out = []
    for k in order:
        r = by[k]
        cells = [float(r["point_Mt"]), float(r["combined_uncert_pct_95"])]
        if k != "TOTAL":
            cells += [float(r["lognormal_mu"]), float(r["lognormal_sigma"])]
        out.append(cells)
    return out


def _agri_s2live_rows():
    """tab:s2live: head (M), TAM (kg) and Nrate per species, engine parameters."""
    from pkinv.sectors.agriculture.ef_library import InventoryData
    d = InventoryData()
    heads = {r["species"]: r for r in _data_rows(os.path.join(
        "activity", "livestock_2024.csv"))}
    cattle = float(heads["cattle"]["head_value"])
    dairy_share = d.p("dairy_share_of_cattle") if "dairy_share_of_cattle" in getattr(
        d, "params", {}) else 0.295
    rows = [[cattle * dairy_share / 1e6, d.p("tam_dairy_cattle"),
             d.p("nex_rate_dairy_cattle")],
            [cattle * (1 - dairy_share) / 1e6, d.p("tam_other_cattle"),
             d.p("nex_rate_other_cattle")],
            [float(heads["buffalo"]["head_value"]) / 1e6, d.p("tam_buffalo"),
             d.p("nex_rate_buffalo")],
            [float(heads["sheep"]["head_value"]) / 1e6, d.p("tam_sheep"),
             d.p("nex_rate_sheep")],
            [float(heads["goats"]["head_value"]) / 1e6, d.p("tam_goats"),
             d.p("nex_rate_goats")],
            [float(heads["camels"]["head_value"]) / 1e6, d.p("tam_camels"),
             d.p("nex_rate_camels")],
            [float(heads["poultry"]["head_value"]) / 1e6, d.p("tam_poultry"),
             d.p("nex_rate_poultry")]]
    return rows


def _agri_apresults_rows():
    """tab:apresults: category x pollutant kt, with the memo dashes dropping out."""
    rows = list(_rows("air_pollutants_2024.csv"))
    def tot(pollutant, category=None):
        return sum(float(r["emissions_kt"]) for r in rows
                   if r["pollutant"] == pollutant
                   and (category is None or r["category"] == category))
    soils_nh3 = tot("NH3", "Managed soils")
    return [[soils_nh3, tot("NOx", "Managed soils")],
            [tot("NH3", "Manure management")],
            [tot("NH3", "Field burning of residues"),
             tot("NOx", "Field burning of residues"),
             tot("PM2.5", "Field burning of residues"),
             tot("CO", "Field burning of residues"),
             tot("NMVOC", "Field burning of residues"),
             tot("BC", "Field burning of residues"),
             tot("SO2", "Field burning of residues")],
            [tot("NH3"), tot("NOx"), tot("PM2.5"), tot("CO"), tot("NMVOC"),
             tot("BC"), tot("SO2")]]


def _agri_apunc_rows():
    """tab:apunc: air Monte-Carlo per pollutant in printed order."""
    by = {r["pollutant"]: r for r in _rows("air_uncertainty_montecarlo.csv")}
    order = ("NH3", "NOx", "CO", "PM2.5", "NMVOC", "BC", "SO2")
    return [[float(by[k]["mean_kt"]), float(by[k]["P2.5_kt"]),
             float(by[k]["P50_kt"]), float(by[k]["P97.5_kt"]),
             float(by[k]["approach1_pct_95"])] for k in order]


def _agri_apstruct_rows():
    """tab:apstruct: the MMS structural configurations."""
    return [[float(r["grazing_share_of_excreted"]),
             float(r["NH3_total_kt"]) / 1000.0,
             float(r["NH3_livestock_kt"]) / 1000.0,
             float(r["national_total_Mt"])]
            for r in _rows(os.path.join("eval", "mms_structural_uncertainty.csv"))]


def _agri_apbench_rows():
    """tab:apbench: matched-2015 and anchor-2024 NH3 comparisons."""
    rows = list(_rows("benchmark_air_comparison.csv"))
    def take(source, scope):
        r = next(x for x in rows if x["source"] == source
                 and x["scope"] == scope)
        return [float(r["benchmark_kt"]), float(r["engine_kt"]),
                float(r["ratio"]), float(r["engine_kt_anchor"]),
                float(r["ratio_anchor"])]
    out = [take("SANH 2026 (ESSD)", "Managed soils - synthetic"),
           take("SANH 2026 (ESSD)", "Livestock (grazing+manure+management)"),
           take("SANH 2026 (ESSD)", "Field burning of residues"),
           take("SANH 2026 (ESSD)", "TOTAL"),
           take("EDGAR v8", "TOTAL"),
           take("HTAP v3", "TOTAL")]
    return out


def _agri_spatialstreams_rows():
    """tab:spatialstreams: r / hotspot % / ratio per stream, then all-sectors."""
    d = json.load(open(os.path.join(OUT, "eval", "spatial_nh3_validation.json")))
    def row(s):
        # the hotspot cells print as "72\%" and fall out of the numeric-cell
        # extractor; they are covered by DOC_CLAIMS instead
        return [round(s["pearson"], 2), s["ratio"]]
    return [row(d["by_stream"]["synthetic"]), row(d["by_stream"]["livestock"]),
            row(d["by_stream"]["burning"]), row(d["all_sectors"])]


def _agri_by_year_2023():
    got = {}
    for r in _rows(os.path.join("districts", "district_totals_by_year.csv")):
        if r["year"] == "2023":
            got[r["category"]] = got.get(r["category"], 0.0) + float(r["co2e_Mt_AR5"])
    return got


def _agri_benchmark_rows():
    """tab:benchmark: engine-2023 category values against FAOSTAT 2023, then the
    urea-inclusive totals against EDGAR/Climate TRACE."""
    eng = _agri_by_year_2023()
    fao = {r["engine_category"]: float(r["benchmark_Mt_co2e"])
           for r in _rows("national_benchmark_comparison.csv") if r["source"] == "FAOSTAT"}
    rows = []
    for cat in ("Enteric fermentation", "Manure management", "Rice cultivation",
                "Managed soils", "Field burning of residues"):
        rows.append([eng[cat], fao[cat], eng[cat] / fao[cat]])
    ex = sum(v for k, v in eng.items() if k != "Urea application")
    rows.append([ex, fao["TOTAL"], ex / fao["TOTAL"]])
    full = sum(eng.values())
    e23 = next(r for r in _rows("national_benchmark_comparison.csv")
               if r["source"] == "EDGAR" and r["year"] == "2023")
    e24 = next(r for r in _rows("national_benchmark_comparison.csv")
               if r["source"] == "EDGAR" and r["year"] == "2024")
    rows.append([full, float(e23["benchmark_Mt_co2e"]),
                 full / float(e23["benchmark_Mt_co2e"])])
    rows.append([_cell("national_totals_2024.csv", "category", "TOTAL",
                       "co2e_Mt_AR5"), float(e24["benchmark_Mt_co2e"]),
                 float(e24["ratio_engine_over_benchmark"])])
    ct = next(r for r in _rows("national_benchmark_comparison.csv")
              if r["source"] == "Climate TRACE" and r["engine_category"] == "TOTAL")
    rows.append([_cell("national_totals_2024.csv", "category", "TOTAL",
                       "co2e_Mt_AR6"), float(ct["benchmark_Mt_co2e"]),
                 _cell("national_totals_2024.csv", "category", "TOTAL",
                       "co2e_Mt_AR6") / float(ct["benchmark_Mt_co2e"])])
    return rows


def _agri_mc_rows():
    """tab:mc: mean/P2.5/P50/P97.5/+-% per category, then the total row."""
    by = {r["category"]: r for r in _rows("uncertainty_montecarlo.csv")}
    order = ("Enteric fermentation", "Manure management", "Managed soils",
             "Rice cultivation", "Urea application",
             "Field burning of residues", "TOTAL")
    return [[float(by[k]["mean_Mt"]), float(by[k]["P2.5_Mt"]),
             float(by[k]["P50_Mt"]), float(by[k]["P97.5_Mt"]),
             float(by[k]["approach1_pct_95"])] for k in order]


def _agri_keycat_rows():
    """tab:keycat: level and trend shares in printed order."""
    by = {r["category"]: r for r in _rows("key_categories.csv")}
    order = ("Enteric fermentation", "Managed soils", "Manure management",
             "Rice cultivation", "Urea application",
             "Field burning of residues")
    return [[float(by[k]["level_pct"]), float(by[k]["trend_pct"])] for k in order]


def _agri_nledger_rows():
    """tab:nledger: the printed subset of the nitrogen ledger, Mt N and % excreted."""
    led = list(_rows("n_ledger_2024.csv"))
    def take(stage, flow_start):
        r = next(x for x in led if x["stage"].startswith(stage)
                 and x["flow"].startswith(flow_start))
        return [float(r["Mt_N"]), float(r["pct_of_excreted"])]
    def pair_sum(stage, *flow_starts):
        rs = [next(x for x in led if x["stage"].startswith(stage)
                   and x["flow"].startswith(f)) for f in flow_starts]
        return [sum(float(r["Mt_N"]) for r in rs),
                sum(float(r["pct_of_excreted"]) for r in rs)]
    return [take("A. ", "Total N excreted"),
            take("A. ", "to grazing"),
            take("A. ", "to managed"),
            take("A. ", "diverted as dung-cake"),
            take("B. ", "NH3-N + NOx-N"),
            pair_sum("B. ", "leached/run-off", "lost as N2", "emitted as direct"),
            take("B. ", "= N available"),
            take("C. ", "direct soil N2O-N"),
            take("C. ", "NH3-N + NOx-N"),
            take("C. ", "leached/run-off"),
            take("C. ", "remaining in the soil"),
            pair_sum("B'. ", "NH3-N lost in housing", "NH3-N lost in storage"),
            take("B'. ", "NH3-N lost on field")]


def _agri_stages_rows():
    """tab:stages: IPCC vs EMEP NH3-N by stage with ratios."""
    return [[float(r["ipcc_nh3_n"]), float(r["emep_nh3_n"]), float(r["ratio"])]
            for r in _rows("n_ledger_stage_comparison.csv")]


def _agriculture_national_rows():
    """tab:national: [AR5, AR6, +/-%] per category in printed order, then the total."""
    by = {r["category"]: r for r in _rows("national_totals_2024.csv")}
    order = ("Enteric fermentation", "Manure management", "Managed soils",
             "Rice cultivation", "Urea application",
             "Field burning of residues", "TOTAL")
    return [[float(by[k]["co2e_Mt_AR5"]), float(by[k]["co2e_Mt_AR6"]),
             float(by[k]["uncert_pct"])] for k in order]


def _agriculture_provincial_rows():
    """tab:provincial: six numeric columns per province (burning omitted in print)."""
    cols = ("Enteric fermentation", "Manure management", "Rice cultivation",
            "Managed soils", "Urea application", "TOTAL")
    rows = []
    for r in _rows("provincial_totals_2024.csv"):
        rows.append([float(r[c]) for c in cols])
    return rows


def _transport_fuelbridge_rows():
    """tab:fuelbridge: the mass-to-energy bridge, [kt, TJ] pairs then CNG TJ-only."""
    rows = list(_rows("transport_fuel_bridge_2024.csv"))
    def take(fuel, kind):
        r = next(x for x in rows if x["fuel"] == fuel and x["kind"] == kind)
        cells = []
        if r["kt"]:
            cells.append(float(r["kt"]))
        cells.append(float(r["TJ"]))
        return cells
    return [take("Petrol", "opening"), take("Petrol", "deduction"),
            take("Petrol", "closing"),
            take("Diesel", "opening"), take("Diesel", "partition"),
            take("Diesel", "closing"),
            take("CNG", "opening"),
            [-(take("CNG", "opening")[0] - take("CNG", "closing")[0])],
            take("CNG", "closing")]


def _residential_hies_rows():
    """tab:hies: the survey-versus-control comparison; daggered cells drop out."""
    by = {r["fuel"]: r for r in _rows("residential_hies_comparison_2024.csv")}
    fw, dg = by["firewood"], None
    rows = [[float(fw["hies2425_annual"]) / 1e9, float(fw["engine_annual"]) / 1e9]]
    dung = next(r for r in _rows("residential_dung_ledger_2024.csv")
                if r["configuration"] == "S")
    rows.append([float(next(r for r in _rows("residential_dung_ledger_2024.csv")
                            if r["configuration"] == "S")["Mt_air_dry"]),
                 float(next(r for r in _rows("residential_dung_ledger_2024.csv")
                            if r["configuration"] == "both")["Mt_air_dry"]),
                 float(next(r for r in _rows("residential_dung_ledger_2024.csv")
                            if r["configuration"] == "S")["Mt_air_dry"])
                 / float(next(r for r in _rows("residential_dung_ledger_2024.csv")
                              if r["configuration"] == "both")["Mt_air_dry"])])
    lpg = by["lpg"]
    rows.append([float(lpg["hies2425_annual"]) / 1e9,
                 float(lpg["engine_annual"]) / 1e9,
                 float(lpg["ratio_hies_over_engine"])])
    ker = by["kerosene"]
    rows.append([float(ker["hies2425_annual"]) / 1e6,
                 float(ker["engine_annual"]) / 1e6])
    return rows


def _residential_hiesdiag_rows():
    """tab:hiesdiag: firewood diagnostics for both survey rounds, column-paired."""
    by = {r["survey"]: r
          for r in _data_rows(os.path.join("activity", "residential", "hies",
                                           "hies_diagnostics.csv"))
          if r["fuel"] == "firewood"}
    a, b = by["hies2019"], by["hies2025"]
    rows = [[float(a["n_reporting_households"]), float(b["n_reporting_households"])],
            [float(a["weighted_users"]) / 1e6, float(b["weighted_users"]) / 1e6],
            [float(a["per_user_hh_day"]), float(b["per_user_hh_day"])],
            [float(a["top1pct_hh_share_of_total"]),
             float(b["top1pct_hh_share_of_total"])],
            [float(a["top5pct_hh_share_of_total"]),
             float(b["top5pct_hh_share_of_total"])]]
    return rows


def _residential_fuel_rows():
    """tab:fuel: streams in printed order; the <0.1 share cells fall out as text."""
    by = {r["stream"]: r for r in _rows("residential_fuel_2024.csv")}
    order = ("Dung cake", "Firewood", "Natural gas", "Crop residues", "LPG",
             "Kerosene", "Generators")
    rows = [[float(by[s]["TJ"]), float(by[s]["share_pct"])] for s in order]
    rows.append([float(by["Coal"]["TJ"])])
    rows.append([float(by["Charcoal"]["TJ"])])
    rows.append([sum(float(r["TJ"]) for r in by.values()), 100.0])
    return rows


def _residential_streams_rows():
    """tab:results: [Gg, Mt, +/-%] per printed gas row, then the total row."""
    by = {r["subitem"]: r for r in _rows("residential_by_stream_2024.csv")}
    order = ("Natural gas CO2", "Natural gas CH4", "LPG CO2", "Kerosene CO2",
             "Coal CO2", "Generators CO2", "Dung cake CH4", "Dung cake N2O",
             "Firewood CH4", "Firewood N2O", "Crop residues CH4",
             "Crop residues N2O")
    rows = [[float(by[k]["emissions_Gg"]), float(by[k]["co2e_Mt_AR5"]),
             float(by[k]["uncert_pct"])] for k in order]
    rows.append([_cell("residential_totals_2024.csv", "category",
                       "Residential fuel combustion", "co2e_Mt_AR5"),
                 _first_where("residential_uncertainty_2024.csv",
                              "approach1_pct_independent",
                              category="Residential fuel combustion")])
    return rows


def _residential_configs_rows():
    """tab:configs: one row per headline quantity, L and S side by side."""
    by = {r["configuration"]: r
          for r in _rows("residential_configurations_2024.csv")}
    cols = ("dung_air_dry_Mt", "energy_TJ", "co2e_Mt_AR5", "memo_biogenic_Gg",
            "pm25_kt", "bc_kt", "pm_ratio_vs_road_exhaust", "national_share_pct")
    return [[float(by["L"][c]), float(by["S"][c])] for c in cols]


def _residential_sensitivity_rows():
    """tab:sensitivity: the four firewood cases, one Mt cell per printed row."""
    keys = ("Sensitivity: firewood excluded", "Sensitivity: firewood low",
            "Residential fuel combustion", "Sensitivity: firewood high")
    return [[_cell("residential_totals_2024.csv", "category", k, "co2e_Mt_AR5")]
            for k in keys]


def _keycat_rows():
    """national_key_categories.csv in its published order - the order the table prints."""
    return _rows("national_key_categories.csv")


# The flagship's own tables. Registered late, and the reason is the finding: until this
# existed, five of the seven tables in paper_national were checked against nothing at all,
# including the one carrying the Monte-Carlo means. See TestEveryPrintedQuantityIsProtected.
def _spatial_row(sector):
    """One module's S1-S3 and NA shares, in the appendix table's column order.

    NA joined the scale when industrial combustion stopped claiming S3 for a sub-provincial
    allocation it does not have. It is a fourth COLUMN and not a fourth quality: S1-S3 grade
    how mass is placed below the province, and NA says there is no such placement to grade.
    """
    got = {r["spatial_method"]: float(r["share_of_scope_pct"])
           for r in _rows("spatial_profile.csv") if r["scope"] == sector}
    return [got.get(c, 0.0) for c in ("S1", "S2", "S3", "NA")]


def _temporal_row(sector):
    """One module's T1-T4 shares, in the appendix table's column order."""
    got = {r["temporal_method"]: float(r["share_of_scope_pct"])
           for r in _rows("temporal_profile.csv") if r["scope"] == sector}
    return [got.get(c, 0.0) for c in ("T1", "T2", "T3", "T4")]


NATIONAL_TABLES = [
    # The monthly layer's per-module class distribution. Ten rows of four, each read from
    # the table the national run writes - the alternative was forty typed percentages.
    ("national", "14_appendix.tex", "tab:temporal",
     lambda: [_temporal_row(s) for s in
              ("agriculture", "power", "transport", "residential", "industry", "ippu",
               "waste", "fugitives", "railways", "aviation")]),
    # The spatial counterpart, from the profile the source-stream ledger writes. The
    # NATIONAL row prints alongside the ten modules.
    ("national", "14_appendix.tex", "tab:spatial",
     lambda: [_spatial_row(s) for s in
              ("agriculture", "power", "transport", "residential", "industry", "ippu",
               "waste", "fugitives", "railways", "aviation")]
             + [_spatial_row("NATIONAL")]),
    # tab:categorygas RETIRED here (v1.0.0 Wave 4): the primary national result is a stored
    # query (paper_national/queries/paper_artefacts.csv, tab_categorygas) rendered into
    # sections/gen_tab_categorygas.tex from query envelopes; tests/paper_numbers/
    # test_paper_artefacts.py replays the query and holds the bytes. _category_gas_rows stays
    # as the record of the constrained-rounding rule the typed table used.
    # tab:sectors - the sector table, in printed order.
    ("national", "06_results.tex", "tab:sectors",
     lambda: [[_sector(s), float(_sector_row(s)["share_pct"]),
               float(_sector_row(s)["uncert_pct_95"])]
              for s in ("agriculture", "power", "transport", "waste", "residential",
                        "fugitives", "ippu", "industry", "railways", "aviation")]
             + [[_sector("TOTAL"), 100.0, float(_sector_row("TOTAL")["uncert_pct_95"])]]),
    # tab:dungvariants - each destination's delta and implied national total, from the
    # variants pricing. Registered on creation; the conservation gate lives in the writer.
    ("national", "07_uncertainty.tex", "tab:dungvariants",
     lambda: [[float(r["delta_vs_S_Mt_co2e_AR5"]),
               float(r["national_total_Mt_co2e_AR5"])]
              for r in _rows("national_dung_variants.csv")]),
    # tab:correlation - the table that printed a Monte-Carlo mean 3.5 Mt from the engine's
    # for a full release, because not one of its twelve cells was registered anywhere.
    ("national", "07_uncertainty.tex", "tab:correlation",
     lambda: [[_mc(s, "TOTAL", c) for s in ("within_sector", "cross_sector")]
              for c in ("mean_Mt", "P50_Mt", "P2.5_Mt", "P97.5_Mt",
                        "rel_uncert_pct_MC_95")]
             + [[_mc(s, n) for s in ("within_sector", "cross_sector")]
                for n in ("transport", "Road transport", "power", "residential",
                          "railways", "agriculture")]),
    # tab:keycat - level and variance shares, straight off the key-category output.
    ("national", "08_key_categories.tex", "tab:keycat",
     lambda: [[float(r["level_Mt_co2e_AR5"]), float(r["level_pct"]),
               float(r["variance_share_pct_independent_approx"])] for r in _keycat_rows()]),
    # tab:completeness RETIRED here (v1.0.0 Wave 4): the tally is four get_completeness
    # stored queries whose cell counts the table prints as value macros
    # (sections/gen_tab_completeness.tex; tab_completeness in the registry).
    # tab:benchmarks - external comparison, in printed order. Transport carries two EDGAR
    # vintages, so the year-matched row is named explicitly.
    # tab:benchmarks - external comparison, in printed order, GROUPED BY WHAT THE COMPARISON
    # CAN SUPPORT. Rows whose boundaries do not support a ratio print a dash, so the expected
    # row is two cells rather than three - which is the point of the grouping and is asserted
    # here rather than left to the caption.
    ("national", "10_benchmarks.tex", "tab:benchmarks",
     lambda: [[_bench(src, cat, "benchmark_Mt_co2e", year),
               _bench(src, cat, "engine_Mt_co2e", year)]
              + ([] if _bench_ratio_withheld(src, cat, year)
                 else [_bench(src, cat, "ratio_engine_over_benchmark", year)])
              for src, cat, year in (
                  ("EDGAR", "Electricity and heat production", 2024),
                  ("EDGAR", "Residential fuel combustion", 2024),
                  ("EDGAR", "waste", 2023),
                  ("FAOSTAT", "TOTAL", 2023),
                  ("EDGAR", "TOTAL", 2024),
                  ("Climate TRACE", "TOTAL", 2024),
                  ("FAOSTAT", "Managed soils", 2023),
                  ("Climate TRACE", "Rice cultivation", 2024),
                  ("EDGAR", "Fugitive emissions from oil and gas", 2024),
                  ("EDGAR", "transport", 2024),
                  ("EDGAR", "NATIONAL", 2024),
                  ("EDGAR", "1A2 (all estimated)", 2024),
                  ("EDGAR", "Cement production", 2024))]),
]


# Registered tables: (document, section, label, expected rows). Each expected row lists the
# numeric cells the printed row must contain, in printed order; the road-table constants in
# tab:factors are IPCC Table 3.2.1/3.2.2 values quoted by the paper and by run_railways.
TABLES = [
    ("railways", "03_study_area_and_data.tex", "tab:fuel",
     lambda: [[_cell("railways_fuel_2024.csv", "stream", s, "TJ"),
               _cell("railways_fuel_2024.csv", "stream", s, "share_pct")]
              for s in ("Diesel", "Furnace oil")]),
    ("railways", "04b_emission_factors.tex", "tab:factors",
     lambda: [[_ef("rail_co2_diesel"), 74100.0, _ef("rail_co2_diesel") / 74100.0],
              [_ef("rail_ch4_diesel"), 3.9, _ef("rail_ch4_diesel") / 3.9],
              [_ef("rail_n2o_diesel"), 3.9, _ef("rail_n2o_diesel") / 3.9]]),
    ("railways", "06_results.tex", "tab:streams",
     lambda: [[_cell("railways_by_stream_2024.csv", "subitem", s, "emissions_Gg"),
               _cell("railways_by_stream_2024.csv", "subitem", s, "co2e_Mt_AR5"),
               _cell("railways_by_stream_2024.csv", "subitem", s, "uncert_pct")]
              for s in ("Diesel CO2", "Diesel N2O", "Diesel CH4", "Furnace oil CO2")]
             + [[_cell("railways_totals_2024.csv", "category",
                       "Railway non-traction energy (1A2/1A4c unresolved)",
                       "co2e_Mt_AR5")],
                [_cell("railways_totals_2024.csv", "category", "Railways",
                       "co2e_Mt_AR5")],
                [_cell("railways_totals_2024.csv", "category",
                       "Railway non-traction energy (1A2/1A4c unresolved)",
                       "co2e_Mt_AR5")],
                [_cell("railways_totals_2024.csv", "category",
                       "Module total (both categories)", "co2e_Mt_AR5")]]),
    ("railways", "06_results.tex", "tab:diagnostic",
     lambda: [[_cell("railways_totals_2024.csv", "category",
                     "Module total (both categories)", "co2e_Mt_AR5")],
              [_cell("railways_totals_2024.csv", "category",
                     "Diagnostic: N2O on the road factor", "co2e_Mt_AR5")]]),
    ("railways", "08_limitations.tex", "tab:yearbook",
     lambda: [[float(r["summary_k_litres"]), float(r["locomotive"]),
               float(r["other_than_locomotive"]), float(r["detail_total"])]
              for r in sorted(_rows("railways_fuel_reconciliation_2024.csv"),
                              key=lambda r: int(r["fiscal_year"]))]),
    ("railways", "06_results.tex", "tab:air",
     lambda: [[_air_kt(pol),
               _first_where("railways_air_pollutants_2024.csv", "uncert_pct",
                            fuel="Diesel", pollutant=pol)]
              for pol in ("NOx", "CO", "NMVOC", "TSP", "PM10", "PM2.5", "BC", "SO2",
                          "NH3")]),
    # Display order: chronological. The TNC/BTR narrative rows carry no numeric cells
    # (their year labels are CY-prefixed for exactly that reason) so the parser drops
    # them, and the three valued rows must match the comparison output.
    ("railways", "05_validation.tex", "tab:official",
     lambda: [[_first_where("railways_official_comparison_2024.csv", col,
                            benchmark_id=b) for col in
               ("official_Mt_co2e", "own_Mt_co2e", "ratio_official_over_own")]
              for b in ("inc1994", "bur1", "crt2022")]),
    ("railways", "06b_uncertainty.tex", "tab:scenarios",
     lambda: [[_first_where("railways_uncertainty_scenarios_2024.csv", "deterministic",
                            structural_scenario=s)]
              for s in ("reference", "road_n2o_factor", "ie_summary",
                        "stock_timing_prior_year_mean", "tier2_service_split")]),
    # ---- transport (August 2026): registered after its tables shipped a stale
    # ---- edition with only eight prose anchors and nothing on the cells ----
    ("transport", "03_study_area_and_data.tex", "tab:fuel",
     lambda: [[_cell("transport_fuel_%d.csv" % _transport_year(), "fuel", "Petrol", "TJ"),
               _cell("transport_fuel_%d.csv" % _transport_year(), "fuel", "Petrol", "share_pct")],
              [_cell("transport_fuel_%d.csv" % _transport_year(), "fuel", "Diesel", "TJ"),
               _cell("transport_fuel_%d.csv" % _transport_year(), "fuel", "Diesel", "share_pct")],
              [_cell("transport_fuel_%d.csv" % _transport_year(), "fuel", "Petrol", "TJ")
               + _cell("transport_fuel_%d.csv" % _transport_year(), "fuel", "Diesel", "TJ"), 100.0]]),
    ("transport", "06_results.tex", "tab:results",
     lambda: [[_cell("transport_totals_%d.csv" % _transport_year(), "category", "Road transport",
                     "co2e_Mt_AR5"),
               _cell("transport_totals_%d.csv" % _transport_year(), "category", "Road transport",
                     "co2e_Mt_AR6"),
               _mc("within_sector", "Road transport", "approach1_pct_95")],
              [_cell("transport_totals_%d.csv" % _transport_year(), "category",
                     "Mixed off-road (1A4c/1A2)", "co2e_Mt_AR5"),
               _cell("transport_totals_%d.csv" % _transport_year(), "category",
                     "Mixed off-road (1A4c/1A2)", "co2e_Mt_AR6"),
               _mc("within_sector", "Mixed off-road (1A4c/1A2)", "approach1_pct_95")],
              [_cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR5"),
               _cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR6"),
               _mc("within_sector", "transport", "approach1_pct_95")]]),
    ("transport", "06_results.tex", "tab:fuels",
     lambda: [[sum(float(r["co2e_Mt_AR5"]) for r in _rows("transport_by_stream_%d.csv" % _transport_year())
                   if r["category"] == "Road transport"
                   and " %s " % fuel in " %s " % r["subitem"])]
              for fuel in ("Petrol", "Diesel")]
             + [[_sum_prefix("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                             "subitem", "CNG")]]),
    ("transport", "06_results.tex", "tab:cnghhv",
     lambda: [[_cell("transport_totals_%d.csv" % _transport_year(), "category", "TOTAL", "co2e_Mt_AR5")],
              [_cell("transport_totals_%d.csv" % _transport_year(), "category",
                     "Sensitivity: CNG at 900 Btu/scf", "co2e_Mt_AR5")]]),
    ("transport", "06_results.tex", "tab:classes",
     lambda: [[_sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                          subitem=s)] for s in
              ("2W Petrol CO2", "HDV Diesel CO2", "BUS Diesel CO2", "4W1 Petrol CO2",
               "LDV Petrol CO2", "LDV Diesel CO2", "Off-road machinery diesel CO2",
               "3W Petrol CO2", "CNG CO2")]
             + [[_sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5", gas="CO2")
                 - sum(_sum_where("transport_by_stream_%d.csv" % _transport_year(), "co2e_Mt_AR5",
                                  subitem=s) for s in
                       ("2W Petrol CO2", "HDV Diesel CO2", "BUS Diesel CO2",
                        "4W1 Petrol CO2", "LDV Petrol CO2", "LDV Diesel CO2",
                        "Off-road machinery diesel CO2", "3W Petrol CO2",
                        "CNG CO2"))]]),
    ("transport", "06_results.tex", "tab:keycat",
     lambda: [[_keycat("Road transport", "level_pct"),
               _keycat("Road transport", "variance_share_pct_independent_approx")],
              [_keycat("Mixed off-road (1A4c/1A2)", "level_pct"),
               _keycat("Mixed off-road (1A4c/1A2)", "variance_share_pct_independent_approx")]]),
    # since the EMEP Tier 1 refactor the table prints [Tier 1, superseded diagnostic]
    # per row; the second cell is FROZEN history (its engine is retired), the BC row's
    # second cell is the word "absent", and the wear-only coarse strata stay out
    ("transport", "06b_air_pollutants.tex", "tab:air",
     lambda: [[_sum_where("transport_air_pollutants_%d.csv" % _transport_year(), "emissions_kt",
                          pollutant=pol)]
             + ([] if pol == "BC" else
                [{"CO": 3588.2, "NMVOC": 679.8, "NOx": 112.7, "SO2": 29.9,
                  "PM2.5": 21.6, "NH3": 5.9}[pol]])
              for pol in ("CO", "NMVOC", "NOx", "SO2", "PM2.5", "BC", "NH3")]),
    # The main-text ledger table: every printed numeric row against the ledger CSV,
    # in printed order; unresolved rows print no number and are absent here.
    ("transport", "04_methods.tex", "tab:ledger",
     lambda: [[_first_where("transport_fuel_ledger_%d.csv" % _transport_year(), "kt",
                            fuel=f, tier=t, claimant=c),
               _first_where("transport_fuel_ledger_%d.csv" % _transport_year(), "share_of_opening",
                            fuel=f, tier=t, claimant=c)]
              for f, t, c in (
                  ("Diesel", "national", "National internal HSD sales"),
                  ("Diesel", "national", "Domestic"),
                  ("Diesel", "national", "Agriculture (bulk)"),
                  ("Diesel", "national", "Industry"),
                  ("Diesel", "national", "Railways"),
                  ("Diesel", "national", "Domestic bunkers"),
                  ("Diesel", "national", "Power"),
                  ("Diesel", "national", "Government"),
                  ("Diesel", "national", "Road (retail pump sales)"),
                  ("Diesel", "road", "Off-road machinery"),
                  ("Diesel", "road", "On-road transport"),
                  ("Petrol", "national", "National internal MS+HOBC sales"),
                  ("Petrol", "national", "Industry"),
                  ("Petrol", "national", "Government"),
                  ("Petrol", "national", "Road (retail pump sales)"),
                  ("Petrol", "road", "Household generators"),
                  ("Petrol", "road", "On-road transport"))]),
    # The boundary-scenario table: printed order is reference, the alternative
    # construction, the customer-class envelope, the within-channel retail cases,
    # and the calendar convention case.
    # Three printed columns per row now - road, off-road, sector - because for the
    # partition and intensity rows the sector total is the least informative of them.
    ("transport", "06_results.tex", "tab:boundary",
     lambda: [[_first_where("transport_uncertainty_scenarios_%d.csv" % _transport_year(), col,
                            structural_scenario=name)
               for col in ("road_Mt", "offroad_Mt", "deterministic")]
              for name in ("reference", "national_hsd_minus_bulk",
                           "road_share_low", "road_share_high",
                           "retail_nonroad_2p5pct", "retail_nonroad_5pct",
                           "retail_nonroad_10pct", "offroad_share_5pct",
                           "offroad_share_15pct", "class_intensity_low",
                           "class_intensity_high", "calendar_2022_controls")]),
    # The provenance-audit table, kept apart from tab:boundary because its rows are
    # bridges to the superseded edition, not candidate constructions.
    ("transport", "06_results.tex", "tab:provenance",
     lambda: [[_first_where("transport_uncertainty_scenarios_%d.csv" % _transport_year(),
                            "deterministic", structural_scenario=name)]
              for name in ("legacy_pes_control", "pes_corrected_12_9")]),
    # The fleet-implied fuel diagnostic: the band cells print as ranges (text to the
    # parser), so each row reconciles on the observed control and the ratio.
    ("transport", "05_validation.tex", "tab:fuelgap",
     lambda: [[_first_where("transport_fleet_fuel_diagnostic_%d.csv" % _transport_year(),
                            "control_TJ", fuel=f),
               _first_where("transport_fleet_fuel_diagnostic_%d.csv" % _transport_year(),
                            "ratio_mid_over_control", fuel=f)]
              for f in ("Petrol", "Diesel", "CNG")]),
    ("transport", "S1_uncertainty.tex", "tab:mc",
     lambda: [[_mc("within_sector", "transport", "mean_Mt"),
               _mc("cross_sector", "transport", "mean_Mt")],
              [_mc("within_sector", "transport", "P2.5_Mt"),
               _mc("cross_sector", "transport", "P2.5_Mt")],
              [_mc("within_sector", "transport", "P97.5_Mt"),
               _mc("cross_sector", "transport", "P97.5_Mt")],
              [_mc("within_sector", "transport"),
               _mc("cross_sector", "transport")],
              [_mc("within_sector", "Road transport"),
               _mc("cross_sector", "Road transport")],
              [_mc("within_sector", "Mixed off-road (1A4c/1A2)"),
               _mc("cross_sector", "Mixed off-road (1A4c/1A2)")]]),
    # ---- waste (August 2026 repair round) ----
    ("waste", "06_results.tex", "tab:results",
     lambda: [[_cell("waste_by_stream_%d.csv" % _waste_year(), "subitem", s, "emissions_Gg"),
               _cell("waste_by_stream_%d.csv" % _waste_year(), "subitem", s, "co2e_Mt_AR5"),
               _cell("waste_by_stream_%d.csv" % _waste_year(), "subitem", s, "uncert_pct")]
              for s in ("Open waste burning CO2 (fossil)", "Open waste burning CH4",
                        "Open waste burning N2O",
                        "Managed and unmanaged disposal sites CH4",
                        "Domestic wastewater CH4", "Domestic wastewater N2O")]
             + [[_cell("waste_totals_%d.csv" % _waste_year(), "category", "TOTAL", "co2e_Mt_AR5"),
                 _mc("within_sector", "waste", "approach1_pct_95")]]),
    ("waste", "06_results.tex", "tab:sensitivity",
     lambda: _waste_sensitivity_rows()),
    ("waste", "06_results.tex", "tab:keycat",
     lambda: [[_keycat(c, "level_pct"), _keycat(c, "variance_share_pct_independent_approx")]
              for c in ("Domestic wastewater", "Solid waste disposal",
                        "Open burning of waste")]),
    # Only cells the parser reduces to a bare number survive: rows whose value cell
    # carries a unit suffix ("0.453 kg/cap/day", "0.065 yr^-1", "0.10 / 0", "40% of
    # first panel year") are text to _cell_value and drop out.
    ("waste", "04b_emission_factors.tex", "tab:params",
     lambda: [[_wpar(p)] for p in
              ("uncollected_urban", "uncollected_rural", "burned_fraction",
               "swds_docf", "swds_mcf", "swds_f", "swds_oxidation", "swds_recovery_t",
               "dry_matter", "oxidation_factor", "ww_mcf_sewer",
               "ww_industrial_factor")]),
    ("waste", "06b_air_pollutants.tex", "tab:air",
     lambda: [[_cell("waste_air_pollutants_%d.csv" % _waste_year(), "pollutant", pol, "emissions_kt")]
              for pol in ("CO", "NMVOC", "PM2.5", "HCl", "NOx", "BC", "NH3", "SO2")]),
    ("waste", "S1_uncertainty.tex", "tab:mc",
     lambda: [[_mc("within_sector", n, "mean_Mt"), _mc("within_sector", n, "P2.5_Mt"),
               _mc("within_sector", n, "P97.5_Mt"), _mc("within_sector", n)]
              for n in ("Domestic wastewater", "Solid waste disposal",
                        "Open burning of waste", "waste")]),
    ("waste", "S1_uncertainty.tex", "tab:wastescenarios",
     lambda: [[float(row[col])
               for col in ("deterministic", "P2.5", "P97.5") if row[col] != ""]
              for row in [next(r for r in
                               _rows("waste_uncertainty_scenarios_%d.csv" % _waste_year())
                               if r["structural_scenario"] == name)
                          for name in ("reference", "sewer_all_stagnant",
                                       "sewer_all_flowing",
                                       "sewer_flowing_river_low",
                                       "sewer_flowing_river_high",
                                       "sewer_equal_mix", "bod_india", "no_spinup",
                                       "hies_route_shares", "unresolved_inert",
                                       "unresolved_shallow_dumps",
                                       "unresolved_deep_dumps",
                                       "effluent_ef_low", "effluent_ef_high")]]),
    # The rc11 parameter-rerun table: every cell from its own output, per draw scope.
    ("waste", "S1_uncertainty.tex", "tab:rerunmc",
     lambda: [[_first_where("waste_parameter_mc_%d.csv" % _waste_year(), col, scope=s)
               for col in ("deterministic", "mean", "P2.5", "P50", "P97.5")]
              for s in ("Domestic wastewater", "Solid waste disposal",
                        "Open burning of waste", "SECTOR")]),
    # The pooled component-lognormal table beside it, from the national MC file.
    ("aviation", "06_results.tex", "tab:two-year",
     lambda: _aviation_two_year_rows()),
    ("aviation", "06_results.tex", "tab:source-bridge",
     lambda: _aviation_bridge_rows()),
    ("aviation", "06_results.tex", "tab:bridge-results",
     lambda: _aviation_estimate_rows()),
    ("fugitives", "06_results.tex", "tab:segments",
     lambda: _fugitives_segment_rows()),
    ("power", "03_study_area_and_data.tex", "tab:fuel",
     lambda: _power_fuel_rows()),
    ("power", "03_study_area_and_data.tex", "tab:captive",
     lambda: _power_captive_rows()),
    ("power", "06_results.tex", "tab:results",
     lambda: _power_results_rows()),
    ("power", "06_results.tex", "tab:sensitivity",
     lambda: _power_sensitivity_rows()),
    ("power", "06_results.tex", "tab:scenarios",
     lambda: _power_scenarios_rows()),
    ("power", "06_results.tex", "tab:keycat",
     lambda: _power_keycat_rows()),
    ("power", "06b_air_pollutants.tex", "tab:air",
     lambda: _power_air_rows()),
    ("power", "05_validation.tex", "tab:heatrate",
     lambda: _power_heatrate_rows()),
    ("residential", "06_results.tex", "tab:configs",
     lambda: _residential_configs_rows()),
    ("residential", "06_results.tex", "tab:sensitivity",
     lambda: _residential_sensitivity_rows()),
    ("residential", "03_study_area_and_data.tex", "tab:fuel",
     lambda: _residential_fuel_rows()),
    ("residential", "06_results.tex", "tab:results",
     lambda: _residential_streams_rows()),
    ("residential", "06b_air_pollutants.tex", "tab:air",
     lambda: _residential_air_pair_rows()),
    ("residential", "03_study_area_and_data.tex", "tab:hiesdiag",
     lambda: _residential_hiesdiag_rows()),
    ("residential", "06_results.tex", "tab:hies",
     lambda: _residential_hies_rows()),
    ("transport", "04_methods.tex", "tab:fuelbridge",
     lambda: _transport_fuelbridge_rows()),
    ("agriculture", "06_results.tex", "tab:national",
     lambda: _agriculture_national_rows()),
    ("agriculture", "06_results.tex", "tab:provincial",
     lambda: _agriculture_provincial_rows()),
    ("agriculture", "06_results.tex", "tab:benchmark",
     lambda: _agri_benchmark_rows()),
    ("agriculture", "06_results.tex", "tab:districttop",
     lambda: _agri_districttop_rows()),
    ("agriculture", "06_results.tex", "tab:mc",
     lambda: _agri_mc_rows()),
    ("agriculture", "06_results.tex", "tab:keycat",
     lambda: _agri_keycat_rows()),
    ("agriculture", "06_results.tex", "tab:nledger",
     lambda: _agri_nledger_rows()),
    ("agriculture", "06_results.tex", "tab:stages",
     lambda: _agri_stages_rows()),
    ("agriculture", "06b_air_pollutants.tex", "tab:apresults",
     lambda: _agri_apresults_rows()),
    ("agriculture", "06b_air_pollutants.tex", "tab:apunc",
     lambda: _agri_apunc_rows()),
    ("agriculture", "06b_air_pollutants.tex", "tab:apstruct",
     lambda: _agri_apstruct_rows()),
    ("agriculture", "06b_air_pollutants.tex", "tab:apbench",
     lambda: _agri_apbench_rows()),
    ("agriculture", "06b_air_pollutants.tex", "tab:spatialstreams",
     lambda: _agri_spatialstreams_rows()),
    ("agriculture", "10_appendix.tex", "tab:crt",
     lambda: _agri_crt_rows()),
    ("agriculture", "10_appendix.tex", "tab:unc",
     lambda: _agri_unc_rows()),
    ("agriculture", "S2_provenance.tex", "tab:s2live",
     lambda: _agri_s2live_rows()),
    ("agriculture", "04b_emission_factors.tex", "tab:sensitivity",
     lambda: _agri_sensitivity_rows()),
    ("agriculture", "04c_shared_ledger.tex", "tab:fertmix",
     lambda: _agri_fertmix_rows()),
] + NATIONAL_TABLES


_AGRI_ORDER = ("Enteric fermentation", "Manure management", "Managed soils",
               "Rice cultivation", "Urea application", "Field burning of residues", "TOTAL")
_NLEDGER_LABELS = ("Total N excreted", "to grazing", "to managed systems",
                   "diverted as dung-cake fuel", "NH3-N + NOx-N (Frac_GasMS)",
                   "leaching, N2, and N2O-N", "= N available for application",
                   "direct soil N2O-N", "NH3-N + NOx-N (Frac_GASM)", "leaching/run-off",
                   "= retained in the soil nitrogen pool",
                   "housing, yards and storage NH3-N", "field-application NH3-N")

# Registered LABELLED tables: (document, section, label, expected [(row label, values)]).
# The comparator joins printed rows to the engine BY LABEL (a prefix of the row's first text
# cell), so a value printed beside the wrong name fails by name. These are the tables whose
# rows are categories, sectors or ledger flows - the ones where a swap is silent to the
# ordinal comparison above.
# =============================================================================================
# THE TECHNICAL SUPPLEMENT'S REFERENCE-YEAR CATEGORY x GAS ACCOUNT (tab:categories)
#
# The October 2026 supplement restates the inventory's primary national result as a hand-typed
# table: 22 IPCC codes x 3 gases plus totals, 60 printed quantities, none of which any getter
# resolved when it arrived. The sectioned corpus never needed a registry entry for the same
# numbers because its version is GENERATED (sections/gen_tab_categorygas.tex, the stored query
# tab_categorygas) and held byte-for-byte by test_paper_artefacts.py. A hand-typed restatement
# has no such protection, and 60 claims in DOC_CLAIMS would be 60 chances to mistype one.
#
# Registering it as a table guards more than the magnitudes. The row ORDER (descending total),
# the row COUNT, and the DASH PATTERN are all checked, and the dash pattern is the caption's
# own claim: "a dash denotes no contribution to this reported row, not a national completeness
# notation". A dash therefore has to mean "this (code, gas) has no atom", which is exactly what
# emitting a cell only where the key exists tests. 1.A.3.a prints 0.000 for CH4 rather than a
# dash - the stream exists and rounds to zero - so zero and absent are not interchangeable
# here, and a rule that treated them as the same would pass a table that lost that distinction.
#
# WHAT THIS DOES NOT GUARD, named rather than left to be discovered: the printed category
# NAMES. The supplement abbreviates them for a narrower column ("Manufacturing and
# construction" against the engine's "Industrial fuel combustion (1A2)"), so comparing them to
# the engine's names would fail for an editorial reason, not a defect. The label is the IPCC
# code, which is the identity the numbers hang on. The names remain the author's.
# =============================================================================================

_SUPPLEMENT_CATEGORY_TABLE_PERIOD = "FY2023-24"
_SUPPLEMENT_CATEGORY_TABLE_CONFIG = "REF_2023_24"
_SUPPLEMENT_GASES = ("CO2", "CH4", "N2O")


def _supplement_category_gas_rows():
    """[(label, [cells])] for tab:categories, from the semantic annual fact's atom grain.

    The atom grain is the one the reference year ships: fact_annual carries a category_gas
    grain only for the survey configuration, so reading "category_gas" here would silently
    select three S-configuration rows and compare the reference table against them.
    """
    import collections
    rows = [r for r in read_rows(os.path.join(OUT, "semantic", "fact_annual.csv"))
            if r["period_id"] == _SUPPLEMENT_CATEGORY_TABLE_PERIOD
            and r["configuration_id"] == _SUPPLEMENT_CATEGORY_TABLE_CONFIG
            and r["grain"] == "atom"]
    if not rows:
        raise AssertionError(
            "no %s/%s atom rows in the semantic annual fact - tab:categories would be "
            "compared against nothing" % (_SUPPLEMENT_CATEGORY_TABLE_PERIOD,
                                          _SUPPLEMENT_CATEGORY_TABLE_CONFIG))
    by_gas = collections.defaultdict(float)
    total = collections.defaultdict(float)
    for r in rows:
        value = float(r["co2e_Mt_AR5"] or 0.0)
        by_gas[(r["ipcc_code"], r["gas"])] += value
        total[r["ipcc_code"]] += value
    out = []
    for code in sorted(total, key=lambda c: (-total[c], c)):
        cells = [by_gas[(code, g)] for g in _SUPPLEMENT_GASES if (code, g) in by_gas]
        # The footnoted row prints its code as a footnote marker alone, so it is named by
        # its text cell instead; see the note above on tuple labels.
        label = ("", "Railway non-traction") if "/" in code else code
        out.append((label, cells + [total[code]]))
    out.append((("", "Total"),
                [sum(v for (_c, g), v in by_gas.items() if g == gas)
                 for gas in _SUPPLEMENT_GASES] + [sum(total.values())]))
    return out


LABELLED_TABLES = [
    ("national", "08_key_categories.tex", "tab:keycat",
     lambda: [(KEYCAT_PRINTED.get(r["category"], r["category"]),
               [float(r["level_Mt_co2e_AR5"]), float(r["level_pct"]),
                float(r["variance_share_pct_independent_approx"])])
              for r in _keycat_rows()]),
    ("national", "06_results.tex", "tab:sectors",
     lambda: [(SECTORS_PRINTED[s],
               [_sector(s), 100.0 if s == "TOTAL" else float(_sector_row(s)["share_pct"]),
                float(_sector_row(s)["uncert_pct_95"])])
              for s in ("agriculture", "power", "transport", "waste", "residential",
                        "fugitives", "ippu", "industry", "railways", "aviation", "TOTAL")]),
    ("agriculture", "06_results.tex", "tab:national",
     lambda: _agri_labelled(_agriculture_national_rows, _AGRI_ORDER, "Agriculture total")),
    ("agriculture", "06_results.tex", "tab:mc",
     lambda: _agri_labelled(_agri_mc_rows, _AGRI_ORDER)),
    ("agriculture", "06_results.tex", "tab:keycat",
     lambda: _agri_labelled(_agri_keycat_rows,
                            ("Enteric fermentation", "Managed soils", "Manure management",
                             "Rice cultivation", "Urea application",
                             "Field burning of residues"))),
    # the nitrogen ledger's transfers: excretion into grazing, managed systems and the
    # dung-cake diversion that crosses to Energy, then the field and TAN stages
    ("agriculture", "06_results.tex", "tab:nledger",
     lambda: list(zip(_NLEDGER_LABELS, _agri_nledger_rows()))),
    # v2's technical supplement, not the shipped version's - see DOCS["national-v3"]
    ("national-v3", "technical_supplement.tex", "tab:categories",
     _supplement_category_gas_rows),
]


# rc42 (the twentieth review's M-7): the 68 label-aware entries for the ordinal tables with
# text row labels live in labelled_tables.py (imported last: it reads the helpers above).
# power tab:captive stays ordinal - its identity column is the fiscal year, a number.
from paper_numbers.labelled_tables import NEW_LABELLED  # noqa: E402

LABELLED_TABLES.extend(NEW_LABELLED)
