# Password Reset Guide

## ⚠️ Important: Passwords Cannot Be Viewed

**Passwords are stored as hashed values** in Supabase for security. They cannot be viewed or retrieved, only reset.

---

## Option 1: Use "Forgot Password" Feature (Recommended)

### In Your App:
1. Go to `/login` page
2. Click **"Forgot password?"** link (below password field)
3. Enter your email address
4. Click **"Send Reset Link"**
5. Check your email for password reset link
6. Click the link → Redirected to `/auth/reset-password`
7. Enter new password → Password updated

**This is the recommended way!**

---

## Option 2: Reset Password in Supabase Dashboard

### Steps:
1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Go to **Authentication** → **Users**
4. Find your user by email
5. Click on the user
6. Click **"Send password reset email"** button
7. Check your email for reset link
8. Click link → Set new password

---

## Option 3: Manually Set Password (Admin)

### Steps:
1. Go to [Supabase Dashboard](https://app.supabase.com)
2. Select your project
3. Go to **Authentication** → **Users**
4. Find your user by email
5. Click on the user
6. Scroll to **"Update User"** section
7. Enter new password in **"Password"** field
8. Click **"Update User"**

**Note**: This bypasses email verification and immediately sets the password.

---

## Troubleshooting

### Issue: "Forgot Password" link not working
**Solution**: 
- Make sure `/app/auth/reset-password/page.tsx` exists (we just created it)
- Check Supabase URL Configuration includes reset password redirect URL
- Add `https://your-vercel-app.vercel.app/auth/reset-password` to Redirect URLs in Supabase

### Issue: Reset link expired
**Solution**: 
- Links expire after 1 hour
- Request a new reset link
- Or use Option 3 (manual reset in dashboard)

### Issue: Not receiving reset email
**Solution**:
- Check spam folder
- Check email rate limits (3/hour on free tier)
- Verify email address is correct
- Use Option 3 (manual reset) as alternative

---

## Supabase Redirect URL Configuration

Make sure your Supabase dashboard has these redirect URLs:

1. **Site URL**: `https://your-vercel-app.vercel.app`
2. **Redirect URLs**:
   - `https://your-vercel-app.vercel.app/auth/callback` (for email confirmation)
   - `https://your-vercel-app.vercel.app/auth/reset-password` (for password reset)

---

## Quick Reference

| Method | When to Use | Steps |
|--------|-------------|-------|
| **Forgot Password** | Normal user flow | Click "Forgot password?" → Enter email → Check email → Reset |
| **Dashboard Reset Email** | Admin helping user | Dashboard → Users → Send reset email |
| **Manual Reset** | Urgent/Testing | Dashboard → Users → Update password directly |

---

**Remember**: Passwords are hashed and cannot be viewed. You can only reset them!
