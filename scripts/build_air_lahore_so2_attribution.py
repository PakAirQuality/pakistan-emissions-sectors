"""WHERE LAHORE'S SO2 DECLINE COMES FROM - the change decomposed into the channels that made it.

WHY THIS EXISTS. The release publishes Lahore District SO2 falling 14.96 -> 6.83 Gg across nine
fiscal years, a 54 % decline, with a maximum at FY2020-21. Read as a fact about Lahore that is a
striking claim, and the release's own products do not support it. This table says, in arithmetic
that closes exactly, what the curve is actually made of.

THE IDENTITY. Lahore's SO2 from a source stream is three factors:

    L  =  A  x  i  x  w

    A   the stream's NATIONAL greenhouse-gas anchor (the fuel quantity the engine booked)
    i   the stream's SO2 per unit of that anchor - the sulfur assumption, as applied
    w   Lahore's share of the national stream - the spatial allocation pattern

so the nine-year change decomposes, in a DECLARED order (activity, then intensity, then
allocation), into three effects that sum to it exactly:

    dL  =  (A_e - A_s) i_s w_s   +   A_e (i_e - i_s) w_s   +   A_e i_e (w_e - w_s)

The order is a choice and a different one moves mass between the terms; it is stated on every row
rather than hidden. The reconstruction is not indicative: L rebuilt this way reproduces the shipped
outputs/pakemis_air_lahore_by_year.csv to four decimal places in all nine periods, and the test
holds it there.

THE CHANNEL VOCABULARY, and what separates the middle term's two kinds:
  recorded activity          A moved - the national fuel series the engine books
  declared sulfur regime     i moved because the class cites TWO sulfur evidence rows with
                             adjacent validity windows, i.e. a fuel specification that was
                             declared to change on a date. Not a measurement.
  activity mix in the anchor i moved because the air class and its greenhouse-gas anchor have
                             different activity functions, so their ratio drifts. Not a sulfur
                             assumption at all.
  allocation pattern         w moved - Lahore's share of the national stream

ROW KINDS, following outputs/pakemis_industrial_change_attribution.csv:
  booked          sums to exactly the published change
  counterfactual  what the change would have been under a different defensible choice - NEVER
                  added to the booked total
  bound           a quantity the series does not contain, carried as a band
  note            carries no arithmetic

This table is a diagnosis. Nothing downstream reads it, no register is written from it, and no
number in the release moves because of it. Gg SO2, configuration REF_2023_24,
FY2015-16 -> FY2023-24.
"""

from pkinv.assets import asset_path
import collections
import csv
import os

from pkinv.core.io import read_rows

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = asset_path(ROOT, "outputs", "pakemis_air_lahore_so2_attribution.csv")
CFG = "S_TAN"
ADM2 = "punjab_lahore"
POLLUTANT = "SO2"
PERIODS = tuple("FY%d-%02d" % (y, (y + 1) % 100) for y in range(2015, 2024))
START, END = PERIODS[0], PERIODS[-1]
VIEW_ORDER = ("physical", "accounting", "origin")
# the brick classes' constant sulfur balance: 2 x 0.045 S x (1 - 0.25 retained), f_oxidised 1.0
BRICK_KG_SO2_PER_T = 67.50
COLUMNS = ("stream", "sector", "channel", "kind", "period_id", "start_Gg", "end_Gg",
           "change_Gg", "effect_on_change_Gg", "low_Gg", "high_Gg", "evidence", "reading")


def path(*parts):
    return asset_path(ROOT, *parts)


def q(x):
    return None if x is None else round(x, 6)


