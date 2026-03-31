"""Lightweight errors for spreadsheet parsing (mirrors backend v1 parsing.errors)."""


class InvalidSchemaError(Exception):
    """Raised when the uploaded file violates the required deterministic schema."""


class CurrencyMismatchError(Exception):
    """Raised when explicit ISO currency conflicts with the deal currency."""
