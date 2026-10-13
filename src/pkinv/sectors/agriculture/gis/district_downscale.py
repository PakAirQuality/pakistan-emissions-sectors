"""District-level (ADM2, 119) spatial downscaling of the province control totals + nowcasts.

`district_control[d][cat] = province_control[p][cat] × district_share[p][d][cat]`, where the district
share is the category's griddable proxy (GLW livestock / MapSPAM rice / cropland / FRP) summed within
each district polygon, normalised by the province sum -> sums to 1 within each province by construction
(same invariant as province_shares.csv). The split is dasymetric (proxy-based) -- no district activity
survey exists. The 'Other' province (GB/AJK/ICT) has incomplete GAUL district coverage, so it is kept
as a single province-level residual rather than over-concentrated in Islamabad.

Nowcast time series downscale as `district[d]_t = province[p]_t × share[p][d]` (province supplies the
temporal shape, the proxy supplies the district magnitude; within-province timing is shared -- a
documented first-order simplification).
"""

from pkinv.assets import asset_path
from pkinv.activity.store import input_exists as _input_exists
import csv
import os
import sys


from pkinv.core.gis.grid import build_grid, PROVINCES, PROV_ID  # noqa: E402
from pkinv.sectors.agriculture.downscale import provincial_matrix    # noqa: E402
from pkinv.sectors.agriculture.gis.run_gis import resolve_proxies, CATEGORIES   # noqa: E402

from pkinv.paths import ROOT, DATA

OUT_CSV = asset_path(ROOT, "outputs", "district_totals_2024.csv")
CENSUS_DISTRICT = asset_path(DATA, "activity", "livestock_district_2024.csv")
NAMED = ["Punjab", "Sindh", "Khyber Pakhtunkhwa", "Balochistan"]   # districts; 'Other' kept as residual
OTHER = "Other"
TOL = 1e-6
# enteric-CH4-weighted heads (matches proxies.GLW_EF_WEIGHT); buffalo dominates per-head
_EF_HEAD = {"cattle": 40.0, "buffalo": 55.0, "sheep": 5.0, "goats": 5.0}


# The one shared normaliser. This module carried its own copy, byte-divergent from the
# residential copy by nothing yet guaranteed by nothing; core.adm2 is now the single home,
# and tests/test_adm2.py proved the swap changes no name this module ever normalises.
from pkinv.core.adm2 import normalise as _norm  # noqa: E402
from pkinv.activity.store import read_rows


NO_SHAPE = {}      # {province: {canonical unit name: share}} - census units with no polygon


def _census_livestock_shares(grid, glw_arr):
    """Livestock district shares from the 2024 census (EF-weighted heads), joined to the grid's
    ADM2 shapes THROUGH THE CANONICAL CROSSWALK (rc42, the twentieth review's S-2).

    Returns ({district_idx: share}, n_matched, n_no_shape) or (None, 0, 0) if the census file is
    absent. Every census district resolves to a canonical unit (pkinv.core.adm2.resolve); a unit
    with a polygon lands on its shape, several units on one shape sum (Karachi's seven, Kohistan's
    three); a unit with NO polygon (Cholistan Area, Larkana District - the boundary vintage) keeps
    its census head as a named row of the panel with no shape, which the cube turns into the
    already-declared "unit with no polygon" fallback event. Nothing is estimated from a proxy:
    rc41 name-matched the census with a bare normaliser, left 15 shapes (Sheikhupura, Vihari,
    Karachi, Mirpurkhas, Nawabshah, ...) to a GLW proxy scaled onto the census unit - 25.5 Mt of
    enteric and manure mass placed by a dasymetric surface while the census sat unread - and
    never consumed 38 of the 137 census districts. A named-province shape the census does not
    reach is a build failure here, not a fallback."""
    if not _input_exists(CENSUS_DISTRICT):
        return None, 0, 0
    from pkinv.core import adm2
    canonical = adm2.load_canonical()
    index = {_norm(name): i for i, name in enumerate(grid.districts)}
    by_shape = {}        # district_idx -> EF-weighted head
    lost = {}            # province -> {canonical name: head}
    for r in _dictread(CENSUS_DISTRICT):
        h = sum(float(r.get(s, 0) or 0) * w for s, w in _EF_HEAD.items())
        unit = canonical[adm2.resolve(r["district"])]
        if unit["province_id"] not in NAMED:
            continue
        if unit["shape_id"]:
            idx = index.get(_norm(unit["shape_name"]))
            if idx is None:
                raise SystemExit("census district %r resolves to shape %r, which the grid does not "
                                 "carry" % (r["district"], unit["shape_name"]))
            by_shape[idx] = by_shape.get(idx, 0.0) + h
        else:
            lost.setdefault(unit["province_id"], {})
            lost[unit["province_id"]][unit["canonical_name"]] = \
                lost[unit["province_id"]].get(unit["canonical_name"], 0.0) + h
    NO_SHAPE.clear()
    shares, matched, no_shape = {}, 0, 0
    for prov in NAMED:
        dids = grid.districts_in(prov)
        unmatched = [grid.districts[d] for d in dids if d not in by_shape]
        if unmatched:
            raise SystemExit("grid shapes in %s the 2024 livestock census does not reach: %s - "
                             "extend data/adm2_crosswalk.csv; a proxy is not an answer"
                             % (prov, unmatched))
        tot = sum(by_shape[d] for d in dids) + sum(lost.get(prov, {}).values())
        for d in dids:
            shares[d] = by_shape[d] / tot
        NO_SHAPE[prov] = {name: head / tot for name, head in lost.get(prov, {}).items()}
        matched += len(dids)
        no_shape += len(lost.get(prov, {}))
    return shares, matched, no_shape


