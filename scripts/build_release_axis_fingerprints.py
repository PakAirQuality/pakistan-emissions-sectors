#!/usr/bin/env python3
"""Which AXIS of a release moved: the totals every guard checks, or only the allocation?

    python3 scripts/build_release_axis_fingerprints.py
    -> outputs/pakemis_release_axis_fingerprints.csv

THE QUESTION THIS ANSWERS, and why it is not rhetorical. Every guard this project has on
a release's numbers is a NATIONAL guard: the release manifest's `national_totals`, the
pins, the claim matrix, the paper's registered claims, the goldens. A change that
conserves the national total at every period and moves only the spatial allocation passes
every one of them. That is not hypothetical - it happened. The furnace-oil provincial
re-base (commit a968aeae) landed after `1.0.0rc59` was published, under an unchanged
version string, and moved 11.87 Mt of absolute provincial mass at exactly 0.000000 net
while all nine national totals stayed identical to nine decimal places. It surfaced only
because a province total was queried twice.

SO EACH DISAGGREGATED TABLE GETS TWO FINGERPRINTS per published vintage, both computed
from git blobs so the whole comparison reproduces inside this repository: a COARSE one
over (period -> total), which is the grain every existing guard checks, and a FINE one
over ((period, axis key) -> total), which is the grain nothing checked. A re-base that
moves the fine digest and not the coarse one is then a visible row rather than a
discovery.

AND THE AXIS IS NOT ONLY SPACE. The national MONTHLY table shows the same thing on the
time axis: 36 cells, all `Electricity and heat production`, net exactly 0.000000000 and
4.56 Mt absolute - the power profile was re-based within every fiscal year, so
`fact_annual`'s fingerprint is byte-identical to the published vintage's while the monthly
shape is not. Two independent instances, one spatial and one temporal, of the same
structural blind spot.

WHAT THE TABLE SHOWS AS IT STANDS. Four layers carry the signature: provincial by year,
district by year, district by month, and national by month. Their coarse fingerprints
have not moved since rc52 and their fine ones have moved since rc59. The air provincial
layer is the control: it moved on BOTH axes, which is exactly why the existing national
guards DID see the air change. Where the coarse axis moves, this project already notices;
where only the fine axis moves, nothing did. `fact_annual` is the second control - the
grain the guards actually watch, and its fingerprint is unmoved.

Rounded to 6 dp before hashing, because the question is whether the allocation moved and
not whether the last float bit did. A table a vintage did not carry is `absent`, which is
information too - the provincial layer begins at rc47 and the air one at rc49.
"""
import csv
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pkinv                                                        # noqa: E402
from pkinv.core.io import read_rows, write_table                    # noqa: E402

OUT = os.path.join(ROOT, "outputs", "pakemis_release_axis_fingerprints.csv")
VINTAGES = os.path.join(ROOT, "data", "catalog", "published_release_vintages.csv")

# (table, fine-axis column, value column, what it is). The fine axis is whichever
# dimension the coarse period total sums away - a geography for the spatial tables, the
# month for the national monthly one.
TABLES = (
    ("outputs/semantic/fact_adm1_year.csv", "province", "co2e_Mt_AR5",
     "greenhouse gases, province x fiscal year"),
    ("outputs/semantic/fact_adm2_year.csv", "shape_id", "co2e_Mt_AR5",
     "greenhouse gases, district x fiscal year"),
    ("outputs/semantic/fact_adm2_month.csv", "shape_id", "co2e_Mt_AR5",
     "greenhouse gases, district x month"),
    ("outputs/semantic/fact_monthly.csv", "month", "co2e_Mt_AR5",
     "greenhouse gases, national x month - the TIME axis, same blind spot"),
    ("outputs/semantic/fact_annual.csv", "period_id", "co2e_Mt_AR5",
     "greenhouse gases, national x fiscal year - a control: this IS the guarded grain, "
     "so its two fingerprints are the same quantity and must never disagree"),
    ("outputs/semantic/fact_air_adm1_year.csv", "province", "emissions_kt",
     "air pollutants, province x fiscal year - a control: this one moved on both axes, "
     "which is why the national guards did see it"),
)
TIME_COLUMNS = ("period_id", "month", "year")


