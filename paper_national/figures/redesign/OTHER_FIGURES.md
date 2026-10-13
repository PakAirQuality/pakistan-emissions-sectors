# Figures found and not redesigned

The redesign covers the main figures of the rewritten manuscript. The two supplied PDFs were
builds of `paper_national/versions/v2/`, which is kept as release 1.0.0rc62 shipped it, with its
seven figures (`figures/fig1_…fig5_*.pdf`, `fig_ghg_grid*.pdf`). The eight redesigned figures
(`figures/f01_…f08_*.pdf`) belong to `paper_national/versions/v3/`. Found beside them:

- **The technical supplement has no figures.** Its only figure-related content is the generated
  provenance text of the gridded figures (`fig_ghg_grid_provenance.tex`), which was rewritten with
  them.
- **The v1 national manuscript and the sector papers** draw about sixty PNG figures through
  `src/pkinv/report/figures.py` and `src/pkinv/report/paper_figures.py` (into `outputs/figures/`
  and `outputs/paper_figures/`). They are a different manuscript line, are guarded by
  `tests/test_figure_text.py`, and were not touched. They do not use the new style module.
- **`paper_national/figures/fig_architecture.tex`** is a v1 TikZ diagram; not used by v2.
- **`rewrite_inputs/data/provincial_so2_ratios.csv`** is still built and no figure draws it; the
  comparison it holds is a table in the v2 appendix.
