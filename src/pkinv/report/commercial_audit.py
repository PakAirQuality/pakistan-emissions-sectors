"""Commercial and institutional combustion (1.A.4.a): the audit the register never had.

THE FINDING (the second review's 8.6). Every other missing category in this inventory is a
DECLARED absence -- an NE row with a gap entry. 1.A.4.a was not: no completeness row, no
gap entry, no code in the EDGAR domain map, so the Buildings coverage line read "2 of 2
codes estimated" while a whole category-class fell through it. This module is the audit of
every commercial-class activity row the repository holds, each with a disposition:
included elsewhere, genuinely unestimated (with a screening magnitude where the held
activity permits one), or unresolvable within the held classes.

WHAT THE AUDIT FOUND, row by row:
- OGRA Table 3.31 carries a COMMERCIAL gas class -- 45 MMCFD, held since the fugitives
  round -- counted once as post-meter LEAKAGE (1.B.2.b.vi) and never as combustion.
  Screened here at ~0.88 Mt CO2e.
- OGRA Figure 5.2 puts COMMERCIAL LPG at ~520 kt (a chart-read value, held only in a
  parameter's source note). Screened at ~1.55 Mt CO2e. Together the two quantifiable
  streams put 1.A.4.a above the 1 Mt materiality line -- a MATERIAL silent omission.
- OCAC's petroleum partition has NO commercial class: commercial liquid fuel is
  distributed inside Road (retail pumps), DOMESTIC and Government; separating it has not
  been attempted here because it needs the HDIP commercial energy balance, which has not
  been acquired. The Government HSD/petrol rows (booked to "various") bound the
  institutional analogue at ~0.44 Mt if wholly stationary, which they are not.
- Pakistan's own BUR-1 filed commercial at 3.8 Mt CO2e for FY2017-18; its newer filings
  publish 1.A.4 only as an aggregate. The screening sum sits below the filed figure, as a
  two-stream floor should.

Everything here is screening arithmetic on held rows, outside every total; the register
row this audit feeds stays NE, with the reasons split honestly: the two gas/LPG streams
await the next reference-year rebuild (the totals are frozen through the release-candidate
series), and the petroleum share awaits the HDIP commercial energy balance.

THE WAVE 4 CONFIGURATION. The quantifiable floor (gas + LPG, ~2.43 Mt) ships as the
JOINT configuration `commercial_institutional_in_scope` so the coverage matrix can say
"screened" instead of bare NE for 1.A.4.a, and a reader can price the omission. The
adjustment is the FLOOR only: the government-liquids bound is not added (its class
includes fleets and aviation and its stationary share is unresolved), the petroleum
share stays unresolvable, and the BUR-1 3.8 benchmark sits above the floor as a
benchmark should. The gas stream's post-meter LEAK stays booked in 1.B.2.b.vi either
way - combustion and leakage are different processes, so the inclusion double-counts
nothing.

Usage:  python3 -m pkinv.report.commercial_audit
Writes: outputs/commercial_institutional_audit_2024.csv,
        outputs/commercial_scope_configuration_2024.csv
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import DATA, OUTPUTS
from pkinv.core.io import write_table

# Screening constants, cited; deliberately not in any factor registry (the category is
# outside every total). Gas conversion is the residential sector's derived gross-to-net
# basis (data/activity/residential/fuel_supply.csv note); factors are IPCC 2006 Vol 2
# Tables 2.2/2.3 and Table 1.2.
GAS_TJ_PER_MMCF = 0.94957
GAS_CO2_KG_TJ = 56100.0
LPG_CHART_READ_KT = 520.0        # OGRA SoIR 2023-24 Figure 5.2, Commercial bar
LPG_NCV_TJ_GG = 47.3
LPG_CO2_KG_TJ = 63100.0
HSD_NCV_TJ_GG = 43.0
HSD_CO2_KG_TJ = 74100.0
MS_NCV_TJ_GG = 44.3
MS_CO2_KG_TJ = 69300.0
BUR1_COMMERCIAL_MT = 3.8         # data/activity/residential/official_benchmarks.csv,
                                 # bur1res note: 1A4 breakdown, commercial, FY2017-18


def _commercial_gas_mmcfd():
    path = asset_path(DATA, "activity", "fugitives", "post_meter_end_use_2023_24.csv")
    for r in _activity_rows(path, comments=False):
        if r["end_use"] == "Commercial":
            return float(r["throughput_mmcfd"])
    raise KeyError("no Commercial row in the OGRA post-meter table; the audit has lost "
                   "its gas stream")


def _government_kt(fuel):
    path = asset_path(OUTPUTS, "transport_fuel_ledger_2024.csv")
    for r in _activity_rows(path, comments=False):
        if r["claimant"] == "Government" and r["fuel"] == fuel:
            return float(r["kt"])
    raise KeyError(fuel)


def rows():
    gas_mmcfd = _commercial_gas_mmcfd()
    gas_tj = gas_mmcfd * 365.0 * GAS_TJ_PER_MMCF
    gas_mt = gas_tj * GAS_CO2_KG_TJ / 1e9
    lpg_tj = LPG_CHART_READ_KT * LPG_NCV_TJ_GG
    lpg_mt = lpg_tj * LPG_CO2_KG_TJ / 1e9
    gov_hsd_kt = _government_kt("Diesel")
    gov_ms_kt = _government_kt("Petrol")
    gov_mt = (gov_hsd_kt * HSD_NCV_TJ_GG * HSD_CO2_KG_TJ
              + gov_ms_kt * MS_NCV_TJ_GG * MS_CO2_KG_TJ) / 1e9

    return [
        {"stream": "Commercial piped gas", "activity": gas_mmcfd, "unit": "MMCFD",
         "source": "OGRA SoIR 2023-24 Table 3.31 (held: "
                   "data/activity/fugitives/post_meter_end_use_2023_24.csv)",
         "disposition": "leakage-counted, combustion-unestimated",
         "screening_Mt_co2e": round(gas_mt, 3),
         "note": "the volume is in the inventory ONCE, as 1.B.2.b.vi post-meter leakage "
                 "(6.1 t CH4 per million m3); its combustion CO2 has never been booked "
                 "anywhere. CO2-only screen; trace gases add under one percent"},
        {"stream": "Commercial LPG", "activity": LPG_CHART_READ_KT, "unit": "kt",
         "source": "OGRA SoIR 2023-24 Figure 5.2 (chart-read; held only in "
                   "data/residential_params.csv's source note)",
         "disposition": "genuinely unestimated",
         "screening_Mt_co2e": round(lpg_mt, 3),
         "note": "a bar-chart reading with no published table behind it - the same "
                 "declared weakness the residential domestic share carries; OGRA's "
                 "Commercial bar includes small catering some inventories book as "
                 "residential"},
        {"stream": "Commercial petroleum (retail classes)", "activity": "", "unit": "",
         "source": "OCAC sectoral sales (held: "
                   "data/activity/transport/ocac_sectoral_annual.csv)",
         "disposition": "unresolvable within held classes",
         "screening_Mt_co2e": "",
         "note": "OCAC's exhaustive partition has NO commercial class: commercial liquid "
                 "fuel sits inside Road (retail pumps), DOMESTIC and Government; "
                 "separating it needs the HDIP commercial energy balance, which has "
                 "not been acquired"},
        {"stream": "Government liquid fuels", "activity": round(gov_hsd_kt + gov_ms_kt, 1),
         "unit": "kt", "source": "OCAC Total Government rows (held; booked to 'various' "
                                 "in the transport fuel ledger)",
         "disposition": "held-unassigned, bounded",
         "screening_Mt_co2e": round(gov_mt, 3),
         "note": "the institutional analogue: at most this much CO2e if wholly "
                 "stationary, which it is not (the class includes military and "
                 "government fleets and aviation); an upper bound on the institutional "
                 "share inside it, not a screen of it"},
        {"stream": "BUR-1 filed commercial", "activity": "", "unit": "",
         "source": "Pakistan BUR-1 1.A.4 breakdown, FY2017-18 (held: "
                   "data/activity/residential/official_benchmarks.csv, bur1res)",
         "disposition": "benchmark",
         "screening_Mt_co2e": BUR1_COMMERCIAL_MT,
         "note": "Pakistan's own filed commercial figure; the two-stream screen above "
                 "is a floor and sits below it, as a floor should. Newer filings "
                 "publish 1.A.4 only as an aggregate"},
    ]


def quantified_floor_mt():
    """The sum of the two screened streams - the category's countable floor."""
    out = rows()
    return round(out[0]["screening_Mt_co2e"] + out[1]["screening_Mt_co2e"], 3)


