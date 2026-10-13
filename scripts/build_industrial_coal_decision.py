"""THE DECISION RECORD: what is booked, what the alternatives are, and what each test actually
established — under an acceptance policy that separates a contradiction from an absence (rc54).

WHY THE POLICY WAS REWRITTEN. rc53 scored every candidate against four tests and rejected all of
them, and the reviewer's objection was that the rule could not tell three different things apart.
Reading rc53's own output proves the objection: its supply-and-use test was a hard constraint in two
years of nine, said "the two tables balance BY CONSTRUCTION so this is a transcription check, not
evidence" in three, and said "undetermined" in four; its independent-count test for cement said NO
COMPANY CLINKER IS HELD in seven years of nine — an absence — and that absence was written into a
sentence concluding the candidate failed. A candidate cannot fail a test that was never run.

THE POLICY, STATED BEFORE ANY CANDIDATE IS SCORED UNDER IT.

  Every test RESULT — not every test — carries one of three kinds, because the same test is a
  constraint in one year and an absence in another:

    constraint   a valid accounting or physical bound, with its tolerance and its assumptions
                 named. An estimate that violates one is inadmissible. THE OFFICIAL SERIES IS
                 SCORED ON THESE TOO: where it violates a constraint, that is a finding about the
                 official series, not a point in its favour.
    validation   a comparison against an independent observation. Neither side is the truth, so a
                 disagreement is evidence about the pair and ADOPTS NOTHING on its own.
    untested     the input is not held. An untested result NEVER favours either estimate, and the
                 record must not phrase it as a failure of the candidate.

  ADOPTION requires: no `constraint` violated, at least one `validation` favouring the candidate,
  and — where the candidate replaces a SERIES rather than a LEVEL — a defensible account of how the
  activity moves between years. An arbitrary midpoint is never a candidate.

  TWO REFUSALS THAT MUST NOT BE CONFLATED. "This candidate assumes a constant fleet and utilisation,
  so it does not establish the TREND" is a valid objection to adopting it as a nine-year series.
  "No reconstruction is admissible without directly surveyed activity in every year" is NOT: IPCC
  2006 Vol 1 Ch 5 (held, data/raw/ipcc/) permits a surrogate relationship developed from a single
  year, noting only that more years improve it. The record says which objection it is making.

WHAT THIS RELEASE DOES NOT DO. rc54 brings no new evidence. It rewrites the policy and re-scores
the SAME candidates under it, so that the evidence rc55 acquires meets a rule that was not built
around it. The rc53 verdicts ship beside the rc54 ones under `policy_version`, unedited, in the same
shape the coal-vintage ledger keeps a superseded print.

Reads:  outputs/pakemis_coal_balance.csv, outputs/pakemis_cement_kiln_coal_reconstruction.csv,
        outputs/pakemis_brick_activity_reconstruction.csv, outputs/pakemis_brick_coal_alternatives.csv,
        outputs/pakemis_coal_vintage_ledger.csv, data/coal_booking_policy.csv,
        data/activity/industry/coal_by_sector_vintages.csv
Writes: outputs/pakemis_industrial_coal_decision.csv
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from pkinv.assets import asset_path

from pkinv.paths import DATA, OUTPUTS, ROOT  # noqa: E402

BALANCE = asset_path(OUTPUTS, "pakemis_coal_balance.csv")
CEMENT = asset_path(OUTPUTS, "pakemis_cement_kiln_coal_reconstruction.csv")
BRICK = asset_path(OUTPUTS, "pakemis_brick_activity_reconstruction.csv")
ALTS = asset_path(OUTPUTS, "pakemis_brick_coal_alternatives.csv")
POLICY = asset_path(DATA, "coal_booking_policy.csv")
VINTAGES = asset_path(DATA, "activity", "industry", "coal_by_sector_vintages.csv")
OUT = asset_path(OUTPUTS, "pakemis_industrial_coal_decision.csv")

PERIODS = ["%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024)]
POLICY_VERSION = "rc54"
KINDS = ("constraint", "validation", "untested")
FIELDS = ("policy_version", "stream", "fiscal_year", "test", "kind", "subject", "result",
          "finding", "booked_kt", "candidate_low_kt", "candidate_high_kt",
          "decision", "decision_rule_row", "why")


def rows(path):
    from pkinv.activity.store import read_rows as canonical_rows
    return canonical_rows(path, comments=True)


def booked():
    prints = {r["estimate_id"]: r for r in rows(VINTAGES)}
    out = {}
    for r in rows(POLICY):
        p = prints[r["booked_estimate_id"]]
        out[(r["consumer"], r["reference_fiscal_year"])] = float(p["value"])
    return out


FLEET_BY_YEAR = asset_path(OUTPUTS, "pakemis_brick_kiln_fleet_by_year.csv")
PUNJAB_KILN_SHARE = 0.8668      # kiln_screening.PUNJAB_BRICKKILN_SHARE, the census cross-section


def fleet_low_national_kt():
    """Punjab's low-end fleet coal demand scaled to the nation, or None if unbuilt.

    The LOW end deliberately: a constraint has to be the weakest claim that still bites, and
    73.9 days is the shorter of the two held seasons. Scaling by the kiln-count share is the
    same assumption kiln_screening already makes, and it is an assumption - stated here rather
    than buried, because a national floor built from one province's count depends on it.
    """
    if not os.path.exists(FLEET_BY_YEAR):
        return None
    punjab = [r for r in rows(FLEET_BY_YEAR)
              if r["reading"] == "bkoap" and r["period_id"] == "FY2020-21"]
    if not punjab:
        return None
    return sum(float(r["coal_kt_low"]) for r in punjab) / PUNJAB_KILN_SHARE


OBSERVATIONS = asset_path(DATA, "activity", "industry", "fuel_sulfur_observations.csv")
GRADE_MIX = asset_path(DATA, "activity", "industry", "furnace_oil_grade_mix.csv")
SULFUR_REGISTER = asset_path(DATA, "activity", "industry", "fuel_sulfur_evidence.csv")


def sulfur_rows():
    """Score the item-3 sulfur evidence under the SAME policy the coal candidates are scored under.

    WHY SULFUR BELONGS IN THIS RECORD. The coal streams above ask "how much fuel". Sulfur asks
    "what was in it", and SO2 is linear in both, so an unevidenced sulfur central is exactly the
    same kind of claim as an unevidenced activity series - and deserves the same three-way reading
    rather than a quiet edit. The brick classes carry 225 of the 318 kt of national industrial SO2
    at FY2015-16, and the number multiplying them is a resource range nobody has ever measured
    at a kiln.

    These rows are NOT year-keyed: every sulfur central in the register is flat across the panel
    (the two road-diesel rows excepted), so a per-year verdict would repeat itself nine times and
    say nothing. fiscal_year is written as the span the register row itself declares.
    """
    if not (os.path.exists(OBSERVATIONS) and os.path.exists(GRADE_MIX)):
        return []
    obs = {r["observation_id"]: r for r in rows(OBSERVATIONS)}
    mix = [r for r in rows(GRADE_MIX) if r["period_id"]]
    reg = {r["evidence_id"]: r for r in rows(SULFUR_REGISTER)}
    span = "FY2015-16..FY2023-24"
    out = []

    def add(stream, test, kind, subject, result, finding, **extra):
        assert kind in KINDS or kind == "", kind
        row = {"policy_version": POLICY_VERSION, "stream": stream, "fiscal_year": span,
               "test": test, "kind": kind, "subject": subject, "result": result,
               "finding": finding, "booked_kt": "", "candidate_low_kt": "",
               "candidate_high_kt": "", "decision": "", "decision_rule_row": "", "why": ""}
        row.update(extra)
        out.append(row)

    # ---- brick-kiln coal sulfur -----------------------------------------------------------
    coal = reg["coal_punjab_fields"]
    booked_s = float(coal["s_pct_central"])
    fired = sorted((o for o in obs.values()
                    if o["fuel"] == "Brick-kiln coal" and o["what_it_measures"] == "as_fired"
                    and o["s_pct_central"]), key=lambda o: float(o["s_pct_central"]))
    values = [float(o["s_pct_central"]) for o in fired]
    add("Brick-kiln coal sulfur", "the band admits every direct observation", "constraint",
        "the OFFICIAL series", "VIOLATED (conditional), AND REPAIRED AT ITEM 3",
        "the booked band ran 2.6-10.7 %% and the lowest as-fired Pakistani kiln-coal analysis reads "
        "%.2f %%, which fell OUTSIDE it; lo now reads %s. The condition, stated because a violation "
        "asserted without one is a claim: every analysis is a single batch and its authors say so, "
        "so the bound is 'the band must contain what has been measured', never 'the fleet is "
        "%.2f %%'." % (values[0], coal["s_pct_lo"], values[0]))
    add("Brick-kiln coal sulfur", "as-fired analyses against the booked central", "validation",
        "the CANDIDATE", "FAVOURS THE CANDIDATE - ADOPTED AT rc63",
        "three as-fired analyses of Pakistani kiln coal are held - %s %% - and their mean %.3f %% is "
        "now the booked central, on basis measured_avg. THE GROUND IS THE BASIS, NOT THE LEVEL: the "
        "superseded 4.5 %% was the geometric middle of two Punjab coalfields' RESOURCE ranges, which "
        "this register's own preamble defines as 'a RANGE of what the seams hold, not the average "
        "burned', and the level moves only 3.2 %%. A fourth CDPR sample (pure Hyderabad, 2.75 %%) is "
        "excluded: that kiln fires a two-to-one mixture, so the pure sample is a component of a "
        "charge and not a charge. THIS TEST WAS SCORED THREE OTHER WAYS FIRST, all withdrawn and all "
        "recorded because each failed differently. DISAGREES, when one analysis was held and the "
        "booked value looked 89 percent too high - one observation is not a finding. CORROBORATED, "
        "when four values including the blend component averaged 4.17 and straddled the booked "
        "value - the wrong evidence counted the right way, and it moved the mean across the booked "
        "central and so across the sign. STRADDLES, when a proportioned mixture of 3.70 was weighed "
        "equally against the measured 5.95 - but the source states its mixture sample 'varies from "
        "the proportional sum of the pure samples', so that reconstruction is the one calculation "
        "the study forbids, and giving it equal weight was over-correction after two errors of "
        "over-confidence."
        % (", ".join("%.2f" % v for v in values), sum(values)/len(values)))
    add("Brick-kiln coal sulfur", "the coalfields the central is built from", "validation",
        "the OFFICIAL series", "DISAGREES",
        "this row is scoped to 'Punjab (Salt Range, Makarwal)' and built from those fields' resource "
        "ranges. Both CDPR/IGC kilns are PUNJAB kilns burning BALOCHISTAN and HYDERABAD (Sindh) "
        "coal, at Rs. 14,000 and Rs. 9,000 per tonne. Price selects sulfur - the cheap Hyderabad "
        "coal assays 2.75 % and the dearer Balochistan 5.60 - so the mix a kiln buys is an economic "
        "choice, not a geological one. The LEVEL survives this; the BASIS for the level may not, and "
        "a central that is right for the wrong reason will not stay right.")
    add("Brick-kiln coal sulfur", "a fleet-representative series", "untested", "both estimates",
        "NOT HELD",
        "four batches from three kilns across ten years is not a fleet distribution, and every "
        "source says its figure is a batch. What the booked central still lacks is a sampling "
        "design, not another anecdote (gap industry-coal-sulfur).")
    add("Brick-kiln coal sulfur", "DECISION", "", "", "",
        "adoption needs no violated constraint and a validation favouring the candidate; here the "
        "validation favours the BOOKED value, which is an argument for leaving it alone",
        booked_kt="%.2f %% S" % booked_s,
        candidate_low_kt="%.2f %% S" % values[0], candidate_high_kt="%.2f %% S" % values[-1],
        decision="ADOPTED - measured_avg replaces field_range (the first adoption in either record)",
        decision_rule_row="3 (bounded alternatives, no central)",
        why="ADOPTION IS EARNED ON THE BASIS, NOT ON THE THREE PERCENT. No constraint is violated; "
            "the validation favours the candidate; and the candidate is the kind of evidence this "
            "register has asked for since rc58 and never had - `measured_avg`, 'consignment "
            "analyses of consumed fuel', declared in the vocabulary and used by no row until now. "
            "The superseded derivation was wrong independently of its value: it was built from Salt "
            "Range and Makarwal resource ranges while both measured Punjab kilns fire Balochistan "
            "and Hyderabad (Sindh) coal bought at Rs. 14,000 and Rs. 9,000 per tonne, so price "
            "selects the sulfur before geology does. WHAT IS NOT CLAIMED: three batches are not a "
            "fleet distribution, every source says so, and uncert_pct was deliberately held at 60 "
            "rather than narrowed to match the new basis - a t-interval on n=3 spanning a factor of "
            "2.5 is about +/- 106 percent, and the unmeasured retention floors the combined term "
            "anyway. The band is the observed range and is asymmetric about the central. Gap "
            "industry-coal-sulfur stays OPEN for a series with a sampling design.")

    # ---- industrial furnace oil sulfur -----------------------------------------------------
    fo, power = reg["fo_hsfo_grade_mix"], reg["power_rfo_spec_range"]
    ratio = float(fo["s_pct_central"]) / float(power["s_pct_central"])
    lo_mix = min(float(r["grade_weighted_s_pct"]) for r in mix)
    hi_mix = max(float(r["grade_weighted_s_pct"]) for r in mix)
    add("Industrial furnace oil sulfur", "one fuel, one sulfur, across sectors", "constraint",
        "the OFFICIAL series", "VIOLATED (conditional), AND RESOLVED AT rc63",
        "fo_hsfo_grade_mix booked %s %% for industry while power_rfo_spec_range booked %s %% for "
        "power - the SAME national furnace oil, in the same years, %.2fx apart. Both could not be "
        "right. RESOLVED BY MERGING RATHER THAN BY COPYING A NUMBER: power_rfo_spec_range is "
        "retired with its reasoning preserved, and the three power RFO classes now cite the "
        "industry row, so one fuel has one sulfur and a later edit cannot restate the "
        "disagreement. The evidence chose which row survived - the held import grade split is "
        "85.3-100 %% high-sulphur grade across the four panel years it covers, so the national pool "
        "sits near the top of the 0.5-3.5 specification span rather than at its unweighted "
        "geometric middle. Power RFO SO2 rises 126.8 %%, national 103.566 -> 234.861 kt at "
        "FY2015-16. THE CONDITION: the import split is four of nine years and imports are not "
        "consumption; what it establishes is the GRADE composition of the pool, which is what "
        "chooses between a midpoint and a near-ceiling, not the ceiling itself."
        % (fo["s_pct_central"], power["s_pct_central"], ratio)) 
    add("Industrial furnace oil sulfur", "grade-mix trajectory against the flat central",
        "validation", "the OFFICIAL series", "DISAGREES IN DIRECTION, NOT ADOPTABLE IN LEVEL",
        "applying the two grades' ceilings to the held import tonnage gives %.2f-%.2f %% across "
        "FY2015-16..FY2018-19, RISING as low-sulphur furnace oil disappears, against a booked "
        "central of %s %% flat for all nine years. Two reasons it is not adopted: both terms are "
        "CEILINGS, so the series is an upper envelope rather than an assay; and imports are not "
        "consumption, with the table stopping at FY2018-19 and furnace-oil imports collapsing "
        "after it. It is published as a bracket."
        % (lo_mix, hi_mix, fo["s_pct_central"]))
    add("Industrial furnace oil sulfur", "an independent factor, never used to set the value",
        "validation", "the CANDIDATE", "CORROBORATES, TO WITHIN 4 PERCENT",
        "the held power-plant workbook (sources/Power Plants/power_plants_emissions.xlsx, hashed in "
        "the release) carries its own SO2 factor of 12 kg/MWh, which through the plant heat rates "
        "implies 57.53 kg SO2 per tonne of furnace oil in seven of nine years. Invert that through "
        "the same complete sulfur balance and it implies 2.877 % sulfur. The adopted central is "
        "3.0 %: the workbook sits 4.1 percent BELOW it. Against the retired power central of "
        "1.3229 % the same workbook sat 117 percent ABOVE - a factor of 2.17 that no one had "
        "explained. THE WORKBOOK PLAYED NO PART IN CHOOSING THE VALUE; it is a second method on a "
        "separate source, and it moved from disagreeing by a factor of two to agreeing within a "
        "twentieth. This is the strongest evidence in the round that the merge kept the right row, "
        "and it surfaced because a test written to pin the OLD constant failed "
        "(tests/test_power_plant_workbooks.py).")
    add("Industrial furnace oil sulfur", "a consignment assay series", "untested", "both estimates",
        "SOUGHT AND NOT HELD",
        "the acquisition fo_hsfo_grade_mix names in its own note. All nine held editions of the "
        "OGRA State of Industry Report mention sulphur only as an abbreviations-page gloss of HSFO "
        "and LSFO - the regulator's flagship publication carries neither a product specification "
        "nor a grade tonnage table (data/raw/ACQUISITION_LOG_fuel_sulfur.csv; gap industry-fo-sulfur).")
    add("Industrial furnace oil sulfur", "DECISION", "", "", "",
        "adoption needs no violated constraint, and a constraint IS violated - by the pair, not by "
        "a candidate",
        booked_kt="%s %% S" % fo["s_pct_central"],
        candidate_low_kt="%.2f %% S" % lo_mix, candidate_high_kt="%.2f %% S" % hi_mix,
        decision="RESOLVED - power joins the industry row; no third value was invented",
        decision_rule_row="3 (bounded alternatives, no central)",
        why="The cross-sector constraint is violated, but it is violated by the DISAGREEMENT "
            "between two booked rows rather than by either candidate, and resolving it means "
            "moving the power row, which this round's scope excludes. The grade-mix trajectory is "
            "real evidence that the flat central discards a time signal, and is still not "
            "adoptable as a central because it is built from ceilings. Booked value unchanged; the "
            "year labels in its source string were corrected, which moved no number.")

    # ---- the retention multiplier ----------------------------------------------------------
    add("Brick-kiln sulfur retention", "elemental conservation of the one paired measurement",
        "constraint", "the CANDIDATE", "VIOLATED (conditional)",
        "CDPR/IGC is the only study measuring BOTH the fuel's sulfur and the stack's SO2 on "
        "Pakistani kilns, with US EPA Methods 2 and 17 and the O2, flow and temperature the "
        "Faisalabad campaign omits - so it ought to determine retention. It cannot, because one of "
        "its two kilns breaks conservation. Complete conversion bounds SO2 at 2 x S: 112 g/kg for "
        "the zigzag kiln (5.60 % S) and 119 for the fixed-chimney kiln (5.95 %). The zigzag's "
        "measured 7.97 g/kg is 7 percent of its bound and implies 0.93 retention; the "
        "fixed-chimney kiln's 299.00 g/kg is 2.51 TIMES its bound and implies -1.51, which is not "
        "a retention. Carbon fails the same way - 8,453 g CO2/kg against the 1,856 its 50.63 "
        "percent carbon allows, 4.55x - while the zigzag sits at 1.13x. The two published factors "
        "reproduce each other through the calorific value to three figures, so the fault is "
        "upstream in the fixed-chimney kiln's fuel-rate or stack-flow term rather than in the "
        "normalisation. THE CONDITION: this scores the CANDIDATE factors, not the kilns, and the "
        "study notes its analysed mixture came from a different batch than the one burned - which "
        "could move sulfur, but not carbon by a factor of four.")
    add("Brick-kiln sulfur retention", "measured stack SO2 by kiln technology", "untested",
        "both estimates", "CANNOT DISCRIMINATE",
        "a held stack campaign (Hasnain et al. 2026, Faisalabad, 30 fixed-chimney and 30 zigzag "
        "kilns, March-April 2023) measures SO2 at 2322.3 mg/Nm3 for FCBTK on coal against 1427.7 "
        "for zigzag - a 39 % difference where the register applies the SAME retention (0.25) and "
        "the same coal sulfur to both. It cannot settle retention: the paper reports neither fuel "
        "sulfur nor the O2, flow or temperature needed to turn a concentration into a factor, so "
        "the difference may be excess-air dilution rather than emission. NAMING THE CONFOUND IS "
        "THE RESULT; an uncorrected concentration ratio is not a retention measurement.")
    add("Brick-kiln sulfur retention", "DECISION", "", "", "",
        "an untested result never favours either estimate",
        booked_kt="0.25 retained", candidate_low_kt="0 retained", candidate_high_kt="0.5 retained",
        decision="OFFICIAL STAYS BOOKED (no Pakistani measurement exists)",
        decision_rule_row="3 (bounded alternatives, no central)",
        why="0.25 is the declared midpoint of a [0, 0.5] bracket taken from AP-42 11.3 note b and "
            "the EMEP 1.A.2 Table 3-29 note, for generic alkaline clay. It multiplies the whole "
            "brick block and has never been measured on a Pakistani kiln (gap "
            "brick-sulfur-retention). The one held campaign cannot close it, for the reason above.")
    return out


def build():
    book = booked()
    balance = {r["fiscal_year"]: r for r in rows(BALANCE)}
    cement = {r["fiscal_year"]: r for r in rows(CEMENT)}
    brick = {r["fiscal_year"]: r for r in rows(BRICK)}
    alts = {r["fiscal_year"]: r for r in rows(ALTS)}
    out = []

    def add(stream, fy, test, kind, subject, result, finding):
        assert kind in KINDS, kind
        out.append({"policy_version": POLICY_VERSION, "stream": stream, "fiscal_year": fy,
                    "test": test, "kind": kind, "subject": subject, "result": result,
                    "finding": finding, "booked_kt": "", "candidate_low_kt": "",
                    "candidate_high_kt": "", "decision": "", "decision_rule_row": "", "why": ""})

    for fy in PERIODS:
        bal = balance.get(fy, {})
        reading = bal.get("supply_use_reading", "") or ""
        b, a, c = brick.get(fy, {}), alts.get(fy, {}), cement.get(fy, {})

        # ---- the supply-and-use account: THREE different kinds, one per regime ---------------
        if reading.startswith("MISDIVIDED"):
            add("Brick-kiln coal", fy, "supply and use", "constraint", "the OFFICIAL series",
                "VIOLATED (conditional)",
                "the official brick column exceeds the domestic non-Thar ceiling. rc55 tests the "
                "conditions this bound rests on - imports by consumer and stock change are not "
                "held, and the publisher's own footnotes put imported coal in the neighbouring "
                "column - so it is carried as a conditional violation of the OFFICIAL value, not "
                "of any candidate")
        elif reading.startswith("CLOSES"):
            add("Brick-kiln coal", fy, "supply and use", "untested", "both",
                "NOT A TEST", "the tonnage account closes because the two published tables balance "
                "by construction; the product says so itself. Nothing is established for or "
                "against either estimate")
        else:
            add("Brick-kiln coal", fy, "supply and use", "untested", "both", "NO METERED LANE",
                "no NEPRA origin split is published for this year, so the account cannot be closed "
                "at all")

        # ---- brick: the counted fleet is a VALIDATION, and it is about the LEVEL --------------
        ratio = float(b["official_over_independent"]) if b.get("official_over_independent") else None
        if ratio is not None:
            add("Brick-kiln coal", fy, "independent counted fleet", "validation", "both",
                "official is %.2fx the counted-fleet level" % ratio,
                "a counted kiln census times a surveyed fuel rate, neither reading HDIP. It "
                "disagrees with the official LEVEL by %.2fx. Neither side is the truth: the "
                "candidate is one cross-section and the official column is a residual" % ratio)
        if a.get("implied_g_per_brick_at_2018_output"):
            add("Brick-kiln coal", fy, "measured fuel intensity", "validation", "both",
                "%s g/brick implied at the one held brick count" % a["implied_g_per_brick_at_2018_output"],
                "against a MEASURED 155-184 g/brick. The denominator is the disputed quantity, so "
                "this is evidence about the pair (tonnage, brick count) and about neither alone")
        # rc62: the fleet's own physical floor, now that the counted fleet has a fuel model.
        # outputs/pakemis_brick_kiln_fleet_by_year.csv puts PUNJAB ALONE at 3,301-9,603 kt of
        # coal a year on the BKOAP roll and 3,095-9,005 on the Hamdani detections. Both ends
        # are the same two measured intensities; what separates them is the operating season,
        # which is open by a factor of 2.9 between the only two held sources. Punjab is 86.7
        # percent of the national kiln count, so the low end scales to roughly 3,800 kt
        # nationally - and the official column prints 2,991 and 1,129 kt in the last two years.
        # A national column below one province's low-end physical demand is a CONSTRAINT on the
        # official series, not a point in its favour; the policy says so explicitly.
        floor = fleet_low_national_kt()
        official_kt = float(a["official_kt"]) if a.get("official_kt") else None
        if floor and official_kt and official_kt < floor:
            add("Brick-kiln coal", fy, "counted fleet's physical floor", "constraint",
                "the OFFICIAL series",
                "%.0f kt booked against a fleet floor of %.0f kt" % (official_kt, floor),
                "the counted fleet cannot fire on this much coal even at the SHORTER of the two "
                "held operating seasons (73.9 days, implied by ICIMOD's own per-kiln figure). "
                "The floor is not an estimate of consumption - it is what the fleet the survey "
                "counted would need, and the official column is below it")
        else:
            add("Brick-kiln coal", fy, "counted fleet's physical floor", "untested", "both",
                "SEASON OPEN BY 2.9x",
                "the fleet's coal demand runs 3,301-9,603 kt for Punjab alone, and the two held "
                "sources for the operating season differ by a factor of 2.9 (73.9 days implied "
                "by ICIMOD's 328.2 t/kiln-year against 215 declared by Hamdani). No midpoint is "
                "taken: an arbitrary midpoint is never a candidate")
        add("Brick-kiln coal", fy, "year-to-year activity", "untested", "the CANDIDATE",
            "NO ANNUAL INDICATOR",
            "the candidate is a 2020 cross-section and no tested indicator of how brick activity "
            "moves between years is held yet. This blocks adopting it as a SERIES; it does not "
            "make a surrogate reconstruction inadmissible - IPCC 2006 Vol 1 Ch 5 permits one "
            "developed from a single year - and rc55 builds the indicator")

        # ---- cement: the SEC floor is a constraint on the OFFICIAL column ---------------------
        sec = c.get("implied_sec_at_full_coal_GJ_per_t", "")
        if sec and float(sec) < 2.85:
            add("Cement-sector coal", fy, "kiln thermal floor", "constraint", "the OFFICIAL series",
                "VIOLATED (conditional) at %s GJ/t" % sec,
                "the official cement column, read as all cement kiln fuel at a full coal share, "
                "implies less thermal intensity than the most efficient line any held source "
                "names. Conditional: the floor is a DESIGN target from a blocked acquisition, the "
                "diagnostic uses the central calorific value only, and any coal share below 100 "
                "percent raises the implied intensity. rc55 propagates the band and the fuel share")
        elif sec:
            add("Cement-sector coal", fy, "kiln thermal floor", "constraint", "the OFFICIAL series",
                "satisfied at %s GJ/t" % sec,
                "the column can physically cover cement kiln fuel; what it holds beyond that is "
                "the other-industry share its own label admits, which is not estimated here")
        producer = c.get("producer_vs_basis_reading", "")
        if "companies print both" in producer:
            add("Cement-sector coal", fy, "producers' own clinker books", "validation", "both",
                "matched-company ratio against the release's basis", producer)
        else:
            add("Cement-sector coal", fy, "producers' own clinker books", "untested",
                "the CANDIDATE", "NO COMPANY CLINKER HELD",
                "the held annual reports do not print production for this year, so the comparison "
                "was never run. Under the rc53 policy this absence was written into the sentence "
                "that rejected the candidate; it establishes nothing either way")
        add("Cement-sector coal", fy, "kiln thermal intensity", "untested", "the CANDIDATE",
            "NOT DISCLOSED BY ANY PRODUCER",
            "no held company report prints kcal/kg, GJ/t or MJ/t, so the reconstruction's heat "
            "term is transferred rather than measured. That is why its band is wide enough to "
            "span both signs - an absence to be closed by acquisition, not a demerit")

    # ---- the decisions, one per stream-year, derived from the scored results ------------------
    by_key = {}
    for r in out:
        by_key.setdefault((r["stream"], r["fiscal_year"]), []).append(r)
    decisions = []
    for (stream, fy), results in sorted(by_key.items()):
        consumer = "brick_kilns" if stream.startswith("Brick") else "cement"
        violated = [r for r in results if r["kind"] == "constraint" and r["result"].startswith("VIOLATED")]
        untested = [r for r in results if r["kind"] == "untested" and r["subject"] == "the CANDIDATE"]
        blocking = [r for r in untested if r["test"] == "year-to-year activity"]
        b, c = brick.get(fy, {}), cement.get(fy, {})
        lo, hi = ((b.get("independent_level_low_kt", ""), b.get("independent_level_high_kt", ""))
                  if stream.startswith("Brick") else (c.get("coal_kt_low", ""), c.get("coal_kt_high", "")))
        why = ("NOT ADOPTED, and the reason is about the CANDIDATE's coverage rather than a test it "
               "failed: %s. %s"
               % ("; ".join(r["result"] for r in untested) or "no untested input",
                  ("The OFFICIAL value violates a constraint this year (%s), which is a finding "
                   "about the official series and is recorded as one - it does not adopt the "
                   "candidate." % "; ".join(r["test"] for r in violated)) if violated else
                  "No constraint is violated by either estimate this year."))
        decisions.append({
            "policy_version": POLICY_VERSION, "stream": stream, "fiscal_year": fy,
            "test": "DECISION", "kind": "", "subject": "", "result": "",
            "finding": ("adoption needs no violated constraint, a validation favouring the "
                        "candidate, and - for a series - an account of how activity moves "
                        "between years"),
            "booked_kt": "%.1f" % book[(consumer, fy)],
            "candidate_low_kt": lo, "candidate_high_kt": hi,
            "decision": "OFFICIAL STAYS BOOKED (candidate not yet admissible as a series)"
                        if blocking else "OFFICIAL STAYS BOOKED",
            "decision_rule_row": "3 (bounded alternatives, no central)", "why": why})
    return out + decisions


HEADER = """\
# THE DECISION RECORD under the rc54 acceptance policy. One row per (stream, year, test) carrying
# the KIND of thing that test established - constraint, validation or untested - plus one DECISION
# row per stream-year. The kinds are the point: a constraint is a bound an estimate may not violate
# and the OFFICIAL series is scored on it too; a validation compares two estimates and adopts
# neither; an untested result means the input is not held and NEVER favours either side. rc53 scored
# absences as candidate failures, and this record does not. No new evidence enters at rc54: the same
# candidates are re-scored so that rc55's evidence meets a rule that was not built around it.
# Generated by scripts/build_industrial_coal_decision.py.
"""


SULFUR_OUT = asset_path(OUTPUTS, "pakemis_fuel_sulfur_decision.csv")

SULFUR_HEADER = """\
# THE FUEL-SULFUR DECISION RECORD (item 3), under the SAME rc54 acceptance policy as
# pakemis_industrial_coal_decision.csv: constraint / validation / untested, and the OFFICIAL series
# is scored on constraints too. A SEPARATE PRODUCT because the grain differs - the coal record is
# one row per (stream, YEAR, test) and every sulfur central in the register is flat across the
# panel, so a per-year verdict would repeat itself nine times and say nothing. fiscal_year here is
# the span the register row itself declares. SO2 is linear in fuel sulfur, so an unevidenced sulfur
# central is the same kind of claim as an unevidenced activity series and earns the same three-way
# reading. Generated by scripts/build_industrial_coal_decision.py.
"""


def main():
    out = build()
    sulfur = sulfur_rows()
    with open(OUT, "w", newline="", encoding="utf-8") as h:
        h.write(HEADER)
        w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
        w.writeheader()
        w.writerows(out)
    tests = [r for r in out if r["test"] != "DECISION"]
    counts = {k: sum(1 for r in tests if r["kind"] == k) for k in KINDS}
    print("industrial coal decision -> %s (%d rows)" % (os.path.relpath(OUT, ROOT), len(out)))
    print("  test results: %s" % ", ".join("%s %d" % (k, counts[k]) for k in KINDS))
    official = [r for r in tests if r["subject"] == "the OFFICIAL series" and r["result"].startswith("VIOLATED")]
    print("  constraints VIOLATED BY THE OFFICIAL SERIES: %d (%s)"
          % (len(official), ", ".join(sorted({"%s %s" % (r["stream"].split("-")[0], r["fiscal_year"])
                                              for r in official})) or "none"))
    print("  adopted: 0 of %d - the pins do not move; the candidates are not yet admissible as series"
          % len([r for r in out if r["test"] == "DECISION"]))
    if sulfur:
        with open(SULFUR_OUT, "w", newline="", encoding="utf-8") as h:
            h.write(SULFUR_HEADER)
            w = csv.DictWriter(h, fieldnames=list(FIELDS), lineterminator="\n")
            w.writeheader()
            w.writerows(sulfur)
        s_tests = [r for r in sulfur if r["test"] != "DECISION"]
        s_counts = {k: sum(1 for r in s_tests if r["kind"] == k) for k in KINDS}
        print("fuel sulfur decision -> %s (%d rows)" % (os.path.relpath(SULFUR_OUT, ROOT), len(sulfur)))
        print("  test results: %s" % ", ".join("%s %d" % (k, s_counts[k]) for k in KINDS))
        decided = [r for r in sulfur if r["test"] == "DECISION"]
        kept = [r for r in decided if r["decision"].startswith("OFFICIAL STAYS BOOKED")]
        print("  decisions: %d adopted or resolved, %d leave the booked value alone"
              % (len(decided) - len(kept), len(kept)))
        for r in decided:
            print("    %-30s %s" % (r["stream"], r["decision"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
