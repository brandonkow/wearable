"""Approximate token pricing used to estimate cost.

Prices below are USD per **1 million** tokens (list/public prices). LLM prices
change often, so treat the cost numbers as estimates. Override any model in
your config file under ``"pricing_overrides"`` (also per-million) or edit this
table directly.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    """Per-token prices (USD)."""

    input: float
    output: float
    cache_write: float
    cache_read: float


def per_million(
    input_: float,
    output_: float,
    cache_write: float | None = None,
    cache_read: float | None = None,
) -> ModelPrice:
    """Build a :class:`ModelPrice` from per-million-token figures."""
    cw = cache_write if cache_write is not None else input_ * 1.25
    cr = cache_read if cache_read is not None else input_ * 0.1
    return ModelPrice(input_ / 1e6, output_ / 1e6, cw / 1e6, cr / 1e6)


# Keyed by a lowercase substring matched against the model id. The longest
# matching key wins (so "gpt-5-codex" beats "gpt-5").
PRICING: dict[str, ModelPrice] = {
    # Anthropic / Claude
    "opus": per_million(15, 75, 18.75, 1.50),
    "sonnet": per_million(3, 15, 3.75, 0.30),
    "haiku": per_million(1.0, 5.0, 1.25, 0.10),
    # OpenAI / Codex
    "gpt-5-codex": per_million(1.25, 10, 1.5625, 0.125),
    "gpt-5-mini": per_million(0.25, 2.0),
    "gpt-5": per_million(1.25, 10),
    "o4-mini": per_million(1.1, 4.4),
    "gpt-4.1": per_million(2.0, 8.0),
    "gpt-4o": per_million(2.5, 10.0),
}

# Fallback for unknown models (~Sonnet-class).
DEFAULT_PRICE = per_million(3, 15)


def price_for(model: str, overrides: dict[str, ModelPrice] | None = None) -> ModelPrice:
    """Return the best matching :class:`ModelPrice` for ``model``."""
    name = (model or "").lower()
    tables = []
    if overrides:
        tables.append(overrides)
    tables.append(PRICING)
    best: tuple[str, ModelPrice] | None = None
    for table in tables:
        for key, mp in table.items():
            if key.lower() in name and (best is None or len(key) > len(best[0])):
                best = (key, mp)
        if best is not None:
            return best[1]
    return DEFAULT_PRICE
