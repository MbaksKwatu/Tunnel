from app.extractors.equity_extractor import extract_equity_pdf

FIXTURE = "/Users/mbakswatu/Desktop/Demofiles/Sassy_Cosmetics_2025_merged.pdf"

result = extract_equity_pdf(FIXTURE)
rows = result.raw_transactions

inflows = [t for t in rows if t.credit_raw and str(t.credit_raw).strip() not in ('', '0', '0.0', '0.00')]
outflows = [t for t in rows if t.debit_raw and str(t.debit_raw).strip() not in ('', '0', '0.0', '0.00')]
zeros = [t for t in rows if not t.credit_raw and not t.debit_raw]

print(f"Total rows: {len(rows)}")
print(f"Inflows: {len(inflows)}")
print(f"Outflows: {len(outflows)}")
print(f"Zeros: {len(zeros)}")
print("--- First 5 rows ---")
for t in rows[:5]:
    print(vars(t))
