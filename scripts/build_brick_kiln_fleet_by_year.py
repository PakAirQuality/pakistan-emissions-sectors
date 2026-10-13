"""THE KILN FLEET AS A YEAR AXIS, and the fuel a production model puts on it (rc62).

WHAT WAS WRONG. `outputs/pakemis_brick_activity_reconstruction.csv` carries `punjab_kilns =
10394` in every one of the nine fiscal years, and `air_pollutants.kiln_shares()` splits FCBK
from zig-zag on undated counts, so Lahore's brick SO2 was HDIP's national coal column times a
multiplier - 0.016859065 - that is identical to nine decimal places in all nine years. The
allocation channel of the Lahore attribution is exactly zero for this stream, by construction.

WHAT THIS IS, AND WHAT IT IS NOT. It is not a reconstructed series: nothing here is booked and
HDIP stays the activity the engine burns. It is the fleet's evidence laid out on the year axis
it actually has, so that the shape of what is missing is visible instead of implied.

THE GRAIN IS DISTRICT x YEAR x READING, not kiln x year. Every observation held is a DISTRICT
count - BKOAP's roll, Hamdani's detections aggregated, CMI's establishments - so a kiln-year
table would repeat a district number 11,272 times and dress a district observation as a
per-object one. The register's own `kiln_id` is not a key anything can be joined on across
dates: no held source tracks an individual kiln through time.

TWO READINGS, NEVER AVERAGED. `bkoap` is an owners' association roll from November 2020 which
counts "converted OR BEING CONVERTED" together; `hamdani` is a July 2023 morphological
classification from Sentinel-2. Between them the Punjab fleet falls 10,394 -> 9,491 and the
zig-zag share falls 22.4 -> 13.7 percent. A conversion programme is one-way, so a falling
zig-zag share is not a measurement of conversion reversing - it is proof the two are counting
different things. Each reading is carried at its own date and CARRIED FLAT elsewhere, with the
carry named on every row. Interpolating between them would manufacture the one quantity this
table exists to say nobody holds.

THE FUEL MODEL, AS A BAND WITH NO CENTRAL. M_coal = kilns x operating_days x t_coal_per_kiln_day.
Two of the three terms are measured and Pakistani: FCBK 4.6 t of coal per kiln-day against
25,000 bricks, zig-zag 3.25 t against 21,000 (Hasnain et al. 2026, 60 kilns at Faisalabad, 2023,
+/-20 percent, already in data/industry_params.csv). THE THIRD IS OPEN AND THE TWO HELD SOURCES
DIFFER BY A FACTOR OF 2.9: Hamdani's supplement declares 215 firing days a year (365 less about
150 of monsoon and smog closure), while ICIMOD's 440-kiln survey figure of 328.2 t per kiln-year
implies 73.9 days at the fleet-weighted rate. Both are carried as ends. Neither is a central and
no midpoint is taken - an arbitrary midpoint is never a candidate under the decision rule this
feeds (scripts/build_industrial_coal_decision.py).

Usage:  python3 scripts/build_brick_kiln_fleet_by_year.py [--check]
Writes: outputs/pakemis_brick_kiln_fleet_by_year.csv
"""
import os
import sys
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path

from pkinv.core.io import read_rows, write_or_check                      # noqa: E402

OBSERVATIONS = asset_path(ROOT, "data", "activity", "industry",
                            "brick_kiln_fleet_observations.csv")
