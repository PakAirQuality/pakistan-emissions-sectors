#!/usr/bin/env python3
"""Can a forest-land component be built? The two available accounts disagree on the SIGN.

WHY THIS EXISTS (T-LAND-2). This inventory excludes land use, land-use change and forestry by
declared scope, and the land lane's extraction established that no official land SERIES exists
to import: Pakistan's BTR1, its CRT and the Third National Communication all carry one
identical FY2020-21 block, and BUR1 carries one different FY2017-18 figure. So any nine-year
land panel would be modelled, and the question became which land component could be built
reproducibly from what is held.

THE ANSWER IS NONE, YET, AND THE REASON IS WORTH PUBLISHING. The two accounts that cover
forest land do not differ by a factor or a vintage. They differ in SIGN: Pakistan's own
submission books forest land as a source of +28.44 Mt CO2, and FAOSTAT books Pakistan's forest
land as a SINK of -4.107 Mt in the same year. A component built on either would be an
inventory-scale choice (the gap is about 7 per cent of the national total) resting on a
disagreement about whether Pakistan is gaining or losing forest.

WHERE THE SIGN COMES FROM, read out of FAOSTAT's own columns rather than argued:
  - FAOSTAT has Pakistan's forest AREA falling from 2004 to 2015 and RISING from 2020, at
    exactly +20.786 kha a year for 2020, 2021, 2022 and 2023. A difference constant to three
    decimal places over four years is interpolation between FRA anchors, not observation, so
    the only annual series available carries no annual information.
  - FAOSTAT's `Net Forest conversion` is exactly 0.000 kha from 2020 onward, against 26.104
    kha in 2015. It books no deforestation at all in the years that matter.
  - Pakistan's own REDD+ forest reference level documents forest area falling from 4,981,118
    ha in 2004 to 4,786,346 ha in 2012, which is a loss, in the opposite direction.
  - And the areas are not the same quantity: FAOSTAT is on the FRA 5 m tree definition
    (about 3,089 kha) where Pakistan's national definition is 2 m plus legal notification
    (the CRT's 4,079.631 kha). That alone is a 24 per cent difference in the stock the flux
    is computed over.

SCOPE. Everything here is a SCREENING. It sits beside the inventory and nothing enters a
total: no pin moves, and LULUCF stays outside the reported boundary. The point of the product
is to make the blocker explicit and measurable, so a later decision to build a land component
is taken against a stated disagreement rather than by picking a number.

Usage:  python3 scripts/build_forest_flux_adjudication.py [--check]
Writes: outputs/pakemis_forest_flux_adjudication.csv
"""
from __future__ import annotations

import argparse
import csv
import io
import os
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from pkinv.assets import asset_path                                    # noqa: E402
from pkinv.core.io import read_rows, write_table                       # noqa: E402
from pkinv.paths import DATA, OUTPUTS                                  # noqa: E402

OUT = asset_path(OUTPUTS, "pakemis_forest_flux_adjudication.csv")
FAOSTAT_ZIP = os.path.join(
    ROOT, "data", "raw", "land",
    "faostat_Emissions_Land_Use_Forests_E_All_Data_(Normalized).zip")
FAOSTAT_MEMBER = "Emissions_Land_Use_Forests_E_All_Data_(Normalized).csv"
BTR_INVENTORY = "btr1_national_inventory.csv"
BTR_FOREST_CODE = "3.B.1"

FIELDS = ("account", "quantity", "period", "value", "unit", "sign_meaning",
          "source", "note")

# Pakistan's own forest AREA figures, for the definitional comparison. Quoted in the banner and
# in a note rather than published as rows: they come from the land lane's extraction, which is
# not a registered ingest, and this product publishes only what a registered source carries.
CRT_FOREST_AREA_KHA = 4079.631


def _faostat():
    """Pakistan's forest-land flux and area from the held FAOSTAT zip."""
    if not os.path.exists(FAOSTAT_ZIP):
        raise SystemExit(
            "the held FAOSTAT forests extract is missing: %s. It is a raw acquisition under "
            "data/raw/land/; this product does not re-download it." % FAOSTAT_ZIP)
    with zipfile.ZipFile(FAOSTAT_ZIP) as zf:
        with zf.open(FAOSTAT_MEMBER) as handle:
            rows = [r for r in csv.DictReader(
                io.TextIOWrapper(handle, encoding="utf-8-sig", errors="replace"))
                if "akistan" in (r.get("Area") or "")]
    if not rows:
        raise SystemExit("the FAOSTAT extract holds no Pakistan rows")
    return rows


def _pick(rows, item, element, year):
    for r in rows:
        if r["Item"] == item and r["Element"].startswith(element) and r["Year"] == str(year):
            return float(r["Value"]), r["Unit"]
    return None, ""


