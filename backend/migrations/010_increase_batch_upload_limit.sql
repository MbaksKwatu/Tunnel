-- Migration 009: Increase batch upload limit from 4 to 20
-- This updates the documentation and function comments to reflect the new limit.
-- The runtime enforcement is handled in backend/v1/api.py.

COMMENT ON COLUMN pds_documents.batch_number IS
  'Batch sequence number (1-20) for multi-file uploads within a deal';

COMMENT ON FUNCTION get_deal_batch_count(uuid) IS
  'Returns number of batch uploads used for a deal (max 20 allowed)';
