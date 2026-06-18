"""Time-window handling for usage records."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple


def window_start(window: str, now: Optional[datetime] = None) -> Tuple[Optional[datetime], str]:
    """Resolve a window spec to (start_datetime_utc, human_label).

    Supported: ``all``, ``today``, ``week``, or ``<N>h`` / ``<N>d``
    (e.g. ``5h``, ``7d``). Falls back to a rolling 5h window, which mirrors
    Claude's rate-limit reset cadence.
    """
    now = now or datetime.now(timezone.utc)
    w = (window or "").strip().lower()

    if w in ("all", "alltime", "all-time"):
        return None, "all time"

    if w == "today":
        local_midnight = (
            datetime.now()
            .astimezone()
            .replace(hour=0, minute=0, second=0, microsecond=0)
        )
        return local_midnight.astimezone(timezone.utc), "today"

    if w in ("week", "weekly", "7d"):
        return now - timedelta(days=7), "last 7d"

    m = re.fullmatch(r"(\d+)\s*([hd])", w)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        delta = timedelta(hours=n) if unit == "h" else timedelta(days=n)
        return now - delta, f"last {n}{unit}"

    return now - timedelta(hours=5), "last 5h"
