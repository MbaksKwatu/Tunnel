# Parity v1 — API Contract

**Version:** 1.0.0
**Schema version:** v1
**Config version:** v1

---

## Core Invariants

| Rule | Description |
|------|-------------|
| **Integer money** | All monetary values are stored and transmitted as integer cents (`_cents` suffix). No floats. |
| **Basis points** | All ratios/percentages are integer basis points (`_bp` suffix, range 0–10000). |
| **Deterministic** | Given the same input transactions, the pipeline always produces the same hashes, confidence, and tier. |
| **Immutable snapshots** | Once created, a snapshot's `canonical_json` and `sha256_hash` can never change. DB triggers enforce this. |
| **Explicit export** | Snapshots are only created when `POST /v1/deals/{deal_id}/export` is called. |
| **Idempotent export** | If the underlying data hasn't changed, re-exporting returns the same snapshot (matched by `sha256_hash`). |
| **No AI/LLM** | v1 is purely deterministic. No scoring models, no narratives, no AI. |

---

## LIVE_DRAFT vs SNAPSHOT

| Concept | Description |
|---------|-------------|
| **LIVE_DRAFT** | The current mutable state of an analysis. Changes whenever you upload documents or add overrides. Not persisted as an immutable artifact. |
| **SNAPSHOT** | An immutable, hash-locked artifact created on explicit export. Contains the canonical JSON representation of all pipeline outputs. Cannot be updated or deleted (enforced at the database level). |

**Workflow:**
1. Create deal → upload documents → overrides (optional)
2. Call `POST /v1/deals/{deal_id}/export` → creates LIVE_DRAFT analysis run + immutable SNAPSHOT
3. Add more overrides → re-export → new analysis run + new SNAPSHOT (old one preserved)

---

## Field Glossary

### Money fields (integer cents)

| Field | Description |
|-------|-------------|
| `signed_amount_cents` | Transaction amount in minor currency units. Positive = inflow, negative = outflow. |
| `abs_amount_cents` | Absolute value of `signed_amount_cents`. DB-generated column. |
| `non_transfer_abs_total_cents` | Sum of `abs(signed_amount_cents)` for all non-transfer transactions. |
| `classified_abs_total_cents` | Sum of `abs(signed_amount_cents)` for classified non-transfer transactions. |

### Ratio fields (integer basis points, 0–10000)

| Field | Description |
|-------|-------------|
| `coverage_pct_bp` | `classified_abs_total / non_transfer_abs_total × 10000`, floored. |
| `missing_month_penalty_bp` | `min(missing_month_count × 1000, 5000)`. |
| `override_penalty_bp` | Weighted penalty from overrides, capped at 7000. |
| `reconciliation_pct_bp` | Reconciliation accuracy vs accrual revenue, if applicable. |
| `base_confidence_bp` | `min(coverage_bp, reconciliation_bp)` or just `coverage_bp` if recon not run. |
| `final_confidence_bp` | `max(0, base_after_months_bp - override_penalty_bp)`. |

### Reconciliation Status

| Value | Meaning |
|-------|---------|
| `NOT_RUN` | No accrual data provided, or zero revenue. |
| `OK` | Accrual comparison successful. |
| `FAILED_OVERLAP` | Transaction date range overlaps less than 60% with accrual period. |

### Tier

| Value | Range |
|-------|-------|
| `Low` | final_confidence_bp < 7000 |
| `Medium` | 7000 ≤ final_confidence_bp < 8500 |
| `High` | final_confidence_bp ≥ 8500 |

**Tier cap rule:** If reconciliation_status ≠ OK and computed tier = High, it is capped to Medium (`tier_capped = true`).

---

## Error Response Schema

All errors return a JSON body with this structure:

```json
{
  "error_code": "NOT_FOUND",
  "error_message": "Deal abc-123 not found",
  "next_action": null,
  "details": {}
}
```

| Code | HTTP Status | Description |
|------|-------------|-------------|
| `CURRENCY_MISMATCH` | 409 | Document contains a different currency than the deal. |
| `INVALID_SCHEMA` | 400 | File is missing required columns or has unparseable data. |
| `NOT_FOUND` | 404 | Resource does not exist. |
| `BAD_REQUEST` | 400 | Missing required parameters or no data to export. |
| `UNAUTHORIZED` | 401 | Authentication required (future). |
| `INTERNAL` | 500 | Unexpected server error. |
| `SERVICE_UNAVAILABLE` | 503 | Database or storage not reachable. |

---

## Endpoint Summary

| Method | Path | Description |
|--------|------|-------------|
| POST | `/v1/deals` | Create a deal |
| GET | `/v1/deals` | List deals (requires `created_by`) |
| GET | `/v1/deals/{deal_id}` | Get deal + runs + snapshots |
| POST | `/v1/deals/{deal_id}/documents` | Upload financial document |
| GET | `/v1/deals/{deal_id}/documents` | List documents |
| GET | `/v1/documents/{document_id}/status` | Document processing status |
| GET | `/v1/documents/{document_id}/transactions` | Raw transactions for document |
| POST | `/v1/deals/{deal_id}/overrides` | Add override (insert-only) |
| GET | `/v1/deals/{deal_id}/overrides` | List overrides |
| GET | `/v1/deals/{deal_id}/analysis/latest` | Latest LIVE_DRAFT analysis |
| POST | `/v1/deals/{deal_id}/export` | Run pipeline + create snapshot |
| GET | `/v1/deals/{deal_id}/snapshots` | List snapshots |
| GET | `/v1/snapshots/{snapshot_id}` | Get single snapshot |

---

## Version Policy

- Any breaking change to the pipeline logic, hash algorithm, or schema requires a `schema_version` bump.
- Any change to deterministic constants (e.g., penalty weights) requires a `config_version` bump.
- The `config_version` is included in the snapshot payload, so changing it will change the snapshot hash.
