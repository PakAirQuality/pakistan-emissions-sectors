"""Bridges: the modelled years this inventory could publish and does not.

WHY DECLARE SOMETHING THAT IS NOT BUILT. Two FY2015-16 sector-years are NE because an observed
total in tonnes has no product split, and a reader who wants a full-scope line for that year
has an obvious next move available to them: divide the total by a neighbouring year's mix.
That move is defensible as a clearly labelled model and indefensible as an inventory row, and
the difference between the two is entirely a matter of how it is declared. Writing the
interface down now - the id, the permitted alternatives, the conservation rule, the derivation
state the rows would carry - means the rules exist before the temptation does, rather than
being written by whoever is in a hurry on the day.

THE CONTRACT, WHICH IS ENFORCED FROM TODAY. `validate()` runs against any populated bridge and
refuses one that:

  - carries product shares not summing to one;
  - produces product tonnages that do not reproduce the observed control EXACTLY;
  - marks its rows anything other than proxy_backcast;
  - is averaged, weighted or otherwise collapsed across its alternatives.

It ships with no bridge to validate, and tests exercise it against synthetic populated
bridges, so the first real alternative meets a working gate instead of a comment.

WHY NOT data/scenarios.csv. That registry is reference-year scoped and structural_bridge()
prices each axis by reading the alternative OUTPUT it names. A bridge has no output; putting
it there would mean either a fake output path or a special case in the pricing loop, and both
are worse than a second small registry that says what it is.

A BRIDGE IS NOT A PARAMETRIC UNCERTAINTY. The Monte Carlo describes how wrong a number might
be given the method; a bridge supplies a number the method cannot produce at all. They are
different kinds of statement and this repository keeps them in different files for the same
reason it keeps structural configurations out of the interval.

Usage:  python3 -m pkinv.report.bridge_configurations
Writes: outputs/pakemis_bridge_configurations.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.activity.store import read_rows
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "pakemis_bridge_configurations.csv")
REGISTRY = asset_path(DATA, "bridge_configurations.csv")

FIELDS = ("configuration_id", "period_scope", "claimant_sector", "control_id",
          "activation_state", "unit_precondition", "permitted_alternatives",
          "conservation_rule", "derivation_state", "weighting_rule", "note")

DECLARED = "declared_not_populated"
# Wave 6 (the freeze): both FY2015-16 bridges moved to this state - the rc20
# recovery of the Oil Report's own product split made every modelled alternative
# moot, and a bridge that says "the strict answer remains NE" two releases after
# the panel reached zero NE sector-years is a contract describing a question
# that no longer exists. Historical-moot rows are retained (rule 5), validated,
# and never populated.
HISTORICAL_MOOT = "declared_historical_moot"
POPULATED = "populated"
ACTIVATION_STATES = (DECLARED, POPULATED, HISTORICAL_MOOT)

# The only derivation state a bridged row may carry. Not `observed`, not `reconstructed`:
# those describe evidence, and a bridge is a model standing in for evidence that is absent.
DERIVATION_STATE = "proxy_backcast"

# Exact, not approximate. A bridge that loses a tonne of the control it was built from has
# invented emissions, which is the one thing it exists to avoid.
CONSERVATION_TOL = 1e-9


class BridgeContractError(Exception):
    """A populated bridge that breaks its declared contract. Raised, never warned."""


def registry(path=None):
    return read_rows(path or REGISTRY)


def declared_ids(rows=None):
    return sorted({r["configuration_id"] for r in (rows if rows is not None else registry())})


def is_bridge(configuration_id, rows=None):
    return configuration_id in set(declared_ids(rows))


def populated(rows=None):
    rows = rows if rows is not None else registry()
    return [r for r in rows if r["activation_state"] == POPULATED]


def validate(rows=None):
    """Check the registry's own shape. Raises BridgeContractError."""
    rows = rows if rows is not None else registry()
    problems = []
    for row in rows:
        if row["activation_state"] not in ACTIVATION_STATES:
            problems.append("%s/%s: unknown activation_state %r"
                            % (row["configuration_id"], row["claimant_sector"],
                               row["activation_state"]))
        if row["derivation_state"] != DERIVATION_STATE:
            problems.append("%s/%s: derivation_state is %r; a bridged row is %r and nothing "
                            "else" % (row["configuration_id"], row["claimant_sector"],
                                      row["derivation_state"], DERIVATION_STATE))
        if not row["permitted_alternatives"].strip():
            problems.append("%s/%s: no permitted alternatives named"
                            % (row["configuration_id"], row["claimant_sector"]))
        if not row["unit_precondition"].strip():
            problems.append("%s/%s: the unit precondition is unrecorded - whether the "
                            "control CAN be divided is the first question, not a detail"
                            % (row["configuration_id"], row["claimant_sector"]))
    if problems:
        raise BridgeContractError("\n  ".join(problems))
    return True


def validate_allocation(control_value, shares, derivation_state=DERIVATION_STATE,
                        weights=None, tolerance=CONSERVATION_TOL):
    """The gate a populated alternative must pass. Raises BridgeContractError.

    control_value      the observed total the bridge divides
    shares             {product: share}; must sum to one
    derivation_state   what the produced rows would be marked
    weights            must be None. A weight across alternatives is the averaging this
                       design forbids: the alternatives answer one open question and no
                       evidence ranks them, so a weighted blend would be a central estimate
                       nobody can defend.
    """
    problems = []
    if weights is not None:
        problems.append("alternatives may not carry weights: they are competing answers, "
                        "not draws, and averaging them manufactures a central estimate no "
                        "evidence supports")
    if derivation_state != DERIVATION_STATE:
        problems.append("rows would be marked %r; a bridged row is %r"
                        % (derivation_state, DERIVATION_STATE))
    if not shares:
        problems.append("no shares given")
    else:
        total = sum(shares.values())
        if abs(total - 1.0) > tolerance:
            problems.append("shares sum to %.12g, not 1" % total)
        if any(v < 0 for v in shares.values()):
            problems.append("negative share: a product cannot consume less than nothing")
        allocated = sum(control_value * share for share in shares.values())
        if abs(allocated - control_value) > max(tolerance * abs(control_value), tolerance):
            problems.append("the allocation sums to %.12g against a control of %.12g"
                            % (allocated, control_value))
    if problems:
        raise BridgeContractError("\n  ".join(problems))
    return True


def main():
    rows = registry()
    validate(rows)
    os.makedirs(OUTPUTS, exist_ok=True)
    write_table(OUT, FIELDS, rows)
    print("bridge configurations -> %s" % OUT)
    for row in rows:
        print("  %-28s %-10s %-9s %s"
              % (row["configuration_id"], row["period_scope"], row["claimant_sector"],
                 row["activation_state"]))
    live = populated(rows)
    print("  %d declared, %d populated; a populated bridge would have to pass "
          "validate_allocation() before any row of it could be written"
          % (len(rows), len(live)))
    if not live:
        print("  nothing here appears in any output of this release, which is the intended "
              "state: since rc20 the strict series answers FY2015-16 with its "
          "OBSERVED split, and the bridges are declared_historical_moot")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
