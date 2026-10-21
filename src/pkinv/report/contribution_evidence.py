"""Ten bounded conclusions derived from existing public products.

This is a synthesis layer, not another emissions engine or validation framework.
It reuses the shared configuration/window vocabulary, claim-pointer resolver and
validation-class definitions. Every result carries scope, admission limits, shared
assumptions and exact input hashes. No source is promoted to independent evidence
because the resulting estimates agree.

Run: python -m pkinv.report.contribution_evidence [--check] [--root PATH]
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
from itertools import product
import math
from pathlib import Path

from pkinv.core.configurations import ALL as CONFIGS, REFERENCE
from pkinv.core.io import read_rows, write_or_check
from pkinv.core.reporting_window import CORE_FY_ENDS, CORE_PERIOD_IDS, CORE_SUFFIX, REFERENCE_PERIOD
from pkinv.applications.gas_reallocation.inputs import REFERENCE_YEAR as GAS_REFERENCE_YEAR
from pkinv.paths import ROOT
from pkinv.report.claims import resolve_pointer
from pkinv.report.validation_five_classes import CLASSES, CAN, classify

AIR = f"pakemis_air_annual_{CORE_SUFFIX}.csv"
GHG = "pakemis_ghg_trend_uncertainty.csv"
AXES = "pakemis_structural_trajectories.csv"
COAL = "pakemis_coal_sector_reallocation.csv"
GAS = "pakemis_transition_gas_conclusions.csv"
MATRIX = "pakemis_transition_gas_matrix.csv"
VALIDATION = "pakemis_validation_five_classes.csv"
CATALOG = "data/shared/evidence/validation_catalog.csv"
GAS_BASELINES = "data/shared/parameters/gas_reallocation/baselines.csv"
GAS_PATHWAYS = "data/shared/parameters/gas_reallocation/pathways.csv"
GAS_COHERENCE = "data/shared/parameters/gas_reallocation/coherence.csv"
GAS_REGISTERS = (GAS_BASELINES, GAS_PATHWAYS, GAS_COHERENCE)
CLAIMS_OUT = "pakemis_contribution_claims.csv"
SUMMARY_OUT = "pakemis_contribution_evidence_summary.csv"
INPUTS = (AIR, GHG, AXES, COAL, GAS, MATRIX, VALIDATION, CATALOG) + GAS_REGISTERS
DEPENDENCE_CASES = ("persistent_parameters", "annual_activity_errors")
FULL_SCOPE = "full scope: mixed pathways and D4"
FULL_PATHWAYS = {"M1", "M2", "M3", "D4"}
GAS_DIMS = ("baseline_fertilizer", "baseline_power", "receiving", "displaced",
            "fertilizer_route", "leak_base", "prill_control")
FIELDS = (
    "claim_id", "question", "period_start", "period_end", "metric", "scope",
    "comparison_set", "admission_limit", "result", "reference_value", "value_min",
    "value_max", "unit", "metric_definition", "source_selection", "source_products",
    "source_sha256", "calculation_evidence", "supporting_catalogue_ids",
    "catalogue_interpretation", "shared_assumptions", "missing_components",
    "permitted_interpretation", "required_next_evidence",
)
SUMMARY_FIELDS = ("summary_kind", "group", "entries", "description", "source_product", "sha256")
BANNER = (
    "Bounded conclusions from existing public products; no emissions engine is rerun.",
    "Four published configurations include diagnostic allocation/method choices; no probabilities attach.",
    "Counts are scenario cells or catalogue entries, not independent observations or probabilities of truth.",
    "Input hashes identify the exact source snapshot; regenerate when any input changes.",
)
FOUR_CASES = ";".join(CONFIGS)
ADMISSION = (
    "S uses survey household dung; L assigns all modelled diverted dung to households and is a "
    "diagnostic allocation, not another observed household record. TAN/IPCC is a method choice. "
    "Agreement over these four published configurations is not a complete admissible uncertainty set."
)
SHARED = (
    "Shared activity reconstructions, transferred emission factors, management/control assumptions "
    "and coverage. Livestock history shares a census anchor and reconstructed annual trajectory."
)
MISSING = "Unestimated source categories and other unpriced structural choices are outside this calculation."


def _fmt(value):
    if value is None:
        return ""
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("non-finite claim value")
        return f"{value:.6f}"
    return str(value)


def _path(root, name):
    return Path(root) / name if name.startswith("data/") else Path(root) / "outputs" / name


def direction(values):
    """A deterministic direction, never a probability or statistical confidence claim."""
    values = list(values)
    if not values or any(not math.isfinite(v) for v in values):
        raise ValueError("a direction needs finite, nonempty values")
    if all(v > 0 for v in values):
        return "increase in every compared case"
    if all(v < 0 for v in values):
        return "decrease in every compared case"
    if all(v == 0 for v in values):
        return "zero in every compared case"
    return "direction differs or includes zero"


def air_statistics(rows, pollutant, start, end, reference):
    totals, sectors = defaultdict(float), defaultdict(float)
    coverage = defaultdict(set)
    seen = set()
    for row in rows:
        if row["pollutant"] != pollutant or row["configuration_id"] not in CONFIGS:
            continue
        key = tuple(row[k] for k in ("period_id", "configuration_id", "sector_id", "category", "pollutant"))
        if key in seen:
            raise ValueError("duplicate air source row: %r" % (key,))
        seen.add(key)
        if row["coverage_scope"] != "covered_sources_only":
            raise ValueError("unexpected air coverage scope")
        value = float(row["emissions_Gg"])
        if not math.isfinite(value) or value < 0:
            raise ValueError("invalid air emission quantity")
        cfg, period = row["configuration_id"], row["period_id"]
        coverage[cfg, period].add((row["sector_id"], row["category"]))
        totals[cfg, period] += value
        sectors[cfg, period, row["sector_id"]] += value
    for cfg in CONFIGS:
        for period in {start, end, reference}:
            if (cfg, period) not in totals or totals[cfg, period] <= 0:
                raise ValueError(f"missing or zero air total: {cfg}/{pollutant}/{period}")
            if coverage[cfg, period] != coverage[REFERENCE, start]:
                raise ValueError(f"air category coverage differs: {cfg}/{pollutant}/{period}")
    changes, leaders, shares = {}, {}, {}
    for cfg in CONFIGS:
        changes[cfg] = 100 * (totals[cfg, end] / totals[cfg, start] - 1)
        by_sector = {sector: value for (c, period, sector), value in sectors.items()
                     if c == cfg and period == reference}
        maximum = max(by_sector.values())
        leaders[cfg] = tuple(sorted(s for s, v in by_sector.items() if v == maximum))
        shares[cfg] = 100 * maximum / totals[cfg, reference]
    return changes, leaders, shares


def ghg_endpoint(rows, start, end):
    selected = [r for r in rows if r["start_period"] == start and r["end_period"] == end
                and r["sector_id"] == "national_covered" and r["species_or_metric"] == "CO2e_AR5"]
    keys = [(r["configuration_id"], r["dependence_case"]) for r in selected]
    expected = {(c, d) for c in CONFIGS for d in DEPENDENCE_CASES}
    if len(keys) != len(set(keys)) or set(keys) != expected:
        raise ValueError("GHG endpoint needs each configuration/dependence case exactly once")
    bounds = []
    for row in selected:
        low, high = float(row["P2_5_quantity"]), float(row["P97_5_quantity"])
        if row["unit"] != "Mt_CO2e" or not math.isfinite(low + high) or low > high:
            raise ValueError("invalid GHG interval")
        bounds.extend((low, high))
    reference = next(r for r in selected if r["configuration_id"] == REFERENCE
                     and r["dependence_case"] == "persistent_parameters")
    return selected, reference, bounds


def expected_gas_cases(baselines, pathways, coherence, boundary):
    """Expand the producer's public admission and coherence registers, without its engine."""
    if boundary not in {"territorial", "combined_partial"}:
        raise ValueError("unsupported gas boundary")
    for rows, field in ((baselines, "baseline_id"), (pathways, "pathway_id")):
        if len({r[field] for r in rows}) != len(rows):
            raise ValueError("duplicate gas register identifier")
    admitted = {axis: {r["baseline_id"] for r in baselines
                       if r["axis"] == axis and r["classification"] == "admissible"}
                for axis in ("fertilizer_2B1", "power_conversion", "leak_base", "prill_control")}
    # The claim is explicitly about these admitted readings. A changed register needs
    # a scope review, not automatic reuse of a sentence describing the old alternatives.
    contract = {"fertilizer_2B1": {"FA2"}, "power_conversion": {"PA1", "PA2"},
                "leak_base": {"LB1", "LB2"}, "prill_control": {"PC1", "PC2"}}
    if admitted != contract:
        raise ValueError("gas admission register differs from the bounded claim scope")
    families = {family: {r["pathway_id"] for r in pathways
                         if r["family"] == family and r["role"] == "evidence"}
                for family in ("receiving", "fertilizer", "mixed", "system")}
    if not families["receiving"] or families["fertilizer"] != {"F1", "F2"}:
        raise ValueError("gas pathway register is missing required evidence families")
    if not FULL_PATHWAYS <= families["mixed"] | families["system"]:
        raise ValueError("gas pathway register is missing the full-scope pathways")
    combinations = set()
    for row in coherence:
        if row["coherent"] != "yes" or row["displaced"] not in FULL_PATHWAYS:
            continue
        receiving = families["receiving"] if row["receiving"] == "R*" else {row["receiving"]}
        fertilizer = families["fertilizer"] if row["fertilizer"] == "F*" else {row["fertilizer"]}
        if not receiving <= families["receiving"] | {"none"} or not fertilizer <= families["fertilizer"]:
            raise ValueError("unknown coherent gas pathway")
        for receiving_id, route in product(receiving, fertilizer):
            key = (receiving_id, row["displaced"], route)
            if key in combinations:
                raise ValueError("duplicate coherent gas pathway")
            combinations.add(key)
    if {displaced for _, displaced, _ in combinations} != FULL_PATHWAYS:
        raise ValueError("gas coherence register does not cover the full scope")
    return {(fa, pa, receiving, displaced, route, lb, pc)
            for fa, pa, lb, pc in product(*(admitted[axis] for axis in contract))
            for receiving, displaced, route in combinations
            if boundary != "territorial" or route == "F1"}


