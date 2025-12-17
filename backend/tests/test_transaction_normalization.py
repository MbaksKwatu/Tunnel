import unittest

from parsers import normalize_transaction_rows


class TestTransactionNormalization(unittest.TestCase):
    def test_amount_and_date_direct_columns(self):
        rows = [
            {"Date": "2024-01-05", "Amount": "100.50", "Description": "Sale"},
            {"Date": "2024-01-06", "Amount": "-25.00", "Description": "Supplies"},
        ]

        out = normalize_transaction_rows(rows)
        self.assertEqual(out[0]["transaction_date"], "2024-01-05")
        self.assertAlmostEqual(out[0]["amount"], 100.50)
        self.assertEqual(out[1]["transaction_date"], "2024-01-06")
        self.assertAlmostEqual(out[1]["amount"], -25.00)

    def test_amount_derived_from_debit_credit(self):
        rows = [
            {"Posting Date": "2024/02/01", "Debit": "10.00", "Credit": ""},
            {"Posting Date": "2024/02/02", "Debit": "", "Credit": "50.00"},
            {"Posting Date": "2024/02/03", "Debit": "10.00", "Credit": "50.00"},
        ]

        out = normalize_transaction_rows(rows)
        self.assertEqual(out[0]["transaction_date"], "2024-02-01")
        self.assertAlmostEqual(out[0]["amount"], -10.00)
        self.assertEqual(out[1]["transaction_date"], "2024-02-02")
        self.assertAlmostEqual(out[1]["amount"], 50.00)
        self.assertEqual(out[2]["transaction_date"], "2024-02-03")
        self.assertAlmostEqual(out[2]["amount"], 40.00)

    def test_amount_derived_from_inflow_outflow(self):
        rows = [
            {"Date": "2024-03-01", "Inflow": "200"},
            {"Date": "2024-03-02", "Outflow": "75"},
        ]

        out = normalize_transaction_rows(rows)
        self.assertAlmostEqual(out[0]["amount"], 200.0)
        self.assertAlmostEqual(out[1]["amount"], -75.0)


if __name__ == '__main__':
    unittest.main()
