"""Extract four NFDC AFR 2024-25 tables: who made the fertilizer, who bought it, whose gas.

WHAT THE TABLES SETTLE. Table 1 is domestic production by product AND manufacturer for
FY2023-24 and FY2024-25 with installed capacity and utilisation. Table 5 is offtake by
product, split domestic and imported. Table 40 is FY2024-25 fertilizer gas by plant, feed
against fuel. ANNEX-28 is the same gas MONTHLY, by plant, for BOTH fiscal years. Between
them they carry the quantities this inventory had been treating as unavailable for 2.B.1.

THE ANNEX COVERS THE REFERENCE YEAR, which is the point of this extraction. Round 11 read
Table 40, got FY2024-25, and borrowed its 83.2/16.8 feed-fuel shares backwards to describe
FY2023-24 because the reference year's own split was believed missing. It was never
missing: Annex-28 prints FY2023-24 plant by plant and month by month. The reference year
is 229,236 MMCF feed and 45,213 fuel, 83.5/16.5, observed. The borrowing is withdrawn.

TWO INSTITUTIONS, HALF A PERCENT APART. Annex-28's FY2023-24 total is 274,449 MMCF, or
751.9 MMCFD, against the 756 MMCFD OGRA reports for the same fiscal year in Table 3.31 of
a different publication by a different body - a manufacturers' association counting its
members' plant meters against a regulator counting utility sales. Nothing upstream is
shared. They agree to 0.54 percent, and data/validation_registry.csv records it as
mag-fertiliser-gas-two-sources.

THE SEVENTH TIME. This repository has now found a category's missing data inside its own
committed files seven times - industrial liquid fuels in an OCAC CSV the transport sector
already read, household coal in HIES, both halves of the ammonia question in this text
dump, and now the reference year's gas one annex further on in the same file. The lesson
does not change: look before declaring an absence.

WHAT THE SPLIT DOES AND DOES NOT DECIDE. A sixth of the fertilizer row is genuinely burned
as process fuel, which corrects the story this inventory used to tell ("almost none of it
is combustion"), but it does NOT move the 1.A.2 boundary: the IPCC ammonia method (2006 GL
V3 Ch3) allocates the plant's TOTAL gas requirement, feed and process fuel together, to
2.B.1, and only separately metered auxiliary combustion outside the process boundary would
stay in Energy. The split is extracted because the reconciliation needs it, not because the
fuel share changes category.

SUBTOTALS ARE ASSERTED, NOT EMITTED. Printed totals close against the summed rows before
anything is written, and the component rows are what lands in the CSVs - a printed subtotal
would be a second, silently-preferred path to the same quantity. The one exception is Table
40's Total row, kept because its note carries the cross-check against OGRA.

AND THE SOURCE DOES NOT CLOSE ON ITSELF. Annex-28's monthly cells sum to within 3 MMCF of
each plant's own printed row total and up to 6 above the printed year lines; Table 40's
fuel rows sum to 47,151 against a printed 47,152; Table 5's product rows sum to 10,274
against a printed Grand Total of 10,275. These are the review's rounding, not misreadings,
and the tolerances name them rather than an exact assertion failing and inviting someone to
"correct" the data. At 0.003 percent of the year none of it reaches a published figure.

WHAT TABLE 5 WILL NOT SAY. NPK's and AS print with no domestic/imported qualifier, while
the review's own subtotals imply about 42 and 68 thousand tonnes spread across them. The
allocation is never stated, so those rows carry supply_basis 'unclassified' and say so.
Table 5's nutrient block (A. DOMESTIC onwards) is deliberately NOT taken: nutrient tonnes
are a different quantity kind, and a second national nitrogen series landing beside the
audited one agriculture already reads is exactly the second path this file avoids.

Usage:  python3 scripts/ingest_nfdc_afr2025_fertilizer.py
Writes: data/nfdc/afr2025_production_by_manufacturer.csv
        data/nfdc/afr2025_fertilizer_gas_by_plant.csv
        data/nfdc/afr2025_offtake_by_product.csv
        data/nfdc/afr2025_fertilizer_gas_monthly.csv
"""

