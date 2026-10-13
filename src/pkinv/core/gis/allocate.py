"""Dasymetric allocation of provincial control totals to grid cells (Phase 4).

For each (province, category): distribute the provincial control total across the
province's cells in proportion to the proxy, then the cell-sum equals the control total
exactly. National and per-province reconciliation are therefore exact by construction.

If a province's proxy sums to zero (no cropland captured), fall back to uniform over the
province's cells so the control total is still placed (and reconciliation still holds).
"""
import numpy as np

from pkinv.core.gis.grid import PROVINCES


def allocate(grid, proxies, matrix, category_proxy, categories=None,
             proxy_semantics=None):
    """Allocate each category with its own proxy.

    proxies: {name: (H,W) array}. category_proxy: {category: proxy_name}.
    Returns {category: (H,W) Mt CO2e} reconciled exactly to the province×category control totals,
    and a list of (province, category) that fell back to uniform (proxy empty in that province).

    categories defaults to the matrix's own columns. This function spent two releases
    importing agriculture's category list by name - the ONLY thing in core/gis that knew a
    sector existed, and the reason no second sector could allocate through it. The maths was
    always sector-agnostic; now the signature is too.
    """
    # MEASURED HERE rather than by each caller (rc45): this function already knows the
    # proxy's NAME and the grid, which is all the registry needs, and its three sector callers
    # each build their own proxies dict straight from get_proxy. Doing it at the choke point
    # is why there is no second file list to go stale.
    from pkinv.core.gis.grid import cell_area_km2
    from pkinv.core.gis.proxies import as_measure
    area = cell_area_km2(grid)
    if categories is None:
        categories = list(next(iter(matrix.values())))
    out = {c: np.zeros((grid.height, grid.width), dtype=np.float64) for c in categories}
    fallbacks = []
    for prov in PROVINCES:
        mask = grid.province_mask(prov)
        ncells = int(mask.sum())
        if ncells == 0:
            continue
        for cat in categories:
            total = matrix[prov][cat]
            name = category_proxy[cat]
            w = as_measure(name, proxies[name].astype(np.float64), area,
                           declared=(proxy_semantics or {}).get(name))[mask]
            wsum = w.sum()
            if wsum <= 0:                     # proxy empty here -> uniform within province
                # Per square kilometre, not per cell: see core.gis.cube.Context for why.
                from pkinv.core.gis.grid import cell_area_km2
                w = cell_area_km2(grid)[mask]
                wsum = float(w.sum())
                fallbacks.append((prov, cat))
            out[cat][mask] = (w / wsum) * total
    return out, fallbacks


def category_totals(allocated):
    return {c: float(arr.sum()) for c, arr in allocated.items()}
