"""The semantic release: ONE numerical truth layer, frozen inside the release (v1.0.0 program).

The paper's tables and figures, the Explorer, the downloads and (later) the Ask PakEmis agent
consume the products through this layer by release id and hash; nothing numerical is computed
outside pakemis_query, and every number a consumer prints is a display field of an envelope with
a receipt. The layer DERIVES: every value is the source product's string copied byte for byte,
and the only arithmetic here is exact decimal arithmetic on two shipped numbers (the ADM1 share
products and the configuration-S module sums), each golden-tested to a closure the release
already publishes. Identity is the canonical CSV (header-first, LF, sorted by key); the Parquet
beside it is a representation of that CSV, as pkinv.report.parquet_twins already rules.
"""

from pkinv.assets import asset_path
import os

from pkinv.paths import OUTPUTS

SCHEMA = "pkinv.semantic_release/v1"
OUT_DIR = asset_path(OUTPUTS, "semantic")
ROW_ID_SCHEME = "pkinv.rowid/v1"
