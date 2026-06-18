"""Render aggregated usage into a compact, band-friendly notification.

The Galaxy Fit 3 shows a short title and a few lines of body, so we keep things
tight: one line per tool, an optional progress bar against a budget, and a
total. Emojis are sent via ntfy "tags" (the Title header must stay ASCII)."""

from __future__ import annotations

from typing import Dict, Optional, Tuple

from .models import Totals


def human_tokens(n: float) -> str:
    n = float(n)
    if n >= 1e9:
        return f"{n / 1e9:.1f}B"
    if n >= 1e6:
        return f"{n / 1e6:.1f}M"
    if n >= 1e3:
        return f"{n / 1e3:.1f}k"
    return f"{int(n)}"


def fmt_usd(x: float) -> str:
    return f"${x:,.2f}"


def progress_bar(pct: float, width: int = 10) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(pct / 100.0 * width))
    filled = max(0, min(width, filled))
    return "█" * filled + "░" * (width - filled)


def build_message(
    claude: Totals,
    codex: Totals,
    window_label: str,
    budgets: Optional[Dict[str, Optional[float]]] = None,
) -> Tuple[str, str]:
    """Return ``(title, body)`` for the notification."""
    budgets = budgets or {}
    title = f"AI usage - {window_label}"
    lines = []

    for name, budget_key, totals in (
        ("Claude", "claude_usd", claude),
        ("Codex", "codex_usd", codex),
    ):
        budget = budgets.get(budget_key)
        if budget and budget > 0:
            pct = min(100.0, totals.cost / budget * 100.0)
            lines.append(f"{name} {fmt_usd(totals.cost)}/{fmt_usd(budget)} {pct:.0f}%")
            lines.append(progress_bar(pct))
        else:
            lines.append(
                f"{name} {human_tokens(totals.total_tokens)} tok - {fmt_usd(totals.cost)}"
            )

    lines.append(f"Total {fmt_usd(claude.cost + codex.cost)}")
    return title, "\n".join(lines)
