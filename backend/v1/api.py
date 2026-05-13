"""
Parity v1 — Deterministic API
All money fields: integer cents.  All ratios: integer basis points.
Snapshot only on explicit POST /v1/deals/{deal_id}/export.
"""

import base64
import csv
import io
import json
import logging
import time
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request, BackgroundTasks, Body
from fastapi.responses import StreamingResponse
from pypdf import PdfWriter

from .utils.pdf_merge import validate_pdf_count

logger = logging.getLogger(__name__)
from datetime import datetime, timezone

from .config import SCHEMA_VERSION, CONFIG_VERSION, GIT_COMMIT, BUILD_TIMESTAMP, DETERMINISTIC_MODE, MAX_PDF_FILES, MAX_BATCH_UPLOADS
from .ingestion.service import IngestionService
from .parsing.errors import CurrencyMismatchError, InvalidSchemaError
from .core.pipeline import run_pipeline
from .core.snapshot_engine import build_pds_payload, export_snapshot, decompress_canonical_json_if_needed
from .core.pdf_generator import generate_pdf as _generate_snapshot_pdf
from .flags import seed_default_flags as _seed_default_flags

router = APIRouter(prefix="/v1", tags=["v1"])

# ---------------------------------------------------------------------------
# System identity (deterministic, no DB, no runtime state)
# ---------------------------------------------------------------------------

_HEALTH_RESPONSE = {
    "schema_version": SCHEMA_VERSION,
    "config_version": CONFIG_VERSION,
    "git_commit": GIT_COMMIT,
    "build_timestamp": BUILD_TIMESTAMP,
    "deterministic_mode": DETERMINISTIC_MODE,
}

_METRICS_TEMPLATE = {
    "schema_version": SCHEMA_VERSION,
    "config_version": CONFIG_VERSION,
    "last_export_ms": None,
    "last_export_at": None,
}

# Read-only lease: if status stays "processing" longer than this, status endpoint reports failed.
PROCESSING_LEASE_SECONDS = 600


def _document_processing_lease_expired(doc: Dict[str, Any]) -> bool:
    """True if the row is still ``processing`` but older than :data:`PROCESSING_LEASE_SECONDS`."""
    if doc.get("status") != "processing":
        return False
    lease_ref = doc.get("updated_at") or doc.get("created_at")
    ref_dt = _parse_document_timestamp(lease_ref)
    if ref_dt is None:
        return False
    age_s = (datetime.now(timezone.utc) - ref_dt).total_seconds()
    return age_s > PROCESSING_LEASE_SECONDS


def _document_row_for_list_response(doc: Dict[str, Any]) -> Dict[str, Any]:
    """
    Align list payload with GET /documents/{{id}}/status: stale processing rows surface as failed
    so clients polling list_documents can unblock (previously only status had lease semantics).
    """
    if not _document_processing_lease_expired(doc):
        return doc
    out = dict(doc)
    out["status"] = "failed"
    out["error_type"] = "ProcessingTimeout"
    out["error_message"] = (
        f"Document remained in processing for more than {PROCESSING_LEASE_SECONDS} seconds"
    )
    out["error_stage"] = "PROCESSING"
    out["next_action"] = "retry_or_contact_support"
    return out


def _document_blocks_export(doc: Dict[str, Any]) -> bool:
    """
    True if this row should block POST /export.

    - ``completed``: does not block.
    - ``failed``: does not block (export uses ingested transactions; failed uploads add no rows).
    - ``processing`` past lease: does not block (stale row; same idea as list/status overlay).
    - ``processing`` within lease: blocks.
    """
    s = (doc.get("status") or "").strip().lower()
    if s == "completed":
        return False
    if s == "failed":
        return False
    if s == "processing":
        return not _document_processing_lease_expired(doc)
    return True


def _parse_document_timestamp(value: Any) -> Optional[datetime]:
    """Parse created_at / updated_at from DB (ISO string or datetime). Returns timezone-aware UTC."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    s = str(value).strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


@router.get("/system/health")
def system_health():
    return _HEALTH_RESPONSE


@router.get("/system/metrics")
def system_metrics(request: Request):
    last_ms = getattr(request.app.state, "last_export_ms", None) if request else None
    last_at = getattr(request.app.state, "last_export_at", None) if request else None
    return {
        "schema_version": SCHEMA_VERSION,
        "config_version": CONFIG_VERSION,
        "last_export_ms": last_ms,
        "last_export_at": last_at,
    }


# ---------------------------------------------------------------------------
# Standardised error response
# ---------------------------------------------------------------------------

_ERROR_CODES = {
    "CURRENCY_MISMATCH": 409,
    "INVALID_SCHEMA": 400,
    "DOCUMENTS_NOT_READY": 409,
    "NOT_FOUND": 404,
    "BAD_REQUEST": 400,
    "UNAUTHORIZED": 401,
    "INTERNAL": 500,
    "SERVICE_UNAVAILABLE": 503,
}


def _error(code: str, message: str, *, status: int = 0, next_action: Optional[str] = None, details: Optional[Dict] = None):
    status = status or _ERROR_CODES.get(code, 500)
    raise HTTPException(
        status_code=status,
        detail={
            "error_code": code,
            "error_message": message,
            "next_action": next_action,
            "details": details or {},
        },
    )


# ---------------------------------------------------------------------------
# Repository provider — overridable for tests via app.state
# ---------------------------------------------------------------------------

def _merge_pdf_bytes_parts(parts: List[bytes]) -> bytes:
    """Merge PDF byte blobs in order (upload order)."""
    writer = PdfWriter()
    for blob in parts:
        writer.append(io.BytesIO(blob))
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _repos(request: Optional[Request] = None) -> Dict[str, Any]:
    if request and hasattr(request.app.state, "repos_factory"):
        return request.app.state.repos_factory()
    from .db.supabase_repositories import (
        DealsRepo, DocumentsRepo, RawTxRepo, TransferLinksRepo,
        EntitiesRepo, TxnEntityMapRepo, OverridesRepo,
        AnalysisRunsRepo, SnapshotsRepo,
        EnrichmentsRepo, ClassificationOverridesRepo, CustomFlagsRepo,
        AccountCoverageRepo, OverrideLogRepo, IntelligenceLogRepo,
    )
    return {
        "deals": DealsRepo(),
        "documents": DocumentsRepo(),
        "raw": RawTxRepo(),
        "links": TransferLinksRepo(),
        "entities": EntitiesRepo(),
        "txn_map": TxnEntityMapRepo(),
        "overrides": OverridesRepo(),
        "override_log": OverrideLogRepo(),
        "intelligence_log": IntelligenceLogRepo(),
        "runs": AnalysisRunsRepo(),
        "snapshots": SnapshotsRepo(),
        "enrichments": EnrichmentsRepo(),
        "cls_overrides": ClassificationOverridesRepo(),
        "custom_flags": CustomFlagsRepo(),
        "account_coverage": AccountCoverageRepo(),
    }


# ===================================================================
# Deals
# ===================================================================

def _extract_user_id_from_request(request: Request) -> Optional[str]:
    """Decode the Supabase JWT from Authorization header to get the user sub."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return None
    token = auth_header[7:]
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        padding = "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(parts[1] + padding))
        return payload.get("sub")
    except Exception:
        return None


@router.post("/deals")
def create_deal(
    request: Request,
    currency: str = Form(...),
    name: Optional[str] = Form(None),
    created_by: Optional[str] = Form(None),
    company_name: Optional[str] = Form(None),
    analyst_initials: Optional[str] = Form(None),
    accrual_revenue_cents: Optional[str] = Form(None),
    accrual_period_start: Optional[str] = Form(None),
    accrual_period_end: Optional[str] = Form(None),
):
    repos = _repos(request)
    user_id = _extract_user_id_from_request(request)
    deal = {
        "id": str(uuid.uuid4()),
        "currency": currency.upper(),
        "name": name,
        "created_by": created_by or user_id or str(uuid.uuid4()),
        "user_id": user_id,
    }
    if company_name and company_name.strip():
        deal["company_name"] = company_name.strip()
    if analyst_initials and analyst_initials.strip():
        deal["analyst_initials"] = analyst_initials.strip()[:3].upper()
    if accrual_revenue_cents is not None and accrual_revenue_cents.strip():
        try:
            deal["accrual_revenue_cents"] = int(accrual_revenue_cents)
        except ValueError:
            pass
    if accrual_period_start is not None and accrual_period_start.strip():
        deal["accrual_period_start"] = accrual_period_start.strip()
    if accrual_period_end is not None and accrual_period_end.strip():
        deal["accrual_period_end"] = accrual_period_end.strip()
    return {"deal": repos["deals"].create_deal(deal)}


