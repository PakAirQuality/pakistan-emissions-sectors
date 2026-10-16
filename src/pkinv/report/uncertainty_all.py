"""Cross-sector Monte-Carlo uncertainty (IPCC Approach 2) over every registered sector.

Until this existed the national total was published as a bare 363 Mt with no band, while
each sector carried a per-component Approach-1 uncert_pct that nothing aggregated. The
machinery was already here and unused: core.montecarlo.run is sector-agnostic, and every
engine declares MC_DISTRIBUTION = "lognormal" - a declaration written in anticipation of
this module and consumed by nothing until now.

AGRICULTURE'S OWN RUN IS UNTOUCHED. core.montecarlo's docstring warns that the RNG stream
is fragile: random.Random.gauss caches its paired Box-Muller variate, so the count and
order of gauss() calls determine every subsequent draw. This module is a separate
invocation with its own component list; the agriculture-scoped Monte Carlo
(pkinv.sectors.agriculture.montecarlo, in the companion research repository) still calls
core.montecarlo.run with exactly the arguments it always did, so outputs/uncertainty_
montecarlo.csv is bit-identical. A test asserts it.

TWO SCENARIOS, BECAUSE THE HONEST ANSWER IS A RANGE.

  independent        Every component draws its own error. This is standard IPCC Approach 2
                     practice when correlations are not quantified, and it is what the
                     per-sector runs would give.

  fossil_correlated  Every CO2 component in the five fuel-combustion sectors shares one
                     draw. Those factors are not independent - aviation, power, road
                     transport, railways and residential all take their CO2 per TJ from the
                     same IPCC 2006 default tables, so if the guidelines' carbon contents
                     are biased, they are biased together.

The truth is between them, and the gap between them is itself the finding: an inventory
that reports only the independent band understates the national uncertainty by exactly
that much. Reporting both costs one extra run and removes the need to guess.

Why not simply declare the correlation and let core.montecarlo handle it: components carry
a corr_group, but tests/test_sector_contract.py forbids a group spanning categories, and
that guard is worth more than the convenience. Cross-category correlation is expressed here
instead, on a copy of the components, so no sector's own rows are modified.

Usage:  python3 -m pkinv.report.uncertainty_all
Writes: outputs/national_uncertainty_montecarlo.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import factors
from pkinv.core import montecarlo as mc_core
from pkinv.core import registry
from pkinv.paths import OUTPUTS
from pkinv.core.shared_parameter_draws import SEED as NATIONAL_SEED

# The sectors whose CO2 comes from the IPCC 2006 default fuel-carbon tables - that is, the
# sectors reporting CO2 under an IPCC 1.A code. Agriculture (3.G/3.H urea and liming), IPPU
# (2.A.1 process CO2), waste (4.C.2 open burning) and fugitives (1.B.2 venting and flaring)
# are excluded because their CO2 comes from a different chapter and a different argument.
#
# INDUSTRY WAS MISSING FROM THIS TUPLE for the whole of the release in which industrial fuel
# combustion was added. It burns natural gas and six petroleum products through exactly the
# Table 2.3 entries the group exists to correlate, and leaving it out understated the
# correlated national band by a whole module. Nothing failed, because the membership was a
# hand-written literal that no test compared against the inventory. It is still written out
# here for readability, but fuel_combustion_sectors() below derives the same set from the
# components and their IPCC codes, and a test asserts the two agree - so the next
# fuel-burning module cannot be forgotten the way this one was.
FUEL_SECTORS = ("aviation", "industry", "power", "railways", "residential", "transport")
# One group PER PHYSICAL FACTOR, not one group for all fuel combustion. See core.factors:
# if the IPCC carbon content for gas/diesel oil is wrong it is wrong wherever diesel burns -
# road, rail, off-road, industrial boilers - and that says nothing about natural gas. The
# first implementation pooled every fossil-CO2 component of every fuel-burning sector into a
# single draw, which asserts that diesel, petrol, gas, coal and jet kerosene are all wrong
# together in the same direction. That is not a physical claim, and it inflated the correlated
# band, making the paper's headline finding look better supported than it was.
SHARED_FOSSIL_GROUP = "shared_fossil_co2_factor:"

FUEL_COMBUSTION_CODE = "1.A"


def fuel_combustion_sectors(components=None):
    """Sectors with at least one CO2 component under an IPCC 1.A code, derived not declared.

    The category -> IPCC code mapping is the completeness table's, which is already the
    repository's single statement of which engine category sits under which code and is
    itself tested against the gap register.
    """
    from pkinv.report import completeness
    codes = {}
    for row in completeness.ROWS:
        if len(row) >= 5 and row[4]:
            codes.setdefault(row[4], set()).add(row[0])
    if components is None:
        components, _cats, _sector_of = registry.build_all()
    out = set()
    for c in components:
        if c["gas"] != "CO2":
            continue
        if any(code.startswith(FUEL_COMBUSTION_CODE)
               for code in codes.get(c["category"], ())):
            out.add(c["_sector"])
    return out


def pooled(correlate_fossil=False):
    """registry.build_all(), optionally with the shared fuel-carbon factors correlated.

    The correlation is applied to registry.build_all()'s copies, so no sector's own rows
    are modified -- a test asserts that.
    """
    components, categories, sector_of = registry.build_all()
    if correlate_fossil:
        for c in components:
            fuel = factors.factor_id(c)
            if fuel is None:
                continue
            if c.get("corr_group"):
                # A SECTOR'S OWN DECLARATION IS NEVER OVERWRITTEN. This assignment used to be
                # unconditional, and it silently destroyed correlation the sector had already
                # declared: power groups its four grid CO2 rows under 1a1a_toe_activity,
                # because they share one TOE-to-terajoule conversion, and replacing that with a
                # fuel-carbon group left them correlated through nothing. The scenario then
                # came out NARROWER than the independent baseline - the power band fell from
                # 9.94 to 7.87 percent - which is impossible for added positive correlation
                # and was the symptom that exposed it.
                #
                # This machinery gives a component ONE group, so the two claims cannot both be
                # expressed: rows sharing a declared activity error stay in that group and sit
                # outside the fuel-carbon scenario. Modelling both would need each component's
                # variance split into activity and factor parts, which the contract does not
                # carry. The exclusion is reported by excluded_from_fossil_scenario() rather
                # than being silent.
                continue
            c["corr_group"] = "%s%s" % (SHARED_FOSSIL_GROUP, fuel)
    return components, categories, sector_of


def excluded_from_fossil_scenario(components=None):
    """Fossil-CO2 rows the correlated scenario cannot reach, and the group that holds them.

    Reported because a scenario that quietly omits four of the power sector's five CO2 rows
    is not the scenario its caption claims."""
    if components is None:
        components, _cats, _sector_of = registry.build_all()
    return [(c["_sector"], c["subitem"], c["corr_group"]) for c in components
            if factors.factor_id(c) is not None and c.get("corr_group")]


# Per-component RNG streams, so a sector's published band moves only when that sector moves.
# See core.montecarlo's docstring: under the shared sequential stream, adding eighteen
# industrial-fuel components shifted waste's disposal median while waste stood still.
STREAM = "per_component"

# The PUBLISHED national run uses ten times the sector default. At 10,000 draws the reported
# half-widths carry a Monte Carlo standard error of a few hundredths of a point, which is the
# same order as the residual movement that made six bands come out very slightly narrower
# under correlation than under independence. A number and its noise floor should not be the
# same size when the paper is drawing a conclusion from their difference. Sector-scoped runs
# keep the 10,000-draw default and their bit-identical published percentiles.
NATIONAL_N_ITER = 100000

# The sampling discipline the PUBLISHED national run uses, named here rather than spelled at
# the call site, so that a test asking "does the paper describe the model that shipped?" has
# one thing to read. The paper described the superseded row-level model for a full release
# after this became "parameter", because the fact lived in an argument.
NATIONAL_STREAM = "parameter"

# THE INJECTED MODULES (rc12, the eighth review's P0). These sectors have native
# uncertainty engines whose draws this pool used to re-express as mean-preserving
# lognormals - compressing waste's rerun-engine upper tail (sector P97.5 ~98.9 Mt
# arrived at the national row as 63.5) and shifting fugitives' bounded
# split-triangular median (25.43 -> 23.79). The pool now consumes their persisted
# draw files (outputs/mc_draws/, written by each sector's own engine on its own
# published seed) by draw index. Injection severs no correlation: both modules are
# CRN-islands in parameter_scope.csv - no dependency group spans them and any other
# module - and a tripwire test keeps that true.
#   module -> (draw file name, distribution_id)
INJECTED_MODULES = {
    "waste": ("waste_parameter_rerun", "parameter_rerun_ledger_true"),
    "fugitives": ("fugitives_bounded", "bounded_split_triangular"),
}

# THE DECLARED CROSS-ISLAND COUPLING (Wave 6, per-draw gas). One column of an
# injected file is a PARAMETER CHANNEL rather than a category: the fugitives
# engine's post-meter factor multiplier per draw. The combustion sectors book
# delivered gas NET of the leak share this factor sets (rc19), and until this
# channel existed the share was FIXED across national draws while fugitives drew
# the same factor +/-60 percent - the physical-atmosphere identity ("leaked gas
# is never also burned") held at the mean and in no single realisation. The
# channel carries NO new randomness (it re-expresses a draw the island already
# made), severs nothing (no z-stream is shared; the island's own draws are
# untouched), and the tagged net_of_leak components are scaled deterministically
# per draw by (1 - leak_det*m_d)/(1 - leak_det). This is the one licensed
# exception to the island rule, and the tripwire test names it.
COUPLING_COLUMNS = {
    "fugitives": ("POST_METER_INDUSTRIAL_MULTIPLIER",),
}


def gas_coupling_scalers(components, coupling, n_iter):
    """{component_ident: [scale_d]} for every net_of_leak-tagged component.

    scale_d = (1 - leak_det*m_d) / (1 - leak_det): the draw's own combusted
    fraction over the deterministic one, m_d the fugitives post-meter factor
    multiplier. Deterministic given the draw file - no RNG is consumed, so the
    ensemble's bit-identical-prefix property survives by construction."""
    mult = coupling.get("POST_METER_INDUSTRIAL_MULTIPLIER")
    if mult is None:
        raise SystemExit(
            "net_of_leak components exist but the fugitives draw file carries "
            "no POST_METER_INDUSTRIAL_MULTIPLIER column - regenerate the draw "
            "stage (python3 -m pkinv.sectors.fugitives.uncertainty draws); a "
            "fixed leak share across draws is the per-draw identity failure "
            "this coupling exists to close")
    from pkinv.sectors.fugitives import post_meter
    leak = post_meter.whole_gas_leak_share()
    det = 1.0 - leak
    scales = [(1.0 - leak * m) / det for m in mult[:n_iter]]
    out = {}
    for c in components:
        if c.get("net_of_leak"):
            ident = c.get("_mc_key") or "%s|%s|%s" % (c["category"], c["subitem"],
                                                      c["gas"])
            out[ident] = scales
    return out