def _dictread(path):
    return read_rows(path, comments=False)


def district_shares(grid, proxies, cat_proxy):
    """{category: {district_idx: share}} -- proxy share of each district within its (named) province.
    Livestock categories (glw_livestock proxy) use real 2024 census district counts where available,
    falling back to the GLW-2020 dasymetric proxy for unmatched districts."""
    census, cmatched, cfallback = (None, 0, 0)
    if "glw_livestock" in set(cat_proxy.values()) and "glw_livestock" in proxies:
        census, cmatched, cfallback = _census_livestock_shares(grid, proxies["glw_livestock"])
    if census is not None:
        print("  livestock district shares: PBS 2024 census through the canonical crosswalk "
              "(%d shapes, %d census units with no polygon carried as named rows)"
              % (cmatched, cfallback))
    shares = {}
    for cat in CATEGORIES:
        if census is not None and cat_proxy[cat] == "glw_livestock":
            shares[cat] = dict(census)
            continue
        arr = proxies[cat_proxy[cat]]
        s = {}
        for prov in NAMED:
            dids = grid.districts_in(prov)
            sums = {d: float(arr[grid.district_mask(d)].sum()) for d in dids}
            tot = sum(sums.values())
            if tot > 0:
                for d in dids:
                    s[d] = sums[d] / tot
            else:                                    # uniform by cell count if the proxy is empty
                cells = {d: int(grid.district_mask(d).sum()) for d in dids}
                ctot = sum(cells.values()) or 1
                for d in dids:
                    s[d] = cells[d] / ctot
        shares[cat] = s
    return shares


def district_controls(grid=None, proxies=None, cat_proxy=None, matrix=None):
    """Per-district annual controls (Mt CO2e) by category, reconciling to the province controls."""
    if grid is None:
        grid = build_grid()
    if proxies is None:
        proxies, cat_proxy, _ = resolve_proxies(grid)
    matrix = matrix or provincial_matrix()
    shares = district_shares(grid, proxies, cat_proxy)
    rows = []
    for cat in CATEGORIES:
        for prov in NAMED:
            for d in grid.districts_in(prov):
                v = matrix[prov][cat] * shares[cat].get(d, 0.0)
                rows.append({"district": grid.districts[d], "province": prov, "category": cat,
                             "co2e_Mt_AR5": v})
            # rc42: the census units with no polygon carry their own share of the livestock
            # categories as named rows (the cube spreads them by the province proxy as a
            # declared fallback event); other categories never had them
            if cat_proxy[cat] == "glw_livestock":
                for name, share in sorted(NO_SHAPE.get(prov, {}).items()):
                    rows.append({"district": name, "province": prov, "category": cat,
                                 "co2e_Mt_AR5": matrix[prov][cat] * share})
        rows.append({"district": "Other (GB/AJK/ICT residual)", "province": OTHER, "category": cat,
                     "co2e_Mt_AR5": matrix[OTHER][cat]})     # not district-split (incomplete coverage)
    return rows, shares, matrix