@router.get("/deals")
def list_deals(request: Request, created_by: Optional[str] = None):
    repos = _repos(request)
    if not created_by:
        _error("BAD_REQUEST", "created_by query parameter is required")
    return {"deals": repos["deals"].list_deals(created_by)}


@router.get("/deals/{deal_id}")
def get_deal(request: Request, deal_id: str):
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    runs = repos["runs"].list_runs(deal_id)
    snaps = repos["snapshots"].list_snapshots(deal_id)
    return {"deal": deal, "analysis_runs": runs, "snapshots": snaps}


# ===================================================================
# Documents / Ingestion
# ===================================================================

@router.post("/deals/{deal_id}/documents")
async def upload_document(
    request: Request,
    deal_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    created_by: Optional[str] = Form(None),
):
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    content = await file.read()
    document_id = str(uuid.uuid4())
    fname = file.filename or "upload.csv"
    ext = ("." + fname.rsplit(".", 1)[-1].lower()) if "." in fname else ".csv"
    ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".pdf"}
    if ext not in ALLOWED_EXTENSIONS:
        _error("BAD_REQUEST", f"Unsupported file type '{ext}'. Accepted: .csv, .xlsx, .pdf")
    file_type = ext.lstrip(".")
    created_by_val = created_by or deal.get("created_by") or str(uuid.uuid4())

    document = {
        "id": document_id,
        "deal_id": deal_id,
        "storage_url": f"inline://{fname}",
        "file_type": file_type.lower(),
        "status": "processing",
        "currency_detected": None,
        "currency_mismatch": False,
        "created_by": created_by_val,
    }
    repos["documents"].create_document(document)

    ingestion = IngestionService(
        documents_repo=repos["documents"],
        raw_tx_repo=repos["raw"],
        analysis_repo=repos["runs"],
    )
    # CSV: local parse. PDF/XLSX: parity-ingestion (XLSX uses POST .../v1/ingest/excel — no openpyxl on this worker).
    background_tasks.add_task(
        ingestion.process_document_background,
        document_id=document_id,
        deal_id=deal_id,
        created_by=created_by_val,
        file_bytes=content,
        file_name=file.filename,
        file_type=file_type,
        deal_currency=deal["currency"],
    )

    return {"ingestion": {"document_id": document_id, "status": "processing", "rows_count": 0}}


@router.post(
    "/deals/{deal_id}/documents/batch",
    summary="Upload multiple PDFs at once (batch upload)",
    description=(
        "Upload 2–3 PDFs; they are merged in upload order and processed as one document. "
        "Limit: 4 batch uploads per deal (tracked via batch_number)."
    ),
)
async def upload_documents_batch(
    request: Request,
    deal_id: str,
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(..., description="2–3 PDF files to merge"),
    created_by: Optional[str] = Form(None),
):
    """
    Batch upload: merge multiple PDFs in memory, one document row, background ingest.
    """
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    try:
        validate_pdf_count(len(files), max_files=MAX_PDF_FILES)
    except ValueError as exc:
        _error("BAD_REQUEST", str(exc))

    if len(files) < 2:
        _error("BAD_REQUEST", "Minimum 2 files required for batch upload")

    docs_repo = repos["documents"]
    batch_count_fn = getattr(docs_repo, "get_batch_upload_count", None)
    batch_count = batch_count_fn(deal_id) if batch_count_fn else 0

    if batch_count >= MAX_BATCH_UPLOADS:
        raise HTTPException(
            status_code=403,
            detail={
                "error_code": "BATCH_LIMIT_REACHED",
                "error_message": (
                    f"Batch upload limit reached. This deal has used all {MAX_BATCH_UPLOADS} batch uploads. "
                    "Use single-file uploads or contact support."
                ),
            },
        )

    next_batch_number = batch_count + 1
    created_by_val = created_by or deal.get("created_by") or str(uuid.uuid4())

    pdf_parts: List[bytes] = []
    source_names: List[str] = []

    for i, up in enumerate(files, start=1):
        fname = up.filename or f"file{i}.pdf"
        ext = ("." + fname.rsplit(".", 1)[-1].lower()) if "." in fname else ".pdf"
        if ext != ".pdf":
            _error("BAD_REQUEST", f"Batch upload accepts PDF only; got '{ext}' for {fname}")
        content = await up.read()
        if not content:
            _error("BAD_REQUEST", f"Empty file: {fname}")
        pdf_parts.append(content)
        source_names.append(fname)
        logger.info(
            "Batch upload: received part %d/%d name=%s bytes=%d",
            i,
            len(files),
            fname,
            len(content),
        )

    try:
        merged_bytes = _merge_pdf_bytes_parts(pdf_parts)
    except Exception as exc:
        logger.exception("PDF merge failed for deal %s", deal_id)
        raise HTTPException(
            status_code=500,
            detail={
                "error_code": "MERGE_FAILED",
                "error_message": f"Failed to merge PDFs: {exc}",
            },
        ) from exc

    document_id = str(uuid.uuid4())
    merged_label = f"batch_{next_batch_number}_merged.pdf"

    document: Dict[str, Any] = {
        "id": document_id,
        "deal_id": deal_id,
        "storage_url": f"inline://{merged_label}",
        "file_type": "pdf",
        "status": "processing",
        "currency_detected": None,
        "currency_mismatch": False,
        "created_by": created_by_val,
        "batch_number": next_batch_number,
        "source_files": source_names,
        "is_batch_upload": True,
    }
    repos["documents"].create_document(document)

    ingestion = IngestionService(
        documents_repo=repos["documents"],
        raw_tx_repo=repos["raw"],
        analysis_repo=repos["runs"],
    )
    background_tasks.add_task(
        ingestion.process_document_background,
        document_id=document_id,
        deal_id=deal_id,
        created_by=created_by_val,
        file_bytes=merged_bytes,
        file_name=merged_label,
        file_type="pdf",
        deal_currency=deal["currency"],
    )

    batches_remaining = max(0, 4 - next_batch_number)

    return {
        "document_id": document_id,
        "batch_number": next_batch_number,
        "batches_remaining": batches_remaining,
        "files_merged": len(files),
        "source_files": source_names,
        "status": "processing",
        "message": f"Batch upload {next_batch_number}/4 submitted successfully",
        "ingestion": {
            "document_id": document_id,
            "status": "processing",
            "rows_count": 0,
        },
    }


@router.get("/deals/{deal_id}/documents")
def list_documents(request: Request, deal_id: str):
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    docs = repos["documents"].list_by_deal(deal_id)
    return {"documents": [_document_row_for_list_response(d) for d in docs]}


@router.get("/documents/{document_id}/status")
def get_document_status(request: Request, document_id: str):
    repos = _repos(request)
    doc = repos["documents"].get_document(document_id)
    if not doc:
        _error("NOT_FOUND", f"Document {document_id} not found")

    db_status = doc.get("status")
    processing_timed_out = _document_processing_lease_expired(doc)
    effective_status = "failed" if processing_timed_out else db_status

    out = {
        "document_id": doc["id"],
        "deal_id": doc.get("deal_id"),
        "status": effective_status,
        "file_type": doc.get("file_type"),
        "currency_mismatch": doc.get("currency_mismatch", False),
        "currency_detected": doc.get("currency_detected"),
        "created_at": doc.get("created_at"),
    }
    if effective_status == "completed":
        if doc.get("analytics"):
            out["analytics"] = doc.get("analytics")
    if effective_status == "failed":
        if processing_timed_out:
            out["reason"] = "processing_timeout"
            out["error_type"] = "ProcessingTimeout"
            out["error_message"] = (
                f"Document remained in processing for more than {PROCESSING_LEASE_SECONDS} seconds"
            )
            out["stage"] = "PROCESSING"
            out["next_action"] = "retry_or_contact_support"
        else:
            out["error_type"] = doc.get("error_type") or "UnknownError"
            out["error_message"] = doc.get("error_message") or "Document processing failed"
            out["stage"] = doc.get("error_stage") or "UNKNOWN"
            out["next_action"] = doc.get("next_action") or "retry_or_contact_support"
        # Legacy: keep "error" for backward compat
        out["error"] = out["error_message"]
    return out


@router.get("/documents/{document_id}/transactions")
def get_document_transactions(request: Request, document_id: str):
    repos = _repos(request)
    doc = repos["documents"].get_document(document_id)
    if not doc:
        _error("NOT_FOUND", f"Document {document_id} not found")
    txns = repos["raw"].list_by_document(document_id)
    return {"document_id": document_id, "transactions": txns}


# ===================================================================
# Overrides
# ===================================================================

_REVENUE_ROLES = frozenset({"revenue_operational", "revenue_non_operational"})