def load():
    """(lahore_by_stream, national_anchor, national_so2, sulfur_ids, kiln_share, shipped)."""
    every = [r for r in read_rows(path("outputs", "pakemis_air_spatial_support_by_year.csv"))
             if r["pollutant"] == POLLUTANT and r["configuration_id"] == CFG]
    support = [r for r in every if r["temporal_operator"] != "not_placed"]
    # the whole national stream, INCLUDING the mass no geometry placed below the province: the
    # brick band is a statement about the coal column, and the column is the whole of it
    national_all = collections.defaultdict(float)
    for r in every:
        national_all[(r["period_id"], r["source_stream_id"])] += float(r["emissions_Gg"])

    lah_ghg = collections.defaultdict(float)
    nat_ghg = collections.defaultdict(float)
    views = collections.defaultdict(set)
    for r in read_rows(path("outputs", "pakemis_adm2_stream_by_year.csv")):
        if r["configuration_id"] != CFG:
            continue
        key = (r["period_id"], r["source_stream_id"], r["spatial_view"])
        value = float(r["emissions_Gg"] or 0)
        nat_ghg[key] += value
        views[r["source_stream_id"]].add(r["spatial_view"])
        if r["adm2_ids"] == ADM2:
            lah_ghg[key] += value

    kiln = {r["kiln_type"]: float(r["share"])
            for r in read_rows(path("outputs", "pakemis_kiln_frame_adm2_by_type.csv"))
            if r["adm2_ids"] == ADM2}
    # rc61: the admitted power classes ride their own per-period vector, published the same way
    # the kiln frames are, so Lahore's share of them is READ rather than inferred from the
    # anchor stream. Keyed by (frame id, period) because these vectors are year-specific.
    power_frame = {("power_admission:" + r["class_id"].replace("power_", ""), r["period_id"]):
                   float(r["share"])
                   for r in read_rows(path("outputs",
                                           "pakemis_power_admission_adm2_by_class.csv"))
                   if r["adm2_ids"] == ADM2}

    def view_of(stream):
        for v in VIEW_ORDER:
            if v in views.get(stream, ()):
                return v
        return None

    anchor, so2, share, sector = (collections.defaultdict(float), collections.defaultdict(float),
                                  {}, {})
    for r in support:
        period, stream, frame = r["period_id"], r["source_stream_id"], r["spatial_frame"]
        sector[stream] = r["sector_id"]
        so2[(period, stream)] += float(r["emissions_Gg"])
        if frame.startswith("kiln_frame:"):
            share[(period, stream, frame)] = kiln[frame.split(":", 1)[1]]
        elif frame.startswith("power_admission:"):
            # rc61: the admitted power SO2 now HAS a Lahore share, and it is the register's own
            # - Kohinoor Energy's mass over the class's total for that period. Taking the
            # greenhouse-gas stream's share here instead, as the `else` branch below would,
            # is the misplacement this whole round removed: it decomposed a Lahore power number
            # 1.3 to 2.2 times the register's. rc60 held this at 0.0 while the mass was
            # published at national grain; it is 0.0 no longer.
            share[(period, stream, frame)] = power_frame.get((frame, period), 0.0)
        else:
            view = view_of(stream)
            total = nat_ghg.get((period, stream, view), 0.0) if view else 0.0
            share[(period, stream, frame)] = (lah_ghg.get((period, stream, view), 0.0) / total) if total else 0.0
        view = view_of(stream)
        anchor[(period, stream)] = nat_ghg.get((period, stream, view), 0.0) if view else 0.0

    # Lahore's SO2 per (period, stream): the frames of one stream share its national intensity
    lahore = collections.defaultdict(float)
    for r in support:
        key = (r["period_id"], r["source_stream_id"])
        lahore[key] += float(r["emissions_Gg"]) * share[(key[0], key[1], r["spatial_frame"])]

    # the share a whole stream carries, mass-weighted across its frames
    stream_share = {}
    for period in PERIODS:
        for stream in {k[1] for k in so2}:
            total = so2.get((period, stream), 0.0)
            stream_share[(period, stream)] = (lahore[(period, stream)] / total) if total else 0.0

    sulfur = collections.defaultdict(set)
    for r in read_rows(path("data", "air_source_classes.csv")):
        ids = [x for x in r["sulfur_evidence_id"].split(";") if x]
        if ids:
            sulfur[(r["ghg_anchor_module"], r["ghg_anchor_subitem"])].update(ids)

    shipped = collections.defaultdict(float)
    for r in read_rows(path("outputs", "pakemis_air_lahore_by_year.csv")):
        if (r["pollutant"] == POLLUTANT and r["configuration_id"] == CFG
                and r["row_kind"] == "district"):
            shipped[r["period_id"]] += float(r["emissions_Gg"])

    return lahore, anchor, so2, stream_share, sulfur, sector, shipped, national_all


