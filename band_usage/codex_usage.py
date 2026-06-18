"""Read Codex CLI subscription limits from its session logs.

Codex persists plan limits directly in ``~/.codex/sessions/**/rollout-*.jsonl``:
each ``token_count`` event carries a ``rate_limits`` block with ``primary``
(5-hour) and ``secondary`` (weekly) windows, each exposing ``used_percent`` and
a reset (``resets_at`` or ``resets_in_seconds``). We use the freshest snapshot
from the most recently modified session that contains one.

The schema has shifted across Codex versions, so ``rate_limits`` is located
with a tolerant depth-first search.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from .models import ToolUsage, limit_window
from .util import find_key, parse_ts

_WINDOWS = (("primary", "5h"), ("secondary", "wk"))


def _mtime(path: Path) -> float:
    try:
        return path.stat().st_mtime
    except OSError:
        return 0.0


def read_codex_usage(sessions_dir: str) -> ToolUsage:
    base = Path(os.path.expanduser(sessions_dir))
    if not base.exists():
        return ToolUsage("Codex", available=False, note="no sessions dir")

    files = sorted(base.rglob("*.jsonl"), key=_mtime, reverse=True)
    for path in files:
        latest = None
        latest_ts: Optional[datetime] = None
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rl = find_key(obj, "rate_limits")
                    if isinstance(rl, dict):
                        latest = rl
                        latest_ts = parse_ts(find_key(obj, "timestamp"))
        except OSError:
            continue

        if latest is not None:
            ref = latest_ts or datetime.fromtimestamp(_mtime(path), timezone.utc)
            windows = []
            for key, label in _WINDOWS:
                raw = latest.get(key)
                if isinstance(raw, dict):
                    windows.append(limit_window(raw, label, ref))
            if windows:
                return ToolUsage("Codex", windows=windows, updated_at=ref)

    return ToolUsage("Codex", available=False, note="no limit data in sessions")
