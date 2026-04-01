import logging
from typing import Any, Dict, Iterable, List, Optional, Sequence

from ..core.snapshot_engine import decode_snapshot_row
from .repositories import (
    AnalysisRunsRepository,
    DealsRepository,
    DocumentsRepository,
    EntitiesRepository,
    RawTransactionsRepository,
    SnapshotsRepository,
    TxnEntityMapRepository,
    TransferLinksRepository,
    OverridesRepository,
)
from .supabase_client import get_supabase

logger = logging.getLogger(__name__)

# PostgREST often caps a single response at ~1000 rows (Supabase API default). Requesting
# a huge limit in one call still returns at most that cap — so we must paginate.
_SELECT_PAGE_SIZE = 1000


class BaseRepo:
    def __init__(self, table: str):
        self.client = get_supabase()
        self.table = table

    def insert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        res = self.client.table(self.table).insert(data).execute()
        return res.data[0] if res.data else data

    def insert_many(self, data: Iterable[Dict[str, Any]]) -> None:
        items = list(data)
        if not items:
            return
        self.client.table(self.table).insert(items).execute()

    def select_eq(self, column: str, value: Any) -> List[Dict[str, Any]]:
        # Paginate: one .range(0, N) with a large N still hits the server max (~1000 rows).
        out: List[Dict[str, Any]] = []
        offset = 0
        while True:
            end = offset + _SELECT_PAGE_SIZE - 1
            res = (
                self.client.table(self.table)
                .select("*")
                .eq(column, value)
                .range(offset, end)
                .execute()
            )
            chunk = res.data or []
            out.extend(chunk)
            if len(chunk) < _SELECT_PAGE_SIZE:
                break
            offset += _SELECT_PAGE_SIZE
            if offset > 2_000_000:
                logger.warning(
                    "select_eq pagination exceeded 2M rows (table=%s %s=...)",
                    self.table,
                    column,
                )
                break
        return out

    def delete_eq(self, column: str, value: Any) -> None:
        self.client.table(self.table).delete().eq(column, value).execute()