def _derive_override_weight(old_role: str, new_value: str) -> float:
    """
    Deterministic weight from role transition.
    Revert (0.0): new_value equals current role (neutralizing override).
    Major (1.0): revenue_operational/revenue_non_operational <-> anything else.
    Minor (0.5): all other transitions.
    """
    old = (old_role or "").strip()
    new = (new_value or "").strip()
    if old == new:
        return 0.0
    old_in_revenue = old in _REVENUE_ROLES
    new_in_revenue = new in _REVENUE_ROLES
    if old_in_revenue != new_in_revenue:
        return 1.0
    return 0.5


@router.post("/deals/{deal_id}/overrides")
def add_override(
    request: Request,
    deal_id: str,
    entity_id: str = Form(...),
    field: str = Form("role"),
    new_value: str = Form(...),
    reason: Optional[str] = Form(None),
    created_by: Optional[str] = Form(None),
):
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    effective_role = None
    for ov in sorted(repos["overrides"].list_overrides(deal_id), key=lambda o: o.get("created_at", ""), reverse=True):
        if ov.get("entity_id") == entity_id:
            effective_role = ov.get("new_value")
            break
    if effective_role is None:
        for m in repos["txn_map"].list_by_deal(deal_id):
            if m.get("entity_id") == entity_id:
                effective_role = m.get("role")
                break

    weight = _derive_override_weight(effective_role or "", new_value)

    ov = {
        "id": str(uuid.uuid4()),
        "deal_id": deal_id,
        "entity_id": entity_id,
        "field": field,
        "old_value": effective_role,
        "new_value": new_value,
        "weight": weight,
        "reason": reason,
        "created_by": created_by or str(uuid.uuid4()),
    }
    repos["overrides"].insert_override(ov)
    return {"override": ov}


@router.get("/deals/{deal_id}/overrides")
def list_overrides(request: Request, deal_id: str):
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    return {"overrides": repos["overrides"].list_overrides(deal_id)}


# ===================================================================
# Needs-Review / Override Gate (transaction-level)
# ===================================================================

_VALID_OVERRIDE_ROLES = frozenset({
    "revenue_operational", "revenue_non_operational", "revenue_investment",
    "mpesa_inflow", "loan_inflow", "equity_inflow", "fund_inflow",
    "supplier_payment", "supplier", "payroll", "tax", "loan_repayment",
    "capital_transfer", "related_party_transfer", "owner_withdrawal",
    "owner_distribution", "utility_payment", "rent_payment", "insurance_payment",
    "legal_professional", "bank_charges", "interest_income",
    "cash_deposit", "cash_withdrawal", "internal_transfer", "transfer",
    "pos_settlement", "reversal", "currency_conversion",
    "needs_review", "other",
})


@router.get("/deals/{deal_id}/transactions/needs-review")
def get_needs_review_transactions(request: Request, deal_id: str):
    """Return all transactions flagged as needs_review for a deal."""
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    all_maps = list(repos["txn_map"].list_by_deal(deal_id))
    nr_maps = [m for m in all_maps if (m.get("role") or "").lower() == "needs_review"]

    if not nr_maps:
        return {"transactions": [], "total": 0}

    all_txns = list(repos["raw"].list_by_deal(deal_id))
    txn_by_id = {str(t.get("id")): t for t in all_txns if t.get("id")}

    all_entities = list(repos["entities"].list_by_deal(deal_id))
    entity_name_by_id = {e.get("entity_id"): e.get("display_name") or "" for e in all_entities}

    results = []
    for m in nr_maps:
        txn_uuid = str(m.get("txn_id") or "")
        tx = txn_by_id.get(txn_uuid)
        if not tx:
            continue
        results.append({
            "row_id": txn_uuid,
            "txn_hash": tx.get("txn_id") or "",
            "txn_date": str(tx.get("txn_date") or ""),
            "description": tx.get("normalized_descriptor") or tx.get("parsed_descriptor") or "",
            "signed_amount_cents": int(tx.get("signed_amount_cents") or 0),
            "entity_name": entity_name_by_id.get(m.get("entity_id") or "", ""),
            "current_role": "needs_review",
        })

    results.sort(key=lambda r: r["txn_date"])
    return {"transactions": results, "total": len(results)}


@router.post("/deals/{deal_id}/transactions/resolve")
def resolve_transaction(
    request: Request,
    deal_id: str,
    row_id: str = Form(...),
    new_role: str = Form(...),
    analyst_initials: str = Form(...),
):
    """Override a single needs_review transaction with an analyst-assigned role."""
    if new_role not in _VALID_OVERRIDE_ROLES:
        _error("BAD_REQUEST", f"Invalid role '{new_role}'. Must be one of the valid classifier roles.")

    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    # Fetch the txn-entity map row to get original role and entity
    all_maps = repos["txn_map"].list_by_deal(deal_id)
    txn_map_row = next((m for m in all_maps if str(m.get("txn_id")) == row_id), None)
    if not txn_map_row:
        _error("NOT_FOUND", f"Transaction mapping {row_id} not found for deal {deal_id}")

    original_role = txn_map_row.get("role") or "needs_review"

    # Fetch the raw transaction for its SHA256 hash
    all_txns = repos["raw"].list_by_deal(deal_id)
    tx_row = next((t for t in all_txns if str(t.get("id")) == row_id), None)
    txn_hash = tx_row.get("txn_id") or "" if tx_row else ""

    user_id = _extract_user_id_from_request(request)

    # Insert immutable audit log entry
    log_entry = {
        "id": str(uuid.uuid4()),
        "deal_id": deal_id,
        "txn_uuid": row_id,
        "txn_hash": txn_hash,
        "original_role": original_role,
        "override_role": new_role,
        "analyst_initials": analyst_initials.strip()[:3].upper(),
    }
    if user_id:
        log_entry["user_id"] = user_id
    if repos.get("override_log"):
        repos["override_log"].insert_log(log_entry)

    # Update the role in pds_txn_entity_map
    if hasattr(repos["txn_map"], "update_role"):
        repos["txn_map"].update_role(row_id, new_role)

    # Count remaining needs_review for this deal
    remaining = sum(
        1 for m in repos["txn_map"].list_by_deal(deal_id)
        if (m.get("role") or "").lower() == "needs_review"
        and str(m.get("txn_id")) != row_id
    )

    return {"success": True, "remaining_count": remaining}


# ===================================================================
# Analysis
# ===================================================================

@router.get("/deals/{deal_id}/analysis/latest")
def get_latest_analysis(request: Request, deal_id: str):
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    runs = repos["runs"].list_runs(deal_id)
    if not runs:
        return {"analysis_run": None}
    latest = sorted(runs, key=lambda r: r.get("created_at", ""), reverse=True)[0]
    return {"analysis_run": latest}


# ===================================================================
# Export / Snapshot
# ===================================================================


