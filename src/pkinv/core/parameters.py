"""The uncertain quantities behind the inventory, as records rather than as one number a row.

WHY THIS EXISTS. Until now a component carried a single `uncert_pct` and at most one
`corr_group` string, and the manuscript said in as many words what that could not express:

    A component carries one correlation group, and a real emissions row depends on several
    uncertain parameters at once: a power row depends on the TOE-to-terajoule conversion, on
    the IPCC carbon content of the fuel it burns, and on its own metered activity, each with a
    different dependency structure.

Because it could not, the power module sat OUTSIDE the cross-sector fuel-carbon scenario
entirely - its rows were already spoken for by the TOE group - and the key-category variance
ranking treated categories as independent while livestock counts drove both enteric
fermentation and manure management, manure nitrogen drove both managed soils and residential
dung, and one fuel control drove both road and off-road.

THE DECOMPOSITION IS ALREADY IN THE ARITHMETIC. core.uncertainty.product() combines relative
uncertainties in quadrature, so a component's variance is a SUM over the terms that compose it:

    sigma^2_component = sum_p sigma^2_p  +  sigma^2_residual

This module names the sigma_p. The residual is whatever the named parameters do not explain,
and it is non-negative by construction: where the named parameters imply MORE variance than
the component declares, the PARAMETER GRAPH IS AUTHORITATIVE -- the row's marginal is derived
from its parameters under a per-row audited disposition (data/uncertainty_reconciliation.csv)
and the declared width is published beside it as a validation comparator. An excess with no
disposition raises.

WHAT IS AND IS NOT DRAWN. kind="parametric" parameters are sampled. kind="structural" ones are
not: they are the scenario axes data/scenarios.csv already registers, and they appear here only
so the two registries can be checked against each other. A structural fork is a choice between
readings of evidence, not a distribution, and sampling it would put a probability on something
this inventory declines to put a probability on.

Usage:  python3 -m pkinv.core.parameters
Writes: outputs/national_uncertainty_parameters.csv
"""

from pkinv.assets import asset_path
import csv
import glob
import math
import os
import re

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows

FIELDS = ("parameter_id", "module", "kind", "value", "unit", "distribution",
          "uncert_pct_95", "confidence_interpretation", "dependency_group", "source",
          "note")

# What the one width column MEANS, stated per parameter rather than assumed. Two honest
# values today: most widths arrive as a symmetric 95% relative half-width; the fugitives
# and ippu tables publish bounds instead, and _half_width_pct() summarises them, which is
# a different statistical object and says so. A third value would mean a third source
# convention entered the registry and must be declared here before it is drawn.
CONFIDENCE_VOCABULARY = ("95pct_relative_halfwidth", "95pct_halfwidth_from_declared_bounds")

# A bounded parameter's 95% half-width, from its own bounds. The sector tables that carry
# lower/upper instead of a percentage - fugitives' 42 rows and ippu's 6 - are not lognormal;
# converting them to a relative half-width is a summary, and it is used only to SIZE the
# parameter's contribution to a variance decomposition, never to redraw the sector's own
# published interval, which each sector computes with its own distribution.
def _half_width_pct(central, lower, upper):
    try:
        c, lo, hi = float(central), float(lower), float(upper)
    except (TypeError, ValueError):
        return None
    if not c:
        return None
    return abs(hi - lo) / 2.0 / abs(c) * 100.0


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first(row, *names):
    for n in names:
        v = (row.get(n) or "").strip()
        if v:
            return v
    return ""


def _rows(path):
    return read_rows(path)


# The gas (or conversion) a factor category is a factor FOR, read off the category suffix.
# data/emission_factors.csv names categories like power_combustion_co2, transport_fuel_ch4,
# transport_ncv - the suffix is the role and the item is the fuel.
_ROLE = re.compile(r"_(co2|ch4|n2o|ncv|nox|so2|pm25|bc|nh3|nmvoc|co)$")


def factor_identity(category, item):
    """The PHYSICAL factor a row is, independent of which sector reads it.

    An ef_id is not that identity. `pow_co2_hsd` and `tr_co2_diesel` are two rows for one
    number - 74100 kg/TJ for gas/diesel oil, carrying the same 2 percent - because the table is
    organised by consumer. Grouping by ef_id would make the power sector's diesel carbon
    content independent of the transport sector's, which is exactly the physical claim this
    inventory has spent three rounds establishing is false.

    Nineteen factors in the table are read by more than one sector on this identity; the CO2
    content of diesel is read by six. It generalises core.factors, which declares the same
    thing for fossil CO2 only, to every gas and to the calorific values.
    """
    m = _ROLE.search(category or "")
    return "factor:%s:%s" % (m.group(1), item) if m else None


