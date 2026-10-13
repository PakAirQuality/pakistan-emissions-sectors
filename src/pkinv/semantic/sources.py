"""The source products the semantic phase reads, by product id, with their release digests.

Every table declares which products it derives from; the release JSON records their sha256 at
build time (pkinv.core.manifest.sha256_file, the release manifest's own function), and a test
asserts those digests equal the release manifest's - the layer cannot describe products the
release did not hash."""

from pkinv.assets import asset_path
import json
import os
from collections import OrderedDict
from contextlib import contextmanager
from types import MappingProxyType

from pkinv.activity.store import CATALOG_PATH, read_rows
from pkinv.core.manifest import sha256_file
from pkinv.paths import DATA, ROOT

SCHEMAS = asset_path(DATA, "product_schemas.csv")

# product_id -> relative path, from data/product_schemas.csv (the registry, not a second list)
def registry():
    return {r["product_id"]: r["relative_path"] for r in read_rows(SCHEMAS)}


# Inputs that are registries or data files rather than products, named by path.
DATA_INPUTS = {
    "periods": "data/periods.csv",
    "months": "data/months.csv",
    "adm2_canonical": "data/adm2_canonical.csv",
    "province_shares": "data/province_shares.csv",
    "scenarios": "data/scenarios.csv",
    "method_registry": "data/method_registry.csv",
    "cross_sector_ledger_map": "data/cross_sector_ledger_map.csv",
    "completeness": "outputs/completeness.csv",
    "national_all_sectors": "outputs/national_all_sectors.csv",
    "national_all_sectors_ledger": "outputs/national_all_sectors_ledger.csv",
    "national_uncertainty_montecarlo": "outputs/national_uncertainty_montecarlo.csv",
    "timeseries_1990_2024": "outputs/timeseries_1990_2024.csv",
    "grid_cube": "outputs/pakemis_grid_0p05_monthly.nc",
    "grid_cube_ledger": "outputs/pakemis_grid_0p05_monthly_ledger.nc",
}


class Sources:
    """Reads by name, remembering every path opened so the release JSON can hash them."""

    def __init__(self, max_cached_rows=100000):
        self.products = registry()
        self.used = {}
        self._rows = OrderedDict()
        self._cached_rows = 0
        self._max_cached_rows = max_cached_rows
        self._digests = {}
        self._tracking = None
        self._identities = {}
        catalog = asset_path(ROOT, CATALOG_PATH)
        self._input_sources = {}
        if os.path.exists(catalog):
            with open(catalog, encoding="utf-8") as handle:
                self._input_sources = {t["source_path"]: t for t in json.load(handle)["tables"]}

    @contextmanager
    def track(self):
        """Record reads for one table, including reads satisfied from the shared cache."""
        previous, names = self._tracking, set()
        self._tracking = names
        try:
            yield names
        finally:
            self._tracking = previous

    def path(self, name):
        rel = self.products.get(name) or DATA_INPUTS.get(name)
        if rel is None and name.startswith(("data/", "outputs/")):
            rel = name
        if rel is None:
            raise KeyError("no product or data input named %r" % name)
        self.used[name] = rel
        if self._tracking is not None:
            self._tracking.add(name)
        return asset_path(ROOT, rel)

    def rows(self, name):
        path = self.path(name)
        table = self._input_sources.get(self.used[name])
        if table:
            self._identities[name] = table["path"]
        if path in self._rows:
            self._rows.move_to_end(path)
            return self._rows[path]
        rows = tuple(MappingProxyType(row) for row in read_rows(path, comments=True, root=ROOT))
        # Large one-use facts must not keep the entire release's source tree in memory.
        if len(rows) <= self._max_cached_rows:
            while self._rows and self._cached_rows + len(rows) > self._max_cached_rows:
                _, evicted = self._rows.popitem(last=False)
                self._cached_rows -= len(evicted)
            self._rows[path] = rows
            self._cached_rows += len(rows)
        return rows

    def digests(self, names=None):
        out = []
        for name in sorted(self.used if names is None else names):
            rel = self._identities.get(name, self.used[name])
            if rel not in self._digests:
                self._digests[rel] = sha256_file(asset_path(ROOT, rel))
            out.append({"name": name, "path": rel, "sha256": self._digests[rel]})
        return out
