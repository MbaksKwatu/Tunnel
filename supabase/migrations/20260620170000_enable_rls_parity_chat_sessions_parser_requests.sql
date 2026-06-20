-- Mirrors backend/migrations/015_enable_rls_parity_chat_sessions_parser_requests.sql
-- so the self-healing startup runner (backend/migrations/) also covers it.
ALTER TABLE public.parity_chat_sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "Users can view their own chat sessions" ON public.parity_chat_sessions;
CREATE POLICY "Users can view their own chat sessions"
  ON public.parity_chat_sessions FOR SELECT
  USING (user_id = (auth.uid())::text);

DROP POLICY IF EXISTS "Users can insert their own chat sessions" ON public.parity_chat_sessions;
CREATE POLICY "Users can insert their own chat sessions"
  ON public.parity_chat_sessions FOR INSERT
  WITH CHECK (user_id = (auth.uid())::text);

DROP POLICY IF EXISTS "Users can update their own chat sessions" ON public.parity_chat_sessions;
CREATE POLICY "Users can update their own chat sessions"
  ON public.parity_chat_sessions FOR UPDATE
  USING (user_id = (auth.uid())::text)
  WITH CHECK (user_id = (auth.uid())::text);

DROP POLICY IF EXISTS "Users can delete their own chat sessions" ON public.parity_chat_sessions;
CREATE POLICY "Users can delete their own chat sessions"
  ON public.parity_chat_sessions FOR DELETE
  USING (user_id = (auth.uid())::text);

ALTER TABLE public.parser_requests ENABLE ROW LEVEL SECURITY;