def _runtime_overrides():
    """Registry-published values that differ from their CSV row, by declaration.

    The registry's job is to publish what the engine runs on, and for eight
    releases the soils_fracgasf row published the IPCC Table 11.3 default 0.15
    while the engine ran on the product-weighted 0.1605 (the eighth review's
    NH3 item). The value now arrives through the SECTOR CONTRACT: any sector
    engine may export ``parameter_overrides() -> dict`` and this sweep collects
    them - rc33's inversion of what used to be core's one downward import of a
    sector module. A sector without the hook contributes nothing; a hook that
    raises fails the phase loudly.
    """
    from pkinv.core import registry
    out = {}
    for sector in registry.all_sectors():
        hook = getattr(sector, "parameter_overrides", None)
        if hook is None:
            continue
        for key, row in hook().items():
            if key in out:
                raise ValueError("two sectors override parameter %r" % key)
            out[key] = row
    return out


def from_emission_factors():
    """One parameter per emission factor, grouped by the PHYSICAL factor it is."""
    out = []
    overrides = _runtime_overrides()
    for r in _rows(asset_path(DATA, "emission_factors.csv")):
        u = _num(r.get("uncert_pct"))
        if u is None:
            continue
        row = {
            "parameter_id": "ef:%s" % r["ef_id"],
            "module": "shared",
            "kind": "parametric",
            "value": _num(r.get("value")),
            "unit": (r.get("unit") or "").strip(),
            "distribution": "lognormal",
            "uncert_pct_95": u,
            "confidence_interpretation": "95pct_relative_halfwidth",
            "dependency_group": (factor_identity(r.get("category"), r.get("item"))
                                 or "ef:%s" % r["ef_id"]),
            "source": (r.get("source") or "").strip(),
            "note": "%s / %s" % (r.get("category", ""), r.get("item", "")),
        }
        row.update(overrides.get(row["parameter_id"], {}))
        out.append(row)
    return out


# The eight sector tables, in three schemas. Normalised rather than rewritten: each is the
# sector's own published record and its own tests pin it.
def from_sector_inputs():
    out = []
    for path in sorted(glob.glob(asset_path(OUTPUTS, "*uncertainty_inputs*.csv"))):
        module = os.path.basename(path).split("_")[0]
        for r in _rows(path):
            name = _first(r, "variable", "input_id", "input")
            if not name:
                continue
            central = _num(_first(r, "central_value", "central"))
            u = _num(_first(r, "uncert_pct_95"))
            interpretation = "95pct_relative_halfwidth"
            if u is None:
                u = _half_width_pct(central, _first(r, "lower_bound", "lower"),
                                    _first(r, "upper_bound", "upper"))
                if u is not None:
                    interpretation = "95pct_halfwidth_from_declared_bounds"
            klass = _first(r, "uncertainty_class", "uncertainty_type", "input_type").lower()
            kind = "structural" if "struct" in klass else "parametric"
            group = _first(r, "correlation_group")
            out.append({
                "parameter_id": "%s:%s" % (module, name),
                "module": module,
                "kind": kind,
                "value": central,
                "unit": _first(r, "unit"),
                "distribution": _first(r, "distribution") or "lognormal",
                # A parameter with no width is a diagnostic the sector publishes beside its
                # inputs - a cross-check, a reported control. It stays in the registry so the
                # record is complete and is never drawn.
                "uncert_pct_95": u,
                "confidence_interpretation": interpretation if u is not None else "",
                "dependency_group": group or "%s:%s" % (module, name),
                "source": _first(r, "source"),
                "note": _first(r, "applies_to", "applicable_model"),
            })
    return out


# Activity files carrying their own uncertainty. This is where agriculture's parameters come
# from, and agriculture is half the inventory: its component uncertainties are computed as
# product(ad_uncert[species], efu(...)), so the activity term is already a named quantity with
# a published width - it simply had nowhere to be recorded.
ACTIVITY_FILES = (
    ("agriculture", "livestock_2024.csv", "species", "livestock"),
    ("agriculture", "crops_2024.csv", "crop", "crop"),
    ("agriculture", "fertilizer_2024.csv", "item", "fertiliser"),
)


