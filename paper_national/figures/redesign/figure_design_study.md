# Figure design study

Made on 11 October 2026, before any production figure was changed. Each article was downloaded as
its publisher PDF and the page carrying the named figure was rendered and looked at; the renders
are in `reference_board/` (kept locally, not in the repository; `ATTRIBUTION.md` there lists
source and licence). These are references to learn from, not templates: each entry says what is
taken and what is left.

## A. Rougier, Droettboom and Bourne (2014), Figs 6 and 7

Source: PLOS Comput. Biol. 10(9), e1003833, <https://doi.org/10.1371/journal.pcbi.1003833>.
Renders: `rougier_fig6-5.png` (PDF p. 5), `rougier_fig7-6.png` (PDF p. 6).

**Question.** How does the same data read under different encodings and layouts?

**What is on the page.** Figure 7 shows seven series twice. On the left they share one axes: a
legend box sits on the curves, eight colours cycle, the tick labels run to three decimals and
collide, and a yellow background and a grid compete with the data. On the right each series has
its own row; the series name is written at the left of its row, the other six series are drawn
faintly behind it for context, the x axis carries three ticks, and a grey band stands for the
range instead of a y axis. Figure 6 has two halves. Discs sized by radius exaggerate a 3:1 ratio
that discs sized by area show correctly. Ten bars on a full range (0–100) look alike; the same
bars on a partial range (80–100) look very different.

**Adopted.**
1. Small aligned panels with the name written beside the data, in place of one crowded axes and a
   legend box. Used for the three gas panels of Fig. 5 and the row labels of Figs 2(c), 7 and 8.
2. Few ticks, chosen: every axis here has at most six, at round values.

**Not copied.** The right panel of Figure 7 drops the y axis because its point is shape only. Our
readers need magnitudes, so every quantitative panel keeps a labelled scale. No series is added
to any figure for the sake of the layout.

**Second lesson, from Figure 6.** A bar's length is read from its baseline. Every bar here starts
at zero (Figs 2a, 3a, 5, 6a). A line chart may use a partial range, so Fig. 2(b) states its range
on the axis and is not drawn as bars.

**Applies to** Figs 2, 3, 5, 7, 8.

## B. Crameri, Shephard and Heron (2020), Figs 2 and 6

Source: Nat. Commun. 11, 5444, <https://doi.org/10.1038/s41467-020-19160-7>.
Renders: `crameri_fig2-03.png` (PDF p. 3), `crameri_fig6-07.png` (PDF p. 7).

**Question.** Which colour maps keep their order for readers with a colour-vision deficiency and
in greyscale, and how is a map matched to the data?

**What is on the page.** Figure 2 is a table of colour bars: viridis, cividis, kry, thermal and
batlow down the side; deuteranopia, protanopia, tritanopia and greyscale across. Each of the five
stays a monotone light-to-dark ramp in every column. Jet, in the last row, breaks into bands and
in greyscale is dark at both ends. Figure 6 is a decision tree: is the data ordered; has it a
central value (diverging) or not (sequential); do small variations matter (continuous or
discrete); are there empty values ("prevent colour map containing the figure background colour");
and, for a light background, which end of the ramp carries the high values.

**Adopted.**
1. Cell mass is ordered, positive and has no centre: a sequential map, tested at the real data
   range, with high values dark on our white page. No diverging map appears anywhere in the set,
   because nothing plotted has a meaningful centre except ratio = 1 in Fig. 7, which is a position,
   not a colour.
2. Empty is not a colour on the ramp. Cells outside the reporting mask take the page background;
   valid cells with exactly zero mass take a neutral grey that is not on the ramp either. Three
   states, three treatments.

**Not copied.** The rounded dark boxes and the flow-chart look of Figure 6 are that paper's
illustration style. Fig. 1 here uses plain rectangles.

**Applies to** Fig. 4 (ramp, zero, no data), Figs 5 and 6 (categorical sets checked in the same
three simulations and in greyscale).

## C. Wu et al. (2024), INTAC, Figs 1 and 4

Source: Earth Syst. Sci. Data 16, 2893–2915, <https://doi.org/10.5194/essd-16-2893-2024>.
Renders: `wu_fig1-03.png` (PDF p. 3), `wu_fig4-11.png` (PDF p. 11).

**Question.** Figure 1: what goes into the integrated inventory and in what order is it
transformed? Figure 4: where are nine species emitted?

**What is on the page.** Figure 1 has three titled columns read left to right: inputs (seven
inventories stacked in priority order, and a block of configuration files), the integration model
(five steps stacked top to bottom: source mapping, species mapping, temporal disaggregation,
spatial allocation, spatial–temporal coupling), and the output (year, step, resolution, species,
and a thumbnail map). Figure 4 is a 3 × 3 grid of maps of equal size and extent. Each map has its
species name inside the frame at lower left and its own colour bar directly beneath, with the
unit under the bar; each bar has its own range.

**Adopted.**
1. Columns that mean something: inputs, operations, products. Fig. 1 here is laid out in lanes,
   and a node's lane says what kind of thing it is.
2. Equal map panels, one extent, one colour bar per map placed immediately under it with its unit.
   Fig. 4 here does the same for three gases, and says in the caption that the scales differ.

