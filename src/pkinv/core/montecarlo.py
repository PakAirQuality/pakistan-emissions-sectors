"""IPCC Approach 2 (Monte Carlo) uncertainty, for any sector.

Mean-preserving lognormal draws per component, with one shared standard normal per
correlation group so that rows split out of a single physical stream for allocation
reasons do not average away a common error.

TWO STREAM DISCIPLINES, AND THE SECOND EXISTS BECAUSE THE FIRST DOES NOT SCALE.

"sequential" is the original: one shared random.Random, one gauss() per ungrouped component
per iteration, in list order. It is load-bearing and fragile - random.Random.gauss caches its
paired Box-Muller variate, so both the COUNT and the ORDER of gauss() calls determine every
subsequent draw across all 10,000 iterations. Changing the component filter, the group set,
or the loop structure silently reshuffles every published percentile.

That is tolerable for a single sector whose component list is stable. It is not tolerable for
a national run over ten sectors that gains components every release: adding eighteen
industrial-fuel rows moved the waste sector's published disposal median from 8.26 to 8.31 Mt,
and waste had not changed at all. A number that moves when an unrelated sector grows is not a
result, and re-anchoring it each round teaches a reader that the bands are soft.

"per_component" gives every component - or every correlation group - its own RNG, seeded from
the run seed and the component's own identity. Adding, removing or reordering a component then
changes that component's draws and nothing else, so a sector's band moves only when the sector
moves. Statistically it is the same estimator: the draws are independent across components
either way, and correlation is still expressed by sharing one stream within a group.

The national run uses per_component. Sector-scoped runs keep sequential so their published
percentiles stay bit-identical, which a test asserts.
"""
import hashlib
import math
import random

from pkinv.core.uncertainty import combine_sum

N_ITER = 10000
SEED = 42
Z95 = 1.959964        # 95% half-width -> 1-sigma


def sigma_log(uncert_pct):
    """Lognormal sigma from a 95% relative half-width (uncert_pct)."""
    rel_sd = (uncert_pct / 100.0) / Z95
    return math.sqrt(math.log(1.0 + rel_sd * rel_sd))


def batch_standard_error(samples, batches=10):
    """The Monte Carlo standard error of the published relative half-width, by batch means.

    The draws are independent, so splitting them into equal batches, computing the reported
    statistic in each and taking the standard error of those is an honest estimate of how much
    the published figure would move on a different seed. It needs no bootstrap resampling and
    no density estimate, and it is computed from the same draws that produced the number.
    """
    n = len(samples) // batches
    if n < 100:
        return None
    widths = []
    for b in range(batches):
        chunk = sorted(samples[b * n:(b + 1) * n])
        lo, mid, hi = (percentile(chunk, 0.025), percentile(chunk, 0.50),
                       percentile(chunk, 0.975))
        if mid:
            widths.append((hi - lo) / 2.0 / mid * 100.0)
    if len(widths) < 2:
        return None
    mean = sum(widths) / len(widths)
    var = sum((w - mean) ** 2 for w in widths) / (len(widths) - 1)
    return math.sqrt(var / len(widths))


def batch_quantile_se(samples, batches=10):
    """Batch-means standard errors of the published QUANTILES themselves, in the
    samples' own units - the convergence diagnostic the asymmetric surface needs
    (rc12): a reader given P2.5/P50/P97.5 instead of one half-width should be
    given each quantile's Monte Carlo noise, not just the half-width's."""
    n = len(samples) // batches
    if n < 100:
        return None
    per_q = {"p025": [], "p50": [], "p975": []}
    for b in range(batches):
        chunk = sorted(samples[b * n:(b + 1) * n])
        per_q["p025"].append(percentile(chunk, 0.025))
        per_q["p50"].append(percentile(chunk, 0.50))
        per_q["p975"].append(percentile(chunk, 0.975))
    out = {}
    for key, vals in per_q.items():
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / (len(vals) - 1)
        out[key + "_se"] = math.sqrt(var / len(vals))
    return out


def percentile(sorted_vals, p):
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p
    lo = int(math.floor(k))
    hi = int(math.ceil(k))
    if lo == hi:
        return sorted_vals[lo]
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (k - lo)