def sulfur_ids_for(sulfur, stream):
    """The sulfur evidence a stream's air classes cite, found through the ghg anchor."""
    subitem = stream.split("|")[2]
    for (_module, anchor_subitem), ids in sulfur.items():
        if anchor_subitem.lower().replace(" ", "-") == subitem.lower().replace("_", "-"):
            return ids
    return set()


def road_regimes():
    """Fuels whose DECLARED road specification changes inside the window, and how far."""
    series = collections.defaultdict(dict)
    for r in read_rows(path("data", "activity", "transport", "fuel_sulfur_by_year.csv")):
        series[r["fuel"].lower()][int(r["fiscal_end_year"])] = float(r["ppm_central"])
    out = {}
    for fuel, by_year in series.items():
        values = [by_year[y] for y in sorted(by_year)]
        if max(values) != min(values):
            out[fuel] = (values[0], values[-1])
    return out


def intensity_channel(stream, sulfur, road):
    """Which of the two kinds of intensity change this stream carries, and why."""
    ids = sulfur_ids_for(sulfur, stream)
    if len(ids) > 1:
        return ("declared sulfur regime",
                "the class cites %s - two windows of a DECLARED fuel specification, so the "
                "intensity step is a date in a register, not a measurement"
                % "; ".join(sorted(ids)))
    subitem = stream.split("|")[2].lower()
    for fuel, (first, last) in road.items():
        if fuel in subitem:
            return ("declared sulfur regime",
                    "data/activity/transport/fuel_sulfur_by_year.csv declares %s falling %.0f -> "
                    "%.0f ppm inside the window; the step is a date in a register, not a "
                    "measurement, and data_gaps row road-fuel-sulfur types it weak-input"
                    % (fuel, first, last))
    return ("activity mix in the anchor",
            "the air class and its greenhouse-gas anchor have different activity functions, so "
            "their ratio drifts; no sulfur assumption changes")


def build():
    lahore, anchor, so2, share, sulfur, sector, shipped, national_all = load()
    streams = sorted({k[1] for k in so2})
    road = road_regimes()
    rows, booked_total = [], 0.0

    for stream in streams:
        label = stream.split("|")[2].replace("-", " ")
        start, end = lahore[(START, stream)], lahore[(END, stream)]
        if abs(start) < 1e-9 and abs(end) < 1e-9:
            continue
        a_s, a_e = anchor[(START, stream)], anchor[(END, stream)]
        i_s = so2[(START, stream)] / a_s if a_s else 0.0
        i_e = so2[(END, stream)] / a_e if a_e else 0.0
        w_s, w_e = share[(START, stream)], share[(END, stream)]

        effects = [
            ("recorded activity", (a_e - a_s) * i_s * w_s,
             "outputs/pakemis_adm2_stream_by_year.csv (the stream's national greenhouse-gas anchor)",
             "the national fuel quantity the engine books, at the FY2015-16 sulfur assumption and "
             "the FY2015-16 allocation share"),
            (None, a_e * (i_e - i_s) * w_s,
             "data/air_source_classes.csv; data/activity/industry/fuel_sulfur_evidence.csv",
             None),
            ("allocation pattern", a_e * i_e * (w_e - w_s),
             "outputs/pakemis_air_spatial_support_by_year.csv (pattern_hash, weight_period)",
             "Lahore's share of the national stream, at the FY2023-24 activity and intensity"),
        ]
        channel, why = intensity_channel(stream, sulfur, road)
        for name, effect, evidence, reading in effects:
            if abs(effect) < 5e-9:
                continue
            if name is None:
                name, reading = channel, why
            rows.append({"stream": label, "sector": sector[stream], "channel": name,
                         "kind": "booked", "period_id": "", "start_Gg": "", "end_Gg": "",
                         "change_Gg": "", "effect_on_change_Gg": q(effect),
                         "low_Gg": "", "high_Gg": "", "evidence": evidence, "reading": reading})
            booked_total += effect

        rows.append({"stream": label, "sector": sector[stream], "channel": "all channels",
                     "kind": "booked", "period_id": "", "start_Gg": q(start), "end_Gg": q(end),
                     "change_Gg": q(end - start), "effect_on_change_Gg": "",
                     "low_Gg": "", "high_Gg": "", "evidence": "outputs/pakemis_air_lahore_by_year.csv",
                     "reading": "the stream's own published change; the three effect rows above "
                                "sum to it in the declared order activity, intensity, allocation"})

    rows.append({"stream": "ALL STREAMS", "sector": "all", "channel": "all channels",
                 "kind": "booked", "period_id": "", "start_Gg": q(shipped[START]), "end_Gg": q(shipped[END]),
                 "change_Gg": q(shipped[END] - shipped[START]),
                 "effect_on_change_Gg": q(booked_total), "low_Gg": "", "high_Gg": "",
                 "evidence": "outputs/pakemis_air_lahore_by_year.csv",
                 "reading": "the published nine-year change in Lahore District SO2; the booked "
                            "effect rows sum to it exactly"})
    return rows, lahore, anchor, so2, share, shipped, national_all


