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

    def list_deals(self, created_by: str) -> Sequence[Dict[str, Any]]:
        """List deals for a user."""
        raise NotImplementedError


class DocumentsRepository:
    def create_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a document row."""
        raise NotImplementedError

    def update_status(self, document_id: str, status: str, *, currency_mismatch: bool = False) -> None:
        """Update document status (and optional currency_mismatch flag)."""
        raise NotImplementedError

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a document by id."""
        raise NotImplementedError

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        """Fetch documents for a deal."""
        raise NotImplementedError

    def get_latest_update_at(self, deal_id: str) -> Optional[str]:
        """Max created_at of documents for deal, or None if none."""
        raise NotImplementedError


class RawTransactionsRepository:
    def insert_batch(self, rows: Iterable[Dict[str, Any]]) -> None:
        """Bulk insert canonical raw transactions; rows must already be deterministic."""
        raise NotImplementedError

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        """Fetch raw transactions for a deal."""
        raise NotImplementedError

    def list_by_document(self, document_id: str) -> Sequence[Dict[str, Any]]:
        """Fetch raw transactions for a document."""
        raise NotImplementedError


class TransferLinksRepository:
    def insert_batch(self, links: Iterable[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        raise NotImplementedError


class EntitiesRepository:
    def upsert_entities(self, entities: Iterable[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        raise NotImplementedError


class TxnEntityMapRepository:
    def upsert_mappings(self, mappings: Iterable[Dict[str, Any]]) -> None:
        raise NotImplementedError

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        raise NotImplementedError


class OverridesRepository:
    def insert_override(self, override: Dict[str, Any]) -> Dict[str, Any]:
        """Insert an override event (insert-only)."""
        raise NotImplementedError

    def list_overrides(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        """List overrides for a deal."""
        raise NotImplementedError

    def get_latest_update_at(self, deal_id: str) -> Optional[str]:
        """Max created_at of overrides for deal, or '' if none."""
        raise NotImplementedError


class AnalysisRunsRepository:
    def insert_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a LIVE_DRAFT analysis run (insert-only)."""
        raise NotImplementedError

    def list_runs(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        """List analysis runs for a deal, typically newest-first."""
        raise NotImplementedError

    def get_latest_run(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Fetch latest analysis run for deal (by created_at desc)."""
        raise NotImplementedError


class SnapshotsRepository:
    def insert_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Insert an immutable snapshot; enforce idempotency by sha256_hash externally."""
        raise NotImplementedError

    def get_by_hash(self, sha256_hash: str) -> Optional[Dict[str, Any]]:
        """Fetch snapshot by hash (for idempotent export)."""
        raise NotImplementedError

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        """Fetch snapshot by id."""
        raise NotImplementedError

    def list_snapshots(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        """List snapshots for a deal."""
        raise NotImplementedError

    def get_latest_snapshot(self, deal_id: str) -> Optional[Dict[str, Any]]:
        """Fetch latest snapshot for deal (by created_at desc)."""
        raise NotImplementedError
