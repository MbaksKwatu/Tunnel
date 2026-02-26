"""
Parity v1 — Golden hash sentinel.

Fixed fixture → deterministic sha256_hash. If this hash changes, CI fails.
Strongest determinism lock possible.
"""

import hashlib
import os
import sys
import unittest

_BACKEND = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
_ROOT = os.path.abspath(os.path.join(_BACKEND, os.pardir))
for p in (_BACKEND, _ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

from backend.v1.config import SCHEMA_VERSION, CONFIG_VERSION
from backend.v1.core.pipeline import run_pipeline
from backend.v1.core.snapshot_engine import build_pds_payload, canonicalize_payload


def _txn(date, cents, desc, account="A", txn_id=None):
    tid = txn_id or hashlib.sha256(f"{date}|{account}|{cents}|{desc}".encode()).hexdigest()
    return {
        "txn_date": date,
        "signed_amount_cents": cents,
        "abs_amount_cents": abs(cents),
        "raw_descriptor": desc,
        "parsed_descriptor": desc.strip(),
        "normalized_descriptor": desc.strip().lower(),
        "account_id": account,
        "txn_id": tid,
        "is_transfer": False,
    }


# Fixed fixture — never modify. Hash must remain stable.
GOLDEN_FIXTURE = [
    _txn("2024-01-01", 25000, "Alpha Payment", "ACC-1", "s1"),
    _txn("2024-01-10", -8000, "Utility Bill", "ACC-1", "s2"),
    _txn("2024-02-01", 50000, "Client X", "ACC-2", "s3"),
    _txn("2024-02-15", -12000, "Office Rent", "ACC-2", "s4"),
    _txn("2024-03-01", 30000, "Client Y", "ACC-1", "s5"),
]

# Expected sha256_hash for GOLDEN_FIXTURE with current SCHEMA_VERSION/CONFIG_VERSION.
# If pipeline, snapshot_engine, or config changes, this must be updated explicitly.
GOLDEN_HASH_EXPECTED = "d78df82f93bdd10e6cca02f94d35d65fa7a59f3f269fe240656332b3cb57ac77"


class TestGoldenHashSentinel(unittest.TestCase):
    """Golden hash sentinel — deterministic lock."""

    def test_golden_hash_unchanged(self):
        """Fixed fixture must produce exact expected sha256_hash."""
        run, links, ents, txm = run_pipeline(
            deal_id="d-golden",
            raw_transactions=GOLDEN_FIXTURE,
            overrides=[],
            accrual={},
        )
        payload = build_pds_payload(
            schema_version=SCHEMA_VERSION,
            config_version=CONFIG_VERSION,
            deal_id="d-golden",
            currency="USD",
            raw_transactions=GOLDEN_FIXTURE,
            transfer_links=links,
            entities=ents,
            txn_entity_map=txm,
            metrics={
                "coverage_bp": run["coverage_pct_bp"],
                "missing_month_count": run["missing_month_count"],
                "missing_month_penalty_bp": run["missing_month_penalty_bp"],
                "reconciliation_status": run["reconciliation_status"],
                "reconciliation_bp": run["reconciliation_pct_bp"],
            },
            confidence={
                "final_confidence_bp": run["final_confidence_bp"],
                "tier": run["tier"],
                "tier_capped": run["tier_capped"],
                "override_penalty_bp": run["override_penalty_bp"],
            },
            overrides_applied=[],
        )
        _, sha = canonicalize_payload(payload)
        self.assertEqual(
            sha,
            GOLDEN_HASH_EXPECTED,
            f"Golden hash changed. Pipeline/snapshot/config drift detected. "
            f"Got {sha} expected {GOLDEN_HASH_EXPECTED}. "
            f"Bump SCHEMA_VERSION and update GOLDEN_HASH_EXPECTED if intentional.",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
