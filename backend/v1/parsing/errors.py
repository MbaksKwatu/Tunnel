class InvalidSchemaError(Exception):
    """Raised when the uploaded file violates the required deterministic schema."""


class CurrencyMismatchError(Exception):
    """Raised when explicit ISO currency conflicts with the deal currency."""
