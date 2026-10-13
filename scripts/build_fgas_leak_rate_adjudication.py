#!/usr/bin/env python3
"""Does the F-gas bank's single leak rate per stratum survive IPCC's own sub-application bands?

    python3 scripts/build_fgas_leak_rate_adjudication.py
    -> outputs/pakemis_fgas_leak_rate_adjudication.csv

THE QUESTION. The species-resolved HFC bank (outputs/ippu_hfc_species_bank.csv, rc46
Wave 4) runs five strata, and each applies ONE operating loss fraction for all years and
all species: refrigeration 8.0 %/yr, stationary AC 6.0 %, mobile AC 15.0 %, aerosol
50.0 %, fire protection 3.0 %. IPCC 2006 Vol 3 Chapter 7 Table 7.9 does not publish a
rate per stratum of that shape - it publishes one per SUB-APPLICATION, eight of them for
refrigeration and air-conditioning, and their operation-emission bands do not agree with
each other. So a lumped stratum is a weighted guess across sub-applications, and the
question this screening answers is whether the guess can be right for the parts.

WHAT IT FINDS, and the three cases are different.

  mobile AC maps ONE-TO-ONE onto Table 7.9's Mobile A/C (10-20 %/yr). The shipped 15.0 %
  is the band's midpoint and nothing is lumped. The rate is defensible as it stands.

  stationary AC lumps TWO sub-applications - Chillers (2-15 %) and Residential and
  Commercial A/C including Heat Pumps (1-10 %). Their bands overlap over 2-10 %, the
  shipped 6.0 % is inside BOTH, so the lumping cannot be shown to matter: whatever the
  split, 6 % is an admissible rate for either part.

  refrigeration lumps FIVE, and their bands span 0.1 % to 50 % with no common value:
  Domestic 0.1-0.5, Stand-alone Commercial 1-15, Medium & Large Commercial 10-35,
  Transport 15-50, Industrial including cold storage 7-25. The shipped 8.0 % lies OUTSIDE
  two of the five - it is 16x to 80x above domestic refrigeration's whole band and below
  transport refrigeration's whole band - so for those parts the single rate is not merely
  uncertain, it is inadmissible. This is the one stratum where a split nobody holds
  decides the answer, and the screening prices exactly that.

HOW IT PRICES. The bank is a recursion, not a multiplier: a leak rate removes gas from
the bank it also emits from, so a rate ten times smaller does NOT give emissions ten
times smaller. The envelope is therefore computed by re-running the shipped kernel with
one stratum's operating_loss_fraction replaced, never by scaling the published number.
The arithmetic is pkinv.sectors.ippu.hfc_bank's own: this script imports it rather than
restating it, and asserts the unmodified re-run reproduces the shipped file, so a change
to the kernel cannot leave this screening quietly describing the old one.

SCOPE. 2.F contributes ZERO to every national total and still does; the species bank is
itself a screening configuration awaiting the activation review. Nothing here enters a
total, no parameter is changed and no pin moves. The point of the file is that the
published screening's own leak rate is a decision, visibly, with the mass it carries
beside it - and that the decision is open for one stratum and closed for the other two.

NOT ADJUDICATED. Table 7.9 governs refrigeration and air-conditioning only. The aerosol
(50 %) and fire-protection (3 %) strata are governed elsewhere in Chapter 7 and are left
alone; both are also empty from 2020 on, so neither touches the latest-year total.
"""
import csv
import io
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.core.io import write_table                                    # noqa: E402
from pkinv.sectors.ippu import hfc_bank                                  # noqa: E402
from pkinv.sectors.ippu.fgases import run_bank                           # noqa: E402
from collections import defaultdict                                      # noqa: E402

# Filled from the shipped file's own latest year before any stratum is priced.
REFERENCE_YEAR_PROBE = [None]

OUT = os.path.join(ROOT, "outputs", "pakemis_fgas_leak_rate_adjudication.csv")
SHIPPED = os.path.join(ROOT, "outputs", "ippu_hfc_species_bank.csv")
PAGE = "IPCC 2006 Vol 3 Ch 7 Table 7.9 p.7.51-7.52 (data/raw/ipcc/ipcc2006_V3_7_Ch7_ODS_Substitutes.pdf)"

