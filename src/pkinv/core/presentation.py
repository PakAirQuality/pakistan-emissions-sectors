"""The validation package's presentation layer, as the package itself declares it.

A built validation package places READING copies of registered files on the validator's
folder layout (data/parameters/power_params.csv is data/power_params.csv) and a few VIEWS
computed from them (data/SOURCE_MANIFEST.csv, the restricted registry, the extract
index), all enumerated by its FILE_INVENTORY.csv. They are not products of the build:
a walker that enumerates data/ to say "every file here is a registered product" must leave
them out, or it reports the package's own index as unregistered data.

rc41: the first rc41 package's reproduction stopped at the data provenance audit for exactly
that reason, and the deposit manifest would have stopped next. Both read this set now. In
the repository there is no inventory and the set is empty; reproduce.sh copies the
inventory into its working tree so the rebuild sees the same set the package does.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import ROOT

INVENTORY = asset_path(ROOT, "FILE_INVENTORY.csv")
LAYER_KINDS = ("presentation_copy", "view")

_layer = None


def layer():
    """frozenset of repo-relative paths the package inventory marks as presentation copies
    or views; empty where there is no inventory."""
    global _layer
    if _layer is None:
        found = set()
        if os.path.exists(INVENTORY):
            for row in _activity_rows(INVENTORY, comments=False):
                if (row.get("generated_or_source") in LAYER_KINDS
                        or row.get("artifact_role") == "presentation_copy"):
                    found.add(row["relative_path"])
        _layer = frozenset(found)
    return _layer
