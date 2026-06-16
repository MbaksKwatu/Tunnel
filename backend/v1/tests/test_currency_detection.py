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

def _make_repo(current_currency):
    """Return a DealsRepo with a mocked Supabase client and a fixed deal row."""
    mock_client = MagicMock()
    _supabase_client_mod.get_supabase = MagicMock(return_value=mock_client)
    repo = DealsRepo()
    repo.get_deal = MagicMock(return_value={"id": "deal-abc", "currency": current_currency})
    repo.client = mock_client
    return repo, mock_client


# ── tests ─────────────────────────────────────────────────────────────────────

def test_sets_currency_when_deal_has_none():
    repo, mock_client = _make_repo(None)
    repo.set_currency_if_unset("deal-abc", "KES")
    mock_client.table.return_value.update.assert_called_once_with({"currency": "KES"})


def test_sets_currency_when_deal_is_usd_default():
    repo, mock_client = _make_repo("USD")
    repo.set_currency_if_unset("deal-abc", "KES")
    mock_client.table.return_value.update.assert_called_once_with({"currency": "KES"})


def test_does_not_overwrite_kes():
    repo, mock_client = _make_repo("KES")
    repo.set_currency_if_unset("deal-abc", "UGX")
    mock_client.table.return_value.update.assert_not_called()


def test_does_not_overwrite_ugx_with_non_kes():
    repo, mock_client = _make_repo("UGX")
    repo.set_currency_if_unset("deal-abc", "USD")
    mock_client.table.return_value.update.assert_not_called()


def test_kes_detected_overrides_ugx():
    """KES takes priority — a KES statement upgrades a UGX deal to KES."""
    repo, mock_client = _make_repo("UGX")
    repo.set_currency_if_unset("deal-abc", "KES")
    mock_client.table.return_value.update.assert_called_once_with({"currency": "KES"})
