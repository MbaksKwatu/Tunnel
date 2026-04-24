-- =============================================================================
-- Parity Staging Schema Mirror
-- Apply this to parity-staging (ref: kstuensfekanfberjubz) once.
-- Mirrors the live Parity DB schema exactly — enums, tables, constraints,
-- indexes, RLS enabled/disabled, and all RLS policies.
--
-- Run via: psql $STAGING_DB_URL -f parity_staging_schema.sql
-- =============================================================================

-- ── Drop existing tables (reverse FK order) to guarantee schema parity ───────
-- Safe: sync workflow truncates all data before calling this script anyway.

DROP TABLE IF EXISTS pds_custom_flags CASCADE;
DROP TABLE IF EXISTS pds_classification_overrides CASCADE;
DROP TABLE IF EXISTS pds_snapshot_enrichments CASCADE;
DROP TABLE IF EXISTS pds_snapshots CASCADE;
DROP TABLE IF EXISTS pds_analysis_runs CASCADE;
DROP TABLE IF EXISTS pds_overrides CASCADE;
DROP TABLE IF EXISTS pds_txn_entity_map CASCADE;
DROP TABLE IF EXISTS pds_entities CASCADE;
DROP TABLE IF EXISTS pds_transfer_links CASCADE;
DROP TABLE IF EXISTS pds_raw_transactions CASCADE;
DROP TABLE IF EXISTS pds_documents CASCADE;
DROP TABLE IF EXISTS pds_deals CASCADE;
DROP TABLE IF EXISTS benchmark_metrics CASCADE;
DROP TABLE IF EXISTS deal_conversations CASCADE;
DROP TABLE IF EXISTS judgments CASCADE;
DROP TABLE IF EXISTS evidence CASCADE;
DROP TABLE IF EXISTS notes CASCADE;
DROP TABLE IF EXISTS anomalies CASCADE;
DROP TABLE IF EXISTS extracted_rows CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP TABLE IF EXISTS thesis CASCADE;
DROP TABLE IF EXISTS deals CASCADE;
DROP TABLE IF EXISTS profiles CASCADE;


-- ── Enums ────────────────────────────────────────────────────────────────────

