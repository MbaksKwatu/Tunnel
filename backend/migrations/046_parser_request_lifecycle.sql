-- 046: parser-request lifecycle redesign (pds_parser_requests becomes the
-- single admin-actionable table for client parser requests).
--
-- Step 0 findings this migration is built on (prod, ifcdbhbuucmjgtjkluna,
-- checked 2026-10-01):
--   * status had no CHECK constraint at all; live values were 9 x 'new',
--     1 x 'resolved' (SBM Bank, set by hand -- no code path wrote it).
--   * the enrich path wrote 'pending' ("client submitted the form"), the
--     client display mapped new/pending/resolved, the admin UI cycled
--     pending/in_progress/done against the OTHER table (parser_requests).
--   * no contact email was stored on the row, so a resolve notification had
--     no recipient for most rows.
--   * the SELECT policy named "...read own parser requests" was USING (true):
--     every signed-in account could read every client's rows.
--
-- What this does:
--   1. One status vocabulary, enforced: new -> in_progress -> testing ->
--      resolved. 'pending' is folded into 'new'; "the client touched the
--      form" moves to its own submitted_at column.
--   2. contact_email on the row (form value, else the account's contact
--      email, else its login email -- backfilled below for attributed rows).
--   3. resolved can only be recorded with a declared basis: 'test_pass'
--      (the admin "Test against submitted file" gate passed), 'override'
--      (requires a written reason), or 'legacy' (resolved before this gate
--      existed). Enforced here, not only in application code.
--   4. pds_parser_request_events: append-only log of status changes, test
--      runs and resolve notifications (service-role only).
--   5. RLS: reads scoped to created_by = auth.uid(); inserts may only
--      attribute a row to the inserting account (or leave it unattributed).

-- ── 1. New columns ─────────────────────────────────────────────────────────
ALTER TABLE public.pds_parser_requests
  ADD COLUMN submitted_at timestamptz,
  ADD COLUMN contact_email text,
  ADD COLUMN resolved_at timestamptz,
  ADD COLUMN resolution_basis text,
  ADD COLUMN resolution_note text;

COMMENT ON COLUMN public.pds_parser_requests.submitted_at IS
  'When a person (client form or deal-page modal) submitted details for this request. NULL = auto-created at detection time and never touched. Replaces the old ''pending'' status value.';
COMMENT ON COLUMN public.pds_parser_requests.contact_email IS
  'Where the resolve notification goes. From the form when supplied, else the created_by account''s user_profiles.contact_email, else its login email.';
COMMENT ON COLUMN public.pds_parser_requests.resolution_basis IS
  'Why this row is resolved: test_pass (admin test against the stored file passed), override (admin override, resolution_note holds the reason), legacy (resolved before migration 046 added the gate).';

-- ── 2. Backfill ────────────────────────────────────────────────────────────
-- A human supplied bank_name on every row that has one (the form requires it,
-- the modal enrich fills it; auto-created rows insert it as NULL), so that is
-- the best available evidence of submission. created_at is the closest known
-- timestamp; the exact submission moment of older rows was never recorded.
UPDATE public.pds_parser_requests
SET submitted_at = coalesce(created_at, now())
WHERE bank_name IS NOT NULL OR status = 'pending';

UPDATE public.pds_parser_requests
SET status = 'new'
WHERE status = 'pending';

UPDATE public.pds_parser_requests
SET resolution_basis = 'legacy',
    resolution_note = 'Marked resolved by hand before migration 046 added the verification gate; no recorded test run.'
WHERE status = 'resolved';

UPDATE public.pds_parser_requests r
SET contact_email = coalesce(nullif(btrim(p.contact_email), ''), u.email)
FROM auth.users u
LEFT JOIN public.user_profiles p ON p.user_id = u.id
WHERE u.id = r.created_by
  AND r.contact_email IS NULL;

