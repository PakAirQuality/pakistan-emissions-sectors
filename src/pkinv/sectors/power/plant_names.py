"""ONE join key for power-station names, because three readers were about to make three.

The grid cube has matched the plant fuel ledger against the coordinate tables on this key since
rc42, and its rule is deliberate: unlike the generic token rule it KEEPS short numeric and roman
tokens, so "Bin Qasim TPS-I" and "TPS-II" cannot collapse into one station, and it strips the
ledger's cost-column prefix. rc44 adds a second consumer - the NEPRA generation panel, matched
against NEPRA's own plant location table - and a second copy of a name-matching rule is how two
readers come to disagree about which station is which while both look right.

A MISS IS NOT AN ERROR HERE. Every consumer of this key treats an unmatched plant as unplaced
and sends it to a declared fallback, never onto a neighbour's point or province. That is the
property that makes an approximate key safe: it can fail to match, and it cannot mis-match a
station onto another station's geography.
"""
import re

_DROP = {"power", "station", "ltd", "limited", "pvt", "private", "company",
         "co", "the", "gen", "generation"}


def plant_key(name):
    """Join tokens for a power station name."""
    cleaned = re.sub(r"\(rs\. million\)", " ", name.lower())
    cleaned = re.sub(r"\(genco-[ivx]+\)", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9 ]", " ", cleaned)
    return tuple(sorted(t for t in cleaned.split() if t and t not in _DROP))
