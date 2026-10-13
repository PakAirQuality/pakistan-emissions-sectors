"""Typed refusals. A request the contract cannot answer is refused by name, never approximated."""


class QueryError(ValueError):
    code = "query_error"

    def __init__(self, message, limitation_id=None, **detail):
        super().__init__(message)
        self.message = message
        self.limitation_id = limitation_id
        self.detail = detail

    def to_dict(self):
        return {"error": self.code, "message": self.message, "limitation_id": self.limitation_id,
                "detail": self.detail}


class MixedBasisError(QueryError):
    code = "mixed_basis"


class MixedConfigurationError(QueryError):
    code = "mixed_configuration"


class MixedGwpError(QueryError):
    code = "mixed_gwp"


class NotEstimated(QueryError):
    """The scope names something the release does not estimate (NE), does not carry at that
    grain, or does not carry on that basis; the limitation id names the contract entry."""
    code = "not_estimated"

    def __init__(self, message, limitation_id, notation_key="NE", **detail):
        super().__init__(message, limitation_id, notation_key=notation_key, **detail)


class UnknownDimensionValue(QueryError):
    code = "unknown_dimension_value"


class GrainUnavailable(QueryError):
    code = "grain_unavailable"


class IdentityError(QueryError):
    """A table's bytes do not match the contract's digest; the release is not served."""
    code = "identity_mismatch"
