# Render Environment Variables Setup

## Required Environment Variables

For Render backend deployment to succeed, you **must** set these environment variables in your Render service settings:

### Supabase (Required)

1. **SUPABASE_URL**
   - Get from: https://supabase.com/dashboard/project/_/settings/api
   - Example: `https://xxxxx.supabase.co`

2. **SUPABASE_SERVICE_ROLE_KEY**
   - Get from: https://supabase.com/dashboard/project/_/settings/api
   - This is the **service_role** key (not the anon key)
   - ⚠️ Keep this secret - it has admin access

### OpenAI (Required for Ask Parity)

3. **OPENAI_API_KEY**
   - Your OpenAI API key
   - Example: `sk-proj-...`

### Python (Optional)

4. **PYTHON_VERSION**
   - Already set in `render.yaml` as `3.11.6`
   - Only override if needed

---

## How to Set Environment Variables in Render

1. Go to: https://dashboard.render.com
2. Select your **parity-backend** service
3. Go to **Environment** tab
4. Click **Add Environment Variable**
5. Add each variable:
   - **Key**: `SUPABASE_URL`
   - **Value**: Your Supabase project URL
6. Repeat for all variables
7. **Manual Deploy** or wait for next git push (auto-deploy)

---

## Why Backend Fails Without These

The backend tries to initialize Supabase storage at startup:
- If `SUPABASE_URL` or `SUPABASE_SERVICE_ROLE_KEY` are missing:
  - Backend crashes on startup
  - Health checks fail
  - Service shows as "unhealthy"

---

## After Setting Env Vars

1. Render will auto-restart the service
2. Check **Logs** tab for:
   - ✅ `Storage initialized: SupabaseStorage`
   - ✅ `Application startup complete`
3. Test health endpoint: `GET https://your-render-url.onrender.com/health`

---

## Verification

After deployment succeeds, check:
- ✅ `/health` endpoint returns 200
- ✅ `/health/db` endpoint returns 200
- ✅ Logs show "Storage initialized"
- ✅ No startup errors

---

## Troubleshooting

**Backend still failing?**
- Check Render logs for specific error messages
- Verify env var names match exactly (case-sensitive)
- Ensure service_role key (not anon key) is used
- Check Supabase project is active and accessible