def _snapshot_for_public_response(snapshot: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Drop canonical_json from the HTTP response. It can be multi‑MB for large deals and
    is not required by the Fund IQ UI (only id / hashes); including it risks 500s from
    response serialization or proxies.
    """
    if not snapshot:
        return None
    out = dict(snapshot)
    out.pop("canonical_json", None)
    return out


@router.post("/deals/{deal_id}/export")
def export(request: Request, deal_id: str, force: bool = False):
    started = time.perf_counter()
    stage = "EXPORT_START"
    logger.info("[EXPORT] stage=%s deal_id=%s force=%s", stage, deal_id, force)
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    docs = repos["documents"].list_by_deal(deal_id)
    blocking = [d for d in docs if _document_blocks_export(d)]
    if blocking:
        _error("DOCUMENTS_NOT_READY", "Documents still processing", status=409, next_action="wait_or_retry")
    raw = list(repos["raw"].list_by_deal(deal_id))
    stage = "FETCH_INPUTS_DONE"
    logger.info("[EXPORT] stage=%s raw_count=%d", stage, len(raw))
    overrides = list(repos["overrides"].list_overrides(deal_id))

    if not raw:
        _error("BAD_REQUEST", "No transactions to export. Upload documents first.", next_action="upload_new_file")

    # Short-circuit: return existing snapshot if no new docs/overrides since last export.
    # Skipped when force=True to rebuild the snapshot unconditionally.
    latest_snapshot = repos["snapshots"].get_latest_snapshot(deal_id)
    latest_doc_at = repos["documents"].get_latest_update_at(deal_id)
    latest_override_at = repos["overrides"].get_latest_update_at(deal_id) or ""
    snap_created_at = (latest_snapshot or {}).get("created_at") or ""
    snap_config_version = (latest_snapshot or {}).get("config_version")
    if not force and (
        latest_snapshot
        and snap_created_at
        and (not latest_doc_at or snap_created_at >= latest_doc_at)
        and snap_created_at > latest_override_at
        and snap_config_version == CONFIG_VERSION
    ):
        latest_run = repos["runs"].get_latest_run(deal_id)
        if latest_run and latest_run.get("id") == latest_snapshot.get("analysis_run_id"):
            entities = list(repos["entities"].list_by_deal(deal_id))
            txn_map = list(repos["txn_map"].list_by_deal(deal_id))
            run = dict(latest_run)
            run.setdefault("bank_operational_inflow_cents", 0)
            duration_ms = int((time.perf_counter() - started) * 1000)
            if request:
                request.app.state.last_export_ms = duration_ms
                request.app.state.last_export_at = datetime.now(timezone.utc).isoformat()
            logger.info("[EXPORT] deal=%s ms=%d short_circuit=1 config_version=%s", deal_id, duration_ms, snap_config_version)
            return {
                "analysis_run": run,
                "snapshot": _snapshot_for_public_response(latest_snapshot),
                "entities": entities,
                "txn_entity_map": txn_map,
            }
    if latest_snapshot and snap_config_version != CONFIG_VERSION:
        logger.info("[EXPORT] deal=%s config_version mismatch snap=%s current=%s — bypassing cache", deal_id, snap_config_version, CONFIG_VERSION)

    stage = "PIPELINE_START"
    run, links, entities, txn_map = run_pipeline(
        deal_id=deal_id,
        raw_transactions=raw,
        overrides=overrides,
        accrual={
            "accrual_revenue_cents": deal.get("accrual_revenue_cents"),
            "accrual_period_start": deal.get("accrual_period_start"),
            "accrual_period_end": deal.get("accrual_period_end"),
        },
    )
    stage = "PIPELINE_DONE"
    logger.info("[EXPORT] stage=%s", stage)

    txn_id_to_uuid = {tx["txn_id"]: tx["id"] for tx in raw if "id" in tx}
    for rec in txn_map:
        text_tid = rec["txn_id"]
        if text_tid in txn_id_to_uuid:
            rec["txn_id"] = txn_id_to_uuid[text_tid]

    for lnk in links:
        if lnk.get("id") is None:
            del lnk["id"]

    repos["txn_map"].delete_eq("deal_id", deal_id)
    repos["links"].delete_eq("deal_id", deal_id)
    repos["entities"].delete_eq("deal_id", deal_id)

    run_for_db = {k: v for k, v in run.items() if k != "bank_operational_inflow_cents"}
    repos["runs"].insert_run(run_for_db)
    repos["links"].insert_batch(links)
    repos["entities"].upsert_entities(entities)
    repos["txn_map"].upsert_mappings(txn_map)

    stage = "SNAPSHOT_BUILD_DONE"
    logger.info("[EXPORT] stage=%s", stage)
    from .db.supabase_repositories import AuditedFinancialsRepo
    af_rows = AuditedFinancialsRepo().get_by_deal_id(deal_id)
    audited_financials = af_rows[0] if af_rows else None
    payload = build_pds_payload(
        schema_version=run["schema_version"],
        config_version=run["config_version"],
        deal_id=deal_id,
        currency=deal["currency"],
        raw_transactions=raw,
        transfer_links=links,
        entities=entities,
        txn_entity_map=txn_map,
        metrics={
            "coverage_bp": run["coverage_pct_bp"],
            "missing_month_count": run["missing_month_count"],
            "missing_month_penalty_bp": run["missing_month_penalty_bp"],
            "reconciliation_status": run["reconciliation_status"],
            "reconciliation_bp": run["reconciliation_pct_bp"],
        },
        confidence={
            "final_confidence_bp": run["final_confidence_bp"],
            "tier": run["tier"],
            "tier_capped": run["tier_capped"],
            "override_penalty_bp": run["override_penalty_bp"],
        },
        overrides_applied=overrides,
        audited_financials=audited_financials,
    )
    snapshot = export_snapshot(
        snapshot_repo=repos["snapshots"],
        deal_id=deal_id,
        analysis_run_id=run["id"],
        payload=payload,
        created_by=deal.get("created_by") or str(uuid.uuid4()),
    )
    stage = "SNAPSHOT_INSERT_DONE"
    logger.info("[EXPORT] stage=%s", stage)

    # Persist account coverage advisory (non-fatal — advisory only)
    try:
        from .analysis.reconciliation_engine import calculate_account_coverage
        from .db.supabase_repositories import AuditedFinancialsRepo
        coverage = calculate_account_coverage(deal_id)
        if coverage.get("advisory_tier"):
            rows = [
                {
                    "deal_id": deal_id,
                    "declared_bank_name": a["bank_name"],
                    "declared_balance_cents": a["declared_balance_cents"],
                    "is_submitted": a["status"] == "SUBMITTED",
                    "materiality_tier": a["materiality"],
                }
                for a in coverage.get("account_details", [])
            ]
            repos["account_coverage"].replace_for_deal(deal_id, rows)
            if audited_financials:
                AuditedFinancialsRepo().patch_coverage_summary(
                    deal_id,
                    audited_financials["financial_year"],
                    {
                        "declared_accounts_count": coverage["declared_accounts_count"],
                        "submitted_accounts_count": coverage["submitted_accounts_count"],
                        "account_coverage_pct": coverage["coverage_pct"],
                        "account_coverage_advisory": coverage["advisory_tier"],
                    },
                )
    except Exception as exc:
        logger.warning("[EXPORT] account_coverage persist failed (non-fatal): %s", exc)

    # Seed default flags on first snapshot (idempotent — skipped if flags already exist)
    try:
        avg_inflow = int(run.get("average_monthly_inflow_cents") or 0)
        _seed_default_flags(deal_id, avg_inflow, repos.get("custom_flags"))
    except Exception as exc:
        logger.warning("[EXPORT] seed_default_flags failed (non-fatal): %s", exc)

    stage = "EXPORT_DONE"
    duration_ms = int((time.perf_counter() - started) * 1000)
    if request:
        request.app.state.last_export_ms = duration_ms
        request.app.state.last_export_at = datetime.now(timezone.utc).isoformat()
    logger.info("[EXPORT] stage=%s deal=%s ms=%d short_circuit=0", stage, deal_id, duration_ms)
    return {
        "analysis_run": run,
        "snapshot": _snapshot_for_public_response(snapshot),
        "entities": entities,
        "txn_entity_map": txn_map,
    }


@router.get("/deals/{deal_id}/snapshots")
def list_snapshots(request: Request, deal_id: str):
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    return {"snapshots": repos["snapshots"].list_snapshots(deal_id)}


@router.get("/snapshots/{snapshot_id}")
def get_snapshot(request: Request, snapshot_id: str):
    repos = _repos(request)
    snap = repos["snapshots"].get_snapshot(snapshot_id)
    if not snap:
        _error("NOT_FOUND", f"Snapshot {snapshot_id} not found")
    return {"snapshot": snap}


@router.get("/deals/{deal_id}/export/transactions")
def export_transactions_csv(request: Request, deal_id: str):
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    raw = list(repos["raw"].list_by_deal(deal_id))
    if not raw:
        _error("NOT_FOUND", "No transactions found. Upload documents first.")

    # Fetch entity/txn-map for entity_name enrichment
    entities = list(repos["entities"].list_by_deal(deal_id))
    txn_map_rows = list(repos["txn_map"].list_by_deal(deal_id))
    # entity_id is a SHA256 hex string; cast to str to guard against int storage variants
    entity_name_by_id = {str(e["entity_id"]): e.get("display_name") or "" for e in entities}
    # txn_id in stored map is UUID (Supabase after export rewrite) or text id (memory/tests)
    txn_id_to_entity_id = {
        str(m["txn_id"]): str(m["entity_id"])
        for m in txn_map_rows
        if m.get("txn_id") and m.get("entity_id")
    }
    txn_id_to_role = {str(m["txn_id"]): m.get("role", "") for m in txn_map_rows}

    raw.sort(key=lambda r: (
        r.get("txn_date", ""),
        r.get("account_id", ""),
        r.get("txn_id", ""),
    ))

    fieldnames = ["txn_date", "description", "amount_cents", "account_id", "txn_id", "entity_name", "role"]
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    for row in raw:
        # Try UUID row id first (Supabase), fall back to text txn_id (memory/tests)
        eid = (
            txn_id_to_entity_id.get(str(row.get("id") or ""))
            or txn_id_to_entity_id.get(str(row.get("txn_id") or ""))
            or ""
        )
        entity_name = entity_name_by_id.get(str(eid), "")
        # entity_name population: ~50%+ expected; was 0% before fix
        role = (
            txn_id_to_role.get(str(row.get("id", "")))
            or txn_id_to_role.get(str(row.get("txn_id", "")))
            or ""
        )
        writer.writerow({
            "txn_date": row.get("txn_date", ""),
            "description": row.get("normalized_descriptor", ""),
            "amount_cents": row.get("signed_amount_cents", ""),
            "account_id": row.get("account_id", ""),
            "txn_id": row.get("txn_id", ""),
            "entity_name": entity_name,
            "role": role,
        })

    content = output.getvalue()
    filename = f"transactions_{deal_id[:8]}.csv"
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/deals/{deal_id}/transactions")
def list_deal_transactions(request: Request, deal_id: str):
    """
    Return all transactions for a deal with their current roles and entity names.
    Used by the Parity Review enrichment UI.
    """
    repos = _repos(request)
    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    raw = list(repos["raw"].list_by_deal(deal_id))
    entities = list(repos["entities"].list_by_deal(deal_id))
    txn_map_rows = list(repos["txn_map"].list_by_deal(deal_id))

    entity_name_by_id = {str(e["entity_id"]): e.get("display_name") or "" for e in entities}
    txn_id_to_entity_id = {
        str(m["txn_id"]): str(m["entity_id"])
        for m in txn_map_rows
        if m.get("txn_id") and m.get("entity_id")
    }
    txn_id_to_role = {str(m["txn_id"]): m.get("role", "") for m in txn_map_rows}

    result = []
    for row in sorted(raw, key=lambda r: (r.get("txn_date", ""), r.get("txn_id", ""))):
        row_uuid = str(row.get("id") or "")
        row_txn_id = str(row.get("txn_id") or "")
        eid = txn_id_to_entity_id.get(row_uuid) or txn_id_to_entity_id.get(row_txn_id) or ""
        role = txn_id_to_role.get(row_uuid) or txn_id_to_role.get(row_txn_id) or ""
        result.append({
            "id": row_uuid,
            "txn_id": row_txn_id,
            "txn_date": row.get("txn_date"),
            "description": row.get("normalized_descriptor", ""),
            "signed_amount_cents": row.get("signed_amount_cents", 0),
            "account_id": row.get("account_id", ""),
            "role": role,
            "entity_name": entity_name_by_id.get(eid, ""),
        })

    return {"deal_id": deal_id, "transactions": result}


@router.get("/deals/{deal_id}/snapshot/pdf")
def get_snapshot_pdf(request: Request, deal_id: str):
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    snapshot = repos["snapshots"].get_latest_snapshot(deal_id)
    if not snapshot:
        _error("NOT_FOUND", "No snapshot found for this deal. Run POST /export first.")
    stored_cj = snapshot.get("canonical_json") or ""
    if not stored_cj:
        _error("INTERNAL", "Snapshot exists but canonical_json is empty.")
    import json
    canonical = json.loads(decompress_canonical_json_if_needed(stored_cj))
    snap_meta = {
        "id":                   snapshot.get("id"),
        "sha256_hash":          snapshot.get("sha256_hash"),
        "financial_state_hash": snapshot.get("financial_state_hash"),
    }
    account_coverage = repos["account_coverage"].list_by_deal(deal_id)
    pdf_bytes = _generate_snapshot_pdf(canonical, snap_meta, account_coverage=account_coverage)
    filename = f"parity_snapshot_{deal_id}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/deals/{deal_id}/snapshot/pdf/enriched")
def get_enriched_pdf(request: Request, deal_id: str, enrichment_id: Optional[str] = None):
    """
    Export PDF with Section A (base analytics) + Section B (analyst enrichment).
    Uses the latest final enrichment unless enrichment_id is specified.
    """
    repos = _repos(request)
    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    snapshot = repos["snapshots"].get_latest_snapshot(deal_id)
    if not snapshot:
        _error("NOT_FOUND", "No snapshot found. Run POST /export first.")

    # Resolve enrichment
    if enrichment_id:
        enrichment = repos["enrichments"].get_enrichment(enrichment_id)
        if not enrichment:
            _error("NOT_FOUND", f"Enrichment {enrichment_id} not found")
    else:
        enrichment = repos["enrichments"].get_latest_for_snapshot(snapshot["id"])

    # Hydrate enrichment with overrides + flags if found
    if enrichment:
        overrides = list(repos["cls_overrides"].list_by_enrichment(enrichment["id"]))
        flags = list(repos["custom_flags"].list_by_enrichment(enrichment["id"]))
        enrichment = {**enrichment, "overrides": overrides, "flags": flags}

    stored_cj = snapshot.get("canonical_json") or ""
    if not stored_cj:
        _error("INTERNAL", "Snapshot canonical_json is empty.")

    import json as _json
    canonical = _json.loads(decompress_canonical_json_if_needed(stored_cj))
    snap_meta = {
        "id":                   snapshot.get("id"),
        "sha256_hash":          snapshot.get("sha256_hash"),
        "financial_state_hash": snapshot.get("financial_state_hash"),
    }

    account_coverage = repos["account_coverage"].list_by_deal(deal_id)
    pdf_bytes = _generate_snapshot_pdf(canonical, snap_meta, enrichment, account_coverage=account_coverage)
    suffix = "_enriched" if enrichment else ""
    filename = f"parity_{deal_id}{suffix}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ===================================================================
# Analyst Enrichment
# ===================================================================

from .core.enrichment_engine import (  # noqa: E402
    build_enrichment_record,
    build_override_records,
    build_flag_records,
    evaluate_threshold_flag,
)


@router.post("/deals/{deal_id}/enrichment")
def create_enrichment(request: Request, deal_id: str, body: dict = Body(...)):
    """
    Create a new analyst enrichment layer on top of the latest base snapshot.

    Body fields (all optional except analyst_id):
      analyst_id     str   — email or user identifier
      analyst_name   str
      overrides      list  — [{txn_id, original_role, override_role, override_reason, original_reason?}]
      flags          list  — [{flag_type, flag_name, flag_severity, flag_description, criteria}]
                             criteria is evaluated against the base snapshot automatically
      narrative      str
      enrichment_reason str
      is_final       bool
    """
    repos = _repos(request)

    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    base_snapshot = repos["snapshots"].get_latest_snapshot(deal_id)
    if not base_snapshot:
        _error("NOT_FOUND", "No snapshot found. Run export first.")

    analyst_id = (body.get("analyst_id") or "").strip()
    if not analyst_id:
        _error("BAD_REQUEST", "analyst_id is required")

    raw_overrides = body.get("overrides") or []
    raw_flags = body.get("flags") or []
    narrative = (body.get("narrative") or "").strip()
    enrichment_reason = (body.get("enrichment_reason") or "").strip()
    is_final = bool(body.get("is_final", False))

    # Evaluate each flag's criteria against base snapshot
    evaluated_flags = []
    for f in raw_flags:
        result = evaluate_threshold_flag(f, base_snapshot)
        evaluated_flags.append({**f, **result})

    enrichment = build_enrichment_record(
        base_snapshot_id=base_snapshot["id"],
        base_snapshot_hash=base_snapshot["sha256_hash"],
        analyst_id=analyst_id,
        analyst_name=body.get("analyst_name"),
        overrides=raw_overrides,
        flags=evaluated_flags,
        narrative=narrative,
        enrichment_reason=enrichment_reason,
        is_final=is_final,
    )

    # Idempotent: return existing if same hash
    existing = repos["enrichments"].get_by_hash(enrichment["enriched_hash"])
    if existing:
        return {"enrichment_id": existing["id"], "enriched_hash": existing["enriched_hash"], "created": False}

    saved = repos["enrichments"].insert_enrichment(enrichment)

    override_records = build_override_records(saved["id"], raw_overrides, analyst_id)
    if override_records:
        repos["cls_overrides"].insert_batch(override_records)

    flag_records = build_flag_records(saved["id"], evaluated_flags, analyst_id)
    if flag_records:
        repos["custom_flags"].insert_batch(flag_records)

    return {"enrichment_id": saved["id"], "enriched_hash": saved["enriched_hash"], "created": True}


@router.get("/deals/{deal_id}/enrichment/latest")
def get_latest_enrichment(request: Request, deal_id: str):
    """Return the most recent enrichment for the latest base snapshot, or null."""
    repos = _repos(request)

    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    base_snapshot = repos["snapshots"].get_latest_snapshot(deal_id)
    if not base_snapshot:
        return {"enrichment": None}

    enrichment = repos["enrichments"].get_latest_for_snapshot(base_snapshot["id"])
    if not enrichment:
        return {"enrichment": None}

    overrides = repos["cls_overrides"].list_by_enrichment(enrichment["id"])
    flags = repos["custom_flags"].list_by_enrichment(enrichment["id"])

    return {
        "enrichment": {
            **enrichment,
            "overrides": list(overrides),
            "flags": list(flags),
        }
    }


@router.get("/enrichments/{enrichment_id}")
def get_enrichment(request: Request, enrichment_id: str):
    """Return a specific enrichment with its overrides and flags."""
    repos = _repos(request)

    enrichment = repos["enrichments"].get_enrichment(enrichment_id)
    if not enrichment:
        _error("NOT_FOUND", f"Enrichment {enrichment_id} not found")

    overrides = repos["cls_overrides"].list_by_enrichment(enrichment_id)
    flags = repos["custom_flags"].list_by_enrichment(enrichment_id)

    return {
        **enrichment,
        "overrides": list(overrides),
        "flags": list(flags),
    }


@router.post("/enrichments/{enrichment_id}/finalize")
def finalize_enrichment(request: Request, enrichment_id: str):
    """Mark an enrichment as final (ready for client export)."""
    repos = _repos(request)

    enrichment = repos["enrichments"].get_enrichment(enrichment_id)
    if not enrichment:
        _error("NOT_FOUND", f"Enrichment {enrichment_id} not found")

    updated = repos["enrichments"].mark_final(enrichment_id)
    return {"enrichment_id": enrichment_id, "is_final": True, "updated": updated is not None}


@router.post("/enrichments/{enrichment_id}/evaluate-flags")
def evaluate_flags(request: Request, enrichment_id: str, body: dict = Body(...)):
    """
    Evaluate a list of flag definitions against the base snapshot without persisting.
    Useful for previewing flag results in the UI before saving an enrichment.

    Body: { "flags": [...flag_defs...] }
    """
    repos = _repos(request)

    enrichment = repos["enrichments"].get_enrichment(enrichment_id)
    if not enrichment:
        _error("NOT_FOUND", f"Enrichment {enrichment_id} not found")

    base_snapshot = repos["snapshots"].get_snapshot(enrichment["base_snapshot_id"])
    if not base_snapshot:
        _error("NOT_FOUND", "Base snapshot not found")

    raw_flags = body.get("flags") or []
    results = []
    for f in raw_flags:
        result = evaluate_threshold_flag(f, base_snapshot)
        results.append({**f, **result})

    return {"flags": results}


# ===================================================================
# Parity Review — deterministic Q&A (LLM = intent classifier only)
# ===================================================================

from .ask import classify_intent, extract_aggregates, answer_intent  # noqa: E402


@router.post("/deals/{deal_id}/ask")
def ask_parity(request: Request, deal_id: str, body: dict = Body(...)):
    question = (body.get("question") or "").strip()
    if not question:
        _error("BAD_REQUEST", "question is required")
    repos = _repos(request)
    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    snapshot = repos["snapshots"].get_latest_snapshot(deal_id)
    if not snapshot:
        _error("NOT_FOUND", "No snapshot found. Run export first.")
    intent = classify_intent(question)
    if intent is None:
        return {"answer": "This question is outside supported scope.", "intent": None}
    agg = extract_aggregates(snapshot)
    result = answer_intent(intent, agg)
    # kra_summary returns a structured dict; other intents return strings
    if isinstance(result, dict):
        return {"answer": result.get("answer"), "intent": intent, "data": result.get("data"), "add_to_snapshot": result.get("add_to_snapshot", False)}
    return {"answer": result, "intent": intent}


# ===================================================================
# Parity Review — Intelligence Query Interface
# ===================================================================

def _intelligence_demo_response(query: str, query_type: str) -> Dict[str, Any]:
    """Return structured demo responses keyed on query content + type."""
    q = query.lower()

    if query_type == "computation":
        if any(k in q for k in ("inflow", "revenue", "income")):
            return {
                "response_text": "Annual inflow total: <strong>KES 3,748,800</strong> — integer sum of 12 monthly inflow totals, no rounding. 12-month mean: <strong>KES 312,400/month</strong>.",
                "basis_sources": ["monthly_cashflow·12mo", "integer arithmetic", "SHA256 f3a2b6c9..."],
                "computation_steps": ["Summing monthly inflows", "Computing 12-month mean", "Applying integer division"],
            }
        if any(k in q for k in ("dsr", "debt service", "coverage")):
            return {
                "response_text": "DSR: <strong>0.38</strong> (38%) — monthly debt service KES 118,800 ÷ monthly net inflow KES 312,400. Below 0.50 threshold — <span style='color:#4ADE80'>serviceable</span>.",
                "basis_sources": ["loan_repayment·monthly", "monthly_cashflow", "DSR threshold:0.50", "SHA256 a1b2c3d4..."],
                "computation_steps": ["Averaging monthly loan repayments", "Averaging monthly net inflow", "Computing ratio"],
            }
        if any(k in q for k in ("outflow", "expense", "spending")):
            return {
                "response_text": "Total outflows: <strong>KES 2,891,200</strong> across 12 months. Largest category: supplier_payment at <strong>KES 1,244,000</strong> (43%).",
                "basis_sources": ["monthly_cashflow·12mo", "entity breakdown", "integer arithmetic", "SHA256 c9d8e7f6..."],
                "computation_steps": ["Summing all debit categories", "Ranking by total", "Computing percentage share"],
            }
        return {
            "response_text": f"Computing over ledger for: '<em>{query}</em>'. Result: all integer arithmetic applied to classified transaction record.",
            "basis_sources": ["transaction ledger", "integer arithmetic", "SHA256 placeholder..."],
            "computation_steps": ["Parsing query", "Fetching classified record", "Applying arithmetic"],
        }

    if query_type == "classification":
        if any(k in q for k in ("meridian",)):
            return {
                "response_text": "Meridian Capital Ltd (KES 650,000 · 01-Aug-2025) resolved to <strong>fund_inflow</strong> by analyst AM. Entity registered in Parity as a Kenya-based investment fund.",
                "basis_sources": ["override log·AM", "entity registry:Meridian Capital", "fund_inflow classification", "SHA256 f3a2b6c9..."],
                "computation_steps": [],
            }
        if any(k in q for k in ("needs_review", "flagged", "unresolved")):
            return {
                "response_text": "0 transactions currently flagged as <strong>needs_review</strong>. All transactions have been classified or overridden.",
                "basis_sources": ["pds_txn_entity_map", "override_log", "SHA256 00000000..."],
                "computation_steps": [],
            }
        return {
            "response_text": f"Classification query: '<em>{query}</em>'. Transaction roles resolved from classifier ontology and analyst overrides.",
            "basis_sources": ["classifier ontology", "override log", "entity registry", "SHA256 placeholder..."],
            "computation_steps": [],
        }

    if query_type == "pattern":
        if any(k in q for k in ("negative", "net negative", "deficit")):
            return {
                "response_text": "Two net-negative months: <span style='color:#F87171'>August 2025 at −KES 447,800</span> (inflow KES 694,100 · outflow KES 1,141,900) driven by capital_transfer of KES 220,000 and supplier spike.",
                "basis_sources": ["monthly_cashflow·2025-08·2025-09", "capital_transfer:KES 220K", "supplier spike", "SHA256 f3a2b6c9..."],
                "computation_steps": [],
            }
        if any(k in q for k in ("concentration", "single", "dominant")):
            return {
                "response_text": "Top entity: <strong>Musa Distributors</strong> at 34% of total outflow (KES 983,000 of KES 2,891,200). Single-entity concentration above 30% threshold — <span style='color:#FBBF24'>review warranted</span>.",
                "basis_sources": ["entity breakdown·outflow", "concentration threshold:30%", "SHA256 d4e5f6a7..."],
                "computation_steps": [],
            }
        if any(k in q for k in ("trend", "growth", "decline", "month")):
            return {
                "response_text": "Inflow trend: +12% MoM average over the trailing 6 months. Peak month: <strong>March 2025 at KES 418,000</strong>. Trough: <strong>June 2025 at KES 247,000</strong>.",
                "basis_sources": ["monthly_cashflow·6mo", "MoM delta", "SHA256 b8c9d0e1..."],
                "computation_steps": [],
            }
        return {
            "response_text": f"Pattern analysis for: '<em>{query}</em>'. Scanning classified transaction record for statistical anomalies and structural patterns.",
            "basis_sources": ["monthly_cashflow", "entity breakdown", "classification distribution", "SHA256 placeholder..."],
            "computation_steps": [],
        }

    # Fallback
    return {
        "response_text": f"Query received: '<em>{query}</em>'. Analysis applied across classified transaction record.",
        "basis_sources": ["transaction ledger", "entity registry", "SHA256 placeholder..."],
        "computation_steps": [],
    }


@router.post("/deals/{deal_id}/intelligence/ask")
def intelligence_ask(request: Request, deal_id: str, body: dict = Body(...)):
    """Intelligence query interface — returns structured response with basis citations."""
    query = (body.get("query") or "").strip()
    query_type = (body.get("query_type") or "classification").strip()
    user_role = (body.get("user_role") or "analyst").strip()
    analyst_initials = (body.get("analyst_initials") or "AM").strip()[:3].upper()

    if not query:
        _error("BAD_REQUEST", "query is required")
    if query_type not in ("classification", "computation", "pattern"):
        _error("BAD_REQUEST", "query_type must be classification, computation, or pattern")
    if user_role not in ("analyst", "officer"):
        _error("BAD_REQUEST", "user_role must be analyst or officer")

    repos = _repos(request)
    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    user_id = _extract_user_id_from_request(request)
    payload = _intelligence_demo_response(query, query_type)

    # Persist to intelligence log
    entry_id = str(uuid.uuid4())
    log_entry = {
        "id": entry_id,
        "deal_id": deal_id,
        "query_text": query,
        "query_type": query_type,
        "user_role": user_role,
        "analyst_initials": analyst_initials,
        "response_text": payload["response_text"],
        "basis_sources": payload["basis_sources"],
        "computation_steps": payload["computation_steps"],
        "is_logged": False,
    }
    if user_id:
        log_entry["user_id"] = user_id

    # Best-effort write; don't fail the response if DB is unavailable
    try:
        if repos.get("intelligence_log"):
            repos["intelligence_log"].insert_log(log_entry)
    except Exception:
        pass

    return {
        "id": entry_id,
        "response_text": payload["response_text"],
        "basis_sources": payload["basis_sources"],
        "computation_steps": payload["computation_steps"],
    }


@router.get("/deals/{deal_id}/export-summary")
def get_export_summary(request: Request, deal_id: str):
    """Aggregated deal stats for the export/completion page."""
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    docs = list(repos["documents"].list_by_deal(deal_id))
    raw = list(repos["raw"].list_by_deal(deal_id))
    override_log = list(repos["override_log"].list_by_deal(deal_id)) if repos.get("override_log") else []
    intelligence_log = list(repos["intelligence_log"].list_by_deal(deal_id)) if repos.get("intelligence_log") else []
    latest_run = repos["runs"].get_latest_run(deal_id)

    files_uploaded = len([d for d in docs if d.get("status") == "ready"])
    override_count = len(override_log)
    logged_entries = len([e for e in intelligence_log if e.get("is_logged")])
    total_transactions = len(raw)
    tier = (latest_run or {}).get("tier") or "—"

    return {
        "deal_id": deal_id,
        "deal_name": deal.get("name") or deal.get("company_name") or "Untitled",
        "company_name": deal.get("company_name") or "",
        "analyst_initials": deal.get("analyst_initials") or "",
        "files_uploaded": files_uploaded,
        "total_transactions": total_transactions,
        "override_count": override_count,
        "logged_entries": logged_entries,
        "tier": tier,
        "has_snapshot": latest_run is not None,
    }


@router.post("/deals/{deal_id}/intelligence/{entry_id}/log")
def log_intelligence_entry(request: Request, deal_id: str, entry_id: str):
    """Mark an intelligence entry as logged (immutable record)."""
    repos = _repos(request)
    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    logged_count = 0
    try:
        if repos.get("intelligence_log"):
            repos["intelligence_log"].mark_logged(entry_id)
            all_entries = repos["intelligence_log"].list_by_deal(deal_id)
            logged_count = sum(1 for e in all_entries if e.get("is_logged"))
    except Exception:
        pass

    return {"success": True, "logged_count": logged_count}


# ===================================================================
# Parity Review — Suggestions Engine
# ===================================================================

from .analytics import loan_drawdowns as _loan_drawdowns  # noqa: E402
from .suggestions import generate_suggestions  # noqa: E402


@router.get("/deals/{deal_id}/analytics/loan-drawdowns")
def get_loan_drawdowns(request: Request, deal_id: str):
    """Returns all loan inflow transactions for a deal. Used by Parity Review."""
    repos = _repos(request)
    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    snapshot = repos["snapshots"].get_latest_snapshot(deal_id)
    if not snapshot:
        _error("NOT_FOUND", "No snapshot found. Run export first.")

    import json
    from .core.snapshot_engine import decompress_canonical_json_if_needed

    data = json.loads(decompress_canonical_json_if_needed(snapshot["canonical_json"]))
    transactions = data.get("transactions", [])
    txn_entity_map = data.get("txn_entity_map", [])
    entities = data.get("entities", [])

    role_lookup = {m["txn_id"]: m["role"] for m in txn_entity_map}
    entities_by_id = {str(e["entity_id"]): e for e in entities}
    txn_entity_id = {str(m.get("txn_id") or ""): str(m.get("entity_id") or "") for m in txn_entity_map}

    tagged = []
    for t in transactions:
        txn_id = str(t.get("id") or t.get("txn_id") or "")
        role = role_lookup.get(txn_id, role_lookup.get(str(t.get("txn_id", "")), "other"))
        entity_id = txn_entity_id.get(txn_id, "")
        entity = entities_by_id.get(entity_id, {})
        entity_name = entity.get("display_name") or str(t.get("normalized_descriptor", ""))[:40]
        tagged.append({
            "role": role,
            "amount_cents": int(t.get("signed_amount_cents", 0)),
            "txn_date": str(t.get("txn_date", "")),
            "txn_id": txn_id,
            "entity_name": entity_name,
        })

    return _loan_drawdowns(tagged)


@router.get("/deals/{deal_id}/review/suggestions")
def get_review_suggestions(request: Request, deal_id: str):
    """Returns Parity Review suggestion cards for a deal. Called when analyst opens Parity Review."""
    repos = _repos(request)
    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    snapshot = repos["snapshots"].get_latest_snapshot(deal_id)
    if not snapshot:
        _error("NOT_FOUND", "No snapshot found. Run export first.")

    import json
    from .core.snapshot_engine import decompress_canonical_json_if_needed

    data = json.loads(decompress_canonical_json_if_needed(snapshot["canonical_json"]))
    transactions = data.get("transactions", [])
    txn_entity_map = data.get("txn_entity_map", [])
    entities = data.get("entities", [])
    metrics = data.get("metrics", {})

    role_lookup = {m["txn_id"]: m["role"] for m in txn_entity_map}
    entities_by_id = {str(e["entity_id"]): e for e in entities}
    txn_entity_id = {str(m.get("txn_id") or ""): str(m.get("entity_id") or "") for m in txn_entity_map}

    tagged = []
    for t in transactions:
        txn_id = str(t.get("id") or t.get("txn_id") or "")
        role = role_lookup.get(txn_id, role_lookup.get(str(t.get("txn_id", "")), "other"))
        entity_id = txn_entity_id.get(txn_id, "")
        entity = entities_by_id.get(entity_id, {})
        entity_name = entity.get("display_name") or str(t.get("normalized_descriptor", ""))[:40]
        tagged.append({
            "role": role,
            "amount_cents": int(t.get("signed_amount_cents", 0)),
            "txn_date": str(t.get("txn_date", "")),
            "txn_id": txn_id,
            "entity_name": entity_name,
        })

    avg_monthly_inflow = int(metrics.get("average_monthly_inflow_cents") or 0)

    # Fetch current enrichment state if any
    enrichment_state = None
    try:
        latest_enrichments = repos["enrichments"].list_enrichments(deal_id)
        if latest_enrichments:
            latest_enrichments.sort(key=lambda e: e.get("created_at") or "", reverse=True)
            enrichment_state = latest_enrichments[0]
    except Exception:
        pass

    suggestions = generate_suggestions(tagged, enrichment_state, avg_monthly_inflow)
    return {"suggestions": suggestions, "count": len(suggestions)}


# ===================================================================
# Audited Financial Statements
# ===================================================================

@router.post("/deals/{deal_id}/upload-financials")
async def upload_audited_financials(
    request: Request,
    deal_id: str,
    file: UploadFile = File(...),
):
    """
    Upload an audited financial statements PDF for a deal.

    Sends the file to parity-ingestion for extraction, then stores the
    structured data in pds_audited_financials.  Idempotent: re-uploading
    the same financial year overwrites the previous record.
    """
    from .db.supabase_repositories import AuditedFinancialsRepo
    from .parsing.audited_financials_client import (
        extract_audited_financials_via_ingestion,
        AuditedFinancialsExtractionError,
    )

    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    filename = file.filename or "financials.pdf"
    if not filename.lower().endswith(".pdf"):
        raise HTTPException(
            status_code=415,
            detail="Only PDF files are accepted for audited financials upload.",
        )

    file_bytes = await file.read()

    try:
        data = extract_audited_financials_via_ingestion(file_bytes, filename)
    except AuditedFinancialsExtractionError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Attach deal FK and optional document FK (no pds_documents row created here)
    row = {
        "deal_id": deal_id,
        **{
            k: v
            for k, v in data.items()
            # Exclude non-column keys and convert Decimal to float for JSON
            if k not in ("sha256_hash",)
        },
        "extraction_confidence": int(data.get("extraction_confidence") or 0),
        "sha256_hash": data.get("sha256_hash"),
    }

    af_repo = AuditedFinancialsRepo()
    saved = af_repo.upsert(row)

    _conf = int(data.get("extraction_confidence") or 0)
    logger.info(
        "[API] Saved audited financials deal_id=%s FY=%s confidence=%d%%",
        deal_id,
        data.get("financial_year"),
        _conf,
    )

    return {
        "id": saved.get("id"),
        "deal_id": deal_id,
        "company_name": data.get("company_name"),
        "financial_year": data.get("financial_year"),
        "extraction_confidence": int(data.get("extraction_confidence") or 0),
        "turnover_cents": data.get("turnover_cents"),
        "profit_after_tax_cents": data.get("profit_after_tax_cents"),
        "total_assets_cents": data.get("total_assets_cents"),
        "cash_and_equivalents_cents": data.get("cash_and_equivalents_cents"),
    }


@router.get("/deals/{deal_id}/audited-financials")
def get_audited_financials(request: Request, deal_id: str):
    """
    Retrieve all audited financials records for a deal, ordered by financial_year desc.
    """
    from .db.supabase_repositories import AuditedFinancialsRepo

    repos = _repos(request)
    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    af_repo = AuditedFinancialsRepo()
    records = af_repo.get_by_deal_id(deal_id)
    records.sort(key=lambda r: r.get("financial_year") or 0, reverse=True)
    return {"deal_id": deal_id, "records": records}


_PATCHABLE_AF_FIELDS = frozenset({
    "company_name", "financial_year", "financial_year_start", "financial_year_end",
    "turnover_cents", "profit_after_tax_cents", "total_assets_cents",
    "cash_and_equivalents_cents", "total_expenses_cents", "total_liabilities_cents",
})


@router.patch("/deals/{deal_id}/audited-financials/{financial_year}")
def patch_audited_financials(request: Request, deal_id: str, financial_year: int, body: dict = Body(...)):
    """
    Manually update / fill in audited financials fields for a given fiscal year.
    Accepts a partial dict of the patchable fields. Creates the record if it doesn't exist.
    """
    from .db.supabase_repositories import AuditedFinancialsRepo

    repos = _repos(request)
    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    patch = {k: v for k, v in body.items() if k in _PATCHABLE_AF_FIELDS}
    if not patch:
        _error("BAD_REQUEST", f"No patchable fields provided. Allowed: {sorted(_PATCHABLE_AF_FIELDS)}")

    af_repo = AuditedFinancialsRepo()
    row = {
        "deal_id": deal_id,
        "financial_year": financial_year,
        **patch,
    }
    saved = af_repo.upsert(row)
    return saved


_VALID_SECTION_KEYS = frozenset({
    "annual_revenue", "loan_drawdowns", "kra_summary",
    "expense_frequency", "owner_distributions",
    "cash_threshold", "overdraft", "large_transactions",
})


@router.get("/deals/{deal_id}/reconciliation")
def get_reconciliation(request: Request, deal_id: str):
    """
    Run the full fiscal-year reconciliation for a deal.

    Compares bank activity against the uploaded audited financials across
    four dimensions: cash position, revenue, expenses, and loan activity.
    Also returns account coverage advisory.

    Requires:
    - At least one completed document (bank statement) for the deal.
    - At least one uploaded audited financials record.

    Returns a reconciliation block including tier (HIGH_CONFIDENCE /
    MEDIUM_CONFIDENCE / LOW_CONFIDENCE) and per-dimension detail.
    """
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    try:
        from .analysis.snapshot_generator import generate_reconciliation_section
        reconciliation = generate_reconciliation_section(deal_id)
    except ValueError as exc:
        # No audited financials uploaded yet
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("[RECONCILIATION] deal=%s error=%s", deal_id, exc)
        raise HTTPException(status_code=500, detail=f"Reconciliation failed: {exc}") from exc

    return {"deal_id": deal_id, "reconciliation": reconciliation}


@router.delete("/documents/{document_id}")
def delete_document(request: Request, document_id: str):
    """
    Delete a document and its raw transactions.

    Only permitted when the deal has no completed analysis run yet
    (i.e. status != 'done' / no snapshot exists with a final hash).
    This prevents deleting data that has already been included in a
    sealed snapshot.
    """
    repos = _repos(request)

    # Fetch document to confirm it exists and get the deal_id
    from .db.supabase_repositories import DocumentsRepo
    docs_repo = DocumentsRepo()
    doc = docs_repo.get_document(document_id)
    if not doc:
        _error("NOT_FOUND", f"Document {document_id} not found")

    deal_id = doc.get("deal_id")

    # Guard: block deletion if a sealed snapshot exists for this deal
    try:
        latest_snap = repos["snapshots"].get_latest_snapshot(deal_id)
    except Exception:
        latest_snap = None

    if latest_snap and latest_snap.get("sha256_hash"):
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete document — a sealed snapshot already exists for this deal. "
                "Documents that have been included in a snapshot cannot be removed."
            ),
        )

    # Delete raw transactions first (FK constraint)
    try:
        repos["raw"].delete_eq("document_id", document_id)
    except Exception as exc:
        logger.warning("[DELETE_DOC] transactions delete failed doc=%s: %s", document_id, exc)

    # Delete the document row
    docs_repo.delete_eq("id", document_id)

    logger.info("[DELETE_DOC] document=%s deal=%s deleted", document_id, deal_id)
    return {"deleted": True, "document_id": document_id, "deal_id": deal_id}


@router.post("/deals/{deal_id}/review/add-to-snapshot")
def add_section_to_snapshot(request: Request, deal_id: str, body: dict = Body(...)):
    """
    Adds a Parity Review suggestion to the enrichment record.
    Body: { "section_key": "annual_revenue", "data": {...} }

    Determinism: sections stored sorted by key. Enriched hash recomputed on each addition.
    """
    import hashlib
    import json as _json

    section_key = body.get("section_key")
    data = body.get("data")

    if section_key not in _VALID_SECTION_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown section_key: {section_key}")

    repos = _repos(request)
    if not repos["deals"].get_deal(deal_id):
        _error("NOT_FOUND", f"Deal {deal_id} not found")

    snapshot = repos["snapshots"].get_latest_snapshot(deal_id)
    if not snapshot:
        _error("NOT_FOUND", "No snapshot found. Run export first.")

    base_snapshot_hash = snapshot.get("sha256_hash") or ""

    # Fetch or create draft enrichment
    try:
        enrichments = repos["enrichments"].list_enrichments(deal_id)
        draft = next((e for e in enrichments if not e.get("is_final")), None)
    except Exception:
        draft = None

    if draft is None:
        draft = {
            "id": str(uuid.uuid4()),
            "deal_id": deal_id,
            "base_snapshot_id": snapshot.get("id"),
            "added_sections": [],
            "sections_data": {},
            "is_final": False,
        }

    added_sections = list(draft.get("added_sections") or [])
    sections_data = dict(draft.get("sections_data") or {})

    if section_key not in added_sections:
        added_sections.append(section_key)
    sections_data[section_key] = data

    # Recompute enriched_hash deterministically
    payload_for_hash = {
        "base_snapshot_hash": base_snapshot_hash,
        "sections": {k: sections_data[k] for k in sorted(sections_data.keys())},
    }
    raw = _json.dumps(payload_for_hash, sort_keys=True, separators=(",", ":"))
    enriched_hash = hashlib.sha256(raw.encode()).hexdigest()

    draft["added_sections"] = sorted(added_sections)
    draft["sections_data"] = sections_data
    draft["enriched_hash"] = enriched_hash

    try:
        if draft.get("id") and enrichments:
            repos["enrichments"].update_enrichment(draft["id"], draft)
        else:
            repos["enrichments"].insert_enrichment(draft)
    except Exception as exc:
        logger.warning("[add-to-snapshot] enrichment persist failed: %s", exc)

    return {
        "enrichment_id": draft.get("id"),
        "section_key": section_key,
        "added_sections": draft["added_sections"],
        "enriched_hash": enriched_hash,
    }