# Table 7.9's operation-emission column, read from the held PDF: (sub-application, x_min, x_max).
TABLE_7_9 = {
    "refrigeration": [
        ("Domestic Refrigeration", 0.1, 0.5),
        ("Stand-alone Commercial Applications", 1.0, 15.0),
        ("Medium & Large Commercial Refrigeration", 10.0, 35.0),
        ("Transport Refrigeration", 15.0, 50.0),
        ("Industrial Refrigeration incl. Food Processing and Cold Storage", 7.0, 25.0),
    ],
    "stationary AC": [
        ("Chillers", 2.0, 15.0),
        ("Residential and Commercial A/C, incl. Heat Pumps", 1.0, 10.0),
    ],
    "mobile AC": [
        ("Mobile A/C", 10.0, 20.0),
    ],
}
# Strata Table 7.9 does not govern, declared rather than silently skipped.
OUT_OF_TABLE = ("aerosol", "fire protection")
CRT_CELLS = "Table2(II).B-Hs2!E54 (stock) and H54 (product life factor)"


def crt_official_reading():
    """The CRT's own 2.F.1.a ACTIVITY cells, which the shipped extraction drops.

    outputs/ippu_unfccc_crt_fgas_species_2022.csv keeps the three EMISSIONS columns
    (J/K/L) and discards the activity block (D/E/F) and the implied factors (G/H/I). The
    emissions alone cannot say that the whole national F-gas inventory is one percent of
    a declared 23.7-tonne stock, which is the sentence this screening sits beside, so the
    two cells are read here from the same held workbook through the sector module's own
    hashing helper - not re-extracted into a parallel copy of a shipped product.
    """
    from openpyxl import load_workbook
    from pkinv.sectors.ippu import official_reporting as ipr

    _package, payload, package_hash, workbook_hash = ipr._hashes(ipr.CRT_SOURCE)
    sheet = load_workbook(io.BytesIO(payload), data_only=True,
                          read_only=True)["Table2(II).B-Hs2"]
    stock, factor, species = sheet["E54"].value, sheet["H54"].value, sheet["B54"].value
    emitted = sheet["K54"].value
    if not isinstance(stock, (int, float)) or not isinstance(factor, (int, float)):
        raise SystemExit(
            "the CRT's 2.F.1.a activity cells are no longer numeric (%r, %r); the "
            "screening's official-reading row rests on them" % (stock, factor))
    return {"species": str(species).strip(), "stock_t": float(stock),
            "factor_pct": float(factor), "emitted_t": float(emitted),
            "year": int(sheet["M1"].value), "package_sha256": package_hash,
            "workbook_sha256": workbook_hash}


def shipped_rates():
    """{application: operating_loss_fraction} from the bank's own input, one per stratum."""
    rates = {}
    for row in hfc_bank.read_rows(hfc_bank.ROWS):
        rate = float(row["operating_loss_fraction"])
        seen = rates.setdefault(row["application"], rate)
        if abs(seen - rate) > 1e-12:
            raise SystemExit(
                "%s carries more than one operating loss fraction (%s and %s); this "
                "screening's premise is that each stratum applies exactly one, and that "
                "premise has stopped holding" % (row["application"], seen, rate))
    return rates


def totals_with(application=None, rate=None):
    """{year: Mt CO2e AR5} from the shipped build, optionally overriding one stratum's rate."""
    original = hfc_bank.read_rows

    def patched(path):
        for row in original(path):
            if application is not None and row["application"] == application:
                row = dict(row)
                row["operating_loss_fraction"] = "%.10f" % rate
            yield row

    hfc_bank.read_rows = patched
    try:
        rows = hfc_bank.build()
    finally:
        hfc_bank.read_rows = original
    out = {}
    for row in rows:
        out[int(row["year"])] = out.get(int(row["year"]), 0.0) + float(row["emissions_Mt_co2e_AR5"])
    return out


