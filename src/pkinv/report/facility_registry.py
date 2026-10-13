"""Publish the facility registry as a release product.

data/facility_registry.csv is the declared registry (built and reviewed through
scripts/build_facility_registry.py); this module validates it against the geometry-set and
ADM2 registries it participates in and publishes it with the release version stamped, the
same relationship pakemis_validation.csv has to data/validation_registry.csv. It recomputes
nothing.

Usage:  python3 -m pkinv.report.facility_registry
Writes: outputs/pakemis_facility_registry.csv
"""

from pkinv.assets import asset_path
import csv
import os

import pkinv
from pkinv.core import adm2
from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

BBOX = (60.5, 23.5, 77.5, 37.5)
STATUSES = ("active", "coordinate_unresolved", "prospective", "observation_only", "retired")


def registry():
    return read_rows(asset_path(DATA, "facility_registry.csv"))


def build():
    rows = registry()
    canonical = adm2.load_canonical()
    for row in rows:
        if row["status"] not in STATUSES:
            raise ValueError("%s: unknown status %r" % (row["facility_id"], row["status"]))
        if row["latitude"].strip():
            lon, lat = float(row["longitude"]), float(row["latitude"])
            if row["adm2_id"] != "not-applicable" and not (
                    BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
                raise ValueError("%s outside the Pakistan bbox" % row["facility_id"])
        elif row["status"] in ("active",):
            raise ValueError("%s is active with no coordinates - that is what "
                             "coordinate_unresolved is for" % row["facility_id"])
        # A semicolon-joined list marks a facility on a shared geoBoundaries shape
        # (the same convention the ADM2 cube view uses); every member must resolve.
        if row["adm2_id"] not in ("unresolved", "not-applicable") \
                and any(part not in canonical
                        for part in row["adm2_id"].split(";")):
            raise ValueError("%s cites unknown adm2_id %r"
                             % (row["facility_id"], row["adm2_id"]))
        row["release_version"] = pkinv.__version__
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = asset_path(OUTPUTS, "pakemis_facility_registry.csv")
    fields = list(rows[0])
    write_table(path, fields, rows)
    geocoded = sum(1 for r in rows if r["latitude"].strip())
    resolved = sum(1 for r in rows
                   if r["adm2_id"] not in ("unresolved", "not-applicable"))
    print("facility registry -> %s" % path)
    print("  %d facilities, %d geocoded (%.1f%%), %d ADM2-resolved"
          % (len(rows), geocoded, 100.0 * geocoded / len(rows), resolved))
    import collections
    for status, n in collections.Counter(r["status"] for r in rows).most_common():
        print("  %-24s %d" % (status, n))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