def digest(mapping):
    payload = "\n".join("%s=%.6f" % ("|".join(k) if isinstance(k, tuple) else k, v)
                        for k, v in sorted(mapping.items()))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def fingerprints(blob, geo, value_column):
    """(national digest, spatial digest, counted rows, why) over one table's aggregates.

    THE COLUMN MUST EXIST BEFORE A DIGEST MEANS ANYTHING. A first version of this used
    row.get(value_column) and happily hashed an empty aggregate for rc47, whose
    fact_adm2_year carried `co2e_Mt_AR5_low`/`_high` rather than `co2e_Mt_AR5`: a
    distinct-looking fingerprint of nothing at all, in a product whose whole job is to
    make a comparison trustworthy. The schema DRIFTS across vintages, so a missing column
    is now its own state and names what the table actually had.
    """
    if blob is None:
        return "absent", "absent", 0, "the vintage did not carry this table"
    lines = [line for line in blob.decode("utf-8").splitlines()
             if not line.startswith("#")]
    reader = csv.DictReader(lines)
    present = reader.fieldnames or []
    if value_column not in present:
        return ("column-absent", "column-absent", 0,
                "this vintage's schema has no %s; it carried %s"
                % (value_column, ", ".join(c for c in present
                                           if c.startswith("co2e") or c.startswith("emissions"))
                   or "no value column this product recognises"))
    if geo not in present:
        return ("column-absent", "column-absent", 0,
                "this vintage's schema has no %s geography column" % geo)
    national, spatial, counted = {}, {}, 0
    for row in reader:
        raw = (row.get(value_column) or "").strip()
        if not raw:
            continue
        # The coarse key is deliberately period_id when the table carries it: for a
        # monthly table the month is the FINE axis, and keying the coarse digest on the
        # month too would make both digests the same quantity and the comparison empty.
        period = next((row[c] for c in TIME_COLUMNS if row.get(c)), "")
        where = row.get(geo) or ""
        national[period] = national.get(period, 0.0) + float(raw)
        # The degenerate case is explicit: when the fine axis IS the coarse key - as for
        # fact_annual, whose axis is period_id - the fine mapping is keyed on the period
        # alone, so the two digests are identical rather than merely equivalent. A first
        # version keyed it on the tuple ("FY2015-16", "FY2015-16"), which hashes
        # differently from "FY2015-16" and made the control fail on its own string
        # formatting while the numbers agreed exactly.
        key = period if where == period else (period, where)
        spatial[key] = spatial.get(key, 0.0) + float(raw)
        counted += 1
    if not counted:
        return ("no-valued-rows", "no-valued-rows", 0,
                "the column exists and every cell in it is empty")
    return digest(national), digest(spatial), counted, "measured"


def blob_at(commit, path):
    run = subprocess.run(["git", "show", "%s:%s" % (commit, path)],
                         cwd=ROOT, capture_output=True)
    return None if run.returncode else run.stdout


def main():
    vintages = [r for r in read_rows(VINTAGES) if r["commit"] != "(working tree)"]
    current = pkinv.__version__
    rows = []
    for path, geo, value_column, what in TABLES:
        measured = []
        for vintage in vintages:
            nat, spa, counted, why = fingerprints(blob_at(vintage["commit"], path), geo,
                                                  value_column)
            measured.append((vintage["version"], vintage["commit"], nat, spa, counted, why))
        try:
            with open(os.path.join(ROOT, path), "rb") as handle:
                tree = fingerprints(handle.read(), geo, value_column)
        except FileNotFoundError:
            tree = ("absent", "absent", 0, "the working tree does not carry this table")
        measured.append((current, "(working tree)") + tree)

        latest = next((m for m in measured[:-1] if m[0] == current), None)
        for version, commit, nat, spa, counted, why in measured:
            if commit != "(working tree)" or latest is None or why != "measured":
                verdict = ""
            elif nat == latest[2] and spa == latest[3]:
                verdict = "matches the published vintage on both axes"
            elif nat == latest[2]:
                verdict = ("FINE AXIS ONLY: the period totals are unchanged, so every "
                           "guard this project has passes while the allocation within "
                           "them has moved")
            elif spa == latest[3]:
                verdict = "period totals moved, allocation unchanged"
            else:
                verdict = "both axes moved, which the existing guards do see"
            rows.append({
                "table": os.path.basename(path),
                "what": what,
                "version": version,
                "commit": commit,
                "fine_axis_key": geo,
                "value_column": value_column,
                "coarse_period_fingerprint": nat,
                "fine_axis_fingerprint": spa,
                "valued_rows": counted,
                "measurable": why,
                "verdict_against_the_published_vintage": verdict,
            })

    banner = [
        "RELEASE AXIS FINGERPRINTS: for each published vintage and each spatial table, one",
        "digest over (period -> total) and one over ((period, geography) -> total). A",
        "re-base that moves the second and not the first passes every national guard this",
        "project has; see the builder's docstring for the one that did. Computed from git",
        "blobs, so the comparison needs nothing outside this repository.",
    ]
    write_table(OUT, list(rows[0]), rows, banner=banner)
    print("Release axis fingerprints -> %s" % OUT)
    for path, _geo, _col, _what in TABLES:
        name = os.path.basename(path)
        tree = [r for r in rows if r["table"] == name and r["commit"] == "(working tree)"]
        if tree and tree[0]["verdict_against_the_published_vintage"]:
            print("   %-28s %s" % (name, tree[0]["verdict_against_the_published_vintage"][:72]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
