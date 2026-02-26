import json
import uuid
from typing import Any, Dict, List, Tuple

from ..parsing.common import canonical_hash, sort_rows


def _build_financial_state_payload(
    *,
    schema_version: str,
    config_version: str,
    deal_id: str,
    currency: str,
    transactions: List[Dict[str, Any]],
    transfer_links: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    txn_entity_map: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    confidence: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Outcome-only view of a snapshot (excludes override audit trail and snapshot metadata).
    This is the canonical input to financial_state_hash.
    """
    return {
        "schema_version": schema_version,
        "config_version": config_version,
        "deal_id": deal_id,
        "currency": currency,
        "raw_transaction_hash": canonical_hash(transactions),
        "transactions": transactions,
        "transfer_links": transfer_links,
        "entities": entities,
        "txn_entity_map": txn_entity_map,
        "metrics": metrics,
        "confidence": confidence,
    }


def compute_financial_state_hash(payload: Dict[str, Any]) -> str:
    """
    Deterministically compute the financial_state_hash from a payload (already sorted).
    Expects the payload to include the same keys produced by _build_financial_state_payload.
    """
    return canonical_hash([payload])


def compute_financial_state_hash_from_canonical_json(canonical_json: str) -> str:
    """
    Idempotent helper for backfill: parses stored canonical_json, rebuilds the
    outcome-only view, and returns the financial_state_hash.
    """
    data = json.loads(canonical_json)
    # Re-sort defensively to avoid relying on stored order
    transactions = sort_rows(data.get("transactions", []))
    transfer_links = sorted(
        data.get("transfer_links", []),
        key=lambda l: (l.get("txn_out_id") or "", l.get("txn_in_id") or ""),
    )
    entities = sorted(data.get("entities", []), key=lambda e: e["entity_id"])
    txn_entity_map = sorted(data.get("txn_entity_map", []), key=lambda m: m["txn_id"])
    metrics = data.get("metrics", {})
    confidence = data.get("confidence", {})

    fs_payload = _build_financial_state_payload(
        schema_version=data.get("schema_version"),
        config_version=data.get("config_version"),
        deal_id=data.get("deal_id"),
        currency=data.get("currency"),
        transactions=transactions,
        transfer_links=transfer_links,
        entities=entities,
        txn_entity_map=txn_entity_map,
        metrics=metrics,
        confidence=confidence,
    )
    return compute_financial_state_hash(fs_payload)


def build_pds_payload(
    *,
    schema_version: str,
    config_version: str,
    deal_id: str,
    currency: str,
    raw_transactions: List[Dict[str, Any]],
    transfer_links: List[Dict[str, Any]],
    entities: List[Dict[str, Any]],
    txn_entity_map: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    confidence: Dict[str, Any],
    overrides_applied: List[Dict[str, Any]],
) -> Dict[str, Any]:
    sorted_txns = sorted(
        raw_transactions,
        key=lambda r: (
            r["txn_date"],
            r["account_id"],
            r["signed_amount_cents"],
            r["normalized_descriptor"],
            r["txn_id"],
        ),
    )
    sorted_transfer_links = sorted(
        transfer_links,
        key=lambda l: (l.get("txn_out_id") or "", l.get("txn_in_id") or ""),
    )
    sorted_entities = sorted(entities, key=lambda e: e["entity_id"])
    sorted_txn_entity_map = sorted(txn_entity_map, key=lambda m: m["txn_id"])

    metrics_block = {
        "coverage_bp": metrics.get("coverage_bp"),
        "missing_month_count": metrics.get("missing_month_count"),
        "missing_month_penalty_bp": metrics.get("missing_month_penalty_bp"),
        "reconciliation_status": metrics.get("reconciliation_status"),
        "reconciliation_bp": metrics.get("reconciliation_bp"),
    }
    confidence_block = {
        "final_confidence_bp": confidence.get("final_confidence_bp"),
        "tier": confidence.get("tier"),
        "tier_capped": confidence.get("tier_capped"),
        "override_penalty_bp": confidence.get("override_penalty_bp"),
    }

    financial_state_payload = _build_financial_state_payload(
        schema_version=schema_version,
        config_version=config_version,
        deal_id=deal_id,
        currency=currency,
        transactions=sorted_txns,
        transfer_links=sorted_transfer_links,
        entities=sorted_entities,
        txn_entity_map=sorted_txn_entity_map,
        metrics=metrics_block,
        confidence=confidence_block,
    )

    financial_state_hash = compute_financial_state_hash(financial_state_payload)

    payload = {
        **financial_state_payload,
        "financial_state_hash": financial_state_hash,
        "overrides_applied": sorted(overrides_applied, key=lambda o: o.get("entity_id") or ""),
    }
    return payload


def canonicalize_payload(payload: Dict[str, Any]) -> Tuple[str, str]:
    canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    sha = canonical_hash([payload])  # reuse canonical_hash utility
    return canonical_json, sha


def export_snapshot(
    *,
    snapshot_repo,
    deal_id: str,
    analysis_run_id: str,
    payload: Dict[str, Any],
    created_by: str,
) -> Dict[str, Any]:
    canonical_json, sha = canonicalize_payload(payload)
    existing = snapshot_repo.get_by_hash(sha)
    if existing:
        return existing
    snapshot = {
        "id": str(uuid.uuid4()),
        "deal_id": deal_id,
        "analysis_run_id": analysis_run_id,
        "schema_version": payload["schema_version"],
        "config_version": payload["config_version"],
        "financial_state_hash": payload.get("financial_state_hash"),
        "sha256_hash": sha,
        "canonical_json": canonical_json,
        "created_by": created_by,
    }
    return snapshot_repo.insert_snapshot(snapshot)
