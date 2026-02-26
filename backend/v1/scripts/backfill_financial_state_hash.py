"""
Idempotent backfill for financial_state_hash on pds_snapshots.

Usage:
  python -m backend.v1.scripts.backfill_financial_state_hash

Behavior:
  - Scans all snapshots.
  - For rows missing financial_state_hash, recomputes deterministically from canonical_json.
  - Updates only financial_state_hash (allowed by snapshot immutability guard migration).
  - Safe to rerun; skips rows already populated.
"""

import json
import os
from typing import Tuple

from backend.v1.core.snapshot_engine import compute_financial_state_hash_from_canonical_json
from backend.v1.db.supabase_client import get_supabase


def _fetch_all_snapshots():
    client = get_supabase()
    res = client.table("pds_snapshots").select("*").execute()
    return res.data or []


def _update_financial_hash(snapshot_id: str, fin_hash: str) -> None:
    client = get_supabase()
    client.table("pds_snapshots").update({"financial_state_hash": fin_hash}).eq("id", snapshot_id).execute()


def backfill() -> Tuple[int, int, int]:
    """
    Returns: (scanned, updated, skipped)
    """
    snapshots = _fetch_all_snapshots()
    scanned = len(snapshots)
    updated = 0
    skipped = 0

    for snap in snapshots:
        if snap.get("financial_state_hash"):
            skipped += 1
            continue
        canonical_json = snap.get("canonical_json")
        if not canonical_json:
            skipped += 1
            continue
        try:
            # validate JSON early
            json.loads(canonical_json)
            fin_hash = compute_financial_state_hash_from_canonical_json(canonical_json)
        except Exception:
            skipped += 1
            continue
        _update_financial_hash(snap["id"], fin_hash)
        updated += 1

    return scanned, updated, skipped


if __name__ == "__main__":
    scanned, updated, skipped = backfill()
    print(f"[financial_state_hash backfill] scanned={scanned} updated={updated} skipped={skipped}")
