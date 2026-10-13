"""Attribute the provincial effect of each spatial-proxy correction separately.

Three proxy decisions changed together, and their effects largely cancel at province level. Reporting
only the net would hide that: the previous allocation was close to the corrected one because two
large errors offset, not because it was right. Each change is worth +/-2 Mt on its own, so the
agreement was coincidental and would have broken as soon as either input moved.

  (1) indirect N2O split by source stream   -- was one lumped row per pathway on fertilizer_N,
                                               though ~2/3 of that nitrogen is livestock-derived
  (2) applied manure -> manure_applied      -- was livestock_total (ignores that manure goes to
                                               fields); cropland alone ignores transport cost, so
                                               the proxy is the per-cell intersection of the two
  (3) rice synthetic N -> rice_area         -- was fertilizer_N

Usage:  python3 -m pkinv.eval.proxy_attribution
Writes: outputs/eval/proxy_attribution.csv
"""

from pkinv.assets import asset_path
import csv
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData, DATA_DIR  # noqa: E402
from pkinv.sectors.agriculture.run_inventory import build_components      # noqa: E402
from pkinv.sectors.agriculture.downscale import PROVINCES, load_shares   # noqa: E402

from pkinv.paths import ROOT

OUT = asset_path(ROOT, "outputs", "eval")

# proxy each stream had BEFORE this round, keyed by the subitem it now carries
LEGACY = {
    "Direct N2O - synthetic fertiliser (rice EF1FR)": "fertilizer_N",
    "Direct N2O - organic manure": "livestock_total",
}
LEGACY_PREFIX = {"Indirect N2O - volatilisation": "fertilizer_N",
                 "Indirect N2O - leaching/runoff": "fertilizer_N"}
# which change each subitem belongs to
CHANGE = {"Direct N2O - synthetic fertiliser (rice EF1FR)": "3 rice -> rice_area",
          "Direct N2O - organic manure": "2 manure -> manure_applied"}


def _legacy_proxy(sub):
    if sub in LEGACY:
        return LEGACY[sub]
    for pre, px in LEGACY_PREFIX.items():
        if sub.startswith(pre):
            return px
    return None


def _change_for(sub):
    if sub in CHANGE:
        return CHANGE[sub]
    if sub.startswith("Indirect N2O -"):
        # the organic sub-stream moved for BOTH reasons; attribute its manure_applied step to (2)
        return ("2 manure -> manure_applied" if "organic manure" in sub
                else "1 split indirect by stream")
    return None


def attribute():
    data = InventoryData()
    shares = load_shares()
    comps = build_components(data)
    from pkinv.sectors.agriculture import downscale
    rows = []
    for c in comps:
        sub = c["subitem"]
        old = _legacy_proxy(sub)
        if old is None:
            continue
        new = downscale.proxy_for(c)
        # the organic indirect streams moved fertilizer_N -> livestock_total (change 1) and then
        # livestock_total -> manure_applied (change 2); split the delta at that intermediate step
        if sub.startswith("Indirect N2O -") and "organic manure" in sub:
            mid = "livestock_total"
            rows.append((sub, "1 split indirect by stream", c["co2e_Mt_AR5"], old, mid))
            rows.append((sub, "2 manure -> manure_applied", c["co2e_Mt_AR5"], mid, new))
            continue
        rows.append((sub, _change_for(sub), c["co2e_Mt_AR5"], old, new))

    per_change = {}
    for sub, change, amt, old, new in rows:
        d = per_change.setdefault(change, {p: 0.0 for p in PROVINCES})
        for p in PROVINCES:
            d[p] += amt * (shares[new][p] - shares[old][p])
    return per_change


def main():
    os.makedirs(OUT, exist_ok=True)
    per_change = attribute()
    changes = sorted(per_change)
    with open(asset_path(OUT, "proxy_attribution.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["province"] + changes + ["net"])
        for p in PROVINCES:
            vals = [per_change[c][p] for c in changes]
            w.writerow([p] + [round(v, 4) for v in vals] + [round(sum(vals), 4)])

    print("Provincial effect of the spatial-proxy corrections (Mt CO2e, AR5):")
    print("  %-20s %22s %26s %22s %8s"
          % ("province", changes[0], changes[1], changes[2], "net"))
    for p in PROVINCES:
        vals = [per_change[c][p] for c in changes]
        print("  %-20s %+22.2f %+26.2f %+22.2f %+8.2f" % (p, vals[0], vals[1], vals[2], sum(vals)))
    print()
    for c in changes:
        tot = sum(per_change[c].values())
        biggest = max(PROVINCES, key=lambda p: abs(per_change[c][p]))
        print("  %-28s largest shift %+.2f Mt (%s); sums to %.1e"
              % (c, per_change[c][biggest], biggest, tot))
    print()
    print("  Each change is individually large; the net is small because they offset. The previous")
    print("  allocation was therefore right by cancellation, not by construction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
