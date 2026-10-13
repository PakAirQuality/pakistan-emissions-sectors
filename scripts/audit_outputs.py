"""Every file in outputs/ should have something that writes it. This finds the ones that do not.

WHY. outputs/ is versioned, and a versioned file outlives the code that made it. When the ten
sectors were harmonised onto one reporting period their outputs were renamed, and the previous
vintages simply stayed - `fugitives_totals_2020.csv` sat beside `fugitives_totals_2024.csv` for
three rounds, quoting 3.81 Mt against a current 24.69. Nothing was wrong with either file. What
was wrong is that both were present, both parsed, and one of them was what a live test happened
to be reading.

An orphan is not a warning about disk space. It is a second vintage with a plausible name,
which is the same defect as three national totals in circulation - the failure this repository
has now been bitten by twice - in the one directory a reader is told to trust.

HOW. Static, not empirical: the audit searches `src/` and `scripts/` for each filename, both
literally and with its digit runs generalised, because output names are routinely built as
`"industry_monthly_%d.csv" % data.year` or `"%s_totals_%d.csv" % (name, year)`. A file no
source mentions in either form is reported.

WHAT IT DOES NOT DO. It does not delete anything, and it does not claim a matched file is
current - only that something in the tree knows how to write it. Products of optional,
network-gated or companion-repository phases are declared in KNOWN with a reason, the way
manuscript constants are, so the list a reader argues with is short and each entry says why.

AND IT WOULD NOT HAVE CAUGHT THE CASE THAT PROMPTED IT, which is worth stating rather than
implying otherwise. Generalising the digits means `fugitives_totals_2020.csv` matches a source
writing `fugitives_totals_2024.csv`, so the superseded vintage reads as accounted for. That is
what `twins()` is for: where two files share a stem and differ only in their year, each must be
written LITERALLY by some source. A vintage nobody writes any more fails that even though the
loose pattern accepts it. Two checks, because one of them has a known blind spot and saying so
is cheaper than pretending it does not.

Usage:  python3 scripts/audit_outputs.py [--verbose]
Exit:   1 if any output is unaccounted for, or any vintage twin is no longer written
"""

from pkinv.assets import asset_path
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUTS = asset_path(ROOT, "outputs")
SEARCHED = (asset_path(ROOT, "src"), asset_path(ROOT, "scripts"))

# Directories under outputs/ whose contents belong to a phase outside `make all`, with the
# command that writes them. Listed as trees rather than file by file because their contents
# are enumerated at run time (one file per district, per validation montage, per gas).
KNOWN_TREES = {
    "outputs/gis": "research tier per docs/spatial_products_contract.md - the sector gis runners IN THIS REPO (agriculture/residential/railways run_gis), hand-run; needs the gis extra and "
                   "the WorldPop and land-cover caches",
    "outputs/districts": "research tier per docs/spatial_products_contract.md; the CANONICAL district panels live at outputs/district_totals_2024.csv etc.",
    "outputs/paper_figure_data": "the national manuscript's stored-query figure data (v1.0.0): "
                                 "scripts/make_paper_artefacts.py writes one canonical CSV per figure "
                                 "row of paper_national/queries/paper_artefacts.csv",
    "outputs/paper_figures": "the drawn PNG+PDF of the same stored-query figures, from the same script",
    "outputs/semantic": "the semantic release (v1.0.0): pkinv.semantic.build writes one canonical "
                        "CSV + one Parquet twin per table in FACTS/DIMENSIONS plus semantic_release.json; "
                        "the 'Semantic release' phase is in all three build definitions",
    "outputs/mc_draws": "the injected sector engines' persisted draw files (rc12): "
                        "core/mc_draws.py writes <name>.csv + <name>.meta.json from a "
                        "name argument, so the sidecar filenames are constructed at "
                        "run time; the draw stages are in all three build definitions",
}

# Individual files whose writer is not in this repository, or is an optional phase.
KNOWN = {
    "aviation_adsblol_pilot_days.csv": "make aviation-adsblol-pilot; the ADS-B cache is "
                                       "several GiB and ODbL, so only aggregates are versioned",
    "aviation_adsblol_pilot_summary.csv": "same",
    "aviation_adsblol_pilot_summary.json": "same",
    "aviation_adsblol_positive_controls.csv": "same",
    "aviation_adsblol_route_pilot.csv": "same",
}


