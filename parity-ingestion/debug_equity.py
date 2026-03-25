from app.extractors.equity_extractor import extract_equity_pdf

FIXTURE = "/Users/mbakswatu/Desktop/Demofiles/bankstatementsamples/Unlock PDF Equity Unlocked.pdf"

result = extract_equity_pdf(FIXTURE)
rows = result.raw_transactions

inflows = [t for t in rows if t.credit_raw != '']
outflows = [t for t in rows if t.debit_raw != '']
zeros = [t for t in rows if t.credit_raw == '' and t.debit_raw == '']

print(f"Total: {len(rows)}")
print(f"Inflows: {len(inflows)}")
print(f"Outflows: {len(outflows)}")
print(f"Zeros (both empty): {len(zeros)}")
print("--- All rows ---")
for t in rows:
    print(vars(t))
