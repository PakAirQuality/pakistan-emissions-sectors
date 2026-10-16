#!/usr/bin/env python3
"""Which commit each PUBLISHED release actually was, verified against this repository's git.

    python3 scripts/build_published_vintages.py
    -> data/catalog/published_release_vintages.csv

WHY THIS EXISTS. A version string is not, by itself, a pin. The API serving PakEmis
fetches a release directory and verifies it against that directory's own
`semantic_release.json`, so a served copy is always internally consistent - which is
exactly what hid the following. The Explorer serves `1.0.0rc59` faithfully, byte-identical
to commit 5915e0c0; this repository's working tree, still labelled `1.0.0rc59`, has moved
hundreds of commits past that tree, dozens of them touching `outputs/semantic/`. Punjab
FY2015-16 reads 220.114574 Mt from the served copy and 220.768318 Mt from this
repository's, a difference of 0.653744 Mt in 21 `physical`-view industry and power cells
that carry the SAME result_row_id on both sides. Neither side's guards could notice,
because each verifies against its own declaration.

So the published vintages are recorded as (version, commit, two digests) and every row is
CHECKED against git: the commit must exist, and the bytes it held for
`outputs/semantic/semantic_release.json` and `outputs/release_manifest.json` must hash to
the digests that were published. That is a falsifiable statement about history rather than
a label, and tests/test_published_vintages.py re-checks it on every run.

WHAT THE ROWS COST TO ESTABLISH. Twelve of the thirteen rows carry their commit in the
serving repository's release table. rc49's entry records only "git latest record", and the
commit was recovered by hashing: 21b54d27d656. A first attempt searched only the commits
that TOUCHED the contract file, found the contract at c4ad155d3c90 with a non-matching
manifest, and nearly recorded rc49 as a release no commit reproduces - the artifacts
commit does not touch the contract it republishes, so it was invisible to that scan.
Searching one layer and concluding from its silence, again.

WHAT THE DIVERGENCE ACTUALLY IS, measured 2026-10-05 against the served copy. All NINE
national totals agree to nine decimal places across the two vintages - FY2023-24 is
469.638224 on both sides, the pin - while the provincial allocation moves 11.87 Mt in
absolute terms and exactly 0.000000 net. 135 rows present in the published vintage are
absent from this tree, all of them province `Other`, `physical` view, five furnace-oil
industrial-combustion streams over nine years and three gases, carrying 0.004053 Mt - the
same 0.004053 that reappears in the cells that differ. It is the declared furnace-oil
provincial re-base (commit a968aeae): the residual province was eliminated and its mass
given a product geography.

So the re-base is not the defect. The defect is that it landed AFTER the vintage was
published under this label and the label did not change, and that no guard on either side
could see it, because every guard on a release's numbers is a NATIONAL guard and this
change conserves the national total at every period. The two axes are measured in
outputs/pakemis_release_axis_fingerprints.csv, which carries one digest per axis per
spatial table per vintage - this register stays about IDENTITY, that one about which axis
moved.

WHAT THIS DOES NOT DO. It does not bump a version, mint anything, or rule that the
divergence is a defect: a release-candidate series may legitimately rebuild under its own
label while it is a candidate. It records that the current __version__ has already been
published from a different tree, so the next mint has to confront that rather than
discover it from a province total.
"""
import hashlib
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pkinv                                                        # noqa: E402
from pkinv.core.io import write_table                               # noqa: E402
from pkinv.core import layers                                       # noqa: E402

OUT = os.path.join(ROOT, "data", "catalog", "published_release_vintages.csv")
CONTRACT = "outputs/semantic/semantic_release.json"
MANIFEST = "outputs/release_manifest.json"