def stratum_channels(application, rate=None):
    """{channel: Mt CO2e AR5} for one stratum in the reference year, plus its closing bank.

    The point of the decomposition: with recovery_fraction zero everywhere, gas the
    operating channel does not leak is still emitted at retirement, so the leak rate
    moves the CHANNEL MIX far more than it moves the total. Reported rather than
    asserted, because "the rate decides the mass" is the intuition and it is wrong here.
    """
    original = hfc_bank.read_rows

    def patched(path):
        for row in original(path):
            if row["application"] == application and rate is not None:
                row = dict(row)
                row["operating_loss_fraction"] = "%.10f" % rate
            yield row

    hfc_bank.read_rows = patched
    try:
        by_stratum = defaultdict(list)
        for row in hfc_bank.read_rows(hfc_bank.ROWS):
            by_stratum[(row["species"], row["application"])].append(row)
        out = defaultdict(float)
        for (species, app), rows in by_stratum.items():
            if app != application or rows[0].get("is_hfc") == "no":
                continue
            gwp = hfc_bank.gwp_ar5(species)
            bank, resolved = 0.0, []
            for row in sorted(rows, key=lambda value: int(value["year"])):
                row = dict(row)
                frac = float(row["retired_charge_t"].split(":", 1)[1])
                row["retired_charge_t"] = "%.6f" % (bank * frac)
                row["supplied_charge_t"] = (float(row["new_equipment_charge_t"])
                                            + float(row["servicing_charge_t"]))
                resolved.append(row)
                supplied = row["supplied_charge_t"] * (1.0 - float(row["manufacturing_loss_fraction"]))
                bank = max((bank + supplied) * (1.0 - float(row["operating_loss_fraction"]))
                           - float(row["retired_charge_t"]), 0.0)
            ledgers, _components = run_bank(species, app, resolved)
            for ledger in ledgers:
                if ledger["year"] != REFERENCE_YEAR_PROBE[0]:
                    continue
                for key, value in ledger.items():
                    if key.endswith("_t") and isinstance(value, float):
                        out[key] += value * gwp / 1e6
        return out
    finally:
        hfc_bank.read_rows = original


def shipped_latest():
    """The latest-year total as the SHIPPED FILE states it, read from disk."""
    per_year = {}
    with open(SHIPPED, encoding="utf-8") as handle:
        for row in csv.DictReader(line for line in handle if not line.startswith("#")):
            per_year[int(row["year"])] = (per_year.get(int(row["year"]), 0.0)
                                          + float(row["emissions_Mt_co2e_AR5"]))
    year = max(per_year)
    return year, per_year[year], per_year