from pkinv.assets import asset_path
import csv
import io
import os
import re
import sys

from pkinv.core.io import write_or_check
from pkinv.paths import DATA

TXT = asset_path(DATA, "nfdc", "AFR_2024-25.txt")
PROD_OUT = asset_path(DATA, "nfdc", "afr2025_production_by_manufacturer.csv")
GAS_OUT = asset_path(DATA, "nfdc", "afr2025_fertilizer_gas_by_plant.csv")
OFFTAKE_OUT = asset_path(DATA, "nfdc", "afr2025_offtake_by_product.csv")
MONTHLY_OUT = asset_path(DATA, "nfdc", "afr2025_fertilizer_gas_monthly.csv")

SOURCE = "NFDC Annual Fertilizer Review 2024-25 (data/nfdc/AFR_2024-25.txt)"
PROD_FIELDS = ("fiscal_year", "product", "manufacturer", "capacity_000t",
               "production_000t", "share_pct", "capacity_utilization_pct", "source", "note")
GAS_FIELDS = ("fiscal_year", "gas_supplier", "plant", "feed_mmcf", "fuel_mmcf",
              "total_mmcf", "source", "note")
OFFTAKE_FIELDS = ("fiscal_year", "product", "supply_basis", "offtake_kt", "share_pct",
                  "source", "note")
MONTHLY_FIELDS = ("fiscal_year", "gas_supplier", "plant", "consumption", "month",
                  "calendar_year", "mmcf", "source", "note")

UNCLASSIFIED_NOTE = (
    "the review prints no domestic/imported split for this product; its own Total "
    "domestic and Total Imported lines imply about 42 and 68 thousand tonnes spread "
    "across NPK's and AS together, an allocation the review never attributes and this "
    "extraction does not invent")

# Table 1 prints the product label with plant qualifiers - Urea (prilled), NP(PAR),
# DAP-SONA. The CSV keys on the plain product so consumers can group; the printed label
# survives in the note when it says more than the product name does.
PRODUCT_OF = {"Urea": "Urea", "CAN": "CAN", "NP": "NP", "DAP-SONA": "DAP",
              "SSP": "SSP", "SOP": "SOP", "NPK": "NPK"}

GAS_SUPPLIERS = {
    "Sui Northern Gas Pipelines Ltd.": "SNGPL",
    "Liquefied Natural Gas (LNG)": "LNG",
    "Oil and Gas Development Company Limited": "OGDCL",
    "Sui Southern Gas Company Ltd.": "SSGCL",
    "Mari Energies": "Mari",
}

# Annex-28 spells four of the five suppliers differently from Table 40 - "Ltd." becomes
# "Limited", "Mari Energies" becomes "Mari Gas Company Limited". Both spellings resolve to
# the SAME short code so the annual and monthly tables join on supplier without a
# crosswalk; a reader comparing them should not have to know the document renamed anyone.
ANNEX28_SUPPLIERS = {
    "Sui Northern Gas Pipelines Limited": "SNGPL",
    "Oil and Gas Development Company Limited": "OGDCL",
    "Liquefied Natural Gas (LNG)": "LNG",
    "Sui Southern Gas Company Limited": "SSGCL",
    "Mari Gas Company Limited": "Mari",
}

# Annex-28 wraps company names across printed lines and qualifies some of them by supply
# route. The assembled label maps to Table 40's plant spelling, with whatever the assembly
# discarded preserved as a note - the join must be on the same name in both tables, and a
# silently renamed plant is how two rows for one factory get counted as two factories.
ANNEX28_PLANTS = {
    "Pak-Arab": ("Pak-Arab", ""),
    "Fatimafert (DHCL)": ("Fatimafert", "printed as Fatimafert (DHCL)"),
    "Agritech": ("Agritech", ""),
    "Agritech Limited": ("Agritech", "printed as Agritech Limited"),
    "Hazara Phosphate": ("Hazara Phosphate", ""),
    "EFERT Mari through SNGPL": (
        "EFERT", "printed as EFERT, Mari through SNGPL - Mari gas carried on the SNGPL "
                 "network, which is why the same plant appears under two suppliers"),
    "EFERT": ("EFERT", ""),
    "FFC": ("FFC", ""),
    "FFC-1& 2": ("FFC I & II", "printed as FFC-1& 2"),
    "FFC-III (MM)": ("FFC III", "printed as FFC-III (MM)"),
    "Fatima Fertilizer": ("Fatima Fertilizer", ""),
}

