"""The rice water-regime axis: the long-named alternative, priced from held rasters.

WHY (Wave 6). The reference books every rice hectare at the continuously-flooded
scaling factor (SFw = 1.0, IPCC 2006 Table 5.12) - the declared convention for
Pakistani irrigated rice - and since rc5 the registry NAMED the intermittent
alternative without pricing it, with a "~0.71" in the note that matched none of the
four IPCC values and was computed by nothing: the exact failure class the FOD
spread figure was repaired for at Wave 3. The pricing inputs landed at rc26: SPAM
2020 V2r2's irrigated (RICE_I) and rainfed (RICE_R) physical-area rasters, held and
hashed beside the rice surface, and the four SFw factors already in the registry
with their own uncertainties.

THREE READINGS, ONE CONFIGURATION, NOTHING AVERAGED (rule 8):

  reference                every hectare at SFw 1.0 - the declared convention,
                           unchanged;
  rainfed_corrected        irrigated area stays continuous (1.0), the SPAM rainfed
                           share takes its own regime factor (0.28). A reading,
                           published and never selected: SPAM's technology split is
                           a 2020-vintage model surface, not a Pakistani water-
                           management observation;
  intermittent_weighted    the named alternative, priced as the configuration:
                           irrigated area at intermittent-single-aeration (0.60 -
                           the conservative member; the 0.52 AWD value is named
                           here and never blended) and rainfed at 0.28, weighted
                           by the SPAM province split. This is the "what if
                           Pakistani rice is not continuously flooded" fork the
                           registry has carried unpriced since rc5.

The CH4 model is linear in SFw (Emissions = EFc x SFw x SFp x SFo x area x days),
so each reading's category total is the reference total times its weighted SFw -
no engine re-run, no second vintage of the rice arithmetic.

Usage:  written by run_inventory on every run; also
        python3 -m pkinv.sectors.agriculture.water_regime
Writes: outputs/agriculture_water_regime_2024.csv
"""
from __future__ import annotations

from pkinv.assets import asset_path

from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import OUTPUTS
from pkinv.core.io import write_table

OUT = asset_path(OUTPUTS, "agriculture_water_regime_2024.csv")

FIELDS = ("configuration", "co2e_Mt_AR5", "weighted_SFw", "irrigated_share",
          "rainfed_share", "status", "note")


def spam_regime_shares():
    """National irrigated/rainfed physical-area shares over the rice-growing
    provinces, from the held SPAM technology rasters. Grid-masked like every
    proxy; the split is the two rasters' own mass ratio."""
    from pkinv.core.gis.grid import build_grid
    from pkinv.core.gis.proxies import build_manual_proxy
    grid = build_grid()
    irr = build_manual_proxy(grid, "spam2020_V2r2_global_A_RICE_I.tif")
    rain = build_manual_proxy(grid, "spam2020_V2r2_global_A_RICE_R.tif")
    if irr is None or rain is None:
        raise SystemExit("the SPAM water-regime rasters are absent - they landed "
                         "at rc26 (RICE_SOURCES.json) and the axis cannot price "
                         "without them")
    i_sum, r_sum = float(irr[0].sum()), float(rain[0].sum())
    total = i_sum + r_sum
    if total <= 0:
        raise SystemExit("the SPAM technology rasters carry no in-country rice "
                         "area - the split is unpriceable")
    return i_sum / total, r_sum / total


def rows():
    from pkinv.sectors.agriculture.ef_library import InventoryData
    data = InventoryData()
    reference_mt = None
    for r in _activity_rows(asset_path(OUTPUTS, "national_totals_2024.csv"), comments=True):
        if r.get("category") == "Rice cultivation":
            reference_mt = float(r["co2e_Mt_AR5"])
    if reference_mt is None:
        raise SystemExit("no Rice cultivation row in national_totals_2024.csv")

    sfw_int = data.efv("rice", "SFw_intermittent_single")
    sfw_awd = data.efv("rice", "SFw_intermittent_multiple")
    sfw_rain = data.efv("rice", "SFw_rainfed")
    irr, rain = spam_regime_shares()

    w_rainfed_only = irr * 1.0 + rain * sfw_rain
    w_intermittent = irr * sfw_int + rain * sfw_rain

    return [
        {"configuration": "reference", "co2e_Mt_AR5": round(reference_mt, 5),
         "weighted_SFw": 1.0, "irrigated_share": round(irr, 4),
         "rainfed_share": round(rain, 4), "status": "reference",
         "note": "every hectare at the continuously-flooded SFw 1.0 - the "
                 "declared convention for Pakistani irrigated rice; the SPAM "
                 "split is printed for context and moves nothing here"},
        {"configuration": "rainfed_corrected",
         "co2e_Mt_AR5": round(reference_mt * w_rainfed_only, 5),
         "weighted_SFw": round(w_rainfed_only, 4),
         "irrigated_share": round(irr, 4), "rainfed_share": round(rain, 4),
         "status": "reading_never_selected",
         "note": "irrigated area stays continuous, the SPAM rainfed share takes "
                 "its own regime factor (%.2f); published so the two moving "
                 "parts of the weighted alternative are separable, never "
                 "selected - the split is a 2020-vintage model surface"
                 % sfw_rain},
        {"configuration": "rice_water_regime_weighted",
         "co2e_Mt_AR5": round(reference_mt * w_intermittent, 5),
         "weighted_SFw": round(w_intermittent, 4),
         "irrigated_share": round(irr, 4), "rainfed_share": round(rain, 4),
         "status": "priced_configuration",
         "note": "the named alternative, priced at last (registered unpriced "
                 "since rc5): irrigated area at intermittent-single-aeration "
                 "SFw %.2f - the conservative member; the %.2f AWD value is "
                 "named and never blended - and rainfed at %.2f, on the SPAM "
                 "V2r2 technology split. No Pakistani water-management "
                 "observation decides between this and the continuous "
                 "reference, which is exactly why it ships as a configuration "
                 "and is never averaged in (rule 8)"
                 % (sfw_int, sfw_awd, sfw_rain)},
    ]


def main():
    out = rows()
    write_table(OUT, list(FIELDS), out, banner=('# The rice water-regime readings: linear SFw re-weightings of the reference rice total', '# on the held SPAM technology split; one configuration, nothing averaged. See water_regime.py.',), lineterminator="\n")
    print("rice water regime -> %s" % OUT)
    for r in out:
        print("  %-28s %9s Mt  SFw %s" % (r["configuration"],
                                          r["co2e_Mt_AR5"], r["weighted_SFw"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
