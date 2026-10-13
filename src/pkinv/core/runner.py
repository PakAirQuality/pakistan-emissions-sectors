"""The sector-runner contract: every write recorded, every check written down.

WHY. The engine contract (core/registry.py + tests/test_sector_contract.py)
made the ten sector ENGINES uniform; the ten RUNNERS stayed hand-rolled -
twelve near-identical write helpers across four incompatible signatures, two
private written-files ledgers (ippu's `generated`, fugitives' `_WRITTEN`),
three QA-table schemas, and seven runners with no gates at all. Worse, the
one runner that both gated and shipped a QA table raised BEFORE writing it,
so a red build kept the previous run's green table on disk - the exact
stale-QA class tests/test_sector_qa_checks.py was written about.

THE CONTRACT. A runner builds one `Runner`, routes every CSV through
`write()`/`write_dicts()`, registers out-of-band files with `record()`,
states its checks with `gate()`, and ends with `finalize()`, which

  1. appends the automatic "declared outputs written" gate (the runner's
     `declared` names against what was actually written this run),
  2. WRITES the QA table - outputs/<sector>_qa_<year>.csv on the ONE schema
     `check, passed, actual, expected, note` (fugitives' schema, the donor) -
  3. and only THEN raises if any gate failed.

Write-then-raise is the point: the shipped table always describes this run,
red or green. Aborts that must stop before later writes stay plain raises.

BYTE-IDENTITY. `write()` keeps `csv.writer` over LIST rows verbatim (the
eight-clone family), including the line terminator the caller pins - aviation
ships "\n", everyone else csv's default "\r\n". List-rows are NOT converted
to core.io dict-rows here; that convergence is the Wave-C sweep, per io.py's
own docstring. `write_dicts` delegates to core.io.write_table with the
first-seen field inference and extrasaction="ignore" its ippu/fugitives
ancestors used.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import io
from pkinv.paths import OUTPUTS

# The one QA schema. `passed` is a stringified bool; a warning is a real
# third state and lives in test_sector_qa_checks.DECLARED_WARNINGS as
# passed=False plus a named reason, never as a column value.
QA_FIELDS = ("check", "passed", "actual", "expected", "note")


def _first_seen_fields(rows):
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields


class Runner:
    """Per-run state for one sector runner: ledgers and gate rows."""

    def __init__(self, sector, declared=(), lineterminator="\r\n"):
        self.sector = sector
        self.declared = tuple(declared)
        self.lineterminator = lineterminator
        self.written = []   # output NAMES, in write order (fugitives' _WRITTEN)
        self.paths = []     # full paths, in write order (ippu's `generated`)
        self.checks = []    # gate rows, in call order

    def _record(self, name, path):
        self.written.append(name)
        self.paths.append(path)

    def write(self, name, header, rows, banner=None):
        """csv.writer over LIST rows - byte-identical to the eight clones.

        `banner` is optional and omitted by default, so every existing caller writes the
        same bytes it always did. It exists because a product can be read for something
        it cannot support: the Climate TRACE plant comparison ships per-plant ratios
        while its comparator applies ONE intensity per fuel class, and a reader had no
        way to see that from the file.
        """
        path = asset_path(OUTPUTS, name)
        with open(path, "w", newline="", encoding="utf-8") as handle:
            for line in banner or []:
                handle.write("# %s%s" % (line, self.lineterminator))
            writer = csv.writer(handle, lineterminator=self.lineterminator)
            writer.writerow(header)
            writer.writerows(rows)
        self._record(name, path)
        return path

    def write_dicts(self, name, rows, fields=None):
        """DictWriter with first-seen field inference, extra keys ignored."""
        rows = list(rows)
        if fields is None:
            fields = _first_seen_fields(rows)
        path = io.write_table(asset_path(OUTPUTS, name), fields, rows,
                              extrasaction="ignore",
                              lineterminator=self.lineterminator)
        self._record(name, path)
        return path

    def record(self, path):
        """Register a file written by machinery outside this object (a monthly
        layer, a screening module's OUT, a .md report), so the ledgers and the
        declared-outputs gate stay complete."""
        full = path if os.path.isabs(path) else asset_path(OUTPUTS, path)
        self._record(os.path.basename(full), full)
        return full

    def gate(self, check, passed, actual="", expected="", note=""):
        self.checks.append({"check": check, "passed": bool(passed),
                            "actual": actual, "expected": expected,
                            "note": note})
        return bool(passed)

    def finalize(self, qa_table=None, tolerated=()):
        """Standard gate, WRITE the QA table, THEN raise on any failure.

        `tolerated` names checks that may fail without aborting the run - a
        warning that is TRUE and known (aviation's one aerodrome with no
        coordinate). The table still records them as passed=False; the guard's
        DECLARED_WARNINGS ratchet must then carry each one with a reason, in
        both directions, so a tolerance here cannot outlive its explanation."""
        missing = sorted(set(self.declared) - set(self.written))
        self.gate(
            "declared outputs written", not missing,
            actual=len(set(self.written) & set(self.declared)),
            expected=len(self.declared),
            note=("every output this runner declares was written by this run"
                  if not missing else "missing: %s" % ", ".join(missing)))
        if qa_table:
            self.write_dicts(qa_table, self.checks, fields=list(QA_FIELDS))
        failing = [r for r in self.checks
                   if not r["passed"] and r["check"] not in tolerated]
        if failing:
            raise AssertionError("%s QA failed: %s" % (self.sector, failing))
        return self.checks