def check(rows, matrix):
    """Per (province, category): Σ districts == province control; total == national."""
    agg = {}
    for r in rows:
        agg[(r["province"], r["category"])] = agg.get((r["province"], r["category"]), 0.0) + r["co2e_Mt_AR5"]
    worst = 0.0
    for prov in PROVINCES:
        for cat in CATEGORIES:
            got = agg.get((prov, cat), 0.0)
            worst = max(worst, abs(got - matrix[prov][cat]))
    nat = sum(matrix[p][c] for p in PROVINCES for c in CATEGORIES)
    got = sum(r["co2e_Mt_AR5"] for r in rows)
    return worst, abs(got - nat), nat


def downscale_series(series_by_prov, category, grid, shares, weights=None):
    """{prov:{key:val}} province series -> {district_name:{key:val}}.

    With per-district-per-time `weights[category][prov][district_idx][time_key]` present, each province-
    time emission is split across its districts by that time's weights: E_{d,t}=E_{p,t}*w_{d,t}/Σ_d w_{d,t}
    -- so each district carries its OWN timing while Σ_d E_{d,t}==E_{p,t} exactly. Without weights (or
    where a time has no district weight) it falls back to the static proxy share. 'Other' stays a
    residual. Reconciles: Σ districts == province series (per time and annually)."""
    cat_w = (weights or {}).get(category)
    out = {}
    for prov in NAMED:
        dids = grid.districts_in(prov)
        pser = series_by_prov.get(prov, {})
        pw = cat_w.get(prov) if cat_w else None          # {district_idx: {time_key: weight}}
        if pw:                                            # per-time district split (real timing)
            for t, val in pser.items():
                wsum = sum(pw.get(d, {}).get(t, 0.0) for d in dids)
                for d in dids:
                    frac = (pw.get(d, {}).get(t, 0.0) / wsum) if wsum > 0 else shares[category].get(d, 0.0)
                    if frac <= 0:
                        continue
                    dd = out.setdefault(grid.districts[d], {})
                    dd[t] = dd.get(t, 0.0) + val * frac
        else:                                             # static within-province shape (fallback)
            for d in dids:
                sh = shares[category].get(d, 0.0)
                if sh > 0:
                    out[grid.districts[d]] = {k: v * sh for k, v in pser.items()}
    if OTHER in series_by_prov:
        out["Other (residual)"] = dict(series_by_prov[OTHER])
    return out


def main():
    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    grid = build_grid()
    if grid.district_id is None:
        print("No PAK_ADM2.geojson - run src/pkinv/gis/fetch_adm2.py first.")
        return 1
    proxies, cat_proxy, _ = resolve_proxies(grid)
    rows, shares, matrix = district_controls(grid, proxies, cat_proxy)
    worst_prov, nat_gap, nat = check(rows, matrix)

    from pkinv.core import adm2 as _adm2
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["district", "adm2_id", "province", "category", "co2e_Mt_AR5"])
        for r in rows:
            w.writerow([r["district"],
                        ("" if r["district"] == "Other"
                         else _adm2.resolve(r["district"])),
                        r["province"], r["category"], round(r["co2e_Mt_AR5"], 5)])

    # top districts by total
    tot = {}
    for r in rows:
        tot[r["district"]] = tot.get(r["district"], 0.0) + r["co2e_Mt_AR5"]
    top = sorted(tot.items(), key=lambda kv: -kv[1])[:8]
    print("District downscaling: %d districts (4 provinces) + Other residual -> district_totals_2024.csv"
          % sum(len(grid.districts_in(p)) for p in NAMED))
    print("  reconciliation: worst per-province residual %.2e Mt | national %.1f (gap %.2e)"
          % (worst_prov, nat, nat_gap))
    print("  top districts (Mt CO2e): " + ", ".join("%s %.1f" % (d.split(" District")[0], v) for d, v in top[:5]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
