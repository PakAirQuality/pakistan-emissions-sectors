# The air panel after the rc63 sulfur adoption, as it stood at rc66

WHAT THIS IS. Two shipped products, taken byte-for-byte from the rc66 release record (commit
64681cb3): `pakemis_air_source_classes_fy2015_16_fy2023_24.csv` and
`pakemis_air_lahore_by_year.csv`. `SHA256SUMS` pins both. They are the CANDIDATE side of
`scripts/measure_sulfur_adoption_effect.py`; `../pre_rc63_sulfur_adoption/` is the baseline side.

WHY IT EXISTS. Until rc67 the measurement read its candidate from `outputs/`. That was sound
while nothing else moved the same streams. At rc67 the residential reference changed (household
dung is taken from the household survey), residential SO2 fell in every year, and a rerun of the
measurement booked that fall as an unattributed effect of the sulfur adoption: Lahore's
residential row went from "unchanged" to -65 percent. The measurement is of ONE change, so both
of its ends have to be held still. rc66 is the last release in which the two files differ from
the baseline by the sulfur adoption and nothing else in SO2.

WHAT IT IS NOT. Not an independent regeneration, for the same reason the baseline is not: these
files were written by the engine as it stood and preserved. The measurement remains a reported
session result.
