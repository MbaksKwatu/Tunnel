"""
Shared test configuration for backend v1 tests.

Fixture convention:
  All test files (XLSX, CSV, PDF) live at tests_v1/fixtures/<filename>.
  Never use absolute ~/Desktop or ~/Downloads paths — commit the file here instead.

Example:
  from pathlib import Path
  _FIXTURES = Path(__file__).parent / "fixtures"
  _MY_FILE = _FIXTURES / "my_statement.xlsx"
  @pytest.mark.skipif(not _MY_FILE.exists(), reason=f"fixture missing: {_MY_FILE.name}")
"""
from pathlib import Path

FIXTURES = Path(__file__).parent / "fixtures"
