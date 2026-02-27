from typing import Any, Dict, Iterable, List, Optional, Sequence

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
        res = self.client.table(self.table).select("*").eq(column, value).execute()
        return res.data or []

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
        self.insert_many(links)

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("deal_id", deal_id)


class EntitiesRepo(EntitiesRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_entities")

    def upsert_entities(self, entities: Iterable[Dict[str, Any]]) -> None:
        items = list(entities)
        if not items:
            return
        self.client.table(self.table).upsert(items).execute()

    def list_by_deal(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("deal_id", deal_id)


class TxnEntityMapRepo(TxnEntityMapRepository, BaseRepo):
    def __init__(self):
        super().__init__("pds_txn_entity_map")

    def upsert_mappings(self, mappings: Iterable[Dict[str, Any]]) -> None:
        items = list(mappings)
        if not items:
            return
        self.client.table(self.table).upsert(items).execute()

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
        return self.insert(snapshot)

    def get_by_hash(self, sha256_hash: str) -> Optional[Dict[str, Any]]:
        rows = self.select_eq("sha256_hash", sha256_hash)
        return rows[0] if rows else None

    def get_snapshot(self, snapshot_id: str) -> Optional[Dict[str, Any]]:
        rows = self.select_eq("id", snapshot_id)
        return rows[0] if rows else None

    def list_snapshots(self, deal_id: str) -> Sequence[Dict[str, Any]]:
        return self.select_eq("deal_id", deal_id)

    def get_latest_snapshot(self, deal_id: str) -> Optional[Dict[str, Any]]:
        rows = self.select_eq("deal_id", deal_id)
        if not rows:
            return None
        return max(rows, key=lambda r: r.get("created_at") or "")
