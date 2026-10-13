"""Auto-repair the manuscripts' registered numbers against the engine.

For every DOC_CLAIM whose printed value disagrees with its getter, rewrite
group(1) in the document to the getter's value at the PRINTED number of
decimals. The agreement rule is the test's own - an absolute tolerance plus
half an ulp at the printed precision - never a bare tolerance: an rc35 draft
that used the bare tolerance "repaired" hundreds of already-passing values
(13.2 -> 13.3, 99.11 -> 99.12) and orphaned their bare prose twins. A value
this script moves usually has unregistered twins elsewhere in the prose;
tests/paper_numbers/test_quantity_coverage.py names them.

Usage:  python3 scripts/repair_claims.py        (from the repo root; prints each repair)
"""
import os, re, sys
sys.path.insert(0, "tests")
from paper_numbers.doc_claims import DOC_CLAIMS
from paper_numbers._common import _doc_path
fixed, unresolved = [], []
for label, doc, section, pattern, getter, tol in DOC_CLAIMS:
    path = _doc_path(doc, section)
    if not os.path.exists(path): continue
    text = open(path, encoding="utf-8").read()
    m = re.search(pattern, text)
    if not m: continue
    printed = m.group(1)
    try: value = getter()
    except Exception as exc:
        continue
    try: pv = float(printed)
    except ValueError: continue
    decimals = len(printed.split(".")[1]) if "." in printed else 0
    # the test's own rule: an absolute tolerance plus half an ulp at the printed precision
    if abs(pv - float(value)) <= tol + 0.5 * 10 ** (-decimals) + 1e-9: continue
    new = ("%%.%df" % decimals) % float(value)
    text = text[:m.start(1)] + new + text[m.end(1):]
    open(path, "w", encoding="utf-8").write(text)
    fixed.append("%s/%s: %s -> %s" % (doc, label, printed, new))
print("\n".join(fixed) if fixed else "nothing to repair"); print(len(fixed), "repaired")
