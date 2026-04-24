# Parity v1 OpenAPI Specification

**Spec file:** `v1.openapi.json` (OpenAPI 3.1.0)

## Validate locally

```bash
# Install jsonschema (already in requirements.txt)
pip install jsonschema

# Run contract validation tests
cd backend
python3 -m pytest tests_v1/test_openapi_contract.py -v

# Run full test suite
python3 -m pytest tests_v1/ -v
```

## Spec conventions

| Convention | Rule |
|---|---|
| Money | Integer cents (`_cents` suffix) |
| Ratios | Integer basis points (`_bp` suffix, 0–10000) |
| Timestamps | ISO 8601 strings |
| IDs | UUID v4 strings |
| Errors | Standardised `ErrorResponse` schema with `error_code`, `error_message`, `next_action`, `details` |
| Enums | Explicit: `ReconciliationStatusEnum`, `TierEnum`, `analysis_state_enum` (LIVE_DRAFT only in v1) |
