"""The dung balance as an ASSIGNMENT question, with the arithmetic that makes it falsifiable.

WHY THIS PRODUCT EXISTS. The 23rd review's item 6, first of the two scoped source
improvements. The L and S configurations differ by about four fifths of the diverted dung, and
the release already prices the four places the residual could go
(outputs/national_dung_variants.csv). What it did not publish is the thing that decides
between the two readings: they are not two estimates of one quantity. L is all excreted
nitrogen leaving manure management for any burner, pushed through a VS/ash/moisture chain. S
is formed cake entering a sampled dwelling. A reader comparing the two masses is comparing a
supply-side derivation against a demand-side observation, and no amount of precision on
either side closes that.

SINCE rc67 THE S SIDE IS THE REFERENCE, and its FY2023-24 quantity is the two-round
interpolation, not the 2024-25 round as measured. The headline rows read the reference. The
falsifiable row does not: the share of households burning cake and the daily quantity are one
round's observations, so the diversion is set against that round's own total there, and the
row keeps the figures it has always had.

So this table states the asymmetry term by term - species, age classes, moisture basis, ash
fraction, handling losses, end user, survey design - and then states what would settle it.
That last row is the point of the whole product: configuration L is FALSIFIABLE. For the
diversion to be burned by households at the intensity the 2024-25 round observes, about
three quarters of Pakistani households would have to burn cake, against the roughly 15 per
cent that round records; or the households that do burn it would have to burn about five
times the observed daily quantity. Either is a checkable claim about Pakistan, and neither is
checked here, which is why no residual is distributed.

NOTHING HERE IS DISTRIBUTED. The unresolved mass stays unresolved: a diagnostic gap is never
inserted as a residual, and the four destinations stay in the variants product as priced
alternatives rather than being averaged into a central case.

TWO ROW BASES, and the column says which.
  recomputed    the value is read from the engine or from a shipped product on this release,
                so it moves when they move.
  transcribed   the value comes from the campaign audit's reading of a survey file or a
                parameter table that this module does not re-open, and carries its pointer.
                A transcribed row is evidence, not a live quantity, and is labelled so a
                reader does not take it for one.

Usage:  python3 -m pkinv.report.dung_balance [--check]
Writes: outputs/pakemis_dung_balance.csv
"""
import argparse
import os
import sys

from pkinv.assets import asset_path
from pkinv.core.io import read_rows, table_text, write_table
from pkinv.paths import DATA, OUTPUTS

OUT = asset_path(OUTPUTS, "pakemis_dung_balance.csv")

FIELDS = ("element", "row_basis", "L_side", "S_side", "unit", "comparability",
          "source_pointer", "what_would_settle_it")

BANNER = """\
# THE DUNG BALANCE: AN ASSIGNMENT QUESTION, NOT A MASS QUESTION
#
# L and S are not two estimates of one quantity. L is all excreted nitrogen leaving manure
# management for any burner, carried through a VS/ash/moisture chain to air-dry cake. S is
# formed cake entering a sampled dwelling. The difference between them is therefore a question
# about WHERE the material goes, and the `comparability` column says, for every term,
# whether the two sides are measuring the same thing at all.
#
# NO RESIDUAL IS DISTRIBUTED HERE. The four candidate destinations are priced one at a time
# in outputs/national_dung_variants.csv and none is adopted.
#
# `row_basis` is recomputed (read from the engine or a shipped product on this release) or
# transcribed (the campaign audit's reading of a survey or parameter file this module does
# not re-open, with its pointer). A transcribed row is evidence, not a live quantity.
"""

