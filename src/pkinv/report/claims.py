"""The claims pointer grammar, resolved against a release tree - ONE resolver for the golden
runner, the claim matrix and anything else that cites a shipped cell by address.

    file.csv#k1=v1,k2=v2#column      one cell; the file is under outputs/ unless it starts
                                     with data/ (then repo-relative); exactly ONE row may
                                     match, and the cell is returned as the STRING the file
                                     holds (the caller decides what it means)

The lifted body is tests/semantic/_golden.py's resolve_pointer, unchanged in what it accepts
and returns; that module now imports it. Row-key values may contain commas (the rule
tests/test_claims_registry.py proved red against a bare split): a comma segment without an
equals sign belongs to the previous value.

resolve_expression() adds the arithmetic forms of data/claims_registry.csv (count:,
count_unique:, count_unique_excl_residual:, max_abs:, PTR - PTR) and two counting forms the
claim matrix needs and the registry did not:

    count_where:file.csv#k=v         data rows matching the key
    pct_where:file.csv#k=v#column    100 x sum(column over matching rows) / sum(column over all)
"""

from pkinv.assets import asset_path
import os
import re

from pkinv.activity.store import read_rows


def parse_pointer(pointer):
    """'file.csv#k1=v1,k2=v2#column' -> (name, [(k, v), ...], column)."""
    parts = pointer.split("#")
    if len(parts) != 3:
        raise ValueError("a pointer has three '#'-separated parts: %r" % pointer)
    name, key, column = parts
    return name, parse_key(key), column


def parse_key(key):
    """'k1=v1,k2=v2' -> [(k1, v1), (k2, v2)]; a value may itself carry commas."""
    matchers = []
    for part in key.split(",") if key else ():
        if "=" in part:
            k, v = part.split("=", 1)
            matchers.append([k, v])
        elif matchers:
            matchers[-1][1] += "," + part
        else:
            raise ValueError("pointer key segment before any k=v pair: %r" % key)
    return [tuple(m) for m in matchers]


def pointer_path(root, name):
    """Where a pointer's file lives: outputs/<name>, or <root>/<name> for data/ paths."""
    if name.startswith("data/"):
        return asset_path(root, name)
    return asset_path(root, "outputs", name)


def matching_rows(root, name, key):
    wanted = parse_key(key) if isinstance(key, str) else list(key)
    return [r for r in read_rows(pointer_path(root, name))
            if all(r.get(k) == v for k, v in wanted)]


def resolve_pointer(root, pointer):
    """file.csv#k1=v1,k2=v2#column -> the cell's string (the claims-registry grammar)."""
    name, wanted, column = parse_pointer(pointer)
    hits = matching_rows(root, name, wanted)
    if len(hits) != 1:
        raise AssertionError("%s resolves to %d rows" % (pointer, len(hits)))
    return hits[0][column]


def resolve_expression(root, expr):
    """The registry's numerator/denominator grammar plus the two counting forms -> float."""
    expr = expr.strip()
    if expr.startswith("count:"):
        path = expr[len("count:"):]
        full = path if os.path.isabs(path) else asset_path(root, path)
        if not os.path.exists(full):
            full = asset_path(root, "outputs", path)
        return float(len(read_rows(full, comments=False)))
    if expr.startswith("count_unique_excl_residual:"):
        name, col = expr[len("count_unique_excl_residual:"):].split("#")
        return float(len({r[col] for r in read_rows(pointer_path(root, name), comments=False)
                          if "residual" not in r[col]}))
    if expr.startswith("count_unique_matching:"):
        # distinct values of a column that match a regex: the completeness table's IPCC
        # codes are the distinct `code` values that begin with a digit (the three
        # cross-cutting pseudo-codes "(air)", "(x-sector)" and "LU" do not)
        name, col, pattern = expr[len("count_unique_matching:"):].split("#", 2)
        return float(len({r[col] for r in read_rows(pointer_path(root, name), comments=False)
                          if re.match(pattern, r[col])}))
    if expr.startswith("count_unique:"):
        name, col = expr[len("count_unique:"):].split("#")
        return float(len({r[col] for r in read_rows(pointer_path(root, name), comments=False)}))
    if expr.startswith("max_abs:"):
        name, col = expr[len("max_abs:"):].split("#")
        return max(abs(float(r[col])) for r in read_rows(pointer_path(root, name), comments=False))
    if expr.startswith("count_where:"):
        name, key = expr[len("count_where:"):].split("#")
        return float(len(matching_rows(root, name, key)))
    if expr.startswith("pct_where:"):
        name, key, col = expr[len("pct_where:"):].split("#")
        rows = read_rows(pointer_path(root, name))
        wanted = parse_key(key)
        part = sum(float(r[col]) for r in rows if all(r.get(k) == v for k, v in wanted))
        whole = sum(float(r[col]) for r in rows)
        return 100.0 * part / whole
    if " - " in expr:
        a, b = expr.split(" - ", 1)
        return float(resolve_pointer(root, a)) - float(resolve_pointer(root, b))
    return float(resolve_pointer(root, expr))
