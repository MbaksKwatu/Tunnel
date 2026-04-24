"""Spreadsheet parsers (XLSX) — aligned with backend v1 parsing."""

from app.parsers.xlsx_parser import extraction_result_from_xlsx_bytes, parse_xlsx

__all__ = ["parse_xlsx", "extraction_result_from_xlsx_bytes"]