def _load_injected(components, sector_of=None):
    """(category_injected, sector_injected, metas) from the persisted draw files.

    STALENESS GUARD: a draw file records the deterministic value of every column,
    and this refuses to run if the live components no longer sum to those values -
    a stale file would silently misstate the sector, and 'regenerate the draw
    stage' is a better failure than a wrong national band.
    """
    from pkinv.core import mc_draws
    cat_injected, sector_injected, metas = {}, {}, {}
    coupling = {}
    for module, (name, _dist) in INJECTED_MODULES.items():
        columns, meta = mc_draws.read(name)
        live = {}
        for c in components:
            if c.get("_sector") == module:
                live[c["category"]] = live.get(c["category"], 0.0) + c["co2e_Mt_AR5"]
        for cat, det in meta["deterministic"].items():
            if cat in COUPLING_COLUMNS.get(module, ()):
                continue        # a per-draw parameter channel, not a category
            live_val = (sum(live.values()) if cat == "MODULE_TOTAL"
                        else live.get(cat))
            if live_val is None or abs(live_val - det) > 1e-6:
                raise SystemExit(
                    "%s draw file is STALE: column %r recorded deterministic %.8f "
                    "but the live components sum to %s - re-run the sector draw "
                    "stage (python3 -m pkinv.sectors.%s.uncertainty draws)"
                    % (module, cat, det, live_val, module))
        for cat, draws in columns.items():
            if cat in COUPLING_COLUMNS.get(module, ()):
                coupling[cat] = draws
            elif cat == "MODULE_TOTAL":
                sector_injected[module] = draws
            else:
                cat_injected[cat] = draws
        metas[module] = meta
    return cat_injected, sector_injected, metas, coupling