FIELDS = ("stream", "activity", "unit", "source", "disposition", "screening_Mt_co2e",
          "note")


def configuration_rows():
    """The reference/alternative pair national_configurations reads: the floor of the
    two screened streams as a signed scope adjustment, the fgas-screening pattern."""
    floor = quantified_floor_mt()
    return [
        {"configuration": "reference", "adjustment_Mt_co2e": 0.0,
         "note": "1.A.4.a stays NE in the reference; the audit rows above are the "
                 "evidence state"},
        {"configuration": "commercial_institutional_in_scope",
         "adjustment_Mt_co2e": floor,
         "note": "the two-stream quantifiable FLOOR (commercial piped gas + chart-read "
                 "LPG) booked into 1.A.4.a; the petroleum share stays unresolvable "
                 "within held classes and the government-liquids bound is deliberately "
                 "not added, so this is a floor, not the category. Pakistan's own "
                 "BUR-1 filed 3.8 Mt above it"},
    ]


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    out = rows()
    path = asset_path(OUTPUTS, "commercial_institutional_audit_2024.csv")
    write_table(path, FIELDS, out, lineterminator="\n")
    config_path = asset_path(OUTPUTS, "commercial_scope_configuration_2024.csv")
    write_table(config_path, ("configuration", "adjustment_Mt_co2e",
                                          "note"), configuration_rows(), lineterminator="\n")
    print("1.A.4.a scope configuration -> %s" % config_path)
    print("1.A.4.a audit -> %s" % path)
    for r in out:
        print("  %-38s %-38s %s" % (r["stream"][:38], r["disposition"],
                                    r["screening_Mt_co2e"]))
    print("  quantifiable floor: %.3f Mt CO2e - above the 1 Mt materiality line"
          % quantified_floor_mt())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
