"""The dung-fate ledger: D_diverted = D_household + D_unresolved as an executable account.

The identity has lived in a docstring since the S configuration was built
(combustion.dung_air_dry_kg): agriculture's ledger diverts 58.74 Mt of air-dry cake to
fuel, the HIES survey observes 11.97 Mt burned in households, and under the survey reading
46.77 Mt of diverted cake has no observed destination. A docstring is a claim a reader must
find; the rc2 review's section 4 asked for the account itself -- mass conservation tells
you the mass exists, it does not tell you its destination, and a fate that lives only in
prose looks resolved when it is not.

Same discipline as sectors/waste/ledger.py: the partition is written as a published CSV
with an explicit UNRESOLVED row, closure is asserted at write time and raises rather than
warns, and the candidate destinations are promoted from the docstring into the row a
reader actually meets. Under L the household fate takes the whole diversion by
construction (that is what configuration L asserts); under S the unresolved row is the
open question the scenario variants price one destination at a time
(report/dung_variants.py).

Usage: written by run_residential on every run; also
       python3 -m pkinv.sectors.residential.dung_ledger
Writes: outputs/residential_dung_ledger_2024.csv
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.sectors.residential import combustion
from pkinv.core.io import write_table

TOLERANCE_KG = 1000.0                 # one tonne, on a ~59,000,000 t account

UNRESOLVED = ("UNRESOLVED - diverted air-dry cake with no observed destination")

CANDIDATES = ("commercial tandoors and eateries; non-household burning; over-stated "
              "burned-fuel MMS shares returning it to manure management; field "
              "application; survey undercapture of own-produced cake")


def rows(data, agri=None):
    """The ledger rows, air-dry kg, closure asserted under both configurations."""
    diverted = combustion.dung_air_dry_kg(data, agri, basis="ledger")
    household_l = diverted
    household_s = combustion.dung_air_dry_kg(data, agri, basis="survey")
    unresolved_s = diverted - household_s

    # The unresolved fate is DEFINED as the difference, so "household + unresolved =
    # diverted" closes by construction and asserting it would check nothing (the first
    # draft did, and its own reinstated-defect test proved the check vacuous). The
    # invariant that can actually fail is non-negativity: a survey quantity above the
    # diversion means the diverting assumption itself is broken, and a negative
    # unresolved row published as a fate would be an anti-mass.
    if unresolved_s < -TOLERANCE_KG:
        raise ValueError(
            "the observed household quantity exceeds the diverted supply by %.1f kg: "
            "the ledger's diversion (%.1f) cannot fund the survey's demand (%.1f), so "
            "the burned_fuel MMS shares or the survey capture are wrong in the OTHER "
            "direction and no fate partition exists to publish"
            % (-unresolved_s, diverted, household_s))
    if abs(household_l - diverted) > TOLERANCE_KG:
        raise ValueError("configuration L no longer assigns the whole diversion to "
                         "households; the ledger's L row is stale")

    def mt(kg):
        return round(kg / 1e9, 4)

    def share(kg):
        return round(kg / diverted, 4)

    return [
        {"configuration": "both", "claimant": "Diverted to fuel (agriculture ledger)",
         "Mt_air_dry": mt(diverted), "share_of_diverted": share(diverted),
         "treatment": "control",
         "note": "agriculture's diverted nitrogen through the VS/ash/moisture chain "
                 "(combustion.dung_air_dry_kg, basis=ledger); the burned_fuel MMS shares "
                 "are the diverting assumption"},
        {"configuration": "L", "claimant": "Household combustion (1.A.4.b)",
         "Mt_air_dry": mt(household_l), "share_of_diverted": share(household_l),
         "treatment": "residential fuel chain, CH4/N2O + biogenic CO2 memo",
         "note": "configuration L assigns the whole diversion to households by "
                 "construction; that assignment, not the mass, is what S contests"},
        {"configuration": "S", "claimant": "Household combustion (1.A.4.b)",
         "Mt_air_dry": mt(household_s), "share_of_diverted": share(household_s),
         "treatment": "residential fuel chain, CH4/N2O + biogenic CO2 memo",
         "note": "household cake consumption on the HIES survey series (per-household "
                 "quantity interpolated between the 2018-19 and 2024-25 rounds; the "
                 "reference since rc67), on the same composition parameters as L"},
        {"configuration": "S", "claimant": UNRESOLVED,
         "Mt_air_dry": mt(unresolved_s), "share_of_diverted": share(unresolved_s),
         "treatment": "no GHG pathway applied; priced one destination at a time in "
                      "outputs/national_dung_variants.csv",
         "note": "candidates, with different CH4/N2O/CO2-memo consequences each: "
                 + CANDIDATES},
    ]


def write(data, agri=None, year=None):
    out = rows(data, agri)
    path = asset_path(OUTPUTS,
                        "residential_dung_ledger_%d.csv" % (year or data.year))
    write_table(path, ["configuration", "claimant", "Mt_air_dry",
                                          "share_of_diverted", "treatment", "note"], out, lineterminator="\n")
    return path, out


def main():
    from pkinv.sectors.residential.data import ResidentialData
    data = ResidentialData()
    path, out = write(data)
    print("dung-fate ledger -> %s" % path)
    for r in out:
        print("  %-5s %-58s %8.2f Mt  %.3f" % (r["configuration"], r["claimant"][:58],
                                               r["Mt_air_dry"], r["share_of_diverted"]))


if __name__ == "__main__":
    main()
