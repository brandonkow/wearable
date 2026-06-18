"""Configuration loading: defaults, JSON file, and environment overrides."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional

DEFAULT_CONFIG = {
    "ntfy": {
        "server": "https://ntfy.sh",
        "topic": "",
        "token": None,
        "priority": "low",
    },
    "bar_width": 8,
    "claude": {"enabled": True, "usage_cache": "~/.claude/usage-cache.json"},
    "codex": {"enabled": True, "sessions_dir": "~/.codex/sessions"},
}


@dataclass
class Config:
    ntfy_server: str
    ntfy_topic: str
    ntfy_token: Optional[str]
    ntfy_priority: str
    bar_width: int
    claude_enabled: bool
    claude_usage_cache: str
    codex_enabled: bool
    codex_sessions_dir: str


def _deep_merge(base: dict, override: dict) -> dict:
    out = dict(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_config(path: Optional[str] = None) -> Config:
    data = dict(DEFAULT_CONFIG)
    if path and os.path.exists(os.path.expanduser(path)):
        with open(os.path.expanduser(path), "r", encoding="utf-8") as fh:
            data = _deep_merge(data, json.load(fh))

    # Environment overrides (handy for cron / secrets).
    ntfy = data["ntfy"]
    if os.environ.get("NTFY_SERVER"):
        ntfy["server"] = os.environ["NTFY_SERVER"]
    if os.environ.get("NTFY_TOPIC"):
        ntfy["topic"] = os.environ["NTFY_TOPIC"]
    if os.environ.get("NTFY_TOKEN"):
        ntfy["token"] = os.environ["NTFY_TOKEN"]

    return Config(
        ntfy_server=ntfy["server"],
        ntfy_topic=ntfy.get("topic", ""),
        ntfy_token=ntfy.get("token"),
        ntfy_priority=ntfy.get("priority", "low"),
        bar_width=int(data.get("bar_width", 8)),
        claude_enabled=bool(data["claude"].get("enabled", True)),
        claude_usage_cache=data["claude"].get("usage_cache", "~/.claude/usage-cache.json"),
        codex_enabled=bool(data["codex"].get("enabled", True)),
        codex_sessions_dir=data["codex"].get("sessions_dir", "~/.codex/sessions"),
    )
