from decimal import Decimal
from types import SimpleNamespace

from app.services.ai.pricing import calculate_token_cost, extract_usage


def test_extract_deepseek_usage_details():
    assert extract_usage({
        "usage": {
            "prompt_tokens": 100,
            "completion_tokens": 30,
            "total_tokens": 130,
            "prompt_tokens_details": {"cached_tokens": 40},
            "completion_tokens_details": {"reasoning_tokens": 10},
        }
    }) == {
        "input_tokens": 100,
        "output_tokens": 30,
        "cached_input_tokens": 40,
        "reasoning_tokens": 10,
        "total_tokens": 130,
    }


def test_calculate_cost_uses_cache_and_decimal_precision():
    price = SimpleNamespace(
        unit_tokens=1_000_000,
        input_price=Decimal("1"),
        cached_input_price=Decimal("0.02"),
        output_price=Decimal("2"),
        reasoning_price=Decimal("0"),
    )
    usage = {
        "input_tokens": 1_000_000,
        "output_tokens": 100_000,
        "cached_input_tokens": 400_000,
        "reasoning_tokens": 50_000,
        "total_tokens": 1_100_000,
    }
    assert calculate_token_cost(usage, price) == Decimal("0.80800000")


def test_missing_price_is_zero_not_estimated():
    usage = {key: 1 for key in (
        "input_tokens", "output_tokens", "cached_input_tokens", "reasoning_tokens", "total_tokens"
    )}
    assert calculate_token_cost(usage, None) == Decimal("0")
