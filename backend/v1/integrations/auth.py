import logging

import bcrypt
from fastapi import Header, HTTPException

from ..db.supabase_client import get_supabase

logger = logging.getLogger(__name__)


def validate_api_key(api_key: str, partner_name: str) -> bool:
    try:
        supabase = get_supabase()
        result = (
            supabase.table("api_keys")
            .select("api_key_hash")
            .eq("partner_name", partner_name)
            .eq("active", True)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return False
        key_bytes = api_key.encode("utf-8")
        return any(
            bcrypt.checkpw(key_bytes, row["api_key_hash"].encode("utf-8"))
            for row in rows
        )
    except Exception:
        logger.exception("Error validating API key for partner %r", partner_name)
        return False


def require_musa_api_key(x_api_key: str = Header(..., alias="x-api-key")) -> bool:
    if not validate_api_key(x_api_key, "Musa Ventures"):
        raise HTTPException(status_code=401, detail="Invalid API key")
    return True
