"""Shared data types for usage records and aggregated totals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, Optional

from .pricing import ModelPrice, price_for


@dataclass
class UsageRecord:
    """A single billable interaction parsed from a CLI log."""

    timestamp: Optional[datetime]  # aware UTC, or None if unknown
    source: str  # "claude" | "codex"
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
        )

    def cost(self, overrides: Optional[Dict[str, ModelPrice]] = None) -> float:
        p = price_for(self.model, overrides)
        return (
            self.input_tokens * p.input
            + self.output_tokens * p.output
            + self.cache_creation_tokens * p.cache_write
            + self.cache_read_tokens * p.cache_read
        )


@dataclass
class Totals:
    """Aggregated usage for a set of records."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    cost: float = 0.0
    count: int = 0

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_creation_tokens
            + self.cache_read_tokens
        )

    @classmethod
    def of(
        cls,
        records: Iterable[UsageRecord],
        overrides: Optional[Dict[str, ModelPrice]] = None,
    ) -> "Totals":
        t = cls()
        for r in records:
            t.input_tokens += r.input_tokens
            t.output_tokens += r.output_tokens
            t.cache_creation_tokens += r.cache_creation_tokens
            t.cache_read_tokens += r.cache_read_tokens
            t.cost += r.cost(overrides)
            t.count += 1
        return t
