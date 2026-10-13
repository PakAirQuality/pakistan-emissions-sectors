# Plot tables and plotting scripts for the v3 manuscript figures

Everything here is generated. Nothing is transcribed and nothing is edited by hand.

| What | Where | Made by |
|---|---|---|
| Plot tables for figures 2, 3, 7, 8 and the closure table | `data/*.csv` | `scripts/build_rewrite_figure_data.py`, from the released products under `outputs/` |
| Figure 1 | `../f01_construction.pdf` | `plot_construction.py` |
| Figures 2, 3, 7, 8 | `../f02_*.pdf`, `../f03_*.pdf`, `../f07_*.pdf`, `../f08_*.pdf` | `plot_figures.py` |
| Figures 4, 5, 6 and their tables | `../f04_*.pdf` … `../f06_*.pdf`, `../fig_ghg_grid_*.csv` | `scripts/make_fig_ghg_grid.py` |
| PNG previews of all eight | `previews/` | the same scripts |
| The style every figure uses | `src/pkinv/report/manuscript_style.py` | — |

One command rebuilds the eight figures: `make figures-v3`. `make papers-v3` rebuilds them and
compiles the two manuscript layouts and the technical supplement.

`transcribed_csv/` is a record, not an input: the values an editor transcribed from an earlier
printed manuscript, which `tests/test_rewrite_figure_data.py` compares with the tables built from
the products. The redesign record (reference study, figure inventory, change and verification
log, before/after sheet) is in `../redesign/`.
