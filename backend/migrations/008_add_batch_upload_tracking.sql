-- Migration 008: Batch Upload Tracking
-- Allows users to upload multiple files at once (3 files/batch, 4 batches/year)

-- Add batch tracking columns to pds_documents
ALTER TABLE pds_documents
ADD COLUMN IF NOT EXISTS batch_number INT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS source_files JSONB DEFAULT NULL,
ADD COLUMN IF NOT EXISTS is_batch_upload BOOLEAN DEFAULT FALSE;

-- Add comment
COMMENT ON COLUMN pds_documents.batch_number IS
  'Batch sequence number (1-4) for multi-file uploads within a deal';
COMMENT ON COLUMN pds_documents.source_files IS
  'Array of original file URLs that were merged into this document';
COMMENT ON COLUMN pds_documents.is_batch_upload IS
  'True if this document was created by merging multiple files';

-- Create index for batch queries
CREATE INDEX IF NOT EXISTS idx_pds_documents_batch
ON pds_documents(deal_id, batch_number)
WHERE batch_number IS NOT NULL;

-- Create function to get batch count for a deal
CREATE OR REPLACE FUNCTION get_deal_batch_count(p_deal_id UUID)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  batch_count INT;
BEGIN
  SELECT COUNT(DISTINCT batch_number)
  INTO batch_count
  FROM pds_documents
  WHERE deal_id = p_deal_id
    AND batch_number IS NOT NULL;

  RETURN COALESCE(batch_count, 0);
END;
$$;

COMMENT ON FUNCTION get_deal_batch_count(uuid) IS
  'Returns number of batch uploads used for a deal (max 4 allowed)';