# The survey-design and parameter readings the campaign audit established. They are carried
# with their pointers rather than re-derived, because re-opening the HIES microdata here
# would duplicate the residential ingest for a diagnostic, and a second reading of a survey
# file is how two numbers for one quantity get into a release.
TRANSCRIBED = (
    ("Species in scope", "dairy cattle, other cattle, buffalo only",
     "any species - the survey records 'dung cake' with no species attribution", "-",
     "not-comparable",
     "combustion.DUNG_SPECIES; data/sectors/agriculture/parameters/mms_shares.csv",
     "a species attribution in the survey instrument, or a species-resolved cake supply"),
    ("Age classes in scope",
     "cattle split dairy/other by dairy_cattle_share; no calf or young-stock class",
     "no age dimension in the survey", "-", "not-comparable",
     "sectors/agriculture/manure.py nex_by_species",
     "an age-resolved excretion panel"),
    ("Fuel preparation and handling losses", "0.0 - no loss term exists in the chain",
     "0.0 - not applicable, S observes delivered cake", "fraction", "L-side only",
     "sectors/residential/combustion.py: no loss term in the VS/ash/moisture chain",
     "a formed-cake yield measurement from excreted solids"),
    ("Survey weights behind the household figure", "not applicable",
     "4,680 reporting households; 5,907,932 weighted users (14.79 pct of 39.9 M weighted "
     "households); 5.55 kg per user-household per day", "-", "S-side only",
     "HIES 2024-25 design weights; outputs/residential_hies_comparison_2024.csv",
     "the published HIES fuel tabulation, to check the weighted total independently"),
    ("Outlier concentration in the survey total", "not applicable",
     "top 1 pct of households hold 17.9 pct and top 5 pct hold 44.7 pct of the national "
     "total", "share", "S-side only",
     "campaign hies_diagnostics.csv",
     "a trimmed or winsorised design-weighted total beside the untrimmed one"),
    ("Household versus commercial use",
     "unqualified 'burned for fuel' - the manure-share vocabulary names no end user",
     "household consumption only, by questionnaire construction", "-", "not-comparable",
     "mms_shares.csv source string; the HIES questionnaire's own scope",
     "a commercial fuel survey - tandoors and eateries are the named candidate and are "
     "outside every household instrument"),
)


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ledger():
    """{(configuration, claimant-prefix): Mt air-dry} from the shipped dung ledger."""
    out = {}
    for r in read_rows(asset_path(OUTPUTS, "residential_dung_ledger_2024.csv"),
                       comments=True):
        out[(r["configuration"], r["claimant"].split(" (")[0])] = r
    return out


def _hies():
    for r in read_rows(asset_path(OUTPUTS, "residential_hies_comparison_2024.csv"),
                       comments=True):
        if r["fuel"] == "dung_cake":
            return r
    raise AssertionError("no dung_cake row in the HIES comparison")


def _variants():
    return list(read_rows(asset_path(OUTPUTS, "national_dung_variants.csv"), comments=True))


def _param(name):
    """One residential parameter, by its own key.

    RAISES rather than returning None. The first version keyed on "parameter" where the
    table's column is "param", and looked for "dung_cake_moisture_frac" where the table
    says "dung_cake_moisture_ar" - two mistakes, and because the miss returned None the
    product shipped a row reading "total solids / (1 - m)" with the symbol in place of the
    number. A lookup that cannot find its subject must say so.
    """
    path = asset_path(DATA, "sectors", "residential", "parameters",
                      "residential_params.csv")
    for r in read_rows(path):
        if r.get("param") == name:
            value = _num(r.get("value"))
            if value is None:
                raise AssertionError("%s has no numeric value in %s" % (name, path))
            return value
    raise AssertionError("no parameter %r in %s" % (name, path))


