"""Copy regenerated figures from outputs/ into every paper's figures/ directory.

For each PNG a paper references, find the matching basename anywhere under outputs/ and copy it over
when the contents differ. Run before compiling any paper.

This originally covered only the companion nowcasting paper, so the main inventory paper had NO sync
mechanism and silently rendered figures up to a month older than the results they illustrated -- map
titles and Monte-Carlo panels showing superseded totals. Both papers are now handled, and
tests/paper_numbers/test_release_integrity.py fails if any shipped figure is older than the output it derives from.
"""

from pkinv.assets import asset_path
import filecmp
import os
import re
import shutil

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SECTORS = ("agriculture", "waste", "transport", "power", "residential", "ippu",
           "fugitives", "railways", "aviation")
# Every manuscript's figures/ directory: one paper per sector, plus the cross-sector paper.
# main() skips entries that do not exist yet, so listing a paper before it is written is
# harmless - which is what makes it safe to register all nine up front.
FIG_DIRS = ([asset_path(ROOT, "paper_national", "figures")]
            + [asset_path(ROOT, "papers", s, "figures") for s in SECTORS])
# Papers that renamed a figure on import need an explicit mapping, or basename matching silently
# finds no source and the stale copy ships. Both of these were stale for weeks for exactly that
# reason: the paper shortened the name and nothing noticed.
ALIASES = {"air_trend.png": "air_trend_chart.png"}
OUTPUTS = asset_path(ROOT, "outputs")


def _index_outputs():
    idx = {}
    for dp, _, files in os.walk(OUTPUTS):
        for fn in files:
            if fn.endswith(".png"):
                idx.setdefault(fn, asset_path(dp, fn))   # first match wins
    return idx


def generated_tex():
    """The generated .tex files: those a build phase declares writing, and everything under a
    generated/ folder (three supplement tables there are made by hand-run scripts that their
    own --check tests keep current). They are skipped when collecting figure names (rc69): a
    generated fragment is not where a paper names its figures, and several are written by
    phases that run AFTER this one, so reading them made the strict build's order check
    refuse to start. tests/test_sync_figures.py holds that none includes a PNG."""
    import glob
    import sys
    sys.path.insert(0, os.path.join(ROOT, "src"))
    from pkinv import run_all
    found = {os.path.normpath(asset_path(ROOT, w)) for p in run_all.PHASES for w in p.writes
             if w.endswith(".tex")}
    for figs in FIG_DIRS:
        paper = os.path.dirname(figs)
        found.update(os.path.normpath(p) for p in glob.glob(
            os.path.join(paper, "**", "generated", "*.tex"), recursive=True))
    return found


def _sync(figs, skip=frozenset()):
    idx = _index_outputs()
    synced, missing, current = [], [], 0
    names = {fn for fn in os.listdir(figs) if fn.endswith(".png")}
    paper = os.path.dirname(figs)
    for dp, _, files in os.walk(paper):
        if os.path.abspath(dp).startswith(os.path.abspath(figs)):
            continue
        for fn in files:
            if not fn.endswith(".tex") or os.path.normpath(asset_path(dp, fn)) in skip:
                continue
            with open(asset_path(dp, fn), encoding="utf-8") as handle:
                names.update(re.findall(r"\\includegraphics(?:\[[^]]*\])?\{([^}]+\.png)\}",
                                        handle.read()))
    for fn in sorted(names):
        src, dst = idx.get(ALIASES.get(fn, fn)), asset_path(figs, fn)
        if not src:
            missing.append(fn)
        elif not os.path.exists(dst) or not filecmp.cmp(src, dst, shallow=False):
            shutil.copy2(src, dst)
            synced.append(fn)
        else:
            current += 1
    return synced, current, missing


def main():
    skip = generated_tex()
    for figs in FIG_DIRS:
        if not os.path.isdir(figs):
            continue
        label = os.path.relpath(figs, ROOT)
        synced, current, missing = _sync(figs, skip)
        print("%s: %d refreshed, %d already current, %d paper-only (no output source)"
              % (label, len(synced), current, len(missing)))
        if synced:
            print("  refreshed: " + ", ".join(synced))
        if missing:
            print("  no source (kept as-is): " + ", ".join(missing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
