from decimal import Decimal, ROUND_HALF_UP
from typing import Any


def extract_usage(payload: dict[str, Any]) -> dict[str, int]:
    usage = payload.get("usage") or {}
    prompt_details = usage.get("prompt_tokens_details") or {}
    completion_details = usage.get("completion_tokens_details") or {}
    return {
        "input_tokens": int(usage.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("completion_tokens") or 0),
        "cached_input_tokens": int(prompt_details.get("cached_tokens") or 0),
        "reasoning_tokens": int(completion_details.get("reasoning_tokens") or 0),
        "total_tokens": int(usage.get("total_tokens") or 0),
    }


def calculate_token_cost(usage: dict[str, int], price: Any | None) -> Decimal:
    if price is None:
        return Decimal("0")
    unit = Decimal(price.unit_tokens)
    normal_input = max(0, usage["input_tokens"] - usage["cached_input_tokens"])
    amount = (
        Decimal(normal_input) * price.input_price
        + Decimal(usage["cached_input_tokens"]) * price.cached_input_price
        + Decimal(usage["output_tokens"]) * price.output_price
        + Decimal(usage["reasoning_tokens"]) * price.reasoning_price
    ) / unit
    return amount.quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP)
