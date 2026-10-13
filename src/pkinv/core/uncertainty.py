"""IPCC Approach 1 uncertainty propagation (2006 GL Vol 1 Ch 3).

- Multiplication (activity data x emission factor): add percentage uncertainties
  in quadrature (Eq 3.1):  U_product = sqrt(U_ad^2 + U_ef^2)
- Addition (summing category/component emissions): combine in quadrature weighted
  by the magnitude of each term (Eq 3.2):
      U_sum = sqrt( sum( (U_i * E_i)^2 ) ) / | sum(E_i) |
"""
import math


def product(*uncert_pcts):
    """Combined % uncertainty of a product of independent terms."""
    return math.sqrt(sum(u * u for u in uncert_pcts if u is not None))


def combine_sum(components):
    """components: (emission, uncert_pct) or (emission, uncert_pct, corr_group).

    Returns (total, total_uncert_pct).

    Eq 3.2 combines terms in quadrature, which assumes their errors are INDEPENDENT. That fails when
    one physical stream is reported as several rows for spatial-allocation reasons: the managed-soils
    indirect pathways are split by source nitrogen so each can carry its own province proxy, but every
    volatilisation row shares EF4 and every leaching row shares EF5. Treating those as independent
    would shrink the reported uncertainty purely as an artefact of how finely the rows are cut.

    Terms sharing a non-None corr_group are therefore treated as fully correlated -- their absolute
    uncertainties add linearly -- and the groups combine in quadrature with the independent terms.
    """
    total = sum(c[0] for c in components)
    if total == 0:
        return 0.0, 0.0
    indep_sq, groups = 0.0, {}
    for c in components:
        absu = c[1] / 100.0 * c[0]
        group = c[2] if len(c) > 2 else None
        if group is None:
            indep_sq += absu * absu
        else:
            groups[group] = groups.get(group, 0.0) + absu
    abs_sq = indep_sq + sum(a * a for a in groups.values())
    return total, math.sqrt(abs_sq) / abs(total) * 100.0
