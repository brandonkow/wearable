"""Parse Claude Code session logs (``~/.claude/projects/**/*.jsonl``).

Each line is a JSON event. Assistant turns carry a ``message.usage`` block with
``input_tokens``, ``output_tokens``, ``cache_creation_input_tokens`` and
``cache_read_input_tokens``, plus a top-level ``timestamp``.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set, Tuple

from .models import UsageRecord
from .util import parse_ts


def parse_claude(logs_dir: str, since: Optional[datetime] = None) -> List[UsageRecord]:
    base = Path(os.path.expanduser(logs_dir))
    records: List[UsageRecord] = []
    if not base.exists():
        return records

    seen: Set[Tuple[str, str]] = set()
    for path in base.rglob("*.jsonl"):
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
                    if not isinstance(obj, dict) or obj.get("type") != "assistant":
                        continue
                    message = obj.get("message")
                    if not isinstance(message, dict):
                        continue
                    usage = message.get("usage")
                    if not isinstance(usage, dict):
                        continue

                    # De-dupe replayed messages across resumed sessions.
                    dedup = (
                        str(message.get("id", "")),
                        str(obj.get("requestId", "")),
                    )
                    if dedup != ("", "") and dedup in seen:
                        continue
                    seen.add(dedup)

                    ts = parse_ts(obj.get("timestamp"))
                    if since is not None and ts is not None and ts < since:
                        continue

                    records.append(
                        UsageRecord(
                            timestamp=ts,
                            source="claude",
                            model=str(message.get("model") or "claude"),
                            input_tokens=int(usage.get("input_tokens", 0) or 0),
                            output_tokens=int(usage.get("output_tokens", 0) or 0),
                            cache_creation_tokens=int(
                                usage.get("cache_creation_input_tokens", 0) or 0
                            ),
                            cache_read_tokens=int(
                                usage.get("cache_read_input_tokens", 0) or 0
                            ),
                        )
                    )
        except OSError:
            continue
    return records
