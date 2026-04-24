"""
Parity v1 — Structured error taxonomy.
Every failure carries: error_type, message, stage, next_action.
Never leak tracebacks in production (use PARITY_DEV_DIAGNOSTICS=1 for dev).
"""

from typing import Optional


class ParityV1Error(Exception):
    """Base for all v1 structured errors."""

    def __init__(
        self,
        message: str,
        *,
        stage: str,
        next_action: str,
    ):
        super().__init__(message)
        self.error_type = self.__class__.__name__
        self.message = message
        self.stage = stage
        self.next_action = next_action

    def to_dict(self, include_traceback: bool = False) -> dict:
        out = {
            "error_type": self.error_type,
            "error_message": self.message,
            "stage": self.stage,
            "next_action": self.next_action,
        }
        if include_traceback:
            import traceback
            out["traceback"] = traceback.format_exc()
        return out


class FileUploadError(ParityV1Error):
    """File upload or read failed."""

    def __init__(self, message: str, stage: str = "FILE_RECEIVED", next_action: str = "retry_upload"):
        super().__init__(message, stage=stage, next_action=next_action)


class SchemaValidationError(ParityV1Error):
    """Uploaded file violates required schema (headers, columns)."""

    def __init__(self, message: str, stage: str = "SCHEMA_VALIDATED", next_action: str = "fix_csv_header"):
        super().__init__(message, stage=stage, next_action=next_action)


class DataValidationError(ParityV1Error):
    """Data content invalid (empty, bad values, etc)."""

    def __init__(self, message: str, stage: str = "NORMALIZATION_DONE", next_action: str = "fix_data"):
        super().__init__(message, stage=stage, next_action=next_action)


class AccrualValidationError(ParityV1Error):
    """Accrual parameters invalid."""

    def __init__(self, message: str, stage: str = "SCHEMA_VALIDATED", next_action: str = "fix_accrual"):
        super().__init__(message, stage=stage, next_action=next_action)


class NormalizationError(ParityV1Error):
    """Row normalization failed."""

    def __init__(self, message: str, stage: str = "NORMALIZATION_DONE", next_action: str = "fix_data"):
        super().__init__(message, stage=stage, next_action=next_action)


class PipelineStageError(ParityV1Error):
    """Pipeline stage failed."""

    def __init__(self, message: str, *, stage_name: str, next_action: str = "retry_or_contact_support"):
        super().__init__(message, stage=stage_name, next_action=next_action)


class MetricsComputationError(ParityV1Error):
    """Metrics computation failed."""

    def __init__(self, message: str, stage: str = "PIPELINE_DONE", next_action: str = "retry_or_contact_support"):
        super().__init__(message, stage=stage, next_action=next_action)


class SnapshotIntegrityError(ParityV1Error):
    """Snapshot build or integrity check failed."""

    def __init__(self, message: str, stage: str = "SNAPSHOT_BUILD_DONE", next_action: str = "retry_or_contact_support"):
        super().__init__(message, stage=stage, next_action=next_action)


class DatabaseInsertError(ParityV1Error):
    """Database insert failed."""

    def __init__(self, message: str, stage: str = "DB_INSERT_DONE", next_action: str = "retry_or_contact_support"):
        super().__init__(message, stage=stage, next_action=next_action)


def is_dev_diagnostics() -> bool:
    import os
    return os.environ.get("PARITY_DEV_DIAGNOSTICS", "").strip() in ("1", "true", "yes")


def format_failed_document_response(
    error_type: str,
    error_message: str,
    stage: str,
    next_action: str,
    traceback_str: Optional[str] = None,
) -> dict:
    out = {
        "error_type": error_type,
        "error_message": error_message,
        "stage": stage,
        "next_action": next_action,
    }
    if is_dev_diagnostics() and traceback_str:
        out["traceback"] = traceback_str
    return out
