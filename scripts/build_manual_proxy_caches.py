#!/usr/bin/env python3
"""Write the grid-resolution caches of the manual rice rasters (rc69).

The SPAM 2020 rice rasters are restricted layers (src/pkinv/core/layers.py): a public clone
does not hold them. Every reader takes only their resample to the inventory grid
(pkinv.core.gis.proxies.build_manual_proxy), so that resample is committed, and a public
clone rebuilds the rice geography and the water-regime axis from it. Run with the rasters
mounted; it refuses otherwise. `--check` compares without writing.

Usage:  python3 scripts/build_manual_proxy_caches.py [--check]
Writes: data/sectors/agriculture/gis/proxy_manual_<raster>_267x340.npy
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import numpy as np  # noqa: E402

from pkinv.assets import asset_path  # noqa: E402
from pkinv.core.gis import proxies  # noqa: E402
from pkinv.core.gis.grid import build_grid  # noqa: E402


def main(argv):
    grid = build_grid()
    stale = []
    for filename in proxies.MANUAL_CACHED:
        path = asset_path(proxies.MANUAL_DIR, filename)
        if not os.path.exists(path):
            raise SystemExit("%s is not mounted; the cache is written from the raster itself "
                             "(python3 scripts/overlay.py link PATH)" % filename)
        array, _desc = proxies._resample_manual(grid, path, filename)
        cache = proxies.manual_cache_path(grid, filename)
        current = np.load(cache) if os.path.exists(cache) else None
        same = current is not None and current.dtype == array.dtype and \
            current.tobytes() == array.tobytes()
        if "--check" in argv:
            if not same:
                stale.append(os.path.relpath(cache, ROOT))
            continue
        if not same:
            np.save(cache, array)
        print("%s -> %s (%s)" % (filename, os.path.relpath(cache, ROOT),
                                 "unchanged" if same else "written"))
    if stale:
        print("stale: %s" % ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