**Not copied.** The orange and green panel fills and gradient arrows of Figure 1; its tiny
metadata; the blue-to-red map palette, which has a perceptual centre the data lack; and the
workflow itself. INTAC merges inventories by priority. PakEmis builds one inventory and allocates
it, so the dependency graph is taken from our own code, including a branch INTAC's figure does
not have (mass that cannot be placed).

**Applies to** Figs 1 and 4.

## D. Crippa et al. (2024), EDGAR v8.0, Figs 6 and 9

Source: Earth Syst. Sci. Data 16, 2811–2830, <https://doi.org/10.5194/essd-16-2811-2024>.
Renders: `crippa_fig6-10.png` (PDF p. 10), `crippa_fig9-13.png` (PDF p. 13).

**Question.** Figure 6: what did a change of proxy do to the map of industrial CO₂? Figure 9: how
do two input fields combine into a spatial weight?

**What is on the page.** Figure 6 sets version 7.0 above version 8.0, a world map and a regional
zoom for each, on the same extent and the same logarithmic colour scale, so a difference in colour
is a difference in the data. Figure 9 stacks three maps: heating degree days, population, and the
cell weights that result, each with a binned legend beside it.

**Adopted.**
1. A comparison is only readable on matched extents and a stated scale. Our three gas maps share
   one extent; because their ranges cannot be shared, each bar is labelled with its gas and the
   caption says that equal colours are not equal masses.
2. Show the mechanism, not only the result. Figure 9 makes the allocation inspectable by showing
   what the weight was built from. Fig. 6(a) here does the tabular equivalent: for each gas, which
   surface, of which vintage, carries how much of the placed mass.

**Not copied.** The rainbow palettes; legend entries such as "0.000010001 – 0.0001"; the logo
inside the map frame. No before-and-after pair is drawn here, because PakEmis has one allocation,
not two versions of one.

**Applies to** Figs 4 and 6.

## E. Li et al. (2023), ABaCAS-EI, Fig. 3

Source: Earth Syst. Sci. Data 15, 2279–2294, <https://doi.org/10.5194/essd-15-2279-2023>.
Render: `li_fig3-06.png` (PDF p. 6).

**Question.** Which sectors drove the 2013–2021 change in each of five species?

**What is on the page.** Five narrow panels side by side share one set of seven sector rows,
named once at the far right. Bars run left or right of a zero line in each panel. Each panel has
its own x range, and the shared axis title says the units differ (Gt for CO₂, Mt for the rest).

**Adopted.**
1. Rows named once and aligned across panels. Used for the three dependence settings in Fig. 2(c)
   and the category rows of Fig. 7.
2. A visible zero for a signed quantity. The change in Fig. 2(c) can be negative under one
   setting, so zero is drawn and labelled.

**Not copied.** Bold type throughout; the fourteen-colour legend of its Figure 2 on the same
page; and the chart type for Fig. 8. Our four managed-soils values are alternative factor choices
for one year, not a decomposition of a change, so they are points, not a waterfall.

**Applies to** Figs 2, 7, 8.

## F. ESSD submission and figure requirements

Source: <https://www.earth-system-science-data.net/submission.html>, read 11 October 2026.

Journal requirements, as written there:

- Review file: one PDF, one-column `manuscript` class, embedded fonts, pages and lines numbered,
  at most 50 MB; figures and captions in the text near first mention.
- Figure files for production: named `f01`, `f02`, …; panels of a composite collected in one
  file; PDF, PS, EPS, JPG, PNG or TIF; 300 dpi; width not less than 8 cm; a PDF figure at most
  2 MB, other formats at most 5 MB, all files together at most 30 MB.
- Vector line work preferred, fonts embedded, no hidden objects, **one font family** (regular,
  italic, bold and bold-italic count as four fonts).
- Content: panel labels lower case in brackets, `(a)`; ranges with an en dash and no spaces;
  coordinates with a degree sign and a space before the direction (30° N); a space between number
  and unit (1 %); units written exponentially (W m⁻²).
- A legend in the figure explains every symbol; the caption does not describe symbols in words.
- Maps: United Nations naming; avoid drawing contested borders; keep caption, legend and labels
  neutral where a disputed territory is shown; credit the boundary source.
- Authors are encouraged to publish the plot data.

Our own design choices, which the journal does not prescribe: 8 pt ticks and annotations, 9 pt
axis labels, 10 pt panel headings, a 7.5 pt floor; one regular weight only, with subscripts set as
Unicode characters so that no second font is embedded; figures drawn at 177 mm or 85 mm and placed
at that size in both layouts.

One consequence for the maps: the boundary layer is drawn quietly, the provinces and territories
are not named on the map, and the caption states the boundary source and the reporting frame
without characterising any border.

## What this changes in the eight figures

| Figure | Lesson applied |
|---|---|
| 1 construction | lanes with meaning (C); plain nodes (B); graph from our own code (C) |
| 2 composition, history, change | zero baselines for bars, stated range for the line (A); rows named once, visible zero (E) |
| 3 temporal support, parameter interval | direct labels, few ticks (A) |
| 4 gas maps | sequential ramp, dark = high on white, zero and no-data off the ramp (B); equal panels, bar under each map (C); shared extent, scales labelled as different (D) |
| 5 spatial evidence by year | aligned small panels, one legend (A); categorical set checked under simulation (B) |
| 6 proxy and concentration | show the mechanism (D); direct labels (A) |
| 7 ratios to BTR1 | rows named once, reference line drawn (E) |
| 8 managed soils | points, not a waterfall (E); zero baseline (A) |
