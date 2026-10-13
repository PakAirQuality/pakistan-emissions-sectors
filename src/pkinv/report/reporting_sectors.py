"""The reporting-sector axis: where IPCC 2006 files each stream, beside the module that computes it.

WHY A SECOND SECTOR COLUMN. `sector_id` (the ledger's `module`) names the ENGINE that computed
a stream, and that is the right key for provenance, uncertainty and the runner contract - the
power module's total is the power module's total. It is the wrong key for one question a reader
of a sector table asks: "how much does industry emit?" Captive gas self-generation is computed in
the power module because it shares the plant register and the factor table, and IPCC 2006 Vol 2
Ch 2 books it under 1.A.2 Manufacturing industries, so a module-keyed sector table reports 5.55 Mt
of industrial combustion under power and understates industry by a fifth. The economic-sector
view of the query core patched that at national grain with a CASE on the IPCC code; this axis
DECLARES the answer per stream in data/stream_reporting_sector.csv and carries it through every
grain (streams -> atoms -> months -> ADM1 -> facts -> query core), so the view can be a column
rather than an expression that has to be re-derived at every table.

WHAT IT IS NOT. It moves no mass, renames no module and re-keys nothing the runner contract
holds: module-keyed outputs are unchanged, and the axis is ADDITIVE with sector_id at every
grain - the same atoms regrouped, sum for sum. Railways' unresolved '1.A.2/1.A.4.c' and
transport's mixed off-road keep their modules until their splits are published: an unresolved
allocation is not re-keyed on a guess.

Vocabulary: exactly the module names (pkinv.core.registry.all_sectors() NAMEs). Resolution:
pkinv.core.declared.match_prefix, the same rule as the geometry and grid-proxy registries.
"""

from pkinv.assets import asset_path
import os

from pkinv.core.declared import match_prefix
from pkinv.activity.store import read_rows
from pkinv.paths import DATA

REGISTRY = asset_path(DATA, "stream_reporting_sector.csv")
FIELDS = ("module", "category", "subitem_prefix", "reporting_sector", "rationale")
VALUE_FIELD = "reporting_sector"
WHAT = "reporting sector"


def vocabulary():
    """The module names, from the sector registry - never a second list."""
    from pkinv.core import registry
    return tuple(s.NAME for s in registry.all_sectors())


def rows(path=REGISTRY):
    """The registry, validated: vocabulary, rationale iff the axis differs, no duplicate keys."""
    out = read_rows(path)
    if not out:
        raise ValueError("%s is empty" % path)
    if tuple(out[0].keys()) != FIELDS:
        raise ValueError("%s columns %r, expected %r" % (path, tuple(out[0].keys()), FIELDS))
    modules = set(vocabulary())
    seen = set()
    for r in out:
        key = (r["module"], r["category"], r["subitem_prefix"])
        if key in seen:
            raise ValueError("duplicate reporting-sector row for %r" % (key,))
        seen.add(key)
        for column in ("module", "reporting_sector"):
            if r[column] not in modules:
                raise ValueError("%s: %s=%r is not a registered module (%s)"
                                 % (path, column, r[column], ", ".join(sorted(modules))))
        differs = r["reporting_sector"] != r["module"]
        if differs and not r["rationale"].strip():
            raise ValueError("%s: (%s, %s) reports under %s without a rationale"
                             % (path, r["module"], r["category"], r["reporting_sector"]))
        if not differs and r["rationale"].strip():
            raise ValueError("%s: (%s, %s) reports under its own module and still argues for "
                             "it; the rationale column is for the rows that differ"
                             % (path, r["module"], r["category"]))
    return out


def resolve(registry_rows, module, category, subitem):
    """The reporting sector of one stream; raises (match_prefix) when nothing declares it."""
    return match_prefix(registry_rows, module, category, subitem, VALUE_FIELD, WHAT)
