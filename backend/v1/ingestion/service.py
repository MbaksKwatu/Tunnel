import logging
import time
import uuid
from typing import Any, Dict, Optional

from ..config import SCHEMA_VERSION, CONFIG_VERSION
from ..parsing import parse_file
from ..parsing.errors import InvalidSchemaError, CurrencyMismatchError
from ..parsing.common import canonical_hash, sort_rows
from ..db.repositories import (
    AnalysisRunsRepository,
    DocumentsRepository,
    RawTransactionsRepository,
)

logger = logging.getLogger(__name__)


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
        parse_start = time.perf_counter()
        try:
            rows, raw_hash, currency_detection = parse_file(file_bytes, file_type, document_id, deal_currency)
        except CurrencyMismatchError:
            raise
        except InvalidSchemaError:
            raise
        except Exception as exc:
            raise InvalidSchemaError(str(exc)) from exc
        parse_end = time.perf_counter()
        parse_ms = int((parse_end - parse_start) * 1000)

        # Persist document
        document = {
            "id": document_id,
            "deal_id": deal_id,
            "storage_url": f"inline://{file_name}",
            "file_type": file_type.lower(),
            "status": "completed",
            "currency_detected": None if currency_detection == "unknown" else currency_detection,
            "currency_mismatch": False,
            "created_by": created_by,
        }
        self.documents_repo.create_document(document)

        # Persist rows (strip abs_amount_cents — it's a DB generated column)
        for r in rows:
            r["document_id"] = document_id
            r["deal_id"] = deal_id
            r.pop("abs_amount_cents", None)

        db_insert_start = time.perf_counter()
        self.raw_tx_repo.insert_batch(rows)
        db_insert_end = time.perf_counter()
        insert_ms = int((db_insert_end - db_insert_start) * 1000)

        logger.info("[INGEST] rows=%d parse_ms=%d insert_ms=%d", len(rows), parse_ms, insert_ms)

        # Optional: seed analysis_runs skeleton (LIVE_DRAFT placeholder without metrics)
        if self.analysis_repo:
            self.analysis_repo.insert_run(
                {
                    "id": str(uuid.uuid4()),
                    "deal_id": deal_id,
                    "state": "LIVE_DRAFT",
                    "schema_version": SCHEMA_VERSION,
                    "config_version": CONFIG_VERSION,
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

    def process_document_background(
        self,
        *,
        document_id: str,
        deal_id: str,
        created_by: str,
        file_bytes: bytes,
        file_name: str,
        file_type: str,
        deal_currency: str,
    ) -> None:
        """
        Process document in background. Document must already exist with status=processing.
        On success: updates status=completed, inserts rows, inserts analysis run.
        On failure: updates status=failed.
        """
        try:
            parse_start = time.perf_counter()
            rows, raw_hash, currency_detection = parse_file(
                file_bytes, file_type, document_id, deal_currency
            )
            parse_end = time.perf_counter()
            parse_ms = int((parse_end - parse_start) * 1000)

            self.documents_repo.update_status(
                document_id,
                "completed",
                currency_mismatch=False,
            )
            # Update currency_detected if we have it (DocumentsRepo may not support; skip if not)
            # Schema has currency_detected; we'd need update_status to accept it. Keep minimal.

            for r in rows:
                r["document_id"] = document_id
                r["deal_id"] = deal_id
                r.pop("abs_amount_cents", None)

            db_insert_start = time.perf_counter()
            self.raw_tx_repo.insert_batch(rows)
            db_insert_end = time.perf_counter()
            insert_ms = int((db_insert_end - db_insert_start) * 1000)

            logger.info("[INGEST] rows=%d parse_ms=%d insert_ms=%d", len(rows), parse_ms, insert_ms)

            if self.analysis_repo:
                self.analysis_repo.insert_run(
                    {
                        "id": str(uuid.uuid4()),
                        "deal_id": deal_id,
                        "state": "LIVE_DRAFT",
                        "schema_version": SCHEMA_VERSION,
                        "config_version": CONFIG_VERSION,
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
        except CurrencyMismatchError:
            logger.warning("[INGEST] background currency mismatch")
            try:
                self.documents_repo.update_status(document_id, "failed", currency_mismatch=True)
            except Exception:
                pass
        except InvalidSchemaError as exc:
            logger.warning("[INGEST] background invalid schema: %s", exc)
            try:
                currency_mismatch = "currency mismatch" in str(exc).lower()
                self.documents_repo.update_status(document_id, "failed", currency_mismatch=currency_mismatch)
            except Exception:
                pass
        except Exception as exc:
            logger.exception("[INGEST] background failed: %s", exc)
            try:
                self.documents_repo.update_status(document_id, "failed", currency_mismatch=False)
            except Exception:
                pass
