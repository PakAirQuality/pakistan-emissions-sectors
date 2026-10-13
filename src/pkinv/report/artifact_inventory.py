"""Every file this release ships, with its declared role and who names it.

WHY. 406 files live in outputs/. Most are named in no manuscript, README or doc, and the
release manifest hashed 42 of them. So most shipped files had no declared role anywhere, and a
reader downloading the release could not tell a product from a working file. Neither could a
test: two defects found by hand in consecutive passes - a validation registry cited nowhere,
and an IPPU two-register agreement computed on every run and never written down - were
instances of a class nobody could enumerate.

Most of those 280 SHOULD be uncited. A paper naming aviation_openap_lookup_fy2023_24.csv
would be worse, not better. The defect was never the silence; it was that the silence was
indistinguishable from an omission.

WHAT THIS IS. One row per file, joined to data/artifact_roles.csv by first-matching pattern,
carrying what the release manifest knows and which manuscripts name it. The tests then hold
the promises each role makes: canonical implies hashed AND cited, sector_headline implies
cited in its own sector's paper, diagnostic implies cited somewhere.

RECOMPUTES NOTHING it can read. Sizes and row counts come from the files; citation comes from
the manuscripts; hashing comes from the manifest that already did it.

Usage:  python3 -m pkinv.report.artifact_inventory
Writes: outputs/pakemis_artifact_inventory.csv
"""

from pkinv.assets import asset_path
import csv
import fnmatch
import glob
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import read_rows, write_table

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
ROLES = asset_path(DATA, "artifact_roles.csv")
# rc36: EVERY file under outputs/ is inventoried, recursively, and a file in a
# subdirectory is named by its path relative to outputs/ ("gis/x.csv"), so the role
# patterns can address a directory. The old scan saw only top-level csv/nc/json/parquet
# and left 203 shipped files - every .md, .png, .html, .tif and every subdirectory -
# with no declared role at all.
SUFFIXES = None

# Where a reader could meet a file by name. The sector papers are included because a
# sector_headline file's promise is about ITS OWN paper, not about any paper.
# EVERY .tex A READER GETS, not only the ones under sections/. Until rc64 this listed
# papers/*/sections/*.tex and stopped, so anything named in a sector supplement's own body was
# invisible: four of the five supplements are partly monolithic (railways carries 153 lines and
# two \input directives, aviation 278 and four), and 17 artifacts were recorded cited_in=none
# while a supplement named them - every aviation figure, the fugitives and railways CRT cell
# audits, and railways_fuel_history.csv, which a registered claim reads for the steam-era peak.
# The consequence was not cosmetic: the register's whole argument is that a product cited
# nowhere is indistinguishable from a diagnostic nobody needed, and "cited nowhere" was partly
# the scanner's opinion rather than the paper's. The escaped underscore is handled below and
# was NOT the cause.
# VERSION-WILDCARDED, not pinned to the shipped version: before the national paper was
# versioned the flat "paper_national/*.tex" glob caught the compact rewrite as well as the
# article, and pinning these to versions/v1 would have dropped a whole manuscript out of
# the citation scan without anything failing.
DOC_GLOBS = ("paper_national/versions/*/sections/*.tex", "paper_national/versions/*/*.tex",
             "papers/*/sections/*.tex", "papers/*/*.tex", "README.md", "docs/*.md")


def _rows(path):
    return read_rows(path)


def roles():
    """[(pattern, role, owner, description)] in file order - FIRST MATCH WINS."""
    return [(r["pattern"], r["role"], r["owner"], r["description"]) for r in _rows(ROLES)]


def role_of(name, table=None):
    for pattern, role, owner, description in (table or roles()):
        if fnmatch.fnmatch(name, pattern):
            return role, owner, description, pattern
    raise KeyError("%s matches no pattern in data/artifact_roles.csv, and the last pattern "
                   "is meant to be a catch-all" % name)


def as_a_reader_sees_it(text):
    """Strip the LaTeX devices a filename must carry, so the search sees the plain name.

    ONE code path. Used by documents(), by tests/test_citation_scan_normalisation.py, by the
    citation-deposit audit builder, by the module-credit sweep and by the supplement-citation
    getter - every reader of a printed name in the repository. A second implementation of this
    is the defect it guards against, and it has now bitten TWICE: cycle 32 found the escape
    normalised and the break hints not (seven files silently un-cited), and cycle 36 found
    three MORE readers with their own `replace("\\_", "_")`, which reported three freshly
    cited files as absent from the repository. `\%`, `\&` and `~` join the list for the same
    reason: a reader that needs one extra escape adds it here, not locally.
    """
    for device, replacement in (("\\_", "_"), ("\\allowbreak ", ""), ("\\allowbreak", ""),
                                ("\\-", ""), ("\\/", ""), ("\\%", "%"), ("\\&", "&"),
                                ("~", "")):
        text = text.replace(device, replacement)
    return text