def from_activity_files():
    out = []
    for module, filename, key_col, group_prefix in ACTIVITY_FILES:
        path = asset_path(DATA, "activity", filename)
        if not os.path.exists(path):
            continue
        for r in _rows(path):
            u = _num(r.get("ad_uncert_pct"))
            key = (r.get(key_col) or "").strip()
            if u is None or not key:
                continue
            out.append({
                "parameter_id": "%s:%s:%s" % (module, group_prefix, key),
                "module": module,
                "kind": "parametric",
                "value": _num(r.get("head_value") or r.get("production_t")
                              or r.get("value_t")),
                "unit": "head" if group_prefix == "livestock" else "t",
                "distribution": "lognormal",
                "uncert_pct_95": u,
                "confidence_interpretation": "95pct_relative_halfwidth",
                # ONE GROUP PER PHYSICAL QUANTITY, which is the whole point: the buffalo count
                # that drives enteric fermentation is the same buffalo count that drives manure
                # management, and enteric.py and manure.py read the same ad_uncert entry.
                "dependency_group": "%s:%s" % (group_prefix, key),
                "source": (r.get("source") or "").strip(),
                "note": "activity quantity, shared by every category that uses it",
            })
    return out


# Modules whose activity datum is already energy, so no calorific conversion enters their rows.
ENERGY_BASED_MODULES = frozenset({"power"})

# How much more variance the named parameters may imply than the component declares before it
# is called a disagreement rather than rounding. Five percent of the variance is about two and
# a half percent on a sigma, which is wider than the rounding in a column stored to one decimal
# place and far narrower than any of the real disagreements this found.
OVER_DECOMPOSITION_TOL = 0.05

# The ef_id prefixes each module's factor rows use, so a shared factor group resolves to THE
# MEMBER THE ROW ACTUALLY READS. The optional category pattern is what makes one module with
# two table copies resolvable: transport's road rows read the tr_* factors (Table 3.2.2) and
# its off-road rows the offroad_* factors (Table 3.3.1), and before the pattern existed the
# resolver took whichever sorted first -- which priced every road diesel row's CH4 at the
# off-road 130 percent instead of its own 60, a third of the rc2 review's 23-row defect.
EF_PREFIX_BINDING = {
    "pow": ("power", r"Electricity"), "cap": ("power", r"Captive"),
    "tr": ("transport", ""), "offroad": ("transport", r"Mixed off-road"),
    "res": ("residential", ""), "rail": ("railways", ""), "ind": ("industry", ""),
    "stat": ("industry", ""), "av": ("aviation", ""), "waste": ("waste", ""),
    "agri": ("agriculture", ""),
}


def load_group_rules():
    """{dependency_group: rule} from data/dependency_group_rules.csv."""
    out = {}
    for r in _rows(asset_path(DATA, "dependency_group_rules.csv")):
        out[r["dependency_group"]] = r["rule"].strip()
    return out


def load_member_bindings():
    """{parameter_id: (category_pattern, subitem_pattern, gas_pattern)}."""
    out = {}
    for r in _rows(asset_path(DATA, "member_bindings.csv")):
        out[r["parameter_id"]] = (r["category_pattern"].strip(),
                                  r["subitem_pattern"].strip(),
                                  r["gas_pattern"].strip())
    return out


def load_scope_exclusions():
    """{(module, dependency_group): substitute_group}."""
    out = {}
    for r in _rows(asset_path(DATA, "parameter_scope_exclusions.csv")):
        out[(r["module"].strip(), r["dependency_group"].strip())] = \
            r["substitute_group"].strip()
    return out


def load_dispositions():
    """{(module, category, subitem, gas): action} from the reconciliation registry.

    Only derive_row_from_parameters is consulted at decompose time; the other rows are the
    audit record of causes repaired in code and data, kept so the 23-row defect has a
    per-row disposition rather than a summary.
    """
    path = asset_path(DATA, "uncertainty_reconciliation.csv")
    if not os.path.exists(path):
        return {}
    out = {}
    for r in _rows(path):
        out[(r["module"].strip(), r["category"].strip(), r["subitem"].strip(),
             r["gas"].strip())] = r["action"].strip()
    return out