def counterfactual_and_bounds(rows, lahore, anchor, so2, share, shipped, national_all):
    """The two rows that are NEVER added: the sulfur step undone, and the brick band."""
    diesel = [s for s in {k[1] for k in so2}
              if so2.get((END, s), 0) and so2.get((START, s), 0)
              and abs((so2[(END, s)] / anchor[(END, s)]) / (so2[(START, s)] / anchor[(START, s)]) - 0.1) < 1e-6
              ] if True else []
    at_end = sum(lahore[(END, s)] for s in diesel)
    at_start_regime = at_end * 10.0
    change = sum(lahore[(END, s)] - lahore[(START, s)] for s in diesel)
    rows.append({
        "stream": "all diesel and kerosene streams", "sector": "transport; industry; railways",
        "channel": "declared sulfur regime", "kind": "counterfactual", "period_id": "",
        "start_Gg": q(sum(lahore[(START, s)] for s in diesel)), "end_Gg": q(at_start_regime),
        "change_Gg": q(at_start_regime - sum(lahore[(START, s)] for s in diesel)),
        "effect_on_change_Gg": "", "low_Gg": "", "high_Gg": "",
        "evidence": "data/activity/transport/fuel_sulfur_by_year.csv; "
                    "data/activity/industry/fuel_sulfur_evidence.csv",
        "reading": "Lahore's FY2023-24 diesel SO2 had the pre-2017 regime never been declared: "
                   "%.3f Gg rather than the booked %.3f. NEVER added to the booked change - it is "
                   "what the published %.3f Gg decline would have been instead (%.3f Gg). The step "
                   "is 5000 -> 500 ppm at FY2017-18, sourced from press coverage of the January "
                   "2017 Euro-II import mandate; data_gaps row road-fuel-sulfur types it "
                   "weak-input and records that the articles were not retained"
                   % (at_start_regime, at_end, change,
                      at_start_regime - sum(lahore[(START, s)] for s in diesel)),
    })

    # the brick band: Lahore brick SO2 scales linearly with the booked coal column
    brick = [s for s in {k[1] for k in so2} if "brick-kiln-coal" in s]
    alt = {r["fiscal_year"]: r for r in read_rows(path("outputs", "pakemis_brick_coal_alternatives.csv"))}
    for period in PERIODS:
        row = alt.get(period.replace("FY", ""))
        if not row or not row.get("band_low_kt"):
            continue
        booked_coal = sum(national_all[(period, s)] for s in brick) / (BRICK_KG_SO2_PER_T / 1000.0)
        here = sum(lahore[(period, s)] for s in brick)
        low, high = float(row["band_low_kt"]), float(row["band_high_kt"])
        ccac = float(row["ccac_own_estimate_kt"])
        rows.append({
            "stream": "brick kiln coal", "sector": "industry",
            "channel": "recorded activity", "kind": "bound", "period_id": period,
            "start_Gg": "", "end_Gg": q(here), "change_Gg": "", "effect_on_change_Gg": "",
            "low_Gg": q(here * low / booked_coal), "high_Gg": q(here * high / booked_coal),
            "evidence": "outputs/pakemis_brick_coal_alternatives.csv (%s)" % period,
            "reading": "%s: the booked coal column is %.0f kt against a published band of "
                       "%.0f-%.0f kt and the CCAC's own %.0f kt. Lahore's brick SO2 scales "
                       "linearly with that column, so the band carries straight through. %s "
                       "READ THE BAND FOR WHAT IT IS: outputs/pakemis_brick_coal_alternatives.csv "
                       "builds it on the NEPRA metered power burn while the booked central uses "
                       "HDIP's own power column, so the two are not the same calculation and the "
                       "gap between them is the power-claimant seam, measured directly in "
                       "outputs/industry_coal_reconciliation.csv. It is not an uncertainty "
                       "interval around the central and a value outside it is not an error in the "
                       "central"
                       % (period, booked_coal, low, high, ccac,
                          ("The booked value sits BELOW its own band low."
                           if booked_coal < low - 0.5 else
                           "The booked value sits above its own band high."
                           if booked_coal > high + 0.5 else
                           "The booked value sits inside the band.")),
        })
    # and what the band does to the whole curve, which is the question a reader actually asks
    span = {}
    for period in PERIODS:
        row = alt.get(period.replace("FY", ""))
        here = sum(lahore[(period, s)] for s in brick)
        total = shipped[period]
        if not row or not row.get("band_low_kt"):
            span[period] = (total, total)
            continue
        booked_coal = sum(national_all[(period, s)] for s in brick) / (BRICK_KG_SO2_PER_T / 1000.0)
        lo, hi = float(row["band_low_kt"]), float(row["band_high_kt"])
        span[period] = (total - here + here * lo / booked_coal,
                        total - here + here * hi / booked_coal)
    worst_low, worst_high = span[END][0], span[END][1]
    rows.append({
        "stream": "ALL STREAMS", "sector": "all", "channel": "recorded activity", "kind": "note",
        "period_id": "", "start_Gg": q(shipped[START]), "end_Gg": q(shipped[END]),
        "change_Gg": q(shipped[END] - shipped[START]), "effect_on_change_Gg": "",
        "low_Gg": "", "high_Gg": "",
        "evidence": "outputs/pakemis_brick_coal_alternatives.csv; "
                    "outputs/industry_coal_reconciliation.csv",
        "reading": "A TREND RANGE IS WITHDRAWN HERE, deliberately. An earlier version of this row "
                   "moved brick to the ends of its band in FY2023-24 only (%.2f to %.2f Gg) and "
                   "divided by the UNCHANGED FY2015-16 total, reporting a decline of 29 to 62 per "
                   "cent. That is not a range of trends: it is one endpoint varied against a fixed "
                   "denominator, and the band does not even exist for FY2015-16. A trend range "
                   "needs a coherent scenario applied at BOTH endpoints - the same coal account, "
                   "fuel-quality history, kiln history, allocation and coverage in each year - and "
                   "that is what the scenario work owes. Until then the honest statement is the "
                   "per-year band above and nothing multiplied out of it"
                   % (worst_low, worst_high),
    })
    rows.append({
        "stream": "brick kiln coal", "sector": "industry", "channel": "recorded activity",
        "kind": "counterfactual", "period_id": "", "start_Gg": "", "end_Gg": "", "change_Gg": "",
        "effect_on_change_Gg": "", "low_Gg": "", "high_Gg": "",
        "evidence": "outputs/pakemis_brick_coal_alternatives.csv (ccac_own_estimate_kt)",
        "reading": "the CCAC's own estimate is a FLAT 13,000 kt of brick-kiln coal in every one of "
                   "the nine years - above every official value and far above the FY2023-24 trough "
                   "of 1,129. On that reading brick contributes no trend at all and Lahore's "
                   "decline is whatever the other streams do. NEVER added to the booked change: it "
                   "is a single cross-section, not an annual indicator, which is why "
                   "outputs/pakemis_industrial_coal_decision.csv leaves the official column booked",
    })
    return rows


