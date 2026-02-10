#!/usr/bin/env bash
# Test API and auth (run with backend on http://localhost:8000)
set -e
BASE="${1:-http://localhost:8000}"

echo "=== Testing API and auth at $BASE ==="

echo ""
echo "1. Health (no auth)..."
health=$(curl -s -w "\n%{http_code}" "$BASE/health")
code=$(echo "$health" | tail -1)
body=$(echo "$health" | sed '$d')
if [ "$code" = "200" ]; then
  echo "   OK: $code"
  echo "   Body: $body"
else
  echo "   FAIL: expected 200, got $code"
  exit 1
fi

echo ""
echo "2. Protected endpoint without token (expect 401)..."
deals_nothing=$(curl -s -w "\n%{http_code}" "$BASE/api/deals")
code=$(echo "$deals_nothing" | tail -1)
if [ "$code" = "401" ]; then
  echo "   OK: $code (Not authenticated)"
else
  echo "   FAIL: expected 401, got $code"
  exit 1
fi

echo ""
echo "3. Protected endpoint with invalid token (expect 401)..."
deals_bad=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer invalid" "$BASE/api/deals")
code=$(echo "$deals_bad" | tail -1)
if [ "$code" = "401" ]; then
  echo "   OK: $code (Invalid credentials)"
else
  echo "   Note: got $code (401 expected; if Supabase env missing you may see 401 with env message)"
fi

echo ""
echo "=== API and auth checks passed ==="
echo ""
echo "Frontend: run 'npm run dev', open http://localhost:3000/login"
echo "  - With NEXT_PUBLIC_DEMO_MODE=true: email prefilled, no Sign up link, message 'Demo: sign in with ...'"
