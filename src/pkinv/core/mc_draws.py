"""Persisted Monte-Carlo draw files: a sector engine's draws, written once, consumed
by the national pool.

WHY THIS EXISTS (rc12, the eighth review's P0). Waste's parameter-rerun engine and
fugitives' bounded split-triangular engine produce asymmetric, physically-constrained
draws that the national pooled MC used to REPLACE with mean-preserving lognormal
surrogates - compressing waste's upper tail from a sector P97.5 of ~98.9 Mt to a
national-row 63.5. The repair injects the sector engines' own draws into the national
pool, and the draw file is the interface: each native engine writes a seeded
100,000-draw file in its sector stage, the national engine consumes it by draw index,
and the file itself is the reviewer's "reproducible draw file" - hashed into the
release manifest, its first 10,000 draws bit-identical to the published sector run
(both engines draw per-parameter identity-seeded or strictly sequential streams, so
extending n_iter appends rather than reshuffles; tests assert the prefix).

WHY INJECTION SEVERS NOTHING. Waste and fugitives are CRN-islands in the national
parameter stream: every dependency group touching them is scoped to that module alone
in data/parameter_scope.csv, so no other module's draws share a z-vector with theirs
- their national rows were already bit-identical between the within_sector and
cross_sector scenarios. A tripwire test (test_parameters) asserts the islands stay
islands; if a future group ever spans an injected module and any other, the honest
options are stream-replay by identical stream_seed keys or a declared decorrelation,
and the tripwire forces that conversation instead of a silent severing.

FORMAT, PINNED. CSV with a draw_index column and one float column per national
category plus MODULE_TOTAL, floats written with repr() (shortest round-trip);
sidecar <name>.meta.json carrying seed, n_iter, the engine's module path, the
distribution id, the RNG identity, the DETERMINISTIC value of every column (the
staleness guard: the national engine refuses a file whose deterministic totals no
longer match the live components), and the sha256 of the CSV bytes as written.
No gzip: the hash surface is the bytes on disk.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import hashlib
import json
import os
import sys

from pkinv.paths import OUTPUTS

DRAW_DIR = asset_path(OUTPUTS, "mc_draws")

RNG_IDENTITY = ("Mersenne Twister (CPython random module); gauss via Box-Muller "
                "with paired-variate cache; python %d.%d" % sys.version_info[:2])


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


def write(name, columns, meta):
    """Write outputs/mc_draws/<name>.csv + .meta.json; returns (csv_path, meta).

    columns: ordered dict-like {column_name: [draws]} - every column same length.
    meta: seed, n_iter, engine, distribution_id, deterministic {column: value}.
    """
    os.makedirs(DRAW_DIR, exist_ok=True)
    names = list(columns)
    lengths = {len(columns[n]) for n in names}
    if len(lengths) != 1:
        raise ValueError("draw columns of unequal length: %s" % lengths)
    n = lengths.pop()
    if n != meta["n_iter"]:
        raise ValueError("meta n_iter %d != column length %d" % (meta["n_iter"], n))
    path = asset_path(DRAW_DIR, "%s.csv" % name)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["draw_index"] + names)
        for i in range(n):
            w.writerow([i] + [repr(columns[c][i]) for c in names])
    full = dict(meta, columns=names, rng=RNG_IDENTITY, sha256=sha256(path),
                file=os.path.relpath(path, OUTPUTS))
    with open(asset_path(DRAW_DIR, "%s.meta.json" % name), "w",
              encoding="utf-8") as f:
        json.dump(full, f, indent=2, sort_keys=True)
        f.write("\n")
    return path, full


def read(name):
    """Return (columns, meta) for one draw file, verifying the recorded hash."""
    path = asset_path(DRAW_DIR, "%s.csv" % name)
    meta_path = asset_path(DRAW_DIR, "%s.meta.json" % name)
    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)
    actual = sha256(path)
    if actual != meta["sha256"]:
        raise ValueError("%s: draw file hash %s does not match its meta record %s "
                         "- the file and its provenance have diverged"
                         % (name, actual[:16], meta["sha256"][:16]))
    columns = {c: [] for c in meta["columns"]}
    for row in _activity_rows(path, comments=False):
        for c in meta["columns"]:
            columns[c].append(float(row[c]))
    if any(len(v) != meta["n_iter"] for v in columns.values()):
        raise ValueError("%s: row count does not match meta n_iter" % name)
    return columns, meta
