# Vercel Environment Variables Setup

## Required Environment Variables

For Vercel deployment to succeed, you **must** set these environment variables in your Vercel project settings:

### Supabase (Required)

1. **NEXT_PUBLIC_SUPABASE_URL**
   - Get from: https://supabase.com/dashboard/project/_/settings/api
   - Example: `https://xxxxx.supabase.co`

2. **NEXT_PUBLIC_SUPABASE_ANON_KEY**
   - Get from: https://supabase.com/dashboard/project/_/settings/api
   - This is the "anon" or "public" key (not the service role key)

### Backend API (Required)

3. **NEXT_PUBLIC_API_URL**
   - Your Render backend URL
   - Example: `https://paritytunnel-w7d2.onrender.com`

---

## How to Set Environment Variables in Vercel

1. Go to: https://vercel.com/dashboard
2. Select your project
3. Go to **Settings** → **Environment Variables**
4. Add each variable:
   - **Key**: `NEXT_PUBLIC_SUPABASE_URL`
   - **Value**: Your Supabase project URL
   - **Environment**: Production, Preview, Development (select all)
5. Repeat for all 3 variables
6. **Redeploy** your project (or push a new commit to trigger auto-deploy)

---

## Why Build Fails Without These

Next.js tries to statically generate pages at build time. If Supabase env vars are missing:
- Build fails with: `"Your project's URL and API key are required"`
- Pages can't be pre-rendered
- Deployment stops

---

## After Setting Env Vars

1. Push a new commit OR
2. Go to Vercel dashboard → Deployments → Click "Redeploy" on latest deployment
3. Build should succeed ✅

---

## Verification

After deployment succeeds, check:
- ✅ Build logs show no Supabase errors
- ✅ Pages load correctly
- ✅ Authentication works