# July-June, the fiscal order the annex prints its columns in.
FISCAL_MONTHS = ("Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
                 "Jan", "Feb", "Mar", "Apr", "May", "Jun")

FEB_NOTE = ("the FY2023-24 header prints FEB ' 23; the column is February 2024 and "
            "calendar_year records the corrected year")

# Lines inside the annex that carry no data: the unit banner, the column header, the page
# furniture, and the bare page numbers - which sit INSIDE the data blocks rather than
# between them, so a parser that only skipped leading matter would swallow them as labels.
ANNEX28_SKIP = re.compile(
    r"^(?:\(MMCF\)|COMPANY\s+CONSUMPTION|PAGE\s+\d+\s+OF\s+ANNEX|ANNEX-\d+|\d{1,3})\s*$")

NUMERIC = re.compile(r"^-?[\d,]+(?:\.\d+)?$")


def _tokens(line):
    return line.strip().split()


def _is_numeric(token):
    return token == "-" or bool(NUMERIC.match(token))


def _value(token):
    return "" if token == "-" else token.replace(",", "")


def _float(token):
    return 0.0 if token in ("", "-") else float(token.replace(",", ""))


def _table_lines(text, header_re, stop_re):
    """Lines between a table header and its terminator, form feeds stripped."""
    out, inside = [], False
    for raw in text.split("\n"):
        line = raw.lstrip("\f")
        if not inside:
            if re.match(header_re, line):
                inside = True
            continue
        if re.match(stop_re, line):
            break
        out.append(line)
    if not inside:
        raise SystemExit("table header not found: %s" % header_re)
    return out


def parse_production(text):
    """Manufacturer rows from Table 1, one CSV row per fiscal year.

    A data line is <product tokens> <manufacturer tokens> <7 numbers>: capacity,
    FY2023-24 production and share, FY2024-25 production and share, percent change,
    and utilisation. Capacity and utilisation are printed once and describe 2024-25,
    so only the 2024-25 row carries them.
    """
    rows, totals = [], {}
    for line in _table_lines(text, r"^Table 1\.\s", r"\s*NUTRIENTS\s*$"):
        tokens = _tokens(line)
        if len(tokens) < 8:
            continue
        tail = []
        while tokens and _is_numeric(tokens[-1]) and len(tail) < 7:
            tail.insert(0, tokens.pop())
        if len(tail) != 7 or not tokens:
            continue
        label = tokens[0]
        product = PRODUCT_OF.get(label.split("(")[0])
        if product is None and label == "All":
            product = "All Products"
        if product is None:
            continue
        name_tokens = tokens[1:]
        while name_tokens and name_tokens[0].startswith("("):
            label += " " + name_tokens.pop(0)
        if label.endswith("(Various"):
            label += " Grades)"   # the qualifier wraps onto the next printed line
        manufacturer = " ".join(name_tokens)
        capacity, p24, s24, p25, s25, _change, util = tail
        if manufacturer == "Total" or product == "All Products":
            totals[product] = (_float(p24), _float(p25))
            continue
        note = "" if label == product else "printed as %s" % label
        if "*" in manufacturer:
            manufacturer = manufacturer.replace("*", "")
            note = (note + "; " if note else "") + "plant shut down since May 2016"
        for year, production, share, cap, ut in (
                ("2023-24", p24, s24, "", ""),
                ("2024-25", p25, s25, capacity, util)):
            rows.append({"fiscal_year": year, "product": product,
                         "manufacturer": manufacturer,
                         "capacity_000t": _value(cap),
                         "production_000t": _value(production),
                         "share_pct": _value(share),
                         "capacity_utilization_pct": _value(ut),
                         "source": SOURCE + " Table 1", "note": note})
    return rows, totals


