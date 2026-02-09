# Email Confirmation Troubleshooting Guide

## Your Configuration ✅

Based on your Supabase dashboard:
- **Site URL**: `https://v0-fund-iq-1-0-12fymqmtn-mbaks-projects.vercel.app` ✅
- **Redirect URL**: `https://v0-fund-iq-1-0-12fymqmtn-mbaks-projects.vercel.app/auth/callback` ✅

**Configuration looks correct!**

---

## Why You're Not Receiving Emails

### 1. Check Email Confirmation Settings

**In Supabase Dashboard:**
1. Go to **Authentication** → **Providers** → **Email**
2. Check **"Enable email confirmations"** toggle
   - If **OFF**: Users are auto-confirmed (no email sent)
   - If **ON**: Users must confirm email (email is sent)

**For Testing**: You can temporarily disable email confirmation to allow immediate signup.

---

### 2. Check Email Provider Status

**In Supabase Dashboard:**
1. Go to **Authentication** → **Email Templates**
2. Check if there are any warnings about email provider
3. Free tier uses Supabase's email service (limited to 3 emails/hour)

**Rate Limits:**
- Free tier: 3 emails per hour per user
- If you've sent multiple test emails, you may have hit the limit
- Wait 1 hour or upgrade to Pro plan

---

### 3. Check Spam/Junk Folder

- Supabase emails sometimes go to spam
- Check your spam/junk folder
- Add `noreply@mail.app.supabase.io` to your contacts/whitelist

---

### 4. Check Email Templates

**In Supabase Dashboard:**
1. Go to **Authentication** → **Email Templates**
2. Click on **"Confirm signup"** template
3. Verify the template is enabled and has correct content
4. Check that `{{ .ConfirmationURL }}` is in the template

---

### 5. Check Browser Console for Errors

When you sign up, check the browser console (F12):
- Look for any errors from Supabase
- Check if `signUp` returns an error
- Verify the response shows `user` but `session` is null (means email confirmation required)

---

### 6. Test Email Sending Directly

**In Supabase Dashboard:**
1. Go to **Authentication** → **Users**
2. Find your test user
3. Click **"Send magic link"** or **"Resend confirmation email"**
4. This tests if emails are working at all

---

## Quick Fixes

### Option 1: Disable Email Confirmation (For Testing)

**In Supabase Dashboard:**
1. Go to **Authentication** → **Providers** → **Email**
2. Toggle **"Enable email confirmations"** to **OFF**
3. Users will be auto-confirmed immediately
4. **Note**: Re-enable for production!

### Option 2: Use Magic Link Instead

Magic links might work better than password signup:
1. In Login component, add magic link option
2. Magic links are more reliable for email delivery

### Option 3: Check User Status

**In Supabase Dashboard:**
1. Go to **Authentication** → **Users**
2. Find your test user
3. Check **"Email Confirmed"** status
4. If already confirmed, email won't be sent again

---

## Expected Behavior

### When Email Confirmation is ENABLED:
1. User signs up → `signUp()` returns success
2. User receives email with confirmation link
3. User clicks link → Redirected to `/auth/callback`
4. Callback verifies session → Redirects to `/onboarding/thesis` or `/deals`

### When Email Confirmation is DISABLED:
1. User signs up → `signUp()` returns success
2. User is immediately signed in
3. Redirected to `/onboarding/thesis` or `/deals`
4. No email sent

---

## Code Check

Your code should handle both cases:

```typescript
const { data, error } = await supabase.auth.signUp({
  email,
  password,
  options: {
    emailRedirectTo: redirectUrl,
  }
})

// If email confirmation is disabled:
// - data.user exists
// - data.session exists (user is signed in)

// If email confirmation is enabled:
// - data.user exists
// - data.session is null (user needs to confirm email)
```

---

## Verification Steps

1. ✅ **Supabase URL Configuration** - Correctly set
2. ⚠️ **Email Confirmation Toggle** - Check if enabled
3. ⚠️ **Email Rate Limits** - Check if limit reached
4. ⚠️ **Spam Folder** - Check spam/junk
5. ⚠️ **Email Templates** - Verify template is enabled
6. ⚠️ **User Status** - Check if already confirmed

---

## Next Steps

1. **Check Email Confirmation Setting**:
   - Go to Authentication → Providers → Email
   - Verify "Enable email confirmations" is ON (if you want emails)

2. **Check User Status**:
   - Go to Authentication → Users
   - Find your test user
   - Check if email is already confirmed

3. **Try Resending**:
   - In Users list, click on your user
   - Click "Resend confirmation email"

4. **Check Email Provider**:
   - Free tier has limits
   - Consider upgrading if you need more emails

---

**Most Common Issue**: Email confirmation is disabled, so no email is sent and users are auto-confirmed.

**Second Most Common**: Email went to spam folder.

**Third Most Common**: Rate limit reached (3 emails/hour on free tier).
