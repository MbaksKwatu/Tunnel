import unittest

try:
    from backend.v1.core.classifier import classify
except ModuleNotFoundError:
    from v1.core.classifier import classify


def _txn(descriptor: str, amount_cents: int, is_transfer: bool = False) -> dict:
    return {
        "normalized_descriptor": descriptor.lower(),
        "signed_amount_cents": amount_cents,
        "is_transfer": is_transfer,
    }


class TestClassifierKeywords(unittest.TestCase):
    def test_mpesa_payment_positive_revenue_operational(self):
        txn = _txn("mpesa payment", 50000)
        self.assertEqual(classify(txn), "revenue_operational")

    def test_loan_disbursement_positive_revenue_non_operational(self):
        txn = _txn("loan disbursement", 100000)
        self.assertEqual(classify(txn), "loan_inflow")

    def test_loan_repayment_negative_supplier(self):
        txn = _txn("loan repayment", -50000)
        self.assertEqual(classify(txn), "loan_repayment")

    def test_staff_salary_negative_payroll(self):
        txn = _txn("staff salary", -30000)
        self.assertEqual(classify(txn), "payroll")

    def test_kra_vat_negative_supplier(self):
        txn = _txn("kra vat", -15000)
        self.assertEqual(classify(txn), "tax_payment")

    def test_fallback_positive_revenue_operational(self):
        txn = _txn("miscellaneous deposit", 20000)
        self.assertEqual(classify(txn), "revenue_operational")

    def test_director_capital_injection_positive_revenue_non_operational(self):
        txn = _txn("director capital injection", 500000)
        self.assertEqual(classify(txn), "capital_injection")

    def test_owner_capital_positive_revenue_non_operational(self):
        txn = _txn("owner capital", 100000)
        self.assertEqual(classify(txn), "revenue_operational")

    def test_shareholder_investment_positive_revenue_non_operational(self):
        txn = _txn("shareholder investment", 250000)
        self.assertEqual(classify(txn), "revenue_operational")

    def test_refund_positive_revenue_non_operational(self):
        txn = _txn("refund", 15000)
        self.assertEqual(classify(txn), "reversal_credit")

    def test_reversal_negative_supplier(self):
        txn = _txn("reversal", -8000)
        self.assertEqual(classify(txn), "reversal_debit")

    def test_refer_to_drawer_classified_as_reversal(self):
        txn = _txn("REJECT INSUFFICIENT FUNDS REFER TO DRAWER 3333624", -333362400)
        self.assertIn(classify(txn), ["reversal_debit", "reversal_credit"])

    def test_insufficient_funds_classified_as_reversal(self):
        txn = _txn("insufficient funds refer to drawer", -100000)
        self.assertIn(classify(txn), ["reversal_debit", "reversal_credit"])

    def test_dishonoured_cheque_classified_as_reversal(self):
        txn = _txn("dishonoured cheque 004515", -50000)
        self.assertIn(classify(txn), ["reversal_debit", "reversal_credit"])

    def test_rev_prefix_classified_as_reversal(self):
        txn = _txn("REV JAMES KARIUKI 254721239867", 15000)
        self.assertIn(classify(txn), ["reversal_credit", "reversal_debit"])

    def test_revenue_not_caught_as_reversal(self):
        txn = _txn("revenue operational mpesa", 50000)
        self.assertNotIn(classify(txn), ["reversal_credit", "reversal_debit"])
