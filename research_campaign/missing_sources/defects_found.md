# Defects found in the F-gas and completeness code — written up, NOT fixed

Found by reading and by running the existing code; nothing in `src/`, `outputs/`,
`tests/` or any registry was touched. None of these moves a pin: 2.F contributes
zero to every total, so every item below is a configuration-lane defect. Each one
is stated with the evidence that would let someone else reproduce it.

---

## D1 — the species bank silently abandons a stratum's bank when its supply rows stop

**Severity: real, mass-conservation.** 0.5557 Mt CO2e of bank mass vanishes.

`run_bank` in `src/pkinv/sectors/ippu/fgases.py` iterates over the rows it is
given:

```python
for row in sorted(annual_rows, key=lambda value: int(value["year"])):
```

A `(species, application)` stratum whose supply rows end before 2024 therefore
produces no ledger for the later years, and the bank it had accumulated simply
stops existing. A bank does not stop leaking when imports stop. Six strata are
affected in `outputs/ippu_hfc_species_bank.csv`:

| species | application | last year | bank abandoned (t) | at AR5 (Mt CO2e) |
|---|---|---|---|---|
| R-407C | stationary AC | 2021 | 281.956 | 0.45796 |
| HFC-152a | aerosol | 2015 | 39.500 | 0.00545 |
| R-507A | refrigeration | 2021 | 9.839 | 0.03921 |
| R-417A | stationary AC | 2021 | 5.449 | 0.01159 |
| HFC-23 | fire protection | 2021 | 3.196 | 0.03963 |
| R-508B | refrigeration | 2021 | 0.333 | 0.00190 |
| | | | **340.3 t** | **0.5557** |

Direction of error: the 2024 figure of 5.854 Mt is biased **low**, and the
2.F.3 fire-protection and 2.F.4 aerosol applications disappear from the latest
year entirely — which is why `coverage_matrix.csv` can report those two
applications as carried by the bank in some years and absent in 2024.

Why the existing guard does not catch it: `fgas_bank_step` asserts closure
**per step** (`abs(residual) > 1e-9` raises). A step that is never executed
cannot fail its own closure test. The series has no closure test. This is the
same shape as the two closure designs recorded in the speed-round lessons as
having failed silently and safely.

Fix sketch (for whoever owns it): run every stratum over the full year grid,
carrying zero supply in years the source does not cover, and label those years'
`data_status` as something other than `reported` — the bank is still real but the
supply observation is absent. A series-level test would then assert that every
stratum with a non-zero bank in year *Y* has a row in *Y+1*.

**Reproduce:** `python3 research_campaign/missing_sources/fgas_screen.py` prints
the table above (the `truncated strata` block).

---

## D2 — the retirement fraction is resolved against a reimplementation of the kernel

**Severity: fragility, no live error.**

`src/pkinv/sectors/ippu/hfc_bank.py` has to resolve the `RETIRE_FRACTION:` tokens
before calling the kernel, so it advances "a shadow bank with the same arithmetic
the kernel applies":

```python
bank = (bank + supplied) * (1.0 - float(r["operating_loss_fraction"])) - float(r["retired_charge_t"])
bank = max(bank, 0.0)
```

That does currently match `fgas_bank_step` exactly — I checked the algebra:
`bank_end = (bank_start + supply·(1−k))·(1−x) − retired` on both sides. But it is
the same arithmetic written twice, and the copy carries a `max(bank, 0.0)` clamp
the kernel does not have; the kernel raises `ValueError` when the retired charge
exceeds the operating bank. If the clamp ever bound, the two would diverge and
the kernel would raise rather than return a wrong number — safe, but only by
luck. The resolution pass should call the kernel rather than restate it.

---

## D3 — one operating-loss rate is applied to a stratum IPCC splits in two

**Severity: this is the largest single number in the 2.F question.** ~1.2 Mt CO2e.

`data/sectors/ippu/activity/hfc_inventory_rows.csv` prices the whole
`refrigeration` application at `operating_loss_fraction = 0.080`. IPCC 2006 Vol 3
Table 7.9 (held at `data/raw/ipcc/ipcc2006_V3_7_Ch7_ODS_Substitutes.pdf` p.7.52)
gives *domestic* refrigeration **0.1–0.5 %/yr** and only the commercial
sub-applications reach 8 % (stand-alone commercial 1–15 %, medium and large
commercial 10–35 %). 8 %/yr is admissible for commercial refrigeration and is
16 to 80 times too high for domestic.

