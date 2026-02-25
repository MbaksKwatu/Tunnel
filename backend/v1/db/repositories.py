"""
Stub repositories for Parity v1 deterministic pipeline.

These interfaces intentionally avoid business logic; they will be implemented
in later phases after the schema is in place. All money values should be
passed/stored as integer cents; snapshots are immutable.
"""

from typing import Any, Dict, Iterable, Optional, Sequence


class DealsRepository:
    def create_deal(self, deal: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a deal; deal dict must include currency and created_by."""
        raise NotImplementedError

    def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a deal by id."""
        raise NotImplementedError


class DocumentsRepository:
    def create_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a document row."""
        raise NotImplementedError

    def update_status(self, document_id: str, status: str, *, currency_mismatch: bool = False) -> None:
        """Update document status (and optional currency_mismatch flag)."""
        raise NotImplementedError


class RawTransactionsRepository:
    def insert_batch(self, rows: Iterable[Dict[str, Any]]) -> None:
        """Bulk insert canonical raw transactions; rows must already be deterministic."""
        raise NotImplementedError


class OverridesRepository:
    def insert_override(self, override: Dict[str, Any]) -> Dict[str, Any]:
        """Insert an override event (insert-only)."""
        raise NotImplementedError

    def list_overrides(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        """List overrides for a deal."""
        raise NotImplementedError


class AnalysisRunsRepository:
    def insert_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a LIVE_DRAFT analysis run (insert-only)."""
        raise NotImplementedError

    def list_runs(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        """List analysis runs for a deal, typically newest-first."""
        raise NotImplementedError


class SnapshotsRepository:
    def insert_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Insert an immutable snapshot; enforce idempotency by sha256_hash externally."""
        raise NotImplementedError

    def get_by_hash(self, sha256_hash: str) -> Optional[Dict[str, Any]]:
        """Fetch snapshot by hash (for idempotent export)."""
        raise NotImplementedError

    def list_snapshots(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        """List snapshots for a deal."""
        raise NotImplementedError
