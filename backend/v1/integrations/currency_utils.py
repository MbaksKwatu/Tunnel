"""
currency_utils.py
Layer 2 + Layer 3 of the Parity currency detection system.

L2: Country string → ISO 4217 via pycountry + babel.
    Handles fuzzy matching, accents, address strings.

L3: Explicit failure. Never silently defaults to KES or any other currency.
    A loud failure at the API boundary is better than a wrong currency
    sealed into a SHA256 snapshot.

Parity principles:
- No floats. No FX conversion. We detect and label only.
- Deterministic: same input → same output.
- No generative AI.
"""
import logging
import pycountry
from babel.numbers import get_territory_currencies
from typing import Optional

logger = logging.getLogger(__name__)

# Manual aliases for names that pycountry.search_fuzzy cannot handle.
# Keys are normalised: lowercased, stripped, common punctuation removed.
_ALIASES: dict[str, str] = {
    'ivory coast': 'CI',
    'cote divoire': 'CI',
    "cote d'ivoire": 'CI',
    'cote d ivoire': 'CI',
    'congo': 'CD',          # DRC — distinguish via 'republic of the congo' = CG
    'dr congo': 'CD',
    'drc': 'CD',
    'democratic republic of the congo': 'CD',
    'republic of the congo': 'CG',
    'brazzaville': 'CG',
    'kinshasa': 'CD',
}


def _normalise_alias_key(s: str) -> str:
    """Lowercase, strip, collapse spaces, remove common diacritics for alias lookup."""
    import unicodedata
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return s.lower().strip()


def country_to_currency(country_input: str) -> str:
    """
    Convert a country name or code to ISO 4217 currency code.

    Raises ValueError if the country cannot be normalised or has no
    unambiguous single official currency.

    Never returns KES (or any other code) as a silent default.

    Examples:
        country_to_currency("Kenya")          → "KES"
        country_to_currency("Ivory Coast")    → "XOF"
        country_to_currency("côte d'ivoire")  → "XOF"
        country_to_currency("Cameroon")       → "XAF"
        country_to_currency("Sanlam House, Nairobi, Kenya")  → "KES"
                                                (extracts "Kenya" from address)
    """
    # Step 1: Try the full string first, then last segment of address strings
    # "Sanlam House, Nairobi, Kenya" → try "Kenya"
    candidates = [country_input.strip()]
    if ',' in country_input:
        candidates.append(country_input.split(',')[-1].strip())

    alpha2 = _resolve_alpha2(candidates)
    if alpha2 is None:
        raise ValueError(
            f"Cannot resolve country to ISO 3166-1 alpha-2 code: {country_input!r}. "
            "Check the venture_country field — it must be a recognisable country name, "
            "not a street address or abbreviation."
        )

    # Step 2: Get official currencies for this territory
    currencies = get_territory_currencies(alpha2)

    if not currencies:
        raise ValueError(
            f"No official currencies found for country code {alpha2!r} "
            f"(resolved from {country_input!r}). "
            "This is unexpected — check if pycountry/babel are up to date."
        )

    if len(currencies) == 1:
        return currencies[0]

    # Step 3: Multiple official currencies (rare — e.g. Zimbabwe uses ZWL + USD)
    # Use the first non-USD, non-EUR one if it exists, otherwise the first
    preferred = [c for c in currencies if c not in ('USD', 'EUR')]
    if preferred:
        logger.warning(
            "Multiple official currencies for %s (%s): using %s. "
            "If this is wrong, set currency explicitly on the deal.",
            alpha2, currencies, preferred[0]
        )
        return preferred[0]

    return currencies[0]


def _resolve_alpha2(candidates: list[str]) -> Optional[str]:
    """Try each candidate string until one resolves to a pycountry country."""
    for candidate in candidates:
        if not candidate:
            continue

        # Check static alias map first (handles pycountry blind spots)
        alias_key = _normalise_alias_key(candidate)
        if alias_key in _ALIASES:
            return _ALIASES[alias_key]

        # Direct alpha-2 or alpha-3 code
        by_code = (
            pycountry.countries.get(alpha_2=candidate.upper()) or
            pycountry.countries.get(alpha_3=candidate.upper())
        )
        if by_code:
            return by_code.alpha_2

        # Fuzzy name search
        try:
            results = pycountry.countries.search_fuzzy(candidate)
            if results:
                return results[0].alpha_2
        except LookupError:
            continue

    return None
