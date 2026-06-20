-- Migration 015: enable RLS on parity_chat_sessions and parser_requests
-- Both tables were created without RLS and are exposed via PostgREST to
-- anon/authenticated roles (Supabase security advisor ERROR findings).
-- parser_requests additionally has no per-user owner column — it's an
-- internal request log written only by the backend and admin app, both of
-- which use the service-role key (which always bypasses RLS), so enabling
-- RLS with zero public policies fully locks it down without breaking either
-- caller. parity_chat_sessions does have a real owner column (user_id, the
-- Supabase auth JWT "sub") and is scoped to it below.
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
