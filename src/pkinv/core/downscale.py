"""Allocate national components to provinces, for any sector.

The mechanism is sector-agnostic: every component rides a proxy whose province shares sum
to one, so the provincial totals reconcile exactly to the national control totals. What
is *not* sector-agnostic is the proxy vocabulary and the component-to-proxy mapping, so
those arrive as arguments rather than being imported.

Extracted when the waste sector needed it. Agriculture keeps its own copy of the loop for
now because its writers are entangled with it; the invariant enforced here is identical.
"""

TOL = 1e-6


def check_shares(shares):
    """Every proxy's province shares must sum to 1, or allocation silently loses mass."""
    for proxy, sh in shares.items():
        s = sum(sh.values())
        if abs(s - 1.0) > TOL:
            raise ValueError("province shares for '%s' sum to %.9f, not 1.0" % (proxy, s))


def allocate_rows(components, shares, proxy_for, provinces):
    """Return province x component allocation rows.

    `proxy_for` must raise on an unknown component rather than returning a default: a
    silent fallback would move a whole stream onto the wrong geography while leaving the
    national total untouched, which is invisible in the headline table.
    """
    check_shares(shares)
    rows = []
    for c in components:
        proxy = proxy_for(c)
        for prov in provinces:
            rows.append({
                "province": prov, "category": c["category"], "subitem": c["subitem"],
                "proxy": proxy,
                "co2e_Mt_AR5": c["co2e_Mt_AR5"] * shares[proxy][prov],
            })
    return rows


def check_reconciliation(rows, components):
    """Sum of allocated rows must equal the national control total."""
    national = sum(c["co2e_Mt_AR5"] for c in components)
    allocated = sum(r["co2e_Mt_AR5"] for r in rows)
    if abs(national - allocated) > TOL:
        raise AssertionError("provincial allocation does not reconcile: national %.9f vs "
                             "allocated %.9f" % (national, allocated))
    return national, allocated
