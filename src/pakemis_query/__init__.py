"""pakemis_query: the deterministic query core over a PakEmis semantic release.

Imports nothing from pkinv at runtime: it takes a release directory (outputs/semantic/ plus the
NetCDF products) and semantic_release.json, verifies every table's identity before serving, and
answers typed requests with an envelope - exact values as decimal strings beside display values,
the context bar, provenance with product digests, the calculation, the evidence and unallocated
mass in scope, the limitations hit, and a reproducible receipt. The FastAPI service in PakEmis
Explorer wraps these functions one to one; the future Ask PakEmis agent may call nothing else."""
CONTRACT_VERSION = "1"

from pakemis_query.release import Release                      # noqa: E402,F401
from pakemis_query.models import (                              # noqa: E402,F401
    QueryEmissions, CompareRequest, TimeseriesRequest, UncertaintyRequest, CompletenessRequest,
    EvidenceRequest, MethodRequest, SpatialLineageRequest, TransferRequest, DownloadRequest,
    GridCellRequest)
from pakemis_query.engine import Engine                        # noqa: E402,F401
