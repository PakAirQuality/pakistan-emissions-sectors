"""Shared mechanics for declared per-stream registries.

Three registries assign a value to every source stream by (module, category, subitem prefix):
data/stream_geometry.csv (which geometry a stream emits from), data/stream_grid_proxy.csv
(which raster spreads it within its administrative units) and data/stream_reporting_sector.csv
(which sector IPCC 2006 reports it under, beside the module that computes it). They must match
streams by IDENTICAL rules - the most specific declared prefix wins, a stream matching nothing
raises - or the registries drift apart in semantics while agreeing in syntax. So the matcher
lives once, here, and all of them import it.
"""


def match_prefix(rows, module, category, subitem, value_field, what):
    """The most specific declared row for a stream; raises naming the stream on none.

    rows: dicts carrying module, category, subitem_prefix and value_field. A row with an
    empty subitem_prefix is the category default; a longer matching prefix beats a shorter
    one. Raising is the contract: a stream with no declaration is exactly the silent gap
    these registries exist to close.
    """
    best = None
    for row in rows:
        if row["module"] != module or row["category"] != category:
            continue
        prefix = row["subitem_prefix"]
        if prefix and not subitem.startswith(prefix):
            continue
        if best is None or len(prefix) > len(best["subitem_prefix"]):
            best = row
    if best is None:
        raise KeyError(
            "no %s declared for stream (%s, %s, %s) - add a row to the registry; a stream "
            "with no declaration is the silent gap the registry exists to close"
            % (what, module, category, subitem))
    return best[value_field]