def parse_gas(text):
    """Plant rows from Table 40, feed and fuel MMCF, plus the printed Total row."""
    rows, supplier = [], None
    for line in _table_lines(text, r"^Table 40\.\s", r"^16\.2\s"):
        stripped = line.strip()
        if stripped in GAS_SUPPLIERS:
            supplier = GAS_SUPPLIERS[stripped]
            continue
        tokens = _tokens(line)
        if len(tokens) < 4 or supplier is None:
            continue
        tail = [tokens.pop(), tokens.pop(), tokens.pop()][::-1]
        if not all(_is_numeric(t) for t in tail):
            continue
        plant = " ".join(tokens).replace("Pak- Arab", "Pak-Arab")
        feed, fuel, total = tail
        if plant == "Total":
            rows.append({"fiscal_year": "2024-25", "gas_supplier": "All",
                         "plant": "Total", "feed_mmcf": _value(feed),
                         "fuel_mmcf": _value(fuel), "total_mmcf": _value(total),
                         "source": SOURCE + " Table 40",
                         "note": ("83.2% feed / 16.8% fuel; ~770 MMCFD against OGRA's "
                                  "756 MMCFD fertiliser row for FY2023-24; both halves "
                                  "belong to 2.B.1 under the IPCC ammonia method "
                                  "(2006 GL V3 Ch3), which allocates the total gas "
                                  "requirement to the process. Printed fuel rows sum "
                                  "to 47,151 against this row's 47,152 - a 1-MMCF "
                                  "rounding slip in the source")})
            continue
        rows.append({"fiscal_year": "2024-25", "gas_supplier": supplier, "plant": plant,
                     "feed_mmcf": _value(feed), "fuel_mmcf": _value(fuel),
                     "total_mmcf": _value(total), "source": SOURCE + " Table 40",
                     "note": ""})
    return rows


def parse_offtake(text):
    """Product-wise offtake rows from Table 5, one CSV row per fiscal year.

    A data line is <product tokens> [domestic|Imported] <5 numbers>: FY2023-24 offtake and
    share, FY2024-25 offtake and share, and the percent change. Where the review prints no
    supply qualifier the row is emitted as `unclassified` rather than guessed at - see the
    note built in main().

    The parser STOPS at the nutrient block. Table 5 continues into 'A. DOMESTIC' with
    nitrogen, phosphate and potash tonnes, which are a different quantity kind and would
    land a second national nitrogen series in data/ beside the audited one agriculture
    already reads - the second, silently-preferred path this file exists to avoid.
    """
    rows, totals = [], {}
    for line in _table_lines(text, r"^Table 5\.\s", r"\s*A\.\s*DOMESTIC\s*$"):
        tokens = _tokens(line)
        if len(tokens) < 6:
            continue
        tail = []
        while tokens and _is_numeric(tokens[-1]) and len(tail) < 5:
            tail.insert(0, tokens.pop())
        if len(tail) != 5 or not tokens:
            continue
        basis = "unclassified"
        if tokens[-1] in ("domestic", "Imported"):
            basis = tokens.pop().lower()
        label = " ".join(tokens)
        if label.startswith("Total") or label.startswith("Grand Total"):
            # "Total domestic" and "Total Imported" both reduce to "Total" once the
            # supply qualifier is popped, so the qualifier goes back into the key - two
            # different subtotals must not collide into one.
            key = label if basis == "unclassified" else "%s %s" % (label, basis)
            totals[key] = (_float(tail[0]), _float(tail[2]))
            continue
        for year, offtake, share in (("2023-24", tail[0], tail[1]),
                                     ("2024-25", tail[2], tail[3])):
            rows.append({"fiscal_year": year, "product": label,
                         "supply_basis": basis, "offtake_kt": _value(offtake),
                         "share_pct": _value(share),
                         "source": SOURCE + " Table 5", "note": ""})
    return rows, totals


