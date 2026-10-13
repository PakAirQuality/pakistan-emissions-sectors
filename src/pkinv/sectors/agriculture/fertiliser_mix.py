"""Product-resolved fertiliser nitrogen, and the NH3 emission factor it implies.

The engine previously applied one IPCC Table 11.3 default, FracGASF = 0.15, described as "urea-dominant
N supply". That is a reasonable default but it is not a country-specific number: the fraction of applied
N volatilised as NH3 depends strongly on which products carry the nitrogen, because urea hydrolyses to
ammonium carbonate at the soil surface while nitrate-bearing products barely volatilise at all. Pakistan
reports its offtake by product, so the weighting can be computed rather than assumed.

The weighted factor is deliberately derived from SHARES, not from the annexe's absolute tonnages:

  * `data/activity/fertilizer_2024.csv` carries the audited national N total and stays the activity datum;
  * `data/nfdc/annex5_national_month_product.csv` supplies only the product composition.

THE WINDOW IS THE FISCAL YEAR ITSELF (rc39 A2). This weighting used to come from Annex-7, whose
year runs April-March -- Kharif then Rabi -- so the composition was drawn from a period that is
not the one the inventory reports. The module argued the shares were robust to that choice
(urea 0.806 against 0.813), and they nearly are; but "nearly" is the wrong standard for a factor
that drives BOTH the ammonia layer and the synthetic indirect-N2O row, and the argument was only
ever needed because the correctly windowed source, though held, had never been given a reader.
Annex-5 is that source: national monthly offtake by product whose own fiscal_year label 2023-24
is exactly the twelve months Jul-2023 .. Jun-2024. Over that window the weighted factor is 0.1608191992 kg NH3-N per kg N.

Annex-5 is the PRINTED NATIONAL ROW. data/activity/monthly/nfdc_month_product_offtake.csv is the
same publication decomposed to twelve supplying agencies; summing those rounded rows drifts by
1-3 t on three products (urea 6,578,841 against the printed 6,578,838). For a national datum the
printed row carries fewer rounding steps, so it is the source and the agency panel is the
cross-check. Annex-7 is retained below for the PROVINCIAL factors, which Annex-5 cannot give.

Annex-5's own nitrogen over the window is 3.746448 Mt N against the audited 3.775 Mt N, 0.756%
lower. Only the normalised composition crosses between them; the magnitude stays with
fertilizer_2024.csv. main() prints both so the two are visibly different quantities.

Emission factors are EMEP/EEA 2023 Guidebook Ch 3.D by product and soil pH class. Pakistan's cropland is
alkaline/calcareous -- the same premise the completeness table already uses to treat liming as
negligible -- so the high-pH column applies.

Usage:  python3 -m pkinv.sectors.agriculture.fertiliser_mix
"""

from pkinv.assets import asset_path
import collections
import csv
import os
import sys


from pkinv.sectors.agriculture.ef_library import InventoryData, DATA_DIR  # noqa: E402
from pkinv.activity.store import read_rows

ANNEX5 = asset_path(DATA_DIR, "nfdc", "annex5_national_month_product.csv")
ANNEX7 = asset_path(DATA_DIR, "nfdc", "annex7_province_month_product_2023-24.csv")

# The reporting fiscal year, named as the twelve (calendar_year, month) pairs it contains rather
# than trusted from the annexe's own label. Both are checked: the label selects the rows, and the
# pairs prove the selection is the window we mean. Annex-7's April-March year made exactly this
# kind of silent mismatch possible, so the successor states its window explicitly.
FY_LABEL = "2023-24"
FY_WINDOW = (("2023", "Jul"), ("2023", "Aug"), ("2023", "Sep"), ("2023", "Oct"),
             ("2023", "Nov"), ("2023", "Dec"), ("2024", "Jan"), ("2024", "Feb"),
             ("2024", "Mar"), ("2024", "Apr"), ("2024", "May"), ("2024", "Jun"))
# One fiscal year: Kharif (Apr-Sep) plus the Rabi that follows it. Kharif2025 is the NEXT year's
# first season and must be excluded or its months are counted twice.
# NFDC's annex year runs April-March (Kharif then Rabi), which is not the July-June
# fiscal year the rest of this inventory reports. That is a difference in what the two
# publications mean by a year, not a mismatch to fix: the annex supplies the product
# COMPOSITION and the annual offtake table supplies the magnitude, so only the shares
# cross between them. The extractor's totals reproduce the annex's own printed season
# subtotals exactly, and they sit above the July-June offtake table for the same reason.
FY_SEASONS = ("Kharif2023", "Rabi2023-24")
NON_PRODUCT = {"province", "season", "month", "calendar_year", "Total", "source"}
PROVINCE_NAME = {"KP": "Khyber Pakhtunkhwa"}       # annex7 abbreviates; engine spells it out


