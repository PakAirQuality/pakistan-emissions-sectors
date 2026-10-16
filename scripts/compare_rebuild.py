#!/usr/bin/env python3
"""Does a rebuilt tree reproduce the committed products, to the precision a platform allows?

    python3 scripts/compare_rebuild.py [--paths outputs data] [--rtol 1e-9] [--atol 1e-12]

WHY THIS EXISTS (rc69). The public-checks job rebuilds the inventory on Ubuntu and used to
require `git diff --exit-code` against products committed from macOS. The first run that got
that far (38967999114) differed in about seventy files, every one of them floating-point
output - Monte Carlo draws, uncertainty quantiles, spatial shares, gridded netCDF - and two
rasterised PNGs. libm and BLAS differ between the two platforms in the last binary place, so
byte identity across operating systems is not a contract this repository can keep, and a
check that always fails checks nothing. On one platform the release path still requires
byte identity (scripts/clean_rebuild.py); this is the cross-platform check.

THE RULE, per changed file (working tree against HEAD):
  - text cells must be identical;
  - a numeric cell passes if |a - b| <= atol + rtol * max(|a|, |b|), OR if the difference is
    at most one unit in the last printed place of either value: a value that moved by an ulp
    can flip its last printed digit, and that is the expected platform effect, not a change;
  - same rows, same columns, same order;
  - CSV comment lines (the banners) must be identical;
  - a JSON key or CSV/Parquet column that is a digest (sha256, digest, hash) is reported,
    not compared: it digests a file this script compares directly;
  - Parquet and netCDF are read and compared column by column / variable by variable;
  - a PNG cannot be compared across platforms (font rasterisation), so it is listed as
    NOT COMPARED and does not fail the check; the figure checks run where it was rendered.
Anything else that differs, a file added or removed, or a value beyond tolerance fails.
The report prints the largest relative and absolute difference per file, so the size of the
platform effect is published with every run rather than assumed.
"""
import argparse
import csv
import io
import json
import math
import os
import re
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DIGEST_KEY = re.compile(r"(^|_)(sha256|sha1|md5|digest|hash)(_|$)", re.I)
NUMBER = re.compile(r"^[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?$")
RASTER = (".png", ".jpg", ".jpeg")


def git(*args, binary=False):
    out = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout
    return out if binary else out.decode("utf-8")


def changed(paths):
    rows = git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--", *paths)
    out = []
    for entry in filter(None, rows.split("\0")):
        out.append((entry[:2], entry[3:]))
    return out


def printed_ulp(text):
    """One unit in the last printed place of a numeric string."""
    mantissa, _, exponent = text.lower().partition("e")
    decimals = len(mantissa.split(".", 1)[1]) if "." in mantissa else 0
    return 10.0 ** (int(exponent or 0) - decimals)


class Diff:
    def __init__(self, path):
        self.path, self.cells, self.max_rel, self.max_abs = path, 0, 0.0, 0.0
        self.problems = []

    def number(self, a, b, a_text=None, b_text=None, rtol=0.0, atol=0.0):
        if a == b or (math.isnan(a) and math.isnan(b)):
            return
        self.cells += 1
        if math.isinf(a) or math.isinf(b) or math.isnan(a) or math.isnan(b):
            self.problems.append("non-finite %r vs %r" % (a, b))
            return
        d = abs(a - b)
        scale = max(abs(a), abs(b))
        self.max_abs = max(self.max_abs, d)
        if scale:
            self.max_rel = max(self.max_rel, d / scale)
        allowed = atol + rtol * scale
        if a_text is not None:
            allowed = max(allowed, printed_ulp(a_text), printed_ulp(b_text))
        # The slack is for the subtraction itself: two values one printed unit apart differ
        # by 1.00000000003e-08 in binary, not 1e-08 (run 38974615431 failed three cells so).
        if d > allowed * (1 + 1e-6):
            self.problems.append("%r vs %r (|d| %.3g > %.3g)" % (a_text or a, b_text or b,
                                                                   d, allowed))


def text_cells(diff, a, b, where, rtol, atol):
    if a == b:
        return
    if NUMBER.match(a.strip()) and NUMBER.match(b.strip()):
        diff.number(float(a), float(b), a.strip(), b.strip(), rtol, atol)
    else:
        diff.problems.append("%s: %r vs %r" % (where, a[:60], b[:60]))