def _btr_forest():
    """The submission's forest-land CO2, from the registered BTR transcription."""
    for r in read_rows(asset_path(DATA, BTR_INVENTORY)):
        if r["btr_code"] == BTR_FOREST_CODE:
            return float(r["co2_Mt_co2e"]), float(r["total_Mt_co2e"])
    raise SystemExit("the BTR transcription has no %s row" % BTR_FOREST_CODE)


def build():
    fao = _faostat()
    co2, total = _btr_forest()
    rows = [{
        "account": "Pakistan BTR1 / CRT", "quantity": "forest land flux",
        "period": "FY2020-21", "value": "%.2f" % co2, "unit": "Mt CO2",
        "sign_meaning": "positive is a SOURCE",
        "source": "data/btr1_national_inventory.csv (3.B.1)",
        "note": "the submission's own figure; its CH4 and N2O carry the rest of the %.2f Mt "
                "CO2e block, which is biomass burning folded into land" % total}]

    years = [2015, 2020, 2021, 2022, 2023]
    for y in years:
        flux, unit = _pick(fao, "Forestland", "Net emissions", y)
        if flux is None:
            continue
        rows.append({
            "account": "FAOSTAT", "quantity": "forest land flux", "period": "CY%d" % y,
            "value": "%.3f" % (flux / 1000.0), "unit": "Mt CO2",
            "sign_meaning": "negative is a SINK",
            "source": "data/raw/land/%s" % os.path.basename(FAOSTAT_ZIP),
            "note": "Forestland = carbon stock change minus net forest conversion, in "
                    "FAOSTAT's own decomposition"})
    for y in years:
        area, unit = _pick(fao, "Forestland", "Area", y)
        conv, _ = _pick(fao, "Net Forest conversion", "Area", y)
        if area is None:
            continue
        rows.append({
            "account": "FAOSTAT", "quantity": "forest area", "period": "CY%d" % y,
            "value": "%.3f" % area, "unit": "1000 ha",
            "sign_meaning": "n.a.",
            "source": "data/raw/land/%s" % os.path.basename(FAOSTAT_ZIP),
            "note": "net forest conversion in the same year: %s kha"
                    % ("%.3f" % conv if conv is not None else "not reported")})

    # THE THIRD ACCOUNT, AND WHY IT IS NOT A THIRD WITNESS. This release already ships an
    # exploratory Tier-1 land module whose forest-land figure is a SINK, so at first reading
    # two of three accounts agree against the submission. They are one assumption counted
    # twice: the module's deforestation_area_ha_yr is 0 ha/yr and its own justification is
    # "FAO net forest conversion ~0 in recent years (afforestation offsets gross loss)". It
    # takes the decisive quantity from FAOSTAT, so its agreement with FAOSTAT is not
    # evidence - and the justification is contradicted by Pakistan's own CRT, where forest
    # gross losses are 2.09 times gross gains.
    for r in read_rows(asset_path(OUTPUTS, "lulucf_totals.csv")):
        if r["code"] != "3.B.1":
            continue
        rows.append({
            "account": "PakEmis exploratory land module", "quantity": "forest land flux",
            "period": "FY2023-24", "value": r["co2e_Mt_AR5_signed"], "unit": "Mt CO2",
            "sign_meaning": "negative is a SINK",
            "source": "outputs/lulucf_totals.csv (3.B.1)",
            "note": "NOT independent of FAOSTAT on the decisive quantity: its "
                    "deforestation_area_ha_yr is 0 ha/yr, justified in "
                    "data/sectors/lulucf/parameters/lulucf_params.csv as \"FAO net forest "
                    "conversion ~0 in recent years\". Its agreement with FAOSTAT is that "
                    "assumption counted twice"})
    # The gross pair the ratio is computed from, published as values rather than left in a
    # note. Their own verification is that (losses - gains) x 44/12 reproduces the
    # submission's independently printed +28.44 Mt to three decimals, which is a stronger
    # check on the transcription than re-reading the cell.
    for label, kt_c in (("CRT forest gross gains", 7113.0834552),
                        ("CRT forest gross losses", 14868.348452164)):
        rows.append({
            "account": "Pakistan BTR1 / CRT", "quantity": label, "period": "FY2020-21",
            "value": "%.3f" % kt_c, "unit": "kt C",
            "sign_meaning": "gains are removals, losses are emissions",
            "source": "Pakistan CRT 2.83 LULUCF 4.A living biomass",
            "note": "printed in the implied-factor column block, which the land lane records "
                    "as a column defect in the submission; the pair nets to the BTR's own "
                    "printed forest figure"})
    rows.append({
        "account": "diagnostic", "quantity": "CRT forest net from the gross pair",
        "period": "FY2020-21",
        "value": "%.3f" % ((14868.348452164 - 7113.0834552) * 44.0 / 12.0 / 1000.0),
        "unit": "Mt CO2", "sign_meaning": "positive is a SOURCE",
        "source": "derived from the two gross rows above",
        "note": "reproduces the submission's printed 28.44 Mt, which is the check that the "
                "gross pair was read correctly"})
    rows.append({
        "account": "diagnostic", "quantity": "CRT gross loss over gross gain",
        "period": "FY2020-21", "value": "%.2f" % (14868.348452164 / 7113.0834552),
        "unit": "ratio", "sign_meaning": "above 1 means forest is being LOST",
        "source": "Pakistan CRT 2.83 LULUCF 4.A living biomass, via the land lane extraction",
        "note": "gross losses 14868.348 kt C against gains 7113.083 kt C, which at 44/12 net "
                "to +28.436 Mt CO2 and reproduce the submission's printed figure. The "
                "exploratory module's zero-deforestation justification says afforestation "
                "offsets gross loss; the submission says loss is twice gain"})

    # The diagnostics the verdict rests on, computed rather than asserted.
    later = [(_pick(fao, "Forestland", "Area", y)[0], y) for y in (2020, 2021, 2022, 2023)]
    later = [(a, y) for a, y in later if a is not None]
    steps = [round(later[i + 1][0] - later[i][0], 6) for i in range(len(later) - 1)]
    rows.append({
        "account": "diagnostic", "quantity": "FAOSTAT area step, 2020-2023",
        "period": "CY2020-CY2023", "value": "/".join("%.3f" % s for s in steps),
        "unit": "1000 ha per year", "sign_meaning": "positive is forest GAIN",
        "source": "derived from the FAOSTAT rows above",
        "note": "identical to three decimals across every step, which is interpolation "
                "between FRA anchors and not an annual observation"
                if len(set(steps)) == 1 else
                "the steps differ, so the series may now carry annual information"})
    flux_2020, _ = _pick(fao, "Forestland", "Net emissions", 2020)
    rows.append({
        "account": "diagnostic", "quantity": "sign disagreement, matched year",
        "period": "FY2020-21 against CY2020",
        "value": "%.2f" % (co2 - flux_2020 / 1000.0), "unit": "Mt CO2",
        "sign_meaning": "the submission minus FAOSTAT",
        "source": "derived from the two accounts above",
        "note": "the two INDEPENDENT accounts disagree on the DIRECTION of the flux, not its size, so no "
                "forest component can be built from them until the area trend is settled; "
                "Pakistan's national forest definition (2 m plus legal notification, the "
                "CRT's %.3f kha) is also not FAOSTAT's FRA 5 m definition" % CRT_FOREST_AREA_KHA})
    return rows