def _member_applies(param, component, bindings):
    """True/False for a declared binding; None where the member declares none."""
    binding = bindings.get(param["parameter_id"])
    if binding is None:
        return None
    cat_p, sub_p, gas_p = binding
    if cat_p and not re.search(cat_p, original_category(component)):
        return False
    if sub_p and not re.search(sub_p, component.get("subitem", "")):
        return False
    if gas_p and not re.search(gas_p, component.get("gas", "")):
        return False
    return True


SCOPE_ROLE_VALUES = ("activity", "conversion", "factor")
SCOPE_ROLES = {}     # {dependency_group: declared role}, filled by scope_map()


def scope_map():
    """{dependency_group: [(module, category_regex, subitem_regex, sign)]}.

    The sign column (default +1) is the rc11 repair for anticorrelated sharing: a
    dependency group is ONE stream of common error, but its members need not move
    the same way - waste's collected/uncollected partition moves burning UP exactly
    when it moves disposal DOWN, and the previous unsigned sharing drew the pair
    positively correlated, the opposite of the physics the sector's own Approach 1
    states. A signed member folds the sign into its sigma; every quadrature is
    sign-invariant and the lognormal mean correction uses sigma squared, so nothing
    downstream changes except the direction of the shared draw.
    """
    out = {}
    SCOPE_ROLES.clear()
    for r in _rows(asset_path(DATA, "parameter_scope.csv")):
        sign = float((r.get("sign") or "").strip() or 1.0)
        if sign not in (1.0, -1.0):
            raise ValueError("parameter_scope sign must be +1 or -1, got %r for %s"
                             % (r["sign"], r["dependency_group"]))
        out.setdefault(r["dependency_group"], []).append(
            (r["module"].strip(), r["category_pattern"].strip(),
             r["subitem_pattern"].strip(), sign))
        # rc41: a scope row may DECLARE the role its group plays in the stream (activity,
        # conversion, factor). By name a module-local group ("power:CH4 and N2O factors",
        # "waste:swds_f") reads as activity; the role column says what it physically is,
        # and the ledger's parameter columns follow it. One role per group.
        role = (r.get("role") or "").strip()
        if role:
            if role not in SCOPE_ROLE_VALUES:
                raise ValueError("parameter_scope role must be one of %s, got %r for %s"
                                 % (SCOPE_ROLE_VALUES, role, r["dependency_group"]))
            if SCOPE_ROLES.get(r["dependency_group"], role) != role:
                raise ValueError("parameter_scope declares two roles for %s" % r["dependency_group"])
            SCOPE_ROLES[r["dependency_group"]] = role
    return out


def scope_sign(component, group, scopes):
    """The declared sign of this component's membership in a scoped group.

    Factor-route groups have no scope rows and default to +1; a scoped group takes
    the sign of the first rule that matches the component.
    """
    for rule in scopes.get(group, ()):
        if _matches(component, *rule[:3]):
            return rule[3]
    return 1.0


def original_category(component):
    """The engine category, surviving uncertainty_all's by-sector relabelling.

    The by-sector Monte Carlo pass rewrites `category` to the sector name so its samples
    aggregate per module; `_mc_key` pins the original (category, subitem, gas) triple.
    Every pattern in this module must match against the ORIGINAL, or the sector pass
    silently drops every category-scoped dependency group -- which it did: the power TOE
    group matched "Electricity and heat production" in the category pass and nothing in
    the relabelled one, so the two passes decomposed the same rows differently and no
    test compared them. Found when the select rule turned the silent mismatch into a
    raise.
    """
    key = component.get("_mc_key")
    if key:
        return key.split("|", 1)[0]
    return component.get("category", "")


def _matches(component, module, category_pattern, subitem_pattern):
    if module and module != "*" and component.get("_sector") != module:
        return False
    if category_pattern and not re.search(category_pattern, original_category(component)):
        return False
    if subitem_pattern and not re.search(subitem_pattern, component.get("subitem", "")):
        return False
    return True


