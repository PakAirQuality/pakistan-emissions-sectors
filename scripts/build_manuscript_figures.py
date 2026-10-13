#!/usr/bin/env python3
"""Rebuild the plot tables, the two tables generated from them, and the five figures that are
not drawn from the grid: f01, f02, f03, f07 and f08.

WHY ONE COMMAND. These figures were run by hand. The plot-data builder and both plotting
scripts sat in no build phase and no Makefile target, so a release could move a number and
leave the figure that prints it behind; the gridded pair had exactly that defect at rc61 and
was given a phase for it, and these five were not. The steps run in dependency order and stop
at the first failure. The gridded figures (f04, f05, f06) keep their own script and phase,
scripts/make_fig_ghg_grid.py.

    python3 scripts/build_manuscript_figures.py            build
    python3 scripts/build_manuscript_figures.py --check    the plot tables only; writes nothing
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

STEPS = (
    "scripts/build_rewrite_figure_data.py",
    "scripts/make_closure_table.py",
    "scripts/make_btr_qualified_table.py",
    "paper_national/figures/rewrite_inputs/plot_construction.py",
    "paper_national/figures/rewrite_inputs/plot_figures.py",
)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.join(ROOT, "src") + os.pathsep + env.get("PYTHONPATH", "")
    env.setdefault("PKINV_ROOT", ROOT)
    steps = STEPS[:1] if "--check" in argv else STEPS
    for step in steps:
        command = [sys.executable, "-B", os.path.join(ROOT, step)] + (["--check"] if "--check" in argv else [])
        done = subprocess.run(command, cwd=ROOT, env=env)
        if done.returncode != 0:
            print("[FAIL] %s exited %d" % (step, done.returncode))
            return done.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
