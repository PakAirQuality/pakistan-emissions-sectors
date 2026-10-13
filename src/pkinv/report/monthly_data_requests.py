"""The monthly gap, turned into an acquisition programme with a price on every line.

WHY THIS EXISTS. The temporal decomposition says which components should vary within the year
and are carried flat, and how much mass that is. That is a diagnosis. It is not yet a thing
anyone can act on, because the reader who could close a gap - a statistics office, a utility, a
regulator - needs to know what to send, for which period, on what boundary, and what it would
be worth. This joins the two: one row per request per component, with the request's text
written by hand and every QUANTITY read from the decomposition.

THE NUMBERS ARE NOT TYPED. Not one figure in the generated document is a literal. The
unobserved mass, the share of national monthly mass and the months already carried all come
from outputs/pakemis_temporal_decomposition.csv at generation time, so a request cannot go on
claiming a gap that has since been closed - which is exactly what would happen to a document
that quoted them once. When the PBS series landed and power's gap fell, this table fell with it
because it never held the number.

THE COMPLETENESS RULE IS THE POINT. A request table assembled by attention would quietly omit
whatever nobody thought about. The test asserts the other direction: every component whose
unobserved mass exceeds one percent of the national monthly total must appear here. The table
is complete against the gap by construction, or the suite fails.

Usage:  python3 -m pkinv.report.monthly_data_requests
Writes: outputs/pakemis_monthly_data_requests.csv
        docs/monthly_data_requests.md
"""

from pkinv.assets import asset_path
import collections
import csv
import os

from pkinv.paths import DATA, OUTPUTS, ROOT
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

REQUESTS = asset_path(DATA, "monthly_data_requests.csv")
DECOMPOSITION = asset_path(OUTPUTS, "pakemis_temporal_decomposition.csv")
OUT = asset_path(OUTPUTS, "pakemis_monthly_data_requests.csv")
DOC = asset_path(ROOT, "docs", "monthly_data_requests.md")

FIELDS = ("request_id", "recipient", "sector_id", "component", "unobserved_Mt_AR5",
          "share_of_national_pct", "months_observed_pct", "expected_temporal_driver",
          "period_requested", "requested_fields", "definitions_and_boundary",
          "preferred_format", "purpose", "status", "contact_or_reference")

# A component holding more than this share of the nine-year monthly product's mass, flat and
# unobserved, must be somebody's request. Below it the table may be selective and say so.
MATERIAL = 1.0


def _rows(path):
    return read_rows(path, comments=False)


def decomposition():
    """{(sector_id, component): row} for the components that carry an unobserved gap."""
    return {(r["sector_id"], r["component"]): r for r in _rows(DECOMPOSITION)}


def material_components(gap=None):
    """The components big enough that leaving them unrequested would be an omission."""
    gap = gap if gap is not None else decomposition()
    total = sum(float(r["co2e_Mt_AR5"]) for r in gap.values())
    return {key: 100.0 * float(row["unobserved_Mt_AR5"]) / total
            for key, row in gap.items()
            if 100.0 * float(row["unobserved_Mt_AR5"]) / total > MATERIAL}


def build():
    gap = decomposition()
    total = sum(float(r["co2e_Mt_AR5"]) for r in gap.values())
    out = []
    for request in _rows(REQUESTS):
        key = (request["sector_id"], request["component"])
        if not key[0] and not key[1]:
            # A NON-TIMING lane (rc20): a drafted request whose payoff is module
            # evidence rather than monthly resolution - the F-gas species detail
            # is the first. It rides the register so the drafts live in one
            # place, carries no decomposition weight, and its priced stake lives
            # in its own product (the screening file for F-gases).
            out.append({
                "request_id": request["request_id"],
                "recipient": request["recipient"],
                "sector_id": "", "component": "",
                "unobserved_Mt_AR5": "",
                "share_of_national_pct": "",
                "months_observed_pct": "",
                "expected_temporal_driver": "not a monthly-timing request",
                "period_requested": request["period_requested"],
                "requested_fields": request["requested_fields"],
                "definitions_and_boundary": request["definitions_and_boundary"],
                "preferred_format": request["preferred_format"],
                "status": request["status"],
                "contact_or_reference": request["contact_or_reference"],
                "purpose": request["purpose"],
            })
            continue
        found = gap.get(key)
        if found is None:
            raise KeyError("request %s names %s, which the decomposition does not have"
                           % (request["request_id"], key))
        unobserved = float(found["unobserved_Mt_AR5"])
        out.append({
            "request_id": request["request_id"], "recipient": request["recipient"],
            "sector_id": key[0], "component": key[1],
            "unobserved_Mt_AR5": round(unobserved, 4),
            "share_of_national_pct": round(100.0 * unobserved / total, 3),
            "months_observed_pct": found["months_observed_pct"],
            "expected_temporal_driver": found["expected_temporal_driver"],
            "period_requested": request["period_requested"],
            "requested_fields": request["requested_fields"],
            "definitions_and_boundary": request["definitions_and_boundary"],
            "preferred_format": request["preferred_format"],
            "purpose": request["purpose"], "status": request["status"],
            "contact_or_reference": request["contact_or_reference"],
        })
    return sorted(out, key=lambda r: (-(r["share_of_national_pct"] or 0.0),
                                      r["request_id"]))


