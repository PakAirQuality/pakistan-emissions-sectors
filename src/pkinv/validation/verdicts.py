"""The one verdict vocabulary, and how the six legacy ones project onto it.

WHY. The repository's validation surface grew four lanes with SIX incompatible
verdict vocabularies (YES/REVIEW/not-comparable; scored/NO_RECORD;
True/False under three different column names; PASS/FAIL; agree/disagree and
its siblings; MET/MET_WITH_NAMED_EXCLUSIONS/REFUSED_TYPED_DATA_BLOCKED) plus
files with no verdict at all. A reader asking "what has been validated, and
did it pass?" needed to know per-file folklore. This module is the closed set
every NEW validation writes and every adapter maps INTO; the legacy files are
not rewritten - LEGACY_MAP is the documented projection, applied at read time
by the catalog's adapters.

THE SET. A verdict is a ROW PROPERTY, never an exception - the typed-refusal
convention extended to validation:

  pass             the instrument and the engine agree within the comparison's
                   own declared bound
  review           they disagree beyond the bound, or the comparison is
                   legitimate but its verdict needs a human reading
  fail             the comparison is decisive against the engine (rare by
                   design: most instruments cannot be decisive)
  no_record        the split/protocol exists but no truth record does
  by_construction  the "check" re-derives the engine's own arithmetic - a
                   conservation identity, not an instrument; it can catch a
                   defect but can never validate against the world
  declared_absent  no validation exists for this cell and the absence is the
                   registered fact (the scorecard's roadmap rows)
  refused_typed    running the validation was refused for a named reason
                   (data blocked, licence, wrong driver)
"""
PASS = "pass"
REVIEW = "review"
FAIL = "fail"
NO_RECORD = "no_record"
BY_CONSTRUCTION = "by_construction"
DECLARED_ABSENT = "declared_absent"
REFUSED_TYPED = "refused_typed"

ALL = (PASS, REVIEW, FAIL, NO_RECORD, BY_CONSTRUCTION, DECLARED_ABSENT,
       REFUSED_TYPED)

# How each legacy vocabulary projects. Keys are (as they appear in files);
# adapters consult this so the projection is one table, not per-adapter lore.
LEGACY_MAP = {
    # national/agriculture benchmark comparisons ("within_0.5_2.0x")
    "YES": PASS, "REVIEW": REVIEW, "not comparable": NO_RECORD, "n/a": NO_RECORD,
    # benchmark suite status
    "scored": PASS,          # scored = the metric exists; the metric itself is
                             # carried beside the verdict, never collapsed into it
    "NO_RECORD": NO_RECORD,
    "declared_unscorable": DECLARED_ABSENT,   # a block too small to score, said so
    # boolean columns named closes / passed / agrees
    "True": PASS, "False": FAIL, "true": PASS, "false": FAIL,
    # aviation QA
    "PASS": PASS, "FAIL": FAIL,
    # rice geography
    "agree": PASS, "disagree": REVIEW, "summary": None,   # summary rows are meta
    # grid provincial check
    "exact_by_construction": BY_CONSTRUCTION,
    "derived_from_grid": BY_CONSTRUCTION,
    "declared_divergence": REVIEW,
    "unallocated_below_adm1": NO_RECORD,
    # pass2 scorecard
    "MET": PASS, "MET_WITH_NAMED_EXCLUSIONS": REVIEW,
    "REFUSED_TYPED_DATA_BLOCKED": REFUSED_TYPED,
    # temporal profiles
    "crosschecked": PASS, "unvalidated": DECLARED_ABSENT,
}
