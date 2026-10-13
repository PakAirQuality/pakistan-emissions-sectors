"""Load activity data, emission factors and parameters from the CSV library.

Single source of truth: every number used by the engine is read from a file under
`data/`. No emission factor is hard-coded in the calculation modules.
"""

from pkinv.assets import asset_path
import csv
import os

from pkinv.paths import ROOT
from pkinv.activity.store import read_rows

DATA_DIR = asset_path(ROOT, "data")


def _read(path):
    return read_rows(path, comments=False)


def _num(s):
    """Parse a numeric cell; blank -> None."""
    s = (s or "").strip()
    if s == "":
        return None
    return float(s)


class InventoryData:
    """Holds the full data library for one inventory run."""

    def __init__(self, data_dir=DATA_DIR):
        self.data_dir = data_dir

        # Emission factors keyed by (category, item) -> {value, uncert_pct, source}
        self.ef = {}
        for r in _read(asset_path(data_dir, "emission_factors.csv")):
            self.ef[(r["category"], r["item"])] = {
                "value": _num(r["value"]),
                "uncert_pct": _num(r["uncert_pct"]),
                "source": r["source"],
            }

        # Scalar parameters keyed by name -> float (source kept for provenance checks)
        self.params = {}
        self.param_source = {}
        for r in _read(asset_path(data_dir, "parameters.csv")):
            self.params[r["param"]] = _num(r["value"])
            self.param_source[r["param"]] = r.get("source", "")

        # Manure management system shares: species -> {system: share}
        self.mms = {}
        for r in _read(asset_path(data_dir, "mms_shares.csv")):
            self.mms.setdefault(r["species"], {})[r["system"]] = _num(r["share"])

        # Residue parameters: crop -> row
        self.residue = {}
        for r in _read(asset_path(data_dir, "residue_params.csv")):
            self.residue[r["crop"]] = {k: _num(v) if k != "crop" else v
                                       for k, v in r.items()
                                       if k in ("residue_ratio_ag", "n_ag_frac",
                                                "below_above_ratio", "n_bg_frac",
                                                "frac_returned", "frac_fuel")}

        # Residue-burning parameters: crop -> burned fraction
        self.burning = {}
        for r in _read(asset_path(data_dir, "burning_params.csv")):
            self.burning[r["crop"]] = {"frac_burned": _num(r["frac_burned"])}

        # Activity data
        self.livestock = {}
        for r in _read(asset_path(data_dir, "activity", "livestock_2024.csv")):
            # rc39: the file states its own basis and the loader respects it. It used to
            # take head_census_2024 when present and fall back to the following year's
            # column otherwise - which silently made "census" mean "whichever column is
            # filled", and left poultry (an Economic Survey projection, not an
            # enumeration) sitting in a field whose name asserts a census.
            basis = r["activity_basis"]
            if basis not in ("census_enumeration", "economic_survey_projection"):
                raise ValueError("livestock_2024.csv: %s carries activity_basis %r, which "
                                 "is not one of the declared bases" % (r["species"], basis))
            self.livestock[r["species"]] = {
                "head": _num(r["head_value"]),
                "head_following_year": _num(r["head_following_year"]),
                "activity_basis": basis,
                "reference_period": r["reference_period"],
                "source_document_id": r["source_document_id"],
                "uncert_pct": _num(r["ad_uncert_pct"]),
            }

        self.crops = {}
        for r in _read(asset_path(data_dir, "activity", "crops_2024.csv")):
            self.crops[r["crop"]] = {
                "area_ha": _num(r["area_ha"]),
                "production_t": _num(r["production_t"]),
                "uncert_pct": _num(r["ad_uncert_pct"]),
            }

        self.fertilizer = {}
        for r in _read(asset_path(data_dir, "activity", "fertilizer_2024.csv")):
            self.fertilizer[r["item"]] = {
                "value_t": _num(r["value_t"]),
                "uncert_pct": _num(r["ad_uncert_pct"]),
            }

    # ---- convenience accessors ----
    def efv(self, category, item):
        """Emission-factor value."""
        return self.ef[(category, item)]["value"]

    def efu(self, category, item):
        """Emission-factor uncertainty (% )."""
        return self.ef[(category, item)]["uncert_pct"]

    def efs(self, category, item):
        """Emission-factor source string (provenance)."""
        return self.ef[(category, item)]["source"]

    def p(self, name):
        """Parameter value."""
        return self.params[name]

    def ps(self, name):
        """Parameter source string (provenance)."""
        return self.param_source[name]

    def nex_per_head(self, species):
        """Annual N excretion (kg N/head/yr) = Nrate * TAM * 365 / 1000  (Eq 10.30)."""
        return (self.p("nex_rate_" + species) * self.p("tam_" + species) * 365.0) / 1000.0
