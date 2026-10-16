"""Species-specific air masses on documented annual source supports.

The four dung/nitrogen configurations compose their own atom masses. Annual
cell, district and provincial weights come from the supported emitting process,
with separate declared frames for reviewed oil/diesel stations and kiln types.
A shared activity anchor is used only where it describes the emitting location.
Within-year monthly grids retain the documented annual source geography and use
the separate process-specific air monthly weights; this is not observed monthly
movement of sources. Household releases are gross appliance emissions, and
municipal waste burning is allocated at origin rather than measured fire sites.

Placed and unallocated mass remain separate. Cruise and excluded native geometry
retain appropriate administrative controls without invented sub-provincial
locations. The air monthly unallocated ledger preserves the same distinction by
month. Reporting territories and outside-frame mass use the common spatial
account. Every species/configuration/year must close to its own covered total;
missing sources are coverage statuses, never observed-zero cells. Spatial
evidence is recorded separately by pollutant in the support product.
"""

from pkinv.assets import asset_path
import collections
import csv
import json
import os

import numpy as np

from pkinv.core import configurations as conf
from pkinv.paths import OUTPUTS
from pkinv.activity.store import read_rows
# module-level is safe: power_admission_vectors defers its own import of this
# module to inside the two functions that need shape_frame
from pkinv.report import power_admission_vectors
from pkinv.report.air_annual import atom_configuration

ATOMS = asset_path(OUTPUTS, "pakemis_air_atomic_annual.csv")

ADM1_OUT = asset_path(OUTPUTS, "pakemis_air_adm1_by_year.csv")
ADM2_OUT = asset_path(OUTPUTS, "pakemis_air_adm2_by_year.csv")
UNALLOC_OUT = asset_path(OUTPUTS, "pakemis_air_unallocated_by_year.csv")
MONTHLY_UNALLOC_OUT = asset_path(OUTPUTS, "pakemis_air_monthly_unallocated.csv")

ADM1_FIELDS = ("period_id", "configuration_id", "sector_id", "source_stream_id",
               "pollutant", "province", "emissions_Gg")
ADM2_FIELDS = ("period_id", "configuration_id", "sector_id", "pollutant", "shape_id",
               "adm2_ids", "allocation_status", "province", "emissions_Gg")
UNALLOC_FIELDS = ("period_id", "configuration_id", "sector_id", "source_stream_id",
                  "pollutant", "level", "emissions_Gg", "reason")
MONTHLY_UNALLOC_FIELDS = ("month",) + UNALLOC_FIELDS

CRUISE_REASON = ("the anchor stream has no native geometry below the provincial "
                 "control (the aviation cruise class); the mass is placed at ADM1 "
                 "and nowhere finer, exactly as its greenhouse-gas mass is")
OUTSIDE_REASON = ("the share of the anchor stream's weight falling outside the "
                  "canonical shape frame (boundary-cell slivers, the cube's own "
                  "OUTSIDE column), carried so the ADM2 closure is exact, never "
                  "dropped")


FRAME_NONE = ""
KILN_FRAME_REASON = ("outside the surveyed kiln frame (the brick coal HDIP books beyond the "
                     "11,272 mapped kilns): placed at ADM1 on the brick stream's provincial "
                     "shares and nowhere finer - never spread over kilns that were not surveyed")
# rc60 wrote a NATIONAL_ONLY_REASON here and typed the admitted power SO2 `below_national` -
# published at national grain, placed nowhere - because its mass could not honestly ride its
# anchor stream's vector and had no vector of its own. rc61 gave it one, in
# pkinv.report.power_admission_vectors, whose docstring carries the measurement that forced the
# wait. The reason and the level it explained are both gone.


def frame_of_class():
    """{source_class_id: spatial_override} from the source-class register (rc59): the
    classes that ride their own frame rather than their anchor stream's vector."""
    from pkinv.sectors.industry.air_pollutants import REGISTER
    out = {}
    for r in read_rows(REGISTER):
        if r["spatial_override"]:
            out[r["source_class_id"]] = r["spatial_override"]
    return out


