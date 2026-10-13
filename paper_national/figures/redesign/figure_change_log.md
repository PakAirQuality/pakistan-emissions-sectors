# Figure redesign: what changed, what did not, and how it was checked

The redesign was made at release 1.0.0rc63, in what was then `versions/v2`. Since rc64 the eight
figures belong to `paper_national/versions/v3`, and `versions/v2` is the manuscript as rc62
shipped it, with the seven figures described below as "before". The numbering is the final
one; the original number is in brackets.
`figure_inventory.csv` holds the contract for each figure, `figure_value_checks.csv` the
value-by-value comparison with the products, and `figure_design_study.md` the references.

## What did not change

No plotted number moved. `scripts/verify_manuscript_figures.py` opens the released products
itself, without going through either plot-table builder, and compares 253 values with what the
figures draw: module totals, the nine annual estimates, the three change intervals, the four
timing shares, the ensemble median and percentiles, placed mass and closure for each gas, 135
evidence shares, the share of each gas at register locations, every BTR ratio in both
weightings with the three totals, and the five managed-soils values. None disagrees (253 values
after the second review; 243 before it). The reference estimate is 451.86 Mt CO₂e and the configuration is unchanged.

## What changed in every figure

- One style module (`src/pkinv/report/manuscript_style.py`) replaces three sets of settings.
- Drawn at 177 mm or 85 mm, the two widths the journal class gives, and no taller than the
  review page carries. Both layouts place every figure at scale 1.0000 (read from the two
  LaTeX logs). Text is 7.5 to 10 pt, measured in the PDFs.
- One font, DejaVu Sans regular, embedded; gas formulae use Unicode subscripts, so no second
  font is embedded. Panel labels are `(a)`, sentence case, regular weight.
- Titles above figures, release strings and configuration codes are off the plots. The release
  is in each PDF's metadata, which is what the release-identity guard now reads.
- Files are named `f01` to `f08`, as the journal asks.

## Figure by figure

**Fig. 1 [1], construction.** Redrawn from the pipeline's own dependencies. Before: the
monthly grid had one incoming arrow (it needs the monthly tables and the spatial allocation); a
conservation note sat on top of a box; the reference year's 451.86 Mt was printed inside a node
standing for nine years; the province and district tables were absent. After: five lanes
(sources, harmonised inputs, estimation, allocation, products), fourteen nodes. Emission
factors are an input to the annual estimates. The monthly grid has both inputs. District and
province tables are separate, because the province tables already contain the unallocated mass
and the district tables do not. The annual estimates reach each allocation by its own line. No
quantity is drawn; the conservation identities are in a footer.

**Fig. 2 [2], composition, annual estimates, change.** Layout changed from three columns to
bars at left with the annual series over the change panel at right; the three-column version put
nine fiscal years on a 38 mm axis. (a) modules ranked, zero baseline, railways and aviation
visible as lines. (b) nine points, unsmoothed; the axis states that it starts at 380; the two
highest years are both labelled (490.6 and 490.5). (c) the deterministic difference is a
diamond and each row's interval is a bar with its ends printed; before, the difference was an
open circle, the symbol Fig. 3 used for a median.

**Fig. 3 [3], timing evidence and parameter interval.** Same two charts, tightened. (a) plain
class names with the registry code in brackets, one colour, shares printed. (b) retitled
"Conditional parameter uncertainty": diamond for the deterministic 451.86, tick for the median
456.41, bar for 406.71 to 532.86. No density is drawn: the released 10,000-draw prefix gives
406.41 / 456.25 / 532.54, not the published 100,000-draw percentiles.

**Fig. 4 [4], gas maps.** Three equal maps on one extent fill the plate; the gap between title
and maps is gone. Plate carrée with the aspect set at 30.4° N. Palette changed from a one-hue
blue ramp to reversed viridis (dark is high), chosen after rendering cividis, viridis and magma
on the CO₂ grid: cividis is grey through the middle of the range and magma's low end disappears
into the page. The log scale is set by mass: its floor is the decade at or below the smallest of the
cells that together hold 99.9 % of the gas's placed mass, and its ceiling the next 1-2-5 step
above the largest cell. Four cell states are distinct: no value (blank), exactly zero (grey;
2,835 N₂O cells), below the scale (one pale colour, together under 0.1 % of the mass), and on
the scale. Bars are labelled Gg cell⁻¹ yr⁻¹. Headings say "placed mass". Half-mass counts moved
to Fig. 6. Boundaries are one quiet grey, credited on the first map and in the caption.

