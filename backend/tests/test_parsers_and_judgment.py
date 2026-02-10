import pytest

from backend.parsers import get_parser
from backend.judgment_engine import JudgmentEngine


@pytest.mark.asyncio
async def test_get_parser_supports_xls_alias():
    parser_xlsx = get_parser("xlsx")
    parser_xls = get_parser("xls")

    assert parser_xlsx is parser_xls


def test_judgment_alignment_uses_cashflow_weights():
    engine = JudgmentEngine()
    # dimension_scores are 0–100
    dimension_scores = {
        "financial": 100,
        "governance": 0,
        "team": 0,
        "market": 0,
    }

    class DummyThesis:
        def __init__(self):
            # 100% weight on cashflow -> maps to financial
            self.weights = {"cashflow": 100}

    thesis = DummyThesis()

    alignment = engine.calculate_alignment(dimension_scores, thesis)

    # With all weight on financial at 100, alignment should be at top end
    assert alignment == pytest.approx(100.0, rel=1e-3)

