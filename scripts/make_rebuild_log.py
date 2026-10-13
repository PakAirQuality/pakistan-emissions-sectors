"""Publish the clean-room rebuild log: the seventeenth review's "publish the rebuild
log and unresolved failures", as two artifacts from one run record.

Reads the clean_room_result.json that scripts/clean_room_full.sh writes into its
workdir, joins the rc29 reacquisition sweep's outcomes from
data/acquisition_attempts.csv, and writes:

    docs/rebuild_log.json         machine-readable
    docs/rebuild_log.md           the human page a reviewer reads

Both live under docs/, deliberately outside outputs/: the log records a run that
compared the release manifest and the artifact inventory, so publishing it as a
product would make it describe registries that would then have to describe it.

Unresolved failures are TYPED: every entry carries a reason, and the standing
declared limits (PDF CreationDate, NetCDF byte churn, LFS objects on no remote
until the branch is pushed) are listed as what they are - declared, not
discovered.

Usage:  python3 scripts/make_rebuild_log.py <workdir>/clean_room_result.json
"""

from pkinv.assets import asset_path
import csv
import json
import os
import sys

from pkinv.paths import DATA, OUTPUTS, ROOT

SWEEP_DATE = "2026-08-23"
OUT_JSON = asset_path(ROOT, "docs", "rebuild_log.json")
OUT_MD = asset_path(ROOT, "docs", "rebuild_log.md")

STANDING = [
    {"item": "papers/pdf/*.pdf",
     "reason": "declared non-byte-stable: LaTeX embeds a CreationDate; the run "
               "records build success and hashes, and outputs/pakemis_paper_hashes.csv "
               "is the sidecar a holder verifies against"},
    {"item": "outputs/pakemis_grid_0p05_monthly.nc",
     "reason": "declared byte-churn: the NetCDF byte stream varies per code path "
               "while its content is deterministic (docs/spatial_products_contract.md); "
               "the conservation gates test content, not bytes"},
    {"item": "git-lfs objects (19, ~3 GB, 7 manifest-hashed source documents)",
     "reason": "no remote holds them until the branch is pushed (user-only action), "
               "so a stranger's clone cannot yet materialise them; this run copied "
               "them from the local object store and asserted no pointer survived"},
]


def main():
    result_path = sys.argv[1]
    with open(result_path, encoding="utf-8") as f:
        result = json.load(f)

    attempts = []
    with open(asset_path(DATA, "acquisition_attempts.csv"), encoding="utf-8") as f:
        body = [l for l in f if not l.startswith("#")]
    for r in csv.DictReader(body):
        if r["attempt_date"] == SWEEP_DATE:
            attempts.append({k: r[k] for k in
                             ("dataset", "url_tried", "outcome", "detail")})

    unresolved = list(STANDING)
    for s in result["steps"]:
        if s["status"] in ("FAIL", "WARN"):
            unresolved.append({"item": "step:%s" % s["step"], "reason": s["detail"]})
    for a in attempts:
        if a["outcome"] in ("discovery_failed", "blocked"):
            unresolved.append({"item": "reacquisition:%s" % a["dataset"],
                               "reason": "%s - %s" % (a["outcome"], a["detail"])})

    log = {
        "what_this_is": "the rc29 clean-room reconstruction record: fresh file:// "
                        "clone, fresh venv from requirements.lock, offline proof by "
                        "unroutable proxy, full offline build, full test suite, PDF "
                        "build, manifest comparison (scripts/clean_room_full.sh)",
        "verdict": result["verdict"],
        "headline": result["headline"],
        "environment": result["environment"],
        "clone": result["clone"],
        "steps": result["steps"],
        "reacquisition_sweep": {
            "date": SWEEP_DATE,
            "attempts": attempts,
            "register": "data/not_retained_register.csv holds URL, access date, "
                        "page/table coordinates, retrieval script and hash-or-reason "
                        "for every not-retained source",
        },
        "unresolved_failures": unresolved,
    }
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(log, f, indent=1, sort_keys=True)
        f.write("\n")
    print("wrote %s (verdict %s, %d unresolved items)"
          % (OUT_JSON, log["verdict"], len(unresolved)))

    md = ["# The rc29 clean-room rebuild log", "",
          "**Verdict: %s** — %s" % (log["verdict"], log["headline"]), "",
          "Run by `scripts/clean_room_full.sh`: a fresh `file://` clone of the "
          "release content commit, a fresh virtualenv from `requirements.lock`, an "
          "unroutable proxy exported so any network attempt fails loudly, the full "
          "offline build, the full test suite, the PDF build, and a byte comparison "
          "against the committed outputs. The machine-readable record is "
          "`docs/rebuild_log.json`, beside this page and outside the product "
          "tree it describes.", "",
          "## Environment", ""]
    for k, v in sorted(log["environment"].items()):
        md.append("- **%s**: %s" % (k, v))
    md += ["", "## Steps", "", "| step | status | detail |", "|---|---|---|"]
    for s in log["steps"]:
        md.append("| %s | %s | %s |" % (s["step"], s["status"],
                                        s["detail"].replace("|", "\\|")))
    md += ["", "## The reacquisition sweep (%s)" % SWEEP_DATE, "",
           "| dataset | outcome |", "|---|---|"]
    for a in attempts:
        md.append("| %s | %s |" % (a["dataset"], a["outcome"]))
    md += ["", "Full per-attempt detail, with URLs, lives in "
           "`data/acquisition_attempts.csv`; the per-source metadata contract is "
           "`data/not_retained_register.csv`.", "",
           "## Unresolved failures, each typed", ""]
    for u in unresolved:
        md.append("- **%s** — %s" % (u["item"], u["reason"]))
    md.append("")
    with open(OUT_MD, "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    print("wrote %s" % OUT_MD)


if __name__ == "__main__":
    main()
