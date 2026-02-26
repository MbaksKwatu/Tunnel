# Parity v1 API Smoke (Manual)

## Prereqs
- Backend running with `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY`.
- `NEXT_PUBLIC_API_URL` set for frontend (or use `http://localhost:8000`).

## Smoke Steps
1) Create deal
```
curl -X POST "$API/v1/deals" -F currency=USD -F name="Demo Deal" -F created_by="user-1"
```
2) Upload document (XLSX/CSV/PDF)
```
curl -X POST "$API/v1/deals/<deal_id>/documents" \
  -F file=@sample.xlsx
```
- Expect 400 with `CURRENCY_MISMATCH` if ISO conflict.
- Expect 400 with `INVALID_SCHEMA: ...` if schema invalid.

3) Add override (optional)
```
curl -X POST "$API/v1/deals/<deal_id>/overrides" \
  -F entity_id="entity-id" -F weight=1.0 -F new_value="revenue_operational" -F created_by="user-1"
```
4) Export snapshot
```
curl -X POST "$API/v1/deals/<deal_id>/export"
```
- Idempotent: repeated call with same data returns existing snapshot.

5) Fetch deal state
```
curl "$API/v1/deals/<deal_id>"
```
- Verify analysis_runs entries and snapshot list.

## Determinism checks (manual)
- Upload same file twice → raw_transaction_hash identical.
- Export twice without changes → same snapshot hash/id.
- Add override then export → new snapshot hash.
- Attempt to update/delete snapshot or override → should fail at DB (immutable).
