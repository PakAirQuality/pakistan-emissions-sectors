"""Which files the manuscripts cite as evidence, and whether a reader can actually get them.

WHY THIS EXISTS. Section 12 tells the reader that the derived quantities "are deposited in
full", and the papers cite output files by path as the evidence behind particular claims.
Both are true statements about different sets. The deposit ships what
release_manifest.PRODUCT_PATTERNS names - a curated list, deliberately so, "nothing is swept
in" - and the papers cite whatever table actually carries the number, which is not the same
thing. Nothing compared the two, so a citation could point at a file the archive does not
contain and no test would notice.

It does. Of the output files the manuscripts cite by path, a substantial minority are absent
from the deposit manifest. They exist in the repository, so the citation is not wrong about
where the number lives; it is wrong about what a reader who has only the archive can open.

WHAT THE ROLES SAY, AND WHY THAT IS THE INTERESTING PART. Most of the absent files are typed
`intermediate` or `diagnostic` in data/catalog/artifact_roles.csv - working files that no
reader-facing claim was supposed to rest on. But a paper citing a table in a results section
IS a reader-facing claim resting on it. So the gap is not only a packaging oversight: for
those files the role and the citation disagree about what the file is, and one of the two
has to give. Either the file ships, or the paper stops pointing at it and points at the
deposited product that carries the same numbers.

THIS FILE DECIDES NOTHING. It lists every citation with its role, its deposit status and the
sections that cite it, so the choice can be made per file with the evidence in front of it.
tests/test_citation_deposit.py ratchets the undeposited count downward only.

Usage:  python3 scripts/build_citation_deposit_audit.py [--check]
Writes: outputs/pakemis_citation_deposit_audit.csv
"""
import argparse
import collections
import csv
import glob
import io
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from pkinv.assets import asset_path                                     # noqa: E402
from pkinv.report.artifact_inventory import as_a_reader_sees_it         # noqa: E402
from pkinv.core.io import read_rows, write_table                        # noqa: E402
from pkinv.paths import OUTPUTS, ROOT                                   # noqa: E402
from pkinv.paths import PAPER_NATIONAL_MAIN  # noqa: E402

OUT = asset_path(OUTPUTS, "pakemis_citation_deposit_audit.csv")

# \texttt{...} is how every manuscript names a file, and it does so in TWO notations. The
# national sections and agriculture's appendix write the path - \texttt{outputs/x.csv} - while
# the fugitives, ippu, aviation, railways, residential, power, transport and waste appendices
# write the bare filename in an itemised list. This pattern used to require the `outputs/`
# prefix, so it saw 110 citations and could not see 194 more: every bare-named file, none of
# which was in the deposit. The register's two halves then disagreed about the word "cited" -
# the artifact inventory counts a bare filename (it searches basenames) and this audit did not
# count it at all - and the published ratchet of 53 was a notation-defined subset of a set of
# about 247. A reader cannot obtain a file any better for its name having been typeset with a
# directory in front of it.
#
# A glob or a brace expansion is a FAMILY rather than a citation of one file and is skipped,
# with a count reported. So is a bare name that resolves to more than one artifact (17
# basenames appear at two paths) - the citation is real but which file it names is a guess,
# and a guess in this register is worse than a skip.
CITE = re.compile(r"\\texttt\{([^}]*?\.(?:csv|nc|json|parquet))\}")

FIELDS = ("row_kind", "artifact", "role", "release_tier", "in_deposit", "named_as", "rows",
          "bytes", "cited_in", "verdict")

BANNER = """\
# WHAT THE MANUSCRIPTS CITE, AND WHETHER THE DEPOSIT CONTAINS IT
#
# One row per distinct output file NAMED in any manuscript section (row_kind=citation), in
# either notation - `\texttt{outputs/x.csv}` or the bare `\texttt{x.csv}` the sector
# appendices use - plus summary rows by role. `named_as` records which notation each file was
# found in, because the two were once measured as different things. `in_deposit` is membership of
# outputs/pakemis_deposit_manifest.csv, which ships what release_manifest.PRODUCT_PATTERNS
# names. A file marked absent still EXISTS in the repository - what it is absent from is the
# archive a reader downloads.
#
# This audit decides nothing. Where a cited file is absent, the fix is one of two things and
# the row carries what is needed to choose: ship it (add a literal entry to PRODUCT_PATTERNS)
# or re-cite the deposited product that already carries the same numbers.
"""


def _tex_files():
    return sorted(glob.glob(os.path.join(PAPER_NATIONAL_MAIN, "**", "*.tex"),
                            recursive=True)
                  + glob.glob(os.path.join(ROOT, "papers", "**", "*.tex"), recursive=True))


