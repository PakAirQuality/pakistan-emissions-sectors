# Where the gas boundary is, and what crosses it

Stage 3 of the response to the twenty-second review (item 3). The review asked whether the
combustion quantity from which a leak is deducted already contains that leak — that is, whether
the deduction double-counts. The answer is published and guarded, and this file states it; one
genuine soft spot is named at the end rather than argued away.

## The deduction is post-meter, so the original quantity does include it

The leak the inventory books at 1.B.2 is **post-meter**: downstream of the utility sales meter,
upstream of the burner. The quantity each combustion module starts from is gas *delivered and
sold* — measured at that same meter — so the leaked molecules are inside it by construction and
removing them is a correction, not a second deduction. `outputs/national_gas_closure.csv` makes
this checkable rather than assertable: every stream carries a `metering_basis` drawn from a
closed vocabulary, and the six streams in the post-meter leak base are exactly the six whose
basis reads `delivered-sold; also metered-downstream-of-loss for the leak factor`.

The three streams that are **not** in the leak base — residential, CNG, and other/independent
systems — are marked `no`, and the file says why for each. `gas_TJ` stays gross throughout; the
leak is booked once, at 1.B.2, and nowhere else.

The identity is enforced, not inspected: the module aborts its own build if the delivered total,
the supply identity and the shared-activity draw do not close at the declared tolerance, and
nine tests cover it including a positive control that breaks the identity on purpose.

## Estimated leakage is not unaccounted-for gas, and the file keeps them apart

Unaccounted-for gas (UFG) is a metering and billing residual. The methane leak is an emission
estimate from a network factor. They are different quantities and the inventory never equates
them: **23.83 per cent of UFG would have to be physical loss** for the two to agree, and no
Pakistani measurement establishes that share. The closure file carries both and books neither
as the other — "neither residual is methane emissions" is its own wording.

## The fertilizer feedstock inconsistency, stated rather than smoothed

**History:** through rc66 the 756 MMCFD of fertilizer gas sat inside the post-meter leak base.
That gas is chemically consumed in the reformers and booked as IPPU feedstock at 2.B.1.

**rc67 moved the feedstock share out of the base,** to a reference of 23.499 Mt fugitives. The rule
was justified as IPCC-directed: the factor's activity was said to be gas consumed for *combustion
end uses*, citing IPCC 2019 Table 4.2.4k, note c.

**That attribution was wrong** (external audit, corrected 21 October 2026). The IPCC 2019 activity
is "volume of gas consumption at industrial plants and power stations" (Eq 4.2.18; Table 4.2.4k,
"non-residential and commercial gas consumed"). Note c gives only the factor's derivation from the
Revised 1996 Table 1-58. The IPCC text excludes the emissions of combustion itself, not
non-combusted gas.

**Where that leaves the rule:**
- The exclusion is a modelling judgement: reformed feedstock is taken not to pass the equipment
  whose leaks the factor describes. No Pakistani measurement supports either treatment.
- The feedstock-inside membership (`fugitives_including_feedstock`, about +1.19 Mt) is therefore an
  admissible alternative, not a superseded one.
- Which membership the reference should carry is a re-base decision for the next mint.

## The one genuine soft spot: power grid gas

Of the nine customer streams, eight are matched or declared against the same publication. The
ninth — **power, 1060.13 MMCFD, 1.A.1.a** — is `reconciled_different_meter`. Its activity is
NEPRA Table 3's TOE (a *consumed-reported* basis), not OGRA's delivered sales, and the two are
reconciled to a ratio of 1.085 rather than established against the customer meter. The
measurement point is therefore **not established** for the largest single gas stream in the
account.

**The quantity at stake is larger than I first said, and the correction matters.** An earlier
draft of this file put it at about 0.11 Mt CO₂e — "small beside the 1.43 Mt feedstock
question". Deriving it instead of estimating it gives an order of magnitude more. The
regulator's own two publications differ by **26,672 TJ on this stream, 8.5 per cent**, which at
the gas combustion factor is **up to 1.48 Mt CO₂e** if the whole difference is activity. So the
power-gas measurement point is the *largest* unestablished quantity in the gas account, not the
smallest — bigger than the feedstock inconsistency it was compared against.

The band is 0 to 1.48 Mt rather than a point, because an unknown share of that difference is
the heating value the plant sum assumes (implied 736 Btu/scf) rather than a quantity. The
decomposition is the open question, and settling it needs OGRA's delivered-sales series for the
power customer class beside NEPRA's consumed figure for the same twelve months — which no held
publication prints together.

The gap now has a row of its own in `outputs/national_gas_closure.csv`
(`GAP: power gas measurement point`, `ledger_status = not_established_declared`), where before
there was none and the nearest row was about NMVOC. It adds to no total: the gas IS estimated,
at 17.42 Mt CO₂e. What is unestablished is which meter the activity describes.