def documents():
    """{document label: text}. The label is what a sector-scoped promise is checked against."""
    out = {}
    for pattern in DOC_GLOBS:
        for path in sorted(glob.glob(asset_path(ROOT, pattern))):
            relative = os.path.relpath(path, ROOT)
            label = (relative.split(os.sep)[1] if relative.startswith("papers" + os.sep)
                     else "national")
            try:
                text = open(path, encoding="utf-8").read()
            except OSError:
                continue
            # LaTeX escapes the underscore in a filename, and a long monospace name needs
            # break hints or it prints outside the page; a reader sees the same name through
            # both. Normalising only the underscore was a live defect: the rc64 appendix
            # rewrites added \allowbreak after each escaped underscore in names over 40
            # characters - the fix for a real overfull-box failure - and that silently
            # un-cited seven files this scanner had just been taught to see. One
            # normalisation without the other is worse than neither, because it makes the
            # citation register's answer depend on how the filename had to be typeset.
            out[label] = out.get(label, "") + as_a_reader_sees_it(text)
    return out


def manifest_products():
    """What the manifest WILL hash, from its own patterns - not from the file it last wrote.

    Reading release_manifest.json here made this column one run stale for anything new: the
    inventory runs before the manifest, so a product added this run was hashed as `no` and
    then hashed for real seconds later. The rule is the manifest's own PRODUCT_PATTERNS,
    applied once, so there is no ordering to get wrong and no second vintage of the answer.
    """
    from pkinv.report.release_manifest import PRODUCT_PATTERNS
    names = set()
    for name in universe():
        if any(fnmatch.fnmatch("outputs/" + name, pattern) for pattern in PRODUCT_PATTERNS):
            # the name as the inventory keys it: relative to outputs/, so a product in a
            # subdirectory (v1.0.0: semantic/) is matched by the same name it is listed under
            names.add(name)
    # The paper-hash sidecar matches the pattern and is excluded by the manifest itself,
    # because it is written after the papers that are built after the manifest.
    return names - {"pakemis_paper_hashes.csv"}


def committed_copies():
    """Names (relative to outputs/) of the held products whose registry row carries the
    `committed-copy` sentinel: written by the release fixpoint or the record, after every
    build phase, so no build-time size or row count can honestly describe them."""
    out = set()
    path = asset_path(ROOT, "data", "held_products.csv")
    if not os.path.exists(path):
        return out
    for row in read_rows(path):
        if row.get("sha256_at_release") == "committed-copy" and row["path"].startswith("outputs/"):
            out.add(row["path"][len("outputs/"):])
    return out


def written_later():
    """Files under outputs/ a phase AFTER this inventory declares it writes (run_all.py),
    as names relative to outputs/. rc41: the inventory listed whatever was on disk, and
    recorded the size of every file - so it was complete only when the previous release's
    files were already there, and an empty outputs/ produced a different inventory. These
    are listed by declaration and carry no size or row count, the context-stamped rule
    extended to everything written after this step."""
    from pkinv.run_all import declared_writes_after
    return {w[len("outputs/"):] for w in declared_writes_after("Artifact inventory", inclusive=True)
            if w.startswith("outputs/")}


def universe():
    """Every file under outputs/ on disk, plus the ones declared to be written later."""
    names = set()
    for path in glob.glob(asset_path(OUTPUTS, "**", "*"), recursive=True):
        if os.path.isfile(path):
            names.add(os.path.relpath(path, OUTPUTS).replace(os.sep, "/"))
    return names | written_later()


# RELEASE TIER, derived from role and seeded now so the catalog migration inherits a
# populated field rather than an empty one. `role` conflates four dimensions - release
# importance, scientific content, intended use and build lifecycle - which are not mutually
# exclusive: a facility registry is supporting AND spatial. Tier is the first of those
# dimensions pulled out on its own, under the deletion test: if this file disappeared, could
# a user still interpret, reproduce and validate a declared product?
TIER_OF_ROLE = {
    "canonical": "core",
    "format_variant": "core",       # the same product in another representation
    "sector_headline": "supporting",
    "diagnostic": "audit",
    "build_record": "audit",
    "intermediate": "build",
    # rc36: the classes the recursive scan brought into view
    "figure": "supporting",         # a generated PNG a manuscript or the dashboard shows
    "report_prose": "supporting",   # a runner's Markdown summary of its own tables
    "dashboard": "supporting",
    "tier3_research": "research",   # docs/spatial_products_contract.md: real, citable, not authoritative
    "eval_lane": "research",        # the hand-run evaluation products (make eval)
    # The audit chain: a sector's source-to-result walk and the parameter values behind each
    # stream. SUPPORTING and not canonical on purpose - every number in one is READ from a
    # product that already ships and is already hashed, so hashing the walk as well would
    # hash the same values twice and make a re-render of a citation look like a data change.
    "derivation": "supporting",
}


