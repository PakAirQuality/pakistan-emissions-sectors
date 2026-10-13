"""Build the legacy monthly request view from the normalized request register.

The register describes each request once. ``monthly_request_components.csv`` links
that request to one or more inventory sectors/components. The historical combined
CSV remains a generated compatibility view for existing reports and external users.
"""
from __future__ import annotations

import argparse

from pkinv.activity.store import read_rows
from pkinv.core.io import write_or_check
from pkinv.paths import ROOT
from pkinv.assets import asset_path


REGISTER = asset_path(ROOT, "data", "shared", "requests", "monthly_request_register.csv")
COMPONENTS = asset_path(ROOT, "data", "shared", "requests", "monthly_request_components.csv")
VIEW = asset_path(ROOT, "data", "shared", "requests", "views", "monthly_data_requests.csv")
COMPONENT_FIELDS = ("request_id", "sector_id", "component", "source_order")
VIEW_FIELDS = ("request_id", "recipient", "purpose", "period_requested", "requested_fields",
               "definitions_and_boundary", "preferred_format", "status", "contact_or_reference",
               "sector_id", "component", "date_sent", "followup_date", "response_status",
               "received_files", "remaining_gap")


def rows():
    requests = read_rows(REGISTER)
    components = read_rows(COMPONENTS)
    by_id = {row["request_id"]: row for row in requests}
    if len(by_id) != len(requests):
        raise ValueError("monthly request register contains duplicate request IDs")
    output = []
    for relation in sorted(components, key=lambda row: int(row["source_order"])):
        request_id = relation["request_id"]
        if request_id not in by_id:
            raise ValueError("request component references missing request: " + request_id)
        output.append({**by_id[request_id], "sector_id": relation["sector_id"],
                       "component": relation["component"]})
    return output


def run(*, check=False):
    output = rows()
    return write_or_check(VIEW, VIEW_FIELDS, output, check=check, lineterminator="\n")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    return run(check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
