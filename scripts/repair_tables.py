"""Auto-repair the manuscripts' registered TABLES against the engine.

The companion of scripts/repair_claims.py for the TABLES registry
(tests/paper_numbers/tables.py): for every registered table whose printed
numeric cells disagree with the engine's rows beyond half an ulp at the
printed precision - the test's own rule - rewrite the disagreeing cells in
the .tex at the printed number of decimals. Cells are located exactly as
the test locates them (the same tabular parser, row by row, numeric cells
in order), so what this repairs is what test_registered_tables_match would
have failed. Row counts and cell counts that disagree are reported, never
repaired: a table with a different shape needs a person.

The printed value of a cell is what tests.paper_numbers.tables._cell_value
returns - the number with its LaTeX wrapping and its thousands separators
(`\\,` or `,`) removed. The first version of this script matched the FIRST
run of digits in the raw cell instead, so `3\\,144\\,392` was read as 3 and
"repaired" into `3144392\\,144\\,392` - 141 cells across fourteen files where
the test had flagged sixteen. The digits are now located as a span that may
carry separators between them, and the new value is written back in the
same separator style. A cell whose printed value cannot be found exactly
once in its raw text is reported as manual, never rewritten.

Usage:  python3 scripts/repair_tables.py            (dry run: lists every repair)
        python3 scripts/repair_tables.py --apply    (writes the .tex files)
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

from paper_numbers.tables import LABELLED_TABLES, TABLES, _cell_value, _label_text  # noqa: E402
from paper_numbers._common import _doc_path  # noqa: E402

RULE = re.compile(r"\\(top|mid|bottom)rule")


def _table_span(text, label):
    for m in re.finditer(r"\\begin\{table\*?\}.*?\\end\{table\*?\}", text, re.S):
        if "\\label{%s}" % label in m.group(0):
            body = re.search(r"\\begin\{tabular\}\{(?:[^{}]|\{[^{}]*\})*\}(.*?)\\end\{tabular\}",
                             m.group(0), re.S)          # a nested-brace column spec (rc42)
            if body:
                return m.start() + body.start(1), m.start() + body.end(1)
    return None


def _locate(cell, printed):
    """The (start, end, separator) of the printed number inside the raw cell.

    `printed` is _cell_value's output: an optional sign, digits, an optional
    decimal part, no separators. The raw cell may carry `\\,` or `,` between
    digit groups; a pattern that permits either between any two integer
    digits finds the span. None unless exactly one span matches.
    """
    sign, rest = (printed[0], printed[1:]) if printed[:1] in ("-", "+") else ("", printed)
    integer, _, decimals = rest.partition(".")
    pattern = re.escape(sign) + r"(?:\\,|,)?".join(re.escape(d) for d in integer)
    if decimals:
        pattern += r"\." + re.escape(decimals)
    pattern = r"(?<![\d.])" + pattern + r"(?![\d.])"
    hits = list(re.finditer(pattern, cell))
    if len(hits) != 1:
        return None
    m = hits[0]
    span = m.group(0)
    sep = "\\," if "\\," in span else ("," if "," in span else "")
    return m.start(), m.end(), sep


def _format(value, decimals, sep, plus=False):
    """`plus`: the printed cell carried an explicit + (a signed reallocation column), which a
    non-negative replacement keeps."""
    s = ("%%.%df" % decimals) % value
    if plus and not s.startswith("-"):
        s = "+" + s
    if not sep:
        return s
    sign, rest = ("-", s[1:]) if s.startswith("-") else ("", s)
    integer, _, frac = rest.partition(".")
    groups = []
    while len(integer) > 3:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    groups.insert(0, integer)
    return sign + sep.join(groups) + ("." + frac if frac else "")


def repair(apply=False):
    fixed, reported = [], []
    # rc42 (M-7): the label-aware registry is repaired too - a labelled table's expected rows
    # are joined to the printed rows BY LABEL (first unclaimed row a label matches, as the
    # comparator does) and the values beside each matched label are repaired in place.
    registry = [(entry, False) for entry in TABLES] + [(entry, True) for entry in LABELLED_TABLES]
    for (doc, section, label, expected_fn), labelled in registry:
        path = _doc_path(doc, section)
        if not os.path.exists(path):
            continue
        text = open(path, encoding="utf-8").read()
        span = _table_span(text, label)
        if span is None:
            continue
        start, end = span
        # a LaTeX comment is not a cell; blanked at equal length so positions survive (rc42)
        body = re.sub(r"(?<!\\)%.*", lambda m: " " * len(m.group(0)), text[start:end])
        expected = expected_fn()
        # the same walk as tests/paper_numbers/tables._tex_table, keeping positions
        rows, row_texts, pos = [], [], 0
        for chunk in body.split("\\\\"):
            chunk_start = pos
            pos += len(chunk) + 2
            cells, texts, cpos = [], [], chunk_start
            for cell in chunk.split("&"):
                printed = _cell_value(RULE.sub("", cell))
                if printed is not None:
                    cells.append((cpos, cell, printed))
                else:
                    texts.append(_label_text(RULE.sub("", cell)))
                cpos += len(cell) + 1
            if cells and RULE.sub("", chunk).strip():
                rows.append(cells)
                row_texts.append(texts)
        if labelled:
            # join by label, then fall through to the positional cell repair
            claimed, aligned_expected, aligned_rows = set(), [], []
            for name, want in expected:
                parts = name if isinstance(name, tuple) else (name,)
                hits = [i for i, texts in enumerate(row_texts)
                        if i not in claimed and len(texts) >= len(parts)
                        and all(texts[j].startswith(part) for j, part in enumerate(parts))]
                if not hits:
                    reported.append("%s: label %r matches no unclaimed printed row - not repaired"
                                    % (label, name))
                    continue
                claimed.add(hits[0])
                aligned_expected.append(want)
                aligned_rows.append(rows[hits[0]])
            if len(claimed) != len(rows):
                reported.append("%s: %d printed rows, %d claimed by label - the unclaimed are not repaired"
                                % (label, len(rows), len(claimed)))
            expected, rows = aligned_expected, aligned_rows
        if len(rows) != len(expected):
            reported.append("%s: %d rows printed, %d expected - not repaired"
                            % (label, len(rows), len(expected)))
            continue
        edits = []
        for i, (want, got) in enumerate(zip(expected, rows)):
            if len(want) != len(got):
                reported.append("%s row %d: %d cells printed, %d expected - not repaired"
                                % (label, i, len(got), len(want)))
                continue
            for w, (cell_start, cell, printed) in zip(want, got):
                decimals = len(printed.split(".")[1]) if "." in printed else 0
                if abs(float(printed) - w) <= 0.5 * 10 ** (-decimals) + 1e-9:
                    continue
                where = _locate(cell, printed)
                if where is None:
                    reported.append("%s row %d: printed %s wanted %s - manual (cell %r)"
                                    % (label, i, printed, w, cell.strip()))
                    continue
                a, b, sep = where
                new = _format(w, decimals, sep, plus=cell[a:b].startswith("+"))
                edits.append((start + cell_start + a, start + cell_start + b, new))
                fixed.append("%s/%s %s row %d: %s -> %s" % (doc, section, label, i,
                                                            cell[a:b], new))
        for a, b, new in sorted(edits, reverse=True):
            text = text[:a] + new + text[b:]
        if edits and apply:
            open(path, "w", encoding="utf-8").write(text)
    print("\n".join(fixed) if fixed else "nothing to repair")
    print(len(fixed), "cells", "repaired" if apply else "would be repaired (dry run; --apply to write)")
    if reported:
        print("NOT repaired:\n  " + "\n  ".join(reported))
    return fixed, reported


if __name__ == "__main__":
    repair(apply="--apply" in sys.argv)
