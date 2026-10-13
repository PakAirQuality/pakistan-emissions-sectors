"""Which IPCC method produced an atom, and which uncertainty model draws it.

Every row of the annual product carried method_id=unresolved and
uncertainty_model_id=unresolved - 1,672 of 1,672, repo-wide - because atomic_annual stamped
the literal on every atom and nothing ever supplied a value. The equations were never unknown:
each agriculture module's docstring names the one it implements. They simply never reached the
published atom, so a reader could not tell Eq 10.19 from Eq 11.13 without opening the source.

A REPORT-LAYER JOIN, and deliberately not a field on the component. core.components v3 is a
closed schema whose own comment records why a provenance key that only some sectors set is
worse than none: it describes the rows that bothered. Agriculture is the sector this round
audits, so agriculture is what this registry covers; adding a key to the shared row for one
sector's benefit is the defect that comment warns about. The join happens where the IPCC-code
join already happens.

MATCHING. A row is matched on its category and, where a category needs splitting, the longest
subitem prefix that matches. Manure management carries three methods - CH4, direct N2O and
indirect N2O are different equations on the same animals - so a category-only key would have
had to pick one of them and mislabel the other two.

Everything not matched stays `unresolved`, and stays VISIBLE: report_coverage() returns the
counts so the share of the product that carries a method can be published rather than
estimated. A registry that silently defaulted would convert an unanswered question into a
plausible answer, which is the failure this whole round keeps finding.

Reads: data/method_registry.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import collections
import csv
import os

from pkinv.paths import DATA

REGISTRY = asset_path(DATA, "method_registry.csv")
UNRESOLVED = "unresolved"


def _rows():
    return list(_activity_rows(REGISTRY, comments=True))


def registry():
    """[(sector, category, subitem_prefix, gas, method_id, uncertainty_model_id, tier,
    equation)], most specific first: longest subitem prefix, then a gas-specific row over a
    gas-agnostic one (rc41: every sector, scoped by sector and gas)."""
    out = [(r.get("sector", "") or "", r["category"], r["subitem_prefix"], r.get("gas", "") or "",
            r["method_id"], r["uncertainty_model_id"], r["tier"], r["equation"]) for r in _rows()]
    return sorted(out, key=lambda e: (-len(e[2]), 0 if e[3] else 1))


def lookup(category, subitem, rules=None, sector=None, gas=None):
    """(method_id, uncertainty_model_id) for one atom, or the unresolved pair.

    A rule scoped to a sector applies only to that sector's atoms; a rule scoped to a gas
    only to that gas. An unscoped rule (the agriculture rows, whose categories recur in no
    other sector) applies wherever category and prefix match."""
    for sec, cat, prefix, rule_gas, method, model, _tier, _eq in (
            rules if rules is not None else registry()):
        if cat != category:
            continue
        if sec and sector is not None and sec != sector:
            continue
        if rule_gas and gas is not None and rule_gas != gas:
            continue
        if not prefix or (subitem or "").startswith(prefix):
            return method, model
    return UNRESOLVED, UNRESOLVED


def report_coverage(rows):
    """{sector: (resolved, total)} over atoms that carry an emission.

    Published rather than asserted: the point of this registry is to make the unresolved
    share countable, and a count nobody prints is a count nobody checks."""
    counts = collections.defaultdict(lambda: [0, 0])
    for row in rows:
        if row.get("co2e_Mt_AR5") in ("", None):
            continue
        entry = counts[row.get("sector_id", "")]
        entry[1] += 1
        if row.get("method_id", UNRESOLVED) != UNRESOLVED:
            entry[0] += 1
    return {sector: tuple(v) for sector, v in sorted(counts.items())}
