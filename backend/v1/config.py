"""
Parity v1 — Canonical version constants.

These are the single source of truth for version strings used in
analysis_runs, snapshot payloads, and the system identity endpoint.
"""

import os
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0.0"
CONFIG_VERSION = "1.0.0"

GIT_COMMIT = os.getenv("GIT_COMMIT") or None
BUILD_TIMESTAMP = os.getenv("BUILD_TIMESTAMP") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
DETERMINISTIC_MODE = True
