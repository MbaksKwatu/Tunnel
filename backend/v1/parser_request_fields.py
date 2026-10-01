"""
Pure field-building helpers for `pds_parser_requests` writes (migration 046).

Kept free of Supabase/FastAPI so the vocabulary rules are unit-testable:
  * status is never written as 'pending' any more -- "a person submitted
    details" is recorded in submitted_at instead (migration 046 folds the old
    value; the CHECK constraint only allows new/in_progress/testing/resolved).
  * contact_email is filled once and never overwritten by a fallback: a
    value the client typed always wins over an account-derived one.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

ContactLookup = Callable[[str], Optional[str]]


def _clean(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_enrich_fields(
    existing: Dict[str, Any],
    body: Dict[str, Any],
    verified_user_id: Optional[str],
    contact_lookup: ContactLookup,
) -> Dict[str, Any]:
    """Fields to update on an auto-created row when the deal-page modal is
    submitted. Never touches status."""
    fields: Dict[str, Any] = {}
    for key in ("bank_name", "country", "account_type", "notes"):
        value = _clean(body.get(key))
        if value:
            fields[key] = value

    if not existing.get("submitted_at"):
        fields["submitted_at"] = _now_iso()

    # Backfill attribution for rows auto-created without a verified caller in
    # scope (e.g. background ingestion). Never overwrites an already-attributed
    # row, and never trusts a client-supplied id.
    owner = existing.get("created_by")
    if not owner and verified_user_id:
        fields["created_by"] = verified_user_id
        owner = verified_user_id

    if not existing.get("contact_email"):
        email = _clean(body.get("contact_email"))
        if not email and owner:
            email = contact_lookup(owner)
        if email:
            fields["contact_email"] = email

    return fields


def build_partner_api_row(
    body: Dict[str, Any],
    verified_user_id: Optional[str],
    contact_lookup: ContactLookup,
) -> Dict[str, Any]:
    """`pds_parser_requests` row for the backend POST /v1/api/request-parser
    route (GBFund's audited-financials failure path). Previously written to
    `parser_requests`, which has no admin status control and no file storage.

    pds_parser_requests has no partner/market/document_url columns, so those
    are carried in `notes` rather than dropped."""
    partner = _clean(body.get("partner")) or "gbfund"
    note_lines = [f"Partner: {partner}"]
    document_url = _clean(body.get("document_url"))
    if document_url:
        note_lines.append(f"Document URL: {document_url}")
    extra = _clean(body.get("notes"))
    if extra:
        note_lines.append(extra)

    row: Dict[str, Any] = {
        "bank_name": _clean(body.get("bank_name")),
        "country": _clean(body.get("market")) or _clean(body.get("country")),
        "deal_id": _clean(body.get("deal_id")),
        "document_id": _clean(body.get("document_id")),
        "error_type": "AuditedFinancialsParseFailed",
        "error_message": _clean(body.get("error_message")) or "Audited financials parse failed",
        "notes": "\n".join(note_lines),
        "status": "new",
        "submitted_at": _now_iso(),
    }
    if verified_user_id:
        row["created_by"] = verified_user_id

    email = _clean(body.get("contact_email"))
    if not email and verified_user_id:
        email = contact_lookup(verified_user_id)
    if email:
        row["contact_email"] = email

    return {k: v for k, v in row.items() if v is not None}