def load_atoms():
    """{period: {(configuration, anchor, frame, sector): {pollutant: Gg}}}.

    The ledger configuration is composed exactly as the panel rollup composes
    it: a sector with its own L atoms contributes those; every other sector's REF atoms
    are shared. Core species only - the panel's extra strata (TSP, PM10, OC...) are
    national-grain detail, not gridded. `frame` (rc59) is the class's spatial_override
    - kiln_frame:FCBK, kiln_frame:ZZ, adm1_only - or "" for every atom that rides its
    anchor stream's own vector; the atom's subitem is its source_class_id.

    THE SECTOR IS IN THE KEY, AND WAS NOT. An anchor is a GEOGRAPHY - the stream whose
    vector the mass rides - and two sectors may ride one: the IPPU soda-ash class borrows
    the general-industry gas stream as its declared proxy, and fugitive petrol
    distribution borrows the two-wheeler petrol stream. This function used to bucket by
    (configuration, anchor, frame) and remember ONE sector per anchor in a side dict, so
    the last atom read named the whole bucket: all of general-industry gas was filed
    under IPPU in the provincial and district tables, and 32 kt of fugitive NMVOC under
    transport. The national panel, which never passes through here, kept the right
    labels - so a sector's provinces did not sum to its national figure, for seven
    species, in every period, while every per-pollutant closure test passed (none closed
    per sector; tests/test_air_spatial_by_year.py does now)."""
    rows = [r for r in read_rows(ATOMS) if r["core7"] == "yes"]
    frames = frame_of_class()
    own = collections.defaultdict(set)
    for r in rows:
        own[r["configuration_id"]].add(r["sector_id"])
    out = collections.defaultdict(lambda: collections.defaultdict(
        lambda: collections.defaultdict(float)))
    for cfg in conf.AIR_ALL:
        for r in rows:
            use = conf.canonical(r["configuration_id"]) == atom_configuration(cfg, r["sector_id"])
            if not use:
                continue
            frame = frames.get(r["subitem"], FRAME_NONE)
            key = (cfg, r["support_anchor_id"], frame, r["sector_id"])
            out[r["period_id"]][key][r["pollutant"]] += float(r["emissions_Gg"])
    return out


def shape_frame(grid):
    """[(district_index, shape_id, adm2_ids, allocation_status, province)] - the SAME
    canonical frame mapping the greenhouse-gas ADM2 products use, so a shape row here
    and there cannot name different geography."""
    from pkinv.core import adm2 as adm2_core
    from pkinv.core.gis.grid import ADM2_PATH
    shape_members = adm2_core.shape_to_adm2()
    canonical = adm2_core.load_canonical()
    name_to_idx = {name: i for i, name in enumerate(grid.districts)}
    idx_by_shape = {}
    with open(ADM2_PATH, encoding="utf-8") as handle:
        for feature in json.load(handle)["features"]:
            p = feature["properties"]
            if p["shapeName"] in name_to_idx:
                idx_by_shape[p["shapeID"]] = name_to_idx[p["shapeName"]]
    frame = []
    for shape_id, members in sorted(shape_members.items()):
        idx = idx_by_shape.get(shape_id)
        if idx is None:
            continue
        provinces = {canonical[m]["province_id"] for m in members}
        status = "one_to_one" if len(members) == 1 else "shared_shape"
        frame.append((idx, shape_id, ";".join(members), status,
                      ";".join(sorted(provinces))))
    return frame


