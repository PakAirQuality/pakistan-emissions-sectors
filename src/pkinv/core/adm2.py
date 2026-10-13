"""The one district system: canonical ADM2 units, and every observed spelling resolved.

WHY THIS EXISTS. District names arrive in this repository in four vocabularies that disagree
- the geoBoundaries 2019 geometry, the PBS Census-2023 panel, the PBS 7th Agricultural
Census, and the provincial registration tables - and until this module the bridges were a
20-row alias file scoped to one sector and a normaliser COPY-PASTED into three modules.
Copies drift; the residential copy and the agriculture copy were already one edit apart from
disagreeing about what a district is called.

The canonical registry is data/adm2_canonical.csv (152 units, PBS Census-2023 naming, with
each unit's relation to the geometry it can be drawn with) and data/adm2_crosswalk.csv
(every observed spelling -> adm2_id). Both are BUILT, reviewed and committed by
scripts/build_adm2_package.py, whose --check mode keeps them regenerable; this module only
reads them.

resolve() RAISES on an unknown name. A district string that resolves nowhere is a unit of
emissions about to be dropped from a spatial product without anyone noticing - the exact
class of silent loss that left Larkana (whose polygon the boundary file simply does not
have) absent from every district product ever built here, undetected until the canonical
table was constructed.
"""

from pkinv.assets import asset_path
import csv
import os
import re

from pkinv.paths import DATA
from pkinv.activity.store import read_rows

CANONICAL = asset_path(DATA, "adm2_canonical.csv")
CROSSWALK = asset_path(DATA, "adm2_crosswalk.csv")

_cache = {}


def normalise(name):
    """One normaliser for every district string in the repository.

    Byte-compatible with the three `_norm` copies it replaced (lowercase, strip a trailing
    'district', hyphens/dots/apostrophes to spaces or nothing, collapse whitespace).
    """
    s = name.strip().lower()
    s = re.sub(r"\s+district$", "", s)
    s = s.replace("-", " ").replace(".", " ").replace("'", "")
    return re.sub(r"\s+", " ", s).strip()


def _rows(path):
    return read_rows(path)


def load_canonical():
    """adm2_id -> canonical row."""
    if "canonical" not in _cache:
        _cache["canonical"] = {r["adm2_id"]: r for r in _rows(CANONICAL)}
    return _cache["canonical"]


def _index():
    """normalised observed name -> adm2_id, from the crosswalk plus canonical names."""
    if "index" not in _cache:
        index = {}
        for row in _rows(CROSSWALK):
            index[normalise(row["observed_name"])] = row["adm2_id"]
        for adm2_id, row in load_canonical().items():
            index.setdefault(normalise(row["canonical_name"]), adm2_id)
        _cache["index"] = index
    return _cache["index"]


def resolve(name):
    """The adm2_id for any observed district spelling. Raises on an unknown name."""
    key = normalise(name)
    index = _index()
    if key not in index:
        raise KeyError(
            "district name %r resolves to no canonical ADM2 unit. If it is a new spelling, "
            "add it to data/adm2_crosswalk.csv via scripts/build_adm2_package.py; a name "
            "that resolves nowhere is emissions about to be dropped from a spatial product "
            "without a trace." % name)
    return index[key]


def shape_to_adm2():
    """geoBoundaries shapeID -> [adm2_id, ...] (several where the census subdivides)."""
    out = {}
    for adm2_id, row in load_canonical().items():
        if row["shape_id"]:
            out.setdefault(row["shape_id"], []).append(adm2_id)
    return {k: sorted(v) for k, v in out.items()}


def adm2_to_shape():
    """adm2_id -> shapeID or None where the geometry is declared absent."""
    return {adm2_id: (row["shape_id"] or None)
            for adm2_id, row in load_canonical().items()}