def gas_cells(rows, boundary, pollutant, expected_cases):
    """Select the same full-scope cells as the gas producer, preserving NE status."""
    selected = [r for r in rows if r["role"] == "evidence" and r["boundary"] == boundary
                and r["pollutant"] == pollutant and r["displaced"] in FULL_PATHWAYS
                and (boundary != "territorial" or r["fertilizer_route"] == "F1")]
    if not selected:
        raise ValueError("missing gas cells")
    if any(r["reference_year"] != GAS_REFERENCE_YEAR for r in selected):
        raise ValueError("gas evidence cells have an unexpected reference year")
    if any(r["baseline_fertilizer"] != "FA2" for r in selected):
        raise ValueError("gas evidence cells require the admitted FA2 fertilizer baseline")
    keys = [tuple(r[k] for k in GAS_DIMS) for r in selected]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate gas case")
    if not expected_cases or set(keys) != expected_cases:
        raise ValueError("gas evidence cells do not match the complete admitted case set")
    signs = Counter(r["sign"] for r in selected)
    if set(signs) - {"-", "+", "0", "~", "NE"}:
        raise ValueError("unknown gas sign")
    if {r["coverage"] for r in selected} - {"complete", "bound", "reversible"}:
        raise ValueError("unknown gas coverage status")
    reversible = sum(r["coverage"] == "reversible" for r in selected)
    spans = signs["~"] + signs["NE"]
    if spans or reversible:
        result = "unresolved"
    elif set(signs) == {"-"}:
        result = "robust reduction"
    elif set(signs) == {"+"}:
        result = "robust increase"
    elif set(signs) == {"0"}:
        result = "no change"
    else:
        result = "conditional"
    return selected, signs, reversible, spans, result