class AirSink:
    """A period_sink for spatial_by_year.build(): consumes each period's resident
    accumulator, streams the rasters into the two NetCDF writers, collects the ADM
    tables, writes the CSVs at close."""

    def __init__(self, grid, writers):
        self.grid = grid
        self.writers = writers          # {configuration_id: AirAnnualGridWriter}
        self.atoms = load_atoms()
        self.anchors = frozenset(key[1] for per in self.atoms.values() for key in per)
        self.frame = shape_frame(grid)
        # rc59: the kiln-type frames, built once (the brick shares are period-invariant)
        from pkinv.report import kiln_frame_vectors
        self.kiln_frames = kiln_frame_vectors.build(grid)
        # rc61: the power-admission frames. Built once too, but keyed by PERIOD as well as class:
        # the admitted fleet's province split runs from Balochistan 0.435 at FY2015-16 to 0.000
        # at FY2023-24 as the furnace-oil fleet collapsed, so one vector cannot serve nine years.
        self.power_frames = {
            (power_admission_vectors.frame_id(class_id), period_id): frame
            for (class_id, period_id), frame in power_admission_vectors.build(grid).items()}
        self.adm1 = collections.OrderedDict()   # aggregate key -> Gg (rc59: the three brick
                                                #   frames share one anchor and sum here)
        self.adm2 = collections.OrderedDict()   # aggregate key -> Gg
        self.unalloc = []
        self.monthly_unalloc = []
        self.monthly_writers = {}
        self.monthly_mass = collections.defaultdict(lambda: collections.defaultdict(float))
        from pkinv.report.air_monthly import OUT as monthly_out
        if os.path.exists(monthly_out):
            from pkinv.report.air_monthly_grid import AirMonthlyGridWriter
            from pkinv.report.annual_grid import period_bounds
            self.monthly_writers = {cfg: AirMonthlyGridWriter(grid, period_bounds(), cfg) for cfg in writers}
            frames = frame_of_class()
            for r in read_rows(monthly_out):
                frame = frames.get(r["source_class_id"], FRAME_NONE)
                key = (r["period_id"], r["configuration_id"], r["support_anchor_id"], frame, r["sector_id"], r["month"])
                self.monthly_mass[key][r["pollutant"]] += float(r["emissions_Gg"])

    def write(self, time_index, period_id, acc):
        per = self.atoms.get(period_id)
        if per is None:
            raise ValueError("period %s has no air atoms" % period_id)
        captured = acc["captured_cells"]
        streams = {}
        for s in acc["streams"]:
            sid = s["source_stream_id"]
            if sid in self.anchors:
                if sid in streams:
                    raise ValueError("anchor %s appears twice in period %s"
                                     % (sid, period_id))
                streams[sid] = s
        rasters = {cfg: {} for cfg in self.writers}
        monthly_rasters = collections.defaultdict(dict)
        for (cfg, sid, frame, sector), by_pol in sorted(per.items()):
            stream = streams.get(sid)
            if stream is None:
                raise ValueError("air atoms anchor %s, absent from the %s build"
                                 % (sid, period_id))
            marginals = acc["marginals"][sid]
            placed = sid in captured
            carrier = None                  # the frame that actually carries this mass, if any
            if frame.startswith("kiln_frame:"):
                carrier = self.kiln_frames[frame.split(":", 1)[1]]
            elif frame.startswith(power_admission_vectors.FRAME_PREFIX):
                carrier = self.power_frames[(frame, period_id)]
            elif frame == "adm1_only":
                placed = False
            elif frame != FRAME_NONE:
                raise ValueError("unknown spatial frame %r on anchor %s" % (frame, sid))

            # A FRAME EITHER INHERITS ITS ANCHOR'S PROVINCES OR DECLARES ITS OWN (rc61).
            # The kiln frames inherit: they are the same mass as the pooled brick stream, split
            # by type within each province, so their marginal IS the stream's and any drift is
            # a defect - asserted, not assumed. The power-admission frames declare: their mass
            # is a REVIEWED SUBSET of the anchor's fleet (the 54-89 percent of CPPA furnace oil
            # the register could price), so its provinces legitimately differ from the whole
            # fleet's, and riding the fleet's vector was measured to put Lahore 1.3-2.2x high
            # and 7 Gg into a Quetta with no furnace-oil station. ADM1 comes from whichever
            # vector carried the mass.
            if carrier is not None and carrier.inherits_anchor_marginal:
                for province, share in marginals.items():
                    if abs(carrier.province_marginal.get(province, 0.0) - share) > 1e-9:
                        raise ValueError("frame %s and stream %s disagree on %s: %.12f vs %.12f"
                                         % (frame, sid, province,
                                            carrier.province_marginal.get(province, 0.0), share))
            if carrier is not None and not carrier.inherits_anchor_marginal:
                marginals = carrier.province_marginal

            for pol, mass in sorted(by_pol.items()):
                for province, share in sorted(marginals.items()):
                    if share == 0.0:
                        continue
                    key = (period_id, cfg, sector, sid, pol, province)
                    self.adm1[key] = self.adm1.get(key, 0.0) + mass * share
                if not placed:
                    record = {
                        "period_id": period_id, "configuration_id": cfg,
                        "sector_id": sector, "source_stream_id": sid,
                        "pollutant": pol,
                        "level": "below_adm1",
                        "emissions_Gg": "%.12g" % mass,
                        "reason": (KILN_FRAME_REASON if frame == "adm1_only" else
                                   "no compatible native geography below ADM1; railway ODbL geometry excluded from primary release" if sector == "railways" else CRUISE_REASON)}
                    self.unalloc.append(record)
                    if self.monthly_writers:
                        from pkinv.core.monthly import months_for
                        for month in months_for(2000 + int(period_id[-2:]) - 1):
                            mkey = (period_id, cfg, sid, frame, sector, month)
                            self.monthly_unalloc.append(dict(record, month=month,
                                emissions_Gg="%.12g" % self.monthly_mass[mkey].get(pol, 0.0)))
                    continue
                grid_r = rasters[cfg]
                if pol not in grid_r:
                    grid_r[pol] = np.zeros((self.grid.height, self.grid.width))
                if carrier is not None:
                    grid_r[pol] += mass * carrier.cells
                    cell_weights = carrier.cells
                    shape_share = carrier.shape_vec
                    outside = carrier.outside * mass
                else:
                    grid_r[pol] += mass * captured[sid]
                    cell_weights = captured[sid]
                    annual = stream["emissions_Gg"]
                    shape_share = acc["stream_shape"][sid] / annual
                    outside = (acc["stream_outside"][sid] / annual) * mass
                if self.monthly_writers:
                    from pkinv.core.monthly import months_for
                    months = months_for(2000 + int(period_id[-2:]) - 1)
                    monthly_total = 0.0
                    for month in months:
                        mkey = (period_id, cfg, sid, frame, sector, month)
                        month_mass = self.monthly_mass[mkey].get(pol, 0.0)
                        monthly_total += month_mass
                        per_month = monthly_rasters[(cfg, month)]
                        if pol not in per_month:
                            per_month[pol] = np.zeros((self.grid.height, self.grid.width))
                        per_month[pol] += month_mass * cell_weights
                    if abs(monthly_total - mass) > 1e-9 * max(mass, 1):
                        raise ValueError("monthly air masses do not match annual placed source %s %s %s" % (period_id, sid, pol))
                total_shapes = 0.0
                for idx, shape_id, adm2_ids, status, province in self.frame:
                    value = mass * float(shape_share[idx])
                    total_shapes += value
                    key = (period_id, cfg, sector, pol, shape_id, adm2_ids,
                           status, province)
                    self.adm2[key] = self.adm2.get(key, 0.0) + value
                # the frame must account for the whole placed mass: a district
                # index missing from the shape frame would silently drop mass here
                if abs(total_shapes + outside - mass) > 1e-9 * max(mass, 1.0):
                    raise ValueError(
                        "shape frame drops mass for %s %s %s: %.12g + %.12g != %.12g"
                        % (period_id, sid, pol, total_shapes, outside, mass))
                if outside != 0.0:
                    self.unalloc.append({
                        "period_id": period_id, "configuration_id": cfg,
                        "sector_id": sector, "source_stream_id": sid,
                        "pollutant": pol, "level": "outside_frame",
                        "emissions_Gg": "%.12g" % outside,
                        "reason": OUTSIDE_REASON})
        for cfg, writer in self.writers.items():
            writer.write_period(period_id, rasters[cfg])
        if self.monthly_writers:
            from pkinv.core.monthly import months_for
            for cfg, writer in self.monthly_writers.items():
                for month in months_for(2000 + int(period_id[-2:]) - 1):
                    writer.write_period(month, monthly_rasters.get((cfg, month), {}))

    def close(self):
        for writer in self.monthly_writers.values():
            writer.close()
        adm1_rows = [{"period_id": k[0], "configuration_id": k[1], "sector_id": k[2],
                      "source_stream_id": k[3], "pollutant": k[4], "province": k[5],
                      "emissions_Gg": "%.12g" % v}
                     for k, v in self.adm1.items()]
        adm2_rows = [{"period_id": k[0], "configuration_id": k[1], "sector_id": k[2],
                      "pollutant": k[3], "shape_id": k[4], "adm2_ids": k[5],
                      "allocation_status": k[6], "province": k[7],
                      "emissions_Gg": "%.12g" % v}
                     for k, v in self.adm2.items()]
        for path, fields, rows in ((ADM1_OUT, ADM1_FIELDS, adm1_rows),
                                   (ADM2_OUT, ADM2_FIELDS, adm2_rows),
                                   (UNALLOC_OUT, UNALLOC_FIELDS, self.unalloc),
                                   (MONTHLY_UNALLOC_OUT, MONTHLY_UNALLOC_FIELDS, self.monthly_unalloc)):
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(fields),
                                        lineterminator="\n")
                writer.writeheader()
                writer.writerows(rows)