def compare_csv(diff, old, new, rtol, atol):
    def split(raw):
        lines = raw.decode("utf-8").splitlines(keepends=True)
        comments = [l for l in lines if l.startswith("#")]
        body = list(csv.reader(io.StringIO("".join(l for l in lines if not l.startswith("#")))))
        return comments, body
    c_old, b_old = split(old)
    c_new, b_new = split(new)
    if c_old != c_new:
        diff.problems.append("comment/banner lines differ")
    if len(b_old) != len(b_new):
        diff.problems.append("%d rows vs %d" % (len(b_old), len(b_new)))
        return
    header = b_old[0] if b_old else []
    if b_old and b_old[0] != b_new[0]:
        diff.problems.append("header differs")
        return
    digest_cols = {j for j, name in enumerate(header) if DIGEST_KEY.search(name)}
    for i, (r_old, r_new) in enumerate(zip(b_old, b_new)):
        if len(r_old) != len(r_new):
            diff.problems.append("row %d: %d cells vs %d" % (i, len(r_old), len(r_new)))
            continue
        for j, (a, b) in enumerate(zip(r_old, r_new)):
            if j in digest_cols and a != b:
                diff.digests = getattr(diff, "digests", 0) + 1
                continue
            text_cells(diff, a, b, "row %d col %d" % (i, j), rtol, atol)


def compare_json_value(diff, a, b, where, rtol, atol):
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            diff.problems.append("%s: keys differ" % where)
        for k in sorted(set(a) & set(b)):
            if DIGEST_KEY.search(k) and a[k] != b[k]:
                diff.digests = getattr(diff, "digests", 0) + 1
                continue
            compare_json_value(diff, a[k], b[k], "%s.%s" % (where, k), rtol, atol)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diff.problems.append("%s: %d items vs %d" % (where, len(a), len(b)))
        for i, (x, y) in enumerate(zip(a, b)):
            compare_json_value(diff, x, y, "%s[%d]" % (where, i), rtol, atol)
    elif isinstance(a, bool) or isinstance(b, bool):
        if a != b:
            diff.problems.append("%s: %r vs %r" % (where, a, b))
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)):
        diff.number(float(a), float(b), repr(a), repr(b), rtol, atol)
    elif isinstance(a, str) and isinstance(b, str):
        text_cells(diff, a, b, where, rtol, atol)
    elif a != b:
        diff.problems.append("%s: %r vs %r" % (where, a, b))


def compare_frames(diff, old, new, rtol, atol):
    import numpy as np
    if list(old.columns) != list(new.columns) or len(old) != len(new):
        diff.problems.append("shape or columns differ: %s vs %s" % (old.shape, new.shape))
        return
    for col in old.columns:
        a, b = old[col], new[col]
        if a.dtype.kind in "fiu" and b.dtype.kind in "fiu":
            x, y = a.to_numpy(dtype=float), b.to_numpy(dtype=float)
            both_nan = np.isnan(x) & np.isnan(y)
            d = np.where(both_nan, 0.0, np.abs(x - y))
            scale = np.maximum(np.abs(x), np.abs(y))
            moved = d > 0
            if moved.any():
                diff.cells += int(moved.sum())
                diff.max_abs = max(diff.max_abs, float(np.nanmax(d)))
                with np.errstate(divide="ignore", invalid="ignore"):
                    rel = np.where(scale > 0, d / scale, 0.0)
                diff.max_rel = max(diff.max_rel, float(np.nanmax(rel)))
                bad = d > (atol + rtol * scale) * (1 + 1e-12)
                if bad.any():
                    i = int(np.argmax(bad))
                    diff.problems.append("%s: %r vs %r beyond tolerance (%d cells)"
                                         % (col, x[i], y[i], int(bad.sum())))
        elif not a.equals(b):
            # The semantic tables keep numbers as decimal TEXT in Parquet, so a string
            # column takes the CSV cell rule, digests included.
            for i, (x, y) in enumerate(zip(a.tolist(), b.tolist())):
                if x == y:
                    continue
                if DIGEST_KEY.search(str(col)):
                    diff.digests = getattr(diff, "digests", 0) + 1
                elif isinstance(x, str) and isinstance(y, str):
                    text_cells(diff, x, y, "%s row %d" % (col, i), rtol, atol)
                else:
                    diff.problems.append("%s row %d: %r vs %r" % (col, i, x, y))


def compare_parquet(diff, old, new, rtol, atol):
    import pandas as pd
    compare_frames(diff, pd.read_parquet(io.BytesIO(old)), pd.read_parquet(io.BytesIO(new)),
                   rtol, atol)


