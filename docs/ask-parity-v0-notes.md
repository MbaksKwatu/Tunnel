# Ask Parity v0 — Post-Implementation Notes (Non-Blocking)

These are **intentional design choices**, not bugs.  
No code changes are required for v0.  
Documented here to avoid accidental "fixes" later.

---

## ⚠️ Gap 1: Evidence Presence vs Meaning (INTENTIONAL)

### Current behavior
Parity can correctly state **evidence presence**, e.g.:

- Financials: yes
- Bank statements: no
- Governance docs: yes

Users may ask follow-up questions such as:
- "Are these financials reliable?"
- "Do the numbers look strong / clean?"
- "Can we trust these statements?"

### Why this is intentional
Parity is designed to:
- Reason over **what evidence exists**
- Explain **how judgment was derived**
- Surface **what is missing or unclear**

Parity is **explicitly not** designed to:
- Verify document truth
- Assess raw data quality
- Re-score or reinterpret financials outside the judgment system

This is a **positioning and trust boundary**, not a missing feature.

### Guidance (no code changes)
When explaining the product (demo / sales / onboarding), use this framing:

> "Parity reasons over *what exists* and *how it was judged*, not the raw truth or cleanliness of documents."

Do **not** add speculative language to the model to answer "reliability" questions.

---

## ⚠️ Gap 2: No Explicit Confidence Calibration Copy (OPTIONAL)

### Current behavior
Parity behaves conservatively due to:
- Strict system prompt
- Judgment-not-run guardrails
- No decision-making language

However, the **UI does not explicitly say this**.

### Optional future UI enhancement (NOT REQUIRED FOR v0)
Consider adding a small subtitle or helper text in the Ask Parity card:

> "Parity explains evidence and judgment. It does not make decisions."

This is **purely UX calibration**, not functional logic.  
Do not block v0 or refactor backend logic for this.

---

## Summary

- Both gaps are **intentional constraints**
- They preserve analyst trust and auditability
- Do not "fix" them unless explicitly changing product philosophy

Ask Parity v0 is correct as implemented.