-- ── 3. Constraints ─────────────────────────────────────────────────────────
-- No guard on the status CHECK: if any row still carries a value outside the
-- vocabulary after the backfill above, this must fail loud, not be skipped.
ALTER TABLE public.pds_parser_requests
  ADD CONSTRAINT pds_parser_requests_status_check
    CHECK (status IN ('new', 'in_progress', 'testing', 'resolved')),
  ADD CONSTRAINT pds_parser_requests_resolution_basis_check
    CHECK (resolution_basis IS NULL OR resolution_basis IN ('test_pass', 'override', 'legacy')),
  ADD CONSTRAINT pds_parser_requests_resolved_requires_basis
    CHECK (status <> 'resolved' OR resolution_basis IS NOT NULL),
  ADD CONSTRAINT pds_parser_requests_override_requires_reason
    CHECK (resolution_basis IS DISTINCT FROM 'override' OR nullif(btrim(resolution_note), '') IS NOT NULL);

COMMENT ON COLUMN public.pds_parser_requests.status IS
  'Lifecycle: new (not yet picked up) -> in_progress (admin building an extractor) -> testing (stored file being / was checked against a candidate extractor) -> resolved (verified, client notified). A failed test returns the row to in_progress.';

-- ── 4. Rollout shim for writers still sending 'pending' ───────────────────
-- staging and prod backends are deployed separately and have drifted before
-- (PAR-86 Rule 14). Until every deployed writer stops sending 'pending', fold
-- it here instead of letting the new CHECK reject the whole write (the old
-- enrich path would otherwise lose the bank name the client just typed).
CREATE FUNCTION public.pds_parser_requests_fold_pending()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  IF NEW.status = 'pending' THEN
    NEW.status := CASE WHEN TG_OP = 'UPDATE' THEN OLD.status ELSE 'new' END;
    NEW.submitted_at := coalesce(NEW.submitted_at, now());
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER pds_parser_requests_fold_pending
  BEFORE INSERT OR UPDATE OF status ON public.pds_parser_requests
  FOR EACH ROW EXECUTE FUNCTION public.pds_parser_requests_fold_pending();

-- ── 5. Event log ───────────────────────────────────────────────────────────
CREATE TABLE public.pds_parser_request_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  request_id uuid NOT NULL REFERENCES public.pds_parser_requests(id) ON DELETE CASCADE,
  kind text NOT NULL CHECK (kind IN ('status_change', 'test_run', 'notification')),
  from_status text,
  to_status text,
  actor text NOT NULL,
  reason text,
  detail jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_pds_parser_request_events_request
  ON public.pds_parser_request_events (request_id, created_at DESC);

ALTER TABLE public.pds_parser_request_events ENABLE ROW LEVEL SECURITY;

COMMENT ON TABLE public.pds_parser_request_events IS
  'Append-only audit log for pds_parser_requests: admin status changes (with override reasons), "Test against submitted file" runs and their harness digests, and resolve-notification outcomes (email / Slack). RLS enabled with no policies on purpose: written and read only by the admin app''s service-role client.';

-- ── 6. RLS on pds_parser_requests ──────────────────────────────────────────
-- Policy names have drifted between environments (supabase/migrations/015
-- creates "Users can view their own parser requests"; prod carries
-- "Authenticated users can read own parser requests" with USING (true)).
-- Drop whatever policies exist on this table and recreate the intended set,
-- so the result is the same on every database regardless of which name it has.
DO $$
DECLARE
  pol record;
BEGIN
  FOR pol IN
    SELECT policyname FROM pg_policies
    WHERE schemaname = 'public' AND tablename = 'pds_parser_requests'
  LOOP
    EXECUTE format('DROP POLICY %I ON public.pds_parser_requests', pol.policyname);
  END LOOP;
END;
$$;

ALTER TABLE public.pds_parser_requests ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users read their own parser requests"
  ON public.pds_parser_requests
  FOR SELECT TO authenticated
  USING (created_by = (SELECT auth.uid()));

CREATE POLICY "Users insert their own parser requests"
  ON public.pds_parser_requests
  FOR INSERT TO authenticated
  WITH CHECK (created_by IS NULL OR created_by = (SELECT auth.uid()));
