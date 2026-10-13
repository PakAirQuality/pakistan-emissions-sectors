# The classification scheme, and the migration to it

**IPCC 2006 is canonical.** Codes in every shipped product are IPCC 2006, taken from Volume 1
Chapter 8 Table 8.2, *Classification and definition of categories of emissions and removals*
(held at `data/raw/ipcc/ipcc2006_V1_8_Ch8_Reporting_Guidance.pdf`). The crosswalk to the
UNFCCC common reporting tables is published as `outputs/pakemis_category_crosswalk.csv`.

## What was wrong

Until 2026-10-06 a column named `ipcc_code` carried values from two classifications at once.

* **Sector 3 was UNFCCC CRT.** Provably: it used `3.I` *Other carbon-containing fertilisers*
  and `3.J` *Other (agriculture)*, which the 2006 Guidelines do not define; its `3.E` read
  *Prescribed burning of savannas* and its `3.D` *Agricultural soils*, both CRF labels.
* **Sector 4 was IPCC 2006.** Provably: Waste sat at `4`, and the string `5.A` appeared
  nowhere in the repository.
* **Energy (1.x) and IPPU (2.x) are identical in both schemes**, which is why the mix survived
  review for so long — most of the inventory looked consistent.

An external reviewer found it in the companion's category table: enteric fermentation printed
at `3.A` (CRT; IPCC 2006 uses `3.A.1`) beside solid-waste disposal at `4.A` (IPCC 2006; the
CRT code is `5.A`). Their conclusion was correct — it makes automated comparison and
aggregation unsafe — and so was their warning that renaming the printed column would not be
enough, because the *exports* carried the mixed codes.

The hybrid had already cost something before it was named. LULUCF had to be filed under a
sentinel `LU`, because IPCC 2006 would put land at `3.B` (taken by Manure management) and the
CRT would put it at `4` (taken by Waste). And inside `outputs/pakemis_btr_comparison.csv` the
string `3.B` denoted *Land* on one row and *Manure management* on the row after it.

## Where the codes come from, and where they deliberately do not

The target codes were read from Table 8.2 — **not** from `scripts/build_btr_comparison.py`,
whose BTR side is itself shifted: Pakistan's submission books urea at `3.C.2`, which Table 8.2
reserves for *Liming*, and indirect manure N₂O at `3.C.5`, which Table 8.2 reserves for
indirect *soils* N₂O. Taking the target from there would have reproduced a second hybrid, and
would have conflated the two nitrogen terms this migration exists to separate.

## The grain is the component, not the category label

Two CRT categories **split** when expressed in IPCC 2006, along a line the engines already
compute:

| PakEmis (CRT) | IPCC 2006 | why |
|---|---|---|
| `3.B` Manure management | `3.A.2` for CH₄ and **direct** N₂O | Table 8.2 books both gases under 3.A.2 |
| | `3.C.6` for **indirect** N₂O | a category of its own, outside the livestock block |
| `3.D` Agricultural soils | `3.C.4` direct N₂O (6 components) | |
| | `3.C.5` indirect N₂O (9 components) | Table 8.2 puts *both* indirect pathways in 3.C.5 |

So a code is a property of the **component**, not of the engine category.
`category_ledger.category_codes()` maps an engine category to exactly one code and raises on
two; it therefore cannot express this, and the split categories are deliberately omitted from
it so that a caller still keying on the category gets a `KeyError` rather than a plausible
wrong answer. `category_ledger.component_code(category, subitem, gas)` is the function
products call.

**The migration is not injective on code text.** `3.A`, `3.B`, `3.C` and `3.D` all exist before
*and* after with different meanings — today's `3.D` is Agricultural soils, IPCC 2006's `3.D` is
the *Other* block. A string rename would have produced plausible, wrong codes that no test
could see. Everything keys on `component_id`, which is `module|category|subitem|gas` and
encodes no code, which is why **no shipped identifier moved**.

## The rest of the mapping

`3.A`→`3.A.1`; `3.C` rice→`3.C.7`; `3.F` residue burning→`3.C.1.b`; `3.E` savanna
burning→`3.C.1.c`; `3.G` liming→`3.C.2`; `3.H` urea→`3.C.3` (do not transpose with liming);
the `LU` sentinel→`3.B.1`–`3.B.5`, except harvested wood products, which is `3.D.1` — the
*Other* block, not the Land block, and the one place the obvious guess is wrong.

## Unresolved mappings, declared rather than invented

* **CRT `3.I` and `3.J`** have no IPCC 2006 counterpart. `3.C.8` *Other* is a different scope
  (other CH₄ and N₂O sources on land), so writing it would be a guess. Both keep their rows,
  their notation keys and their CRT identity in the label, under a `(crt-only)` sentinel; the
  crosswalk records them with `tier=unmapped` and no code.
* **CRT `4.E` Settlements and `4.F` Other land** arrive as one PakEmis row facing two IPCC 2006
  codes, `3.B.5` and `3.B.6`. Declared `tier=needs_separation` rather than apportioned by a
  share nobody holds.
* **The NH₃ row** under managed soils is marked `tier=precursor`: it is an input to 3.C.5's
  volatilisation pathway, not an emission reported under it.