# (version, commit, semantic_release.json sha256, release_manifest.json sha256, how the
# commit was established). Transcribed from the serving repository's RELEASES.md, which is
# the publication record: one release is pinned at a time and its row carries both digests.
PUBLISHED = (
    ("1.0.0rc59", "5915e0c0",
     "bf9fef0dde2db46d595391c36dda50be45f9525289ec7ec3e434dd81af0b4316",
     "7e7fed3f559f0c1379ea8aa412bc9b1d0bfd58c074be68ac5ca21687713c874a", "stated"),
    ("1.0.0rc58", "53273f9d",
     "41a17985020f8578a3d580d9d27349e2b8734e1aefba792f2381c7988708aa42",
     "e1342443371e5307a7ce3b7b2b0513713c4289754ce2396c7c158797912d2257", "stated"),
    ("1.0.0rc57", "27b37210",
     "51d605339623e7180f69e4b1d631edc9d9a0f04e78da34e14420f7e284181a44",
     "f9a4079a5448d25888d30f1b1fea94d7d9e0378220ba9479ff112ce4e44217de", "stated"),
    ("1.0.0rc56", "96536a00",
     "2a5c2d25ac569bf2cb6ebd8a1335253e721ef0cacc6a5924adc6dcf5278de90f",
     "453be7fbe252d2ef15f33c77b3277af0fbb5d9539f907c70b7407f7f144931c2", "stated"),
    ("1.0.0rc55", "5044572a",
     "8cf24cd0d6bab300fd9aee82cb7eb6014bc037bd6c19f1bc5434adc1b8b7b71b",
     "a89b3e04e3c5de9f4395496f9d3e9bc40c33e2eeaec3eebb326594fc0a59d68a", "stated"),
    ("1.0.0rc54", "30c5a697",
     "df635dc28af834adf819f0c8821b21d5f16e192bae39a489cf9dcb43b73cd1a5",
     "e338c2fc25d67a6d683c12792d90f038658c6c4762782f39ce0f07c4cb17359a", "stated"),
    ("1.0.0rc53", "09b4445a",
     "e5832c1b7100fe08a7f47f892e1514f5ef6aafc869d407281220a011740de6c9",
     "ab3ba2f9a7bb53d80d512e047fce5ef4f34886fd11a61bf52cf4e8df64ee4f8d", "stated"),
    ("1.0.0rc52", "06643c3a",
     "75bb03f5ab15bcc7089f027cddbe2c4a0fd3b06b340cb2bb2417ea66b714e8f0",
     "78a16eee67fe8e2d19e5a8ef06eb5522c6c56d641853c0d229f7d0d856155717", "stated"),
    ("1.0.0rc51", "9acbf489",
     "aff51ddb9e74c251bc2ec23b761a3e2c4ebddf0a859469c85c134a30f072bf87",
     "c11fe8783cab39cfaefe3f020f16a74972ee4b4da1c68d34e63124a0fd07eb8b", "stated"),
    ("1.0.0rc50", "19fb48c3",
     "014cfcfce78ae439b4b5f9f110f0302e1bbdb6df47a87e4805f9fe5c18b8a9c6",
     "5a82b58bd742a8426154941776f1592c06568e5e3afa9619201a03171105615f", "stated"),
    ("1.0.0rc49", "21b54d27",
     "a608bb378551258ebe15e69564e57abfe94049db515b9cdb83843c78858b2ff8",
     "714f62b19c8e08e558e2bb03077a12555f90a04e7866b73c9bd4737583bc747f",
     "recovered-by-hashing"),
    ("1.0.0rc47", "51b5acf9",
     "3fbe78f1263e5047993809f65e38706f021948277b2d31e2c9ffde0e56818957",
     "848a1460559da96a74766b93c9cc1eb7955ccf906767803e7cd557afb4ddb56d", "stated"),
    ("1.0.0rc42", "5e42b7cb12",
     "0d612d2e19ec055cf7768f86cb5dffd2b803a0856a22a9e36c0a9af03ef28d4d",
     "630d11228d768eef5e3889a916bdf5c7610f330f4327689ba38ef845e203c9ce", "stated"),
)


def blob_sha256(commit, path):
    """sha256 of the bytes `commit` held at `path`, or None if it held nothing there."""
    # rc69: releases through rc68 exist only in the private history, which the restricted
    # layers' checkout holds (pkinv.core.layers asks the public repository first).
    held = layers.git_show(commit, path, root=ROOT)
    return None if held is None else hashlib.sha256(held).hexdigest()