def _row_count(path):
    if not path.endswith(".csv"):
        return ""
    try:
        with open(path, encoding="utf-8", errors="replace") as handle:
            return max(0, sum(1 for line in handle if not line.startswith("#")) - 1)
    except OSError:
        return ""


def build():
    table = roles()
    hashed = manifest_products()
    docs = documents()

    out = []
    later = written_later()
    for name in sorted(universe()):
        path = asset_path(OUTPUTS, name)
        role, owner, description, pattern = role_of(name, table)
        matching = [p for p, _r, _o, _d in table if fnmatch.fnmatch(name, p)]
        base = os.path.basename(name)
        stem = base.rsplit(".", 1)[0]
        cited = sorted(label for label, text in docs.items()
                       if base in text or stem in text)
        # THE CATCH-ALL DEFERS INSTEAD OF ASSERTING (rc64). Its row types an unmatched file
        # `intermediate`, whose declared meaning is "a working file ... no reader-facing claim
        # rests on it" - a substantive claim about every file nobody has classified. 262 of the
        # 890 shipped artifacts reach it, nearly a third, and 135 of the products a registered
        # claim reads were among them. A file no pattern names is not thereby a working file.
        #
        # More patterns were the obvious fix and the wrong one: the fall-through files have no
        # shared naming structure - a validated cover needed 61 patterns for 74 files, with
        # names like *bridge.csv - which is WHY they fall through in the first place. So the
        # role is derived from the one fact that is already in scope here instead: a
        # fall-through file a manuscript names is evidence behind a claim, which is
        # `diagnostic`; one nothing names is a working file, and `intermediate` is honest.
        #
        # Deliberately NOT in role_of(): that function is the pure pattern lookup, has no
        # citation data, and one test pins its contract that an unwritten filename lands on the
        # catch-all as `intermediate`. The derivation belongs where the evidence is.
        if pattern == "*" and cited:
            role = "diagnostic"
        # A SIZE THIS FILE CANNOT HONESTLY RECORD. release_manifest.json is written after this
        # inventory and stamps the commit it describes, so its byte count differs between a
        # maintainer's working tree and a fresh clone by construction - one byte, which is
        # exactly what the clean-room rebuild reported. The same holds for anything else
        # written later in the release dance. Recording a stale number that looks current is
        # worse than a blank that says why, and deposit_manifest.CONTEXT_STAMPED is the one
        # place that class is declared, so the two files cannot disagree about it.
        from pkinv.report.deposit_manifest import context_stamped
        # rc42: the four files the release fixpoint and the record write AFTER this inventory
        # (data/held_products.csv sentinel `committed-copy`) are the same class - SHA256SUMS
        # was recorded at 67,548 bytes in the content commit and rewritten to 67,654 by the
        # fixpoint, and every clean reproduction rebuilt the inventory truthfully and differed.
        stamped = (context_stamped(asset_path("outputs", name)) or name in later
                   or name in committed_copies())
        out.append({
            "artifact": name,
            "role": role,
            "owner": owner,
            "matched_pattern": pattern,
            "matching_patterns": ";".join(matching),
            "bytes": "" if stamped else os.path.getsize(path),
            "rows": "" if stamped else _row_count(path),
            "release_tier": TIER_OF_ROLE[role],
            "in_release_manifest": "yes" if name in hashed else "no",
            "cited_in": ";".join(cited) or "none",
            "description": description,
        })
    return out


def summary(rows=None):
    rows = rows if rows is not None else build()
    out = {}
    for row in rows:
        bucket = out.setdefault(row["role"], {"files": 0, "hashed": 0, "cited": 0})
        bucket["files"] += 1
        bucket["hashed"] += row["in_release_manifest"] == "yes"
        bucket["cited"] += row["cited_in"] != "none"
    return out


def main():
    rows = build()
    os.makedirs(OUTPUTS, exist_ok=True)
    path = asset_path(OUTPUTS, "pakemis_artifact_inventory.csv")
    write_table(path, list(rows[0]), rows, banner=('# Every file this release ships, with the role it declares and who names it.', '# Roles and their promises are in data/artifact_roles.csv; tests/test_artifact_inventory.py holds them.',))
    print("artifact inventory -> %s" % path)
    print("  %d files" % len(rows))
    print("  %-16s %6s %8s %7s" % ("role", "files", "hashed", "cited"))
    for role, counts in sorted(summary(rows).items()):
        print("  %-16s %6d %8d %7d"
              % (role, counts["files"], counts["hashed"], counts["cited"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
