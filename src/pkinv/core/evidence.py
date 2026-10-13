"""One evidence vocabulary for the whole inventory.

WHY THIS EXISTS. Four sectors independently invented a way to say how well a number is
supported, and none of them can be compared with another:

    aviation   SOURCE_TIERS A/B/C/D            (ledger.py)
    ippu       MATURITY_LABELS 0..6            (schemas.py)
    power      exact / assumed / default       (plant_ledger.py)
    residential "SYNTHETIC PROFILE" in a note   (monthly.py)

Each is right about its own sector and useless across sectors, so a national product could
not answer "how much of this dataset is observed?" without a per-sector translation table
held in someone's head. That question has to be answerable from the data, because a
harmonised, monthly, gridded dataset invites exactly the misreading that resolution implies
observation.

THREE INDEPENDENT AXES, DELIBERATELY. A row can be an observed annual quantity spread over
months by a guessed profile and allocated by population - strong on one axis, weak on two.
Collapsing that into a single grade would hide precisely the thing a reuser needs. So:

    E1..E4   how well the ANNUAL QUANTITY is supported
    T1..T4   how the row is resolved in TIME
    S1..S4   how the row is allocated in SPACE

Lower is stronger on every axis, and the numbering is deliberately parallel so a row reading
(E1, T4, S3) is legible at a glance: measured quantity, invented seasonality, administrative
geography.

WHAT THE CLASSES ARE NOT. They are not uncertainty. A T1 monthly series can still carry a
wide interval, and a T4 flat profile can be nearly right for a genuinely aseasonal source.
They describe the PROVENANCE of the resolution, not the width of the error - which is why
they sit beside uncert_pct on the row rather than replacing it.
"""

# --- how well the annual quantity is supported -----------------------------------------
EVIDENCE = {
    "E1": "measured or metered quantity for this source and period",
    "E2": "published statistic for this source and period, not independently verified",
    "E3": "derived from a related published quantity (a share, a ratio, a balance)",
    "E4": "declared judgement or default, with no quantity specific to this source",
}

# --- how the row is resolved in time ---------------------------------------------------
TEMPORAL = {
    "T1": "observed monthly activity for this source and year",
    "T2": "reconstructed from cumulative or related monthly administrative records",
    "T3": "process-based seasonal profile (degree days, crop calendar, fire counts)",
    "T4": "flat or weakly-informed profile; no monthly evidence for this source",
}

# The same four classes under the names the monthly product publishes. TE, not T, because a
# reader meeting "T2" beside an IPCC Tier 2 in the same table reads them as the same ladder
# and they are unrelated: a Tier is how good the METHOD is, a TE class is how the year's
# emissions were spread across its months. The T-codes stay - they are stamped on every
# component row in the shipped schema and pinned by tests - and this is the published
# spelling, with the mapping written down once rather than in each reader's head.
TEMPORAL_EVIDENCE = {
    "TE1": "direct monthly activity for this process, boundary and year",
    "TE2": "reconstructed or benchmarked monthly administrative activity",
    "TE3": "process-informed temporal proxy (degree days, crop calendar, fire counts)",
    "TE4": "weak, borrowed, flat or days-weighted allocation",
}
TEMPORAL_TO_EVIDENCE = {"T1": "TE1", "T2": "TE2", "T3": "TE3", "T4": "TE4"}
TEMPORAL_FROM_EVIDENCE = {v: k for k, v in TEMPORAL_TO_EVIDENCE.items()}

# WHAT THE PROFILE ACTUALLY TIMES, which is not always what the emission does. A fertiliser
# offtake series records when urea left the depot; the nitrogen reaches the soil later and
# emits later again, and a monthly product that prints the offtake shape without saying so
# invites the reader to treat a commercial record as an observation of soil chemistry. The
# same gap opens between a fuel SALE and its combustion, and between a plant's production
# and the process that emits inside it. Naming the target is the only thing that keeps a
# TE1 class honest: the class says how well the timing is evidenced, this says of what.
TIMING_TARGET = {
    "fuel_sale": "when fuel was sold or delivered, not when it was burned",
    "production": "when a physical product was made",
    "commodity_offtake": "when a commodity left a depot, plant or port",
    "physical_application": "when a material was applied to land",
    "emitting_process": "the emitting process itself, observed or modelled directly",
    "stock_exposure": "a stock exposed continuously; the month is duration, not an event",
    "proxy_only": "a shape with no claimed relationship to this process's timing",
}