def native_components(components, n_iter, seed=NATIONAL_SEED, dung_basis="survey"):
    """Shared native nitrogen and rank-heat draws for this reference ensemble.

    The annual/category and downstream draw products call the same native replay;
    neither may substitute the superseded independent component approximation.
    """
    from pkinv.core.shared_parameter_draws import (Draws, nitrogen_realisations,
        power_coal_realisations, dung_mass_multiplier, residue_burning_realisations)
    from pkinv.core import gwp
    shared = Draws(n_iter, "persistent_parameters", seed)
    nitrogen, _closure = nitrogen_realisations(2024, shared)
    coal = power_coal_realisations(2024, shared)
    burning = residue_burning_realisations(2024, shared)
    native = {}
    for c in components:
        if c.get("_sector") == "power" and c["subitem"].startswith("Coal "):
            native[c["_mc_key"]] = coal[c["gas"]] * gwp.GWP["AR5"].get(
                "CH4_fossil" if c["gas"] == "CH4" else c["gas"], 1) / 1000
        elif (c.get("_sector") == "agriculture" and c["gas"] == "N2O"
              and c["category"] in ("Manure management", "Managed soils")):
            key = "ghg:" + c["_mc_key"]
            if key not in nitrogen:
                raise ValueError("native N2O recipe missing for %s" % key)
            native[c["_mc_key"]] = nitrogen[key] * gwp.GWP["AR5"]["N2O"] / 1000
        elif c.get("_sector") == "agriculture" and c["category"] == "Field burning of residues":
            native[c["_mc_key"]] = burning[c["gas"]] * gwp.GWP["AR5"][c["gas"]] / 1000
        elif (dung_basis == "ledger" and c.get("_sector") == "residential"
              and c["subitem"].startswith("Dung cake ")):
            import numpy as np
            from pkinv.core import parameters
            _row, groups, residual, _derived = parameters.decompose([c])[0]
            log = np.zeros(n_iter)
            for group, sigma in groups.items():
                if group.startswith(("livestock:", "activity:livestock:")) or group in ("1a4b_dung", "1a4b_dung_chain"):
                    continue
                log += shared.normal(group, 2024) * sigma - sigma * sigma / 2
            if residual:
                raise ValueError("ledger dung has an unexplained residual after material-flow replay")
            native[c["_mc_key"]] = float(c["co2e_Mt_AR5"]) * np.exp(log) * dung_mass_multiplier(2024, shared)
    return native, shared


