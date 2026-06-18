"""Read Claude Code's subscription limits from the statusline cache.

Claude Code does NOT persist the 5-hour / weekly limit percentages to its
JSONL session logs — that data is only handed to a statusline script at
runtime (fields ``rate_limits.five_hour`` / ``rate_limits.seven_day`` with
``used_percentage`` + ``resets_at``). The bundled statusline hook
(``statusline/band_statusline.py``) captures it into a small cache file that
we read here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .models import ToolUsage, limit_window
from .util import parse_ts

_SETUP_HINT = "no data - set up the statusline hook"

_WINDOWS = (("five_hour", "5h"), ("seven_day", "wk"))


def read_claude_usage(cache_path: str) -> ToolUsage:
    path = Path(os.path.expanduser(cache_path))
    if not path.exists():
        return ToolUsage("Claude", available=False, note=_SETUP_HINT)

    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return ToolUsage("Claude", available=False, note="cache unreadable")

    if not isinstance(data, dict):
        return ToolUsage("Claude", available=False, note="cache malformed")

    updated_at = parse_ts(data.get("updated_at"))
    windows = []
    for key, label in _WINDOWS:
        raw = data.get(key)
        if isinstance(raw, dict):
            windows.append(limit_window(raw, label, updated_at))

    if not windows:
        return ToolUsage("Claude", available=False, note="no limit data yet")

    return ToolUsage("Claude", windows=windows, updated_at=updated_at)
