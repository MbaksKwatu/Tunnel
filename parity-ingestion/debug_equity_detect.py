import pdfplumber

FIXTURE = "/Users/mbakswatu/Desktop/Demofiles/Sassy_Cosmetics_2025_merged.pdf"

with pdfplumber.open(FIXTURE) as pdf:
    print(f"Total pages: {len(pdf.pages)}")
    print("--- Page 1 full text ---")
    text = pdf.pages[0].extract_text() or ""
    print(repr(text[:1000]))
    print()
    print("--- Detection string checks ---")
    checks = [
        "STATEMENT OF ACCOUNT",
        "EQUITY",
        "Particulars",
        "Money Out",
        "Money In",
        "equity",
        "statement of account",
    ]
    for c in checks:
        print(f"  '{c}' found: {c in text}")
