"""Compare-only runs for producers that otherwise overwrite what they check.

WHY THIS EXISTS. Eight hand-run validation products (data/catalog/held_products.csv) had no
check a reader could run. Five could only be "verified" by running the producer, which
overwrites the committed file with whatever it computes: after that there is nothing left to
compare against, so a changed result is indistinguishable from an unchanged one. Three had no
instruction at all. The manuscript said so: "some held validation products have only partial
re-derivation checks".

compare_only() runs a producer's own main() with its output paths pointed at a temporary
directory, then compares each file it wrote with the committed one, byte for byte. Nothing
in the tree is written. It prints one `checked: <path>` line per product that matched, which
is the line tests/test_held_product_freshness.py holds a `checks` row to, and returns
non-zero on any difference, naming the first lines that differ.

It works on the module's path CONSTANTS because that is how every one of these producers
names its outputs. A producer that writes a file through any other name would write into the
tree during a check; `outputs` must therefore list every constant the producer opens for
writing, and tests/test_validation_checks.py reads each producer's source to hold it to that.
"""
import os
import shutil
import tempfile

from pkinv.paths import ROOT


def _first_differences(old, new, limit=6):
    try:
        a = old.decode("utf-8").splitlines()
        b = new.decode("utf-8").splitlines()
    except UnicodeDecodeError:
        return ["binary contents differ (%d bytes committed, %d re-derived)"
                % (len(old), len(new))]
    out = []
    if len(a) != len(b):
        out.append("%d lines committed, %d re-derived" % (len(a), len(b)))
    wrong = [i for i in range(min(len(a), len(b))) if a[i] != b[i]]
    for i in wrong[:limit]:
        out.append("line %d: committed %r | re-derived %r" % (i + 1, a[i][:150], b[i][:150]))
    if len(wrong) > limit:
        out.append("... and %d more differing lines" % (len(wrong) - limit))
    return out or ["the files differ only in line endings"]


def compare_only(namespace, outputs, produce, seed=()):
    """Run `produce()` with the path constants named in `outputs` redirected to a temporary
    directory, compare what it wrote with the committed files, and return an exit code.

    namespace  the producer module's globals()
    outputs    names of every module-level path constant the producer opens for writing
    seed       the subset a producer READS before it rewrites (a table it extends in place);
               the committed file is copied to the temporary path first so the run starts
               from the same state a real run would
    """
    committed = {name: namespace[name] for name in outputs}
    scratch = tempfile.mkdtemp(prefix="pkinv_check_")
    try:
        for index, name in enumerate(outputs):
            namespace[name] = os.path.join(scratch, "%02d_%s" % (
                index, os.path.basename(committed[name])))
            if name in seed and os.path.exists(committed[name]):
                shutil.copyfile(committed[name], namespace[name])
        produce()
        worst = 0
        for name in outputs:
            real, fresh = committed[name], namespace[name]
            relative = os.path.relpath(real, ROOT)
            if not os.path.exists(fresh) and not os.path.exists(real):
                continue            # a file written only when there is something to report
            if not os.path.exists(fresh):
                print("DIFFERS: %s is committed and this run did not write it" % relative)
                worst = 1
                continue
            if not os.path.exists(real):
                print("DIFFERS: this run wrote %s and no committed copy exists" % relative)
                worst = 1
                continue
            with open(real, "rb") as handle:
                old = handle.read()
            with open(fresh, "rb") as handle:
                new = handle.read()
            if old == new:
                print("checked: %s" % relative)
            else:
                print("DIFFERS: %s" % relative)
                for line in _first_differences(old, new):
                    print("  %s" % line)
                worst = 1
        return worst
    finally:
        for name in outputs:
            namespace[name] = committed[name]
        shutil.rmtree(scratch, ignore_errors=True)
