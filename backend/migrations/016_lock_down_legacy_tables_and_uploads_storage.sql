-- Migration 016: lock down legacy pre-pds_ tables and the "uploads" storage
-- bucket. Confirmed dead in current code (commit 5aea748f, 2026-03-03,
-- "legacy cleanup" — deleted backend/routes/deals.py and local_storage.py)
-- but still holding real historical data: deals (7 rows, one dev test
-- account), deal_conversations (4 rows), documents (57 rows across 24
-- distinct real user_ids, Dec 2025-Feb 2026), evidence (3 rows), judgments
-- (0 rows). Several carried blanket USING(true) policies letting ANY
-- authenticated (or, for documents/notes/anomalies/extracted_rows, fully
-- unauthenticated) caller read/write rows belonging to other users. The
-- "uploads" storage bucket had matching public SELECT/INSERT/DELETE
-- policies exposing the actual uploaded bank-statement files to anyone with
-- no auth at all. The current v1 pipeline never touches this bucket (files
-- are read into memory and parsed in-process, never persisted to Storage),
-- so this is safe to lock down. Policies are replaced with owner-scoped
-- equivalents rather than dropped outright, preserving the data for its
-- rightful owners rather than deleting it.

-- deals: drop blanket-true policies; the owner-scoped quad already in
-- place ("Users can view/insert/update/delete their own deals") remains.
DROP POLICY IF EXISTS "authenticated_read_deals" ON public.deals;
DROP POLICY IF EXISTS "authenticated_write_deals" ON public.deals;
DROP POLICY IF EXISTS "authenticated_update_deals" ON public.deals;

-- deal_conversations: replace blanket true SELECT/INSERT with deal-owner scoping
DROP POLICY IF EXISTS "authenticated_read_deal_conversations" ON public.deal_conversations;
DROP POLICY IF EXISTS "authenticated_write_deal_conversations" ON public.deal_conversations;
DROP POLICY IF EXISTS "deal_conversations_via_deal" ON public.deal_conversations;
CREATE POLICY "deal_conversations_via_deal" ON public.deal_conversations
  FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.deals d WHERE d.id = deal_conversations.deal_id AND d.created_by = auth.uid()))
  WITH CHECK (EXISTS (SELECT 1 FROM public.deals d WHERE d.id = deal_conversations.deal_id AND d.created_by = auth.uid()));

-- documents: replace public ALL-true with owner scoping via user_id
DROP POLICY IF EXISTS "Public access for demo" ON public.documents;
DROP POLICY IF EXISTS "documents_owner" ON public.documents;
CREATE POLICY "documents_owner" ON public.documents
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- notes/anomalies/extracted_rows: replace public ALL-true with scoping via
-- the parent document's owner
DROP POLICY IF EXISTS "Public access for demo notes" ON public.notes;
DROP POLICY IF EXISTS "notes_via_document" ON public.notes;
CREATE POLICY "notes_via_document" ON public.notes
  FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.documents doc WHERE doc.id = notes.document_id AND doc.user_id = auth.uid()))
  WITH CHECK (EXISTS (SELECT 1 FROM public.documents doc WHERE doc.id = notes.document_id AND doc.user_id = auth.uid()));

DROP POLICY IF EXISTS "Public access for demo anomalies" ON public.anomalies;
DROP POLICY IF EXISTS "anomalies_via_document" ON public.anomalies;
CREATE POLICY "anomalies_via_document" ON public.anomalies
  FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.documents doc WHERE doc.id = anomalies.document_id AND doc.user_id = auth.uid()))
  WITH CHECK (EXISTS (SELECT 1 FROM public.documents doc WHERE doc.id = anomalies.document_id AND doc.user_id = auth.uid()));

DROP POLICY IF EXISTS "Public access for demo rows" ON public.extracted_rows;
DROP POLICY IF EXISTS "extracted_rows_via_document" ON public.extracted_rows;
CREATE POLICY "extracted_rows_via_document" ON public.extracted_rows
  FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.documents doc WHERE doc.id = extracted_rows.document_id AND doc.user_id = auth.uid()))
  WITH CHECK (EXISTS (SELECT 1 FROM public.documents doc WHERE doc.id = extracted_rows.document_id AND doc.user_id = auth.uid()));

-- storage.objects ("uploads" bucket): drop public read/write/delete, scope
-- to the owning user's folder (path convention: uploads/{user_id}/{file})
DROP POLICY IF EXISTS "Public view access" ON storage.objects;
DROP POLICY IF EXISTS "Public upload access" ON storage.objects;
DROP POLICY IF EXISTS "Public delete access" ON storage.objects;
DROP POLICY IF EXISTS "uploads_owner_select" ON storage.objects;
DROP POLICY IF EXISTS "uploads_owner_insert" ON storage.objects;
DROP POLICY IF EXISTS "uploads_owner_delete" ON storage.objects;
CREATE POLICY "uploads_owner_select" ON storage.objects
  FOR SELECT TO authenticated
  USING (bucket_id = 'uploads' AND (storage.foldername(name))[1] = auth.uid()::text);
CREATE POLICY "uploads_owner_insert" ON storage.objects
  FOR INSERT TO authenticated
  WITH CHECK (bucket_id = 'uploads' AND (storage.foldername(name))[1] = auth.uid()::text);
CREATE POLICY "uploads_owner_delete" ON storage.objects
  FOR DELETE TO authenticated
  USING (bucket_id = 'uploads' AND (storage.foldername(name))[1] = auth.uid()::text);