def main():
    year, disk_total, disk_by_year = shipped_latest()
    REFERENCE_YEAR_PROBE[0] = year
    rerun = totals_with()
    # The re-run must reproduce the shipped file before any override is believable.
    for check_year, value in disk_by_year.items():
        if abs(rerun[check_year] - value) > 5e-6:
            raise SystemExit(
                "the unmodified re-run does not reproduce the shipped bank for %d "
                "(%.6f re-run vs %.6f on disk); regenerate "
                "outputs/ippu_hfc_species_bank.csv before trusting this screening"
                % (check_year, rerun[check_year], value))

    rates = shipped_rates()
    per_app = {}
    with open(SHIPPED, encoding="utf-8") as handle:
        for row in csv.DictReader(line for line in handle if not line.startswith("#")):
            if int(row["year"]) == year:
                per_app[row["application"]] = (per_app.get(row["application"], 0.0)
                                               + float(row["emissions_Mt_co2e_AR5"]))

    rows = []
    for application in sorted(TABLE_7_9):
        bands = TABLE_7_9[application]
        shipped_pct = rates[application] * 100.0
        inside = [name for name, lo, hi in bands if lo <= shipped_pct <= hi]
        outside = [name for name, lo, hi in bands if not lo <= shipped_pct <= hi]
        envelope_lo = min(lo for _n, lo, _h in bands)
        envelope_hi = max(hi for _n, _l, hi in bands)
        at_lo = totals_with(application, envelope_lo / 100.0)[year]
        at_hi = totals_with(application, envelope_hi / 100.0)[year]
        channels = {band: stratum_channels(application, pct / 100.0)
                    for band, pct in (("lo", envelope_lo), ("ship", shipped_pct),
                                      ("hi", envelope_hi))}
        verdict = ("one-to-one" if len(bands) == 1 else
                   "lumped, admissible" if not outside else "lumped, inadmissible for a part")
        rows.append({
            "row_kind": "bank_stratum",
            "stratum": application,
            "shipped_operating_loss_pct_yr": "%.1f" % shipped_pct,
            "table_7_9_sub_applications": len(bands),
            "sub_applications_whose_band_contains_the_rate": len(inside),
            "sub_applications_whose_band_excludes_it": "; ".join(outside) or "none",
            "band_envelope_pct_yr": "%.1f-%.1f" % (envelope_lo, envelope_hi),
            "verdict": verdict,
            "stratum_emissions_Mt_co2e_AR5": "%.5f" % per_app.get(application, 0.0),
            "national_2_F_screening_at_shipped_rate_Mt": "%.5f" % disk_total,
            "at_envelope_low_Mt": "%.5f" % at_lo,
            "at_envelope_high_Mt": "%.5f" % at_hi,
            "stratum_operating_channel_Mt": "%.5f" % channels["ship"]["operating_emissions_t"],
            "stratum_retirement_channel_Mt": "%.5f" % channels["ship"]["retirement_emissions_t"],
            "stratum_at_envelope_low_Mt": "%.5f" % channels["lo"]["total_emissions_t"],
            "stratum_at_envelope_high_Mt": "%.5f" % channels["hi"]["total_emissions_t"],
            "operating_channel_low_to_high_Mt": "%.5f-%.5f" % (
                channels["lo"]["operating_emissions_t"], channels["hi"]["operating_emissions_t"]),
            "retirement_channel_low_to_high_Mt": "%.5f-%.5f" % (
                channels["lo"]["retirement_emissions_t"], channels["hi"]["retirement_emissions_t"]),
            "closing_bank_low_to_high_Mt": "%.3f-%.3f" % (
                channels["hi"]["bank_end_t"], channels["lo"]["bank_end_t"]),
            "crt_declared_stock_t": "n.a.",
            "crt_emitted_t": "n.a.",
            "reference_year": year,
            "source": PAGE,
            "note": {
                "one-to-one":
                    "the stratum IS a Table 7.9 sub-application; the shipped rate is "
                    "inside its published band and nothing is lumped, so the single rate "
                    "is a reading of the table rather than a weighting of it",
                "lumped, admissible":
                    "the lumped sub-applications' bands overlap and the shipped rate is "
                    "inside every one of them, so no split of this stratum could make the "
                    "rate wrong - the lumping is invisible to the answer. Admissible is "
                    "NOT narrow: this stratum's envelope can be wider than an "
                    "inadmissible one's, because band width and band disagreement are "
                    "different quantities and only the second is a defect",
                "lumped, inadmissible for a part":
                    "the lumped bands have no common value and the shipped rate falls "
                    "outside at least one of them, so for that part the rate is not "
                    "uncertain but wrong; the split is unheld and it decides the mass in "
                    "stratum_emissions_Mt_co2e_AR5",
            }[verdict],
        })

    for application in OUT_OF_TABLE:
        rows.append({
            "row_kind": "bank_stratum",
            "stratum": application,
            "shipped_operating_loss_pct_yr": "%.1f" % (rates[application] * 100.0),
            "table_7_9_sub_applications": 0,
            "sub_applications_whose_band_contains_the_rate": "n.a.",
            "sub_applications_whose_band_excludes_it": "n.a.",
            "band_envelope_pct_yr": "n.a.",
            "verdict": "not governed by this table",
            "stratum_emissions_Mt_co2e_AR5": "%.5f" % per_app.get(application, 0.0),
            "national_2_F_screening_at_shipped_rate_Mt": "%.5f" % disk_total,
            "at_envelope_low_Mt": "NE",
            "at_envelope_high_Mt": "NE",
            "stratum_operating_channel_Mt": "NE",
            "stratum_retirement_channel_Mt": "NE",
            "stratum_at_envelope_low_Mt": "NE",
            "stratum_at_envelope_high_Mt": "NE",
            "operating_channel_low_to_high_Mt": "NE",
            "retirement_channel_low_to_high_Mt": "NE",
            "closing_bank_low_to_high_Mt": "NE",
            "crt_declared_stock_t": "n.a.",
            "crt_emitted_t": "n.a.",
            "reference_year": year,
            "source": PAGE,
            "note": "Table 7.9 covers refrigeration and air-conditioning only; this "
                    "stratum's rate comes from elsewhere in Chapter 7 and is left alone. "
                    "It is also empty in the reference year, so it moves no total here",
        })

    crt = crt_official_reading()
    rows.append({
        "row_kind": "official_reading",
        "stratum": "CRT %d, 2.F.1.a commercial refrigeration" % crt["year"],
        "shipped_operating_loss_pct_yr": "%.1f" % crt["factor_pct"],
        "table_7_9_sub_applications": 1,
        "sub_applications_whose_band_contains_the_rate": 1,
        "sub_applications_whose_band_excludes_it": "none",
        "band_envelope_pct_yr": "1.0-15.0",
        "verdict": "one-to-one",
        "stratum_emissions_Mt_co2e_AR5": "%.5f" % (crt["emitted_t"] * 12400.0 / 1e6),
        "national_2_F_screening_at_shipped_rate_Mt": "%.5f" % disk_total,
        "at_envelope_low_Mt": "NE",
        "at_envelope_high_Mt": "NE",
        "stratum_operating_channel_Mt": "%.5f" % (crt["emitted_t"] * 12400.0 / 1e6),
        "stratum_retirement_channel_Mt": "NE",
        "stratum_at_envelope_low_Mt": "NE",
        "stratum_at_envelope_high_Mt": "NE",
        "operating_channel_low_to_high_Mt": "NE",
        "retirement_channel_low_to_high_Mt": "NE",
        "closing_bank_low_to_high_Mt": "NE",
        "crt_declared_stock_t": "%.10f" % crt["stock_t"],
        "crt_emitted_t": "%.12f" % crt["emitted_t"],
        "reference_year": crt["year"],
        "source": "Pakistan CRT %d %s; package sha256 %s" % (
            crt["year"], CRT_CELLS, crt["package_sha256"][:12]),
        "note": "PAKISTAN'S OWN OFFICIAL READING, beside the bank it is being compared "
                "with. All of category 2.F is one species, %s, at %.9f t - exactly "
                "%.1f%% of a declared %.10f t operating stock (crt_declared_stock_t) - filed under "
                "2.F.1.a commercial refrigeration with every other species and "
                "sub-category NE or NO. %s is an HCFC-22 by-product and a cascade "
                "low-temperature refrigerant, not a commercial refrigerant, so the "
                "placement is a reporting artefact; the 1%% factor is admissible for the "
                "sub-category it was filed under, which is why the verdict is one-to-one "
                "and the defect is the SPECIES rather than the rate. Pakistan's first "
                "BTR then books 2.F, 2.C, 2.E and 2.G all at zero"
                % (crt["species"], crt["emitted_t"], crt["factor_pct"], crt["stock_t"],
                   crt["species"]),
    })

    banner = [
        "F-GAS LEAK-RATE ADJUDICATION: the species bank's one rate per stratum against",
        "IPCC Table 7.9's rate per SUB-APPLICATION, read from the held PDF. A screening",
        "beside a screening - 2.F contributes zero to every national total and this file",
        "changes no parameter. The envelope columns RE-RUN the shipped kernel with one",
        "rate replaced, because a bank is a recursion and cannot be rescaled.",
        "Reference year %d: shipped %.5f Mt CO2e AR5. The last row is not a stratum but"
        % (year, disk_total),
        "Pakistan's own official reading of 2.F, carried here so the comparison is visible.",
    ]
    write_table(OUT, list(rows[0]), rows, banner=banner)
    print("F-gas leak-rate adjudication -> %s" % OUT)
    for row in rows:
        print("   %-14s %5s%%/yr  %-30s %s Mt  envelope %s-%s"
              % (row["stratum"], row["shipped_operating_loss_pct_yr"], row["verdict"],
                 row["stratum_emissions_Mt_co2e_AR5"], row["at_envelope_low_Mt"],
                 row["at_envelope_high_Mt"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
