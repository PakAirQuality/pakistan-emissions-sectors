"""National Key Category Analysis - IPCC 2006 Vol 1 Ch 4, Approach 1, over every sector.

A key category is one that has a significant influence on the national inventory's total
level of emissions. Approach 1 sorts categories by their share of the absolute total and
flags them cumulatively to a 95% threshold.

WHY THIS EXISTS SEPARATELY FROM THE AGRICULTURE ONE. The agriculture-scoped screen
(pkinv.sectors.agriculture.key_categories, in the companion research repository)
screens the six agriculture categories against the AGRICULTURE total, which was the right
denominator when agriculture was the inventory. It no longer is. Against the national
total, road transport and electricity generation are the second and third largest
categories in the country - each larger than every agriculture category except enteric
fermentation - and neither had ever appeared in a key-category screen. That is the whole
point of the analysis: it tells you where methodological effort pays off, and it was
pointing at the wrong set.

LEVEL ONLY, AND THAT IS DECLARED RATHER THAN QUIETLY OMITTED. IPCC also defines a trend
assessment, which needs a consistent time series for every category between a base and a
reference year. Four of the nine sectors report a single year, and the four that do carry a
series (aviation from 2006, power from 2018, railways from 2014 with gaps, fugitives from
2011) do not reach agriculture's 1990 base. A trend assessment across mixed vintages would be arithmetic without meaning.
The agriculture-only trend assessment remains valid on its own terms and is still produced
by the sector module.

VARIANCE CONTRIBUTION, WHICH IS THE MORE ACTIONABLE RANKING. Being large is not the same as
being uncertain. A category's contribution to the national variance is (E_x * U_x)^2 as a
share of the sum over all categories, from the same Approach-1 quadrature that produces the
national band. A category can be key by level and contribute almost nothing to the
uncertainty, or the reverse - and the reverse is where the next measurement campaign
should go. docs/ROADMAP_COVERAGE.md has listed a variance-contribution ranking as an open
item since before the other six sectors existed; this is it, at national scope.

Usage:  python3 -m pkinv.report.key_categories_all
Writes: outputs/national_key_categories.csv, outputs/national_key_categories_report.md
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.core import registry
from pkinv.paths import OUTPUTS
from pkinv.report import category_ledger

THRESHOLD = 0.95        # IPCC Approach 1 cumulative cut-off


def _screen_units(components):
    """The units this screen ranks: IPCC CATEGORIES, not engine categories.

    WHY THIS CHANGED. The screen used to rank the engine's own categories, which are software
    units. Two of them - captive gas self-generation in the power module and industrial fuel
    combustion in the industry module - are both IPCC 1.A.2, so the national result reported
    18 IPCC categories in its category table and 19 here, and the cumulative 95 percent
    threshold, the level ranking and every variance share were computed over the second
    hierarchy. A reader could not tell which count was the inventory's.

    The IPCC category is canonical now. 1.A.2 enters once at its full magnitude, and the two
    engine categories beneath it are reported as SOURCE STREAMS in their own column - the
    diagnostic split survives without being a second category system.

    Returns {code: {"label", "streams", "sectors", "members"}}. The label is ALWAYS the
    Guidelines' name for the code, never the engine's. Using the engine name where a code has
    only one looked tidier and reintroduced the same defect at a different layer: the engine
    calls 3.H "Urea application", and liming is 3.G, which this inventory does not estimate.
    The engine names survive in the source_streams column, where they are diagnostics rather
    than category names.
    """
    # PER COMPONENT, not per engine category: under IPCC 2006 manure management's indirect
    # N2O is 3.C.6 while its CH4 and direct N2O are 3.A.2, and managed soils divides into
    # 3.C.4 and 3.C.5. A key-category analysis that grouped on the engine label would hide
    # exactly the distinction the codes exist to make - and it is a key-category analysis, so
    # a category that is material only after the split would never surface.
    units = {}
    for c in components:
        code = category_ledger.component_code(c["category"], c.get("subitem"), c["gas"])
        unit = units.setdefault(code, {"streams": {}, "sectors": set(), "members": []})
        unit["streams"].setdefault(c["category"], 0.0)
        unit["streams"][c["category"]] += c["co2e_Mt_AR5"]
        unit["sectors"].add(c["_sector"])
        unit["members"].append(c)
    for code, unit in units.items():
        unit["label"] = category_ledger.IPCC_CATEGORY_NAMES[code]
    return units


def _cumulative_flag(scores):
    """scores: {name: value} -> ordered [(name, share, cumulative, is_key)].

    The row that crosses the threshold is itself key; everything after it is not. Same
    convention as the agriculture-scoped screen in the companion repository, deliberately.
    """
    total = sum(scores.values())
    out, cum, reached = [], 0.0, False
    for name, val in sorted(scores.items(), key=lambda kv: kv[1], reverse=True):
        share = val / total if total else 0.0
        cum += share
        is_key = not reached
        if cum >= THRESHOLD:
            reached = True
        out.append((name, share, cum, is_key))
    return out


def compute(prebuilt=None):
    """Return (level_rows, variance_rows, by_category) for the national inventory.

    Ranked over IPCC categories - see _screen_units. by_category is keyed by the row label so
    downstream readers keep working; it carries the code and the source streams beside it.
    """
    components, _categories, _sector_of = prebuilt or registry.build_all()
    units = _screen_units(components)

    level, variance = {}, {}
    for code, unit in units.items():
        label = unit["label"]
        level[label] = abs(sum(c["co2e_Mt_AR5"] for c in unit["members"]))
        # Approach-1 quadrature within the category, then squared to give its variance
        # contribution. Correlated rows add linearly before squaring, matching combine_sum.
        grouped, ungrouped = {}, 0.0
        for c in unit["members"]:
            absolute = abs(c["co2e_Mt_AR5"]) * c["uncert_pct"] / 100.0
            if c.get("corr_group"):
                grouped[c["corr_group"]] = grouped.get(c["corr_group"], 0.0) + absolute
            else:
                ungrouped += absolute ** 2
        variance[label] = ungrouped + sum(v ** 2 for v in grouped.values())

    by_category = {
        unit["label"]: {
            "level_Mt": level[unit["label"]],
            "sector": " + ".join(sorted(unit["sectors"])),
            "ipcc_code": code,
            # Always populated, including for a code with one stream: it is the join back
            # to the engine, and it is what lets a reader (or a test) look a category up by
            # the name the module computes it under.
            "source_streams": "; ".join(
                "%s %.2f" % (s, v) for s, v in sorted(unit["streams"].items(),
                                                      key=lambda kv: -kv[1])),
        }
        for code, unit in units.items()
    }
    return _cumulative_flag(level), _cumulative_flag(variance), by_category


def main():
    os.makedirs(OUTPUTS, exist_ok=True)
    level_rows, variance_rows, by_category = compute()
    key_by_level = {n for n, _s, _c, k in level_rows if k}
    variance_lookup = {n: (s, c) for n, s, c, _k in variance_rows}
    total = sum(r["level_Mt"] for r in by_category.values())

    csv_path = asset_path(OUTPUTS, "national_key_categories.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        # variance_share_pct is Approach 1 and is LABELLED as the independent-category
        # approximation it is. It apportions (E U)^2 across categories, which is exact only
        # when their errors are independent - and one livestock count drives both enteric
        # fermentation and manure management, one nitrogen offtake drives managed soils and
        # residential dung, one fuel control drives road and off-road. The covariance-aware
        # answer is read from the released ensemble, where shared quantities move their
        # categories together draw by draw: outputs/pakemis_uncertainty_drivers.csv (rc67;
        # the surrogate parameter ranking this comment used to point at is retired).
        w.writerow(["category", "ipcc_code", "sector", "source_streams",
                    "level_Mt_co2e_AR5", "level_pct", "cum_level_pct",
                    "key_by_level", "variance_share_pct_independent_approx",
                    "cum_variance_pct"])
        for name, share, cum, is_key in level_rows:
            vshare, vcum = variance_lookup[name]
            row = by_category[name]
            w.writerow([name, row["ipcc_code"], row["sector"], row["source_streams"],
                        round(row["level_Mt"], 3), round(share * 100, 2),
                        round(cum * 100, 2), "YES" if is_key else "no",
                        round(vshare * 100, 2), round(vcum * 100, 2)])

    md = ["# National Key Category Analysis (IPCC 2006 Vol 1 Ch 4, Approach 1)\n",
          "Across all %d registered sectors, %.2f Mt CO2e (AR5). A **key category** is one "
          "with a significant influence on the national total; Approach 1 flags categories "
          "cumulatively to the **95%%** threshold on absolute CO2e.\n"
          % (len({v["sector"] for v in by_category.values()}), total),
          "**Level assessment only.** A trend assessment needs a consistent series for every "
          "category between a common base and reference year. Four of the nine sectors "
          "report a single year, so a national trend assessment would be arithmetic without "
          "meaning. The agriculture-only trend assessment remains valid and is produced by "
          "`pkinv.sectors.agriculture.key_categories` in the companion research repository.\n",
          "The totals span reference years 2022 to 2024, so this is a screen across "
          "vintages - see `outputs/national_all_sectors.csv`.\n",
          "## Level assessment\n",
          "| Category | Sector | Mt CO2e | Level % | Cumulative % | Key |",
          "|---|---|---:|---:|---:|:--:|"]
    for name, share, cum, is_key in level_rows:
        md.append("| %s | %s | %.2f | %.1f | %.1f | %s |"
                  % (name, by_category[name]["sector"], by_category[name]["level_Mt"],
                     share * 100, cum * 100, "**KEY**" if is_key else "-"))
    md.append("")
    md.append("## Contribution to national variance\n")
    md.append("Where uncertainty reduction pays off, which is not the same ranking as size. "
              "Shares are (E x U)^2 normalised, the same Approach-1 quadrature that produces "
              "the national band in `outputs/national_all_sectors.csv`.\n")
    md.append("| Category | Sector | Variance share % | Cumulative % |")
    md.append("|---|---|---:|---:|")
    for name, share, cum, _k in variance_rows:
        md.append("| %s | %s | %.1f | %.1f |"
                  % (name, by_category[name]["sector"], share * 100, cum * 100))
    md.append("")
    md.append("## Key categories by level\n")
    for name, share, _c, is_key in level_rows:
        if is_key:
            md.append("- **%s** (%s, %.1f%% of the national total)"
                      % (name, by_category[name]["sector"], share * 100))
    md.append("")
    with open(asset_path(OUTPUTS, "national_key_categories_report.md"), "w",
              encoding="utf-8") as f:
        f.write("\n".join(md))

    print("National Key Category Analysis (IPCC Approach 1, 95%% threshold, %.1f Mt)" % total)
    for name, share, cum, is_key in level_rows:
        vshare, _vc = variance_lookup[name]
        print("  %-32s %-12s %6.2f Mt  %5.1f%%  cum %5.1f%%  var %5.1f%%  %s"
              % (name[:32], by_category[name]["sector"], by_category[name]["level_Mt"],
                 share * 100, cum * 100, vshare * 100, "KEY" if is_key else ""))
    print("  %d of %d categories are key by level" % (len(key_by_level), len(level_rows)))


if __name__ == "__main__":
    main()