DO $$ BEGIN
  CREATE TYPE analysis_state_enum AS ENUM ('LIVE_DRAFT');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE document_status_enum AS ENUM ('uploaded','processing','completed','failed');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE reconciliation_status_enum AS ENUM ('OK','NOT_RUN','FAILED_OVERLAP');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE role_enum AS ENUM (
    'revenue_operational','revenue_non_operational','payroll','supplier',
    'transfer','other','bank_charge','loan_inflow','loan_repayment',
    'capital_injection','reversal_credit','reversal_debit','mpesa_inflow',
    'pesalink_inflow','needs_review','tax_payment','cash_withdrawal',
    'airtime_purchase','bill_payment','merchant_payment','mobile_money_transfer',
    'opening_balance','closing_balance','named_counterparty_debit',
    'person_to_person_transfer','supplier_payment','pesalink_outflow',
    'currency_conversion','owner_distribution'
  );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE run_trigger_enum AS ENUM ('parse_complete','override_applied','manual_rerun');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE TYPE tier_enum AS ENUM ('High','Medium','Low');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- ── Non-PDS tables ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS profiles (
  id          uuid PRIMARY KEY REFERENCES auth.users ON DELETE CASCADE,
  email       text,
  role        text,
  created_at  timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deals (
  id          text PRIMARY KEY,
  company_name text NOT NULL,
  sector      text NOT NULL,
  geography   text NOT NULL,
  deal_type   text NOT NULL,
  stage       text NOT NULL,
  revenue_usd numeric,
  created_by  uuid REFERENCES auth.users,
  status      text NOT NULL DEFAULT 'draft',
  created_at  timestamp NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS thesis (
  id                       text PRIMARY KEY,
  fund_id                  uuid REFERENCES auth.users,
  investment_focus         text,
  sector_preferences       jsonb,
  kill_conditions          jsonb,
  weights                  jsonb,
  is_default               boolean DEFAULT false,
  geography_constraints    jsonb,
  stage_preferences        jsonb,
  min_revenue_usd          numeric,
  governance_requirements  jsonb,
  financial_thresholds     jsonb,
  data_confidence_tolerance text,
  impact_requirements      jsonb,
  name                     text,
  created_at               timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id          uuid,
  file_name        text NOT NULL,
  file_type        text NOT NULL,
  file_url         text,
  format_detected  text,
  upload_date      timestamptz DEFAULT now(),
  status           text DEFAULT 'uploaded',
  rows_count       int DEFAULT 0,
  anomalies_count  int DEFAULT 0,
  error_message    text,
  insights_summary jsonb,
  created_at       timestamptz DEFAULT now(),
  updated_at       timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS extracted_rows (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id),
  row_index   int NOT NULL,
  raw_json    jsonb NOT NULL,
  created_at  timestamptz DEFAULT now(),
  UNIQUE (document_id, row_index)
);

CREATE TABLE IF NOT EXISTS anomalies (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id      uuid NOT NULL REFERENCES documents(id),
  row_index        int,
  anomaly_type     text NOT NULL,
  severity         text NOT NULL,
  description      text NOT NULL,
  score            real,
  suggested_action text,
  metadata         jsonb,
  raw_json         jsonb,
  evidence         jsonb,
  detected_at      timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notes (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES documents(id),
  anomaly_id  uuid,
  parent_id   uuid REFERENCES notes(id),
  author      text DEFAULT 'system',
  content     text,
  created_at  timestamptz DEFAULT now(),
  updated_at  timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS evidence (
  id               text PRIMARY KEY,
  deal_id          text NOT NULL REFERENCES deals(id),
  document_id      uuid REFERENCES documents(id),
  evidence_type    text NOT NULL,
  extracted_data   jsonb,
  confidence_score double precision DEFAULT 0.7,
  uploaded_at      timestamp DEFAULT now(),
  evidence_subtype text
);

CREATE TABLE IF NOT EXISTS judgments (
  id                  text PRIMARY KEY,
  deal_id             text NOT NULL REFERENCES deals(id),
  investment_readiness text,
  thesis_alignment    text,
  kill_signals        jsonb,
  confidence_level    text,
  dimension_scores    jsonb,
  explanations        jsonb,
  created_at          timestamp DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deal_conversations (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id    text NOT NULL REFERENCES deals(id),
  role       text NOT NULL,
  content    text NOT NULL,
  created_at timestamptz DEFAULT now()
);

CREATE TABLE IF NOT EXISTS benchmark_metrics (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id        uuid NOT NULL,
  institution_id    uuid NOT NULL,
  deal_id           uuid,
  recorded_at       timestamptz DEFAULT now(),
  metric_name       text NOT NULL,
  metric_value_bps  int,
  notes             text
);


-- ── PDS core tables ───────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pds_deals (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  created_by              uuid NOT NULL,
  currency                text NOT NULL,
  name                    text,
  accrual_revenue_cents   bigint,
  accrual_period_start    date,
  accrual_period_end      date,
  accrual_manually_entered boolean NOT NULL DEFAULT true,
  created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pds_documents (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id          uuid NOT NULL REFERENCES pds_deals(id),
  storage_url      text NOT NULL,
  file_type        text NOT NULL,
  status           document_status_enum NOT NULL DEFAULT 'uploaded',
  currency_detected text,
  currency_mismatch boolean NOT NULL DEFAULT false,
  created_by       uuid,
  created_at       timestamptz NOT NULL DEFAULT now(),
  analytics        jsonb,
  batch_number     int,
  source_files     jsonb,
  is_batch_upload  boolean DEFAULT false,
  error_message    text,
  error_type       text,
  error_stage      text,
  next_action      text,
  updated_at       timestamptz DEFAULT now()
);

-- Created without transfer_pair_id FK to break the circular dependency.
-- The FK is added after pds_transfer_links is created (see below).
CREATE TABLE IF NOT EXISTS pds_raw_transactions (
  id                   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id              uuid NOT NULL REFERENCES pds_deals(id),
  document_id          uuid NOT NULL REFERENCES pds_documents(id),
  account_id           text NOT NULL,
  txn_date             date NOT NULL,
  signed_amount_cents  bigint NOT NULL,
  abs_amount_cents     bigint,
  raw_descriptor       text NOT NULL,
  parsed_descriptor    text NOT NULL,
  normalized_descriptor text NOT NULL,
  txn_id               text NOT NULL,
  is_transfer          boolean NOT NULL DEFAULT false,
  transfer_pair_id     uuid,
  created_at           timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, txn_id)
);

CREATE TABLE IF NOT EXISTS pds_transfer_links (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id            uuid NOT NULL REFERENCES pds_deals(id),
  txn_out_id         uuid NOT NULL UNIQUE REFERENCES pds_raw_transactions(id),
  txn_in_id          uuid NOT NULL UNIQUE REFERENCES pds_raw_transactions(id),
  abs_amount_cents   bigint NOT NULL,
  match_rule_version text NOT NULL,
  created_at         timestamptz NOT NULL DEFAULT now()
);

-- Close the circular FK now that pds_transfer_links exists
DO $$ BEGIN
  ALTER TABLE pds_raw_transactions
    ADD CONSTRAINT pds_raw_txn_transfer_pair_fk
    FOREIGN KEY (transfer_pair_id) REFERENCES pds_transfer_links(id);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

CREATE TABLE IF NOT EXISTS pds_entities (
  entity_id          text PRIMARY KEY,
  deal_id            uuid NOT NULL REFERENCES pds_deals(id),
  normalized_name    text NOT NULL,
  display_name       text NOT NULL,
  strong_identifiers jsonb NOT NULL DEFAULT '{}',
  created_at         timestamptz NOT NULL DEFAULT now(),
  UNIQUE (deal_id, normalized_name)
);

CREATE TABLE IF NOT EXISTS pds_txn_entity_map (
  txn_id       uuid NOT NULL REFERENCES pds_raw_transactions(id),
  entity_id    text NOT NULL REFERENCES pds_entities(entity_id),
  deal_id      uuid NOT NULL REFERENCES pds_deals(id),
  role         role_enum NOT NULL,
  role_version text NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (txn_id)
);

CREATE TABLE IF NOT EXISTS pds_overrides (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id     uuid NOT NULL REFERENCES pds_deals(id),
  entity_id   text NOT NULL REFERENCES pds_entities(entity_id),
  field       text NOT NULL,
  old_value   text,
  new_value   text NOT NULL,
  weight      numeric NOT NULL,
  reason      text,
  created_by  uuid NOT NULL,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pds_analysis_runs (
  id                            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id                       uuid NOT NULL REFERENCES pds_deals(id),
  state                         analysis_state_enum NOT NULL DEFAULT 'LIVE_DRAFT',
  schema_version                text NOT NULL,
  config_version                text NOT NULL,
  run_trigger                   run_trigger_enum NOT NULL,
  non_transfer_abs_total_cents  bigint NOT NULL,
  classified_abs_total_cents    bigint NOT NULL,
  coverage_pct_bp               int NOT NULL,
  missing_month_penalty_bp      int NOT NULL,
  override_penalty_bp           int NOT NULL,
  reconciliation_pct_bp         int,
  base_confidence_bp            int NOT NULL,
  final_confidence_bp           int NOT NULL,
  missing_month_count           int NOT NULL,
  reconciliation_status         reconciliation_status_enum NOT NULL,
  tier                          tier_enum NOT NULL,
  tier_capped                   boolean NOT NULL DEFAULT false,
  raw_transaction_hash          text NOT NULL,
  transfer_links_hash           text NOT NULL,
  entities_hash                 text NOT NULL,
  overrides_hash                text NOT NULL,
  created_at                    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pds_snapshots (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_id             uuid NOT NULL REFERENCES pds_deals(id),
  analysis_run_id     uuid NOT NULL REFERENCES pds_analysis_runs(id),
  schema_version      text NOT NULL,
  config_version      text NOT NULL,
  sha256_hash         text NOT NULL UNIQUE,
  canonical_json      text NOT NULL,
  created_by          uuid NOT NULL,
  created_at          timestamptz NOT NULL DEFAULT now(),
  financial_state_hash text
);

CREATE TABLE IF NOT EXISTS pds_snapshot_enrichments (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  base_snapshot_id uuid NOT NULL REFERENCES pds_snapshots(id),
  enriched_hash    text NOT NULL UNIQUE,
  analyst_id       text NOT NULL,
  analyst_name     text,
  narrative        text,
  enrichment_reason text,
  is_final         boolean NOT NULL DEFAULT false,
  created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pds_classification_overrides (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  enrichment_id    uuid NOT NULL REFERENCES pds_snapshot_enrichments(id),
  txn_id           uuid NOT NULL REFERENCES pds_raw_transactions(id),
  original_role    text NOT NULL,
  original_reason  text,
  override_role    text NOT NULL,
  override_reason  text NOT NULL,
  overridden_by    text NOT NULL,
  overridden_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (enrichment_id, txn_id)
);

CREATE TABLE IF NOT EXISTS pds_custom_flags (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  enrichment_id    uuid NOT NULL REFERENCES pds_snapshot_enrichments(id),
  flag_type        text NOT NULL,
  flag_name        text NOT NULL,
  flag_severity    text NOT NULL,
  flag_description text NOT NULL,
  criteria         jsonb NOT NULL,
  triggered        boolean NOT NULL,
  trigger_count    int NOT NULL DEFAULT 0,
  trigger_details  jsonb NOT NULL DEFAULT '[]',
  created_by       text NOT NULL,
  created_at       timestamptz NOT NULL DEFAULT now()
);


-- ── Indexes ───────────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_anomalies_document_id ON anomalies(document_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity ON anomalies(severity);
CREATE INDEX IF NOT EXISTS idx_deal_conversations_deal_id ON deal_conversations(deal_id);
CREATE INDEX IF NOT EXISTS idx_deal_conversations_created_at ON deal_conversations(deal_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_deals_created_by ON deals(created_by);
CREATE INDEX IF NOT EXISTS idx_deals_status_created_by ON deals(status, created_by);
CREATE INDEX IF NOT EXISTS idx_documents_status ON documents(status);
CREATE INDEX IF NOT EXISTS idx_documents_user_id ON documents(user_id);
CREATE INDEX IF NOT EXISTS idx_evidence_deal_id ON evidence(deal_id);
CREATE INDEX IF NOT EXISTS idx_evidence_document_id ON evidence(document_id);
CREATE INDEX IF NOT EXISTS idx_extracted_rows_document_id ON extracted_rows(document_id);
CREATE INDEX IF NOT EXISTS idx_judgments_deal_id ON judgments(deal_id);
CREATE INDEX IF NOT EXISTS idx_pds_analysis_runs_deal ON pds_analysis_runs(deal_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pds_cls_overrides_enrichment ON pds_classification_overrides(enrichment_id);
CREATE INDEX IF NOT EXISTS idx_pds_cls_overrides_txn ON pds_classification_overrides(txn_id);
CREATE INDEX IF NOT EXISTS idx_pds_custom_flags_enrichment ON pds_custom_flags(enrichment_id);
CREATE INDEX IF NOT EXISTS idx_pds_custom_flags_type ON pds_custom_flags(flag_type);
CREATE INDEX IF NOT EXISTS idx_pds_custom_flags_severity ON pds_custom_flags(flag_severity) WHERE triggered = true;
CREATE INDEX IF NOT EXISTS idx_pds_documents_batch ON pds_documents(deal_id, batch_number) WHERE batch_number IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pds_overrides_deal_entity ON pds_overrides(deal_id, entity_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pds_raw_txn_deal_date ON pds_raw_transactions(deal_id, txn_date);
CREATE INDEX IF NOT EXISTS idx_pds_raw_txn_acct_date ON pds_raw_transactions(deal_id, account_id, txn_date);
CREATE INDEX IF NOT EXISTS idx_pds_raw_txn_document ON pds_raw_transactions(document_id);
CREATE INDEX IF NOT EXISTS idx_pds_enrichments_base ON pds_snapshot_enrichments(base_snapshot_id);
CREATE INDEX IF NOT EXISTS idx_pds_enrichments_analyst ON pds_snapshot_enrichments(analyst_id);
CREATE INDEX IF NOT EXISTS idx_pds_enrichments_final ON pds_snapshot_enrichments(is_final) WHERE is_final = true;
CREATE INDEX IF NOT EXISTS idx_pds_snapshots_deal ON pds_snapshots(deal_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_pds_snapshots_fin_state ON pds_snapshots(deal_id, financial_state_hash);
CREATE INDEX IF NOT EXISTS idx_pds_txn_entity_map_deal_role ON pds_txn_entity_map(deal_id, role);
CREATE INDEX IF NOT EXISTS idx_pds_txn_entity_map_entity_id ON pds_txn_entity_map(entity_id);


-- ── RLS ───────────────────────────────────────────────────────────────────────

ALTER TABLE documents                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE extracted_rows             ENABLE ROW LEVEL SECURITY;
ALTER TABLE anomalies                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE notes                      ENABLE ROW LEVEL SECURITY;
ALTER TABLE thesis                     ENABLE ROW LEVEL SECURITY;
ALTER TABLE judgments                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE evidence                   ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_deals                  ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_documents              ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_raw_transactions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_transfer_links         ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_entities               ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_txn_entity_map         ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_overrides              ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_analysis_runs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_snapshots              ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_snapshot_enrichments   ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_classification_overrides ENABLE ROW LEVEL SECURITY;
ALTER TABLE pds_custom_flags           ENABLE ROW LEVEL SECURITY;


-- ── RLS Policies ─────────────────────────────────────────────────────────────

-- anomalies
DO $$ BEGIN
  CREATE POLICY "Public access for demo anomalies" ON anomalies FOR ALL TO public USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- documents
DO $$ BEGIN
  CREATE POLICY "Public access for demo" ON documents FOR ALL TO public USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- extracted_rows
DO $$ BEGIN
  CREATE POLICY "Public access for demo rows" ON extracted_rows FOR ALL TO public USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- notes
DO $$ BEGIN
  CREATE POLICY "Public access for demo notes" ON notes FOR ALL TO public USING (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- deals
DO $$ BEGIN
  CREATE POLICY "Users can view their own deals" ON deals FOR SELECT TO public USING ((created_by)::text = (auth.uid())::text);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "Users can insert their own deals" ON deals FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "Users can update their own deals" ON deals FOR UPDATE TO public USING ((created_by)::text = (auth.uid())::text);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "Users can delete their own deals" ON deals FOR DELETE TO public USING ((created_by)::text = (auth.uid())::text);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- thesis
DO $$ BEGIN
  CREATE POLICY "thesis_owner_rw" ON thesis FOR ALL TO authenticated USING (fund_id = auth.uid());
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- evidence
DO $$ BEGIN
  CREATE POLICY "evidence_via_deal" ON evidence FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM deals d WHERE d.id = evidence.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- judgments
DO $$ BEGIN
  CREATE POLICY "judgments_via_deal" ON judgments FOR ALL TO authenticated
    USING (EXISTS (SELECT 1 FROM deals d WHERE d.id = judgments.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_deals
DO $$ BEGIN
  CREATE POLICY "pds_deals_select" ON pds_deals FOR SELECT TO public USING (created_by = auth.uid());
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_deals_insert" ON pds_deals FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_deals_update" ON pds_deals FOR UPDATE TO public USING (created_by = auth.uid());
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_documents
DO $$ BEGIN
  CREATE POLICY "pds_documents_select" ON pds_documents FOR SELECT TO public
    USING (EXISTS (SELECT 1 FROM pds_deals d WHERE d.id = pds_documents.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_documents_insert" ON pds_documents FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_documents_update" ON pds_documents FOR UPDATE TO public
    USING (EXISTS (SELECT 1 FROM pds_deals d WHERE d.id = pds_documents.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_raw_transactions
DO $$ BEGIN
  CREATE POLICY "pds_raw_txn_select" ON pds_raw_transactions FOR SELECT TO public
    USING (EXISTS (SELECT 1 FROM pds_deals d WHERE d.id = pds_raw_transactions.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_raw_txn_insert" ON pds_raw_transactions FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_transfer_links
DO $$ BEGIN
  CREATE POLICY "pds_transfer_links_select" ON pds_transfer_links FOR SELECT TO public
    USING (EXISTS (SELECT 1 FROM pds_deals d WHERE d.id = pds_transfer_links.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_transfer_links_insert" ON pds_transfer_links FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_entities
DO $$ BEGIN
  CREATE POLICY "pds_entities_select" ON pds_entities FOR SELECT TO public
    USING (EXISTS (SELECT 1 FROM pds_deals d WHERE d.id = pds_entities.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_entities_insert" ON pds_entities FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_txn_entity_map
DO $$ BEGIN
  CREATE POLICY "pds_txn_entity_map_select" ON pds_txn_entity_map FOR SELECT TO public
    USING (EXISTS (SELECT 1 FROM pds_deals d WHERE d.id = pds_txn_entity_map.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_txn_entity_map_insert" ON pds_txn_entity_map FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_overrides
DO $$ BEGIN
  CREATE POLICY "pds_overrides_select" ON pds_overrides FOR SELECT TO public
    USING (EXISTS (SELECT 1 FROM pds_deals d WHERE d.id = pds_overrides.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_overrides_insert" ON pds_overrides FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_analysis_runs
DO $$ BEGIN
  CREATE POLICY "pds_analysis_runs_select" ON pds_analysis_runs FOR SELECT TO public
    USING (EXISTS (SELECT 1 FROM pds_deals d WHERE d.id = pds_analysis_runs.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_analysis_runs_insert" ON pds_analysis_runs FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_snapshots
DO $$ BEGIN
  CREATE POLICY "pds_snapshots_select" ON pds_snapshots FOR SELECT TO public
    USING (EXISTS (SELECT 1 FROM pds_deals d WHERE d.id = pds_snapshots.deal_id AND d.created_by = auth.uid()));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_snapshots_insert" ON pds_snapshots FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_snapshot_enrichments
DO $$ BEGIN
  CREATE POLICY "pds_enrichments_select" ON pds_snapshot_enrichments FOR SELECT TO public
    USING (EXISTS (
      SELECT 1 FROM pds_snapshots s JOIN pds_deals d ON d.id = s.deal_id
      WHERE s.id = pds_snapshot_enrichments.base_snapshot_id AND d.created_by = auth.uid()
    ));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_enrichments_insert" ON pds_snapshot_enrichments FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_enrichments_update_final" ON pds_snapshot_enrichments FOR UPDATE TO public
    USING (analyst_id = (auth.uid())::text);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_classification_overrides
DO $$ BEGIN
  CREATE POLICY "pds_cls_overrides_select" ON pds_classification_overrides FOR SELECT TO public
    USING (EXISTS (
      SELECT 1
      FROM pds_snapshot_enrichments e
      JOIN pds_snapshots s ON s.id = e.base_snapshot_id
      JOIN pds_deals d ON d.id = s.deal_id
      WHERE e.id = pds_classification_overrides.enrichment_id AND d.created_by = auth.uid()
    ));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_cls_overrides_insert" ON pds_classification_overrides FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- pds_custom_flags
DO $$ BEGIN
  CREATE POLICY "pds_custom_flags_select" ON pds_custom_flags FOR SELECT TO public
    USING (EXISTS (
      SELECT 1
      FROM pds_snapshot_enrichments e
      JOIN pds_snapshots s ON s.id = e.base_snapshot_id
      JOIN pds_deals d ON d.id = s.deal_id
      WHERE e.id = pds_custom_flags.enrichment_id AND d.created_by = auth.uid()
    ));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
  CREATE POLICY "pds_custom_flags_insert" ON pds_custom_flags FOR INSERT TO public WITH CHECK (true);
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
