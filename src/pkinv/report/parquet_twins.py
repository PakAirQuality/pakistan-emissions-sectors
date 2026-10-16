"""Parquet twins of the two canonical long tables.

THE CATALOG PROMISED A FILE THAT DID NOT EXIST. pakemis_product_catalog.csv declared the
monthly panel's representations as `csv;parquet` from the day the catalog was written, and
no monthly parquet was ever built - the annual panel had one (annual_product writes it), and
the declaration was copied across. The reviewer's package specification asks for a parquet
twin of the atomic annual table as well. Both are written here, from the CSV the release
hashes, so the twin can never carry numbers the CSV does not: the CSV is the product, the
parquet is a representation of it, and a test reads both back and asserts equality row for
row.

Column types are inferred from the CSV by pandas with the identifier columns pinned to
strings, so a `month` written as 201507 stays an integer and a `period_id` stays text. The
writer is pyarrow with a fixed compression, which makes the file byte-stable across runs on
one pyarrow version; it is NOT in release_manifest.PRODUCT_PATTERNS, exactly as the existing
annual parquet is not, because pyarrow's footer names its own version and a manifest hash
would then pin the release to a library build rather than to the numbers.

Reads:  outputs/pakemis_atomic_annual.csv
        outputs/pakemis_monthly_fy2015_16_fy2024_25.csv
Writes: outputs/pakemis_atomic_annual.parquet
        outputs/pakemis_monthly_fy2015_16_fy2024_25.parquet
"""

from pkinv.assets import asset_path
import os
import sys

from pkinv.paths import OUTPUTS

TWINS = (
    ("pakemis_atomic_annual.csv", "pakemis_atomic_annual.parquet"),
    ("pakemis_monthly_fy2015_16_fy2024_25.csv", "pakemis_monthly_fy2015_16_fy2024_25.parquet"),
)

# Identifier columns that must stay text even when every value happens to look numeric.
TEXT_COLUMNS = ("period_id", "component_id", "gas", "configuration_id", "geography_id",
                "sector_id", "ipcc_code", "category", "subitem", "gas_origin", "estimate_status",
                "activity_status", "evidence_class", "method_id", "uncertainty_model_id",
                "native_unit", "source_stream_id", "release_id", "closure_basis",
                "temporal_evidence_class", "timing_target", "temporal_status", "profile_id",
                "source_id", "borrowed_from_year", "special_period_flag")


def write_twin(csv_name, parquet_name):
    import pandas as pd

    src = asset_path(OUTPUTS, csv_name)
    dst = asset_path(OUTPUTS, parquet_name)
    frame = pd.read_csv(src, comment="#", dtype={c: "string" for c in TEXT_COLUMNS},
                        keep_default_na=False, na_values=[])
    for col in frame.columns:
        if col in TEXT_COLUMNS:
            continue
        if frame[col].dtype == object:
            converted = pd.to_numeric(frame[col], errors="coerce")
            if converted.notna().sum() == (frame[col] != "").sum():
                frame[col] = converted
    frame.to_parquet(dst, engine="pyarrow", index=False, compression="snappy")
    return len(frame), len(frame.columns)


def main():
    try:
        import pandas  # noqa: F401
        import pyarrow  # noqa: F401
    except ImportError as exc:
        print("parquet twins: %s is not installed; the CSV products stand alone" % exc.name)
        return 0
    for csv_name, parquet_name in TWINS:
        rows, cols = write_twin(csv_name, parquet_name)
        print("Parquet twin -> outputs/%s  (%d rows x %d columns)" % (parquet_name, rows, cols))
    return 0


if __name__ == "__main__":
    sys.exit(main())
