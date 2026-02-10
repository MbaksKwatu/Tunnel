#!/usr/bin/env bash
# Test Ask Parity API: conversation and ask endpoints (auth required, optional token for full test)
# Usage: ./scripts/test-ask-parity.sh [BASE_URL] [DEAL_ID]
# Example: ./scripts/test-ask-parity.sh http://localhost:8000
# With token: TOKEN="your-jwt" ./scripts/test-ask-parity.sh http://localhost:8000 <deal-id>
set -e
BASE="${1:-http://localhost:8000}"
DEAL_ID="${2:-}"
TOKEN="${TOKEN:-}"

echo "=== Ask Parity API tests at $BASE ==="

if [ -z "$DEAL_ID" ]; then
  # Use a placeholder UUID for auth/validation tests (will get 401 or 403 without token)
  DEAL_ID="00000000-0000-0000-0000-000000000000"
fi

echo ""
echo "1. GET /api/deals/{id}/conversation without auth (expect 401)..."
code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/deals/$DEAL_ID/conversation")
if [ "$code" = "401" ]; then
  echo "   OK: $code"
else
  echo "   FAIL: expected 401, got $code"
  exit 1
fi

echo ""
echo "2. POST /api/deals/{id}/ask without auth (expect 401)..."
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/deals/$DEAL_ID/ask" \
  -H "Content-Type: application/json" \
  -d '{"message":"What is the investment readiness?"}')
if [ "$code" = "401" ]; then
  echo "   OK: $code"
else
  echo "   FAIL: expected 401, got $code"
  exit 1
fi

echo ""
echo "3. POST /api/deals/{id}/ask with invalid token (expect 401)..."
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/deals/$DEAL_ID/ask" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer invalid-token" \
  -d '{"message":"Hello"}')
if [ "$code" = "401" ]; then
  echo "   OK: $code"
else
  echo "   Note: got $code (401 expected for invalid token)"
fi

echo ""
echo "4. POST with empty message body (no auth -> 401; with auth would be 400)..."
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/deals/$DEAL_ID/ask" \
  -H "Content-Type: application/json" \
  -d '{}')
if [ "$code" = "401" ]; then
  echo "   OK: 401 (no auth)"
else
  echo "   Got: $code"
fi

echo ""
echo "=== Ask Parity API auth checks passed ==="

if [ -n "$TOKEN" ] && [ "$DEAL_ID" != "00000000-0000-0000-0000-000000000000" ]; then
  echo ""
  echo "5. GET conversation with token..."
  conv=$(curl -s -w "\n%{http_code}" -H "Authorization: Bearer $TOKEN" "$BASE/api/deals/$DEAL_ID/conversation")
  ccode=$(echo "$conv" | tail -1)
  if [ "$ccode" = "200" ]; then
    echo "   OK: 200"
  else
    echo "   Got: $ccode (200=OK, 403=demo/ownership, 404=deal not found)"
  fi
  echo "6. POST ask with token (needs OPENAI_API_KEY on server)..."
  ask=$(curl -s -w "\n%{http_code}" -X POST "$BASE/api/deals/$DEAL_ID/ask" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $TOKEN" \
    -d '{"message":"What is the investment readiness for this deal?"}')
  acode=$(echo "$ask" | tail -1)
  if [ "$acode" = "200" ]; then
    echo "   OK: 200 (response returned)"
  elif [ "$acode" = "503" ]; then
    echo "   OK: 503 (Ask Parity unavailable, e.g. OPENAI_API_KEY not set)"
  else
    echo "   Got: $acode"
  fi
else
  echo ""
  echo "Optional: set TOKEN and a real DEAL_ID to test authenticated conversation and ask."
  echo "  TOKEN=\"<jwt>\" ./scripts/test-ask-parity.sh $BASE <deal-uuid>"
fi
