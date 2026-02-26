import io
import unittest
from copy import deepcopy

from openpyxl import Workbook

from backend.v1.parsing.xlsx_parser import parse_xlsx
from backend.v1.parsing.csv_parser import parse_csv
from backend.v1.parsing.errors import InvalidSchemaError


def _make_wb(rows):
    wb = Workbook()
    ws = wb.active
    ws.title = "Sheet1"
    ws.append(["date", "amount", "description"])
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class TestDeterministicParsers(unittest.TestCase):
    def test_xlsx_same_file_same_hash(self):
        rows = [
            ["2024-01-01", "100.00", "A"],
            ["2024-01-02", "-50", "B"],
        ]
        content = _make_wb(rows)
        parsed1, hash1, _ = parse_xlsx(content, "doc-1", "USD")
        parsed2, hash2, _ = parse_xlsx(content, "doc-1", "USD")
        self.assertEqual(parsed1, parsed2)
        self.assertEqual(hash1, hash2)

    def test_xlsx_reorder_rows_same_hash(self):
        rows_a = [
            ["2024-01-01", "100", "A"],
            ["2024-01-02", "200", "B"],
        ]
        rows_b = deepcopy(rows_a)[::-1]
        content_a = _make_wb(rows_a)
        content_b = _make_wb(rows_b)
        parsed_a, hash_a, _ = parse_xlsx(content_a, "doc-1", "USD")
        parsed_b, hash_b, _ = parse_xlsx(content_b, "doc-1", "USD")
        self.assertEqual(parsed_a, parsed_b)
        self.assertEqual(hash_a, hash_b)

    def test_xlsx_amount_equivalence(self):
        rows = [
            ["2024-01-01", "100", "A"],
            ["2024-01-02", "100.00", "B"],
        ]
        content = _make_wb(rows)
        parsed, _, _ = parse_xlsx(content, "doc-1", "USD")
        cents = [r["signed_amount_cents"] for r in parsed]
        self.assertIn(10000, cents)

    def test_xlsx_invalid_schema_missing_header(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["date", "description"])  # missing amount
        buf = io.BytesIO()
        wb.save(buf)
        with self.assertRaises(InvalidSchemaError):
            parse_xlsx(buf.getvalue(), "doc-1", "USD")

    def test_csv_reorder_rows_same_hash(self):
        content_a = "date,amount,description\n2024-01-01,100,A\n2024-01-02,200,B\n"
        content_b = "date,amount,description\n2024-01-02,200,B\n2024-01-01,100,A\n"
        parsed_a, hash_a, _ = parse_csv(content_a.encode(), "doc-1", "USD")
        parsed_b, hash_b, _ = parse_csv(content_b.encode(), "doc-1", "USD")
        self.assertEqual(parsed_a, parsed_b)
        self.assertEqual(hash_a, hash_b)


if __name__ == "__main__":
    unittest.main()