def run(correlate_fossil=False, n_iter=mc_core.N_ITER, seed=NATIONAL_SEED, prebuilt=None,
        stream=None, cross_sector=True):
    """Return (by_category, by_sector, total_samples).

    Two passes over the same component list in the same order. Relabelling a component's
    category changes neither the parameter order nor the correlation-group set, so both
    passes draw an IDENTICAL RNG stream - the same physical realisation viewed two ways.

    Their totals still differ in the last floating-point digit, because the two passes
    accumulate into a different number of buckets (agriculture's six categories collapse
    into one sector bucket) and addition is not associative in floating point. The test
    asserts agreement to twelve significant figures rather than bit-equality, which is the
    honest form of the claim.

    prebuilt lets a caller supply an already-built (components, categories, sector_of)
    tuple. Building all seven sectors costs about ten seconds - dominated by transport's
    fleet model and residential's import of the agriculture manure chain - so the test
    suite builds once and reuses.
    """
    components, categories, _sector_of = prebuilt or pooled(correlate_fossil)
    # Pin each component's RNG identity before either run, so the by-sector run is the same
    # draws re-aggregated rather than a second independent simulation.
    for c in components:
        c["_mc_key"] = "%s|%s|%s" % (c["category"], c["subitem"], c["gas"])
    stream = STREAM if stream is None else stream
    # The injected sector engines (parameter stream only). The draw files carry
    # 100,000 draws; a shorter run takes the PREFIX, which is principled because
    # both engines' streams are strictly extendable - draw i is draw i at any
    # n_iter (tests assert the 10k prefix reproduces the published sector runs).
    cat_injected = sector_injected = None
    scalers = None
    native, shared = {}, None
    if stream == "parameter":
        native, shared = native_components(components, n_iter, seed)
    if stream == "parameter" and INJECTED_MODULES:
        cat_all, sector_all, _metas, coupling = _load_injected(components)
        cat_injected = {k: v[:n_iter] for k, v in cat_all.items()}
        sector_injected = {k: v[:n_iter] for k, v in sector_all.items()}
        short = [k for k, v in cat_injected.items() if len(v) < n_iter]
        if short:
            raise SystemExit("draw files carry fewer than n_iter=%d draws for %s"
                             % (n_iter, short))
        # Wave 6: the per-draw gas identity. The tagged net-of-leak components
        # scale by the draw's own combusted fraction, from the fugitives file's
        # parameter channel - see COUPLING_COLUMNS for the licence.
        scalers = gas_coupling_scalers(components, coupling, n_iter)
    by_category, total_samples, cat_samples = mc_core.run(
        components, categories, n_iter=n_iter, seed=seed, has_sinks=False,
        stream=stream, return_samples=True, cross_sector=cross_sector,
        injected=cat_injected, component_scalers=scalers,
        component_values=native, parameter_draws=shared)

    relabelled = [dict(c, category=c["_sector"]) for c in components]
    sector_names = [s.NAME for s in registry.all_sectors()]
    by_sector, _, sector_samples = mc_core.run(relabelled, sector_names,
                                               n_iter=n_iter, seed=seed, has_sinks=False,
                                               stream=stream, return_samples=True,
                                               cross_sector=cross_sector,
                                               injected=sector_injected,
                                               component_scalers=scalers,
                                               component_values=native, parameter_draws=shared)
    # The standard error of each published half-width, by batch means over the same
    # draws - and, since rc12's asymmetric surface, of each published quantile.
    for stats, samples in ((by_category, cat_samples), (by_sector, sector_samples)):
        for key, row in stats.items():
            row["rel_se_pp"] = mc_core.batch_standard_error(samples[key])
            row["quantile_se"] = mc_core.batch_quantile_se(samples[key])
    return by_category, by_sector, total_samples