# Where a month's number stands in its own lifecycle. Every fiscal year this inventory
# publishes is closed, so everything is "final" today; the column exists because the
# provisional lane (docs/monthly_lane.md) needs somewhere to put a month that is not.
TEMPORAL_STATUS = {
    "final": "the source edition for this month is closed and will not be revised",
    "provisional": "published but subject to revision by a later edition",
    "corrected": "revised by a later edition; this is the revised value",
    "superseded": "replaced by a later edition and retained for provenance",
}

# --- how the row is allocated in space -------------------------------------------------
SPATIAL = {
    "S1": "native source geometry (facility coordinate, network segment, trajectory)",
    "S2": "facility or network proxy without per-object activity",
    "S3": "administrative statistic (provincial sales, registrations, census counts)",
    "S4": "population or area fallback with no source-specific basis",
    # THE STATE THE SCALE WAS MISSING. S1-S4 all describe HOW mass is placed below the
    # province, so a stream with no sub-provincial placement at all has nothing on this scale
    # to be. Twenty-four industrial-combustion streams were carrying S3 - "an administrative
    # statistic does the placing" - while being retained whole at ADM1 in
    # pakemis_spatial_unallocated.csv and placed below it by nothing.
    #
    # NA is NOT "unlocated". Those streams have a province on every row; what they lack is a
    # level beneath it. The class says there is no sub-provincial placement to grade, and
    # `placement_status` and `finest_placement_level` in the spatial decomposition say what is
    # true instead - which keeps evidence quality and product availability in separate columns.
    "NA": "no sub-provincial placement: controlled at ADM1 and retained there, not spread",
}

# --- where the gas enters the atmosphere -----------------------------------------------
# CATEGORICAL ONLY, AND DELIBERATELY SO. An atmospheric model needs to know that a cement
# kiln is not a cooking fire and that cruise emissions are not at the surface; it does not
# need a stack height this inventory would have to invent. Where a real height is not held,
# the class says so rather than defaulting to ground level, which is the assumption a reader
# would otherwise make silently.
RELEASE_HEIGHT = {
    "surface": "diffuse ground-level release (soils, livestock, open area sources)",
    "traffic_surface": "road and rail traffic at street level",
    "household_low": "domestic chimneys and flues, below roof height",
    "low_stack": "small industrial and captive plant, roughly below 30 m",
    "high_stack": "large combustion and process plant, roughly above 30 m",
    "airport_LTO": "aircraft landing and take-off cycle, within the airport boundary",
    "aviation_climb_descent": "aircraft between the LTO ceiling and cruise",
    "aviation_cruise": "aircraft at cruise altitude",
    "unknown": "no release geometry established for this stream",
}

AXES = {"evidence_class": EVIDENCE, "temporal_method": TEMPORAL, "spatial_method": SPATIAL}

# Sector ladders that predate this one, mapped rather than replaced. Each sector keeps its
# own vocabulary - it is meaningful there and its tests pin it - and translates on the way
# out. Where a legacy class spans two of these, the mapping takes the WEAKER, because a
# summary that overstates support is worse than one that understates it.
AVIATION_SOURCE_TIER = {          # aviation/ledger.py SOURCE_TIERS
    "A": ("E1", "T1", "S1"),      # observed trajectory
    "B": ("E1", "T1", "S2"),      # observed stage, modelled trajectory
    "C": ("E3", "T2", "S2"),      # reconstructed missing stage
    "D": ("E3", "T4", "S3"),      # aggregate residual
}
IPPU_MATURITY = {                 # ippu/schemas.py MATURITY_LABELS
    0: "E4", 1: "E4", 2: "E2", 3: "E3", 4: "E2", 5: "E1", 6: "E1",
}
POWER_ENERGY_CLASS = {            # power/plant_ledger.py legs()
    "exact": "E1", "assumed": "E3", "default": "E4",
}


