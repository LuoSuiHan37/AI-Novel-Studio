"""Approximate USD cost per 1M tokens. Values are estimates for budgeting, not invoices."""

from __future__ import annotations

# (input_per_1m, output_per_1m)
_MODEL_RATES: dict[str, tuple[float, float]] = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1": (2.00, 8.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "text-embedding-3-small": (0.02, 0.0),
    "text-embedding-3-large": (0.13, 0.0),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-haiku-4": (0.80, 4.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-1.5-flash": (0.075, 0.30),
    "gemini-1.5-pro": (1.25, 5.00),
    "gemini-embedding": (0.15, 0.0),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
}


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    rates = _lookup_rates(model)
    if rates is None:
        return 0.0
    input_rate, output_rate = rates
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000


def _lookup_rates(model: str) -> tuple[float, float] | None:
    key = model.strip().lower()
    if key in _MODEL_RATES:
        return _MODEL_RATES[key]
    matches = [pair for name, pair in _MODEL_RATES.items() if name in key or key.startswith(name)]
    if len(matches) == 1:
        return matches[0]
    return None