def groups_for(component, scopes=None):
    """Every dependency group whose parameters multiply into this component.

    Two routes, and the split is deliberate. A fuel factor scopes itself through
    core.factors.fuel_of(), because the mapping from a stream to the fuel it burns is already
    declared and tested there; everything else is scoped in data/parameter_scope.csv. The
    alternative - one file listing both - would be a second copy of the fuel table, and two
    copies of a mapping is how the manuscript came to print two category hierarchies.
    """
    if component.get("uncertainty_driver_widths") is not None:
        return sorted(component["uncertainty_driver_widths"])
    from pkinv.core import factors
    scopes = scope_map() if scopes is None else scopes
    exclusions = load_scope_exclusions()
    found = []
    fuel = factors.fuel_of(component)
    if fuel:
        # ONLY THE ROW'S OWN GAS. A CO2 row reads the fuel's carbon content and does not read
        # its methane factor; adding every role to every row of the stream triples the factor
        # variance and was the first draft's mistake. The calorific value is the exception -
        # every gas of the stream is computed per terajoule, so all of them read it.
        role = (component.get("gas") or "").lower()
        if role:
            found.append("factor:%s:%s" % (role, fuel))
        # The calorific value converts a MASS or VOLUME of fuel into energy, so it only enters
        # where the sector's activity is a mass or a volume. Power's activity is already energy
        # - NEPRA publishes tonnes of oil equivalent - and its own input table records the
        # TOE-to-terajoule basis as "not sampled" for exactly that reason. Scoping the calorific
        # value to it made a 10.9 percent row imply 21 percent from that term alone, which is
        # how this exclusion was found rather than assumed.
        if component.get("_sector") not in ENERGY_BASED_MODULES:
            found.append("factor:ncv:%s" % fuel)
    for group, rules in scopes.items():
        if any(_matches(component, *rule[:3]) for rule in rules):
            found.append(group)
    # A module whose own input table declares the same physical quantity does not also
    # receive it through the shared registry: railways' diesel CO2 carried its declared
    # 1a3c_ncv AND factor:ncv:Gas/Diesel Oil, one Table 1.2 number counted twice.
    sector = component.get("_sector")
    found = [g for g in found if (sector, g) not in exclusions]
    return sorted(set(found))