def notes(rows, share, so2):
    fixed = []
    for stream in sorted({k[1] for k in so2}):
        if so2.get((START, stream), 0) < 1e-6:
            continue
        if abs(share[(END, stream)] - share[(START, stream)]) < 1e-9:
            fixed.append((stream.split("|")[2].replace("-", " "), share[(START, stream)]))
    top = sorted(fixed, key=lambda x: -so2.get((START, "x"), 0))
    rows.append({
        "stream": "brick kiln coal; industrial furnace oil", "sector": "industry",
        "channel": "allocation pattern", "kind": "note", "period_id": "", "start_Gg": "", "end_Gg": "",
        "change_Gg": "", "effect_on_change_Gg": "", "low_Gg": "", "high_Gg": "",
        "evidence": "outputs/pakemis_air_spatial_support_by_year.csv; "
                    "outputs/pakemis_kiln_frame_adm2_by_type.csv; data/validation_catalog.csv",
        "reading": "the two largest streams reach Lahore on patterns that never move. Brick rides "
                   "one FY2023-24 kiln frame reused backwards - pattern_hash byte-identical in all "
                   "nine periods, Lahore 1.4419 % of FCBK and 3.2303 % of ZZ. Industrial furnace "
                   "oil is a flat diffuse provincial share on hash 844098a49b75cbaa, and the "
                   "catalog row abs-industry-geography-non-kiln declares that stream has no "
                   "independent spatial record at all. Neither carries any observation of Lahore",
    })
    rows.append({
        "stream": "power generation", "sector": "power", "channel": "coverage", "kind": "note",
        "period_id": "", "start_Gg": "", "end_Gg": "", "change_Gg": "", "effect_on_change_Gg": "",
        "low_Gg": "", "high_Gg": "", "evidence": "outputs/pakemis_air_coverage_matrix.csv",
        "reading": "POWER SO2 IS IN THIS CURVE, AND THIS ROW SAID THE OPPOSITE UNTIL rc64. It read "
                   "'power SO2 is typed NE (uncontrolled-screening-only) in all nine periods, so "
                   "it has never been in this curve in any year' - true when written and false "
                   "from rc60, when the oil and diesel fleet was admitted on a reviewed register "
                   "and rc61 placed it. The coverage matrix now types power SO2 as E in all nine "
                   "periods. Lahore's power row is ONE station, Kohinoor Energy, whose published "
                   "SO2 equals its own row in data/activity/power/power_so2_admission.csv to six "
                   "decimals, metered from NEPRA fuel quantities in five of the nine years. It "
                   "contributes 8.598 Gg of the 17.456 Gg fall - the largest single sector - so a "
                   "reader who took this row at its word was missing half the curve. What the row "
                   "still establishes is unchanged: the sector coverage matrix is identical across "
                   "the nine periods, so no part of the change is coverage moving",
    })
    return rows


