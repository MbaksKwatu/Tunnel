-- Migration: 20260420_add_currency_conversion_role
-- Add currency_conversion to role_enum

ALTER TYPE role_enum ADD VALUE IF NOT EXISTS 'currency_conversion';

-- Verify
-- SELECT unnest(enum_range(NULL::role_enum)) AS role ORDER BY role;

-- Optional backfill — uncomment to reclassify historical misclassified conversions:
-- UPDATE pds_txn_entity_map m
-- SET role = 'currency_conversion'
-- FROM pds_raw_transactions t
-- WHERE m.txn_id = t.id
--   AND m.role = 'needs_review'
--   AND (t.description ILIKE '%CONVERSION TRANSFER%EUR%'
--        OR t.description ILIKE '%CONVERSION TRANSFER%USD%'
--        OR t.description ILIKE '%EUR%AT%TRF FROM%');
