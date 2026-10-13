"""Electricity generation, resolved into the twelve months of a fiscal year.

THE ABSENCE THIS LAYER USED TO DECLARE WAS NOT ONE. Its previous docstring said gas, coal and
bagasse are flat and T4 because "no plant-month generation series was obtained", which was
true of this repository and not of the world: PBS publishes Electricity Generation Data plant
by plant and month by month, and has since FY1999-2000. It is read now, in
pkinv.sectors.power.pbs_generation, and it carries coal and gas in FY2018-19 through FY2020-21
- the years where the flat line was most wrong, because Pakistani demand peaks hard in summer
and the thermal fleet follows it.

WHICH YEAR YOU ASK FOR DECIDES WHICH SOURCE ANSWERS:

  * FY2015-16 to FY2020-21 - PBS plant-month generation, where enough of a subitem's annual
    control sits in plants the publication actually labels. The timing target is GENERATION.
  * FY2021-22 onward - NEPRA's SIR Detail-of-Generation listings, the same panel's second
    lane (scripts/ingest_sir_generation.py), carrying grid coal (TE2) and gas (TE3, the
    RLNG/HSD group assigned by annual-control bound). Coal and gas ONLY, deliberately: the
    liquid fuels already ride the OCAC Total Power customer-class row in these years with
    T1/T2 months, and a TE3 generation shape must not displace that - the SIR furnace-oil
    series is a published crosscheck against the OCAC profile instead.
  * The OCAC Total Power row itself - a fuel SALE, reaching only furnace oil and diesel.
    Furnace oil's profile is the sharpest in the inventory, from under a third of a percent
    of the year in one month to twenty-three percent in another, because oil-fired plant is
    dispatched at the margin.
  * Anything neither held source covers stays flat and says so. FY2016-17 and FY2017-18 gas is the
    clearest case: PBS names the fuel of barely a third of gas generation in those years,
    because it never labels Guddu, Jamshoro, Muzaffargarh or K-Electric and the plant ledger
    starts in FY2019-20; FY2021-22 gas is another - the annual-control bound misses the 95
    percent rule by one point there, so the year is refused rather than fitted.

CAPTIVE SELF-GENERATION IS NOT ON THIS PROFILE AND MUST NOT BE. An industrial plant burning
its own gas behind the meter follows its host industry, not national dispatch.

THE SUFFIX SAYS FY2023-24 AND SO DO THE ROWS. It read fy2024_25 for one release: power
keys its year by the fiscal year's START (2023 means July 2023 to June 2024) and the
suffix rename treated every sector as END-keyed, so the two fiscal-start sectors - this one
and aviation - were the only two labelled a year forward. The months inside never moved;
they are 202307 to 202406 throughout. A filename that disagrees with its own rows is the
kind of thing a reader trusts and a test does not read, which is why it lasted.

Usage:  python3 -m pkinv.sectors.power.monthly
Writes: outputs/power_monthly_fy2023_24.csv
"""

from pkinv.assets import asset_path
import os

from pkinv.core import monthly as core_monthly
from pkinv.core import pbs_qim
from pkinv.core import ocac_monthly
from pkinv.paths import OUTPUTS
from pkinv.sectors.power import engine, pbs_generation
from pkinv.sectors.power.data import PowerData

FY_START = 2023
OUT = asset_path(OUTPUTS, "power_monthly_fy2023_24.csv")

# Streams whose fuel OCAC's Total Power row actually covers.
LIQUID_PREFIXES = ("Furnace Oil", "Diesel Oil")


def rows(data=None, fy_start=FY_START):
    data = data if data is not None else PowerData()
    components = engine.build_components(data)

    # PBS's plant-month generation, where the year has it and the subitem is covered well
    # enough to be worth applying. It comes first because it times GENERATION rather than a
    # fuel sale, and because a fuel it does not cover simply is not in `available` - so the
    # branches below still handle everything else exactly as they did.
    available = pbs_generation.shapes(fy_start)
    observed = [c for c in components if pbs_generation.shape_for(c, available)]
    rest = [c for c in components if c not in observed]
    panel = ocac_monthly.covers(
        ocac_monthly.TOTAL_POWER, ocac_monthly.FURNACE_OIL + ocac_monthly.DIESEL, fy_start)
    liquid = [c for c in rest if panel and c["subitem"].startswith(LIQUID_PREFIXES)]
    # Bagasse cogeneration follows the crushing season, and since rc30 the season
    # is READ rather than assumed: PBS QIM's sugar months (the 1-3 group row, all
    # nine editions) time the mills' own bagasse combustion at TE2. A year the
    # QIM does not cover stays flat with the refusal stated below.
    bagasse = [c for c in rest if c not in liquid and "agasse" in c["subitem"]
               and pbs_qim.covers(pbs_qim.SUGAR, fy_start)]
    other = [c for c in rest if c not in liquid and c not in bagasse]

    out = []
    if observed:
        out.extend(core_monthly.apply_profile(
            observed, None, fy_start,
            temporal_method=lambda c, _m: pbs_generation.shape_for(c, available)[1],
            profile_for=lambda c: pbs_generation.shape_for(c, available)[0],
            basis=lambda c: pbs_generation.shape_for(c, available)[2]))
    if liquid:
        shares, method = ocac_monthly.profile(
            ocac_monthly.TOTAL_POWER, ocac_monthly.FURNACE_OIL + ocac_monthly.DIESEL, fy_start)
        out.extend(core_monthly.apply_profile(
            liquid, shares, fy_start, temporal_method=ocac_monthly.method_of(method),
            basis="OCAC Total Power customer class, FO+HSD, monthly editions differenced"))
    if bagasse:
        out.extend(core_monthly.apply_profile(
            bagasse, pbs_qim.profile(pbs_qim.SUGAR, fy_start), fy_start,
            temporal_method="T2",
            basis="PBS QIM sugar months (group row 1-3): the crushing season the "
                  "mills' own production prints, timing their bagasse cogeneration - "
                  "own-year, twelve observed months"))
    if other:
        out.extend(core_monthly.apply_profile(
            other, core_monthly.days_weighted_profile(fy_start), fy_start,
            temporal_method="T4",
            basis="flat: no monthly series reaches this stream in this year - neither "
                  "lane of the plant-month generation record (PBS, then the NEPRA SIR "
                  "listings) labels enough of this fuel or deliberately never shapes it "
                  "(captive plant does not follow grid dispatch), and the OCAC panel "
                  "covers only the liquid fuels"))
    return components, out


def main():
    components, month_rows = rows()
    core_monthly.write_layer(OUT, month_rows, components)
    flat_share = sum(r["co2e_Mt_AR5"] for r in month_rows if r["temporal_method"] == "T4")
    total = sum(r["co2e_Mt_AR5"] for r in month_rows)
    print("power monthly layer -> %s" % OUT)
    print("  %d rows; closes exactly" % len(month_rows))
    print("  %.0f%% of the sector carries a FLAT declared profile - the gas and coal "
          "rows" % (100 * flat_share / total))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
