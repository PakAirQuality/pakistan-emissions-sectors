"""Source-neutral data library for oil-and-gas fugitives (IPCC 1.B.2)."""
from __future__ import annotations

from pkinv.activity.store import input_exists as _input_exists
import csv
import os

from pkinv.paths import DATA
from pkinv.activity.store import read_rows
from pkinv.assets import asset_path

YEAR = 2024
LEGACY_YEAR = 2020


def _read(path):
    return read_rows(path, comments=False)


def _num(value):
    value = (value or "").strip()
    return None if value == "" else float(value)


class FugitivesData:
    """All normalized inputs; calculators never parse a PDF or workbook directly."""

    def __init__(self, data_dir=DATA, year=YEAR):
        self.data_dir = data_dir
        self.year = int(year)
        activity_dir = asset_path(data_dir, "activity", "fugitives")

        self.ef = {}
        for row in _read(asset_path(data_dir, "emission_factors.csv")):
            self.ef[(row["category"], row["item"])] = {
                "value": _num(row["value"]),
                "uncert_pct": _num(row["uncert_pct"]),
                "source": row["source"],
            }

        self.params, self.param_uncert, self.param_source = {}, {}, {}
        for row in _read(asset_path(data_dir, "fugitives_params.csv")):
            self.params[row["param"]] = _num(row["value"])
            self.param_uncert[row["param"]] = _num(row["uncert_pct"])
            self.param_source[row["param"]] = row["source"]

        self.production = {}
        for row in _read(asset_path(activity_dir, "production.csv")):
            self.production[int(row["fiscal_year"])] = {
                "oil_000_bbl": float(row["crude_oil_000_barrels"]),
                "gas_MMCFT": float(row["natural_gas_MMCFT"]),
                "source": row["source"],
            }
        self.province = _read(asset_path(activity_dir, "production_province.csv"))

        self.network = {}
        for row in _read(asset_path(activity_dir, "gas_network.csv")):
            self.network[(int(row["fiscal_year"]), row["item"])] = float(row["mmcfd"])

        self.flow_controls = {}
        flow_path = asset_path(activity_dir, "gas_flow_controls_2021_24.csv")
        if _input_exists(flow_path):
            for row in _read(flow_path):
                parsed = dict(row)
                for key in ("gross_domestic_production_mmcfd",
                            "indigenous_marketable_supply_mmcfd", "rlng_supply_mmcfd",
                            "total_supply_mmcfd", "categorized_consumption_mmcfd",
                            "ufg_mmcfd"):
                    parsed[key] = float(parsed[key])
                self.flow_controls[int(row["fiscal_year"])] = parsed

        self.anchors = {}
        for row in _read(asset_path(activity_dir, "anchor_activity_2023_24.csv")):
            parsed = dict(row)
            for key in ("value", "uncertainty_low_pct", "uncertainty_high_pct"):
                parsed[key] = float(parsed[key])
            self.anchors[(2024, row["activity_id"])] = parsed
        matched = asset_path(activity_dir, "anchor_activity_2021_23.csv")
        if _input_exists(matched):
            for row in _read(matched):
                parsed = dict(row)
                for key in ("value", "uncertainty_low_pct", "uncertainty_high_pct"):
                    parsed[key] = float(parsed[key])
                self.anchors[(int(row["fiscal_year"]), row["activity_id"])] = parsed
        history = asset_path(activity_dir, "infrastructure_history_2015_21.csv")
        if _input_exists(history):
            self._add_historical_anchors(_read(history))
        # Backwards-compatible view of the registered anchor.
        self.anchor = {activity_id: row for (year, activity_id), row in self.anchors.items()
                       if year == self.year}

        self.factors2019 = {}
        for row in _read(asset_path(data_dir, "fugitives_ipcc2019_factors.csv")):
            parsed = dict(row)
            for key in ("value", "uncertainty_low_pct", "uncertainty_high_pct"):
                parsed[key] = float(parsed[key])
            self.factors2019[row["factor_id"]] = parsed

        self.infrastructure = _read(asset_path(activity_dir, "infrastructure_2023_24.csv"))
        self.provincial_controls = _read(
            asset_path(activity_dir, "provincial_controls_2023_24.csv"))

    def _add_historical_anchors(self, controls):
        """Build normalized annual activities from explicit, report-level controls.

        This is mechanical normalization, not temporal interpolation. Templates supply
        IPCC codes, units and uncertainty fields; each activity value and provenance is
        replaced with the year-specific public control or a disclosed proxy.
        """
        template = {activity_id: dict(row) for (year, activity_id), row in self.anchors.items()
                    if year == 2024}
        conversion = 365.0 * self.p("mcf_to_e6m3")
        for source in controls:
            year = int(source["fiscal_year"])
            if year not in self.production:
                raise ValueError("historical infrastructure year lacks production: %s" % year)
            oil = self.oil_e3m3(year)
            gas = self.gas_e6m3(year)
            values = {
                "oil_onshore_production": oil,
                "oil_pipeline_transport": oil,
                "oil_refining": float(source["refinery_output_million_t"]) * 1000.0 / 0.85,
                "gas_onshore_production": gas,
                "gas_gathering": gas,
                "gas_processing": gas,
                "sour_gas_processing": gas * 0.32,
                "gas_transmission_pipeline": float(source["transmission_length_km"]),
                "gas_transmission_throughput": (
                    (float(source["categorized_consumption_mmcfd"]) +
                     float(source["ufg_mmcfd"])) * conversion),
                "lng_import_terminals": float(source["lng_terminals"]),
                "gas_distribution_pipeline": float(source["distribution_length_km"]),
                "gas_distribution_throughput": (
                    float(source["categorized_consumption_mmcfd"]) * conversion),
                "post_meter_appliances": float(source["domestic_customers"]),
                "post_meter_nonresidential": (
                    float(source["eligible_postmeter_mmcfd"]) * conversion),
                "ufg_diagnostic": float(source["ufg_mmcfd"]) * conversion,
            }
            for activity_id, value in values.items():
                row = dict(template[activity_id])
                row["value"] = value
                row["source"] = source["source"]
                row["source_reference"] = source["source_reference"]
                row["note"] = source["revision_note"]
                if activity_id in {"oil_pipeline_transport", "oil_refining", "gas_gathering",
                                   "gas_processing", "sour_gas_processing"}:
                    row["method_tier"] = "proxy" if activity_id != "sour_gas_processing" else "ipcc_default"
                if activity_id == "sour_gas_processing":
                    row["source"] = "IPCC 2019 Refinement"
                    row["source_reference"] = "Default 32% sour-gas share"
                    row["note"] = "Structural default applied to the year-specific gross gas volume."
                self.anchors[(year, activity_id)] = row

    def tnd_year(self):
        return int(self.p("tnd_year"))

    def network_e6m3(self, item, year=None):
        y = self.tnd_year() if year is None else int(year)
        return self.network[(y, item)] * 365.0 * self.p("mcf_to_e6m3")

    def efv(self, category, item):
        return self.ef[(category, item)]["value"]

    def efs(self, category, item):
        return self.ef[(category, item)]["source"]

    def p(self, name):
        return self.params[name]

    def ps(self, name):
        return self.param_source[name]

    def years(self):
        return sorted(self.production)

    def oil_e3m3(self, year=None):
        year = self.year if year is None else int(year)
        return self.production[year]["oil_000_bbl"] * self.p("bbl_to_m3")

    def gas_e6m3(self, year=None):
        year = self.year if year is None else int(year)
        return self.production[year]["gas_MMCFT"] * self.p("cf_to_m3")

    def activity(self, activity_id, year=None):
        y = self.year if year is None else int(year)
        return self.anchors[(y, activity_id)]

    def marketable_processing_activity(self, year=None):
        """Marketable indigenous supply as a lower processing-throughput proxy."""
        y = self.year if year is None else int(year)
        control = self.flow_controls[y]
        value = (control["indigenous_marketable_supply_mmcfd"] * 365.0 *
                 self.p("mcf_to_e6m3"))
        return {
            "activity_id": "gas_processing_marketable",
            "ipcc_code": "1.B.2.b.iii",
            "segment": "Natural gas",
            "subsegment": "Processing",
            "value": value,
            "unit": "million_m3",
            "uncertainty_low_pct": 5.0,
            "uncertainty_high_pct": 5.0,
            "source": control["source"],
            "source_reference": control["source_reference"],
            "method_tier": "official_lower_proxy",
            "status": "estimated",
            "note": ("Indigenous marketable supply is a lower processing-throughput proxy; "
                     "it is not assumed to equal measured plant inlet gas."),
        }

    @staticmethod
    def processing_corr_group(basis):
        return ("gas-production-volume" if basis == "gross"
                else "indigenous-marketable-supply")

    def has_anchor_year(self, year):
        return any(y == int(year) for y, _activity_id in self.anchors)

    @staticmethod
    def activity_corr_group(activity_id):
        """Physical-source correlation used by the segment Monte Carlo.

        Production volume is one observed quantity reused in production, gathering and
        processing. Oil production likewise supports its transport fallback. Remaining
        activities have independent control totals.
        """
        if activity_id in {"gas_onshore_production", "gas_gathering", "gas_processing",
                           "sour_gas_processing"}:
            return "gas-production-volume"
        if activity_id in {"oil_onshore_production", "oil_pipeline_transport"}:
            return "oil-production-volume"
        return activity_id

    def factor2019(self, factor_id):
        return self.factors2019[factor_id]

    # What each post-meter state withholds from the non-residential leak base.
    #   feed_excluded        chemical feedstock only: the reference since rc67
    #   fertilizer_excluded  the whole fertiliser class, process fuel too
    #   full / half / excluded withhold no activity (the last two act on the factor)
    POST_METER_WITHHOLDS = {"feed_excluded": "feed", "fertilizer_excluded": "class",
                            "full": None, "half": "feed", "excluded": None}

    def fertilizer_gas_class(self, year=None):
        """OGRA's fertiliser gas class for one fiscal year: the printed row, in million m3.

        Read from the verified ingest (fertilizer_gas_class.csv), one row per edition of
        the regulator's sector-wise table. A year with no row raises: the class is never
        carried from another year, because every year's own print is held."""
        y = self.year if year is None else int(year)
        for row in _read(asset_path(self.data_dir, "activity", "fugitives",
                                    "fertilizer_gas_class.csv")):
            if int(row["fiscal_year"]) == y:
                mmcfd = float(row["total_mmcfd"])
                return {"mmcfd": mmcfd,
                        "million_m3": mmcfd * 365.0 * self.p("mcf_to_e6m3"),
                        "printed_label": row["printed_label"], "status": row["status"],
                        "source": row["source"]}
        raise KeyError("no fertiliser gas class is held for fiscal year %d" % y)

    def fertilizer_feed_fraction(self, year=None):
        """The part of fertiliser gas that is chemical feedstock, and how it is known.

        NFDC's Annex-28 meters each plant's feed gas and fuel gas by month, for FY2023-24
        and FY2024-25 only. A year it covers returns its own fraction, basis `observed`.
        Any other year returns the FY2023-24 fraction, basis `carried`: the split is set
        by how an ammonia plant is built (reformer feed against furnace and boiler fuel),
        the two observed years differ by 0.3 points, and the label travels with the number
        into every product that uses it."""
        y = self.year if year is None else int(year)
        totals = {}
        for row in _read(asset_path(self.data_dir, "nfdc",
                                    "afr2025_fertilizer_gas_monthly.csv")):
            if str(row["mmcf"]).strip():
                key = (row["fiscal_year"], row["consumption"])
                totals[key] = totals.get(key, 0.0) + float(row["mmcf"])

        def fraction(label):
            feed, fuel = totals[(label, "Feed")], totals[(label, "Fuel")]
            return feed / (feed + fuel)

        label = "%d-%02d" % (y - 1, y % 100)
        source = "NFDC Annual Fertilizer Review 2024-25, Annex-28 (plant-wise feed and fuel gas)"
        if (label, "Feed") in totals:
            return {"value": fraction(label), "basis": "observed", "source": source,
                    "observed_year": label}
        return {"value": fraction("2023-24"), "basis": "carried", "source": source,
                "observed_year": "2023-24"}

    def post_meter_feedstock_share(self, year=None, scope="feed"):
        """Share of the non-residential post-meter leak base that a state withholds.

        scope="feed"   chemical feedstock: the fertiliser class times the feed fraction.
                       Feedstock is reformed, not burned, so a factor whose activity is
                       "gas consumed" in combustion equipment has no basis on it.
        scope="class"  the whole fertiliser class, the process fuel with it.

        The class is each year's own print and the base is each year's own
        (post_meter_nonresidential), so the share is never carried between years; only
        the feed fraction can be, and fertilizer_feed_fraction says when it is."""
        if scope not in ("feed", "class"):
            raise ValueError("scope must be feed or class")
        y = self.year if year is None else int(year)
        fertilizer = self.fertilizer_gas_class(y)["million_m3"]
        eligible = self.activity("post_meter_nonresidential", year=y)["value"]
        share = fertilizer / eligible
        if scope == "feed":
            share *= self.fertilizer_feed_fraction(y)["value"]
        return share
