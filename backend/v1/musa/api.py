"""
Musa Ventures file-URL async integration.

Endpoints
---------
POST /api/musa/v2/sessions
    Accept file URLs, store in pds_musa_sessions, return 202 immediately.
    Background worker (worker.py) polls and processes.

GET /api/musa/v2/sessions/{session_id}
    Poll processing status.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, HttpUrl

from ..db.supabase_client import get_supabase
from ..integrations.auth import require_musa_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/musa/v2", tags=["musa-v2"])


# ============================================================================
# MODELS
# ============================================================================

class MusaSessionRequest(BaseModel):
    file_urls: List[HttpUrl]
    webhook_url: Optional[HttpUrl] = None
    deal_id: Optional[str] = None
    metadata: Optional[dict] = None


class MusaSessionResponse(BaseModel):
    session_id: str
    status: str
    message: str
    created_at: str


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/sessions", status_code=202, response_model=MusaSessionResponse)
async def create_session(
    body: MusaSessionRequest,
    _: bool = Depends(require_musa_api_key),
) -> MusaSessionResponse:
    """
    Queue file URLs for async processing.

    Returns 202 Accepted immediately.  Background worker picks up the job,
    ingests files through Parity pipeline, then POSTs results to webhook_url.
    """
    session_id = f"musa_{uuid.uuid4().hex[:12]}"
    created_at = datetime.now(timezone.utc).isoformat()

    session_data = {
        "session_id": session_id,
        "status": "pending",
        "file_urls": [str(url) for url in body.file_urls],
        "webhook_url": str(body.webhook_url) if body.webhook_url else None,
        "deal_id": body.deal_id,
        "metadata": body.metadata or {},
        "created_at": created_at,
    }

    try:
        supabase = get_supabase()
        result = supabase.table("pds_musa_sessions").insert(session_data).execute()
        if not result.data:
            raise RuntimeError("Insert returned no data")
    except Exception as exc:
        msg = str(exc)
        if "duplicate" in msg.lower() or "unique" in msg.lower():
            raise HTTPException(status_code=409, detail="Session already exists")
        logger.exception("Failed to create pds_musa_session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to create session")

    return MusaSessionResponse(
        session_id=session_id,
        status="pending",
        message="Session queued. Results will be POSTed to webhook_url when complete.",
        created_at=created_at,
    )


@router.get("/sessions/{session_id}", response_model=dict)
async def get_session_status(
    session_id: str,
    _: bool = Depends(require_musa_api_key),
) -> dict:
    """Check status of a pds_musa_session job."""
    try:
        supabase = get_supabase()
        result = (
            supabase.table("pds_musa_sessions")
            .select("session_id, status, created_at, started_at, completed_at, error_message, file_urls, retry_count")
            .eq("session_id", session_id)
            .execute()
        )
    except Exception:
        logger.exception("Failed to query pds_musa_session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve session")

    rows = result.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")

    row = rows[0]
    return {
        "session_id": row["session_id"],
        "status": row["status"],
        "file_count": len(row.get("file_urls") or []),
        "retry_count": row.get("retry_count", 0),
        "created_at": row.get("created_at"),
        "started_at": row.get("started_at"),
        "completed_at": row.get("completed_at"),
        "error_message": row.get("error_message"),
    }