def _rows():
    return read_rows(ANNEX7, comments=False)


def product_nitrogen(data=None, seasons=FY_SEASONS):
    """{province: {product: t N}} over the given seasons, using Table A2 N contents."""
    if data is None:
        data = InventoryData()
    rows = _rows()
    products = [c for c in rows[0] if c not in NON_PRODUCT]
    out = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in rows:
        if seasons is not None and r["season"] not in seasons:
            continue
        prov = PROVINCE_NAME.get(r["province"], r["province"])
        for p in products:
            raw = (r.get(p) or "").strip()
            if not raw:
                continue
            nc = data.efv("fert_n_content", p)
            if nc:
                out[prov][p] += float(raw) * nc
    return {p: dict(v) for p, v in out.items()}


def annex5_window(label=FY_LABEL):
    """The Annex-5 rows for one fiscal year, proven to be the twelve months it claims.

    The label alone is not trusted. If NFDC ever relabels a row, or an extraction picks up the
    adjacent Kharif, the (calendar_year, month) set stops matching FY_WINDOW and this raises
    instead of quietly weighting a thirteen- or fifteen-month mix -- the failure Annex-7's
    April-March year made possible."""
    rows = [r for r in read_rows(ANNEX5, comments=False) if r["fiscal_year"] == label]
    if not rows:
        raise KeyError("%s carries no rows for fiscal year %s" % (ANNEX5, label))
    seen = {(r["calendar_year"], r["month"]) for r in rows}
    if seen != set(FY_WINDOW):
        raise ValueError("%s fiscal year %s is not the Jul-Jun window: %d months, "
                         "unexpected %s, missing %s"
                         % (ANNEX5, label, len(seen), sorted(seen - set(FY_WINDOW)),
                            sorted(set(FY_WINDOW) - seen)))
    return rows


def national_product_nitrogen(data=None, label=FY_LABEL):
    """{product: t N} nationally over the fiscal-year window, and the product tonnes behind it.

    Products with no nitrogen content (MOP, SOP, SSP, TSP) contribute tonnage and no nitrogen;
    they are carried in the tonnes map so the composition can be shown against the offtake the
    annexe actually prints."""
    if data is None:
        data = InventoryData()
    nitrogen = collections.defaultdict(float)
    tonnes = collections.defaultdict(float)
    for r in annex5_window(label):
        product = r["product"]
        t = float(r["offtake_product_tonnes"] or 0.0)
        tonnes[product] += t
        try:
            nc = data.efv("fert_n_content", product)
        except KeyError:
            nc = 0.0
        if nc:
            nitrogen[product] += t * nc
    return dict(nitrogen), dict(tonnes)


def national_shares(data=None, seasons=None):
    """{product: share of national fertiliser N}, summing to 1, over the Jul-Jun window.

    `seasons` is accepted and ignored: it selected Annex-7 seasons before rc39 A2 and the
    signature is kept so the eight registered claims that call this keep working."""
    nitrogen, _ = national_product_nitrogen(data)
    s = sum(nitrogen.values())
    if s <= 0:
        raise ValueError("no fertiliser nitrogen found in %s" % ANNEX5)
    return {p: v / s for p, v in nitrogen.items()}, s


def weighted_fracgasf(data=None, ph_class=None, urea_override=None, seasons=FY_SEASONS):
    """Share-weighted NH3-N loss per kg N applied, and the per-product detail behind it.

    ph_class: "high" (default, from parameters.csv) or "normal" -- the EMEP/EEA soil-pH column.
    urea_override: substitute a different urea EF (e.g. the Bhatia South-Asian value) as a sensitivity.
    """
    if data is None:
        data = InventoryData()
    # "high" is not a tunable: Pakistan's cropland is alkaline/calcareous, the same premise the
    # completeness table uses to treat liming as negligible. The justification travels with the
    # factor rows themselves (see their source strings), not a parameter switch.
    ph_class = ph_class or "high"
    category = "fert_nh3_highpH" if ph_class == "high" else "fert_nh3_normalpH"

    shares, total_n = national_shares(data)
    detail, weighted = [], 0.0
    for p, share in sorted(shares.items(), key=lambda kv: -kv[1]):
        ef = data.efv(category, p)
        if p == "Urea" and urea_override is not None:
            ef = urea_override
        weighted += share * ef
        detail.append({"product": p, "share_of_N": share, "EF_NH3N_per_N": ef,
                       "contribution": share * ef})
    return weighted, detail, total_n