def disk_sha256(path):
    with open(os.path.join(ROOT, path), "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def blob(commit, path):
    return layers.git_show(commit, path, root=ROOT)


def commits_since(commit, path=None):
    args = ["git", "rev-list", "--count", "%s..HEAD" % commit]
    if path:
        args += ["--", path]
    run = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    return int(run.stdout.strip()) if run.returncode == 0 else -1


def main():
    rows = []
    for version, commit, contract, manifest, basis in PUBLISHED:
        at_contract = blob_sha256(commit, CONTRACT)
        at_manifest = blob_sha256(commit, MANIFEST)
        verified = at_contract == contract and at_manifest == manifest
        rows.append({
            "version": version,
            "commit": commit,
            "semantic_release_sha256": contract,
            "release_manifest_sha256": manifest,
            "commit_basis": basis,
            "git_reproduces_both_digests": "yes" if verified else "NO",
            "contract_at_commit": at_contract or "MISSING",
            "manifest_at_commit": at_manifest or "MISSING",
        })

    current = pkinv.__version__
    published = {r["version"]: r for r in rows}
    tree_contract, tree_manifest = disk_sha256(CONTRACT), disk_sha256(MANIFEST)
    row = published.get(current)
    if row is None:
        state, detail = "not-yet-published", "this version string has never been served"
    elif (row["semantic_release_sha256"] == tree_contract
          and row["release_manifest_sha256"] == tree_manifest):
        state, detail = "matches-published", "the tree is the published vintage, byte for byte"
    else:
        state = "diverged-under-the-same-label"
        # No commit COUNTS here either: they rise with every commit and would restale
        # the register daily. The count is printed to stdout instead, where a reader sees
        # it at build time and no file has to be rewritten for it.
        detail = ("the tree differs from the vintage published as %s (commit %s). The label "
                  "does not identify the content, so the next mint must bump the version "
                  "rather than republish this one" % (current, row["commit"]))
    # The working-tree row deliberately carries NO digests. A first version wrote the
    # live sha256 of both files, and that register went stale on every regeneration of
    # the release manifest - several times per release dance - so the guard would have
    # failed on routine work and taught people to rebuild it without reading it. What is
    # durable is the STATE: it changes only when the version is bumped or the tree
    # returns to the published bytes, and the test RECOMPUTES it rather than comparing a
    # stored digest.
    rows.append({
        "version": current,
        "commit": "(working tree)",
        "semantic_release_sha256": "n.a. - see commit_basis",
        "release_manifest_sha256": "n.a. - see commit_basis",
        "commit_basis": "state recomputed by tests/test_published_vintages.py",
        "git_reproduces_both_digests": "n.a.",
        "contract_at_commit": state,
        "manifest_at_commit": detail,
    })

    banner = [
        "PUBLISHED RELEASE VINTAGES: which commit each served release actually was, and",
        "whether this repository's git reproduces both of its published digests. The last",
        "row is not a published vintage - it is the working tree, and its two text columns",
        "say how the tree stands against the vintage already published under its own label.",
        "A version string is not a pin: see this script's docstring for the 0.653744 Mt",
        "provincial difference that proved it.",
    ]
    write_table(OUT, list(rows[0]), rows, banner=banner)
    print("Published release vintages -> %s" % OUT)
    bad = [r for r in rows if r["git_reproduces_both_digests"] == "NO"]
    print("   %d published vintage(s), %d verified against git, %d not"
          % (len(rows) - 1, len(rows) - 1 - len(bad), len(bad)))
    print("   working tree (%s): %s" % (current, state))
    if state == "diverged-under-the-same-label":
        print("     %d commits since %s, %d of them touching outputs/semantic/"
              % (commits_since(row["commit"]), row["commit"],
                 commits_since(row["commit"], "outputs/semantic/")))
    for r in bad:
        print("   UNREPRODUCED %s at %s" % (r["version"], r["commit"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
