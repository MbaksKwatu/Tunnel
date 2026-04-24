# Frontend Split for Parity v1

## Goals
- Keep legacy UI reachable under `/legacy/*` with a clear banner: “Legacy Decision-Support Mode (Deprecated)”.
- Build new minimal v1 surfaces under `/v1/deals` and `/v1/deals/[deal_id]` that show deterministic, non-narrative state.

## Legacy Scope
- Move/route all existing judgment/anomaly/LLM/report features under `/legacy/*`.
- Add banner on legacy pages indicating deprecation and separation from v1 deterministic flows.
- Do not delete legacy code in this phase; only isolate routing/visibility.

## v1 Minimal UI Requirements
- Deal list `/v1/deals`:
  - Columns: deal_name, currency, state (LIVE_DRAFT/SNAPSHOT), final_confidence_pct, tier, snapshot_id (if any).
- Deal detail `/v1/deals/[deal_id]`:
  - Show coverage_pct, reconciliation status and pct, missing_month_count, override count, final_confidence_pct, tier, tier_cap_applied flag.
  - Export snapshot button (calls POST /v1/deals/{deal_id}/export).
- No narratives, no scoring language, no charts. Text-only deterministic fields.

## Navigation/Behavior
- Default landing should go to v1 deals list (once implemented).
- Legacy menu item should be visibly marked as deprecated/legacy.

## Next Steps (later phases)
- Implement routing split in Next.js (app router) and add banners.
- Wire v1 screens to new deterministic APIs once pipeline is ready.