BANNER = (
    "CAN A FOREST-LAND COMPONENT BE BUILT? The two available accounts disagree on the SIGN.",
    "A SCREENING, beside the inventory and never inside it: LULUCF stays outside the reported",
    "boundary and no pin moves. Pakistan's own submission books forest land as a SOURCE and",
    "FAOSTAT books it as a SINK in the same year, a gap of about 7 per cent of the national",
    "total. FAOSTAT's own columns carry the mechanism: its Pakistani forest area RISES from",
    "2020 at exactly +20.786 kha a year - constant to three decimals over four years, so",
    "interpolation rather than observation - and its net forest conversion is exactly 0.000",
    "kha from 2020, against 26.104 kha in 2015. Pakistan's REDD+ reference level documents",
    "forest area FALLING from 4,981,118 ha in 2004 to 4,786,346 ha in 2012. The areas are",
    "also not the same quantity: FRA's 5 m tree definition against Pakistan's 2 m plus legal",
    "notification. See scripts/build_forest_flux_adjudication.py for what each row cites.",
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    rows = build()
    if args.check:
        current = io.open(OUT, encoding="utf-8").read() if os.path.exists(OUT) else ""
        write_table(OUT + ".tmp", FIELDS, rows, banner=BANNER)
        fresh = io.open(OUT + ".tmp", encoding="utf-8").read()
        os.remove(OUT + ".tmp")
        if current != fresh:
            raise SystemExit("outputs/pakemis_forest_flux_adjudication.csv is stale")
        print("checked: %d rows" % len(rows))
        return 0
    write_table(OUT, FIELDS, rows, banner=BANNER)
    print("forest flux adjudication -> %s" % OUT)
    for r in rows:
        if r["account"] == "diagnostic":
            print("  %-34s %s %s" % (r["quantity"], r["value"], r["unit"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
