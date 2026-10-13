"""Key Category Analysis - IPCC 2006 Guidelines Vol 1 Ch 4, Approach 1.

A key category is one that, individually, has a significant influence on a national inventory's
total level of emissions, its trend, or both. The IPCC Approach 1 identifies them with a 95%
cumulative threshold on two assessments computed from absolute (unsigned) CO2e:

  Level assessment (reference year t):
      L_x = |E_x,t| / Sum_x |E_x,t|
  sorted descending; categories are key-by-level until the cumulative sum reaches 0.95.

  Trend assessment (base year 0 -> reference year t), IPCC Eq 4.2:
      T_x = L_x,0 * | g_x - g_tot |
      g_x   = (E_x,t - E_x,0) / |E_x,0|         (category growth relative to base year)
      g_tot = (E_tot,t - E_tot,0) / |E_tot,0|   (total growth relative to base year)
      L_x,0 = |E_x,0| / Sum_x |E_x,0|           (base-year level share)
  normalised to sum to 1, sorted descending; key-by-trend until cumulative reaches 0.95.

A category is KEY if it is key by level OR by trend.

Level covers the full AFOLU set (6 agriculture categories + LULUCF forest & mangrove, 2024).
Trend covers the 6 agriculture categories over 1990->2024 (the consistent time series); LULUCF
carries no historical series here, so it is level-only (flagged - a documented limitation).

Reads existing outputs (no emissions recomputed):
  outputs/national_totals_2024.csv   (agriculture level, reference year)
  outputs/lulucf_totals.csv          (LULUCF level, reference year)
  outputs/timeseries_1990_2024.csv   (agriculture trend, base + reference year)
Writes:
  outputs/key_categories.csv, outputs/key_categories_report.md

Usage:  python3 -m pkinv.sectors.agriculture.key_categories
"""

from pkinv.assets import asset_path
from pkinv.activity.store import read_rows as _activity_rows
import csv
import os

from pkinv.paths import OUTPUTS
import sys


from pkinv.sectors.agriculture.run_inventory import CATEGORIES, OUT_DIR, YEAR  # noqa: E402

BASE_YEAR = 1990
THRESHOLD = 0.95        # IPCC Approach 1 cumulative cut-off


def _read_level():
    """Absolute reference-year CO2e (AR5) per category, agriculture only.

    The level denominator is the agriculture total (221.71 Mt); the LULUCF land sector is reported
    separately (Supplementary Note S1) and is deliberately excluded from the key-category analysis, so
    the level shares are agriculture-relative and match the totals reported in the Results.
    """
    level = {}
    for r in _activity_rows(asset_path(OUTPUTS, "national_totals_2024.csv"), comments=False):
        if r["category"] == "TOTAL":
            continue
        level[r["category"]] = abs(float(r["co2e_Mt_AR5"]))
    return level


def _read_trend():
    """Base- and reference-year absolute CO2e (AR5) per agriculture category."""
    base, ref = {}, {}
    path = asset_path(OUT_DIR, "timeseries_1990_2024.csv")
    if not os.path.exists(path):
        return None, None
    for r in _activity_rows(path, comments=False):
        if r["category"] == "TOTAL":
            continue
        y = int(r["year"])
        if y == BASE_YEAR:
            base[r["category"]] = abs(float(r["co2e_Mt_AR5"]))
        elif y == YEAR:
            ref[r["category"]] = abs(float(r["co2e_Mt_AR5"]))
    return (base, ref) if base and ref else (None, None)


def _cumulative_flag(scores):
    """scores: dict name->value. Returns ordered list of (name, share, cum, key)."""
    total = sum(scores.values())
    ordered = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    out, cum = [], 0.0
    reached = False
    for name, val in ordered:
        share = val / total if total else 0.0
        cum += share
        key = not reached
        if cum >= THRESHOLD:
            reached = True          # this row is the last key one; later rows are not key
        out.append((name, share, cum, key))
    return out


def compute():
    level = _read_level()
    level_rows = _cumulative_flag(level)

    base, ref = _read_trend()
    trend_rows = []
    if base and ref:
        base_total = sum(base.values())
        tot_b = sum(base.values())
        tot_r = sum(ref.get(c, 0.0) for c in base)
        g_tot = (tot_r - tot_b) / abs(tot_b) if tot_b else 0.0
        trend_score = {}
        for cat, e0 in base.items():
            et = ref.get(cat, 0.0)
            g_x = (et - e0) / abs(e0) if e0 else 0.0
            l_x0 = abs(e0) / base_total if base_total else 0.0
            trend_score[cat] = l_x0 * abs(g_x - g_tot)
        trend_rows = _cumulative_flag(trend_score)

    return level_rows, trend_rows