PARAMS = asset_path(ROOT, "data", "industry_params.csv")
OUT = asset_path(ROOT, "outputs", "pakemis_brick_kiln_fleet_by_year.csv")
PERIODS = tuple("FY%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024))

# The two operating-day ends, and where each comes from. See the docstring.
DAYS = {
    "icimod_implied": (73.9, "ICIMOD's 440-kiln 2020 survey prints 328.2 t of coal per "
                             "kiln-year; at the fleet-weighted 4.443 t/kiln-day that is 73.9 "
                             "firing days - an IMPLIED figure, never stated as a season"),
    "hamdani_declared": (215.0, "Hamdani et al. supplement p.2 declares 215 firing days a year "
                                "(365 less roughly 150 of monsoon and smog closure) - a DECLARED "
                                "assumption behind that paper's own emission estimates"),
}
READING_DATE = {"bkoap": ("2020-11", "FY2020-21"), "hamdani": ("2023-07", "FY2023-24")}

FIELDS = ("period_id", "adm2_id", "reading", "observation_date", "year_basis",
          "kilns_total", "kilns_zigzag", "kilns_fcbk", "zigzag_share",
          "coal_kt_low", "coal_kt_high", "coal_kt_central",
          "days_low_basis", "days_high_basis", "note")


def params():
    out = {}
    for r in read_rows(PARAMS):
        out[r["param"]] = float(r["value"])
    return out


def observations():
    """{reading: {adm2_id: (total, zigzag)}} from the dated observation table."""
    out = defaultdict(dict)
    for r in read_rows(OBSERVATIONS):
        if r["geography_level"] != "district" or not r["adm2_id"] or r["adm2_id"] == "unresolved":
            continue
        reading = "bkoap" if r["observation_date"] == "2020-11" else "hamdani"
        zz = float(r["kilns_zigzag"]) if r["kilns_zigzag"] else 0.0
        out[reading][r["adm2_id"]] = (float(r["kilns_total"]), zz)
    return out


def build():
    p = params()
    fcbk_rate = p["brick_fcbtk_coal_t_per_kiln_day"]
    zz_rate = p["brick_zigzag_coal_t_per_kiln_day"]
    obs = observations()
    lo_days, lo_why = DAYS["icimod_implied"]
    hi_days, hi_why = DAYS["hamdani_declared"]

    rows = []
    for reading in ("bkoap", "hamdani"):
        date, own_period = READING_DATE[reading]
        for adm2_id, (total, zz) in sorted(obs[reading].items()):
            fcbk = total - zz
            for period in PERIODS:
                carried = period != own_period
                # kt of coal = kilns x days x t/kiln-day / 1000
                def coal(days):
                    return (fcbk * days * fcbk_rate + zz * days * zz_rate) / 1000.0
                rows.append({
                    "period_id": period, "adm2_id": adm2_id, "reading": reading,
                    "observation_date": date,
                    "year_basis": ("carried from %s - the fleet was counted once and this "
                                   "period is not that year" % date) if carried
                                  else "the observation's OWN period",
                    "kilns_total": "%.1f" % total, "kilns_zigzag": "%.1f" % zz,
                    "kilns_fcbk": "%.1f" % fcbk,
                    "zigzag_share": "%.4f" % (zz / total) if total else "",
                    "coal_kt_low": "%.3f" % coal(lo_days),
                    "coal_kt_high": "%.3f" % coal(hi_days),
                    "coal_kt_central": "",
                    "days_low_basis": lo_why, "days_high_basis": hi_why,
                    "note": ("NOTHING HERE IS BOOKED. The engine burns HDIP's national brick "
                             "column; this is the fleet's own evidence beside it. The two "
                             "readings are not averaged - see the module docstring for why a "
                             "falling zig-zag share proves they count different things."),
                })
    rows.sort(key=lambda r: (r["reading"], r["period_id"], r["adm2_id"]))
    return rows


def main():
    rows = build()
    write_or_check(OUT, FIELDS, rows, check="--check" in sys.argv, lineterminator="\n")
    print("%s: %d rows" % (os.path.relpath(OUT, ROOT), len(rows)))
    for reading in ("bkoap", "hamdani"):
        sub = [r for r in rows if r["reading"] == reading and r["period_id"] == "FY2020-21"]
        kilns = sum(float(r["kilns_total"]) for r in sub)
        lo = sum(float(r["coal_kt_low"]) for r in sub)
        hi = sum(float(r["coal_kt_high"]) for r in sub)
        print("   %-9s %7.0f kilns -> coal %7.0f - %7.0f kt/yr  (Punjab, %d districts)"
              % (reading, kilns, lo, hi, len(sub)))
    lah = [r for r in rows if r["adm2_id"] == "punjab_lahore" and r["period_id"] == "FY2020-21"]
    print()
    for r in lah:
        print("   Lahore %-9s %6s kilns, %5s zig-zag -> %6.2f - %6.2f kt coal"
              % (r["reading"], r["kilns_total"], r["kilns_zigzag"],
                 float(r["coal_kt_low"]), float(r["coal_kt_high"])))


if __name__ == "__main__":
    main()