**Fig. 5 [5a–c], spatial evidence by year.** Now its own figure. Three gas panels, nine bars
each, one legend, the five stored classes in registry words, the denominator on the axis. Colour
separates the classes by lightness, and the rescaled class is hatched; checked in greyscale and
three colour-vision simulations. The per-panel "not that year's own activity" headlines, which
described 2023–24 only without saying so, are off the figure; the provenance text gives them with
the year.

**Fig. 6 [5d–e], surface and concentration.** (a) replaces the proxy-vintage panel: nine kinds
of surface with source and vintage, and the mass retained at province level, in a palette that
is not the evidence palette. A register that falls back to a raster is divided by its located
share. Before, a
quarter of CO₂ (the road network) and 19 % of N₂O (manure) were filed under "point set or ADM2
panel", and cropland was labelled SPAM. (b) the concentration curves on a linear axis, with
"Equal mass per cell". (c) the same curves by number of cells on a true logarithmic axis that
starts at one cell, with half-mass markers (78, 3,021 and 3,566 cells). Before, the axis was a
symmetric-log hybrid with a zero tick.

**Fig. 7 [6], ratios to the national submission.** The dot plot is kept. Ticks are a factor of
two apart; the numerator, denominator and year are in the axis title; totals are squares below a
rule. Points are one colour: the half-to-double band is for orientation, so it no longer
colours points as inside or outside. Three totals: the sum of the sixteen plotted categories
(1.04), that sum with the other-sectors aggregate (1.02), and the national totals excluding
land use (1.01). An open marker and a bracketed value give the ratio at a uniform CH₄ weighting
of 28 on every row where the printed ratio changes (four rows).

**Fig. 8 [7], managed soils.** 85 mm in both layouts (it was 177 mm in the review layout, with
16.9 pt labels). Points on stems from zero in place of bars: diamond for the reference, open
circles for three alternatives (the 2006 direct soil factor, the 2006 pasture factors, and both),
a grey circle for FAOSTAT, set apart. Showing the two substitutions separately as well as
together stops the rows reading as steps toward the comparator. The two different years are printed in the figure.

## Corrections the evidence supported

1. **Surface labels, at the product.** `surface_vintage` called the cropland surface "SPAM 2020".
   It is ESA WorldCover 2021, class 40. The MapSPAM rice surface, the road and rail networks,
   the manure surface and the fire detections had no label. Corrected in
   `pkinv.report.spatial_weights`; 495 rows of one column of
   `outputs/pakemis_spatial_weights_by_year.csv` change and nothing else does.
2. **"Every raster predates the fiscal year it places"** was in the old caption and panel title.
   The road surface is an OpenStreetMap extract of August 2026. Removed.
3. **"All in-country cells are strictly positive for every gas"** was in the generated
   provenance text. 2,835 valid cells hold exactly zero N₂O. Corrected and counted.
4. **The BTR plot table** said no harmonisation was required while its product said the
   comparison is not matched on the methane convention. The table now carries both statements
   and the uniform-28 ratios.
5. **"A finer raster would add no information"** narrowed: a concentration curve does depend on
   the grid; what a finer display grid cannot add is evidence about where sources are.
6. **One symbol, two quantities.** Resolved by the shared glyph grammar.
7. **Float32 running sums** reached "100 %" of CH₄ at 33,039 cells of 33,674. Sums are float64;
   the worst closure residual falls from 0.111 to 0.032 ppm.

## Found and left alone

Not inputs to any figure, recorded for the author: the monthly NetCDF's attribute gives the
spatial-view shares as 82.30 / 8.40 / 9.30 % where `outputs/spatial_view_profile.csv` gives
82.26 / 8.39 / 9.35; a comment line in `outputs/pakemis_longitudinal_uncertainty.csv` still says
the first year carries eight sectors.

## Checks performed

- **Values:** 243 re-read from products, none disagreeing (`figure_value_checks.csv`).
- **Identities:** evidence and surface shares each sum to 100; placed plus unallocated equals
  the national mass for all 27 gas-years; zero and below-limit cell counts recounted from the
  per-cell table; half-mass counts recomputed from the ranked cells.
