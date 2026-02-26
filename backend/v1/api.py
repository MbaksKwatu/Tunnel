"""
Parity v1 — Deterministic API
All money fields: integer cents.  All ratios: integer basis points.
Snapshot only on explicit POST /v1/deals/{deal_id}/export.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Form, Request, BackgroundTasks
from typing import Any, Dict, Optional

import uuid
import time
from datetime import datetime, timezone

from .config import SCHEMA_VERSION, CONFIG_VERSION, GIT_COMMIT, BUILD_TIMESTAMP, DETERMINISTIC_MODE
from .ingestion.service import IngestionService
from .parsing.errors import CurrencyMismatchError, InvalidSchemaError
from .core.pipeline import run_pipeline
from .core.snapshot_engine import build_pds_payload, export_snapshot

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

def _repos(request: Optional[Request] = None) -> Dict[str, Any]:
    if request and hasattr(request.app.state, "repos_factory"):
        return request.app.state.repos_factory()
    from .db.supabase_repositories import (
        DealsRepo, DocumentsRepo, RawTxRepo, TransferLinksRepo,
        EntitiesRepo, TxnEntityMapRepo, OverridesRepo,
        AnalysisRunsRepo, SnapshotsRepo,
    )
    return {
        "deals": DealsRepo(),
        "documents": DocumentsRepo(),
        "raw": RawTxRepo(),
        "links": TransferLinksRepo(),
        "entities": EntitiesRepo(),
        "txn_map": TxnEntityMapRepo(),
        "overrides": OverridesRepo(),
        "runs": AnalysisRunsRepo(),
        "snapshots": SnapshotsRepo(),
    }


# ===================================================================
# Deals
# ===================================================================

@router.post("/deals")
def create_deal(
    request: Request,
    currency: str = Form(...),
    name: Optional[str] = Form(None),
    created_by: Optional[str] = Form(None),
    accrual_revenue_cents: Optional[str] = Form(None),
    accrual_period_start: Optional[str] = Form(None),
    accrual_period_end: Optional[str] = Form(None),
):
    repos = _repos(request)
    deal = {
        "id": str(uuid.uuid4()),
        "currency": currency.upper(),
        "name": name,
        "created_by": created_by or str(uuid.uuid4()),
    }
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
    file_type = file.filename.split(".")[-1] if "." in file.filename else "csv"
    created_by_val = created_by or deal.get("created_by") or str(uuid.uuid4())

    document = {
        "id": document_id,
        "deal_id": deal_id,
        "storage_url": f"inline://{file.filename}",
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


@router.get("/deals/{deal_id}/documents")
def list_documents(request: Request, deal_id: str):
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    docs = repos["documents"].list_by_deal(deal_id)
    return {"documents": docs}


@router.get("/documents/{document_id}/status")
def get_document_status(request: Request, document_id: str):
    repos = _repos(request)
    doc = repos["documents"].get_document(document_id)
    if not doc:
        _error("NOT_FOUND", f"Document {document_id} not found")
    return {
        "document_id": doc["id"],
        "deal_id": doc.get("deal_id"),
        "status": doc.get("status"),
        "file_type": doc.get("file_type"),
        "currency_mismatch": doc.get("currency_mismatch", False),
        "created_at": doc.get("created_at"),
    }


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

@router.post("/deals/{deal_id}/export")
def export(request: Request, deal_id: str):
    started = time.perf_counter()
    repos = _repos(request)
    deal = repos["deals"].get_deal(deal_id)
    if not deal:
        _error("NOT_FOUND", f"Deal {deal_id} not found")
    docs = repos["documents"].list_by_deal(deal_id)
    not_ready = [d for d in docs if d.get("status") != "completed"]
    if not_ready:
        _error("DOCUMENTS_NOT_READY", "Documents still processing", status=409, next_action="wait_or_retry")
    raw = list(repos["raw"].list_by_deal(deal_id))
    overrides = list(repos["overrides"].list_overrides(deal_id))

    if not raw:
        _error("BAD_REQUEST", "No transactions to export. Upload documents first.", next_action="upload_new_file")

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

    run_for_db = {k: v for k, v in run.items() if k != "bank_operational_inflow_cents"}
    repos["runs"].insert_run(run_for_db)
    repos["links"].insert_batch(links)
    repos["entities"].upsert_entities(entities)
    repos["txn_map"].upsert_mappings(txn_map)

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
    )
    snapshot = export_snapshot(
        snapshot_repo=repos["snapshots"],
        deal_id=deal_id,
        analysis_run_id=run["id"],
        payload=payload,
        created_by=deal.get("created_by") or str(uuid.uuid4()),
    )
    duration_ms = int((time.perf_counter() - started) * 1000)
    if request:
        request.app.state.last_export_ms = duration_ms
        request.app.state.last_export_at = datetime.now(timezone.utc).isoformat()
    return {
        "analysis_run": run,
        "snapshot": snapshot,
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