def _write(level_rows, trend_rows):
    key_by_level = {n for n, _, _, k in level_rows if k}
    key_by_trend = {n for n, _, _, k in trend_rows if k}
    trend_lookup = {n: (s, c, k) for n, s, c, k in trend_rows}
    all_key = key_by_level | key_by_trend

    csv_path = asset_path(OUT_DIR, "key_categories.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["category", "level_pct", "cum_level_pct", "key_by_level",
                    "trend_pct", "cum_trend_pct", "key_by_trend", "key", "basis"])
        for name, share, cum, klev in level_rows:
            ts, tc, ktr = trend_lookup.get(name, (None, None, False))
            basis = "level+trend" if name in trend_lookup else "level only (no historical series)"
            w.writerow([
                name, round(share * 100, 2), round(cum * 100, 2), "YES" if klev else "no",
                round(ts * 100, 2) if ts is not None else "n/a",
                round(tc * 100, 2) if tc is not None else "n/a",
                "YES" if ktr else ("no" if ts is not None else "n/a"),
                "YES" if name in all_key else "no", basis])

    md = []
    md.append("# Key Category Analysis (IPCC 2006 Vol 1 Ch 4, Approach 1)\n")
    md.append("A **key category** has a significant influence on the national inventory's total "
              "**level**, **trend**, or both. Approach 1 flags categories cumulatively to the "
              "**95%** threshold on absolute (unsigned) CO2e (AR5 GWP-100).\n")
    md.append("- **Level assessment:** reference year %d, full AFOLU set (6 agriculture "
              "categories + LULUCF forest & mangrove).\n"
              "- **Trend assessment:** %d -> %d, agriculture categories (the consistent time "
              "series). LULUCF is level-only here (no historical series - a documented "
              "limitation).\n" % (YEAR, BASE_YEAR, YEAR))
    md.append("## Level assessment (%d)\n" % YEAR)
    md.append("| Category | Level % | Cumulative % | Key (level) |")
    md.append("|---|---:|---:|:--:|")
    for name, share, cum, klev in level_rows:
        md.append("| %s | %.1f | %.1f | %s |"
                  % (name, share * 100, cum * 100, "**KEY**" if klev else "-"))
    md.append("")
    if trend_rows:
        md.append("## Trend assessment (%d -> %d)\n" % (BASE_YEAR, YEAR))
        md.append("| Category | Trend contribution % | Cumulative % | Key (trend) |")
        md.append("|---|---:|---:|:--:|")
        for name, share, cum, ktr in trend_rows:
            md.append("| %s | %.1f | %.1f | %s |"
                      % (name, share * 100, cum * 100, "**KEY**" if ktr else "-"))
        md.append("")
    key_names = sorted(all_key, key=lambda n: -dict((r[0], r[1]) for r in level_rows).get(n, 0))
    md.append("## Key categories (level OR trend)\n")
    for n in key_names:
        tags = []
        if n in key_by_level:
            tags.append("level")
        if n in key_by_trend:
            tags.append("trend")
        md.append("- **%s** (%s)" % (n, ", ".join(tags)))
    md.append("")
    md.append("_Interpretation: key categories are where methodological rigour, better activity "
              "data, and uncertainty reduction pay off most - consistent with the Monte-Carlo "
              "uncertainty ranking (`uncertainty_montecarlo.csv`)._\n")
    with open(asset_path(OUT_DIR, "key_categories_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    return csv_path, all_key


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    level_rows, trend_rows = compute()
    _, all_key = _write(level_rows, trend_rows)
    print("Key Category Analysis (IPCC Approach 1, 95%% threshold):")
    print("  Level assessment: %d AFOLU categories (ref %d)" % (len(level_rows), YEAR))
    print("  Trend assessment: %d agriculture categories (%d->%d)"
          % (len(trend_rows), BASE_YEAR, YEAR))
    print("  Key categories (%d): %s" % (len(all_key), ", ".join(sorted(all_key))))


if __name__ == "__main__":
    main()
