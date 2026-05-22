-- Validate KRA tax payment classification after deal ingestion.
-- Usage: replace <deal_uuid> with the target deal_id.

SELECT
    t.txn_date,
    t.description,
    t.signed_amount_cents / 100.0 AS amount_kes,
    CASE WHEN t.signed_amount_cents > 0 THEN 'credit' ELSE 'debit' END AS direction,
    m.role
FROM pds_raw_transactions t
JOIN pds_txn_entity_map m ON m.txn_id = t.id
WHERE t.deal_id = '<deal_uuid>'
  AND (
      t.description ILIKE '%KRA%'
      OR t.description ILIKE '%PAYE%'
      OR t.description ILIKE '%VAT%'
      OR t.description ILIKE '%TAX%'
  )
ORDER BY t.txn_date;

-- RED FLAGS:
-- tax_payment with direction = 'credit'  → direction guard missed (should not happen)
-- KRA credit with role not in (reversal_credit, needs_review) → misclassified
-- No rows at all for a business that should pay tax → KRA Compliance: NOT_DETECTED

-- EXPECTED:
-- Most rows:    debit  + tax_payment      (normal KRA payments)
-- Rare rows:    credit + reversal_credit  (tax reversals)
-- Very rare:    credit + needs_review     (unexpected credits — verify with client)
