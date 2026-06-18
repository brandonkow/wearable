#!/usr/bin/env python3
"""Claude Code statusline hook that captures subscription limits.

Claude Code passes a JSON payload on stdin to the statusline command. For
Pro/Max accounts that payload includes a ``rate_limits`` block with
``five_hour`` / ``seven_day`` windows (``used_percentage`` + ``resets_at``)
after the first API response in a session. Those numbers are never written to
disk by Claude Code, so this script:

  1. caches them to ``~/.claude/usage-cache.json`` (so band_usage can read
     them), merging with the last-known values when a window is absent, and
  2. prints a short status line back to Claude Code.

Register it in ``~/.claude/settings.json``::

    {
      "statusLine": {
        "type": "command",
        "command": "python3 /ABSOLUTE/PATH/TO/statusline/band_statusline.py"
      }
    }

Override the cache location with the ``BAND_USAGE_CLAUDE_CACHE`` env var.
This script is intentionally dependency-free and standalone.
"""

import json
import os
import sys
from datetime import datetime, timezone

CACHE = os.environ.get(
    "BAND_USAGE_CLAUDE_CACHE", os.path.expanduser("~/.claude/usage-cache.json")
)


def find_key(obj, key):
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


def load_cache():
    try:
        with open(CACHE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def main():
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        payload = {}

    rate_limits = find_key(payload, "rate_limits")
    cache = load_cache()
    updated = False

    if isinstance(rate_limits, dict):
        for key in ("five_hour", "seven_day"):
            window = rate_limits.get(key)
            if not isinstance(window, dict):
                continue
            used = window.get("used_percentage")
            if used is None:
                used = window.get("used_percent")
            if used is None:
                continue
            cache[key] = {"used_percent": used, "resets_at": window.get("resets_at")}
            updated = True

    if updated:
        cache["updated_at"] = (
            datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        )
        try:
            os.makedirs(os.path.dirname(CACHE) or ".", exist_ok=True)
            with open(CACHE, "w", encoding="utf-8") as fh:
                json.dump(cache, fh)
        except OSError:
            pass

    def pct(key):
        window = cache.get(key) or {}
        value = window.get("used_percent")
        return f"{value:.0f}%" if isinstance(value, (int, float)) else "-"

    model = find_key(payload, "display_name") or "Claude"
    sys.stdout.write(f"{model} | 5h {pct('five_hour')} · wk {pct('seven_day')}")


if __name__ == "__main__":
    main()
