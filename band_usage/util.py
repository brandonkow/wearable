"""Small shared helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional


def parse_ts(value: Any) -> Optional[datetime]:
    """Parse a timestamp into an aware UTC datetime, or None if not parseable.

    Accepts ISO-8601 strings (with or without a trailing ``Z``) and numeric
    unix epoch seconds.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if not isinstance(value, str):
        return None
    s = value.strip()
    if not s:
        return None
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def find_key(obj: Any, key: str) -> Any:
    """Depth-first search for the first value stored under ``key`` in nested
    dict/list structures. Returns None when not found."""
    stack = [obj]
    while stack:
        cur = stack.pop()
        if isinstance(cur, dict):
            if key in cur:
                return cur[key]
            stack.extend(cur.values())
        elif isinstance(cur, list):
            stack.extend(cur)
    return None
