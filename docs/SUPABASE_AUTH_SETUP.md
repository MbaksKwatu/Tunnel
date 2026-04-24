# Supabase Auth Email Redirect Setup

## Problem

When users register, Supabase sends an email confirmation link, but it points to `localhost:3000` instead of your production URL, causing "site can't be reached" errors.

## Solution

You need to configure Supabase to use your production URL. There are two places to fix this:

---

## 1. Supabase Dashboard Configuration (REQUIRED)

### Step 1: Add Production URL to Supabase

1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Go to **Authentication** → **URL Configuration**
4. Under **Redirect URLs**, add your production URL:
   ```
   https://your-vercel-app.vercel.app/auth/callback
   ```
   Or if you have a custom domain:
   ```
   https://yourdomain.com/auth/callback
   ```

5. Under **Site URL**, set your production URL:
   ```
   https://your-vercel-app.vercel.app
   ```

6. Click **Save**

### Step 2: Verify Email Templates

1. Go to **Authentication** → **Email Templates**
2. Check the **Confirm signup** template
3. Make sure it uses the correct redirect URL (should use `{{ .SiteURL }}` which will use your Site URL setting)

---

## 2. Code Configuration (Already Fixed)

The code has been updated to:
- Use `window.location.origin` in the browser (works for both localhost and production)
- Fall back to `NEXT_PUBLIC_SITE_URL` environment variable if needed
- Created `/app/auth/callback/page.tsx` to handle the callback

---

## 3. Environment Variable (Optional but Recommended)

Add to your Vercel environment variables:

```
NEXT_PUBLIC_SITE_URL=https://your-vercel-app.vercel.app
```

This ensures the redirect URL is correct even during server-side rendering.

---

## 4. Testing

### Local Testing:
1. Register a new user
2. Check email for confirmation link
3. Link should point to: `http://localhost:3000/auth/callback`
4. Click link → Should redirect to `/onboarding/thesis` or `/deals`

### Production Testing:
1. Deploy to Vercel
2. Register a new user
3. Check email for confirmation link
4. Link should point to: `https://your-vercel-app.vercel.app/auth/callback`
5. Click link → Should redirect to `/onboarding/thesis` or `/deals`

---

## Troubleshooting

### Issue: Link still points to localhost
**Solution**: 
- Check Supabase Dashboard → Authentication → URL Configuration
- Make sure Site URL is set to production URL
- Make sure Redirect URLs includes production callback URL

### Issue: "Invalid or expired link"
**Solution**:
- Links expire after 1 hour by default
- Register a new account to get a fresh link
- Or disable email confirmation in Supabase Dashboard (for testing only)

### Issue: Callback page shows error
**Solution**:
- Check browser console for errors
- Verify `/app/auth/callback/page.tsx` exists
- Check Supabase environment variables are set correctly

---

## Quick Fix Checklist

- [ ] Supabase Dashboard → Authentication → URL Configuration
  - [ ] Site URL = Production URL
  - [ ] Redirect URLs includes `/auth/callback` for production
- [ ] Vercel Environment Variables
  - [ ] `NEXT_PUBLIC_SITE_URL` = Production URL (optional)
- [ ] Code deployed with `/app/auth/callback/page.tsx`
- [ ] Test registration flow

---

**Last Updated**: February 9, 2026