_CACHE = {}


def fracgasf(data=None):
    """The FracGASF the engine should use: product-weighted where the NFDC mix is available.

    This is the single accessor for the synthetic-fertiliser volatilisation fraction. Both layers
    depend on it through soils.volatilised_n -- the air layer's NH3 and the greenhouse-gas layer's
    synthetic indirect-N2O row -- so they cannot drift onto different fractions for the same nitrogen,
    which is the failure the shared nitrogen ledger exists to prevent.

    Falls back to the IPCC Table 11.3 default if the product annexe is missing, and says so.
    """
    if data is None:
        data = InventoryData()
    key = id(data)
    if key in _CACHE:
        return _CACHE[key]
    try:
        value, _, _ = weighted_fracgasf(data)
        source = ("product-weighted EMEP/EEA high-pH (NFDC Annex-5 national mix, "
                  "Jul-2023..Jun-2024)")
    except (OSError, KeyError) as e:
        value = data.efv("soils", "FracGASF")
        source = "IPCC Table 11.3 default (product mix unavailable: %s)" % e
    _CACHE[key] = (value, source)
    return value, source


def fracgasf_uncert(data=None):
    """Uncertainty (%) of the product-weighted FracGASF, magnitude-weighted over the products.

    The IPCC default row carried 50%; the EEA product factors carry 30% each, so the weighted factor
    is better constrained than the generic default it replaces -- reporting the old 50% would
    overstate the uncertainty of a more specific number.

    The products are combined as ONE correlation group: every factor comes from the same EEA Table
    3.D and shares its systematic error, so quadrature would understate the result (it gives 26%
    against the correct 30%) purely because the table has many rows."""
    if data is None:
        data = InventoryData()
    from pkinv.core.uncertainty import combine_sum
    try:
        _, detail, _ = weighted_fracgasf(data)
    except (OSError, KeyError):
        return data.efu("soils", "FracGASF")
    terms = [(d["contribution"], data.efu("fert_nh3_highpH", d["product"]), "eea_table_3d")
             for d in detail]
    _, u = combine_sum(terms)
    return u


def provincial_fracgasf(data=None, ph_class="high", seasons=FY_SEASONS):
    """{province: weighted EF} -- provinces differ in product mix, so their implied factors differ."""
    if data is None:
        data = InventoryData()
    category = "fert_nh3_highpH" if ph_class == "high" else "fert_nh3_normalpH"
    out = {}
    for prov, prods in product_nitrogen(data, seasons).items():
        tot = sum(prods.values())
        if tot <= 0:
            continue
        out[prov] = sum(v / tot * data.efv(category, p) for p, v in prods.items())
    return out


def main():
    data = InventoryData()
    weighted, detail, total_n = weighted_fracgasf(data)
    audited = data.fertilizer["nitrogen_N_offtake"]["value_t"]
    print("Pakistan fertiliser nitrogen by product (NFDC Annex-7, %s):" % " + ".join(FY_SEASONS))
    print("  %-8s %10s %10s %12s" % ("product", "share of N", "EF NH3-N/N", "contribution"))
    for d in detail:
        print("  %-8s %10.4f %10.3f %12.4f"
              % (d["product"], d["share_of_N"], d["EF_NH3N_per_N"], d["contribution"]))
    print("  %-8s %10.4f %10s %12.4f" % ("TOTAL", sum(d["share_of_N"] for d in detail), "", weighted))
    print()
    print("  window N total   %10.0f t N" % total_n)
    print("  audited N total  %10.0f t N  (fertilizer_2024.csv; used as the activity datum)" % audited)
    print("  agreement        %10.1f%%" % (100.0 * total_n / audited))
    print()
    print("  weighted FracGASF (EEA high pH)   %.4f   <- adopted" % weighted)
    print("  IPCC Table 11.3 default           %.4f   <- superseded"
          % data.efv("soils", "FracGASF"))
    alt, _, _ = weighted_fracgasf(data, ph_class="normal")
    bha, _, _ = weighted_fracgasf(data, urea_override=data.efv("fert_nh3_alt", "Urea_Bhatia"))
    print("  sensitivity, EEA normal pH        %.4f" % alt)
    print("  sensitivity, Bhatia urea 0.114    %.4f" % bha)
    print()
    print("  provincial implied factors (product mix differs by province):")
    for prov, ef in sorted(provincial_fracgasf(data).items(), key=lambda kv: -kv[1]):
        print("    %-20s %.4f" % (prov, ef))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