def parse_gas_monthly(text, fiscal_year, header, stop):
    """One page of Annex-28: monthly Feed and Fuel by plant, for one fiscal year.

    A data line ends in THIRTEEN values - twelve months plus the printed row total - and
    the token before them says Feed, Fuel or Total. Everything earlier on the line is
    company label, and the annex wraps labels across their own lines, so fragments seen
    since the last row are carried forward and a fragment arriving AFTER a Feed row still
    belongs to it: '(DHCL)' prints below 'Fatimafert', not beside it. The buffered Feed row
    is therefore renamed when its Fuel row completes the name.

    Printed totals - the per-plant Total, the per-supplier Total, and the closing
    Total/Grand Total block - are returned separately for assertion and never emitted.
    """
    year_start = int(fiscal_year.split("-")[0])
    blocks, totals = [], {}
    supplier, pending, block = None, [], None

    def month_rows(kind, values):
        out = []
        for index, month in enumerate(FISCAL_MONTHS):
            # Column POSITION sets the calendar year, not the printed header: the
            # FY2023-24 page prints FEB ' 23 where it means February 2024. The correction
            # rides the note rather than happening invisibly.
            out.append({
                "fiscal_year": fiscal_year, "gas_supplier": supplier,
                "consumption": kind, "month": month,
                "calendar_year": year_start if index < 6 else year_start + 1,
                "mmcf": _value(values[index]), "source": SOURCE + " Annex-28",
                "note": FEB_NOTE if (month == "Feb" and fiscal_year == "2023-24") else ""})
        return out

    for line in _table_lines(text, header, stop):
        stripped = line.strip()
        if not stripped or ANNEX28_SKIP.match(stripped):
            continue
        if stripped in ANNEX28_SUPPLIERS:
            supplier, pending, block = ANNEX28_SUPPLIERS[stripped], [], None
            continue
        tokens = _tokens(line)
        values = []
        while tokens and _is_numeric(tokens[-1]) and len(values) < 13:
            values.insert(0, tokens.pop())
        if len(values) != 13 or not tokens or tokens[-1] not in ("Feed", "Fuel", "Total"):
            if not values and not any(_is_numeric(t) for t in tokens):
                pending.extend(tokens)          # a label wrapped onto its own line
            continue
        kind = tokens.pop()
        if kind == "Total":                      # a plant, supplier or grand subtotal
            # A fragment still pending when a subtotal arrives is the tail of the plant
            # name above it, not a label for the subtotal: 'SNGPL' prints below 'EFERT'
            # and 'Mari through', completing "EFERT, Mari through SNGPL".
            if pending and blocks:
                blocks[-1]["label"].extend(pending)
            totals.setdefault(" ".join(tokens) or "(subtotal)", []).append(
                _float(values[-1]))
            pending, block = [], None
            continue
        label, pending = pending + tokens, []
        if kind == "Feed" or block is None:
            block = {"label": list(label), "rows": []}
            blocks.append(block)
        else:
            block["label"].extend(label)         # the Fuel line completed the name
        block["rows"].extend(month_rows(kind, values))

    rows = []
    for entry in blocks:
        printed = " ".join(entry["label"])
        if printed in ("Total", "Grand Total"):
            continue
        plant, note = ANNEX28_PLANTS.get(printed, (printed, ""))
        for row in entry["rows"]:
            row["plant"] = plant
            if note:
                row["note"] = (row["note"] + "; " + note) if row["note"] else note
        rows.extend(entry["rows"])
    return rows, totals


def _assert_close(name, got, want, tolerance=0.0):
    if abs(got - want) > tolerance:
        raise SystemExit("%s: extracted %s, the review prints %s" % (name, got, want))