def _one_artifact_per_basename():
    """{basename: outputs-relative artifact} for the basenames that resolve UNIQUELY.

    The inventory keys its rows relative to outputs/, so a bare citation is resolved through
    this map and then written in the same canonical form as a pathed one - otherwise the same
    file would appear as two rows whenever both notations are used for it.
    """
    seen = collections.defaultdict(list)
    for row in read_rows(asset_path(OUTPUTS, "pakemis_artifact_inventory.csv")):
        seen[os.path.basename(row["artifact"])].append(row["artifact"])
    return {base: paths[0] for base, paths in seen.items() if len(paths) == 1}


def citations():
    """({outputs/ path: sections}, {outputs/ path: notation}, skip counts by reason)."""
    out, notation = collections.defaultdict(set), {}
    resolvable = _one_artifact_per_basename()
    skipped = collections.Counter()
    for path in _tex_files():
        text = io.open(path, encoding="utf-8").read()
        rel = os.path.relpath(path, ROOT)
        for m in CITE.finditer(text):
            # ONE normalisation, shared with the artifact inventory. This line used to
            # carry its own `replace("\\_", "_")` and was blind to \allowbreak, so three
            # freshly cited files - the two transport CNG tables and the waste release
            # assignment - were reported ABSENT FROM THE REPOSITORY, which is the audit's
            # most serious verdict, for a break hint the typesetting required.
            raw = as_a_reader_sees_it(m.group(1)).strip()
            if "*" in raw or "{" in raw or raw.endswith("/"):
                skipped["a glob or brace expansion, which names a family"] += 1
                continue
            if raw.startswith("outputs/"):
                canonical, named = raw, "path"
            elif os.path.basename(raw) != raw:
                # a path into some other tree (data/, sources/): not this register's subject
                skipped["a path outside outputs/"] += 1
                continue
            elif raw in resolvable:
                canonical, named = "outputs/" + resolvable[raw], "bare"
            else:
                skipped["a bare name with no unique artifact"] += 1
                continue
            out[canonical].add(rel)
            was = notation.get(canonical)
            notation[canonical] = "both" if was and was != named else named
    return out, notation, skipped


def build():
    cited, notation, _skipped = citations()
    deposit = {r["path"] for r in read_rows(asset_path(OUTPUTS,
                                                       "pakemis_deposit_manifest.csv"))}
    inv = {}
    for r in read_rows(asset_path(OUTPUTS, "pakemis_artifact_inventory.csv")):
        inv[r["artifact"]] = r
        inv[os.path.basename(r["artifact"])] = r

    rows = []
    for path in sorted(cited):
        meta = inv.get(path) or inv.get(os.path.basename(path)) or {}
        present = path in deposit
        role = meta.get("role", "(not in the artifact inventory)")
        if present:
            verdict = "deposited"
        elif not os.path.exists(os.path.join(ROOT, path)):
            verdict = "CITED BUT ABSENT FROM THE REPOSITORY TOO"
        else:
            verdict = "CITED BUT NOT DEPOSITED (role: %s)" % role
        rows.append({
            "row_kind": "citation", "artifact": path, "role": role,
            "release_tier": meta.get("release_tier", ""),
            "in_deposit": "yes" if present else "no",
            "named_as": notation.get(path, ""),
            "rows": meta.get("rows", ""), "bytes": meta.get("bytes", ""),
            "cited_in": "; ".join(sorted(cited[path])),
            "verdict": verdict,
        })

    by_role = collections.Counter()
    for r in rows:
        if r["in_deposit"] == "no":
            by_role[r["role"]] += 1
    for role, n in sorted(by_role.items(), key=lambda kv: (-kv[1], kv[0])):
        rows.append({
            "row_kind": "summary_by_role", "artifact": "", "role": role,
            "release_tier": "", "in_deposit": "no", "named_as": "", "rows": "", "bytes": "",
            "cited_in": "",
            "verdict": "%d cited file(s) typed %s are not in the deposit" % (n, role),
        })
    rows.append({
        "row_kind": "summary_total", "artifact": "", "role": "", "release_tier": "",
        "in_deposit": "", "named_as": "", "rows": str(len(rows) - len(by_role)), "bytes": "",
        "cited_in": "",
        "verdict": "%d distinct output files named; %d deposited, %d not"
                   % (len(cited), sum(1 for r in rows
                                      if r["row_kind"] == "citation" and r["in_deposit"] == "yes"),
                      sum(by_role.values())),
    })
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the shipped file matches a fresh build; write nothing")
    args = ap.parse_args()
    rows = build()
    if args.check:
        if not os.path.exists(OUT):
            raise SystemExit("%s does not exist" % OUT)
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=FIELDS, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
        if io.open(OUT, encoding="utf-8").read() != BANNER + buf.getvalue():
            raise SystemExit("%s differs from a fresh build" % OUT)
        print("%s: current" % OUT)
        return
    write_table(OUT, FIELDS, rows, banner=BANNER.splitlines())
    total = next(r for r in rows if r["row_kind"] == "summary_total")
    print("Citation deposit audit -> %s" % OUT)
    print("   %s" % total["verdict"])
    for r in rows:
        if r["row_kind"] == "summary_by_role":
            print("   %s" % r["verdict"])


if __name__ == "__main__":
    main()
