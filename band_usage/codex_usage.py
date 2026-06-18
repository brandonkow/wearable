"""Parse OpenAI Codex CLI session logs (``~/.codex/sessions/**/*.jsonl``).

Codex rollout files contain ``token_count`` events whose ``info`` carries both
a cumulative ``total_token_usage`` and a per-turn ``last_token_usage``. We sum
the per-turn deltas (which are window-friendly) when present, and otherwise
fall back to the final cumulative total for the session.

The exact schema has shifted across Codex versions, so the token blocks and
model name are located with a tolerant depth-first search.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import UsageRecord
from .util import find_key, parse_ts


def _record_from_usage(
    ts: Optional[datetime], model: str, usage: Dict[str, Any]
) -> UsageRecord:
    # In OpenAI accounting, ``input_tokens`` includes the cached portion, so we
    # split it out to price cached reads correctly.
    total_input = int(usage.get("input_tokens", 0) or 0)
    cached = int(usage.get("cached_input_tokens", 0) or 0)
    fresh_input = max(0, total_input - cached)
    output = int(usage.get("output_tokens", 0) or 0)
    return UsageRecord(
        timestamp=ts,
        source="codex",
        model=model,
        input_tokens=fresh_input,
        output_tokens=output,
        cache_creation_tokens=0,
        cache_read_tokens=cached,
    )


def parse_codex(
    logs_dir: str,
    since: Optional[datetime] = None,
    default_model: str = "gpt-5-codex",
) -> List[UsageRecord]:
    base = Path(os.path.expanduser(logs_dir))
    records: List[UsageRecord] = []
    if not base.exists():
        return records

    for path in sorted(base.rglob("*.jsonl")):
        try:
            file_ts = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        except OSError:
            file_ts = None

        model = default_model
        saw_delta = False
        final_total: Optional[Dict[str, Any]] = None
        final_total_ts: Optional[datetime] = file_ts

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

                    found_model = find_key(obj, "model")
                    if isinstance(found_model, str) and found_model:
                        model = found_model

                    ts = parse_ts(find_key(obj, "timestamp")) or file_ts

                    last = find_key(obj, "last_token_usage")
                    if isinstance(last, dict):
                        saw_delta = True
                        rec = _record_from_usage(ts, model, last)
                        if since is None or rec.timestamp is None or rec.timestamp >= since:
                            records.append(rec)

                    total = find_key(obj, "total_token_usage")
                    if isinstance(total, dict):
                        final_total = total
                        final_total_ts = ts
        except OSError:
            continue

        # No per-turn deltas in this file: use the final cumulative total.
        if not saw_delta and final_total is not None:
            rec = _record_from_usage(final_total_ts, model, final_total)
            if since is None or rec.timestamp is None or rec.timestamp >= since:
                records.append(rec)

    return records
