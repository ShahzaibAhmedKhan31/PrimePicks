from __future__ import annotations

import re

# Standard text-token prices in USD per million tokens. These are estimates;
# OpenAI pricing can change and may include cache or account-specific discounts.
MODEL_RATES_USD_PER_MILLION: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-nano": (0.10, 0.40),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "o4-mini": (1.10, 4.40),
    "o3-mini": (1.10, 4.40),
    "o3": (10.00, 40.00),
}


def get_model_rates(model: str) -> tuple[float, float] | None:
    """Return (input, output) USD-per-million rates for a known model ID."""
    normalized = model.strip().lower()
    for model_id, rates in MODEL_RATES_USD_PER_MILLION.items():
        if normalized == model_id or re.fullmatch(rf"{re.escape(model_id)}-\d{{4}}-\d{{2}}-\d{{2}}", normalized):
            return rates
    return None