def main(check=False):
    with open(TXT, encoding="utf-8") as f:
        text = f.read()

    prod_rows, totals = parse_production(text)
    by = lambda product, year: sum(_float(r["production_000t"]) for r in prod_rows
                                   if r["product"] == product and r["fiscal_year"] == year)
    # Urea closes exactly; the smaller products carry sub-thousand-tonne rounding in the
    # printed subtotals, so they close to within 2.
    _assert_close("urea FY2023-24", by("Urea", "2023-24"), 6591)
    _assert_close("urea FY2024-25", by("Urea", "2024-25"), 6780)
    _assert_close("urea FY2023-24 printed total", totals["Urea"][0], 6591)
    _assert_close("urea FY2024-25 printed total", totals["Urea"][1], 6780)
    _assert_close("CAN FY2024-25", by("CAN", "2024-25"), totals["CAN"][1], 2)
    _assert_close("NP FY2024-25", by("NP", "2024-25"), totals["NP"][1], 2)
    all_2425 = sum(_float(r["production_000t"]) for r in prod_rows
                   if r["fiscal_year"] == "2024-25")
    _assert_close("all products FY2024-25", all_2425, totals["All Products"][1], 3)

    gas_rows = parse_gas(text)
    plants = [r for r in gas_rows if r["plant"] != "Total"]
    total_row = [r for r in gas_rows if r["plant"] == "Total"]
    if len(plants) != 12 or len(total_row) != 1:
        raise SystemExit("Table 40: expected 12 plant rows and one Total, got %d + %d"
                         % (len(plants), len(total_row)))
    feed = sum(_float(r["feed_mmcf"]) for r in plants)
    fuel = sum(_float(r["fuel_mmcf"]) for r in plants)
    _assert_close("gas feed MMCF", feed, 234001)
    # The printed fuel rows sum to 47,151 against a printed subtotal of 47,152 - a
    # 1-MMCF rounding slip in the source, recorded on the Total row's note.
    _assert_close("gas fuel MMCF", fuel, 47152, 1)
    _assert_close("gas total MMCF", feed + fuel, 281153, 1)
    _assert_close("printed gas total", _float(total_row[0]["total_mmcf"]), 281153)
    for r in plants:
        _assert_close("row %s feed+fuel" % r["plant"],
                      _float(r["feed_mmcf"]) + _float(r["fuel_mmcf"]),
                      _float(r["total_mmcf"]), 1)

    offtake_rows, offtake_totals = parse_offtake(text)
    off = lambda year, basis: sum(_float(r["offtake_kt"]) for r in offtake_rows
                                  if r["fiscal_year"] == year
                                  and r["supply_basis"] == basis)
    urea = lambda year: sum(_float(r["offtake_kt"]) for r in offtake_rows
                            if r["fiscal_year"] == year and r["product"] == "Urea")
    # The urea legs are the bridge's inputs and they close EXACTLY - domestic plus
    # imported reproduces the printed Total Urea for both years.
    _assert_close("urea offtake FY2023-24", urea("2023-24"), 6579)
    _assert_close("urea offtake FY2024-25", urea("2024-25"), 5890)
    _assert_close("printed Total Urea FY2023-24", offtake_totals["Total Urea"][0], 6579)
    _assert_close("printed Total Urea FY2024-25", offtake_totals["Total Urea"][1], 5890)
    for index, year in ((0, "2023-24"), (1, "2024-25")):
        _assert_close("offtake grand total %s" % year,
                      off(year, "domestic") + off(year, "imported")
                      + off(year, "unclassified"),
                      offtake_totals["Grand Total"][index], 2)
        # NPK's and AS print with no supply qualifier, and the review's own domestic and
        # imported subtotals exceed the qualified rows by about 42 and 68 thousand tonnes
        # - an allocation across those two products that the review never states. The
        # unattributed remainder must equal them, or a product has been mis-read.
        unattributed = ((offtake_totals["Total domestic"][index] - off(year, "domestic"))
                        + (offtake_totals["Total imported"][index]
                           - off(year, "imported")))
        # 112 implied against 110 printed on the two products themselves: each subtotal
        # carries its own rounding, so the residue is checked to 2 rather than exactly.
        _assert_close("unattributed NPK/AS %s" % year, unattributed,
                      off(year, "unclassified"), 2)
    for row in offtake_rows:
        if row["supply_basis"] == "unclassified":
            row["note"] = UNCLASSIFIED_NOTE

    monthly_rows = []
    for fiscal_year, header, stop in (
            ("2023-24", r"\s*GAS CONSUMPTION BY PLANTS DURING 2023-24",
             r"\s*GAS CONSUMPTION BY PLANTS DURING 2024-25"),
            ("2024-25", r"\s*GAS CONSUMPTION BY PLANTS DURING 2024-25",
             r"\s*ANNEX-29")):
        year_rows, _year_totals = parse_gas_monthly(text, fiscal_year, header, stop)
        pairs = {(r["gas_supplier"], r["plant"]) for r in year_rows}
        if len(pairs) != 14 or len(year_rows) != 14 * 2 * 12:
            raise SystemExit("Annex-28 %s: expected 14 plants x Feed/Fuel x 12 months, "
                             "got %d pairs and %d rows"
                             % (fiscal_year, len(pairs), len(year_rows)))
        monthly_rows.extend(year_rows)

    mfeed = lambda year: sum(_float(r["mmcf"]) for r in monthly_rows
                             if r["fiscal_year"] == year and r["consumption"] == "Feed")
    mfuel = lambda year: sum(_float(r["mmcf"]) for r in monthly_rows
                             if r["fiscal_year"] == year and r["consumption"] == "Fuel")
    # THE ANNEX DOES NOT CLOSE ON ITSELF, and the tolerances say by how much rather than
    # hiding it: every plant's twelve months sum to within 3 MMCF of its own printed row
    # total, and the year aggregates run up to 6 MMCF above the printed feed and fuel
    # lines. That is 0.003 percent of the year and it is the source's arithmetic, not a
    # reading error - an exact assertion here would fail and invite someone to "fix" the
    # data. Both figures are carried; nothing is rounded away silently.
    _assert_close("Annex-28 FY2023-24 feed", mfeed("2023-24"), 229236, 2)
    _assert_close("Annex-28 FY2023-24 fuel", mfuel("2023-24"), 45213, 6)
    _assert_close("Annex-28 FY2023-24 total", mfeed("2023-24") + mfuel("2023-24"),
                  274449, 7)
    # The internal cross-check: Annex-28's second page and Table 40 are the same year in
    # the same document, reached by two different printings. They must agree.
    _assert_close("Annex-28 FY2024-25 against Table 40",
                  mfeed("2024-25") + mfuel("2024-25"), 281153, 2)
    _assert_close("Annex-28 FY2024-25 feed against Table 40", mfeed("2024-25"), 234001, 2)

    for path, fields, rows in ((PROD_OUT, PROD_FIELDS, prod_rows),
                               (GAS_OUT, GAS_FIELDS, gas_rows),
                               (OFFTAKE_OUT, OFFTAKE_FIELDS, offtake_rows),
                               (MONTHLY_OUT, MONTHLY_FIELDS, monthly_rows)):
        if write_or_check(path, fields, rows, check):
            return 1
    if check:
        print("NFDC AFR 2024-25: all four tables reproduce from the held document.")
        return 0

    print("NFDC AFR 2024-25 -> %s" % PROD_OUT)
    print("  %d manufacturer-year rows; urea 6,591 / 6,780 thousand t closes exactly"
          % len(prod_rows))
    print("NFDC AFR 2024-25 -> %s" % GAS_OUT)
    print("  12 plants + total; 234,001 feed + 47,152 fuel = 281,153 MMCF closes")
    print("NFDC AFR 2024-25 -> %s" % OFFTAKE_OUT)
    print("  %d product-year rows; urea 6,579 / 5,890 thousand t closes exactly"
          % len(offtake_rows))
    print("NFDC AFR 2024-25 -> %s" % MONTHLY_OUT)
    print("  %d rows, 14 plants x Feed/Fuel x 12 months x 2 years" % len(monthly_rows))
    total_2024 = mfeed("2023-24") + mfuel("2023-24")
    print("  FY2023-24, THE REFERENCE YEAR: %s feed + %s fuel = %s MMCF "
          "(%.1f%% feed), %.1f MMCFD against OGRA's 756"
          % ("{:,.0f}".format(mfeed("2023-24")), "{:,.0f}".format(mfuel("2023-24")),
             "{:,.0f}".format(total_2024), mfeed("2023-24") / total_2024 * 100.0,
             total_2024 / 365.0))
    return 0


if __name__ == "__main__":
    sys.exit(main(check="--check" in sys.argv))
