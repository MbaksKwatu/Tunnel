-- post_ingestion_check.sql
-- Run after every deal upload. Replace :deal_id with the actual deal UUID.
-- Any row with role + direction mismatch = pipeline bug. Investigate before proceeding.

SELECT
  role,
  CASE WHEN signed_amount_cents > 0 THEN 'credit' ELSE 'debit' END as direction,
  COUNT(*) as cnt
FROM pds_raw_transactions
WHERE deal_id = ':deal_id'
GROUP BY role, direction
ORDER BY role, direction;

-- RED FLAGS — these combinations should never appear:
-- revenue_operational + debit
-- bank_charge         + credit
-- tax_payment         + credit
-- loan_repayment      + credit
-- supplier_payment    + credit

-- GARBAGE DATE CHECK — run alongside the above:
SELECT COUNT(*) as future_date_rows
FROM pds_raw_transactions
WHERE deal_id = ':deal_id'
  AND txn_date > CURRENT_DATE + INTERVAL '5 years';
-- Expected: 0. Any non-zero value = parser artifact (see xlsx_parser._is_valid_transaction_date).