def stream_seed(seed, key):
    """A stable RNG seed for one component or correlation group.

    Deliberately not built on hash(): Python salts str hashing per process, so the same
    component would draw differently between runs and nothing in this file would notice.
    """
    digest = hashlib.blake2b(("%d|%s" % (seed, key)).encode("utf-8"), digest_size=8)
    return int.from_bytes(digest.digest(), "big")


def group_representatives(group_ident_pairs):
    """Lexicographically-first member row identity per group.

    The scenario-invariant anchor for common random numbers: a group's z-stream is keyed
    to a MEMBER of the group, not to the group's (scenario-dependent) name, so the
    representative's realisation is identical across covariance scenarios and only the
    sharing structure differs. Shared by the per_component and parameter modes, because
    the fix living in one of them while the other shipped was the rc2 review's 3.7.
    """
    rep = {}
    for group, ident in group_ident_pairs:
        if group is None:
            continue
        cur = rep.get(group)
        if cur is None or ident < cur:
            rep[group] = ident
    return rep


def group_stream_key(group, rep_ident, cross_sector):
    """The z-stream key for a parameter-mode dependency group.

    Keyed on the group STRING, the within-sector run renames every group "<sector>|<g>"
    and thereby reseeds it: a grouped component drew an unrelated random sequence in the
    two published scenarios, so their comparison mixed the structural effect with a
    wholesale re-draw -- the exact defect the per_component mode documents and fixes,
    never ported here. The PHYSICAL group name plus the representative member's row
    identity is invariant to the renaming: for the sector holding the global
    representative, the correlated and uncorrelated draws are identical, and what remains
    is the dependency structure the scenarios exist to compare.
    """
    physical = group if cross_sector else group.split("|", 1)[1]
    return "group|%s|rep|%s" % (physical, rep_ident)