def _exact_shares():
    """{(sector, component): unrounded share of monthly mass} - the quantity the document's
    sums are formed from. rc42: the CSV rows carry the share rounded to 3 dp, and summing
    those rounded values landed MON-GAS-01 on an exact tie (4.765) that printed as 4.76
    while the unrounded sum is 4.7652 - a chained rounding, not a stale document. Sums are
    formed from the exact shares and rounded once, at print."""
    gap = decomposition()
    total = sum(float(r["co2e_Mt_AR5"]) for r in gap.values())
    return {key: 100.0 * float(row["unobserved_Mt_AR5"]) / total for key, row in gap.items()}


def document(rows=None):
    """The generated markdown, as a string, so a test can regenerate and compare it."""
    rows = rows if rows is not None else build()
    exact = _exact_shares()

    def share_of(row):
        if row["share_of_national_pct"] == "":
            return 0.0
        return exact[(row["sector_id"], row["component"])]
    by_request = collections.OrderedDict()
    for row in sorted(rows, key=lambda r: r["request_id"]):
        by_request.setdefault(row["request_id"], []).append(row)
    ranked = sorted(by_request.items(),
                    key=lambda kv: -sum(r["share_of_national_pct"] or 0.0
                                        for r in kv[1]))

    lines = [
        "# What would close the monthly gap, and what each piece is worth",
        "",
        "*Generated by `python3 -m pkinv.report.monthly_data_requests`. Every quantity here is",
        "read from `outputs/pakemis_temporal_decomposition.csv` when this file is written, so a",
        "request cannot go on claiming a gap that has been closed. Do not edit it by hand.*",
        "",
        "The monthly product carries %.1f Mt of CO2e-AR5 across nine years. Of that, %.1f%% is"
        % (sum(float(r["co2e_Mt_AR5"]) for r in decomposition().values()),
           sum(share_of(r) for r in rows)),
        "mass that should vary within the year, is carried flat, and is asked for below.",
        "",
        "| request | recipient | what it would close | share of monthly mass |",
        "|---|---|---|---|",
    ]
    for request_id, group in ranked:
        share = sum(share_of(r) for r in group)
        stake = "**%.2f%%**" % share if share else "module evidence, not timing"
        lines.append("| `%s` | %s | %d component%s | %s |"
                     % (request_id, group[0]["recipient"], len(group),
                        "" if len(group) == 1 else "s", stake))
    lines.append("")

    for request_id, group in ranked:
        first = group[0]
        lines.extend([
            "## %s — %s" % (request_id, first["recipient"]),
            "",
            first["purpose"] + ".",
            "",
            "**Period.** %s  " % first["period_requested"],
            "**Fields.** %s  " % first["requested_fields"],
            "**Boundary and definitions.** %s  " % first["definitions_and_boundary"],
            "**Format.** %s  " % first["preferred_format"],
            "**Status.** %s  " % first["status"],
            "**Where to ask.** %s" % first["contact_or_reference"],
            "",
            "| component | unobserved | share of monthly mass | months already carried | driver |",
            "|---|---|---|---|---|",
        ])
        for row in sorted(group,
                          key=lambda r: -(r["share_of_national_pct"] or 0.0)):
            if row["share_of_national_pct"] == "":
                lines.append("| (module evidence, not a timing gap) | - | - | - | %s |"
                             % row["expected_temporal_driver"])
                continue
            lines.append("| %s / %s | %.2f Mt | %.2f%% | %s%% | %s |"
                         % (row["sector_id"], row["component"], row["unobserved_Mt_AR5"],
                            row["share_of_national_pct"], row["months_observed_pct"],
                            row["expected_temporal_driver"]))
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, FIELDS, rows)
    with open(DOC, "w", encoding="utf-8") as handle:
        handle.write(document(rows))
    requests = len({r["request_id"] for r in rows})
    print("monthly data requests -> %s" % OUT)
    print("                        %s" % DOC)
    print("  %d requests over %d components, worth %.1f%% of the monthly product's mass"
          % (requests, len(rows), sum(r["share_of_national_pct"] or 0.0 for r in rows)))
    missing = set(material_components()) - {(r["sector_id"], r["component"]) for r in rows}
    print("  %d component%s above %.0f%% of national mass has no request"
          % (len(missing), "" if len(missing) == 1 else "s", MATERIAL))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
