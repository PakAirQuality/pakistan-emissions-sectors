"""Derive the `manure_applied` province shares from the gridded proxy of the same name.

The province layer (src/pkinv/inventory/downscale.py) allocates on a static table,
data/province_shares.csv, while the grid layer allocates on rasters. For every other proxy the two
are independent measurements of the same thing. For `manure_applied` they must not be: it is defined
as a per-cell intersection (cropland x livestock density), which has no province-level equivalent --
multiplying province shares and renormalising is a different operation and over-concentrates.

So the province row is DERIVED from the raster: one definition, two representations. This script
regenerates it, and tests/test_manure_proxy.py asserts the shipped CSV still matches, so the two
cannot silently drift apart.

Usage:  python3 -m pkinv.sectors.agriculture.gis.derive_manure_proxy            # print the derived shares
        python3 -m pkinv.sectors.agriculture.gis.derive_manure_proxy --write    # update data/province_shares.csv
"""

from pkinv.assets import asset_path
import csv
import os
import sys


from pkinv.core.gis.grid import build_grid, PROVINCES          # noqa: E402
from pkinv.core.gis.proxies import get_proxy                   # noqa: E402

from pkinv.paths import ROOT, DATA
from pkinv.core.io import write_table

SHARES = asset_path(DATA, "province_shares.csv")
PROXY = "manure_applied"
SOURCE = "Derived (per-cell cropland x GLW livestock; src/pkinv/gis/derive_manure_proxy.py)"


def derive(grid=None):
    """{province: share} summing to 1, from the gridded manure_applied proxy."""
    if grid is None:
        grid = build_grid()
    arr, _ = get_proxy(PROXY, grid)
    tot = {}
    for prov in PROVINCES:
        tot[prov] = float(arr[grid.province_mask(prov)].sum())
    s = sum(tot.values())
    if s <= 0:
        raise ValueError("manure_applied proxy is empty over all provinces")
    return {p: v / s for p, v in tot.items()}


def _read_rows():
    with open(SHARES, newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        return list(r), r.fieldnames


def shipped():
    """The manure_applied row as shipped in data/province_shares.csv, or None."""
    rows, _ = _read_rows()
    for r in rows:
        if r["proxy"] == PROXY:
            return {p: float(r[p]) for p in PROVINCES}
    return None


DP = 6


def _rounded(shares):
    """Round to DP places and absorb the rounding error into the largest share, so the written row
    sums to exactly 1 -- downscale.allocate_rows rejects shares that miss it by more than 1e-6."""
    out = {p: round(shares[p], DP) for p in PROVINCES}
    biggest = max(PROVINCES, key=lambda p: out[p])
    out[biggest] = round(out[biggest] + (1.0 - sum(out.values())), DP)
    return out


def write(shares):
    rows, fields = _read_rows()
    row = {"proxy": PROXY, "source": SOURCE}
    row.update({p: "%.*f" % (DP, v) for p, v in _rounded(shares).items()})
    for k in fields:
        row.setdefault(k, "")
    rows = [r for r in rows if r["proxy"] != PROXY] + [row]
    write_table(SHARES, fields, rows)


def main():
    shares = derive()
    print("manure_applied province shares (per-cell cropland x livestock, aggregated):")
    for p in PROVINCES:
        print("  %-20s %.5f" % (p, shares[p]))
    print("  %-20s %.5f" % ("sum", sum(shares.values())))
    if "--write" in sys.argv:
        write(shares)
        print("-> written to data/province_shares.csv")
    else:
        cur = shipped()
        if cur is None:
            print("(not yet in province_shares.csv; rerun with --write)")
        else:
            worst = max(abs(cur[p] - shares[p]) for p in PROVINCES)
            print("  shipped row differs by at most %.2e" % worst)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
