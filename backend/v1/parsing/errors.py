class InvalidSchemaError(Exception):
    """Raised when the uploaded file violates the required deterministic schema."""


class InvalidDocumentError(InvalidSchemaError):
    """Category A: file is not a parseable document at all (corrupt, wrong type, unreadable).
    Not retriable — a different file is needed. Never triggers a parser-request record."""


class CurrencyMismatchError(Exception):
    """Raised when explicit ISO currency conflicts with the deal currency."""