def rows():
    led, hies, variants = _ledger(), _hies(), _variants()
    base = variants[0]
    diverted = _num(base["diverted_Mt"])
    household = _num(base["household_Mt"])
    unresolved = _num(base["unresolved_Mt"])
    out = []

    def add(element, basis, l_side, s_side, unit, comparability, pointer, settle=""):
        out.append({"element": element, "row_basis": basis, "L_side": l_side,
                    "S_side": s_side, "unit": unit, "comparability": comparability,
                    "source_pointer": pointer, "what_would_settle_it": settle})

    add("Headline mass", "recomputed", "%.5f" % diverted, "%.5f" % household,
        "Mt air-dry (as-received) cake", "not-comparable",
        "outputs/residential_dung_ledger_2024.csv; outputs/national_dung_variants.csv",
        "nothing - these are a supply-side derivation and a demand-side observation, and "
        "the question is which destinations the difference has, not which number is right")
    add("The difference", "recomputed", "", "%.5f" % unresolved,
        "Mt air-dry", "S-side only",
        "national_dung_variants.csv unresolved_Mt (= diverted - household)",
        "a destination for the residual; four are priced and none is adopted")
    add("The difference as a share of the diversion", "recomputed", "",
        "%.2f" % (100.0 * unresolved / diverted), "percent of the L-side mass",
        "S-side only", "derived from the two columns beside it", "")
    add("Household share of the diversion", "recomputed", "100.00",
        "%.2f" % (100.0 * household / diverted), "percent", "not-comparable",
        "residential_dung_ledger_2024.csv share_of_diverted", "")

    ash, moisture = _param("dung_ash_frac_dry"), _param("dung_cake_moisture_ar")
    add("Moisture basis", "recomputed",
        "as-received = total solids / (1 - %.2f)" % moisture,
        "total solids = as-received x (1 - %.2f)" % moisture,
        "fraction of as-received mass", "same parameter, opposite direction",
        "residential_params.csv dung_cake_moisture_ar",
        "a measured moisture content for Pakistani formed cake")
    add("Ash fraction binding volatile to total solids", "recomputed",
        "%.2f of dry matter" % ash, "not used - S observes formed cake",
        "fraction of dry matter", "L-side only",
        "residential_params.csv dung_ash_frac_dry",
        "a Pakistani ash measurement on formed cake; the published range is 15-35 per cent "
        "of dry matter and the chain is linear in it")

    add("Survey round stability", "recomputed",
        "not applicable",
        "HIES 2018-19 %.3f Mt against HIES 2024-25 %.3f Mt (%+.0f pct)"
        % (_num(hies["hies1819_annual"]) / 1e9, _num(hies["hies2425_annual"]) / 1e9,
           100.0 * (_num(hies["hies2425_annual"]) / _num(hies["hies1819_annual"]) - 1.0)),
        "Mt air-dry", "S-side only",
        "outputs/residential_hies_comparison_2024.csv",
        "a third survey round, or a reconciliation of the two instruments - an 84 per cent "
        "move between rounds is larger than the parameter uncertainty carried on either")
    add("Survey users share", "recomputed", "not applicable",
        "%.2f" % (100.0 * _num(hies["hies2425_users_share"])),
        "percent of weighted households", "S-side only",
        "residential_hies_comparison_2024.csv hies2425_users_share", "")
    add("Ratio of the two readings", "recomputed", "",
        hies["ratio_hies_over_engine"], "S over L", "not-comparable",
        "residential_hies_comparison_2024.csv ratio_hies_over_engine", "")

    # THE FALSIFIABLE ROW. Derived from the survey's own intensity and coverage, so it moves
    # with them: if the diversion were household fuel at the observed per-household rate,
    # the implied coverage is diverted / observed x observed share. The observed quantity is
    # the 2024-25 round AS MEASURED, because the share and the daily quantity are that
    # round's; the reference's interpolated FY2023-24 quantity has no user share of its own.
    share = _num(hies["hies2425_users_share"])
    observed = _num(hies["hies2425_annual"]) / 1e9
    implied_share = share * diverted / observed
    implied_intensity_factor = diverted / observed
    add("Falsifiable implication of configuration L", "recomputed",
        "either %.1f pct of weighted households burn cake at the observed per-household "
        "intensity, or the observed %.2f pct burn %.1f times the observed daily quantity"
        % (100.0 * implied_share, 100.0 * share, implied_intensity_factor),
        "the observed %.2f pct at the observed intensity" % (100.0 * share),
        "percent of weighted households", "L-side claim, S-side observation",
        "derived from residential_hies_comparison_2024.csv (the 2024-25 round as measured) "
        "and the diverted mass",
        "a household fuel-use survey with national coverage of cake burning, or a commercial "
        "cake-fuel survey: L requires one of the two implied facts and both are checkable")

    for r in variants[1:]:
        add("Residual destination priced: %s" % r["destination"], "recomputed",
            "not applicable", r["delta_vs_S_Mt_co2e_AR5"], "Mt CO2e AR5 against S",
            "scenario, beside the total and never inside it",
            "outputs/national_dung_variants.csv#%s" % r["variant_id"],
            r["description"])

    for element, l_side, s_side, unit, comparability, pointer, settle in TRANSCRIBED:
        add(element, "transcribed", l_side, s_side, unit, comparability, pointer, settle)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--check", action="store_true",
                        help="compare the shipped file with a fresh build; write nothing")
    args = parser.parse_args(argv)
    data = rows()
    fresh = table_text(list(FIELDS), data, banner=BANNER.splitlines())
    if args.check:
        held = ""
        if os.path.exists(OUT):
            with open(OUT, encoding="utf-8", newline="") as handle:
                held = handle.read()
        print("dung balance: %s" % ("byte-identical" if held == fresh else "DIFFERS"))
        return 0 if held == fresh else 1
    write_table(OUT, list(FIELDS), data, banner=BANNER.splitlines())
    bases = {}
    for r in data:
        bases[r["row_basis"]] = bases.get(r["row_basis"], 0) + 1
    print("dung balance -> %s" % OUT)
    print("  %d rows (%s); no residual distributed"
          % (len(data), ", ".join("%d %s" % (n, k) for k, n in sorted(bases.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