def _row_distribution(scope, name, sector_of):
    """The distribution family a row's draws ACTUALLY came from (rc12: per-row
    truth, where a single constant used to claim lognormal for rows the injected
    sector engines drew)."""
    if scope == "national":
        return ("mixture: injected sector engines (%s) + mean_preserving_lognormal "
                "remainder" % ", ".join(sorted(INJECTED_MODULES)))
    module = name if scope == "sector" else sector_of.get(name)
    if module in INJECTED_MODULES:
        return INJECTED_MODULES[module][1]
    if module == "agriculture":
        return "native_conserved_nitrogen_plus_shared_parameter_multipliers"
    return "mean_preserving_lognormal"


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = []
    totals, sectors = {}, {}
    total_draws = None
    names = [s.NAME for s in registry.all_sectors()]
    _comps, _cats, sector_of = registry.build_all()
    # THE TWO SCENARIOS, re-expressed for the parameter model. They used to ask whether the
    # shared fossil fuel-carbon factors were independent or drawn once; correlation is intrinsic
    # now, so the question is WHERE SHARING STOPS - at the module boundary, as an inventory
    # compiled sector by sector implicitly assumes, or at the physical quantity.
    for scenario, cross in (("within_sector", False), ("cross_sector", True)):
        by_category, by_sector, samples = run(n_iter=NATIONAL_N_ITER,
                                              stream=NATIONAL_STREAM, cross_sector=cross)
        totals[scenario] = by_category["TOTAL"]
        sectors[scenario] = by_sector
        if scenario == "within_sector":
            total_draws = samples
        for name in names:
            rows.append((scenario, "sector", name, by_sector[name]))
        for cat, stats in by_category.items():
            if cat != "TOTAL":
                rows.append((scenario, "category", cat, stats))
        rows.append((scenario, "national", "TOTAL", by_category["TOTAL"]))

    path = asset_path(OUTPUTS, "national_uncertainty_montecarlo.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # aggregation_level spells out what `scope` meant. The manuscript quoted "transport"
        # for the transport MODULE in a table and for the road-transport CATEGORY in the prose
        # beneath it - 11.54 against 11.96 - with nothing in either saying which. A reader
        # cannot tell two numbers apart when both are labelled the same thing.
        # distribution_id is per-row TRUTH since rc12: waste rows carry the
        # ledger-true rerun engine's draws, fugitives the bounded split-triangular,
        # the rest the lognormal surrogate - one constant used to claim lognormal
        # for all of them. rel_down/rel_up are the asymmetric surface: (P50-P2.5)/P50
        # and (P97.5-P50)/P50, which a single symmetric half-width cannot carry.
        w.writerow(["scenario", "scope", "aggregation_level", "name", "mean_Mt", "P2.5_Mt",
                    "P50_Mt", "P97.5_Mt", "rel_uncert_pct_MC_95",
                    "rel_down_pct_95", "rel_up_pct_95",
                    "rel_uncert_se_pp", "p025_se_Mt", "p975_se_Mt",
                    "n_iter", "approach1_pct_95", "distribution_id",
                    "source_registry", "correlation_model"])
        model = {"within_sector": "parameters shared within a module only; the same physical "
                                  "factor is a different quantity in each sector",
                 "cross_sector": "parameters shared by physical identity across modules; one "
                                 "diesel carbon content for road, rail, power and industry"}
        for scenario, scope, name, s in rows:
            level = {"national": "national", "sector": "module",
                     "category": "category"}[scope]
            qse = s.get("quantile_se") or {}
            down = (s["p50"] - s["p025"]) / s["p50"] * 100.0 if s["p50"] else 0.0
            up = (s["p975"] - s["p50"]) / s["p50"] * 100.0 if s["p50"] else 0.0
            w.writerow([scenario, scope, level, name, round(s["mean"], 3),
                        round(s["p025"], 3), round(s["p50"], 3), round(s["p975"], 3),
                        round(s["rel_pct"], 2), round(down, 2), round(up, 2),
                        "" if s.get("rel_se_pp") is None else round(s["rel_se_pp"], 4),
                        "" if not qse else round(qse["p025_se"], 4),
                        "" if not qse else round(qse["p975_se"], 4),
                        NATIONAL_N_ITER, round(s["approach1_pct"], 2),
                        _row_distribution(scope, name, sector_of),
                        "national_uncertainty_sources.csv",
                        model[scenario]])

    _write_sources()
    _write_convergence(total_draws)
    _print_summary(totals, sectors, names)


def _write_sources():
    """outputs/national_uncertainty_sources.csv: the eighth review's item (2) - a
    registry of WHICH engine, distribution, parameterization, seed and draw file
    stands behind each module's national draws, so distribution_id is a pointer
    into provenance rather than a bare label."""
    from pkinv.core import mc_draws
    path = asset_path(OUTPUTS, "national_uncertainty_sources.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["module", "engine", "distribution_id", "parameterization",
                    "seed", "n_iter", "draw_file", "draw_file_sha256", "note"])
        for module in sorted(INJECTED_MODULES):
            name, dist = INJECTED_MODULES[module]
            _cols, meta = mc_draws.read(name)
            param = {"waste": "waste_uncertainty_inputs_2024.csv + data/waste_params.csv "
                              "(bounded rows: published ranges)",
                     "fugitives": "fugitives_uncertainty_inputs_2024.csv"}[module]
            w.writerow([module, meta["engine"], dist, param, meta["seed"],
                        meta["n_iter"], meta["file"], meta["sha256"], meta["note"]])
        w.writerow(["(all other modules)",
                    "pkinv.core.montecarlo.run stream=parameter",
                    "mean_preserving_lognormal",
                    "national_uncertainty_parameters.csv (signed shared groups) + "
                    "component uncert_pct",
                    NATIONAL_SEED, NATIONAL_N_ITER, "", "",
                    "drawn in the national loop on identity-seeded per-parameter "
                    "streams; no draw file because the loop itself is the engine"])
        w.writerow(["(shared gas activity)", "", "", "", "", "", "", "",
                    "DECLARED BOUNDARY (rc19, the per-draw gas identity): the "
                    "residential, CNG, industrial and captive delivered volumes "
                    "share one activity draw through the cross-module dependency "
                    "group delivered_gas_ogra_3_31 (data/parameter_scope.csv) - "
                    "one OGRA Table 3.31 publication, one draw direction, each "
                    "module's own declared width. The FUGITIVES leak side stays "
                    "a separately injected island (the draw-file injection above "
                    "is licensed by exactly that independence) and the GRID gas "
                    "volume rides its own NEPRA meter; both exclusions are "
                    "deliberate and the deterministic closure lives in "
                    "national_gas_closure.csv"])
    print("uncertainty sources -> %s" % os.path.basename(path))


