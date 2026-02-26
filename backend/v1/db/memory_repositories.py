"""
In-memory repository implementations for CI/test use.
No external dependencies (no Supabase, no SQLite).
"""

import copy
from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence

from .repositories import (
    AnalysisRunsRepository,
    DealsRepository,
    DocumentsRepository,
    EntitiesRepository,
    OverridesRepository,
    RawTransactionsRepository,
    SnapshotsRepository,
    TransferLinksRepository,
    TxnEntityMapRepository,
)


class MemoryDealsRepo(DealsRepository):
    def __init__(self):
        self._store: List[Dict[str, Any]] = []

    def create_deal(self, deal: Dict[str, Any]) -> Dict[str, Any]:
        row = {**deal, "created_at": deal.get("created_at") or datetime.utcnow().isoformat()}
        self._store.append(row)
        return copy.deepcopy(row)

    def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        for d in self._store:
            if d["id"] == deal_id:
                return copy.deepcopy(d)
        return None

    def list_deals(self, created_by: str) -> Sequence[Dict[str, Any]]:
        return [copy.deepcopy(d) for d in self._store if d.get("created_by") == created_by]


class MemoryDocumentsRepo(DocumentsRepository):
    def __init__(self):
        self._store: List[Dict[str, Any]] = []

    def create_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        row = {**document, "created_at": document.get("created_at") or datetime.utcnow().isoformat()}
        self._store.append(row)
        return copy.deepcopy(row)

    def update_status(self, document_id: str, status: str, *, currency_mismatch: bool = False) -> None:
        for d in self._store:
            if d["id"] == document_id:
                d["status"] = status
                d["currency_mismatch"] = currency_mismatch
                break

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return [copy.deepcopy(d) for d in self._store if d.get("deal_id") == deal_id]

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        for d in self._store:
            if d["id"] == document_id:
                return copy.deepcopy(d)
        return None


class MemoryRawTxRepo(RawTransactionsRepository):
    def __init__(self):
        self._store: List[Dict[str, Any]] = []

    def insert_batch(self, rows: Iterable[Dict[str, Any]]) -> None:
        for r in rows:
            self._store.append(copy.deepcopy(r))

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return [copy.deepcopy(r) for r in self._store if r.get("deal_id") == deal_id]

    def list_by_document(self, document_id: str) -> Sequence[Dict[str, Any]]:
        return [copy.deepcopy(r) for r in self._store if r.get("document_id") == document_id]


class MemoryTransferLinksRepo(TransferLinksRepository):
    def __init__(self):
        self._store: List[Dict[str, Any]] = []

    def insert_batch(self, links: Iterable[Dict[str, Any]]) -> None:
        for lnk in links:
            self._store.append(copy.deepcopy(lnk))

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return [copy.deepcopy(l) for l in self._store if l.get("deal_id") == deal_id]

    def delete_eq(self, column: str, value: Any) -> None:
        self._store = [l for l in self._store if l.get(column) != value]


class MemoryEntitiesRepo(EntitiesRepository):
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def upsert_entities(self, entities: Iterable[Dict[str, Any]]) -> None:
        for e in entities:
            self._store[e["entity_id"]] = copy.deepcopy(e)

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return [copy.deepcopy(e) for e in self._store.values() if e.get("deal_id") == deal_id]


class MemoryTxnEntityMapRepo(TxnEntityMapRepository):
    def __init__(self):
        self._store: Dict[str, Dict[str, Any]] = {}

    def upsert_mappings(self, mappings: Iterable[Dict[str, Any]]) -> None:
        for m in mappings:
            self._store[m["txn_id"]] = copy.deepcopy(m)

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return [copy.deepcopy(m) for m in self._store.values() if m.get("deal_id") == deal_id]

    def delete_eq(self, column: str, value: Any) -> None:
        self._store = {k: v for k, v in self._store.items() if v.get(column) != value}


class MemoryOverridesRepo(OverridesRepository):
    def __init__(self):
        self._store: List[Dict[str, Any]] = []

    def insert_override(self, override: Dict[str, Any]) -> Dict[str, Any]:
        row = {**override, "created_at": override.get("created_at") or datetime.utcnow().isoformat()}
        self._store.append(row)
        return copy.deepcopy(row)

    def list_overrides(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return [copy.deepcopy(o) for o in self._store if o.get("deal_id") == deal_id]


class MemoryAnalysisRunsRepo(AnalysisRunsRepository):
    def __init__(self):
        self._store: List[Dict[str, Any]] = []

    def insert_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        row = {**run, "created_at": run.get("created_at") or datetime.utcnow().isoformat()}
        self._store.append(row)
        return copy.deepcopy(row)

    def list_runs(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return [copy.deepcopy(r) for r in self._store if r.get("deal_id") == deal_id]


class MemorySnapshotsRepo(SnapshotsRepository):
    def __init__(self):
        self._store: List[Dict[str, Any]] = []

    def insert_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        # Idempotent on sha256_hash to mirror DB unique constraint
        existing = self.get_by_hash(snapshot.get("sha256_hash"))
        if existing:
            return existing
        row = {**snapshot, "created_at": snapshot.get("created_at") or datetime.utcnow().isoformat()}
        self._store.append(row)
        return copy.deepcopy(row)

    def get_by_hash(self, sha256_hash: str) -> Optional[Dict[str, Any]]:
        for s in self._store:
            if s.get("sha256_hash") == sha256_hash:
                return copy.deepcopy(s)
        return None

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        for s in self._store:
            if s["id"] == snapshot_id:
                return copy.deepcopy(s)
        return None

    def list_snapshots(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return [copy.deepcopy(s) for s in self._store if s.get("deal_id") == deal_id]


def build_memory_repos() -> Dict[str, Any]:
    return {
        "deals": MemoryDealsRepo(),
        "documents": MemoryDocumentsRepo(),
        "raw": MemoryRawTxRepo(),
        "links": MemoryTransferLinksRepo(),
        "entities": MemoryEntitiesRepo(),
        "txn_map": MemoryTxnEntityMapRepo(),
        "overrides": MemoryOverridesRepo(),
        "runs": MemoryAnalysisRunsRepo(),
        "snapshots": MemorySnapshotsRepo(),
    }
