"""The declared classification scheme, and the resolver that puts a code on a component.

IPCC 2006 is canonical. The authority is data/shared/lookups/category_crosswalk.csv, whose
banner records why (the shipped `ipcc_code` column used to mix CRT sector 3 with IPCC 2006
sector 4) and where the target codes come from (Volume 1 Chapter 8 Table 8.2, held).

WHY A RESOLVER AND NOT A DICT. Two CRT categories SPLIT when expressed in IPCC 2006, along a
line the engines already compute: manure management's indirect N2O leaves the livestock block
for 3.C.6, and agricultural soils divides into direct 3.C.4 and indirect 3.C.5. So the code is
a property of the COMPONENT, not of the engine category, and `category_ledger.category_codes()`
- which maps engine category to exactly one code and raises when it sees two - cannot express
it. This resolver matches on (module, engine_category, subitem_prefix, gas) with the most
specific subitem_prefix winning, so the split is declared data rather than a branch in code.

WHAT IT REFUSES TO DO. There is no fallback. A component that matches no rule raises, because
the alternative - returning the old code, or an empty string, or the parent - is how a
half-done migration ships: a rename that reaches writers and not readers fails silently, and
this repository has paid for that before. tests/test_category_crosswalk.py asserts both
directions: every live component resolves, and every rule naming an engine category matches at
least one live component, so a stale rule cannot sit here looking like coverage.
"""
import os

from pkinv.assets import asset_path
from pkinv.core.io import read_rows
from pkinv.paths import DATA

CROSSWALK = asset_path(DATA, "shared", "lookups", "category_crosswalk.csv")
SCHEME = "ipcc2006/v1"


def _rules():
    rows = read_rows(CROSSWALK, comments=True)
    if not rows:
        raise IOError("%s is empty" % CROSSWALK)
    return rows


def rules():
    """Every crosswalk rule, as read."""
    return _rules()


def scheme_declared():
    """The one scheme version this release is coded in."""
    versions = {r["scheme_version"] for r in _rules()}
    if versions != {SCHEME}:
        raise ValueError("the crosswalk declares %s; this release is %s"
                         % (sorted(versions), SCHEME))
    return SCHEME


def _component_rules():
    """Only the rules that resolve a component. See `applies_to` in the crosswalk."""
    return [r for r in _rules() if r["applies_to"] == "component"]


def split_categories():
    """Engine categories whose code is NOT a property of the category.

    `category_ledger.category_codes()` maps engine category to one code and raises on two.
    For these the premise does not hold - the component decides - so that guard must skip
    them rather than be loosened for everything.
    """
    out = {}
    for r in _component_rules():
        out.setdefault(r["engine_category"], set()).add(r["ipcc2006_code"])
    return {k for k, v in out.items() if len(v) > 1}


def resolve(engine_category, subitem, gas):
    """IPCC 2006 code for one component. Most specific subitem_prefix wins.

    Keyed on the ENGINE CATEGORY, not on the module: the module column in the crosswalk names
    the inventory block for a reader, while callers hold a sector name that does not always
    match it (LULUCF runs from its own module, and the engine category already carries the
    "LULUCF - " prefix). The engine categories are distinctive, so nothing is gained by
    requiring both to agree and a mismatch would silently fall through to the fallback.
    """
    subitem = subitem or ""
    best, best_len = None, -1
    for r in _component_rules():
        if r["engine_category"] != engine_category:
            continue
        if r["gas"] and gas and r["gas"] != gas and gas not in r["gas"].split("/"):
            continue
        prefix = r["subitem_prefix"]
        if prefix and not subitem.startswith(prefix):
            continue
        if len(prefix) > best_len:
            best, best_len = r, len(prefix)
    if best is None:
        raise KeyError(
            "no crosswalk rule for engine_category=%r subitem=%r gas=%r - add a rule to %s "
            "rather than letting the component keep a code from another scheme"
            % (engine_category, subitem, gas, os.path.basename(CROSSWALK)))
    return best["ipcc2006_code"], best


def crt_of(code2006):
    """The CRT counterpart of an IPCC 2006 code, where the crosswalk declares one."""
    for r in _rules():
        if r["ipcc2006_code"] == code2006 and r["crt_code"]:
            return r["crt_code"]
    return ""