def compare_netcdf(diff, old, new, rtol, atol):
    import numpy as np
    import xarray as xr
    with tempfile.TemporaryDirectory() as tmp:
        paths = []
        for name, raw in (("old.nc", old), ("new.nc", new)):
            p = os.path.join(tmp, name)
            with open(p, "wb") as handle:
                handle.write(raw)
            paths.append(p)
        with xr.open_dataset(paths[0]) as a, xr.open_dataset(paths[1]) as b:
            compare_json_value(diff, dict(a.attrs), dict(b.attrs), "attrs", rtol, atol)
            if set(a.variables) != set(b.variables):
                diff.problems.append("variables differ")
                return
            for name in sorted(a.variables):
                x, y = a[name].values, b[name].values
                if x.shape != y.shape:
                    diff.problems.append("%s: shape %s vs %s" % (name, x.shape, y.shape))
                elif x.dtype.kind in "fiu":
                    x, y = x.astype(float), y.astype(float)
                    d = np.where(np.isnan(x) & np.isnan(y), 0.0, np.abs(x - y))
                    scale = np.maximum(np.abs(x), np.abs(y))
                    if (d > 0).any():
                        diff.cells += int((d > 0).sum())
                        diff.max_abs = max(diff.max_abs, float(np.nanmax(d)))
                        with np.errstate(divide="ignore", invalid="ignore"):
                            diff.max_rel = max(diff.max_rel, float(np.nanmax(
                                np.where(scale > 0, d / scale, 0.0))))
                        bad = d > (atol + rtol * scale) * (1 + 1e-12)
                        if bad.any():
                            diff.problems.append("%s: %d cells beyond tolerance"
                                                 % (name, int(bad.sum())))
                elif not np.array_equal(x, y):
                    diff.problems.append("%s: values differ" % name)
                compare_json_value(diff, dict(a[name].attrs), dict(b[name].attrs),
                                   "%s.attrs" % name, rtol, atol)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--paths", nargs="+", default=["outputs", "data"])
    parser.add_argument("--rtol", type=float, default=1e-9)
    parser.add_argument("--atol", type=float, default=1e-12)
    args = parser.parse_args(argv)
    failed, not_compared, within = [], [], []
    for status, path in changed(args.paths):
        diff = Diff(path)
        if status.strip() in ("??", "A", "D") or "D" in status:
            failed.append((path, ["added or removed (%s)" % status.strip()]))
            continue
        old = git("show", "HEAD:%s" % path, binary=True)
        with open(os.path.join(ROOT, path), "rb") as handle:
            new = handle.read()
        if old == new:
            continue
        suffix = os.path.splitext(path)[1].lower()
        try:
            if suffix in RASTER:
                not_compared.append(path)
                continue
            if suffix == ".csv":
                compare_csv(diff, old, new, args.rtol, args.atol)
            elif suffix == ".json":
                compare_json_value(diff, json.loads(old), json.loads(new), "$", args.rtol,
                                   args.atol)
            elif suffix == ".parquet":
                compare_parquet(diff, old, new, args.rtol, args.atol)
            elif suffix == ".nc":
                compare_netcdf(diff, old, new, args.rtol, args.atol)
            else:
                diff.problems.append("differs, and %s files are not compared numerically"
                                     % (suffix or "extension-less"))
        except Exception as error:                      # an unreadable product fails, loudly
            diff.problems.append("could not compare: %s" % error)
        (failed if diff.problems else within).append(
            (path, diff.problems) if diff.problems else (path, diff))
    print("Rebuilt products against HEAD (rtol %g, atol %g, or one printed last place)"
          % (args.rtol, args.atol))
    for path, diff in within:
        print("  WITHIN      %-62s %7d cells moved, max rel %.2e, max abs %.2e%s"
              % (path, diff.cells, diff.max_rel, diff.max_abs,
                 ", %d digest(s) of compared files" % diff.digests
                 if getattr(diff, "digests", 0) else ""))
    for path in not_compared:
        print("  NOT COMPARED %s (rasterised figure; not comparable across platforms)" % path)
    for path, problems in failed:
        print("  DIFFERS     %s" % path)
        for line in problems[:5]:
            print("      %s" % line)
        if len(problems) > 5:
            print("      ... %d more" % (len(problems) - 5))
    print("%d within tolerance, %d not compared, %d differ"
          % (len(within), len(not_compared), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
