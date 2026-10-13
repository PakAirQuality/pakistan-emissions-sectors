# Baseline: the national account immediately before the rc67 reference re-base

WHAT THIS IS. Ten extracts of release 1.0.0rc66 (commit 64681cb3), cut with `git show`: the
national series, the reference-year totals, the national configurations and dung variants, the
fugitives structural scenarios, the national Monte Carlo table and the two ensemble summaries,
each whole; and the atomic annual product and ADM1 by year for the three modules that move
(`fugitives`, `residential`, `waste`), the rows of every other module left out because nothing
in this re-base touches them. `SHA256SUMS` pins them.

WHY IT EXISTS. At rc67 the reference changes in three places at once: chemical feedstock
leaves the post-meter gas leakage base, household dung follows the survey in every year, and
domestic wastewater nitrous oxide moves to the 2019 Refinement method. Each movement is
published as a before-and-after, and the "before" has to survive the rebuild of `outputs/`.
A git ref would do in a checkout; a validation package is not a checkout.

WHAT RC66 HELD, so the "before" columns are read correctly. Reference total L 451.85782 and
survey configuration S 446.72502 Mt CO2e (AR5), FY2023-24. The post-meter base contained the
whole fertiliser gas class. Household dung in the reference was the agriculture-diverted
quantity (58.74 Mt air-dry); the survey quantity was a second configuration for the reference
year only. Wastewater nitrous oxide was the 2006 Guidelines equation on the whole population.

WHAT IT IS NOT. Not an input to any estimate. Nothing reads these files except the comparison
products and their tests.