def _write_convergence(total_draws):
    """outputs/national_uncertainty_convergence.csv: the eighth review's item (8).

    Prefix quantiles at N = 10k/25k/50k/100k - principled because every stream in
    the pool is identity-seeded or strictly sequential, so draw i is draw i at any
    N - plus batch-means standard errors of each quantile at the full N."""
    from pkinv.core import mc_draws
    series = {"national TOTAL (within_sector)": total_draws}
    for module in sorted(INJECTED_MODULES):
        cols, _meta = mc_draws.read(INJECTED_MODULES[module][0])
        series["%s module (sector engine draws)" % module] = cols["MODULE_TOTAL"]
    path = asset_path(OUTPUTS, "national_uncertainty_convergence.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["series", "n_draws", "P2.5_Mt", "P50_Mt", "P97.5_Mt",
                    "p025_se_Mt", "p50_se_Mt", "p975_se_Mt"])
        for name, draws in series.items():
            for n in (10000, 25000, 50000, 100000):
                if n > len(draws):
                    continue
                chunk = sorted(draws[:n])
                qse = mc_core.batch_quantile_se(draws[:n]) or {}
                w.writerow([name, n,
                            round(mc_core.percentile(chunk, 0.025), 4),
                            round(mc_core.percentile(chunk, 0.50), 4),
                            round(mc_core.percentile(chunk, 0.975), 4),
                            round(qse.get("p025_se", 0.0), 4),
                            round(qse.get("p50_se", 0.0), 4),
                            round(qse.get("p975_se", 0.0), 4)])
    print("uncertainty convergence -> %s" % os.path.basename(path))


