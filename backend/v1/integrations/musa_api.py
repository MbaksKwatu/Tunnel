import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ..db.supabase_client import get_supabase
from ..db.supabase_repositories import DealsRepo, SnapshotsRepo
from ..core.snapshot_engine import decompress_canonical_json_if_needed
from .auth import require_musa_api_key

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/musa", tags=["musa"])


class CreateSessionRequest(BaseModel):
    venture_id: str
    venture_name: str
    company_metadata: Optional[dict] = None


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str


@router.post("/sessions", response_model=CreateSessionResponse)
def create_session(
    body: CreateSessionRequest,
    _: bool = Depends(require_musa_api_key),
) -> CreateSessionResponse:
    session_id = str(uuid.uuid4())

    try:
        deal = DealsRepo().create_deal({
            "id": str(uuid.uuid4()),
            "currency": "USD",
            "name": body.venture_name,
            "created_by": str(uuid.uuid4()),
        })
    except Exception:
        logger.exception("Failed to create deal for Musa session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to create deal")

    deal_id = deal.get("id")

    try:
        supabase = get_supabase()
        result = (
            supabase.table("musa_sessions")
            .insert({
                "session_id": session_id,
                "venture_id": body.venture_id,
                "venture_name": body.venture_name,
                "deal_id": deal_id,
                "status": "processing",
            })
            .execute()
        )
        if not result.data:
            raise RuntimeError("Insert returned no data")
    except Exception as exc:
        _msg = str(exc)
        if "duplicate" in _msg.lower() or "unique" in _msg.lower():
            raise HTTPException(status_code=409, detail="Session already exists")
        logger.exception("Failed to insert musa_session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to create session")

    return CreateSessionResponse(session_id=session_id, status="processing")


class SessionStatusResponse(BaseModel):
    session_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None


def _to_iso(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).isoformat()
    except (ValueError, AttributeError):
        return value


@router.get("/sessions/{session_id}/status", response_model=SessionStatusResponse)
def get_session_status(
    session_id: str,
    _: bool = Depends(require_musa_api_key),
) -> SessionStatusResponse:
    try:
        supabase = get_supabase()
        result = (
            supabase.table("musa_sessions")
            .select("session_id, status, created_at, completed_at")
            .eq("session_id", session_id)
            .execute()
        )
    except Exception:
        logger.exception("Failed to query musa_session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve session")

    rows = result.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")

    row = rows[0]
    return SessionStatusResponse(
        session_id=row["session_id"],
        status=row["status"],
        created_at=_to_iso(row.get("created_at")) or "",
        completed_at=_to_iso(row.get("completed_at")),
    )


class SessionResultsResponse(BaseModel):
    session_id: str
    venture_id: str
    venture_name: str
    status: str
    results: dict
    pdf_url: Optional[str] = None
    completed_at: str


@router.get("/sessions/{session_id}/results", response_model=SessionResultsResponse)
def get_session_results(
    session_id: str,
    _: bool = Depends(require_musa_api_key),
) -> SessionResultsResponse:
    try:
        supabase = get_supabase()
        session_result = (
            supabase.table("musa_sessions")
            .select("session_id, venture_id, venture_name, deal_id, status, completed_at")
            .eq("session_id", session_id)
            .execute()
        )
    except Exception:
        logger.exception("Failed to query musa_session %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to retrieve session")

    rows = session_result.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Session not found")

    session = rows[0]

    if session["status"] != "complete":
        raise HTTPException(status_code=400, detail="Session not complete yet")

    deal_id = session.get("deal_id")
    if not deal_id:
        raise HTTPException(status_code=404, detail="Deal not found for session")

    deal = DealsRepo().get_deal(deal_id)
    if not deal:
        raise HTTPException(status_code=404, detail="Deal not found")

    snapshot = SnapshotsRepo().get_latest_snapshot(deal_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="No snapshot exists for this session")

    raw_cj = snapshot.get("canonical_json") or "{}"
    try:
        analytics = json.loads(decompress_canonical_json_if_needed(raw_cj))
    except (ValueError, TypeError):
        logger.exception("Failed to decode canonical_json for deal %s", deal_id)
        raise HTTPException(status_code=500, detail="Failed to decode analytics data")

    return SessionResultsResponse(
        session_id=session["session_id"],
        venture_id=session["venture_id"],
        venture_name=session["venture_name"],
        status=session["status"],
        results=analytics,
        pdf_url=None,
        completed_at=_to_iso(session.get("completed_at")) or "",
    )
