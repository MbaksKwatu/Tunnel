import logging
import time
import traceback
import uuid
from typing import Any, Dict, Optional

from ..config import SCHEMA_VERSION, CONFIG_VERSION
from ..parsing import parse_file
from ..parsing.errors import InvalidSchemaError, CurrencyMismatchError
from ..parsing.common import canonical_hash, sort_rows
from ..errors import is_dev_diagnostics
from ..db.repositories import (
    AnalysisRunsRepository,
    DocumentsRepository,
    RawTransactionsRepository,
)

logger = logging.getLogger(__name__)

# Ingestion stages (must match exactly for diagnostics)
STAGE_FILE_RECEIVED = "FILE_RECEIVED"
STAGE_PARSE_START = "PARSE_START"
STAGE_PARSE_DONE = "PARSE_DONE"
STAGE_SCHEMA_VALIDATED = "SCHEMA_VALIDATED"
STAGE_NORMALIZATION_DONE = "NORMALIZATION_DONE"
STAGE_DB_INSERT_START = "DB_INSERT_START"
STAGE_DB_INSERT_DONE = "DB_INSERT_DONE"
STAGE_STATUS_COMPLETED = "STATUS_COMPLETED"


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

    def _update_failed(
        self,
        document_id: str,
        error_type: str,
        error_message: str,
        stage: str,
        next_action: str,
        currency_mismatch: bool = False,
        exc: Optional[Exception] = None,
    ) -> None:
        tb_str = traceback.format_exc() if (is_dev_diagnostics() and exc) else None
        try:
            self.documents_repo.update_status(
                document_id,
                "failed",
                currency_mismatch=currency_mismatch,
                error_message=error_message,
                error_type=error_type,
                error_stage=stage,
                next_action=next_action,
            )
        except Exception:
            pass
        if tb_str:
            logger.debug("[INGEST] traceback (dev): %s", tb_str)

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
        On failure: updates status=failed with structured error taxonomy.
        """
        stage = STAGE_FILE_RECEIVED
        try:
            stage = STAGE_PARSE_START
            logger.info("[INGEST] stage=%s document_id=%s", stage, document_id)
            parse_start = time.perf_counter()
            rows, raw_hash, currency_detection = parse_file(
                file_bytes, file_type, document_id, deal_currency
            )
            parse_end = time.perf_counter()
            parse_ms = int((parse_end - parse_start) * 1000)
            stage = STAGE_PARSE_DONE
            logger.info("[INGEST] stage=%s rows=%d parse_ms=%d", stage, len(rows), parse_ms)

            stage = STAGE_SCHEMA_VALIDATED
            logger.info("[INGEST] stage=%s rows=%d", stage, len(rows))

            stage = STAGE_NORMALIZATION_DONE
            for r in rows:
                r["document_id"] = document_id
                r["deal_id"] = deal_id
                r.pop("abs_amount_cents", None)

            stage = STAGE_DB_INSERT_START
            logger.info("[INGEST] stage=%s rows=%d", stage, len(rows))
            db_insert_start = time.perf_counter()
            self.raw_tx_repo.insert_batch(rows)
            db_insert_end = time.perf_counter()
            insert_ms = int((db_insert_end - db_insert_start) * 1000)
            stage = STAGE_DB_INSERT_DONE
            logger.info("[INGEST] stage=%s rows=%d insert_ms=%d", stage, len(rows), insert_ms)

            self.documents_repo.update_status(
                document_id,
                "completed",
                currency_mismatch=False,
            )
            stage = STAGE_STATUS_COMPLETED

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

            logger.info("[INGEST] rows=%d parse_ms=%d insert_ms=%d", len(rows), parse_ms, insert_ms)
        except CurrencyMismatchError as exc:
            logger.warning("[INGEST] background currency mismatch stage=%s", stage)
            self._update_failed(
                document_id,
                error_type="CurrencyMismatchError",
                error_message=str(exc),
                stage=stage,
                next_action="fix_currency",
                currency_mismatch=True,
                exc=exc,
            )
        except InvalidSchemaError as exc:
            logger.warning("[INGEST] background invalid schema stage=%s: %s", stage, exc)
            currency_mismatch = "currency mismatch" in str(exc).lower()
            self._update_failed(
                document_id,
                error_type="SchemaValidationError",
                error_message=str(exc),
                stage=stage,
                next_action="fix_csv_header",
                currency_mismatch=currency_mismatch,
                exc=exc,
            )
        except Exception as exc:
            logger.exception("[INGEST] background failed stage=%s: %s", stage, exc)
            self._update_failed(
                document_id,
                error_type=exc.__class__.__name__,
                error_message=str(exc),
                stage=stage,
                next_action="retry_or_contact_support",
                currency_mismatch=False,
                exc=exc,
            )
