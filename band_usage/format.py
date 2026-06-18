"""Render subscription limits into a compact, band-friendly notification.

The Galaxy Fit 3 has a narrow screen, so lines are kept short: one header per
tool (with the soonest reset) and one bar line per window. Example::

    AI limits
    Claude .2h
    5h ██░░░░░░ 24%
    wk ████░░░░ 41%
    Codex .47m
    5h ██████░░ 62%
    wk ███░░░░░ 38%
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional, Tuple

from .models import ToolUsage


def bar(pct: Optional[float], width: int = 8) -> str:
    if pct is None:
        return "·" * width
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct / 100.0 * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def fmt_pct(pct: Optional[float]) -> str:
    return f"{pct:.0f}%" if pct is not None else "?"


def fmt_reset(resets_at: Optional[datetime], now: datetime) -> str:
    if resets_at is None:
        return ""
    secs = (resets_at - now).total_seconds()
    if secs <= 0:
        return "now"
    mins = int(secs // 60)
    if mins < 60:
        return f"{mins}m"
    hours = secs / 3600.0
    if hours < 48:
        return f"{int(round(hours))}h"
    return f"{int(round(hours / 24))}d"


def fmt_age(updated_at: Optional[datetime], now: datetime) -> str:
    """Human age, only when notably stale (>10 min). Empty otherwise."""
    if updated_at is None:
        return ""
    secs = (now - updated_at).total_seconds()
    if secs < 600:
        return ""
    mins = int(secs // 60)
    if mins < 60:
        return f"{mins}m old"
    hours = secs / 3600.0
    if hours < 48:
        return f"{int(round(hours))}h old"
    return f"{int(round(hours / 24))}d old"


def build_card(
    tools: List[ToolUsage],
    bar_width: int = 8,
    now: Optional[datetime] = None,
) -> Tuple[str, str]:
    """Return ``(title, body)`` for the notification."""
    now = now or datetime.now(timezone.utc)
    lines: List[str] = []

    for tool in tools:
        if not tool.available:
            lines.append(f"{tool.name}: {tool.note or 'no data'}")
            continue

        header = tool.name
        resets = [w.resets_at for w in tool.windows if w.resets_at]
        soonest = fmt_reset(min(resets), now) if resets else ""
        if soonest:
            header += f" .{soonest}"
        age = fmt_age(tool.updated_at, now)
        if age:
            header += f" ({age})"
        lines.append(header)

        for w in tool.windows:
            lines.append(f"{w.label} {bar(w.used_percent, bar_width)} {fmt_pct(w.used_percent)}")

    return "AI limits", "\n".join(lines)
