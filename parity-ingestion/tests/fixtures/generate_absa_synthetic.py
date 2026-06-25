"""
One-off generator for tests/fixtures/absa_synthetic.pdf — a fabricated
ABSA-formatted statement (no real customer data) used as the repo-committed
fixture for the Phase 0+1 PR's byte-identical equivalence test. Decision
recorded in the Request Parser Pipeline scoping doc §2d, 2026-06-21: the real
absa.pdf (a real customer's statement) is not committed; this synthetic file
replaces it for the long-term repo fixture. Re-run this script if the fixture
ever needs regenerating — it is not run as part of the test suite itself.

Column x-positions match absa_extractor.py's real thresholds exactly
(_TXN_DATE_X_MAX=120, _DESC_X_MAX=400, _MONEY_OUT_X_MAX=465,
_MONEY_IN_X_MAX=515) so this fixture exercises the same column-assignment
boundaries as production. All transactions reconcile cleanly — this fixture
is for equivalence/proving, not for reproducing the row-grouping defect
tracked separately in §2d.
"""
from __future__ import annotations

from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

OUT_PATH = Path(__file__).parent / "absa_synthetic.pdf"

# (date, description, debit, credit, balance)
ROWS = [
    ("", "OPENING BALANCE", "", "", "500,000.00"),
    ("02/01/2024", "SALARY PAYMENT", "", "50,000.00", "550,000.00"),
    ("03/01/2024", "RENT PAYMENT", "20,000.00", "", "530,000.00"),
    ("05/01/2024", "MPESA TRANSFER", "", "15,000.00", "545,000.00"),
    ("06/01/2024", "ATM WITHDRAWAL", "5,000.00", "", "540,000.00"),
]

DATE_X = 10
DESC_X = 130
DEBIT_X = 405
CREDIT_X = 470
BALANCE_X = 520
ROW_HEIGHT = 20
TOP_Y = 700


def build():
    c = canvas.Canvas(str(OUT_PATH), pagesize=letter)
    c.setFont("Helvetica", 9)

    c.drawString(200, 760, "Absa Bank Kenya")
    c.drawString(200, 745, "Statement of Account")

    header_y = 720
    c.drawString(DATE_X, header_y, "Txn Date")
    c.drawString(DESC_X, header_y, "Description")
    c.drawString(DEBIT_X, header_y, "Money Out")
    c.drawString(CREDIT_X, header_y, "Money In")
    c.drawString(BALANCE_X, header_y, "Balance")

    y = TOP_Y - (header_y - TOP_Y) * 0 - 20
    y = header_y - ROW_HEIGHT
    for date, desc, debit, credit, balance in ROWS:
        if date:
            c.drawString(DATE_X, y, date)
        c.drawString(DESC_X, y, desc)
        if debit:
            c.drawString(DEBIT_X, y, debit)
        if credit:
            c.drawString(CREDIT_X, y, credit)
        if balance:
            c.drawString(BALANCE_X, y, balance)
        y -= ROW_HEIGHT

    c.drawString(250, 100, "Page 1 of 1")
    c.drawString(150, 80, "absa.kenya@absa.africa")
    c.showPage()
    c.save()
    print(f"wrote {OUT_PATH}")


if __name__ == "__main__":
    build()
