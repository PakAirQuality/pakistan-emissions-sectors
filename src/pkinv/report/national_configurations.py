"""Named policy-facing configurations of the national inventory, one axis at a time.

WHY THIS EXISTS. The structural bridge (outputs/national_structural_bridge.csv) prices
every registered alternative, but its rows are named by AXIS - "power coal energy
basis" - which is the engineering view. A policy reader asks a different question:
"what is the national total if the household survey is right about dung?", "what if
the sewers flow?", "what if the producer census is right about clinker?". This module
publishes that view: a short list of NAMED configurations, each the reference scenario
with exactly one axis moved to its published alternative, resolved through the same
machinery as the bridge so the two products cannot disagree.

NO PROBABILITIES, BY CONSTRUCTION. Each configuration is a fork in the evidence, not a
draw from a distribution; no probability attaches to any of them, and a schema test
(tests/test_national_configurations.py) fails the build if a probability-like column
ever appears here - the same contract national_dung_variants.csv carries.

NOT A SCENARIO SPACE. Each row moves ONE axis off REF_2023_24. The rows do not compose:
two of the power axes describe the same coal energy two ways and cannot both be taken,
which is why this file does not publish combinations.

Usage:  python3 -m pkinv.report.national_configurations
Writes: outputs/national_configurations.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.report import national_rollup
from pkinv.core.io import write_table

FIELDS = ("configuration_id", "axis", "module", "alternative_value_Mt",
          "national_delta_Mt", "national_total_Mt", "family_id", "family_kind",
          "family_role", "machinery", "note")

# WHAT KIND OF MEMBER A FAMILY ROW IS (rc67, the review's Priority 4). A family groups
# readings of one control, and through rc66 that was the only grouping there was. The
# power family then held four members of three different kinds, and the manuscript's
# abstract quoted the family's minimum and maximum as one range: from a member whose
# energy is circular to an account that has been superseded, passing through a member
# that is not about fuel at all. The kind says what may be compared with what:
#
#   reference                  the selected member
#   fuel_property_alternative  the SAME stations and coverage as the reference, a
#                              different heating-value or energy-basis reading
#   coverage_alternative       a different set of generators inside the boundary; says
#                              nothing about fuel properties
#   legacy_published_account   an account an earlier release published, retained so its
#                              totals can be traced; not a current reading
#   structural_envelope_member a member of the fugitives practice and coverage envelope
#
# A RANGE IS ONLY EVER FORMED WITHIN ONE KIND (range_within_kind below);
# tests/test_national_configurations.py holds the manuscript to that.
FAMILY_KINDS = ("reference", "fuel_property_alternative", "coverage_alternative",
                "legacy_published_account", "structural_envelope_member")
FAMILY_KIND = {
    "inventory_reference": "reference",
    "power_plant_physical_coal": "fuel_property_alternative",
    "power_with_kelectric": "coverage_alternative",
    "power_table3_legacy_control": "legacy_published_account",
    "lower_fugitive_practice": "structural_envelope_member",
    "fugitives_including_feedstock": "structural_envelope_member",
    "fugitives_central_practice": "structural_envelope_member",
    "fugitives_joint_minimum": "structural_envelope_member",
}

# STRUCTURAL FAMILIES (rc11, the seventh review's demand that national products carry
# the power family as a family). A family groups configurations that are competing
# READINGS OF ONE CONTROL rather than independent axes: its members cannot be
# combined, and quoting any one of them without the others beside it is the defect
# the grouping exists to prevent. The reference member's row carries the DECLARED
# SELECTION RULE - the reason the headline uses it - so a reader can re-derive the
# choice instead of inferring it.
#   configuration_id -> (family_id, family_role)
FAMILIES = {
    # {grid} is substituted from the row's own alternative_value_Mt (see _role below).
    # It used to be typed in, and two of these labels then sat 17.78 Mt stale through the
    # coal re-base - the reference reading "grid 57.82 Mt" when it was 40.04, and
    # K-Electric "grid 61.83" when it was 44.05 - beside the correct value in the same row.
    "inventory_reference": (
        "power_grid_control", "selected member (grid {grid} Mt; selected, not "
        "settled - the coal energy-basis question is open)"),
    "power_plant_physical_coal": (
        "power_grid_control", "FUEL-PROPERTY alternative on the reference's own fleet "
        "(grid {grid} Mt): the heat-rate route, which is circular"),
    # THE ACCOUNT THE REFERENCE REPLACED. Every release before the coal re-base booked NEPRA
    # Table 3's coal energy; it is retained as a named control rather than deleted, so a
    # reader holding one of those totals can find the account it came from. It is not equally
    # probable with the reference and the registry says so.
    "power_table3_legacy_control": (
        "power_grid_control", "LEGACY PUBLISHED CONTROL (grid {grid} Mt): the reference for "
        "every release before the coal re-base, retained and not preferred"),
    "power_with_kelectric": (
        "power_grid_control", "COVERAGE alternative (grid {grid} Mt): the K-Electric "
        "system's fuel added to the reference's fleet. Not a reading of coal energy, "
        "and not established as omitted from the reference's fuel control"),
    # The fugitives structural envelope (rc14, the ninth review). Through rc66 the
    # reference 24.694 sat at the TOP of its own 9.601-24.694 envelope by construction -
    # conservative default-practice, full coverage - and quoting it without the envelope
    # read a structural maximum as a neutral centre. At rc67 chemical feedstock left the
    # post-meter base, so the reference is 23.499 and the envelope's top is the member
    # that keeps the feedstock in. The practice legs are still at their conservative
    # setting, so the reference still sits high in the envelope and still needs it
    # beside every quote. The reference row already carries the power family, and one
    # row carries one family, so the envelope is labelled on its member rows and the
    # selection rule below rides their notes the way POWER_SELECTION_RULE rides the
    # power rows.
    "lower_fugitive_practice": (
        "fugitives_structural_envelope",
        "envelope member (sector 14.894; the reference 23.499 keeps the conservative "
        "practice factors and sits one membership step below the envelope's top)"),
    "fugitives_including_feedstock": (
        "fugitives_structural_envelope",
        "ENVELOPE TOP, RETAINED AND NOT DEFENDED (sector 24.694): fertiliser feedstock "
        "inside the post-meter base, the membership of every release through rc66"),
    "fugitives_central_practice": (
        "fugitives_structural_envelope",
        "central member (sector 17.678; geometric mean of the published "
        "practice bounds - priced, never selected)"),
    "fugitives_joint_minimum": (
        "fugitives_structural_envelope",
        "envelope joint floor (sector 9.601; the reference is 23.499 and the "
        "envelope's top 24.694)"),
}
FUGITIVES_SELECTION_RULE = (
    "SELECTION RULE for the fugitives_structural_envelope family: the reference "
    "takes the conservative default-practice reading - higher published factors "
    "wherever Pakistan-specific evidence is absent, full segment coverage - with one "
    "membership JUDGEMENT: fertiliser feedstock, which is reformed and not burned in "
    "the equipment whose leaks the post-meter factor describes, is outside its base "
    "(rc67). IPCC 2019 (Eq 4.2.18, Table 4.2.4k) defines the activity as gas consumed "
    "at industrial plants and power stations and does not itself exclude feedstock, so "
    "the feedstock-inside membership is an admissible alternative and the choice is a "
    "re-base question for the next mint. That places the "
    "reference at 23.499 in a 9.601-24.694 structural envelope whose top is the "
    "feedstock-inside membership used through rc66. No probability attaches to any "
    "point in the envelope, and a national quote of 23.499 without the envelope "
    "beside it reads a conservative reading as a neutral centre.")
POWER_SELECTION_RULE = (
    "SELECTION RULE for the power_grid_control family: the reference books grid coal "
    "on each station's reported tonnage at rank-default heating values, and gas and "
    "oil on the regulator's national fuel statistic. Its members are of THREE KINDS "
    "(column family_kind) and may be compared only within a kind. FUEL-PROPERTY "
    "alternatives keep the reference's stations and change the coal energy basis; the "
    "heat-rate member is circular, because its energy contains the generation it is "
    "later divided by. The COVERAGE alternative adds the K-Electric system's fuel; "
    "whether the national fuel statistic already contains that fuel is NOT "
    "established (the gas comparison favours 'omitted', the furnace-oil comparison "
    "'included' in four of five years), so it is priced beside the reference and not "
    "added to it. The LEGACY PUBLISHED ACCOUNT is what releases before the coal "
    "re-base booked; it is retained for traceability and is not a current reading. "
    "Every national quote of the reference carries the family beside it.")


def range_within_kind(rows, family_id, kind, include_reference=True):
    """(low, high) of national_total_Mt over one family's members of ONE kind, with the
    reference member beside them unless told otherwise. The only sanctioned way to form
    a range over a family: a range across kinds mixes questions."""
    if kind not in FAMILY_KINDS:
        raise ValueError("unknown family kind %r" % (kind,))
    wanted = {kind} | ({"reference"} if include_reference else set())
    values = [float(r["national_total_Mt"]) for r in rows
              if (r["family_id"] == family_id and r["family_kind"] in wanted)
              or (include_reference and r["family_kind"] == "reference")]
    if not values:
        raise ValueError("family %s has no member of kind %s" % (family_id, kind))
    return min(values), max(values)


# configuration_id -> (axis in data/scenarios.csv, policy-facing note).
# None axis marks the reference row.
CONFIGURATIONS = (
    ("inventory_reference", None,
     "every axis at its REF_2023_24 setting; the release's deterministic baseline"),
    ("all_diverted_dung_household_fuel", "residential dung basis",
     "CONFIGURATION L: households burn ALL the dung agriculture diverts from manure "
     "management, about five times what the HIES rounds observe them burning. The "
     "reference of every release through rc66, retained as a bounded destination "
     "assumption for the diverted dung and not as a reading of household use. The other "
     "candidate destinations are priced separately, for every year, in "
     "outputs/pakemis_dung_fate_by_year.csv"),
    ("lower_fugitive_practice", "fugitive practice",
     "the gas network operates at the lower published practice factors; no national "
     "LDAR or pipe-material evidence decides between the readings"),
    ("fugitives_including_feedstock", "post-meter feedstock scope",
     "fertiliser feedstock INSIDE the post-meter leak base, the membership of every "
     "release through rc66, and the literal reading of IPCC 2019 Eq 4.2.18 (gas "
     "consumed at industrial plants and power stations). An ADMISSIBLE alternative to "
     "the rc67 reference, whose exclusion is a judgement that reformed feedstock does "
     "not pass the leaking equipment; corrected 21 October 2026, the rationale having "
     "been misattributed to IPCC note c. About +1.19 Mt. The process fuel the same "
     "plants burn is inside the base in both readings"),
    ("power_plant_physical_coal", "power coal energy basis",
     "the same station mass at the calorific values the plants' own generation implies - the "
     "HEAT-RATE route, which is circular (its energy contains the generation it is later "
     "divided by) and lands 1.6 Mt from the booked account"),
    ("power_table3_legacy_control", "power coal energy basis (legacy published control)",
     "NEPRA SoIR Table 3's published coal energy, the reference for every release before the "
     "coal re-base. Retained so a reader holding a total published then can find the account "
     "it came from; not preferred, because divided into NEPRA's own printed generation it "
     "implies net fleet efficiencies inside 28-47 per cent in two of nine years against the "
     "booked account's nine of nine"),
    ("power_with_kelectric", "power scope",
     "the K-Electric ledger fuel inside the power boundary; a scope choice, not a "
     "measurement"),
    ("waste_flowing_sewer", "sewer methane correction factor",
     "wastewater on the river-discharge MCF (0.1), the reading the one independent "
     "comparator supports against the stagnant-drain description"),
    # rc41 (the nineteenth review's M-2): this row was `cement_observed_company_floor`
    # from rc9 to rc40, named for the fifteen-company census floor (21.477 Mt) it priced
    # against a Tier 1 reference. rc30 made the completed census THE reference and
    # re-pointed the row at the Tier 1 model it displaced - without renaming it, so a
    # configuration whose value was the 0.75-fraction MODEL (17.389 Mt) carried an id and
    # a note that said "observed producer floor". The id now says what the value is.
    ("cement_tier1_model_low", "cement clinker activity basis",
     "the Tier 1 PBS-QIM cement times a 0.75 clinker fraction, trade-corrected (17.389 "
     "Mt) in place of the sixteen-company producer census's observed clinker (21.816 Mt) "
     "- the modelled activity the census superseded as reference at rc30, kept priced "
     "as the low end of the IPCC clinker-fraction bracket"),
    # The other end of the published 17.389-21.504 range. The paper claimed both
    # ends were priced here; until the ninth review only the low end was.
    ("cement_all_portland_upper", "cement clinker fraction",
     "the 0.95 all-Portland clinker fraction - IPCC's other default, neither of "
     "which is Pakistani; the reference is the observed producer census (21.816), "
     "1.4 percent above this high end of the Tier 1 bracket"),
    # The aviation scope fork ships as THREE configurations since rc11, one per fuel
    # evidence class: lumping them priced a single +0.434 take-it-or-leave-it bundle,
    # when military attribution, general-aviation activity and the bridge residual
    # are independent questions a reader may answer differently.
    ("military_government_in_scope", "aviation military scope",
     "the national total if the 120,758 t of military/government jet fuel the OCAC "
     "bridge identifies were inside the boundary (+0.382 Mt CO2, CO2-only); IPCC "
     "books military aviation under 1A5b, and no record attributes the activity, so "
     "the reference keeps it as a priced memo row"),
    ("general_aviation_in_scope", "aviation general aviation scope",
     "the national total if the 4,542 t of general-aviation 100LL were inside the "
     "boundary (+0.014 Mt CO2, CO2-only); the fuel is identified but the activity "
     "unresolved, so the reference keeps it as a priced memo row"),
    ("unresolved_jp1_in_scope", "aviation unresolved residual scope",
     "the national total if the bridge's 12,282 t unresolved government JP-1 "
     "residual were inside the boundary (+0.039 Mt CO2, CO2-only); labelled "
     "unresolved because no record attributes it, so the reference keeps it as a "
     "priced memo row"),
    ("cement_kiln_fuel_in_scope", "cement kiln fuel scope",
     "the national total if the transferred-intensity cement model REPLACED the "
     "measured HDIP cement-sector coal the reference books (rc46 activation, "
     "10.80 Mt): +2.59 Mt central excess over a +1.20 to +4.86 bracket - the "
     "completeness question 'does the consumer series capture all kiln fuel?', "
     "priced NET of the reference's own copy (rc47 Wave 0; pricing the whole "
     "model was the twenty-first review's double count). The intensity is still "
     "transferred and the detail lives in "
     "outputs/industry_solid_screenings_2024.csv"),
    ("bagasse_ceiling_in_scope", "bagasse process heat scope",
     "the national total if the process-bagasse CEILING were booked into 1A2 "
     "(~0.39 Mt of CH4+N2O if the ENTIRE cane crop's bagasse were burned; the "
     "mill crush share is unheld and the CO2 is biogenic, outside every total by "
     "construction). Priced so the claimant reads as bounded SMALL rather than "
     "unexamined"),
    # brick_kiln_coal_in_scope and captive_coal_in_scope were RETIRED at rc47
    # Wave 0: the rc46 activation put measured brick coal (and, inside its residual
    # column, the captive share) INTO the reference, so both configurations priced
    # a second copy of mass the baseline already contained - the twenty-first
    # review's double count. Their screenings survive as comparator rows in
    # industry_totals and their screening products are unchanged.
    ("coal_mining_fugitives_in_scope", "coal mining fugitives scope",
     "the national total if the Thar surface-mining screen's HIGH bound were booked "
     "into 1.B.1 (+0.5464 Mt CO2e: 13,238 kt of mine-mouth lignite deliveries held "
     "in the plant ledger all along, under IPCC Table 4.1.5 surface factors). "
     "PARTIAL BY CONSTRUCTION and never the category's bound: underground mining is "
     "unquantified and its factors run ~30x the surface low, so even a small "
     "underground tonnage could dominate the category. The reference keeps 1.B.1 NE "
     "and the detail lives in outputs/fugitives_coal_screen_2024.csv"),
    ("aviation_route_resolved_reading", "aviation model resolution",
     "the domestic aviation total read from the flight-route ledger instead of "
     "aggregate movements (~-0.030 Mt CO2, coverage 99.0%): the resolution "
     "ladder's route_resolved model, priced so the long-deferred re-base "
     "question is a configuration a reader can take or leave. The reference "
     "stays on aggregate movements BY TYPE: every finer product is provisional "
     "and the OCAC-vs-ledger reconciliation spreads 0.98-3.81x - the EMEP "
     "fuel-sales reconciliation is the closer"),
    ("rice_water_regime_weighted", "rice water regime",
     "the national total if Pakistani rice is NOT continuously flooded: irrigated "
     "area at the intermittent-single-aeration factor (0.60; the 0.52 AWD member "
     "is named and never blended), rainfed at 0.28, weighted by the held SPAM "
     "V2r2 technology split - about -6.7 Mt riding on a water-management practice "
     "no Pakistani observation decides. The reference keeps the declared "
     "continuous convention; readings in "
     "outputs/agriculture_water_regime_2024.csv, never averaged (rule 8)"),
    ("rail_ie_summary", "rail traction boundary",
     "the pre-rc11 booking restated: all 0.39437 Mt inside 1.A.3.c with the measured "
     "non-traction share declared IE. The rc11 REFERENCE is the recode - 1.A.3.c at "
     "0.38939 Mt locomotive traction, 0.00498 Mt at the non-traction category "
     "(1A2/1A4c unresolved) per outputs/railways_fuel_claimants_2024.csv - same fuel, "
     "same factors, so either booking conserves the national total exactly"),
)

# JOINT configurations: the declared exceptions to "each row moves ONE axis".
# The fugitives factorial floor is a jointly-minimal reading of SEVEN axes at once
# (outputs/fugitives_structural_factorial_2024.csv, 280 combinations), and until rc11
# it never reached a national product - the reviewer's point that the 9.601 envelope
# floor existed only inside the sector. The gas deduction (rc14) is the second kind
# of exception: a CROSS-SECTOR adjustment no single module's scenario table can
# carry, priced from the gas closure's own arithmetic. The central practice reading
# (rc17) is the third: data/scenarios.csv holds ONE alternative per axis, so a THIRD
# reading of the fugitive-practice control cannot ride the axis register and ships
# through this mechanism instead. (config_id, output, row_key, value_col, module,
# axis_label, note); delta = value - the same file's reference row.
JOINT_CONFIGURATIONS = (
    ("fugitives_joint_minimum", "fugitives_conditional_intervals_2024.csv",
     "minimum_coverage_combined", "deterministic_mt_co2e_ar5",
     "fugitives", "JOINT (seven fugitive axes)",
     "the JOINT floor of the fugitives structural envelope: every axis at its "
     "minimal-coverage/lower-practice leg simultaneously (9.601 Mt against the "
     "conservative default-practice reference 23.499, in an envelope whose top is "
     "24.694). "
     "A joint configuration, deliberately outside the one-axis rule and labelled "
     "as the exception; no probability attaches to any point in the envelope"),
    ("fugitives_central_practice", "fugitives_conditional_intervals_2024.csv",
     "central", "deterministic_mt_co2e_ar5",
     "fugitives", "READING (fugitive practice at the geometric mean)",
     "the central practice reading the twelfth review asked for: every stream "
     "with published high/low practice bounds at their geometric mean - the "
     "retired 2006 module's midpoint mechanism carried into the 2019 engine - "
     "with reference scope and coverage. A synthesized interior member, priced "
     "with its own conditional interval and NEVER selected: no measurement "
     "locates Pakistani practice inside the bounds, so the reference stays the "
     "declared conservative top"),
    ("scope_plus_fgas_screening", "ippu_fgas_screening_2024.csv",
     "scope_plus_fgas_screening", "adjustment_Mt_co2e",
     "cross-sector (scope)", "JOINT (F-gas scope screening, potential-consumption-equivalent)",
     "the fifteenth review's F-gas lane: UNEP's Article-7 aggregate consumption "
     "for calendar 2024 (9.815 Mt CO2e of SUPPLY, not emissions) taken as a "
     "potential-consumption-equivalent scope bound on the NE category 2.F - "
     "screening grade by its own label, the kiln-coal pattern. The reference "
     "keeps 2.F NE because consumption is not emissions without a species-, "
     "application- and bank-resolved model; the three typed evidence lanes "
     "(consumption 9.815 / Pakistan's own CRT 0.003 / EDGAR benchmark 11.54) "
     "are published unblended in the screening file"),
    # rc46 Wave 4: the species-resolved bank, superseding the one-stratum reading as the
    # lane's answer; the bounded bank stays beside it as the comparator whose bracket
    # contains it. Both outside every total pending the rc47 activation review.
    ("scope_plus_fgas_species_bank", "ippu_fgas_screening_2024.csv",
     "scope_plus_fgas_species_bank", "adjustment_Mt_co2e",
     "cross-sector (scope)", "JOINT (F-gas scope screening, species-resolved bank)",
     "rc46 Wave 4: per (species, application) strata over the UNDP RAC import table, "
     "Comtrade HS-2022 and a typed 2020-21 bridge, run through the fgases.py kernel with "
     "IPCC application defaults and component-priced blend GWPs. 5.854 Mt CO2e for 2024 - "
     "inside the superseded model's [2.3, 6.2] for 2023, under the 9.815 consumption "
     "ceiling and the 11.54 EDGAR benchmark, exactly the ordering a bank answer owes. "
     "The gate's charged-equipment criterion remains unmet; 2.F stays NE"),
    ("scope_plus_fgas_bounded_bank", "ippu_fgas_screening_2024.csv",
     "scope_plus_fgas_bounded_bank", "adjustment_Mt_co2e",
     "cross-sector (scope)", "JOINT (F-gas scope screening, bounded bank model)",
     "the eighteenth review's free configuration (rc30): the one-stratum "
     "CO2e-weighted equipment bank run on the UNEP consumption series itself - "
     "empty 2019 start, declared interpolation for the unreported 2021-23, "
     "0.5% assembly loss, 10%/yr operating loss bracketed by IPCC's 5-15% "
     "range, no retirement inside the window, zero recovery per UNEP's "
     "no-licensing-system record. 4.42 Mt CO2e for 2024, between the CRT's "
     "near-zero and the 9.815 consumption ceiling - screening grade, outside "
     "every reference total, and the species/application split it cannot "
     "resolve is exactly the NOU/FBR request"),
    ("commercial_institutional_in_scope", "commercial_scope_configuration_2024.csv",
     "commercial_institutional_in_scope", "adjustment_Mt_co2e",
     "cross-sector (scope)", "JOINT (commercial/institutional scope screening)",
     "the Wave 4 configuration of the 1.A.4.a audit: the two-stream quantifiable "
     "FLOOR (commercial piped gas 0.875 + chart-read LPG 1.552 Mt CO2e) booked "
     "into the category the second review found silently missing. A floor, not "
     "the category: the commercial petroleum share is unresolvable within OCAC's "
     "held classes (needs the HDIP commercial energy balance) and the "
     "government-liquids bound is deliberately not added (its class includes "
     "fleets and aviation). Pakistan's own BUR-1 filed 3.8 Mt sits above the "
     "floor, as a floor should sit below its benchmark. The reference keeps "
     "1.A.4.a NE; detail in outputs/commercial_institutional_audit_2024.csv"),
    # The three non-cement IPPU screenings (Wave 4): categories with no module row in
    # any total, so they ship through the JOINT mechanism like the F-gas screening.
    ("nitric_acid_unabated_in_scope", "ippu_chemicals_screening_2024.csv",
     "nitric_acid_unabated_in_scope", "adjustment_Mt_co2e",
     "cross-sector (scope)", "JOINT (2.B.2 scope screening, unabated)",
     "the national total if the Sadiqabad plant's calendar-2022 nitric acid "
     "(563,701 t, declared prior vintage) were booked into 2.B.2 with NO abatement "
     "operating, under the technology-matched IPCC medium-pressure factor. A FLOOR "
     "of the category (Pakarab Multan's nitric line is identified with no "
     "activity); the activation gate's own pair - this row and the abated variant "
     "beside it bracket the operating question the gate demands evidence on. "
     "Reference keeps 2.B.2 NE; detail in outputs/ippu_chemicals_screening_2024.csv"),
    ("nitric_acid_abated_in_scope", "ippu_chemicals_screening_2024.csv",
     "nitric_acid_abated_in_scope", "adjustment_Mt_co2e",
     "cross-sector (scope)", "JOINT (2.B.2 scope screening, abatement at last "
     "verified rate)",
     "the same inclusion with the plant's ACM0019 catalyst destroying N2O at the "
     "rate its last monitored period verified (2019-2020, annualised, CERs "
     "re-expressed from the SAR GWP to AR5). Whether the catalyst still operates "
     "is the operating evidence the activation gate demands - the pair prices both "
     "answers so neither is presumed"),
    # ammonia_feedstock_in_scope RETIRED at rc52: 2.B.1 entered the reference through its gate
    # (Tier 1 calibrated on NFDC production, nine years); the chemicals screening keeps the
    # pathway reconciliation as a diagnostic, and no configuration re-adds the mass.
    ("gross_delivered_gas_accounting", "national_gas_closure_variant.csv",
     "gross_delivered_gas_accounting", "adjustment_Mt_co2e",
     "cross-sector (gas)", "JOINT (cross-sector gas restoration)",
     "the administrative-fuel view of the rc19 gas boundary decision: the "
     "reference books delivered gas NET of the post-meter leaked share (all "
     "three gases, four combustion claims - the fourteenth review's physical-"
     "atmosphere identity, enforced in the booking itself), and this "
     "configuration restores the full metered delivery as combusted, i.e. the "
     "pre-rc19 double-claim, for readers reconciling against fuel-sales "
     "statistics (the alternative_value column is the SIGNED ADJUSTMENT, not a "
     "sector total - see outputs/national_gas_closure_variant.csv for the "
     "arithmetic and the two corrected rc17 defects in the share's "
     "derivation). A cross-sector adjustment no single-axis scenario can "
     "express, so it ships as a JOINT configuration"),
)



def _role(template, grid_value):
    """Fill a family_role's {grid} from the row's own value, to two decimals.

    A role with no {grid} passes through unchanged, and a {grid} with no value resolves to
    a typed absence rather than to a stale number or an empty parenthesis.
    """
    if "{grid}" not in template:
        return template
    if grid_value in (None, ""):
        return template.replace("{grid}", "NE")
    return template.replace("{grid}", "%.2f" % float(grid_value))

def build(prebuilt=None):
    """Compose the rows through structural_bridge so the two products agree by
    construction: same registry pointers, same reference logic, same baseline."""
    baseline, bridge = national_rollup.structural_bridge(prebuilt)
    by_axis = {r["axis"]: r for r in bridge}
    registry = {r["axis"]: r for r in national_rollup.scenario_registry()}
    family_ref, family_role_ref = FAMILIES["inventory_reference"]
    # The reference's own grid figure is the booked power total, not a constant: it is the
    # legacy control's value less that control's delta, which is how the re-base moved it.
    reference_grid = None
    for row in bridge:
        if "coal energy basis (legacy published control)" in (row.get("axis") or ""):
            reference_grid = (float(row["alternative_Mt"])
                              - float(row["national_delta_Mt"]))
    family_role_ref = _role(family_role_ref, reference_grid)
    rows = [{
        "configuration_id": "inventory_reference", "axis": "", "module": "",
        "alternative_value_Mt": "", "national_delta_Mt": 0.0,
        "national_total_Mt": round(baseline, 5),
        "family_id": family_ref, "family_kind": FAMILY_KIND["inventory_reference"],
        "family_role": family_role_ref,
        "machinery": "sum of outputs/national_all_sectors.csv components",
        "note": CONFIGURATIONS[0][2] + " " + POWER_SELECTION_RULE,
    }]
    for config_id, axis, note in CONFIGURATIONS[1:]:
        b = by_axis[axis]
        if b["national_delta_Mt"] is None:
            raise SystemExit("%s: axis %r has no published alternative row"
                             % (config_id, axis))
        reg = registry[axis]
        family_id, family_role = FAMILIES.get(config_id, ("", ""))
        family_role = _role(family_role, b["alternative_Mt"])
        rows.append({
            "configuration_id": config_id, "axis": axis, "module": b["module"],
            "alternative_value_Mt": round(b["alternative_Mt"], 5),
            "national_delta_Mt": round(b["national_delta_Mt"], 5),
            "national_total_Mt": round(baseline + b["national_delta_Mt"], 5),
            "family_id": family_id, "family_kind": FAMILY_KIND.get(config_id, ""),
            "family_role": family_role,
            "machinery": "%s#%s" % (reg["alternative_output"], reg["alternative_row"]),
            "note": (note + (" " + POWER_SELECTION_RULE
                             if family_id == "power_grid_control" else "")
                     + (" " + FUGITIVES_SELECTION_RULE
                        if family_id == "fugitives_structural_envelope" else "")),
        })
    for (config_id, out_name, row_key, value_col, module, axis_label,
         note) in JOINT_CONFIGURATIONS:
        value = None
        reference = None
        path = asset_path(OUTPUTS, out_name)
        for row in _activity_rows(path, comments=True):
            if row["configuration"] == row_key:
                value = float(row[value_col])
            if row["configuration"] == "reference":
                reference = float(row[value_col])
        if value is None or reference is None:
            raise SystemExit("%s: %s has no %r/reference rows"
                             % (config_id, out_name, row_key))
        delta = value - reference
        family_id, family_role = FAMILIES.get(config_id, ("", ""))
        family_role = _role(family_role, value)
        rows.append({
            "configuration_id": config_id, "axis": axis_label,
            "module": module,
            "alternative_value_Mt": round(value, 5),
            "national_delta_Mt": round(delta, 5),
            "national_total_Mt": round(baseline + delta, 5),
            "family_id": family_id, "family_kind": FAMILY_KIND.get(config_id, ""),
            "family_role": family_role,
            "machinery": "%s#%s" % (out_name, row_key),
            "note": (note + (" " + FUGITIVES_SELECTION_RULE
                             if family_id == "fugitives_structural_envelope"
                             else ""))})
    for row in rows:
        if bool(row["family_id"]) != bool(row["family_kind"]):
            raise SystemExit("%s: a family member needs a kind and a kind needs a family"
                             % row["configuration_id"])
    return rows


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    rows = build()
    path = asset_path(OUTPUTS, "national_configurations.csv")
    write_table(path, list(FIELDS), rows)
    print("national configurations -> %s" % os.path.basename(path))
    for r in rows:
        print("  %-32s %10s Mt  (%+0.3f)" % (r["configuration_id"],
                                             r["national_total_Mt"],
                                             r["national_delta_Mt"] or 0.0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