def build(root=ROOT):
    root = Path(root)
    raw_hash = {name: hashlib.sha256(_path(root, name).read_bytes()).hexdigest() for name in INPUTS}
    data = {name: read_rows(_path(root, name)) for name in INPUTS}
    catalogue = {r["validation_id"]: r for r in data[CATALOG]}
    if len(catalogue) != len(data[CATALOG]):
        raise ValueError("duplicate source validation catalogue identifier")
    start, end = CORE_PERIOD_IDS[0], CORE_PERIOD_IDS[-1]
    claims = []

    def add(claim_id, question, sources, **kw):
        row = {name: "" for name in FIELDS}
        row.update(claim_id=claim_id, question=question, period_start=start, period_end=end,
                   scope="covered national inventory", comparison_set=FOUR_CASES,
                   admission_limit=ADMISSION, shared_assumptions=SHARED, missing_components=MISSING,
                   calculation_evidence="model-output synthesis; not independent validation",
                   source_products=";".join("outputs/" + s if not s.startswith("data/") else s for s in sources),
                   source_sha256=";".join(s + "=" + raw_hash[s] for s in sources))
        row.update(kw)
        for identifier in row["supporting_catalogue_ids"].split(";"):
            if identifier and identifier not in catalogue:
                raise ValueError("unknown supporting catalogue entry: " + identifier)
        claims.append({k: _fmt(v) for k, v in row.items()})

    selected, ref, bounds = ghg_endpoint(data[GHG], start, end)
    add("ghg_decade_direction", "Does covered national CO2e change retain its sign over the published endpoint uncertainty cases?", [GHG],
        metric="CO2e_AR5", comparison_set=FOUR_CASES + ";" + ";".join(DEPENDENCE_CASES),
        result=direction(bounds), reference_value=float(ref["deterministic_change"]),
        value_min=min(bounds), value_max=max(bounds), unit="Mt_CO2e",
        metric_definition="Reference deterministic endpoint change; min/max are outer endpoints of eight separate paired 95% intervals, NOT a pooled 95% interval.",
        source_selection=f"{GHG}#start_period={start},end_period={end},configuration_id={REFERENCE},sector_id=national_covered,species_or_metric=CO2e_AR5,dependence_case=persistent_parameters#deterministic_change",
        supporting_catalogue_ids="mag-national-faostat-series;mag-national-btr",
        catalogue_interpretation="Contextual compilation comparisons; they do not independently validate these paired trend intervals.",
        permitted_interpretation="The endpoint direction is conditional on the represented scope and published dependence models; other structural choices remain outside the intervals.",
        required_next_evidence="Test major common historical activity reconstructions against unused, period-matched source records.")

    air = {p: air_statistics(data[AIR], p, start, end, REFERENCE_PERIOD) for p in ("PM2.5", "SO2", "NOx")}
    for pollutant in ("PM2.5", "SO2"):
        changes, _, _ = air[pollutant]
        add("air_" + pollutant.lower().replace(".", "") + "_decade_direction",
            f"Does the covered {pollutant} endpoint trend retain its sign across the four published configurations?", [AIR],
            metric=pollutant, result=direction(changes.values()), reference_value=changes[REFERENCE],
            value_min=min(changes.values()), value_max=max(changes.values()), unit="percent_change",
            metric_definition="100 x (covered endpoint emissions / covered starting emissions - 1); deterministic configuration range, not a confidence interval.",
            source_selection=f"sum_where:{AIR}#configuration_id={REFERENCE},pollutant={pollutant},period_id={end}#emissions_Gg",
            supporting_catalogue_ids="mag-air-htap-species",
            catalogue_interpretation="HTAP is a partially independent inventory comparison; shared statistics and factors prevent treating agreement as observed truth.",
            permitted_interpretation="A covered-emissions trend under these configurations; it does not establish an ambient-concentration or exposure trend.",
            required_next_evidence="Evaluate factor/control histories and missing-source bounds, including potential changes common to all configurations.")
    for pollutant in ("PM2.5", "NOx"):
        _, leaders, shares = air[pollutant]
        unique = {names for names in leaders.values()}
        same = len(unique) == 1 and len(next(iter(unique))) == 1
        result = ("same leading sector: " + next(iter(unique))[0]) if same else "leading sector differs or is tied"
        detail = "; ".join(c + "=" + "+".join(leaders[c]) for c in CONFIGS)
        add("air_" + pollutant.lower().replace(".", "") + "_sector_leader",
            f"Is the largest covered {pollutant} sector invariant across the four published configurations?", [AIR],
            period_start=REFERENCE_PERIOD, period_end=REFERENCE_PERIOD, metric=pollutant,
            result=result, reference_value=shares[REFERENCE], value_min=min(shares.values()), value_max=max(shares.values()),
            unit="percent_of_covered_emissions",
            metric_definition="Share of the largest covered sector in each configuration; the sectors can differ. " + detail,
            source_selection=f"{AIR}#period_id={REFERENCE_PERIOD},pollutant={pollutant}#emissions_Gg (aggregate by configuration and sector)",
            supporting_catalogue_ids="mag-air-htap-species;mag-residential-hies",
            catalogue_interpretation="Links identify relevant contextual comparisons, not independent confirmation of this sector ranking.",
            permitted_interpretation="Leadership among estimated source categories only; the diagnostic L allocation has not become an independent household observation.",
            required_next_evidence="Constrain household end uses and technology factors; bound omitted sources that could overtake the leading sector.")

    axis_rows = data[AXES]
    allowed = {"priced", "priced_reference_register", "not_priceable_for_year"}
    if {r["status"] for r in axis_rows} - allowed:
        raise ValueError("unknown structural-axis status")
    axis_keys = {(r["axis"], r["fiscal_end_year"]) for r in axis_rows}
    if len(axis_keys) != len(axis_rows):
        raise ValueError("duplicate structural axis/year")
    expected_axes = {(axis, str(year)) for axis in {r["axis"] for r in axis_rows}
                     for year in CORE_FY_ENDS}
    if axis_keys != expected_axes:
        raise ValueError("structural table must retain every axis/year, including explicit refusals")
    n_priced = sum(r["status"] != "not_priceable_for_year" for r in axis_rows)
    add("structural_axis_coverage", "How much of the registered structural axis/year table is numerically evaluated?", [AXES],
        metric="priced_axis_year_rows", comparison_set="registered one-axis alternatives by fiscal year",
        admission_limit="Some registered axes are diagnostics, legacy controls or coverage alternatives; priced does not mean admissible, correct, independent or jointly composable.",
        result=f"{n_priced} priced of {len(axis_rows)} registered axis/year rows; {len(axis_rows)-n_priced} unpriced",
        reference_value=n_priced, unit="axis_year_rows",
        metric_definition="Count of priced plus priced_reference_register rows; denominator is registered axis/year rows, not a probability or completeness estimate.",
        source_selection=f"count_where:{AXES}#status=priced + count_where:{AXES}#status=priced_reference_register",
        calculation_evidence="internal coverage accounting",
        shared_assumptions="The axis register determines what is asked; unregistered alternatives are not counted.",
        missing_components="Rows explicitly refused remain unpriced; absence is not zero effect.",
        permitted_interpretation="A map of which structural questions can currently be calculated, with no probability assigned to axes.",
        required_next_evidence="Prioritize unpriced axes that can reverse a principal claim; preserve refusal reasons for the rest.")

    coal = [r for r in data[COAL] if r["period_id"] == end]
    if len(coal) != 1:
        raise ValueError("latest core year must have one coal-accounting row")
    coal = coal[0]
    change, seam = float(coal["d_national_yoy_S_TAN_Mt"]), float(coal["d_allocation_seam_yoy_Mt"])
    share = None if change == 0 else 100 * seam / change
    if share is not None and abs(share - float(coal["seam_share_of_national_change_yoy_S_TAN_pct"])) > 0.01:
        raise ValueError("coal seam share does not reproduce its published operands")
    add("latest_year_coal_accounting", "How much of the latest covered national annual change is algebraically associated with the coal allocation seam?", [COAL],
        period_start=CORE_PERIOD_IDS[-2], metric="coal_allocation_seam_share", comparison_set=REFERENCE,
        admission_limit="This decomposition contrasts booked accounting with a supply-balance diagnostic; it is not an observed intervention or proof of the destination of residual coal.",
        result="undefined: national change is zero" if share is None else "accounting contribution; physical cause unresolved",
        reference_value=share, unit="percent_of_signed_national_change",
        metric_definition=f"100 x seam annual change ({seam:.6f} Mt) / covered national annual change ({change:.6f} Mt); can exceed 100% or be negative.",
        source_selection=f"{COAL}#period_id={end}#seam_share_of_national_change_yoy_S_TAN_pct",
        calculation_evidence="internal accounting identity; not causal attribution",
        supporting_catalogue_ids="mag-industry-change-attribution;mag-industry-coal-balance",
        catalogue_interpretation="Accounting and compilation checks establish the decomposition, not the actual consuming sector of unresolved coal.",
        shared_assumptions="Supply, station burn and industrial conversion use the same underlying inventory inputs as the central total.",
        missing_components=coal["unresolved_quantity_kind"],
        permitted_interpretation="Report the seam beside the annual trend; do not interpret it as measured emissions avoided by a physical transition.",
        required_next_evidence="Period-matched stocks, exports and consuming-sector fuel records that can distinguish the unresolved residual's explanations.")

    for claim_id, boundary, pollutant in (("gas_domestic_co2e", "territorial", "CO2e_AR5"),
                                          ("gas_domestic_methane", "territorial", "CH4"),
                                          ("gas_combined_footprint", "combined_partial", "CO2e_AR5")):
        expected = expected_gas_cases(*(data[name] for name in GAS_REGISTERS), boundary)
        cells, signs, reversible, spans, result = gas_cells(data[MATRIX], boundary, pollutant, expected)
        pointer = f"{GAS}#boundary={boundary},pollutant={pollutant},scope={FULL_SCOPE}"
        reported = resolve_pointer(root, pointer + "#classification")
        if reported != result or int(resolve_pointer(root, pointer + "#cases")) != len(cells):
            raise ValueError("gas conclusion and matrix do not agree: " + claim_id)
        counts = (f"{len(cells)} cells: {signs['-']} negative intervals; {signs['+']} positive intervals; "
                  f"{spans} spanning or NE; {reversible} potentially reversible through missing terms")
        add(claim_id, "What does the full-scope gas application establish for " + boundary + " " + pollutant + "?", [GAS, MATRIX, *GAS_REGISTERS],
            period_start=GAS_REFERENCE_YEAR, period_end=GAS_REFERENCE_YEAR, metric=pollutant,
            scope="fertilizer-power gas pilot; " + boundary,
            comparison_set="admissible metered-gas baseline; two power readings; two leakage memberships; two prill-control cases; mixed pathways and LNG substitution",
            admission_limit="Complete admitted FA2 case set for FY2023-24, reconstructed from baseline/pathway/coherence registers; only role=evidence and M1/M2/M3/D4. Domestic cells retain F1 only because import route does not alter domestic emissions. Cases share inputs and are not independent observations.",
            result=result + " within tested scope", reference_value=len(cells), unit="scenario_cells",
            metric_definition=counts, source_selection=pointer + "#classification",
            calculation_evidence="paired counterfactual model; admission/completeness and matrix/conclusion consistency checks",
            shared_assumptions="Annual records, screening factors, gas deliverability and displaced-generation assumptions; actual dispatch is unobserved.",
            missing_components="Exporter stages and shipping can reverse a negative partial combined result." if boundary == "combined_partial" else "Operational feasibility and marginal dispatch remain unobserved; broader evidence alternatives are not exhausted.",
            permitted_interpretation="A conditional counterfactual calculation. Numerical negative intervals are not complete-footprint reductions when omitted components can reverse them; case counts are not probabilities of success.",
            required_next_evidence="Resolve exporter stage coverage and import origin for the combined boundary; validate gas-property basis and obtain dispatch/deliverability evidence for operational interpretation.")

    evidence = []
    class_rows = data[VALIDATION]
    classes = Counter(r["five_class"] for r in class_rows)
    if set(classes) - set(CLASSES):
        raise ValueError("unrecognized validation class")
    if len({r["validation_id"] for r in class_rows}) != len(class_rows):
        raise ValueError("duplicate validation catalogue identifier")
    if {r["validation_id"] for r in class_rows} != set(catalogue):
        raise ValueError("validation class product and source catalogue have different entries")
    for row in class_rows:
        source = catalogue[row["validation_id"]]
        role = source.get("calibration_or_validation") or source.get("role") or ""
        if classify(role, source["independence_class"]) != row["five_class"]:
            raise ValueError("stale validation class: " + row["validation_id"])
    for label in CLASSES:
        evidence.append(dict(summary_kind="validation_class", group=label, entries=classes[label],
                             description=CAN[label] + "; entries are not independent emission observations or emission-weighted coverage",
                             source_product="outputs/" + VALIDATION, sha256=raw_hash[VALIDATION]))
    for label, n in sorted(Counter(r["status"] for r in axis_rows).items()):
        evidence.append(dict(summary_kind="structural_axis_status", group=label, entries=n,
                             description="Registered axis/year questions, not a probability distribution or a measure of admissible scope.",
                             source_product="outputs/" + AXES, sha256=raw_hash[AXES]))
    for name in INPUTS:
        evidence.append(dict(summary_kind="source_snapshot", group=name, entries=len(data[name]),
                             description="Exact bytes read for this synthesis; hash changes require regeneration.",
                             source_product=name if name.startswith("data/") else "outputs/" + name,
                             sha256=raw_hash[name]))
    return claims, [{k: _fmt(v) for k, v in r.items()} for r in evidence]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--root", default=ROOT)
    args = parser.parse_args(argv)
    claims, evidence = build(args.root)
    status = write_or_check(Path(args.root) / "outputs" / CLAIMS_OUT, FIELDS, claims, check=args.check, banner=BANNER)
    status |= write_or_check(Path(args.root) / "outputs" / SUMMARY_OUT, SUMMARY_FIELDS, evidence,
                             check=args.check, banner=BANNER)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
