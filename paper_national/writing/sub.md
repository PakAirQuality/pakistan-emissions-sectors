# Writing in the national paper — read this before you touch `paper_national/`

This note is the house practice for anyone (person or agent) who edits prose in the
national ESSD paper (`paper_national/versions/<v>/paper.tex`, `technical_supplement.tex`,
`submission.tex`) or its figure captions. It was written after the 8 October 2026 editorial
review, which found that the draft "repeatedly mixes scientific explanation with release
notes, audit commentary and responses to earlier objections." Every rule below exists to
stop one of those three things.

## 1. What the paper is for

ESSD reads a data-description article for how the dataset was generated, how it should be
used, and what limits that use. The reader is a scientist who wants the inventory, not the
history of its repository. Three kinds of text therefore do not belong in the paper:

- **Release notes** — what an earlier version did, what a re-base moved, which guard caught
  what. These go in `CHANGELOG.md` and `docs/reproducibility.md`.
- **Audit commentary** — "this is stated rather than inferred", "nothing recomputed",
  "the register holds". The paper reports the result; the register is cited by file name.
- **Replies to earlier objections** — a sentence whose only purpose is to pre-empt a reviewer.
  State the limitation once, beside the result it qualifies, and move on.

## 2. The voice: the RSASE PM2.5 paper

Carry the progression of the author's PM2.5 paper: **a concrete problem → the modelling
choice → the result → the limitation placed beside the claim it qualifies.**

- The subject of a sentence is the thing acting: the survey, the station record, the
  calculation, the factor. Not "it is worth saying", not "the obvious reading".
- Actions are the authors' work in first person plural: we compile, we estimate, we compare,
  we allocate.
- Inference is hedged and attributed: "indicates", "is consistent with". Evidence is named;
  findings are not "decisive".
- Every number sits beside the table, figure or product that holds it.
- A limit is stated in the same sentence or paragraph as the gain, once.
- Paragraphs open on the scientific point. One task per sentence: method, result, limitation
  are separate sentences.
- No "Importantly", "Moreover", "This highlights"; no rule-of-three cadence for emphasis
  ("sources, assumptions and qualifications" as a closing refrain). Keep necessary technical
  lists (CO2, CH4 and N2O).

## 3. Vocabulary: repository words are translated

| Do not write | Write |
|---|---|
| booked, books | estimated, assigned |
| release pin, pin | reference estimate |
| shipped (cube, product) | released (gridded dataset, product) |
| re-base | the revised calculation |
| control (as a noun for a total) | the aggregate account / the published total |
| verdict | the test result |
| "transferred from the wider road-customer control" | "Petrol assigned to residential generators is deducted from the customer-class quantity otherwise used for road transport." |
| "What places the gridded mass, and how much of the map does the work" | "Spatial allocation evidence and emission concentration" |
| "Activity, factors and coverage" (as an explanation) | name the particular activity record, factor or omitted source responsible |
| "None rescues it." | the five tests and their numerical bounds (a table) |
| `_FillValue`, `REF_2023_24`, `L`/`S` as bare tokens in reader-facing text | "no value (fill)", "the reference configuration", "the ledger-closed / survey-observed reading" (define once, then use) |

## 4. Periods

Define once, in Sect. 2.1: *The inventory covers nine fiscal years from July 2015 to
June 2024. Each fiscal year runs from July to June.* After that write "2015–16",
"2023–24", "the study period" or "the reference year". Keep the explicit FY/calendar labels
only in comparisons that mix the two (the BTR's FY2020–21 against the CRT's calendar 2022;
FAOSTAT's calendar 2023 against our 2023–24). The title states the period as
"July 2015–June 2024" so it cannot be read as ten calendar years.

## 5. Numbers

- Every printed quantity is a registered claim in `tests/paper_numbers/doc_claims.py`,
  anchored by a regex on the sentence and resolved from the product. Changing a sentence
  that carries a number means re-anchoring the claim in the same commit; `python3 -m unittest
  discover -s tests -p test_claims.py` must be green ("anchors lost" is a failure).
- Typeset quantities with `siunitx` (`\SI`, `\num`, `\SIrange`); a bare number is invisible to
  the sweep.
- Keep the deterministic estimate (451.86 Mt) distinct from the Monte Carlo median
  (456.41 Mt). Keep parameter intervals, structural alternatives and unestimated categories
  as three different things; the three-item list in Sect. 2.4 is the one place a list is
  justified.
- Aggregations are named for what they are: "calculation modules" (power includes captive
  generation; transport includes off-road machinery) are not IPCC "sectors" without the
  crosswalk.

## 6. Figures and captions

- Simple bars, lines and maps. Descriptive panel titles ("Annual totals", "Spatial
  allocation evidence"), readable legends, no software identifiers or internal
  configuration codes in the plot text. The dataset version may appear once, small.
- Captions describe what is plotted and name the product. They do not argue with the
  reader, defend the dataset or recount what an earlier version showed.
- Every figure is generated from released products by a script under
  `paper_national/figures/rewrite_inputs/` or `scripts/`; regenerate, never hand-edit.
- The `figure_briefs.md` pattern: for each panel say which kind it shows — deterministic
  estimate, parameter uncertainty, structural alternative, allocation support, missing scope.

## 7. Availability statements and the front page

The front page carries the title, authors and abstract. Dataset identity (version, DOI,
citation, access link) belongs in Data availability; hashes, manifests and the clean-tree
rule belong in `docs/reproducibility.md`. The availability statements are concise: version,
link, citation, reproduction documentation. Do not narrate what is missing beyond one
sentence that says it is pending.

## 8. What an agent may and may not do

- May: correct definite errors, improve structure and readability without changing meaning,
  generate tables and figures from products, cite products, re-anchor claims.
- May not: write new scientific interpretation into the paper. A sentence that attributes a
  cause, ranks a gap, or judges evidence that the products do not already state goes to
  `campaign/.../author_actions.md` (or the current review's equivalent) as a draft for the
  author, with the evidence file named. "Humanize" means closer to the author's voice; it
  never means targeting detectors, inserting imperfections or concealing assistance.
- Record every edit that moves a number, a claim or a label in the review's
  `change_impact.csv`, and every AI-written passage in its `ai_use_record.md`.

## 9. Before you finish

1. `latexmk` all three documents; zero `Float too large`, zero `??`.
2. `python3 -m unittest discover -s tests -p "test_v3_documents.py"` and `-p test_claims.py`.
3. Render every page (`pdftoppm -r 110`) and look at the pages you changed.
4. Figures before the references in `submission.pdf`; margin line numbers on every text page.
