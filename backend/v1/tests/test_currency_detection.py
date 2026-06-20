"""
Tests for currency detection persistence — DealsRepo.set_currency_if_unset.
Mocks the Supabase client; does not hit the real DB.
"""
import os
import sys
from unittest.mock import MagicMock

# Ensure backend/ is on sys.path so v1.* package imports resolve correctly
_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

# Stub get_supabase before importing the module so BaseRepo.__init__ doesn't
# attempt a real connection at import time.
import v1.db.supabase_client as _supabase_client_mod
_supabase_client_mod.get_supabase = MagicMock(return_value=MagicMock())

from v1.db.supabase_repositories import DealsRepo  # noqa: E402


# ── helpers ───────────────────────────────────────────────────────────────────

def _make_repo(current_currency, currency_source="default"):
    """Return a DealsRepo with a mocked Supabase client and a fixed deal row."""
    mock_client = MagicMock()
    _supabase_client_mod.get_supabase = MagicMock(return_value=mock_client)
    repo = DealsRepo()
    repo.get_deal = MagicMock(return_value={
        "id": "deal-abc",
        "currency": current_currency,
        "currency_source": currency_source,
    })
    repo.client = mock_client
    return repo, mock_client


# ── tests ─────────────────────────────────────────────────────────────────────

def test_sets_currency_when_source_is_default_and_currency_none():
    repo, mock_client = _make_repo(None, "default")
    repo.set_currency_if_unset("deal-abc", "KES")
    mock_client.table.return_value.update.assert_called_once_with(
        {"currency": "KES", "currency_source": "detected"}
    )


def test_sets_currency_when_source_is_default_and_currency_usd():
    repo, mock_client = _make_repo("USD", "default")
    repo.set_currency_if_unset("deal-abc", "KES")
    mock_client.table.return_value.update.assert_called_once_with(
        {"currency": "KES", "currency_source": "detected"}
    )


def test_corrects_kes_placeholder_when_source_is_default():
    """
    Regression test for the PR #16 interaction: deals now default to currency='KES',
    currency_source='default' at creation. A real document detecting a different
    currency must still correct it — the literal string 'KES' must never by itself
    block correction.
    """
    repo, mock_client = _make_repo("KES", "default")
    repo.set_currency_if_unset("deal-abc", "UGX")
    mock_client.table.return_value.update.assert_called_once_with(
        {"currency": "UGX", "currency_source": "detected"}
    )


def test_does_not_overwrite_once_source_is_detected():
    repo, mock_client = _make_repo("UGX", "detected")
    repo.set_currency_if_unset("deal-abc", "USD")
    mock_client.table.return_value.update.assert_not_called()


def test_does_not_overwrite_kes_once_source_is_detected():
    repo, mock_client = _make_repo("KES", "detected")
    repo.set_currency_if_unset("deal-abc", "UGX")
    mock_client.table.return_value.update.assert_not_called()


def test_full_lifecycle_default_then_locked():
    """
    The exact regression scenario PR #16 would have shipped blind:
    1. Deal created with currency='KES', currency_source='default' (new creation default).
    2. First real document detects 'UGX' — deal must update to UGX and lock as 'detected'.
    3. A second document detects a different currency — must NOT change again.
    """
    repo, mock_client = _make_repo("KES", "default")

    repo.set_currency_if_unset("deal-abc", "UGX")
    mock_client.table.return_value.update.assert_called_once_with(
        {"currency": "UGX", "currency_source": "detected"}
    )

    # Simulate the row now reflecting the update that just happened.
    repo.get_deal.return_value = {
        "id": "deal-abc",
        "currency": "UGX",
        "currency_source": "detected",
    }
    mock_client.table.return_value.update.reset_mock()

    repo.set_currency_if_unset("deal-abc", "TZS")
    mock_client.table.return_value.update.assert_not_called()