## Affected products

42 shipped products carry a code column. The migration touched the registry
(`src/pkinv/report/completeness.py::ROWS`) and everything derived from it — the atomic annual
product, the source-stream ledger, the category ledger, key categories, the monthly lane, the
completeness-mass ledger, the coverage matrix and five semantic tables. Three registries keyed
on the old codes moved with them: the gap register, the EDGAR domain map and the BTR
crosswalk's PakEmis side.

**`outputs/crt_AFOLU_table.csv` deliberately keeps CRT codes** and is the only file that does.
It exists to be read against Pakistan's own reporting; rewriting it would destroy what it is
for. `tests/test_category_crosswalk.py` exempts it by name and asserts the exemption still
matches something, so it cannot quietly widen.

## Conservation: before and after

Codes are labels, so no mass may move. 28 of 29 invariants are **bit-identical** across the
migration, including:

* native-gas and CO₂e totals by period × gas × configuration × geography
* the same aggregates by period × module and per component
* the 202-component set and its identifiers
* row counts of the annual, monthly, ADM1, ADM2 and semantic products
* both national pins — **L 469.63822 / S 464.50543**

The single change is the intended one: `national_category_gas.csv` goes from 50 to 52 rows as
the two splits become their own categories, while its aggregate **by gas is unchanged**. The
split pairs sum to the single CRT category they replace:

```
3.A.2 19.330010 + 3.C.6 1.898470 = 21.228480   against the external audit's 3.B 21.228487
3.C.4 16.434470 + 3.C.5 12.091480 = 28.525950  against the external audit's 3.D 28.525954
```

`tests/test_agriculture_control.py` asserts this by folding the product back to the auditor's
own CRT codes **through the crosswalk**, which also exercises it in the CRT direction.

## Two checks, because one of them is blind

Conservation and re-coding are verified separately, and they see different things. The
conservation check aggregates at a grain **no code appears in** — that is what makes it a
conservation check — so it passed while the entire monthly lane still carried `3.F` and `3.H`,
because no mass had moved. Only a sweep of the code columns themselves found it. Both now run:
`tests/test_category_crosswalk.py` asserts the crosswalk resolves every live component, that
every component rule matches a live component, that the shipped code equals what the crosswalk
resolves, and that no product retains a retired sector-3 leaf.

## The all-sector audit

The user's instruction was to audit **all** sectors, not only the ones that moved. The result
is that the inconsistency was confined to sectors 3 and 4, and the reason the hybrid survived
two reviews is that everywhere else the two schemes agree code for code.

**Sectors 1 and 2 — 50 live codes, no rule needed.** Energy and IPPU are numbered identically
in IPCC 2006 Vol.1 Ch.8 Table 8.2 and in the UNFCCC Common Reporting Tables, down to the leaf:

```
1.A.1.a 1.A.2 1.A.2/1.A.4.c 1.A.3.a 1.A.3.b 1.A.3.c 1.A.3.d 1.A.4.a 1.A.4.b 1.A.4.c
1.A.5.b 1.B.1 1.B.2
2.A.1 2.A.2 2.A.3 2.A.4  2.B.1..2.B.10  2.C.1..2.C.7  2.D.1 2.D.2 2.D.3
2.E 2.F 2.F.1..2.F.6  2.G.1..2.G.4  2.H
```

The crosswalk carries **no rule for any of them**, and that absence is the audit's finding
rather than an omission: a rule whose two sides are the same string would assert a
correspondence that needs no assertion, and would then have to be maintained. The one
composite, `1.A.2/1.A.4.c`, is a declared shared row (industrial vs agricultural off-road
machinery that the customer class does not separate) and is not a scheme artefact — it reads
the same way in both schemes.

**Sector 4 (Waste) renumbers wholesale, and that is the easiest mistake in the file.** IPCC
2006 puts Waste at 4; the CRT puts LULUCF at 4 and Waste at 5. The six waste rules therefore
all exist to move a sector digit — `4.A → 5.A`, `4.B → 5.B`, `4.C.1 → 5.C.1`, `4.C.2 → 5.C.2`,
`4.D → 5.D`, `4.D.1 → 5.D.1` — with no change of meaning. A reader who assumed the sector
digit was stable across schemes would silently book every waste category under land use.

**Sector 3 is where the two schemes genuinely differ**, and where all twelve component rules
live: IPCC 2006 folds Agriculture and LULUCF into one AFOLU sector (3.A Livestock, 3.B Land,
3.C Aggregate sources and non-CO₂ on land, 3.D Other), while the CRT keeps Agriculture at 3
and Land at 4. This is the only place where one code string means different things on the two
sides, which is why the migration keys on `component_id` throughout.

**Two CRT codes get no mapping, deliberately.** `3.I` (other carbon-containing fertilisers)
and `3.J` (other) have no IPCC 2006 counterpart that could be asserted without inventing an
allocation. They are carried with their notation status under a `(crt-only)` sentinel, and
`tests/test_category_crosswalk.py` asserts that an `unmapped` row names no IPCC code — so the
absence cannot quietly become a guess later.
