"""Civil aviation as a registered sector (IPCC 1A3a).

Only domestic aviation (1A3a ii) is a component. International bunkers (1A3a i) and the
non-commercial stream are memo items: reported, never summed into the national total.
"""
from pkinv.core import evidence, period
from pkinv.core.components import enrich_co2e
from pkinv.sectors.aviation import downscale, lto
from pkinv.sectors.aviation.data import AviationData, YEAR

NAME = "aviation"
CATEGORIES = ("Domestic aviation",)
GASES = ("CO2", "CH4", "N2O")
HAS_SINKS = False
YEAR = YEAR                  # fiscal year, July to June

# The reference PERIOD, not just a year. See core.period: this sector's YEAR is the calendar
# year its reporting period OPENS in, a convention that was implicit until it collided
# with the opposite one in a neighbouring sector.
YEAR_CONVENTION = 'fiscal-start'
PERIOD_START, PERIOD_END = period.from_year(YEAR, YEAR_CONVENTION)

MC_DISTRIBUTION = "lognormal"

load_data = AviationData
proxy_for = downscale.proxy_for
load_shares = downscale.load_shares


# core.evidence classes. E2 because the annual quantity is a published movement statistic
# (PCAA) driving ICAO's per-cycle fuel burn, reconciled against OCAC's domestic-aviation fuel
# row - published rather than metered here. T1 because OCAC publishes a DIRECT monthly
# domestic-aviation fuel series that this sector already ingests and closes against. For
# FY2023-24 those editions are CUMULATIVE, so eleven of the twelve months are recovered by
# differencing and only July is read directly: T2, with the monthly layer carrying the T1 month
# where it belongs rather than the sector claiming it for the year.
#
# S1, WAS S2, AND THE OLD REASON ARGUED FROM THE WRONG SCALE. It read "S2 because emissions
# are placed at airports - real facilities with coordinates - but without per-airport activity
# for every stage of the cycle". Per-airport activity is exactly what this allocation has:
# the cube weights the airport points by PCAA domestic MOVEMENTS per airport, and thirty-six
# of the thirty-seven carry a coordinate (Juzzak is logged absent, aviation-juzzak-coords-01).
# Native geometry consuming observed per-object activity is S1 - FOR THE LTO SHARE, which is
# the fuel that actually burns within the airport boundary. Until rc47 Wave 3 this paragraph
# went on to argue that the flight stage was "a WITHIN-airport question", which was true of
# taxiways and false of cruise: ~83.5% of the full-flight fuel burns en route, and placing it
# at airports at S1 was the twenty-first review's aviation finding. The stream is split now;
# the cruise components are overridden to NA below and are not placed beneath the province.
# T3, not T2 (rc68): the monthly layer allocates domestic-flight emissions by jet fuel sold to
# resident airline customers, whose flights include international services, so the timing is
# a proxy. The layer was downgraded and the declaration had stayed T2; test_monthly_layer
# holds the two to one class.
EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD = "E2", "T3", "S1"
SOURCE_ID = "pcaa_movements_ocac_jet_fuel"


def build_components(data, year=None):
    components, _memo = lto.compute(data, year)
    evidence.stamp(components, (EVIDENCE_CLASS, TEMPORAL_METHOD, SPATIAL_METHOD),
                   SOURCE_ID, year if year is not None else YEAR)
    for c in components:
        if "cruise" in c["subitem"]:
            # rc47 Wave 3: the S1 above is the LTO share's - per-object airports with
            # per-object movements. Cruise fuel burns along corridors no held evidence
            # can draw (no OD matrix; endpoint-movement corridors would be invented),
            # so it is NOT placed below the province: booked at the uplift provinces
            # on the accounting view and NA here, the industry-activation pattern.
            # The old construction put all of it - ~83.5% of the stream - on airport
            # points at S1, which is the audit finding this split answers.
            c["spatial_method"] = "NA"
    return enrich_co2e(components)


def memo_items(data, year=None):
    """International bunkers and non-commercial movements - outside the national total."""
    _components, memo = lto.compute(data, year)
    return memo