def run(components, categories, n_iter=N_ITER, seed=SEED, has_sinks=False,
        stream="sequential", return_samples=False, cross_sector=True,
        injected=None, group_qualifier=None, residual_qualifier=None,
        component_scalers=None, component_values=None, parameter_draws=None,
        parameter_year=2024):
    """Return ({category|'TOTAL': stats}, total_samples), or a third value with the draws.

    return_samples=True adds {category|'TOTAL': [draws]} so a caller can quantify the Monte
    Carlo error of what it publishes. It exists because six bands came out very slightly
    NARROWER under correlation than under independence - residential by 0.22 points - and the
    manuscript asserted that correlation cannot narrow a sum. Asserting that the residual is
    sampling noise is not the same as showing it, and batch means over the returned draws
    show it.

    has_sinks=False keeps the historic filter that drops non-positive components. It is
    sum-neutral but NOT stream-neutral under stream="sequential": dropping a row removes a
    gauss() call and can empty a correlation group, so it must stay exactly as it was for
    agriculture.

    stream="per_component" makes each component's draws depend on its own identity rather
    than on its position in the list - see the module docstring for why the national run
    needs that and a sector run does not.

    injected={category: [draws]} (parameter stream only, rc12): those categories'
    components leave the parameter plan entirely and each iteration takes the
    pre-drawn value instead - the mechanism by which waste's ledger-true rerun
    engine and fugitives' bounded split-triangular engine reach the national row
    with their asymmetry intact, rather than being re-expressed as the
    mean-preserving lognormal surrogate this function would otherwise draw.
    Isolation is by construction: every remaining component's z-streams are
    identity-seeded, so excluding a module changes nobody else's draws (a test
    asserts bit-identity), and the injected modules are CRN-islands in
    parameter_scope.csv (the tripwire test), so no shared z is severed.
    """
    injected = injected or {}
    # component_scalers (Wave 6, per-draw gas): {component_ident: [scale_d]} of
    # DETERMINISTIC per-draw multiplicative scales - the licensed cross-island
    # channel by which the net-of-leak gas components carry the fugitives
    # engine's own post-meter factor draw. No randomness enters here: the scales
    # are a function of draws another engine already made and persisted, so
    # every z-stream, every seed and the bit-identical-prefix property are
    # untouched. Parameter stream only, like injection.
    component_scalers = component_scalers or {}
    component_values = component_values or {}
    if (component_values or parameter_draws is not None) and stream != "parameter":
        raise ValueError("native shared parameter replay requires stream='parameter'")
    for identity, values in component_values.items():
        if len(values) < n_iter or any(not math.isfinite(float(v)) for v in values[:n_iter]):
            raise ValueError("invalid native component draws for %s" % identity)
    if component_scalers and stream != "parameter":
        raise ValueError("component_scalers are a parameter-stream mechanism; "
                         "stream=%r cannot consume them" % stream)
    for ident, scales in component_scalers.items():
        if len(scales) < n_iter:
            raise ValueError("component_scalers[%r] carries %d scales for an "
                             "n_iter=%d run" % (ident, len(scales), n_iter))
    if (group_qualifier is not None or residual_qualifier is not None) \
            and stream != "parameter":
        raise ValueError("the qualifiers split dependency-group and residual streams, which "
                         "only the parameter stream has; stream=%r cannot use them" % stream)
    if injected and stream != "parameter":
        raise ValueError("injected draws are a parameter-stream mechanism; "
                         "stream=%r cannot consume them" % stream)
    for cat, draws in injected.items():
        if len(draws) != n_iter:
            raise ValueError("injected[%r] carries %d draws for an n_iter=%d run"
                             % (cat, len(draws), n_iter))
    if has_sinks:
        comps = [c for c in components if c["co2e_Mt_AR5"] != 0]
    else:
        comps = [c for c in components if c["co2e_Mt_AR5"] > 0]
    # The Approach-1 cross-check column keeps seeing the WHOLE inventory: excluding
    # an injected module from the sampling plan must not zero its analytic column.
    a1_comps = comps
    if injected:
        comps = [c for c in comps if c["category"] not in injected]
    native = []
    if component_values:
        remaining = []
        for c in comps:
            identity = c.get("_mc_key") or "%s|%s|%s" % (c["category"], c["subitem"], c["gas"])
            if identity in component_values:
                native.append((c["category"], component_values[identity]))
            else:
                remaining.append(c)
        comps = remaining

    # _mc_key lets a caller pin a component's stream identity across runs that relabel the
    # category column. uncertainty_all does exactly that - it runs once by category and again
    # by sector - and without the pin the two runs would draw differently and the sector bands
    # would stop being a re-aggregation of the category bands.
    params = [(c["category"], c["co2e_Mt_AR5"], sigma_log(c["uncert_pct"]), c.get("corr_group"),
               c.get("_mc_key") or "%s|%s|%s" % (c["category"], c["subitem"], c["gas"]))
              for c in comps]
    groups = sorted({g for _, _, _, g, _ in params if g is not None})

    if stream == "parameter":
        # THE PARAMETER MODE. A component's draw is the product of one multiplier per shared
        # parameter that enters it, times a residual multiplier private to the row:
        #
        #   E_j  x  prod_p exp(z_p sigma_p - sigma_p^2/2)  x  exp(z_j sigma_res - sigma_res^2/2)
        #
        # z_p is shared by every component the parameter multiplies, ACROSS SECTORS. That is
        # the whole change: a row may now depend on several dependency groups at once, so the
        # power sector's gas rows carry the TOE conversion AND the natural-gas carbon content,
        # where the single corr_group string forced a choice between them and the fuel-carbon
        # scenario simply excluded power as a result.
        #
        # Each component's TOTAL log-variance is the marginal core.parameters.decompose
        # derives: the declared row variance with the residual sized to close it where the
        # row reconciles, and the recomposed parameter variance where the graph is
        # authoritative (an audited disposition, never a silent clamp). Between the two
        # covariance scenarios no marginal moves for any reason other than the correlation
        # structure this mode exists to represent -- held by common random numbers below.
        from pkinv.core import parameters as param_core
        decomposition = param_core.decompose(comps)
        # THE TWO SCENARIOS, re-expressed. The old pair asked whether the fossil fuel-carbon
        # factors were independent or shared; correlation is intrinsic to this model, so the
        # question becomes WHERE sharing stops. cross_sector=True lets a dependency group span
        # modules - one diesel carbon content for road, rail, power and industry. False
        # qualifies every group by its module, so the same physical factor is treated as a
        # different quantity in each sector, which is what an inventory compiled sector by
        # sector implicitly assumes.
        if not cross_sector:
            decomposition = [(c, {"%s|%s" % (c.get("_sector"), g): s
                                  for g, s in shared.items()}, r, o)
                             for c, shared, r, o in decomposition]
        groups = sorted({g for _c, shared, _r, _o in decomposition for g in shared})
        # COMMON RANDOM NUMBERS across the two covariance scenarios: each group's stream
        # is anchored to its representative member row (see group_stream_key), never to
        # the scenario-dependent group name.
        rep = group_representatives(
            (g, c.get("_mc_key") or "%s|%s|%s" % (c["category"], c["subitem"], c["gas"]))
            for c, shared, _r, _o in decomposition for g in shared)
        z_group = {}
        for g in groups:
            if parameter_draws is not None:
                physical = g if cross_sector else g.split("|", 1)[1]
                # Native nitrogen and other agriculture rows use identical herd
                # draws in both covariance cases. Other module boundaries remain
                # the explicit within-sector sensitivity.
                if not cross_sector and not g.startswith("agriculture|"):
                    physical = g
                z_group[g] = parameter_draws.normal(physical, parameter_year)
                continue
            key = group_stream_key(g, rep[g], cross_sector)
            # group_qualifier SPLITS a dependency group's stream, and exists for exactly one
            # caller: the longitudinal ensemble, which runs this inventory over nine fiscal
            # years and must say, per group, whether its error is ONE draw shared by every
            # year (an emission factor does not take a different value in FY2017 than in
            # FY2020) or a fresh draw wherever the underlying quantity actually changed.
            # Returning None - the default for every existing caller - leaves the key exactly
            # as it was, and tests/test_montecarlo_qualifier.py holds that the published runs
            # are bit-identical with the parameter present.
            if group_qualifier is not None:
                suffix = group_qualifier(g)
                if suffix:
                    key = "%s|%s" % (key, suffix)
            rng = random.Random(stream_seed(seed, key))
            z_group[g] = [rng.gauss(0.0, 1.0) for _ in range(n_iter)]
        z_resid, plan = {}, []
        for c, shared, residual, _over in decomposition:
            ident = c.get("_mc_key") or "%s|%s|%s" % (c["category"], c["subitem"], c["gas"])
            # residual_qualifier is the sibling of group_qualifier and exists for the same
            # caller. It has to be separate: `ident` doubles as the residual's stream key AND
            # as the anchor for a dependency group's representative member, so varying the
            # residual by writing the year into _mc_key would silently re-seed every shared
            # parameter too - which it did, and the typed scenario came out indistinguishable
            # from full independence until the two were pulled apart.
            resid_key = ident
            if residual_qualifier is not None:
                suffix = residual_qualifier(c)
                if suffix:
                    resid_key = "%s|%s" % (ident, suffix)
            if resid_key not in z_resid:
                rng = random.Random(stream_seed(seed, resid_key))
                z_resid[resid_key] = [rng.gauss(0.0, 1.0) for _ in range(n_iter)]
            ident = resid_key
            plan.append((c["category"], c["co2e_Mt_AR5"], sorted(shared.items()),
                         residual, ident))

        cat_samples = {c: [] for c in categories}
        total_samples = []
        for i in range(n_iter):
            cat_iter = {c: 0.0 for c in categories}
            for category, value, shared, residual, ident in plan:
                log = 0.0
                for g, sig in shared:
                    log += z_group[g][i] * sig - sig * sig / 2.0
                if residual:
                    log += z_resid[ident][i] * residual - residual * residual / 2.0
                drawn = math.copysign(abs(value) * math.exp(log), value)
                scales = component_scalers.get(ident)
                if scales is not None:
                    drawn *= scales[i]
                cat_iter[category] += drawn
            for cat, draws in injected.items():
                cat_iter[cat] += draws[i]
            for cat, draws in native:
                cat_iter[cat] += draws[i]
            for c in categories:
                cat_samples[c].append(cat_iter[c])
            total_samples.append(sum(cat_iter.values()))
        return _summarise(cat_samples, total_samples, a1_comps, categories, n_iter,
                          return_samples)

    if stream == "per_component":
        # One RNG per drawing unit, seeded from its identity.
        #
        # COMMON RANDOM NUMBERS. A correlation group's stream is keyed to one of its OWN
        # MEMBERS - the lexicographically first - rather than to the group name. That is not
        # cosmetic. Keying on the group name means every grouped component draws a different
        # random sequence than it draws in the uncorrelated run, so comparing the two
        # scenarios mixes the structural effect with a wholesale re-draw.
        #
        # It showed up as an impossibility: the power sector's band NARROWED by 2.3 points
        # under correlation, which cannot happen to a sum of positively-correlated positive
        # terms. Power's variance is dominated by one wide-banded coal row, and re-drawing it
        # moved the realised percentile further than the structure did. The defect was
        # invisible while every fuel shared a single group, because that effect was large
        # enough to swamp the noise; grouping per physical factor made the effect small and
        # the noise visible.
        #
        # With the group keyed to a member, that member's realisation is IDENTICAL across
        # scenarios and only its group-mates move - which is exactly the structural
        # difference the two scenarios exist to measure.
        representative = group_representatives(
            (group, ident) for _c, _v, _s, group, ident in params)
        identities = sorted({representative.get(g, ident) if g is not None else ident
                             for _c, _v, _s, g, ident in params})
        z_by_key = {}
        for key in identities:
            rng = random.Random(stream_seed(seed, key))
            z_by_key[key] = [rng.gauss(0.0, 1.0) for _ in range(n_iter)]
    elif stream == "sequential":
        rng = random.Random(seed)
    else:
        raise ValueError("unknown stream discipline %r" % stream)

    cat_samples = {c: [] for c in categories}
    total_samples = []
    for i in range(n_iter):
        cat_iter = {c: 0.0 for c in categories}
        if stream == "sequential":
            gz = {g: rng.gauss(0.0, 1.0) for g in groups}
        for category, value, sig, group, ident in params:
            # mean-preserving lognormal: E[draw] = deterministic value (IPCC best estimate = mean).
            # copysign carries a sink's sign through a distribution that cannot go negative; for a
            # positive value it is bit-identical to the plain multiplication it replaces, so the
            # sink branch costs agriculture nothing.
            if stream == "per_component":
                z = z_by_key[representative.get(group, ident) if group is not None
                             else ident][i]
            else:
                z = gz[group] if group is not None else rng.gauss(0.0, 1.0)
            draw = math.copysign(abs(value) * math.exp(z * sig - sig * sig / 2.0), value)
            cat_iter[category] += draw
        for c in categories:
            cat_samples[c].append(cat_iter[c])
        total_samples.append(sum(cat_iter.values()))

    return _summarise(cat_samples, total_samples, comps, categories, n_iter, return_samples)