class DealsRepo(DealsRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_deals")

    def create_deal(self, deal: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert(deal)

    def get_deal(self, deal_id: str) -> Optional[Dict[str, Any]]:
        rows = self.select_eq("id", deal_id)
        return rows[0] if rows else None

    def list_deals(self, created_by: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("created_by", created_by)


class DocumentsRepo(DocumentsRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_documents")

    def create_document(self, document: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert(document)

    def get_batch_upload_count(self, deal_id: str) -> int:
        """Distinct batch_number count for a deal (RPC when available, else local count)."""
        try:
            res = self.client.rpc(
                "get_deal_batch_count", {"p_deal_id": deal_id}
            ).execute()
            d = res.data
            if d is None:
                return 0
            if isinstance(d, int):
                return d
            if isinstance(d, list):
                if not d:
                    return 0
                x = d[0]
                if isinstance(x, dict):
                    return int(next(iter(x.values())))
                return int(x)
            return int(d)
        except Exception as exc:
            logger.warning(
                "get_deal_batch_count RPC failed for deal %s: %s", deal_id, exc
            )
            rows = self.list_by_deal(deal_id)
            batches = {
                r.get("batch_number")
                for r in rows
                if r.get("batch_number") is not None
            }
            return len(batches)

    def update_status(
        self,
        document_id: str,
        status: str,
        *,
        currency_mismatch: bool = False,
        error_message: Optional[str] = None,
        error_type: Optional[str] = None,
        error_stage: Optional[str] = None,
        next_action: Optional[str] = None,
        analytics: Optional[Dict[str, Any]] = None,
        currency_detected: Optional[str] = None,
    ) -> None:
        data: Dict[str, Any] = {"status": status, "currency_mismatch": currency_mismatch}
        if error_message is not None:
            data["error_message"] = error_message
        if error_type is not None:
            data["error_type"] = error_type
        if error_stage is not None:
            data["error_stage"] = error_stage
        if next_action is not None:
            data["next_action"] = next_action
        if analytics is not None:
            data["analytics"] = analytics
        if currency_detected is not None:
            data["currency_detected"] = currency_detected
        self.client.table(self.table).update(data).eq("id", document_id).execute()

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        rows = self.select_eq("id", document_id)
        return rows[0] if rows else None

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("deal_id", deal_id)

    def get_latest_update_at(self, deal_id: str) -> Optional[str]:
        rows = self.select_eq("deal_id", deal_id)
        if not rows:
            return None
        return max((r.get("created_at") or "") for r in rows)


BATCH_SIZE = 1000


class RawTxRepo(RawTransactionsRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_raw_transactions")

    def insert_batch(self, rows: Iterable[Dict[str, Any]]) -> None:
        items = list(rows)
        if not items:
            return
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            self.client.table(self.table).insert(batch).execute()

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("deal_id", deal_id)

    def list_by_document(self, document_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("document_id", document_id)


class TransferLinksRepo(TransferLinksRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_transfer_links")

    def insert_batch(self, links: Iterable[Dict[str, Any]]) -> None:
        items = list(links)
        if not items:
            return
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            self.client.table(self.table).insert(batch).execute()

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("deal_id", deal_id)


class EntitiesRepo(EntitiesRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_entities")

    def upsert_entities(self, entities: Iterable[Dict[str, Any]]) -> None:
        items = list(entities)
        if not items:
            return
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            self.client.table(self.table).upsert(batch).execute()

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("deal_id", deal_id)


class TxnEntityMapRepo(TxnEntityMapRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_txn_entity_map")

    def upsert_mappings(self, mappings: Iterable[Dict[str, Any]]) -> None:
        items = list(mappings)
        if not items:
            return
        for i in range(0, len(items), BATCH_SIZE):
            batch = items[i : i + BATCH_SIZE]
            self.client.table(self.table).upsert(batch).execute()

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("deal_id", deal_id)


class OverridesRepo(OverridesRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_overrides")

    def insert_override(self, override: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert(override)

    def list_overrides(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("deal_id", deal_id)

    def get_latest_update_at(self, deal_id: str) -> Optional[str]:
        rows = self.select_eq("deal_id", deal_id)
        if not rows:
            return ""
        return max((r.get("created_at") or "") for r in rows)


class AnalysisRunsRepo(AnalysisRunsRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_analysis_runs")

    def insert_run(self, run: Dict[str, Any]) -> Dict[str, Any]:
        return self.insert(run)

    def list_runs(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("deal_id", deal_id)

    def get_latest_run(self, deal_id: str) -> Optional[Dict[str, Any]]:
        rows = self.select_eq("deal_id", deal_id)
        if not rows:
            return None
        return max(rows, key=lambda r: r.get("created_at") or "")


class SnapshotsRepo(SnapshotsRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_snapshots")

    def insert_snapshot(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        existing = self.get_by_hash(snapshot.get("sha256_hash", ""))
        if existing:
            return existing
        inserted = self.insert(snapshot)
        return decode_snapshot_row(inserted) or inserted

    def get_by_hash(self, sha256_hash: str) -> Optional[Dict[str, Any]]:
        rows = self.select_eq("sha256_hash", sha256_hash)
        if not rows:
            return None
        return decode_snapshot_row(rows[0])

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        rows = self.select_eq("id", snapshot_id)
        if not rows:
            return None
        return decode_snapshot_row(rows[0])

    def list_snapshots(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        rows = self.select_eq("deal_id", deal_id)
        return [decode_snapshot_row(r) or r for r in rows]

    def get_latest_snapshot(self, deal_id: str) -> Optional[Dict[str, Any]]:
        rows = self.select_eq("deal_id", deal_id)
        if not rows:
            return None
        latest = max(rows, key=lambda r: r.get("created_at") or "")
        return decode_snapshot_row(latest)
