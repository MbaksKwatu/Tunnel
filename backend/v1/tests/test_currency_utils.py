"""
Tests for currency_utils.py — L2/L3 country → currency resolution.

Uses pycountry + babel.numbers.get_territory_currencies. No network calls.
"""
import os
import sys

import pytest

_backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from v1.integrations.currency_utils import country_to_currency, _resolve_alpha2


# ── All current Musa markets ───────────────────────────────────────────────────

class TestKnownMarkets:
    def test_kenya(self):
        assert country_to_currency("Kenya") == "KES"

    def test_kenya_lowercase(self):
        assert country_to_currency("kenya") == "KES"

    def test_kenya_uppercase(self):
        assert country_to_currency("KENYA") == "KES"

    def test_uganda(self):
        assert country_to_currency("Uganda") == "UGX"

    def test_rwanda(self):
        assert country_to_currency("Rwanda") == "RWF"

    def test_tanzania(self):
        assert country_to_currency("Tanzania") == "TZS"

    def test_nigeria(self):
        assert country_to_currency("Nigeria") == "NGN"

    def test_ghana(self):
        assert country_to_currency("Ghana") == "GHS"

    def test_ethiopia(self):
        assert country_to_currency("Ethiopia") == "ETB"

    def test_south_africa(self):
        assert country_to_currency("South Africa") == "ZAR"

    def test_zambia(self):
        assert country_to_currency("Zambia") == "ZMW"


# ── CFA zone disambiguation ────────────────────────────────────────────────────

class TestCFADisambiguation:
    def test_cameroon_returns_xaf(self):
        assert country_to_currency("Cameroon") == "XAF"

    def test_senegal_returns_xof(self):
        assert country_to_currency("Senegal") == "XOF"

    def test_ivory_coast_alias(self):
        assert country_to_currency("Ivory Coast") == "XOF"

    def test_cote_divoire_accent(self):
        assert country_to_currency("Côte d'Ivoire") == "XOF"

    def test_cote_divoire_no_accent(self):
        assert country_to_currency("cote divoire") == "XOF"

    def test_burkina_faso(self):
        assert country_to_currency("Burkina Faso") == "XOF"

    def test_mali(self):
        assert country_to_currency("Mali") == "XOF"

    def test_congo_republic(self):
        # Republic of Congo (Brazzaville) → XAF
        assert country_to_currency("Republic of the Congo") == "XAF"


# ── Accent / variant inputs ────────────────────────────────────────────────────

class TestVariantInputs:
    def test_kenya_with_leading_space(self):
        assert country_to_currency("  Kenya  ") == "KES"

    def test_rwanda_mixed_case(self):
        assert country_to_currency("rWaNdA") == "RWF"

    def test_tanzania_full_name(self):
        assert country_to_currency("United Republic of Tanzania") == "TZS"

    def test_nigeria_alpha3_code(self):
        # Alpha-3 code NGA → NG → NGN
        assert country_to_currency("NGA") == "NGN"

    def test_kenya_alpha2_code(self):
        assert country_to_currency("KE") == "KES"


# ── Address-style inputs ───────────────────────────────────────────────────────

class TestAddressInputs:
    def test_sanlam_house_nairobi_kenya(self):
        # Deed Technologies address case
        assert country_to_currency("Sanlam House, Nairobi, Kenya") == "KES"

    def test_lagos_address(self):
        assert country_to_currency("123 Main Street, Lagos") == "NGN"

    def test_city_comma_country(self):
        assert country_to_currency("Kampala, Uganda") == "UGX"

    def test_city_comma_country_ghana(self):
        assert country_to_currency("Accra, Ghana") == "GHS"


# ── Invalid inputs must raise ValueError ──────────────────────────────────────

class TestInvalidInputs:
    def test_wakanda_raises(self):
        with pytest.raises(ValueError, match="Cannot resolve country"):
            country_to_currency("Wakanda")

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="Cannot resolve country"):
            country_to_currency("")

    def test_unknown_code_raises(self):
        with pytest.raises(ValueError, match="Cannot resolve country"):
            country_to_currency("XYZ")

    def test_numeric_string_raises(self):
        with pytest.raises(ValueError, match="Cannot resolve country"):
            country_to_currency("12345")

    def test_gibberish_raises(self):
        with pytest.raises(ValueError, match="Cannot resolve country"):
            country_to_currency("zxqwerty")


# ── _resolve_alpha2 internal helper ───────────────────────────────────────────

class TestResolveAlpha2:
    def test_resolves_kenya(self):
        assert _resolve_alpha2(["Kenya"]) == "KE"

    def test_resolves_ivory_coast_alias(self):
        assert _resolve_alpha2(["Ivory Coast"]) == "CI"

    def test_resolves_last_segment_of_address(self):
        assert _resolve_alpha2(["", "Kenya"]) == "KE"

    def test_empty_list_returns_none(self):
        assert _resolve_alpha2([]) is None

    def test_unknown_returns_none(self):
        assert _resolve_alpha2(["Wakanda"]) is None
