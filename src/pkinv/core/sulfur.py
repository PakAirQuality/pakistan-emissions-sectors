"""The sulfur balance for SO2 (rc58 W1).

    E_SO2 [kg] = 2 x M_fuel [kg] x s x f_oxidised x (1 - retention)

where s is the fuel's sulfur mass fraction from the DATED evidence register
(data/activity/industry/fuel_sulfur_evidence.csv), f_oxidised the fraction of fuel sulfur
released as SO2 (1.0 for boilers and engines; AP-42 assumes 100 percent conversion) and
retention the fraction held in ash, clinker or an alkaline charge (declared per class).

The register is the point of the module: the rc57 screening scaled every fuel's SO2 by the
POWER sector's Thar-lignite range, and the user's rule is the opposite - a regulatory maximum
is not a measured average, Thar lignite is not brick coal, and the year matters. evidence()
therefore resolves a class's evidence ids against the fiscal year and RAISES with a typed
reason when none is valid, so the caller writes an SO2 absence rather than a borrowed number.
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.core.uncertainty import product
from pkinv.paths import DATA

REGISTER = asset_path(DATA, "activity", "industry", "fuel_sulfur_evidence.csv")
BASES = ("measured_avg", "field_range", "regulatory_max", "declared_regime")
# WHAT WAS MEASURED IS NOT WHERE IT IS APPLIED, and conflating them is how a real measurement
# acquires an unearned "observed nationally" reading simply by being copied into this register.
# `basis` says what KIND of evidence the number is; `application` says whether it is being used on
# the population that was actually sampled. A transferred row must name the transfer.
APPLICATIONS = ("own_population", "transferred", "retired")


class NoSulfurEvidence(LookupError):
    pass


def load():
    rows = list(_activity_rows(REGISTER, comments=True))
    for r in rows:
        if r["basis"] not in BASES:
            raise ValueError("%s: basis %r" % (r["evidence_id"], r["basis"]))
        lo, c, hi = (float(r[k]) for k in ("s_pct_lo", "s_pct_central", "s_pct_hi"))
        if not lo <= c <= hi:
            raise ValueError("%s: central %.3f outside [%.3f, %.3f]" % (r["evidence_id"], c, lo, hi))
        if r.get("application") not in APPLICATIONS:
            raise ValueError("%s: application %r must be one of %s"
                             % (r["evidence_id"], r.get("application"), ", ".join(APPLICATIONS)))
        if r["application"] == "transferred" and not (r.get("transfer_basis") or "").strip():
            raise ValueError("%s is applied beyond the population it was measured on and says "
                             "nothing about the transfer. Name the population and period it is "
                             "carried to, and on what grounds." % r["evidence_id"])
        if not (r.get("measured_scope") or "").strip():
            raise ValueError("%s states a sulfur value without saying what was sampled to get it"
                             % r["evidence_id"])
        if not (r.get("fuel_pool") or "").strip():
            raise ValueError("%s names no fuel pool; the one-pool-one-sulfur invariant cannot be "
                             "checked without it" % r["evidence_id"])
    return {r["evidence_id"]: r for r in rows}


def evidence(ids, fy_end, source_class_id, register=None):
    """The one evidence row among `ids` valid for fiscal-END year fy_end and naming the class
    in applies_to. Zero rows -> NoSulfurEvidence (typed); two rows -> ValueError (the register
    overlaps and must be fixed, not averaged)."""
    register = register or load()
    hits = []
    for eid in [i for i in ids.split(";") if i]:
        r = register.get(eid)
        if r is None:
            raise KeyError("sulfur evidence %r is not in %s" % (eid, os.path.relpath(REGISTER)))
        if source_class_id not in r["applies_to"].split(";"):
            raise ValueError("%s cites sulfur evidence %s, whose applies_to does not name it"
                             % (source_class_id, eid))
        if int(r["valid_from_fy_end"]) <= fy_end <= int(r["valid_to_fy_end"]):
            hits.append(r)
    if not hits:
        raise NoSulfurEvidence("%s: no sulfur evidence valid for FY ending %d among %s"
                               % (source_class_id, fy_end, ids))
    if len(hits) > 1:
        raise ValueError("%s: %d sulfur evidence rows overlap FY ending %d"
                         % (source_class_id, len(hits), fy_end))
    return hits[0]


def so2_kt(fuel_kt, s_pct, oxidised_frac, retention_frac):
    """kt SO2 from kt fuel at s_pct weight-percent sulfur."""
    return 2.0 * fuel_kt * (s_pct / 100.0) * oxidised_frac * (1.0 - retention_frac)


def so2_uncert_pct(evidence_row, retention_frac, retention_uncert_pct):
    """The balance's own uncertainty: the evidence row's percent combined with the retention
    term's (a retention of 0.25 +/- 100 percent moves (1 - r) by +/- 33 percent)."""
    r_term = 0.0
    if retention_frac and retention_uncert_pct:
        r_term = retention_frac * retention_uncert_pct / (1.0 - retention_frac)
    return product(float(evidence_row["uncert_pct"]), r_term)