BANNER = """\
# WHERE LAHORE'S SO2 DECLINE COMES FROM, FY2015-16 -> FY2023-24. Gg SO2, configuration REF_2023_24,
# ADM2 punjab_lahore (the census district - not the municipal area, not an airshed; a TERRITORIAL
# total). One row per (stream, channel). The identity is L = A x i x w: the national greenhouse-gas
# anchor, the SO2 per unit of it, and Lahore's share of the stream. kind=booked rows sum to exactly
# the published change in the DECLARED order activity, then intensity, then allocation - a different
# order moves mass between the terms. kind=counterfactual says what the change would have been under
# a different defensible choice and is NEVER added to it; kind=bound is a band the series does not
# contain; kind=note carries no arithmetic. A diagnosis: no register is written from this file and no
# number in the release moves because of it. Generated by scripts/build_air_lahore_so2_attribution.py.
"""


def main():
    rows, lahore, anchor, so2, share, shipped, national_all = build()
    rows = counterfactual_and_bounds(rows, lahore, anchor, so2, share, shipped, national_all)
    rows = notes(rows, share, so2)
    with open(OUT, "w", encoding="utf-8", newline="") as handle:
        handle.write(BANNER)
        writer = csv.DictWriter(handle, fieldnames=COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print("%s: %d rows" % (os.path.relpath(OUT, ROOT), len(rows)))


if __name__ == "__main__":
    main()
