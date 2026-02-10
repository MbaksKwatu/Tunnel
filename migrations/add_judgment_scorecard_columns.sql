-- Add scorecard and follow-up questions to judgments for Phase 1 outputs

ALTER TABLE judgments
ADD COLUMN IF NOT EXISTS scorecard JSONB,
ADD COLUMN IF NOT EXISTS follow_up_questions JSONB;

-- No backfill necessary; existing rows can remain NULL.
