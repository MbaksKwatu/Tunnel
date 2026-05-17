"""
Shared test configuration for parity-ingestion tests.

Fixture convention:
  All test files (PDF, XLSX, CSV) live at tests/fixtures/<extractor>/<filename>.
  Never use absolute ~/Desktop or ~/Downloads paths — commit the file here instead.

Example:
  _FIXTURES = Path(__file__).parent / "fixtures"
  _MY_PDF = _FIXTURES / "kcb" / "sample_statement.pdf"
  pytestmark = pytest.mark.skipif(not _MY_PDF.exists(), reason=f"fixture missing: {_MY_PDF.name}")
"""
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