def stamp(rows, default, source_id, year, overrides=None, period_kind="span",
          category_overrides=None):
    """Apply the schema keys to a sector's component rows, uniformly.

    Ten modules had ten shapes of this loop, or none. It is one function because the keys are
    a CONTRACT and a contract implemented ten ways is a convention.

    `default` is the sector's (evidence, temporal, spatial) triple. `overrides` maps a subitem
    PREFIX to a partial triple for the streams that genuinely differ - which is most sectors,
    because a module rarely knows all of its streams equally well. A residential module that
    reads piped gas from a utility return and dung cake from another sector's nitrogen ledger
    is not one evidence class, and flattening it to one would be the same overstatement the
    axes exist to prevent.

    A stream may override any subset of the axes; the sector default fills the rest, and
    `source_id` may be overridden per stream too by passing a four-tuple. Existing values are
    never replaced: a row that already carries a class computed from its own evidence - the
    aviation ledger's per-stage tiers, power's per-leg energy classes - keeps it.

    `category_overrides` is the same thing keyed on the exact CATEGORY, for axes that divide
    the sector the way the reporting categories do rather than the way its subitems do:
    agriculture's temporal classes follow enteric-versus-soils-versus-rice, and its subitems
    are animal names. A subitem override wins over a category one where both match.
    """
    overrides = overrides or {}
    category_overrides = category_overrides or {}
    for row in rows:
        subitem = row.get("subitem", "")
        triple, sid = default, source_id
        entry = category_overrides.get(row.get("category"))
        if entry:
            triple = tuple(a if a is not None else b for a, b in zip(entry[:3], default))
            sid = entry[3] if len(entry) > 3 and entry[3] else source_id
        for prefix in sorted(overrides, key=len, reverse=True):
            if subitem.startswith(prefix):
                entry = overrides[prefix]
                triple = tuple(a if a is not None else b
                               for a, b in zip(entry[:3], triple))
                sid = entry[3] if len(entry) > 3 and entry[3] else sid
                break
        row.setdefault("activity_year", year)
        row.setdefault("activity_period_kind",
                       period_kind(subitem) if callable(period_kind) else period_kind)
        row.setdefault("evidence_class", triple[0])
        row.setdefault("temporal_method", triple[1])
        row.setdefault("spatial_method", triple[2])
        row.setdefault("source_id", sid)
    return rows


def validate(row):
    """Return the invalid (key, value) pairs on a component row, empty if clean.

    Silent on absent keys: the classes are optional while sectors adopt them, and a row
    that says nothing is honest. A row that says something wrong is not.
    """
    bad = []
    for key, vocabulary in AXES.items():
        value = row.get(key)
        if value is not None and value not in vocabulary:
            bad.append((key, value))
    return bad


def describe(row):
    """Human-readable provenance of one row's classes, for notes and captions."""
    parts = []
    for key, vocabulary in AXES.items():
        value = row.get(key)
        if value:
            parts.append("%s (%s)" % (value, vocabulary[value]))
    return "; ".join(parts) if parts else "unclassified"


def summarise(rows, key="evidence_class", weight="co2e_Mt_AR5"):
    """{class: weighted share} over rows carrying that axis.

    Weighted by emissions rather than by row count, because "80% of our rows are observed"
    means nothing if the unobserved 20% is most of the inventory. Rows without the class
    are pooled under None so the unclassified remainder stays visible instead of silently
    renormalising away.
    """
    totals, grand = {}, 0.0
    for r in rows:
        w = abs(float(r.get(weight) or 0.0))
        totals[r.get(key)] = totals.get(r.get(key), 0.0) + w
        grand += w
    if not grand:
        return {}
    return {k: v / grand for k, v in sorted(totals.items(), key=lambda kv: (kv[0] is None,
                                                                           kv[0] or ""))}
