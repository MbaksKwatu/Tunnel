import uuid
from typing import Any, Dict, Optional

from ..parsing import parse_file
from ..parsing.errors import InvalidSchemaError, CurrencyMismatchError
from ..parsing.common import canonical_hash, sort_rows
from ..db.repositories import (
    AnalysisRunsRepository,
    DocumentsRepository,
    RawTransactionsRepository,
)


class IngestionResult(Dict[str, Any]):
    pass


class IngestionService:
    """
    Deterministic ingestion orchestrator for v1.

    Responsibilities:
    - Parse file deterministically (csv/xlsx/pdf) into canonical rows
    - Persist document and raw transactions via repositories
    - Return raw_transaction_hash and currency_detection
    """

    def __init__(
        self,
        documents_repo: DocumentsRepository,
        raw_tx_repo: RawTransactionsRepository,
        analysis_repo: Optional[AnalysisRunsRepository] = None,
    ):
        self.documents_repo = documents_repo
        self.raw_tx_repo = raw_tx_repo
        self.analysis_repo = analysis_repo

    def ingest(
        self,
        *,
        deal_id: str,
        created_by: str,
        file_bytes: bytes,
        file_name: str,
        file_type: str,
        deal_currency: str,
    ) -> IngestionResult:
        document_id = str(uuid.uuid4())

        # Parse deterministically
        rows, raw_hash, currency_detection = parse_file(file_bytes, file_type, document_id, deal_currency)

        # Persist document
        document = {
            "id": document_id,
            "deal_id": deal_id,
            "storage_url": f"inline://{file_name}",
            "file_type": file_type.lower(),
            "status": "completed",
            "currency_detected": None if currency_detection == "unknown" else currency_detection,
            "currency_mismatch": False,
        }
        self.documents_repo.create_document(document)

        # Persist rows
        for r in rows:
            r["document_id"] = document_id
            r["deal_id"] = deal_id
        self.raw_tx_repo.insert_batch(rows)

        # Optional: seed analysis_runs skeleton (LIVE_DRAFT placeholder without metrics)
        if self.analysis_repo:
            self.analysis_repo.insert_run(
                {
                    "id": str(uuid.uuid4()),
                    "deal_id": deal_id,
                    "state": "LIVE_DRAFT",
                    "schema_version": "v1",
                    "config_version": "v1",
                    "run_trigger": "parse_complete",
                    "non_transfer_abs_total_cents": 0,
                    "classified_abs_total_cents": 0,
                    "coverage_pct_bp": 0,
                    "missing_month_penalty_bp": 0,
                    "override_penalty_bp": 0,
                    "reconciliation_pct_bp": None,
                    "base_confidence_bp": 0,
                    "final_confidence_bp": 0,
                    "missing_month_count": 0,
                    "reconciliation_status": "NOT_RUN",
                    "tier": "Low",
                    "tier_capped": False,
                    "raw_transaction_hash": raw_hash,
                    "transfer_links_hash": canonical_hash([]),
                    "entities_hash": canonical_hash([]),
                    "overrides_hash": canonical_hash([]),
                }
            )

        return {
            "document_id": document_id,
            "rows_count": len(rows),
            "raw_transaction_hash": raw_hash,
            "currency_detection": currency_detection,
        }
