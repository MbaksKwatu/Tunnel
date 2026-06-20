-- Mirrors backend/migrations/016_lock_down_legacy_tables_and_uploads_storage.sql
-- so the self-healing startup runner (backend/migrations/) also covers it.
DROP POLICY IF EXISTS "authenticated_read_deals" ON public.deals;
DROP POLICY IF EXISTS "authenticated_write_deals" ON public.deals;
DROP POLICY IF EXISTS "authenticated_update_deals" ON public.deals;

DROP POLICY IF EXISTS "authenticated_read_deal_conversations" ON public.deal_conversations;
DROP POLICY IF EXISTS "authenticated_write_deal_conversations" ON public.deal_conversations;
DROP POLICY IF EXISTS "deal_conversations_via_deal" ON public.deal_conversations;
CREATE POLICY "deal_conversations_via_deal" ON public.deal_conversations
  FOR ALL TO authenticated
  USING (EXISTS (SELECT 1 FROM public.deals d WHERE d.id = deal_conversations.deal_id AND d.created_by = auth.uid()))
  WITH CHECK (EXISTS (SELECT 1 FROM public.deals d WHERE d.id = deal_conversations.deal_id AND d.created_by = auth.uid()));

DROP POLICY IF EXISTS "Public access for demo" ON public.documents;
DROP POLICY IF EXISTS "documents_owner" ON public.documents;
CREATE POLICY "documents_owner" ON public.documents
  FOR ALL TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

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