- **Size and type:** page size, single embedded font, 7.5 pt floor and 2 MB limit on each PDF;
  scale 1.0000 for all eight in both logs (`tests/test_figure_redesign.py`).
- **Manuscript:** eight labels, each cited, numbered in order of first citation; no unresolved
  reference in any of the three PDFs; no LaTeX error.
- **Looked at:** every preview during drawing; the placed pages of both layouts; greyscale and
  deuteranopia, protanopia and tritanopia simulations of all eight (`simulations/`), which
  found one legend clipped and two neighbouring colours printing as one grey, both fixed;
  before beside after at one resolution (`before_after/`).
- **Second reviewer:** an independent agent audited the figures, captions and tables without
  the first drawer's conclusions; its findings and what was done about each are listed below.

## The second review, and what was done

An independent agent was given the figures, captions, plot tables and products, and not the
first drawer's opinion of them. It opened all eight as images and both compiled layouts. It
found three errors that mislead and fourteen places a reader would stumble; each was checked
against the data before anything was changed.

| Finding | Checked | Done |
|---|---|---|
| Fig. 6(a) filed registers with a fallback wholly under "facility locations": 16 % of CH₄ and 8 % of N₂O drawn at points | True. `located_share` gives 5.08 % and 0.73 %; the wastewater register locates 5 % of its stream | Each such stream is split by its located share; population now reads 13 % (CH₄) and 8 % (N₂O) |
| The "1.02" total under the sixteen BTR points is not their total | True. The sixteen sum to 1.036; the product's total also holds "Other sectors" | Three total rows in the figure; the sentence in Sect. 4.2 corrected and both numbers registered as claims |
| Fig. 5(a) shows one road pattern as three evidence classes, so the reference year looks less observed than the two before it | True, and it is the product's own classification | Caption says what the classes mean for road transport and industrial fuels; left to the author as a question about the taxonomy |
| "223.4" for 223.45447 Mt, a double rounding | True | Labels print the plot table's own two decimals |
| Province tables already contain the unallocated mass | True (national = province; province = district + unallocated) | Fig. 1 separates district and province tables and the footer states both identities |
| Fig. 1 lacked emission factors; the two-headed line read as an arrow between the allocations | Fair | Factors are a node; each allocation is fed by its own line |
| Fig. 2 caption said no per-year interval exists, against Fig. 3(b) | True for the reference year | Caption corrected and cross-referenced |
| The map scale spent most of the ramp on under 1 % of the mass; N₂O's top decade was unused | True (CO₂: lower half of the ramp held 64 % of cells and 0.6 % of mass) | Scale set by mass; cells below it in one pale colour |
| Colour bars had no time basis, mixed "1" with "10¹", and neighbouring end labels nearly touched | True | Gg cell⁻¹ yr⁻¹; one tick form; bars inset |
| Boundary credit only in the caption; the dashed legend named nothing | True | Credit on the map; legend uses the supplement's own names |
| "490.6490.5" ran together | True | Labels placed either side of the pair |
| Open markers hid shifts that change a printed digit | True for transport and one total | Drawn on every row whose printed ratio changes |
| The cell count was nowhere | True | In the axis title of Fig. 6(b) |
| Fig. 8 read as a progression | Fair | The two substitutions are shown separately and together |
| Table 2 ran 19.8 pt into the next column beside Fig. 8 | True | Column widths narrowed in its generator |
| The accent blue was also CO₂; a square meant "total" in one figure and "comparator" in another; interval labels differed | True | A slate accent; one glyph per meaning; one interval label |
| Fig. 3(a) class names differed from the text's | True | The plot table uses the text's names |
| Thousands separators were commas; the manuscript uses thin spaces | True | Thin spaces |
| Monte Carlo percentiles are printed more precisely than their standard errors | True; the sentence is the author's and carries registered claims | Not changed; listed for the author |
| Figures sit two to four pages after first citation in the review layout | Partly: three large figures are cited in one sentence | Figures 1 and 3 moved up to their citing paragraphs; the rest follow the float queue |

Not done by the second reviewer: colour-vision simulation (done separately, above), the
technical supplement, and a check of the two source documents behind the BTR and FAOSTAT values.

## Build

`make figures-v3` rebuilds the plot tables, the two generated tables and all eight figures, and
runs the value check. `make papers-v3` does that and compiles both layouts and the supplement.