def _sources():
    """Every source file that could name an output - excluding this one.

    This file is skipped because it writes nothing and yet names outputs: the docstring above
    quotes `fugitives_totals_2020.csv` as the example that prompted the audit, and while that
    string was being searched, the audit read its own prose as evidence that something writes
    the file. A detector that names its examples has to exclude itself or it immunises them.
    """
    text = []
    for tree in SEARCHED:
        for root, _dirs, files in os.walk(tree):
            if "__pycache__" in root:
                continue
            for name in files:
                if asset_path(root, name) == os.path.abspath(__file__):
                    continue
                if name.endswith((".py", ".csv")):
                    with open(asset_path(root, name), encoding="utf-8",
                              errors="replace") as f:
                        text.append(f.read())
    return "\n".join(text)


def _patterns(name):
    """The literal name, and the same name with each digit run generalised.

    `railways_totals_2024.csv` also matches a source writing `railways_totals_%d.csv` or
    `%s_totals_%d.csv`; the stem is required to survive so that generalising cannot turn a
    filename into a pattern that matches everything. rc37: the rule moved to
    pkinv.core.filenames so the data/ audit (pkinv.report.data_provenance) shares it.
    """
    from pkinv.core.filenames import name_patterns
    yield from name_patterns(name)


def audit():
    """(accounted, orphans, declared) - three lists of repo-relative paths."""
    text = _sources()
    accounted, orphans, declared = [], [], []
    for root, _dirs, files in os.walk(OUTPUTS):
        rel_dir = os.path.relpath(root, ROOT)
        if any(rel_dir == t or rel_dir.startswith(t + os.sep) for t in KNOWN_TREES):
            declared.extend(asset_path(rel_dir, n) for n in sorted(files))
            continue
        for name in sorted(files):
            rel = asset_path(rel_dir, name)
            if name in KNOWN:
                declared.append(rel)
            elif any(re.search(p, text) for p in _patterns(name)):
                accounted.append(rel)
            else:
                orphans.append(rel)
    return accounted, orphans, declared


def twins():
    """Superseded vintages: year-variants of one stem that no source writes by name.

    Grouped on the stem alone, so `<stem>_2020.csv` and `<stem>_2024.csv` are compared and a
    lone `<stem>_2024.csv` is not. Where a stem has more than one year, each file must appear
    VERBATIM in the sources; a `%d` writer is not enough, because one `%d` writer produces one
    file per run and the extra ones are what it used to produce.
    """
    text = _sources()
    by_stem = {}
    for name in sorted(os.listdir(OUTPUTS)):
        if not os.path.isfile(asset_path(OUTPUTS, name)):
            continue
        m = re.match(r"^(.*?)_((?:fy|cy)?(?:19|20)\d{2}(?:_\d{2,4})?)(\.[a-z]+)$", name)
        if m:
            by_stem.setdefault((m.group(1), m.group(3)), []).append(name)
    stale = []
    for (stem, ext), names in sorted(by_stem.items()):
        if len(names) < 2:
            continue
        for name in sorted(names):
            if name not in text and name not in KNOWN:
                stale.append((stem + ext, name))
    return stale


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    accounted, orphans, declared = audit()
    stale_twins = twins()
    total = len(accounted) + len(orphans) + len(declared)
    print("outputs audit: %d files" % total)
    print("  %d written by something in src/ or scripts/" % len(accounted))
    print("  %d declared as belonging to an optional or companion phase" % len(declared))
    if "--verbose" in argv:
        for path in declared:
            print("      %s" % path)
    if orphans:
        print("  %d UNACCOUNTED FOR - nothing in this repository writes these:"
              % len(orphans))
        for path in orphans:
            print("      %s" % path)
        print("    Either the generator was removed and the file is a superseded vintage, or "
              "it belongs to a phase that should be declared in KNOWN with the reason.")
    else:
        print("  0 unaccounted for")

    if stale_twins:
        print("  %d SUPERSEDED VINTAGE(S) - a year-variant no source writes by name:"
              % len(stale_twins))
        for stem, name in stale_twins:
            print("      outputs/%s   (stem %s has more than one year)" % (name, stem))
        print("    A second vintage under a plausible name is what a reader or a test reads "
              "by accident. Retire it, or declare it in KNOWN.")
    else:
        print("  0 superseded vintages")
    return 1 if (orphans or stale_twins) else 0


if __name__ == "__main__":
    raise SystemExit(main())
