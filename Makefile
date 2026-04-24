# Parity v1 — Make targets
# For test-v1-live: set SUPABASE_TEST_MODE=1, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
# Example: make test-v1-live (requires env vars)
# Or: SUPABASE_TEST_MODE=1 SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... make test-v1-live

.PHONY: test-v1 test-v1-live install-backend

install-backend:
	pip install -r backend/requirements.txt

# Run v1 tests without Supabase (some tests will skip)
test-v1:
	python3 -m pytest backend/tests_v1/ -v --tb=short

# Run full v1 suite with live Supabase (0 skipped when creds configured)
# Requires: SUPABASE_TEST_MODE=1 SUPABASE_URL SUPABASE_SERVICE_ROLE_KEY
# Usage: SUPABASE_TEST_MODE=1 SUPABASE_URL=https://xxx.supabase.co SUPABASE_SERVICE_ROLE_KEY=eyJ... make test-v1-live
test-v1-live:
	@if [ -z "$$SUPABASE_URL" ] || [ -z "$$SUPABASE_SERVICE_ROLE_KEY" ]; then \
		echo "Error: SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set."; \
		echo "Usage: SUPABASE_TEST_MODE=1 SUPABASE_URL=... SUPABASE_SERVICE_ROLE_KEY=... make test-v1-live"; \
		exit 1; \
	fi
	@SUPABASE_TEST_MODE=1 python3 -m pytest backend/tests_v1/ -v --tb=short 2>&1 | tee pytest.log; \
	rc=$${PIPESTATUS[0]}; \
	grep -qE "[1-9][0-9]* skipped" pytest.log 2>/dev/null && { echo "Error: Expected 0 skipped. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY."; exit 1; }; \
	exit $$rc
