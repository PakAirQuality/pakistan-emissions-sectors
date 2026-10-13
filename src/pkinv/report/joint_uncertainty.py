"""One uncertainty statement per figure, with its parts kept apart.

WHAT THIS IS FOR. The Monte Carlo is mature - 100,000 draws, correlated within and across
sectors, native draw files, convergence and decomposition published, a national interval of
-10.0/+15.7 percent - and it stops at the annual product. national_monthly_2024.csv has no
interval column. Neither ADM2 view has one. The grid has none. A reader looking at a district
in June has no bound at all, and the one number they can find - the national interval - is the
NARROWEST statement this release makes, which is exactly the wrong one to borrow.

THREE KINDS, AND THEY MAY NOT BE ADDED. What exists is parametric uncertainty (probabilistic,
from the MC), timing brackets and placement brackets. The brackets are disagreements between
two defensible readings of the same evidence, and 06_results.tex already says it: "no
probability attaches to any spread". Summing a structural disagreement into a sigma would
manufacture a distribution nobody measured. So this table keeps them in separate columns with
their epistemic class on each, and offers one combined number as an ENVELOPE - a bound, not a
distribution - built by widening the probabilistic interval by the structural half-widths
rather than by convolving them.

A BRACKET ONLY BITES ON THE FIGURE IT CAN MOVE, which is why the key is (category, resolution)
and not category alone. Re-allocating a category across districts does not change its national
total; re-profiling it across months does not change its annual one:

    resolution        parametric   timing   placement
    annual national       yes         -         -
    monthly national      yes        yes        -
    annual ADM2           yes         -        yes
    monthly ADM2          yes        yes       yes

That table is why a district map has a wider bound than the headline, which is a question the
paper could not previously answer.

WHAT THE ENVELOPE DOES NOT CONTAIN IS PUBLISHED BESIDE IT. The priced-timing and
priced-placement category counts LIVE IN THE SHIPPED FILE, never in this prose - an
earlier revision froze "three of twenty / placement for four" here and both went
stale twice as the hindcast, crosscheck and bracket lanes grew; the ADM1 register
still carries the no_alternative_declared rows for the categories no admissible
alternative exists for. An envelope that silently omitted those would be narrower than the
truth while reading as though it were wider, so `unpriced_components` names them on every row.
That column is the one that keeps this product honest, and filling those cells with a weak
alternative to make the envelope look rigorous would make the dataset worse, not better.
The two timing SOURCES are different kinds and the rc18 ensemble treats them differently:
a measured hindcast dispersion is DRAWN in the common ensemble's monthly layer
(timing_basis = measured_hindcast_dispersion below), while the power variant is a
structural reading with no dispersion to draw and stays a conditional configuration
(timing_basis = structural_variant).

THE ONE RESOLUTION THIS TABLE DOES NOT HOLD IS TIME-ACROSS-YEARS. Every row here conditions
on the reference year, and the header above is only half a sentence without its other half:
the national interval is the narrowest statement this release makes, and the WIDEST is the
interval on a year-on-year CHANGE. Those live in
outputs/pakemis_longitudinal_uncertainty.csv and outputs/pakemis_trend_uncertainty.csv,
because a change is not a resolution of the reference year - it is a different quantity, and
folding it into this lattice as though it were a fifth cell would invite exactly the
borrowing this table exists to stop.

RECOMPUTES NOTHING. Every quantity is read from an output that already exists - the
release_manifest discipline, for the same reason: a second arithmetic path is a second vintage
waiting to disagree with the first.

Usage:  python3 -m pkinv.report.joint_uncertainty
Writes: outputs/pakemis_joint_uncertainty.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

# The four figures a reader can be looking at. They form a LATTICE and not a chain: refining
# from annual to monthly adds a timing bracket, refining from national to ADM2 adds a
# placement one, and the two middle resolutions are therefore incomparable. Railways is the
# case that proves it - timing priced at 15.1 percent, placement unpriced - so its monthly
# national bound is legitimately wider than its annual district bound. A finer figure may
# never be narrower along a REAL refinement edge, which is what the tests assert.
RESOLUTIONS = ("annual_national", "monthly_national", "annual_adm2", "monthly_adm2")
APPLIES = {
    "annual_national": (True, False, False),
    "monthly_national": (True, True, False),
    "annual_adm2": (True, False, True),
    "monthly_adm2": (True, True, True),
}

PRICED = "priced"
UNPRICED = "declared-unpriced"
NOT_APPLICABLE = "not-applicable"

# Within a category the parametric error is PERFECTLY CORRELATED: one emission factor moves
# every district and every month of that category together. A user aggregating districts must
# therefore add intervals linearly and never in quadrature, which would make a national total
# look an order of magnitude more certain than the MC says it is. Published as a column
# because a rule that lives only in a document is a rule nobody applies, and proved by a
# worked example in tests/test_joint_uncertainty.py because a rule in a column is a rule
# nobody checks.
CORRELATION_WITHIN_CATEGORY = 1.0

ENVELOPE_KIND = ("bound, not a distribution: the probabilistic interval widened by the "
                 "structural half-widths, never convolved with them")

# Which module's brackets speak for which engine category. Declared rather than matched on a
# substring, because a silent miss here reads as "no alternative exists" - the strongest claim
# this file can make - when it would only mean the join failed.
CATEGORY_MODULE = {
    "Enteric fermentation": "agriculture",
    "Manure management": "agriculture",
    "Rice cultivation": "agriculture",
    "Managed soils": "agriculture",
    "Field burning of residues": "agriculture",
    "Urea application": "agriculture",
    "Open burning of waste": "waste",
    "Solid waste disposal": "waste",
    "Domestic wastewater": "waste",
    "Domestic aviation": "aviation",
    "Electricity and heat production": "power",
    "Captive gas self-generation (1A2)": "power",
    "Road transport": "transport",
    "Mixed off-road (1A4c/1A2)": "transport",
    "Railways": "railways",
    "Railway non-traction energy (1A2/1A4c unresolved)": "railways",
    "Fugitive emissions from oil and gas": "fugitives",
    "Residential fuel combustion": "residential",
    "Cement production": "ippu",
    # rc52: the three IPPU categories that entered the reference
    "Ammonia production": "ippu",
    "Iron and steel production": "ippu",
    "Lubricant use": "ippu",
    "Industrial fuel combustion (1A2)": "industry",
}

# The hindcast scores a STREAM, and a stream belongs to a category. Same discipline.
# EXTENDED at rc20 (the fifteenth review's ensemble ask): every stream the hindcast
# actually scores now maps, so a measured dispersion is never left unpriced - the
# extension moved timing from 3 to 6 categories and the common ensemble draws each
# of them (timing_basis = measured_hindcast_dispersion). The remaining categories
# stay unpriced because no hindcast truth exists for them, not because nobody looked.
HINDCAST_CATEGORY = {
    "transport_petrol": "Road transport",
    "transport_diesel": "Road transport",
    "railways_diesel": "Railways",
    "industry_diesel": "Industrial fuel combustion (1A2)",
    "power_liquids": "Electricity and heat production",
    "aviation_domestic_jp1": "Domestic aviation",
}
PROFILE_VARIANT_CATEGORY = "Electricity and heat production"


def deterministic_by_category():
    """{category: Mt AR5} as the inventory PUBLISHES it, for the reference year.

    Read from the atomic annual product rather than recomputed: it is the same table the
    external control in tests/test_agriculture_control.py is checked against, so the two
    cannot drift into two answers about what the inventory estimated.
    """
    import collections as _collections
    out = _collections.defaultdict(float)
    for row in _rows("pakemis_atomic_annual.csv"):
        if row.get("period_id") != "FY2023-24":
            continue
        value = row.get("co2e_Mt_AR5", "")
        if value in ("", None):
            continue
        out[row["category"]] += float(value)
    return dict(out)


def _rows(name, root=OUTPUTS):
    return read_rows(asset_path(root, name))


def parametric():
    """{category: {scenario: (mean_Mt, down_pct, up_pct)}} from the published MC.

    Both correlation scenarios are carried. cross_sector is the one the envelope uses - it is
    the wider of the two wherever they differ, because a factor shared between sectors cannot
    be assumed to move independently in each.
    """
    out = {}
    for row in _rows("national_uncertainty_montecarlo.csv"):
        if row["aggregation_level"] != "category":
            continue
        out.setdefault(row["name"], {})[row["scenario"]] = (
            float(row["mean_Mt"]), float(row["rel_down_pct_95"]),
            float(row["rel_up_pct_95"]))
    return out


def timing_brackets():
    """{category: (pct, source)} - how far a MONTHLY figure could move under a defensible
    alternative profile, as a percentage of that figure.

    Two sources, both already published and neither built for this purpose:

      * the temporal hindcast, which scored candidate profiles against the OCAC panel and
        reports WAPE on monthly SHARES. A weighted absolute share error is directly the
        fraction by which a month's value could be wrong under the alternative, so it is
        carried across as-is;
      * the power profile variant, which prices one station's fuel mix being constant within
        the year against the reference. Its share columns give a per-month disagreement, and
        the bracket is the largest of them.

    The best-scoring candidate is taken per category, not the worst: the bracket asks how far
    the reference could move under the best ALTERNATIVE reading, and a candidate that
    hindcasts badly is evidence against itself rather than a wider bound.
    """
    out = {}
    best = {}
    for row in _rows("benchmark_temporal_hindcast.csv"):
        category = HINDCAST_CATEGORY.get(row["stream"])
        if category is None or row["status"] != "scored" or not row["wape_monthly_shares"]:
            continue
        wape = float(row["wape_monthly_shares"])
        if category not in best or wape < best[category]:
            best[category] = wape
    for category, wape in best.items():
        out[category] = (100.0 * wape,
                         "temporal hindcast WAPE on monthly shares "
                         "(benchmark_temporal_hindcast.csv)")

    # THE THIRD SOURCE (Wave 3): a published two-instrument crosscheck IS a measured
    # dispersion - the same profile built a second way from evidence the first never
    # used, disagreeing by a mean absolute share error that is exactly the L1
    # quantity WAPE measures (Sigma|delta|/12; NEVER the worst-month figure, which is
    # a different statistic the prose quotes for a different purpose). A hindcast
    # entry wins where both exist: it scores against held truth, a crosscheck only
    # against a rival model.
    crosscheck_categories = {
        "fertiliser": "Managed soils",
        "burning": "Field burning of residues",
    }
    gaps = {}
    for row in _rows("monthly_crosschecks.csv"):
        category = crosscheck_categories.get(row["check"])
        if category is None:
            continue
        gaps.setdefault(category, []).append(abs(float(row["difference"])))
    for category, deltas in gaps.items():
        if category in out or len(deltas) != 12:
            continue
        out[category] = (100.0 * sum(deltas) / 12.0,
                         "two-instrument crosscheck mean absolute share gap "
                         "(monthly_crosschecks.csv: %s)"
                         % [k for k, v in crosscheck_categories.items()
                            if v == category][0])

    # The structural fuel-mix variant is a FALLBACK, never an override. Until Wave 6
    # this assignment was unconditional and it CLOBBERED power's measured hindcast
    # dispersion (best WAPE 45.24%) with the variant's smaller structural number -
    # so the largest category in the inventory was silently excluded from the drawn
    # set while rc20's changelog claimed it was in. The precedence is the declared
    # one: measured beats structural, and the variant prices only a category no
    # instrument has measured.
    spread = 0.0
    for row in _rows("pakemis_power_profile_variant.csv"):
        reference = float(row["reference_share"] or 0.0)
        variant = float(row["variant_share"] or 0.0)
        if reference > 0:
            spread = max(spread, abs(variant - reference) / reference)
    if spread > 0 and PROFILE_VARIANT_CATEGORY not in out:
        out[PROFILE_VARIANT_CATEGORY] = (
            100.0 * spread,
            "constant-within-year fuel mix against the reference profile "
            "(pakemis_power_profile_variant.csv)")
    return out


# Bracket stream_match -> the engine categories that stream actually carries. A
# bracket naming a stream outside this map keeps its module-wide reach (the
# pre-Wave-6 behaviour, correct for the module-scoped transport and captive
# brackets); a mapped stream prices only its own categories.
STREAM_MATCH_CATEGORY = {
    "rice_area": ("Rice cultivation",),
    # The captive bracket prices captive placement, not the grid's - the grid has
    # its own points-vs-fallback bracket since Wave 6.
    "captive_gas": ("Captive gas self-generation (1A2)",),
    "power_coal": ("Electricity and heat production",),
}


def placement_brackets():
    """{category: {level: (pct, source)}} - how far a SUB-NATIONAL figure could move under a
    defensible alternative proxy.

    The bracket files publish a disagreement in SHARE POINTS between two allocations of the
    same mass. A share that could be 14.7 points different is a figure that could be wrong by
    14.7 points of the category's total, so the percentage carries across directly. Province
    spreads bound an ADM1 reading and district spreads an ADM2 one; where only the province
    file prices a stream, that spread is used at ADM2 too and the source says so, because a
    coarser bracket is a real bound on a finer figure and refusing to carry it would publish
    `declared-unpriced` where evidence exists.
    """
    out = {}
    for name, level in (("pakemis_spatial_brackets.csv", "adm1"),
                        ("pakemis_spatial_brackets_adm2.csv", "adm2")):
        for row in _rows(name):
            proof = row["status"].startswith("structurally_invariant")
            if not (row["status"].startswith("priced") or proof) \
                    or not row["spread_pp"]:
                continue
            try:
                spread = abs(float(row["spread_pp"]))
            except ValueError:
                continue                        # a declared non-numeric spread, e.g. a hole
            if proof:
                # A PROOF of zero spread is a priced bracket, not an absence: the
                # district panel fixes each shape's mass, so the alternative raster
                # cannot move an ADM2 figure. Until Wave 6 this status fell through
                # the priced filter and residential shipped as declared-unpriced
                # beside genuine absences - the opposite of what the proof shows.
                # A zero proof never overrides a real nonzero bracket.
                scoped_p = STREAM_MATCH_CATEGORY.get(row.get("stream_match", ""))
                for category, module in CATEGORY_MODULE.items():
                    if module != row["module"]:
                        continue
                    if scoped_p is not None and category not in scoped_p:
                        continue
                    out.setdefault(category, {}).setdefault(
                        level, (0.0, "%s (%s; structurally invariant - proof, "
                                     "not absence)" % (row["alternative_id"], name)))
                continue
            # A bracket that declares a stream prices THAT stream's category, never
            # its whole module. The module-wide join was correct while every bracket
            # was module-scoped (transport's fuel split, captive's points); the rc26
            # rice GCD bracket broke the assumption - joined by module, its 4.66 pp
            # was priced onto Enteric fermentation (151.5 Mt of livestock whose
            # placement rides a census, not a paddy map) and that alone widened the
            # district-month envelope by 2.3 points in each direction. Scoped here
            # (Wave 6): a stream-scoped bracket reaches only the categories its
            # stream belongs to; module-scoped brackets keep the old reach.
            scoped = STREAM_MATCH_CATEGORY.get(row.get("stream_match", ""))
            for category, module in CATEGORY_MODULE.items():
                if module != row["module"]:
                    continue
                if scoped is not None and category not in scoped:
                    continue
                held = out.setdefault(category, {}).get(level, (0.0, ""))
                if spread > held[0]:
                    out[category][level] = (spread, "%s (%s)" % (row["alternative_id"], name))
    return out


# --- completeness, the fifth kind (rc18, the twelfth review's separation) ------------
#
# Parameter, profile, placement and structure were already columns of this lattice or
# rows of the configurations file; completeness was the one kind with no seat - it
# lived in the register as notation keys and in the coverage ranking as comparator
# magnitudes, and the reviewer's "integrate completeness uncertainty" is answered the
# repository's way: a BOUND beside the interval, never a distribution inside it. A
# category with a comparator-bounded absent remainder carries that bound; everything
# else carries no_bound_declared, which is a statement, not a blank.
#
# The rows below map the coverage ranking's comparator names onto lattice categories.
# Absences with NO lattice category to sit in (F-gases, ammonia) cannot appear here;
# completeness_national() carries them instead.
COVERAGE_BOUND_CATEGORY = {
    "1A2 (all estimated) (EDGAR)": "Industrial fuel combustion (1A2)",
    "Cement production (EDGAR)": "Cement production",
    "Residential fuel combustion (EDGAR)": "Residential fuel combustion",
    "Managed soils (Cui 2021)": "Managed soils",
}

# EDGAR's Pakistani F-gases, reported separately from every domain row and excluded
# from both sides of the national comparator (data/benchmarks.csv, gas_scope notes).
# No engine category exists to attach it to, so it rides the national statement; a
# test pins this literal to the number inside the benchmarks register's own note.
FGAS_BOUND_MT = 11.54
FGAS_BOUND_SOURCE = ("EDGAR 2025 booklet F-gases, reported separately "
                     "(data/benchmarks.csv gas_scope notes); no engine category "
                     "exists to carry it")


def completeness_bounds():
    """{category: (bound_Mt, source)} - the comparator-bounded absent mass beside
    each category, from the coverage ranking (which already carries every
    caveat about what a comparator magnitude is and is not)."""
    out = {}
    for row in _rows("national_priority_rankings.csv"):
        if row["ranking"] != "coverage":
            continue
        category = COVERAGE_BOUND_CATEGORY.get(row["name"])
        if category is None:
            continue
        out[category] = (float(row["metric"]),
                         "%s - national_priority_rankings.csv coverage rank %s: %s"
                         % (row["name"], row["rank"], row["note"][:160]))
    return out


def completeness_national():
    """The composed national completeness statement: what the held bounds say is
    outside the inventory, and why the pieces must not be naively summed."""
    bounds = completeness_bounds()
    industry = bounds.get("Industrial fuel combustion (1A2)", (0.0, ""))[0]
    composable = industry + FGAS_BOUND_MT
    return {
        "composable_bound_Mt": round(composable, 2),
        "pieces": "1A2 unresolved solid-fuel residual %.2f + F-gases %.2f"
                  % (industry, FGAS_BOUND_MT),
        "not_composed": ("ammonia's CRT comparator (19.4, red-flagged as a "
                         "chemical-industries aggregate) and cement's whole-IPPU "
                         "EDGAR row (9.99, not like-for-like) are bounds on "
                         "OVERLAPPING or mislabelled scopes and are listed, not "
                         "summed"),
        "kind": "bound beside the interval, never a distribution inside it",
    }


def build():
    param = parametric()
    deterministic = deterministic_by_category()
    timing = timing_brackets()
    placement = placement_brackets()
    completeness = completeness_bounds()

    missing = set(CATEGORY_MODULE) - set(param)
    if missing:
        raise ValueError("the Monte Carlo publishes no category row for %s; this table would "
                         "silently omit it" % sorted(missing))
    extra = set(param) - set(CATEGORY_MODULE)
    if extra:
        raise ValueError("the Monte Carlo carries categories this table does not map to a "
                         "module: %s - add them rather than dropping them" % sorted(extra))

    out = []
    for category in sorted(param):
        cross = param[category]["cross_sector"]
        within = param[category]["within_sector"]
        for resolution in RESOLUTIONS:
            has_t, has_p = APPLIES[resolution][1], APPLIES[resolution][2]
            level = "adm2" if resolution.endswith("adm2") else None

            if not has_t:
                t_pct, t_status, t_source = 0.0, NOT_APPLICABLE, ""
            elif category in timing:
                t_pct, t_source = timing[category]
                t_status = PRICED
            else:
                t_pct, t_status, t_source = 0.0, UNPRICED, ""

            if not has_p:
                p_pct, p_status, p_source = 0.0, NOT_APPLICABLE, ""
            elif category in placement:
                held = placement[category]
                p_pct, p_source = held.get(level) or held.get("adm1") or held["adm2"]
                p_status = PRICED
            else:
                p_pct, p_status, p_source = 0.0, UNPRICED, ""

            unpriced = [name for name, status in (("timing", t_status),
                                                  ("placement", p_status))
                        if status == UNPRICED]
            out.append({
                "category": category,
                "module": CATEGORY_MODULE[category],
                "resolution": resolution,
                # estimate_Mt IS THE MONTE CARLO MEAN, and it is not the inventory's
                # published estimate: for a skewed distribution the two differ on purpose.
                # The name read as "the estimate" and an audit reasonably took the gap for
                # staleness, so the deterministic figure is published beside it and the
                # divergence is a column rather than a discrepancy someone has to discover.
                "estimate_Mt": round(cross[0], 4),
                "deterministic_Mt": round(deterministic.get(category, 0.0), 6),
                "mc_mean_minus_deterministic_Mt": round(
                    cross[0] - deterministic.get(category, 0.0), 6),
                "parametric_low_pct": round(-cross[1], 3),
                "parametric_high_pct": round(cross[2], 3),
                "parametric_low_pct_within_sector": round(-within[1], 3),
                "parametric_high_pct_within_sector": round(within[2], 3),
                "parametric_kind": "probabilistic: 100,000-draw Monte Carlo, 95% interval",
                "timing_pct": round(t_pct, 3),
                "timing_status": t_status,
                "timing_source": t_source,
                # rc18: the two timing kinds diverge in the common ensemble - a
                # measured dispersion is DRAWN there, a structural variant is a
                # conditional configuration with nothing to draw.
                "timing_basis": ("measured_hindcast_dispersion"
                                 if "hindcast" in t_source
                                 else "measured_crosscheck_disagreement"
                                 if "crosscheck" in t_source
                                 else "structural_variant" if t_source
                                 else ""),
                "placement_pct": round(p_pct, 3),
                "placement_status": p_status,
                "placement_source": p_source,
                "bracket_kind": "structural: a disagreement between defensible readings, "
                                "carrying no probability",
                "envelope_low_pct": round(-(cross[1] + t_pct + p_pct), 3),
                "envelope_high_pct": round(cross[2] + t_pct + p_pct, 3),
                "envelope_kind": ENVELOPE_KIND,
                "completeness_bound_Mt": (
                    round(completeness[category][0], 2)
                    if category in completeness else ""),
                "completeness_bound_source": (
                    completeness[category][1] if category in completeness
                    else "no_bound_declared"),
                "unpriced_components": ";".join(unpriced) or "none",
                "correlation_within_category": CORRELATION_WITHIN_CATEGORY,
                "aggregation_rule": "WITHIN a category, intervals add linearly across "
                                    "districts and months - never in quadrature. ACROSS "
                                    "categories, do not add at all: the Monte Carlo measures "
                                    "the dependence and publishes it at "
                                    "aggregation_level=national",
            })
    return out


def national_envelope(rows=None):
    """The national bound at each resolution.

    THE CORRELATION RULE IS DIRECTIONAL, and the first cut of this function got it wrong in a
    way worth recording. Within a category the parametric error is perfectly correlated, so
    intervals add linearly. ACROSS categories it is not - the Monte Carlo measures the actual
    dependence and publishes the answer at aggregation_level=national. Adding the twenty
    category intervals linearly instead inflated the national bound from -10.0/+15.7 to
    -22.0/+45.3, which is not a conservative reading of the evidence but a different and
    wrong one: it asserts that every sector's factors move together, which the correlation
    model explicitly denies.

    So the parametric term is READ from the MC's national row and never re-derived. The
    structural brackets are then added on top, mass-weighted across categories. They may be
    added because they are bounds rather than distributions - a bound is allowed to be
    conservative - and because nothing measures how two proxy disagreements co-vary.
    """
    rows = rows if rows is not None else build()
    national = next(r for r in _rows("national_uncertainty_montecarlo.csv")
                    if r["aggregation_level"] == "national"
                    and r["scenario"] == "cross_sector")
    down, up = float(national["rel_down_pct_95"]), float(national["rel_up_pct_95"])
    out = {}
    for resolution in RESOLUTIONS:
        mine = [r for r in rows if r["resolution"] == resolution]
        total = sum(r["estimate_Mt"] for r in mine)
        structural = sum(r["estimate_Mt"] * (r["timing_pct"] + r["placement_pct"]) / 100.0
                         for r in mine)
        widening = 100.0 * structural / total
        out[resolution] = (total, -(down + widening), up + widening)
    return out


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    path = asset_path(OUTPUTS, "pakemis_joint_uncertainty.csv")
    write_table(path, list(rows[0]), rows, banner=('# Joint uncertainty by category and by the RESOLUTION of the figure being read.', '# The components are different KINDS and are not added into one sigma; the envelope is a bound.', '# Within a category the parametric error is perfectly correlated: add intervals linearly, never in quadrature.',))

    print("joint uncertainty -> %s" % path)
    print("  %d rows: %d categories x %d resolutions"
          % (len(rows), len(rows) // len(RESOLUTIONS), len(RESOLUTIONS)))
    national = national_envelope(rows)
    print("  the national bound widens as the figure gets finer:")
    for resolution in RESOLUTIONS:
        total, low, high = national[resolution]
        print("    %-18s %7.2f Mt   %+6.2f%% / %+6.2f%%"
              % (resolution, total, low, high))
    for name, status in (("timing", "timing_status"), ("placement", "placement_status")):
        unpriced = sorted({r["category"] for r in rows if r[status] == UNPRICED})
        priced = sorted({r["category"] for r in rows if r[status] == PRICED})
        print("  %s: %d categories priced, %d declared-unpriced"
              % (name, len(priced), len(unpriced)))
        for category in unpriced:
            print("      unpriced: %s" % category)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