def _group_sigma(group, members, component, rules, bindings):
    """The one sigma a dependency group contributes to one component.

    Resolution, in order:

    1. Shared FACTOR groups (every member an ef: row): the member the row reads, by table
       identity -- ef_id prefix matched on (module, category pattern). A pattern-restricted
       match outranks a module-only match, which is what separates transport's road factors
       (tr_*) from its off-road factors (offroad_*). Ambiguity between members with
       DIFFERENT widths raises; equal widths take the first, because it does not matter.
    2. A declared rule from data/dependency_group_rules.csv:
       select   exactly one member binds this row (data/member_bindings.csv), and its width
                is the answer; zero or several binding is an error, never a summary.
       product  the binding members are distinct quantities that all multiply into the row;
                the group contributes their quadrature.
       blend    the members mix into the quantity the rows use with no declared weights;
                the median stands, documented in the rules file.
    3. No rule: a single member, or several members of identical width. Anything else
       raises -- the median-of-members summary this replaces priced railways' diesel with
       the furnace-oil account's width, and a silent summary is how it survived.
    """
    module = component.get("_sector")
    if all(p["parameter_id"].startswith("ef:") for p in members):
        best_tier, best = 0, []
        for p in members:
            prefix = p["parameter_id"].split(":", 1)[-1].split("_")[0]
            bind = EF_PREFIX_BINDING.get(prefix)
            if not bind or bind[0] != module:
                continue
            if bind[1]:
                if re.search(bind[1], original_category(component)):
                    tier = 2
                else:
                    continue
            else:
                tier = 1
            if tier > best_tier:
                best_tier, best = tier, [p]
            elif tier == best_tier:
                best.append(p)
        if best:
            sigmas = {round(sigma_log(p["uncert_pct_95"]), 12) for p in best}
            if len(sigmas) > 1:
                raise ValueError(
                    "factor group %s resolves ambiguously for (%s, %s, %s): members %s "
                    "carry different widths -- add a category pattern to "
                    "EF_PREFIX_BINDING" % (group, module, component.get("subitem"),
                                           component.get("gas"),
                                           sorted(p["parameter_id"] for p in best)))
            return sigma_log(best[0]["uncert_pct_95"])
        # No member belongs to this module's tables: the row reads the factor through a
        # shared identity none of its own tables restate. One width means no ambiguity.
        sigmas = {round(sigma_log(p["uncert_pct_95"]), 12) for p in members}
        if len(sigmas) == 1:
            return sigma_log(members[0]["uncert_pct_95"])
        raise ValueError("factor group %s has no member for module %s and its members "
                         "disagree on width" % (group, module))

    rule = rules.get(group)
    if rule == "select":
        applicable = [p for p in members
                      if _member_applies(p, component, bindings) is True]
        if len(applicable) != 1:
            raise ValueError(
                "select group %s binds %d members for (%s, %s, %s, %s); exactly one must "
                "-- fix data/member_bindings.csv"
                % (group, len(applicable), module, component.get("category"),
                   component.get("subitem"), component.get("gas")))
        return sigma_log(applicable[0]["uncert_pct_95"])
    if rule in ("product", "blend"):
        applicable = [p for p in members
                      if _member_applies(p, component, bindings) is not False]
        if not applicable:
            raise ValueError("group %s (%s) binds no member for (%s, %s, %s)"
                             % (group, rule, module, component.get("subitem"),
                                component.get("gas")))
        sigmas = sorted(sigma_log(p["uncert_pct_95"]) for p in applicable)
        if rule == "product":
            return math.sqrt(sum(s * s for s in sigmas))
        return sigmas[len(sigmas) // 2]

    sigmas = sorted(sigma_log(p["uncert_pct_95"]) for p in members)
    if len(sigmas) == 1 or abs(sigmas[-1] - sigmas[0]) < 1e-9:
        return sigmas[0]
    raise ValueError(
        "dependency group %s has %d members with differing widths and no declared rule -- "
        "add a row to data/dependency_group_rules.csv; the median summary this replaces "
        "priced rows with the wrong member's width" % (group, len(members)))


def decompose(components, params=None, scopes=None, dispositions=None):
    """Split each component's log-variance into named shared parameters plus a residual.

    Returns [(component, {group: sigma}, sigma_residual, derived)].

    THE IDENTITY. core.uncertainty.product() combines relative uncertainties in quadrature, so

        sigma^2_component = sum over shared groups sigma^2_g  +  sigma^2_residual

    holds where the declared row width is at least what its named parameters imply, and the
    residual is what they do not explain -- for those rows no marginal band moves.

    Where the named parameters imply MORE variance than the row declares, THE PARAMETER
    GRAPH IS AUTHORITATIVE: the row's marginal is derived from its parameters (residual
    zero, `derived` True), and the divergence from the declared width is published in the
    decomposition output as a validation comparator. That requires a per-row disposition in
    data/uncertainty_reconciliation.csv naming the cause; an undeclared excess RAISES. The
    previous edition clamped the residual to zero silently, which sampled more variance
    than 23 rows declared while the docstrings promised none moved -- both halves of that
    are exactly what this replaces.
    """
    params = registry() if params is None else params
    scopes = scope_map() if scopes is None else scopes
    dispositions = load_dispositions() if dispositions is None else dispositions
    rules = load_group_rules()
    bindings = load_member_bindings()
    by_g = by_group(params)
    out = []
    for c in components:
        total = sigma_log(c["uncert_pct"]) if c.get("uncert_pct") else 0.0
        shared = {}
        for g in groups_for(c, scopes):
            members = by_g.get(g)
            explicit = c.get("uncertainty_driver_widths", {})
            if g in explicit:
                shared[g] = sigma_log(float(explicit[g]))
                continue
            if not members:
                continue
            # ONE SIGMA PER GROUP, not the quadrature of its members. A dependency group is
            # one source of common error: `factor:co2:Gas/Diesel Oil` has seven parameters
            # because seven sector rows record the same 74100 kg/TJ, and a given diesel
            # component reads ONE of them. Summing all seven was the first draft's mistake and
            # made 107 of 184 rows imply more variance than they declare. (A product-rule
            # group returns its members' quadrature as one sigma, because there the members
            # are DIFFERENT quantities that all enter the row.)
            # the sign folds into the sigma: quadrature and the lognormal mean
            # correction square it away, while the shared z draw flips direction
            # for anticorrelated members (see scope_map's docstring)
            shared[g] = (_group_sigma(g, members, c, rules, bindings)
                         * scope_sign(c, g, scopes))
        named = sum(s * s for s in shared.values())
        # A RELATIVE tolerance, because the component's uncert_pct is stored rounded and the
        # recomposition from parameters lands a fraction of a percent either side of it. At an
        # absolute tolerance the power sector reported eight "over-decomposed" rows that agreed
        # to four significant figures - 0.6793 declared against 0.6809 named - which is not a
        # disagreement, it is the rounding in the published column. Beyond this tolerance it is
        # a real disagreement between a sector's input table and its component uncertainty.
        derived = named > total * total * (1.0 + OVER_DECOMPOSITION_TOL)
        if derived:
            key = (c.get("_sector"), original_category(c), c.get("subitem", ""),
                   c.get("gas", ""))
            if dispositions.get(key) != "derive_row_from_parameters":
                raise ValueError(
                    "(%s, %s, %s, %s): named parameters imply %.4f sigma against %.4f "
                    "declared and no disposition covers it -- audit the row and add it to "
                    "data/uncertainty_reconciliation.csv; a silent clamp is how 23 rows "
                    "sampled variance their sectors never declared"
                    % (key + (math.sqrt(named), total)))
            residual = 0.0
        else:
            # max() guards only float dust inside the tolerance band; a genuine excess is
            # handled above, never truncated.
            residual = math.sqrt(max(total * total - named, 0.0))
        out.append((c, shared, residual, derived))
    return out


def registry():
    """Every parameter, deduplicated by id, in a stable order."""
    seen, out = set(), []
    for source in (from_emission_factors(), from_sector_inputs(), from_activity_files(), from_coal_controls()):
        for p in source:
            if p["parameter_id"] in seen:
                continue
            seen.add(p["parameter_id"])
            out.append(p)
    out.sort(key=lambda p: (p["module"], p["parameter_id"]))
    return out


def from_coal_controls():
    """Physical activity drivers missing from the old emission-row residuals."""
    from pkinv.sectors.industry.data import IndustryData
    from pkinv.sectors.industry import solid_fuels
    data = IndustryData()
    out = []
    for consumer in ("brick_kilns", "cement"):
        identity = "activity:coal:" + consumer
        out.append({"parameter_id": identity, "module": "industry", "kind": "parametric",
                    "value": solid_fuels.coal_kt(solid_fuels._fiscal_label(data.year), consumer),
                    "unit": "kt", "distribution": "lognormal",
                    "uncert_pct_95": data.p("industry_coal_activity_uncert"),
                    "confidence_interpretation": "95pct_relative_halfwidth",
                    "dependency_group": identity, "source": data.ps("industry_coal_activity_uncert"),
                    "note": "conditional activity width; shared by every gas/species using this coal; structural allocations separate"})
    for identity, role, value, width in (
            ("activity:coal:power_station_mass", "activity", 1, 5),
            ("power:coal_factor_rank_share", "factor", 1, 12),
            ("factor:ncv:Lignite", "conversion", 11.9, (21.6 - 5.5) / (2 * 11.9) * 100)):
        out.append({"parameter_id": identity, "module": "power", "kind": "parametric",
                    "value": value, "unit": "multiplier" if value == 1 else "TJ/Gg",
                    "distribution": "lognormal", "uncert_pct_95": width,
                    "confidence_interpretation": "95pct_relative_halfwidth",
                    "dependency_group": identity, "source": "station mass inputs and IPCC 2006 Vol2 Ch1 Table1.2",
                    "note": role + "; component-specific derivative weights are published in decomposition"})
    return out


def drawable(params=None):
    """The parametric parameters that carry a width - the ones a Monte Carlo can sample."""
    return [p for p in (params if params is not None else registry())
            if p["kind"] == "parametric" and p["uncert_pct_95"]]


def sigma_log(uncert_pct):
    """Lognormal sigma from a 95% relative half-width. Same convention as core.montecarlo."""
    rel_sd = (uncert_pct / 100.0) / 1.959964
    return math.sqrt(math.log(1.0 + rel_sd * rel_sd))


def pct_from_sigma(sigma):
    """The inverse: a lognormal sigma back to the 95% relative half-width convention."""
    rel_sd = math.sqrt(math.exp(sigma * sigma) - 1.0)
    return rel_sd * 1.959964 * 100.0


def by_group(params=None):
    """{dependency_group: [parameters]} over the drawable set."""
    out = {}
    for p in drawable(params):
        out.setdefault(p["dependency_group"], []).append(p)
    return out


def decomposition_sampling_method(component):
    """Actual reference uncertainty route, independent of the analytical audit."""
    sector, category = component.get("_sector"), component.get("category", "")
    if sector == "agriculture" and (category == "Field burning of residues" or
            component.get("gas") == "N2O" and category in ("Manure management", "Managed soils")):
        return "native_material_flow_replay"
    if sector in ("waste", "fugitives") or (sector == "power" and component.get("subitem", "").startswith("Coal ")):
        return "native_material_flow_replay"
    return "shared_lognormal_parameter_graph"


def write_decomposition(components, path=None):
    """Publish the analytical graph audit; it is not every native sampled marginal.

    For ordinary graph rows, derived_uncert_pct is its sampled graph marginal.
    Native nitrogen, crop burning, waste, fugitives and coal replay their physical
    inputs instead; this scalar is only an analytical comparator for those rows.
    The sampling_method and analytical_width_role columns distinguish them.
    """
    path = path or asset_path(OUTPUTS, "national_uncertainty_decomposition.csv")
    rows = decompose(components)
    dispositions = load_dispositions()
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["module", "category", "subitem", "gas", "declared_uncert_pct",
                    "derived_uncert_pct", "divergence_pct", "declared_sigma",
                    # NOT a share, and it was called one for several releases. It is the
                    # ratio of the named parameters' variance to the row's DECLARED
                    # variance, so it exceeds 1 whenever the named parameters imply a
                    # wider row than the row admits to - 37 rows do, up to 1.337. That is
                    # the finding the reconciles/disposition columns then act on, not an
                    # arithmetic error, and a column called a "share" made a diagnostic
                    # look like a bug.
                    "named_sigma", "residual_sigma", "named_var_over_declared_var",
                    "reconciles", "disposition", "dependency_groups",
                    "sampling_method", "analytical_width_role"])
        for c, shared, residual, derived in rows:
            total = sigma_log(c["uncert_pct"]) if c.get("uncert_pct") else 0.0
            named = math.sqrt(sum(s * s for s in shared.values()))
            sampled = math.sqrt(named * named + residual * residual)
            declared_pct = c.get("uncert_pct") or 0.0
            derived_pct = pct_from_sigma(sampled) if sampled else 0.0
            key = (c.get("_sector"), original_category(c), c.get("subitem", ""),
                   c.get("gas", ""))
            w.writerow([c.get("_sector"), c["category"], c["subitem"], c["gas"],
                        round(declared_pct, 3), round(derived_pct, 3),
                        round(derived_pct - declared_pct, 3), round(total, 5),
                        round(named, 5), round(residual, 5),
                        round(named * named / (total * total), 4) if total else "",
                        "no" if derived else "yes",
                        dispositions.get(key, "") if derived else "",
                        "; ".join("%s=%.4f" % (g, s)
                                  for g, s in sorted(shared.items(), key=lambda kv: -kv[1])),
                        decomposition_sampling_method(c),
                        "analytical_comparator_not_sampled" if decomposition_sampling_method(c) == "native_material_flow_replay"
                        else "sampled_graph_marginal"])
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    params = registry()
    path = asset_path(OUTPUTS, "national_uncertainty_parameters.csv")
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for p in params:
            w.writerow({k: ("" if p[k] is None else p[k]) for k in FIELDS})

    groups = by_group(params)
    kinds = {}
    for p in params:
        kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
    print("uncertainty parameters -> %s" % path)
    print("  %d parameters: %s" % (len(params),
                                   ", ".join("%d %s" % (v, k)
                                             for k, v in sorted(kinds.items()))))
    print("  %d drawable, in %d dependency groups" % (len(drawable(params)), len(groups)))
    multi = {g: v for g, v in groups.items() if len(v) > 1}
    print("  %d groups carry more than one parameter" % len(multi))

    from pkinv.core import registry as core_registry
    components, _cats, _sec = core_registry.build_all()
    rows = write_decomposition(components)
    named = sum(sum(s * s for s in sh.values()) for _c, sh, _r, _o in rows)
    total = sum(sigma_log(c["uncert_pct"]) ** 2 for c, _sh, _r, _o in rows
                if c.get("uncert_pct"))
    unreconciled = [r for r in rows if r[3]]
    print("  %.1f%% of the summed component log-variance is now named" % (100 * named / total))
    print("  %d of %d analytical rows have named input variance above the scalar comparator"
          % (len(unreconciled), len(rows)))
    print("    (audited graph overrides; native material-flow routes bypass that scalar):")
    for c, sh, _r, _o in unreconciled[:6]:
        print("      %-11s %-32s %.1f%% declared" % (c["_sector"], c["subitem"][:32],
                                                     c["uncert_pct"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