def _print_summary(totals, sectors, names):
    ind, cor = totals["within_sector"], totals["cross_sector"]
    print("Cross-sector Monte Carlo (N=%d, seed=%d, 95%% CI)"
          % (NATIONAL_N_ITER, mc_core.SEED))
    # The lognormal REMAINDER is mean-preserving; the injected engines are NOT and
    # are not meant to be - waste's rerun anchors its bounded effluent draw at the
    # published MODE, so its mean sits above the deterministic estimate by
    # construction (its own docstrings state this), and since rc12 that honest gap
    # reaches the national mean instead of being flattened by a surrogate. The
    # deterministic total is printed beside the mean and median so nobody reads
    # either as a revised estimate.
    deterministic = sum(c["co2e_Mt_AR5"] for c in pooled()[0])
    print("  deterministic total %.2f Mt; Monte-Carlo mean %.2f (the +%.1f Mt gap is "
          "the injected engines' mode-anchored asymmetry, stated not hidden); "
          "median %.2f" % (deterministic, ind["mean"],
                           ind["mean"] - deterministic, ind["p50"]))
    print("  asymmetric interval: -%.1f%% / +%.1f%% about the median"
          % ((ind["p50"] - ind["p025"]) / ind["p50"] * 100,
             (ind["p975"] - ind["p50"]) / ind["p50"] * 100))
    print("  within_sector      [%7.1f, %7.1f]  +/- %4.1f%%   (Approach 1: %4.1f%%)"
          % (ind["p025"], ind["p975"], ind["rel_pct"], ind["approach1_pct"]))
    print("  cross_sector       [%7.1f, %7.1f]  +/- %4.1f%%"
          % (cor["p025"], cor["p975"], cor["rel_pct"]))
    print("  sharing parameters across modules rather than within them widens the national")
    print("  band by %.2f points" % (cor["rel_pct"] - ind["rel_pct"]))
    by_sector = sectors["within_sector"]
    for name in sorted(names, key=lambda n: -by_sector[n]["mean"]):
        s = by_sector[name]
        print("  %-13s %7.2f Mt  [%7.2f, %7.2f]  +/- %5.1f%% (A1 %5.1f%%)"
              % (name, s["mean"], s["p025"], s["p975"], s["rel_pct"], s["approach1_pct"]))


if __name__ == "__main__":
    main()
