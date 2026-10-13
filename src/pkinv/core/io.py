"""The one CSV reader and the one CSV writer.

WHY. The repository grew ~145 near-identical local `_rows()` readers in TWO
incompatible conventions - 102 clones that read a file raw, and 131 inline
`startswith("#")` filters that honour the comment-banner convention - plus
FOUR incompatible `_write()` signatures across the sector runners. Which
convention a module follows depends on which neighbour it was copied from,
and a file that gains a comment banner breaks every raw reader silently
(test_grid_cube and two spatial-contract readers broke on the same day for
exactly this, and the ADM2 view's comment says so). core/manifest.py already
consolidated the hashing helpers under the same argument; this module is the
same consolidation for tabular io.

THE CONTRACT.

  read_rows(path, comments=True)      -> list[dict]
      utf-8, newline="", DictReader; lines starting with "#" are banner
      commentary and are skipped by default (comments=False reads them as
      data for the rare file where "#" is content).

  write_table(path, fieldnames, rows, banner=None)
      DictWriter with an optional banner: an iterable of strings written as
      "# ..." lines above the header. NEVER writes a timestamp - byte-identical
      regeneration is a release property (the fixpoint, the clean-room gate and
      three regenerates-identically tests depend on it), so nondeterminism here
      is a defect, not a nicety.

Adoption is incremental by design: new code uses this module exclusively;
existing clones migrate in declared batches (the Wave-C sweep), each batch
asserting byte-identical outputs, because a mass rewrite that changed one
banner byte would light up the manifest guards for reasons nobody could read.
"""
import csv
import io
import os
from pkinv.assets import resolve


class MalformedRow(ValueError):
    """A CSV row whose field count differs from its header's."""


def read_rows(path, comments=True, strict=True):
    """Every data row of a CSV, as dicts; '#' banner lines skipped by default.

    rc41 (the nineteenth review's D-1/D-2): STRICT by default. csv.DictReader tolerates a
    row with surplus fields (they land under the key None) or too few (missing columns
    become None), and ten committed payloads shipped that way for releases - an unquoted
    comma in a note, a source with a parenthesis list - with every reader silently
    truncating the field. A row whose field count differs from the header's raises
    MalformedRow naming the file and the row; strict=False is for a caller that inspects
    a file it knows to be irregular.
    """
    path = resolve(path)
    with open(path, newline="", encoding="utf-8") as handle:
        lines = [line for line in handle if not (comments and line.startswith("#"))]
    reader = csv.DictReader(lines)
    rows = []
    for index, row in enumerate(reader, 2):
        if strict and (None in row or any(v is None for v in row.values())):
            raise MalformedRow("%s row %d: %d fields against a %d-column header"
                               % (path, index, len(row) - (1 if None in row else 0)
                                  + (len(row[None]) if None in row else 0)
                                  - sum(v is None for v in row.values()),
                                  len(reader.fieldnames or [])))
        rows.append(row)
    return rows


def write_table(path, fieldnames, rows, banner=None, extrasaction="raise",
                lineterminator="\r\n"):
    """Write rows under an optional '#' banner. No timestamps, ever.

    extrasaction and lineterminator are passed to DictWriter; the defaults are
    csv's own, so existing callers are byte-unchanged. "ignore" exists for the
    runner harness (its ippu/fugitives ancestors dropped extra keys) and the
    terminator for the aviation modules, which pin "\n".
    """
    path = resolve(path)
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        handle.write(table_text(fieldnames, rows, banner, extrasaction, lineterminator))
    return path


def table_text(fieldnames, rows, banner=None, extrasaction="raise",
               lineterminator="\r\n"):
    """Exactly what write_table would put in the file, as a string.

    Split out so write_table and write_or_check emit through ONE code path: a
    re-derivation check is only worth anything if the text it compares against is
    produced by the same writer that wrote the file.
    """
    buf = io.StringIO(newline="")
    for line in banner or ():
        buf.write("# %s\n" % line if not line.startswith("#") else line + "\n")
    writer = csv.DictWriter(buf, fieldnames=list(fieldnames),
                            extrasaction=extrasaction, lineterminator=lineterminator)
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def write_or_check(path, fieldnames, rows, check=False, banner=None,
                   extrasaction="raise", lineterminator="\r\n"):
    """Write the table, or with check=True re-derive it and report any difference.

    The contract the sector passes rely on: an ingest that reads a held document can be
    re-run at any time and must reproduce the file it committed. NOTHING IS REWRITTEN
    under check - a producer that stops reproducing its own output is a finding for a
    person, because the document, the parser or the committed file may each be the one
    that moved. Returns 0 when they agree, 1 when they do not, so a caller can
    `return write_or_check(...)` straight out of main().
    """
    path = resolve(path)
    text = table_text(fieldnames, rows, banner, extrasaction, lineterminator)
    if not check:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            handle.write(text)
        return 0
    held = (open(path, newline="", encoding="utf-8").read()
            if os.path.exists(path) else "")
    if held == text:
        return 0
    print("%s does not reproduce from the held document; re-run this script without "
          "--check to see the new content, and treat the difference as a finding"
          % os.path.basename(path))
    return 1


def seq_sum(values):
    """Left-to-right IEEE accumulation: the sum the published series were cut with.

    rc42 (the twentieth review's reproduction finding). CPython 3.12 changed the built-in
    `sum()` of floats to Neumaier compensated summation. Both answers are correct to the
    last bit or so, but they are not the same bits, and a published cell that sits on an
    exact half-way tie at its printed precision - agriculture FY2022-23 at five decimals,
    208.5645650... - rounds one way under 3.11 and the other under 3.12+. The reviewer's
    rerun on a newer interpreter then failed the ensemble's closure gate by one unit in the
    last digit. Every product the release hashes was cut with sequential accumulation, so
    the writers that feed a rounded, published cell accumulate sequentially by name - not
    with `sum()`, whose semantics are the interpreter's to change, and not with `math.fsum`,
    which moves the same cell the other way.
    """
    total = 0.0
    for value in values:
        total += value
    return total
