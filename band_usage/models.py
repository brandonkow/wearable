"""Shared data types for subscription rate-limit windows."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from .util import parse_ts


@dataclass
class LimitWindow:
    """One plan-limit window (e.g. the 5-hour or weekly cap)."""

    label: str  # short label for the card, e.g. "5h" / "wk"
    used_percent: Optional[float]  # 0..100, or None if unknown
    resets_at: Optional[datetime]  # aware UTC, or None if unknown


@dataclass
class ToolUsage:
    """Subscription usage for one tool (Claude / Codex)."""

    name: str
    windows: List[LimitWindow] = field(default_factory=list)
    updated_at: Optional[datetime] = None  # when this snapshot was captured
    available: bool = True
    note: str = ""  # shown when not available


def limit_window(
    raw: Dict[str, Any], label: str, ref_ts: Optional[datetime]
) -> LimitWindow:
    """Build a :class:`LimitWindow` from a provider's window dict.

    Tolerates the different field names used by Claude (``used_percentage``)
    and Codex (``used_percent``), and resolves resets given either an absolute
    ``resets_at`` (epoch or ISO) or a relative ``resets_in_seconds``.
    """
    used = raw.get("used_percent")
    if used is None:
        used = raw.get("used_percentage")
    try:
        used_f: Optional[float] = float(used) if used is not None else None
    except (TypeError, ValueError):
        used_f = None

    resets: Optional[datetime] = None
    if raw.get("resets_at") is not None:
        resets = parse_ts(raw.get("resets_at"))
    elif raw.get("resets_in_seconds") is not None and ref_ts is not None:
        try:
            resets = ref_ts + timedelta(seconds=float(raw["resets_in_seconds"]))
        except (TypeError, ValueError):
            resets = None

    return LimitWindow(label=label, used_percent=used_f, resets_at=resets)