The independent stock-side screen built in this lane isolates the effect cleanly:
the supply-side bank and the household equipment stock agree on the refrigeration
bank to within a factor of 1.3 (4,128 t against 3,092 t), while the emissions
differ by 107× (1.2902 Mt against 0.0121 Mt central). With bank size agreed, the
leak rate is the only remaining explanation.

This is not a coding error — the value is inside Table 7.9 for *a*
sub-application — but the stratum cannot carry both sub-applications at one rate,
and the row's `application_split_basis` already says the split is the UNDP
report's declared structure rather than a measurement. It should be split, or the
single rate should be published with its sensitivity attached.

---

## D4 — the national completeness table under-enumerates IPPU by 28 categories

**Severity: reporting completeness, the silent-absence class.**

`data/sectors/ippu/metadata/master_data_gap_matrix.csv` carries 36 IPPU
categories. `outputs/completeness.csv` carries nine IPPU codes (2.A.1, 2.A.2,
2.B.1, 2.B.2, 2.B.7, 2.C.1, 2.D.1, 2.F, 2.F.1). The 28 in the gap matrix and not
in the national table are listed in `coverage_matrix.csv` and flagged
`NOT IN outputs/completeness.csv` in their notes.

This is exactly the class the 1.A.4.a audit closed ("no NE row and no EDGAR-map
code existed for this category") and the class the Wave-4 2.B.2 insertion closed
("the national completeness table had NO 2.B.2 row while the sector-level IPPU
view carried it at critical materiality"). Three of the 28 have official
Pakistani magnitudes: 2.H 1.35 Mt, 2.A.4 0.27 Mt, and 2.G/2.E/2.C at zero.
2.G.1 (SF6 in electrical equipment) is rated medium-high materiality in the
sector matrix and has no national row at all.

A test asserting that every row of each sector gap matrix appears in
`outputs/completeness.csv` would close the class rather than the instance.

---

## D5 — WITHDRAWN, and the withdrawal is the item worth keeping

**I wrote D5 as "the HIES equipment-stock indicator is held, labelled for exactly
this purpose, and no code reads it." That was false.** It is read by
`scripts/build_hfc_bank_series.py`, registered as a `Phase` in
`src/pkinv/run_all.py` line 1336, and it already produces
`outputs/pakemis_hfc_bank_series.csv` — a household stock-side HFC bank band for
FY2015-16..FY2023-24 on the same IPCC Table 7.9 basis, with the same household
scope, and with the same floor framing (FY2023-24: 0.191–2.423 Mt CO2e).

**How the false claim was produced.** I ran

```
grep -rl "hies" src/pkinv/sectors/ippu/     # no output
```

and read the silence as absence. The producer lives in `scripts/`, not in the
sector package. One layer searched, a conclusion drawn from its silence — the
same failure mode as re-downloading the IPCC chapter after keywording
`holdings.py` wrongly, and the same failure mode the repository's own gap
register has corrected twice on 1A2-industrial-fuel ("OGRA reports gas by sector
in a table this inventory already read … only an unread row").

**What survives.** `fgas_stock_screen.csv` is a second, independently
parameterised run of the same method (AC charge 0.6–1.5 kg rather than 0.5–2.0, an
explicit AC-fitment discount on the mobile lane, a central beside the band) and it
lands *inside* the shipped band. Two parameter sets agreeing is corroboration.
The genuinely new thing is the comparison axis used in D3 above: the shipped band
compares household EMISSIONS against the supply lanes' emissions, while D3's
finding needs the two banks compared in TONNES OF REFRIGERANT per application.
That is what shows the refrigeration banks agreeing to 1.3× while the emissions
differ 107×, and the emissions-only comparison cannot show it.

**Standing lesson for this repository**, which already has three instances of it:
a negative result from one search layer is not evidence of absence. Search the
sector package, `scripts/`, `run_all.py`'s phase list and `data/catalog/` before
writing "unused" — exactly as `scripts/holdings.py` searches all four data layers
before writing "not held".
