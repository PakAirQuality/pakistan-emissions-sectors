# Ask PakEmis: an evaluation set from the inventory's real confusions, and a first baseline

T-AGENT-1. Everything is in `~/Desktop/pakemis-explorer/eval/` on `campaign/pakemis-24h`,
committed locally; nothing pushed or provisioned.

## The cases

Fifty-four. Each carries the question, the period, scope, gas, configuration and warming-potential
basis it assumes, a reference answer, a tolerance, and a truth spec that establishes the figure
**by execution**: the typed request runs through the same `Service` the API serves from. No number
was typed by hand; all fifty-four resolved against 1.0.0rc59, and nine were re-derived from this
repository's published CSVs (zero disagreements), so the references are not engine-circular.

Covered: fiscal versus calendar basis, and release versus service version; native mass versus
CO2e, and AR5 versus AR6 (refused at district grain; `compare` refuses to cross bases);
calculation module versus IPCC reporting sector (captive generation: power module 63.37 Mt,
reporting sector 57.82 Mt); total rows never added to their parts; gross versus delivered gas
across the eight transfer ledgers (fertiliser feedstock 7,813.8 Mm3 unresolved); the L and S dung
configurations (469.63822 against 464.50543 Mt) and the 46.7741 Mt
of air-dry dung cake with no destination - dung cake, not CO2e; parameter intervals against the
twenty-eight structural alternatives, an endpoint of which is not an extra structural allowance;
observed against modelled timing; spatial closure, unallocated mass, borrowed geography; NE, IE,
NO and NA as four distinct statements; questions the evidence cannot answer; and two inventories
agreeing because they share an input. Eighteen are ordinary reader questions.

## The isolation actually achieved

Twenty cases are held out in `eval/holdout/`, frozen by SHA-256 before the baseline, which ran on
the development split alone. `check_isolation.py` and an added API test assert three checkable
things: the digests still match; no module the agent loads at runtime names the holdout; no
holdout question appears under `api/`, `assistant/`, `web/` or `scripts/`.

**This is not secrecy.** Same repository, same working tree, no access control, no separate
remote - anything with read access opens it in one command. The claim is only "frozen before
measurement, and absent from what the agent reads at runtime"; it is good for a few checkpoints,
not for iteration.

## The baseline

gemini-3.1-pro-preview (the provider default under the repository's existing key), thirty-four dev
cases, 3.61 M tokens, a fresh conversation each. Fixed checks over the event stream; no LLM
preference score.

| axis | pass |
| --- | --- |
| numeric correctness | 15/18 (0.83) |
| boundary correctness | 20/22 (0.91) |
| source support | 29/31 (0.94) |
| uncertainty and missing information | 8/10 (0.80) |
| appropriate refusal | 3/5 (0.60) |

All five axes clean: **25/34 (0.74)**. Twenty-nine answers came through the tool loop, four from
the model with no tool call at all, and two cases produced nothing.

## Top failure modes

**A refused boundary answered with a different one, fully receipted.** D22 asked for the gross-gas
accounting alternative, which is not queryable (`UnknownDimensionValue`). The agent called
`query_emissions{spatial_view: "accounting"}` - the spatial view, not the configuration - and wrote
"Under the gross-gas accounting view ... the national total is 469.64", the reference total. The
receipt is valid and proves a different question was answered: source support is not correctness.

**No answer at all when the boundary is ambiguous.** D19 (industry as IPCC reports it) and D28
(district uncertainty) both hit the eight-call cap and emitted nothing. The cause is mechanical:
the tool schema advertises `group_by` values (`module`, `spatial_view`) the engine refuses at
national grain, and `get_uncertainty` returns the same national rows for every `resolution`, so
nothing tells the agent to stop.

**Uncertainty reported as a point.** D26 returned two Monte Carlo medians (474.20 Mt twice), no
interval, no percentage. The `get_uncertainty` cells *are* P50s; the -10.5/+16.2 per cent interval
sits in a block the model's view cannot print. It also gave 474.20 as the reference value, 469.64.

**A false unavailability, straight from the prompt.** D32 asked whether provincial figures exist
for 2015-16. They do (Punjab 220.11 Mt). With no tool call the agent said adm1 is reference-year
only - what the system prompt states. The prompt contradicts the engine, and four of thirty-four
answers came this receipt-free way.

**Boundary left unnamed** where a question is two-valued: D16 gave power 63.37 Mt without saying
captive generation is inside it.

## Retrieved documents as instructions

`get_completeness` and `get_method` ship the registries' free-text `justification` and `notes` -
prose transcribed from government documents, up to 25 KB a call - into the model's tool-result
content, unfenced, and the prompt carries no rule that tool text is data
rather than instruction. A probe placing an override instruction there (no repository data
modified) was ignored on the one turn tested: mechanism present, defence absent, exploit unproven.

## Regression

Before any edit: `test-api` 492, `test-web` 433. After: 494 and 433, the two added being the
holdout guard. `test_vendor.py` passes; the vendored engine was untouched.