def _summarise(cat_samples, total_samples, comps, categories, n_iter, return_samples):
    """Percentiles, the Approach-1 cross-check column, and optionally the draws.

    Factored out when the parameter mode arrived: three sampling disciplines now produce the
    same shape of samples, and one of them computing its percentiles differently would be a
    difference nobody could see in the output.
    """
    # Approach-1 per-category and national, for the cross-check column
    a1 = {}
    for c in categories:
        members = [(x["co2e_Mt_AR5"], x["uncert_pct"], x.get("corr_group"))
                   for x in comps if x["category"] == c]
        _, a1[c] = combine_sum(members) if members else (0.0, 0.0)
    _, a1["TOTAL"] = combine_sum([(x["co2e_Mt_AR5"], x["uncert_pct"], x.get("corr_group"))
                                  for x in comps])

    stats = {}
    for key, samples in list(cat_samples.items()) + [("TOTAL", total_samples)]:
        s = sorted(samples)
        p025, p50, p975 = percentile(s, 0.025), percentile(s, 0.50), percentile(s, 0.975)
        mean = sum(s) / len(s)
        rel = ((p975 - p025) / 2.0 / p50 * 100.0) if p50 else 0.0   # matches Approach 1
        stats[key] = {"mean": mean, "p025": p025, "p50": p50, "p975": p975,
                      "rel_pct": rel, "approach1_pct": a1.get(key, 0.0)}
    if return_samples:
        return stats, total_samples, dict(cat_samples, TOTAL=total_samples)
    return stats, total_samples


def run_sector(sector, n_iter=N_ITER, seed=SEED, data=None):
    """Convenience wrapper: build a registered sector's components and run the MC."""
    data = data if data is not None else sector.load_data()
    return run(sector.build_components(data), list(sector.CATEGORIES),
               n_iter=n_iter, seed=seed, has_sinks=sector.HAS_SINKS)
