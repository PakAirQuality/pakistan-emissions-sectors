"""The validation catalogue regrouped by what each comparison can establish.

WHY. The catalogue counts 103 entries, and a count of entries is not a count of
validations: a declared absence, a calibration and an accounting identity are catalogue
rows too. This module files every entry under one of five classes, by a rule on the
catalogue's own `role` and `independence_class` columns, and prints the counts the
supplement's table carries, so the table is a product and not a transcription.

The rule, in order:
  role declared-absence                      -> declared absence (no check performed)
  role calibration                           -> calibration (fitted to the comparator; cannot validate it)
  independence not-applicable, role corroboration -> not a comparison
  independence independent-compilation       -> independent compilation (another inventory; not an observation)
  independence internal-consistency/-identity -> internal consistency / accounting identity
  independence none or shared-upstream       -> shares activity or factors with the estimate
  independence partial or large              -> partially independent benchmark
Anything else RAISES: a new vocabulary value must be classified, not defaulted.

Usage:  python3 -m pkinv.report.validation_five_classes
Writes: outputs/pakemis_validation_five_classes.csv          one row per catalogue entry
        outputs/pakemis_validation_five_classes_summary.csv  one row per class
"""
import csv
import io
import os

from pkinv.core.io import write_table
from pkinv.paths import OUTPUTS

CATALOG = os.path.join(OUTPUTS, "pakemis_validation_catalog.csv")
OUT = os.path.join(OUTPUTS, "pakemis_validation_five_classes.csv")
SUMMARY = os.path.join(OUTPUTS, "pakemis_validation_five_classes_summary.csv")
CLASSES = ("partially independent benchmark",
           "independent compilation (another inventory; not an observation of emissions)",
           "calibration (fitted to the comparator; cannot validate it)",
           "shares activity or factors with the estimate",
           "internal consistency / accounting identity",
           "declared absence (no check performed)",
           "not a comparison")
FIELDS = ("validation_id", "role", "independence_class", "five_class", "what_it_can_establish")
CAN = {CLASSES[0]: "agreement or disagreement with a comparator that shares some inputs",
       CLASSES[1]: "agreement with another compilation; not accuracy against observations",
       CLASSES[2]: "nothing about the estimate it was fitted to",
       CLASSES[3]: "consistency of shared inputs, not independent confirmation",
       CLASSES[4]: "that the products agree with each other",
       CLASSES[5]: "nothing: the check was not performed",
       CLASSES[6]: "nothing: not a comparison"}


def classify(role, independence):
    if role == "declared-absence":
        return CLASSES[5]
    if role == "calibration":
        return CLASSES[2]
    if independence == "not-applicable" and role == "corroboration":
        return CLASSES[6]
    if independence == "independent-compilation":
        return CLASSES[1]
    if independence in ("internal-consistency", "internal-identity"):
        return CLASSES[4]
    if independence in ("none", "shared-upstream"):
        return CLASSES[3]
    if independence in ("partial", "large"):
        return CLASSES[0]
    raise SystemExit("unclassified catalogue entry: role=%r independence=%r" % (role, independence))


def build():
    with io.open(CATALOG, encoding="utf-8") as handle:
        rows = list(csv.DictReader(line for line in handle if not line.startswith("#")))
    out = []
    for r in rows:
        role = r.get("calibration_or_validation") or r.get("role") or ""
        c = classify(role, r["independence_class"])
        out.append({"validation_id": r["validation_id"], "role": role,
                    "independence_class": r["independence_class"], "five_class": c,
                    "what_it_can_establish": CAN[c]})
    counts = {c: sum(1 for r in out if r["five_class"] == c) for c in CLASSES}
    summary = [{"five_class": c, "entries": counts[c], "what_it_can_establish": CAN[c]} for c in CLASSES]
    summary.append({"five_class": "TOTAL", "entries": len(out), "what_it_can_establish": "catalogue entries"})
    return out, summary


def main():
    out, summary = build()
    write_table(OUT, FIELDS, out, banner=(
        "# Every validation-catalogue entry filed under what the comparison can establish.",
        "# Rule in pkinv/report/validation_five_classes.py; the catalogue is the only input.",))
    write_table(SUMMARY, ("five_class", "entries", "what_it_can_establish"), summary, banner=(
        "# Counts of pakemis_validation_five_classes.csv by class.",))
    print("validation_five_classes: " + ", ".join("%s %d" % (s["five_class"][:28], s["entries"]) for s in summary))


if __name__ == "__main__":
    main()
